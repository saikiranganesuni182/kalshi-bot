# Kalshi Trading Bot

Automated market-making bot for Kalshi prediction markets.

## Features

- **Multi-threaded trading**: Each market runs in its own thread for parallel scanning
- **Real-time orderbook**: WebSocket connection for live market data
- **Market making strategy**: Buy at bid, sell at ask to capture spread
- **Automatic order management**: Places, monitors, and cancels orders
- **Risk controls**: Position limits, order timeouts, minimum spread requirements

## Project Structure

```
kalshi-bot/
├── kalshi/                    # Core API package
│   ├── __init__.py
│   ├── config.py              # Centralized configuration
│   ├── auth.py                # Authentication/signing logic
│   ├── client.py              # REST API client
│   └── websocket.py           # WebSocket client
│
├── strategies/                # Trading strategies
│   ├── __init__.py
│   └── market_maker.py        # Market making strategy
│
├── bots/                      # Bot implementations
│   ├── __init__.py
│   ├── trading_bot.py         # Single-threaded bot
│   └── trading_bot_mt.py      # Multi-threaded bot (main)
│
├── scripts/                   # Utility scripts
│   ├── run_bot.py             # Main entry point
│   ├── check_status.py        # Account status checker
│   ├── get_markets.py         # Market discovery
│   └── demo.py                # Strategy demonstration
│
├── docs/                      # Documentation
│   └── LOGIC_EXPLAINED.md     # Trading logic explanation
│
├── requirements.txt
├── README.md
├── .gitignore
└── private_key.pem
```

## Setup

1. Install dependencies:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

2. Configure credentials:
   - Place your RSA private key in `private_key.pem`
   - Update `API_KEY` in `kalshi/config.py` (or set `KALSHI_API_KEY` environment variable)

3. Run the bot:
```bash
# Main entry point (recommended)
python scripts/run_bot.py

# Or run directly
python -m bots.trading_bot_mt
```

## Configuration

Edit `kalshi/config.py` to customize:

```python
DEFAULT_CONFIG = {
    'min_spread': 3,           # Minimum spread to trade (cents)
    'order_size': 5,           # Contracts per order
    'max_position': 50,        # Max position per market
    'edge': 1,                 # Edge to add to bid/ask
    'order_timeout': 10,       # Cancel orders after N seconds
    'aggressive_spread': 10,   # Wide spread threshold
    'max_threads': 20,         # Max concurrent market threads
}
```

## Usage

### Run the Trading Bot
```bash
python scripts/run_bot.py
```

### Check Account Status
```bash
python scripts/check_status.py
```

### Discover Active Markets
```bash
python scripts/get_markets.py
```

### Run Strategy Demo
```bash
python scripts/demo.py
```

## Strategy

The bot implements a market-making strategy:

1. **Scan markets**: Find markets with bid/ask spreads
2. **Place orders**: Buy at bid+1, sell at ask-1
3. **Wait for fills**: Orders rest for up to 10 seconds
4. **Capture spread**: Profit when both sides fill
5. **Repeat**: Cancel unfilled orders and try again

## API Package

Use the `kalshi` package in your own code:

```python
from kalshi import KalshiClient, KalshiWebSocket

# REST API
client = KalshiClient()
print(f"Balance: ${client.get_balance_dollars():.2f}")
print(f"Positions: {client.get_positions_dict()}")

# WebSocket
import asyncio
ws = KalshiWebSocket()
asyncio.run(ws.run(['TICKER1', 'TICKER2']))
```

## Demo vs Production

Currently configured for **DEMO** environment.

To switch to production, update `kalshi/config.py`:
```python
REST_URL = "https://api.elections.kalshi.com/trade-api/v2"
WS_URL = "wss://api.elections.kalshi.com/trade-api/ws/v2"
```

## Documentation

See `docs/LOGIC_EXPLAINED.md` for detailed explanation of:
- Authentication flow
- Orderbook structure
- YES/NO contract mechanics
- Trading strategy concepts

## Disclaimer

This bot is for educational purposes. Trading involves risk. Use at your own discretion.
