"""
Ultra-Fast Automated Parameter Optimization & Sensitivity Analysis Engine.
Runs through probable indicator, pattern, and risk configurations
to find the settings with the highest Win Rate, Profit Factor, and Net PnL.
"""

import os
import sys
import time
import argparse
import itertools
import logging
import multiprocessing
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Tuple

# Ensure safe console printing on Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

import numpy as np
import pandas as pd

from config.strategy_config import ALL_FX_PAIRS, MAJOR_FX_PAIRS, MINOR_FX_PAIRS
from data.dukascopy_loader import DukascopyDataLoader
from indicators.rsi import calc_wilder_rsi

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("Optimizer")


class FastOptimizer:
    def __init__(self, df: pd.DataFrame, pip_size: float = 0.0001):
        self.df = df
        self.pip = pip_size
        self.n = len(df)

        self.opens = df['open'].values
        self.highs = df['high'].values
        self.lows = df['low'].values
        self.closes = df['close'].values

        logger.info(f"Loaded {self.n} bars for optimization.")
        self._precompute_geometry()

    def _precompute_geometry(self):
        c0, o0, h0, l0 = self.closes, self.opens, self.highs, self.lows

        # Shift 1 (Star)
        c1 = np.roll(c0, 1); c1[0] = np.nan
        o1 = np.roll(o0, 1); o1[0] = np.nan
        h1 = np.roll(h0, 1); h1[0] = np.nan
        l1 = np.roll(l0, 1); l1[0] = np.nan

        # Shift 2 (First leg)
        c2 = np.roll(c0, 2); c2[:2] = np.nan
        o2 = np.roll(o0, 2); o2[:2] = np.nan
        h2 = np.roll(h0, 2); h2[:2] = np.nan
        l2 = np.roll(l0, 2); l2[:2] = np.nan

        self.c0, self.o0, self.h0, self.l0 = c0, o0, h0, l0
        self.c1, self.o1, self.h1, self.l1 = c1, o1, h1, l1
        self.c2, self.o2, self.h2, self.l2 = c2, o2, h2, l2

        self.body1 = np.abs(c2 - o2)
        self.range1 = h2 - l2
        with np.errstate(divide='ignore', invalid='ignore'):
            self.body1_pct = np.where(self.range1 > 0, (self.body1 / self.range1) * 100.0, 0.0)

        self.body2 = np.abs(c1 - o1)
        self.range2 = h1 - l1
        with np.errstate(divide='ignore', invalid='ignore'):
            self.star_body_pct = np.where(self.range2 > 0, (self.body2 / self.range2) * 100.0, np.nan)

        self.body3 = np.abs(c0 - o0)

        self.first_bear = c2 < o2
        self.first_bull = c2 > o2
        self.third_bull = c0 > o0
        self.third_bear = c0 < o0

        self.star_bull = c1 > o1
        self.star_bear = c1 < o1

        self.pattern_low = np.minimum(np.minimum(l0, l1), l2)
        self.pattern_high = np.maximum(np.maximum(h0, h1), h2)

        self.star_low = l1
        self.star_high = h1

        self.detach_bull = np.minimum(o1, c1) >= np.minimum(o2, c2)
        self.detach_bear = np.maximum(o1, c1) <= np.maximum(o2, c2)

        self.doji_ok = self.body1_pct >= 10.0

    def precompute_rsi_masks(
        self,
        rsi_lengths: List[int],
        rsi_thresholds: List[Tuple[float, float]],
        rsi_windows: List[int],
        rsi_ma_options: List[bool],
        rsi_ma_len: int = 14,
    ) -> Dict[Tuple, Tuple[np.ndarray, np.ndarray]]:
        """Precomputes boolean masks (bull_rsi_ok, bear_rsi_ok) for all RSI configs."""
        rsi_masks = {}
        close_series = pd.Series(self.closes)

        rsi_raw = {}
        ma_raw = {}
        for r_len in rsi_lengths:
            rsi_s = calc_wilder_rsi(close_series, period=r_len).values
            rsi_raw[r_len] = rsi_s
            ma_raw[r_len] = pd.Series(rsi_s).rolling(rsi_ma_len).mean().values

        for r_len in rsi_lengths:
            r_vals = rsi_raw[r_len]
            ma_v = ma_raw[r_len]
            ma_valid = ~np.isnan(ma_v)

            for (r_os, r_ob) in rsi_thresholds:
                valid = ~np.isnan(r_vals)
                valid_prev = np.roll(valid, 1); valid_prev[0] = False
                r_prev = np.roll(r_vals, 1); r_prev[0] = np.nan

                both_valid = valid & valid_prev
                cross_up = both_valid & (r_prev < r_os) & (r_vals >= r_os)
                cross_dn = both_valid & (r_prev > r_ob) & (r_vals <= r_ob)

                last_dir = np.zeros(self.n, dtype=int)
                last_age = np.full(self.n, 999999, dtype=int)

                cur_dir = 0
                cur_bar = -999999
                for i in range(1, self.n):
                    if cross_up[i]:
                        cur_dir = 1
                        cur_bar = i
                    elif cross_dn[i]:
                        cur_dir = -1
                        cur_bar = i
                    last_dir[i] = cur_dir
                    last_age[i] = i - cur_bar

                for r_win in rsi_windows:
                    age_ok = last_age <= r_win
                    bull_cross_ok = (last_dir == 1) & age_ok
                    bear_cross_ok = (last_dir == -1) & age_ok

                    for r_ma_en in rsi_ma_options:
                        if not r_ma_en:
                            key = (r_len, (r_os, r_ob), r_win, False)
                            rsi_masks[key] = (bull_cross_ok, bear_cross_ok)
                        else:
                            ma_bull_ok = ma_valid & (r_vals >= ma_v)
                            ma_bear_ok = ma_valid & (r_vals <= ma_v)

                            b_ok = bull_cross_ok & ma_bull_ok
                            s_ok = bear_cross_ok & ma_bear_ok
                            key = (r_len, (r_os, r_ob), r_win, True)
                            rsi_masks[key] = (b_ok, s_ok)

        return rsi_masks

    def precompute_star_masks(
        self,
        star_body_factors: List[float],
        third_body_factors: List[float],
        star_detaches: List[bool],
        star_color_rules: List[bool],
        first_vs_thirds: List[float] = [0.65],
        star_penetrations: List[float] = [0.50],
    ) -> Dict[Tuple, Tuple[np.ndarray, np.ndarray]]:
        """Precomputes boolean masks for Morning Star and Evening Star."""
        star_masks = {}

        for s_pen in star_penetrations:
            pen_bull_level = np.maximum(self.o2, self.c2) - self.body1 * s_pen
            pen_bear_level = np.minimum(self.o2, self.c2) + self.body1 * s_pen
            penetrate_bull = self.third_bull & (self.c0 > pen_bull_level)
            penetrate_bear = self.third_bear & (self.c0 < pen_bear_level)

            for f_vt in first_vs_thirds:
                first_leg_big = self.body1 >= self.body3 * f_vt

                for s_bf in star_body_factors:
                    middle_small = (
                        (self.body2 <= self.body1 * s_bf) &
                        (self.body2 <= self.body3 * s_bf) &
                        (self.body2 <= self.range2 * 0.40)
                    )

                    for t_bf in third_body_factors:
                        third_real = self.body3 >= self.body1 * t_bf

                        for s_det in star_detaches:
                            det_bull = np.ones(self.n, dtype=bool) if not s_det else self.detach_bull
                            det_bear = np.ones(self.n, dtype=bool) if not s_det else self.detach_bear

                            for s_col in star_color_rules:
                                if not s_col:
                                    col_bull = np.ones(self.n, dtype=bool)
                                    col_bear = np.ones(self.n, dtype=bool)
                                else:
                                    amb = np.isnan(self.star_body_pct) | (self.star_body_pct < 10.0)
                                    col_bull = amb | self.star_bull
                                    col_bear = amb | self.star_bear

                                m_star = (
                                    self.first_bear & self.third_bull & middle_small &
                                    third_real & first_leg_big & col_bull &
                                    penetrate_bull & det_bull & self.doji_ok
                                )

                                e_star = (
                                    self.first_bull & self.third_bear & middle_small &
                                    third_real & first_leg_big & col_bear &
                                    penetrate_bear & det_bear & self.doji_ok
                                )

                                key = (s_bf, t_bf, f_vt, s_pen, s_det, s_col)
                                star_masks[key] = (m_star, e_star)

        return star_masks

    def fast_simulate(
        self,
        bull_signals: np.ndarray,
        bear_signals: np.ndarray,
        sl_source: str = "pattern_extreme",
        sl_buffer_pips: float = 0.0,
        risk_reward_ratio: float = 2.0,
        max_holding_bars: int = 120,
    ) -> Dict[str, Any]:
        """Fast discrete simulation of non-overlapping trades."""
        buf = sl_buffer_pips * self.pip
        sig_indices = np.where(bull_signals | bear_signals)[0]
        
        if len(sig_indices) == 0:
            return {
                "trades": 0, "wins": 0, "losses": 0,
                "win_rate": 0.0, "profit_factor": 0.0,
                "net_profit_usd": 0.0, "return_pct": 0.0,
                "expectancy_r": 0.0, "avg_bars": 0.0,
            }

        next_avail_bar = 0
        trades = []
        equity = 10000.0

        for idx in sig_indices:
            if idx < next_avail_bar or idx + 1 >= self.n:
                continue

            entry_idx = idx + 1
            o_entry = self.opens[entry_idx]
            d = 1 if bull_signals[idx] else -1

            if sl_source == "pattern_extreme":
                sl_raw = self.pattern_low[idx] if d == 1 else self.pattern_high[idx]
            else:
                sl_raw = self.star_low[idx] if d == 1 else self.star_high[idx]

            end_idx = min(entry_idx + max_holding_bars, self.n)

            if d == 1:
                sl = sl_raw - buf
                if sl >= o_entry: sl = o_entry - (5.0 * self.pip)
                risk_dist = o_entry - sl
                tp = o_entry + (risk_dist * risk_reward_ratio)

                sub_l = self.lows[entry_idx:end_idx]
                sub_h = self.highs[entry_idx:end_idx]

                sl_mask = sub_l <= sl
                tp_mask = sub_h >= tp

                s_bar = np.argmax(sl_mask) if sl_mask.any() else 999999
                t_bar = np.argmax(tp_mask) if tp_mask.any() else 999999

                if s_bar == 999999 and t_bar == 999999:
                    continue

                if t_bar < s_bar:
                    won = True; bars = t_bar
                else:
                    won = False; bars = s_bar

            else:  # Short
                sl = sl_raw + buf
                if sl <= o_entry: sl = o_entry + (5.0 * self.pip)
                risk_dist = sl - o_entry
                tp = o_entry - (risk_dist * risk_reward_ratio)

                sub_l = self.lows[entry_idx:end_idx]
                sub_h = self.highs[entry_idx:end_idx]

                sl_mask = sub_h >= sl
                tp_mask = sub_l <= tp

                s_bar = np.argmax(sl_mask) if sl_mask.any() else 999999
                t_bar = np.argmax(tp_mask) if tp_mask.any() else 999999

                if s_bar == 999999 and t_bar == 999999:
                    continue

                if t_bar < s_bar:
                    won = True; bars = t_bar
                else:
                    won = False; bars = s_bar

            next_avail_bar = entry_idx + bars + 1
            r_mult = risk_reward_ratio if won else -1.0
            pnl_usd = (equity * 0.01) * r_mult
            equity += pnl_usd
            trades.append((r_mult, pnl_usd, won, bars))

        total_trades = len(trades)
        if total_trades == 0:
            return {
                "trades": 0, "wins": 0, "losses": 0,
                "win_rate": 0.0, "profit_factor": 0.0,
                "net_profit_usd": 0.0, "return_pct": 0.0,
                "expectancy_r": 0.0, "avg_bars": 0.0,
            }

        wins = sum(1 for t in trades if t[2])
        losses = total_trades - wins
        win_rate = (wins / total_trades) * 100.0

        gross_profit = sum(t[1] for t in trades if t[2])
        gross_loss = abs(sum(t[1] for t in trades if not t[2]))
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (99.0 if gross_profit > 0 else 0.0)

        net_profit = equity - 10000.0
        return_pct = (net_profit / 10000.0) * 100.0
        expectancy_r = float(np.mean([t[0] for t in trades]))
        avg_bars = float(np.mean([t[3] for t in trades]))

        return {
            "trades": total_trades,
            "wins": wins,
            "losses": losses,
            "win_rate": round(win_rate, 2),
            "profit_factor": round(profit_factor, 2),
            "net_profit_usd": round(net_profit, 2),
            "return_pct": round(return_pct, 2),
            "expectancy_r": round(expectancy_r, 2),
            "avg_bars": round(avg_bars, 1),
        }


def _worker_task(task_args):
    """Worker task evaluating a subset of star masks against all RSI and exit configs."""
    chunk_star_items, rsi_masks, exit_configs, opt_obj, min_trades, symbol, interval = task_args
    results = []
    sim_cache = {}
    tested = 0

    for s_key, (m_star, e_star) in chunk_star_items:
        s_bf, t_bf, f_vt, s_pen, s_det, s_col = s_key

        for r_key, (b_rsi, s_rsi) in rsi_masks.items():
            r_len, (r_os, r_ob), r_win, r_ma_en = r_key

            final_bull = m_star & b_rsi
            final_bear = e_star & s_rsi

            tested += len(exit_configs)

            bull_idxs = np.where(final_bull)[0]
            bear_idxs = np.where(final_bear)[0]
            n_sigs = len(bull_idxs) + len(bear_idxs)

            if n_sigs < min_trades:
                continue

            sig_key = (tuple(bull_idxs), tuple(bear_idxs))

            for sl_src, sl_buf, rr in exit_configs:
                c_key = (sig_key, sl_src, sl_buf, rr)
                if c_key in sim_cache:
                    sim = sim_cache[c_key]
                else:
                    sim = opt_obj.fast_simulate(
                        bull_signals=final_bull,
                        bear_signals=final_bear,
                        sl_source=sl_src,
                        sl_buffer_pips=sl_buf,
                        risk_reward_ratio=rr,
                    )
                    sim_cache[c_key] = sim

                if sim["trades"] >= min_trades:
                    results.append({
                        "Symbol": symbol,
                        "Interval": interval,
                        "RSI_Len": r_len,
                        "RSI_Levels": f"{int(r_os)}/{int(r_ob)}",
                        "RSI_Win": r_win,
                        "RSI_MA": r_ma_en,
                        "Star_Body_Fac": s_bf,
                        "Third_Body_Fac": t_bf,
                        "First_Vs_Third": f_vt,
                        "Star_Penetration": s_pen,
                        "Star_Detach": s_det,
                        "Star_Color": s_col,
                        "SL_Source": sl_src,
                        "SL_Buffer": sl_buf,
                        "RR_Ratio": rr,
                        "Total_Trades": sim["trades"],
                        "Wins": sim["wins"],
                        "Losses": sim["losses"],
                        "Win_Rate_Pct": sim["win_rate"],
                        "Profit_Factor": sim["profit_factor"],
                        "Net_Profit_USD": sim["net_profit_usd"],
                        "Return_Pct": sim["return_pct"],
                        "Expectancy_R": sim["expectancy_r"],
                        "Avg_Bars": sim["avg_bars"],
                    })

    return results, tested


def run_optimization(args):
    cache_path = os.path.join(os.path.dirname(__file__), "data", "cache")
    loader = DukascopyDataLoader(cache_dir=cache_path)
    
    end_dt = datetime.now(timezone.utc)
    start_dt = end_dt - timedelta(days=args.days)
    
    sym_arg = args.symbol.upper().strip()
    if sym_arg == "ALL":
        symbols = list(ALL_FX_PAIRS.keys())
    elif sym_arg == "MAJORS":
        symbols = list(MAJOR_FX_PAIRS.keys())
    elif sym_arg == "MINORS":
        symbols = list(MINOR_FX_PAIRS.keys())
    else:
        symbols = [s.strip().upper() for s in args.symbol.split(",") if s.strip()]

    # Grids
    if args.grid == "fast":
        rsi_lengths = [5, 7, 9, 14]
        rsi_thresholds = [(30.0, 70.0), (25.0, 75.0)]
        rsi_windows = [0, 1, 2]
        rsi_ma_options = [True, False]

        star_body_factors = [0.35, 0.40]
        third_body_factors = [0.60, 0.70]
        first_vs_thirds = [0.65]
        star_penetrations = [0.50]
        star_detaches = [False, True]
        star_color_rules = [True, False]

        sl_sources = ["pattern_extreme", "star_candle"]
        risk_rewards = [1.0, 1.5, 2.0, 2.5]
        sl_buffers = [0.0]

    elif args.grid == "full":
        rsi_lengths = [5, 6, 7, 8, 9, 10, 12, 14, 16, 21]
        rsi_thresholds = [(25.0, 75.0), (30.0, 70.0), (35.0, 65.0)]
        rsi_windows = [0, 1, 2, 3]
        rsi_ma_options = [True, False]

        star_body_factors = [0.25, 0.30, 0.35, 0.40]
        third_body_factors = [0.50, 0.60, 0.70]
        first_vs_thirds = [0.50, 0.65]
        star_penetrations = [0.50]
        star_detaches = [False, True]
        star_color_rules = [True, False]

        sl_sources = ["pattern_extreme", "star_candle"]
        risk_rewards = [1.0, 1.25, 1.5, 1.75, 2.0, 2.25, 2.5]
        sl_buffers = [0.0]

    else:  # Massive grid (>2,000,000 configurations)
        rsi_lengths = [4, 5, 6, 7, 8, 9, 10, 12, 14, 16, 18, 21]
        rsi_thresholds = [(20.0, 80.0), (25.0, 75.0), (30.0, 70.0), (35.0, 65.0)]
        rsi_windows = [0, 1, 2, 3, 4]
        rsi_ma_options = [True, False]

        star_body_factors = [0.25, 0.30, 0.35, 0.40, 0.45]
        third_body_factors = [0.50, 0.60, 0.70, 0.80]
        first_vs_thirds = [0.50, 0.65]
        star_penetrations = [0.35, 0.50]
        star_detaches = [False, True]
        star_color_rules = [True, False]

        sl_sources = ["pattern_extreme", "star_candle"]
        risk_rewards = [1.0, 1.25, 1.5, 1.75, 2.0, 2.25, 2.5, 3.0]
        sl_buffers = [0.0]

    exit_configs = list(itertools.product(sl_sources, sl_buffers, risk_rewards))
    num_workers = min(os.cpu_count() or 4, 8)

    all_results = []
    total_tested_all = 0
    t_global_start = time.time()

    for p_idx, sym in enumerate(symbols, 1):
        logger.info(f"\n[{p_idx}/{len(symbols)}] Loading {sym} ({args.interval}) for {args.days} days...")
        try:
            df = loader.load_pair(
                symbol=sym,
                interval=args.interval,
                start=start_dt,
                end=end_dt,
                force_refresh=args.refresh,
            )
        except Exception as e:
            logger.error(f"Failed to load data for {sym}: {e}")
            continue

        if df.empty:
            logger.warning(f"No data for {sym}, skipping.")
            continue

        inst = ALL_FX_PAIRS.get(sym)
        pip_size = inst.pip_size if inst else (0.01 if "JPY" in sym else 0.0001)
        opt = FastOptimizer(df, pip_size=pip_size)

        rsi_masks = opt.precompute_rsi_masks(
            rsi_lengths, rsi_thresholds, rsi_windows, rsi_ma_options
        )
        star_masks = opt.precompute_star_masks(
            star_body_factors, third_body_factors, star_detaches, star_color_rules,
            first_vs_thirds=first_vs_thirds, star_penetrations=star_penetrations
        )

        star_items = list(star_masks.items())
        chunk_size = max(1, len(star_items) // (num_workers * 2) or 1)
        star_chunks = [star_items[i:i + chunk_size] for i in range(0, len(star_items), chunk_size)]

        worker_args = [
            (chunk, rsi_masks, exit_configs, opt, args.min_trades, sym, args.interval)
            for chunk in star_chunks
        ]

        pair_results = []
        pair_tested = 0
        t_pair_start = time.time()

        with multiprocessing.Pool(processes=num_workers) as pool:
            for worker_res, worker_tested in pool.imap_unordered(_worker_task, worker_args):
                pair_results.extend(worker_res)
                pair_tested += worker_tested

        elapsed_pair = time.time() - t_pair_start
        rate_pair = pair_tested / max(elapsed_pair, 0.001)
        logger.info(f"[{sym}] Finished {pair_tested:,} configs in {elapsed_pair:.1f}s ({rate_pair:,.0f} configs/sec) - {len(pair_results):,} viable found.")

        all_results.extend(pair_results)
        total_tested_all += pair_tested

    total_elapsed = time.time() - t_global_start
    logger.info(f"\n=======================================================")
    logger.info(f"Total Sweep Complete: {total_tested_all:,} evaluations across {len(symbols)} pairs in {total_elapsed:.1f}s ({total_tested_all / max(total_elapsed, 0.001):,.0f} configs/sec)!")
    logger.info(f"Total Viable Configurations Across All Pairs: {len(all_results):,}")
    logger.info(f"=======================================================\n")

    if not all_results:
        logger.warning(f"No configuration met the threshold of at least {args.min_trades} trades. Try lowering --min_trades.")
        return

    res_df = pd.DataFrame(all_results)

    sort_col = {
        "win_rate": "Win_Rate_Pct",
        "profit_factor": "Profit_Factor",
        "net_profit": "Net_Profit_USD",
        "expectancy_r": "Expectancy_R",
    }.get(args.sort_by, "Win_Rate_Pct")

    res_df.sort_values(by=[sort_col, "Profit_Factor", "Total_Trades"], ascending=False, inplace=True)

    # Save to CSV
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    res_df.to_csv(args.out, index=False)
    logger.info(f"Saved complete optimization results ({len(res_df):,} rows) to {args.out}")

    # Top configurations table
    top_n = res_df.head(args.top_n)
    display_headers = [
        "Pair", "RSI", "Levels", "Win", "MA?", "Detach", "Color", "SL", "R:R", "Trades", "Win Rate", "Prof Fac", "Return %", "Avg R"
    ]
    
    rows = []
    for _, r in top_n.iterrows():
        rows.append([
            str(r["Symbol"]),
            str(r["RSI_Len"]),
            r["RSI_Levels"],
            str(r["RSI_Win"]),
            "Yes" if r["RSI_MA"] else "No",
            "Yes" if r["Star_Detach"] else "No",
            "Yes" if r["Star_Color"] else "No",
            "Extr" if r["SL_Source"] == "pattern_extreme" else "Star",
            f"{r['RR_Ratio']:.2f}",
            str(r["Total_Trades"]),
            f"{r['Win_Rate_Pct']:.1f}%",
            f"{r['Profit_Factor']:.2f}",
            f"{r['Return_Pct']:+.1f}%",
            f"{r['Expectancy_R']:+.2f}R",
        ])

    col_widths = [max(len(str(val)) for val in [h] + [r[i] for r in rows]) + 2 for i, h in enumerate(display_headers)]
    sep_line = "+" + "+".join("-" * w for w in col_widths) + "+"
    hdr_line = "|" + "|".join(f" {h}".ljust(w) for h, w in zip(display_headers, col_widths)) + "|"

    print("\n" + "=" * len(sep_line))
    print(f" [PORTFOLIO TOP {args.top_n} CONFIGURATIONS] ({args.symbol} | {args.interval} | Sorted by {sort_col})")
    print("=" * len(sep_line))
    print(sep_line)
    print(hdr_line)
    print(sep_line)
    for r in rows:
        print("|" + "|".join(f" {v}".ljust(w) for v, w in zip(r, col_widths)) + "|")
    print(sep_line + "\n")

    # If multiple symbols tested, print per-pair summary
    if len(symbols) > 1:
        pair_grp = res_df.groupby("Symbol").agg(
            best_win_rate=("Win_Rate_Pct", "max"),
            best_profit_factor=("Profit_Factor", "max"),
            best_return=("Return_Pct", "max"),
            total_viable=("Total_Trades", "count"),
        ).reset_index()

        pair_headers = ["Pair", "Best Win Rate", "Best Profit Factor", "Best Return %", "Viable Configs"]
        p_rows = []
        for _, pr in pair_grp.iterrows():
            p_rows.append([
                pr["Symbol"],
                f"{pr['best_win_rate']:.1f}%",
                f"{pr['best_profit_factor']:.2f}",
                f"{pr['best_return']:+.1f}%",
                f"{pr['total_viable']:,}",
            ])

        p_widths = [max(len(str(val)) for val in [h] + [r[i] for r in p_rows]) + 2 for i, h in enumerate(pair_headers)]
        p_sep = "+" + "+".join("-" * w for w in p_widths) + "+"
        p_hdr = "|" + "|".join(f" {h}".ljust(w) for h, w in zip(pair_headers, p_widths)) + "|"

        print("\n" + "=" * len(p_sep))
        print(" [PER-PAIR BEST PERFORMANCE SUMMARY]")
        print("=" * len(p_sep))
        print(p_sep)
        print(p_hdr)
        print(p_sep)
        for r in p_rows:
            print("|" + "|".join(f" {v}".ljust(w) for v, w in zip(r, p_widths)) + "|")
        print(p_sep + "\n")


def main():
    parser = argparse.ArgumentParser(description="Ultra-Fast Star+RSI Strategy Parameter Optimizer")
    parser.add_argument("--symbol", type=str, default="EURUSD", help="Forex symbol to optimize (default: EURUSD)")
    parser.add_argument("--interval", type=str, default="5m", help="Candle timeframe (default: 5m)")
    parser.add_argument("--days", type=int, default=180, help="Days of history to analyze (default: 180)")
    parser.add_argument("--min_trades", type=int, default=20, help="Minimum sample trades required (default: 20)")
    parser.add_argument("--top_n", type=int, default=15, help="Number of top configurations to show (default: 15)")
    parser.add_argument("--sort_by", type=str, default="win_rate", choices=["win_rate", "profit_factor", "net_profit", "expectancy_r"], help="Sorting metric")
    parser.add_argument("--grid", type=str, default="full", choices=["fast", "full", "massive"], help="Search grid depth")
    parser.add_argument("--refresh", action="store_true", help="Force fresh download from Dukascopy")
    parser.add_argument("--out", type=str, default="reports/optimization_results.csv", help="Output CSV filepath")

    args = parser.parse_args()
    run_optimization(args)


if __name__ == "__main__":
    main()
