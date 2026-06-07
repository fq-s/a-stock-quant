"""因子库

提供可复用的技术因子，统一接口便于策略与选股器组合使用。
"""

from .base import Factor, FactorRegistry
from .technical import (
    MA,
    EMA,
    RSI,
    MACD,
    Momentum,
    Volatility,
    ATR,
    Return,
)

__all__ = [
    "Factor",
    "FactorRegistry",
    "MA",
    "EMA",
    "RSI",
    "MACD",
    "Momentum",
    "Volatility",
    "ATR",
    "Return",
]
