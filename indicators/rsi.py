"""
RSI and RSI Moving Average Calculations.
Matches TradingView's ta.rsi (Wilder's RSI), ta.sma/ema/wma, and cross-tracking logic.
"""

from typing import Literal, Tuple
import numpy as np
import pandas as pd


def calc_wilder_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """
    Computes Wilder's RSI, identical to Pine Script's ta.rsi().
    Uses exponential moving average with alpha = 1 / period.
    """
    delta = series.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)

    # Wilder's smoothing is equivalent to ewm(alpha=1/period, adjust=False)
    # after initializing with the simple mean of the first `period` bars
    n = len(series)
    avg_gain = np.full(n, np.nan, dtype=float)
    avg_loss = np.full(n, np.nan, dtype=float)

    if n < period + 1:
        return pd.Series(np.nan, index=series.index)

    # Initial SMA
    gain_vals = gain.values
    loss_vals = loss.values
    
    first_gain_sum = np.sum(gain_vals[1:period + 1])
    first_loss_sum = np.sum(loss_vals[1:period + 1])
    
    avg_gain[period] = first_gain_sum / period
    avg_loss[period] = first_loss_sum / period

    for i in range(period + 1, n):
        avg_gain[i] = (avg_gain[i - 1] * (period - 1) + gain_vals[i]) / period
        avg_loss[i] = (avg_loss[i - 1] * (period - 1) + loss_vals[i]) / period

    rsi = np.full(n, np.nan, dtype=float)
    for i in range(period, n):
        gl = avg_gain[i]
        ls = avg_loss[i]
        if np.isnan(gl) or np.isnan(ls):
            continue
        if ls == 0:
            rsi[i] = 100.0 if gl > 0 else 50.0
        elif gl == 0:
            rsi[i] = 0.0
        else:
            rs = gl / ls
            rsi[i] = 100.0 - (100.0 / (1.0 + rs))

    return pd.Series(rsi, index=series.index)


def calc_wma(series: pd.Series, period: int) -> pd.Series:
    """Computes Linear Weighted Moving Average."""
    weights = np.arange(1, period + 1)
    w_sum = weights.sum()

    def _wma(window):
        return np.dot(window, weights) / w_sum

    return series.rolling(period).apply(_wma, raw=True)


def calc_rsi_ma(
    rsi_series: pd.Series,
    ma_len: int = 14,
    ma_type: Literal["SMA", "EMA", "WMA"] = "SMA",
) -> pd.Series:
    """Computes moving average over the RSI series."""
    if ma_type == "EMA":
        return rsi_series.ewm(span=ma_len, adjust=False).mean()
    elif ma_type == "WMA":
        return calc_wma(rsi_series, ma_len)
    else:  # SMA default
        return rsi_series.rolling(ma_len).mean()


def evaluate_rsi_signals(
    rsi: pd.Series,
    rsi_ma: pd.Series,
    rsi_enabled: bool = True,
    rsi_os: float = 30.0,
    rsi_ob: float = 70.0,
    rsi_win: int = 0,
    rsi_ma_enabled: bool = True,
) -> Tuple[pd.Series, pd.Series]:
    """
    Evaluates bull_rsi_ok and bear_rsi_ok based on Pine Script logic:
    - CrossUp: rsi[1] < rsiOs and rsi >= rsiOs
    - CrossDn: rsi[1] > rsiOb and rsi <= rsiOb
    - Tracks lastCrossDir (1 or -1) and lastCrossBar
    - If crossAge <= rsiWin: armed
    - If rsiMaEnabled: Bull requires rsi >= rsiMa, Bear requires rsi <= rsiMa
    """
    n = len(rsi)
    bull_rsi_ok = np.zeros(n, dtype=bool)
    bear_rsi_ok = np.zeros(n, dtype=bool)

    if not rsi_enabled:
        return pd.Series(True, index=rsi.index), pd.Series(True, index=rsi.index)

    rsi_vals = rsi.values
    rsi_ma_vals = rsi_ma.values

    last_cross_dir = 0
    last_cross_bar = -999999

    for i in range(1, n):
        r_curr = rsi_vals[i]
        r_prev = rsi_vals[i - 1]

        if not np.isnan(r_curr) and not np.isnan(r_prev):
            # rsiCrossUp: rsi[1] < rsiOs and rsi >= rsiOs
            if r_prev < rsi_os and r_curr >= rsi_os:
                last_cross_dir = 1
                last_cross_bar = i
            # rsiCrossDn: rsi[1] > rsiOb and rsi <= rsiOb
            elif r_prev > rsi_ob and r_curr <= rsi_ob:
                last_cross_dir = -1
                last_cross_bar = i

        cross_age = i - last_cross_bar

        # Check MA filter
        ma_val = rsi_ma_vals[i]
        if not rsi_ma_enabled:
            rsi_ma_bull_ok = True
            rsi_ma_bear_ok = True
        else:
            rsi_ma_bull_ok = not np.isnan(ma_val) and (r_curr >= ma_val)
            rsi_ma_bear_ok = not np.isnan(ma_val) and (r_curr <= ma_val)

        # Bull RSI OK
        if (last_cross_dir == 1) and (cross_age <= rsi_win) and rsi_ma_bull_ok:
            bull_rsi_ok[i] = True

        # Bear RSI OK
        if (last_cross_dir == -1) and (cross_age <= rsi_win) and rsi_ma_bear_ok:
            bear_rsi_ok[i] = True

    return pd.Series(bull_rsi_ok, index=rsi.index), pd.Series(bear_rsi_ok, index=rsi.index)
