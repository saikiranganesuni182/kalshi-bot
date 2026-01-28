#!/usr/bin/env python3
"""
Check trading bot status and account state
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kalshi.client import KalshiClient


def main():
    client = KalshiClient()

    print("=" * 60)
    print("KALSHI ACCOUNT STATUS")
    print("=" * 60)

    # Balance
    try:
        balance = client.get_balance_dollars()
        print(f"\nBalance: ${balance:.2f}")
    except Exception as e:
        print(f"\nBalance: Error - {e}")

    # Open orders
    try:
        orders = client.get_resting_orders()
        print(f"\nOpen Orders: {len(orders)}")
        for o in orders:
            print(f"   {o.get('action').upper()} {o.get('remaining_count')} @ {o.get('yes_price')}c - {o.get('ticker')[:40]}")
    except Exception as e:
        print(f"\nOpen Orders: Error - {e}")

    # Positions
    try:
        positions = client.get_positions_dict()
        print(f"\nPositions: {len(positions)}")
        for ticker, pos in positions.items():
            print(f"   {ticker[:40]}: {pos} contracts")
        if not positions:
            print("   (none)")
    except Exception as e:
        print(f"\nPositions: Error - {e}")

    # Active markets
    try:
        markets = client.fetch_active_markets(limit=100)
        print(f"\nActive Markets: {len(markets)}")
        for m in markets[:10]:
            bid = m.get('yes_bid', 0)
            ask = m.get('yes_ask', 0)
            spread = ask - bid if (bid and ask) else 0
            vol = m.get('volume', 0)
            print(f"   {m['ticker'][:40]}: {bid}c/{ask}c spread={spread}c vol={vol}")
    except Exception as e:
        print(f"\nActive Markets: Error - {e}")

    # Bot log
    print(f"\nRecent Bot Activity:")
    try:
        with open('/tmp/bot_output.log', 'r') as f:
            lines = f.readlines()
            for line in lines[-10:]:
                print(f"   {line.rstrip()}")
    except:
        print("   (no log found)")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
