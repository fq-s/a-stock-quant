"""选股器单元测试"""

import os
import sys
import tempfile

import numpy as np
import pandas as pd
import pytest

from factor import Momentum, Volatility, Return
from selector import FactorSelector, SelectionResult
from selector.universe import load_custom_universe


@pytest.fixture
def universe_data():
    """3 只股票 80 个交易日数据，趋势差异化"""
    np.random.seed(0)
    dates = pd.date_range("2024-01-01", periods=80, freq="B")
    out = {}
    for i, (sym, drift) in enumerate([("AAA", 0.005), ("BBB", -0.003), ("CCC", 0.001)]):
        rng = np.random.RandomState(i + 100)
        returns = rng.normal(drift, 0.015, len(dates))
        close = 10 * np.cumprod(1 + returns)
        out[sym] = pd.DataFrame({
            "date": dates,
            "open": close,
            "high": close * 1.01,
            "low": close * 0.99,
            "close": close,
            "volume": [100000] * len(dates),
        })
    return out


class TestFactorSelector:
    def test_default_config(self):
        sel = FactorSelector.default()
        assert len(sel.factors) == 3
        assert sel.lookback_days == 60

    def test_select_top_n(self, universe_data):
        sel = FactorSelector.default()
        result = sel.select(
            date=pd.Timestamp("2024-04-15"),
            universe_data=universe_data,
            top_n=2,
        )
        assert isinstance(result, SelectionResult)
        assert len(result.symbols) <= 2
        assert result.universe_size == 3
        # 选中股票的评分应单调递减
        scores = [result.scores[s] for s in result.symbols]
        assert scores == sorted(scores, reverse=True)

    def test_uptrend_beats_downtrend(self, universe_data):
        """AAA 强趋势主导动量因子，应排在第一"""
        sel = FactorSelector(
            factors=[(Momentum(window=20), 1.0)],
            lookback_days=30,
        )
        result = sel.select(
            date=pd.Timestamp("2024-04-15"),
            universe_data=universe_data,
            top_n=3,
        )
        assert result.symbols[0] == "AAA"
        # BBB 是下跌趋势，必然不会排第一
        assert "BBB" != result.symbols[0]

    def test_empty_universe(self):
        sel = FactorSelector.default()
        result = sel.select(
            date=pd.Timestamp("2024-01-01"),
            universe_data={},
            top_n=10,
        )
        assert result.symbols == []
        assert result.universe_size == 0

    def test_insufficient_history(self, universe_data):
        """lookback_days 过大时应过滤掉所有股票"""
        sel = FactorSelector(
            factors=[(Momentum(window=10), 1.0)],
            lookback_days=1000,
        )
        result = sel.select(
            date=pd.Timestamp("2024-04-15"),
            universe_data=universe_data,
            top_n=3,
        )
        # 所有都因数据不足被剔除（评分 0）
        # 长度可能为 0 或评分相同
        assert all(result.scores.get(s, 0) == 0 for s in result.symbols)

    def test_no_factors_raises(self):
        with pytest.raises(ValueError):
            FactorSelector(factors=[])


class TestLoadCustomUniverse:
    def test_with_header(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False
        ) as f:
            f.write("symbol\n000001\n600519\n")
            path = f.name
        try:
            syms = load_custom_universe(path)
            assert syms == ["000001", "600519"]
        finally:
            os.unlink(path)

    def test_without_header(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False
        ) as f:
            f.write("000001\n600519\n300750\n")
            path = f.name
        try:
            syms = load_custom_universe(path)
            assert syms == ["000001", "600519", "300750"]
        finally:
            os.unlink(path)

    def test_missing_file_raises(self):
        with pytest.raises(FileNotFoundError):
            load_custom_universe("/nonexistent/path.csv")
