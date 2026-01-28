"""
Entry point for the momentum trading bot.

Usage:
    python -m momentum_bot
"""

import asyncio
import os
import signal
import sys
from dotenv import load_dotenv
from .config import Config
from .bot import MomentumBot

# Load environment variables from .env file
load_dotenv()


def main():
    """Main entry point."""
    print("=" * 60)
    print("🎯 KALSHI MOMENTUM CONVERGENCE BOT")
    print("=" * 60)
    print("Monitors YES/NO price convergence and trades momentum")
    print("Press Ctrl+C to stop\n")

    # Load API credentials from environment
    api_key = os.getenv("KALSHI_API_KEY")
    private_key_path = os.getenv("KALSHI_PRIVATE_KEY_PATH", "private_key.pem")
    use_demo = os.getenv("KALSHI_USE_DEMO", "true").lower() == "true"

    if not api_key:
        print("❌ Error: KALSHI_API_KEY not found in environment")
        print("   Create a .env file with: KALSHI_API_KEY=your-api-key")
        sys.exit(1)

    # Configuration
    config = Config(
        # API credentials (from .env)
        api_key=api_key,
        private_key_path=private_key_path,
        use_demo=use_demo,

        # Liquidity requirements (relaxed for demo API)
        min_volume=0,  # Demo has low volume
        max_spread=20,  # Allow wider spreads on demo

        # Momentum detection
        momentum_window_seconds=5.0,  # Look for momentum over 5 seconds
        entry_threshold_cents=2,  # Enter when price moves 2+ cents
        convergence_threshold_pct=3.0,  # Enter when gap shrinks 3%+

        # Risk management
        order_size=5,  # 5 contracts per trade
        max_position_per_market=50,  # Max 50 contracts per market
        max_total_exposure=500.0,  # Max $500 total exposure
        stop_loss_cents=2,  # Stop loss 2 cents below entry
        trailing_stop_cents=2,  # Trailing stop 2 cents below peak
        kalshi_fee_cents=1,  # Kalshi takes 1 cent per contract
        max_daily_loss=50.0,  # Circuit breaker at $50 loss

        # Execution
        max_markets=10,  # Monitor top 10 markets
        cooldown_seconds=2.0,  # Wait 2 seconds between trades
    )

    print(f"Configuration:")
    for key, value in config.to_dict().items():
        print(f"  {key}: {value}")
    print()

    # Create bot
    bot = MomentumBot(config)

    # Handle Ctrl+C gracefully
    def signal_handler(sig, frame):
        print("\n\n⚠️ Shutdown signal received...")
        bot.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Run bot
    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        bot.stop()
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        bot.stop()
        raise


if __name__ == "__main__":
    main()
