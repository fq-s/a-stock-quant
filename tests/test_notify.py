"""测试 notify/ 模块"""

import json
import os

import pytest

from notify import (
    NotifyHub,
    NotifyLevel,
    NotifyMessage,
    BaseNotifier,
    ConsoleNotifier,
    ServerChanNotifier,
)


class _Collector(BaseNotifier):
    name = "collector"
    def __init__(self):
        self.received = []
    def send(self, msg):
        self.received.append(msg)
        return True


class _Failing(BaseNotifier):
    name = "failing"
    def send(self, msg):
        raise RuntimeError("boom")


class TestNotifyHub:
    def test_min_level_filter(self):
        c = _Collector()
        hub = NotifyHub([c], min_level=NotifyLevel.WARNING)
        hub.info("ignore me")
        hub.trade("also ignore")
        hub.warning("keep")
        hub.error("keep too")
        assert len(c.received) == 2
        assert c.received[0].level == NotifyLevel.WARNING

    def test_multi_notifier(self):
        c1, c2 = _Collector(), _Collector()
        hub = NotifyHub([c1, c2], min_level=NotifyLevel.INFO)
        hub.info("hi")
        assert len(c1.received) == 1
        assert len(c2.received) == 1

    def test_failure_does_not_block_others(self):
        c = _Collector()
        hub = NotifyHub([_Failing(), c], min_level=NotifyLevel.INFO)
        ok = hub.info("hi")
        assert ok == 1
        assert len(c.received) == 1

    def test_min_level_accepts_string(self):
        hub = NotifyHub([_Collector()], min_level="warning")
        assert hub.min_level == NotifyLevel.WARNING


class TestConsoleNotifier:
    def test_writes_jsonl(self, tmp_path, capsys):
        log = tmp_path / "notify.log"
        n = ConsoleNotifier(log_file=str(log))
        msg = NotifyMessage(NotifyLevel.TRADE, "买入 000001", "数量 1000")
        assert n.send(msg) is True

        # 验证文件内容
        lines = log.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["level"] == "trade"
        assert data["title"] == "买入 000001"
        assert data["body"] == "数量 1000"

        # 控制台输出
        out = capsys.readouterr().out
        assert "买入 000001" in out

    def test_no_log_file(self, capsys):
        n = ConsoleNotifier()
        assert n.send(NotifyMessage(NotifyLevel.INFO, "hi")) is True
        out = capsys.readouterr().out
        assert "hi" in out


class TestServerChanNotifier:
    def test_empty_sendkey_returns_false(self):
        n = ServerChanNotifier(sendkey="")
        assert n.send(NotifyMessage(NotifyLevel.INFO, "x")) is False

    def test_success(self, monkeypatch):
        calls = {}

        class FakeResp:
            status_code = 200
            def json(self):
                return {"code": 0}

        def fake_post(url, data=None, timeout=None):
            calls["url"] = url
            calls["data"] = data
            return FakeResp()

        monkeypatch.setattr("notify.serverchan.requests.post", fake_post)
        n = ServerChanNotifier(sendkey="abc123")
        ok = n.send(NotifyMessage(NotifyLevel.WARNING, "止损", "亏 8%"))
        assert ok is True
        assert "abc123" in calls["url"]
        assert "止损" in calls["data"]["title"]
        assert "亏 8%" in calls["data"]["desp"]

    def test_http_error_no_raise(self, monkeypatch, capsys):
        class FakeResp:
            status_code = 500
            def json(self):
                return {}

        monkeypatch.setattr("notify.serverchan.requests.post",
                            lambda *a, **kw: FakeResp())
        n = ServerChanNotifier(sendkey="abc")
        assert n.send(NotifyMessage(NotifyLevel.INFO, "x")) is False

    def test_network_exception_no_raise(self, monkeypatch):
        def raise_(*a, **kw):
            raise ConnectionError("net down")
        monkeypatch.setattr("notify.serverchan.requests.post", raise_)
        n = ServerChanNotifier(sendkey="abc")
        assert n.send(NotifyMessage(NotifyLevel.INFO, "x")) is False

    def test_title_truncated(self, monkeypatch):
        captured = {}
        class FakeResp:
            status_code = 200
            def json(self): return {"code": 0}
        def fake_post(url, data=None, timeout=None):
            captured["title"] = data["title"]
            return FakeResp()
        monkeypatch.setattr("notify.serverchan.requests.post", fake_post)
        n = ServerChanNotifier(sendkey="x")
        long_title = "标的" * 20  # 远超 32 字
        n.send(NotifyMessage(NotifyLevel.INFO, long_title))
        assert len(captured["title"]) <= 32
