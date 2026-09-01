from __future__ import annotations

import argparse
import asyncio
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

from day_trading.live_acceptance import LiveAcceptanceRunner
from day_trading.session import EASTERN
from providers.alpaca_market_provider import AlpacaMarketProvider

BACKEND_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = BACKEND_ROOT.parent
RECORDING_ROOT = BACKEND_ROOT / "data" / "day_trading_recordings"
ARTIFACT_PATH = (
    REPOSITORY_ROOT / "artifacts" / "live_intraday_acceptance_summary.json"
)
REPORT_PATH = (
    REPOSITORY_ROOT / "docs" / "LIVE_INTRADAY_DATA_ACCEPTANCE.md"
)


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-sessions", type=int, default=3)
    parser.add_argument("--rehearsal-seconds", type=int)
    arguments = parser.parse_args()
    load_dotenv(BACKEND_ROOT / ".env")
    runner = LiveAcceptanceRunner(
        provider=AlpacaMarketProvider(),
        recording_root=RECORDING_ROOT,
        artifact_path=ARTIFACT_PATH,
        report_path=REPORT_PATH,
    )
    if arguments.rehearsal_seconds:
        now = runner.clock()
        await runner.record_session(
            now.astimezone(EASTERN).date(),
            start=now,
            end=now + timedelta(seconds=arguments.rehearsal_seconds),
            reconnect_after_seconds=max(5, arguments.rehearsal_seconds / 2),
            rehearsal=True,
        )
        return 0
    await runner.run_until_complete(
        target_sessions=max(3, arguments.target_sessions)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
