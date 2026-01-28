#!/usr/bin/env python3
"""
Kalshi Trading Bot - Main Entry Point
--------------------------------------
Run this script to start the trading bot.
"""

import asyncio
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bots.trading_bot_mt import TradingBotMT


async def main():
    print("=" * 60)
    print("KALSHI TRADING BOT")
    print("=" * 60)
    print("\nStarting Multi-Threaded Trading Bot...")
    print("Press Ctrl+C to stop\n")

    bot = TradingBotMT()

    try:
        await bot.run()
    except KeyboardInterrupt:
        print("\nShutting down...")
        bot.stop()


if __name__ == "__main__":
    sys.stdout.reconfigure(line_buffering=True)
    asyncio.run(main())
