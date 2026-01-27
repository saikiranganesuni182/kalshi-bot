# Kalshi Trading Bot

Automated market-making bot for Kalshi prediction markets.

## Features

- **Multi-threaded trading**: Each market runs in its own thread for parallel scanning
- **Real-time orderbook**: WebSocket connection for live market data
- **Market making strategy**: Buy at bid, sell at ask to capture spread
- **Automatic order management**: Places, monitors, and cancels orders
- **Risk controls**: Position limits, order timeouts, minimum spread requirements

## Files

| File | Description |
|------|-------------|
| `trading_bot_mt.py` | Multi-threaded trading bot (main) |
| `trading_bot.py` | Single-threaded trading bot |
| `market_maker.py` | Market making logic |
| `kalshi_websocket.py` | WebSocket client for orderbook |
| `kalshi_client.py` | REST API client |
| `check_status.py` | Account status checker |
| `get_markets.py` | Market discovery utility |
| `LOGIC_EXPLAINED.md` | Detailed explanation of trading logic |

## Setup

1. Install dependencies:
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

2. Add your API credentials:
   - Create `private_key.pem` with your Kalshi RSA private key
   - Update `API_KEY` in the bot files

3. Run the bot:
```bash
# Multi-threaded (recommended)
python -u trading_bot_mt.py

# Single-threaded
python -u trading_bot.py
```

## Configuration

Edit the config in `trading_bot_mt.py`:

```python
self.config = {
    'min_spread': 3,        # Minimum spread to trade (cents)
    'order_size': 5,        # Contracts per order
    'max_position': 50,     # Max position per market
    'edge': 1,              # Edge to add to bid/ask
    'order_timeout': 10,    # Cancel orders after N seconds
    'aggressive_spread': 10, # Wide spread threshold
    'max_threads': 20,      # Max concurrent market threads
}
```

## Strategy

The bot implements a market-making strategy:

1. **Scan markets**: Find markets with bid/ask spreads
2. **Place orders**: Buy at bid+1, sell at ask-1
3. **Wait for fills**: Orders rest for up to 10 seconds
4. **Capture spread**: Profit when both sides fill
5. **Repeat**: Cancel unfilled orders and try again

## Commands

```bash
# Watch live activity
tail -f /tmp/bot_mt.log

# Check account status
python check_status.py

# Stop the bot
pkill -f trading_bot_mt
```

## Demo vs Production

Currently configured for **DEMO** environment:
- URL: `demo-api.kalshi.co`

To switch to production, update URLs in bot files to:
- URL: `api.elections.kalshi.com`

## Disclaimer

This bot is for educational purposes. Trading involves risk. Use at your own discretion.
