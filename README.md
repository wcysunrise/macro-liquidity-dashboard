# 美元流动性雷达 Macro Liquidity Radar

本项目是一个本地可运行的 Streamlit dashboard，用于观察美元宏观流动性和美债 funding pressure。

## 功能

- 拉取 FRED 数据：Bank Reserves、RRP、TGA、SOFR、IORB、10Y Treasury Yield、2Y Treasury Yield
- 拉取 FRED 信用利差：HY credit spread、IG credit spread
- 使用 yfinance 拉取 AI/半导体风险资产：NVDA、AMD、SNDK、INTC、MU、ORCL、SOXX、SMH、QQQ
- 使用 yfinance 拉取风险指标：VIX、DXY proxy
- 计算 Net Liquidity、SOFR-IORB、10Y-2Y yield spread
- 计算 Net Liquidity 与 NVDA、SMH、SOXX、QQQ 的 30日 / 90日 rolling correlation
- 生成 regime 标签与「交易观察」页面
- 自动统一金额单位为十亿美元，并按需显示为万亿美元
- 展示 summary cards、交互式 Plotly 图表和中文自动解读
- 单个 FRED series 拉取失败时在 UI 中显示错误，不让程序崩溃
- 使用 `st.cache_data` 缓存数据，减少重复请求

## 项目结构

```text
macro-liquidity-dashboard/
  app.py
  data.py
  market.py
  indicators.py
  rules.py
  charts.py
  config.py
  requirements.txt
  .env.example
  .gitignore
  README.md
```

## 安装与运行

```bash
cd macro-liquidity-dashboard
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

编辑 `.env`，填入你的 FRED API key：

```bash
FRED_API_KEY=your_fred_api_key_here
```

启动 dashboard：

```bash
streamlit run app.py
```

如果没有 FRED API key，请前往 FRED 官方文档申请：

https://fred.stlouisfed.org/docs/api/api_key.html

## 部署成网页

推荐使用 GitHub + Streamlit Community Cloud。GitHub Pages 只能托管静态网页，不能直接运行这个 Python dashboard；Streamlit Cloud 可以从 GitHub 仓库启动 `app.py` 并提供网页地址。

### 1. 推送到 GitHub

在项目目录初始化 Git 仓库并推送：

```bash
cd macro-liquidity-dashboard
git init
git add .
git commit -m "Initial macro liquidity dashboard"
git branch -M main
git remote add origin https://github.com/你的用户名/macro-liquidity-dashboard.git
git push -u origin main
```

注意：`.env` 已被 `.gitignore` 忽略，不要把 FRED API key 提交到 GitHub。

### 2. 在 Streamlit Cloud 创建 App

1. 打开 https://share.streamlit.io/
2. 使用 GitHub 登录
3. 选择仓库 `macro-liquidity-dashboard`
4. Branch 选择 `main`
5. Main file path 填写 `app.py`

### 3. 配置 API key

在 Streamlit Cloud 的 App settings -> Secrets 中添加：

```toml
FRED_API_KEY = "your_fred_api_key_here"
```

保存后重启 App，即可获得一个公开网页链接。

## 指标定义

### Net Liquidity

```text
Net Liquidity = Bank Reserves + RRP - TGA
```

金额类指标统一转换为十亿美元：

- 大于 1000B 时显示为 `x.x 万亿美元`
- 小于 1000B 时显示为 `x.x 十亿美元`

### SOFR - IORB

```text
spread_bps = (SOFR - IORB) * 100
```

FRED 利率单位为 percentage points，dashboard 转换为 basis points。

### 10Y - 2Y Yield Spread

```text
yield_spread_bps = (DGS10 - DGS2) * 100
```

### Rolling Correlation

```text
corr = rolling_corr(Net Liquidity 日度百分比变化, 风险资产日收益率)
```

当前支持：

- NVDA
- SMH
- SOXX
- QQQ，作为 NASDAQ proxy

窗口：

- 30日
- 90日

### Regime

Dashboard 将流动性方向与风险资产动量组合为四类 regime：

- Liquidity easing + risk-on
- Liquidity tightening + risk-on
- Liquidity tightening + risk-off
- Liquidity easing + risk-off

「交易观察」页面展示：

- 流动性方向
- 利率方向
- 风险资产动量
- 半导体相对强弱
- 当前 regime

该页面仅用于观察，不直接给出买卖建议。

## 状态规则

### Bank Reserves

- 周变化 > +50B：宽松
- 周变化 between -50B and +50B：平稳
- 周变化 < -50B：观察
- 周变化 < -150B：警戒

### RRP

- 当前值 > 500B：缓冲充足
- 当前值 between 100B and 500B：缓冲下降
- 当前值 < 100B：接近枯竭

### TGA

- 周变化 > +100B：抽水
- 周变化 between -100B and +100B：平稳
- 周变化 < -100B：放水

### SOFR-IORB

- spread_bps < -5：宽松
- spread_bps between -5 and 0：平稳
- spread_bps between 0 and 5：观察
- spread_bps > 5：警戒

### Net Liquidity

- 周变化 > +100B：流动性改善
- 周变化 between -100B and +100B：平稳
- 周变化 < -100B：流动性收紧
- 周变化 < -250B：明显收紧

## 综合状态规则

- 如果 Bank Reserves 快速下降，RRP < 100B，TGA 上升，SOFR-IORB > 0，则状态为「警戒」
- 如果 TGA 上升但 RRP 下降、Bank Reserves 稳定，则状态为「观察但未失控」
- 如果 TGA 下降、Bank Reserves 上升、SOFR-IORB < 0，则状态为「宽松」
- 否则为「中性」

## 备注

本工具用于宏观研究与监控，不构成投资建议。
