"""双均线交叉策略

经典趋势跟踪策略：
- 短均线上穿长均线 → 买入
- 短均线下穿长均线 → 卖出
"""

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

from .base import BaseStrategy, Signal, StrategyConfig


@dataclass
class MACrossConfig(StrategyConfig):
    name: str = "ma_cross"
    description: str = "双均线交叉策略"
    short_window: int = 5    # 短均线周期
    long_window: int = 20    # 长均线周期


class MACrossStrategy(BaseStrategy):
    """双均线交叉策略"""

    def __init__(self, config: Optional[MACrossConfig] = None):
        super().__init__(config or MACrossConfig())
        self.cfg: MACrossConfig = self.config

    def on_bar(self, idx: int, bar, position: int, cash: float) -> Signal:
        # 数据不足，不操作
        if idx < self.cfg.long_window:
            return Signal.HOLD

        # 这里依赖外部传入的 df，通过 idx 访问
        # 在 engine 里会把 df 绑定到 strategy 上
        df = self.df
        short_ma = df["close"].iloc[idx - self.cfg.short_window + 1: idx + 1].mean()
        long_ma = df["close"].iloc[idx - self.cfg.long_window + 1: idx + 1].mean()
        prev_short_ma = df["close"].iloc[idx - self.cfg.short_window: idx].mean()
        prev_long_ma = df["close"].iloc[idx - self.cfg.long_window: idx].mean()

        # 金叉：短均线从下方穿越长均线
        if prev_short_ma <= prev_long_ma and short_ma > long_ma:
            return Signal.BUY

        # 死叉：短均线从上方穿越长均线
        if prev_short_ma >= prev_long_ma and short_ma < long_ma:
            return Signal.SELL

        return Signal.HOLD
