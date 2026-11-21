# FX Backtester: Institutional Quantitative Forex Research Engine

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Trading-Quantitative Finance](https://img.shields.io/badge/Domain-Quantitative%20Finance-emerald.svg)]()
[![Platform-Forex Algorithmic Trading](https://img.shields.io/badge/Platform-Algorithmic%20Trading-purple.svg)]()
[![MQL5 Production EA](https://img.shields.io/badge/MQL5-Expert%20Advisor-orange.svg)]()
[![Pine Script v6](https://img.shields.io/badge/TradingView-Pine%20Script%20v6-blueviolet.svg)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

An institutional-grade, vectorized quantitative backtesting, parameter optimization, and multi-asset research engine engineered specifically for Foreign Exchange (Forex) spot markets.

The framework is calibrated around high-probability candlestick price action reversals (Morning Star and Evening Star formations) synergized with Wilder's Relative Strength Index (RSI), moving average cross filters, ultra-short frequency regime detection, and Chaikin Money Flow (CMF).

---

## Table of Contents

- [Overview & Philosophy](#overview--philosophy)
- [System Architecture](#system-architecture)
- [Key Features](#key-features)
- [Strategy & Technical Methodology](#strategy--technical-methodology)
- [Supported Currency Universe](#supported-currency-universe)
- [Directory Structure](#directory-structure)
- [Installation & Quickstart](#installation--quickstart)
- [CLI Usage Guide](#cli-usage-guide)
  - [1. Single-Pair and Portfolio Backtesting](#1-single-pair-and-portfolio-backtesting)
  - [2. Multi-Year Validation (5-Year Stress Test)](#2-multi-year-validation-5-year-stress-test)
  - [3. Batch Research Engine (10-Year Slice Analysis)](#3-batch-research-engine-10-year-slice-analysis)
  - [4. Vectorized Parameter Optimization](#4-vectorized-parameter-optimization)
  - [5. Batch Leaderboard Aggregation](#5-batch-leaderboard-aggregation)
- [MetaTrader 5 & TradingView Integration](#metatrader-5--tradingview-integration)
- [Unit Testing](#unit-testing)
- [Risk Disclaimer](#risk-disclaimer)
- [License](#license)

---

## Overview & Philosophy

Retail backtesting often suffers from severe methodological flaws: lookahead bias, unmodelled bid/ask spread dynamics, unrealized slippage, and curve-fitting over brief historical samples.

**FX Backtester** solves these pitfalls through:
1. **Realistic Execution Modeling:** Trades trigger strictly on the open of the subsequent bar (`bar[i+1]`), with exact point/pip spread subtraction, slippage tolerances, and per-lot broker commission tracking.
2. **Strict Intra-Bar Path Resolution:** High/low boundary analysis detects adverse stops versus profit targets without ambiguous optimistic fills.
3. **Multi-Regime Batch Slicing:** A rolling 180-day slice evaluation method assesses whether parameter stability holds across trending, ranging, and high-volatility macroeconomic environments.
4. **End-to-End Deployment Bridge:** Seamless transition from research in Python to production via native MetaTrader 5 (MQL5) Expert Advisors and TradingView Pine Script v6 indicators.

---

## System Architecture

```
                       ┌───────────────────────────────┐
                       │   Dukascopy Historical Feed   │
                       └───────────────┬───────────────┘
                                       │ Raw Tick / OHLCV
                                       ▼
                       ┌───────────────────────────────┐
                       │   data/dukascopy_loader.py    │
                       │     (Local Parquet Cache)     │
                       └───────────────┬───────────────┘
                                       │ Cleaned Time Series
                                       ▼
    ┌──────────────────────────────────┴──────────────────────────────────┐
    │                                                                     │
    ▼                                                                     ▼
┌──────────────────────────────┐                       ┌──────────────────────────────┐
│  indicators/                 │                       │  optimize.py                 │
│  - star_pattern.py           │                       │  (Vectorized Bitmasks &      │
│  - rsi.py (Wilder + MA)      │                       │   Geometry Precalculation)   │
│  - rsi_env.py (RSI-2 Regime) │                       └──────────────┬───────────────┘
│  - cmf.py (Chaikin Flow)     │                                      │
└──────────────┬───────────────┘                                      │
               │ Precomputed Signals                                  ▼
               ▼                                       ┌──────────────────────────────┐
┌──────────────────────────────┐                       │  batch_research_engine.py    │
│  strategy/star_rsi_strategy  │                       │  (10-Year 180-Day Slices)    │
└──────────────┬───────────────┘                       └──────────────┬───────────────┘
               │ Triggers & Stops                                     │
               ▼                                                      ▼
┌──────────────────────────────┐                       ┌──────────────────────────────┐
│  backtest/engine.py          │                       │  analyze_batch_leaderboard   │
│  - Next-bar execution        │                       │  (Cross-Asset Master Tables) │
│  - Spread, Slippage, Comm    │                       └──────────────────────────────┘
│  - Intra-bar SL / TP paths   │
└──────────────┬───────────────┘
               │ Realized Trades
               ▼
┌──────────────────────────────┐
│  backtest/metrics.py         │
│  - Sharpe, Sortino, Calmar   │
│  - Max DD %, Profit Factor   │
│  - R-Multiple Expectancy     │
└──────────────┬───────────────┘
               │ Exported Artifacts
               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Production Targets:                                                     │
│ - mql5/StarRSI_EURUSD_M5.mq5  (MT5 Production Trading Bot)              │
│ - pine.pine                   (TradingView v6 Visualization Engine)     │
│ - reports/                    (CSV trade logs & Markdown leaderboards)  │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Key Features

- **Multi-Year Historical Analysis:** Seamless automated downloading of tick and candle data across any customizable date horizon using Dukascopy feeds.
- **Fast Parameter Grid Search:** NumPy-accelerated precomputation of candle geometries and RSI cross matrices, running hundreds of thousands of combinations per minute.
- **Regime-Robust Batch Research:** Partitions up to 10 years of data into independent 180-day non-overlapping segments to score cross-market robustness and prevent overfitting.
- **Institutional Risk & Performance Metrics:**
  - Net Profit & Total Return percentage
  - Profit Factor (Gross Gains / Gross Losses)
  - Annualized Sharpe, Sortino, and Calmar ratios
  - Peak-to-Trough Maximum Drawdown ($ and %)
  - Mathematical Expectancy in both fiat currency ($) and risk-unit multiples (R)
  - Average Trade Holding Period (bars) and Payoff Ratio
- **Full Production Equivalents:** Includes both a ready-to-compile MetaTrader 5 Expert Advisor (`.mq5`) with visual chart HUD and a TradingView Pine Script v6 indicator (`pine.pine`).

---

## Strategy & Technical Methodology

The primary algorithmic model utilizes a multi-layered filter architecture:

### 1. Candlestick Star Geometry
- **Morning Star (Bullish Reversal):**
  - **Leg 1:** Strong bearish candle with body exceeding the minimum threshold (`body >= 10% of candle range`).
  - **Leg 2 (The Star):** Small real body relative to its neighbors (`body2 <= body1 * factor` and `body2 <= range2 * factor`).
  - **Soft Detachment:** Star opens or closes lower than Leg 1 without requiring extreme weekend gaps.
  - **Leg 3 (Confirmation):** Strong bullish close driving past at least 50% of Leg 1's real body.
- **Evening Star (Bearish Reversal):** Inverted bearish counterpart at cyclical swing highs.
- **Color Conformity & Doji Guards:** Optional rules requiring Leg 2 color to confirm Leg 3 or waiving color matching when Leg 2 forms a neutral doji.

### 2. Wilder's RSI Signal Confirmation
- Computes standard Wilder smoothed Relative Strength Index.
- Validates bullish reversals when RSI crosses upward from oversold levels (e.g., 25, 30, or 35) or bearish reversals when crossing downward from overbought levels (e.g., 65, 70, or 75).
- Optional moving average filter: verifies RSI is above its 14-period SMA for longs, or below for shorts.
- Window lookback tolerance: permits the RSI cross to occur concurrently or within an *N*-bar window preceding pattern completion.

### 3. Context & Regime Overlays
- **RSI(2) Extreme-Frequency Filter:** Measures short-term exhaustion imbalances across a rolling 30-bar window.
- **Chaikin Money Flow (CMF):** Evaluates whether institutional volume-weighted accumulation supports the reversal.
- **SMA Trend Filter:** Configurable for either trend-following entries (e.g., price above SMA 50) or mean-reversion counter-trend entries.

---

## Supported Currency Universe

The system defines 28 standard Forex pairs across G8 currencies with precise pip calculations:

| Group | Currency Pairs |
| :--- | :--- |
| **7 Majors** | EUR/USD, GBP/USD, USD/JPY, AUD/USD, USD/CAD, USD/CHF, NZD/USD |
| **EUR Crosses** | EUR/GBP, EUR/JPY, EUR/AUD, EUR/CAD, EUR/CHF, EUR/NZD |
| **GBP Crosses** | GBP/JPY, GBP/AUD, GBP/CAD, GBP/CHF, GBP/NZD |
| **AUD Crosses** | AUD/JPY, AUD/CAD, AUD/CHF, AUD/NZD |
| **CAD Crosses** | CAD/JPY, CAD/CHF |
| **CHF Crosses** | CHF/JPY |
| **NZD Crosses** | NZD/JPY, NZD/CAD, NZD/CHF |

---

## Directory Structure

```
fx-backtester/
├── backtest/                  # Core simulation and execution logic
│   ├── engine.py              # Next-bar fill simulator with SL/TP/Spread
│   ├── metrics.py             # Quantitative performance calculator
│   └── risk_manager.py        # Position sizing and pip valuation
├── config/                    # Configuration objects & instrument metadata
│   └── strategy_config.py     # StrategyConfig, BacktestConfig, Instrument specs
├── data/                      # Market data pipeline
│   ├── dukascopy_loader.py    # Automated Dukascopy fetcher
│   └── cache/                 # Local historical data cache directory
├── indicators/                # Technical indicator implementations
│   ├── star_pattern.py        # Candlestick geometry & detachment engine
│   ├── rsi.py                 # Wilder RSI & RSI moving average logic
│   ├── rsi_env.py             # RSI(2) exhaustion regime detector
│   └── cmf.py                 # Chaikin Money Flow calculator
├── mql5/                      # Production MetaTrader 5 code
│   └── StarRSI_EURUSD_M5.mq5  # Full MQL5 Expert Advisor with HUD
├── reports/                   # Performance output and research artifacts
│   ├── pair_optimizations/    # Per-pair optimization CSV logs
│   ├── all_28_pairs_best_leaderboard.csv
│   └── research_paper_star_rsi_reversal.md
├── scripts/                   # Utility and multi-pair automation scripts
│   ├── fetch_remaining_4.py   # Data download utility
│   └── optimize_all_28_pairs.py
├── strategy/                  # Strategy definition
│   └── star_rsi_strategy.py   # Signal aggregator and rejection logger
├── tests/                     # Unit test suite
│   ├── test_indicators.py     # Indicator mathematical accuracy tests
│   └── test_strategy.py       # Strategy execution and signal logic tests
├── analyze_batch_leaderboard.py # Batch aggregation and ranking utility
├── backtest_5yr.py            # 5-Year historical validation engine
├── batch_research_engine.py   # 10-Year rolling 180-day research grid
├── main.py                    # Primary CLI runner for backtesting
├── optimize.py                # Vectorized parameter optimization engine
├── pine.pine                  # TradingView Pine Script v6 indicator
├── prefetch_10yr_data.py      # Bulk downloader for historical data
├── requirements.txt           # Python package requirements
└── README.md                  # System documentation
```

---

## Installation & Quickstart

### Prerequisites
- Python 3.10 or higher
- Git

### Setup
```bash
# 1. Clone the repository
git clone https://github.com/Gifted87/fx-backtester.git
cd fx-backtester

# 2. Create and activate a virtual environment
python -m venv venv

# On Windows:
.\venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt
```

---

## CLI Usage Guide

### 1. Single-Pair and Portfolio Backtesting
Run the default backtester across major pairs or specify select instruments, timeframes, and historical windows:

```bash
# Run on all 7 major currency pairs over the last 180 days on 1-hour candles
python main.py --pairs EURUSD GBPUSD USDJPY AUDUSD USDCAD USDCHF NZDUSD --interval 1h --days 180

# Run on EURUSD 5-minute candles with 1:2 Risk-Reward
python main.py --pairs EURUSD --interval 5m --days 90 --risk 1.0 --rr 2.0

# Customize strategy parameters directly
python main.py --pairs EURUSD --interval 1h --rsi_len 14 --rsi_win 1 --enable_sma --sma_len 50
```

### 2. Multi-Year Validation (5-Year Stress Test)
Evaluates top decile configurations over an uninterrupted 5-year sample (2021–2026), generating year-by-year performance tables and drawdown curves:

```bash
python backtest_5yr.py
```

### 3. Batch Research Engine (10-Year Slice Analysis)
Splits long-horizon history into chronological, non-overlapping 180-day batches to discover configurations with stable multi-regime persistence:

```bash
python batch_research_engine.py
```

### 4. Vectorized Parameter Optimization
Performs sensitivity analysis and hyperparameter grid searches across RSI periods, star geometry ratios, stop-loss anchors, and target multipliers:

```bash
python optimize.py --symbol EURUSD --interval 5m --days 180
```

### 5. Batch Leaderboard Aggregation
Aggregates all output batches, calculating pass rates, consistency metrics, and average profit factors to rank optimal global settings:

```bash
python analyze_batch_leaderboard.py
```

---

## MetaTrader 5 & TradingView Integration

### MetaTrader 5 Expert Advisor (`mql5/StarRSI_EURUSD_M5.mq5`)
The repository contains a fully structured MQL5 Expert Advisor matching the Python engine's exact math:
- Copy `mql5/StarRSI_EURUSD_M5.mq5` into your MetaTrader 5 `MQL5/Experts/` folder.
- Compile with MetaEditor 5.
- Features include:
  - Account equity-based fractional position sizing or fixed lots
  - Pattern-extreme and star-candle stop-loss placements
  - Real-time on-chart dashboard HUD showing signal counts and win rates
  - Push notification alerts and terminal audio chimes

### TradingView Pine Script v6 (`pine.pine`)
- Open the Pine Editor in TradingView.
- Paste the complete contents of `pine.pine`.
- Click **Add to Chart**.
- Features include:
  - Visual bounding boxes outlining detected Morning/Evening Star patterns
  - Visual tags for star geometries (Doji, Hammer, Inverted Hammer)
  - Color-coded rejection tooltips detailing why potential patterns were excluded (e.g., `✗ RSI`, `✗ doji`, `✗ 1st/3rd`)

---

## Unit Testing

Run the included automated test suite to verify indicator calculations and strategy signal evaluations:

```bash
python -m unittest discover tests
```

---

## Risk Disclaimer

> **Important Notice:** Foreign exchange and derivative trading involves substantial risk of loss and is not suitable for all investors. The high degree of leverage that is often obtainable in commodity and currency trading can work against you as well as for you. Past performance, whether actual or indicated by simulated historical backtests, is not indicative of future results. No representation is being made that any account will or is likely to achieve profits or losses similar to those discussed in this repository. All code and research materials are provided strictly for educational and informational purposes.

---

## License

This project is open-source software licensed under the [MIT License](LICENSE).
