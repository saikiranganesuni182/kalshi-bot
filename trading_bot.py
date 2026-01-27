"""
Kalshi Continuous Trading Bot
-----------------------------
Runs as a background job, continuously scanning for opportunities
and executing trades automatically.
"""

import asyncio
import base64
import json
import time
import requests
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend
import websockets


@dataclass
class Trade:
    """Record of a trade"""
    ticker: str
    side: str
    price: int
    quantity: int
    timestamp: datetime
    order_id: str


@dataclass
class MarketState:
    """Current state of a market"""
    ticker: str
    # YES side
    yes_bid: int = 0          # Best bid to BUY yes
    yes_ask: int = 0          # Best ask to SELL yes
    yes_bid_qty: int = 0
    yes_ask_qty: int = 0
    # NO side
    no_bid: int = 0           # Best bid to BUY no
    no_ask: int = 0           # Best ask to SELL no
    no_bid_qty: int = 0
    no_ask_qty: int = 0
    last_update: datetime = field(default_factory=datetime.now)

    @property
    def best_bid(self) -> int:
        """Best price to BUY YES (max of yes_bid or implied from no_ask)"""
        implied = 100 - self.no_ask if self.no_ask else 0
        return max(self.yes_bid, implied)

    @property
    def best_ask(self) -> int:
        """Best price to SELL YES (min of yes_ask or implied from no_bid)"""
        implied = 100 - self.no_bid if self.no_bid else 100
        return min(self.yes_ask if self.yes_ask else 100, implied)

    @property
    def spread(self) -> int:
        if self.best_bid and self.best_ask:
            return self.best_ask - self.best_bid
        return 0

    @property
    def mid_price(self) -> float:
        if self.best_bid and self.best_ask:
            return (self.best_bid + self.best_ask) / 2
        return 0

    def best_buy_route(self) -> tuple:
        """Returns (side, price) for best way to BUY YES"""
        implied_via_no = 100 - self.no_ask if self.no_ask else 100
        if self.yes_ask and self.yes_ask <= implied_via_no:
            return ('yes', 'buy', self.yes_ask)
        elif self.no_ask:
            return ('no', 'sell', self.no_ask)  # Sell NO = Buy YES
        return ('yes', 'buy', self.yes_ask or 100)

    def best_sell_route(self) -> tuple:
        """Returns (side, action, price) for best way to SELL YES"""
        implied_via_no = 100 - self.no_bid if self.no_bid else 0
        if self.yes_bid and self.yes_bid >= implied_via_no:
            return ('yes', 'sell', self.yes_bid)
        elif self.no_bid:
            return ('no', 'buy', self.no_bid)  # Buy NO = Sell YES
        return ('yes', 'sell', self.yes_bid or 0)


class TradingBot:
    """
    Continuous Trading Bot

    Strategies:
    1. Market Making - Place orders on both sides to capture spread
    2. Spread Capture - When spread is wide, aggressively capture it
    """

    # DEMO environment
    REST_URL = "https://demo-api.kalshi.co/trade-api/v2"
    WS_URL = "wss://demo-api.kalshi.co/trade-api/ws/v2"
    WS_PATH = "/trade-api/ws/v2"

    def __init__(self, api_key: str, private_key_path: str):
        self.api_key = api_key
        self.private_key = self._load_private_key(private_key_path)

        # State tracking
        self.markets: dict[str, MarketState] = {}
        self.open_orders: dict[str, dict] = {}  # order_id -> order
        self.positions: dict[str, int] = {}     # ticker -> position
        self.trades: list[Trade] = []
        self.pnl: float = 0

        # Configuration
        self.config = {
            'min_spread': 3,           # Minimum spread to trade (cents)
            'order_size': 5,           # Contracts per order
            'max_position': 50,        # Max position per market
            'edge': 1,                 # Edge to add to bid/ask
            'order_timeout': 10,       # Cancel orders after N seconds (shorter = faster cycling)
            'aggressive_spread': 10,   # Spread threshold for aggressive entry
            'refresh_interval': 3,     # Seconds between order management cycles
        }

        # Stats
        self.stats = {
            'orders_placed': 0,
            'orders_filled': 0,
            'orders_canceled': 0,
            'total_volume': 0,
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
        """Place a limit order (GTC - good till canceled, we manage timeout ourselves)"""
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

    def get_positions(self) -> dict:
        path = "/trade-api/v2/portfolio/positions"
        r = requests.get(f"{self.REST_URL}/portfolio/positions", headers=self._headers("GET", path))
        positions = {}
        for p in r.json().get('market_positions', []):
            if p.get('position', 0) != 0:
                positions[p['ticker']] = p['position']
        return positions

    def fetch_markets(self) -> list:
        """Fetch ALL markets with pagination and find active ones"""
        all_markets = []
        cursor = None

        # Paginate through all markets
        for _ in range(10):  # Up to 10 pages (2000 markets)
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

        self._log(f"📊 Scanned {len(all_markets)} total markets")

        # Find markets with ANY activity (bid > 0 OR 0 < ask < 100 OR volume > 0)
        active = [
            m for m in all_markets
            if m.get('yes_bid', 0) > 0
            or (m.get('yes_ask') and 0 < m.get('yes_ask', 0) < 100)
            or m.get('volume', 0) > 0
        ]

        # Sort by: first by spread availability, then by volume
        def sort_key(m):
            bid = m.get('yes_bid', 0) or 0
            ask = m.get('yes_ask', 0) or 100
            has_spread = 1 if (bid > 0 and ask < 100) else 0
            return (has_spread, m.get('volume', 0))

        active.sort(key=sort_key, reverse=True)

        if not active:
            self._log("⚠️ No active markets found, monitoring first 50 for activity...")
            return all_markets[:50]

        return active

    # ==================== Trading Logic ====================

    def process_snapshot(self, data: dict):
        """Process orderbook snapshot"""
        ticker = data.get('market_ticker')
        if not ticker:
            return

        yes_orders = sorted(data.get('yes', []), key=lambda x: x[0], reverse=True)
        no_orders = sorted(data.get('no', []), key=lambda x: x[0], reverse=True)

        state = MarketState(ticker=ticker)

        # YES bids - people wanting to BUY YES
        if yes_orders:
            state.yes_bid = yes_orders[0][0]
            state.yes_bid_qty = yes_orders[0][1]

        # NO bids - people wanting to BUY NO (= implied YES asks)
        if no_orders:
            state.no_bid = no_orders[0][0]
            state.no_bid_qty = no_orders[0][1]

        state.last_update = datetime.now()
        self.markets[ticker] = state

        self._log(f"[{ticker[:30]}] YES bid:{state.yes_bid}c | NO bid:{state.no_bid}c → " +
                  f"Best bid:{state.best_bid}c | Best ask:{state.best_ask}c | Spread:{state.spread}c")

        self._evaluate_opportunity(ticker)

    def process_delta(self, data: dict):
        """Process orderbook delta"""
        ticker = data.get('market_ticker')
        if not ticker or ticker not in self.markets:
            return

        state = self.markets[ticker]
        price = data.get('price', 0)
        delta = data.get('delta', 0)
        side = data.get('side')

        # Update the appropriate side
        if side == 'yes' and delta > 0:
            if price > state.yes_bid:
                state.yes_bid = price
                state.yes_bid_qty = delta
        elif side == 'no' and delta > 0:
            if price > state.no_bid:
                state.no_bid = price
                state.no_bid_qty = delta

        state.last_update = datetime.now()
        self._evaluate_opportunity(ticker)

    def _evaluate_opportunity(self, ticker: str):
        """Evaluate trading opportunity"""
        state = self.markets.get(ticker)
        if not state or not state.best_bid or not state.best_ask:
            return

        spread = state.spread
        position = self.positions.get(ticker, 0)

        # Check if we have pending orders for this ticker
        has_pending = any(ticker in str(o) for o in self.open_orders.values())

        # Strategy 1: Wide spread - aggressive capture
        if spread >= self.config['aggressive_spread'] and not has_pending:
            self._execute_spread_capture(ticker, state)

        # Strategy 2: Normal market making
        elif spread >= self.config['min_spread'] and not has_pending:
            self._execute_market_making(ticker, state)

        # Strategy 3: Close position if spread narrowed
        elif abs(position) > 0 and spread <= 2:
            self._close_position(ticker, state, position)

    def _execute_spread_capture(self, ticker: str, state: MarketState):
        """Capture wide spread by placing orders near mid-price"""
        position = self.positions.get(ticker, 0)

        if abs(position) >= self.config['max_position']:
            return

        # Place orders around the mid-price to capture spread
        mid = state.mid_price
        our_bid = int(mid - 2)  # Buy below mid
        our_ask = int(mid + 2)  # Sell above mid

        # Ensure profit after edge
        if our_ask - our_bid < 2:
            return

        self._log(f"🎯 SPREAD CAPTURE: {ticker} | Spread:{state.spread}c | Mid:{mid:.0f}c")
        self._place_both_orders(ticker, our_bid, our_ask)

    def _execute_market_making(self, ticker: str, state: MarketState):
        """Standard market making"""
        position = self.positions.get(ticker, 0)

        if abs(position) >= self.config['max_position']:
            return

        our_bid = state.best_bid + self.config['edge']
        our_ask = state.best_ask - self.config['edge']

        if our_ask - our_bid < 1:
            return

        self._log(f"📊 MARKET MAKE: {ticker} | Bid: {our_bid}c | Ask: {our_ask}c | Spread: {our_ask - our_bid}c")
        self._place_both_orders(ticker, our_bid, our_ask)

    def _place_both_orders(self, ticker: str, bid_price: int, ask_price: int):
        """Place buy and sell limit orders"""
        size = self.config['order_size']

        try:
            # Place BUY order
            buy = self.place_order(ticker, 'yes', 'buy', bid_price, size)
            buy_id = buy.get('order', {}).get('order_id')
            if buy_id:
                self.open_orders[buy_id] = {'ticker': ticker, 'side': 'buy', 'price': bid_price, 'time': time.time()}
                self.stats['orders_placed'] += 1
                self._log(f"   ✅ BUY {size} @ {bid_price}c (timeout: {self.config['order_timeout']}s)")

            # Place SELL order
            sell = self.place_order(ticker, 'yes', 'sell', ask_price, size)
            sell_id = sell.get('order', {}).get('order_id')
            if sell_id:
                self.open_orders[sell_id] = {'ticker': ticker, 'side': 'sell', 'price': ask_price, 'time': time.time()}
                self.stats['orders_placed'] += 1
                self._log(f"   ✅ SELL {size} @ {ask_price}c (timeout: {self.config['order_timeout']}s)")

        except Exception as e:
            self._log(f"   ❌ Order error: {e}")

    def _close_position(self, ticker: str, state: MarketState, position: int):
        """Close an open position"""
        if position > 0:
            # Long position - sell at bid
            price = state.best_bid
            self._log(f"🔄 CLOSING LONG: {ticker} | Sell {position} @ {price}c")
            try:
                self.place_order(ticker, 'yes', 'sell', price, abs(position))
            except:
                pass
        elif position < 0:
            # Short position - buy at ask
            price = state.best_ask
            self._log(f"🔄 CLOSING SHORT: {ticker} | Buy {abs(position)} @ {price}c")
            try:
                self.place_order(ticker, 'yes', 'buy', price, abs(position))
            except:
                pass

    async def _manage_orders(self):
        """Cancel stale orders and update positions"""
        while self.running:
            try:
                # Get current orders from API
                current_orders = self.get_orders()
                current_ids = {o['order_id'] for o in current_orders}

                # Check for filled orders
                for oid in list(self.open_orders.keys()):
                    if oid not in current_ids:
                        order = self.open_orders.pop(oid)
                        self.stats['orders_filled'] += 1
                        self._log(f"   💰 FILLED: {order['side'].upper()} @ {order['price']}c")

                # Cancel stale orders
                now = time.time()
                for o in current_orders:
                    oid = o['order_id']
                    if oid in self.open_orders:
                        age = now - self.open_orders[oid]['time']
                        if age > self.config['order_timeout']:
                            try:
                                self.cancel_order(oid)
                                self.open_orders.pop(oid, None)
                                self.stats['orders_canceled'] += 1
                                self._log(f"   ⏱️ CANCELED (stale): {o['action']} @ {o['yes_price']}c")
                            except:
                                pass

                # Update positions
                self.positions = self.get_positions()

            except Exception as e:
                self._log(f"Order manager error: {e}")

            await asyncio.sleep(self.config['refresh_interval'])

    async def _refresh_markets(self):
        """Periodically refresh market list"""
        while self.running:
            try:
                markets = self.fetch_markets()
                self.active_tickers = [m['ticker'] for m in markets[:10]]

                # Log active markets
                if markets:
                    self._log(f"\n📡 Active markets: {len(markets)}")
                    for m in markets[:5]:
                        spread = (m.get('yes_ask', 0) or 0) - (m.get('yes_bid', 0) or 0)
                        self._log(f"   {m['ticker'][:40]}: {m.get('yes_bid')}c/{m.get('yes_ask')}c (spread: {spread}c)")

            except Exception as e:
                self._log(f"Market refresh error: {e}")

            await asyncio.sleep(30)  # Refresh every 30 seconds

    def _log(self, msg: str):
        """Log with timestamp"""
        ts = datetime.now().strftime("%H:%M:%S")
        print(f"[{ts}] {msg}", flush=True)

    def _print_status(self):
        """Print current status"""
        runtime = (datetime.now() - self.start_time).seconds
        balance = self.get_balance()

        print("\n" + "=" * 60)
        print(f"📊 STATUS | Runtime: {runtime}s | Balance: ${balance:.2f}")
        print("=" * 60)
        print(f"Orders: {self.stats['orders_placed']} placed | {self.stats['orders_filled']} filled | {self.stats['orders_canceled']} canceled")

        if self.positions:
            print(f"Positions: {self.positions}")

        if self.open_orders:
            print(f"Open orders: {len(self.open_orders)}")
        print("=" * 60 + "\n")

    async def run(self):
        """Main run loop"""
        self._log("=" * 60)
        self._log("🤖 KALSHI TRADING BOT STARTED")
        self._log("=" * 60)
        self._log(f"Config: {self.config}")
        self._log(f"Balance: ${self.get_balance():.2f}")

        # Get initial markets
        markets = self.fetch_markets()
        self.active_tickers = [m['ticker'] for m in markets[:10]]
        self._log(f"Found {len(markets)} active markets")

        if not self.active_tickers:
            self._log("No active markets found!")
            return

        # Start background tasks
        asyncio.create_task(self._manage_orders())
        asyncio.create_task(self._refresh_markets())

        # Status printer
        async def print_status_loop():
            while self.running:
                await asyncio.sleep(30)
                self._print_status()
        asyncio.create_task(print_status_loop())

        # Connect to websocket
        while self.running:
            try:
                self._log("Connecting to WebSocket...")
                async with websockets.connect(self.WS_URL, additional_headers=self._ws_headers()) as ws:
                    self._log("✅ Connected!")

                    # Subscribe
                    sub = {
                        "id": 1,
                        "cmd": "subscribe",
                        "params": {
                            "channels": ["orderbook_delta"],
                            "market_tickers": self.active_tickers
                        }
                    }
                    await ws.send(json.dumps(sub))
                    self._log(f"Subscribed to {len(self.active_tickers)} markets")

                    # Listen for messages
                    async for msg in ws:
                        if not self.running:
                            break

                        try:
                            data = json.loads(msg)
                            msg_type = data.get('type')

                            if msg_type == 'orderbook_snapshot':
                                self.process_snapshot(data.get('msg', {}))
                            elif msg_type == 'orderbook_delta':
                                self.process_delta(data.get('msg', {}))

                        except json.JSONDecodeError:
                            pass

            except Exception as e:
                self._log(f"WebSocket error: {e}")
                self._log("Reconnecting in 5 seconds...")
                await asyncio.sleep(5)

    def stop(self):
        """Stop the bot"""
        self.running = False
        self._log("🛑 Bot stopping...")

        # Cancel all open orders
        for oid in list(self.open_orders.keys()):
            try:
                self.cancel_order(oid)
                self._log(f"Canceled order: {oid}")
            except:
                pass

        self._print_status()


async def main():
    API_KEY = "54d3008b-2b1a-4bed-844c-177a8de556e4"
    PRIVATE_KEY_PATH = "private_key.pem"

    bot = TradingBot(API_KEY, PRIVATE_KEY_PATH)

    try:
        await bot.run()
    except KeyboardInterrupt:
        bot.stop()


if __name__ == "__main__":
    import sys
    # Unbuffered output
    sys.stdout.reconfigure(line_buffering=True)
    print("Starting Kalshi Trading Bot...", flush=True)
    print("Press Ctrl+C to stop\n", flush=True)
    asyncio.run(main())
