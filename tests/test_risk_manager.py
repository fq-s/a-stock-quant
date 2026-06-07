"""测试 risk/base.py 的 RiskManager 聚合逻辑"""

import pytest

from live.broker import Account, Position
from risk import (
    RiskManager,
    RiskContext,
    RiskRule,
    RiskDecision,
    RiskAction,
    MaxPositionRule,
    StopLossRule,
)


class _AlwaysAllow(RiskRule):
    name = "allow"
    def check_buy(self, ctx): return RiskDecision(RiskAction.ALLOW)
    def check_sell(self, ctx): return RiskDecision(RiskAction.ALLOW)
    def check_hold(self, ctx): return RiskDecision(RiskAction.ALLOW)


class _AlwaysRejectBuy(RiskRule):
    name = "reject"
    def check_buy(self, ctx):
        return RiskDecision(RiskAction.REJECT, rule="reject", reason="测试拒绝")
    def check_sell(self, ctx): return RiskDecision(RiskAction.ALLOW)
    def check_hold(self, ctx): return RiskDecision(RiskAction.ALLOW)


class _AdjustQty(RiskRule):
    name = "adjust"
    def __init__(self, qty): self.qty = qty
    def check_buy(self, ctx):
        return RiskDecision(RiskAction.ALLOW, rule="adjust",
                            reason="调整", adjusted_qty=self.qty)
    def check_sell(self, ctx): return RiskDecision(RiskAction.ALLOW)
    def check_hold(self, ctx): return RiskDecision(RiskAction.ALLOW)


class _ForceClose(RiskRule):
    name = "force"
    def check_buy(self, ctx): return RiskDecision(RiskAction.ALLOW)
    def check_sell(self, ctx): return RiskDecision(RiskAction.ALLOW)
    def check_hold(self, ctx):
        return RiskDecision(RiskAction.FORCE_CLOSE, rule="force", reason="强平")


def _ctx(quantity=1000):
    account = Account(total_assets=1_000_000, cash=1_000_000, market_value=0)
    return RiskContext(symbol="000001", price=10, quantity=quantity, account=account)


class TestEvaluateBuy:
    def test_empty_rules_allow(self):
        mgr = RiskManager()
        assert mgr.evaluate_buy(_ctx()).action == RiskAction.ALLOW

    def test_any_reject_wins(self):
        mgr = RiskManager([_AlwaysAllow(), _AlwaysRejectBuy()])
        d = mgr.evaluate_buy(_ctx())
        assert d.action == RiskAction.REJECT
        assert d.rule == "reject"

    def test_adjust_takes_min(self):
        mgr = RiskManager([_AdjustQty(800), _AdjustQty(500)])
        d = mgr.evaluate_buy(_ctx(quantity=1000))
        assert d.action == RiskAction.ALLOW
        assert d.adjusted_qty == 500

    def test_no_adjust_needed(self):
        mgr = RiskManager([_AdjustQty(2000)])
        d = mgr.evaluate_buy(_ctx(quantity=1000))
        # 1000 已小于 2000，无需调整
        assert d.action == RiskAction.ALLOW

    def test_reject_short_circuits(self):
        # 即使有 adjust，REJECT 也直接返回
        mgr = RiskManager([_AdjustQty(500), _AlwaysRejectBuy()])
        d = mgr.evaluate_buy(_ctx())
        assert d.action == RiskAction.REJECT


class TestEvaluateSell:
    def test_empty_allow(self):
        mgr = RiskManager()
        assert mgr.evaluate_sell(_ctx()).action == RiskAction.ALLOW

    def test_no_sell_check_in_buy_rules(self):
        # AlwaysRejectBuy 不影响 sell
        mgr = RiskManager([_AlwaysRejectBuy()])
        assert mgr.evaluate_sell(_ctx()).action == RiskAction.ALLOW


class TestScanPositions:
    def test_returns_force_closes(self):
        mgr = RiskManager([_AlwaysAllow(), _ForceClose()])
        results = mgr.scan_positions(_ctx())
        assert len(results) == 1
        assert results[0].action == RiskAction.FORCE_CLOSE
        assert results[0].rule == "force"

    def test_empty_when_no_close(self):
        mgr = RiskManager([_AlwaysAllow()])
        assert mgr.scan_positions(_ctx()) == []


class TestFromConfig:
    def test_default_config(self):
        cfg = {
            "max_position_pct": 0.3,
            "stop_loss_pct": 0.07,
        }
        mgr = RiskManager.from_config(cfg)
        names = [r.name for r in mgr.rules]
        assert "MaxPositionRule" in names
        assert "StopLossRule" in names
        assert "TradingTimeRule" not in names

    def test_live_adds_trading_time(self):
        mgr = RiskManager.from_config({}, is_live=True)
        names = [r.name for r in mgr.rules]
        assert "TradingTimeRule" in names
