"""Best-effort Yahoo option-chain proxies for options microstructure."""

from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd
import streamlit as st
import yfinance as yf


def _safe_ratio(numerator: float, denominator: float) -> float | None:
    if denominator == 0 or pd.isna(denominator):
        return None
    return float(numerator / denominator)


def _prepare_chain_table(frame: pd.DataFrame) -> pd.DataFrame:
    columns = ["contractSymbol", "strike", "lastPrice", "bid", "ask", "volume", "openInterest", "impliedVolatility"]
    available = [column for column in columns if column in frame.columns]
    result = frame[available].copy()
    for column in ["strike", "lastPrice", "bid", "ask", "volume", "openInterest", "impliedVolatility"]:
        if column in result.columns:
            result[column] = pd.to_numeric(result[column], errors="coerce").fillna(0)
    return result


def max_pain_proxy(calls: pd.DataFrame, puts: pd.DataFrame) -> float | None:
    """Return the strike with minimum aggregate option-holder intrinsic value."""

    if calls.empty and puts.empty:
        return None
    if not calls.empty and not {"strike", "openInterest"}.issubset(calls.columns):
        return None
    if not puts.empty and not {"strike", "openInterest"}.issubset(puts.columns):
        return None

    call_oi = calls.groupby("strike")["openInterest"].sum() if not calls.empty else pd.Series(dtype=float)
    put_oi = puts.groupby("strike")["openInterest"].sum() if not puts.empty else pd.Series(dtype=float)
    strikes = sorted(set(call_oi.index).union(set(put_oi.index)))
    if not strikes:
        return None

    pain_by_strike: dict[float, float] = {}
    for settlement in strikes:
        call_pain = sum(max(settlement - strike, 0) * oi for strike, oi in call_oi.items())
        put_pain = sum(max(strike - settlement, 0) * oi for strike, oi in put_oi.items())
        pain_by_strike[float(settlement)] = float(call_pain + put_pain)

    return min(pain_by_strike, key=pain_by_strike.get)


def summarize_option_chain(ticker: str, expiry: str, calls: pd.DataFrame, puts: pd.DataFrame) -> dict[str, Any]:
    calls = _prepare_chain_table(calls)
    puts = _prepare_chain_table(puts)

    call_volume = float(calls["volume"].sum()) if "volume" in calls else 0
    put_volume = float(puts["volume"].sum()) if "volume" in puts else 0
    call_oi = float(calls["openInterest"].sum()) if "openInterest" in calls else 0
    put_oi = float(puts["openInterest"].sum()) if "openInterest" in puts else 0

    top_calls = calls.sort_values("openInterest", ascending=False).head(8) if "openInterest" in calls else pd.DataFrame()
    top_puts = puts.sort_values("openInterest", ascending=False).head(8) if "openInterest" in puts else pd.DataFrame()

    call_wall = None if top_calls.empty else float(top_calls.iloc[0]["strike"])
    put_wall = None if top_puts.empty else float(top_puts.iloc[0]["strike"])
    expiry_date = pd.to_datetime(expiry).date()

    return {
        "ticker": ticker,
        "expiry": expiry,
        "is_0dte": expiry_date == date.today(),
        "put_call_volume_ratio": _safe_ratio(put_volume, call_volume),
        "put_call_oi_ratio": _safe_ratio(put_oi, call_oi),
        "call_volume": call_volume,
        "put_volume": put_volume,
        "call_oi": call_oi,
        "put_oi": put_oi,
        "call_wall": call_wall,
        "put_wall": put_wall,
        "max_pain": max_pain_proxy(calls, puts),
        "top_calls": top_calls,
        "top_puts": top_puts,
        "zero_dte_volume_proxy": put_volume + call_volume if expiry_date == date.today() else None,
    }


def _choose_expiry(expirations: tuple[str, ...]) -> str | None:
    if not expirations:
        return None

    today = date.today().isoformat()
    if today in expirations:
        return today
    return sorted(expirations)[0]


@st.cache_data(ttl=60 * 60 * 6, show_spinner="正在低频拉取 Yahoo option-chain proxy...")
def load_options_microstructure(tickers: tuple[str, ...] = ("SPY", "QQQ")) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    """Fetch one nearest useful expiry per ticker. Errors are isolated per ticker."""

    summaries: dict[str, dict[str, Any]] = {}
    errors: dict[str, str] = {}

    for ticker in tickers:
        try:
            yf_ticker = yf.Ticker(ticker)
            expiry = _choose_expiry(tuple(yf_ticker.options))
            if expiry is None:
                errors[ticker] = "Yahoo 未返回 option expirations"
                continue
            chain = yf_ticker.option_chain(expiry)
            summaries[ticker] = summarize_option_chain(ticker, expiry, chain.calls, chain.puts)
        except Exception as exc:
            errors[ticker] = f"Options data unavailable / rate-limited: {exc}"

    return summaries, errors
