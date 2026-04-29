"""QMT/xtquant 实盘券商适配器

需要:
1. 开通支持QMT的券商账户（国金证券、华鑫证券等）
2. 安装 QMT 客户端并登录
3. pip install xtquant

注意: QMT客户端需要在Windows上运行，Python脚本可以远程连接。
"""

from typing import Optional

from .broker import BaseBroker, Account, Position, Order, OrderSide, OrderStatus


class QMTBroker(BaseBroker):
    """QMT实盘券商适配器"""

    def __init__(self, account_id: str = "", qmt_path: str = ""):
        """
        Parameters
        ----------
        account_id : str
            QMT资金账号
        qmt_path : str
            QMT安装路径 (如 "C:/国金QMT/userdata_mini")
        """
        self._account_id = account_id
        self._qmt_path = qmt_path
        self._connected = False
        self._xt_trader = None
        self._xt_account = None

    def connect(self) -> bool:
        try:
            from xtquant import xttrader
            from xtquant.xttrader import XtQuantTrader

            # 创建交易对象
            session_id = int(time.time() * 1000)
            self._xt_trader = XtQuantTrader(self._qmt_path, session_id)
            self._xt_trader.start()

            # 连接
            connect_result = self._xt_trader.connect()
            if connect_result == 0:
                self._connected = True
                # 订阅账户
                self._xt_account = self._xt_trader.get_stock_account(self._account_id)
                print(f"✅ QMT已连接 (账号: {self._account_id})")
                return True
            else:
                print(f"❌ QMT连接失败 (错误码: {connect_result})")
                return False
        except ImportError:
            print("❌ 未安装xtquant，请运行: pip install xtquant")
            return False
        except Exception as e:
            print(f"❌ QMT连接异常: {e}")
            return False

    def disconnect(self):
        if self._xt_trader:
            self._xt_trader.stop()
            self._connected = False
            print("📤 QMT已断开")

    @property
    def is_connected(self) -> bool:
        return self._connected

    def get_account(self) -> Account:
        if not self._connected:
            return Account()
        try:
            asset = self._xt_trader.query_asset(self._xt_account)
            return Account(
                total_assets=asset.total_asset,
                cash=asset.cash,
                market_value=asset.market_value,
                today_pnl=asset.today_profit,
            )
        except Exception as e:
            print(f"⚠️ 查询账户失败: {e}")
            return Account()

    def get_positions(self) -> list:
        if not self._connected:
            return []
        try:
            positions = self._xt_trader.query_stock_positions(self._xt_account)
            result = []
            for p in positions:
                if p.volume > 0:
                    result.append(Position(
                        symbol=p.stock_code,
                        quantity=p.volume,
                        available=p.can_use_volume,
                        cost_price=p.avg_price,
                        current_price=p.market_price,
                        pnl=p.market_price * p.volume - p.avg_price * p.volume,
                    ))
            return result
        except Exception as e:
            print(f"⚠️ 查询持仓失败: {e}")
            return []

    def get_price(self, symbol: str) -> float:
        try:
            from xtquant import xtdata
            code = self._to_xt_code(symbol)
            tick = xtdata.get_full_tick([code])
            if code in tick:
                return tick[code]["lastPrice"]
        except Exception as e:
            print(f"⚠️ 获取价格失败: {e}")
        return 0.0

    def buy(self, symbol: str, price: float, quantity: int) -> Order:
        if not self._connected:
            return self._error_order(symbol, OrderSide.BUY, price, quantity, "未连接")

        try:
            from xtquant.xttrader import XtQuantTraderHelper
            from xtquant.xttype import StockOrder

            code = self._to_xt_code(symbol)
            order_id = self._xt_trader.order_stock(
                self._xt_account,
                code,
                xttrader.STOCK_BUY,
                price,
                quantity,
                xttrader.FIX_PRICE,
            )

            return Order(
                order_id=str(order_id), symbol=symbol,
                side=OrderSide.BUY, price=price, quantity=quantity,
                status=OrderStatus.PENDING,
                message=f"委托已报 (QMT订单号: {order_id})",
            )
        except Exception as e:
            return self._error_order(symbol, OrderSide.BUY, price, quantity, str(e))

    def sell(self, symbol: str, price: float, quantity: int) -> Order:
        if not self._connected:
            return self._error_order(symbol, OrderSide.SELL, price, quantity, "未连接")

        try:
            import xttrader
            code = self._to_xt_code(symbol)
            order_id = self._xt_trader.order_stock(
                self._xt_account,
                code,
                xttrader.STOCK_SELL,
                price,
                quantity,
                xttrader.FIX_PRICE,
            )

            return Order(
                order_id=str(order_id), symbol=symbol,
                side=OrderSide.SELL, price=price, quantity=quantity,
                status=OrderStatus.PENDING,
                message=f"委托已报 (QMT订单号: {order_id})",
            )
        except Exception as e:
            return self._error_order(symbol, OrderSide.SELL, price, quantity, str(e))

    def cancel_order(self, order_id: str) -> bool:
        if not self._connected:
            return False
        try:
            result = self._xt_trader.cancel_order_stock(self._xt_account, int(order_id))
            return result == 0
        except:
            return False

    def get_order(self, order_id: str) -> Optional[Order]:
        if not self._connected:
            return None
        try:
            orders = self._xt_trader.query_stock_orders(self._xt_account)
            for o in orders:
                if str(o.order_id) == order_id:
                    status_map = {
                        48: OrderStatus.PENDING,
                        49: OrderStatus.PARTIAL,
                        50: OrderStatus.FILLED,
                        51: OrderStatus.CANCELLED,
                        52: OrderStatus.REJECTED,
                    }
                    return Order(
                        order_id=str(o.order_id),
                        symbol=o.stock_code,
                        side=OrderSide.BUY if o.order_type == 23 else OrderSide.SELL,
                        price=o.price,
                        quantity=o.order_volume,
                        status=status_map.get(o.order_status, OrderStatus.PENDING),
                        filled_price=o.traded_price,
                        filled_quantity=o.traded_volume,
                    )
        except:
            pass
        return None

    @staticmethod
    def _to_xt_code(symbol: str) -> str:
        """000001 -> SZ.000001, 600519 -> SH.600519"""
        clean = symbol.replace("SH.", "").replace("SZ.", "").replace("sh", "").replace("sz", "")
        prefix = "SH" if clean.startswith("6") else "SZ"
        return f"{prefix}.{clean}"

    @staticmethod
    def _error_order(symbol, side, price, quantity, msg):
        return Order(
            order_id="ERROR", symbol=symbol, side=side,
            price=price, quantity=quantity,
            status=OrderStatus.REJECTED, message=msg,
        )
