"""风控模块

提供回测和实盘共用的风险管理器，由若干 RiskRule 组合。
"""

from .base import (
    RiskAction,
    RiskDecision,
    RiskContext,
    RiskRule,
    RiskManager,
)
from .rules import (
    MaxPositionRule,
    TotalPositionRule,
    StopLossRule,
    MaxDrawdownRule,
    DailyLossRule,
    TradingTimeRule,
)
from .config import RiskConfig

__all__ = [
    "RiskAction",
    "RiskDecision",
    "RiskContext",
    "RiskRule",
    "RiskManager",
    "RiskConfig",
    "MaxPositionRule",
    "TotalPositionRule",
    "StopLossRule",
    "MaxDrawdownRule",
    "DailyLossRule",
    "TradingTimeRule",
]
