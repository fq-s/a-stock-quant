"""共享 pytest fixture"""

import os
import sys

import pandas as pd
import pytest

# 确保项目根目录在 sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from live.broker import Account, Position


@pytest.fixture
def sample_df() -> pd.DataFrame:
    """30 根 K 线的样本数据，价格从 10 缓慢上升到 13"""
    dates = pd.date_range("2024-01-01", periods=30, freq="D")
    closes = [10 + i * 0.1 for i in range(30)]
    return pd.DataFrame({
        "date": dates,
        "open": closes,
        "high": [c + 0.1 for c in closes],
        "low": [c - 0.1 for c in closes],
        "close": closes,
        "volume": [10000] * 30,
    })


@pytest.fixture
def fake_account() -> Account:
    return Account(
        total_assets=1_000_000,
        cash=1_000_000,
        market_value=0,
    )


@pytest.fixture
def fake_position() -> Position:
    return Position(
        symbol="000001",
        quantity=1000,
        available=1000,
        cost_price=10.0,
        current_price=10.0,
    )
