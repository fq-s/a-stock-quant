"""测试 risk/rules.py 各规则"""

import pytest
import pandas as pd

from live.broker import Account, Position
from risk import (
    RiskContext,
    RiskAction,
    MaxPositionRule,
    TotalPositionRule,
    StopLossRule,
    MaxDrawdownRule,
    DailyLossRule,
)


def _ctx(symbol="000001", price=10.0, quantity=0, total_assets=1_000_000,
         cash=1_000_000, positions=None, today_open_value=1_000_000,
         initial_cash=1_000_000):
    account = Account(
        total_assets=total_assets,
        cash=cash,
        market_value=total_assets - cash,
    )
    return RiskContext(
        symbol=symbol,
        price=price,
        quantity=quantity,
        account=account,
        positions=positions or [],
        initial_cash=initial_cash,
        today_open_value=today_open_value,
    )


class TestMaxPositionRule:
    def test_allow_when_room_available(self):
        rule = MaxPositionRule(max_pct=0.3)
        # 30 万额度，10 块钱 → 最多 30000 股
        ctx = _ctx(quantity=20000, price=10)
        d = rule.check_buy(ctx)
        assert d.action == RiskAction.ALLOW
        # 在仓位内不需要调整
        assert d.adjusted_qty == 0 or d.adjusted_qty >= 20000

    def test_adjust_when_exceeds(self):
        rule = MaxPositionRule(max_pct=0.3)
        # 想买 50000 股，超出 30% 上限
        ctx = _ctx(quantity=50000, price=10)
        d = rule.check_buy(ctx)
        assert d.action == RiskAction.ALLOW
        assert d.adjusted_qty == 30000  # 30万/10/100*100

    def test_reject_when_already_full(self):
        rule = MaxPositionRule(max_pct=0.3)
        # 已持仓 30000 股，已达上限
        pos = Position(symbol="000001", quantity=30000, available=30000,
                       cost_price=10, current_price=10)
        ctx = _ctx(quantity=1000, positions=[pos])
        d = rule.check_buy(ctx)
        assert d.action == RiskAction.REJECT

    def test_sell_and_hold_allow(self):
        rule = MaxPositionRule(max_pct=0.3)
        ctx = _ctx()
        assert rule.check_sell(ctx).action == RiskAction.ALLOW
        assert rule.check_hold(ctx).action == RiskAction.ALLOW


class TestTotalPositionRule:
    def test_allow_when_under(self):
        rule = TotalPositionRule(max_pct=0.8)
        ctx = _ctx(quantity=10000, price=10)
        assert rule.check_buy(ctx).action == RiskAction.ALLOW

    def test_reject_when_over(self):
        rule = TotalPositionRule(max_pct=0.8)
        # 已有 50万 持仓，再买 40万 → 总 90万 > 80%
        pos = Position(symbol="600000", quantity=50000, available=50000,
                       cost_price=10, current_price=10)
        ctx = _ctx(quantity=40000, price=10, positions=[pos])
        assert rule.check_buy(ctx).action == RiskAction.REJECT


class TestStopLossRule:
    def test_force_close_on_loss(self):
        rule = StopLossRule(stop_pct=0.07)
        pos = Position(symbol="000001", quantity=1000, available=1000,
                       cost_price=10.0, current_price=9.0)
        # 现价 9.2 → 亏 8%
        ctx = _ctx(price=9.2, positions=[pos])
        d = rule.check_hold(ctx)
        assert d.action == RiskAction.FORCE_CLOSE
        assert "止损" in d.reason

    def test_no_trigger_above_threshold(self):
        rule = StopLossRule(stop_pct=0.07)
        pos = Position(symbol="000001", quantity=1000, available=1000,
                       cost_price=10.0, current_price=9.5)
        ctx = _ctx(price=9.5, positions=[pos])
        assert rule.check_hold(ctx).action == RiskAction.ALLOW

    def test_no_trigger_on_gain(self):
        rule = StopLossRule(stop_pct=0.07)
        pos = Position(symbol="000001", quantity=1000, available=1000,
                       cost_price=10.0, current_price=11.0)
        ctx = _ctx(price=11.0, positions=[pos])
        assert rule.check_hold(ctx).action == RiskAction.ALLOW

    def test_buy_sell_allow(self):
        rule = StopLossRule(stop_pct=0.07)
        ctx = _ctx()
        assert rule.check_buy(ctx).action == RiskAction.ALLOW
        assert rule.check_sell(ctx).action == RiskAction.ALLOW


class TestMaxDrawdownRule:
    def test_reject_at_drawdown(self):
        rule = MaxDrawdownRule(max_dd_pct=0.15)
        # 初始 100 万，现在 80 万 → 回撤 20%
        ctx = _ctx(total_assets=800_000, initial_cash=1_000_000)
        assert rule.check_buy(ctx).action == RiskAction.REJECT

    def test_allow_below_drawdown(self):
        rule = MaxDrawdownRule(max_dd_pct=0.15)
        # 回撤 10%
        ctx = _ctx(total_assets=900_000, initial_cash=1_000_000)
        assert rule.check_buy(ctx).action == RiskAction.ALLOW


class TestDailyLossRule:
    def test_reject_at_daily_loss(self):
        rule = DailyLossRule(max_loss_pct=0.05)
        # 开盘 100 万，现 94 万 → 当日 -6%
        ctx = _ctx(total_assets=940_000, today_open_value=1_000_000)
        assert rule.check_buy(ctx).action == RiskAction.REJECT

    def test_allow_below(self):
        rule = DailyLossRule(max_loss_pct=0.05)
        ctx = _ctx(total_assets=980_000, today_open_value=1_000_000)
        assert rule.check_buy(ctx).action == RiskAction.ALLOW
