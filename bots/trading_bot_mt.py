"""
Kalshi Multi-Threaded Trading Bot
---------------------------------
Each contract runs in its own thread for continuous parallel scanning.
"""

import asyncio
import json
import time
import threading
from datetime import datetime
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor

try:
    import websockets
except ImportError:
    print("Please install websockets: pip install websockets")
    exit(1)

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kalshi import config
from kalshi.client import KalshiClient
from kalshi import auth


@dataclass
class MarketState:
    """Current state of a market"""
    ticker: str
    yes_bid: int = 0
    yes_ask: int = 0
    no_bid: int = 0
    no_ask: int = 0
    last_update: float = 0

    @property
    def best_bid(self) -> int:
        implied = 100 - self.no_ask if self.no_ask else 0
        return max(self.yes_bid, implied)

    @property
    def best_ask(self) -> int:
        implied = 100 - self.no_bid if self.no_bid else 100
        return min(self.yes_ask if self.yes_ask else 100, implied)

    @property
    def spread(self) -> int:
        if self.best_bid and self.best_ask:
            return self.best_ask - self.best_bid
        return 0

    @property
    def mid(self) -> float:
        return (self.best_bid + self.best_ask) / 2 if self.best_bid and self.best_ask else 0


class MarketTrader(threading.Thread):
    """
    Individual thread for trading a single market.
    Each market gets its own trader thread that continuously monitors and trades.
    """

    def __init__(self, ticker: str, bot: 'TradingBotMT'):
        super().__init__(daemon=True)
        self.ticker = ticker
        self.bot = bot
        self.state = MarketState(ticker=ticker)
        self.running = True
        self.open_orders = {}
        self.stats = {'placed': 0, 'filled': 0, 'canceled': 0}
        self.last_trade_time = 0

    def log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        print(f"[{ts}] [{self.ticker[:25]}] {msg}", flush=True)

    def update_state(self, yes_bid=None, no_bid=None):
        """Update market state from websocket data"""
        if yes_bid is not None:
            self.state.yes_bid = yes_bid
        if no_bid is not None:
            self.state.no_bid = no_bid
        self.state.last_update = time.time()

    def place_order(self, side: str, action: str, price: int, count: int) -> dict:
        """Place order through the main bot"""
        return self.bot.place_order(self.ticker, side, action, price, count)

    def cancel_order(self, order_id: str):
        """Cancel order through the main bot"""
        return self.bot.cancel_order(order_id)

    def get_open_orders(self) -> list:
        """Get open orders for this ticker"""
        try:
            all_orders = self.bot.get_orders()
            return [o for o in all_orders if o.get('ticker') == self.ticker]
        except:
            return []

    def execute_trade(self):
        """Execute market making trade if opportunity exists"""
        state = self.state
        spread = state.spread

        if spread < self.bot.config['min_spread']:
            return

        if time.time() - self.last_trade_time < 2:
            return

        if spread >= self.bot.config['aggressive_spread']:
            our_bid = int(state.mid - 2)
            our_ask = int(state.mid + 2)
            self.log(f"SPREAD {spread}c | Mid:{state.mid:.0f}c | BUY@{our_bid}c SELL@{our_ask}c")
        else:
            our_bid = state.best_bid + self.bot.config['edge']
            our_ask = state.best_ask - self.bot.config['edge']
            self.log(f"SPREAD {spread}c | BUY@{our_bid}c SELL@{our_ask}c")

        if our_ask <= our_bid:
            return

        size = self.bot.config['order_size']

        try:
            buy = self.place_order('yes', 'buy', our_bid, size)
            buy_id = buy.get('order', {}).get('order_id')
            if buy_id:
                self.open_orders[buy_id] = {'side': 'buy', 'price': our_bid, 'time': time.time()}
                self.stats['placed'] += 1

            sell = self.place_order('yes', 'sell', our_ask, size)
            sell_id = sell.get('order', {}).get('order_id')
            if sell_id:
                self.open_orders[sell_id] = {'side': 'sell', 'price': our_ask, 'time': time.time()}
                self.stats['placed'] += 1

            self.last_trade_time = time.time()

        except Exception as e:
            self.log(f"x Order error: {e}")

    def manage_orders(self):
        """Cancel stale orders and track fills"""
        try:
            current_orders = self.get_open_orders()
            current_ids = {o['order_id'] for o in current_orders}

            for oid in list(self.open_orders.keys()):
                if oid not in current_ids:
                    order = self.open_orders.pop(oid)
                    self.stats['filled'] += 1
                    self.log(f"FILLED: {order['side'].upper()} @ {order['price']}c")

            now = time.time()
            timeout = self.bot.config['order_timeout']
            for o in current_orders:
                oid = o['order_id']
                if oid in self.open_orders:
                    age = now - self.open_orders[oid]['time']
                    if age > timeout:
                        try:
                            self.cancel_order(oid)
                            self.open_orders.pop(oid, None)
                            self.stats['canceled'] += 1
                        except:
                            pass

        except Exception as e:
            pass

    def run(self):
        """Main thread loop - continuously monitor and trade"""
        self.log("Thread started")

        while self.running:
            try:
                self.manage_orders()

                if len(self.open_orders) == 0:
                    self.execute_trade()

                time.sleep(0.5)

            except Exception as e:
                self.log(f"Error: {e}")
                time.sleep(1)

        self.log("Thread stopped")

    def stop(self):
        """Stop the thread"""
        self.running = False
        for oid in list(self.open_orders.keys()):
            try:
                self.cancel_order(oid)
            except:
                pass


class TradingBotMT:
    """
    Multi-Threaded Trading Bot
    - Main thread handles WebSocket connection and market discovery
    - Each market gets its own trading thread
    """

    def __init__(self, api_key: str = None, private_key_path: str = None):
        self.api_key = api_key or config.API_KEY
        self.private_key_path = private_key_path or config.PRIVATE_KEY_PATH
        self.private_key = auth.load_private_key(self.private_key_path)
        self.client = KalshiClient(self.api_key, self.private_key_path)

        # Thread management
        self.traders: dict[str, MarketTrader] = {}
        self.lock = threading.Lock()

        # Configuration
        self.config = dict(config.DEFAULT_CONFIG)

        self.running = True
        self.start_time = datetime.now()

    # ==================== REST API ====================

    def get_balance(self) -> float:
        return self.client.get_balance_dollars()

    def place_order(self, ticker: str, side: str, action: str, price: int, count: int) -> dict:
        return self.client.place_order(ticker, side, action, price, count)

    def cancel_order(self, order_id: str):
        return self.client.cancel_order(order_id)

    def get_orders(self) -> list:
        return self.client.get_resting_orders()

    def fetch_markets(self) -> list:
        return self.client.fetch_active_markets(limit=100)

    # ==================== Thread Management ====================

    def start_trader(self, ticker: str):
        """Start a trading thread for a market"""
        with self.lock:
            if ticker in self.traders:
                return

            if len(self.traders) >= self.config['max_threads']:
                return

            trader = MarketTrader(ticker, self)
            self.traders[ticker] = trader
            trader.start()

    def stop_trader(self, ticker: str):
        """Stop a trading thread"""
        with self.lock:
            if ticker in self.traders:
                self.traders[ticker].stop()
                del self.traders[ticker]

    def update_market(self, ticker: str, yes_bid=None, no_bid=None):
        """Update market state from websocket"""
        with self.lock:
            if ticker in self.traders:
                self.traders[ticker].update_state(yes_bid=yes_bid, no_bid=no_bid)

    # ==================== WebSocket ====================

    async def handle_websocket(self, tickers: list):
        """Handle websocket connection and messages"""
        self._log("Connecting to WebSocket...")

        ws_headers = auth.get_ws_auth_headers(self.api_key, self.private_key, config.WS_PATH)

        async with websockets.connect(config.WS_URL, additional_headers=ws_headers) as ws:
            self._log(f"OK Connected! Subscribing to {len(tickers)} markets...")

            sub = {
                "id": 1,
                "cmd": "subscribe",
                "params": {
                    "channels": ["orderbook_delta"],
                    "market_tickers": tickers
                }
            }
            await ws.send(json.dumps(sub))

            for ticker in tickers:
                self.start_trader(ticker)

            self._log(f"Started {len(self.traders)} trading threads")

            async for msg in ws:
                if not self.running:
                    break

                try:
                    data = json.loads(msg)
                    msg_type = data.get('type')

                    if msg_type == 'orderbook_snapshot':
                        self._handle_snapshot(data.get('msg', {}))
                    elif msg_type == 'orderbook_delta':
                        self._handle_delta(data.get('msg', {}))

                except json.JSONDecodeError:
                    pass

    def _handle_snapshot(self, data: dict):
        """Handle orderbook snapshot"""
        ticker = data.get('market_ticker')
        if not ticker:
            return

        yes_orders = data.get('yes', [])
        no_orders = data.get('no', [])

        yes_bid = yes_orders[0][0] if yes_orders else 0
        no_bid = no_orders[0][0] if no_orders else 0

        self.update_market(ticker, yes_bid=yes_bid, no_bid=no_bid)

    def _handle_delta(self, data: dict):
        """Handle orderbook delta"""
        ticker = data.get('market_ticker')
        if not ticker:
            return

        price = data.get('price', 0)
        side = data.get('side')

        if side == 'yes':
            self.update_market(ticker, yes_bid=price)
        elif side == 'no':
            self.update_market(ticker, no_bid=price)

    def _log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        print(f"[{ts}] [MAIN] {msg}", flush=True)

    def print_status(self):
        """Print current status"""
        runtime = (datetime.now() - self.start_time).seconds
        balance = self.get_balance()

        total_placed = sum(t.stats['placed'] for t in self.traders.values())
        total_filled = sum(t.stats['filled'] for t in self.traders.values())
        total_canceled = sum(t.stats['canceled'] for t in self.traders.values())

        print("\n" + "=" * 70, flush=True)
        print(f"STATUS | Runtime: {runtime}s | Balance: ${balance:.2f}", flush=True)
        print(f"Active threads: {len(self.traders)}", flush=True)
        print(f"Orders: {total_placed} placed | {total_filled} filled | {total_canceled} canceled", flush=True)
        print("=" * 70, flush=True)

        for ticker, trader in list(self.traders.items())[:10]:
            spread = trader.state.spread
            print(f"   {ticker[:35]}: spread={spread}c | orders={trader.stats['placed']}", flush=True)
        print("", flush=True)

    async def run(self):
        """Main run loop"""
        self._log("=" * 60)
        self._log("MULTI-THREADED TRADING BOT STARTED")
        self._log("=" * 60)
        self._log(f"Config: {self.config}")
        self._log(f"Balance: ${self.get_balance():.2f}")

        self._log("Fetching markets...")
        markets = self.fetch_markets()
        self._log(f"Found {len(markets)} active markets")

        if not markets:
            self._log("No active markets found!")
            return

        tickers = [m['ticker'] for m in markets[:self.config['max_threads']]]

        self._log(f"\nTop {len(tickers)} markets to trade:")
        for m in markets[:10]:
            bid = m.get('yes_bid', 0)
            ask = m.get('yes_ask', 0)
            spread = ask - bid if (bid and ask) else 0
            self._log(f"   {m['ticker'][:40]}: {bid}c/{ask}c spread={spread}c")

        async def status_loop():
            while self.running:
                await asyncio.sleep(30)
                self.print_status()

        asyncio.create_task(status_loop())

        while self.running:
            try:
                await self.handle_websocket(tickers)
            except Exception as e:
                self._log(f"WebSocket error: {e}")
                self._log("Reconnecting in 5 seconds...")
                await asyncio.sleep(5)

    def stop(self):
        """Stop the bot and all threads"""
        self._log("Stopping bot...")
        self.running = False

        for ticker in list(self.traders.keys()):
            self.stop_trader(ticker)

        self.print_status()


async def main():
    bot = TradingBotMT()

    try:
        await bot.run()
    except KeyboardInterrupt:
        bot.stop()


if __name__ == "__main__":
    print("Starting Multi-Threaded Kalshi Trading Bot...", flush=True)
    print("Press Ctrl+C to stop\n", flush=True)
    asyncio.run(main())
