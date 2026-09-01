from __future__ import annotations

import argparse
import os
from pathlib import Path

from day_trading.mismatch_forensics import (
    LiveBarMismatchForensics,
    write_forensic_outputs,
)

DEFAULT_SESSIONS = (
    "live-iex-20260819",
    "live-iex-20260820",
    "live-iex-20260831",
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Forensically audit finalized Alpaca IEX live bar mismatches."
    )
    parser.add_argument(
        "--recording-root",
        default=os.getenv(
            "DAY_TRADING_RECORDING_ROOT",
            "backend/data/day_trading_recordings",
        ),
    )
    parser.add_argument("--sessions", nargs="+", default=list(DEFAULT_SESSIONS))
    parser.add_argument(
        "--ledger",
        default="artifacts/live_bar_mismatch_ledger.json",
    )
    parser.add_argument(
        "--summary",
        default="artifacts/live_bar_mismatch_forensics_summary.json",
    )
    arguments = parser.parse_args()

    result = LiveBarMismatchForensics(arguments.recording_root).analyze(
        arguments.sessions
    )
    write_forensic_outputs(
        result,
        ledger_path=Path(arguments.ledger),
        summary_path=Path(arguments.summary),
    )
    print(
        f"Analysed {result['mismatch_count']} mismatches: "
        f"{result['acceptance']['verdict']}"
    )


if __name__ == "__main__":
    main()
