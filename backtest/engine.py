"""回测引擎

模拟逐K线驱动策略，计算收益与风险指标。
"""

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from strategy.base import BaseStrategy, Signal, Trade
from utils.metrics import calc_metrics
from live.broker import Account, Position
from risk import RiskManager, RiskContext, RiskAction


@dataclass
class BacktestConfig:
    initial_cash: float = 1_000_000
    commission_rate: float = 0.0003     # 买入佣金 万三
    stamp_tax_rate: float = 0.001       # 卖出印花税 千一
    slippage: float = 0.001             # 滑点 0.1%
    position_size: float = 0.95         # 仓位比例（用多少现金买入）
    risk_manager: Optional[RiskManager] = None  # 风控管理器，与实盘共用同一套规则


class BacktestEngine:
    """回测引擎"""

    def __init__(self, strategy: BaseStrategy, config: Optional[BacktestConfig] = None):
        self.strategy = strategy
        self.cfg = config or BacktestConfig()
        self.results: Optional[pd.DataFrame] = None
        self.metrics: dict = {}

    def _make_context(self, df, idx, bar, cash, position, symbol="BACKTEST"):
        """构造风控上下文（用回测内部状态模拟实盘 account/positions）"""
        market_value = position * bar["close"]
        account = Account(
            total_assets=cash + market_value,
            cash=cash,
            market_value=market_value,
        )
        positions = []
        if position > 0:
            positions.append(Position(
                symbol=symbol,
                quantity=position,
                available=position,
                cost_price=self._avg_cost,
                current_price=bar["close"],
            ))
        return RiskContext(
            symbol=symbol,
            price=bar["close"],
            account=account,
            positions=positions,
            hist_df=df.iloc[: idx + 1],
            initial_cash=self.cfg.initial_cash,
            today_open_value=self.cfg.initial_cash,
            is_live=False,
        )

    def run(self, df: pd.DataFrame, symbol: str = "BACKTEST") -> dict:
        """运行回测

        Parameters
        ----------
        df : pd.DataFrame
            必须包含 date, open, high, low, close, volume
        symbol : str
            用于风控上下文，回测一般无所谓
        """
        self.strategy.df = df
        self.strategy.trades = []

        cash = self.cfg.initial_cash
        position = 0
        self._avg_cost = 0.0
        portfolio_values = []
        risk_mgr = self.cfg.risk_manager

        for idx in range(len(df)):
            bar = df.iloc[idx]

            # 持仓巡检：风控强制平仓（如止损）
            if risk_mgr and position > 0:
                ctx = self._make_context(df, idx, bar, cash, position, symbol)
                ctx.quantity = position
                for decision in risk_mgr.scan_positions(ctx):
                    sell_price = bar["close"] * (1 - self.cfg.slippage)
                    revenue = position * sell_price
                    tax = revenue * self.cfg.stamp_tax_rate
                    commission = revenue * self.cfg.commission_rate
                    cash += revenue - tax - commission
                    self.strategy.record_trade(
                        bar["date"], Signal.SELL, sell_price, position,
                        cash, 0, reason=f"风控:{decision.reason}",
                    )
                    position = 0
                    self._avg_cost = 0.0
                    break  # 一次平仓即可

            signal = self.strategy.on_bar(idx, bar, position, cash)

            if signal == Signal.BUY and position == 0:
                buy_price = bar["close"] * (1 + self.cfg.slippage)
                max_shares = int(cash * self.cfg.position_size / buy_price / 100) * 100

                if risk_mgr:
                    ctx = self._make_context(df, idx, bar, cash, position, symbol)
                    ctx.quantity = max_shares
                    ctx.price = buy_price
                    decision = risk_mgr.evaluate_buy(ctx)
                    if decision.action == RiskAction.REJECT:
                        portfolio_values.append(cash + position * bar["close"])
                        continue
                    if decision.adjusted_qty > 0:
                        max_shares = decision.adjusted_qty

                if max_shares >= 100:
                    cost = max_shares * buy_price * (1 + self.cfg.commission_rate)
                    if cost <= cash:
                        cash -= cost
                        position = max_shares
                        self._avg_cost = buy_price * (1 + self.cfg.commission_rate)
                        self.strategy.record_trade(
                            bar["date"], Signal.BUY, buy_price, max_shares,
                            cash, position, reason="策略买入"
                        )

            elif signal == Signal.SELL and position > 0:
                if risk_mgr:
                    ctx = self._make_context(df, idx, bar, cash, position, symbol)
                    ctx.quantity = position
                    decision = risk_mgr.evaluate_sell(ctx)
                    if decision.action == RiskAction.REJECT:
                        portfolio_values.append(cash + position * bar["close"])
                        continue

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
                self._avg_cost = 0.0

            portfolio_values.append(cash + position * bar["close"])

        # 生成结果 DataFrame
        self.results = df.copy()
        self.results["portfolio"] = portfolio_values
        self.results["benchmark"] = df["close"] / df["close"].iloc[0] * self.cfg.initial_cash

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
