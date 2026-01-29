#!/usr/bin/env python3
"""
Get active markets from Kalshi to find valid tickers for websocket
"""

import requests
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kalshi import config


def get_active_markets(limit=100):
    """Get active markets (no auth needed for public endpoint)"""
    response = requests.get(
        f"{config.REST_URL}/markets",
        params={"limit": limit, "status": "open"}
    )
    response.raise_for_status()
    return response.json()


def main():
    print("Fetching active markets from Kalshi demo...\n")

    try:
        data = get_active_markets(limit=100)
        markets = data.get("markets", [])

        # Filter for markets with some activity
        active_markets = [
            m for m in markets
            if m.get("volume", 0) > 0 or (m.get("yes_bid", 0) > 0 and m.get("yes_ask", 0) > 0)
        ]

        print(f"Found {len(markets)} total markets, {len(active_markets)} with activity:\n")

        if active_markets:
            print(f"{'Ticker':<35} {'Bid':>6} {'Ask':>6} {'Vol':>8}")
            print("=" * 60)

            for market in active_markets[:20]:
                ticker = market.get("ticker", "")
                yes_bid = market.get("yes_bid", 0)
                yes_ask = market.get("yes_ask", 0)
                volume = market.get("volume", 0)

                print(f"{ticker:<35} {yes_bid:>5}c {yes_ask:>5}c {volume:>8}")
        else:
            print("No markets with activity found in demo.")
            print("\nHere are the first 10 markets anyway:")
            print(f"{'Ticker':<35}")
            print("=" * 35)
            for market in markets[:10]:
                print(f"{market.get('ticker', '')}")

        print("\n" + "=" * 60)
        print("Copy a ticker above to use with the trading bot")

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
