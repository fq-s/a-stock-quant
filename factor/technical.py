"""技术因子库

输入约定: df 至少包含 close 列，部分因子需 high/low；输出与 df 同长。
"""

import numpy as np
import pandas as pd

from .base import Factor, FactorRegistry


@FactorRegistry.register
class MA(Factor):
    """简单移动平均"""
    name = "MA"

    def __init__(self, window: int = 20):
        self.window = window

    def compute(self, df: pd.DataFrame) -> pd.Series:
        return df["close"].rolling(window=self.window, min_periods=self.window).mean()


@FactorRegistry.register
class EMA(Factor):
    """指数移动平均"""
    name = "EMA"

    def __init__(self, window: int = 20):
        self.window = window

    def compute(self, df: pd.DataFrame) -> pd.Series:
        return df["close"].ewm(span=self.window, adjust=False, min_periods=self.window).mean()


@FactorRegistry.register
class RSI(Factor):
    """相对强弱指标

    与原 strategy/rsi_reversal.py 实现一致：
    - 用 period 内 gain/loss 的算术平均
    - 全 0 loss 返回 100
    """
    name = "RSI"

    def __init__(self, period: int = 14):
        self.period = period

    def compute(self, df: pd.DataFrame) -> pd.Series:
        close = df["close"].values
        n = len(close)
        out = np.full(n, np.nan)
        for i in range(self.period, n):
            window = close[i - self.period: i + 1]
            deltas = np.diff(window)
            gains = deltas[deltas > 0].sum() / self.period
            losses = (-deltas[deltas < 0]).sum() / self.period
            if losses == 0:
                out[i] = 100.0
            else:
                rs = gains / losses
                out[i] = 100.0 - (100.0 / (1.0 + rs))
        return pd.Series(out, index=df.index)


@FactorRegistry.register
class MACD(Factor):
    """MACD：返回 DIF 序列（DIF = EMA_fast - EMA_slow）

    若需要 DEA 或 HIST，可分别再用 EMA(signal) 处理。
    保持 Factor 接口"单序列输出"简单一致。
    """
    name = "MACD"

    def __init__(self, fast: int = 12, slow: int = 26, signal: int = 9):
        self.fast = fast
        self.slow = slow
        self.signal = signal

    def compute(self, df: pd.DataFrame) -> pd.Series:
        ema_fast = df["close"].ewm(span=self.fast, adjust=False).mean()
        ema_slow = df["close"].ewm(span=self.slow, adjust=False).mean()
        dif = ema_fast - ema_slow
        # 前 slow 个值不可信，标 NaN
        dif.iloc[: self.slow] = np.nan
        return dif


@FactorRegistry.register
class Momentum(Factor):
    """动量：window 日累计收益率"""
    name = "Momentum"

    def __init__(self, window: int = 20):
        self.window = window

    def compute(self, df: pd.DataFrame) -> pd.Series:
        close = df["close"]
        return close / close.shift(self.window) - 1


@FactorRegistry.register
class Return(Factor):
    """收益率（与 Momentum 数学等价，语义不同，便于配置可读性）"""
    name = "Return"

    def __init__(self, window: int = 1):
        self.window = window

    def compute(self, df: pd.DataFrame) -> pd.Series:
        return df["close"].pct_change(self.window)


@FactorRegistry.register
class Volatility(Factor):
    """波动率：window 日收益率标准差（年化前）"""
    name = "Volatility"

    def __init__(self, window: int = 20):
        self.window = window

    def compute(self, df: pd.DataFrame) -> pd.Series:
        returns = df["close"].pct_change()
        return returns.rolling(window=self.window, min_periods=self.window).std()


@FactorRegistry.register
class ATR(Factor):
    """平均真实波幅

    TR = max(high-low, |high - prev_close|, |low - prev_close|)
    ATR = TR 的 period 简单移动平均
    """
    name = "ATR"

    def __init__(self, period: int = 14):
        self.period = period

    def compute(self, df: pd.DataFrame) -> pd.Series:
        if not {"high", "low", "close"}.issubset(df.columns):
            raise ValueError("ATR 需要 high/low/close 列")
        high = df["high"]
        low = df["low"]
        prev_close = df["close"].shift(1)
        tr = pd.concat([
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ], axis=1).max(axis=1)
        return tr.rolling(window=self.period, min_periods=self.period).mean()
