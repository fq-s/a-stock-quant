"""实时交易引擎

将策略与券商对接，实现实时行情驱动的自动交易。
启动时自动加载历史数据，让策略有足够的上下文计算指标。
风控由 RiskManager 统一处理；通知由 NotifyHub 推送。
"""

import json
import os
import sys
import time
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from strategy.base import BaseStrategy, Signal
from .broker import BaseBroker, OrderSide, OrderStatus
from .paper_broker import PaperBroker
from risk import RiskManager, RiskContext, RiskAction
from notify import NotifyHub, ConsoleNotifier, formatter


class LiveTrader:
    """实时交易引擎"""

    def __init__(
        self,
        strategy: BaseStrategy,
        broker: Optional[BaseBroker] = None,
        symbols: Optional[list] = None,
        poll_interval: int = 60,
        risk_manager: Optional[RiskManager] = None,
        notify_hub: Optional[NotifyHub] = None,
        log_file: str = "",
        history_days: int = 120,
    ):
        self.strategy = strategy
        self.broker = broker or PaperBroker()
        self.symbols = symbols or ["000001"]
        self.poll_interval = poll_interval
        self.risk = risk_manager or RiskManager()
        self.hub = notify_hub or NotifyHub([ConsoleNotifier()])
        self.history_days = history_days
        self.log_file = log_file or os.path.join(
            os.path.dirname(__file__), "trade_log.jsonl"
        )
        self._running = False
        self._log = []
        # 每只股票的历史数据 + 实时数据
        self._hist_data: dict[str, pd.DataFrame] = {}
        # 当日开盘总资产，用于 DailyLossRule
        self._today_open_value: float = 0.0

    def start(self):
        """启动实时交易"""
        if not self.broker.connect():
            self.hub.error("券商连接失败", "无法启动实盘")
            return

        self._load_history()

        account = self.broker.get_account()
        self._today_open_value = account.total_assets

        self._running = True
        title, body = formatter.format_startup(
            self.strategy.config.name,
            self.symbols,
            历史=f"{self.history_days}天",
            轮询=f"{self.poll_interval}s",
            初始资产=f"¥{account.total_assets:,.0f}",
            风控规则=", ".join(r.name for r in self.risk.rules) or "无",
        )
        self.hub.info(title, body)

        try:
            while self._running:
                if self._is_trading_time():
                    self._tick()
                    time.sleep(self.poll_interval)
                else:
                    now = datetime.now()
                    t = (now.hour, now.minute)
                    if t < (9, 30):
                        wait = (9 - now.hour) * 60 + (30 - now.minute)
                    elif (11, 30) < t < (13, 0):
                        wait = (13 - now.hour) * 60 + (0 - now.minute)
                    else:
                        wait = 5
                    status = "休市" if now.weekday() < 5 else "周末"
                    print(f"  ⏸ {status}... {wait}分钟后检查", flush=True)
                    time.sleep(min(wait * 60, 300))

        except KeyboardInterrupt:
            print("\n⏹ 收到停止信号")
        finally:
            self.stop()

    def stop(self):
        self._running = False
        self.broker.disconnect()
        self.hub.info("实盘停止", f"策略 {self.strategy.config.name} 已停止")

    @staticmethod
    def _is_trading_time() -> bool:
        now = datetime.now()
        if now.weekday() >= 5:
            return False
        t = (now.hour, now.minute)
        return ((9, 30) <= t <= (11, 30)) or ((13, 0) <= t <= (15, 0))

    def _load_history(self):
        """加载历史K线数据"""
        from data.fetcher import fetch_daily

        end = datetime.now().strftime("%Y%m%d")
        start = (datetime.now() - timedelta(days=self.history_days)).strftime("%Y%m%d")

        for symbol in self.symbols:
            try:
                df = fetch_daily(symbol, start, end)
                self._hist_data[symbol] = df
                print(f"  ✓ {symbol} 历史数据: {len(df)}天")
            except Exception as e:
                print(f"  ⚠️ {symbol} 历史数据加载失败: {e}")
                self.hub.error(f"历史数据加载失败 {symbol}", str(e))

    def _build_ctx(self, symbol: str, price: float, account, positions, hist) -> RiskContext:
        return RiskContext(
            symbol=symbol,
            price=price,
            account=account,
            positions=positions,
            hist_df=hist,
            initial_cash=account.total_assets if self._today_open_value == 0 else self._today_open_value,
            today_open_value=self._today_open_value,
            is_live=True,
        )

    def _tick(self):
        """一次行情轮询 + 策略驱动"""
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        prices = self._fetch_prices()

        for symbol in self.symbols:
            try:
                price = prices.get(symbol, 0)
                if price <= 0:
                    continue

                print(f"  💰 {symbol} 现价: {price:.2f}", flush=True)

                account = self.broker.get_account()
                positions = self.broker.get_positions()
                hist = self._hist_data.get(symbol)

                # 持仓巡检：风控强制平仓（止损 / 回撤熔断等）
                ctx = self._build_ctx(symbol, price, account, positions, hist)
                for decision in self.risk.scan_positions(ctx):
                    pos_qty = next((p.quantity for p in positions if p.symbol == symbol), 0)
                    if pos_qty > 0:
                        self.broker.sell(symbol, price, pos_qty)
                        self._log_trade(now_str, symbol, "FORCE_CLOSE", price, pos_qty,
                                        f"{decision.rule}:{decision.reason}")
                        title, body = formatter.format_risk(
                            symbol, decision.rule, decision.reason, action="强制平仓")
                        self.hub.warning(title, body)
                    break  # 一次平仓即可

                # 策略信号需要完整历史数据
                if hist is None or len(hist) == 0:
                    continue

                today = pd.Timestamp.now().normalize()
                if hist["date"].iloc[-1] == today:
                    hist.iloc[-1, hist.columns.get_loc("close")] = price
                else:
                    new_row = pd.DataFrame([{
                        "date": today, "open": price, "high": price,
                        "low": price, "close": price, "volume": 0,
                    }])
                    hist = pd.concat([hist, new_row], ignore_index=True)
                    self._hist_data[symbol] = hist

                self.strategy.df = hist
                idx = len(hist) - 1
                bar = hist.iloc[idx]
                pos_qty = next((p.quantity for p in positions if p.symbol == symbol), 0)
                signal = self.strategy.on_bar(idx, bar, pos_qty, account.cash)

                if signal == Signal.BUY and pos_qty == 0:
                    # 默认按账户全仓评估，让风控决定实际下单量
                    plan_qty = int(account.total_assets / price / 100) * 100
                    ctx = self._build_ctx(symbol, price, account, positions, hist)
                    ctx.quantity = plan_qty
                    decision = self.risk.evaluate_buy(ctx)
                    if decision.action == RiskAction.REJECT:
                        title, body = formatter.format_risk(
                            symbol, decision.rule, decision.reason, action="拒绝买入")
                        self.hub.warning(title, body)
                        continue
                    qty = decision.adjusted_qty or plan_qty
                    if qty < 100:
                        continue
                    self.broker.buy(symbol, price, qty)
                    self._log_trade(now_str, symbol, "BUY", price, qty)
                    title, body = formatter.format_trade("BUY", symbol, price, qty,
                                                        account_cash=account.cash)
                    self.hub.trade(title, body)

                elif signal == Signal.SELL and pos_qty > 0:
                    ctx = self._build_ctx(symbol, price, account, positions, hist)
                    ctx.quantity = pos_qty
                    decision = self.risk.evaluate_sell(ctx)
                    if decision.action == RiskAction.REJECT:
                        title, body = formatter.format_risk(
                            symbol, decision.rule, decision.reason, action="拒绝卖出")
                        self.hub.warning(title, body)
                        continue
                    self.broker.sell(symbol, price, pos_qty)
                    self._log_trade(now_str, symbol, "SELL", price, pos_qty)
                    title, body = formatter.format_trade("SELL", symbol, price, pos_qty,
                                                        account_cash=account.cash)
                    self.hub.trade(title, body)

                # 更新持仓现价
                for p in positions:
                    if p.symbol == symbol:
                        p.current_price = price

            except Exception as e:
                print(f"  ⚠️ {symbol} 处理异常: {e}")
                self._log_trade(now_str, symbol, "ERROR", 0, 0, str(e))
                title, body = formatter.format_error(symbol, str(e))
                self.hub.error(title, body)

    def _log_trade(self, timestamp, symbol, action, price, quantity, msg=""):
        entry = {
            "time": timestamp, "symbol": symbol, "action": action,
            "price": price, "quantity": quantity, "msg": msg,
        }
        self._log.append(entry)
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:
            print(f"  ⚠️ 交易日志写入失败: {e}")

    def status(self) -> str:
        account = self.broker.get_account()
        positions = self.broker.get_positions()
        lines = [
            f"📊 实时交易状态",
            f"   策略: {self.strategy.config.name}",
            f"   总资产: ¥{account.total_assets:,.0f}",
            f"   现金:   ¥{account.cash:,.0f}",
            f"   市值:   ¥{account.market_value:,.0f}",
            f"   持仓:   {len(positions)}只",
        ]
        for p in positions:
            pnl_pct = (p.current_price - p.cost_price) / p.cost_price if p.cost_price > 0 else 0
            emoji = "🟢" if pnl_pct >= 0 else "🔴"
            lines.append(f"   {emoji} {p.symbol}: {p.quantity}股  成本{p.cost_price:.2f}  现价{p.current_price:.2f}  {pnl_pct:+.2%}")
        return "\n".join(lines)

    def _fetch_prices(self) -> dict:
        """批量获取实时价格（优先东方财富，降级新浪）"""
        from data.realtime import fetch_prices_em
        prices = fetch_prices_em(self.symbols)
        if prices:
            return prices

        print("  ⚠️ 东方财富行情失败，降级新浪")
        try:
            import requests
            codes = []
            for s in self.symbols:
                prefix = "sh" if s.startswith("6") else "sz"
                codes.append(f"{prefix}{s}")
            code_str = ",".join(codes)
            url = f"http://hq.sinajs.cn/list={code_str}"
            headers = {"Referer": "http://finance.sina.com.cn"}
            r = requests.get(url, headers=headers, timeout=5)
            if r.status_code == 200:
                for line in r.text.strip().split("\n"):
                    try:
                        code_part = line.split("=")[0].split("_")[-1]
                        data = line.split('="')[1].rstrip('";').split(',')
                        if len(data) > 3:
                            symbol = code_part[2:]
                            prices[symbol] = float(data[3])
                    except Exception:
                        pass
        except Exception as e:
            print(f"  ⚠️ 新浪行情也失败: {e}")
        return prices
