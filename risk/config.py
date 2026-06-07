"""风控配置"""

from dataclasses import dataclass


@dataclass
class RiskConfig:
    """风控参数

    与 config.RISK 字典等价的强类型表示，便于代码内部传递。
    """
    max_position_pct: float = 0.3
    max_total_position_pct: float = 0.8
    stop_loss_pct: float = 0.07
    max_drawdown_pct: float = 0.15
    daily_loss_pct: float = 0.05
    enable_in_backtest: bool = True

    def to_dict(self) -> dict:
        return {
            "max_position_pct": self.max_position_pct,
            "max_total_position_pct": self.max_total_position_pct,
            "stop_loss_pct": self.stop_loss_pct,
            "max_drawdown_pct": self.max_drawdown_pct,
            "daily_loss_pct": self.daily_loss_pct,
        }
