"""风控核心抽象

- RiskAction / RiskDecision：决策结果
- RiskContext：传给规则的上下文
- RiskRule：抽象规则
- RiskManager：组合多条规则
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

import pandas as pd

from live.broker import Account, Position


class RiskAction(Enum):
    ALLOW = "allow"               # 放行
    REJECT = "reject"             # 拒绝下单
    FORCE_CLOSE = "force_close"   # 强制平仓


@dataclass
class RiskDecision:
    """风控决策结果"""
    action: RiskAction
    rule: str = ""
    reason: str = ""
    adjusted_qty: int = 0   # ALLOW 但需调整下单量时使用，0 表示不调整


ALLOW = RiskDecision(action=RiskAction.ALLOW)


@dataclass
class RiskContext:
    """规则评估上下文

    回测和实盘共用：实盘从 broker 拉取 account/positions，
    回测由引擎本地构造一份等价结构。
    """
    symbol: str
    price: float
    quantity: int = 0                    # 计划下单股数
    account: Optional[Account] = None
    positions: List[Position] = field(default_factory=list)
    hist_df: Optional[pd.DataFrame] = None   # 历史 K 线（用于回撤等指标）
    initial_cash: float = 0.0            # 账户初始资金（用于回撤基准）
    today_open_value: float = 0.0        # 今日开盘总资产（用于当日亏损）
    is_live: bool = False                # 是否实盘（部分规则仅实盘启用）


class RiskRule(ABC):
    """风控规则抽象基类

    子类必须实现 check_buy / check_sell / check_hold。
    若某种场景不关心，直接返回 ALLOW 即可。
    """

    name: str = "base"

    @abstractmethod
    def check_buy(self, ctx: RiskContext) -> RiskDecision:
        """买入前检查"""
        pass

    @abstractmethod
    def check_sell(self, ctx: RiskContext) -> RiskDecision:
        """卖出前检查"""
        pass

    @abstractmethod
    def check_hold(self, ctx: RiskContext) -> RiskDecision:
        """持仓巡检（用于止损、回撤熔断等）"""
        pass


class RiskManager:
    """风险管理器：聚合多条规则"""

    def __init__(self, rules: Optional[List[RiskRule]] = None):
        self.rules: List[RiskRule] = list(rules or [])

    def add(self, rule: RiskRule):
        self.rules.append(rule)

    def evaluate_buy(self, ctx: RiskContext) -> RiskDecision:
        """买入评估：任一规则 REJECT 即 REJECT；ALLOW 时取最严格的 adjusted_qty"""
        final_qty = ctx.quantity
        triggered: Optional[RiskDecision] = None

        for rule in self.rules:
            d = rule.check_buy(ctx)
            if d.action == RiskAction.REJECT:
                return d
            if d.adjusted_qty > 0:
                final_qty = min(final_qty, d.adjusted_qty) if final_qty > 0 else d.adjusted_qty
                triggered = d

        if triggered and final_qty < ctx.quantity:
            return RiskDecision(
                action=RiskAction.ALLOW,
                rule=triggered.rule,
                reason=triggered.reason,
                adjusted_qty=final_qty,
            )
        return ALLOW

    def evaluate_sell(self, ctx: RiskContext) -> RiskDecision:
        for rule in self.rules:
            d = rule.check_sell(ctx)
            if d.action == RiskAction.REJECT:
                return d
        return ALLOW

    def scan_positions(self, ctx: RiskContext) -> List[RiskDecision]:
        """持仓巡检：返回所有 FORCE_CLOSE 决策（按规则顺序）"""
        results: List[RiskDecision] = []
        for rule in self.rules:
            d = rule.check_hold(ctx)
            if d.action == RiskAction.FORCE_CLOSE:
                results.append(d)
        return results

    @classmethod
    def from_config(cls, cfg: dict, is_live: bool = False) -> "RiskManager":
        """从配置字典构造默认规则集"""
        from .rules import (
            MaxPositionRule,
            TotalPositionRule,
            StopLossRule,
            MaxDrawdownRule,
            DailyLossRule,
            TradingTimeRule,
        )

        rules: List[RiskRule] = []
        if "max_position_pct" in cfg:
            rules.append(MaxPositionRule(cfg["max_position_pct"]))
        if "max_total_position_pct" in cfg:
            rules.append(TotalPositionRule(cfg["max_total_position_pct"]))
        if "stop_loss_pct" in cfg:
            rules.append(StopLossRule(cfg["stop_loss_pct"]))
        if "max_drawdown_pct" in cfg:
            rules.append(MaxDrawdownRule(cfg["max_drawdown_pct"]))
        if "daily_loss_pct" in cfg:
            rules.append(DailyLossRule(cfg["daily_loss_pct"]))
        if is_live:
            rules.append(TradingTimeRule())
        return cls(rules)
