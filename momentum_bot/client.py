"""
Kalshi REST API client.
"""

import requests
from typing import List, Dict
from .auth import KalshiAuth
from .config import Config


class KalshiClient:
    """REST API client for Kalshi."""

    def __init__(self, config: Config):
        self.config = config
        self.auth = KalshiAuth(config.api_key, config.private_key_path)
        self.base_url = config.rest_url

    def _request(self, method: str, endpoint: str, params: dict = None, json: dict = None) -> dict:
        """Make authenticated API request."""
        path = f"/trade-api/v2{endpoint}"
        url = f"{self.base_url}{endpoint}"
        headers = self.auth.get_headers(method, path)

        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            params=params,
            json=json
        )
        response.raise_for_status()
        return response.json()

    # ==================== Account ====================

    def get_balance(self) -> float:
        """Get account balance in dollars."""
        data = self._request("GET", "/portfolio/balance")
        return data.get('balance', 0) / 100

    def get_positions(self) -> List[Dict]:
        """Get all current positions."""
        data = self._request("GET", "/portfolio/positions")
        return data.get('market_positions', [])

    # ==================== Markets ====================

    def get_markets(self, status: str = "open", limit: int = 200, cursor: str = None) -> Dict:
        """
        Fetch markets with optional filtering.

        Args:
            status: Market status filter (open, closed, settled)
            limit: Max results per page
            cursor: Pagination cursor

        Returns:
            Dict with 'markets' list and 'cursor' for pagination
        """
        params = {'limit': limit, 'status': status}
        if cursor:
            params['cursor'] = cursor
        return self._request("GET", "/markets", params=params)

    def get_all_markets(self, status: str = "open") -> List[Dict]:
        """Fetch all markets with pagination."""
        all_markets = []
        cursor = None

        for _ in range(20):  # Max 20 pages
            data = self.get_markets(status=status, cursor=cursor)
            markets = data.get('markets', [])
            cursor = data.get('cursor')
            all_markets.extend(markets)

            if not cursor or not markets:
                break

        return all_markets

    def get_market(self, ticker: str) -> Dict:
        """Get single market details."""
        return self._request("GET", f"/markets/{ticker}")

    def get_orderbook(self, ticker: str, depth: int = 10) -> Dict:
        """
        Get orderbook for a market.

        Args:
            ticker: Market ticker
            depth: Number of price levels

        Returns:
            Dict with 'yes' and 'no' arrays of [price, quantity] pairs
        """
        params = {'depth': depth}
        data = self._request("GET", f"/markets/{ticker}/orderbook", params=params)
        return data.get('orderbook', {})

    # ==================== Orders ====================

    def place_order(
        self,
        ticker: str,
        side: str,  # 'yes' or 'no'
        action: str,  # 'buy' or 'sell'
        price: int,  # in cents
        count: int,
        order_type: str = "limit"
    ) -> Dict:
        """
        Place an order.

        Args:
            ticker: Market ticker
            side: 'yes' or 'no'
            action: 'buy' or 'sell'
            price: Price in cents (1-99)
            count: Number of contracts
            order_type: 'limit' or 'market'

        Returns:
            Order response with 'order' dict
        """
        payload = {
            "ticker": ticker,
            "side": side,
            "action": action,
            "type": order_type,
            "count": count,
        }

        if side == "yes":
            payload["yes_price"] = price
        else:
            payload["no_price"] = price

        return self._request("POST", "/portfolio/orders", json=payload)

    def cancel_order(self, order_id: str) -> None:
        """Cancel an order by ID."""
        self._request("DELETE", f"/portfolio/orders/{order_id}")

    def get_orders(self, status: str = "resting") -> List[Dict]:
        """
        Get orders with optional status filter.

        Args:
            status: Order status filter (resting, pending, canceled, executed)

        Returns:
            List of order dicts
        """
        params = {'status': status}
        data = self._request("GET", "/portfolio/orders", params=params)
        return data.get('orders', [])

    def get_order(self, order_id: str) -> Dict:
        """Get single order by ID."""
        return self._request("GET", f"/portfolio/orders/{order_id}")

    # ==================== Fills ====================

    def get_fills(self, ticker: str = None, limit: int = 100) -> List[Dict]:
        """
        Get trade fills.

        Args:
            ticker: Optional ticker filter
            limit: Max results

        Returns:
            List of fill dicts
        """
        params = {'limit': limit}
        if ticker:
            params['ticker'] = ticker
        data = self._request("GET", "/portfolio/fills", params=params)
        return data.get('fills', [])

    # ==================== Utility ====================

    def get_exchange_status(self) -> Dict:
        """Get exchange status."""
        return self._request("GET", "/exchange/status")

    def filter_liquid_markets(self, markets: List[Dict]) -> List[Dict]:
        """
        Filter markets by liquidity requirements.

        Args:
            markets: List of market dicts

        Returns:
            Filtered list meeting liquidity criteria
        """
        liquid = []

        for m in markets:
            # Check volume (if configured)
            if self.config.min_volume > 0:
                if m.get('volume', 0) < self.config.min_volume:
                    continue

            # Check spread
            yes_bid = m.get('yes_bid', 0) or 0
            yes_ask = m.get('yes_ask', 0) or 100
            spread = yes_ask - yes_bid

            if spread > self.config.max_spread or spread <= 0:
                continue

            # Must have active quotes
            if yes_bid <= 0 or yes_ask >= 100:
                continue

            liquid.append(m)

        return liquid

    def filter_active_markets(self, markets: List[Dict]) -> List[Dict]:
        """
        Filter to markets with any trading activity (more permissive).
        Use this when liquidity requirements are too strict.

        Args:
            markets: List of market dicts

        Returns:
            Markets with any bid or volume
        """
        active = []

        for m in markets:
            yes_bid = m.get('yes_bid', 0) or 0
            yes_ask = m.get('yes_ask', 0) or 100
            volume = m.get('volume', 0) or 0

            # Accept any market with a bid, or any volume
            has_bid = yes_bid > 0 and yes_ask < 100
            has_volume = volume > 0

            if has_bid or has_volume:
                # Calculate spread for sorting
                spread = yes_ask - yes_bid if has_bid else 999
                m['_spread'] = spread
                active.append(m)

        # Sort by spread (tightest first)
        active.sort(key=lambda x: x.get('_spread', 999))

        return active
