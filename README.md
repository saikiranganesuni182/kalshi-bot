# Kalshi Momentum Convergence Trading Bot

A multi-threaded trading bot for Kalshi prediction markets that detects momentum through YES/NO price convergence and automatically trades with stop-loss protection.

---

## What This Bot Does

### The Core Idea

In Kalshi prediction markets:
- **YES contracts** = probability the event happens (priced 1-99 cents)
- **NO contracts** = probability the event doesn't happen (priced 1-99 cents)
- In theory: **YES + NO = 100 cents**

When there's a **gap** between YES and NO prices, it means the market hasn't fully priced in the probability. When this gap **shrinks**, it signals **momentum** - someone knows something and is buying.

### Example

```
Initial State:
  YES = 30 cents (30% chance)
  NO  = 60 cents (60% chance)
  GAP = 100 - 30 - 60 = 10 cents

5 seconds later:
  YES = 35 cents (rising!)
  NO  = 60 cents (unchanged)
  GAP = 100 - 35 - 60 = 5 cents (shrinking!)

Signal: BULLISH MOMENTUM → Buy YES
```

The gap shrinking from 10 to 5 cents while YES is rising = someone is buying YES aggressively = momentum detected.

---

## How It Works

### 1. Market Discovery & Liquidity Check

```
Every 60 seconds:
  1. Fetch all open markets from Kalshi API
  2. Filter by liquidity:
     - Has active bids (yes_bid > 0)
     - Spread not too wide (< 20 cents)
     - Optionally: minimum volume
  3. Start a trader thread for each liquid market
  4. Remove traders from markets that lost liquidity
```

### 2. Real-Time Price Monitoring (WebSocket)

```
Kalshi WebSocket sends orderbook updates:
  - Snapshots: Full orderbook state
  - Deltas: Price/quantity changes

Bot maintains price history for each market:
  [t=0] YES=30, NO=60, gap=10
  [t=1] YES=31, NO=60, gap=9
  [t=2] YES=32, NO=59, gap=9
  [t=3] YES=33, NO=58, gap=9
  [t=4] YES=34, NO=58, gap=8
  [t=5] YES=35, NO=58, gap=7  ← Momentum detected!
```

### 3. Momentum Detection (Every 500ms)

```python
# Calculate changes over 5-second window
gap_change = current_gap - old_gap        # Negative = converging
yes_change = current_yes - old_yes        # Positive = YES rising

# Generate signal
if gap_change < -3% AND yes_change >= 2 cents:
    signal = BULLISH  → Buy YES

if gap_change < -3% AND yes_change <= -2 cents:
    signal = BEARISH  → Buy NO
```

### 4. Entry with Stop-Loss

When momentum signal detected:

```
1. Check risk limits (position size, exposure, daily loss)

2. Place entry order:
   - BULLISH: Buy YES at current_price + 1 cent
   - BEARISH: Buy NO at current_price + 1 cent

3. Set stop-loss immediately:
   stop_loss = entry_price - stop_loss_cents - kalshi_fee

   Example: Entry at 45c, stop=2c, fee=1c
   → Stop-loss at 42c (max loss = 3 cents/contract)

4. Set trailing stop:
   trailing_stop = entry_price - trailing_stop_cents
```

### 5. Position Management

```
Every 200ms while holding position:

1. UPDATE TRAILING STOP (lock in profits):
   if current_price > highest_seen:
       highest_seen = current_price
       trailing_stop = highest_seen - 2 cents

   Example progression:
     Entry: 45c, trail=43c
     Price→47c: trail=45c (breakeven!)
     Price→50c: trail=48c (profit locked!)
     Price→48c: EXIT at 48c (+3 cents profit)

2. CHECK STOP-LOSS:
   if current_price <= stop_loss:
       EXIT immediately (accept small loss)

3. CHECK REVERSAL:
   if holding YES and BEARISH signal appears:
       Close YES position
       Open NO position (flip!)
```

### 6. Exit Scenarios

| Scenario | Trigger | Result |
|----------|---------|--------|
| **Stop-Loss** | Price drops to stop_loss | Small controlled loss |
| **Trailing Stop** | Price drops from peak | Profit locked in |
| **Reversal** | Opposite momentum signal | Close & flip position |
| **Shutdown** | Ctrl+C | Exit all positions |

---

## Multi-Threading Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    MAIN THREAD (Orchestrator)               │
│  - Initializes API client, risk manager, trade tracker      │
│  - Fetches liquid markets                                   │
│  - Spawns trader threads                                    │
│  - Runs market scanner every 60s                            │
└─────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│ WebSocket     │   │ Market        │   │ Status        │
│ Listener      │   │ Scanner       │   │ Printer       │
│ (async)       │   │ (async 60s)   │   │ (async 30s)   │
└───────┬───────┘   └───────────────┘   └───────────────┘
        │
        │ Price updates broadcast to all traders
        ▼
┌─────────────────────────────────────────────────────────────┐
│                    TRADER THREADS (1 per market)            │
├─────────────┬─────────────┬─────────────┬─────────────┬────┤
│  Market A   │  Market B   │  Market C   │  Market D   │... │
│  Thread     │  Thread     │  Thread     │  Thread     │    │
├─────────────┼─────────────┼─────────────┼─────────────┼────┤
│ -Price hist │ -Price hist │ -Price hist │ -Price hist │    │
│ -Momentum   │ -Momentum   │ -Momentum   │ -Momentum   │    │
│ -Position   │ -Position   │ -Position   │ -Position   │    │
│ -Orders     │ -Orders     │ -Orders     │ -Orders     │    │
└─────────────┴─────────────┴─────────────┴─────────────┴────┘
```

**Why multi-threaded?**
- Each market can have different momentum timing
- One slow market doesn't block others
- Parallel order execution
- Independent stop-loss monitoring

---

## Risk Management

### Pre-Trade Checks

```python
Before every trade:
  ✓ Circuit breaker not tripped (daily loss < $50)
  ✓ Position limit not exceeded (< 50 contracts/market)
  ✓ Total exposure within limit (< $500)
  ✓ Cooldown period passed (> 2 seconds since last trade)
```

### Stop-Loss Calculation

```
stop_loss_price = entry_price - stop_loss_cents - kalshi_fee

Example:
  Entry: 45 cents
  Stop loss: 2 cents
  Kalshi fee: 1 cent

  Stop price = 45 - 2 - 1 = 42 cents
  Max loss per contract = 3 cents ($0.03)
  Max loss for 5 contracts = 15 cents ($0.15)
```

### Trailing Stop Logic

```
As price rises, trailing stop moves up (never down):

  Entry at 45c → trail at 43c
  Price rises to 48c → trail moves to 46c
  Price rises to 52c → trail moves to 50c
  Price drops to 50c → EXIT (profit = 50 - 45 = 5 cents)

The trailing stop "ratchets up" to lock in gains.
```

---

## Configuration

```python
config = Config(
    # API
    api_key="your-api-key",
    private_key_path="private_key.pem",
    use_demo=True,  # Use demo API for testing

    # Liquidity Filters
    min_volume=0,        # Minimum trading volume
    max_spread=20,       # Maximum bid-ask spread (cents)

    # Momentum Detection
    momentum_window_seconds=5.0,    # Lookback window
    entry_threshold_cents=2,        # Min price move to trigger
    convergence_threshold_pct=3.0,  # Min gap shrink %

    # Risk Management
    order_size=5,                   # Contracts per trade
    max_position_per_market=50,     # Max position per market
    max_total_exposure=500.0,       # Max $ at risk total
    stop_loss_cents=2,              # Stop loss distance
    trailing_stop_cents=2,          # Trailing stop distance
    kalshi_fee_cents=1,             # Kalshi fee per contract
    max_daily_loss=50.0,            # Circuit breaker

    # Execution
    max_markets=10,                 # Max markets to monitor
    cooldown_seconds=2.0,           # Cooldown between trades
    market_scan_interval=60,        # Scan for new markets (seconds)
)
```

---

## Running the Bot

### Prerequisites

```bash
pip install -r requirements.txt
```

### Start the Momentum Bot

```bash
python -m momentum_bot
```

### Example Output

```
============================================================
🚀 MOMENTUM CONVERGENCE BOT STARTING
============================================================
[13:45:33] Starting balance: $1113.30
[13:45:39] Found 4000 open markets
[13:45:39] Found 16 liquid markets (strict)

[13:45:39] [MARKET-A] 🚀 Trader started
[13:45:39] [MARKET-B] 🚀 Trader started
[13:45:40] [WS] Connected! Subscribing to 5 markets...

[13:46:15] [MARKET-A] 📈 Signal: bullish | Gap Δ: -4.2 | YES Δ: +3.0c
[13:46:15] [MARKET-A] 🎯 ENTERING: BUY YES @ 47c | Stop: 44c | Trail: 45c
[13:46:15] [MARKET-A] ✅ Entry filled

[13:47:30] [MARKET-A] 🚪 EXITING (trailing_stop): SELL YES @ 52c
[13:47:30] [MARKET-A] 🟢 Exit: trailing_stop | P&L: +$0.25

======================================================================
📊 MOMENTUM BOT STATUS | Runtime: 180s | Balance: $1113.55
🧵 Active Traders: 5
🟢 Realized P&L: +$0.25 | Trades: 2
💼 Exposure: $0.00 / $500.00
🎯 Win Rate: 100.0% (1W / 0L)
======================================================================
```

---

## Project Structure

```
momentum_bot/
├── __init__.py      # Package init
├── __main__.py      # Entry point
├── auth.py          # RSA authentication
├── client.py        # REST API client
├── config.py        # Configuration
├── models.py        # Data models
├── websocket.py     # Real-time price feed
├── strategy.py      # Momentum detection
├── risk.py          # Risk management
├── tracker.py       # P&L tracking
├── trader.py        # Per-market trader thread
├── bot.py           # Main orchestrator
└── ARCHITECTURE.md  # Detailed architecture docs
```

### Legacy Files (Market Making Bot)

| File | Description |
|------|-------------|
| `trading_bot_mt.py` | Multi-threaded market making bot |
| `trading_bot.py` | Single-threaded trading bot |

---

## Key Concepts Summary

| Concept | Description |
|---------|-------------|
| **Gap** | 100 - YES - NO; represents market inefficiency |
| **Convergence** | Gap shrinking = prices moving toward equilibrium |
| **Momentum** | Convergence + price direction = trading signal |
| **Stop-Loss** | Fixed exit point to limit losses |
| **Trailing Stop** | Moving exit point to lock in profits |
| **Multi-threading** | Each market runs independently in parallel |
| **Circuit Breaker** | Stops all trading if daily loss limit hit |

---

## Commands

```bash
# Run momentum bot
python -m momentum_bot

# Stop the bot
pkill -f momentum_bot

# Check account status
python check_status.py
```

---

## Demo vs Production

Currently configured for **DEMO** environment:
- REST API: `demo-api.kalshi.co`
- WebSocket: `wss://demo-api.kalshi.co`

To switch to production, set `use_demo=False` in config:
- REST API: `trading-api.kalshi.co`
- WebSocket: `wss://trading-api.kalshi.co`

---

## Disclaimer

This bot is for educational purposes. Trading prediction markets involves risk. Always test with the demo API before using real money.
