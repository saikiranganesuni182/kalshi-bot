"""
Kalshi WebSocket Client
-----------------------
WebSocket client for real-time Kalshi market data.
"""

import asyncio
import json
import requests

try:
    import websockets
except ImportError:
    print("Please install websockets: pip install websockets")
    exit(1)

from . import config
from . import auth


def fetch_active_markets(base_url: str = None, limit: int = 100) -> list:
    """Fetch active markets from REST API"""
    base_url = base_url or config.REST_URL
    response = requests.get(
        f"{base_url}/markets",
        params={"limit": limit, "status": "open"}
    )
    response.raise_for_status()
    markets = response.json().get("markets", [])

    # Filter for markets with activity
    active = [
        m for m in markets
        if m.get("volume", 0) > 0
        or (m.get("yes_bid", 0) > 0 and m.get("yes_ask", 0) > 0)
    ]

    # Sort by volume descending
    active.sort(key=lambda x: x.get("volume", 0), reverse=True)

    return active


class KalshiWebSocket:
    """WebSocket client for real-time Kalshi market data"""

    def __init__(self, api_key: str = None, private_key_path: str = None):
        self.api_key = api_key or config.API_KEY
        self.private_key_path = private_key_path or config.PRIVATE_KEY_PATH
        self.private_key = auth.load_private_key(self.private_key_path)
        self.ws_url = config.WS_URL
        self.ws_path = config.WS_PATH
        self.orderbooks = {}  # Store orderbook state per market

    def _get_auth_headers(self) -> dict:
        """Generate authentication headers for websocket connection"""
        return auth.get_ws_auth_headers(self.api_key, self.private_key, self.ws_path)

    async def connect(self):
        """Establish websocket connection"""
        headers = self._get_auth_headers()
        return await websockets.connect(self.ws_url, additional_headers=headers)

    async def subscribe_orderbook(self, ws, market_tickers: list):
        """Subscribe to orderbook updates for specified markets"""
        subscription = {
            "id": 1,
            "cmd": "subscribe",
            "params": {
                "channels": ["orderbook_delta"],
                "market_tickers": market_tickers
            }
        }
        await ws.send(json.dumps(subscription))
        print(f"Subscribed to orderbook for: {market_tickers}")

    async def subscribe_ticker(self, ws, market_tickers: list):
        """Subscribe to ticker updates (bid/ask spreads)"""
        subscription = {
            "id": 2,
            "cmd": "subscribe",
            "params": {
                "channels": ["ticker"],
                "market_tickers": market_tickers
            }
        }
        await ws.send(json.dumps(subscription))
        print(f"Subscribed to ticker for: {market_tickers}")

    def process_orderbook_snapshot(self, data: dict):
        """Process initial orderbook snapshot"""
        ticker = data.get("market_ticker")
        if not ticker:
            return

        self.orderbooks[ticker] = {
            "yes": data.get("yes", []),
            "no": data.get("no", [])
        }
        self._display_orderbook(ticker)

    def process_orderbook_delta(self, data: dict):
        """Process orderbook delta (incremental update)"""
        ticker = data.get("market_ticker")
        if not ticker or ticker not in self.orderbooks:
            return

        price = data.get("price")
        delta = data.get("delta")
        side = data.get("side")

        if side and price is not None and delta is not None:
            book = self.orderbooks[ticker][side]
            found = False
            for level in book:
                if level[0] == price:
                    level[1] += delta
                    if level[1] <= 0:
                        book.remove(level)
                    found = True
                    break
            if not found and delta > 0:
                book.append([price, delta])
                book.sort(key=lambda x: x[0], reverse=(side == "yes"))

        self._display_orderbook(ticker)

    def _display_orderbook(self, ticker: str):
        """Display current orderbook state with bid/ask spread"""
        if ticker not in self.orderbooks:
            return

        book = self.orderbooks[ticker]
        yes_book = sorted(book.get("yes", []), key=lambda x: x[0], reverse=True)
        no_book = sorted(book.get("no", []), key=lambda x: x[0], reverse=True)

        best_bid = yes_book[0][0] if yes_book else None
        best_ask = (100 - no_book[0][0]) if no_book else None

        print(f"\n{'='*50}")
        print(f"ORDERBOOK: {ticker}")
        print(f"{'='*50}")

        if best_bid and best_ask:
            spread = best_ask - best_bid
            print(f"Best Bid: {best_bid}c | Best Ask: {best_ask}c | Spread: {spread}c")
        else:
            print(f"Best Bid: {best_bid}c | Best Ask: {best_ask}c")

        print(f"\nYES orders (bids):")
        for price, qty in yes_book[:5]:
            print(f"  {price}c: {qty} contracts")

        print(f"\nNO orders (asks as implied YES):")
        for price, qty in no_book[:5]:
            implied_yes = 100 - price
            print(f"  {implied_yes}c (NO@{price}c): {qty} contracts")

    def process_ticker(self, data: dict):
        """Process ticker update with bid/ask"""
        ticker = data.get("market_ticker")
        yes_bid = data.get("yes_bid")
        yes_ask = data.get("yes_ask")
        last_price = data.get("last_price")
        volume = data.get("volume")

        print(f"\n[TICKER] {ticker}")
        print(f"  Bid: {yes_bid}c | Ask: {yes_ask}c", end="")
        if yes_bid and yes_ask:
            print(f" | Spread: {yes_ask - yes_bid}c", end="")
        print(f" | Last: {last_price}c | Vol: {volume}")

    async def listen(self, ws):
        """Listen for and process incoming messages"""
        async for message in ws:
            try:
                data = json.loads(message)
                msg_type = data.get("type")

                if msg_type == "orderbook_snapshot":
                    print("\n[SNAPSHOT] Received orderbook snapshot")
                    self.process_orderbook_snapshot(data.get("msg", {}))

                elif msg_type == "orderbook_delta":
                    self.process_orderbook_delta(data.get("msg", {}))

                elif msg_type == "ticker":
                    self.process_ticker(data.get("msg", {}))

                elif msg_type == "subscribed":
                    print(f"[OK] Subscription confirmed: {data}")

                elif msg_type == "error":
                    print(f"[ERROR] {data}")

                else:
                    print(f"[MSG] {data}")

            except json.JSONDecodeError:
                print(f"[RAW] {message}")

    async def run(self, market_tickers: list):
        """Main run loop - connect and subscribe to markets"""
        print("Connecting to Kalshi WebSocket...")

        try:
            async with websockets.connect(
                self.ws_url,
                additional_headers=self._get_auth_headers()
            ) as ws:
                print("Connected!")

                await self.subscribe_orderbook(ws, market_tickers)
                await self.subscribe_ticker(ws, market_tickers)

                await self.listen(ws)

        except Exception as e:
            print(f"Connection error: {e}")
            raise


async def main():
    """Demo the websocket functionality"""
    print("=" * 60)
    print("Kalshi WebSocket - Real-time Orderbook Viewer")
    print("=" * 60)

    print("\nFetching active markets...")
    active_markets = fetch_active_markets(limit=100)

    if not active_markets:
        print("No active markets found. Using all open markets instead.")
        response = requests.get(f"{config.REST_URL}/markets", params={"limit": 20, "status": "open"})
        all_markets = response.json().get("markets", [])
        tickers = [m["ticker"] for m in all_markets[:10]]
    else:
        print(f"\nFound {len(active_markets)} active markets:")
        print(f"{'Ticker':<40} {'Bid':>5} {'Ask':>5} {'Vol':>8}")
        print("-" * 60)
        for m in active_markets[:15]:
            print(f"{m['ticker']:<40} {m.get('yes_bid', 0):>4}c {m.get('yes_ask', 0):>4}c {m.get('volume', 0):>8}")

        tickers = [m["ticker"] for m in active_markets[:10]]

    print(f"\nSubscribing to {len(tickers)} markets...")
    print("Press Ctrl+C to stop\n")

    client = KalshiWebSocket()
    await client.run(tickers)


if __name__ == "__main__":
    asyncio.run(main())
