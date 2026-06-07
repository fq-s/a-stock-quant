"""RSI均值回归策略

- RSI < 超卖阈值 → 买入
- RSI > 超买阈值 → 卖出

指标计算复用 factor.RSI。
"""

from dataclasses import dataclass
from typing import Optional

from .base import BaseStrategy, Signal, StrategyConfig
from factor import RSI


@dataclass
class RSIConfig(StrategyConfig):
    name: str = "rsi_reversal"
    description: str = "RSI均值回归策略"
    period: int = 14
    oversold: float = 30.0
    overbought: float = 70.0


class RSIStrategy(BaseStrategy):
    """RSI均值回归策略"""

    def __init__(self, config: Optional[RSIConfig] = None):
        super().__init__(config or RSIConfig())
        self.cfg: RSIConfig = self.config
        self._factor = RSI(period=self.cfg.period)
        self._cached_df_id = None
        self._rsi = None

    def _ensure_rsi(self):
        df = self.df
        if id(df) == self._cached_df_id and self._rsi is not None:
            return
        self._rsi = self._factor.compute(df)
        self._cached_df_id = id(df)

    def on_bar(self, idx: int, bar, position: int, cash: float) -> Signal:
        if idx < self.cfg.period:
            return Signal.HOLD

        self._ensure_rsi()
        rsi = self._rsi.iloc[idx]

        if rsi < self.cfg.oversold:
            return Signal.BUY
        if rsi > self.cfg.overbought:
            return Signal.SELL
        return Signal.HOLD
