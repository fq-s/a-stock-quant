"""RSI均值回归策略

- RSI < 超卖阈值 → 买入
- RSI > 超买阈值 → 卖出
"""

from dataclasses import dataclass
from typing import Optional

from .base import BaseStrategy, Signal, StrategyConfig


@dataclass
class RSIConfig(StrategyConfig):
    name: str = "rsi_reversal"
    description: str = "RSI均值回归策略"
    period: int = 14          # RSI周期
    oversold: float = 30.0    # 超卖阈值
    overbought: float = 70.0  # 超买阈值


class RSIStrategy(BaseStrategy):
    """RSI均值回归策略"""

    def __init__(self, config: Optional[RSIConfig] = None):
        super().__init__(config or RSIConfig())
        self.cfg: RSIConfig = self.config

    def _calc_rsi(self, idx: int) -> float:
        """计算RSI"""
        df = self.df
        period = self.cfg.period
        if idx < period:
            return 50.0  # 默认中性

        closes = df["close"].iloc[idx - period: idx + 1].values
        deltas = closes[1:] - closes[:-1]
        gains = deltas[deltas > 0].sum() / period
        losses = (-deltas[deltas < 0]).sum() / period

        if losses == 0:
            return 100.0
        rs = gains / losses
        return 100.0 - (100.0 / (1.0 + rs))

    def on_bar(self, idx: int, bar, position: int, cash: float) -> Signal:
        if idx < self.cfg.period:
            return Signal.HOLD

        rsi = self._calc_rsi(idx)

        if rsi < self.cfg.oversold:
            return Signal.BUY
        if rsi > self.cfg.overbought:
            return Signal.SELL

        return Signal.HOLD
