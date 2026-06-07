"""测试 backtest/engine.py 的费用计算和风控集成"""

import pandas as pd
import pytest

from backtest.engine import BacktestEngine, BacktestConfig
from strategy.base import BaseStrategy, Signal, StrategyConfig
from risk import RiskManager, RiskRule, RiskDecision, RiskAction


def _df(closes):
    return pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=len(closes), freq="D"),
        "open": closes, "high": closes, "low": closes,
        "close": closes, "volume": [10000] * len(closes),
    })


class _ScriptedStrategy(BaseStrategy):
    """按预设信号序列出信号"""
    def __init__(self, signals):
        super().__init__(StrategyConfig(name="scripted"))
        self.signals = signals
    def on_bar(self, idx, bar, position, cash):
        if idx < len(self.signals):
            return self.signals[idx]
        return Signal.HOLD


class TestFeeMath:
    def test_buy_cost_with_slippage_and_commission(self):
        """买入：成本 = qty * price * (1+slippage) * (1+commission)"""
        # bar 0 close=10，下一根 hold
        df = _df([10.0, 10.0, 10.0])
        strat = _ScriptedStrategy([Signal.BUY, Signal.HOLD, Signal.HOLD])
        cfg = BacktestConfig(
            initial_cash=10_000,
            commission_rate=0.0003,
            stamp_tax_rate=0.001,
            slippage=0.001,
            position_size=0.95,
        )
        engine = BacktestEngine(strat, cfg)
        engine.run(df)

        # buy_price = 10 * 1.001 = 10.01
        # max_shares = int(10000 * 0.95 / 10.01 / 100) * 100 = 900
        # cost = 900 * 10.01 * (1 + 0.0003)
        buy_price = 10.0 * 1.001
        expected_shares = int(10_000 * 0.95 / buy_price / 100) * 100
        expected_cost = expected_shares * buy_price * 1.0003
        trades = strat.trades
        assert len(trades) == 1
        assert trades[0].action == Signal.BUY
        assert trades[0].shares == expected_shares
        # 剩余现金
        expected_cash = 10_000 - expected_cost
        assert trades[0].cash_after == pytest.approx(expected_cash, rel=1e-6)

    def test_sell_revenue_with_tax(self):
        """卖出：净收入 = qty*price*(1-slip) - tax - commission"""
        df = _df([10.0, 11.0, 11.0])
        strat = _ScriptedStrategy([Signal.BUY, Signal.SELL, Signal.HOLD])
        cfg = BacktestConfig(initial_cash=10_000,
                             commission_rate=0.0003,
                             stamp_tax_rate=0.001,
                             slippage=0.001)
        engine = BacktestEngine(strat, cfg)
        engine.run(df)

        sell = next(t for t in strat.trades if t.action == Signal.SELL)
        # 卖价 = 11 * (1-0.001) = 10.989
        sell_price = 11.0 * 0.999
        assert sell.price == pytest.approx(sell_price, rel=1e-6)


class TestInsufficientFunds:
    def test_no_buy_when_below_one_lot(self):
        # cash 太小，连一手都买不起
        df = _df([10000.0, 10000.0])
        strat = _ScriptedStrategy([Signal.BUY, Signal.HOLD])
        cfg = BacktestConfig(initial_cash=1000)  # 100元，买不起 10000元/股
        engine = BacktestEngine(strat, cfg)
        engine.run(df)
        assert len(strat.trades) == 0


class TestRiskIntegration:
    def test_reject_blocks_buy(self):
        class _RejectAll(RiskRule):
            name = "reject"
            def check_buy(self, ctx):
                return RiskDecision(RiskAction.REJECT, rule="reject", reason="ban")
            def check_sell(self, ctx): return RiskDecision(RiskAction.ALLOW)
            def check_hold(self, ctx): return RiskDecision(RiskAction.ALLOW)

        df = _df([10.0, 10.0])
        strat = _ScriptedStrategy([Signal.BUY, Signal.HOLD])
        cfg = BacktestConfig(initial_cash=10_000,
                             risk_manager=RiskManager([_RejectAll()]))
        engine = BacktestEngine(strat, cfg)
        engine.run(df)
        assert len(strat.trades) == 0  # 买入被拒

    def test_force_close_sells_position(self):
        """风控强平：建仓后立即触发 force_close"""
        triggered = {"n": 0}
        class _ForceCloseAfterBuy(RiskRule):
            name = "force"
            def check_buy(self, ctx): return RiskDecision(RiskAction.ALLOW)
            def check_sell(self, ctx): return RiskDecision(RiskAction.ALLOW)
            def check_hold(self, ctx):
                if triggered["n"] == 0 and ctx.positions:
                    triggered["n"] += 1
                    return RiskDecision(RiskAction.FORCE_CLOSE,
                                        rule="force", reason="强平")
                return RiskDecision(RiskAction.ALLOW)

        df = _df([10.0, 10.0, 10.0])
        strat = _ScriptedStrategy([Signal.BUY, Signal.HOLD, Signal.HOLD])
        cfg = BacktestConfig(initial_cash=10_000,
                             risk_manager=RiskManager([_ForceCloseAfterBuy()]))
        engine = BacktestEngine(strat, cfg)
        engine.run(df)
        # 至少一次 SELL（来自风控）
        sells = [t for t in strat.trades if t.action == Signal.SELL]
        assert len(sells) >= 1
        assert "风控" in sells[0].reason


class TestPortfolioValue:
    def test_no_trade_tracks_initial(self):
        """无信号时 portfolio 始终等于 initial_cash"""
        df = _df([10.0] * 5)
        strat = _ScriptedStrategy([Signal.HOLD] * 5)
        cfg = BacktestConfig(initial_cash=10_000)
        engine = BacktestEngine(strat, cfg)
        result = engine.run(df)
        for v in result["results"]["portfolio"]:
            assert v == pytest.approx(10_000)
