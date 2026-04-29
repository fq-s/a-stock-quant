"""全局配置"""

# 数据源设置
DATA_SOURCE = "akshare"  # akshare (免费) / tushare (需token)

# Tushare token (如果用tushare)
TUSHARE_TOKEN = ""

# 默认回测参数
BACKTEST = {
    "initial_cash": 1_000_000,  # 初始资金 100万
    "commission_rate": 0.0003,  # 佣金万三
    "stamp_tax_rate": 0.001,   # 印花税千一（卖出）
    "slippage": 0.001,         # 滑点 0.1%
}

# 数据缓存目录
CACHE_DIR = "data/cache"
