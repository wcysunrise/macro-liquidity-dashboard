from __future__ import annotations

import pandas as pd
import streamlit as st

from charts import correlation_bar_chart, line_chart, multi_line_chart
from config import FRED_API_KEY, FRED_API_KEY_HELP, RISK_ASSETS, SERIES
from data import load_macro_data
from indicators import (
    add_derived_indicators,
    latest_rolling_correlation_series,
    metric_snapshot,
    pct_change_over_days,
    rolling_correlations,
    trading_observation,
)
from market import load_market_data
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


def format_pct(value: float | None) -> str:
    if value is None:
        return "N/A"
    sign = "+" if value > 0 else ""
    return f"{sign}{value * 100:.1f}%"


def render_metric_table(rows: list[dict[str, str]]) -> None:
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


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
    st.subheader("自动解读")
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


def render_risk_asset_page(market_df: pd.DataFrame, macro_df: pd.DataFrame) -> None:
    st.subheader("AI / 半导体风险资产")
    if market_df.empty:
        st.error("yfinance 市场价格数据不可用。")
        return

    asset_columns = [ticker for ticker in RISK_ASSETS if ticker in market_df.columns]
    rows = []
    for ticker in asset_columns:
        snapshot = metric_snapshot(market_df, ticker)
        rows.append(
            {
                "Ticker": ticker,
                "名称": RISK_ASSETS.get(ticker, ticker),
                "最新价格": (
                    "N/A"
                    if snapshot["current"] is None
                    else f"{snapshot['current']:.2f}"
                ),
                "1周": format_pct(pct_change_over_days(market_df, ticker, 7)),
                "1月": format_pct(pct_change_over_days(market_df, ticker, 30)),
                "3月": format_pct(pct_change_over_days(market_df, ticker, 90)),
            }
        )
    render_metric_table(rows)

    st.plotly_chart(
        multi_line_chart(
            market_df,
            [
                ticker
                for ticker in ["NVDA", "AMD", "SNDK", "INTC", "MU", "ORCL", "SOXX"]
                if ticker in market_df.columns
            ],
            "AI / 半导体资产相对走势（过去 1 年，起点=100）",
            "Indexed price",
            12,
            normalize=True,
        ),
        use_container_width=True,
    )

    left, right = st.columns(2)
    with left:
        risk_cols = [
            column for column in ["^VIX", "DXY"] if column in market_df.columns
        ]
        if risk_cols:
            st.plotly_chart(
                multi_line_chart(
                    market_df, risk_cols, "VIX / DXY 风险指标（过去 1 年）", "Level", 12
                ),
                use_container_width=True,
            )
    with right:
        spread_cols = [
            column
            for column in ["BAMLH0A0HYM2", "BAMLC0A0CM"]
            if column in macro_df.columns
        ]
        if spread_cols:
            st.plotly_chart(
                multi_line_chart(
                    macro_df,
                    spread_cols,
                    "HY / IG Credit Spread（过去 1 年）",
                    "percentage points",
                    12,
                ),
                use_container_width=True,
            )


def render_correlation_page(macro_df: pd.DataFrame, market_df: pd.DataFrame) -> None:
    st.subheader("Net Liquidity 与风险资产 Rolling Correlation")
    st.caption(
        "这里使用 Net Liquidity 日度百分比变化与资产日收益率计算 30日 / 90日 rolling correlation。"
    )

    if macro_df.empty or market_df.empty:
        st.error("宏观数据或市场数据不可用，无法计算相关性。")
        return

    assets = [
        asset for asset in ["NVDA", "SMH", "SOXX", "QQQ"] if asset in market_df.columns
    ]
    if not assets:
        st.warning("缺少 NVDA、SMH、SOXX、QQQ 价格数据，无法计算相关性。")
        return

    corr_df = rolling_correlations(macro_df, market_df, assets)
    st.plotly_chart(
        correlation_bar_chart(corr_df, "最新 30日 / 90日 Rolling Correlation"),
        use_container_width=True,
    )

    if not corr_df.empty:
        display = corr_df.copy()
        display["correlation"] = display["correlation"].map(
            lambda x: "N/A" if pd.isna(x) else f"{x:.2f}"
        )
        render_metric_table(
            display.rename(
                columns={"asset": "资产", "window": "窗口", "correlation": "相关性"}
            ).to_dict("records")
        )

    selected_asset = st.selectbox("选择资产查看历史相关性", assets, index=0)
    selected_window = st.radio("窗口", [30, 90], horizontal=True)
    if selected_asset:
        series = latest_rolling_correlation_series(
            macro_df, market_df, selected_asset, selected_window
        )
        corr_history = series.to_frame(f"{selected_asset}_{selected_window}D_CORR")
        st.plotly_chart(
            line_chart(
                corr_history,
                corr_history.columns[0],
                f"{selected_asset} {selected_window}日相关性历史",
                "correlation",
                12,
                "#2563eb",
            ),
            use_container_width=True,
        )


def render_trading_observation_page(
    macro_df: pd.DataFrame, market_df: pd.DataFrame
) -> None:
    st.subheader("交易观察")
    st.caption("仅展示宏观与市场状态，不构成直接买卖建议。")

    if macro_df.empty or market_df.empty:
        st.error("宏观数据或市场数据不可用，无法生成交易观察。")
        return

    observations = trading_observation(macro_df, market_df)
    cols = st.columns(len(observations))
    for col, (label, value) in zip(cols, observations.items()):
        with col:
            st.markdown(
                f"""
                <div style="border:1px solid #e5e7eb;border-radius:8px;padding:1rem;background:white;height:100%;">
                  <div style="font-size:0.88rem;color:#64748b;margin-bottom:0.35rem;">{label}</div>
                  <div style="font-size:1.1rem;font-weight:750;color:#0f172a;line-height:1.35;">{value}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.divider()
    st.write("观察框架：")
    st.write("- 流动性方向：基于 Net Liquidity 近 1周与 1月变化。")
    st.write("- 利率方向：基于 10Y Treasury Yield 近 1月变化。")
    st.write("- 风险资产动量：基于 QQQ 近 1月收益率。")
    st.write("- 半导体相对强弱：基于 SOXX 相对 QQQ 的近 3月收益差。")
    st.write("- 当前 regime：组合流动性方向与风险资产动量。")


def main() -> None:
    st.title("美股流动性雷达 Macro Liquidity Radar")
    st.caption(
        "监控 Bank Reserves / RRP / TGA / SOFR-IORB / Net Liquidity / AI 半导体风险资产"
    )

    if FRED_API_KEY:
        raw_df, units, errors = load_macro_data(years=3)
        macro_df = (
            add_derived_indicators(raw_df) if not raw_df.empty else pd.DataFrame()
        )
    else:
        units = {}
        errors = {"FRED_API_KEY": FRED_API_KEY_HELP}
        macro_df = pd.DataFrame()

    market_df, market_errors = load_market_data(years=3)

    if errors:
        st.warning("部分宏观数据不可用，相关指标和图表可能缺失。")
        with st.expander("查看 FRED 失败详情", expanded=False):
            for series_id, message in errors.items():
                name = SERIES[series_id].name if series_id in SERIES else series_id
                st.write(f"- {series_id} ({name})：{message}")

    if market_errors:
        st.warning("部分 yfinance 市场数据不可用，相关指标和图表可能缺失。")
        with st.expander("查看 yfinance 失败详情", expanded=False):
            for ticker, message in market_errors.items():
                st.write(f"- {ticker}：{message}")

    tab_liquidity, tab_risk, tab_corr, tab_trade = st.tabs(
        ["流动性雷达", "AI/半导体与风险指标", "相关性分析", "交易观察"]
    )

    with tab_liquidity:
        render_liquidity_page(macro_df, units)
    with tab_risk:
        render_risk_asset_page(market_df, macro_df)
    with tab_corr:
        render_correlation_page(macro_df, market_df)
    with tab_trade:
        render_trading_observation_page(macro_df, market_df)


if __name__ == "__main__":
    main()
