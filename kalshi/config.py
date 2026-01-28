"""
Kalshi Bot Configuration
------------------------
Centralized configuration for all bot components.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env file from project root
_project_root = Path(__file__).parent.parent
load_dotenv(_project_root / ".env")

# API Credentials (loaded from .env)
API_KEY = os.environ.get("KALSHI_API_KEY")
PRIVATE_KEY_PATH = os.environ.get("KALSHI_PRIVATE_KEY_PATH", "private_key.pem")

if not API_KEY:
    raise ValueError("KALSHI_API_KEY not set. Please create a .env file with your API key.")

# Environment URLs (Demo)
REST_URL = "https://demo-api.kalshi.co/trade-api/v2"
WS_URL = "wss://demo-api.kalshi.co/trade-api/ws/v2"
WS_PATH = "/trade-api/ws/v2"

# Production URLs (uncomment to switch)
# REST_URL = "https://api.elections.kalshi.com/trade-api/v2"
# WS_URL = "wss://api.elections.kalshi.com/trade-api/ws/v2"

# Trading Configuration
DEFAULT_CONFIG = {
    'min_spread': 3,           # Minimum spread to trade (cents)
    'order_size': 5,           # Contracts per order
    'max_position': 50,        # Max position per market
    'edge': 1,                 # Edge to add to bid/ask (cents)
    'order_timeout': 10,       # Cancel orders after N seconds
    'aggressive_spread': 10,   # Spread threshold for aggressive entry
    'refresh_interval': 3,     # Seconds between order management cycles
    'max_threads': 20,         # Max concurrent market threads
}
