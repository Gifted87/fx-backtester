# Optimal Parameter Configurations by Currency Pair

Empirical analysis identifying the single best, most consistent parameter configuration for each Forex pair across 180-day market batches.

### Summary Table of Best Configuration per Pair

| Pair | Batches Won | Consistency | Optimal RSI | Geometry (Star/3rd/Detach) | SL & R:R | Avg Win Rate | Avg PF | Total Return | Total Trades |
| :--- | :---: | :---: | :--- | :--- | :--- | :---: | :---: | :---: | :---: |
| **AUDCAD** | **3 / 3** | **100.0%** | `RSI(21, 35/65, W=0, MA=False)` | `SB=0.25, 3B=0.6, Det=Yes, Col=No` | `Star @ 1.25R` | **59.2%** | **2.46** | **+8.0%** | 48 |
| **AUDCHF** | **3 / 3** | **100.0%** | `RSI(12, 20/80, W=3, MA=False)` | `SB=0.5, 3B=0.7, Det=No, Col=No` | `Star @ 1.25R` | **69.4%** | **34.0** | **+12.3%** | 35 |
| **AUDJPY** | **3 / 3** | **100.0%** | `RSI(18, 30/70, W=1, MA=False)` | `SB=0.4, 3B=0.6, Det=Yes, Col=No` | `Extreme @ 1.0R` | **71.1%** | **33.88** | **+11.1%** | 41 |
| **AUDNZD** | **3 / 3** | **100.0%** | `RSI(12, 25/75, W=3, MA=False)` | `SB=0.2, 3B=0.6, Det=Yes, Col=Yes` | `Extreme @ 1.0R` | **69.8%** | **3.83** | **+18.1%** | 29 |
| **AUDUSD** | **3 / 3** | **100.0%** | `RSI(8, 20/80, W=0, MA=True)` | `SB=0.4, 3B=0.5, Det=Yes, Col=No` | `Star @ 1.0R` | **76.0%** | **34.24** | **+12.0%** | 34 |
| **CADCHF** | **3 / 3** | **100.0%** | `RSI(16, 30/70, W=1, MA=True)` | `SB=0.3, 3B=0.5, Det=Yes, Col=Yes` | `Extreme @ 1.0R` | **79.8%** | **34.56** | **+12.2%** | 22 |
| **CADJPY** | **3 / 3** | **100.0%** | `RSI(8, 20/80, W=3, MA=False)` | `SB=0.2, 3B=0.7, Det=Yes, Col=Yes` | `Star @ 1.25R` | **79.6%** | **36.75** | **+16.9%** | 24 |
| **CHFJPY** | **3 / 3** | **100.0%** | `RSI(9, 20/80, W=1, MA=False)` | `SB=0.25, 3B=0.6, Det=Yes, Col=Yes` | `Extreme @ 1.0R` | **75.7%** | **34.25** | **+9.1%** | 21 |
| **EURAUD** | **3 / 3** | **100.0%** | `RSI(21, 35/65, W=0, MA=False)` | `SB=0.25, 3B=0.5, Det=Yes, Col=Yes` | `Star @ 1.0R` | **71.7%** | **33.9** | **+9.9%** | 38 |
| **EURCAD** | **3 / 3** | **100.0%** | `RSI(18, 30/70, W=3, MA=False)` | `SB=0.25, 3B=0.6, Det=Yes, Col=No` | `Extreme @ 1.0R` | **72.2%** | **33.95** | **+11.0%** | 39 |
| **EURCHF** | **3 / 3** | **100.0%** | `RSI(10, 20/80, W=0, MA=False)` | `SB=0.35, 3B=0.5, Det=No, Col=No` | `Star @ 2.5R` | **65.0%** | **34.56** | **+32.5%** | 35 |
| **EURGBP** | **3 / 3** | **100.0%** | `RSI(12, 25/75, W=1, MA=False)` | `SB=0.25, 3B=0.7, Det=Yes, Col=No` | `Extreme @ 2.0R` | **65.7%** | **34.33** | **+17.3%** | 22 |
| **EURJPY** | **3 / 3** | **100.0%** | `RSI(16, 25/75, W=3, MA=True)` | `SB=0.2, 3B=0.7, Det=No, Col=No` | `Star @ 1.0R` | **71.9%** | **33.92** | **+9.2%** | 21 |
| **EURNZD** | **3 / 3** | **100.0%** | `RSI(21, 35/65, W=3, MA=True)` | `SB=0.35, 3B=0.5, Det=Yes, Col=No` | `Extreme @ 2.0R` | **58.7%** | **3.9** | **+19.3%** | 32 |
| **EURUSD** | **20 / 24** | **83.3%** | `RSI(18, 30/70, W=3, MA=False)` | `SB=0.2, 3B=0.5, Det=Yes, Col=No` | `Extreme @ 1.0R` | **57.6%** | **1.46** | **+44.0%** | 355 |
| **GBPAUD** | **3 / 3** | **100.0%** | `RSI(7, 20/80, W=1, MA=True)` | `SB=0.5, 3B=0.5, Det=Yes, Col=Yes` | `Extreme @ 1.0R` | **67.3%** | **2.65** | **+9.9%** | 38 |
| **GBPCAD** | **3 / 3** | **100.0%** | `RSI(21, 30/70, W=3, MA=False)` | `SB=0.4, 3B=0.6, Det=Yes, Col=Yes` | `Extreme @ 2.5R` | **54.0%** | **6.03** | **+19.6%** | 23 |
| **GBPCHF** | **3 / 3** | **100.0%** | `RSI(18, 25/75, W=3, MA=True)` | `SB=0.5, 3B=0.6, Det=No, Col=No` | `Extreme @ 1.0R` | **88.9%** | **66.67** | **+14.3%** | 20 |
| **GBPJPY** | **3 / 3** | **100.0%** | `RSI(16, 25/75, W=1, MA=False)` | `SB=0.25, 3B=0.5, Det=No, Col=Yes` | `Extreme @ 1.25R` | **71.1%** | **34.13** | **+16.0%** | 36 |
| **GBPNZD** | **3 / 3** | **100.0%** | `RSI(7, 20/80, W=3, MA=False)` | `SB=0.5, 3B=0.6, Det=Yes, Col=No` | `Star @ 2.5R` | **49.8%** | **5.78** | **+23.8%** | 95 |
| **GBPUSD** | **11 / 11** | **100.0%** | `RSI(16, 25/75, W=1, MA=False)` | `SB=0.3, 3B=0.6, Det=No, Col=No` | `Extreme @ 1.5R` | **47.3%** | **1.39** | **+32.3%** | 187 |
| **NZDCAD** | **3 / 3** | **100.0%** | `RSI(7, 35/65, W=0, MA=True)` | `SB=0.2, 3B=0.7, Det=Yes, Col=No` | `Extreme @ 1.0R` | **61.7%** | **1.67** | **+24.5%** | 120 |
| **NZDCHF** | **3 / 3** | **100.0%** | `RSI(10, 20/80, W=0, MA=False)` | `SB=0.5, 3B=0.5, Det=No, Col=Yes` | `Extreme @ 1.25R` | **64.5%** | **3.48** | **+12.1%** | 33 |
| **NZDJPY** | **3 / 3** | **100.0%** | `RSI(18, 30/70, W=1, MA=True)` | `SB=0.35, 3B=0.6, Det=No, Col=No` | `Extreme @ 1.25R` | **78.5%** | **34.78** | **+31.2%** | 51 |
| **NZDUSD** | **3 / 3** | **100.0%** | `RSI(12, 20/80, W=1, MA=False)` | `SB=0.5, 3B=0.7, Det=No, Col=No` | `Star @ 2.5R` | **45.7%** | **2.57** | **+20.3%** | 60 |
| **USDCAD** | **3 / 3** | **100.0%** | `RSI(12, 25/75, W=0, MA=True)` | `SB=0.35, 3B=0.5, Det=Yes, Col=No` | `Extreme @ 1.75R` | **55.8%** | **4.86** | **+13.2%** | 23 |
| **USDCHF** | **3 / 3** | **100.0%** | `RSI(5, 20/80, W=0, MA=True)` | `SB=0.3, 3B=0.7, Det=No, Col=Yes` | `Star @ 1.5R` | **59.5%** | **4.34** | **+23.7%** | 119 |
| **USDJPY** | **3 / 3** | **100.0%** | `RSI(9, 20/80, W=3, MA=True)` | `SB=0.2, 3B=0.5, Det=No, Col=No` | `Extreme @ 1.0R` | **69.1%** | **33.77** | **+7.9%** | 46 |
