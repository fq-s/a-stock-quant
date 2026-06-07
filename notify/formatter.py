"""把领域对象格式化为通知用 Markdown"""

from typing import Optional


def format_trade(action: str, symbol: str, price: float, quantity: int,
                 reason: str = "", account_cash: Optional[float] = None) -> tuple[str, str]:
    """格式化成交通知，返回 (title, body)"""
    title = f"{action} {symbol} {quantity}股 @ {price:.2f}"
    lines = [
        f"- 操作: **{action}**",
        f"- 标的: `{symbol}`",
        f"- 价格: {price:.2f}",
        f"- 数量: {quantity}",
    ]
    if account_cash is not None:
        lines.append(f"- 余额: ¥{account_cash:,.2f}")
    if reason:
        lines.append(f"- 备注: {reason}")
    return title, "\n".join(lines)


def format_risk(symbol: str, rule: str, reason: str, action: str = "") -> tuple[str, str]:
    """格式化风控事件通知"""
    title = f"风控 {action or rule}: {symbol}"
    body = "\n".join([
        f"- 标的: `{symbol}`",
        f"- 规则: **{rule}**",
        f"- 动作: {action or '-'}",
        f"- 原因: {reason}",
    ])
    return title, body


def format_error(symbol: str, message: str) -> tuple[str, str]:
    title = f"实盘异常 {symbol}"
    body = f"标的 `{symbol}` 处理异常:\n\n```\n{message}\n```"
    return title, body


def format_startup(strategy_name: str, symbols: list, **extra) -> tuple[str, str]:
    title = f"实盘启动 — {strategy_name}"
    lines = [
        f"- 策略: **{strategy_name}**",
        f"- 监控: {', '.join(symbols)}",
    ]
    for k, v in extra.items():
        lines.append(f"- {k}: {v}")
    return title, "\n".join(lines)
