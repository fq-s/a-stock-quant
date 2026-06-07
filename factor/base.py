"""因子抽象基类与注册表"""

from abc import ABC, abstractmethod
from typing import Dict, Type

import pandas as pd


class Factor(ABC):
    """因子抽象基类

    子类约定:
    - name: 因子名（唯一）
    - compute(df) -> pd.Series：输入 OHLCV DataFrame，输出与之等长的因子序列
      数据不足的位置返回 NaN，调用方应能处理
    """

    name: str = "base"

    @abstractmethod
    def compute(self, df: pd.DataFrame) -> pd.Series:
        """计算因子值

        Parameters
        ----------
        df : pd.DataFrame
            必须至少包含 close 列；部分因子还需 high/low

        Returns
        -------
        pd.Series  与 df 同长，索引保持一致
        """
        pass

    def __repr__(self):
        params = {k: v for k, v in self.__dict__.items() if not k.startswith("_")}
        return f"{self.__class__.__name__}({params})"


class FactorRegistry:
    """因子注册表

    用于通过名称构造因子实例，方便配置驱动。
    """

    _registry: Dict[str, Type[Factor]] = {}

    @classmethod
    def register(cls, factor_cls: Type[Factor]) -> Type[Factor]:
        """装饰器/手动注册"""
        cls._registry[factor_cls.__name__] = factor_cls
        return factor_cls

    @classmethod
    def get(cls, name: str, **params) -> Factor:
        if name not in cls._registry:
            raise KeyError(f"未注册的因子: {name}。已注册: {list(cls._registry)}")
        return cls._registry[name](**params)

    @classmethod
    def list(cls) -> list:
        return sorted(cls._registry.keys())

    @classmethod
    def clear(cls):
        """主要用于测试"""
        cls._registry.clear()
