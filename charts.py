"""Plotly 图表。"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go


def _window(df: pd.DataFrame, column: str, months: int) -> pd.DataFrame:
    if column not in df.columns or df[column].dropna().empty:
        return pd.DataFrame(columns=[column])
    end = df[column].dropna().index[-1]
    start = end - pd.DateOffset(months=months)
    return df.loc[df.index >= start, [column]].dropna()


def line_chart(
    df: pd.DataFrame,
    column: str,
    title: str,
    y_title: str,
    months: int,
    color: str = "#2563eb",
) -> go.Figure:
    data = _window(df, column, months)
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=data.index,
            y=data[column] if column in data.columns else [],
            mode="lines",
            line={"color": color, "width": 2},
            hovertemplate="%{x|%Y-%m-%d}<br>%{y:.2f}<extra></extra>",
        )
    )
    fig.update_layout(
        title={"text": title, "font": {"size": 16}},
        height=330,
        margin={"l": 48, "r": 24, "t": 48, "b": 36},
        template="plotly_white",
        hovermode="x unified",
        xaxis_title=None,
        yaxis_title=y_title,
        font={"family": "Arial, sans-serif"},
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor="#e5e7eb", zerolinecolor="#9ca3af")
    return fig


def multi_line_chart(
    df: pd.DataFrame,
    columns: list[str],
    title: str,
    y_title: str,
    months: int,
    normalize: bool = False,
) -> go.Figure:
    fig = go.Figure()
    if df.empty:
        return fig

    end = df.dropna(how="all").index[-1]
    start = end - pd.DateOffset(months=months)
    data = df.loc[df.index >= start, [column for column in columns if column in df.columns]].dropna(how="all")

    for column in data.columns:
        series = data[column].dropna()
        if normalize and not series.empty:
            series = series / series.iloc[0] * 100
        fig.add_trace(
            go.Scatter(
                x=series.index,
                y=series,
                mode="lines",
                name=column,
                line={"width": 2},
                hovertemplate="%{x|%Y-%m-%d}<br>%{y:.2f}<extra></extra>",
            )
        )

    fig.update_layout(
        title={"text": title, "font": {"size": 16}},
        height=360,
        margin={"l": 48, "r": 24, "t": 48, "b": 36},
        template="plotly_white",
        hovermode="x unified",
        xaxis_title=None,
        yaxis_title=y_title,
        legend={"orientation": "h", "y": -0.18},
        font={"family": "Arial, sans-serif"},
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor="#e5e7eb", zerolinecolor="#9ca3af")
    return fig


def correlation_bar_chart(corr_df: pd.DataFrame, title: str) -> go.Figure:
    fig = go.Figure()
    if corr_df.empty:
        return fig

    for window in sorted(corr_df["window"].dropna().unique()):
        subset = corr_df[corr_df["window"] == window]
        fig.add_trace(
            go.Bar(
                x=subset["asset"],
                y=subset["correlation"],
                name=f"{int(window)}日",
                hovertemplate="%{x}<br>corr=%{y:.2f}<extra></extra>",
            )
        )

    fig.update_layout(
        title={"text": title, "font": {"size": 16}},
        height=360,
        margin={"l": 48, "r": 24, "t": 48, "b": 36},
        template="plotly_white",
        barmode="group",
        yaxis_title="correlation",
        xaxis_title=None,
        font={"family": "Arial, sans-serif"},
    )
    fig.update_yaxes(range=[-1, 1], gridcolor="#e5e7eb", zerolinecolor="#9ca3af")
    return fig


def vix_regime_chart(df: pd.DataFrame, months: int = 12) -> go.Figure:
    fig = go.Figure()
    if df.empty or "VIX" not in df.columns or df["VIX"].dropna().empty:
        return fig

    end = df["VIX"].dropna().index[-1]
    start = end - pd.DateOffset(months=months)
    data = df.loc[df.index >= start, ["VIX"]].dropna()
    if data.empty:
        return fig

    fig.add_hrect(y0=0, y1=15, fillcolor="#16a34a", opacity=0.10, line_width=0, annotation_text="Calm")
    fig.add_hrect(y0=15, y1=25, fillcolor="#64748b", opacity=0.10, line_width=0, annotation_text="Normal")
    fig.add_hrect(y0=25, y1=35, fillcolor="#d97706", opacity=0.12, line_width=0, annotation_text="Stress")
    fig.add_hrect(y0=35, y1=max(80, float(data["VIX"].max()) + 5), fillcolor="#dc2626", opacity=0.10, line_width=0, annotation_text="Crisis")
    fig.add_trace(
        go.Scatter(
            x=data.index,
            y=data["VIX"],
            name="VIX",
            mode="lines",
            line={"color": "#2563eb", "width": 2},
            hovertemplate="%{x|%Y-%m-%d}<br>VIX=%{y:.2f}<extra></extra>",
        )
    )
    fig.update_layout(
        title={"text": "VIX Regime Color Band", "font": {"size": 16}},
        height=360,
        margin={"l": 48, "r": 24, "t": 48, "b": 36},
        template="plotly_white",
        hovermode="x unified",
        xaxis_title=None,
        yaxis_title="VIX",
        font={"family": "Arial, sans-serif"},
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor="#e5e7eb", zerolinecolor="#9ca3af", range=[0, max(45, float(data["VIX"].max()) + 5)])
    return fig


def gauge_chart(value: float | None, title: str, min_value: float, max_value: float, suffix: str = "") -> go.Figure:
    fig = go.Figure()
    numeric_value = 0 if value is None or pd.isna(value) else float(value)
    fig.add_trace(
        go.Indicator(
            mode="gauge+number",
            value=numeric_value,
            title={"text": title, "font": {"size": 16}},
            number={"suffix": suffix},
            gauge={
                "axis": {"range": [min_value, max_value]},
                "bar": {"color": "#2563eb"},
                "steps": [
                    {"range": [min_value, 0], "color": "#fee2e2"},
                    {"range": [0, max_value], "color": "#dcfce7"},
                ],
                "threshold": {"line": {"color": "#0f172a", "width": 2}, "value": numeric_value},
            },
        )
    )
    fig.update_layout(
        height=300,
        margin={"l": 32, "r": 32, "t": 56, "b": 16},
        template="plotly_white",
        font={"family": "Arial, sans-serif"},
    )
    return fig
