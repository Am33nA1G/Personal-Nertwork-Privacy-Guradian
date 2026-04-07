"""Synthetic load generator for PNPG (TEST-02).

Usage:
    python tools/load_generator.py --rate 100 --duration 10 --base-url http://localhost:8000 --token <jwt>
"""

import argparse
import asyncio
import time

import httpx


async def run_load(rate: int, duration: int, base_url: str, token: str) -> None:
    """Send authenticated GET requests at an approximate fixed rate."""
    interval = 1.0 / rate
    end_time = time.monotonic() + duration
    sent = 0
    errors = 0

    async with httpx.AsyncClient(base_url=base_url) as client:
        headers = {"Authorization": f"Bearer {token}"}
        while time.monotonic() < end_time:
            start = time.monotonic()
            try:
                response = await client.get(
                    "/api/v1/connections?page_size=1",
                    headers=headers,
                )
                if response.status_code == 200:
                    sent += 1
                else:
                    errors += 1
            except Exception:  # noqa: BLE001
                errors += 1

            elapsed = time.monotonic() - start
            sleep_time = max(0.0, interval - elapsed)
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)

    print(f"Load test complete: {sent} successful, {errors} errors in {duration}s")
    print(f"Effective rate: {sent / duration:.1f} req/s")


def main() -> None:
    """Parse CLI arguments and run the load test."""
    parser = argparse.ArgumentParser(description="PNPG load generator (TEST-02)")
    parser.add_argument("--rate", type=int, default=100, help="Requests per second")
    parser.add_argument("--duration", type=int, default=10, help="Duration in seconds")
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="API base URL",
    )
    parser.add_argument("--token", required=True, help="JWT access token")
    args = parser.parse_args()
    asyncio.run(run_load(args.rate, args.duration, args.base_url, args.token))


if __name__ == "__main__":
    main()
