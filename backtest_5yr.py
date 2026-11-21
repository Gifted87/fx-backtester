"""
5-Year Multi-Year Validation Engine for Star+RSI Reversal Strategy.
Tests the top 10% of configurations across each category over 5 years (2021 - 2026).
Computes full 5-year Win Rate, Profit Factor, Max Drawdown, and Year-by-Year breakdown.
"""

import os
import sys
import time
import argparse
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Tuple

# Ensure safe console printing on Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

import numpy as np
import pandas as pd

from config.strategy_config import ALL_FX_PAIRS, MAJOR_FX_PAIRS
from data.dukascopy_loader import DukascopyDataLoader
from indicators.rsi import calc_wilder_rsi
from optimize import FastOptimizer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("5YrValidator")


def extract_top_decile_configs(csv_path: str = "reports/optimization_results.csv") -> Dict[str, pd.DataFrame]:
    """Extracts the top 10% of configurations across 5 distinct categories."""
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Optimization results file not found: {csv_path}")

    df = pd.read_csv(csv_path)
    logger.info(f"Loaded {len(df):,} configurations from {csv_path}")

    categories = {}

    # Category 1: High Win-Rate (>60% WR)
    cat1 = df[df["Win_Rate_Pct"] >= 60.0].sort_values(by=["Win_Rate_Pct", "Profit_Factor"], ascending=False)
    n1 = max(5, int(len(cat1) * 0.10))
    categories["1_High_WinRate"] = cat1.head(n1)

    # Category 2: Balanced Frequency (50 - 100 trades/yr)
    cat2 = df[(df["Total_Trades"] >= 50) & (df["Total_Trades"] <= 100)].sort_values(by=["Win_Rate_Pct", "Profit_Factor"], ascending=False)
    n2 = max(5, int(len(cat2) * 0.10))
    categories["2_Balanced_Freq"] = cat2.head(n2)

    # Category 3: Active Day-Trading (100 - 250 trades/yr)
    cat3 = df[(df["Total_Trades"] >= 100) & (df["Total_Trades"] <= 250)].sort_values(by=["Profit_Factor", "Win_Rate_Pct"], ascending=False)
    n3 = max(5, int(len(cat3) * 0.10))
    categories["3_Active_DayTrading"] = cat3.head(n3)

    # Category 4: Pure 2.0 R:R Target Bracket
    cat4 = df[df["RR_Ratio"] == 2.0].sort_values(by=["Win_Rate_Pct", "Profit_Factor"], ascending=False)
    n4 = max(5, int(len(cat4) * 0.10))
    categories["4_Target_2.0_RR"] = cat4.head(n4)

    # Category 5: Peak Expectancy & Profit Factor
    cat5 = df.sort_values(by=["Profit_Factor", "Return_Pct"], ascending=False)
    n5 = max(5, int(len(cat5) * 0.10))
    categories["5_Peak_ProfitFactor"] = cat5.head(n5)

    for c_name, c_df in categories.items():
        logger.info(f"Category '{c_name}': Extracted top 10% ({len(c_df):,} candidates)")

    return categories


class MultiYearSimulator:
    def __init__(self, df: pd.DataFrame, pip_size: float = 0.0001):
        self.df = df
        self.opt = FastOptimizer(df, pip_size=pip_size)
        self.pip = pip_size
        self.years = df.index.year.values
        self.unique_years = sorted(list(set(self.years)))

    def simulate_config_detailed(
        self,
        rsi_len: int,
        rsi_os: float,
        rsi_ob: float,
        rsi_win: int,
        rsi_ma_en: bool,
        star_bf: float,
        third_bf: float,
        star_det: bool,
        star_col: bool,
        sl_source: str,
        sl_buffer: float,
        rr: float,
    ) -> Dict[str, Any]:
        """Runs 5-year simulation and computes year-by-year breakdown and max drawdown."""
        # 1. RSI mask
        close_series = pd.Series(self.opt.closes)
        rsi_vals = calc_wilder_rsi(close_series, period=rsi_len).values

        valid = ~np.isnan(rsi_vals)
        valid_prev = np.roll(valid, 1); valid_prev[0] = False
        r_prev = np.roll(rsi_vals, 1); r_prev[0] = np.nan
        both_valid = valid & valid_prev

        cross_up = both_valid & (r_prev < rsi_os) & (rsi_vals >= rsi_os)
        cross_dn = both_valid & (r_prev > rsi_ob) & (rsi_vals <= rsi_ob)

        if rsi_ma_en:
            ma_vals = pd.Series(rsi_vals).rolling(14).mean().values
            ma_valid = ~np.isnan(ma_vals)
            cross_up = cross_up & ma_valid & (rsi_vals > ma_vals)
            cross_dn = cross_dn & ma_valid & (rsi_vals < ma_vals)

        if rsi_win == 0:
            b_rsi = cross_up
            s_rsi = cross_dn
        else:
            b_rsi = np.zeros(self.opt.n, dtype=bool)
            s_rsi = np.zeros(self.opt.n, dtype=bool)
            last_dir = np.zeros(self.opt.n, dtype=int)
            last_age = np.full(self.opt.n, 999999, dtype=int)

            cur_dir = 0
            cur_age = 999999
            for i in range(self.opt.n):
                if cross_up[i] and not cross_dn[i]:
                    cur_dir = 1; cur_age = 0
                elif cross_dn[i] and not cross_up[i]:
                    cur_dir = -1; cur_age = 0
                else:
                    if cur_dir != 0: cur_age += 1
                last_dir[i] = cur_dir
                last_age[i] = cur_age

            b_rsi = (last_dir == 1) & (last_age <= rsi_win)
            s_rsi = (last_dir == -1) & (last_age <= rsi_win)

        # 2. Star pattern mask
        middle_small = (
            (self.opt.body2 <= self.opt.body1 * star_bf) &
            (self.opt.body2 <= self.opt.body3 * star_bf) &
            (self.opt.body2 <= self.opt.range2 * 0.40)
        )
        third_real = self.opt.body3 >= self.opt.body1 * third_bf
        first_leg_big = self.opt.body1 >= self.opt.body3 * 0.50

        det_bull = np.ones(self.opt.n, dtype=bool) if not star_det else self.opt.detach_bull
        det_bear = np.ones(self.opt.n, dtype=bool) if not star_det else self.opt.detach_bear

        if not star_col:
            col_bull = np.ones(self.opt.n, dtype=bool)
            col_bear = np.ones(self.opt.n, dtype=bool)
        else:
            amb = np.isnan(self.opt.star_body_pct) | (self.opt.star_body_pct < 10.0)
            col_bull = amb | self.opt.star_bull
            col_bear = amb | self.opt.star_bear

        pen_bull = self.opt.third_bull & (self.opt.c0 > (np.maximum(self.opt.o2, self.opt.c2) - self.opt.body1 * 0.50))
        pen_bear = self.opt.third_bear & (self.opt.c0 < (np.minimum(self.opt.o2, self.opt.c2) + self.opt.body1 * 0.50))

        m_star = (
            self.opt.first_bear & self.opt.third_bull & middle_small &
            third_real & first_leg_big & col_bull &
            pen_bull & det_bull & self.opt.doji_ok
        )
        e_star = (
            self.opt.first_bull & self.opt.third_bear & middle_small &
            third_real & first_leg_big & col_bear &
            pen_bear & det_bear & self.opt.doji_ok
        )

        final_bull = m_star & b_rsi
        final_bear = e_star & s_rsi

        # 3. Simulate trades
        buf = sl_buffer * self.pip
        sig_indices = np.where(final_bull | final_bear)[0]

        if len(sig_indices) == 0:
            return None

        trades = []
        equity = 10000.0
        peak_equity = 10000.0
        max_drawdown_pct = 0.0
        next_avail_bar = 0

        for idx in sig_indices:
            if idx < next_avail_bar or idx + 1 >= self.opt.n:
                continue

            entry_idx = idx + 1
            o_entry = self.opt.opens[entry_idx]
            d = 1 if final_bull[idx] else -1

            if sl_source == "pattern_extreme":
                sl_raw = self.opt.pattern_low[idx] if d == 1 else self.opt.pattern_high[idx]
            else:
                sl_raw = self.opt.star_low[idx] if d == 1 else self.opt.star_high[idx]

            end_idx = min(entry_idx + 120, self.opt.n)
            trade_year = self.years[entry_idx]

            if d == 1:
                sl = sl_raw - buf
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

                if t_bar < s_bar:
                    won = True; bars = t_bar
                else:
                    won = False; bars = s_bar

            else:  # Short
                sl = sl_raw + buf
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

                if t_bar < s_bar:
                    won = True; bars = t_bar
                else:
                    won = False; bars = s_bar

            next_avail_bar = entry_idx + bars + 1
            r_mult = rr if won else -1.0
            pnl_usd = (equity * 0.01) * r_mult
            equity += pnl_usd

            if equity > peak_equity:
                peak_equity = equity
            dd = (peak_equity - equity) / peak_equity * 100.0
            if dd > max_drawdown_pct:
                max_drawdown_pct = dd

            trades.append({
                "year": trade_year,
                "won": won,
                "r_mult": r_mult,
                "pnl": pnl_usd,
            })

        total_trades = len(trades)
        if total_trades < 10:
            return None

        wins = sum(1 for t in trades if t["won"])
        losses = total_trades - wins
        win_rate = (wins / total_trades) * 100.0

        gross_profit = sum(t["pnl"] for t in trades if t["won"])
        gross_loss = abs(sum(t["pnl"] for t in trades if not t["won"]))
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (99.0 if gross_profit > 0 else 0.0)
        net_profit = equity - 10000.0
        return_pct = (net_profit / 10000.0) * 100.0
        expectancy_r = np.mean([t["r_mult"] for t in trades])

        # Year by year breakdown
        t_df = pd.DataFrame(trades)
        yearly_summary = {}
        for yr in self.unique_years:
            yr_t = t_df[t_df["year"] == yr]
            if len(yr_t) > 0:
                y_w = yr_t["won"].sum()
                y_n = len(yr_t)
                y_wr = (y_w / y_n) * 100.0
                yearly_summary[f"{yr}_Trades"] = y_n
                yearly_summary[f"{yr}_WinRate"] = round(y_wr, 1)
            else:
                yearly_summary[f"{yr}_Trades"] = 0
                yearly_summary[f"{yr}_WinRate"] = 0.0

        return {
            "Total_Trades_5Yr": total_trades,
            "Wins_5Yr": wins,
            "Losses_5Yr": losses,
            "Win_Rate_5Yr": round(win_rate, 1),
            "Profit_Factor_5Yr": round(profit_factor, 2),
            "Return_Pct_5Yr": round(return_pct, 1),
            "Max_Drawdown_Pct": round(max_drawdown_pct, 1),
            "Expectancy_R_5Yr": round(expectancy_r, 2),
            **yearly_summary,
        }


def run_5yr_validation(args):
    logger.info(f"Loading 5-year data for {args.symbol} ({args.interval}) from {args.days} days history...")
    cache_path = os.path.join(os.path.dirname(__file__), "data", "cache")
    loader = DukascopyDataLoader(cache_dir=cache_path)

    end_dt = datetime.now(timezone.utc)
    start_dt = end_dt - timedelta(days=args.days)

    df = loader.load_pair(
        symbol=args.symbol,
        interval=args.interval,
        start=start_dt,
        end=end_dt,
        force_refresh=args.refresh,
    )

    if df.empty:
        logger.error("Failed to load 5-year data.")
        return

    logger.info(f"Loaded 5-Year Dataset: {len(df):,} bars from {df.index[0].date()} to {df.index[-1].date()}")
    inst = ALL_FX_PAIRS.get(args.symbol.upper())
    pip_size = inst.pip_size if inst else (0.01 if "JPY" in args.symbol else 0.0001)

    categories = extract_top_decile_configs(args.results_csv)
    sim = MultiYearSimulator(df, pip_size=pip_size)

    validated_results = []

    for cat_name, cat_df in categories.items():
        logger.info(f"\n=======================================================")
        logger.info(f"Evaluating Category: {cat_name} ({len(cat_df)} candidate configurations)...")
        logger.info(f"=======================================================")

        # Deduplicate configs
        unique_configs = cat_df.drop_duplicates(subset=[
            "RSI_Len", "RSI_Levels", "RSI_Win", "Star_Body_Fac", "Third_Body_Fac", "Star_Detach", "Star_Color", "SL_Source", "RR_Ratio"
        ]).head(args.top_k)

        for idx, (_, r) in enumerate(unique_configs.iterrows(), 1):
            r_os, r_ob = [float(x) for x in str(r["RSI_Levels"]).split("/")]
            res = sim.simulate_config_detailed(
                rsi_len=int(r["RSI_Len"]),
                rsi_os=r_os,
                rsi_ob=r_ob,
                rsi_win=int(r["RSI_Win"]),
                rsi_ma_en=bool(r["RSI_MA"]),
                star_bf=float(r["Star_Body_Fac"]),
                third_bf=float(r["Third_Body_Fac"]),
                star_det=bool(r["Star_Detach"]),
                star_col=bool(r["Star_Color"]),
                sl_source=str(r["SL_Source"]),
                sl_buffer=float(r.get("SL_Buffer", 0.0)),
                rr=float(r["RR_Ratio"]),
            )

            if res:
                validated_results.append({
                    "Category": cat_name,
                    "Symbol": args.symbol,
                    "RSI_Len": int(r["RSI_Len"]),
                    "RSI_Levels": r["RSI_Levels"],
                    "RSI_Win": int(r["RSI_Win"]),
                    "Star_Body_Fac": r["Star_Body_Fac"],
                    "Third_Body_Fac": r["Third_Body_Fac"],
                    "Star_Detach": r["Star_Detach"],
                    "SL_Source": r["SL_Source"],
                    "RR_Ratio": r["RR_Ratio"],
                    **res,
                })

    if not validated_results:
        logger.warning("No configurations produced valid 5-year simulations.")
        return

    out_df = pd.DataFrame(validated_results)
    out_df.sort_values(by=["Category", "Win_Rate_5Yr", "Profit_Factor_5Yr"], ascending=[True, False, False], inplace=True)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    out_df.to_csv(args.out, index=False)
    logger.info(f"\nSaved 5-Year Multi-Year Validation Report ({len(out_df):,} configurations) to {args.out}")

    # Display Category Summaries
    print("\n" + "=" * 115)
    print(f" [5-YEAR MULTI-YEAR VALIDATION SUMMARY] ({args.symbol} · M5 · 2021 to 2026)")
    print("=" * 115)

    headers = ["Category", "RSI", "Lvl", "Det", "SL", "R:R", "5Y Trd", "5Y WR", "5Y PF", "5Y Ret%", "MaxDD%", "Avg Exp"]
    disp_rows = []
    for _, r in out_df.groupby("Category").head(3).iterrows():
        disp_rows.append([
            r["Category"][:15],
            str(r["RSI_Len"]),
            r["RSI_Levels"],
            "Yes" if r["Star_Detach"] else "No",
            "Extr" if r["SL_Source"] == "pattern_extreme" else "Star",
            f"{r['RR_Ratio']:.1f}",
            str(r["Total_Trades_5Yr"]),
            f"{r['Win_Rate_5Yr']:.1f}%",
            f"{r['Profit_Factor_5Yr']:.2f}",
            f"{r['Return_Pct_5Yr']:+.1f}%",
            f"{r['Max_Drawdown_Pct']:.1f}%",
            f"{r['Expectancy_R_5Yr']:+.2f}R",
        ])

    widths = [max(len(str(val)) for val in [h] + [r[i] for r in disp_rows]) + 2 for i, h in enumerate(headers)]
    sep = "+" + "+".join("-" * w for w in widths) + "+"
    hdr = "|" + "|".join(f" {h}".ljust(w) for h, w in zip(headers, widths)) + "|"

    print(sep)
    print(hdr)
    print(sep)
    for r in disp_rows:
        print("|" + "|".join(f" {v}".ljust(w) for v, w in zip(r, widths)) + "|")
    print(sep + "\n")


def main():
    parser = argparse.ArgumentParser(description="5-Year Validation of Top Decile Configurations")
    parser.add_argument("--symbol", type=str, default="EURUSD", help="Forex symbol (default: EURUSD)")
    parser.add_argument("--interval", type=str, default="5m", help="Timeframe (default: 5m)")
    parser.add_argument("--days", type=int, default=1825, help="History in days (default: 1825 = 5 years)")
    parser.add_argument("--top_k", type=int, default=15, help="Number of candidate configurations per category (default: 15)")
    parser.add_argument("--results_csv", type=str, default="reports/optimization_results.csv", help="Source optimization results")
    parser.add_argument("--out", type=str, default="reports/five_year_analysis.csv", help="Output CSV path")
    parser.add_argument("--refresh", action="store_true", help="Force refresh data download")

    args = parser.parse_args()
    run_5yr_validation(args)


if __name__ == "__main__":
    main()
