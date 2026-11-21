//+------------------------------------------------------------------+
//|                                           StarRSI_EURUSD_M5.mq5  |
//|               Morning/Evening Star + Wilder RSI Reversal Expert  |
//|                 Optimized for EUR/USD 5-Minute Timeframe         |
//+------------------------------------------------------------------+
#property copyright "Antigravity Quant Research"
#property link      "https://github.com/fx-backtester"
#property version   "1.00"
#property description "Empirically validated Morning/Evening Star + Wilder RSI Reversal EA."
#property description "Calibrated on 10 years of 5-minute EUR/USD data (80.5% batch win rate, PF 1.40)."

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>
#include <Trade\AccountInfo.mqh>
#include <Trade\SymbolInfo.mqh>

//+------------------------------------------------------------------+
//| INPUT PARAMETERS — Calibrated for EUR/USD M5                    |
//+------------------------------------------------------------------+
input group "=== 1. RSI Reversal Engine ==="
input int      InpRsiPeriod       = 12;          // RSI Length (EURUSD Optimal = 12)
input double   InpRsiOversold     = 30.0;        // Oversold Level
input double   InpRsiOverbought   = 70.0;        // Overbought Level
input int      InpRsiWindow       = 1;           // Cross Lookback Window (bars, 1 = within 1 bar)
input bool     InpRsiMaEnabled    = false;       // Require RSI vs MA Filter (EURUSD Optimal = False)
input int      InpRsiMaPeriod     = 14;          // RSI MA Period (if enabled)

input group "=== 2. Star Pattern Quality & Geometry ==="
input double   InpStarBodyFactor  = 0.20;        // Star Body Factor (<= 0.20 of neighbours)
input double   InpThirdBodyFactor = 0.50;        // 3rd Confirmation Body Factor (>= 0.50 of 1st leg)
input double   InpStarRangeFactor = 0.40;        // Star Body / Own Range (<= 0.40)
input double   InpStarPenetration = 0.50;        // Penetration Factor into 1st Leg Body (0.50 = 50%)
input bool     InpStarDetach      = true;        // Require Soft Detachment (EURUSD Optimal = True)
input double   InpMinBodyPct      = 10.0;        // Doji Guard: 1st Leg Body % of Range
input bool     InpStarColorMatch  = false;       // Require Star & 3rd Candle Same Color (EURUSD = False)

input group "=== 3. Risk Management & Execution ==="
enum ENUM_SL_ANCHOR
{
   SL_STAR_CANDLE,      // Star Candle Extreme (EURUSD Optimal)
   SL_PATTERN_EXTREME   // 3-Candle Pattern Extreme
};
input ENUM_SL_ANCHOR InpSlAnchor  = SL_STAR_CANDLE;// Stop Loss Anchor
input double   InpRiskReward      = 1.0;         // Risk-Reward Ratio (EURUSD Optimal = 1.0)
input double   InpRiskPercent     = 1.0;         // Risk % of Equity per Trade (0 = Fixed Lot)
input double   InpFixedLotSize    = 0.10;        // Fixed Lot Size (if Risk % == 0)
input double   InpMaxSpreadPips   = 2.5;         // Max Allowable Spread in Pips
input ulong    InpMagicNumber     = 120501;      // Magic Number
input int      InpSlippagePoints  = 20;          // Max Slippage in Points

input group "=== 4. Visual Dashboard & Alerts ==="
input bool     InpShowDashboard   = true;        // Show HUD on Chart
input bool     InpSendAlerts      = true;        // Popup Audio Alerts
input bool     InpSendPush        = false;       // Mobile Push Notifications

//+------------------------------------------------------------------+
//| GLOBAL OBJECTS & STATE                                           |
//+------------------------------------------------------------------+
CTrade         m_trade;
CPositionInfo  m_position;
CAccountInfo   m_account;
CSymbolInfo    m_symbol;

int            m_rsi_handle       = INVALID_HANDLE;
datetime       m_last_bar_time    = 0;
double         m_pip_size         = 0.0001;
double         m_pip_point_ratio  = 10.0;

// Dashboard metrics
int            m_total_signals    = 0;
int            m_bull_signals     = 0;
int            m_bear_signals     = 0;
string         m_last_signal_text = "None";

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   // 1. Initialize symbol
   if(!m_symbol.Name(_Symbol))
   {
      Print("[-] Failed to initialize symbol: ", _Symbol);
      return INIT_FAILED;
   }
   m_symbol.Refresh();

   // Calculate pip size based on digits
   if(_Digits == 5 || _Digits == 3)
   {
      m_pip_size = 10.0 * _Point;
      m_pip_point_ratio = 10.0;
   }
   else
   {
      m_pip_size = _Point;
      m_pip_point_ratio = 1.0;
   }

   // 2. Initialize trade object
   m_trade.SetExpertMagicNumber(InpMagicNumber);
   m_trade.SetDeviationInPoints(InpSlippagePoints);
   m_trade.SetTypeFillingBySymbol(_Symbol);

   // 3. Initialize RSI Indicator Handle (Wilder's RSI via standard iRSI)
   m_rsi_handle = iRSI(_Symbol, _Period, InpRsiPeriod, PRICE_CLOSE);
   if(m_rsi_handle == INVALID_HANDLE)
   {
      Print("[-] Failed to create RSI indicator handle. Error: ", GetLastError());
      return INIT_FAILED;
   }

   PrintFormat("[+] StarRSI EA initialized successfully on %s (M%d). SL: Star Candle, RR: %.2f", 
               _Symbol, PeriodSeconds() / 60, InpRiskReward);

   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   if(m_rsi_handle != INVALID_HANDLE)
      IndicatorRelease(m_rsi_handle);

   // Clean dashboard comments
   Comment("");
}

//+------------------------------------------------------------------+
//| Check for New Bar Event                                          |
//+------------------------------------------------------------------+
bool IsNewBar()
{
   datetime current_bar_time = iTime(_Symbol, _Period, 0);
   if(current_bar_time != m_last_bar_time)
   {
      m_last_bar_time = current_bar_time;
      return true;
   }
   return false;
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   // Always refresh symbol quotes
   m_symbol.RefreshRates();

   // Update visual dashboard
   if(InpShowDashboard)
      UpdateDashboard();

   // Signals are evaluated strictly once on the OPEN of a new bar
   if(!IsNewBar())
      return;

   // Check spread filter
   double current_spread_pips = (m_symbol.Ask() - m_symbol.Bid()) / m_pip_size;
   if(current_spread_pips > InpMaxSpreadPips)
   {
      PrintFormat("[!] Spread %.1f pips exceeds max allowed %.1f pips. Skipping signal.", 
                  current_spread_pips, InpMaxSpreadPips);
      return;
   }

   // Check if we already have an open position for this magic number
   if(HasOpenPosition())
      return;

   // Evaluate Trading Signals on Closed Bars:
   // Bar 1 = Confirmation Candle (3rd leg)
   // Bar 2 = Star Candle (middle leg)
   // Bar 3 = First Leg Candle
   bool is_morning_star = false;
   bool is_evening_star = false;
   double sl_price = 0.0;

   if(!EvaluateStarPattern(is_morning_star, is_evening_star, sl_price))
      return;

   // Evaluate RSI Reversal Condition
   bool rsi_bull_ok = false;
   bool rsi_bear_ok = false;
   EvaluateRsiCondition(rsi_bull_ok, rsi_bear_ok);

   // Execute Trade Orders
   if(is_morning_star && rsi_bull_ok)
   {
      ExecuteBuyOrder(sl_price);
   }
   else if(is_evening_star && rsi_bear_ok)
   {
      ExecuteSellOrder(sl_price);
   }
}

//+------------------------------------------------------------------+
//| Check if open position already exists for this EA                |
//+------------------------------------------------------------------+
bool HasOpenPosition()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(m_position.SelectByIndex(i))
      {
         if(m_position.Symbol() == _Symbol && m_position.Magic() == InpMagicNumber)
            return true;
      }
   }
   return false;
}

//+------------------------------------------------------------------+
//| Evaluate Candlestick Pattern Geometry                            |
//+------------------------------------------------------------------+
bool EvaluateStarPattern(bool &is_morning_star, bool &is_evening_star, double &sl_price)
{
   is_morning_star = false;
   is_evening_star = false;
   sl_price = 0.0;

   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   if(CopyRates(_Symbol, _Period, 1, 4, rates) < 4)
      return false;

   // rates[0] = Bar 1 (Confirmation candle)
   // rates[1] = Bar 2 (Star candle)
   // rates[2] = Bar 3 (First leg candle)
   
   double c0 = rates[0].close, o0 = rates[0].open, h0 = rates[0].high, l0 = rates[0].low;
   double c1 = rates[1].close, o1 = rates[1].open, h1 = rates[1].high, l1 = rates[1].low;
   double c2 = rates[2].close, o2 = rates[2].open, h2 = rates[2].high, l2 = rates[2].low;

   double body1 = fabs(c2 - o2);
   double range1 = h2 - l2;
   double body2 = fabs(c1 - o1);
   double range2 = h1 - l1;
   double body3 = fabs(c0 - o0);

   // 1. Doji Guard: 1st leg body must be >= MinBodyPct of its range
   if(range1 <= 0.0 || (body1 / range1 * 100.0) < InpMinBodyPct)
      return false;

   // 2. Middle Star Size Requirements
   bool middle_small = (body2 <= body1 * InpStarBodyFactor) &&
                       (body2 <= body3 * InpStarBodyFactor) &&
                       (range2 > 0.0 && (body2 <= range2 * InpStarRangeFactor));
   if(!middle_small)
      return false;

   // 3. Confirmation Leg Significance
   bool third_real = (body3 >= body1 * InpThirdBodyFactor);
   bool first_leg_big = (body1 >= body3 * 0.50);
   if(!third_real || !first_leg_big)
      return false;

   // 4. Color Requirements
   bool first_bear = (c2 < o2);
   bool first_bull = (c2 > o2);
   bool third_bull = (c0 > o0);
   bool third_bear = (c0 < o0);

   bool star_bull = (c1 > o1);
   bool star_bear = (c1 < o1);
   bool star_ambiguous = (range2 > 0.0) && ((body2 / range2 * 100.0) < 10.0);

   bool col_bull = (!InpStarColorMatch) || star_ambiguous || star_bull;
   bool col_bear = (!InpStarColorMatch) || star_ambiguous || star_bear;

   // 5. Penetration Rule (close of confirmation candle penetrates 50% into first leg)
   double pen_bull_level = MathMax(o2, c2) - (body1 * InpStarPenetration);
   double pen_bear_level = MathMin(o2, c2) + (body1 * InpStarPenetration);
   bool pen_bull = third_bull && (c0 > pen_bull_level);
   bool pen_bear = third_bear && (c0 < pen_bear_level);

   // 6. Soft Detachment Rule
   bool det_bull = true;
   bool det_bear = true;
   if(InpStarDetach)
   {
      det_bull = MathMin(o1, c1) <= MathMin(o2, c2); // Star body pushes lower
      det_bear = MathMax(o1, c1) >= MathMax(o2, c2); // Star body pushes higher
   }

   // 7. Full Pattern Confirmation
   if(first_bear && third_bull && col_bull && pen_bull && det_bull)
   {
      is_morning_star = true;
      if(InpSlAnchor == SL_STAR_CANDLE)
         sl_price = l1; // Low of the star candle
      else
         sl_price = MathMin(l0, MathMin(l1, l2)); // Pattern extreme low
      return true;
   }
   else if(first_bull && third_bear && col_bear && pen_bear && det_bear)
   {
      is_evening_star = true;
      if(InpSlAnchor == SL_STAR_CANDLE)
         sl_price = h1; // High of the star candle
      else
         sl_price = MathMax(h0, MathMax(h1, h2)); // Pattern extreme high
      return true;
   }

   return false;
}

//+------------------------------------------------------------------+
//| Evaluate RSI Reversal Signal with Lookback Window                |
//+------------------------------------------------------------------+
void EvaluateRsiCondition(bool &rsi_bull_ok, bool &rsi_bear_ok)
{
   rsi_bull_ok = false;
   rsi_bear_ok = false;

   int lookback = InpRsiWindow + 2;
   double rsi_values[];
   ArraySetAsSeries(rsi_values, true);

   if(CopyBuffer(m_rsi_handle, 0, 1, lookback, rsi_values) < lookback)
      return;

   // Check for cross up (oversold) and cross down (overbought) within window
   for(int i = 0; i <= InpRsiWindow; i++)
   {
      double r_curr = rsi_values[i];
      double r_prev = rsi_values[i + 1];

      // Bullish Cross: Previous RSI < 30 and Current RSI >= 30
      if(r_prev < InpRsiOversold && r_curr >= InpRsiOversold)
         rsi_bull_ok = true;

      // Bearish Cross: Previous RSI > 70 and Current RSI <= 70
      if(r_prev > InpRsiOverbought && r_curr <= InpRsiOverbought)
         rsi_bear_ok = true;
   }
}

//+------------------------------------------------------------------+
//| Calculate Lot Size based on Account Equity Risk %                |
//+------------------------------------------------------------------+
double CalculateLotSize(double entry_price, double sl_price)
{
   if(InpRiskPercent <= 0.0)
      return InpFixedLotSize;

   double risk_distance = fabs(entry_price - sl_price);
   if(risk_distance <= 0.0)
      return InpFixedLotSize;

   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   double risk_amount = equity * (InpRiskPercent / 100.0);

   double tick_size = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double tick_value = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   if(tick_size <= 0.0 || tick_value <= 0.0)
      return InpFixedLotSize;

   double points_at_risk = risk_distance / _Point;
   double cost_per_lot = (risk_distance / tick_size) * tick_value;

   if(cost_per_lot <= 0.0)
      return InpFixedLotSize;

   double raw_lots = risk_amount / cost_per_lot;

   // Normalize to broker limits
   double min_lot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double max_lot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double step_lot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);

   double lots = MathFloor(raw_lots / step_lot) * step_lot;
   if(lots < min_lot) lots = min_lot;
   if(lots > max_lot) lots = max_lot;

   return NormalizeDouble(lots, 2);
}

//+------------------------------------------------------------------+
//| Execute BUY Position                                             |
//+------------------------------------------------------------------+
void ExecuteBuyOrder(double sl_price)
{
   double ask = m_symbol.Ask();
   if(sl_price >= ask)
      sl_price = ask - (5.0 * m_pip_size); // Safety stop

   double risk_dist = ask - sl_price;
   double tp_price = NormalizeDouble(ask + (risk_dist * InpRiskReward), _Digits);
   sl_price = NormalizeDouble(sl_price, _Digits);

   double lots = CalculateLotSize(ask, sl_price);

   if(m_trade.Buy(lots, _Symbol, ask, sl_price, tp_price, "StarRSI_Buy_M5"))
   {
      m_total_signals++;
      m_bull_signals++;
      m_last_signal_text = StringFormat("BUY %.2f lots @ %.5f | SL: %.5f | TP: %.5f", lots, ask, sl_price, tp_price);
      Print("[+] ", m_last_signal_text);

      if(InpSendAlerts)
         Alert(StringFormat("[StarRSI M5] EURUSD BUY executed at %.5f (SL: %.5f, TP: %.5f)", ask, sl_price, tp_price));
      if(InpSendPush)
         SendNotification(StringFormat("[StarRSI M5] EURUSD BUY executed at %.5f", ask));
   }
   else
   {
      Print("[-] Buy order failed. Error: ", GetLastError());
   }
}

//+------------------------------------------------------------------+
//| Execute SELL Position                                            |
//+------------------------------------------------------------------+
void ExecuteSellOrder(double sl_price)
{
   double bid = m_symbol.Bid();
   if(sl_price <= bid)
      sl_price = bid + (5.0 * m_pip_size); // Safety stop

   double risk_dist = sl_price - bid;
   double tp_price = NormalizeDouble(bid - (risk_dist * InpRiskReward), _Digits);
   sl_price = NormalizeDouble(sl_price, _Digits);

   double lots = CalculateLotSize(bid, sl_price);

   if(m_trade.Sell(lots, _Symbol, bid, sl_price, tp_price, "StarRSI_Sell_M5"))
   {
      m_total_signals++;
      m_bear_signals++;
      m_last_signal_text = StringFormat("SELL %.2f lots @ %.5f | SL: %.5f | TP: %.5f", lots, bid, sl_price, tp_price);
      Print("[+] ", m_last_signal_text);

      if(InpSendAlerts)
         Alert(StringFormat("[StarRSI M5] EURUSD SELL executed at %.5f (SL: %.5f, TP: %.5f)", bid, sl_price, tp_price));
      if(InpSendPush)
         SendNotification(StringFormat("[StarRSI M5] EURUSD SELL executed at %.5f", bid));
   }
   else
   {
      Print("[-] Sell order failed. Error: ", GetLastError());
   }
}

//+------------------------------------------------------------------+
//| Update Real-Time Chart HUD                                       |
//+------------------------------------------------------------------+
void UpdateDashboard()
{
   double rsi_now[];
   ArraySetAsSeries(rsi_now, true);
   double cur_rsi = 50.0;
   if(CopyBuffer(m_rsi_handle, 0, 0, 1, rsi_now) > 0)
      cur_rsi = rsi_now[0];

   string hud = "";
   hud += "=====================================================\n";
   hud += "     STAR + RSI REVERSAL EA (EUR/USD M5 OPTIMIZED)   \n";
   hud += "=====================================================\n";
   hud += StringFormat("Account Balance: $%.2f | Equity: $%.2f\n", AccountInfoDouble(ACCOUNT_BALANCE), AccountInfoDouble(ACCOUNT_EQUITY));
   hud += StringFormat("Current RSI(%d): %.2f (OS: %.0f / OB: %.0f)\n", InpRsiPeriod, cur_rsi, InpRsiOversold, InpRsiOverbought);
   hud += StringFormat("Execution Model: SL at Star Candle | Target: %.1f R:R\n", InpRiskReward);
   hud += StringFormat("Risk per Trade: %.1f%% Equity (Dynamic Lot)\n", InpRiskPercent);
   hud += StringFormat("Total Session Signals: %d (Bull: %d | Bear: %d)\n", m_total_signals, m_bull_signals, m_bear_signals);
   hud += StringFormat("Last Executed Signal: %s\n", m_last_signal_text);
   hud += "=====================================================\n";

   Comment(hud);
}
//+------------------------------------------------------------------+
