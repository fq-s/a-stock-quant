"""回测引擎

模拟逐K线驱动策略，计算收益与风险指标。
"""

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from strategy.base import BaseStrategy, Signal, Trade
from utils.metrics import calc_metrics


@dataclass
class BacktestConfig:
    initial_cash: float = 1_000_000
    commission_rate: float = 0.0003     # 买入佣金 万三
    stamp_tax_rate: float = 0.001       # 卖出印花税 千一
    slippage: float = 0.001             # 滑点 0.1%
    position_size: float = 0.95         # 仓位比例（用多少现金买入）


class BacktestEngine:
    """回测引擎"""

    def __init__(self, strategy: BaseStrategy, config: Optional[BacktestConfig] = None):
        self.strategy = strategy
        self.cfg = config or BacktestConfig()
        self.results: Optional[pd.DataFrame] = None
        self.metrics: dict = {}

    def run(self, df: pd.DataFrame) -> dict:
        """
        运行回测

        Parameters
        ----------
        df : pd.DataFrame
            必须包含 date, open, high, low, close, volume

        Returns
        -------
        dict  包含 metrics 和交易记录
        """
        # 把数据绑定到策略上（策略通过 idx 访问历史数据）
        self.strategy.df = df
        self.strategy.trades = []

        cash = self.cfg.initial_cash
        position = 0  # 持仓股数
        portfolio_values = []

        for idx in range(len(df)):
            bar = df.iloc[idx]

            signal = self.strategy.on_bar(idx, bar, position, cash)

            if signal == Signal.BUY and position == 0:
                # 买入
                buy_price = bar["close"] * (1 + self.cfg.slippage)
                max_shares = int(cash * self.cfg.position_size / buy_price / 100) * 100  # 整手
                if max_shares >= 100:
                    cost = max_shares * buy_price * (1 + self.cfg.commission_rate)
                    if cost <= cash:
                        cash -= cost
                        position = max_shares
                        self.strategy.record_trade(
                            bar["date"], Signal.BUY, buy_price, max_shares,
                            cash, position, reason="策略买入"
                        )

            elif signal == Signal.SELL and position > 0:
                # 卖出
                sell_price = bar["close"] * (1 - self.cfg.slippage)
                revenue = position * sell_price
                tax = revenue * self.cfg.stamp_tax_rate
                commission = revenue * self.cfg.commission_rate
                cash += revenue - tax - commission
                self.strategy.record_trade(
                    bar["date"], Signal.SELL, sell_price, position,
                    cash, 0, reason="策略卖出"
                )
                position = 0

            # 记录当日组合市值
            portfolio_values.append(cash + position * bar["close"])

        # 生成结果 DataFrame
        self.results = df.copy()
        self.results["portfolio"] = portfolio_values
        self.results["benchmark"] = df["close"] / df["close"].iloc[0] * self.cfg.initial_cash

        # 计算指标
        self.metrics = calc_metrics(
            portfolio_values=portfolio_values,
            benchmark_values=self.results["benchmark"].tolist(),
            initial_cash=self.cfg.initial_cash,
            trades=self.strategy.trades,
        )

        return {
            "metrics": self.metrics,
            "trades": self.strategy.trades,
            "results": self.results,
        }

    def report(self) -> str:
        """生成文本报告"""
        m = self.metrics
        lines = [
            "=" * 50,
            f"  回测报告 — {self.strategy.config.name}",
            "=" * 50,
            f"  初始资金:    ¥{self.cfg.initial_cash:>14,.0f}",
            f"  最终市值:    ¥{m.get('final_value', 0):>14,.0f}",
            f"  总收益率:    {m.get('total_return', 0):>13.2%}",
            f"  年化收益率:  {m.get('annual_return', 0):>13.2%}",
            f"  最大回撤:    {m.get('max_drawdown', 0):>13.2%}",
            f"  夏普比率:    {m.get('sharpe_ratio', 0):>13.2f}",
            f"  交易次数:    {m.get('trade_count', 0):>13d}",
            f"  胜率:        {m.get('win_rate', 0):>13.2%}",
            "-" * 50,
        ]
        return "\n".join(lines)
