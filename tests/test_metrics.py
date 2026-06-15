"""测试 utils/metrics.py"""

import math

import pytest

from strategy.base import Trade, Signal
from utils.metrics import calc_metrics


def _make_trade(action: Signal, price: float) -> Trade:
    return Trade(date="2024-01-01", action=action, price=price, shares=100,
                 cash_after=0, position_after=0)


class TestTotalReturn:
    def test_positive(self):
        m = calc_metrics([100, 120], [100, 110], 100, [])
        assert m["total_return"] == pytest.approx(0.2)

    def test_loss(self):
        m = calc_metrics([100, 80], [100, 100], 100, [])
        assert m["total_return"] == pytest.approx(-0.2)

    def test_flat(self):
        m = calc_metrics([100, 100], [100, 100], 100, [])
        assert m["total_return"] == 0.0


class TestAnnualReturn:
    def test_full_year(self):
        # 252 个交易日翻倍
        values = [100] + [200] * 252
        m = calc_metrics(values, values, 100, [])
        # 总收益 100%，年化也约 100%
        assert m["annual_return"] == pytest.approx(1.0, rel=0.02)

    def test_short_period(self):
        # 1 个交易日 +10%
        m = calc_metrics([100, 110], [100, 100], 100, [])
        # 年化 = 1.1^(252/2) - 1，巨大
        assert m["annual_return"] > 100


class TestMaxDrawdown:
    def test_monotone_up_no_drawdown(self):
        m = calc_metrics([100, 110, 120, 130], [100] * 4, 100, [])
        assert m["max_drawdown"] == 0.0

    def test_v_shape(self):
        # peak=100，谷底 50 → 回撤 50%
        m = calc_metrics([100, 80, 50, 60, 70], [100] * 5, 100, [])
        assert m["max_drawdown"] == pytest.approx(0.5)

    def test_late_peak(self):
        # peak 出现在中间，之后跌
        m = calc_metrics([100, 200, 150], [100] * 3, 100, [])
        assert m["max_drawdown"] == pytest.approx(0.25)


class TestSharpe:
    def test_constant_returns_no_explosion(self):
        # 全 100，std=0 时不应抛异常或返回 inf
        m = calc_metrics([100, 100, 100, 100], [100] * 4, 100, [])
        assert m["sharpe_ratio"] == 0

    def test_positive_returns(self):
        # 稳定上涨，夏普应为正
        m = calc_metrics([100, 101, 102, 103, 104], [100] * 5, 100, [])
        assert m["sharpe_ratio"] > 0

    def test_negative_returns(self):
        m = calc_metrics([100, 99, 98, 97, 96], [100] * 5, 100, [])
        assert m["sharpe_ratio"] < 0


class TestWinRate:
    def test_all_wins(self):
        trades = [
            _make_trade(Signal.BUY, 10),
            _make_trade(Signal.SELL, 12),
            _make_trade(Signal.BUY, 10),
            _make_trade(Signal.SELL, 11),
        ]
        m = calc_metrics([100, 100], [100, 100], 100, trades)
        assert m["win_rate"] == 1.0
        assert m["trade_count"] == 4

    def test_half_wins(self):
        trades = [
            _make_trade(Signal.BUY, 10),
            _make_trade(Signal.SELL, 12),
            _make_trade(Signal.BUY, 10),
            _make_trade(Signal.SELL, 9),
        ]
        m = calc_metrics([100, 100], [100, 100], 100, trades)
        assert m["win_rate"] == 0.5

    def test_no_trades(self):
        m = calc_metrics([100, 100], [100, 100], 100, [])
        assert m["win_rate"] == 0
        assert m["trade_count"] == 0

    def test_unpaired_buy_only(self):
        trades = [_make_trade(Signal.BUY, 10)]
        m = calc_metrics([100, 100], [100, 100], 100, trades)
        assert m["win_rate"] == 0


class TestAlpha:
    def test_outperform(self):
        m = calc_metrics([100, 120], [100, 110], 100, [])
        assert m["alpha"] == pytest.approx(0.1)

    def test_underperform(self):
        m = calc_metrics([100, 105], [100, 120], 100, [])
        assert m["alpha"] == pytest.approx(-0.15)
