"""Volatility, CTA proxy and vol-control proxy calculations."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd


TRADING_DAYS = 252


def annualized_realized_vol(price: pd.Series, window: int) -> pd.Series:
    """Rolling realized volatility in annualized percent points."""

    returns = pd.to_numeric(price, errors="coerce").pct_change()
    return returns.rolling(window).std() * math.sqrt(TRADING_DAYS) * 100


def classify_vix_regime(vix: float | None) -> str:
    if vix is None or pd.isna(vix):
        return "数据不足"
    if vix < 15:
        return "Calm"
    if vix < 25:
        return "Normal"
    if vix < 35:
        return "Stress"
    return "Crisis"


def build_volatility_frame(market_df: pd.DataFrame) -> pd.DataFrame:
    """Build VIX, realized vol and volatility risk premium series."""

    if market_df.empty or "SPY" not in market_df.columns:
        return pd.DataFrame()

    result = pd.DataFrame(index=market_df.index)
    result["SPY"] = market_df["SPY"]
    result["SPY_20D_RV"] = annualized_realized_vol(market_df["SPY"], 20)
    result["SPY_60D_RV"] = annualized_realized_vol(market_df["SPY"], 60)

    if "VIX" in market_df.columns:
        result["VIX"] = market_df["VIX"]
        result["VOL_RISK_PREMIUM"] = result["VIX"] - result["SPY_20D_RV"]
        result["VIX_REGIME"] = result["VIX"].apply(classify_vix_regime)

    if "VVIX" in market_df.columns:
        result["VVIX"] = market_df["VVIX"]

    return result.dropna(how="all")


def _trend_signal(price: pd.Series, window: int) -> pd.Series:
    ma = price.rolling(window).mean()
    signal = pd.Series(np.nan, index=price.index)
    signal[price > ma] = 1
    signal[price < ma] = -1
    return signal


def build_cta_proxy(market_df: pd.DataFrame) -> pd.DataFrame:
    """Estimated CTA equity position proxy using SPY/QQQ trend and SPY vol."""

    required = {"SPY", "QQQ"}
    if market_df.empty or not required.issubset(market_df.columns):
        return pd.DataFrame()

    result = pd.DataFrame(index=market_df.index)
    signal_columns: list[str] = []
    for asset in ["SPY", "QQQ"]:
        for window in [20, 60, 120]:
            column = f"{asset}_{window}D_SIGNAL"
            result[column] = _trend_signal(market_df[asset], window)
            signal_columns.append(column)

    result["TREND_SCORE"] = result[signal_columns].mean(axis=1)
    result["SPY_20D_RV"] = annualized_realized_vol(market_df["SPY"], 20)
    result["SPY_60D_RV"] = annualized_realized_vol(market_df["SPY"], 60)
    result["AVG_RV"] = result[["SPY_20D_RV", "SPY_60D_RV"]].mean(axis=1)
    vol_adjustment = (result["AVG_RV"] / 15).clip(lower=0.5)
    result["CTA_PROXY"] = (result["TREND_SCORE"] / vol_adjustment).clip(-2, 2)
    return result.dropna(how="all")


def cta_shock_scenarios(market_df: pd.DataFrame, shocks: tuple[float, ...] = (-0.01, -0.03, -0.05)) -> pd.DataFrame:
    """Recompute latest CTA proxy after one-day SPY shocks."""

    base = build_cta_proxy(market_df)
    if base.empty or "SPY" not in market_df.columns:
        return pd.DataFrame()

    base_proxy = base["CTA_PROXY"].dropna()
    if base_proxy.empty:
        return pd.DataFrame()

    rows: list[dict[str, float | str]] = []
    for shock in shocks:
        shocked = market_df.copy()
        latest_idx = shocked["SPY"].dropna().index[-1]
        shocked.at[latest_idx, "SPY"] = shocked.at[latest_idx, "SPY"] * (1 + shock)
        shocked_proxy = build_cta_proxy(shocked)["CTA_PROXY"].dropna()
        if shocked_proxy.empty:
            continue
        proxy_after = float(shocked_proxy.iloc[-1])
        proxy_change = proxy_after - float(base_proxy.iloc[-1])
        rows.append(
            {
                "SPY shock": f"{shock * 100:.0f}%",
                "Estimated CTA proxy after shock": proxy_after,
                "Estimated selling pressure proxy": min(proxy_change, 0),
            }
        )

    return pd.DataFrame(rows)


def build_vol_control_proxy(
    market_df: pd.DataFrame,
    target_vol: float = 10,
    max_exposure: float = 1.5,
) -> pd.DataFrame:
    """Estimated vol-control exposure from SPY 20D/60D realized volatility."""

    if market_df.empty or "SPY" not in market_df.columns:
        return pd.DataFrame()

    result = pd.DataFrame(index=market_df.index)
    result["SPY_20D_RV"] = annualized_realized_vol(market_df["SPY"], 20)
    result["SPY_60D_RV"] = annualized_realized_vol(market_df["SPY"], 60)
    for window in [20, 60]:
        rv = result[f"SPY_{window}D_RV"]
        exposure = target_vol / rv.replace(0, np.nan)
        result[f"VOL_CONTROL_{window}D_EXPOSURE"] = exposure.clip(upper=max_exposure)

    result["VOL_CONTROL_AVG_EXPOSURE"] = result[
        ["VOL_CONTROL_20D_EXPOSURE", "VOL_CONTROL_60D_EXPOSURE"]
    ].mean(axis=1)
    return result.dropna(how="all")


def vol_control_scenarios(
    current_exposure: float | None,
    target_vol: float = 10,
    max_exposure: float = 1.5,
    scenario_vols: tuple[float, ...] = (15, 20, 25, 30),
) -> pd.DataFrame:
    if current_exposure is None or pd.isna(current_exposure):
        return pd.DataFrame()

    rows = []
    for realized_vol in scenario_vols:
        exposure = min(max_exposure, target_vol / realized_vol)
        rows.append(
            {
                "Realized vol scenario": f"{realized_vol:.0f}%",
                "Target equity exposure": exposure,
                "Estimated forced selling risk": max(current_exposure - exposure, 0),
            }
        )
    return pd.DataFrame(rows)
