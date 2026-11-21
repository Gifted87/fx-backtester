"""
Main CLI Runner for Forex Star+RSI Strategy Backtester.
Coordinates Dukascopy data downloading, signal generation, backtesting across major pairs,
and rich analytics generation.
"""

import os
import sys
import argparse
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict

# Ensure UTF-8 stdout encoding on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Ensure project root is in path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

import pandas as pd
from config.strategy_config import StrategyConfig, BacktestConfig, MAJOR_FX_PAIRS
from data.dukascopy_loader import DukascopyDataLoader
from strategy.star_rsi_strategy import StarRsiStrategy
from backtest.engine import BacktestEngine, BacktestResult
from backtest.metrics import BacktestMetrics

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("FX-Backtester")


def run_single_pair(
    symbol: str,
    strat_cfg: StrategyConfig,
    bt_cfg: BacktestConfig,
    loader: DukascopyDataLoader,
    interval: str = "1h",
    days: int = 180,
    force_refresh: bool = False,
) -> BacktestResult:
    end_dt = datetime.now(timezone.utc)
    start_dt = end_dt - timedelta(days=days)

    logger.info(f"Loading data for {symbol} ({interval}) for the last {days} days...")
    df = loader.load_pair(
        symbol=symbol,
        interval=interval,
        start=start_dt,
        end=end_dt,
        force_refresh=force_refresh,
    )

    logger.info(f"{symbol}: Loaded {len(df)} bars from {df.index[0]} to {df.index[-1]}.")

    # Generate strategy signals
    strategy = StarRsiStrategy(strat_cfg)
    strat_output = strategy.generate_signals(df)

    n_bull = strat_output.bull_signals.sum()
    n_bear = strat_output.bear_signals.sum()
    logger.info(f"{symbol}: Detected {n_bull} Bullish Morning Star signals and {n_bear} Bearish Evening Star signals.")

    # Run backtest simulation
    engine = BacktestEngine(bt_cfg)
    result = engine.run(symbol=symbol, data=strat_output.df, interval=interval)
    return result


def print_comparison_table(metrics_list: List[BacktestMetrics]):
    headers = [
        "Pair", "Trades", "Win Rate", "Net PnL ($)", "Return (%)", 
        "Profit Fac", "Sharpe", "Max DD (%)", "Avg R", "Commissions ($)"
    ]
    
    rows = []
    tot_profit = 0.0
    tot_trades = 0
    tot_wins = 0

    for m in metrics_list:
        rows.append([
            m.symbol,
            str(m.total_trades),
            f"{m.win_rate_pct:.1f}%",
            f"${m.total_net_profit:,.2f}",
            f"{m.total_return_pct:+.2f}%",
            f"{m.profit_factor:.2f}",
            f"{m.sharpe_ratio:.2f}",
            f"{m.max_drawdown_pct:.2f}%",
            f"{m.expectancy_r:+.2f}R",
            f"${m.total_commission_paid:,.2f}"
        ])
        tot_profit += m.total_net_profit
        tot_trades += m.total_trades
        tot_wins += m.winning_trades

    # Formatted terminal table
    col_widths = [max(len(str(val)) for val in [h] + [r[i] for r in rows]) + 2 for i, h in enumerate(headers)]
    
    sep_line = "+" + "+".join("-" * w for w in col_widths) + "+"
    hdr_line = "|" + "|".join(f" {h}".ljust(w) for h, w in zip(headers, col_widths)) + "|"
    
    print("\n" + "=" * len(sep_line))
    print(" 🌟 MAJOR FOREX PAIRS — STAR + RSI REVERSAL BACKTEST SUMMARY 🌟")
    print("=" * len(sep_line))
    print(sep_line)
    print(hdr_line)
    print(sep_line)
    for r in rows:
        print("|" + "|".join(f" {v}".ljust(w) for v, w in zip(r, col_widths)) + "|")
    print(sep_line)

    port_win_rate = (tot_wins / tot_trades * 100.0) if tot_trades > 0 else 0.0
    print(f"\n📊 PORTFOLIO AGGREGATE:")
    print(f"   • Total Trades:     {tot_trades}")
    print(f"   • Overall Win Rate: {port_win_rate:.1f}%")
    print(f"   • Total Net PnL:    ${tot_profit:,.2f}")
    print("=" * len(sep_line) + "\n")


def save_reports(results: Dict[str, BacktestResult], out_dir: str = "reports"):
    os.makedirs(out_dir, exist_ok=True)
    
    summary_data = []
    for sym, res in results.items():
        m = res.metrics
        summary_data.append({
            "Symbol": m.symbol,
            "Initial_Capital": m.initial_capital,
            "Ending_Equity": m.ending_equity,
            "Net_Profit_USD": m.total_net_profit,
            "Return_Pct": m.total_return_pct,
            "Total_Trades": m.total_trades,
            "Win_Rate_Pct": m.win_rate_pct,
            "Profit_Factor": m.profit_factor,
            "Sharpe_Ratio": m.sharpe_ratio,
            "Sortino_Ratio": m.sortino_ratio,
            "Max_Drawdown_Pct": m.max_drawdown_pct,
            "Expectancy_USD": m.expectancy_usd,
            "Expectancy_R": m.expectancy_r,
            "Avg_Trade_Bars": m.avg_trade_bars,
        })
        
        # Save individual trades
        if not res.trades.empty:
            trades_path = os.path.join(out_dir, f"{sym}_trades.csv")
            res.trades.to_csv(trades_path, index=False)
            logger.info(f"Saved {sym} trade log to {trades_path}")

    summary_df = pd.DataFrame(summary_data)
    summary_path = os.path.join(out_dir, "summary_portfolio.csv")
    summary_df.to_csv(summary_path, index=False)
    logger.info(f"Saved portfolio summary to {summary_path}")


def main():
    parser = argparse.ArgumentParser(description="Forex Star+RSI Reversal Strategy Backtester")
    parser.add_argument("--pairs", nargs="+", default=list(MAJOR_FX_PAIRS.keys()), help="Pairs to test (default: all 7 majors)")
    parser.add_argument("--interval", type=str, default="1h", choices=["1m", "5m", "15m", "30m", "1h", "4h", "1d"], help="Candle timeframe")
    parser.add_argument("--days", type=int, default=180, help="Days of history to backtest")
    parser.add_argument("--capital", type=float, default=10000.0, help="Initial account capital")
    parser.add_argument("--risk", type=float, default=1.0, help="Risk percentage per trade")
    parser.add_argument("--rr", type=float, default=2.0, help="Risk-to-reward ratio for TP (default: 2.0)")
    parser.add_argument("--refresh", action="store_true", help="Force fresh download from Dukascopy")
    
    # Strategy parameters
    parser.add_argument("--rsi_len", type=int, default=7, help="RSI period (default: 7)")
    parser.add_argument("--rsi_win", type=int, default=0, help="RSI cross window in bars (default: 0)")
    parser.add_argument("--no_rsi", action="store_true", help="Disable RSI reversal requirement")
    parser.add_argument("--no_detach", action="store_true", help="Disable soft detachment requirement")
    parser.add_argument("--enable_env", action="store_true", default=False, help="Enable RSI(2) environment filter (default: False)")
    parser.add_argument("--enable_cmf", action="store_true", default=False, help="Enable CMF filter (default: False)")
    parser.add_argument("--enable_sma", action="store_true", help="Enable SMA trend filter")
    parser.add_argument("--sma_len", type=int, default=50, help="SMA period (default: 50)")

    args = parser.parse_args()

    strat_cfg = StrategyConfig(
        rsi_len=args.rsi_len,
        rsi_enabled=not args.no_rsi,
        rsi_win=args.rsi_win,
        star_detach=not args.no_detach,
        env_enabled=args.enable_env,
        cmf_enabled=args.enable_cmf,
        sma_enabled=args.enable_sma,
        sma_len=args.sma_len,
    )
    bt_cfg = BacktestConfig(
        initial_capital=args.capital,
        risk_pct_per_trade=args.risk,
        risk_reward_ratio=args.rr,
    )

    loader = DukascopyDataLoader()
    results: Dict[str, BacktestResult] = {}
    metrics_list: List[BacktestMetrics] = []

    for sym in args.pairs:
        sym = sym.upper()
        if sym not in MAJOR_FX_PAIRS:
            logger.warning(f"Skipping unknown symbol: {sym}")
            continue
        try:
            res = run_single_pair(
                symbol=sym,
                strat_cfg=strat_cfg,
                bt_cfg=bt_cfg,
                loader=loader,
                interval=args.interval,
                days=args.days,
                force_refresh=args.refresh,
            )
            results[sym] = res
            metrics_list.append(res.metrics)
        except Exception as e:
            logger.error(f"Failed backtest for {sym}: {e}", exc_info=True)

    if metrics_list:
        print_comparison_table(metrics_list)
        save_reports(results)
    else:
        logger.error("No backtest results were generated.")


if __name__ == "__main__":
    main()
