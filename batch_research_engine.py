"""
10-Year Multi-Batch Cross-Asset Data Science Research Engine
Executes exhaustive parameter grid search across 180-day batches for all 28 Major & Minor Forex pairs.
Finds the robust configuration that succeeds in the maximum number of batches.
"""

import os
import sys
import time
import argparse
import logging
import multiprocessing
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Tuple
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

import numpy as np
import pandas as pd

from config.strategy_config import ALL_FX_PAIRS, MAJOR_FX_PAIRS, MINOR_FX_PAIRS
from data.dukascopy_loader import DukascopyDataLoader
from indicators.rsi import calc_wilder_rsi
from optimize import FastOptimizer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("10YrBatchResearch")


def partition_into_180d_batches(df: pd.DataFrame, batch_days: int = 180) -> List[Tuple[int, pd.DataFrame, str, str]]:
    """Splits a 10-year DataFrame into chronological non-overlapping batches of N days."""
    if df.empty:
        return []

    batches = []
    start_time = df.index[0]
    end_limit = df.index[-1]
    batch_idx = 1

    current_start = start_time
    while current_start < end_limit:
        current_end = current_start + timedelta(days=batch_days)
        sub_df = df[(df.index >= current_start) & (df.index < current_end)]
        if len(sub_df) >= 5000:  # Minimum valid bars for a batch (~3-4 weeks minimum)
            s_str = sub_df.index[0].strftime("%Y-%m-%d")
            e_str = sub_df.index[-1].strftime("%Y-%m-%d")
            batches.append((batch_idx, sub_df, s_str, e_str))
            batch_idx += 1
        current_start = current_end

    return batches


class BatchGridEvaluator:
    """Evaluates all configurations across a single 180-day batch slice."""

    def __init__(self, df: pd.DataFrame, pip_size: float = 0.0001):
        self.df = df
        self.opt = FastOptimizer(df, pip_size=pip_size)
        self.pip = pip_size

    def evaluate_all_configurations(
        self,
        rsi_lengths: List[int] = None,
        rsi_levels: List[Tuple[float, float]] = None,
        rsi_windows: List[int] = None,
        rsi_ma_options: List[bool] = None,
        star_body_factors: List[float] = None,
        third_body_factors: List[float] = None,
        star_detach_options: List[bool] = None,
        star_color_options: List[bool] = None,
        sl_sources: List[str] = None,
        rr_ratios: List[float] = None,
    ) -> List[Dict[str, Any]]:
        if rsi_lengths is None:
            rsi_lengths = [5, 7, 8, 9, 10, 12, 14, 16, 18, 21]
        if rsi_levels is None:
            rsi_levels = [(20.0, 80.0), (25.0, 75.0), (30.0, 70.0), (35.0, 65.0)]
        if rsi_windows is None:
            rsi_windows = [0, 1, 2, 3]
        if rsi_ma_options is None:
            rsi_ma_options = [False, True]
        if star_body_factors is None:
            star_body_factors = [0.20, 0.25, 0.30, 0.35, 0.40, 0.50]
        if third_body_factors is None:
            third_body_factors = [0.50, 0.60, 0.70]
        if star_detach_options is None:
            star_detach_options = [False, True]
        if star_color_options is None:
            star_color_options = [False, True]
        if sl_sources is None:
            sl_sources = ["star_candle", "pattern_extreme"]
        if rr_ratios is None:
            rr_ratios = [1.0, 1.25, 1.5, 1.75, 2.0, 2.5]

        # 1. Precompute RSI masks
        close_series = pd.Series(self.opt.closes)
        rsi_masks = {}

        for length in rsi_lengths:
            rsi_vals = calc_wilder_rsi(close_series, period=length).values
            valid = ~np.isnan(rsi_vals)
            valid_prev = np.roll(valid, 1); valid_prev[0] = False
            r_prev = np.roll(rsi_vals, 1); r_prev[0] = np.nan
            both_valid = valid & valid_prev

            for os_val, ob_val in rsi_levels:
                cup_base = both_valid & (r_prev < os_val) & (rsi_vals >= os_val)
                cdn_base = both_valid & (r_prev > ob_val) & (rsi_vals <= ob_val)

                for ma_en in rsi_ma_options:
                    if ma_en:
                        ma_vals = pd.Series(rsi_vals).rolling(14).mean().values
                        ma_ok = ~np.isnan(ma_vals)
                        cup = cup_base & ma_ok & (rsi_vals > ma_vals)
                        cdn = cdn_base & ma_ok & (rsi_vals < ma_vals)
                    else:
                        cup = cup_base
                        cdn = cdn_base

                    for win in rsi_windows:
                        if win == 0:
                            b_sig = cup
                            s_sig = cdn
                        else:
                            b_sig = np.zeros(self.opt.n, dtype=bool)
                            s_sig = np.zeros(self.opt.n, dtype=bool)
                            cur_dir = 0
                            cur_age = 999999
                            last_dir = np.zeros(self.opt.n, dtype=int)
                            last_age = np.full(self.opt.n, 999999, dtype=int)

                            for i in range(self.opt.n):
                                if cup[i] and not cdn[i]:
                                    cur_dir = 1; cur_age = 0
                                elif cdn[i] and not cup[i]:
                                    cur_dir = -1; cur_age = 0
                                else:
                                    if cur_dir != 0: cur_age += 1
                                last_dir[i] = cur_dir
                                last_age[i] = cur_age

                            b_sig = (last_dir == 1) & (last_age <= win)
                            s_sig = (last_dir == -1) & (last_age <= win)

                        key = (length, os_val, ob_val, win, ma_en)
                        rsi_masks[key] = (b_sig, s_sig)

        # 2. Precompute Star Pattern masks
        star_masks = {}
        for s_bf in star_body_factors:
            m_small = (
                (self.opt.body2 <= self.opt.body1 * s_bf) &
                (self.opt.body2 <= self.opt.body3 * s_bf) &
                (self.opt.body2 <= self.opt.range2 * 0.40)
            )
            for t_bf in third_body_factors:
                t_real = self.opt.body3 >= self.opt.body1 * t_bf
                first_big = self.opt.body1 >= self.opt.body3 * 0.50

                for det in star_detach_options:
                    det_bull = np.ones(self.opt.n, dtype=bool) if not det else self.opt.detach_bull
                    det_bear = np.ones(self.opt.n, dtype=bool) if not det else self.opt.detach_bear

                    for col in star_color_options:
                        if not col:
                            col_bull = np.ones(self.opt.n, dtype=bool)
                            col_bear = np.ones(self.opt.n, dtype=bool)
                        else:
                            amb = np.isnan(self.opt.star_body_pct) | (self.opt.star_body_pct < 10.0)
                            col_bull = amb | self.opt.star_bull
                            col_bear = amb | self.opt.star_bear

                        pen_bull = self.opt.third_bull & (self.opt.c0 > (np.maximum(self.opt.o2, self.opt.c2) - self.opt.body1 * 0.50))
                        pen_bear = self.opt.third_bear & (self.opt.c0 < (np.minimum(self.opt.o2, self.opt.c2) + self.opt.body1 * 0.50))

                        m_star = (
                            self.opt.first_bear & self.opt.third_bull & m_small &
                            t_real & first_big & col_bull &
                            pen_bull & det_bull & self.opt.doji_ok
                        )
                        e_star = (
                            self.opt.first_bull & self.opt.third_bear & m_small &
                            t_real & first_big & col_bear &
                            pen_bear & det_bear & self.opt.doji_ok
                        )

                        key = (s_bf, t_bf, det, col)
                        star_masks[key] = (m_star, e_star)

        # 3. Simulate and collect metrics with multiprocessing parallelization
        num_cpus = max(1, min(multiprocessing.cpu_count(), 8))
        star_items = list(star_masks.items())
        chunk_size = max(1, len(star_items) // num_cpus)
        chunks = [star_items[i:i + chunk_size] for i in range(0, len(star_items), chunk_size)]

        task_args = [
            (chunk, rsi_masks, sl_sources, rr_ratios, self)
            for chunk in chunks
        ]

        results = []
        with multiprocessing.Pool(processes=num_cpus) as pool:
            for chunk_res in pool.map(_batch_worker_task, task_args):
                results.extend(chunk_res)

        return results

    def _fast_trade_sim(
        self,
        bull_mask: np.ndarray,
        bear_mask: np.ndarray,
        sig_indices: np.ndarray,
        sl_source: str,
        rr: float,
    ) -> Dict[str, Any]:
        trades_won = 0
        trades_lost = 0
        pnl_sum = 0.0
        r_sum = 0.0
        equity = 10000.0
        peak_equity = 10000.0
        max_dd = 0.0
        next_avail = 0

        for idx in sig_indices:
            if idx < next_avail or idx + 1 >= self.opt.n:
                continue

            entry_idx = idx + 1
            o_entry = self.opt.opens[entry_idx]
            d = 1 if bull_mask[idx] else -1

            if sl_source == "pattern_extreme":
                sl_raw = self.opt.pattern_low[idx] if d == 1 else self.opt.pattern_high[idx]
            else:
                sl_raw = self.opt.star_low[idx] if d == 1 else self.opt.star_high[idx]

            end_idx = min(entry_idx + 120, self.opt.n)

            if d == 1:
                sl = sl_raw
                if sl >= o_entry: sl = o_entry - (5.0 * self.pip)
                risk_dist = o_entry - sl
                tp = o_entry + (risk_dist * rr)

                sub_l = self.opt.lows[entry_idx:end_idx]
                sub_h = self.opt.highs[entry_idx:end_idx]

                sl_mask = sub_l <= sl
                tp_mask = sub_h >= tp

                s_bar = np.argmax(sl_mask) if sl_mask.any() else 999999
                t_bar = np.argmax(tp_mask) if tp_mask.any() else 999999

                if s_bar == 999999 and t_bar == 999999:
                    continue

                won = t_bar < s_bar
                bars = t_bar if won else s_bar

            else:
                sl = sl_raw
                if sl <= o_entry: sl = o_entry + (5.0 * self.pip)
                risk_dist = sl - o_entry
                tp = o_entry - (risk_dist * rr)

                sub_l = self.opt.lows[entry_idx:end_idx]
                sub_h = self.opt.highs[entry_idx:end_idx]

                sl_mask = sub_h >= sl
                tp_mask = sub_l <= tp

                s_bar = np.argmax(sl_mask) if sl_mask.any() else 999999
                t_bar = np.argmax(tp_mask) if tp_mask.any() else 999999

                if s_bar == 999999 and t_bar == 999999:
                    continue

                won = t_bar < s_bar
                bars = t_bar if won else s_bar

            next_avail = entry_idx + bars + 1

            r_mult = rr if won else -1.0
            r_sum += r_mult
            trade_pnl = (equity * 0.01) * r_mult
            pnl_sum += trade_pnl
            equity += trade_pnl

            if equity > peak_equity:
                peak_equity = equity
            dd = (peak_equity - equity) / peak_equity * 100.0
            if dd > max_dd:
                max_dd = dd

            if won:
                trades_won += 1
            else:
                trades_lost += 1

        total = trades_won + trades_lost
        if total < 5:
            return None

        wr = (trades_won / total) * 100.0
        gross_p = trades_won * rr
        gross_l = trades_lost * 1.0
        pf = (gross_p / gross_l) if gross_l > 0 else (99.0 if gross_p > 0 else 0.0)
        ret_pct = ((equity - 10000.0) / 10000.0) * 100.0
        exp_r = r_sum / total

        # Batch success criteria:
        # Breakeven WR for rr = 1 / (1 + rr)
        be_wr = (1.0 / (1.0 + rr)) * 100.0
        batch_passed = (wr >= be_wr) and (pf >= 1.05) and (ret_pct > 0)

        return {
            "Total_Trades": total,
            "Wins": trades_won,
            "Losses": trades_lost,
            "Win_Rate_Pct": round(wr, 1),
            "Profit_Factor": round(pf, 2),
            "Return_Pct": round(ret_pct, 1),
            "Max_Drawdown_Pct": round(max_dd, 1),
            "Expectancy_R": round(exp_r, 2),
            "Batch_Passed": batch_passed,
        }


def _batch_worker_task(args):
    """Parallel worker evaluating a star mask chunk against all RSI and exit configurations."""
    chunk_star_items, rsi_masks, sl_sources, rr_ratios, evaluator = args
    results = []
    trade_cache = {}

    for (s_bf, t_bf, s_det, s_col), (m_star, e_star) in chunk_star_items:
        for (r_len, os_v, ob_v, r_win, r_ma), (b_rsi, s_rsi) in rsi_masks.items():
            final_bull = m_star & b_rsi
            final_bear = e_star & s_rsi

            sig_idx = np.where(final_bull | final_bear)[0]
            if len(sig_idx) < 5:
                continue

            sig_tuple = tuple(sig_idx)

            for sl_src in sl_sources:
                for rr in rr_ratios:
                    sim_key = (sig_tuple, sl_src, rr)

                    if sim_key in trade_cache:
                        res = trade_cache[sim_key]
                    else:
                        res = evaluator._fast_trade_sim(final_bull, final_bear, sig_idx, sl_src, rr)
                        trade_cache[sim_key] = res

                    if res is not None:
                        results.append({
                            "RSI_Len": r_len,
                            "RSI_Levels": f"{int(os_v)}/{int(ob_v)}",
                            "RSI_Win": r_win,
                            "RSI_MA": r_ma,
                            "Star_Body_Fac": s_bf,
                            "Third_Body_Fac": t_bf,
                            "Star_Detach": s_det,
                            "Star_Color": s_col,
                            "SL_Source": sl_src,
                            "RR_Ratio": rr,
                            **res,
                        })

    return results


def process_single_batch(
    symbol: str,
    batch_idx: int,
    batch_df: pd.DataFrame,
    start_str: str,
    end_str: str,
    output_dir: str,
) -> str:
    """Evaluates all configurations on one batch and saves results."""
    inst = ALL_FX_PAIRS.get(symbol.upper())
    pip_size = inst.pip_size if inst else (0.01 if "JPY" in symbol else 0.0001)

    evaluator = BatchGridEvaluator(batch_df, pip_size=pip_size)
    t0 = time.time()
    results = evaluator.evaluate_all_configurations()
    dur = time.time() - t0

    if not results:
        logger.warning(f"[{symbol}] Batch #{batch_idx} ({start_str} to {end_str}): No valid trade setups found.")
        return ""

    out_df = pd.DataFrame(results)
    out_df["Symbol"] = symbol
    out_df["Batch_Index"] = batch_idx
    out_df["Batch_Start"] = start_str
    out_df["Batch_End"] = end_str

    # Create unique configuration hash/ID
    out_df["Config_ID"] = (
        "RSI_" + out_df["RSI_Len"].astype(str) + "_" +
        out_df["RSI_Levels"] + "_W" + out_df["RSI_Win"].astype(str) +
        "_MA" + out_df["RSI_MA"].astype(str) +
        "_SB" + out_df["Star_Body_Fac"].astype(str) +
        "_TB" + out_df["Third_Body_Fac"].astype(str) +
        "_Det" + out_df["Star_Detach"].astype(str) +
        "_Col" + out_df["Star_Color"].astype(str) +
        "_SL" + out_df["SL_Source"] +
        "_RR" + out_df["RR_Ratio"].astype(str)
    )

    # Sort and rank within this batch
    out_df.sort_values(by=["Batch_Passed", "Profit_Factor", "Return_Pct"], ascending=[False, False, False], inplace=True)
    out_df["Rank_In_Batch"] = np.arange(1, len(out_df) + 1)

    os.makedirs(output_dir, exist_ok=True)
    file_path = os.path.join(output_dir, f"{symbol}_batch_{batch_idx:02d}_{start_str}_{end_str}.parquet")
    out_df.to_parquet(file_path, index=False)

    passed_count = out_df["Batch_Passed"].sum()
    logger.info(
        f"[{symbol}] Batch #{batch_idx:02d} ({start_str} to {end_str} · {len(batch_df):,} bars) completed in {dur:.1f}s | "
        f"Evaluated {len(out_df):,} configs | Passed: {passed_count:,} ({passed_count/len(out_df)*100:.1f}%)"
    )
    return file_path


def run_10yr_batch_pipeline(pairs: List[str], batch_days: int = 180, max_batches: int = None, output_dir: str = "reports/batch_research"):
    os.makedirs(output_dir, exist_ok=True)
    cache_path = os.path.join(os.path.dirname(__file__), "data", "cache")
    loader = DukascopyDataLoader(cache_dir=cache_path)

    end_dt = datetime.now(timezone.utc)
    start_dt = end_dt - timedelta(days=3650)  # 10 full years

    logger.info("=" * 90)
    logger.info("STARTING 10-YEAR MULTI-BATCH RESEARCH PIPELINE")
    logger.info(f"Target Universe: {len(pairs)} Forex Pairs | Timeframe: 5m | Period: 10 Years (3,650 Days)")
    logger.info(f"Batch Duration: {batch_days} Days (~20 Batches per Pair)")
    logger.info("=" * 90)

    for p_idx, sym in enumerate(pairs, 1):
        logger.info(f"\n>>> [{p_idx}/{len(pairs)}] Loading 10-year 5m data for {sym}...")
        try:
            df = loader.load_pair(symbol=sym, interval="5m", start=start_dt, end=end_dt)
        except Exception as e:
            logger.error(f"Failed to load {sym}: {e}")
            continue

        if df.empty:
            logger.warning(f"Empty data for {sym}, skipping.")
            continue

        logger.info(f"Loaded {sym}: {len(df):,} bars ({df.index[0].date()} to {df.index[-1].date()})")
        batches = partition_into_180d_batches(df, batch_days=batch_days)
        if max_batches is not None and max_batches > 0:
            batches = batches[-max_batches:]
            logger.info(f"Filtered to most recent {len(batches)} batches for {sym}.")

        for b_idx, b_df, b_start, b_end in batches:
            batch_file = os.path.join(output_dir, f"{sym}_batch_{b_idx:02d}_{b_start}_{b_end}.parquet")
            if os.path.exists(batch_file):
                logger.info(f"[{sym}] Batch #{b_idx:02d} already computed at {batch_file}, skipping.")
                continue

            process_single_batch(
                symbol=sym,
                batch_idx=b_idx,
                batch_df=b_df,
                start_str=b_start,
                end_str=b_end,
                output_dir=output_dir,
            )

    logger.info("\nPipeline finished processing all available pairs and batches!")

    # Automatically aggregate and compute leaderboard
    try:
        from analyze_batch_leaderboard import compute_leaderboard
        logger.info("\nAggregating multi-batch leaderboard across all batches...")
        compute_leaderboard(batch_dir=output_dir, top_k=25)
    except Exception as e:
        logger.warning(f"Could not auto-aggregate leaderboard: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="10-Year Multi-Batch Cross-Asset Data Science Engine")
    parser.add_argument("--pairs", nargs="+", default=list(ALL_FX_PAIRS.keys()), help="Pairs to evaluate")
    parser.add_argument("--batch_days", type=int, default=180, help="Batch duration in days")
    parser.add_argument("--max_batches", type=int, default=None, help="Max recent batches per pair to evaluate")
    parser.add_argument("--output_dir", type=str, default="reports/batch_research", help="Output directory")

    args = parser.parse_args()
    run_10yr_batch_pipeline(pairs=args.pairs, batch_days=args.batch_days, max_batches=args.max_batches, output_dir=args.output_dir)
