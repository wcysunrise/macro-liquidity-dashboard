from __future__ import annotations

import pandas as pd
import streamlit as st

from charts import line_chart, multi_line_chart
from config import FRED_API_KEY, FRED_API_KEY_HELP, SERIES
from data import load_macro_data
from indicators import (
    add_derived_indicators,
    metric_snapshot,
)
from rules import (
    build_statuses,
    comprehensive_status,
    generate_interpretation,
)

st.set_page_config(
    page_title="美元流动性雷达",
    page_icon="📡",
    layout="wide",
)


STATUS_COLORS = {
    "宽松": "#16a34a",
    "流动性改善": "#16a34a",
    "放水": "#16a34a",
    "缓冲充足": "#16a34a",
    "平稳": "#64748b",
    "中性": "#64748b",
    "观察": "#d97706",
    "观察但未失控": "#d97706",
    "缓冲下降": "#d97706",
    "流动性收紧": "#d97706",
    "警戒": "#dc2626",
    "明显收紧": "#dc2626",
    "接近枯竭": "#dc2626",
    "抽水": "#dc2626",
    "数据不足": "#94a3b8",
    "risk-on": "#16a34a",
    "risk-off": "#dc2626",
    "收紧": "#dc2626",
    "上行": "#dc2626",
    "下行": "#16a34a",
    "震荡": "#64748b",
    "Liquidity easing + risk-on": "#16a34a",
    "Liquidity tightening + risk-on": "#d97706",
    "Liquidity tightening + risk-off": "#dc2626",
    "Liquidity easing + risk-off": "#d97706",
}


def format_amount_b(value: float | None) -> str:
    if value is None:
        return "N/A"
    if abs(value) >= 1_000:
        return f"{value / 1_000:.2f} 万亿美元"
    return f"{value:.1f} 十亿美元"


def format_change_b(value: float | None) -> str:
    if value is None:
        return "N/A"
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.1f}B"


def format_bps(value: float | None) -> str:
    if value is None:
        return "N/A"
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.1f} bps"


def status_badge(status: str) -> str:
    color = STATUS_COLORS.get(status, "#64748b")
    return (
        f"<span style='display:inline-block;padding:0.18rem 0.5rem;"
        f"border-radius:999px;background:{color}1A;color:{color};"
        f"font-size:0.82rem;font-weight:700;'>{status}</span>"
    )


def render_card(
    title: str, current: str, weekly: str, monthly: str, status: str
) -> None:
    st.markdown(
        f"""
        <div style="border:1px solid #e5e7eb;border-radius:8px;padding:1rem;background:white;height:100%;">
          <div style="font-size:0.9rem;color:#64748b;margin-bottom:0.3rem;">{title}</div>
          <div style="font-size:1.55rem;font-weight:750;color:#0f172a;margin-bottom:0.35rem;">{current}</div>
          <div style="font-size:0.86rem;color:#475569;">周变化：<b>{weekly}</b></div>
          <div style="font-size:0.86rem;color:#475569;margin-bottom:0.45rem;">月变化：<b>{monthly}</b></div>
          {status_badge(status)}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_liquidity_page(df: pd.DataFrame, units: dict[str, str]) -> None:
    if df.empty:
        st.error("宏观流动性数据不可用。")
        return

    statuses = build_statuses(df)
    overall = comprehensive_status(df)

    latest_date = df.dropna(how="all").index[-1].date()
    st.markdown(
        f"**最新数据日期：** {latest_date} &nbsp;&nbsp; **综合状态：** {status_badge(overall)}",
        unsafe_allow_html=True,
    )

    st.divider()

    cards = [
        ("Bank Reserves", "WRESBAL", format_amount_b, statuses["bank_reserves"]),
        ("RRP", "RRPONTSYD", format_amount_b, statuses["rrp"]),
        ("TGA", "WTREGEN", format_amount_b, statuses["tga"]),
        ("SOFR - IORB", "SOFR_IORB_BPS", format_bps, statuses["sofr_iorb"]),
        ("Net Liquidity", "NET_LIQUIDITY", format_amount_b, statuses["net_liquidity"]),
    ]

    cols = st.columns(5)
    for col, (title, column, formatter, status) in zip(cols, cards):
        snapshot = metric_snapshot(df, column)
        with col:
            current = formatter(snapshot["current"])
            weekly = (
                format_bps(snapshot["weekly_change"])
                if column == "SOFR_IORB_BPS"
                else format_change_b(snapshot["weekly_change"])
            )
            monthly = (
                format_bps(snapshot["monthly_change"])
                if column == "SOFR_IORB_BPS"
                else format_change_b(snapshot["monthly_change"])
            )
            render_card(title, current, weekly, monthly, status)

    st.divider()

    left, right = st.columns(2)
    with left:
        st.plotly_chart(
            line_chart(
                df, "WRESBAL", "Bank Reserves 过去 1 年", "十亿美元", 12, "#2563eb"
            ),
            use_container_width=True,
        )
        st.plotly_chart(
            line_chart(df, "WTREGEN", "TGA 过去 1 年", "十亿美元", 12, "#dc2626"),
            use_container_width=True,
        )
        st.plotly_chart(
            line_chart(
                df,
                "NET_LIQUIDITY",
                "Net Liquidity 过去 1 年",
                "十亿美元",
                12,
                "#0f766e",
            ),
            use_container_width=True,
        )
    with right:
        st.plotly_chart(
            line_chart(df, "RRPONTSYD", "RRP 过去 1 年", "十亿美元", 12, "#7c3aed"),
            use_container_width=True,
        )
        st.plotly_chart(
            line_chart(
                df, "SOFR_IORB_BPS", "SOFR - IORB 过去 6 个月", "bps", 6, "#ea580c"
            ),
            use_container_width=True,
        )
        st.plotly_chart(
            line_chart(
                df,
                "YIELD_2S10S_BPS",
                "10Y - 2Y Yield Spread 过去 1 年",
                "bps",
                12,
                "#475569",
            ),
            use_container_width=True,
        )

    st.divider()

    left, right = st.columns(2)
    with left:
        st.plotly_chart(
            multi_line_chart(
                df,
                [
                    column
                    for column in ["BAMLH0A0HYM2", "BAMLC0A0CM"]
                    if column in df.columns
                ],
                "HY / IG OAS 过去 1 年",
                "percentage points",
                12,
            ),
            use_container_width=True,
        )
    with right:
        st.plotly_chart(
            multi_line_chart(
                df,
                [column for column in ["DGS2", "DGS10", "REAL_YIELD_10Y"] if column in df.columns],
                "2Y / 10Y / 10Y Real Yield 过去 1 年",
                "percentage points",
                12,
            ),
            use_container_width=True,
        )

    st.divider()
    st.info(generate_interpretation(df))

    with st.expander("数据说明与单位", expanded=False):
        st.write(
            "金额类指标已统一转换为十亿美元；利率类指标保留 FRED 的 percentage points，并在 spread 中转换为 bps。"
        )
        if units:
            st.write("FRED 原始单位：")
            for series_id, unit in units.items():
                st.write(f"- {series_id} ({SERIES[series_id].name})：{unit}")
        st.write(
            "Net Liquidity = Bank Reserves + RRP - TGA。SOFR-IORB 与 10Y-2Y 均以 bps 展示。"
        )


def main() -> None:
    st.title("美股流动性雷达 Macro Liquidity Radar")
    st.caption("监控美元流动性相关指标：Bank Reserves / RRP / TGA / SOFR-IORB / Net Liquidity")

    if FRED_API_KEY:
        raw_df, units, errors = load_macro_data(years=3)
        macro_df = (
            add_derived_indicators(raw_df) if not raw_df.empty else pd.DataFrame()
        )
    else:
        units = {}
        errors = {"FRED_API_KEY": FRED_API_KEY_HELP}
        macro_df = pd.DataFrame()

    if errors:
        st.warning("部分宏观数据不可用，相关指标和图表可能缺失。")
        with st.expander("查看 FRED 失败详情", expanded=False):
            for series_id, message in errors.items():
                name = SERIES[series_id].name if series_id in SERIES else series_id
                st.write(f"- {series_id} ({name})：{message}")

    render_liquidity_page(macro_df, units)


if __name__ == "__main__":
    main()
