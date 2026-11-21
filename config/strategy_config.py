"""
Strategy and Backtester Configuration Module.
Encapsulates all configurable parameters with exact defaults from pine.pine.
"""

from dataclasses import dataclass, field
from typing import Dict, Literal, Optional


@dataclass
class StrategyConfig:
    # ── Group 1: RSI Reversal — Signal Engine ──
    rsi_enabled: bool = True
    rsi_len: int = 7                    # Main RSI length (default: 7)
    rsi_src: str = "close"
    rsi_os: float = 30.0
    rsi_ob: float = 70.0
    rsi_win: int = 0                    # Cross window in bars (0 = exact bar)
    rsi_ma_enabled: bool = True
    rsi_ma_len: int = 14
    rsi_ma_type: Literal["SMA", "EMA", "WMA"] = "SMA"

    # ── Group 2: Star Pattern Quality ──
    star_body_factor: float = 0.35      # Star body factor (x neighbour: body1 & body3)
    star_range_factor: float = 0.40     # Star body / own range
    third_body_factor: float = 0.70     # Confirmation body factor (x first leg)
    first_vs_third: float = 0.65        # First-leg body >= third body x
    star_penetration: float = 0.50      # Penetration into first-leg body (0.5 = 50%)
    star_detach: bool = True            # Require soft detachment (gap substitute)
    min_body_pct: float = 10.0          # Doji guard: first-leg body %
    strong_thresh: float = 2.0          # Strong signal threshold (body3 / body1 >= 2.0)
    star_color_enabled: bool = True     # Require star & 3rd candle same colour
    star_color_pct: float = 10.0        # Star colour-ambiguous body % threshold (doji waiver)

    # ── Group 3: SMA Trend Context (optional) ──
    sma_enabled: bool = False
    sma_len: int = 50
    sma_src: str = "close"
    sma_mode: Literal["With trend", "Reversion"] = "With trend"

    # ── Group 4: RSI(2) Extreme-Frequency Environment ──
    env_enabled: bool = False           # 2-period RSI environment filter (default: disabled)
    env_len: int = 2
    env_lookback: int = 30
    env_os: float = 30.0
    env_ob: float = 70.0
    env_imb: float = 1.5                # Imbalance threshold (x)

    # ── Group 5: Chaikin Money Flow ──
    cmf_enabled: bool = False           # CMF filter (default: disabled)
    cmf_len: int = 20
    cmf_zero: float = 0.0


@dataclass
class InstrumentSpec:
    symbol: str                         # Standard name e.g. "EURUSD"
    dukascopy_symbol: str               # Dukascopy instrument constant
    pip_size: float                     # 0.0001 or 0.01
    default_spread_pips: float          # In pips (e.g. 0.8)
    base_currency: str
    quote_currency: str


# 7 Major Forex Pairs
MAJOR_FX_PAIRS: Dict[str, InstrumentSpec] = {
    "EURUSD": InstrumentSpec("EURUSD", "INSTRUMENT_FX_MAJORS_EUR_USD", 0.0001, 0.8, "EUR", "USD"),
    "GBPUSD": InstrumentSpec("GBPUSD", "INSTRUMENT_FX_MAJORS_GBP_USD", 0.0001, 1.2, "GBP", "USD"),
    "USDJPY": InstrumentSpec("USDJPY", "INSTRUMENT_FX_MAJORS_USD_JPY", 0.01,   0.9, "USD", "JPY"),
    "AUDUSD": InstrumentSpec("AUDUSD", "INSTRUMENT_FX_MAJORS_AUD_USD", 0.0001, 1.0, "AUD", "USD"),
    "USDCAD": InstrumentSpec("USDCAD", "INSTRUMENT_FX_MAJORS_USD_CAD", 0.0001, 1.3, "USD", "CAD"),
    "USDCHF": InstrumentSpec("USDCHF", "INSTRUMENT_FX_MAJORS_USD_CHF", 0.0001, 1.2, "USD", "CHF"),
    "NZDUSD": InstrumentSpec("NZDUSD", "INSTRUMENT_FX_MAJORS_NZD_USD", 0.0001, 1.5, "NZD", "USD"),
}

# 21 Minor / Cross Forex Pairs
MINOR_FX_PAIRS: Dict[str, InstrumentSpec] = {
    # EUR Crosses
    "EURGBP": InstrumentSpec("EURGBP", "INSTRUMENT_FX_CROSSES_EUR_GBP", 0.0001, 1.0, "EUR", "GBP"),
    "EURJPY": InstrumentSpec("EURJPY", "INSTRUMENT_FX_CROSSES_EUR_JPY", 0.01,   1.2, "EUR", "JPY"),
    "EURAUD": InstrumentSpec("EURAUD", "INSTRUMENT_FX_CROSSES_EUR_AUD", 0.0001, 1.5, "EUR", "AUD"),
    "EURCAD": InstrumentSpec("EURCAD", "INSTRUMENT_FX_CROSSES_EUR_CAD", 0.0001, 1.5, "EUR", "CAD"),
    "EURCHF": InstrumentSpec("EURCHF", "INSTRUMENT_FX_CROSSES_EUR_CHF", 0.0001, 1.3, "EUR", "CHF"),
    "EURNZD": InstrumentSpec("EURNZD", "INSTRUMENT_FX_CROSSES_EUR_NZD", 0.0001, 1.8, "EUR", "NZD"),
    # GBP Crosses
    "GBPJPY": InstrumentSpec("GBPJPY", "INSTRUMENT_FX_CROSSES_GBP_JPY", 0.01,   1.6, "GBP", "JPY"),
    "GBPAUD": InstrumentSpec("GBPAUD", "INSTRUMENT_FX_CROSSES_GBP_AUD", 0.0001, 1.8, "GBP", "AUD"),
    "GBPCAD": InstrumentSpec("GBPCAD", "INSTRUMENT_FX_CROSSES_GBP_CAD", 0.0001, 1.8, "GBP", "CAD"),
    "GBPCHF": InstrumentSpec("GBPCHF", "INSTRUMENT_FX_CROSSES_GBP_CHF", 0.0001, 1.6, "GBP", "CHF"),
    "GBPNZD": InstrumentSpec("GBPNZD", "INSTRUMENT_FX_CROSSES_GBP_NZD", 0.0001, 2.0, "GBP", "NZD"),
    # AUD Crosses
    "AUDJPY": InstrumentSpec("AUDJPY", "INSTRUMENT_FX_CROSSES_AUD_JPY", 0.01,   1.3, "AUD", "JPY"),
    "AUDCAD": InstrumentSpec("AUDCAD", "INSTRUMENT_FX_CROSSES_AUD_CAD", 0.0001, 1.4, "AUD", "CAD"),
    "AUDCHF": InstrumentSpec("AUDCHF", "INSTRUMENT_FX_CROSSES_AUD_CHF", 0.0001, 1.4, "AUD", "CHF"),
    "AUDNZD": InstrumentSpec("AUDNZD", "INSTRUMENT_FX_CROSSES_AUD_NZD", 0.0001, 1.6, "AUD", "NZD"),
    # CAD Crosses
    "CADJPY": InstrumentSpec("CADJPY", "INSTRUMENT_FX_CROSSES_CAD_JPY", 0.01,   1.4, "CAD", "JPY"),
    "CADCHF": InstrumentSpec("CADCHF", "INSTRUMENT_FX_CROSSES_CAD_CHF", 0.0001, 1.5, "CAD", "CHF"),
    # CHF Crosses
    "CHFJPY": InstrumentSpec("CHFJPY", "INSTRUMENT_FX_CROSSES_CHF_JPY", 0.01,   1.5, "CHF", "JPY"),
    # NZD Crosses
    "NZDJPY": InstrumentSpec("NZDJPY", "INSTRUMENT_FX_CROSSES_NZD_JPY", 0.01,   1.5, "NZD", "JPY"),
    "NZDCAD": InstrumentSpec("NZDCAD", "INSTRUMENT_FX_CROSSES_NZD_CAD", 0.0001, 1.6, "NZD", "CAD"),
    "NZDCHF": InstrumentSpec("NZDCHF", "INSTRUMENT_FX_CROSSES_NZD_CHF", 0.0001, 1.6, "NZD", "CHF"),
}

# All 28 Standard Forex Pairs
ALL_FX_PAIRS: Dict[str, InstrumentSpec] = {**MAJOR_FX_PAIRS, **MINOR_FX_PAIRS}


@dataclass
class BacktestConfig:
    initial_capital: float = 10000.0     # Account balance in base USD
    risk_pct_per_trade: float = 1.0      # 1.0% equity risk per trade
    max_open_trades_per_pair: int = 1   # Max concurrent positions per pair
    max_total_open_trades: int = 5      # Max concurrent portfolio positions

    # Stop Loss & Take Profit
    sl_mode: Literal["pattern_extreme", "atr"] = "pattern_extreme"
    sl_buffer_pips: float = 0.0         # Exactly at pattern low / high (0 buffer)
    atr_period: int = 14
    atr_multiplier_sl: float = 1.5

    # Take profit ratio
    tp_mode: Literal["risk_reward", "opposite_signal", "trailing"] = "risk_reward"
    risk_reward_ratio: float = 2.0      # TP is 2x the SL (1:2 R:R)
    
    # Trailing Stop options
    trail_after_r: float = 0.0          # 0.0 = disabled (no trailing stop)
    
    # Costs (zero friction as requested)
    include_spread: bool = False
    slippage_pips: float = 0.0
    commission_per_lot: float = 0.0
