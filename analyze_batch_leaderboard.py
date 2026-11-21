"""
Batch Leaderboard Analysis Engine
Aggregates all 180-day batch parquet files across all pairs and 10 years of history.
Ranks configurations by the number of batches won / passed and identifies the most robust configuration.
"""

import os
import sys
import glob
import argparse
import pandas as pd
import numpy as np

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def compute_leaderboard(batch_dir: str = "reports/batch_research", top_k: int = 25):
    parquet_files = glob.glob(os.path.join(batch_dir, "*.parquet"))
    if not parquet_files:
        print(f"No batch parquet files found in {batch_dir}")
        return None

    print("=" * 115)
    print(f" AGGREGATING 10-YEAR MULTI-BATCH LEADERBOARD ({len(parquet_files)} batches discovered)")
    print("=" * 115)

    batch_dfs = []
    for f in parquet_files:
        try:
            b_df = pd.read_parquet(f)
            batch_dfs.append(b_df)
        except Exception as e:
            print(f"Error reading {f}: {e}")

    if not batch_dfs:
        print("No readable batch data.")
        return None

    full_df = pd.concat(batch_dfs, ignore_index=True)
    total_batches = full_df["Batch_Index"].nunique() if "Batch_Index" in full_df else len(parquet_files)
    total_pairs = full_df["Symbol"].nunique() if "Symbol" in full_df else 1
    total_batch_instances = len(parquet_files)

    print(f"Total Batches Processed: {total_batch_instances} across {total_pairs} currency pairs.")
    print(f"Total Rows in Evaluation Matrix: {len(full_df):,}")

    # Group by configuration parameters
    config_cols = [
        "Config_ID", "RSI_Len", "RSI_Levels", "RSI_Win", "RSI_MA",
        "Star_Body_Fac", "Third_Body_Fac", "Star_Detach", "Star_Color", "SL_Source", "RR_Ratio"
    ]

    agg_dict = {
        "Batch_Passed": ["count", "sum"],
        "Profit_Factor": ["mean", "median"],
        "Win_Rate_Pct": "mean",
        "Return_Pct": ["mean", "sum"],
        "Expectancy_R": "mean",
        "Max_Drawdown_Pct": "mean",
        "Total_Trades": ["mean", "sum"],
    }

    # Add Rank 1 count if available
    full_df["Is_Rank_1"] = full_df["Rank_In_Batch"] == 1
    full_df["Is_Top_5_Pct"] = full_df["Rank_In_Batch"] <= (len(full_df.groupby("Config_ID")) * 0.05)
    agg_dict["Is_Rank_1"] = "sum"
    agg_dict["Is_Top_5_Pct"] = "sum"

    grouped = full_df.groupby(config_cols).agg(agg_dict).reset_index()

    # Flatten column names
    flattened_cols = []
    for col in grouped.columns:
        if isinstance(col, tuple):
            if col[1] == "":
                flattened_cols.append(col[0])
            else:
                flattened_cols.append(f"{col[0]}_{col[1]}")
        else:
            flattened_cols.append(col)
    grouped.columns = flattened_cols

    # Renaming for clarity
    grouped.rename(columns={
        "Batch_Passed_count": "Total_Batches_Run",
        "Batch_Passed_sum": "Batches_Passed",
        "Is_Rank_1_sum": "Batches_Rank_1",
        "Is_Top_5_Pct_sum": "Batches_Top_5Pct",
        "Profit_Factor_mean": "Avg_Profit_Factor",
        "Win_Rate_Pct_mean": "Avg_Win_Rate",
        "Expectancy_R_mean": "Avg_Expectancy_R",
        "Return_Pct_mean": "Avg_Return_Pct",
        "Return_Pct_sum": "Total_Cum_Return_Pct",
        "Max_Drawdown_Pct_mean": "Avg_Max_DD",
        "Total_Trades_sum": "Total_Trades_All_Batches",
    }, inplace=True)

    grouped["Consistency_Score_Pct"] = round((grouped["Batches_Passed"] / grouped["Total_Batches_Run"]) * 100.0, 1)
    grouped["Avg_Win_Rate"] = round(grouped["Avg_Win_Rate"], 1)
    grouped["Avg_Profit_Factor"] = round(grouped["Avg_Profit_Factor"], 2)
    grouped["Avg_Expectancy_R"] = round(grouped["Avg_Expectancy_R"], 2)
    grouped["Avg_Return_Pct"] = round(grouped["Avg_Return_Pct"], 1)
    grouped["Total_Cum_Return_Pct"] = round(grouped["Total_Cum_Return_Pct"], 1)

    # Sort primarily by:
    # 1. Batches_Passed (highest number of successful batches)
    # 2. Consistency_Score_Pct
    # 3. Avg_Profit_Factor
    grouped.sort_values(
        by=["Batches_Passed", "Consistency_Score_Pct", "Avg_Profit_Factor", "Avg_Expectancy_R"],
        ascending=[False, False, False, False],
        inplace=True
    )

    out_csv = os.path.join(batch_dir, "master_leaderboard.csv")
    grouped.to_csv(out_csv, index=False)
    print(f"\nSaved Master Leaderboard to {out_csv} ({len(grouped):,} configurations ranked).")

    # Display Top K
    print("\n" + "=" * 125)
    print(f" TOP {top_k} CONFIGURATIONS PERFORMING BEST IN THE MOST NUMBER OF 180-DAY BATCHES")
    print("=" * 125)

    headers = ["Rank", "RSI", "Lvl", "Win", "Det", "SL", "R:R", "Pass/Total", "Consist%", "Avg WR", "Avg PF", "Avg Exp", "Cum Ret%"]
    rows = []
    for rank, (_, r) in enumerate(grouped.head(top_k).iterrows(), 1):
        rows.append([
            f"#{rank}",
            f"RSI({r['RSI_Len']})",
            str(r["RSI_Levels"]),
            str(r["RSI_Win"]),
            "Yes" if r["Star_Detach"] else "No",
            "Extr" if r["SL_Source"] == "pattern_extreme" else "Star",
            f"{r['RR_Ratio']:.1f}",
            f"{int(r['Batches_Passed'])}/{int(r['Total_Batches_Run'])}",
            f"{r['Consistency_Score_Pct']:.1f}%",
            f"{r['Avg_Win_Rate']:.1f}%",
            f"{r['Avg_Profit_Factor']:.2f}",
            f"{r['Avg_Expectancy_R']:+.2f}R",
            f"{r['Total_Cum_Return_Pct']:+.1f}%",
        ])

    widths = [max(len(str(val)) for val in [h] + [r[i] for r in rows]) + 2 for i, h in enumerate(headers)]
    sep = "+" + "+".join("-" * w for w in widths) + "+"
    hdr = "|" + "|".join(f" {h}".ljust(w) for h, w in zip(headers, widths)) + "|"

    print(sep)
    print(hdr)
    print(sep)
    for r in rows:
        print("|" + "|".join(f" {v}".ljust(w) for v, w in zip(r, widths)) + "|")
    print(sep + "\n")

    return grouped


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyze 10-Year Multi-Batch Leaderboard")
    parser.add_argument("--batch_dir", type=str, default="reports/batch_research", help="Directory with batch parquets")
    parser.add_argument("--top_k", type=int, default=25, help="Top K to display")
    args = parser.parse_args()

    compute_leaderboard(batch_dir=args.batch_dir, top_k=args.top_k)
