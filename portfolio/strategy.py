"""组合策略：on_rebalance(date, data, account, positions) -> TargetWeights"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import pandas as pd

from selector.base import BaseSelector


@dataclass
class TargetWeights:
    """目标持仓权重：{symbol: weight}，weight 总和 ≤ 1"""
    weights: Dict[str, float] = field(default_factory=dict)
    date: Optional[pd.Timestamp] = None

    def normalize(self) -> "TargetWeights":
        """权重和归一为 1（如果原本就 <1 表示留一部分现金，可保持原值）"""
        s = sum(self.weights.values())
        if s <= 0:
            return self
        if s > 1.0:
            self.weights = {k: v / s for k, v in self.weights.items()}
        return self


class PortfolioStrategy(ABC):
    """组合策略抽象基类"""

    @abstractmethod
    def on_rebalance(
        self,
        date: pd.Timestamp,
        data: Dict[str, pd.DataFrame],
        account,
        positions: List,
    ) -> TargetWeights:
        """调仓日触发，返回目标权重

        Parameters
        ----------
        date : pd.Timestamp
            调仓日
        data : Dict[str, pd.DataFrame]
            候选池数据：{symbol: 截至 date 的 OHLCV DataFrame}
        account : Account
            账户快照（total_assets/cash/market_value）
        positions : List[Position]
            当前持仓
        """
        ...


class SelectorPortfolioStrategy(PortfolioStrategy):
    """用 selector 选股 + 等权重分配生成 TargetWeights"""

    def __init__(self, selector: BaseSelector, top_n: int = 10,
                 cash_buffer: float = 0.02):
        """
        Parameters
        ----------
        selector : BaseSelector
        top_n : int
            选股数
        cash_buffer : float
            保留现金比例（用于费用/滑点），默认 2%
        """
        self.selector = selector
        self.top_n = top_n
        self.cash_buffer = cash_buffer

    def on_rebalance(self, date, data, account, positions) -> TargetWeights:
        result = self.selector.select(date, data, top_n=self.top_n)
        if not result.symbols:
            return TargetWeights(weights={}, date=date)
        equal_weight = (1.0 - self.cash_buffer) / len(result.symbols)
        return TargetWeights(
            weights={sym: equal_weight for sym in result.symbols},
            date=date,
        )
