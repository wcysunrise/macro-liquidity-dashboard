"""yfinance 市场数据拉取。"""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import streamlit as st
import yfinance as yf

from config import RISK_ASSETS, RISK_INDICATORS


def _display_ticker(ticker: str) -> str:
    return "DXY" if ticker == "DX-Y.NYB" else ticker


def _extract_close(frame: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """从 yfinance 返回结果中提取单个 ticker 的收盘价。"""

    if frame.empty:
        return pd.DataFrame()

    price_column = "Adj Close" if "Adj Close" in frame.columns else "Close"
    if price_column not in frame.columns:
        return pd.DataFrame()

    close = pd.to_numeric(frame[price_column], errors="coerce").dropna()
    if close.empty:
        return pd.DataFrame()

    close.index = pd.to_datetime(close.index).tz_localize(None)
    return close.to_frame(_display_ticker(ticker)).sort_index()


def _fetch_one_ticker(ticker: str, start: str) -> pd.DataFrame:
    """逐个 ticker 拉取，避免批量请求被单个异常 ticker 拖垮。"""

    history = yf.Ticker(ticker).history(start=start, auto_adjust=False)
    close = _extract_close(history, ticker)
    if not close.empty:
        return close

    downloaded = yf.download(
        ticker,
        start=start,
        auto_adjust=False,
        progress=False,
        threads=False,
    )
    return _extract_close(downloaded, ticker)


@st.cache_data(ttl=60 * 60, show_spinner="正在从 yfinance 拉取风险资产数据...")
def load_market_data(years: int = 3) -> tuple[pd.DataFrame, dict[str, str]]:
    """拉取 AI/半导体、VIX、DXY 与 NASDAQ proxy 价格数据。"""

    tickers = list(dict.fromkeys([*RISK_ASSETS.keys(), *RISK_INDICATORS.keys()]))
    start = (date.today() - timedelta(days=365 * years + 45)).isoformat()
    frames: list[pd.DataFrame] = []
    errors: dict[str, str] = {}

    for ticker in tickers:
        try:
            frame = _fetch_one_ticker(ticker, start)
            if frame.empty:
                errors[_display_ticker(ticker)] = "yfinance 未返回该 ticker 的价格序列"
            else:
                frames.append(frame)
        except Exception as exc:
            errors[_display_ticker(ticker)] = f"市场数据拉取失败：{exc}"

    if not frames:
        return pd.DataFrame(), {"yfinance": "yfinance 未返回任何 ticker 的价格数据"}

    prices = pd.concat(frames, axis=1, join="outer").sort_index()
    prices = prices.dropna(how="all").ffill()
    return prices, errors
