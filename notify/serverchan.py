"""Server酱通知（微信推送）

需在 https://sct.ftqq.com/ 获取 SENDKEY。
"""

from typing import Optional

import requests

from .base import BaseNotifier, NotifyMessage


SCT_URL = "https://sctapi.ftqq.com/{sendkey}.send"


class ServerChanNotifier(BaseNotifier):
    """Server 酱推送"""

    name = "serverchan"

    def __init__(self, sendkey: str, timeout: float = 5.0):
        self.sendkey = sendkey
        self.timeout = timeout

    def send(self, msg: NotifyMessage) -> bool:
        if not self.sendkey:
            return False
        url = SCT_URL.format(sendkey=self.sendkey)
        title = f"[{msg.level.value.upper()}] {msg.title}"
        # Server 酱 title 限 32 字，多余截断
        if len(title) > 32:
            title = title[:31] + "…"
        body = f"**{msg.timestamp}**\n\n{msg.body}" if msg.body else f"**{msg.timestamp}**"
        try:
            r = requests.post(
                url,
                data={"title": title, "desp": body},
                timeout=self.timeout,
            )
            if r.status_code != 200:
                print(f"  ⚠️ Server酱推送失败: HTTP {r.status_code}")
                return False
            payload = r.json()
            if payload.get("code") not in (0, None):
                print(f"  ⚠️ Server酱业务错误: {payload}")
                return False
            return True
        except Exception as e:
            print(f"  ⚠️ Server酱网络异常: {e}")
            return False
