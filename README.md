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
├── config.py              # 全局配置（佣金、印花税、风控、通知等）
├── main.py                # 回测入口
├── live_main.py           # 实盘入口
├── data/
│   ├── fetcher.py         # A股数据获取（akshare）
│   └── cache/             # 数据缓存（parquet格式）
├── strategy/
│   ├── base.py            # 策略基类
│   ├── ma_cross.py        # 双均线交叉策略
│   └── rsi_reversal.py    # RSI均值回归策略
├── backtest/
│   └── engine.py          # 回测引擎（支持风控）
├── live/
│   ├── trader.py          # 实时交易引擎
│   ├── broker.py          # 券商抽象
│   ├── paper_broker.py    # 模拟盘
│   └── qmt_broker.py      # QMT 实盘
├── risk/                  # 风控模块（回测+实盘共用）
│   ├── base.py            # RiskManager / RiskRule
│   ├── rules.py           # 6 条内置规则
│   └── config.py          # 风控参数
├── notify/                # 通知模块
│   ├── base.py            # NotifyHub
│   ├── console.py         # 终端+文件
│   ├── serverchan.py      # Server酱（微信）
│   └── formatter.py       # 消息格式化
├── utils/
│   └── metrics.py         # 绩效指标计算
├── factor/                # 因子库（MA/EMA/RSI/MACD/Momentum/Volatility/ATR/Return）
├── selector/              # 选股器（指数成份股 + 多因子打分）
├── portfolio/             # 组合回测（多股票 + 定期调仓）
├── portfolio_main.py      # 组合回测入口
└── tests/                 # 单元测试 (pytest)
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
回测和实盘共用同一套 `RiskManager`，由 6 条规则组成：

| 规则 | 默认阈值 | 触发动作 |
|------|----------|----------|
| `MaxPositionRule` | 单股 30% | 拒绝/调整下单量 |
| `TotalPositionRule` | 总仓位 80% | 拒绝 |
| `StopLossRule` | 个股亏损 7% | 强制平仓 |
| `MaxDrawdownRule` | 账户回撤 15% | 当日禁止买入 |
| `DailyLossRule` | 当日亏损 5% | 当日禁止买入 |
| `TradingTimeRule` | 非交易时间 | 拒绝（仅实盘） |

调整参数：编辑 `config.py` 中的 `RISK` 段。回测可加 `--no-risk` 关闭风控对比。

### 通知推送（Server酱）
1. 注册 https://sct.ftqq.com/ 获取 SENDKEY
2. 编辑 `config.py`：
   ```python
   NOTIFY = {
       "serverchan_sendkey": "你的SENDKEY",
       "min_level": "trade",  # 只推送成交以上级别
   }
   ```
3. 实盘启动、成交、风控告警、异常都会推送到微信。

### 单元测试
```bash
pip install -r requirements-dev.txt
pytest tests/ -v          # 跑所有测试（95 个）
pytest tests/ --cov=risk --cov=notify --cov=utils --cov=backtest --cov=factor --cov=selector --cov=portfolio
```

## 因子库 & 选股 & 组合回测

第二阶段补齐"因子库 → 选股 → 组合回测"流水线，与 `risk` / `notify` 模块联动。

### 因子库 `factor/`

```python
from factor import MA, RSI, Momentum, Volatility, ATR, FactorRegistry

# 直接构造
ma = MA(window=20).compute(df)        # 返回 pd.Series

# 配置驱动
rsi = FactorRegistry.get("RSI", period=14).compute(df)
print(FactorRegistry.list())          # 列出所有已注册因子
```

内置因子：MA / EMA / RSI / MACD / Momentum / Volatility / ATR / Return。

### 选股器 `selector/`

```python
from selector import FactorSelector, get_index_constituents
from factor import Momentum, Volatility, Return

symbols = get_index_constituents("000300")    # 沪深300
selector = FactorSelector(factors=[
    (Momentum(20), 0.5),
    (Volatility(20), -0.3),     # 负权重 = 低波动加分
    (Return(5), -0.2),          # 短期反转
], lookback_days=60)
result = selector.select(date, universe_data, top_n=10)
```

支持指数：000300（沪深300）、000905（中证500）、000852（中证1000）、000016（上证50），自带 7 天本地缓存。也可用 `load_custom_universe(path)` 读 CSV。

### 组合回测 `portfolio/`

```bash
# 默认：沪深300 选 10 只，20 日调仓
python3 portfolio_main.py

# 中证500，10 日调仓
python3 portfolio_main.py --universe 000905 --top 15 --rebalance 10

# 快速测试（只取股票池前 20 只）
python3 portfolio_main.py --limit 20

# 自定义 CSV 股票池
python3 portfolio_main.py --custom my_picks.csv
```

特性：
- 等权重 1/N 资金分配（可配 `cash_buffer` 留现金）
- 定期调仓（默认 20 个交易日）+ 自动先卖后买
- 与单股回测共用 `RiskManager`，REJECT 标的自动跳过并记录
- 等权 Buy-and-Hold 作为基准对比
- 输出净值曲线图（`portfolio_result.png`）

## 后续计划

- [x] ~~消息通知（微信推送交易信号）~~
- [x] ~~Web面板监控~~
- [x] ~~风控模块（回测+实盘共用）~~
- [x] ~~核心模块单元测试~~
- [x] ~~因子库（多因子选股）~~
- [x] ~~选股器（全市场扫描）~~
- [x] ~~组合管理（多股票回测/实盘）~~
- [ ] 参数优化（网格搜索 + 贝叶斯）
- [ ] 实盘组合调仓（PortfolioStrategy → 实盘 trader）
