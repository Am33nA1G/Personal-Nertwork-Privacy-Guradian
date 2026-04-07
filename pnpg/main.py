"""FastAPI application entry point with lifespan context manager.

The lifespan handles the full startup/shutdown sequence for PNPG:
  Startup:  load_config -> check_npcap -> check_admin -> select_interface
            -> start sniffer supervisor -> start pipeline worker
  Shutdown: set stop_event -> cancel supervisor task -> cancel worker task

CONFIG-01/02: Config loaded and validated first, before any network activity.
CAP-02:       Npcap verified at startup — hard exit if missing.
CAP-03:       Admin privileges verified at startup — hard exit if not admin.
CAP-04/09:    Interface selected (override from config, else auto-select).
CAP-10:       Sniffer supervisor started as an asyncio task.
PIPE-01:      Pipeline worker started as an asyncio task.
"""
import asyncio
import json
import logging
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from pnpg.api.auth import resolve_jwt_secret, router as auth_router
from pnpg.api.middleware import setup_rate_limiting
from pnpg.api.routes.alerts import router as alerts_router
from pnpg.api.routes.allowlist import router as allowlist_router
from pnpg.api.routes.connections import router as connections_router
from pnpg.api.routes.stats import router as stats_router
from pnpg.api.routes.status import router as status_router
from pnpg.api.routes.threats import router as threats_router
from pnpg.api.routes.ws import router as ws_router
from pnpg.capture.interface import select_interface
from pnpg.capture.sniffer import sniffer_supervisor
from pnpg.config import load_config
from pnpg.db.pool import create_pool
from pnpg.pipeline.detector import DetectorState, load_tor_exit_nodes
from pnpg.pipeline.dns_resolver import TtlLruCache
from pnpg.pipeline.geo_enricher import check_db_freshness, close_readers, open_readers
from pnpg.pipeline.process_mapper import process_poller_loop
from pnpg.pipeline.threat_intel import load_blocklist
from pnpg.pipeline.worker import pipeline_worker
from pnpg.prereqs import check_admin, check_npcap, get_probe_type
from pnpg.scheduler import setup_scheduler
from pnpg.storage.ndjson import NdjsonWriter
from pnpg.ws.manager import WsManager

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)


async def shutdown_runtime(
    stop_event,
    supervisor_task,
    poller_task,
    worker_task,
    ws_manager,
    scheduler,
    ndjson_writer,
    db_pool,
) -> None:
    """Shut down runtime components in the planned Phase 5 order."""
    stop_event.set()
    supervisor_task.cancel()
    poller_task.cancel()

    try:
        await poller_task
    except asyncio.CancelledError:
        pass

    worker_task.cancel()

    try:
        await supervisor_task
    except asyncio.CancelledError:
        pass

    try:
        await worker_task
    except asyncio.CancelledError:
        pass

    if ws_manager is not None:
        await ws_manager.stop()
    if scheduler is not None:
        scheduler.shutdown(wait=False)
    if ndjson_writer is not None:
        await ndjson_writer.flush()
    if db_pool is not None:
        await db_pool.close()

    close_readers()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown sequence.

    Startup sequence (in order):
    1. Load config (CONFIG-01/02)
    2. Check Npcap installed (CAP-02)
    3. Check admin privileges (CAP-03)
    4. Select network interface (CAP-04/09)
    5. Create asyncio.Queue with configured maxsize (CAP-05)
    6. Start sniffer supervisor task (CAP-10)
    7. Start pipeline worker task (PIPE-01)

    State stored on app.state for access by route handlers:
    - app.state.queue
    - app.state.config
    - app.state.drop_counter
    - app.state.stop_event

    Shutdown sequence:
    1. Set stop_event to signal sniffer thread
    2. Cancel supervisor and worker tasks
    3. Await both tasks (swallow CancelledError)
    """
    # 1. Load config (CONFIG-01/02)
    config = load_config()
    resolve_jwt_secret(config)

    # Phase 3: Initialize DNS cache (DNS-04, DNS-06)
    dns_cache = TtlLruCache(
        maxsize=config["dns_cache_size"],
        ttl=config["dns_cache_ttl_sec"],
    )

    # Phase 3: Open GeoIP database readers (GEO-01, GEO-02)
    open_readers(config["geoip_country_db"], config["geoip_asn_db"])

    # Phase 3: Check GeoIP database freshness (GEO-05)
    check_db_freshness(config["geoip_country_db"], 30 * 86400, "GEOIP_STALE")
    check_db_freshness(config["geoip_asn_db"], 30 * 86400, "GEOIP_STALE")

    # Phase 3: Load threat intel blocklist (THREAT-01, THREAT-02)
    load_blocklist(config["blocklist_path"])

    detector_state = DetectorState(
        tor_exit_nodes=load_tor_exit_nodes(
            config.get("tor_exit_list_path", "data/tor-exit-nodes.txt")
        )
    )
    app.state.detector_state = detector_state

    # 2. Verify Npcap is installed (CAP-02)
    check_npcap()

    # 3. Verify admin privileges (CAP-03)
    check_admin()

    # SYS-03: select the active capture probe type
    probe_type = get_probe_type()

    # 4. Select network interface (CAP-04/09)
    iface = select_interface(config)

    # 5. Shared state for sniffer <-> pipeline bridge
    loop = asyncio.get_running_loop()
    queue = asyncio.Queue(maxsize=config["queue_size"])  # CAP-05
    drop_counter = [0]
    stop_event = threading.Event()
    app.state.started_at = time.monotonic()

    db_pool = await create_pool(
        config["db_dsn"],
        config["db_pool_min"],
        config["db_pool_max"],
    )
    ndjson_writer = NdjsonWriter(
        config["log_dir"],
        config["ndjson_max_size_mb"] * 1024 * 1024,
    )

    auth_path = Path(config["auth_file"])
    if auth_path.exists():
        password_hash = json.loads(auth_path.read_text(encoding="utf-8")).get("hash")
        needs_setup = False
    else:
        password_hash = None
        needs_setup = True

    scheduler = setup_scheduler(db_pool, config, drop_counter)
    setup_rate_limiting(app)

    ws_manager = WsManager(
        batch_interval=config["ws_batch_interval_ms"] / 1000.0,
        max_batch=config["ws_max_batch_size"],
        heartbeat_interval=config["ws_heartbeat_interval_s"],
    )
    await ws_manager.start()
    app.state.ws_manager = ws_manager

    # 6. Start sniffer supervisor task (CAP-10)
    supervisor_task = asyncio.create_task(
        sniffer_supervisor(loop, queue, iface, config, drop_counter, stop_event),
        name="sniffer-supervisor",
    )

    # 6.5. Create process attribution cache and start poller (PROC-02)
    process_cache: dict = {}
    poller_task = asyncio.create_task(
        process_poller_loop(process_cache, config),
        name="process-poller",
    )

    # 7. Start pipeline worker task (PIPE-01)
    worker_task = asyncio.create_task(
        pipeline_worker(
            queue,
            config,
            process_cache,
            dns_cache,
            detector_state=detector_state,
            db_pool=db_pool,
            ndjson_writer=ndjson_writer,
            ws_manager=ws_manager,
        ),
        name="pipeline-worker",
    )

    # Expose shared state on app.state for route handlers
    app.state.queue = queue
    app.state.config = config
    app.state.db_pool = db_pool
    app.state.ndjson_writer = ndjson_writer
    app.state.password_hash = password_hash
    app.state.needs_setup = needs_setup
    app.state.drop_counter = drop_counter
    app.state.stop_event = stop_event
    app.state.process_cache = process_cache
    app.state.dns_cache = dns_cache
    app.state.detector_state = detector_state
    app.state.probe_type = probe_type
    app.state.scheduler = scheduler
    app.state.ws_manager = ws_manager

    logger.info(
        "PNPG started — interface: %s, queue_size: %d",
        iface,
        config["queue_size"],
    )

    yield  # Application runs here — FastAPI handles requests

    # --- Shutdown ---
    logger.info("PNPG shutting down...")
    await shutdown_runtime(
        stop_event,
        supervisor_task,
        poller_task,
        worker_task,
        ws_manager,
        scheduler,
        ndjson_writer,
        db_pool,
    )

    logger.info("PNPG shutdown complete.")


app = FastAPI(title="PNPG", lifespan=lifespan)
app.include_router(auth_router, prefix="/api/v1")
app.include_router(connections_router, prefix="/api/v1")
app.include_router(alerts_router, prefix="/api/v1")
app.include_router(allowlist_router, prefix="/api/v1")
app.include_router(stats_router, prefix="/api/v1")
app.include_router(status_router, prefix="/api/v1")
app.include_router(threats_router, prefix="/api/v1")
app.include_router(ws_router, prefix="/api/v1")


@app.get("/status")
async def status():
    """Health check endpoint — returns running status."""
    return {"status": "running"}
