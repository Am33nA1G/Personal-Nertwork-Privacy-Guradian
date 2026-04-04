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
import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI

from pnpg.capture.interface import select_interface
from pnpg.capture.sniffer import sniffer_supervisor
from pnpg.config import load_config
from pnpg.pipeline.dns_resolver import TtlLruCache
from pnpg.pipeline.geo_enricher import check_db_freshness, close_readers, open_readers
from pnpg.pipeline.process_mapper import process_poller_loop
from pnpg.pipeline.threat_intel import load_blocklist
from pnpg.pipeline.worker import pipeline_worker
from pnpg.prereqs import check_admin, check_npcap, get_probe_type

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)


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
        pipeline_worker(queue, config, process_cache, dns_cache),
        name="pipeline-worker",
    )

    # Expose shared state on app.state for route handlers
    app.state.queue = queue
    app.state.config = config
    app.state.drop_counter = drop_counter
    app.state.stop_event = stop_event
    app.state.process_cache = process_cache
    app.state.dns_cache = dns_cache
    app.state.probe_type = probe_type

    logger.info(
        "PNPG started — interface: %s, queue_size: %d",
        iface,
        config["queue_size"],
    )

    yield  # Application runs here — FastAPI handles requests

    # --- Shutdown ---
    logger.info("PNPG shutting down...")
    stop_event.set()
    supervisor_task.cancel()

    # Cancel poller before worker so worker can still read cache during queue drain
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

    # Phase 3: Close GeoIP readers
    close_readers()

    logger.info("PNPG shutdown complete.")


app = FastAPI(title="PNPG", lifespan=lifespan)


@app.get("/status")
async def status():
    """Health check endpoint — returns running status."""
    return {"status": "running"}
