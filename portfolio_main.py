"""组合回测主入口

用法：
    # 默认：沪深300 选 10 只、20 日调仓、2024 年
    python portfolio_main.py

    # 自定义参数
    python portfolio_main.py --universe 000905 --top 15 --rebalance 10 \
        --start 20240101 --end 20241231

    # 用本地 CSV 股票池
    python portfolio_main.py --custom my_universe.csv --top 5
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from data.fetcher import fetch_daily_batch
from factor import Momentum, Volatility, Return
from portfolio import (
    PortfolioBacktestConfig,
    PortfolioBacktestEngine,
    SelectorPortfolioStrategy,
)
from risk import RiskManager
from selector import FactorSelector, get_index_constituents, load_custom_universe
from utils.console import configure_utf8_console

configure_utf8_console()


def run_portfolio_backtest(
    universe_code: str = "000300",
    custom_path: str = "",
    top_n: int = 10,
    rebalance_interval: int = 20,
    start: str = "20240101",
    end: str = "20241231",
    initial_cash: float = 1_000_000,
    limit_symbols: int = 0,
    with_risk: bool = True,
    plot: bool = True,
):
    # 1. 获取股票池
    if custom_path:
        print(f"\n📁 读取自定义股票池: {custom_path}")
        symbols = load_custom_universe(custom_path)
    else:
        print(f"\n📊 组合回测 — 股票池 {universe_code}")
        symbols = get_index_constituents(universe_code)

    if limit_symbols and limit_symbols < len(symbols):
        symbols = symbols[:limit_symbols]
        print(f"   ⚠️  已截取前 {limit_symbols} 只用于快速测试")
    print(f"   候选池: {len(symbols)} 只")

    # 2. 批量拉数据（首跑较慢，后续走 cache）
    print(f"   下载行情 {start} ~ {end} ...")
    universe_data = fetch_daily_batch(symbols, start, end)
    if not universe_data:
        print("❌ 无可用数据")
        return None

    # 3. 选股器 + 组合策略
    selector = FactorSelector(
        factors=[
            (Momentum(window=20), 0.5),
            (Volatility(window=20), -0.3),
            (Return(window=5), -0.2),
        ],
        lookback_days=config.PORTFOLIO.get("lookback_days", 60),
    )
    strategy = SelectorPortfolioStrategy(
        selector=selector,
        top_n=top_n,
        cash_buffer=config.PORTFOLIO.get("cash_buffer", 0.02),
    )

    # 4. 回测
    risk_mgr = None
    if with_risk and config.RISK.get("enable_in_backtest", True):
        risk_mgr = RiskManager.from_config(config.RISK)
        print(f"   风控: {', '.join(r.name for r in risk_mgr.rules)}")

    bt_cfg = PortfolioBacktestConfig(
        initial_cash=initial_cash,
        rebalance_interval=rebalance_interval,
        risk_manager=risk_mgr,
    )
    print(f"   调仓周期: {rebalance_interval} 个交易日，选 top {top_n}")
    engine = PortfolioBacktestEngine(strategy, bt_cfg)
    result = engine.run(universe_data)

    # 5. 报告
    print(engine.report())

    # 6. 调仓明细
    print("\n📋 调仓明细:")
    for log in result["rebalance_log"]:
        if "symbols" in log:
            syms = log["symbols"][:5]
            extra = f" (+{len(log['symbols']) - 5} 更多)" if len(log["symbols"]) > 5 else ""
            print(f"  {log['date'].date()}  选中 {log['n']} 只: {', '.join(syms)}{extra}")
        elif "action" in log and log["action"] == "REJECT":
            print(f"  {log['date'].date()}  ⚠️  风控拒绝: {log['symbol']} ({log['reason']})")

    # 7. 绘图
    if plot:
        try:
            _plot_result(engine.results, universe_code or "custom")
        except Exception as e:
            print(f"\n⚠️  绘图失败: {e}")

    return result


def _plot_result(results, universe_label):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt

    plt.rcParams["font.sans-serif"] = ["SimHei", "WenQuanYi Micro Hei", "Noto Sans CJK SC", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False

    fig, ax = plt.subplots(figsize=(14, 6))
    dates = results["date"]
    ax.plot(dates, results["portfolio"] / 1e6, label="组合策略", color="royalblue", linewidth=1.5)
    ax.plot(dates, results["benchmark"] / 1e6, label="等权基准", color="gray", linewidth=1, alpha=0.7)
    ax.set_ylabel("市值 (百万)")
    ax.set_title(f"组合回测净值 — {universe_label}")
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))

    plt.tight_layout()
    out = os.path.join(os.path.dirname(__file__), "portfolio_result.png")
    plt.savefig(out, dpi=150)
    plt.close()
    print(f"\n📈 组合净值图已保存: {out}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="A股组合回测（因子选股 + 定期调仓）")
    parser.add_argument("--universe", default=config.PORTFOLIO.get("universe", "000300"),
                        choices=["000300", "000905", "000852", "000016"],
                        help="指数代码")
    parser.add_argument("--custom", default="", help="自定义股票池 CSV 路径（指定后忽略 --universe）")
    parser.add_argument("--top", type=int, default=config.PORTFOLIO.get("top_n", 10),
                        help="选股数量")
    parser.add_argument("--rebalance", type=int,
                        default=config.PORTFOLIO.get("rebalance_interval", 20),
                        help="调仓周期（交易日）")
    parser.add_argument("--start", default="20240101", help="开始日期")
    parser.add_argument("--end", default="20241231", help="结束日期")
    parser.add_argument("--cash", type=float, default=1_000_000, help="初始资金")
    parser.add_argument("--limit", type=int, default=0,
                        help="只取股票池前 N 只（用于快速测试，0=全部）")
    parser.add_argument("--no-risk", action="store_true", help="禁用风控")
    parser.add_argument("--no-plot", action="store_true", help="不绘图")
    args = parser.parse_args()

    run_portfolio_backtest(
        universe_code=args.universe,
        custom_path=args.custom,
        top_n=args.top,
        rebalance_interval=args.rebalance,
        start=args.start,
        end=args.end,
        initial_cash=args.cash,
        limit_symbols=args.limit,
        with_risk=not args.no_risk,
        plot=not args.no_plot,
    )
