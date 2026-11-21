"""
Per-Pair Best Parameter Configuration Analysis & Documentation Engine
Computes and documents the exact optimal configuration for each currency pair.
"""

import os
import sys
import glob
import pandas as pd
import numpy as np

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BATCH_DIR = "reports/batch_research"
OUT_CSV = "reports/per_pair_best_configurations.csv"
OUT_MD = "reports/per_pair_best_configurations.md"

def analyze_per_pair():
    parquet_files = glob.glob(os.path.join(BATCH_DIR, "*.parquet"))
    print(f"Total Completed Batch Files Found: {len(parquet_files)}")
    
    # Group files by pair
    pair_files = {}
    for f in parquet_files:
        bn = os.path.basename(f)
        parts = bn.split("_")
        pair = parts[0]
        if pair not in pair_files:
            pair_files[pair] = []
        pair_files[pair].append(f)
        
    print(f"Analyzing {len(pair_files)} Currency Pairs...")
    
    results = []
    
    for pair in sorted(pair_files.keys()):
        p_files = pair_files[pair]
        print(f"--> Processing {pair} ({len(p_files)} batches)...", flush=True)
        
        # Load batches for this pair
        batch_dfs = []
        for pf in p_files:
            try:
                b_df = pd.read_parquet(pf, columns=[
                    'Config_ID', 'RSI_Len', 'RSI_Levels', 'RSI_Win', 'RSI_MA',
                    'Star_Body_Fac', 'Third_Body_Fac', 'Star_Detach', 'Star_Color',
                    'SL_Source', 'RR_Ratio', 'Batch_Passed', 'Profit_Factor',
                    'Win_Rate_Pct', 'Return_Pct', 'Total_Trades', 'Expectancy_R'
                ])
                batch_dfs.append(b_df)
            except Exception as e:
                print(f"    Error loading {pf}: {e}")
                
        if not batch_dfs:
            continue
            
        full_p_df = pd.concat(batch_dfs, ignore_index=True)
        total_batches = len(p_files)
        
        config_cols = [
            'Config_ID', 'RSI_Len', 'RSI_Levels', 'RSI_Win', 'RSI_MA',
            'Star_Body_Fac', 'Third_Body_Fac', 'Star_Detach', 'Star_Color',
            'SL_Source', 'RR_Ratio'
        ]
        
        grouped = full_p_df.groupby(config_cols).agg({
            'Batch_Passed': ['count', 'sum'],
            'Profit_Factor': 'mean',
            'Win_Rate_Pct': 'mean',
            'Return_Pct': ['mean', 'sum'],
            'Expectancy_R': 'mean',
            'Total_Trades': 'sum'
        }).reset_index()
        
        grouped.columns = [
            'Config_ID', 'RSI_Len', 'RSI_Levels', 'RSI_Win', 'RSI_MA',
            'Star_Body_Fac', 'Third_Body_Fac', 'Star_Detach', 'Star_Color',
            'SL_Source', 'RR_Ratio',
            'Batches_Run', 'Batches_Passed', 'Avg_PF', 'Avg_WR',
            'Avg_Return', 'Total_Return', 'Avg_Exp', 'Total_Trades'
        ]
        
        grouped['Consistency_Pct'] = (grouped['Batches_Passed'] / grouped['Batches_Run']) * 100.0
        
        # Rank by: Batches_Passed -> Consistency_Pct -> Avg_PF -> Total_Return
        grouped.sort_values(
            by=['Batches_Passed', 'Consistency_Pct', 'Avg_PF', 'Total_Return'],
            ascending=[False, False, False, False],
            inplace=True
        )
        
        best = grouped.iloc[0]
        
        results.append({
            'Pair': pair,
            'Batches_Run': int(best['Batches_Run']),
            'Batches_Passed': int(best['Batches_Passed']),
            'Consistency_Pct': round(best['Consistency_Pct'], 1),
            'RSI_Len': int(best['RSI_Len']),
            'RSI_Levels': best['RSI_Levels'],
            'RSI_Win': int(best['RSI_Win']),
            'RSI_MA': bool(best['RSI_MA']),
            'Star_Body_Fac': float(best['Star_Body_Fac']),
            'Third_Body_Fac': float(best['Third_Body_Fac']),
            'Star_Detach': bool(best['Star_Detach']),
            'Star_Color': bool(best['Star_Color']),
            'SL_Source': best['SL_Source'],
            'RR_Ratio': float(best['RR_Ratio']),
            'Avg_Win_Rate': round(best['Avg_WR'], 1),
            'Avg_Profit_Factor': round(best['Avg_PF'], 2),
            'Total_Cumulative_Return': round(best['Total_Return'], 1),
            'Avg_Expectancy_R': round(best['Avg_Exp'], 2),
            'Total_Trades': int(best['Total_Trades']),
        })
        
    res_df = pd.DataFrame(results)
    res_df.to_csv(OUT_CSV, index=False)
    print(f"\nSaved CSV to {OUT_CSV}")
    
    # Generate Markdown Report
    md_content = "# Optimal Parameter Configurations by Currency Pair\n\n"
    md_content += "Empirical analysis identifying the single best, most consistent parameter configuration for each Forex pair across 180-day market batches.\n\n"
    md_content += "### Summary Table of Best Configuration per Pair\n\n"
    md_content += "| Pair | Batches Won | Consistency | Optimal RSI | Geometry (Star/3rd/Detach) | SL & R:R | Avg Win Rate | Avg PF | Total Return | Total Trades |\n"
    md_content += "| :--- | :---: | :---: | :--- | :--- | :--- | :---: | :---: | :---: | :---: |\n"
    
    for _, r in res_df.iterrows():
        sl_short = "Extreme" if r['SL_Source'] == "pattern_extreme" else "Star"
        det_str = "Det=Yes" if r['Star_Detach'] else "Det=No"
        col_str = "Col=Yes" if r['Star_Color'] else "Col=No"
        geom = f"SB={r['Star_Body_Fac']}, 3B={r['Third_Body_Fac']}, {det_str}, {col_str}"
        rsi_str = f"RSI({r['RSI_Len']}, {r['RSI_Levels']}, W={r['RSI_Win']}, MA={r['RSI_MA']})"
        sl_rr = f"{sl_short} @ {r['RR_Ratio']}R"
        
        md_content += f"| **{r['Pair']}** | **{r['Batches_Passed']} / {r['Batches_Run']}** | **{r['Consistency_Pct']}%** | `{rsi_str}` | `{geom}` | `{sl_rr}` | **{r['Avg_Win_Rate']}%** | **{r['Avg_Profit_Factor']}** | **{r['Total_Cumulative_Return']:+0.1f}%** | {r['Total_Trades']} |\n"
        
    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write(md_content)
    print(f"Saved Markdown Report to {OUT_MD}")
    
    # Print formatted console table
    print("\n" + "=" * 120)
    print(" BEST PARAMETER CONFIGURATION PER PAIR SUMMARY")
    print("=" * 120)
    for _, r in res_df.iterrows():
        print(f"[{r['Pair']:<6}] Won {r['Batches_Passed']}/{r['Batches_Run']} ({r['Consistency_Pct']}%) | RSI({r['RSI_Len']} {r['RSI_Levels']} W={r['RSI_Win']} MA={r['RSI_MA']}) | SB={r['Star_Body_Fac']} 3B={r['Third_Body_Fac']} Det={r['Star_Detach']} | SL={r['SL_Source']} RR={r['RR_Ratio']}R | WR: {r['Avg_Win_Rate']}% | PF: {r['Avg_Profit_Factor']} | Ret: {r['Total_Cumulative_Return']:+.1f}% | Trades: {r['Total_Trades']}")
    print("=" * 120)

if __name__ == "__main__":
    analyze_per_pair()
