"""
Star + RSI Reversal Strategy Module.
Executes the full indicator calculation and signal generation pipeline matching pine.pine.
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any
import numpy as np
import pandas as pd

from config.strategy_config import StrategyConfig
from indicators.rsi import calc_wilder_rsi, calc_rsi_ma, evaluate_rsi_signals
from indicators.rsi_env import calc_rsi_environment
from indicators.cmf import calc_cmf
from indicators.star_pattern import detect_star_patterns, StarPatternResult


@dataclass
class StrategyOutput:
    df: pd.DataFrame
    bull_signals: pd.Series
    bear_signals: pd.Series
    strong_signals: pd.Series
    pattern_results: StarPatternResult
    rejection_reasons: pd.Series


class StarRsiStrategy:
    """
    Morning / Evening Star + RSI Reversal Strategy.
    """
    def __init__(self, config: Optional[StrategyConfig] = None):
        self.cfg = config or StrategyConfig()

    def generate_signals(self, df: pd.DataFrame) -> StrategyOutput:
        """
        Runs the complete signal evaluation on an OHLCV DataFrame.
        Returns StrategyOutput containing signals and intermediate calculations.
        """
        data = df.copy()

        # 1. Candlestick Star Pattern Engine
        patterns = detect_star_patterns(data, self.cfg)

        # 2. RSI & RSI MA Engine
        rsi_series = calc_wilder_rsi(data[self.cfg.rsi_src], period=self.cfg.rsi_len)
        rsi_ma_series = calc_rsi_ma(
            rsi_series,
            ma_len=self.cfg.rsi_ma_len,
            ma_type=self.cfg.rsi_ma_type,
        )
        bull_rsi_ok, bear_rsi_ok = evaluate_rsi_signals(
            rsi=rsi_series,
            rsi_ma=rsi_ma_series,
            rsi_enabled=self.cfg.rsi_enabled,
            rsi_os=self.cfg.rsi_os,
            rsi_ob=self.cfg.rsi_ob,
            rsi_win=self.cfg.rsi_win,
            rsi_ma_enabled=self.cfg.rsi_ma_enabled,
        )

        # 3. SMA Trend Filter
        if self.cfg.sma_enabled:
            sma_val = data[self.cfg.sma_src].rolling(self.cfg.sma_len).mean()
            if self.cfg.sma_mode == "With trend":
                sma_bull_ok = data['close'] > sma_val
                sma_bear_ok = data['close'] < sma_val
            else:  # Reversion
                sma_bull_ok = data['close'] < sma_val
                sma_bear_ok = data['close'] > sma_val
        else:
            sma_bull_ok = pd.Series(True, index=data.index)
            sma_bear_ok = pd.Series(True, index=data.index)

        # 4. RSI(2) Extreme-Frequency Environment Filter
        env_bull_ok, env_bear_ok, env_state = calc_rsi_environment(
            close=data['close'],
            enabled=self.cfg.env_enabled,
            period=self.cfg.env_len,
            lookback=self.cfg.env_lookback,
            os_level=self.cfg.env_os,
            ob_level=self.cfg.env_ob,
            imbalance_mult=self.cfg.env_imb,
        )

        # 5. Chaikin Money Flow (CMF) Filter
        if 'volume' in data.columns:
            vol = data['volume']
        else:
            vol = pd.Series(0.0, index=data.index)

        cmf_bull_ok, cmf_bear_ok, cmf_val = calc_cmf(
            high=data['high'],
            low=data['low'],
            close=data['close'],
            volume=vol,
            enabled=self.cfg.cmf_enabled,
            period=self.cfg.cmf_len,
            zero_level=self.cfg.cmf_zero,
        )

        # ── Signal Combinations (Exact pine.pine rules) ──
        # bool bullSignal = morningStar and dojiOk and factorGateOk and firstLegBig and bullRsiOk and smaBullOk and envBullOk and cmfBullOk
        bull_signal = (
            patterns.morning_star &
            patterns.doji_ok &
            patterns.factor_gate_ok &
            patterns.first_leg_big &
            bull_rsi_ok &
            sma_bull_ok &
            env_bull_ok &
            cmf_bull_ok
        )

        # bool bearSignal = eveningStar and dojiOk and factorGateOk and firstLegBig and bearRsiOk and smaBearOk and envBearOk and cmfBearOk
        bear_signal = (
            patterns.evening_star &
            patterns.doji_ok &
            patterns.factor_gate_ok &
            patterns.first_leg_big &
            bear_rsi_ok &
            sma_bear_ok &
            env_bear_ok &
            cmf_bear_ok
        )

        # Strong signal indicator (bodyRatio >= strongThresh)
        strong_signal = (bull_signal | bear_signal) & (patterns.body_ratio >= self.cfg.strong_thresh)

        # Debug rejection tracking
        rejections = self._evaluate_rejections(
            patterns,
            bull_rsi_ok, bear_rsi_ok,
            sma_bull_ok, sma_bear_ok,
            env_bull_ok, env_bear_ok,
            cmf_bull_ok, cmf_bear_ok,
            bull_signal, bear_signal,
        )

        # 6. Average True Range (ATR) for volatility-adjusted trade management
        tr0 = data['high'] - data['low']
        tr1 = (data['high'] - data['close'].shift(1)).abs()
        tr2 = (data['low'] - data['close'].shift(1)).abs()
        tr = pd.concat([tr0, tr1, tr2], axis=1).max(axis=1)
        atr = tr.rolling(14).mean()

        # Attach intermediate metrics to dataframe
        data['rsi'] = rsi_series
        data['rsi_ma'] = rsi_ma_series
        data['cmf'] = cmf_val
        data['env_state'] = env_state
        data['atr'] = atr
        data['body_ratio'] = patterns.body_ratio
        data['star_body_pct'] = patterns.star_body_pct
        data['star_shape'] = patterns.star_shape
        data['pattern_low'] = patterns.pattern_low
        data['pattern_high'] = patterns.pattern_high
        data['bull_signal'] = bull_signal
        data['bear_signal'] = bear_signal
        data['strong_signal'] = strong_signal

        return StrategyOutput(
            df=data,
            bull_signals=bull_signal,
            bear_signals=bear_signal,
            strong_signals=strong_signal,
            pattern_results=patterns,
            rejection_reasons=rejections,
        )

    def _evaluate_rejections(
        self,
        patterns: StarPatternResult,
        bull_rsi_ok: pd.Series, bear_rsi_ok: pd.Series,
        sma_bull_ok: pd.Series, sma_bear_ok: pd.Series,
        env_bull_ok: pd.Series, env_bear_ok: pd.Series,
        cmf_bull_ok: pd.Series, cmf_bear_ok: pd.Series,
        bull_signal: pd.Series, bear_signal: pd.Series,
    ) -> pd.Series:
        """
        Diagnoses reasons why candidate morning or evening stars were filtered out.
        """
        rejection_txt = pd.Series("", index=bull_signal.index)
        candidate_star = (patterns.morning_star | patterns.evening_star) & ~(bull_signal | bear_signal)

        for idx in candidate_star[candidate_star].index:
            reasons = []
            is_bull = patterns.morning_star.loc[idx]

            if not patterns.doji_ok.loc[idx]:
                reasons.append("✗ doji")
            if not patterns.factor_gate_ok.loc[idx]:
                reasons.append("✗ factor")
            if not patterns.first_leg_big.loc[idx]:
                reasons.append("✗ 1st/3rd")

            rsi_ok = bull_rsi_ok.loc[idx] if is_bull else bear_rsi_ok.loc[idx]
            if self.cfg.rsi_enabled and not rsi_ok:
                reasons.append("✗ RSI")

            sma_ok = sma_bull_ok.loc[idx] if is_bull else sma_bear_ok.loc[idx]
            if self.cfg.sma_enabled and not sma_ok:
                reasons.append("✗ trend")

            env_ok = env_bull_ok.loc[idx] if is_bull else env_bear_ok.loc[idx]
            if self.cfg.env_enabled and not env_ok:
                reasons.append("✗ RSI(2)")

            cmf_ok = cmf_bull_ok.loc[idx] if is_bull else cmf_bear_ok.loc[idx]
            if self.cfg.cmf_enabled and not cmf_ok:
                reasons.append("✗ CMF")

            rejection_txt.loc[idx] = " · ".join(reasons) if reasons else "✗ other"

        return rejection_txt
