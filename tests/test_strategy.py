"""
Unit Tests for Strategy Pipeline and Backtest Execution Engine.
"""

import unittest
import numpy as np
import pandas as pd

from config.strategy_config import StrategyConfig, BacktestConfig, MAJOR_FX_PAIRS
from strategy.star_rsi_strategy import StarRsiStrategy
from backtest.engine import BacktestEngine
from backtest.risk_manager import RiskManager


class TestStrategyAndEngine(unittest.TestCase):
    def setUp(self):
        # Create a 50-bar synthetic dataset with realistic movement
        np.random.seed(42)
        dates = pd.date_range("2026-01-01", periods=60, freq="1h")
        base = 1.1000
        returns = np.random.normal(0, 0.001, 60)
        closes = base * np.cumprod(1 + returns)
        opens = closes + np.random.normal(0, 0.0005, 60)
        highs = np.maximum(opens, closes) + abs(np.random.normal(0, 0.0005, 60))
        lows = np.minimum(opens, closes) - abs(np.random.normal(0, 0.0005, 60))
        vols = np.random.uniform(500, 5000, 60)

        self.df = pd.DataFrame({
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": vols,
        }, index=dates)

    def test_strategy_execution_pipeline(self):
        cfg = StrategyConfig()
        strat = StarRsiStrategy(cfg)
        output = strat.generate_signals(self.df)

        self.assertEqual(len(output.bull_signals), len(self.df))
        self.assertEqual(len(output.bear_signals), len(self.df))
        self.assertIn("rsi", output.df.columns)
        self.assertIn("rsi_ma", output.df.columns)
        self.assertIn("cmf", output.df.columns)
        self.assertIn("env_state", output.df.columns)

    def test_risk_manager_pip_value(self):
        bt_cfg = BacktestConfig()
        eurusd_spec = MAJOR_FX_PAIRS["EURUSD"]
        usdjpy_spec = MAJOR_FX_PAIRS["USDJPY"]

        rm_eur = RiskManager(bt_cfg, eurusd_spec)
        rm_jpy = RiskManager(bt_cfg, usdjpy_spec)

        # EURUSD: 1 pip on 100k standard lot = $10.00
        pip_val_eur = rm_eur.calculate_pip_value(1.1000)
        self.assertAlmostEqual(pip_val_eur, 10.0, places=4)

        # USDJPY: at price 150.00, pip value = (0.01 / 150.0) * 100000 ≈ 6.6667
        pip_val_jpy = rm_jpy.calculate_pip_value(150.0)
        self.assertAlmostEqual(pip_val_jpy, 6.6667, places=3)

    def test_backtest_engine_run(self):
        bt_cfg = BacktestConfig(initial_capital=10000.0)
        engine = BacktestEngine(bt_cfg)

        strat_cfg = StrategyConfig(rsi_enabled=False, env_enabled=False, cmf_enabled=False)
        strat = StarRsiStrategy(strat_cfg)
        strat_out = strat.generate_signals(self.df)

        result = engine.run("EURUSD", strat_out.df)
        self.assertEqual(result.symbol, "EURUSD")
        self.assertIsNotNone(result.metrics)
        self.assertEqual(len(result.equity_curve), len(self.df))
        self.assertGreater(result.metrics.ending_equity, 0.0)


    def test_default_config_values(self):
        cfg = StrategyConfig()
        self.assertEqual(cfg.rsi_len, 7, "Default RSI period should be 7")
        self.assertFalse(cfg.env_enabled, "RSI(2) environment filter should be disabled by default")
        self.assertFalse(cfg.cmf_enabled, "CMF filter should be disabled by default")
        self.assertTrue(cfg.rsi_enabled, "RSI reversal should remain enabled by default")
        self.assertEqual(cfg.rsi_os, 30.0)
        self.assertEqual(cfg.rsi_ob, 70.0)

    def test_risk_manager_atr_stop(self):
        bt_cfg = BacktestConfig(sl_mode="atr", atr_multiplier_sl=1.5)
        spec = MAJOR_FX_PAIRS["EURUSD"]
        rm = RiskManager(bt_cfg, spec)

        sl, tp, risk_pips = rm.calculate_stops(
            direction=1,
            entry_price=1.1000,
            pattern_low=1.0950,
            pattern_high=1.1050,
            atr_val=0.0020,  # 20 pips -> 1.5 * 20 = 30 pips SL
        )
        self.assertAlmostEqual(sl, 1.0970, places=4)
        self.assertAlmostEqual(risk_pips, 30.0, places=1)


if __name__ == "__main__":
    unittest.main()
