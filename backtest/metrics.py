"""
Quantitative Performance and Risk Metrics Calculator.
Computes Sharpe, Sortino, Calmar, Max Drawdown, Win Rate, and multi-pair comparative statistics.
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional
import numpy as np
import pandas as pd


@dataclass
class BacktestMetrics:
    symbol: str
    initial_capital: float
    ending_equity: float
    total_net_profit: float
    total_return_pct: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate_pct: float
    profit_factor: float
    expectancy_usd: float
    expectancy_r: float
    avg_win_usd: float
    avg_loss_usd: float
    payoff_ratio: float
    max_drawdown_usd: float
    max_drawdown_pct: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    total_commission_paid: float
    avg_trade_bars: float


def compute_metrics(
    symbol: str,
    initial_capital: float,
    trades: List[Dict[str, Any]],
    equity_curve: pd.Series,
    annualization_factor: float = 24 * 252,  # Hourly bars per trading year
) -> BacktestMetrics:
    """
    Computes standard institutional backtest metrics from completed trades and equity curve.
    """
    ending_equity = equity_curve.iloc[-1] if not equity_curve.empty else initial_capital
    net_profit = ending_equity - initial_capital
    return_pct = (net_profit / initial_capital) * 100.0 if initial_capital > 0 else 0.0

    if not trades:
        return BacktestMetrics(
            symbol=symbol,
            initial_capital=initial_capital,
            ending_equity=ending_equity,
            total_net_profit=0.0,
            total_return_pct=0.0,
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            win_rate_pct=0.0,
            profit_factor=0.0,
            expectancy_usd=0.0,
            expectancy_r=0.0,
            avg_win_usd=0.0,
            avg_loss_usd=0.0,
            payoff_ratio=0.0,
            max_drawdown_usd=0.0,
            max_drawdown_pct=0.0,
            sharpe_ratio=0.0,
            sortino_ratio=0.0,
            calmar_ratio=0.0,
            total_commission_paid=0.0,
            avg_trade_bars=0.0,
        )

    pnls = np.array([t['pnl_usd'] for t in trades])
    r_mults = np.array([t.get('r_multiple', 0.0) for t in trades])
    commissions = np.array([t.get('commission', 0.0) for t in trades])
    durations = np.array([t.get('duration_bars', 0) for t in trades])

    wins = pnls[pnls > 0]
    losses = pnls[pnls < 0]

    n_trades = len(pnls)
    n_wins = len(wins)
    n_losses = len(losses)

    win_rate = (n_wins / n_trades) * 100.0 if n_trades > 0 else 0.0
    gross_profits = wins.sum() if n_wins > 0 else 0.0
    gross_losses = abs(losses.sum()) if n_losses > 0 else 0.0

    profit_factor = (gross_profits / gross_losses) if gross_losses > 0 else (99.0 if gross_profits > 0 else 0.0)
    avg_win = float(wins.mean()) if n_wins > 0 else 0.0
    avg_loss = float(abs(losses.mean())) if n_losses > 0 else 0.0
    payoff_ratio = (avg_win / avg_loss) if avg_loss > 0 else 0.0

    expectancy_usd = float(pnls.mean()) if n_trades > 0 else 0.0
    expectancy_r = float(r_mults.mean()) if n_trades > 0 else 0.0

    # Max Drawdown from equity curve
    running_max = equity_curve.cummax()
    drawdown_usd = running_max - equity_curve
    max_dd_usd = float(drawdown_usd.max())

    drawdown_pct = np.where(running_max > 0, (drawdown_usd / running_max) * 100.0, 0.0)
    max_dd_pct = float(np.max(drawdown_pct))

    # Returns per bar for Sharpe & Sortino
    bar_returns = equity_curve.pct_change().dropna()
    mean_ret = bar_returns.mean()
    std_ret = bar_returns.std()

    if std_ret > 0:
        sharpe = float((mean_ret / std_ret) * np.sqrt(annualization_factor))
    else:
        sharpe = 0.0

    downside_returns = bar_returns[bar_returns < 0]
    downside_std = downside_returns.std()
    if downside_std > 0:
        sortino = float((mean_ret / downside_std) * np.sqrt(annualization_factor))
    else:
        sortino = 0.0

    # Calmar ratio: Annualized return / Max Drawdown %
    total_bars = len(equity_curve)
    years = total_bars / annualization_factor if total_bars > 0 else 1.0
    cagr = ((ending_equity / initial_capital) ** (1.0 / max(years, 0.01)) - 1.0) * 100.0 if initial_capital > 0 and ending_equity > 0 else 0.0
    calmar = (cagr / max_dd_pct) if max_dd_pct > 0 else 0.0

    return BacktestMetrics(
        symbol=symbol,
        initial_capital=initial_capital,
        ending_equity=round(ending_equity, 2),
        total_net_profit=round(net_profit, 2),
        total_return_pct=round(return_pct, 2),
        total_trades=n_trades,
        winning_trades=n_wins,
        losing_trades=n_losses,
        win_rate_pct=round(win_rate, 2),
        profit_factor=round(profit_factor, 2),
        expectancy_usd=round(expectancy_usd, 2),
        expectancy_r=round(expectancy_r, 2),
        avg_win_usd=round(avg_win, 2),
        avg_loss_usd=round(avg_loss, 2),
        payoff_ratio=round(payoff_ratio, 2),
        max_drawdown_usd=round(max_dd_usd, 2),
        max_drawdown_pct=round(max_dd_pct, 2),
        sharpe_ratio=round(sharpe, 2),
        sortino_ratio=round(sortino, 2),
        calmar_ratio=round(calmar, 2),
        total_commission_paid=round(float(commissions.sum()), 2),
        avg_trade_bars=round(float(durations.mean()), 1) if len(durations) > 0 else 0.0,
    )
