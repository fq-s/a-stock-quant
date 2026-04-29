"""模拟盘引擎

用真实行情数据，模拟下单和持仓，不花真钱。
适合验证策略在实时行情下的表现和风控逻辑。
"""

import json
import os
import time
from datetime import datetime
from typing import Optional

from .broker import BaseBroker, Account, Position, Order, OrderSide, OrderStatus


class PaperBroker(BaseBroker):
    """模拟盘券商

    - 用真实行情（akshare）
    - 模拟下单、成交、持仓
    - 状态持久化到 JSON 文件
    """

    def __init__(self, initial_cash: float = 1_000_000, state_file: str = ""):
        self._connected = False
        self._state_file = state_file or os.path.join(
            os.path.dirname(__file__), "paper_state.json"
        )
        self._account = Account(cash=initial_cash, total_assets=initial_cash)
        self._positions: dict[str, Position] = {}
        self._orders: list[Order] = []
        self._order_counter = 0

        # 加载已有状态
        self._load_state()

    def connect(self) -> bool:
        self._connected = True
        print("✅ 模拟盘已连接")
        return True

    def disconnect(self):
        self._save_state()
        self._connected = False
        print("📤 模拟盘已断开，状态已保存")

    @property
    def is_connected(self) -> bool:
        return self._connected

    def get_account(self) -> Account:
        # 更新持仓市值
        market_value = sum(
            p.current_price * p.quantity for p in self._positions.values()
        )
        self._account.market_value = market_value
        self._account.total_assets = self._account.cash + market_value
        self._account.positions = list(self._positions.values())
        return self._account

    def get_positions(self) -> list:
        return list(self._positions.values())

    def get_price(self, symbol: str) -> float:
        """获取实时价格（新浪行情接口，秒级响应）"""
        try:
            import requests
            prefix = "sh" if symbol.startswith("6") else "sz"
            code = f"{prefix}{symbol}"
            url = f"http://hq.sinajs.cn/list={code}"
            headers = {"Referer": "http://finance.sina.com.cn"}
            r = requests.get(url, headers=headers, timeout=5)
            if r.status_code == 200:
                data = r.text.split('="')[1].split('"')[0]
                fields = data.split(",")
                if len(fields) > 3:
                    return float(fields[3])  # 当前价格
        except Exception as e:
            print(f"  ⚠️ 获取实时价格失败 {symbol}: {e}")
        return 0.0

    def buy(self, symbol: str, price: float, quantity: int) -> Order:
        """模拟买入

        A股规则: 必须整手(100股起), 佣金万三
        """
        if quantity < 100 or quantity % 100 != 0:
            return Order(
                order_id=self._next_order_id(), symbol=symbol,
                side=OrderSide.BUY, price=price, quantity=quantity,
                status=OrderStatus.REJECTED, message="数量必须为100的整数倍",
            )

        cost = price * quantity * 1.0003  # 含佣金
        if cost > self._account.cash:
            return Order(
                order_id=self._next_order_id(), symbol=symbol,
                side=OrderSide.BUY, price=price, quantity=quantity,
                status=OrderStatus.REJECTED, message=f"资金不足(需{cost:.0f}, 有{self._account.cash:.0f})",
            )

        # 扣款
        self._account.cash -= cost
        self._order_counter += 1

        # 更新持仓
        if symbol in self._positions:
            pos = self._positions[symbol]
            total_cost = pos.cost_price * pos.quantity + price * quantity
            pos.quantity += quantity
            pos.cost_price = total_cost / pos.quantity
            pos.current_price = price
        else:
            self._positions[symbol] = Position(
                symbol=symbol, quantity=quantity, available=0,
                cost_price=price, current_price=price,
            )

        order = Order(
            order_id=self._next_order_id(), symbol=symbol,
            side=OrderSide.BUY, price=price, quantity=quantity,
            status=OrderStatus.FILLED, filled_price=price,
            filled_quantity=quantity, created_at=datetime.now().isoformat(),
            message="模拟成交",
        )
        self._orders.append(order)
        self._save_state()

        print(f"  🟢 买入 {symbol} × {quantity} @ {price:.2f}  花费: {cost:.0f}")
        return order

    def sell(self, symbol: str, price: float, quantity: int) -> Order:
        """模拟卖出

        A股规则: 印花税千一(卖出), 佣金万三
        """
        if symbol not in self._positions:
            return Order(
                order_id=self._next_order_id(), symbol=symbol,
                side=OrderSide.SELL, price=price, quantity=quantity,
                status=OrderStatus.REJECTED, message="无持仓",
            )

        pos = self._positions[symbol]
        if quantity > pos.available:
            return Order(
                order_id=self._next_order_id(), symbol=symbol,
                side=OrderSide.SELL, price=price, quantity=quantity,
                status=OrderStatus.REJECTED,
                message=f"可卖不足(可卖{pos.available}, 欲卖{quantity})",
            )

        revenue = price * quantity * (1 - 0.001 - 0.0003)  # 扣印花税+佣金
        self._account.cash += revenue

        pos.quantity -= quantity
        pos.available -= quantity
        pos.current_price = price
        if pos.quantity <= 0:
            del self._positions[symbol]

        order = Order(
            order_id=self._next_order_id(), symbol=symbol,
            side=OrderSide.SELL, price=price, quantity=quantity,
            status=OrderStatus.FILLED, filled_price=price,
            filled_quantity=quantity, created_at=datetime.now().isoformat(),
            message="模拟成交",
        )
        self._orders.append(order)
        self._save_state()

        print(f"  🔴 卖出 {symbol} × {quantity} @ {price:.2f}  到账: {revenue:.0f}")
        return order

    def cancel_order(self, order_id: str) -> bool:
        # 模拟盘即时成交，不支持撤单
        return False

    def get_order(self, order_id: str) -> Optional[Order]:
        for o in self._orders:
            if o.order_id == order_id:
                return o
        return None

    def get_all_orders(self) -> list:
        return self._orders

    def update_available(self):
        """T+1更新: 将昨日买入的股数变为可卖"""
        for pos in self._positions.values():
            pos.available = pos.quantity

    def _next_order_id(self) -> str:
        self._order_counter += 1
        return f"PAPER_{self._order_counter:06d}"

    def _save_state(self):
        """持久化账户状态"""
        state = {
            "cash": self._account.cash,
            "positions": {
                sym: {
                    "symbol": p.symbol, "name": p.name,
                    "quantity": p.quantity, "available": p.available,
                    "cost_price": p.cost_price, "current_price": p.current_price,
                }
                for sym, p in self._positions.items()
            },
            "orders": [
                {
                    "order_id": o.order_id, "symbol": o.symbol,
                    "side": o.side.value, "price": o.price,
                    "quantity": o.quantity, "status": o.status.value,
                    "filled_price": o.filled_price, "filled_quantity": o.filled_quantity,
                    "created_at": o.created_at, "message": o.message,
                }
                for o in self._orders
            ],
            "updated_at": datetime.now().isoformat(),
        }
        with open(self._state_file, "w") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)

    def _load_state(self):
        """加载已有状态"""
        if not os.path.exists(self._state_file):
            return
        try:
            with open(self._state_file) as f:
                state = json.load(f)
            self._account.cash = state.get("cash", self._account.cash)
            for sym, p in state.get("positions", {}).items():
                self._positions[sym] = Position(**p)
            for o in state.get("orders", []):
                o["side"] = OrderSide(o["side"])
                o["status"] = OrderStatus(o["status"])
                self._orders.append(Order(**o))
            print(f"  ✓ 已加载模拟盘状态 (现金: {self._account.cash:,.0f}, 持仓: {len(self._positions)}只)")
        except Exception as e:
            print(f"  ⚠️ 加载模拟盘状态失败: {e}")
