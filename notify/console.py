"""控制台 + 文件通知

零依赖兜底通道。
"""

import json
import os
from typing import Optional

from .base import BaseNotifier, NotifyMessage, NotifyLevel


_EMOJI = {
    NotifyLevel.INFO: "ℹ️",
    NotifyLevel.TRADE: "💱",
    NotifyLevel.WARNING: "⚠️",
    NotifyLevel.ERROR: "❌",
}


class ConsoleNotifier(BaseNotifier):
    """打印到终端，同时追加写 JSONL 日志文件"""

    name = "console"

    def __init__(self, log_file: Optional[str] = None):
        self.log_file = log_file

    def send(self, msg: NotifyMessage) -> bool:
        emoji = _EMOJI.get(msg.level, "·")
        print(f"  {emoji} [{msg.timestamp}] {msg.title}", flush=True)
        if msg.body:
            for line in msg.body.splitlines():
                print(f"     {line}", flush=True)

        if self.log_file:
            try:
                os.makedirs(os.path.dirname(os.path.abspath(self.log_file)), exist_ok=True)
                with open(self.log_file, "a", encoding="utf-8") as f:
                    f.write(json.dumps({
                        "time": msg.timestamp,
                        "level": msg.level.value,
                        "title": msg.title,
                        "body": msg.body,
                    }, ensure_ascii=False) + "\n")
            except Exception as e:
                print(f"  ⚠️ 通知日志写入失败: {e}")
                return False
        return True
