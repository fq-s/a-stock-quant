"""组合回测引擎

工作流：
1. 对齐多股票交易日历，按时间逐日推进
2. 每个调仓日：调用 strategy.on_rebalance 拿目标权重
3. 计算目标股数，先卖后买，扣手续费/印花税/滑点
4. 每根 K 线后更新组合市值，记录净值曲线
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from live.broker import Account, Position
from risk import RiskManager, RiskContext, RiskAction
from utils.metrics import calc_metrics
from strategy.base import Signal, Trade

from .strategy import PortfolioStrategy, TargetWeights
from .rebalance import RebalanceScheduler


@dataclass
class PortfolioBacktestConfig:
    initial_cash: float = 1_000_000
    commission_rate: float = 0.0003       # 双边万三
    stamp_tax_rate: float = 0.001         # 卖出印花税千一
    slippage: float = 0.001               # 滑点 0.1%
    rebalance_interval: int = 20          # 每 N 个交易日调仓
    min_trade_shares: int = 100           # 每手 100 股
    risk_manager: Optional[RiskManager] = None


@dataclass
class _Holding:
    """组合内的持仓状态"""
    symbol: str
    shares: int = 0
    cost_price: float = 0.0


class PortfolioBacktestEngine:
    """多股票组合回测引擎"""

    def __init__(self, strategy: PortfolioStrategy,
                 config: Optional[PortfolioBacktestConfig] = None):
        self.strategy = strategy
        self.cfg = config or PortfolioBacktestConfig()
        self.scheduler = RebalanceScheduler(interval=self.cfg.rebalance_interval)
        self.results: Optional[pd.DataFrame] = None
        self.metrics: dict = {}
        self.trades: List[Trade] = []
        self.rebalance_log: List[dict] = []

    def _align_calendar(self, universe_data: Dict[str, pd.DataFrame]) -> List[pd.Timestamp]:
        """取所有股票的并集交易日，按升序排列"""
        all_dates = set()
        for df in universe_data.values():
            all_dates.update(pd.to_datetime(df["date"]).tolist())
        return sorted(all_dates)

    def _price_at(self, df: pd.DataFrame, date: pd.Timestamp,
                  field: str = "close") -> Optional[float]:
        """取 date 当天的价格，没有则返回 None（停牌）"""
        match = df[df["date"] == date]
        if match.empty:
            return None
        v = match[field].iloc[0]
        return float(v) if pd.notna(v) else None

    def _portfolio_value(self, cash: float, holdings: Dict[str, _Holding],
                        prices: Dict[str, float]) -> float:
        mv = sum(h.shares * prices.get(s, h.cost_price)
                 for s, h in holdings.items())
        return cash + mv

    def _build_account(self, cash: float, holdings: Dict[str, _Holding],
                      prices: Dict[str, float]) -> Account:
        mv = sum(h.shares * prices.get(s, h.cost_price)
                 for s, h in holdings.items())
        return Account(total_assets=cash + mv, cash=cash, market_value=mv)

    def _build_positions(self, holdings: Dict[str, _Holding],
                        prices: Dict[str, float]) -> List[Position]:
        out = []
        for sym, h in holdings.items():
            if h.shares > 0:
                out.append(Position(
                    symbol=sym, quantity=h.shares, available=h.shares,
                    cost_price=h.cost_price,
                    current_price=prices.get(sym, h.cost_price),
                ))
        return out

    def _record(self, date, action: Signal, sym: str, price: float,
                shares: int, cash_after: float, reason: str = ""):
        self.trades.append(Trade(
            date=str(date), action=action, price=price, shares=shares,
            cash_after=cash_after, position_after=shares,
            reason=f"[{sym}] {reason}",
        ))

    def _rebalance(
        self,
        date: pd.Timestamp,
        target: TargetWeights,
        cash: float,
        holdings: Dict[str, _Holding],
        prices: Dict[str, float],
    ) -> float:
        """执行调仓：根据目标权重计算买卖单"""
        total_value = self._portfolio_value(cash, holdings, prices)
        target_weights = target.weights or {}

        # 计算目标股数
        target_shares: Dict[str, int] = {}
        for sym, w in target_weights.items():
            price = prices.get(sym)
            if price is None or price <= 0:
                continue
            raw = total_value * w / price
            lots = int(raw / self.cfg.min_trade_shares) * self.cfg.min_trade_shares
            if lots > 0:
                target_shares[sym] = lots

        risk_mgr = self.cfg.risk_manager

        # 1) 先卖：当前持有但不在目标里，或目标股数 < 当前
        for sym, h in list(holdings.items()):
            if h.shares <= 0:
                continue
            tgt = target_shares.get(sym, 0)
            if tgt >= h.shares:
                continue
            price = prices.get(sym)
            if price is None:  # 停牌，跳过
                continue
            sell_shares = h.shares - tgt
            sell_price = price * (1 - self.cfg.slippage)
            revenue = sell_shares * sell_price
            tax = revenue * self.cfg.stamp_tax_rate
            commission = revenue * self.cfg.commission_rate
            cash += revenue - tax - commission
            h.shares -= sell_shares
            if h.shares == 0:
                del holdings[sym]
            self._record(date, Signal.SELL, sym, sell_price, sell_shares,
                        cash, reason="调仓卖出")

        # 2) 再买：目标股数 > 当前
        for sym, tgt in target_shares.items():
            cur = holdings.get(sym, _Holding(symbol=sym)).shares
            if tgt <= cur:
                continue
            price = prices.get(sym)
            if price is None:
                continue
            buy_shares = tgt - cur
            buy_price = price * (1 + self.cfg.slippage)

            # 风控
            if risk_mgr:
                account = self._build_account(cash, holdings, prices)
                positions = self._build_positions(holdings, prices)
                ctx = RiskContext(
                    symbol=sym, price=buy_price, account=account,
                    positions=positions, hist_df=None,
                    initial_cash=self.cfg.initial_cash,
                    today_open_value=self.cfg.initial_cash,
                    is_live=False,
                )
                ctx.quantity = buy_shares
                decision = risk_mgr.evaluate_buy(ctx)
                if decision.action == RiskAction.REJECT:
                    self.rebalance_log.append({
                        "date": date, "symbol": sym, "action": "REJECT",
                        "reason": decision.reason,
                    })
                    continue
                if decision.adjusted_qty > 0:
                    buy_shares = (decision.adjusted_qty //
                                  self.cfg.min_trade_shares) * self.cfg.min_trade_shares

            if buy_shares < self.cfg.min_trade_shares:
                continue
            cost = buy_shares * buy_price * (1 + self.cfg.commission_rate)
            if cost > cash:
                # 现金不够，按现金能买的部分缩量
                affordable = int(cash / (buy_price * (1 + self.cfg.commission_rate))
                                 / self.cfg.min_trade_shares) * self.cfg.min_trade_shares
                if affordable < self.cfg.min_trade_shares:
                    continue
                buy_shares = affordable
                cost = buy_shares * buy_price * (1 + self.cfg.commission_rate)

            cash -= cost
            h = holdings.setdefault(sym, _Holding(symbol=sym))
            new_total = h.shares + buy_shares
            # 均价加权（含佣金）
            entry = buy_price * (1 + self.cfg.commission_rate)
            h.cost_price = ((h.cost_price * h.shares + entry * buy_shares)
                           / new_total if new_total else 0.0)
            h.shares = new_total
            self._record(date, Signal.BUY, sym, buy_price, buy_shares,
                        cash, reason="调仓买入")

        return cash

    def run(self, universe_data: Dict[str, pd.DataFrame]) -> dict:
        """运行组合回测

        Parameters
        ----------
        universe_data : Dict[str, pd.DataFrame]
            候选池数据，每个 df 须含 date/open/high/low/close/volume
        """
        if not universe_data:
            raise ValueError("候选池为空")

        # 标准化日期类型
        for df in universe_data.values():
            df["date"] = pd.to_datetime(df["date"])

        calendar = self._align_calendar(universe_data)
        if not calendar:
            raise ValueError("无可用交易日")

        rebalance_dates = set(self.scheduler.get_rebalance_dates(calendar))

        cash = self.cfg.initial_cash
        holdings: Dict[str, _Holding] = {}
        nav_curve: List[float] = []
        nav_dates: List[pd.Timestamp] = []

        for date in calendar:
            # 当日全市场价格
            prices: Dict[str, float] = {}
            for sym, df in universe_data.items():
                p = self._price_at(df, date, "close")
                if p is not None:
                    prices[sym] = p

            if date in rebalance_dates:
                # 调仓所需的历史数据切片：每只截至 date
                hist_slice = {
                    sym: df[df["date"] <= date].copy()
                    for sym, df in universe_data.items()
                }
                account = self._build_account(cash, holdings, prices)
                positions = self._build_positions(holdings, prices)
                target = self.strategy.on_rebalance(date, hist_slice, account, positions)
                self.rebalance_log.append({
                    "date": date, "symbols": list(target.weights.keys()),
                    "n": len(target.weights),
                })
                cash = self._rebalance(date, target, cash, holdings, prices)

            nav = self._portfolio_value(cash, holdings, prices)
            nav_curve.append(nav)
            nav_dates.append(date)

        # 结果
        self.results = pd.DataFrame({
            "date": nav_dates,
            "portfolio": nav_curve,
        })

        # benchmark：等权重 buy & hold（首日均买入，无调仓）
        first_prices = {}
        for sym, df in universe_data.items():
            p = self._price_at(df, calendar[0], "close")
            if p:
                first_prices[sym] = p
        if first_prices:
            per_sym_cash = self.cfg.initial_cash / len(first_prices)
            bench_shares = {sym: per_sym_cash / p for sym, p in first_prices.items()}
            bench_values = []
            for date in calendar:
                v = 0.0
                for sym, shares in bench_shares.items():
                    p = self._price_at(universe_data[sym], date, "close")
                    if p is None:
                        # 停牌沿用最近收盘价
                        prior = universe_data[sym][universe_data[sym]["date"] <= date]
                        p = prior["close"].iloc[-1] if not prior.empty else first_prices[sym]
                    v += shares * p
                bench_values.append(v)
            self.results["benchmark"] = bench_values
        else:
            self.results["benchmark"] = self.cfg.initial_cash

        self.metrics = calc_metrics(
            portfolio_values=nav_curve,
            benchmark_values=self.results["benchmark"].tolist(),
            initial_cash=self.cfg.initial_cash,
            trades=self.trades,
        )

        return {
            "metrics": self.metrics,
            "trades": self.trades,
            "results": self.results,
            "rebalance_log": self.rebalance_log,
        }

    def report(self) -> str:
        m = self.metrics
        lines = [
            "=" * 50,
            "  组合回测报告",
            "=" * 50,
            f"  初始资金:    ¥{self.cfg.initial_cash:>14,.0f}",
            f"  最终市值:    ¥{m.get('final_value', 0):>14,.0f}",
            f"  总收益率:    {m.get('total_return', 0):>13.2%}",
            f"  年化收益率:  {m.get('annual_return', 0):>13.2%}",
            f"  最大回撤:    {m.get('max_drawdown', 0):>13.2%}",
            f"  夏普比率:    {m.get('sharpe_ratio', 0):>13.2f}",
            f"  交易笔数:    {m.get('trade_count', 0):>13d}",
            f"  调仓次数:    {sum(1 for r in self.rebalance_log if 'symbols' in r):>13d}",
            "-" * 50,
        ]
        return "\n".join(lines)
