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
from risk import RiskManager
from notify import NotifyHub, ConsoleNotifier, ServerChanNotifier, NotifyLevel
from utils.console import configure_utf8_console
import config

configure_utf8_console()


def _build_notify_hub() -> NotifyHub:
    cfg = config.NOTIFY
    notifiers = []
    if cfg.get("console_enabled", True):
        notifiers.append(ConsoleNotifier(log_file=cfg.get("log_file", "notify.log")))
    sendkey = cfg.get("serverchan_sendkey", "")
    if sendkey:
        notifiers.append(ServerChanNotifier(sendkey=sendkey))
    return NotifyHub(notifiers, min_level=cfg.get("min_level", "trade"))


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
    parser.add_argument("--no-risk", action="store_true", help="禁用风控（不推荐）")

    args = parser.parse_args()

    # 策略
    if args.strategy == "rsi":
        strategy = RSIStrategy(RSIConfig())
    else:
        strategy = MACrossStrategy(MACrossConfig())

    # 券商
    if args.qmt:
        from live.qmt_broker import QMTBroker
        broker = QMTBroker(account_id=args.account, qmt_path=args.qmt_path)
    else:
        broker = PaperBroker(initial_cash=args.cash)

    # 风控 + 通知
    risk_mgr = None if args.no_risk else RiskManager.from_config(config.RISK, is_live=True)
    hub = _build_notify_hub()

    trader = LiveTrader(
        strategy=strategy,
        broker=broker,
        symbols=args.symbols,
        poll_interval=args.interval,
        risk_manager=risk_mgr,
        notify_hub=hub,
    )

    print(trader.status())
    trader.start()


if __name__ == "__main__":
    main()
