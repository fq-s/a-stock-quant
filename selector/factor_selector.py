"""多因子打分选股器

工作流：
1. 对股票池每只股票，分别计算每个因子在 date 当天的值
2. 截面 z-score 归一化（每个因子独立）
3. 加权求和得到综合评分
4. 取 top_n
"""

from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

from factor import Factor, Momentum, Volatility, Return

from .base import BaseSelector, SelectionResult


class FactorSelector(BaseSelector):
    """多因子打分选股器"""

    def __init__(
        self,
        factors: List[Tuple[Factor, float]],
        lookback_days: int = 60,
    ):
        """
        Parameters
        ----------
        factors : List[(Factor, weight)]
            因子及其权重，权重正负决定方向（如波动率用负权重 → 低波动加分）
        lookback_days : int
            因子计算的最小历史天数，不足则跳过该股
        """
        if not factors:
            raise ValueError("至少需要一个因子")
        self.factors = factors
        self.lookback_days = lookback_days

    @classmethod
    def default(cls) -> "FactorSelector":
        """默认配置：动量 + 低波动 + 短期反转"""
        return cls(
            factors=[
                (Momentum(window=20), 0.5),
                (Volatility(window=20), -0.3),
                (Return(window=5), -0.2),
            ],
            lookback_days=60,
        )

    def _factor_value_at(self, factor: Factor, df: pd.DataFrame,
                         date: pd.Timestamp) -> float:
        """取因子在 date 当天的值（找 <=date 的最后一行）"""
        sub = df[df["date"] <= date]
        if len(sub) < self.lookback_days:
            return np.nan
        series = factor.compute(sub)
        if series.empty:
            return np.nan
        val = series.iloc[-1]
        return float(val) if pd.notna(val) else np.nan

    @staticmethod
    def _zscore(values: Dict[str, float]) -> Dict[str, float]:
        """对一个截面做 z-score（忽略 NaN）"""
        valid = {k: v for k, v in values.items() if pd.notna(v)}
        if len(valid) < 2:
            return {k: 0.0 for k in values}
        arr = np.array(list(valid.values()))
        mean, std = arr.mean(), arr.std(ddof=0)
        if std == 0:
            return {k: 0.0 for k in values}
        return {k: (v - mean) / std if pd.notna(v) else 0.0
                for k, v in values.items()}

    def select(
        self,
        date: pd.Timestamp,
        universe_data: Dict[str, pd.DataFrame],
        top_n: int = 10,
    ) -> SelectionResult:
        if not universe_data:
            return SelectionResult(date=date, symbols=[], scores={}, universe_size=0)

        # 1. 各因子在截面上的原始值
        raw: List[Dict[str, float]] = []
        for factor, _weight in self.factors:
            vals = {sym: self._factor_value_at(factor, df, date)
                    for sym, df in universe_data.items()}
            raw.append(vals)

        # 2. 截面 z-score
        z_scores = [self._zscore(vals) for vals in raw]

        # 3. 加权求和
        composite: Dict[str, float] = {}
        for sym in universe_data:
            s = 0.0
            valid_any = False
            for (_, weight), z in zip(self.factors, z_scores):
                v = z.get(sym, 0.0)
                # 原始值为 NaN 的股票跳过（评分 0），但保留全 NaN 则视为无效
                if pd.notna(v) and v != 0:
                    valid_any = True
                s += weight * v
            # 至少一个因子有意义才纳入
            if valid_any or self.lookback_days == 0:
                composite[sym] = s

        # 还要排除原始数据不足的股票
        ranked = sorted(composite.items(), key=lambda x: x[1], reverse=True)
        symbols = [sym for sym, _ in ranked[:top_n]]

        return SelectionResult(
            date=date,
            symbols=symbols,
            scores={sym: composite[sym] for sym in symbols},
            universe_size=len(universe_data),
        )
