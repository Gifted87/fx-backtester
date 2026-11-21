"""
Dukascopy Market Data Downloader & Cache Manager.
Fetches high-quality bid/ask Forex data using dukascopy_python and caches locally as Parquet.
"""

import os
import sys
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pandas as pd
import dukascopy_python as dp
from dukascopy_python import instruments

from config.strategy_config import ALL_FX_PAIRS, MAJOR_FX_PAIRS, MINOR_FX_PAIRS, InstrumentSpec

logger = logging.getLogger(__name__)

# Mapping interval strings to dukascopy constants
TIMEFRAME_MAP = {
    "1m": dp.INTERVAL_MIN_1,
    "5m": dp.INTERVAL_MIN_5,
    "15m": dp.INTERVAL_MIN_15,
    "30m": dp.INTERVAL_MIN_30,
    "1h": dp.INTERVAL_HOUR_1,
    "4h": dp.INTERVAL_HOUR_4,
    "1d": dp.INTERVAL_DAY_1,
}

CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache")


class DukascopyDataLoader:
    def __init__(self, cache_dir: str = CACHE_DIR):
        self.cache_dir = cache_dir
        os.makedirs(self.cache_dir, exist_ok=True)

    def _get_cache_filepath(self, symbol: str, interval: str, start: datetime, end: datetime) -> str:
        s_str = start.strftime("%Y%m%d")
        e_str = end.strftime("%Y%m%d")
        filename = f"{symbol}_{interval}_{s_str}_{e_str}.parquet"
        return os.path.join(self.cache_dir, filename)

    def load_pair(
        self,
        symbol: str,
        interval: str = "1h",
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        offer_side: str = dp.OFFER_SIDE_BID,
        force_refresh: bool = False,
    ) -> pd.DataFrame:
        """
        Loads OHLCV data for a given forex symbol.
        Checks local cache first; if not present or force_refresh is True, fetches from Dukascopy.
        """
        symbol = symbol.upper()
        if symbol not in ALL_FX_PAIRS:
            raise ValueError(f"Unknown symbol '{symbol}'. Supported: {list(ALL_FX_PAIRS.keys())}")

        spec = ALL_FX_PAIRS[symbol]
        dp_instrument = getattr(instruments, spec.dukascopy_symbol)
        dp_interval = TIMEFRAME_MAP.get(interval.lower())
        if not dp_interval:
            raise ValueError(f"Unsupported interval '{interval}'. Choose from {list(TIMEFRAME_MAP.keys())}")

        if end is None:
            end = datetime.now(timezone.utc)
        elif end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)

        if start is None:
            # Default to last 365 days
            start = end - timedelta(days=365)
        elif start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)

        cache_file = self._get_cache_filepath(symbol, interval, start, end)

        if not force_refresh:
            if os.path.exists(cache_file):
                logger.info(f"Loading {symbol} ({interval}) from cache: {cache_file}")
                df = pd.read_parquet(cache_file)
                return self._normalize_dataframe(df)

            # Fallback: check for any existing cached multi-year parquet
            import glob
            cached_candidates = glob.glob(os.path.join(self.cache_dir, f"{symbol}_{interval}_*.parquet"))
            if cached_candidates:
                largest_file = max(cached_candidates, key=os.path.getsize)
                try:
                    df_candidate = pd.read_parquet(largest_file)
                    df_candidate = self._normalize_dataframe(df_candidate)
                    if len(df_candidate) >= 50000:
                        logger.info(f"Loading {symbol} ({interval}) from multi-year cache: {largest_file} ({len(df_candidate):,} bars)")
                        return df_candidate
                except Exception as e:
                    logger.warning(f"Error reading candidate cache {largest_file}: {e}")


        logger.info(f"Fetching {symbol} ({interval}) from Dukascopy: {start} -> {end}")
        try:
            raw_df = dp.fetch(
                instrument=dp_instrument,
                interval=dp_interval,
                offer_side=offer_side,
                start=start,
                end=end,
                max_retries=5,
            )
        except Exception as e:
            logger.error(f"Error fetching data from Dukascopy for {symbol}: {e}")
            raise

        if raw_df is None or raw_df.empty:
            raise ValueError(f"No data returned by Dukascopy for {symbol} ({start} to {end})")

        df = self._normalize_dataframe(raw_df)

        # Cache locally
        try:
            df.to_parquet(cache_file)
            logger.info(f"Cached {len(df)} bars to {cache_file}")
        except Exception as e:
            logger.warning(f"Could not write cache file {cache_file}: {e}")

        return df

    def _normalize_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Normalizes column names to lowercase ['open', 'high', 'low', 'close', 'volume'],
        sorts ascending by index, and removes duplicate timestamps.
        """
        df = df.copy()
        df.columns = [str(c).strip().lower() for c in df.columns]

        # Ensure index is datetime UTC
        if not isinstance(df.index, pd.DatetimeIndex):
            if 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
                df.set_index('timestamp', inplace=True)
            elif 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date'], utc=True)
                df.set_index('date', inplace=True)

        if df.index.tz is None:
            df.index = df.index.tz_localize('UTC')
        else:
            df.index = df.index.tz_convert('UTC')

        df = df[~df.index.duplicated(keep='first')]
        df.sort_index(inplace=True)

        # Ensure float types
        for col in ['open', 'high', 'low', 'close', 'volume']:
            if col in df.columns:
                df[col] = df[col].astype(float)

        return df

    def load_all_majors(
        self,
        interval: str = "1h",
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        force_refresh: bool = False,
    ) -> Dict[str, pd.DataFrame]:
        """
        Downloads / loads all 7 major FX pairs.
        """
        data = {}
        for sym in MAJOR_FX_PAIRS:
            logger.info(f"Loading pair: {sym}")
            data[sym] = self.load_pair(
                symbol=sym,
                interval=interval,
                start=start,
                end=end,
                force_refresh=force_refresh,
            )
        return data


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    loader = DukascopyDataLoader()
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(days=10)
    df = loader.load_pair("EURUSD", "1h", start=start_time, end=end_time)
    print(df.tail())
