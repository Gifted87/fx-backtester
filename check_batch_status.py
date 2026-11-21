import glob
import os
import pandas as pd

batch_files = glob.glob('reports/batch_research/*.parquet')
print(f'Total Completed Batch Parquet Files: {len(batch_files)}')

pairs = set()
for bf in batch_files:
    fname = os.path.basename(bf)
    p = fname.split('_')[0]
    pairs.add(p)
print(f'Pairs covered: {sorted(list(pairs))}')

leaderboard_path = 'reports/batch_research/master_leaderboard.csv'
if os.path.exists(leaderboard_path):
    df = pd.read_csv(leaderboard_path)
    print(f'Master Leaderboard Configurations: {len(df):,}')
    max_b = df['Total_Batches_Run'].max()
    print(f'Max Batches Evaluated per Configuration: {max_b}')
    print('\n--- TOP 10 CONFIGURATIONS (BY CONSISTENCY & BATCHES WON) ---')
    cols = ['Config_ID', 'Total_Batches_Run', 'Batches_Passed', 'Consistency_Score_Pct', 'Avg_Profit_Factor', 'Avg_Win_Rate', 'Avg_Return_Pct', 'Total_Cum_Return_Pct']
    print(df[cols].head(10).to_string())
