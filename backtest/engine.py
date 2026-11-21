"""
Forex Strategy Backtesting Engine.
Simulates realistic trade execution with next-bar entries, spreads, slippage,
intra-candle SL/TP resolution, commission, and marked-to-market equity curve tracking.
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional
import numpy as np
import pandas as pd

from config.strategy_config import BacktestConfig, InstrumentSpec, MAJOR_FX_PAIRS
from backtest.risk_manager import RiskManager
from backtest.metrics import compute_metrics, BacktestMetrics


@dataclass
class BacktestResult:
    symbol: str
    metrics: BacktestMetrics
    trades: pd.DataFrame
    equity_curve: pd.Series
    signals_df: pd.DataFrame


class BacktestEngine:
    def __init__(self, bt_cfg: Optional[BacktestConfig] = None):
        self.bt_cfg = bt_cfg or BacktestConfig()

    def run(
        self,
        symbol: str,
        data: pd.DataFrame,
        instrument: Optional[InstrumentSpec] = None,
        interval: str = "1h",
    ) -> BacktestResult:
        """
        Runs the backtest on a prepared DataFrame with 'bull_signal', 'bear_signal',
        'pattern_low', and 'pattern_high' columns.
        """
        symbol = symbol.upper()
        inst = instrument or MAJOR_FX_PAIRS.get(symbol)
        if not inst:
            raise ValueError(f"Unknown instrument spec for {symbol}")

        risk_mgr = RiskManager(self.bt_cfg, inst)
        pip = inst.pip_size

        # Costs
        spread_pips = inst.default_spread_pips if self.bt_cfg.include_spread else 0.0
        slippage_pips = self.bt_cfg.slippage_pips
        total_friction_pips = (spread_pips / 2.0) + slippage_pips

        current_equity = self.bt_cfg.initial_capital
        equity_series = pd.Series(index=data.index, dtype=float)

        trades: List[Dict[str, Any]] = []
        open_trade: Optional[Dict[str, Any]] = None

        n = len(data)
        timestamps = data.index
        opens = data['open'].values
        highs = data['high'].values
        lows = data['low'].values
        closes = data['close'].values
        bull_sigs = data['bull_signal'].values
        bear_sigs = data['bear_signal'].values
        pattern_lows = data['pattern_low'].values
        pattern_highs = data['pattern_high'].values
        atrs = data['atr'].values if 'atr' in data.columns else np.zeros(n)

        for i in range(n):
            t_curr = timestamps[i]
            o_curr = opens[i]
            h_curr = highs[i]
            l_curr = lows[i]
            c_curr = closes[i]

            # 1. Opposite signal exit check (if enabled)
            if open_trade is not None and i > 0 and self.bt_cfg.tp_mode == "opposite_signal":
                d = open_trade['direction']
                sig_prev_bull = bull_sigs[i - 1]
                sig_prev_bear = bear_sigs[i - 1]
                if (d == 1 and sig_prev_bear) or (d == -1 and sig_prev_bull):
                    exit_price = o_curr - (total_friction_pips * pip) if d == 1 else o_curr + (total_friction_pips * pip)
                    pnl_pips = (exit_price - open_trade['entry_price']) / pip if d == 1 else (open_trade['entry_price'] - exit_price) / pip
                    pip_val = risk_mgr.calculate_pip_value(exit_price)
                    commission = open_trade['lots'] * self.bt_cfg.commission_per_lot * 2.0
                    pnl_usd = (pnl_pips * pip_val * open_trade['lots']) - commission
                    current_equity += pnl_usd

                    trades.append({
                        "symbol": symbol,
                        "direction": "LONG" if d == 1 else "SHORT",
                        "entry_time": open_trade['entry_time'],
                        "exit_time": t_curr,
                        "entry_price": round(open_trade['entry_price'], 5),
                        "exit_price": round(exit_price, 5),
                        "stop_loss": round(open_trade['stop_loss'], 5),
                        "take_profit": round(open_trade['take_profit'], 5),
                        "lots": round(open_trade['lots'], 2),
                        "risk_pips": round(open_trade['risk_pips'], 1),
                        "pnl_pips": round(pnl_pips, 1),
                        "pnl_usd": round(pnl_usd, 2),
                        "r_multiple": round(pnl_pips / open_trade['risk_pips'], 2) if open_trade['risk_pips'] > 0 else 0.0,
                        "commission": round(commission, 2),
                        "exit_reason": "Opposite Signal",
                        "duration_bars": i - open_trade['entry_bar'],
                        "equity_after": round(current_equity, 2),
                    })
                    open_trade = None

            # 2. Check for new entries triggered by signal on previous bar (i - 1)
            # Pine script: Signal confirmed at close of bar i - 1 -> entry executed at open of bar i
            if open_trade is None and i > 0:
                sig_prev_bull = bull_sigs[i - 1]
                sig_prev_bear = bear_sigs[i - 1]

                if sig_prev_bull or sig_prev_bear:
                    direction = 1 if sig_prev_bull else -1
                    p_low = pattern_lows[i - 1]
                    p_high = pattern_highs[i - 1]
                    atr_val = atrs[i - 1] if i - 1 < len(atrs) else None

                    # Account for spread / slippage on entry
                    if direction == 1:
                        entry_px = o_curr + (total_friction_pips * pip)
                    else:
                        entry_px = o_curr - (total_friction_pips * pip)

                    sl, tp, risk_pips = risk_mgr.calculate_stops(
                        direction=direction,
                        entry_price=entry_px,
                        pattern_low=p_low,
                        pattern_high=p_high,
                        atr_val=atr_val,
                    )

                    units, lots, risk_usd = risk_mgr.size_position(
                        current_equity=current_equity,
                        entry_price=entry_px,
                        risk_pips=risk_pips,
                    )

                    open_trade = {
                        "direction": direction,
                        "entry_bar": i,
                        "entry_time": t_curr,
                        "entry_price": entry_px,
                        "stop_loss": sl,
                        "take_profit": tp,
                        "units": units,
                        "lots": lots,
                        "risk_pips": risk_pips,
                        "risk_usd": risk_usd,
                        "trailed": False,
                    }

            # 3. Check open trade intra-candle execution (SL / TP / Trailing)
            if open_trade is not None:
                d = open_trade['direction']
                sl = open_trade['stop_loss']
                tp = open_trade['take_profit']
                entry_px = open_trade['entry_price']
                lots = open_trade['lots']
                risk_pips = open_trade['risk_pips']

                hit_sl = False
                hit_tp = False
                exit_price = 0.0
                exit_reason = ""

                if d == 1:  # Long position
                    sl_breached = l_curr <= sl
                    tp_breached = h_curr >= tp

                    if sl_breached and tp_breached:
                        # Conservative assumption: SL touched first
                        hit_sl = True
                        exit_price = sl - (total_friction_pips * pip)
                        exit_reason = "SL (Conservative Dual Breach)"
                    elif sl_breached:
                        hit_sl = True
                        exit_price = sl - (total_friction_pips * pip)
                        exit_reason = "SL"
                    elif tp_breached:
                        hit_tp = True
                        exit_price = tp - (total_friction_pips * pip)
                        exit_reason = "TP"
                    elif self.bt_cfg.trail_after_r > 0 and not open_trade['trailed']:
                        # Break-even trail condition: if price reached +1R, trail SL to entry
                        if h_curr >= entry_px + (risk_pips * self.bt_cfg.trail_after_r * pip):
                            open_trade['stop_loss'] = entry_px + (1.0 * pip)
                            open_trade['trailed'] = True

                else:  # Short position
                    sl_breached = h_curr >= sl
                    tp_breached = l_curr <= tp

                    if sl_breached and tp_breached:
                        hit_sl = True
                        exit_price = sl + (total_friction_pips * pip)
                        exit_reason = "SL (Conservative Dual Breach)"
                    elif sl_breached:
                        hit_sl = True
                        exit_price = sl + (total_friction_pips * pip)
                        exit_reason = "SL"
                    elif tp_breached:
                        hit_tp = True
                        exit_price = tp + (total_friction_pips * pip)
                        exit_reason = "TP"
                    elif self.bt_cfg.trail_after_r > 0 and not open_trade['trailed']:
                        # Break-even trail condition
                        if l_curr <= entry_px - (risk_pips * self.bt_cfg.trail_after_r * pip):
                            open_trade['stop_loss'] = entry_px - (1.0 * pip)
                            open_trade['trailed'] = True

                if hit_sl or hit_tp:
                    # Finalize trade
                    pnl_pips = (exit_price - entry_px) / pip if d == 1 else (entry_px - exit_price) / pip
                    pip_val = risk_mgr.calculate_pip_value(exit_price)
                    commission = lots * self.bt_cfg.commission_per_lot * 2.0  # Round turn
                    pnl_usd = (pnl_pips * pip_val * lots) - commission
                    r_multiple = pnl_pips / risk_pips if risk_pips > 0 else 0.0

                    current_equity += pnl_usd
                    duration_bars = i - open_trade['entry_bar']

                    trades.append({
                        "symbol": symbol,
                        "direction": "LONG" if d == 1 else "SHORT",
                        "entry_time": open_trade['entry_time'],
                        "exit_time": t_curr,
                        "entry_price": round(entry_px, 5),
                        "exit_price": round(exit_price, 5),
                        "stop_loss": round(sl, 5),
                        "take_profit": round(tp, 5),
                        "lots": round(lots, 2),
                        "risk_pips": round(risk_pips, 1),
                        "pnl_pips": round(pnl_pips, 1),
                        "pnl_usd": round(pnl_usd, 2),
                        "r_multiple": round(r_multiple, 2),
                        "commission": round(commission, 2),
                        "exit_reason": exit_reason,
                        "duration_bars": duration_bars,
                        "equity_after": round(current_equity, 2),
                    })
                    open_trade = None

            # 4. Mark to market equity at bar close
            if open_trade is not None:
                d = open_trade['direction']
                unrealized_pips = (c_curr - open_trade['entry_price']) / pip if d == 1 else (open_trade['entry_price'] - c_curr) / pip
                pip_val = risk_mgr.calculate_pip_value(c_curr)
                unrealized_usd = unrealized_pips * pip_val * open_trade['lots']
                equity_series.iloc[i] = current_equity + unrealized_usd
            else:
                equity_series.iloc[i] = current_equity

        # Close any lingering trade at last bar close
        if open_trade is not None:
            last_idx = n - 1
            d = open_trade['direction']
            exit_price = closes[last_idx]
            pnl_pips = (exit_price - open_trade['entry_price']) / pip if d == 1 else (open_trade['entry_price'] - exit_price) / pip
            pip_val = risk_mgr.calculate_pip_value(exit_price)
            commission = open_trade['lots'] * self.bt_cfg.commission_per_lot * 2.0
            pnl_usd = (pnl_pips * pip_val * open_trade['lots']) - commission
            current_equity += pnl_usd

            trades.append({
                "symbol": symbol,
                "direction": "LONG" if d == 1 else "SHORT",
                "entry_time": open_trade['entry_time'],
                "exit_time": timestamps[last_idx],
                "entry_price": round(open_trade['entry_price'], 5),
                "exit_price": round(exit_price, 5),
                "stop_loss": round(open_trade['stop_loss'], 5),
                "take_profit": round(open_trade['take_profit'], 5),
                "lots": round(open_trade['lots'], 2),
                "risk_pips": round(open_trade['risk_pips'], 1),
                "pnl_pips": round(pnl_pips, 1),
                "pnl_usd": round(pnl_usd, 2),
                "r_multiple": round(pnl_pips / open_trade['risk_pips'], 2) if open_trade['risk_pips'] > 0 else 0.0,
                "commission": round(commission, 2),
                "exit_reason": "End of Data",
                "duration_bars": last_idx - open_trade['entry_bar'],
                "equity_after": round(current_equity, 2),
            })
            equity_series.iloc[-1] = current_equity

        # Annualization factor for Sharpe/Sortino based on timeframe
        tf_factors = {
            "1m": 252 * 24 * 60,
            "5m": 252 * 24 * 12,
            "15m": 252 * 24 * 4,
            "30m": 252 * 24 * 2,
            "1h": 252 * 24,
            "4h": 252 * 6,
            "1d": 252,
        }
        ann_factor = tf_factors.get(interval.lower(), 252 * 24)

        trades_df = pd.DataFrame(trades)
        metrics = compute_metrics(
            symbol=symbol,
            initial_capital=self.bt_cfg.initial_capital,
            trades=trades,
            equity_curve=equity_series,
            annualization_factor=ann_factor,
        )

        return BacktestResult(
            symbol=symbol,
            metrics=metrics,
            trades=trades_df,
            equity_curve=equity_series,
            signals_df=data,
        )
