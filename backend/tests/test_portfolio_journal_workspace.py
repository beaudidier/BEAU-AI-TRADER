from pathlib import Path

from paper_trading.engine import build_portfolio_summary
from saas.router import PaperTradeJournalUpdate


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
