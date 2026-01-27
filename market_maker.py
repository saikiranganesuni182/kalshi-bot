"""
Kalshi Market Maker Bot
-----------------------
Strategy: Buy at bid, sell at ask to capture the spread.

Profit = Ask Price - Bid Price - Fees

Example:
  - Best Bid: 30c (someone wants to buy YES at 30c)
  - Best Ask: 35c (someone wants to sell YES at 35c)
  - You place: Buy at 31c, Sell at 34c
  - If both fill: Profit = 34c - 31c = 3c per contract
"""

import asyncio
import base64
import json
import time
import requests
from dataclasses import dataclass
from typing import Optional
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend

try:
    import websockets
except ImportError:
    print("Please install websockets: pip install websockets")
    exit(1)


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

    # Demo environment URLs
    REST_URL = "https://demo-api.kalshi.co/trade-api/v2"
    WS_URL = "wss://demo-api.kalshi.co/trade-api/ws/v2"
    WS_PATH = "/trade-api/ws/v2"

    def __init__(self, api_key: str, private_key_path: str):
        self.api_key = api_key
        self.private_key = self._load_private_key(private_key_path)
        self.orderbooks: dict[str, OrderbookState] = {}
        self.active_orders: dict[str, dict] = {}  # order_id -> order details
        self.positions: dict[str, int] = {}       # ticker -> position size

        # Configuration
        self.max_position = 100          # Max contracts per market
        self.min_spread = 3              # Minimum spread to trade (cents)
        self.order_size = 10             # Contracts per order
        self.edge = 1                    # How much to improve bid/ask (cents)
        self.live_trading = True         # Set to False to disable order placement
        self.pending_orders: dict[str, list] = {}  # ticker -> [order_ids]

    def _load_private_key(self, path: str):
        with open(path, "rb") as key_file:
            return serialization.load_pem_private_key(
                key_file.read(),
                password=None,
                backend=default_backend()
            )

    def _sign_request(self, timestamp: str, method: str, path: str) -> str:
        message = f"{timestamp}{method}{path}"
        signature = self.private_key.sign(
            message.encode('utf-8'),
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.DIGEST_LENGTH
            ),
            hashes.SHA256()
        )
        return base64.b64encode(signature).decode('utf-8')

    def _get_headers(self, method: str, path: str) -> dict:
        timestamp = str(int(time.time() * 1000))
        signature = self._sign_request(timestamp, method, path)
        return {
            "KALSHI-ACCESS-KEY": self.api_key,
            "KALSHI-ACCESS-SIGNATURE": signature,
            "KALSHI-ACCESS-TIMESTAMP": timestamp,
            "Content-Type": "application/json"
        }

    def _get_ws_headers(self) -> dict:
        timestamp = str(int(time.time() * 1000))
        signature = self._sign_request(timestamp, "GET", self.WS_PATH)
        return {
            "KALSHI-ACCESS-KEY": self.api_key,
            "KALSHI-ACCESS-SIGNATURE": signature,
            "KALSHI-ACCESS-TIMESTAMP": timestamp
        }

    # ==================== REST API Methods ====================

    def get_balance(self) -> dict:
        """Get account balance"""
        path = "/trade-api/v2/portfolio/balance"
        response = requests.get(
            f"{self.REST_URL}/portfolio/balance",
            headers=self._get_headers("GET", path)
        )
        response.raise_for_status()
        return response.json()

    def place_order(
        self,
        ticker: str,
        side: str,      # "yes" or "no"
        action: str,    # "buy" or "sell"
        price: int,     # Price in cents (1-99)
        count: int      # Number of contracts
    ) -> dict:
        """
        Place an order on Kalshi

        To BUY YES at 30c:  side="yes", action="buy", price=30
        To SELL YES at 35c: side="yes", action="sell", price=35

        Alternative (equivalent):
        To SELL YES at 35c: side="no", action="buy", price=65 (100-35)
        """
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

        # Remove None values
        payload = {k: v for k, v in payload.items() if v is not None}

        response = requests.post(
            f"{self.REST_URL}/portfolio/orders",
            headers=self._get_headers("POST", path),
            json=payload
        )
        response.raise_for_status()
        return response.json()

    def cancel_order(self, order_id: str) -> dict:
        """Cancel an existing order"""
        path = f"/trade-api/v2/portfolio/orders/{order_id}"
        response = requests.delete(
            f"{self.REST_URL}/portfolio/orders/{order_id}",
            headers=self._get_headers("DELETE", path)
        )
        response.raise_for_status()
        return response.json()

    def get_positions(self) -> dict:
        """Get current positions"""
        path = "/trade-api/v2/portfolio/positions"
        response = requests.get(
            f"{self.REST_URL}/portfolio/positions",
            headers=self._get_headers("GET", path)
        )
        response.raise_for_status()
        return response.json()

    def get_open_orders(self) -> dict:
        """Get open/resting orders"""
        path = "/trade-api/v2/portfolio/orders"
        response = requests.get(
            f"{self.REST_URL}/portfolio/orders",
            headers=self._get_headers("GET", path),
            params={"status": "resting"}
        )
        response.raise_for_status()
        return response.json()

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
            # Convert NO bid to YES ask
            state.best_ask = 100 - no_orders[0][0]
            state.ask_qty = no_orders[0][1]

        self.orderbooks[ticker] = state
        self._on_orderbook_update(ticker)

    def process_orderbook_delta(self, data: dict):
        """Process orderbook update"""
        ticker = data.get("market_ticker")
        if not ticker or ticker not in self.orderbooks:
            return

        # For simplicity, we'll recalculate from the delta
        # In production, you'd want to maintain full book state
        price = data.get("price")
        delta = data.get("delta")
        side = data.get("side")

        state = self.orderbooks[ticker]

        if side == "yes":
            if delta > 0 and (state.best_bid is None or price > state.best_bid):
                state.best_bid = price
                state.bid_qty = delta
            elif delta < 0 and price == state.best_bid:
                # Best bid was reduced, need full book to know new best
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

        # Log current state
        print(f"[{ticker}] Bid: {state.best_bid}c | Ask: {state.best_ask}c | Spread: {spread}c")

        # Check if tradeable
        if state.is_tradeable:
            print(f"  ✓ OPPORTUNITY: {spread}c spread - profitable to market make!")
            self._evaluate_trade(ticker, state)

    # ==================== Trading Logic ====================

    def _evaluate_trade(self, ticker: str, state: OrderbookState):
        """
        Evaluate and potentially execute a market making trade

        Strategy:
        - Place buy order 1c above best bid (to be first in queue)
        - Place sell order 1c below best ask (to be first in queue)
        - If both fill, capture the spread minus our edge
        """
        current_position = self.positions.get(ticker, 0)

        # Check position limits
        if abs(current_position) >= self.max_position:
            print(f"  ✗ Position limit reached ({current_position})")
            return

        # Calculate our prices
        our_bid = state.best_bid + self.edge   # 1c above best bid
        our_ask = state.best_ask - self.edge   # 1c below best ask

        # Make sure we still profit
        our_spread = our_ask - our_bid
        if our_spread < 1:
            print(f"  ✗ Spread too tight after edge ({our_spread}c)")
            return

        print(f"  → Strategy: Buy at {our_bid}c, Sell at {our_ask}c")
        print(f"  → Expected profit: {our_spread}c per contract")
        print(f"  → Order size: {self.order_size} contracts")

        # Place the orders
        self._place_market_making_orders(ticker, our_bid, our_ask)

    def _place_market_making_orders(self, ticker: str, bid_price: int, ask_price: int):
        """Place both sides of market making trade"""

        # Check if we already have pending orders for this ticker
        if ticker in self.pending_orders and len(self.pending_orders[ticker]) > 0:
            print(f"  ⏳ Already have pending orders for {ticker}, skipping")
            return

        if not self.live_trading:
            print(f"  [DRY RUN] Would place BUY {self.order_size} @ {bid_price}c, SELL @ {ask_price}c")
            return

        try:
            order_ids = []

            # Place buy order
            print(f"  📤 Placing BUY order: {self.order_size} @ {bid_price}c")
            buy_order = self.place_order(
                ticker=ticker,
                side="yes",
                action="buy",
                price=bid_price,
                count=self.order_size
            )
            buy_id = buy_order.get('order', {}).get('order_id')
            order_ids.append(buy_id)
            print(f"  ✅ BUY order placed: {buy_id}")

            # Place sell order
            print(f"  📤 Placing SELL order: {self.order_size} @ {ask_price}c")
            sell_order = self.place_order(
                ticker=ticker,
                side="yes",
                action="sell",
                price=ask_price,
                count=self.order_size
            )
            sell_id = sell_order.get('order', {}).get('order_id')
            order_ids.append(sell_id)
            print(f"  ✅ SELL order placed: {sell_id}")

            # Track pending orders
            self.pending_orders[ticker] = order_ids

        except Exception as e:
            print(f"  ❌ Order failed: {e}")
            # If buy succeeded but sell failed, cancel the buy
            if order_ids:
                print(f"  🔄 Canceling partial orders...")
                for oid in order_ids:
                    try:
                        self.cancel_order(oid)
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
        print(f"Mode: {'🔴 LIVE TRADING' if self.live_trading else '⚪ DRY RUN (no orders)'}")
        print(f"Strategy: Buy at bid + {self.edge}c, Sell at ask - {self.edge}c")
        print(f"Min spread: {self.min_spread}c | Order size: {self.order_size}")
        print(f"Max position: {self.max_position} contracts")
        print("=" * 60)

        # Check balance
        try:
            balance = self.get_balance()
            print(f"Account balance: ${balance.get('balance', 0) / 100:.2f}")
        except Exception as e:
            print(f"Could not fetch balance: {e}")

        print("\nConnecting to WebSocket...")

        async with websockets.connect(
            self.WS_URL,
            additional_headers=self._get_ws_headers()
        ) as ws:
            print("Connected!")
            await self.subscribe(ws, tickers)
            await self.listen(ws)


def fetch_active_markets(limit: int = 100) -> list:
    """Fetch markets with activity"""
    response = requests.get(
        "https://demo-api.kalshi.co/trade-api/v2/markets",
        params={"limit": limit, "status": "open"}
    )
    response.raise_for_status()
    markets = response.json().get("markets", [])

    # Filter for markets with REAL bid/ask (non-zero)
    active = [
        m for m in markets
        if (m.get("yes_bid") and m.get("yes_bid") > 0)
        or (m.get("yes_ask") and m.get("yes_ask") > 0 and m.get("yes_ask") < 100)
        or m.get("volume", 0) > 0
    ]

    # Sort by volume descending
    active.sort(key=lambda x: x.get("volume", 0), reverse=True)

    return active


async def main():
    # Configuration
    API_KEY = "54d3008b-2b1a-4bed-844c-177a8de556e4"
    PRIVATE_KEY_PATH = "private_key.pem"

    # Fetch active markets
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

    # Get tickers for top markets
    tickers = [m["ticker"] for m in markets[:5]]

    print(f"\nMonitoring {len(tickers)} markets for opportunities...")
    print("Press Ctrl+C to stop\n")

    # Run market maker
    bot = MarketMaker(API_KEY, PRIVATE_KEY_PATH)
    await bot.run(tickers)


if __name__ == "__main__":
    asyncio.run(main())
