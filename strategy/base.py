"""策略基类"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class Signal(Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


@dataclass
class Trade:
    """一笔交易记录"""
    date: str
    action: Signal
    price: float
    shares: int
    cash_after: float
    position_after: int
    reason: str = ""


@dataclass
class StrategyConfig:
    """策略配置基类 — 子策略继承并扩展"""
    name: str = "base"
    description: str = ""


class BaseStrategy(ABC):
    """策略抽象基类

    子类需要实现:
    - on_bar(bar, position, cash) -> Signal
    - get_config() -> StrategyConfig
    """

    def __init__(self, config: Optional[StrategyConfig] = None):
        self.config = config or StrategyConfig()
        self.trades: List[Trade] = []

    @abstractmethod
    def on_bar(self, idx: int, bar, position: int, cash: float) -> Signal:
        """
        每根K线触发一次

        Parameters
        ----------
        idx : int        当前K线索引（可用于访问历史数据）
        bar : Series     当前行数据 (date, open, high, low, close, volume)
        position : int   当前持仓股数
        cash : float     当前现金

        Returns
        -------
        Signal  买卖信号
        """
        pass

    def record_trade(self, date, action, price, shares, cash_after, position_after, reason=""):
        self.trades.append(Trade(
            date=str(date), action=action, price=price,
            shares=shares, cash_after=cash_after,
            position_after=position_after, reason=reason,
        ))
