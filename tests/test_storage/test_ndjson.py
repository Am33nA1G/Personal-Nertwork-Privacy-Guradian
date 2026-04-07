"""Tests for NDJSON storage writer."""

import asyncio
import json

import pytest


@pytest.mark.asyncio
async def test_append_creates_file_and_writes_json_line(tmp_path):
    from pnpg.storage.ndjson import NdjsonWriter

    writer = NdjsonWriter(str(tmp_path))
    record = {"message": "hello", "count": 1}

    await writer.append("connections", record)

    path = tmp_path / "connections.ndjson"
    assert path.exists()

    content = path.read_text(encoding="utf-8")
    assert content.endswith("\n")
    assert json.loads(content) == record


@pytest.mark.asyncio
async def test_append_rotates_on_size_exceed(tmp_path):
    from pnpg.storage.ndjson import NdjsonWriter

    writer = NdjsonWriter(str(tmp_path), max_bytes=50)

    await writer.append("connections", {"payload": "x" * 40})
    await writer.append("connections", {"payload": "y" * 40})

    assert (tmp_path / "connections.ndjson.1").exists()


@pytest.mark.asyncio
async def test_append_creates_dir(tmp_path):
    from pnpg.storage.ndjson import NdjsonWriter

    log_dir = tmp_path / "nested" / "logs"
    writer = NdjsonWriter(str(log_dir))

    await writer.append("connections", {"message": "created"})

    assert log_dir.exists()
    assert (log_dir / "connections.ndjson").exists()


@pytest.mark.asyncio
async def test_flush_completes(tmp_path):
    from pnpg.storage.ndjson import NdjsonWriter

    writer = NdjsonWriter(str(tmp_path))

    await writer.flush()


@pytest.mark.asyncio
async def test_concurrent_appends(tmp_path):
    from pnpg.storage.ndjson import NdjsonWriter

    writer = NdjsonWriter(str(tmp_path))

    await asyncio.gather(
        *[
            writer.append("connections", {"index": index})
            for index in range(10)
        ]
    )

    content = (tmp_path / "connections.ndjson").read_text(encoding="utf-8")
    assert len(content.splitlines()) == 10
