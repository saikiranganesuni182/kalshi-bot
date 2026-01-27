"""
Kalshi API Client for Demo Environment
"""

import base64
import time
import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend


class KalshiClient:
    """Client for interacting with Kalshi's API"""

    # Demo environment base URL
    BASE_URL = "https://demo-api.kalshi.co/trade-api/v2"

    def __init__(self, api_key: str, private_key_path: str):
        self.api_key = api_key
        self.private_key = self._load_private_key(private_key_path)

    def _load_private_key(self, path: str):
        """Load RSA private key from file"""
        with open(path, "rb") as key_file:
            return serialization.load_pem_private_key(
                key_file.read(),
                password=None,
                backend=default_backend()
            )

    def _sign_request(self, timestamp: str, method: str, path: str) -> str:
        """Create signature for API request using RSA-PSS"""
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
        """Generate headers with authentication"""
        timestamp = str(int(time.time() * 1000))
        signature = self._sign_request(timestamp, method, path)

        return {
            "KALSHI-ACCESS-KEY": self.api_key,
            "KALSHI-ACCESS-SIGNATURE": signature,
            "KALSHI-ACCESS-TIMESTAMP": timestamp,
            "Content-Type": "application/json"
        }

    def _request(self, method: str, endpoint: str, params: dict = None) -> dict:
        """Make authenticated request to Kalshi API"""
        path = f"/trade-api/v2{endpoint}"
        url = f"{self.BASE_URL}{endpoint}"
        headers = self._get_headers(method, path)

        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            params=params
        )

        response.raise_for_status()
        return response.json()

    def get_balance(self) -> dict:
        """Get account balance"""
        return self._request("GET", "/portfolio/balance")

    def get_positions(self) -> dict:
        """Get current positions"""
        return self._request("GET", "/portfolio/positions")

    def get_fills(self, limit: int = 100, cursor: str = None) -> dict:
        """Get trade fills (executed trades)"""
        params = {"limit": limit}
        if cursor:
            params["cursor"] = cursor
        return self._request("GET", "/portfolio/fills", params=params)

    def get_orders(self, status: str = None) -> dict:
        """Get orders. Status can be 'resting', 'canceled', 'executed'"""
        params = {}
        if status:
            params["status"] = status
        return self._request("GET", "/portfolio/orders", params=params)

    def get_exchange_status(self) -> dict:
        """Get exchange status (public endpoint for testing)"""
        response = requests.get(f"{self.BASE_URL}/exchange/status")
        response.raise_for_status()
        return response.json()


def main():
    # Configuration
    API_KEY = "54d3008b-2b1a-4bed-844c-177a8de556e4"
    PRIVATE_KEY_PATH = "private_key.pem"

    # Initialize client
    client = KalshiClient(API_KEY, PRIVATE_KEY_PATH)

    print("=" * 60)
    print("Kalshi Demo Account - Trade Viewer")
    print("=" * 60)

    # Test connection with exchange status
    print("\n1. Checking Exchange Status...")
    try:
        status = client.get_exchange_status()
        print(f"   Exchange Status: {status}")
    except Exception as e:
        print(f"   Error: {e}")

    # Get account balance
    print("\n2. Fetching Account Balance...")
    try:
        balance = client.get_balance()
        print(f"   Balance: {balance}")
    except Exception as e:
        print(f"   Error: {e}")

    # Get positions
    print("\n3. Fetching Current Positions...")
    try:
        positions = client.get_positions()
        if positions.get("market_positions"):
            for pos in positions["market_positions"]:
                print(f"   - Ticker: {pos.get('ticker')}, "
                      f"Position: {pos.get('position')}, "
                      f"Realized PnL: {pos.get('realized_pnl')}")
        else:
            print("   No open positions")
    except Exception as e:
        print(f"   Error: {e}")

    # Get trade fills (executed trades)
    print("\n4. Fetching Trade History (Fills)...")
    try:
        fills = client.get_fills(limit=20)
        if fills.get("fills"):
            print(f"   Found {len(fills['fills'])} trades:")
            for fill in fills["fills"]:
                print(f"   - Ticker: {fill.get('ticker')}, "
                      f"Side: {fill.get('side')}, "
                      f"Count: {fill.get('count')}, "
                      f"Price: {fill.get('price')}, "
                      f"Time: {fill.get('created_time')}")
        else:
            print("   No trades found")
    except Exception as e:
        print(f"   Error: {e}")

    # Get orders
    print("\n5. Fetching Orders...")
    try:
        orders = client.get_orders()
        if orders.get("orders"):
            print(f"   Found {len(orders['orders'])} orders:")
            for order in orders["orders"]:
                print(f"   - Ticker: {order.get('ticker')}, "
                      f"Side: {order.get('side')}, "
                      f"Status: {order.get('status')}, "
                      f"Price: {order.get('price')}")
        else:
            print("   No orders found")
    except Exception as e:
        print(f"   Error: {e}")

    print("\n" + "=" * 60)
    print("Done!")


if __name__ == "__main__":
    main()
