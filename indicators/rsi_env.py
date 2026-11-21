"""
RSI(2) Extreme-Frequency Environment Filter.
Tracks rolling count of extreme overbought vs oversold bars to detect regime imbalance.
"""

from typing import Tuple
import numpy as np
import pandas as pd
from indicators.rsi import calc_wilder_rsi


def calc_rsi_environment(
    close: pd.Series,
    enabled: bool = True,
    period: int = 2,
    lookback: int = 30,
    os_level: float = 30.0,
    ob_level: float = 70.0,
    imbalance_mult: float = 1.5,
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """
    Computes:
    - env_bull_ok: True if environment is NOT bearish (or disabled)
    - env_bear_ok: True if environment is NOT bullish (or disabled)
    - env_state: Series with 'Bullish', 'Bearish', or 'Neutral'
    """
    if not enabled:
        all_true = pd.Series(True, index=close.index)
        neutral = pd.Series("Neutral", index=close.index)
        return all_true, all_true, neutral

    env_rsi = calc_wilder_rsi(close, period=period)

    # Flag bars: RSI < 30 (Bearish frequency indicator) and RSI > 70 (Bullish frequency indicator)
    bear_flag = (env_rsi < os_level).astype(float)
    bull_flag = (env_rsi > ob_level).astype(float)

    # Rolling sums over lookback window
    bear_count = bear_flag.rolling(lookback).sum()
    bull_count = bull_flag.rolling(lookback).sum()

    # Imbalance conditions
    is_bearish = (bear_count > bull_count * imbalance_mult) & bear_count.notna()
    is_bullish = (bull_count > bear_count * imbalance_mult) & bull_count.notna()

    # Pipeline filters:
    # bullSignal requires not envBearish
    # bearSignal requires not envBullish
    env_bull_ok = ~is_bearish
    env_bear_ok = ~is_bullish

    env_state = pd.Series("Neutral", index=close.index)
    env_state[is_bearish] = "Bearish"
    env_state[is_bullish] = "Bullish"

    return env_bull_ok, env_bear_ok, env_state
