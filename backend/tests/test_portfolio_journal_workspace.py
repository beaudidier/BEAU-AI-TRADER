from pathlib import Path

from paper_trading.engine import build_portfolio_summary
from fastapi import HTTPException
from saas.auth import CurrentUser
from saas.router import (
    PaperTradeJournalUpdate,
    get_paper_trade,
    update_paper_trade_journal,
)


def test_portfolio_summary_adds_workspace_values_without_changing_risk_inputs():
    trade = {
        "id": "trade-1", "ticker": "MSFT", "side": "BUY", "status": "OPEN",
        "entry_price": 100, "stop_loss": 95, "target_1": 110, "target_2": 115,
        "quantity": 10, "opened_at": "2026-07-28T10:00:00Z",
        "initial_risk_amount": 50, "initial_risk_r": 0.5,
    }
    summary = build_portfolio_summary(
        {"initial_balance": 10_000, "cash_balance": 9_000},
        [trade], [], {"MSFT": {"price": 105, "previous_close": 104, "timestamp": "2026-07-28T12:00:00Z"}},
    )
    position = summary["open_positions"][0]
    assert summary["portfolio_balance"] == 10_050
    assert summary["open_position_value"] == 1_050
    assert position["unrealized_pnl"] == 50
    assert position["unrealized_r"] == 1
    assert position["initial_risk_amount"] == 50
    assert position["initial_risk_r"] == 0.5
    assert position["stop_loss"] == 95
    assert position["target_1"] == 110
    assert position["target_2"] == 115


def test_journal_payload_never_accepts_user_or_trading_fields():
    fields = PaperTradeJournalUpdate.model_fields
    assert "user_id" not in fields
    assert "entry_price" not in fields
    assert "stop_loss" not in fields
    assert "target_1" not in fields
    assert "target_2" not in fields
    update = PaperTradeJournalUpdate(
        setup_tags=[" breakout ", "breakout", ""],
        mistake_tags=["late entry"],
        emotion_tags=["calm"],
        confidence_before=70,
        review_completed=True,
    ).safe_update()
    assert update["setup_tags"] == ["breakout"]
    assert update["confidence_before"] == 70
    assert "journal_updated_at" in update


def test_journal_migration_preserves_owner_rls_and_routes_scope_user():
    root = Path(__file__).parents[2]
    migration = (root / "supabase/migrations/202607280001_portfolio_journal_workspace.sql").read_text()
    router = (root / "backend/saas/router.py").read_text()
    assert 'Existing "paper trades own records" RLS policy remains authoritative' in migration
    assert '.eq("id", trade_id).eq("user_id", user.id)' in router
    assert "payload.safe_update()" in router


class _Response:
    def __init__(self, data):
        self.data = data


class _OwnedQuery:
    def __init__(self, rows, operation="select", values=None):
        self.rows = rows
        self.operation = operation
        self.values = values
        self.filters = []

    def select(self, *_args): return self
    def update(self, values):
        self.operation, self.values = "update", values
        return self
    def eq(self, key, value):
        self.filters.append((key, value))
        return self
    def maybe_single(self): return self
    def execute(self):
        matches = [row for row in self.rows if all(row.get(key) == value for key, value in self.filters)]
        if self.operation == "update":
            for row in matches:
                row.update(self.values)
            return _Response(matches)
        return _Response(matches[0] if matches else None)


class _OwnedClient:
    def __init__(self, rows): self.rows = rows
    def table(self, name):
        assert name == "paper_trades"
        return _OwnedQuery(self.rows)


def test_two_users_cannot_read_or_update_each_others_journal(monkeypatch):
    rows = [
        {"id": "trade-a", "user_id": "user-a", "ticker": "AAPL", "journal_notes": "A"},
        {"id": "trade-b", "user_id": "user-b", "ticker": "MSFT", "journal_notes": "B"},
    ]
    client = _OwnedClient(rows)
    monkeypatch.setattr("saas.router._client", lambda _user: client)
    user_a = CurrentUser("user-a", "a@example.com", "token-a")
    user_b = CurrentUser("user-b", "b@example.com", "token-b")

    assert get_paper_trade("trade-a", user_a)["ticker"] == "AAPL"
    for caller, foreign_id in ((user_a, "trade-b"), (user_b, "trade-a")):
        try:
            get_paper_trade(foreign_id, caller)
        except HTTPException as error:
            assert error.status_code == 404
        else:
            raise AssertionError("Cross-user read must fail closed")
        try:
            update_paper_trade_journal(
                foreign_id, PaperTradeJournalUpdate(journal_notes="hijack"), caller
            )
        except HTTPException as error:
            assert error.status_code == 404
        else:
            raise AssertionError("Cross-user update must fail closed")
    assert rows[0]["journal_notes"] == "A"
    assert rows[1]["journal_notes"] == "B"


def test_client_user_id_and_trading_fields_are_ignored():
    payload = PaperTradeJournalUpdate.model_validate({
        "journal_notes": "safe",
        "user_id": "attacker",
        "entry_price": 1,
        "stop_loss": 0.5,
        "target_1": 999,
    })
    update = payload.safe_update()
    assert update["journal_notes"] == "safe"
    assert "user_id" not in update
    assert "entry_price" not in update
    assert "stop_loss" not in update
    assert "target_1" not in update


def test_unsafe_reference_scheme_is_rejected():
    try:
        PaperTradeJournalUpdate(screenshot_url="javascript:alert(1)").safe_update()
    except ValueError as error:
        assert "http" in str(error)
    else:
        raise AssertionError("Unsafe reference URL must be rejected")
