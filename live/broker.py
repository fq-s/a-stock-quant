"""券商接口抽象基类

所有券商适配器继承此类，统一接口。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class OrderSide(Enum):
    BUY = "buy"
    SELL = "sell"


class OrderStatus(Enum):
    PENDING = "pending"       # 已报
    FILLED = "filled"         # 已成
    PARTIAL = "partial"       # 部成
    CANCELLED = "cancelled"   # 已撤
    REJECTED = "rejected"     # 废单


@dataclass
class Order:
    """订单"""
    order_id: str
    symbol: str           # 股票代码 "000001"
    side: OrderSide
    price: float
    quantity: int         # 股数
    status: OrderStatus = OrderStatus.PENDING
    filled_price: float = 0.0
    filled_quantity: int = 0
    created_at: str = ""
    message: str = ""


@dataclass
class Position:
    """持仓"""
    symbol: str
    name: str = ""
    quantity: int = 0         # 持仓数量
    available: int = 0        # 可卖数量
    cost_price: float = 0.0   # 成本价
    current_price: float = 0.0  # 现价
    pnl: float = 0.0          # 浮动盈亏


@dataclass
class Account:
    """账户信息"""
    total_assets: float = 0.0    # 总资产
    cash: float = 0.0            # 可用现金
    market_value: float = 0.0    # 持仓市值
    today_pnl: float = 0.0       # 当日盈亏
    positions: list = None        # 持仓列表

    def __post_init__(self):
        if self.positions is None:
            self.positions = []


class BaseBroker(ABC):
    """券商接口基类"""

    @abstractmethod
    def connect(self) -> bool:
        """连接券商"""
        pass

    @abstractmethod
    def disconnect(self):
        """断开连接"""
        pass

    @abstractmethod
    def get_account(self) -> Account:
        """查询账户"""
        pass

    @abstractmethod
    def get_positions(self) -> list:
        """查询持仓"""
        pass

    @abstractmethod
    def get_price(self, symbol: str) -> float:
        """获取实时价格"""
        pass

    @abstractmethod
    def buy(self, symbol: str, price: float, quantity: int) -> Order:
        """买入"""
        pass

    @abstractmethod
    def sell(self, symbol: str, price: float, quantity: int) -> Order:
        """卖出"""
        pass

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """撤单"""
        pass

    @abstractmethod
    def get_order(self, order_id: str) -> Order:
        """查询订单"""
        pass

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """连接状态"""
        pass
