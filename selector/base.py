"""选股器抽象基类"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import pandas as pd


@dataclass
class SelectionResult:
    """选股结果"""
    date: pd.Timestamp
    symbols: List[str]                          # 选中股票代码（按评分降序）
    scores: Dict[str, float] = field(default_factory=dict)  # 各股票评分
    universe_size: int = 0                      # 候选池大小


class BaseSelector(ABC):
    """选股器抽象基类"""

    @abstractmethod
    def select(
        self,
        date: pd.Timestamp,
        universe_data: Dict[str, pd.DataFrame],
        top_n: int = 10,
    ) -> SelectionResult:
        """从 universe 中选出 top_n 只股票

        Parameters
        ----------
        date : pd.Timestamp
            选股日期（评估时点，因子值取到此日为止）
        universe_data : Dict[str, pd.DataFrame]
            股票池数据：{symbol: 单股OHLCV DataFrame}
        top_n : int
            选股数量

        Returns
        -------
        SelectionResult
        """
        pass
