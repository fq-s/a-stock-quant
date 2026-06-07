"""股票池获取

支持指数成份股（带本地 cache）和自定义 CSV 池。
"""

import os
import time
from datetime import datetime
from typing import List

import pandas as pd

try:
    import akshare as ak
except ImportError:
    ak = None


CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache")
os.makedirs(CACHE_DIR, exist_ok=True)

# 缓存有效期（天）：指数成份股不会天天换
CACHE_TTL_DAYS = 7

# 支持的指数
SUPPORTED_INDEXES = {
    "000300": "沪深300",
    "000905": "中证500",
    "000852": "中证1000",
    "000016": "上证50",
}


def _cache_path(index: str) -> str:
    return os.path.join(CACHE_DIR, f"index_{index}_constituents.parquet")


def _is_cache_fresh(path: str) -> bool:
    if not os.path.exists(path):
        return False
    mtime = datetime.fromtimestamp(os.path.getmtime(path))
    return (datetime.now() - mtime).days < CACHE_TTL_DAYS


def get_index_constituents(index: str = "000300", use_cache: bool = True) -> List[str]:
    """获取指数成份股代码列表

    Parameters
    ----------
    index : str
        指数代码，支持 000300/000905/000852/000016
    use_cache : bool
        是否使用本地缓存（TTL=7 天）

    Returns
    -------
    List[str]  6 位股票代码列表，如 ["000001", "600519", ...]
    """
    if index not in SUPPORTED_INDEXES:
        raise ValueError(f"不支持的指数 {index}，支持: {list(SUPPORTED_INDEXES)}")

    cache_file = _cache_path(index)
    if use_cache and _is_cache_fresh(cache_file):
        df = pd.read_parquet(cache_file)
        print(f"  ✓ 读取成份股缓存: {index} ({len(df)}只)")
        return df["symbol"].tolist()

    if ak is None:
        raise RuntimeError("akshare 未安装，无法获取成份股")

    # 优先用中证官方
    df = None
    for attempt in range(1, 4):
        try:
            print(f"  ↓ 下载 {SUPPORTED_INDEXES[index]} 成份股 ...")
            df = ak.index_stock_cons_csindex(symbol=index)
            break
        except Exception as e:
            print(f"  ⚠️  中证源第{attempt}次失败: {e}")
            time.sleep(2)

    # 备选：新浪源（只支持部分指数）
    if df is None or df.empty:
        try:
            df = ak.index_stock_cons_sina(symbol=index)
        except Exception as e:
            raise RuntimeError(f"获取指数 {index} 成份股失败: {e}") from e

    # 列名兼容
    code_col = None
    for col in ["成分券代码", "证券代码", "code", "品种代码"]:
        if col in df.columns:
            code_col = col
            break
    if code_col is None:
        raise RuntimeError(f"未识别成份股代码列，columns={list(df.columns)}")

    symbols = (
        df[code_col].astype(str).str.zfill(6).tolist()
    )

    if use_cache:
        pd.DataFrame({"symbol": symbols}).to_parquet(cache_file, index=False)
        print(f"  ✓ 已缓存成份股: {index} ({len(symbols)}只)")

    return symbols


def load_custom_universe(path: str) -> List[str]:
    """从 CSV 文件加载自定义股票池

    CSV 第一列即为股票代码（带不带表头都行）。
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"股票池文件不存在: {path}")

    df = pd.read_csv(path, dtype=str)
    col = df.columns[0]
    # 如果第一列是 "symbol"/"code" 之类的表头，正常用；否则当无表头重读
    if col.strip().lower() in {"symbol", "code", "ticker", "股票代码"}:
        symbols = df[col].astype(str).str.zfill(6).tolist()
    else:
        df = pd.read_csv(path, header=None, dtype=str)
        symbols = df[0].astype(str).str.zfill(6).tolist()

    return [s for s in symbols if s and s.isdigit()]
