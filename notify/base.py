"""通知抽象层

- NotifyLevel：四级（info/trade/warning/error）
- NotifyMessage：消息数据类
- BaseNotifier：抽象渠道
- NotifyHub：聚合多渠道发送，按 min_level 过滤，失败容错
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional


class NotifyLevel(Enum):
    INFO = "info"        # 启动/停止/状态
    TRADE = "trade"      # 成交
    WARNING = "warning"  # 风控告警/止损
    ERROR = "error"      # 异常/连接失败


_LEVEL_ORDER = {
    NotifyLevel.INFO: 0,
    NotifyLevel.TRADE: 1,
    NotifyLevel.WARNING: 2,
    NotifyLevel.ERROR: 3,
}


def _level_from(value) -> NotifyLevel:
    if isinstance(value, NotifyLevel):
        return value
    return NotifyLevel(value)


@dataclass
class NotifyMessage:
    level: NotifyLevel
    title: str
    body: str = ""
    timestamp: str = field(
        default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )


class BaseNotifier(ABC):
    """通知渠道抽象基类"""

    name: str = "base"

    @abstractmethod
    def send(self, msg: NotifyMessage) -> bool:
        """发送消息，返回是否成功"""
        pass


class NotifyHub:
    """聚合多个 notifier，按级别过滤，任一失败不阻塞其他渠道"""

    def __init__(
        self,
        notifiers: Optional[List[BaseNotifier]] = None,
        min_level: NotifyLevel = NotifyLevel.TRADE,
    ):
        self.notifiers: List[BaseNotifier] = list(notifiers or [])
        self.min_level = _level_from(min_level)

    def add(self, notifier: BaseNotifier):
        self.notifiers.append(notifier)

    def send(self, msg: NotifyMessage) -> int:
        """返回成功送达的渠道数"""
        if _LEVEL_ORDER[msg.level] < _LEVEL_ORDER[self.min_level]:
            return 0
        ok = 0
        for n in self.notifiers:
            try:
                if n.send(msg):
                    ok += 1
            except Exception as e:
                # 通知失败不抛异常，仅打印
                print(f"  ⚠️ 通知渠道 {n.name} 发送失败: {e}")
        return ok

    # 便捷方法
    def info(self, title: str, body: str = "") -> int:
        return self.send(NotifyMessage(NotifyLevel.INFO, title, body))

    def trade(self, title: str, body: str = "") -> int:
        return self.send(NotifyMessage(NotifyLevel.TRADE, title, body))

    def warning(self, title: str, body: str = "") -> int:
        return self.send(NotifyMessage(NotifyLevel.WARNING, title, body))

    def error(self, title: str, body: str = "") -> int:
        return self.send(NotifyMessage(NotifyLevel.ERROR, title, body))
