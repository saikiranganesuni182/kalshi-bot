"""
Kalshi Continuous Trading Bot
-----------------------------
Runs as a background job, continuously scanning for opportunities
and executing trades automatically.
"""

import asyncio
import json
import time
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional

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
    yes_bid: int = 0
    yes_ask: int = 0
    yes_bid_qty: int = 0
    yes_ask_qty: int = 0
    # NO side
    no_bid: int = 0
    no_ask: int = 0
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
            return ('no', 'sell', self.no_ask)
        return ('yes', 'buy', self.yes_ask or 100)

    def best_sell_route(self) -> tuple:
        """Returns (side, action, price) for best way to SELL YES"""
        implied_via_no = 100 - self.no_bid if self.no_bid else 0
        if self.yes_bid and self.yes_bid >= implied_via_no:
            return ('yes', 'sell', self.yes_bid)
        elif self.no_bid:
            return ('no', 'buy', self.no_bid)
        return ('yes', 'sell', self.yes_bid or 0)


class TradingBot:
    """
    Continuous Trading Bot

    Strategies:
    1. Market Making - Place orders on both sides to capture spread
    2. Spread Capture - When the spread is wide, aggressively capture it
    """

    def __init__(self, api_key: str = None, private_key_path: str = None):
        self.api_key = api_key or config.API_KEY
        self.private_key_path = private_key_path or config.PRIVATE_KEY_PATH
        self.private_key = auth.load_private_key(self.private_key_path)
        self.client = KalshiClient(self.api_key, self.private_key_path)

        # State tracking
        self.markets: dict[str, MarketState] = {}
        self.open_orders: dict[str, dict] = {}
        self.positions: dict[str, int] = {}
        self.trades: list[Trade] = []
        self.pnl: float = 0

        # Configuration
        self.config = dict(config.DEFAULT_CONFIG)

        # Stats
        self.stats = {
            'orders_placed': 0,
            'orders_filled': 0,
            'orders_canceled': 0,
            'total_volume': 0,
        }

        self.running = True
        self.start_time = datetime.now()
        self.active_tickers = []

    # ==================== Trading Logic ====================

    def process_snapshot(self, data: dict):
        """Process orderbook snapshot"""
        ticker = data.get('market_ticker')
        if not ticker:
            return

        yes_orders = sorted(data.get('yes', []), key=lambda x: x[0], reverse=True)
        no_orders = sorted(data.get('no', []), key=lambda x: x[0], reverse=True)

        state = MarketState(ticker=ticker)

        if yes_orders:
            state.yes_bid = yes_orders[0][0]
            state.yes_bid_qty = yes_orders[0][1]

        if no_orders:
            state.no_bid = no_orders[0][0]
            state.no_bid_qty = no_orders[0][1]

        state.last_update = datetime.now()
        self.markets[ticker] = state

        self._log(f"[{ticker[:30]}] YES bid:{state.yes_bid}c | NO bid:{state.no_bid}c -> " +
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

        has_pending = any(ticker in str(o) for o in self.open_orders.values())

        if spread >= self.config['aggressive_spread'] and not has_pending:
            self._execute_spread_capture(ticker, state)
        elif spread >= self.config['min_spread'] and not has_pending:
            self._execute_market_making(ticker, state)
        elif abs(position) > 0 and spread <= 2:
            self._close_position(ticker, state, position)

    def _execute_spread_capture(self, ticker: str, state: MarketState):
        """Capture wide spread by placing orders near mid-price"""
        position = self.positions.get(ticker, 0)

        if abs(position) >= self.config['max_position']:
            return

        mid = state.mid_price
        our_bid = int(mid - 2)
        our_ask = int(mid + 2)

        if our_ask - our_bid < 2:
            return

        self._log(f"SPREAD CAPTURE: {ticker} | Spread:{state.spread}c | Mid:{mid:.0f}c")
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

        self._log(f"MARKET MAKE: {ticker} | Bid: {our_bid}c | Ask: {our_ask}c | Spread: {our_ask - our_bid}c")
        self._place_both_orders(ticker, our_bid, our_ask)

    def _place_both_orders(self, ticker: str, bid_price: int, ask_price: int):
        """Place buy and sell limit orders"""
        size = self.config['order_size']

        try:
            buy = self.client.place_order(ticker, 'yes', 'buy', bid_price, size)
            buy_id = buy.get('order', {}).get('order_id')
            if buy_id:
                self.open_orders[buy_id] = {'ticker': ticker, 'side': 'buy', 'price': bid_price, 'time': time.time()}
                self.stats['orders_placed'] += 1
                self._log(f"   OK BUY {size} @ {bid_price}c (timeout: {self.config['order_timeout']}s)")

            sell = self.client.place_order(ticker, 'yes', 'sell', ask_price, size)
            sell_id = sell.get('order', {}).get('order_id')
            if sell_id:
                self.open_orders[sell_id] = {'ticker': ticker, 'side': 'sell', 'price': ask_price, 'time': time.time()}
                self.stats['orders_placed'] += 1
                self._log(f"   OK SELL {size} @ {ask_price}c (timeout: {self.config['order_timeout']}s)")

        except Exception as e:
            self._log(f"   x Order error: {e}")

    def _close_position(self, ticker: str, state: MarketState, position: int):
        """Close an open position"""
        if position > 0:
            price = state.best_bid
            self._log(f"CLOSING LONG: {ticker} | Sell {position} @ {price}c")
            try:
                self.client.place_order(ticker, 'yes', 'sell', price, abs(position))
            except:
                pass
        elif position < 0:
            price = state.best_ask
            self._log(f"CLOSING SHORT: {ticker} | Buy {abs(position)} @ {price}c")
            try:
                self.client.place_order(ticker, 'yes', 'buy', price, abs(position))
            except:
                pass

    async def _manage_orders(self):
        """Cancel stale orders and update positions"""
        while self.running:
            try:
                current_orders = self.client.get_resting_orders()
                current_ids = {o['order_id'] for o in current_orders}

                for oid in list(self.open_orders.keys()):
                    if oid not in current_ids:
                        order = self.open_orders.pop(oid)
                        self.stats['orders_filled'] += 1
                        self._log(f"   FILLED: {order['side'].upper()} @ {order['price']}c")

                now = time.time()
                for o in current_orders:
                    oid = o['order_id']
                    if oid in self.open_orders:
                        age = now - self.open_orders[oid]['time']
                        if age > self.config['order_timeout']:
                            try:
                                self.client.cancel_order(oid)
                                self.open_orders.pop(oid, None)
                                self.stats['orders_canceled'] += 1
                                self._log(f"   CANCELED (stale): {o['action']} @ {o['yes_price']}c")
                            except:
                                pass

                self.positions = self.client.get_positions_dict()

            except Exception as e:
                self._log(f"Order manager error: {e}")

            await asyncio.sleep(self.config['refresh_interval'])

    async def _refresh_markets(self):
        """Periodically refresh market list"""
        while self.running:
            try:
                markets = self.client.fetch_active_markets(limit=50)
                self.active_tickers = [m['ticker'] for m in markets[:10]]

                if markets:
                    self._log(f"\nActive markets: {len(markets)}")
                    for m in markets[:5]:
                        spread = (m.get('yes_ask', 0) or 0) - (m.get('yes_bid', 0) or 0)
                        self._log(f"   {m['ticker'][:40]}: {m.get('yes_bid')}c/{m.get('yes_ask')}c (spread: {spread}c)")

            except Exception as e:
                self._log(f"Market refresh error: {e}")

            await asyncio.sleep(30)

    def _log(self, msg: str):
        """Log with timestamp"""
        ts = datetime.now().strftime("%H:%M:%S")
        print(f"[{ts}] {msg}", flush=True)

    def _print_status(self):
        """Print current status"""
        runtime = (datetime.now() - self.start_time).seconds
        balance = self.client.get_balance_dollars()

        print("\n" + "=" * 60)
        print(f"STATUS | Runtime: {runtime}s | Balance: ${balance:.2f}")
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
        self._log("KALSHI TRADING BOT STARTED")
        self._log("=" * 60)
        self._log(f"Config: {self.config}")
        self._log(f"Balance: ${self.client.get_balance_dollars():.2f}")

        markets = self.client.fetch_active_markets(limit=50)
        self.active_tickers = [m['ticker'] for m in markets[:10]]
        self._log(f"Found {len(markets)} active markets")

        if not self.active_tickers:
            self._log("No active markets found!")
            return

        asyncio.create_task(self._manage_orders())
        asyncio.create_task(self._refresh_markets())

        async def print_status_loop():
            while self.running:
                await asyncio.sleep(30)
                self._print_status()
        asyncio.create_task(print_status_loop())

        ws_headers = auth.get_ws_auth_headers(self.api_key, self.private_key, config.WS_PATH)

        while self.running:
            try:
                self._log("Connecting to WebSocket...")
                async with websockets.connect(config.WS_URL, additional_headers=ws_headers) as ws:
                    self._log("OK Connected!")

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
        self._log("Bot stopping...")

        for oid in list(self.open_orders.keys()):
            try:
                self.client.cancel_order(oid)
                self._log(f"Canceled order: {oid}")
            except:
                pass

        self._print_status()


async def main():
    bot = TradingBot()

    try:
        await bot.run()
    except KeyboardInterrupt:
        bot.stop()


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(line_buffering=True)
    print("Starting Kalshi Trading Bot...", flush=True)
    print("Press Ctrl+C to stop\n", flush=True)
    asyncio.run(main())
