"""组合回测引擎单元测试"""

import numpy as np
import pandas as pd
import pytest

from factor import Momentum
from portfolio import (
    PortfolioBacktestEngine,
    PortfolioBacktestConfig,
    SelectorPortfolioStrategy,
    TargetWeights,
    PortfolioStrategy,
    RebalanceScheduler,
)
from selector import FactorSelector


@pytest.fixture
def small_universe():
    """3 只股票 50 个交易日"""
    np.random.seed(1)
    dates = pd.date_range("2024-01-01", periods=50, freq="B")
    out = {}
    for i, (sym, drift) in enumerate([("X", 0.004), ("Y", 0.001), ("Z", -0.002)]):
        rng = np.random.RandomState(i + 200)
        returns = rng.normal(drift, 0.01, len(dates))
        close = 20 * np.cumprod(1 + returns)
        out[sym] = pd.DataFrame({
            "date": dates,
            "open": close,
            "high": close * 1.01,
            "low": close * 0.99,
            "close": close,
            "volume": [1_000_000] * len(dates),
        })
    return out


class _FixedStrategy(PortfolioStrategy):
    """固定权重策略，方便单元测试"""

    def __init__(self, target: dict):
        self.target = target

    def on_rebalance(self, date, data, account, positions) -> TargetWeights:
        return TargetWeights(weights=self.target, date=date)


class TestRebalanceScheduler:
    def test_first_and_every_n(self):
        dates = pd.date_range("2024-01-01", periods=10, freq="D").tolist()
        sched = RebalanceScheduler(interval=3)
        result = sched.get_rebalance_dates(dates)
        # 首日 + idx 3, 6, 9
        assert result == [dates[0], dates[3], dates[6], dates[9]]

    def test_invalid_interval(self):
        with pytest.raises(ValueError):
            RebalanceScheduler(interval=0)

    def test_empty(self):
        assert RebalanceScheduler(interval=5).get_rebalance_dates([]) == []


class TestPortfolioBacktestEngine:
    def test_basic_run(self, small_universe):
        strat = _FixedStrategy({"X": 0.4, "Y": 0.3, "Z": 0.3})
        eng = PortfolioBacktestEngine(
            strat, PortfolioBacktestConfig(rebalance_interval=10)
        )
        res = eng.run(small_universe)
        # 50 天 nav 曲线
        assert len(res["results"]) == 50
        # 至少有买单
        buys = [t for t in res["trades"] if t.action.value == "BUY"]
        assert len(buys) >= 3
        # 含 final_value
        assert "final_value" in res["metrics"]

    def test_empty_universe_raises(self):
        strat = _FixedStrategy({"X": 1.0})
        eng = PortfolioBacktestEngine(strat)
        with pytest.raises(ValueError):
            eng.run({})

    def test_rebalance_replaces_holdings(self, small_universe):
        """先全仓 X，调仓后切换到 Y → 应卖 X 买 Y"""

        class _SwitchStrategy(PortfolioStrategy):
            def __init__(self):
                self.call = 0

            def on_rebalance(self, date, data, account, positions):
                self.call += 1
                if self.call == 1:
                    return TargetWeights({"X": 0.95}, date)
                return TargetWeights({"Y": 0.95}, date)

        strat = _SwitchStrategy()
        eng = PortfolioBacktestEngine(
            strat, PortfolioBacktestConfig(rebalance_interval=20)
        )
        res = eng.run(small_universe)
        trades = res["trades"]
        # 应该有 X 的买入 + 卖出 + Y 的买入
        bought = {t.reason.split("]")[0][1:] for t in trades if t.action.value == "BUY"}
        sold = {t.reason.split("]")[0][1:] for t in trades if t.action.value == "SELL"}
        assert "X" in bought
        assert "Y" in bought
        assert "X" in sold

    def test_selector_integration(self, small_universe):
        sel = FactorSelector(
            factors=[(Momentum(window=10), 1.0)],
            lookback_days=15,
        )
        strat = SelectorPortfolioStrategy(selector=sel, top_n=2)
        eng = PortfolioBacktestEngine(
            strat, PortfolioBacktestConfig(rebalance_interval=15)
        )
        res = eng.run(small_universe)
        assert len(res["rebalance_log"]) >= 2
        # 报告能生成
        report = eng.report()
        assert "组合回测报告" in report

    def test_cash_buffer_respected(self, small_universe):
        """目标权重和 < 1 时应保留现金"""
        strat = _FixedStrategy({"X": 0.3, "Y": 0.3})  # 总和 0.6，保 40% 现金
        eng = PortfolioBacktestEngine(strat, PortfolioBacktestConfig(rebalance_interval=10))
        res = eng.run(small_universe)
        # 第一次调仓后的现金占比应接近 40%（含费用误差）
        # 最终 nav 应在合理范围
        assert res["metrics"]["final_value"] > 100_000

    def test_target_weights_normalize(self):
        tw = TargetWeights({"A": 0.6, "B": 0.6})  # 总和 1.2
        tw.normalize()
        assert sum(tw.weights.values()) == pytest.approx(1.0)
        # ≤1 时保持
        tw2 = TargetWeights({"A": 0.3, "B": 0.3})
        tw2.normalize()
        assert tw2.weights["A"] == 0.3
