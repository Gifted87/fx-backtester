"""
Forex Risk and Trade Sizing Manager.
Calculates pip values, position sizing based on account equity risk,
and sets SL / TP levels according to candlestick pattern geometry.
"""

from dataclasses import dataclass
from typing import Optional
from config.strategy_config import BacktestConfig, InstrumentSpec


@dataclass
class TradeOrder:
    symbol: str
    direction: int                      # 1 for Long, -1 for Short
    entry_price: float
    stop_loss: float
    take_profit: float
    units: float                        # Position size in base currency units
    lots: float                         # Standard lots (1 lot = 100,000 units)
    risk_usd: float
    risk_pips: float
    entry_time: any


class RiskManager:
    def __init__(self, bt_cfg: BacktestConfig, instrument: InstrumentSpec):
        self.bt_cfg = bt_cfg
        self.instrument = instrument

    def calculate_pip_value(self, current_price: float, lot_size: float = 100000.0) -> float:
        """
        Calculates the USD value of 1 pip for 1 standard lot (100,000 units).
        - If quote currency is USD (EURUSD, GBPUSD, AUDUSD, NZDUSD): 1 pip = $10.00
        - If base currency is USD (USDJPY, USDCAD, USDCHF): 1 pip = (pip_size / current_price) * 100,000
        """
        if self.instrument.quote_currency == "USD":
            return self.instrument.pip_size * lot_size  # 0.0001 * 100,000 = $10.00
        elif self.instrument.base_currency == "USD":
            # e.g. USDJPY: (0.01 / 150.00) * 100,000 ≈ $6.67
            return (self.instrument.pip_size / current_price) * lot_size
        else:
            # Default cross approximation
            return self.instrument.pip_size * lot_size

    def calculate_stops(
        self,
        direction: int,
        entry_price: float,
        pattern_low: float,
        pattern_high: float,
        atr_val: Optional[float] = None,
    ) -> tuple[float, float, float]:
        """
        Calculates Stop Loss and Take Profit prices.
        Returns: (stop_loss, take_profit, risk_pips)
        """
        pip = self.instrument.pip_size
        buf = self.bt_cfg.sl_buffer_pips * pip

        if self.bt_cfg.sl_mode == "atr" and atr_val is not None and atr_val > 0:
            sl_dist = atr_val * self.bt_cfg.atr_multiplier_sl
        else:
            sl_dist = None

        if direction == 1:  # Long
            if sl_dist is not None:
                sl = entry_price - sl_dist
            else:
                sl = pattern_low - buf
            # Safety check: SL must be strictly below entry
            if sl >= entry_price:
                sl = entry_price - 10 * pip
            risk_dist = entry_price - sl
            tp = entry_price + (risk_dist * self.bt_cfg.risk_reward_ratio)
            risk_pips = risk_dist / pip

        else:  # Short
            if sl_dist is not None:
                sl = entry_price + sl_dist
            else:
                sl = pattern_high + buf
            # Safety check: SL must be strictly above entry
            if sl <= entry_price:
                sl = entry_price + 10 * pip
            risk_dist = sl - entry_price
            tp = entry_price - (risk_dist * self.bt_cfg.risk_reward_ratio)
            risk_pips = risk_dist / pip

        return round(sl, 5), round(tp, 5), max(risk_pips, 1.0)

    def size_position(
        self,
        current_equity: float,
        entry_price: float,
        risk_pips: float,
    ) -> tuple[float, float, float]:
        """
        Calculates position size in units and lots given account equity risk %.
        Returns: (units, lots, risk_usd)
        """
        risk_usd = current_equity * (self.bt_cfg.risk_pct_per_trade / 100.0)
        pip_value_per_std_lot = self.calculate_pip_value(entry_price, lot_size=100000.0)

        # Total pip value needed
        # risk_usd = risk_pips * pip_value_per_std_lot * lots
        lots = risk_usd / (risk_pips * pip_value_per_std_lot)
        lots = max(round(lots, 2), 0.01)  # Minimum 0.01 micro-lot
        units = lots * 100000.0

        return units, lots, risk_usd
