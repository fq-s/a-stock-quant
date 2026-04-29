# A股量化交易系统

轻量级 A股回测框架，纯 Python，基于 akshare 免费数据源。

## 快速开始

```bash
cd quant
pip install -r requirements.txt

# 默认回测：平安银行 2024全年 双均线策略
python main.py

# 指定股票和策略
python main.py --stock 600519 --strategy rsi

# 自定义均线参数
python main.py --short 10 --long 30

# 自定义日期范围
python main.py --stock 000858 --start 20230101 --end 20241231
```

## 项目结构

```
quant/
├── config.py              # 全局配置（佣金、印花税等）
├── main.py                # 回测入口
├── data/
│   ├── fetcher.py         # A股数据获取（akshare）
│   └── cache/             # 数据缓存（parquet格式）
├── strategy/
│   ├── base.py            # 策略基类
│   ├── ma_cross.py        # 双均线交叉策略
│   └── rsi_reversal.py    # RSI均值回归策略
├── backtest/
│   └── engine.py          # 回测引擎
└── utils/
    └── metrics.py         # 绩效指标计算
```

## 自定义策略

继承 `BaseStrategy` 实现 `on_bar()` 方法：

```python
from strategy.base import BaseStrategy, Signal

class MyStrategy(BaseStrategy):
    def on_bar(self, idx, bar, position, cash):
        df = self.df  # 完整K线数据
        # ... 你的逻辑 ...
        return Signal.BUY  # 或 Signal.SELL / Signal.HOLD
```

## 内置指标

- 总收益率 / 年化收益率
- 最大回撤
- 夏普比率
- 交易胜率
- 超额收益（Alpha）

## 回测参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| 佣金 | 万三 | 买入卖出均收 |
| 印花税 | 千一 | 仅卖出收取 |
| 滑点 | 0.1% | 模拟成交偏差 |
| 仓位 | 95% | 单次买入使用现金比例 |

## 注意事项

- 本系统仅用于**回测研究**，不构成投资建议
- 数据来自 akshare，仅供学习使用
- 实盘交易需要对接券商接口（QMT / xtquant 等）

## 实盘交易

### 模拟盘（推荐先用）
```bash
# 不花真钱，用真实行情验证策略和风控
python3 live_main.py --symbols 000001 600519 --paper
```

### QMT实盘
需要先开通支持QMT的券商账户（国金/华鑫等），安装QMT客户端。
```bash
pip install xtquant
python3 live_main.py --symbols 000001 --qmt --account 12345678 --qmt-path /path/to/qmt
```

### 风控功能
- 单股最大仓位限制（默认30%）
- 自动止损（默认7%回撤）
- A股交易时间自动检测
- 交易日志持久化

## 后续计划

- [ ] 多因子选股策略
- [ ] 组合回测（多只股票）
- [ ] 参数优化（网格搜索）
- [ ] 消息通知（微信/Telegram推送交易信号）
- [ ] Web面板监控
