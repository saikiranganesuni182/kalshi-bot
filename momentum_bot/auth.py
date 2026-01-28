"""
Authentication module for Kalshi API.
Handles RSA signature generation and header creation.
"""

import base64
import time
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend


class KalshiAuth:
    """Handles authentication for Kalshi API requests."""

    def __init__(self, api_key: str, private_key_path: str):
        self.api_key = api_key
        self.private_key = self._load_private_key(private_key_path)

    def _load_private_key(self, path: str):
        """Load RSA private key from PEM file."""
        with open(path, "rb") as f:
            return serialization.load_pem_private_key(
                f.read(),
                password=None,
                backend=default_backend()
            )

    def sign(self, timestamp: str, method: str, path: str) -> str:
        """
        Generate RSA-PSS signature for API request.

        Args:
            timestamp: Millisecond timestamp as string
            method: HTTP method (GET, POST, DELETE)
            path: API path (e.g., /trade-api/v2/portfolio/balance)

        Returns:
            Base64-encoded signature
        """
        message = f"{timestamp}{method}{path}"
        signature = self.private_key.sign(
            message.encode(),
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.DIGEST_LENGTH
            ),
            hashes.SHA256()
        )
        return base64.b64encode(signature).decode()

    def get_headers(self, method: str, path: str) -> dict:
        """
        Generate authenticated headers for REST API request.

        Args:
            method: HTTP method
            path: API path

        Returns:
            Headers dict with authentication
        """
        timestamp = str(int(time.time() * 1000))
        return {
            "KALSHI-ACCESS-KEY": self.api_key,
            "KALSHI-ACCESS-SIGNATURE": self.sign(timestamp, method, path),
            "KALSHI-ACCESS-TIMESTAMP": timestamp,
            "Content-Type": "application/json"
        }

    def get_ws_headers(self, ws_path: str) -> dict:
        """
        Generate authenticated headers for WebSocket connection.

        Args:
            ws_path: WebSocket path

        Returns:
            Headers dict with authentication
        """
        timestamp = str(int(time.time() * 1000))
        return {
            "KALSHI-ACCESS-KEY": self.api_key,
            "KALSHI-ACCESS-SIGNATURE": self.sign(timestamp, "GET", ws_path),
            "KALSHI-ACCESS-TIMESTAMP": timestamp
        }
