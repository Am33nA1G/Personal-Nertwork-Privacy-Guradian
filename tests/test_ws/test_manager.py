"""Tests for the WebSocket manager."""

import unittest.mock as mock

import pytest


def _make_ws():
    ws = mock.AsyncMock()
    ws.accept = mock.AsyncMock(return_value=None)
    ws.send_json = mock.AsyncMock(return_value=None)
    ws.close = mock.AsyncMock(return_value=None)
    return ws


@pytest.mark.asyncio
async def test_connect_adds_client():
    from pnpg.ws.manager import WsManager

    manager = WsManager()
    ws = _make_ws()

    await manager.connect(ws)

    assert manager.client_count == 1


@pytest.mark.asyncio
async def test_disconnect_removes_client():
    from pnpg.ws.manager import WsManager

    manager = WsManager()
    ws = _make_ws()
    await manager.connect(ws)

    manager.disconnect(ws)

    assert manager.client_count == 0


@pytest.mark.asyncio
async def test_disconnect_unknown_ws_no_error():
    from pnpg.ws.manager import WsManager

    manager = WsManager()
    ws = _make_ws()

    manager.disconnect(ws)

    assert manager.client_count == 0


@pytest.mark.asyncio
async def test_broadcast_adds_to_queue():
    from pnpg.ws.manager import WsManager

    manager = WsManager()
    ws = _make_ws()
    await manager.connect(ws)

    await manager.broadcast({"connections": [{"process_name": "chrome.exe"}], "alerts": []})

    assert len(manager._clients[ws]["queue"]) == 1


@pytest.mark.asyncio
async def test_flush_sends_batch():
    from pnpg.ws.manager import WsManager

    manager = WsManager()
    ws = _make_ws()
    await manager.connect(ws)

    await manager.broadcast({"connections": [{"seq": 1}], "alerts": []})
    await manager.broadcast({"connections": [{"seq": 2}], "alerts": []})
    await manager.broadcast({"connections": [{"seq": 3}], "alerts": []})

    await manager._flush_once()

    ws.send_json.assert_awaited()
    sent = ws.send_json.await_args.args[0]
    assert sent["type"] == "batch"
    assert len(sent["events"]) == 3


@pytest.mark.asyncio
async def test_flush_drops_bad_client():
    from pnpg.ws.manager import WsManager

    manager = WsManager()
    ws = _make_ws()
    ws.send_json.side_effect = RuntimeError("boom")
    await manager.connect(ws)
    await manager.broadcast({"connections": [{"seq": 1}], "alerts": []})

    await manager._flush_once()

    assert manager.client_count == 0


@pytest.mark.asyncio
async def test_batch_capped_at_max():
    from pnpg.ws.manager import WsManager

    manager = WsManager(max_batch=2)
    ws = _make_ws()
    await manager.connect(ws)

    for seq in range(5):
        await manager.broadcast({"connections": [{"seq": seq}], "alerts": []})

    assert len(manager._clients[ws]["queue"]) == 2


@pytest.mark.asyncio
async def test_set_filter():
    from pnpg.ws.manager import WsManager

    manager = WsManager()
    ws = _make_ws()
    await manager.connect(ws)

    manager.set_filter(ws, {"process": "chrome.exe"})

    assert manager._clients[ws]["filter"] == {"process": "chrome.exe"}


@pytest.mark.asyncio
async def test_heartbeat_sends_message():
    from pnpg.ws.manager import WsManager

    manager = WsManager()
    ws = _make_ws()
    await manager.connect(ws)

    await manager._heartbeat_once()

    ws.send_json.assert_awaited()
    payload = ws.send_json.await_args.args[0]
    assert payload["type"] == "heartbeat"


@pytest.mark.asyncio
async def test_start_creates_background_tasks():
    from pnpg.ws.manager import WsManager

    manager = WsManager()

    await manager.start()

    assert manager._batch_task is not None
    assert not manager._batch_task.done()
    assert manager._heartbeat_task is not None
    assert not manager._heartbeat_task.done()

    # Cleanup
    await manager.stop()


@pytest.mark.asyncio
async def test_start_idempotent():
    """Calling start() twice reuses existing tasks if they are still running."""
    from pnpg.ws.manager import WsManager

    manager = WsManager()
    await manager.start()
    first_batch_task = manager._batch_task

    await manager.start()

    assert manager._batch_task is first_batch_task

    await manager.stop()


@pytest.mark.asyncio
async def test_stop_cancels_tasks_and_closes_clients():
    from pnpg.ws.manager import WsManager

    manager = WsManager()
    ws = _make_ws()
    await manager.start()
    await manager.connect(ws)
    assert manager.client_count == 1

    await manager.stop()

    assert manager._batch_task is None
    assert manager._heartbeat_task is None
    assert manager.client_count == 0
    ws.close.assert_awaited()


@pytest.mark.asyncio
async def test_stop_handles_ws_close_error():
    """stop() continues even when ws.close() raises."""
    from pnpg.ws.manager import WsManager

    manager = WsManager()
    ws = _make_ws()
    ws.close.side_effect = RuntimeError("already closed")
    await manager.start()
    await manager.connect(ws)

    await manager.stop()  # Must not raise

    assert manager.client_count == 0


@pytest.mark.asyncio
async def test_broadcast_filter_no_matching_conns_no_alerts_skips():
    """broadcast with process filter: no matching connections and no alerts — client skipped."""
    from pnpg.ws.manager import WsManager

    manager = WsManager()
    ws = _make_ws()
    await manager.connect(ws)
    manager.set_filter(ws, {"process": "chrome.exe"})

    await manager.broadcast(
        {"connections": [{"process_name": "firefox.exe"}], "alerts": []}
    )

    # Nothing should be enqueued because filter excluded all connections and no alerts
    assert len(manager._clients[ws]["queue"]) == 0


@pytest.mark.asyncio
async def test_broadcast_filter_with_alerts_passes():
    """broadcast with process filter: no matching connections but there are alerts — payload passed."""
    from pnpg.ws.manager import WsManager

    manager = WsManager()
    ws = _make_ws()
    await manager.connect(ws)
    manager.set_filter(ws, {"process": "chrome.exe"})

    await manager.broadcast(
        {
            "connections": [{"process_name": "firefox.exe"}],
            "alerts": [{"alert_id": "1"}],
        }
    )

    assert len(manager._clients[ws]["queue"]) == 1
    queued = manager._clients[ws]["queue"][0]
    assert queued["alerts"] == [{"alert_id": "1"}]
    assert queued["connections"] == []


@pytest.mark.asyncio
async def test_broadcast_filter_matching_connection_passes():
    """broadcast with process filter: matching connection is included in payload."""
    from pnpg.ws.manager import WsManager

    manager = WsManager()
    ws = _make_ws()
    await manager.connect(ws)
    manager.set_filter(ws, {"process": "chrome.exe"})

    await manager.broadcast(
        {
            "connections": [
                {"process_name": "chrome.exe"},
                {"process_name": "firefox.exe"},
            ],
            "alerts": [],
        }
    )

    assert len(manager._clients[ws]["queue"]) == 1
    queued = manager._clients[ws]["queue"][0]
    assert len(queued["connections"]) == 1
    assert queued["connections"][0]["process_name"] == "chrome.exe"


@pytest.mark.asyncio
async def test_heartbeat_drops_failed_client():
    """_heartbeat_once removes clients that fail to receive the heartbeat."""
    from pnpg.ws.manager import WsManager

    manager = WsManager()
    ws = _make_ws()
    ws.send_json.side_effect = RuntimeError("dead")
    await manager.connect(ws)

    await manager._heartbeat_once()

    assert manager.client_count == 0
