"""
Kalshi Multi-Threaded Trading Bot
---------------------------------
Each contract runs in its own thread for continuous parallel scanning.
"""

import asyncio
import base64
import json
import time
import threading
import requests
from datetime import datetime
from dataclasses import dataclass, field
from queue import Queue
from concurrent.futures import ThreadPoolExecutor
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend
import websockets


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
        self.open_orders = {}  # order_id -> order info
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

        # Skip if no spread or too tight
        if spread < self.bot.config['min_spread']:
            return

        # Skip if we just traded (cooldown)
        if time.time() - self.last_trade_time < 2:
            return

        # Calculate our prices
        if spread >= self.bot.config['aggressive_spread']:
            # Wide spread - place around mid
            our_bid = int(state.mid - 2)
            our_ask = int(state.mid + 2)
            self.log(f"🎯 SPREAD {spread}c | Mid:{state.mid:.0f}c | BUY@{our_bid}c SELL@{our_ask}c")
        else:
            # Normal spread - improve best bid/ask
            our_bid = state.best_bid + self.bot.config['edge']
            our_ask = state.best_ask - self.bot.config['edge']
            self.log(f"📊 SPREAD {spread}c | BUY@{our_bid}c SELL@{our_ask}c")

        # Validate prices
        if our_ask <= our_bid:
            return

        size = self.bot.config['order_size']

        try:
            # Place BUY
            buy = self.place_order('yes', 'buy', our_bid, size)
            buy_id = buy.get('order', {}).get('order_id')
            if buy_id:
                self.open_orders[buy_id] = {'side': 'buy', 'price': our_bid, 'time': time.time()}
                self.stats['placed'] += 1

            # Place SELL
            sell = self.place_order('yes', 'sell', our_ask, size)
            sell_id = sell.get('order', {}).get('order_id')
            if sell_id:
                self.open_orders[sell_id] = {'side': 'sell', 'price': our_ask, 'time': time.time()}
                self.stats['placed'] += 1

            self.last_trade_time = time.time()

        except Exception as e:
            self.log(f"❌ Order error: {e}")

    def manage_orders(self):
        """Cancel stale orders and track fills"""
        try:
            current_orders = self.get_open_orders()
            current_ids = {o['order_id'] for o in current_orders}

            # Check for filled orders
            for oid in list(self.open_orders.keys()):
                if oid not in current_ids:
                    order = self.open_orders.pop(oid)
                    self.stats['filled'] += 1
                    self.log(f"💰 FILLED: {order['side'].upper()} @ {order['price']}c")

            # Cancel stale orders
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
            pass  # Silently handle errors

    def run(self):
        """Main thread loop - continuously monitor and trade"""
        self.log("🚀 Thread started")

        while self.running:
            try:
                # Manage existing orders
                self.manage_orders()

                # Only trade if we don't have open orders
                if len(self.open_orders) == 0:
                    self.execute_trade()

                # Sleep before next iteration
                time.sleep(0.5)

            except Exception as e:
                self.log(f"Error: {e}")
                time.sleep(1)

        self.log("🛑 Thread stopped")

    def stop(self):
        """Stop the thread"""
        self.running = False
        # Cancel all open orders
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

    REST_URL = "https://demo-api.kalshi.co/trade-api/v2"
    WS_URL = "wss://demo-api.kalshi.co/trade-api/ws/v2"
    WS_PATH = "/trade-api/ws/v2"

    def __init__(self, api_key: str, private_key_path: str):
        self.api_key = api_key
        self.private_key = self._load_private_key(private_key_path)

        # Thread management
        self.traders: dict[str, MarketTrader] = {}
        self.lock = threading.Lock()

        # Configuration
        self.config = {
            'min_spread': 3,
            'order_size': 5,
            'max_position': 50,
            'edge': 1,
            'order_timeout': 10,
            'aggressive_spread': 10,
            'max_threads': 20,  # Max concurrent market threads
        }

        self.running = True
        self.start_time = datetime.now()

    def _load_private_key(self, path: str):
        with open(path, "rb") as f:
            return serialization.load_pem_private_key(
                f.read(), password=None, backend=default_backend()
            )

    def _sign(self, timestamp: str, method: str, path: str) -> str:
        msg = f"{timestamp}{method}{path}"
        sig = self.private_key.sign(
            msg.encode(),
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH),
            hashes.SHA256()
        )
        return base64.b64encode(sig).decode()

    def _headers(self, method: str, path: str) -> dict:
        ts = str(int(time.time() * 1000))
        return {
            "KALSHI-ACCESS-KEY": self.api_key,
            "KALSHI-ACCESS-SIGNATURE": self._sign(ts, method, path),
            "KALSHI-ACCESS-TIMESTAMP": ts,
            "Content-Type": "application/json"
        }

    def _ws_headers(self) -> dict:
        ts = str(int(time.time() * 1000))
        return {
            "KALSHI-ACCESS-KEY": self.api_key,
            "KALSHI-ACCESS-SIGNATURE": self._sign(ts, "GET", self.WS_PATH),
            "KALSHI-ACCESS-TIMESTAMP": ts
        }

    # ==================== REST API ====================

    def get_balance(self) -> float:
        path = "/trade-api/v2/portfolio/balance"
        r = requests.get(f"{self.REST_URL}/portfolio/balance", headers=self._headers("GET", path))
        return r.json().get('balance', 0) / 100

    def place_order(self, ticker: str, side: str, action: str, price: int, count: int) -> dict:
        path = "/trade-api/v2/portfolio/orders"
        payload = {
            "ticker": ticker,
            "side": side,
            "action": action,
            "type": "limit",
            "count": count,
            "yes_price": price if side == "yes" else None,
            "no_price": price if side == "no" else None,
        }
        payload = {k: v for k, v in payload.items() if v is not None}
        r = requests.post(f"{self.REST_URL}/portfolio/orders", headers=self._headers("POST", path), json=payload)
        r.raise_for_status()
        return r.json()

    def cancel_order(self, order_id: str):
        path = f"/trade-api/v2/portfolio/orders/{order_id}"
        r = requests.delete(f"{self.REST_URL}/portfolio/orders/{order_id}", headers=self._headers("DELETE", path))
        r.raise_for_status()

    def get_orders(self) -> list:
        path = "/trade-api/v2/portfolio/orders"
        r = requests.get(f"{self.REST_URL}/portfolio/orders", headers=self._headers("GET", path), params={"status": "resting"})
        return r.json().get('orders', [])

    def fetch_markets(self) -> list:
        """Fetch all active markets with pagination"""
        all_markets = []
        cursor = None

        for _ in range(10):
            params = {'limit': 200, 'status': 'open'}
            if cursor:
                params['cursor'] = cursor

            r = requests.get(f"{self.REST_URL}/markets", params=params)
            data = r.json()
            markets = data.get('markets', [])
            cursor = data.get('cursor')
            all_markets.extend(markets)

            if not cursor or not markets:
                break

        # Filter active markets
        active = [
            m for m in all_markets
            if m.get('yes_bid', 0) > 0
            or (m.get('yes_ask') and 0 < m.get('yes_ask', 0) < 100)
            or m.get('volume', 0) > 0
        ]

        # Sort by spread and volume
        def sort_key(m):
            bid = m.get('yes_bid', 0) or 0
            ask = m.get('yes_ask', 0) or 100
            spread = ask - bid if (bid > 0 and ask < 100) else 0
            return (spread, m.get('volume', 0))

        active.sort(key=sort_key, reverse=True)
        return active

    # ==================== Thread Management ====================

    def start_trader(self, ticker: str):
        """Start a trading thread for a market"""
        with self.lock:
            if ticker in self.traders:
                return  # Already running

            if len(self.traders) >= self.config['max_threads']:
                return  # Max threads reached

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

        async with websockets.connect(self.WS_URL, additional_headers=self._ws_headers()) as ws:
            self._log(f"✅ Connected! Subscribing to {len(tickers)} markets...")

            # Subscribe
            sub = {
                "id": 1,
                "cmd": "subscribe",
                "params": {
                    "channels": ["orderbook_delta"],
                    "market_tickers": tickers
                }
            }
            await ws.send(json.dumps(sub))

            # Start trader threads for each market
            for ticker in tickers:
                self.start_trader(ticker)

            self._log(f"🧵 Started {len(self.traders)} trading threads")

            # Listen for messages
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
        print(f"📊 STATUS | Runtime: {runtime}s | Balance: ${balance:.2f}", flush=True)
        print(f"🧵 Active threads: {len(self.traders)}", flush=True)
        print(f"📈 Orders: {total_placed} placed | {total_filled} filled | {total_canceled} canceled", flush=True)
        print("=" * 70, flush=True)

        # Show per-thread stats
        for ticker, trader in list(self.traders.items())[:10]:
            spread = trader.state.spread
            print(f"   {ticker[:35]}: spread={spread}c | orders={trader.stats['placed']}", flush=True)
        print("", flush=True)

    async def run(self):
        """Main run loop"""
        self._log("=" * 60)
        self._log("🤖 MULTI-THREADED TRADING BOT STARTED")
        self._log("=" * 60)
        self._log(f"Config: {self.config}")
        self._log(f"Balance: ${self.get_balance():.2f}")

        # Fetch active markets
        self._log("Fetching markets...")
        markets = self.fetch_markets()
        self._log(f"Found {len(markets)} active markets")

        if not markets:
            self._log("No active markets found!")
            return

        # Get top markets by spread
        tickers = [m['ticker'] for m in markets[:self.config['max_threads']]]

        self._log(f"\nTop {len(tickers)} markets to trade:")
        for m in markets[:10]:
            bid = m.get('yes_bid', 0)
            ask = m.get('yes_ask', 0)
            spread = ask - bid if (bid and ask) else 0
            self._log(f"   {m['ticker'][:40]}: {bid}c/{ask}c spread={spread}c")

        # Start status printer
        async def status_loop():
            while self.running:
                await asyncio.sleep(30)
                self.print_status()

        asyncio.create_task(status_loop())

        # Run websocket handler
        while self.running:
            try:
                await self.handle_websocket(tickers)
            except Exception as e:
                self._log(f"WebSocket error: {e}")
                self._log("Reconnecting in 5 seconds...")
                await asyncio.sleep(5)

    def stop(self):
        """Stop the bot and all threads"""
        self._log("🛑 Stopping bot...")
        self.running = False

        # Stop all trader threads
        for ticker in list(self.traders.keys()):
            self.stop_trader(ticker)

        self.print_status()


async def main():
    API_KEY = "54d3008b-2b1a-4bed-844c-177a8de556e4"
    PRIVATE_KEY_PATH = "private_key.pem"

    bot = TradingBotMT(API_KEY, PRIVATE_KEY_PATH)

    try:
        await bot.run()
    except KeyboardInterrupt:
        bot.stop()


if __name__ == "__main__":
    print("Starting Multi-Threaded Kalshi Trading Bot...", flush=True)
    print("Press Ctrl+C to stop\n", flush=True)
    asyncio.run(main())
