"""实时交易入口

用法:
    # 模拟盘（默认，不花真钱）
    python live_main.py --symbols 000001 600519 --paper

    # QMT实盘
    python live_main.py --symbols 000001 --qmt --account 12345678 --qmt-path /path/to/qmt
"""

import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from strategy.ma_cross import MACrossStrategy, MACrossConfig
from strategy.rsi_reversal import RSIStrategy, RSIConfig
from live.paper_broker import PaperBroker
from live.trader import LiveTrader


def main():
    parser = argparse.ArgumentParser(description="A股实时交易")
    parser.add_argument("--symbols", nargs="+", default=["000001"], help="监控股票列表")
    parser.add_argument("--strategy", default="ma_cross", choices=["ma_cross", "rsi"])
    parser.add_argument("--paper", action="store_true", default=True, help="模拟盘模式")
    parser.add_argument("--qmt", action="store_true", help="QMT实盘模式")
    parser.add_argument("--account", default="", help="QMT资金账号")
    parser.add_argument("--qmt-path", default="", help="QMT安装路径")
    parser.add_argument("--cash", type=float, default=1_000_000, help="模拟盘初始资金")
    parser.add_argument("--interval", type=int, default=60, help="轮询间隔(秒)")
    parser.add_argument("--max-position", type=float, default=0.3, help="单股最大仓位")
    parser.add_argument("--stop-loss", type=float, default=0.07, help="止损线")

    args = parser.parse_args()

    # 创建策略
    if args.strategy == "rsi":
        strategy = RSIStrategy(RSIConfig())
    else:
        strategy = MACrossStrategy(MACrossConfig())

    # 创建券商
    broker = None
    if args.qmt:
        from live.qmt_broker import QMTBroker
        broker = QMTBroker(account_id=args.account, qmt_path=args.qmt_path)
    else:
        broker = PaperBroker(initial_cash=args.cash)

    # 创建交易引擎
    trader = LiveTrader(
        strategy=strategy,
        broker=broker,
        symbols=args.symbols,
        poll_interval=args.interval,
        max_position_pct=args.max_position,
        stop_loss_pct=args.stop_loss,
    )

    # 启动
    print(trader.status())
    trader.start()


if __name__ == "__main__":
    main()
