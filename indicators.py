"""指标计算。"""

from __future__ import annotations

import pandas as pd


def add_derived_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """计算 Net Liquidity、SOFR-IORB、2s10s 和 10Y Real Yield。"""

    result = df.copy()

    if {"WRESBAL", "RRPONTSYD", "WTREGEN"}.issubset(result.columns):
        result["NET_LIQUIDITY"] = result["WRESBAL"] + result["RRPONTSYD"] - result["WTREGEN"]

    if {"SOFR", "IORB"}.issubset(result.columns):
        result["SOFR_IORB_BPS"] = (result["SOFR"] - result["IORB"]) * 100

    if {"DGS10", "DGS2"}.issubset(result.columns):
        result["YIELD_2S10S_BPS"] = (result["DGS10"] - result["DGS2"]) * 100

    if {"DGS10", "T10YIE"}.issubset(result.columns):
        result["REAL_YIELD_10Y"] = result["DGS10"] - result["T10YIE"]

    return result


def latest_valid_date(df: pd.DataFrame, column: str) -> pd.Timestamp | None:
    if column not in df.columns:
        return None
    series = df[column].dropna()
    if series.empty:
        return None
    return series.index[-1]


def latest_value(df: pd.DataFrame, column: str) -> float | None:
    latest_date = latest_valid_date(df, column)
    if latest_date is None:
        return None
    value = df.at[latest_date, column]
    if pd.isna(value):
        return None
    return float(value)


def change_over_days(df: pd.DataFrame, column: str, days: int) -> float | None:
    """计算最近值相对 days 天前或更早最近可得值的变化。"""

    if column not in df.columns:
        return None

    series = df[column].dropna().sort_index()
    if series.empty:
        return None

    latest_date = series.index[-1]
    target_date = latest_date - pd.Timedelta(days=days)
    previous = series.loc[:target_date]
    if previous.empty:
        return None

    return float(series.iloc[-1] - previous.iloc[-1])


def metric_snapshot(df: pd.DataFrame, column: str) -> dict[str, float | None]:
    return {
        "current": latest_value(df, column),
        "weekly_change": change_over_days(df, column, 7),
        "monthly_change": change_over_days(df, column, 30),
    }


def pct_change_over_days(df: pd.DataFrame, column: str, days: int) -> float | None:
    """计算价格或指数相对 days 天前的百分比变化。"""

    if column not in df.columns:
        return None

    series = df[column].dropna().sort_index()
    if series.empty:
        return None

    latest_date = series.index[-1]
    target_date = latest_date - pd.Timedelta(days=days)
    previous = series.loc[:target_date]
    if previous.empty or previous.iloc[-1] == 0:
        return None

    return float(series.iloc[-1] / previous.iloc[-1] - 1)


def rolling_correlations(
    macro_df: pd.DataFrame,
    market_df: pd.DataFrame,
    assets: list[str],
    windows: tuple[int, ...] = (30, 90),
) -> pd.DataFrame:
    """计算 Net Liquidity 日变化与风险资产日收益的 rolling correlation。"""

    if "NET_LIQUIDITY" not in macro_df.columns or market_df.empty:
        return pd.DataFrame()

    joined = pd.concat([macro_df[["NET_LIQUIDITY"]], market_df], axis=1, join="outer").sort_index().ffill()
    liquidity_change = joined["NET_LIQUIDITY"].pct_change()
    rows: list[dict[str, float | str | int | None]] = []

    for asset in assets:
        if asset not in joined.columns:
            continue
        asset_return = joined[asset].pct_change()
        for window in windows:
            corr = liquidity_change.rolling(window).corr(asset_return).dropna()
            rows.append(
                {
                    "asset": asset,
                    "window": window,
                    "correlation": float(corr.iloc[-1]) if not corr.empty else None,
                }
            )

    return pd.DataFrame(rows)


def latest_rolling_correlation_series(
    macro_df: pd.DataFrame,
    market_df: pd.DataFrame,
    asset: str,
    window: int,
) -> pd.Series:
    if "NET_LIQUIDITY" not in macro_df.columns or asset not in market_df.columns:
        return pd.Series(dtype=float)

    joined = pd.concat([macro_df[["NET_LIQUIDITY"]], market_df[[asset]]], axis=1, join="outer").sort_index().ffill()
    return joined["NET_LIQUIDITY"].pct_change().rolling(window).corr(joined[asset].pct_change()).dropna()


def classify_liquidity_direction(macro_df: pd.DataFrame) -> str:
    net = metric_snapshot(macro_df, "NET_LIQUIDITY")
    weekly = net["weekly_change"]
    monthly = net["monthly_change"]
    if monthly is None and weekly is None:
        return "数据不足"
    score = (monthly or 0) + 0.5 * (weekly or 0)
    if score > 100:
        return "宽松"
    if score < -100:
        return "收紧"
    return "中性"


def classify_rate_direction(macro_df: pd.DataFrame) -> str:
    ten_year = metric_snapshot(macro_df, "DGS10")
    monthly = ten_year["monthly_change"]
    if monthly is None:
        return "数据不足"
    change_bps = monthly * 100
    if change_bps > 15:
        return "上行"
    if change_bps < -15:
        return "下行"
    return "震荡"


def classify_risk_momentum(market_df: pd.DataFrame) -> str:
    qqq_20d = pct_change_over_days(market_df, "QQQ", 30)
    if qqq_20d is None:
        return "数据不足"
    if qqq_20d > 0.03:
        return "risk-on"
    if qqq_20d < -0.03:
        return "risk-off"
    return "中性"


def semiconductor_relative_strength(market_df: pd.DataFrame) -> tuple[str, float | None]:
    soxx_60d = pct_change_over_days(market_df, "SOXX", 90)
    qqq_60d = pct_change_over_days(market_df, "QQQ", 90)
    if soxx_60d is None or qqq_60d is None:
        return "数据不足", None

    spread = soxx_60d - qqq_60d
    if spread > 0.03:
        return "半导体强于 NASDAQ proxy", spread
    if spread < -0.03:
        return "半导体弱于 NASDAQ proxy", spread
    return "半导体与 NASDAQ proxy 接近", spread


def classify_regime(macro_df: pd.DataFrame, market_df: pd.DataFrame) -> str:
    liquidity = classify_liquidity_direction(macro_df)
    momentum = classify_risk_momentum(market_df)

    easing = liquidity in {"宽松", "中性"}
    risk_on = momentum in {"risk-on", "中性"}

    if easing and risk_on:
        return "Liquidity easing + risk-on"
    if not easing and risk_on:
        return "Liquidity tightening + risk-on"
    if not easing and not risk_on:
        return "Liquidity tightening + risk-off"
    return "Liquidity easing + risk-off"


def trading_observation(macro_df: pd.DataFrame, market_df: pd.DataFrame) -> dict[str, str]:
    semi_strength, spread = semiconductor_relative_strength(market_df)
    spread_text = "N/A" if spread is None else f"{spread * 100:+.1f}%"
    return {
        "流动性方向": classify_liquidity_direction(macro_df),
        "利率方向": classify_rate_direction(macro_df),
        "风险资产动量": classify_risk_momentum(market_df),
        "半导体相对强弱": f"{semi_strength}（90日相对收益 {spread_text}）",
        "当前 regime": classify_regime(macro_df, market_df),
    }
