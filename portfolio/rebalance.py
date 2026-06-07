"""调仓调度器：决定哪些日期需要调仓"""

from typing import List

import pandas as pd


class RebalanceScheduler:
    """按固定 N 个交易日触发调仓"""

    def __init__(self, interval: int = 20):
        """
        Parameters
        ----------
        interval : int
            调仓间隔（交易日数）
        """
        if interval < 1:
            raise ValueError("调仓间隔必须 >= 1")
        self.interval = interval

    def get_rebalance_dates(self, all_dates: List[pd.Timestamp]) -> List[pd.Timestamp]:
        """从全部交易日中挑出调仓日（首日 + 每 N 日）"""
        if not all_dates:
            return []
        out = [all_dates[0]]
        for i, d in enumerate(all_dates):
            if i > 0 and i % self.interval == 0:
                out.append(d)
        return out
