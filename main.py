"""量化回测主入口

用法:
    python main.py                    # 默认：平安银行，2024全年，双均线策略
    python main.py --stock 600519     # 指定股票（贵州茅台）
    python main.py --strategy rsi     # RSI策略
    python main.py --short 10 --long 30  # 自定义均线参数
"""

import argparse
import sys
import os

# 确保项目根目录在 path 中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data.fetcher import fetch_daily
from strategy.ma_cross import MACrossStrategy, MACrossConfig
from strategy.rsi_reversal import RSIStrategy, RSIConfig
from backtest.engine import BacktestEngine, BacktestConfig
from risk import RiskManager
from utils.console import configure_utf8_console
import config

configure_utf8_console()


def run_backtest(
    stock: str = "000001",
    start: str = "20240101",
    end: str = "20241231",
    strategy_name: str = "ma_cross",
    short_window: int = 5,
    long_window: int = 20,
    rsi_period: int = 14,
    rsi_oversold: float = 30,
    rsi_overbought: float = 70,
    initial_cash: float = 1_000_000,
    plot: bool = True,
    with_risk: bool = True,
):
    # 1. 获取数据
    print(f"\n📊 A股量化回测")
    print(f"   股票: {stock}  区间: {start} ~ {end}")
    df = fetch_daily(stock, start, end)
    if df.empty:
        print("❌ 数据为空，请检查股票代码和日期")
        return
    print(f"   数据: {len(df)} 个交易日\n")

    # 2. 创建策略
    if strategy_name == "rsi":
        cfg = RSIConfig(period=rsi_period, oversold=rsi_oversold, overbought=rsi_overbought)
        strategy = RSIStrategy(cfg)
        print(f"   策略: RSI均值回归 (period={rsi_period}, <{rsi_oversold}买, >{rsi_overbought}卖)")
    else:
        cfg = MACrossConfig(short_window=short_window, long_window=long_window)
        strategy = MACrossStrategy(cfg)
        print(f"   策略: 双均线交叉 (MA{short_window} x MA{long_window})")

    # 3. 回测
    risk_mgr = RiskManager.from_config(config.RISK) if (with_risk and config.RISK.get("enable_in_backtest", True)) else None
    if risk_mgr:
        print(f"   风控: {', '.join(r.name for r in risk_mgr.rules)}")
    bt_cfg = BacktestConfig(initial_cash=initial_cash, risk_manager=risk_mgr)
    engine = BacktestEngine(strategy, bt_cfg)
    result = engine.run(df, symbol=stock)

    # 4. 报告
    print(engine.report())

    # 5. 交易明细
    trades = result["trades"]
    if trades:
        print("\n📋 交易明细:")
        for t in trades:
            action = "买入" if "BUY" in str(t.action) else "卖出"
            print(f"  {t.date}  {action}  价格:{t.price:.2f}  数量:{t.shares}  {t.reason}")

    # 6. 绘图
    if plot:
        try:
            _plot_result(engine.results, stock, strategy.config.name)
        except Exception as e:
            print(f"\n⚠️  绘图失败: {e}（可忽略，不影响回测结果）")

    return result


def _plot_result(results, stock, strategy_name):
    """绘制回测曲线"""
    import matplotlib
    matplotlib.use("Agg")  # 无头模式
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    # 中文字体
    plt.rcParams["font.sans-serif"] = ["SimHei", "WenQuanYi Micro Hei", "Noto Sans CJK SC", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8), gridspec_kw={"height_ratios": [3, 1]})

    dates = results["date"]

    # 净值曲线
    ax1.plot(dates, results["portfolio"] / 1e6, label=f"策略({strategy_name})", color="royalblue", linewidth=1.5)
    ax1.plot(dates, results["benchmark"] / 1e6, label="买入持有", color="gray", linewidth=1, alpha=0.7)
    ax1.set_ylabel("市值 (百万)")
    ax1.set_title(f"回测净值 — {stock}")
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax1.xaxis.set_major_locator(mdates.MonthLocator(interval=2))

    # 成交量
    ax2.bar(dates, results["volume"] / 1e6, color="steelblue", alpha=0.5, width=1)
    ax2.set_ylabel("成交量 (百万)")
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax2.xaxis.set_major_locator(mdates.MonthLocator(interval=2))

    plt.tight_layout()

    output_path = os.path.join(os.path.dirname(__file__), "backtest_result.png")
    plt.savefig(output_path, dpi=150)
    plt.close()
    print(f"\n📈 回测图已保存: {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="A股量化回测")
    parser.add_argument("--stock", default="000001", help="股票代码 (默认: 000001 平安银行)")
    parser.add_argument("--start", default="20240101", help="开始日期 (默认: 20240101)")
    parser.add_argument("--end", default="20241231", help="结束日期 (默认: 20241231)")
    parser.add_argument("--strategy", default="ma_cross", choices=["ma_cross", "rsi"], help="策略选择")
    parser.add_argument("--short", type=int, default=5, help="短均线周期")
    parser.add_argument("--long", type=int, default=20, help="长均线周期")
    parser.add_argument("--rsi-period", type=int, default=14, help="RSI周期")
    parser.add_argument("--rsi-oversold", type=float, default=30, help="RSI超卖阈值")
    parser.add_argument("--rsi-overbought", type=float, default=70, help="RSI超买阈值")
    parser.add_argument("--cash", type=float, default=1_000_000, help="初始资金")
    parser.add_argument("--no-plot", action="store_true", help="不绘图")
    parser.add_argument("--no-risk", action="store_true", help="禁用风控（用于对比测试）")

    args = parser.parse_args()
    run_backtest(
        stock=args.stock,
        start=args.start,
        end=args.end,
        strategy_name=args.strategy,
        short_window=args.short,
        long_window=args.long,
        rsi_period=args.rsi_period,
        rsi_oversold=args.rsi_oversold,
        rsi_overbought=args.rsi_overbought,
        initial_cash=args.cash,
        plot=not args.no_plot,
        with_risk=not args.no_risk,
    )
