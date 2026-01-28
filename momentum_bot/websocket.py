"""
WebSocket connection manager for real-time price updates.
"""

import json
import asyncio
from typing import Callable, List
import websockets
from .auth import KalshiAuth
from .config import Config


class WebSocketManager:
    """
    Manages WebSocket connection to Kalshi.

    Features:
    - Auto-reconnect on disconnect
    - Orderbook snapshot and delta handling
    - Callback system for price updates
    """

    def __init__(self, config: Config, on_price_update: Callable[[str, dict], None]):
        """
        Args:
            config: Bot configuration
            on_price_update: Callback function(ticker, data) for price updates
        """
        self.config = config
        self.auth = KalshiAuth(config.api_key, config.private_key_path)
        self.on_price_update = on_price_update

        self.ws = None
        self.connected = False
        self.subscribed_tickers: List[str] = []
        self.reconnect_delay = 1.0
        self.max_reconnect_delay = 30.0

    async def connect(self, tickers: List[str]):
        """
        Connect to WebSocket and subscribe to markets.

        Args:
            tickers: List of market tickers to subscribe to
        """
        self.subscribed_tickers = tickers

        while True:
            try:
                await self._connect_and_run()
            except websockets.exceptions.ConnectionClosed as e:
                self._log(f"Connection closed: {e}")
            except Exception as e:
                self._log(f"WebSocket error: {e}")

            if not self.connected:
                self._log(f"Reconnecting in {self.reconnect_delay}s...")
                await asyncio.sleep(self.reconnect_delay)
                self.reconnect_delay = min(self.reconnect_delay * 2, self.max_reconnect_delay)

    async def _connect_and_run(self):
        """Internal connection handler."""
        headers = self.auth.get_ws_headers(self.config.ws_path)

        self._log(f"Connecting to {self.config.ws_url}...")

        async with websockets.connect(
            self.config.ws_url,
            additional_headers=headers,
            ping_interval=20,
            ping_timeout=10
        ) as ws:
            self.ws = ws
            self.connected = True
            self.reconnect_delay = 1.0  # Reset delay on successful connect

            self._log(f"Connected! Subscribing to {len(self.subscribed_tickers)} markets...")

            # Subscribe to orderbook updates
            subscribe_msg = {
                "id": 1,
                "cmd": "subscribe",
                "params": {
                    "channels": ["orderbook_delta"],
                    "market_tickers": self.subscribed_tickers
                }
            }
            await ws.send(json.dumps(subscribe_msg))

            # Listen for messages
            async for message in ws:
                try:
                    data = json.loads(message)
                    await self._handle_message(data)
                except json.JSONDecodeError:
                    pass

    async def _handle_message(self, data: dict):
        """Handle incoming WebSocket message."""
        msg_type = data.get('type')
        msg = data.get('msg', {})

        if msg_type == 'orderbook_snapshot':
            self._handle_snapshot(msg)
        elif msg_type == 'orderbook_delta':
            self._handle_delta(msg)
        elif msg_type == 'subscribed':
            self._log(f"Subscribed to {len(self.subscribed_tickers)} markets")
        elif msg_type == 'error':
            self._log(f"WS Error: {msg}")

    def _handle_snapshot(self, msg: dict):
        """Handle orderbook snapshot."""
        ticker = msg.get('market_ticker')
        if not ticker:
            return

        yes_orders = msg.get('yes', [])
        no_orders = msg.get('no', [])

        # Get best bid/ask from orderbook
        # Format: [[price, quantity], ...]
        yes_bid = yes_orders[0][0] if yes_orders else 0
        yes_ask = 100 - (no_orders[0][0] if no_orders else 0)  # Implied ask
        no_bid = no_orders[0][0] if no_orders else 0

        # Calculate ask from full orderbook if available
        if yes_orders:
            # Find the lowest ask (sell orders)
            asks = [o for o in yes_orders if len(o) > 1]
            if asks:
                yes_ask = min(yes_ask, asks[-1][0] if asks else 100)

        update = {
            'type': 'snapshot',
            'yes_bid': yes_bid,
            'yes_ask': yes_ask,
            'no_bid': no_bid,
            'no_ask': 100 - yes_bid if yes_bid else 0
        }

        self.on_price_update(ticker, update)

    def _handle_delta(self, msg: dict):
        """Handle orderbook delta update."""
        ticker = msg.get('market_ticker')
        if not ticker:
            return

        price = msg.get('price', 0)
        delta = msg.get('delta', 0)
        side = msg.get('side')  # 'yes' or 'no'

        update = {
            'type': 'delta',
            'side': side,
            'price': price,
            'delta': delta
        }

        self.on_price_update(ticker, update)

    async def subscribe(self, tickers: List[str]):
        """Subscribe to additional tickers."""
        if not self.ws or not self.connected:
            return

        new_tickers = [t for t in tickers if t not in self.subscribed_tickers]
        if not new_tickers:
            return

        subscribe_msg = {
            "id": 2,
            "cmd": "subscribe",
            "params": {
                "channels": ["orderbook_delta"],
                "market_tickers": new_tickers
            }
        }
        await self.ws.send(json.dumps(subscribe_msg))
        self.subscribed_tickers.extend(new_tickers)

    async def unsubscribe(self, tickers: List[str]):
        """Unsubscribe from tickers."""
        if not self.ws or not self.connected:
            return

        unsubscribe_msg = {
            "id": 3,
            "cmd": "unsubscribe",
            "params": {
                "channels": ["orderbook_delta"],
                "market_tickers": tickers
            }
        }
        await self.ws.send(json.dumps(unsubscribe_msg))
        self.subscribed_tickers = [t for t in self.subscribed_tickers if t not in tickers]

    def _log(self, msg: str):
        """Log message with timestamp."""
        from datetime import datetime
        ts = datetime.now().strftime("%H:%M:%S")
        print(f"[{ts}] [WS] {msg}", flush=True)

    async def close(self):
        """Close WebSocket connection."""
        if self.ws:
            await self.ws.close()
            self.connected = False
