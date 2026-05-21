# 美股流动性雷达 Macro Liquidity Radar

©Chuyang Wu 2026

一个本地可运行的 Streamlit dashboard，用于观察美元流动性、美股波动率 regime、估算系统性仓位压力，以及 Yahoo option-chain proxy 下的 options microstructure 信号。

本工具用于宏观研究与监控，不构成投资建议。

## 功能概览

Dashboard 当前包含 5 个页面：

- `宏观流动性`：Bank Reserves、RRP、TGA、SOFR-IORB、Net Liquidity、2s10s、credit spreads。
- `VIX / Vol Regime`：VIX、VVIX best effort、SPY 20D / 60D realized volatility、volatility risk premium proxy、VIX regime color band。
- `CTA Proxy`：基于 SPY / QQQ 趋势信号和 realized volatility 缩放的 Estimated CTA Equity Position Proxy。
- `Vol-Control Proxy`：基于 10% 目标波动率和 150% 杠杆上限的 Estimated Vol-Control Equity Exposure。
- `Options Microstructure`：低频拉取 SPY / QQQ option chain，估算 put/call、large OI strikes、put wall、call wall、max pain 和 0DTE volume proxy。

## 数据源

- FRED：宏观流动性、利率、信用利差数据。需要 `FRED_API_KEY`。
- yfinance / Yahoo：SPY、QQQ、VIX、VVIX、DXY、AI / 半导体资产和 option-chain proxy。
- Streamlit `st.cache_data`：缓存 FRED、市价和 options 请求，减少重复访问。

Yahoo / yfinance 是免费 best-effort 数据源，可能出现字段缺失、延迟、请求失败或 rate limit。Options 页面已经设计为失败不影响其它页面。

## 安装运行

```bash
cd macro-liquidity-dashboard
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

编辑 `.env`：

```bash
FRED_API_KEY=your_fred_api_key_here
```

启动：

```bash
streamlit run app.py
```

如果没有 FRED API key，可以在 FRED 官方文档申请：

https://fred.stlouisfed.org/docs/api/api_key.html

## 项目结构

```text
macro-liquidity-dashboard/
  app.py                    # Streamlit UI 与页面编排
  data.py                   # FRED 拉取、单位转换、频率对齐
  market.py                 # yfinance 价格数据拉取
  indicators.py             # 宏观流动性衍生指标
  rules.py                  # 状态规则与中文解读
  positioning.py            # volatility / CTA / vol-control proxy
  options_microstructure.py # option-chain proxy 计算
  charts.py                 # Plotly 图表
  config.py                 # series / ticker 配置
  requirements.txt
  .env.example
  README.md
```

## 指标定义

### 宏观流动性

金额类指标统一转换为十亿美元：

```text
Net Liquidity = Bank Reserves + RRP - TGA
SOFR-IORB bps = (SOFR - IORB) * 100
10Y-2Y bps = (DGS10 - DGS2) * 100
10Y Real Yield = DGS10 - T10YIE
```

状态规则：

- Bank Reserves 周变化 `< -150B` 为警戒，`> +50B` 为宽松。
- RRP `< 100B` 为接近枯竭，`> 500B` 为缓冲充足。
- TGA 周变化 `> +100B` 为抽水，`< -100B` 为放水。
- SOFR-IORB `> 5 bps` 为警戒，`< -5 bps` 为宽松。
- Net Liquidity 周变化 `< -250B` 为明显收紧，`> +100B` 为流动性改善。

### VIX / Vol Regime

SPY 用作 SPX proxy。Realized volatility 使用日收益率滚动标准差年化：

```text
realized_vol = rolling_std(daily_return, window) * sqrt(252)
volatility_risk_premium_proxy = VIX - SPY_20D_realized_vol
```

VIX regime：

- `VIX < 15`：Calm
- `15 <= VIX < 25`：Normal
- `25 <= VIX < 35`：Stress
- `VIX >= 35`：Crisis

VVIX 使用 yfinance best effort。如果免费数据不可用，页面会显示说明并保留接口。

### CTA Proxy

该指标是 **Estimated Proxy，不是真实 CTA 持仓**。

```text
trend_signal = +1 if price > moving_average else -1
trend_score = average(SPY/QQQ 20D, 60D, 120D trend signals)
vol_adjustment = max(avg(SPY_20D_RV, SPY_60D_RV) / 15%, 0.5)
CTA_proxy = clip(trend_score / vol_adjustment, -2, 2)
```

页面还会估算 SPY 再跌 `1%`、`3%`、`5%` 时 CTA proxy 的变化，并将负向变化展示为 selling pressure proxy。

### Vol-Control Proxy

该指标是 **Estimated Vol-Control Exposure，不是真实基金仓位**。

```text
target_vol = 10%
max_exposure = 150%
target_equity_exposure = min(max_exposure, target_vol / realized_vol)
```

页面使用 SPY 20D / 60D realized volatility 分别估算仓位，并展示 realized vol 升至 `15%`、`20%`、`25%`、`30%` 时的 forced selling risk。

### Options Microstructure Proxy

Options microstructure 为 Yahoo option-chain proxy，可能缺失或延迟。当前实现只低频拉取 SPY / QQQ 最近可用 expiry：

- Put/call volume ratio
- Put/call open-interest ratio
- Put wall / call wall
- Large OI strikes
- Max pain proxy
- 0DTE volume proxy，仅当最近 expiry 是当天

这不是完整 dealer gamma / delta 模型。真实 dealer positioning 通常需要 Cboe、ORATS、OptionMetrics、Polygon、Tradier 等更稳定或付费的数据源。

## 部署到 Streamlit Cloud

1. 将项目推送到 GitHub。
2. 打开 https://share.streamlit.io/ 并创建 app。
3. Main file path 填 `app.py`。
4. 在 App settings -> Secrets 中添加：

```toml
FRED_API_KEY = "your_fred_api_key_here"
```

`.env` 已被 `.gitignore` 忽略，不要把 API key 提交到 GitHub。

## 验证

语法检查：

```bash
python -m py_compile app.py charts.py config.py data.py indicators.py market.py options_microstructure.py positioning.py rules.py
```

本地页面检查：

```bash
streamlit run app.py
```

如果 yfinance 或 Yahoo options 被限流，页面会显示错误详情，但不应影响其它 tab 渲染。
