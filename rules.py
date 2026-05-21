"""状态判断与中文自动解读规则。"""

from __future__ import annotations

from indicators import metric_snapshot


def status_bank_reserves(weekly_change_b: float | None) -> str:
    if weekly_change_b is None:
        return "数据不足"
    if weekly_change_b < -150:
        return "警戒"
    if weekly_change_b < -50:
        return "观察"
    if weekly_change_b <= 50:
        return "平稳"
    return "宽松"


def status_rrp(current_b: float | None) -> str:
    if current_b is None:
        return "数据不足"
    if current_b < 100:
        return "接近枯竭"
    if current_b <= 500:
        return "缓冲下降"
    return "缓冲充足"


def status_tga(weekly_change_b: float | None) -> str:
    if weekly_change_b is None:
        return "数据不足"
    if weekly_change_b < -100:
        return "放水"
    if weekly_change_b <= 100:
        return "平稳"
    return "抽水"


def status_sofr_iorb(spread_bps: float | None) -> str:
    if spread_bps is None:
        return "数据不足"
    if spread_bps > 5:
        return "警戒"
    if spread_bps >= 0:
        return "观察"
    if spread_bps >= -5:
        return "平稳"
    return "宽松"


def status_net_liquidity(weekly_change_b: float | None) -> str:
    if weekly_change_b is None:
        return "数据不足"
    if weekly_change_b < -250:
        return "明显收紧"
    if weekly_change_b < -100:
        return "流动性收紧"
    if weekly_change_b <= 100:
        return "平稳"
    return "流动性改善"


def build_statuses(df) -> dict[str, str]:
    bank = metric_snapshot(df, "WRESBAL")
    rrp = metric_snapshot(df, "RRPONTSYD")
    tga = metric_snapshot(df, "WTREGEN")
    sofr_iorb = metric_snapshot(df, "SOFR_IORB_BPS")
    net = metric_snapshot(df, "NET_LIQUIDITY")

    return {
        "bank_reserves": status_bank_reserves(bank["weekly_change"]),
        "rrp": status_rrp(rrp["current"]),
        "tga": status_tga(tga["weekly_change"]),
        "sofr_iorb": status_sofr_iorb(sofr_iorb["current"]),
        "net_liquidity": status_net_liquidity(net["weekly_change"]),
    }


def comprehensive_status(df) -> str:
    bank = metric_snapshot(df, "WRESBAL")
    rrp = metric_snapshot(df, "RRPONTSYD")
    tga = metric_snapshot(df, "WTREGEN")
    sofr_iorb = metric_snapshot(df, "SOFR_IORB_BPS")

    bank_falling_fast = bank["weekly_change"] is not None and bank["weekly_change"] < -150
    rrp_depleted = rrp["current"] is not None and rrp["current"] < 100
    tga_rising = tga["weekly_change"] is not None and tga["weekly_change"] > 100
    tga_falling = tga["weekly_change"] is not None and tga["weekly_change"] < -100
    bank_stable = bank["weekly_change"] is not None and -50 <= bank["weekly_change"] <= 50
    bank_rising = bank["weekly_change"] is not None and bank["weekly_change"] > 50
    sofr_positive = sofr_iorb["current"] is not None and sofr_iorb["current"] > 0
    sofr_negative = sofr_iorb["current"] is not None and sofr_iorb["current"] < 0
    rrp_falling = rrp["weekly_change"] is not None and rrp["weekly_change"] < 0

    if bank_falling_fast and rrp_depleted and tga_rising and sofr_positive:
        return "警戒"
    if tga_rising and rrp_falling and bank_stable:
        return "观察但未失控"
    if tga_falling and bank_rising and sofr_negative:
        return "宽松"
    return "中性"


def generate_interpretation(df) -> str:
    statuses = build_statuses(df)
    overall = comprehensive_status(df)

    fragments = [f"当前美元流动性综合状态为「{overall}」。"]

    if statuses["net_liquidity"] in {"流动性收紧", "明显收紧"}:
        fragments.append("Net Liquidity 边际回落，说明流动性正在收紧。")
    elif statuses["net_liquidity"] == "流动性改善":
        fragments.append("Net Liquidity 边际改善，对风险资产和融资环境相对友好。")
    else:
        fragments.append("Net Liquidity 近期变化不大，整体偏平稳。")

    if statuses["tga"] == "抽水":
        fragments.append("TGA 上升正在吸收市场流动性。")
    elif statuses["tga"] == "放水":
        fragments.append("TGA 下降正在向市场释放流动性。")

    if statuses["rrp"] == "接近枯竭":
        fragments.append("RRP 已接近低位，后续财政发债或准备金冲击更容易直接传导到银行准备金。")
    elif statuses["rrp"] == "缓冲充足":
        fragments.append("RRP 仍提供一定流动性缓冲。")

    if statuses["sofr_iorb"] in {"观察", "警戒"}:
        fragments.append("SOFR-IORB 已接近或高于 0，需关注隔夜融资压力是否持续。")
    else:
        fragments.append("SOFR-IORB 尚未持续转正，暂未显示明显 funding stress。")

    if overall == "警戒":
        fragments.append("组合信号显示准备金快速下降、RRP 缓冲不足、TGA 抽水且融资利差走高，需提高警惕。")
    elif overall == "观察但未失控":
        fragments.append("TGA 抽水与 RRP 下降并存，但 Bank Reserves 仍相对稳定，属于观察区间而非失控状态。")

    return "".join(fragments)
