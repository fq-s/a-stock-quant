"""内置风控规则"""

from datetime import datetime

from .base import (
    RiskRule,
    RiskContext,
    RiskDecision,
    RiskAction,
    ALLOW,
)


MORNING_OPEN = (9, 30)
MORNING_CLOSE = (11, 30)
AFTERNOON_OPEN = (13, 0)
AFTERNOON_CLOSE = (15, 0)


class MaxPositionRule(RiskRule):
    """单股仓位上限：超出时按上限调整下单量，无法调整则 REJECT"""

    name = "MaxPositionRule"

    def __init__(self, max_pct: float):
        self.max_pct = max_pct

    def check_buy(self, ctx: RiskContext) -> RiskDecision:
        if not ctx.account or ctx.account.total_assets <= 0:
            return ALLOW
        existing_value = 0.0
        for p in ctx.positions:
            if p.symbol == ctx.symbol:
                existing_value = p.quantity * ctx.price
                break
        max_value = ctx.account.total_assets * self.max_pct
        room = max_value - existing_value
        if room <= 0:
            return RiskDecision(
                action=RiskAction.REJECT,
                rule=self.name,
                reason=f"{ctx.symbol} 已达单股仓位上限 {self.max_pct:.0%}",
            )
        max_qty = int(room / ctx.price / 100) * 100
        if max_qty < 100:
            return RiskDecision(
                action=RiskAction.REJECT,
                rule=self.name,
                reason=f"{ctx.symbol} 剩余可买额度不足一手",
            )
        if ctx.quantity > 0 and ctx.quantity > max_qty:
            return RiskDecision(
                action=RiskAction.ALLOW,
                rule=self.name,
                reason=f"按单股上限 {self.max_pct:.0%} 调整下单量 {ctx.quantity}→{max_qty}",
                adjusted_qty=max_qty,
            )
        if ctx.quantity == 0:
            return RiskDecision(
                action=RiskAction.ALLOW,
                rule=self.name,
                reason="按单股上限给出建议下单量",
                adjusted_qty=max_qty,
            )
        return ALLOW

    def check_sell(self, ctx: RiskContext) -> RiskDecision:
        return ALLOW

    def check_hold(self, ctx: RiskContext) -> RiskDecision:
        return ALLOW


class TotalPositionRule(RiskRule):
    """总持仓上限"""

    name = "TotalPositionRule"

    def __init__(self, max_pct: float):
        self.max_pct = max_pct

    def check_buy(self, ctx: RiskContext) -> RiskDecision:
        if not ctx.account or ctx.account.total_assets <= 0:
            return ALLOW
        market_value = sum(p.quantity * ctx.price if p.symbol == ctx.symbol
                           else p.quantity * p.current_price for p in ctx.positions)
        planned = (ctx.quantity or 0) * ctx.price
        new_total = market_value + planned
        if new_total > ctx.account.total_assets * self.max_pct:
            return RiskDecision(
                action=RiskAction.REJECT,
                rule=self.name,
                reason=f"总持仓将超过上限 {self.max_pct:.0%}",
            )
        return ALLOW

    def check_sell(self, ctx: RiskContext) -> RiskDecision:
        return ALLOW

    def check_hold(self, ctx: RiskContext) -> RiskDecision:
        return ALLOW


class StopLossRule(RiskRule):
    """止损规则：持仓亏损达阈值则 FORCE_CLOSE"""

    name = "StopLossRule"

    def __init__(self, stop_pct: float):
        self.stop_pct = stop_pct

    def check_buy(self, ctx: RiskContext) -> RiskDecision:
        return ALLOW

    def check_sell(self, ctx: RiskContext) -> RiskDecision:
        return ALLOW

    def check_hold(self, ctx: RiskContext) -> RiskDecision:
        for p in ctx.positions:
            if p.symbol != ctx.symbol or p.cost_price <= 0 or p.quantity <= 0:
                continue
            loss_pct = (p.cost_price - ctx.price) / p.cost_price
            if loss_pct >= self.stop_pct:
                return RiskDecision(
                    action=RiskAction.FORCE_CLOSE,
                    rule=self.name,
                    reason=f"{ctx.symbol} 触发止损，亏损 {loss_pct:.2%}，成本 {p.cost_price:.2f} → 现价 {ctx.price:.2f}",
                )
        return ALLOW


class MaxDrawdownRule(RiskRule):
    """账户最大回撤熔断：回撤达阈值则当日 REJECT 所有买入"""

    name = "MaxDrawdownRule"

    def __init__(self, max_dd_pct: float):
        self.max_dd_pct = max_dd_pct

    def _current_dd(self, ctx: RiskContext) -> float:
        if not ctx.account or ctx.initial_cash <= 0:
            return 0.0
        peak = max(ctx.initial_cash, ctx.account.total_assets)
        return (peak - ctx.account.total_assets) / peak if peak > 0 else 0.0

    def check_buy(self, ctx: RiskContext) -> RiskDecision:
        dd = self._current_dd(ctx)
        if dd >= self.max_dd_pct:
            return RiskDecision(
                action=RiskAction.REJECT,
                rule=self.name,
                reason=f"账户回撤 {dd:.2%} 达熔断线 {self.max_dd_pct:.2%}，暂停买入",
            )
        return ALLOW

    def check_sell(self, ctx: RiskContext) -> RiskDecision:
        return ALLOW

    def check_hold(self, ctx: RiskContext) -> RiskDecision:
        return ALLOW


class DailyLossRule(RiskRule):
    """单日亏损熔断"""

    name = "DailyLossRule"

    def __init__(self, max_loss_pct: float):
        self.max_loss_pct = max_loss_pct

    def check_buy(self, ctx: RiskContext) -> RiskDecision:
        if not ctx.account or ctx.today_open_value <= 0:
            return ALLOW
        loss = (ctx.today_open_value - ctx.account.total_assets) / ctx.today_open_value
        if loss >= self.max_loss_pct:
            return RiskDecision(
                action=RiskAction.REJECT,
                rule=self.name,
                reason=f"当日亏损 {loss:.2%} 达熔断线 {self.max_loss_pct:.2%}，暂停买入",
            )
        return ALLOW

    def check_sell(self, ctx: RiskContext) -> RiskDecision:
        return ALLOW

    def check_hold(self, ctx: RiskContext) -> RiskDecision:
        return ALLOW


class TradingTimeRule(RiskRule):
    """A 股交易时间检查（仅实盘）"""

    name = "TradingTimeRule"

    def _is_trading_time(self) -> bool:
        now = datetime.now()
        if now.weekday() >= 5:
            return False
        t = (now.hour, now.minute)
        return (MORNING_OPEN <= t <= MORNING_CLOSE) or (AFTERNOON_OPEN <= t <= AFTERNOON_CLOSE)

    def check_buy(self, ctx: RiskContext) -> RiskDecision:
        if not ctx.is_live:
            return ALLOW
        if not self._is_trading_time():
            return RiskDecision(
                action=RiskAction.REJECT,
                rule=self.name,
                reason="非 A 股交易时间，拒绝下单",
            )
        return ALLOW

    def check_sell(self, ctx: RiskContext) -> RiskDecision:
        return self.check_buy(ctx)

    def check_hold(self, ctx: RiskContext) -> RiskDecision:
        return ALLOW
