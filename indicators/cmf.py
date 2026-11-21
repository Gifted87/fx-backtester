"""
Chaikin Money Flow (CMF) Calculation.
Calculates Money Flow Multiplier, Money Flow Volume, and CMF crossover filters.
"""

from typing import Tuple
import numpy as np
import pandas as pd


def calc_cmf(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    volume: pd.Series,
    enabled: bool = True,
    period: int = 20,
    zero_level: float = 0.0,
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """
    Computes:
    - cmf_bull_ok: True if CMF filter allows Bull signal
    - cmf_bear_ok: True if CMF filter allows Bear signal
    - cmf_val: The CMF numerical series
    """
    if not enabled:
        all_true = pd.Series(True, index=close.index)
        all_na = pd.Series(np.nan, index=close.index)
        return all_true, all_true, all_na

    cmf_range = high - low
    # MFM = ((close - low) - (high - close)) / (high - low)
    # If high == low, MFM is 0.0
    mfm = np.where(cmf_range > 0, ((close - low) - (high - close)) / cmf_range, 0.0)
    mfv = mfm * volume.fillna(0.0)

    vol_sum = volume.rolling(period).sum()
    mfv_sum = pd.Series(mfv, index=close.index).rolling(period).sum()

    cmf_val = np.where(vol_sum > 0, mfv_sum / vol_sum, np.nan)
    cmf_series = pd.Series(cmf_val, index=close.index)

    cmf_prev = cmf_series.shift(1)

    cmf_cross_up = (cmf_series.notna()) & (cmf_prev.notna()) & (cmf_prev < zero_level) & (cmf_series >= zero_level)
    cmf_cross_dn = (cmf_series.notna()) & (cmf_prev.notna()) & (cmf_prev > zero_level) & (cmf_series <= zero_level)

    # Pine script:
    # cmfBullOk = not cmfEnabled or na(cmfVal) or cmfVal < cmfZero or cmfCrossUp
    # cmfBearOk = not cmfEnabled or na(cmfVal) or cmfVal > cmfZero or cmfCrossDn
    cmf_bull_ok = cmf_series.isna() | (cmf_series < zero_level) | cmf_cross_up
    cmf_bear_ok = cmf_series.isna() | (cmf_series > zero_level) | cmf_cross_dn

    return cmf_bull_ok, cmf_bear_ok, cmf_series
