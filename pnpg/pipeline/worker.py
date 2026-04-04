"""Async pipeline worker — consumes packet events from asyncio.Queue.

PIPE-01: Async pipeline worker consuming queue in a single coroutine.
PIPE-02: Single asyncio.Queue guarantees FIFO order by design.
PIPE-03: All blocking operations (future: DNS, process mapping) dispatched via
         loop.run_in_executor() with ThreadPoolExecutor — never blocks event loop.
TEST-01: debug_mode=True logs each pipeline event at DEBUG level.
CONFIG-03/SYS-01: Critical errors are caught and logged; worker continues.
"""
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor

from pnpg.pipeline.dns_resolver import TtlLruCache, enrich_dns
from pnpg.pipeline.geo_enricher import enrich_geo
from pnpg.pipeline.process_mapper import enrich_event
from pnpg.pipeline.threat_intel import check_threat_intel


logger = logging.getLogger(__name__)


async def pipeline_worker(
    queue: asyncio.Queue,
    config: dict,
    process_cache: dict,
    dns_cache: TtlLruCache,
) -> None:
    """Consume packet events from the queue and route them through enrichment stages.

    The worker runs until cancelled. On each iteration it:
    1. Awaits an event from the queue (FIFO order — PIPE-02).
    2. Enriches the event with process attribution via enrich_event (PROC-01/PROC-05).
    3. Passes the event through enrichment stage stubs (Phase 3-5 placeholders).
    4. Logs the event at DEBUG level if debug_mode is enabled (TEST-01).
    5. Handles any processing exception via logging.critical without crashing
       (CONFIG-03/SYS-01).
    6. Calls queue.task_done() in the finally block to unblock queue.join().

    The ThreadPoolExecutor is created once and reused across iterations so
    future blocking stages (DNS) can use run_in_executor without creating a
    new pool per event (PIPE-03).

    Args:
        queue:         The bounded asyncio.Queue fed by the sniffer queue bridge.
        config:        Config dict (from load_config()). Checked for 'debug_mode'.
        process_cache: Shared process attribution cache dict populated by
                       process_poller_loop. Passed to enrich_event each iteration.
    """
    executor = ThreadPoolExecutor(max_workers=16)
    loop = asyncio.get_running_loop()

    while True:
        try:
            event = await queue.get()
        except asyncio.CancelledError:
            break

        try:
            # Phase 2: Process attribution (PROC-01/PROC-05)
            event = enrich_event(event, process_cache)

            # Phase 3: DNS resolution (DNS-01..06) - async, uses thread pool
            event = await enrich_dns(event, dns_cache, executor, loop)

            # Phase 3: GeoIP + ASN enrichment (GEO-01..05) - synchronous, local memory
            event = enrich_geo(event)

            # Phase 3: Threat intel check (THREAT-01..05) - synchronous, frozenset lookup
            event = check_threat_intel(event)

            # Phase 4: alerts = detection_engine(event, config)
            # Phase 5: storage_writer(event)
            # Phase 5: websocket_push(event)

            if config.get("debug_mode"):
                logger.debug("PIPELINE EVENT: %s", event)  # TEST-01

        except asyncio.CancelledError:
            # Re-raise so the task can be cancelled cleanly
            queue.task_done()
            raise
        except Exception as exc:  # noqa: BLE001
            logger.critical(
                "Pipeline worker error: %s", exc, exc_info=True
            )  # CONFIG-03 / SYS-01
        finally:
            queue.task_done()
