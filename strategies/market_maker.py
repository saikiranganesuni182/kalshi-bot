"""
Kalshi Market Maker Strategy
----------------------------
Strategy: Buy at bid, sell at ask to capture the spread.

Profit = Ask Price - Bid Price - Fees

Example:
  - Best Bid: 30c (someone wants to buy YES at 30c)
  - Best Ask: 35c (someone wants to sell YES at 35c)
  - You place: Buy at 31c, Sell at 34c
  - If both fill: Profit = 34c - 31c = 3c per contract
"""

import asyncio
import json
from dataclasses import dataclass
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
from kalshi.websocket import KalshiWebSocket, fetch_active_markets
from kalshi import auth


@dataclass
class OrderbookState:
    """Current state of a market's orderbook"""
    ticker: str
    best_bid: Optional[int] = None  # Highest YES bid (cents)
    best_ask: Optional[int] = None  # Lowest YES ask (cents)
    bid_qty: int = 0                # Quantity at best bid
    ask_qty: int = 0                # Quantity at best ask

    @property
    def spread(self) -> Optional[int]:
        if self.best_bid and self.best_ask:
            return self.best_ask - self.best_bid
        return None

    @property
    def is_tradeable(self) -> bool:
        """Check if spread is wide enough to profit (after fees)"""
        # Kalshi fee is ~1c per contract, so need 3c+ spread to profit
        return self.spread is not None and self.spread >= 3


class MarketMaker:
    """
    Market Making Bot for Kalshi

    Strategy:
    1. Monitor orderbook for markets with good spreads
    2. Place buy order slightly above best bid
    3. Place sell order slightly below best ask
    4. Capture the spread when both orders fill
    """

    def __init__(self, api_key: str = None, private_key_path: str = None):
        self.api_key = api_key or config.API_KEY
        self.private_key_path = private_key_path or config.PRIVATE_KEY_PATH
        self.private_key = auth.load_private_key(self.private_key_path)
        self.client = KalshiClient(self.api_key, self.private_key_path)

        self.orderbooks: dict[str, OrderbookState] = {}
        self.active_orders: dict[str, dict] = {}
        self.positions: dict[str, int] = {}

        # Configuration
        self.max_position = config.DEFAULT_CONFIG['max_position']
        self.min_spread = config.DEFAULT_CONFIG['min_spread']
        self.order_size = config.DEFAULT_CONFIG['order_size']
        self.edge = config.DEFAULT_CONFIG['edge']
        self.live_trading = True
        self.pending_orders: dict[str, list] = {}

    # ==================== Orderbook Processing ====================

    def process_orderbook_snapshot(self, data: dict):
        """Process initial orderbook state"""
        ticker = data.get("market_ticker")
        if not ticker:
            return

        yes_orders = sorted(data.get("yes", []), key=lambda x: x[0], reverse=True)
        no_orders = sorted(data.get("no", []), key=lambda x: x[0], reverse=True)

        state = OrderbookState(ticker=ticker)

        if yes_orders:
            state.best_bid = yes_orders[0][0]
            state.bid_qty = yes_orders[0][1]

        if no_orders:
            state.best_ask = 100 - no_orders[0][0]
            state.ask_qty = no_orders[0][1]

        self.orderbooks[ticker] = state
        self._on_orderbook_update(ticker)

    def process_orderbook_delta(self, data: dict):
        """Process orderbook update"""
        ticker = data.get("market_ticker")
        if not ticker or ticker not in self.orderbooks:
            return

        price = data.get("price")
        delta = data.get("delta")
        side = data.get("side")

        state = self.orderbooks[ticker]

        if side == "yes":
            if delta > 0 and (state.best_bid is None or price > state.best_bid):
                state.best_bid = price
                state.bid_qty = delta
            elif delta < 0 and price == state.best_bid:
                pass

        elif side == "no":
            implied_ask = 100 - price
            if delta > 0 and (state.best_ask is None or implied_ask < state.best_ask):
                state.best_ask = implied_ask
                state.ask_qty = delta

        self._on_orderbook_update(ticker)

    def _on_orderbook_update(self, ticker: str):
        """Called whenever orderbook updates - check for trading opportunity"""
        state = self.orderbooks.get(ticker)
        if not state:
            return

        spread = state.spread

        print(f"[{ticker}] Bid: {state.best_bid}c | Ask: {state.best_ask}c | Spread: {spread}c")

        if state.is_tradeable:
            print(f"  -> OPPORTUNITY: {spread}c spread - profitable to market make!")
            self._evaluate_trade(ticker, state)

    # ==================== Trading Logic ====================

    def _evaluate_trade(self, ticker: str, state: OrderbookState):
        """Evaluate and potentially execute a market making trade"""
        current_position = self.positions.get(ticker, 0)

        if abs(current_position) >= self.max_position:
            print(f"  x Position limit reached ({current_position})")
            return

        our_bid = state.best_bid + self.edge
        our_ask = state.best_ask - self.edge

        our_spread = our_ask - our_bid
        if our_spread < 1:
            print(f"  x Spread too tight after edge ({our_spread}c)")
            return

        print(f"  -> Strategy: Buy at {our_bid}c, Sell at {our_ask}c")
        print(f"  -> Expected profit: {our_spread}c per contract")
        print(f"  -> Order size: {self.order_size} contracts")

        self._place_market_making_orders(ticker, our_bid, our_ask)

    def _place_market_making_orders(self, ticker: str, bid_price: int, ask_price: int):
        """Place both sides of market making trade"""
        if ticker in self.pending_orders and len(self.pending_orders[ticker]) > 0:
            print(f"  - Already have pending orders for {ticker}, skipping")
            return

        if not self.live_trading:
            print(f"  [DRY RUN] Would place BUY {self.order_size} @ {bid_price}c, SELL @ {ask_price}c")
            return

        try:
            order_ids = []

            print(f"  >> Placing BUY order: {self.order_size} @ {bid_price}c")
            buy_order = self.client.place_order(
                ticker=ticker,
                side="yes",
                action="buy",
                price=bid_price,
                count=self.order_size
            )
            buy_id = buy_order.get('order', {}).get('order_id')
            order_ids.append(buy_id)
            print(f"  OK BUY order placed: {buy_id}")

            print(f"  >> Placing SELL order: {self.order_size} @ {ask_price}c")
            sell_order = self.client.place_order(
                ticker=ticker,
                side="yes",
                action="sell",
                price=ask_price,
                count=self.order_size
            )
            sell_id = sell_order.get('order', {}).get('order_id')
            order_ids.append(sell_id)
            print(f"  OK SELL order placed: {sell_id}")

            self.pending_orders[ticker] = order_ids

        except Exception as e:
            print(f"  x Order failed: {e}")
            if order_ids:
                print(f"  ~ Canceling partial orders...")
                for oid in order_ids:
                    try:
                        self.client.cancel_order(oid)
                        print(f"  Canceled: {oid}")
                    except:
                        pass

    # ==================== WebSocket Connection ====================

    async def subscribe(self, ws, tickers: list):
        """Subscribe to orderbook updates"""
        subscription = {
            "id": 1,
            "cmd": "subscribe",
            "params": {
                "channels": ["orderbook_delta"],
                "market_tickers": tickers
            }
        }
        await ws.send(json.dumps(subscription))
        print(f"Subscribed to: {tickers}")

    async def listen(self, ws):
        """Listen for orderbook updates"""
        async for message in ws:
            try:
                data = json.loads(message)
                msg_type = data.get("type")

                if msg_type == "orderbook_snapshot":
                    self.process_orderbook_snapshot(data.get("msg", {}))
                elif msg_type == "orderbook_delta":
                    self.process_orderbook_delta(data.get("msg", {}))
                elif msg_type == "subscribed":
                    print(f"[OK] Subscription confirmed")
                elif msg_type == "error":
                    print(f"[ERROR] {data}")

            except json.JSONDecodeError:
                print(f"[RAW] {message}")

    async def run(self, tickers: list):
        """Main run loop"""
        print("=" * 60)
        print("KALSHI MARKET MAKER BOT")
        print("=" * 60)
        print(f"Mode: {'LIVE TRADING' if self.live_trading else 'DRY RUN (no orders)'}")
        print(f"Strategy: Buy at bid + {self.edge}c, Sell at ask - {self.edge}c")
        print(f"Min spread: {self.min_spread}c | Order size: {self.order_size}")
        print(f"Max position: {self.max_position} contracts")
        print("=" * 60)

        try:
            balance = self.client.get_balance_dollars()
            print(f"Account balance: ${balance:.2f}")
        except Exception as e:
            print(f"Could not fetch balance: {e}")

        print("\nConnecting to WebSocket...")

        ws_headers = auth.get_ws_auth_headers(self.api_key, self.private_key, config.WS_PATH)

        async with websockets.connect(
            config.WS_URL,
            additional_headers=ws_headers
        ) as ws:
            print("Connected!")
            await self.subscribe(ws, tickers)
            await self.listen(ws)


async def main():
    """Run the market maker"""
    print("Fetching active markets...")
    markets = fetch_active_markets(limit=50)

    if not markets:
        print("No active markets found!")
        return

    print(f"\nFound {len(markets)} active markets:")
    print(f"{'Ticker':<40} {'Bid':>5} {'Ask':>5} {'Spread':>7} {'Volume':>8}")
    print("-" * 70)

    for m in markets[:10]:
        bid = m.get('yes_bid', 0)
        ask = m.get('yes_ask', 0)
        spread = ask - bid if bid and ask else 0
        vol = m.get('volume', 0)
        spread_str = f"{spread}c" if spread > 0 else "-"
        print(f"{m['ticker']:<40} {bid:>4}c {ask:>4}c {spread_str:>7} {vol:>8}")

    tickers = [m["ticker"] for m in markets[:5]]

    print(f"\nMonitoring {len(tickers)} markets for opportunities...")
    print("Press Ctrl+C to stop\n")

    bot = MarketMaker()
    await bot.run(tickers)


if __name__ == "__main__":
    asyncio.run(main())
