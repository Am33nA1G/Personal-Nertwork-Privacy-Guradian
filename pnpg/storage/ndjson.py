"""NDJSON audit log writer with size-based rotation."""

import asyncio
import json
from pathlib import Path


class NdjsonWriter:
    """Append newline-delimited JSON records to named log files."""

    def __init__(self, log_dir: str, max_bytes: int = 100 * 1024 * 1024) -> None:
        self.log_dir = Path(log_dir)
        self.max_bytes = max_bytes
        self._lock = asyncio.Lock()
        self.log_dir.mkdir(parents=True, exist_ok=True)

    async def append(self, name: str, record: dict) -> None:
        path = self.log_dir / f"{name}.ndjson"
        line = json.dumps(record, default=str) + "\n"
        line_bytes = line.encode("utf-8")

        async with self._lock:
            if path.exists() and path.stat().st_size + len(line_bytes) > self.max_bytes:
                path.replace(path.with_suffix(".ndjson.1"))

            with path.open("a", encoding="utf-8") as handle:
                handle.write(line)

    async def flush(self) -> None:
        """Flush pending writes.

        Writes are immediate, so this is currently a no-op.
        """
