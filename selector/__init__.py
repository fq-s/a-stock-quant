"""选股器模块

基于因子库做多因子打分选股，支持指数成份股和自定义股票池。
"""

from .base import BaseSelector, SelectionResult
from .factor_selector import FactorSelector
from .universe import get_index_constituents, load_custom_universe

__all__ = [
    "BaseSelector",
    "SelectionResult",
    "FactorSelector",
    "get_index_constituents",
    "load_custom_universe",
]
