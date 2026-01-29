"""
Kalshi REST API Client
----------------------
Client for interacting with Kalshi's REST API.
"""

import requests
from . import config
from . import auth


class KalshiClient:
    """Client for interacting with Kalshi's REST API"""

    def __init__(self, api_key: str = None, private_key_path: str = None):
        self.api_key = api_key or config.API_KEY
        self.private_key_path = private_key_path or config.PRIVATE_KEY_PATH
        self.private_key = auth.load_private_key(self.private_key_path)
        self.base_url = config.REST_URL

    def _get_headers(self, method: str, path: str) -> dict:
        """Generate authenticated headers"""
        return auth.get_auth_headers(self.api_key, self.private_key, method, path)

    def _request(self, method: str, endpoint: str, params: dict = None, json: dict = None) -> dict:
        """Make authenticated request to Kalshi API"""
        path = f"/trade-api/v2{endpoint}"
        url = f"{self.base_url}{endpoint}"
        headers = self._get_headers(method, path)

        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            params=params,
            json=json
        )

        response.raise_for_status()
        return response.json()

    # Account endpoints
    def get_balance(self) -> dict:
        """Get account balance"""
        return self._request("GET", "/portfolio/balance")

    def get_balance_cents(self) -> int:
        """Get account balance in cents"""
        return self.get_balance().get('balance', 0)

    def get_balance_dollars(self) -> float:
        """Get account balance in dollars"""
        return self.get_balance_cents() / 100

    # Position endpoints
    def get_positions(self) -> dict:
        """Get current positions"""
        return self._request("GET", "/portfolio/positions")

    def get_positions_dict(self) -> dict:
        """Get positions as {ticker: position} dict"""
        positions = {}
        for p in self.get_positions().get('market_positions', []):
            if p.get('position', 0) != 0:
                positions[p['ticker']] = p['position']
        return positions

    # Order endpoints
    def get_orders(self, status: str = None) -> dict:
        """Get orders. Status can be 'resting', 'canceled', 'executed'"""
        params = {}
        if status:
            params["status"] = status
        return self._request("GET", "/portfolio/orders", params=params)

    def get_resting_orders(self) -> list:
        """Get open/resting orders"""
        return self.get_orders(status="resting").get('orders', [])

    def place_order(
        self,
        ticker: str,
        side: str,      # "yes" or "no"
        action: str,    # "buy" or "sell"
        price: int,     # Price in cents (1-99)
        count: int      # Number of contracts
    ) -> dict:
        """Place a limit order"""
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
        return self._request("POST", "/portfolio/orders", json=payload)

    def cancel_order(self, order_id: str) -> dict:
        """Cancel an existing order"""
        return self._request("DELETE", f"/portfolio/orders/{order_id}")

    # Trade history
    def get_fills(self, limit: int = 100, cursor: str = None) -> dict:
        """Get trade fills (executed trades)"""
        params = {"limit": limit}
        if cursor:
            params["cursor"] = cursor
        return self._request("GET", "/portfolio/fills", params=params)

    # Market endpoints
    def get_markets(self, limit: int = 100, status: str = "open", cursor: str = None) -> dict:
        """Get markets"""
        params = {"limit": limit, "status": status}
        if cursor:
            params["cursor"] = cursor
        return self._request("GET", "/markets", params=params)

    def fetch_all_markets(self, status: str = "open", max_pages: int = 10) -> list:
        """Fetch all markets with pagination"""
        all_markets = []
        cursor = None

        for _ in range(max_pages):
            params = {'limit': 200, 'status': status}
            if cursor:
                params['cursor'] = cursor

            response = requests.get(f"{self.base_url}/markets", params=params)
            data = response.json()
            markets = data.get('markets', [])
            cursor = data.get('cursor')
            all_markets.extend(markets)

            if not cursor or not markets:
                break

        return all_markets

    def fetch_active_markets(self, limit: int = 100) -> list:
        """Fetch markets with activity (volume > 0 or has bid/ask)"""
        all_markets = self.fetch_all_markets()

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
        return active[:limit]

    # Exchange status (public endpoint)
    def get_exchange_status(self) -> dict:
        """Get exchange status (public endpoint)"""
        response = requests.get(f"{self.base_url}/exchange/status")
        response.raise_for_status()
        return response.json()


def main():
    """Demo the client functionality"""
    client = KalshiClient()

    print("=" * 60)
    print("Kalshi API Client Demo")
    print("=" * 60)

    print("\n1. Checking Exchange Status...")
    try:
        status = client.get_exchange_status()
        print(f"   Exchange Status: {status}")
    except Exception as e:
        print(f"   Error: {e}")

    print("\n2. Fetching Account Balance...")
    try:
        balance = client.get_balance_dollars()
        print(f"   Balance: ${balance:.2f}")
    except Exception as e:
        print(f"   Error: {e}")

    print("\n3. Fetching Current Positions...")
    try:
        positions = client.get_positions_dict()
        if positions:
            for ticker, pos in positions.items():
                print(f"   - {ticker}: {pos} contracts")
        else:
            print("   No open positions")
    except Exception as e:
        print(f"   Error: {e}")

    print("\n4. Fetching Open Orders...")
    try:
        orders = client.get_resting_orders()
        if orders:
            print(f"   Found {len(orders)} orders")
            for order in orders[:5]:
                print(f"   - {order.get('ticker')}: {order.get('action')} @ {order.get('yes_price')}c")
        else:
            print("   No open orders")
    except Exception as e:
        print(f"   Error: {e}")

    print("\n" + "=" * 60)
    print("Done!")


if __name__ == "__main__":
    main()
