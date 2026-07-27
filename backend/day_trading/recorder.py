from __future__ import annotations

import gzip
import hashlib
import json
import os
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import RLock
from typing import Any
from uuid import uuid4

from .session import EASTERN, as_utc

EVENT_TYPES = {
    "t": "trade",
    "q": "quote",
    "b": "bar_1m",
    "success": "stream_control",
    "subscription": "stream_control",
    "error": "stream_error",
}
SAFE_FIELDS = {
    "T",
    "S",
    "t",
    "p",
    "s",
    "x",
    "c",
    "i",
    "z",
    "bp",
    "ap",
    "bs",
    "as",
    "bx",
    "ax",
    "o",
    "h",
    "l",
    "v",
    "vw",
    "n",
    "seq",
    "sequence",
}
SECRET_KEY_MARKERS = {
    "api_key",
    "apikey",
    "authorization",
    "password",
    "secret",
    "token",
}


def _canonical(value: dict[str, Any]) -> bytes:
    return (
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode()


def _iso(value: datetime | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return as_utc(value).isoformat()
    return str(value)


def _contains_secret_key(value: Any) -> bool:
    if isinstance(value, dict):
        for key, nested in value.items():
            normalized = str(key).lower()
            if any(marker in normalized for marker in SECRET_KEY_MARKERS):
                return True
            if _contains_secret_key(nested):
                return True
    elif isinstance(value, list):
        return any(_contains_secret_key(item) for item in value)
    return False


@dataclass
class RecordingMetadata:
    session_id: str
    status: str
    symbols: list[str]
    source: str
    coverage: str
    started_at: str
    market_date: str
    completed_at: str | None = None
    event_count: int = 0
    event_counts: dict[str, int] = field(default_factory=dict)
    symbol_counts: dict[str, int] = field(default_factory=dict)
    duplicate_events: int = 0
    out_of_order_events: int = 0
    gaps: list[dict[str, Any]] = field(default_factory=list)
    checksum_sha256: str | None = None
    compressed_file: str = ""
    secrets_present: bool = False
    blocked_sensitive_events: int = 0
    recovered: bool = False


class IntradayRecorder:
    """Append-only gzip recorder for local/staging market-data research."""

    def __init__(self, root: str | Path):
        self.root = Path(root).expanduser().resolve()
        self._lock = RLock()
        self._writer: Any | None = None
        self._metadata: RecordingMetadata | None = None
        self._data_path: Path | None = None
        self._meta_path: Path | None = None
        self._hasher = hashlib.sha256()
        self._last_provider_timestamp: dict[tuple[str, str], datetime] = {}
        self._last_sequence: dict[tuple[str, str], int] = {}

    @property
    def active(self) -> bool:
        return self._writer is not None and self._metadata is not None

    def start(
        self,
        *,
        symbols: list[str],
        source: str,
        coverage: str,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            if self.active:
                raise RuntimeError("An intraday recording is already active.")
            now = datetime.now(timezone.utc)
            clean_symbols = sorted(
                {value.strip().upper() for value in symbols if value.strip()}
            )
            if not clean_symbols:
                raise ValueError("At least one recording symbol is required.")
            if session_id is not None and not re.fullmatch(
                r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}",
                session_id,
            ):
                raise ValueError("Recording session id is invalid.")
            recoverable = (
                self._find_recoverable(clean_symbols, source, coverage)
                if session_id is None
                else None
            )
            identifier = (
                recoverable[1]["session_id"]
                if recoverable
                else session_id
                or f"{now:%Y%m%dT%H%M%SZ}-{uuid4().hex[:8]}"
            )
            if recoverable:
                self._meta_path = recoverable[0]
                partition = self._meta_path.parent
                self._data_path = partition / recoverable[1]["compressed_file"]
            else:
                partition = (
                    self.root
                    / now.astimezone(EASTERN).date().isoformat()
                )
                partition.mkdir(parents=True, exist_ok=True)
                self._data_path = partition / f"{identifier}.jsonl.gz"
                self._meta_path = partition / f"{identifier}.meta.json"
            recovered = self._data_path.exists()
            self._hasher = hashlib.sha256()
            existing_count = 0
            existing_counts: dict[str, int] = {}
            existing_symbol_counts: dict[str, int] = {}
            if recovered:
                with gzip.open(
                    self._data_path,
                    "rt",
                    encoding="utf-8",
                ) as existing:
                    for line in existing:
                        encoded = line.encode()
                        self._hasher.update(encoded)
                        event = json.loads(line)
                        existing_count += 1
                        kind = str(event.get("event_type", "unknown"))
                        existing_counts[kind] = existing_counts.get(kind, 0) + 1
                        symbol = event.get("symbol")
                        if symbol:
                            existing_symbol_counts[symbol] = (
                                existing_symbol_counts.get(symbol, 0) + 1
                            )
            self._metadata = RecordingMetadata(
                session_id=identifier,
                status="recording",
                symbols=clean_symbols,
                source=source,
                coverage=coverage,
                started_at=(
                    str(recoverable[1]["started_at"])
                    if recoverable
                    else now.isoformat()
                ),
                market_date=partition.name,
                event_count=existing_count,
                event_counts=existing_counts,
                symbol_counts=existing_symbol_counts,
                duplicate_events=int(
                    recoverable[1].get("duplicate_events", 0)
                    if recoverable
                    else 0
                ),
                out_of_order_events=int(
                    recoverable[1].get("out_of_order_events", 0)
                    if recoverable
                    else 0
                ),
                gaps=list(
                    recoverable[1].get("gaps", [])
                    if recoverable
                    else []
                ),
                blocked_sensitive_events=int(
                    recoverable[1].get(
                        "blocked_sensitive_events",
                        0,
                    )
                    if recoverable
                    else 0
                ),
                compressed_file=self._data_path.name,
                recovered=recovered,
            )
            self._writer = gzip.open(
                self._data_path,
                "at",
                encoding="utf-8",
                compresslevel=6,
            )
            self._write_metadata()
            self.record_system(
                "recording_resumed" if recovered else "recording_started",
                {
                    "symbols": clean_symbols,
                    "source": source,
                    "coverage": coverage,
                    "recovered": recovered,
                },
                occurred_at=now,
            )
            return self.status()

    def _find_recoverable(
        self,
        symbols: list[str],
        source: str,
        coverage: str,
    ) -> tuple[Path, dict[str, Any]] | None:
        if not self.root.exists():
            return None
        for path in sorted(
            self.root.glob("*/*.meta.json"),
            reverse=True,
        ):
            market_date = datetime.now(timezone.utc).astimezone(EASTERN).date()
            if path.parent.name != market_date.isoformat():
                continue
            try:
                metadata = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if (
                metadata.get("status") == "recording"
                and metadata.get("symbols") == symbols
                and metadata.get("source") == source
                and metadata.get("coverage") == coverage
            ):
                return path, metadata
        return None

    def _append(self, event: dict[str, Any]) -> None:
        if not self.active or self._metadata is None or self._writer is None:
            return
        if _contains_secret_key(event):
            self._metadata.blocked_sensitive_events += 1
            raise ValueError("Sensitive fields cannot be recorded.")
        event["index"] = self._metadata.event_count
        encoded = _canonical(event)
        self._writer.write(encoded.decode())
        self._writer.flush()
        self._hasher.update(encoded)
        self._metadata.event_count += 1
        kind = str(event["event_type"])
        self._metadata.event_counts[kind] = (
            self._metadata.event_counts.get(kind, 0) + 1
        )
        symbol = event.get("symbol")
        if symbol:
            self._metadata.symbol_counts[symbol] = (
                self._metadata.symbol_counts.get(symbol, 0) + 1
            )
        if self._metadata.event_count % 1_000 == 0:
            file_object = getattr(
                getattr(self._writer, "buffer", None),
                "fileobj",
                None,
            )
            if file_object is not None:
                os.fsync(file_object.fileno())
            self._metadata.checksum_sha256 = self._hasher.hexdigest()
            self._write_metadata()

    def record_raw(
        self,
        raw: dict[str, Any],
        *,
        received_at: datetime,
        disposition: str = "received",
    ) -> None:
        if not self.active:
            return
        with self._lock:
            kind_code = str(raw.get("T", "unknown"))
            kind = EVENT_TYPES.get(kind_code, f"unknown_{kind_code}")
            if disposition == "duplicate" and self._metadata:
                self._metadata.duplicate_events += 1
            symbol = str(raw.get("S", "")).upper() or None
            provider_timestamp = _iso(raw.get("t"))
            sequence_value = raw.get("sequence", raw.get("seq"))
            sequence = (
                int(sequence_value)
                if isinstance(sequence_value, (int, float))
                else None
            )
            payload = {
                key: value
                for key, value in raw.items()
                if key in SAFE_FIELDS
            }
            key = (symbol or "", kind)
            if provider_timestamp:
                current = as_utc(datetime.fromisoformat(
                    provider_timestamp.replace("Z", "+00:00")
                ))
                previous = self._last_provider_timestamp.get(key)
                if previous and current < previous:
                    if self._metadata:
                        self._metadata.out_of_order_events += 1
                if (
                    kind == "bar_1m"
                    and previous
                    and current - previous > timedelta(minutes=1)
                    and self._metadata
                ):
                    self._metadata.gaps.append(
                        {
                            "symbol": symbol,
                            "event_type": kind,
                            "from": (
                                previous
                                + timedelta(minutes=1)
                            ).isoformat(),
                            "to": (
                                current
                                - timedelta(minutes=1)
                            ).isoformat(),
                        }
                    )
                if previous is None or current >= previous:
                    self._last_provider_timestamp[key] = current
            if sequence is not None:
                previous_sequence = self._last_sequence.get(key)
                if (
                    previous_sequence is not None
                    and sequence > previous_sequence + 1
                    and self._metadata
                ):
                    self._metadata.gaps.append(
                        {
                            "symbol": symbol,
                            "event_type": kind,
                            "sequence_from": previous_sequence + 1,
                            "sequence_to": sequence - 1,
                        }
                    )
                self._last_sequence[key] = max(
                    sequence,
                    previous_sequence or sequence,
                )
            self._append(
                {
                    "provider_timestamp": provider_timestamp,
                    "receipt_timestamp": _iso(received_at),
                    "symbol": symbol,
                    "event_type": kind,
                    "sequence": sequence,
                    "disposition": disposition,
                    "source": (
                        self._metadata.source if self._metadata else "unknown"
                    ),
                    "coverage": (
                        self._metadata.coverage if self._metadata else "unknown"
                    ),
                    "payload": payload,
                }
            )

    def record_system(
        self,
        event_type: str,
        payload: dict[str, Any],
        *,
        occurred_at: datetime | None = None,
    ) -> None:
        if not self.active:
            return
        with self._lock:
            self._append(
                {
                    "provider_timestamp": None,
                    "receipt_timestamp": _iso(
                        occurred_at or datetime.now(timezone.utc)
                    ),
                    "symbol": None,
                    "event_type": event_type,
                    "sequence": None,
                    "disposition": "observed",
                    "source": (
                        self._metadata.source if self._metadata else "unknown"
                    ),
                    "coverage": (
                        self._metadata.coverage if self._metadata else "unknown"
                    ),
                    "payload": payload,
                }
            )

    def stop(self) -> dict[str, Any]:
        with self._lock:
            if not self.active or self._metadata is None:
                return self.status()
            completed = datetime.now(timezone.utc)
            self.record_system(
                "recording_stopped",
                {"reason": "requested"},
                occurred_at=completed,
            )
            self._writer.close()
            self._writer = None
            self._metadata.status = "completed"
            self._metadata.completed_at = completed.isoformat()
            self._metadata.checksum_sha256 = self._hasher.hexdigest()
            self._write_metadata()
            return self.status()

    def _write_metadata(self) -> None:
        if self._metadata is None or self._meta_path is None:
            return
        payload = json.dumps(
            asdict(self._metadata),
            indent=2,
            sort_keys=True,
        )
        temporary = self._meta_path.with_suffix(".tmp")
        temporary.write_text(payload + "\n", encoding="utf-8")
        os.replace(temporary, self._meta_path)

    def status(self) -> dict[str, Any]:
        with self._lock:
            if self._metadata is None:
                return {
                    "status": "idle",
                    "active": False,
                    "session_id": None,
                    "event_count": 0,
                }
            result = asdict(self._metadata)
            result["active"] = self.active
            if self.active:
                result["checksum_sha256"] = self._hasher.hexdigest()
            return result

    def sessions(self) -> list[dict[str, Any]]:
        if not self.root.exists():
            return []
        values = []
        for path in sorted(
            self.root.glob("*/*.meta.json"),
            reverse=True,
        ):
            try:
                values.append(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError):
                values.append(
                    {
                        "session_id": path.name.removesuffix(".meta.json"),
                        "status": "metadata_error",
                    }
                )
        return values

    def resolve_session(self, session_id: str) -> tuple[Path, dict[str, Any]]:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", session_id):
            raise FileNotFoundError("Recorded session was not found.")
        matches = list(self.root.glob(f"*/{session_id}.meta.json"))
        if len(matches) != 1:
            raise FileNotFoundError("Recorded session was not found.")
        metadata = json.loads(matches[0].read_text(encoding="utf-8"))
        data_path = matches[0].with_name(metadata["compressed_file"])
        return data_path, metadata

    def verify(self, session_id: str) -> dict[str, Any]:
        data_path, metadata = self.resolve_session(session_id)
        hasher = hashlib.sha256()
        count = 0
        secrets_present = False
        with gzip.open(data_path, "rt", encoding="utf-8") as source:
            for line in source:
                event = json.loads(line)
                secrets_present = (
                    secrets_present or _contains_secret_key(event)
                )
                hasher.update(line.encode())
                count += 1
        expected = metadata.get("checksum_sha256")
        return {
            "session_id": session_id,
            "event_count": count,
            "checksum_valid": bool(expected) and hasher.hexdigest() == expected,
            "secrets_present": secrets_present,
        }
