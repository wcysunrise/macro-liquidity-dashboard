from __future__ import annotations

import pandas as pd
import streamlit as st

from charts import line_chart, multi_line_chart
from charts import gauge_chart, vix_regime_chart
from config import FRED_API_KEY, FRED_API_KEY_HELP, SERIES
from data import load_macro_data
from indicators import (
    add_derived_indicators,
    metric_snapshot,
)
from market import load_market_data
from options_microstructure import load_options_microstructure
from positioning import (
    build_cta_proxy,
    build_vol_control_proxy,
    build_volatility_frame,
    classify_vix_regime,
    cta_shock_scenarios,
    vol_control_scenarios,
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
    "Calm": "#16a34a",
    "Normal": "#64748b",
    "Stress": "#d97706",
    "Crisis": "#dc2626",
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


def format_pct(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "N/A"
    return f"{value:.1f}%"


def format_exposure(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "N/A"
    return f"{value * 100:.0f}%"


def format_ratio(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "N/A"
    return f"{value:.2f}x"


def latest_value_from_series(series: pd.Series) -> float | None:
    data = series.dropna()
    if data.empty:
        return None
    return float(data.iloc[-1])


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


def render_volatility_page(market_df: pd.DataFrame, market_errors: dict[str, str]) -> None:
    vol_df = build_volatility_frame(market_df)
    if vol_df.empty or "VIX" not in vol_df.columns or vol_df["VIX"].dropna().empty:
        st.error("VIX / volatility 数据不可用。")
        return

    latest_vix = latest_value_from_series(vol_df["VIX"])
    latest_rv20 = latest_value_from_series(vol_df["SPY_20D_RV"])
    latest_rv60 = latest_value_from_series(vol_df["SPY_60D_RV"])
    latest_vrp = latest_value_from_series(vol_df["VOL_RISK_PREMIUM"])
    regime = classify_vix_regime(latest_vix)

    st.markdown(
        f"**VIX regime：** {status_badge(regime)} &nbsp;&nbsp; "
        "**SPY 作为 SPX proxy；realized volatility 为年化百分比。**",
        unsafe_allow_html=True,
    )

    cols = st.columns(4)
    cols[0].metric("VIX", "N/A" if latest_vix is None else f"{latest_vix:.1f}")
    cols[1].metric("SPY 20D Realized Vol", format_pct(latest_rv20))
    cols[2].metric("SPY 60D Realized Vol", format_pct(latest_rv60))
    cols[3].metric("VIX - 20D RV", format_pct(latest_vrp))

    if "VVIX" in vol_df.columns and not vol_df["VVIX"].dropna().empty:
        st.metric("VVIX", f"{vol_df['VVIX'].dropna().iloc[-1]:.1f}")
    else:
        detail = market_errors.get("VVIX", "免费数据源未返回 VVIX；接口已预留。")
        st.info(f"VVIX 暂不可用：{detail}")

    left, right = st.columns(2)
    with left:
        st.plotly_chart(vix_regime_chart(vol_df, 12), use_container_width=True)
        st.plotly_chart(
            line_chart(vol_df, "VOL_RISK_PREMIUM", "Volatility Risk Premium Proxy", "VIX - RV", 12, "#0f766e"),
            use_container_width=True,
        )
    with right:
        st.plotly_chart(
            multi_line_chart(vol_df, ["VIX", "SPY_20D_RV", "SPY_60D_RV"], "Realized Vol vs Implied Vol", "%", 12),
            use_container_width=True,
        )
        if "VVIX" in vol_df.columns:
            st.plotly_chart(line_chart(vol_df, "VVIX", "VVIX 时间序列", "VVIX", 12, "#7c3aed"), use_container_width=True)


def render_cta_page(market_df: pd.DataFrame) -> None:
    cta_df = build_cta_proxy(market_df)
    if cta_df.empty:
        st.error("CTA proxy 数据不可用，需要 SPY 和 QQQ 价格。")
        return

    st.warning("Estimated Proxy，不是真实 CTA 持仓。SPY 作为 SPX proxy，QQQ 作为 Nasdaq proxy。")
    latest_proxy = latest_value_from_series(cta_df["CTA_PROXY"])
    latest_trend = latest_value_from_series(cta_df["TREND_SCORE"])
    latest_rv = latest_value_from_series(cta_df["AVG_RV"])

    cols = st.columns([1, 1, 2])
    cols[0].metric("CTA Equity Position Proxy", f"{latest_proxy:.2f}" if latest_proxy is not None else "N/A")
    cols[1].metric("Trend Score", f"{latest_trend:.2f}" if latest_trend is not None else "N/A")
    cols[2].metric("Vol Scaling Input", format_pct(latest_rv))

    left, right = st.columns([2, 1])
    with left:
        st.plotly_chart(line_chart(cta_df, "CTA_PROXY", "CTA Proxy Position Over Time", "proxy", 18, "#2563eb"), use_container_width=True)
    with right:
        st.plotly_chart(gauge_chart(latest_proxy, "当前 CTA 仓位仪表盘", -2, 2), use_container_width=True)

    scenarios = cta_shock_scenarios(market_df)
    st.subheader("SPY 下跌情景：Estimated CTA Selling Pressure Proxy")
    if scenarios.empty:
        st.info("CTA shock scenario 数据不足。")
    else:
        display = scenarios.copy()
        display["Estimated CTA proxy after shock"] = display["Estimated CTA proxy after shock"].map(lambda value: f"{value:.2f}")
        display["Estimated selling pressure proxy"] = display["Estimated selling pressure proxy"].map(lambda value: f"{value:.2f}")
        st.dataframe(display, use_container_width=True, hide_index=True)


def render_vol_control_page(market_df: pd.DataFrame) -> None:
    vol_control_df = build_vol_control_proxy(market_df)
    if vol_control_df.empty:
        st.error("Vol-control proxy 数据不可用，需要 SPY 价格。")
        return

    st.warning("Estimated Vol-Control Exposure，不是真实基金仓位。目标波动率假设为 10%，最大杠杆上限为 150%。")
    latest_20d = latest_value_from_series(vol_control_df["VOL_CONTROL_20D_EXPOSURE"])
    latest_60d = latest_value_from_series(vol_control_df["VOL_CONTROL_60D_EXPOSURE"])
    latest_avg = latest_value_from_series(vol_control_df["VOL_CONTROL_AVG_EXPOSURE"])

    cols = st.columns(3)
    cols[0].metric("20D Estimated Exposure", format_exposure(latest_20d))
    cols[1].metric("60D Estimated Exposure", format_exposure(latest_60d))
    cols[2].metric("Average Estimated Exposure", format_exposure(latest_avg))

    left, right = st.columns([2, 1])
    with left:
        st.plotly_chart(
            multi_line_chart(
                vol_control_df,
                ["VOL_CONTROL_20D_EXPOSURE", "VOL_CONTROL_60D_EXPOSURE", "VOL_CONTROL_AVG_EXPOSURE"],
                "Estimated Vol-Control Equity Exposure",
                "exposure",
                18,
            ),
            use_container_width=True,
        )
    with right:
        st.plotly_chart(gauge_chart(latest_avg, "Estimated Vol-Control Exposure", 0, 1.5), use_container_width=True)

    scenarios = vol_control_scenarios(latest_avg)
    st.subheader("Realized Vol 上升情景：Estimated Forced Selling Risk")
    if scenarios.empty:
        st.info("Vol-control scenario 数据不足。")
    else:
        display = scenarios.copy()
        display["Target equity exposure"] = display["Target equity exposure"].map(format_exposure)
        display["Estimated forced selling risk"] = display["Estimated forced selling risk"].map(format_exposure)
        st.dataframe(display, use_container_width=True, hide_index=True)


def render_options_page() -> None:
    st.warning("Options microstructure 为 Yahoo option-chain proxy，可能缺失或延迟。该页不是完整 dealer gamma / delta 模型。")
    summaries, errors = load_options_microstructure()

    if errors:
        with st.expander("Options 拉取失败详情", expanded=False):
            for ticker, message in errors.items():
                st.write(f"- {ticker}: {message}")

    if not summaries:
        st.info("Options data unavailable / rate-limited。其它页面不受影响。")
        return

    for ticker, summary in summaries.items():
        st.subheader(f"{ticker} Options Microstructure Proxy")
        st.caption(f"Expiry: {summary['expiry']} | 0DTE proxy: {'Yes' if summary['is_0dte'] else 'No'}")
        cols = st.columns(5)
        cols[0].metric("Put/Call Volume", format_ratio(summary["put_call_volume_ratio"]))
        cols[1].metric("Put/Call OI", format_ratio(summary["put_call_oi_ratio"]))
        cols[2].metric("Put Wall", "N/A" if summary["put_wall"] is None else f"{summary['put_wall']:.0f}")
        cols[3].metric("Call Wall", "N/A" if summary["call_wall"] is None else f"{summary['call_wall']:.0f}")
        cols[4].metric("Max Pain Proxy", "N/A" if summary["max_pain"] is None else f"{summary['max_pain']:.0f}")

        if summary["zero_dte_volume_proxy"] is not None:
            st.metric("0DTE Volume Proxy", f"{summary['zero_dte_volume_proxy']:,.0f}")
        else:
            st.info("0DTE volume proxy 暂不可用：最近拉取的 expiry 不是今天。")

        left, right = st.columns(2)
        with left:
            st.write("Top Call OI Strikes")
            st.dataframe(summary["top_calls"], use_container_width=True, hide_index=True)
        with right:
            st.write("Top Put OI Strikes")
            st.dataframe(summary["top_puts"], use_container_width=True, hide_index=True)


def main() -> None:
    st.title("美股流动性雷达 Macro Liquidity Radar")
    st.markdown(
        "<div style='margin-top:-0.85rem;margin-bottom:0.45rem;color:#94a3b8;font-size:0.82rem;'>©Chuyang Wu 2026</div>",
        unsafe_allow_html=True,
    )
    st.caption("监控美元流动性、波动率 regime、估算 CTA / vol-control 仓位和 options microstructure proxy")

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

    market_df, market_errors = load_market_data(years=3)
    if market_errors:
        st.warning("部分 yfinance 市场数据不可用，相关指标和图表可能缺失。")
        with st.expander("查看 yfinance 失败详情", expanded=False):
            for ticker, message in market_errors.items():
                st.write(f"- {ticker}: {message}")

    tabs = st.tabs(
        [
            "宏观流动性",
            "VIX / Vol Regime",
            "CTA Proxy",
            "Vol-Control Proxy",
            "Options Microstructure",
        ]
    )
    with tabs[0]:
        render_liquidity_page(macro_df, units)
    with tabs[1]:
        render_volatility_page(market_df, market_errors)
    with tabs[2]:
        render_cta_page(market_df)
    with tabs[3]:
        render_vol_control_page(market_df)
    with tabs[4]:
        render_options_page()


if __name__ == "__main__":
    main()
