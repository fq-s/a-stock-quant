"""A股数据获取模块 — 基于 akshare（免费，无需token）

数据源优先级:
1. 新浪 (stock_zh_a_daily) — 稳定
2. 东方财富 (stock_zh_a_hist) — 备选
"""

import os
import time
from typing import Dict, List

import pandas as pd
import akshare as ak
from datetime import datetime, timedelta


CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache")
os.makedirs(CACHE_DIR, exist_ok=True)

MAX_RETRIES = 3
RETRY_DELAY = 5


def _cache_path(symbol: str, start: str, end: str, source: str = "sina") -> str:
    return os.path.join(CACHE_DIR, f"{source}_{symbol}_{start}_{end}.parquet")


def _normalize_sina_code(symbol: str) -> str:
    """纯数字代码转新浪格式: 000001 -> sz000001, 600519 -> sh600519"""
    if symbol.startswith(("sh", "sz", "SH", "SZ")):
        return symbol.lower()
    # 6开头 = 上证, 其他 = 深证
    prefix = "sh" if symbol.startswith("6") else "sz"
    return f"{prefix}{symbol}"


def fetch_daily(symbol: str, start: str, end: str, use_cache: bool = True) -> pd.DataFrame:
    """
    获取日线数据

    Parameters
    ----------
    symbol : str
        股票代码，如 "000001"（平安银行）或 "sz000001"
    start : str
        起始日期 "YYYYMMDD"
    end : str
        结束日期 "YYYYMMDD"
    use_cache : bool
        是否使用本地缓存

    Returns
    -------
    pd.DataFrame  columns: date, open, high, low, close, volume
    """
    # 尝试新浪源
    cache_file = _cache_path(symbol, start, end, "sina")
    if use_cache and os.path.exists(cache_file):
        print(f"  ✓ 读取缓存: {symbol}")
        return pd.read_parquet(cache_file)

    sina_code = _normalize_sina_code(symbol)
    df = None

    # 新浪源
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            print(f"  ↓ [新浪] 下载 {symbol} 行情 ({start} ~ {end}) ...")
            df = ak.stock_zh_a_daily(
                symbol=sina_code,
                start_date=start,
                end_date=end,
                adjust="qfq",
            )
            break
        except Exception as e:
            print(f"  ⚠️  新浪源第{attempt}次失败: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)

    # 备选：东方财富源
    if df is None or df.empty:
        clean_code = symbol.replace("sh", "").replace("sz", "").replace("SH", "").replace("SZ", "")
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                print(f"  ↓ [东财] 下载 {clean_code} 行情 ({start} ~ {end}) ...")
                df = ak.stock_zh_a_hist(
                    symbol=clean_code,
                    period="daily",
                    start_date=start,
                    end_date=end,
                    adjust="qfq",
                )
                break
            except Exception as e:
                print(f"  ⚠️  东财源第{attempt}次失败: {e}")
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY)

    if df is None or df.empty:
        raise RuntimeError(f"下载 {symbol} 行情失败，所有数据源均不可用")

    # 统一列名（新浪源）
    col_map = {}
    for old, new in [("date", "date"), ("open", "open"), ("high", "high"),
                      ("low", "low"), ("close", "close"), ("volume", "volume")]:
        if old in df.columns:
            col_map[old] = new

    # 东财源列名映射
    em_map = {"日期": "date", "开盘": "open", "收盘": "close",
              "最高": "high", "最低": "low", "成交量": "volume"}
    for old, new in em_map.items():
        if old in df.columns:
            col_map[old] = new

    df = df.rename(columns=col_map)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    df = df[["date", "open", "high", "low", "close", "volume"]]

    if use_cache:
        df.to_parquet(cache_file, index=False)
        print(f"  ✓ 已缓存: {symbol} ({len(df)}条)")

    return df


def fetch_index_daily(index_code: str = "000300", start: str = "", end: str = "") -> pd.DataFrame:
    """
    获取指数日线数据（默认沪深300）

    Parameters
    ----------
    index_code : str
        指数代码 "000300"(沪深300) "000016"(上证50) "000905"(中证500)
    """
    if not start:
        start = (datetime.now() - timedelta(days=365)).strftime("%Y%m%d")
    if not end:
        end = datetime.now().strftime("%Y%m%d")

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            print(f"  ↓ 正在下载指数 {index_code} 行情 ...")
            df = ak.index_zh_a_hist(
                symbol=index_code,
                period="daily",
                start_date=start,
                end_date=end,
            )

            df = df.rename(columns={
                "日期": "date", "开盘": "open", "收盘": "close",
                "最高": "high", "最低": "low", "成交量": "volume",
            })

            df["date"] = pd.to_datetime(df["date"])
            df = df.sort_values("date").reset_index(drop=True)
            df = df[["date", "open", "high", "low", "close", "volume"]]
            return df

        except Exception as e:
            print(f"  ⚠️  第{attempt}次失败: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)
            else:
                raise RuntimeError(f"下载指数 {index_code} 失败") from e


def fetch_daily_batch(
    symbols: List[str],
    start: str,
    end: str,
    use_cache: bool = True,
    sleep_between: float = 0.5,
) -> Dict[str, pd.DataFrame]:
    """批量获取多只股票日线（串行，复用 cache）

    Parameters
    ----------
    symbols : List[str]
        股票代码列表
    start, end : str
        起止日期 YYYYMMDD
    use_cache : bool
        命中本地 cache 时跳过 sleep
    sleep_between : float
        实际请求间隔秒数（防 akshare 限流）

    Returns
    -------
    Dict[str, pd.DataFrame]  缺失的股票不出现在返回中
    """
    out: Dict[str, pd.DataFrame] = {}
    total = len(symbols)
    for i, sym in enumerate(symbols, 1):
        cache_file = _cache_path(sym, start, end, "sina")
        cache_hit = use_cache and os.path.exists(cache_file)
        try:
            df = fetch_daily(sym, start, end, use_cache=use_cache)
            out[sym] = df
        except Exception as e:
            print(f"  ✗ [{i}/{total}] {sym} 跳过: {e}")
            continue
        if not cache_hit and sleep_between > 0 and i < total:
            time.sleep(sleep_between)
        if i % 20 == 0:
            print(f"  ◐ 进度: {i}/{total}")
    print(f"  ✓ 批量下载完成: {len(out)}/{total}")
    return out


if __name__ == "__main__":
    df = fetch_daily("000001", "20240101", "20250101")
    print(df.head())
    print(f"共 {len(df)} 条记录")
