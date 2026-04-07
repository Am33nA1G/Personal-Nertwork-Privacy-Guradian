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
