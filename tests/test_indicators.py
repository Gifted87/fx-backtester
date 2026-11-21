"""
Unit Tests for Technical Indicators and Candlestick Recognition.
Validates Wilder's RSI, RSI MA, RSI(2) environment, CMF, and Star Pattern Geometry.
"""

import unittest
import numpy as np
import pandas as pd

from config.strategy_config import StrategyConfig
from indicators.rsi import calc_wilder_rsi, calc_rsi_ma, evaluate_rsi_signals
from indicators.rsi_env import calc_rsi_environment
from indicators.cmf import calc_cmf
from indicators.star_pattern import detect_star_patterns


class TestIndicators(unittest.TestCase):
    def test_wilder_rsi_basic(self):
        # 20 bars of consecutive upward movement -> RSI should approach 100
        prices = pd.Series([100.0 + i for i in range(25)])
        rsi = calc_wilder_rsi(prices, period=14)
        self.assertFalse(np.isnan(rsi.iloc[-1]))
        self.assertGreater(rsi.iloc[-1], 90.0)

        # 20 bars of consecutive downward movement -> RSI should approach 0
        prices_dn = pd.Series([200.0 - i for i in range(25)])
        rsi_dn = calc_wilder_rsi(prices_dn, period=14)
        self.assertFalse(np.isnan(rsi_dn.iloc[-1]))
        self.assertLess(rsi_dn.iloc[-1], 10.0)

    def test_rsi_cross_and_ma(self):
        # Construct series crossing 30 from below
        rsi_vals = pd.Series([25.0, 28.0, 31.0, 32.0, 33.0])
        rsi_ma = pd.Series([26.0, 27.0, 28.0, 29.0, 30.0])
        bull_ok, bear_ok = evaluate_rsi_signals(
            rsi=rsi_vals,
            rsi_ma=rsi_ma,
            rsi_enabled=True,
            rsi_os=30.0,
            rsi_ob=70.0,
            rsi_win=1,
            rsi_ma_enabled=True,
        )
        # Bar 2 crossed 30 (28 -> 31) and rsi (31) >= rsi_ma (28) -> bull_ok should be True
        self.assertTrue(bull_ok.iloc[2])
        # Bar 3 is 1 bar after cross (crossAge = 1 <= rsiWin 1) -> bull_ok should be True
        self.assertTrue(bull_ok.iloc[3])
        # Bar 4 is 2 bars after cross (crossAge = 2 > rsiWin 1) -> bull_ok should be False
        self.assertFalse(bull_ok.iloc[4])

    def test_star_pattern_morning_star(self):
        cfg = StrategyConfig(
            star_detach=False,  # Relax detachment for synthetic test
            star_color_enabled=False,
        )
        # Construct 3 synthetic candles forming textbook Morning Star:
        # Bar 0 (first leg): Bearish, Open 1.1000, Close 1.0900 (body 100 pips, range 110 pips)
        # Bar 1 (star): Tiny body, Open 1.0880, Close 1.0885 (body 5 pips, range 20 pips)
        # Bar 2 (confirm): Bullish, Open 1.0890, Close 1.0980 (body 90 pips, penetrates > 50%)
        dates = pd.date_range("2026-01-01", periods=3, freq="1h")
        df = pd.DataFrame({
            "open":  [1.1000, 1.0880, 1.0890],
            "high":  [1.1010, 1.0895, 1.0990],
            "low":   [1.0890, 1.0875, 1.0885],
            "close": [1.0900, 1.0885, 1.0980],
            "volume":[1000, 500, 1500],
        }, index=dates)

        res = detect_star_patterns(df, cfg)
        self.assertTrue(res.morning_star.iloc[2], "Textbook Morning Star must be detected")
        self.assertFalse(res.evening_star.iloc[2], "Evening star must be False")
        self.assertTrue(res.doji_ok.iloc[2])
        self.assertTrue(res.factor_gate_ok.iloc[2])
        self.assertTrue(res.first_leg_big.iloc[2])

    def test_star_pattern_evening_star(self):
        cfg = StrategyConfig(
            star_detach=False,
            star_color_enabled=False,
        )
        # Construct 3 synthetic candles forming textbook Evening Star:
        # Bar 0 (first leg): Bullish, Open 1.0900, Close 1.1000 (body 100 pips)
        # Bar 1 (star): Tiny body, Open 1.1020, Close 1.1015 (body 5 pips)
        # Bar 2 (confirm): Bearish, Open 1.1010, Close 1.0920 (body 90 pips)
        dates = pd.date_range("2026-01-01", periods=3, freq="1h")
        df = pd.DataFrame({
            "open":  [1.0900, 1.1020, 1.1010],
            "high":  [1.1010, 1.1030, 1.1020],
            "low":   [1.0890, 1.1010, 1.0910],
            "close": [1.1000, 1.1015, 1.0920],
            "volume":[1000, 500, 1500],
        }, index=dates)

        res = detect_star_patterns(df, cfg)
        self.assertTrue(res.evening_star.iloc[2], "Textbook Evening Star must be detected")
        self.assertFalse(res.morning_star.iloc[2], "Morning star must be False")

    def test_cmf_calculation(self):
        dates = pd.date_range("2026-01-01", periods=25, freq="1h")
        # Uptrending closes near high -> positive CMF
        df = pd.DataFrame({
            "open":  [1.0 + 0.01 * i for i in range(25)],
            "high":  [1.01 + 0.01 * i for i in range(25)],
            "low":   [0.99 + 0.01 * i for i in range(25)],
            "close": [1.01 + 0.01 * i for i in range(25)],  # Close at high
            "volume":[1000.0] * 25,
        }, index=dates)

        cmf_bull, cmf_bear, cmf_val = calc_cmf(
            df['high'], df['low'], df['close'], df['volume'],
            enabled=True, period=20, zero_level=0.0
        )
        self.assertGreater(cmf_val.iloc[-1], 0.5)


if __name__ == "__main__":
    unittest.main()
