"""
Kalshi Authentication
---------------------
Shared authentication and signing logic for Kalshi API.
"""

import base64
import time
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend


def load_private_key(path: str):
    """Load RSA private key from file"""
    with open(path, "rb") as key_file:
        return serialization.load_pem_private_key(
            key_file.read(),
            password=None,
            backend=default_backend()
        )


def sign_request(private_key, timestamp: str, method: str, path: str) -> str:
    """Create signature for API request using RSA-PSS"""
    message = f"{timestamp}{method}{path}"
    signature = private_key.sign(
        message.encode('utf-8'),
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.DIGEST_LENGTH
        ),
        hashes.SHA256()
    )
    return base64.b64encode(signature).decode('utf-8')


def get_auth_headers(api_key: str, private_key, method: str, path: str) -> dict:
    """Generate headers with authentication for REST requests"""
    timestamp = str(int(time.time() * 1000))
    signature = sign_request(private_key, timestamp, method, path)

    return {
        "KALSHI-ACCESS-KEY": api_key,
        "KALSHI-ACCESS-SIGNATURE": signature,
        "KALSHI-ACCESS-TIMESTAMP": timestamp,
        "Content-Type": "application/json"
    }


def get_ws_auth_headers(api_key: str, private_key, ws_path: str) -> dict:
    """Generate headers with authentication for WebSocket connections"""
    timestamp = str(int(time.time() * 1000))
    signature = sign_request(private_key, timestamp, "GET", ws_path)

    return {
        "KALSHI-ACCESS-KEY": api_key,
        "KALSHI-ACCESS-SIGNATURE": signature,
        "KALSHI-ACCESS-TIMESTAMP": timestamp
    }
