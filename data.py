"""FRED 数据拉取、单位转换与频率对齐。"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pandas as pd
import requests
import streamlit as st

from config import FRED_API_KEY, FRED_BASE_URL, SERIES


class FredDataError(Exception):
    """FRED 请求或解析失败。"""


def _request_fred(endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
    url = f"{FRED_BASE_URL}/{endpoint}"
    payload = {
        "api_key": FRED_API_KEY,
        "file_type": "json",
        **params,
    }
    try:
        response = requests.get(url, params=payload, timeout=20)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as exc:
        raise FredDataError(f"网络请求失败：{exc}") from exc
    except ValueError as exc:
        raise FredDataError("FRED 返回了非 JSON 响应") from exc

    if "error_code" in data:
        raise FredDataError(f"FRED API 错误：{data.get('error_message', data['error_code'])}")
    return data


def _get_series_units(series_id: str) -> str:
    data = _request_fred("series", {"series_id": series_id})
    seriess = data.get("seriess", [])
    if not seriess:
        raise FredDataError("未找到 series 元数据")
    return str(seriess[0].get("units", "")).strip()


def _amount_to_billions(values: pd.Series, units: str, series_id: str) -> pd.Series:
    """金额类 series 统一转为十亿美元。

    FRED 金额单位常见为 Millions of Dollars 或 Billions of Dollars。
    如果元数据不可识别，保守使用该项目的已知兜底映射。
    """

    normalized = units.lower()
    if "millions" in normalized:
        return values / 1_000
    if "billions" in normalized:
        return values
    if "trillions" in normalized:
        return values * 1_000

    fallback_divisor = {
        "WTREGEN": 1_000,  # Treasury General Account 通常为 Millions of Dollars
    }
    return values / fallback_divisor.get(series_id, 1)


@st.cache_data(ttl=60 * 60, show_spinner=False)
def fetch_series(series_id: str, observation_start: str) -> tuple[pd.DataFrame, str]:
    """拉取单个 FRED series，并返回日期索引 DataFrame 与原始单位。"""

    units = _get_series_units(series_id)
    data = _request_fred(
        "series/observations",
        {
            "series_id": series_id,
            "observation_start": observation_start,
            "sort_order": "asc",
        },
    )
    observations = data.get("observations", [])
    if not observations:
        raise FredDataError("未返回 observations")

    frame = pd.DataFrame(observations)
    frame["date"] = pd.to_datetime(frame["date"])
    frame[series_id] = pd.to_numeric(frame["value"].replace(".", pd.NA), errors="coerce")
    frame = frame[["date", series_id]].set_index("date").sort_index()

    if SERIES[series_id].kind == "amount":
        frame[series_id] = _amount_to_billions(frame[series_id], units, series_id)

    return frame, units


@st.cache_data(ttl=60 * 60, show_spinner="正在从 FRED 拉取宏观流动性数据...")
def load_macro_data(years: int = 3) -> tuple[pd.DataFrame, dict[str, str], dict[str, str]]:
    """拉取全部 series，outer join 后 forward fill。

    返回：
    - df：按日对齐后的数据，金额单位为十亿美元，利率单位为 percentage points
    - units：FRED 原始单位
    - errors：单个 series 的错误信息
    """

    observation_start = (date.today() - timedelta(days=365 * years + 45)).isoformat()
    frames: list[pd.DataFrame] = []
    units: dict[str, str] = {}
    errors: dict[str, str] = {}

    for series_id in SERIES:
        try:
            frame, unit = fetch_series(series_id, observation_start)
            frames.append(frame)
            units[series_id] = unit
        except FredDataError as exc:
            errors[series_id] = str(exc)
        except Exception as exc:  # UI 需要优雅展示未知错误，不能让页面崩溃
            errors[series_id] = f"未知错误：{exc}"

    if not frames:
        return pd.DataFrame(), units, errors

    df = pd.concat(frames, axis=1, join="outer").sort_index()
    df = df.ffill()
    df = df.dropna(how="all")
    return df, units, errors
