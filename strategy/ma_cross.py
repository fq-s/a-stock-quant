"""双均线交叉策略

经典趋势跟踪策略：
- 短均线上穿长均线 → 买入
- 短均线下穿长均线 → 卖出

指标计算复用 factor.MA。
"""

from dataclasses import dataclass
from typing import Optional

from .base import BaseStrategy, Signal, StrategyConfig
from factor import MA


@dataclass
class MACrossConfig(StrategyConfig):
    name: str = "ma_cross"
    description: str = "双均线交叉策略"
    short_window: int = 5
    long_window: int = 20


class MACrossStrategy(BaseStrategy):
    """双均线交叉策略"""

    def __init__(self, config: Optional[MACrossConfig] = None):
        super().__init__(config or MACrossConfig())
        self.cfg: MACrossConfig = self.config
        self._short_factor = MA(window=self.cfg.short_window)
        self._long_factor = MA(window=self.cfg.long_window)
        self._cached_df_id = None  # 用于缓存因子序列
        self._short_ma = None
        self._long_ma = None

    def _ensure_factors(self):
        df = self.df
        if id(df) == self._cached_df_id and self._short_ma is not None:
            return
        self._short_ma = self._short_factor.compute(df)
        self._long_ma = self._long_factor.compute(df)
        self._cached_df_id = id(df)

    def on_bar(self, idx: int, bar, position: int, cash: float) -> Signal:
        if idx < self.cfg.long_window:
            return Signal.HOLD

        self._ensure_factors()
        short_ma = self._short_ma.iloc[idx]
        long_ma = self._long_ma.iloc[idx]
        prev_short = self._short_ma.iloc[idx - 1]
        prev_long = self._long_ma.iloc[idx - 1]

        if prev_short <= prev_long and short_ma > long_ma:
            return Signal.BUY
        if prev_short >= prev_long and short_ma < long_ma:
            return Signal.SELL
        return Signal.HOLD
