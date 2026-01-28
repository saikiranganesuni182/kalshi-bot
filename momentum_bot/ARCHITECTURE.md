# Kalshi Momentum Convergence Trading Bot - Architecture

## Overview

A multi-threaded trading bot that monitors Kalshi prediction markets for momentum signals
based on YES/NO price convergence, with dynamic liquidity tracking.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           MOMENTUM BOT ORCHESTRATOR                         │
│                              (bot.py - Main Thread)                         │
├─────────────────────────────────────────────────────────────────────────────┤
│  - Initializes all components                                               │
│  - Fetches and filters liquid markets                                       │
│  - Spawns trader threads for each market                                    │
│  - Periodically scans for NEW liquid markets (every 60s)                    │
│  - Monitors liquidity changes and adds/removes traders                      │
│  - Handles graceful shutdown                                                │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
          ┌───────────────────────────┼───────────────────────────┐
          │                           │                           │
          ▼                           ▼                           ▼
┌─────────────────┐       ┌─────────────────────┐       ┌─────────────────┐
│  WebSocket Feed │       │   Risk Manager      │       │  Trade Tracker  │
│  (websocket.py) │       │   (risk.py)         │       │  (tracker.py)   │
├─────────────────┤       ├─────────────────────┤       ├─────────────────┤
│ - Connects to   │       │ - Position limits   │       │ - Records all   │
│   Kalshi WS     │       │ - Stop-loss logic   │       │   trades        │
│ - Subscribes to │       │ - Trailing stops    │       │ - Calculates    │
│   orderbook     │       │ - Daily loss limit  │       │   P&L           │
│ - Parses deltas │       │ - Circuit breaker   │       │ - Persists to   │
│ - Auto-reconnect│       │ - Thread-safe locks │       │   JSON file     │
└────────┬────────┘       └─────────────────────┘       └─────────────────┘
         │
         │ Price updates broadcast to all trader threads
         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         MARKET TRADER THREADS                               │
│                    (trader.py - One thread per market)                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │  Market A   │  │  Market B   │  │  Market C   │  │  Market N   │        │
│  │   Thread    │  │   Thread    │  │   Thread    │  │   Thread    │  ...   │
│  ├─────────────┤  ├─────────────┤  ├─────────────┤  ├─────────────┤        │
│  │ Price hist  │  │ Price hist  │  │ Price hist  │  │ Price hist  │        │
│  │ Momentum    │  │ Momentum    │  │ Momentum    │  │ Momentum    │        │
│  │ Strategy    │  │ Strategy    │  │ Strategy    │  │ Strategy    │        │
│  │ Position    │  │ Position    │  │ Position    │  │ Position    │        │
│  │ Orders      │  │ Orders      │  │ Orders      │  │ Orders      │        │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Threading Model

```
Main Thread (Bot Orchestrator)
    │
    ├── WebSocket Listener (async)
    │       └── Broadcasts price updates to trader threads
    │
    ├── Market Scanner (async, every 60s)
    │       └── Finds new liquid markets, starts new traders
    │
    ├── Status Printer (async, every 30s)
    │       └── Prints P&L and position summary
    │
    └── Trader Threads (one per market)
            ├── Market A Thread (daemon)
            ├── Market B Thread (daemon)
            ├── Market C Thread (daemon)
            └── ... up to max_markets
```

## Data Flow

```
1. PRICE UPDATE FLOW
   ─────────────────
   Kalshi WebSocket
         │
         ▼
   WebSocket Manager
   (parses snapshot/delta)
         │
         ▼
   Bot._on_price_update()
         │
         ▼
   MarketTrader.update_price()
         │
         ▼
   MarketState.add_snapshot()
   (stores in price_history)


2. TRADING DECISION FLOW
   ──────────────────────
   MarketTrader._tick() [every 200ms]
         │
         ├── Check exits (stop-loss, trailing stop)
         │
         └── Run strategy analysis [every 500ms]
                   │
                   ▼
             MomentumStrategy.analyze()
                   │
                   ├── Calculate gap change over window
                   ├── Calculate YES price change
                   ├── Generate signal (BULLISH/BEARISH/NEUTRAL)
                   │
                   ▼
             If signal detected:
                   │
                   ├── Check risk limits (RiskManager)
                   ├── Place entry order (KalshiClient)
                   ├── Set stop-loss price
                   ├── Set trailing stop price
                   └── Record trade (TradeTracker)


3. LIQUIDITY MONITORING FLOW
   ─────────────────────────
   Bot._market_scanner_loop() [every 60s]
         │
         ▼
   Fetch all open markets
         │
         ▼
   Filter by liquidity criteria:
   - Spread < max_spread
   - Has active bids
   - Volume increasing
         │
         ▼
   Compare with current traders:
         │
         ├── New liquid market? → Start new trader thread
         │
         └── Market lost liquidity? → Stop trader thread
```

## Momentum Strategy Logic

```
CONVERGENCE DETECTION
─────────────────────

In Kalshi prediction markets:
- YES price = probability of YES outcome (1-99 cents)
- NO price = probability of NO outcome (1-99 cents)
- Theoretical: YES + NO = 100 cents

The "GAP" = 100 - YES_mid - NO_mid

Example:
  YES bid/ask = 30/35 → YES mid = 32.5
  NO bid/ask  = 55/60 → NO mid = 57.5
  GAP = 100 - 32.5 - 57.5 = 10 cents

When the GAP SHRINKS, it means prices are CONVERGING:
  - If YES is rising → BULLISH momentum
  - If YES is falling (NO rising) → BEARISH momentum


SIGNAL GENERATION
─────────────────

window = 5 seconds (configurable)

1. Calculate gap_change = current_gap - old_gap
   - Negative gap_change = convergence (momentum detected)

2. Calculate yes_price_change = current_yes - old_yes

3. Generate signal:

   IF gap_change < -convergence_threshold:
       IF yes_price_change >= entry_threshold:
           SIGNAL = BULLISH (buy YES)
       ELIF yes_price_change <= -entry_threshold:
           SIGNAL = BEARISH (buy NO)

   ELSE:
       SIGNAL = NEUTRAL (no trade)


ENTRY LOGIC
───────────

When BULLISH signal:
  1. Buy YES at current_yes_mid + 1 (slightly aggressive)
  2. Set stop_loss = entry_price - stop_loss_cents - kalshi_fee
  3. Set trailing_stop = entry_price - trailing_stop_cents

When BEARISH signal:
  1. Buy NO at current_no_mid + 1
  2. Same stop logic


EXIT LOGIC
──────────

Check on every tick (200ms):

1. STOP LOSS: If current_price <= stop_loss_price
   → Exit immediately, accept loss

2. TRAILING STOP:
   - If price rises above entry, update highest_seen
   - trailing_stop = highest_seen - trailing_stop_cents
   - If current_price <= trailing_stop
   → Exit, lock in profit

3. REVERSAL:
   - If holding YES and BEARISH signal appears (conf >= 50%)
   → Close YES, open NO position
   - Vice versa for BEARISH → BULLISH
```

## Risk Management

```
PRE-TRADE CHECKS (RiskManager.check_can_trade)
──────────────────────────────────────────────

1. Circuit Breaker
   └── If daily_loss > max_daily_loss → BLOCK ALL TRADES

2. Position Limit Per Market
   └── If position + new_size > max_position_per_market → REJECT

3. Total Exposure Limit
   └── If total_exposure + new_exposure > max_total_exposure → REJECT

4. Cooldown Period
   └── If time_since_last_trade < cooldown_seconds → WAIT


STOP-LOSS CALCULATION
─────────────────────

stop_loss_price = entry_price - stop_loss_cents - kalshi_fee_cents

Example:
  entry_price = 45 cents
  stop_loss_cents = 2
  kalshi_fee_cents = 1

  stop_loss_price = 45 - 2 - 1 = 42 cents

  Max loss per contract = 3 cents (including fee)


TRAILING STOP LOGIC
───────────────────

Initial: trailing_stop = entry_price - trailing_stop_cents

As price rises:
  IF current_price > highest_seen:
      highest_seen = current_price
      trailing_stop = highest_seen - trailing_stop_cents

Example:
  entry = 45, trailing_stop_cents = 2
  initial trailing_stop = 43

  price rises to 50:
      highest_seen = 50
      trailing_stop = 48

  price drops to 48:
      EXIT with profit of 3 cents (48 - 45)
```

## Liquidity Monitoring

```
CONTINUOUS MARKET SCANNING
──────────────────────────

Every 60 seconds, the bot:

1. Fetches all open markets from API
2. Filters for liquidity:
   - Has bid > 0 and ask < 100
   - Spread <= max_spread
   - Optionally: volume > min_volume

3. Compares with currently tracked markets:

   NEW LIQUID MARKETS:
   └── Market not in traders but passes filter
       → Start new MarketTrader thread
       → Subscribe to WebSocket updates
       → Log: "New liquid market detected: {ticker}"

   MARKETS LOSING LIQUIDITY:
   └── Market in traders but fails filter
       → If no open position: stop trader
       → If has position: keep trading until exit
       → Log: "Market lost liquidity: {ticker}"

4. Tracks liquidity trends:
   - Volume increasing = more interest
   - Spread tightening = more competitive
   - Both = HIGH PRIORITY market
```

## File Descriptions

| File | Purpose |
|------|---------|
| `__init__.py` | Package initialization |
| `__main__.py` | Entry point, configuration |
| `auth.py` | RSA signature for API authentication |
| `client.py` | REST API client (markets, orders, balance) |
| `config.py` | Configuration dataclass with defaults |
| `models.py` | Data models (MarketState, Position, Trade, Signal) |
| `websocket.py` | Real-time WebSocket connection with auto-reconnect |
| `strategy.py` | Momentum convergence detection algorithm |
| `risk.py` | Risk management (limits, stops, circuit breaker) |
| `tracker.py` | P&L tracking with JSON persistence |
| `trader.py` | Per-market trading thread |
| `bot.py` | Main orchestrator, thread management |

## Configuration Parameters

```python
config = Config(
    # API
    api_key="...",
    private_key_path="private_key.pem",
    use_demo=True,  # True for demo-api.kalshi.co

    # Liquidity Filters
    min_volume=0,           # Minimum volume to consider
    max_spread=20,          # Maximum bid-ask spread (cents)

    # Momentum Detection
    momentum_window_seconds=5.0,    # Lookback window
    entry_threshold_cents=2,        # Min price move for signal
    convergence_threshold_pct=3.0,  # Min gap shrink %

    # Risk Management
    order_size=5,                   # Contracts per trade
    max_position_per_market=50,     # Max position per market
    max_total_exposure=500.0,       # Max $ exposure total
    stop_loss_cents=2,              # Stop loss from entry
    trailing_stop_cents=2,          # Trailing stop distance
    kalshi_fee_cents=1,             # Kalshi fee per contract
    max_daily_loss=50.0,            # Circuit breaker

    # Execution
    max_markets=10,                 # Max markets to monitor
    cooldown_seconds=2.0,           # Cooldown between trades
    market_scan_interval=60,        # Seconds between market scans
)
```

## Running the Bot

```bash
# Run with default configuration
python -m momentum_bot

# Or import and customize
from momentum_bot.config import Config
from momentum_bot.bot import MomentumBot
import asyncio

config = Config(
    api_key="your-key",
    private_key_path="your-key.pem",
    max_markets=20,
)

bot = MomentumBot(config)
asyncio.run(bot.run())
```

## Output Example

```
============================================================
🚀 MOMENTUM CONVERGENCE BOT STARTING
============================================================
[13:32:39] [BOT] Config: {...}
[13:32:39] [BOT] Starting balance: $1113.30
[13:32:39] [BOT] Fetching markets...
[13:32:47] [BOT] Found 4000 open markets
[13:32:47] [BOT] Found 15 liquid markets (strict)

[13:32:47] [MARKET-A] 🚀 Trader started
[13:32:47] [MARKET-B] 🚀 Trader started
[13:32:48] [WS] Connected! Subscribing to 5 markets...

[13:33:15] [MARKET-A] 📈 Signal: bullish | Gap Δ: -3.5 | YES Δ: +2.5c | Conf: 50%
[13:33:15] [MARKET-A] 🎯 ENTERING: BUY YES @ 47c | Stop: 44c | Trail: 45c
[13:33:15] [MARKET-A] ✅ Entry filled: abc12345

[13:34:00] [BOT] 🔄 Market scan: Found 2 new liquid markets
[13:34:00] [MARKET-C] 🚀 Trader started

[13:35:20] [MARKET-A] 🚪 EXITING (trailing_stop): SELL YES @ 52c
[13:35:20] [MARKET-A] 🟢 Exit filled: trailing_stop | P&L: +$0.25

======================================================================
📊 MOMENTUM BOT STATUS | Runtime: 180s | Balance: $1113.55
🧵 Active Traders: 6
🟢 Realized P&L: +$0.25 | Trades: 2
💼 Exposure: $47.00 / $500.00
🎯 Win Rate: 100.0% (1W / 0L)
======================================================================
```
