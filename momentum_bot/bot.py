"""
Main bot orchestrator.
Ties together all components and manages the trading lifecycle.
"""

import asyncio
import time
import threading
from datetime import datetime
from typing import Dict, List, Optional, Set

from .config import Config
from .client import KalshiClient
from .websocket import WebSocketManager
from .trader import MarketTrader
from .risk import RiskManager
from .tracker import TradeTracker


class MomentumBot:
    """
    Main momentum trading bot orchestrator.

    Responsibilities:
    - Initialize all components
    - Fetch and filter markets
    - Start WebSocket feed
    - Spawn trader threads
    - Continuously monitor for new liquid markets
    - Monitor and report status
    - Handle graceful shutdown
    """

    def __init__(self, config: Config):
        self.config = config
        self.client = KalshiClient(config)
        self.risk_manager = RiskManager(config)
        self.tracker = TradeTracker()

        # Trader threads by ticker
        self.traders: Dict[str, MarketTrader] = {}
        self.traders_lock = threading.Lock()

        # WebSocket manager
        self.ws_manager: Optional[WebSocketManager] = None

        # Market tracking
        self.known_markets: Set[str] = set()
        self.market_liquidity: Dict[str, dict] = {}  # ticker -> {volume, spread, last_seen}

        # State
        self.running = False
        self.start_time: Optional[float] = None

    def _log(self, msg: str):
        """Log with timestamp."""
        ts = datetime.now().strftime("%H:%M:%S")
        print(f"[{ts}] [BOT] {msg}", flush=True)

    def _on_price_update(self, ticker: str, data: dict):
        """Callback for WebSocket price updates."""
        with self.traders_lock:
            if ticker in self.traders:
                self.traders[ticker].update_price(data)

    def fetch_liquid_markets(self, log_output: bool = True) -> List[Dict]:
        """Fetch markets meeting liquidity criteria."""
        if log_output:
            self._log("Fetching markets...")

        all_markets = self.client.get_all_markets(status="open")
        if log_output:
            self._log(f"Found {len(all_markets)} open markets")

        # First try strict liquidity filter
        liquid = self.client.filter_liquid_markets(all_markets)
        if log_output:
            self._log(f"Found {len(liquid)} liquid markets (strict)")

        # If too few, fall back to active markets
        if len(liquid) < 3:
            if log_output:
                self._log("Using relaxed filter for active markets...")
            liquid = self.client.filter_active_markets(all_markets)
            if log_output:
                self._log(f"Found {len(liquid)} active markets")

        # Sort by spread (tightest first), then volume
        liquid.sort(key=lambda m: (m.get('_spread', 999), -m.get('volume', 0)))

        # Update liquidity tracking
        for m in liquid:
            ticker = m['ticker']
            self.market_liquidity[ticker] = {
                'volume': m.get('volume', 0),
                'spread': m.get('_spread', m.get('yes_ask', 100) - m.get('yes_bid', 0)),
                'yes_bid': m.get('yes_bid', 0),
                'yes_ask': m.get('yes_ask', 100),
                'last_seen': time.time()
            }

        return liquid[:self.config.max_markets]

    def _check_liquidity_changes(self, markets: List[Dict]) -> tuple:
        """
        Check for liquidity changes in markets.
        Returns (new_markets, improved_markets, lost_liquidity)
        """
        current_tickers = {m['ticker'] for m in markets}
        tracked_tickers = set(self.traders.keys())

        # New markets we're not tracking yet
        new_markets = []
        for m in markets:
            ticker = m['ticker']
            if ticker not in tracked_tickers:
                new_markets.append(m)

        # Markets with improved liquidity (volume or spread improved)
        improved_markets = []
        for m in markets:
            ticker = m['ticker']
            if ticker in self.market_liquidity:
                old = self.market_liquidity[ticker]
                new_volume = m.get('volume', 0)
                new_spread = m.get('_spread', 999)

                # Check if liquidity improved
                volume_increased = new_volume > old.get('volume', 0) * 1.2  # 20% increase
                spread_tightened = new_spread < old.get('spread', 999) * 0.8  # 20% tighter

                if volume_increased or spread_tightened:
                    improved_markets.append({
                        'ticker': ticker,
                        'volume_change': new_volume - old.get('volume', 0),
                        'spread_change': new_spread - old.get('spread', 999),
                        'market': m
                    })

        # Markets that lost liquidity (no longer in liquid list)
        lost_liquidity = []
        for ticker in tracked_tickers:
            if ticker not in current_tickers:
                lost_liquidity.append(ticker)

        return new_markets, improved_markets, lost_liquidity

    async def _market_scanner_loop(self):
        """Periodically scan for new liquid markets and liquidity changes."""
        while self.running:
            await asyncio.sleep(self.config.market_scan_interval)

            if not self.running:
                break

            try:
                self._log("🔍 Scanning for market changes...")

                # Fetch current liquid markets
                markets = self.fetch_liquid_markets(log_output=False)

                # Check for changes
                new_markets, improved, lost = self._check_liquidity_changes(markets)

                # Log and handle new markets
                if new_markets:
                    self._log(f"📈 Found {len(new_markets)} NEW liquid markets:")
                    for m in new_markets[:5]:  # Show top 5
                        ticker = m['ticker']
                        spread = m.get('_spread', 999)
                        volume = m.get('volume', 0)
                        self._log(f"   + {ticker[:40]}: spread={spread}c vol={volume}")

                        # Start trader if we have capacity
                        if len(self.traders) < self.config.max_markets:
                            self.start_trader(ticker)
                            self.known_markets.add(ticker)

                            # Subscribe to WebSocket
                            if self.ws_manager and self.ws_manager.connected:
                                await self.ws_manager.subscribe([ticker])

                # Log improved liquidity
                if improved:
                    self._log(f"💧 Liquidity improving in {len(improved)} markets:")
                    for info in improved[:3]:
                        ticker = info['ticker']
                        vol_chg = info['volume_change']
                        spr_chg = info['spread_change']
                        self._log(f"   ↑ {ticker[:35]}: vol+{vol_chg} spread{spr_chg:+.0f}c")

                # Handle markets that lost liquidity
                if lost:
                    self._log(f"📉 {len(lost)} markets lost liquidity:")
                    for ticker in lost:
                        self._log(f"   - {ticker[:40]}")
                        # Only stop if no open position
                        with self.traders_lock:
                            if ticker in self.traders:
                                trader = self.traders[ticker]
                                if not trader.position or not trader.position.is_open:
                                    self._log(f"   Stopping trader for {ticker[:30]}")
                                    self.stop_trader(ticker)
                                else:
                                    self._log(f"   Keeping {ticker[:30]} (has open position)")

                if not new_markets and not improved and not lost:
                    self._log("   No significant changes detected")

            except Exception as e:
                self._log(f"Market scan error: {e}")

    def start_trader(self, ticker: str):
        """Start a trader thread for a market."""
        with self.traders_lock:
            if ticker in self.traders:
                return  # Already running

            trader = MarketTrader(ticker, self)
            self.traders[ticker] = trader
            trader.start()

    def stop_trader(self, ticker: str):
        """Stop a trader thread."""
        with self.traders_lock:
            if ticker in self.traders:
                self.traders[ticker].stop()
                del self.traders[ticker]

    def print_status(self):
        """Print current status."""
        if not self.start_time:
            return

        runtime = int(time.time() - self.start_time)
        balance = self.client.get_balance()

        # Get risk summary
        risk = self.risk_manager.get_summary()

        # Get tracker summary
        tracker_summary = self.tracker.get_summary()

        # Format P&L
        pnl = tracker_summary['realized_pnl']
        pnl_str = f"+${pnl:.2f}" if pnl >= 0 else f"-${abs(pnl):.2f}"
        pnl_emoji = "🟢" if pnl >= 0 else "🔴"

        print("\n" + "=" * 70, flush=True)
        print(f"📊 MOMENTUM BOT STATUS | Runtime: {runtime}s | Balance: ${balance:.2f}", flush=True)
        print(f"🧵 Active Traders: {len(self.traders)}", flush=True)
        print(f"{pnl_emoji} Realized P&L: {pnl_str} | Trades: {tracker_summary['total_trades']}", flush=True)
        print(f"💼 Exposure: ${risk['total_exposure']:.2f} / ${risk['max_exposure']:.2f}", flush=True)
        print(f"🎯 Win Rate: {tracker_summary['win_rate']*100:.1f}% ({tracker_summary['winning_trades']}W / {tracker_summary['losing_trades']}L)", flush=True)

        if risk['circuit_breaker']:
            print("⚠️ CIRCUIT BREAKER ACTIVE", flush=True)

        print("-" * 70, flush=True)

        # Show trader status
        with self.traders_lock:
            for ticker, trader in list(self.traders.items())[:10]:
                status = trader.get_status()
                gap = status['gap']
                signals = status['stats']['signals_detected']

                pos = status['position']
                if pos:
                    pnl_unrealized = pos['unrealized_pnl']
                    pos_str = f"| {pos['side']}@{pos['entry']:.0f}c -> {pos['current']}c | uPnL: ${pnl_unrealized:.2f}"
                else:
                    pos_str = ""

                print(f"   {ticker[:30]}: gap={gap:.1f}c | signals={signals} {pos_str}", flush=True)

        print("=" * 70 + "\n", flush=True)

    async def _status_loop(self):
        """Periodic status printing."""
        while self.running:
            await asyncio.sleep(30)
            if self.running:
                self.print_status()

    async def run(self):
        """Main run loop."""
        self.running = True
        self.start_time = time.time()

        self._log("=" * 60)
        self._log("🚀 MOMENTUM CONVERGENCE BOT STARTING")
        self._log("=" * 60)
        self._log(f"Config: {self.config.to_dict()}")

        # Get starting balance
        try:
            balance = self.client.get_balance()
            self.tracker.set_starting_balance(balance)
            self._log(f"Starting balance: ${balance:.2f}")
        except Exception as e:
            self._log(f"Failed to get balance: {e}")
            return

        # Fetch liquid markets
        markets = self.fetch_liquid_markets()
        if not markets:
            self._log("No liquid markets found!")
            return

        tickers = [m['ticker'] for m in markets]

        self._log(f"\nTop {len(tickers)} markets to trade:")
        for m in markets[:10]:
            yes_bid = m.get('yes_bid', 0)
            yes_ask = m.get('yes_ask', 0)
            no_bid = m.get('no_bid', 0)
            volume = m.get('volume', 0)
            spread = m.get('_spread', (yes_ask - yes_bid) if yes_bid and yes_ask else 999)
            self._log(f"   {m['ticker'][:40]}: YES={yes_bid}/{yes_ask} | spread={spread}c | vol={volume}")

        # Create WebSocket manager
        self.ws_manager = WebSocketManager(self.config, self._on_price_update)

        # Start trader threads
        for ticker in tickers:
            self.start_trader(ticker)
            self.known_markets.add(ticker)

        self._log(f"Started {len(self.traders)} trader threads")

        # Start background tasks
        asyncio.create_task(self._status_loop())
        asyncio.create_task(self._market_scanner_loop())

        self._log(f"Market scanner running every {self.config.market_scan_interval}s")

        # Run WebSocket connection (with auto-reconnect)
        try:
            await self.ws_manager.connect(tickers)
        except asyncio.CancelledError:
            self._log("WebSocket cancelled")
        except Exception as e:
            self._log(f"WebSocket error: {e}")

    def stop(self):
        """Graceful shutdown."""
        self._log("🛑 Stopping bot...")
        self.running = False

        # Stop all traders
        with self.traders_lock:
            for ticker in list(self.traders.keys()):
                self.traders[ticker].stop()
            self.traders.clear()

        # Final status
        self.print_status()
        self.tracker.print_summary()

        self._log("Bot stopped")


async def run_bot(config: Config):
    """Run the bot with the given configuration."""
    bot = MomentumBot(config)

    try:
        await bot.run()
    except KeyboardInterrupt:
        bot.stop()
    except Exception as e:
        print(f"Fatal error: {e}")
        bot.stop()
        raise
