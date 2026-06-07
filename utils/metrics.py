"""回测指标计算"""

import math
from typing import List

from strategy.base import Trade, Signal


def calc_metrics(
    portfolio_values: List[float],
    benchmark_values: List[float],
    initial_cash: float,
    trades: List[Trade],
) -> dict:
    """计算核心回测指标"""

    n = len(portfolio_values)
    final_value = portfolio_values[-1]
    total_return = (final_value - initial_cash) / initial_cash

    # 年化收益率（按252个交易日）
    trading_days = n
    annual_return = (1 + total_return) ** (252 / max(trading_days, 1)) - 1 if trading_days > 0 else 0

    # 日收益率序列
    daily_returns = []
    for i in range(1, n):
        if portfolio_values[i - 1] > 0:
            daily_returns.append((portfolio_values[i] - portfolio_values[i - 1]) / portfolio_values[i - 1])
        else:
            daily_returns.append(0)

    # 最大回撤
    peak = portfolio_values[0]
    max_dd = 0
    for v in portfolio_values:
        if v > peak:
            peak = v
        dd = (peak - v) / peak
        if dd > max_dd:
            max_dd = dd

    # 夏普比率（无风险利率取3%）
    rf_daily = 0.03 / 252
    if len(daily_returns) > 1:
        excess_returns = [r - rf_daily for r in daily_returns]
        mean_excess = sum(excess_returns) / len(excess_returns)
        std = math.sqrt(sum((r - mean_excess) ** 2 for r in excess_returns) / (len(excess_returns) - 1))
        sharpe = (mean_excess / std) * math.sqrt(252) if std > 0 else 0
    else:
        sharpe = 0

    # 交易统计
    trade_count = len(trades)
    buy_trades = [t for t in trades if t.action == Signal.BUY]
    sell_trades = [t for t in trades if t.action == Signal.SELL]

    # 配对计算盈亏
    wins = 0
    for i in range(min(len(buy_trades), len(sell_trades))):
        if sell_trades[i].price > buy_trades[i].price:
            wins += 1
    total_pairs = min(len(buy_trades), len(sell_trades))
    win_rate = wins / total_pairs if total_pairs > 0 else 0

    # 超额收益（相对基准）
    benchmark_final = benchmark_values[-1] if benchmark_values else initial_cash
    benchmark_return = (benchmark_final - initial_cash) / initial_cash
    alpha = total_return - benchmark_return

    return {
        "final_value": final_value,
        "total_return": total_return,
        "annual_return": annual_return,
        "max_drawdown": max_dd,
        "sharpe_ratio": sharpe,
        "trade_count": trade_count,
        "win_rate": win_rate,
        "alpha": alpha,
    }
