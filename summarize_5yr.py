import os
import sys
import pandas as pd

def summarize(csv_path: str = "reports/five_year_analysis.csv"):
    if len(sys.argv) > 1:
        csv_path = sys.argv[1]
    if not os.path.exists(csv_path):
        print(f"File {csv_path} not found.")
        return

    df = pd.read_csv(csv_path)
    print("=" * 110)
    print("5-YEAR MULTI-YEAR PERFORMANCE BREAKDOWN (EUR/USD M5: 2021-2026)")
    print("Zero Spread · Zero Commission · Zero Slippage Reference Model")
    print("=" * 110)

    categories = [
        ("1_High_WinRate", "Tier 1: High Win-Rate Focus (>55-60% WR)"),
        ("2_Balanced_Freq", "Tier 2: Balanced Frequency (50-100 trades/yr)"),
        ("3_Active_DayTrading", "Tier 3: Active Day-Trading (>200 trades/yr)"),
        ("4_Target_2.0_RR", "Tier 4: Target 2.0 R:R Bracket (2:1 Asymmetric TP)"),
        ("5_Peak_ProfitFactor", "Tier 5: Peak Expectancy & Profit Factor"),
    ]

    for cat_id, cat_title in categories:
        sub = df[df["Category"] == cat_id].sort_values(
            by=["Return_Pct_5Yr" if "2.0" in cat_id else "Win_Rate_5Yr", "Profit_Factor_5Yr"],
            ascending=False
        ).drop_duplicates(subset=["RSI_Len", "RSI_Levels", "Star_Detach", "SL_Source", "RR_Ratio"]).head(3)

        print(f"\n>>> {cat_title} <<<")
        for i, (_, r) in enumerate(sub.iterrows(), 1):
            sl_name = "Star Candle" if r["SL_Source"] == "star_candle" else "Pattern Extreme"
            det_name = "Yes" if r["Star_Detach"] else "No"
            print(f"  Rank #{i}: RSI({int(r['RSI_Len'])}) [{r['RSI_Levels']}] | Detach={det_name} | SL={sl_name} | RR={r['RR_Ratio']:.1f}")
            print(f"    5Y Metrics: Trades={int(r['Total_Trades_5Yr'])} | WinRate={r['Win_Rate_5Yr']:.1f}% | PF={r['Profit_Factor_5Yr']:.2f} | Net Return={r['Return_Pct_5Yr']:+.1f}% | MaxDD={r['Max_Drawdown_Pct']:.1f}% | Expectancy={r['Expectancy_R_5Yr']:+.2f}R")
            print(f"    Annual Consistency:")
            print(f"      2021 (Q4):  {r['2021_WinRate']:.1f}% WR ({int(r['2021_Trades'])} trades)")
            print(f"      2022:       {r['2022_WinRate']:.1f}% WR ({int(r['2022_Trades'])} trades)")
            print(f"      2023:       {r['2023_WinRate']:.1f}% WR ({int(r['2023_Trades'])} trades)")
            print(f"      2024:       {r['2024_WinRate']:.1f}% WR ({int(r['2024_Trades'])} trades)")
            print(f"      2025:       {r['2025_WinRate']:.1f}% WR ({int(r['2025_Trades'])} trades)")
            print(f"      2026 (YTD): {r['2026_WinRate']:.1f}% WR ({int(r['2026_Trades'])} trades)")

if __name__ == "__main__":
    summarize()
