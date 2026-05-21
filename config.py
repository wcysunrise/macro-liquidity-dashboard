"""项目配置与 FRED series 元数据。"""

from __future__ import annotations

import os
from dataclasses import dataclass

import streamlit as st
from dotenv import load_dotenv


load_dotenv()


def _get_secret(name: str) -> str:
    """优先读取本地环境变量，其次读取 Streamlit Cloud secrets。"""

    value = os.getenv(name, "").strip()
    if value:
        return value

    try:
        return str(st.secrets.get(name, "")).strip()
    except Exception:
        return ""


FRED_API_KEY = _get_secret("FRED_API_KEY")
FRED_BASE_URL = "https://api.stlouisfed.org/fred"


@dataclass(frozen=True)
class SeriesConfig:
    series_id: str
    name: str
    description: str
    kind: str


SERIES: dict[str, SeriesConfig] = {
    "WRESBAL": SeriesConfig(
        series_id="WRESBAL",
        name="Bank Reserves",
        description="Reserve Balances with Federal Reserve Banks",
        kind="amount",
    ),
    "RRPONTSYD": SeriesConfig(
        series_id="RRPONTSYD",
        name="RRP",
        description="Overnight Reverse Repurchase Agreements",
        kind="amount",
    ),
    "WTREGEN": SeriesConfig(
        series_id="WTREGEN",
        name="TGA",
        description="Treasury General Account",
        kind="amount",
    ),
    "SOFR": SeriesConfig(
        series_id="SOFR",
        name="SOFR",
        description="Secured Overnight Financing Rate",
        kind="rate",
    ),
    "IORB": SeriesConfig(
        series_id="IORB",
        name="IORB",
        description="Interest on Reserve Balances",
        kind="rate",
    ),
    "DGS10": SeriesConfig(
        series_id="DGS10",
        name="10Y Treasury Yield",
        description="10-Year Treasury Constant Maturity Rate",
        kind="rate",
    ),
    "DGS2": SeriesConfig(
        series_id="DGS2",
        name="2Y Treasury Yield",
        description="2-Year Treasury Constant Maturity Rate",
        kind="rate",
    ),
    "BAMLH0A0HYM2": SeriesConfig(
        series_id="BAMLH0A0HYM2",
        name="HY Credit Spread",
        description="ICE BofA US High Yield Index Option-Adjusted Spread",
        kind="rate",
    ),
    "BAMLC0A0CM": SeriesConfig(
        series_id="BAMLC0A0CM",
        name="IG Credit Spread",
        description="ICE BofA US Corporate Index Option-Adjusted Spread",
        kind="rate",
    ),
    "T10YIE": SeriesConfig(
        series_id="T10YIE",
        name="10Y Breakeven Inflation",
        description="10-Year Breakeven Inflation Rate",
        kind="rate",
    ),
}


RISK_ASSETS = {
    "NVDA": "NVIDIA",
    "AMD": "Advanced Micro Devices",
    "SNDK": "SanDisk",
    "INTC": "Intel",
    "MU": "Micron",
    "ORCL": "Oracle",
    "SOXX": "iShares Semiconductor ETF",
    "SMH": "VanEck Semiconductor ETF",
    "QQQ": "NASDAQ 100 proxy",
}


RISK_INDICATORS = {
    "^VIX": "VIX",
    "DX-Y.NYB": "DXY proxy",
}


FRED_API_KEY_HELP = (
    "未检测到 FRED_API_KEY。请前往 https://fred.stlouisfed.org/docs/api/api_key.html "
    "申请 API key。本地运行时复制 .env.example 为 .env 并填入 FRED_API_KEY；"
    "部署到 Streamlit Cloud 时在 App secrets 中添加 FRED_API_KEY。"
)
