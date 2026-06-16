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

# Web管理后台配置
WEB = {
    "admin_username": "admin",
    "admin_password_hash": "pbkdf2:sha256:1000000$q6bAhiiCHjxUugJc$60375ee30781c2748483ef7815cbe869ecccc75f6b2cfb7a77f15ed878804e18",  # 默认密码: admin
    "secret_key": "a-stock-quant-change-me-in-production",
    "host": "127.0.0.1",
    "port": 5000,
    "debug": False,
    "local_client_mode": True,
}

# 风控参数（回测与实盘共用）
RISK = {
    "max_position_pct": 0.3,         # 单股最大仓位 30%
    "max_total_position_pct": 0.8,   # 总持仓上限 80%
    "stop_loss_pct": 0.07,           # 个股止损线 7%
    "max_drawdown_pct": 0.15,        # 账户回撤熔断 15%
    "daily_loss_pct": 0.05,          # 当日亏损熔断 5%
    "enable_in_backtest": True,      # 回测是否启用风控
}

# 通知配置
NOTIFY = {
    "serverchan_sendkey": "",        # Server酱 SENDKEY，留空则不推送微信
    "console_enabled": True,         # 终端 + 文件输出
    "log_file": "notify.log",        # 通知日志路径
    "min_level": "trade",            # 最低推送级别 info/trade/warning/error
}

# 组合回测参数
PORTFOLIO = {
    "universe": "000300",            # 默认股票池：000300(沪深300) / 000905(中证500) / 000852(中证1000) / 000016(上证50)
    "top_n": 10,                     # 选股数量
    "rebalance_interval": 20,        # 调仓周期（交易日）
    "lookback_days": 60,             # 因子计算回看天数
    "cash_buffer": 0.02,             # 保留现金比例（防费用滑点）
}
