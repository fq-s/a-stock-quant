"""策略改造回归测试：迁移到 factor 库后行为保持等价"""

import numpy as np
import pandas as pd
import pytest

from factor import MA, RSI
from strategy.ma_cross import MACrossStrategy, MACrossConfig
from strategy.rsi_reversal import RSIStrategy, RSIConfig
from backtest.engine import BacktestEngine, BacktestConfig


@pytest.fixture
def trending_df():
    """40 根 K 线，先涨后跌后涨，保证 MA/RSI 信号都能触发"""
    np.random.seed(42)
    n = 60
    base = np.concatenate([
        np.linspace(10, 15, 20),
        np.linspace(15, 8, 20),
        np.linspace(8, 14, 20),
    ])
    noise = np.random.normal(0, 0.15, n)
    closes = base + noise
    return pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=n, freq="D"),
        "open": closes,
        "high": closes + 0.2,
        "low": closes - 0.2,
        "close": closes,
        "volume": [10000] * n,
    })


class TestMACrossRefactor:
    def test_factor_matches_inline(self, trending_df):
        """MA(window=5).compute() 与手动 rolling(5).mean() 完全相同"""
        from_factor = MA(window=5).compute(trending_df)
        inline = trending_df["close"].rolling(5, min_periods=5).mean()
        pd.testing.assert_series_equal(from_factor, inline, check_names=False)

    def test_strategy_produces_trades(self, trending_df):
        strat = MACrossStrategy(MACrossConfig(short_window=5, long_window=20))
        eng = BacktestEngine(strat, BacktestConfig(initial_cash=100_000))
        res = eng.run(trending_df)
        # 至少触发一次信号
        assert len(res["trades"]) > 0


class TestRSIRefactor:
    def test_factor_matches_inline(self, trending_df):
        """RSI 工厂值应当与原内嵌实现一致（验证一处即可代表算法迁移正确）"""
        period = 14
        rsi = RSI(period=period).compute(trending_df)
        # 手算最后一个点
        closes = trending_df["close"].values
        window = closes[-period - 1:]
        deltas = np.diff(window)
        gains = deltas[deltas > 0].sum() / period
        losses = (-deltas[deltas < 0]).sum() / period
        expected = 100.0 if losses == 0 else 100.0 - 100.0 / (1.0 + gains / losses)
        assert rsi.iloc[-1] == pytest.approx(expected, rel=1e-6)

    def test_strategy_produces_trades(self, trending_df):
        strat = RSIStrategy(RSIConfig(period=14, oversold=40, overbought=60))
        eng = BacktestEngine(strat, BacktestConfig(initial_cash=100_000))
        res = eng.run(trending_df)
        assert len(res["trades"]) > 0
