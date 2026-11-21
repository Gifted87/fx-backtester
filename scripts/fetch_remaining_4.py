"""
Robust downloader for the remaining 4 GBP cross pairs over the 10-year period (2016-09-28 to 2026-09-26).
Includes retries with backoff to handle any transient DNS or network hiccups.
"""
import os
import sys
import time
import logging
from datetime import datetime, timezone, timedelta

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from data.dukascopy_loader import DukascopyDataLoader

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("RetryDownloader")

loader = DukascopyDataLoader()
end_dt = datetime(2026, 9, 26, 21, 35, 32, tzinfo=timezone.utc)
start_dt = end_dt - timedelta(days=3650)

missing_pairs = ["GBPJPY", "GBPCAD", "GBPAUD", "GBPCHF"]

print("=" * 80)
print(f"DOWNLOADING 10-YEAR 5M DATA FOR {len(missing_pairs)} REMAINING GBP CROSS PAIRS")
print("=" * 80)

for sym in missing_pairs:
    cache_path = os.path.join("data", "cache", f"{sym}_5m_{start_dt.strftime('%Y%m%d')}_{end_dt.strftime('%Y%m%d')}.parquet")
    if os.path.exists(cache_path):
        print(f"[{sym}] Already cached at {cache_path}, skipping.")
        continue

    success = False
    for attempt in range(1, 6):
        try:
            print(f"[{sym}] Downloading attempt {attempt}/5...")
            t0 = time.time()
            df = loader.load_pair(sym, "5m", start=start_dt, end=end_dt)
            elapsed = time.time() - t0
            print(f"[{sym}] SUCCESS! Downloaded {len(df):,} bars in {elapsed:.1f}s -> {cache_path}")
            success = True
            break
        except Exception as e:
            print(f"[{sym}] Attempt {attempt} failed: {e}. Retrying in 5 seconds...")
            time.sleep(5)

    if not success:
        print(f"[{sym}] FAILED after 5 attempts!")

print("\nFinished downloading remaining pairs!")
