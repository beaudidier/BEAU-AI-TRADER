from __future__ import annotations

import os
from typing import Any

import httpx


class AlpacaPaperBrokerError(RuntimeError):
    pass


class AlpacaPaperBrokerClient:
    """Strictly paper-domain Alpaca adapter, disabled until explicitly enabled."""

    PAPER_BASE_URL = "https://paper-api.alpaca.markets"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        secret_key: str | None = None,
        enabled: bool | None = None,
        base_url: str | None = None,
        client: httpx.Client | None = None,
    ):
        self.api_key = api_key or os.getenv("ALPACA_API_KEY_ID", "")
        self.secret_key = secret_key or os.getenv("ALPACA_SECRET_KEY", "")
        configured_url = base_url or os.getenv(
            "ALPACA_PAPER_BASE_URL",
            self.PAPER_BASE_URL,
        )
        if configured_url.rstrip("/") != self.PAPER_BASE_URL:
            raise ValueError("Only Alpaca's paper trading domain is allowed.")
        self.base_url = self.PAPER_BASE_URL
        self.enabled = (
            enabled
            if enabled is not None
            else os.getenv("ALPACA_PAPER_API_ENABLED", "false").lower()
            == "true"
        )
        self.client = client or httpx.Client(timeout=10)

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.secret_key)

    @property
    def ready(self) -> bool:
        return self.configured and self.enabled

    @property
    def headers(self) -> dict[str, str]:
        return {
            "APCA-API-KEY-ID": self.api_key,
            "APCA-API-SECRET-KEY": self.secret_key,
        }

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        if not self.ready:
            raise AlpacaPaperBrokerError(
                "Alpaca paper execution is disabled or not configured."
            )
        response = self.client.request(
            method,
            f"{self.base_url}{path}",
            headers=self.headers,
            json=payload,
        )
        if response.status_code >= 400:
            raise AlpacaPaperBrokerError(
                f"Alpaca paper request failed ({response.status_code})."
            )
        return None if response.status_code == 204 else response.json()

    def account(self) -> dict[str, Any]:
        return self._request("GET", "/v2/account")

    def positions(self) -> list[dict[str, Any]]:
        return self._request("GET", "/v2/positions")

    def submit_order(self, payload: dict[str, Any]) -> dict[str, Any]:
        safe = {**payload, "time_in_force": payload.get("time_in_force", "day")}
        return self._request("POST", "/v2/orders", safe)

    def cancel_order(self, order_id: str) -> None:
        self._request("DELETE", f"/v2/orders/{order_id}")

    def status(self) -> dict[str, Any]:
        return {
            "provider": "Alpaca Paper Trading",
            "configured": self.configured,
            "enabled": self.enabled,
            "ready": self.ready,
            "paper_only": True,
            "base_url": self.base_url,
            "live_money_enabled": False,
        }
