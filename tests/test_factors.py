"""因子库单元测试"""

import numpy as np
import pandas as pd
import pytest

from factor import MA, EMA, RSI, MACD, Momentum, Volatility, ATR, Return, Factor, FactorRegistry


@pytest.fixture
def df_basic():
    closes = [10, 11, 12, 13, 12, 11, 12, 13, 14, 15]
    n = len(closes)
    return pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=n),
        "open": closes,
        "high": [c + 0.5 for c in closes],
        "low": [c - 0.5 for c in closes],
        "close": closes,
        "volume": [1000] * n,
    })


class TestMA:
    def test_basic(self, df_basic):
        ma = MA(window=3).compute(df_basic)
        # 前两个 NaN，第三个 = (10+11+12)/3 = 11
        assert pd.isna(ma.iloc[0]) and pd.isna(ma.iloc[1])
        assert ma.iloc[2] == pytest.approx(11.0)
        assert ma.iloc[3] == pytest.approx(12.0)  # (11+12+13)/3

    def test_window_too_large(self, df_basic):
        ma = MA(window=100).compute(df_basic)
        assert ma.isna().all()


class TestEMA:
    def test_first_value_after_window(self, df_basic):
        ema = EMA(window=3).compute(df_basic)
        # 前 window-1 个 NaN（min_periods=window）
        assert pd.isna(ema.iloc[0])
        assert not pd.isna(ema.iloc[2])


class TestRSI:
    def test_all_up(self):
        # 全部上涨 → RSI 应该 = 100
        closes = list(range(10, 25))
        df = pd.DataFrame({"close": closes})
        rsi = RSI(period=5).compute(df)
        assert rsi.iloc[-1] == pytest.approx(100.0)

    def test_alternating(self, df_basic):
        rsi = RSI(period=5).compute(df_basic)
        # 前 period 个 NaN
        assert pd.isna(rsi.iloc[4])
        assert not pd.isna(rsi.iloc[5])
        # RSI 值应在 [0, 100]
        valid = rsi.dropna()
        assert (valid >= 0).all() and (valid <= 100).all()


class TestMACD:
    def test_shape(self, df_basic):
        # MACD 需要至少 slow 个点（默认 26），加更多数据
        closes = list(np.linspace(10, 20, 50))
        df = pd.DataFrame({"close": closes})
        dif = MACD().compute(df)
        # 前 slow 个 NaN
        assert pd.isna(dif.iloc[0])
        assert pd.isna(dif.iloc[25])
        assert not pd.isna(dif.iloc[40])


class TestMomentum:
    def test_basic(self, df_basic):
        mom = Momentum(window=3).compute(df_basic)
        # 前 3 个 NaN（shift(3) 导致）
        assert pd.isna(mom.iloc[2])
        # 第 4 个 = 13/10 - 1 = 0.3
        assert mom.iloc[3] == pytest.approx(0.3)


class TestReturn:
    def test_equiv_to_momentum(self, df_basic):
        m = Momentum(window=3).compute(df_basic)
        r = Return(window=3).compute(df_basic)
        pd.testing.assert_series_equal(m.dropna(), r.dropna(), check_names=False)


class TestVolatility:
    def test_basic(self, df_basic):
        vol = Volatility(window=5).compute(df_basic)
        # 前 5 个 NaN（4 个 pct_change 等待 + 1 个 rolling 等待）
        assert pd.isna(vol.iloc[4])
        assert not pd.isna(vol.iloc[5])
        assert vol.iloc[5] > 0


class TestATR:
    def test_basic(self, df_basic):
        atr = ATR(period=3).compute(df_basic)
        assert pd.isna(atr.iloc[0])
        assert not pd.isna(atr.iloc[5])
        assert (atr.dropna() >= 0).all()

    def test_missing_columns_raises(self):
        df = pd.DataFrame({"close": [1, 2, 3]})
        with pytest.raises(ValueError):
            ATR().compute(df)


class TestFactorRegistry:
    def test_get_by_name(self):
        ma = FactorRegistry.get("MA", window=5)
        assert isinstance(ma, MA)
        assert ma.window == 5

    def test_unknown_factor_raises(self):
        with pytest.raises(KeyError):
            FactorRegistry.get("NotAFactor")

    def test_list_contains_builtins(self):
        names = FactorRegistry.list()
        for n in ["MA", "EMA", "RSI", "MACD", "Momentum", "Volatility", "ATR", "Return"]:
            assert n in names
