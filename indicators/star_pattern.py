"""
Morning / Evening Star Candlestick Recognition Engine.
Replicates the exact candle geometry, detachment, penetration, and color rules of pine.pine.
"""

from dataclasses import dataclass
from typing import Tuple
import numpy as np
import pandas as pd
from config.strategy_config import StrategyConfig


@dataclass
class StarPatternResult:
    morning_star: pd.Series
    evening_star: pd.Series
    doji_ok: pd.Series
    factor_gate_ok: pd.Series
    first_leg_big: pd.Series
    body_ratio: pd.Series
    star_body_pct: pd.Series
    star_shape: pd.Series
    pattern_low: pd.Series
    pattern_high: pd.Series


def detect_star_patterns(df: pd.DataFrame, cfg: StrategyConfig) -> StarPatternResult:
    """
    Scans OHLC dataframe and computes Morning Star and Evening Star pattern criteria.
    df must contain ['open', 'high', 'low', 'close']
    Index 0 is current confirmation candle, shift(1) is star, shift(2) is first leg.
    """
    c0 = df['close']
    o0 = df['open']
    h0 = df['high']
    l0 = df['low']

    c1 = df['close'].shift(1)
    o1 = df['open'].shift(1)
    h1 = df['high'].shift(1)
    l1 = df['low'].shift(1)

    c2 = df['close'].shift(2)
    o2 = df['open'].shift(2)
    h2 = df['high'].shift(2)
    l2 = df['low'].shift(2)

    # ── Geometry ──
    # [2] = first leg
    body1 = (c2 - o2).abs()
    range1 = h2 - l2
    body1_pct = pd.Series(np.where(range1 > 0, (body1 / range1) * 100.0, 0.0), index=df.index)

    # [1] = star (middle)
    body2 = (c1 - o1).abs()
    range2 = h1 - l1
    star_body_pct = pd.Series(np.where(range2 > 0, (body2 / range2) * 100.0, np.nan), index=df.index)

    # [0] = confirmation candle
    body3 = (c0 - o0).abs()
    body_ratio = pd.Series(np.where(body1 > 0, body3 / body1, np.nan), index=df.index)

    # Star wicks
    star_max_oc = np.maximum(o1, c1)
    star_min_oc = np.minimum(o1, c1)
    star_upper_wick = h1 - star_max_oc
    star_lower_wick = star_min_oc - l1

    # ── Directional components ──
    first_bear = c2 < o2
    first_bull = c2 > o2
    third_bull = c0 > o0
    third_bear = c0 < o0

    # ── Middle candle smallness ──
    middle_small = (
        (body2 <= body1 * cfg.star_body_factor) &
        (body2 <= body3 * cfg.star_body_factor) &
        (body2 <= range2 * cfg.star_range_factor)
    )

    # ── Body size relationships ──
    third_real = body3 >= body1 * cfg.third_body_factor
    first_leg_big = body1 >= body3 * cfg.first_vs_third

    # ── Penetration levels ──
    pen_bull_level = np.maximum(o2, c2) - body1 * cfg.star_penetration
    pen_bear_level = np.minimum(o2, c2) + body1 * cfg.star_penetration
    penetrate_bull = third_bull & (c0 > pen_bull_level)
    penetrate_bear = third_bear & (c0 < pen_bear_level)

    # ── Soft Detachment ──
    if not cfg.star_detach:
        detach_bull = pd.Series(True, index=df.index)
        detach_bear = pd.Series(True, index=df.index)
    else:
        detach_bull = np.minimum(o1, c1) >= np.minimum(o2, c2)
        detach_bear = np.maximum(o1, c1) <= np.maximum(o2, c2)

    # ── Star colour vs confirmation candle ──
    star_bull = c1 > o1
    star_bear = c1 < o1
    star_ambiguous = np.isnan(star_body_pct) | (star_body_pct < cfg.star_color_pct)

    if not cfg.star_color_enabled:
        star_color_bull = pd.Series(True, index=df.index)
        star_color_bear = pd.Series(True, index=df.index)
    else:
        star_color_bull = star_ambiguous | star_bull
        star_color_bear = star_ambiguous | star_bear

    # ── Candidate Star Patterns ──
    morning_star = (
        first_bear &
        third_bull &
        middle_small &
        third_real &
        first_leg_big &
        star_color_bull &
        penetrate_bull &
        detach_bull
    )

    evening_star = (
        first_bull &
        third_bear &
        middle_small &
        third_real &
        first_leg_big &
        star_color_bear &
        penetrate_bear &
        detach_bear
    )

    # ── Doji guard & factor gate ──
    doji_ok = body1_pct >= cfg.min_body_pct
    factor_gate_ok = pd.Series(body_ratio).notna() & (body3 >= body1 * cfg.third_body_factor)

    # ── Pattern Shapes ──
    is_doji_shape = star_body_pct < 10.0
    is_hammer = (star_lower_wick > body2 * 2.0) & (star_upper_wick < body2)
    is_inv_hammer = (star_upper_wick > body2 * 2.0) & (star_lower_wick < body2)

    star_shape = np.where(
        is_doji_shape, "doji",
        np.where(is_hammer, "hammer",
                 np.where(is_inv_hammer, "inv. hammer", "pin bar"))
    )

    # Pattern extreme high and low (over all 3 candles)
    pattern_low = pd.concat([l0, l1, l2], axis=1).min(axis=1)
    pattern_high = pd.concat([h0, h1, h2], axis=1).max(axis=1)

    return StarPatternResult(
        morning_star=pd.Series(morning_star, index=df.index).fillna(False),
        evening_star=pd.Series(evening_star, index=df.index).fillna(False),
        doji_ok=pd.Series(doji_ok, index=df.index).fillna(False),
        factor_gate_ok=pd.Series(factor_gate_ok, index=df.index).fillna(False),
        first_leg_big=pd.Series(first_leg_big, index=df.index).fillna(False),
        body_ratio=pd.Series(body_ratio, index=df.index),
        star_body_pct=pd.Series(star_body_pct, index=df.index),
        star_shape=pd.Series(star_shape, index=df.index),
        pattern_low=pattern_low,
        pattern_high=pattern_high,
    )
