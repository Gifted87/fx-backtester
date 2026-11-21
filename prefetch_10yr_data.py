"""
Multi-Threaded 10-Year Data Prefetcher for 28 Major & Minor Forex Pairs
Downloads and caches 10 years of 5m bars in parallel using thread pool.
"""

import os
import sys
import time
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from config.strategy_config import ALL_FX_PAIRS
from data.dukascopy_loader import DukascopyDataLoader


def prefetch_pair(sym: str, days: int = 3650):
    cache_path = os.path.join(os.path.dirname(__file__), "data", "cache")
    end_dt = datetime.now(timezone.utc)
    start_dt = end_dt - timedelta(days=days)
    s_tag = start_dt.strftime("%Y%m%d")
    e_tag = end_dt.strftime("%Y%m%d")
    target_parquet = os.path.join(cache_path, f"{sym.upper()}_5m_{s_tag}_{e_tag}.parquet")

    if os.path.exists(target_parquet):
        print(f"[{sym}] Already cached at {target_parquet}, skipping.")
        return sym, 0, True

    loader = DukascopyDataLoader(cache_dir=cache_path)
    t0 = time.time()
    try:
        print(f"[{sym}] Starting 10-year download...")
        df = loader.load_pair(symbol=sym, interval="5m", start=start_dt, end=end_dt)
        dur = time.time() - t0
        print(f"[{sym}] Finished in {dur:.1f}s: {len(df):,} bars from {df.index[0].date()} to {df.index[-1].date()}")
        return sym, len(df), True
    except Exception as e:
        print(f"[{sym}] Error: {e}")
        return sym, 0, False


def main():
    pairs = list(ALL_FX_PAIRS.keys())
    print("=" * 80)
    print(f"PREFETCHING 10-YEAR 5M DATA FOR {len(pairs)} FOREX PAIRS")
    print("=" * 80)

    # Use 4 parallel workers so Dukascopy rate limits are respected without getting blocked
    with ThreadPoolExecutor(max_workers=4) as ex:
        futures = {ex.submit(prefetch_pair, p): p for p in pairs}
        for fut in as_completed(futures):
            p = futures[fut]
            try:
                sym, bars, ok = fut.result()
            except Exception as e:
                print(f"[{p}] Exception in worker: {e}")

    print("\nAll downloads completed!")


if __name__ == "__main__":
    main()
