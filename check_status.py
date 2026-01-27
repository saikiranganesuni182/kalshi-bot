#!/usr/bin/env python3
"""
Check trading bot status and account state
"""

import requests
import base64
import time
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend

API_KEY = "54d3008b-2b1a-4bed-844c-177a8de556e4"
PRIVATE_KEY_PATH = "private_key.pem"
REST_URL = "https://demo-api.kalshi.co/trade-api/v2"


def load_key():
    with open(PRIVATE_KEY_PATH, "rb") as f:
        return serialization.load_pem_private_key(f.read(), password=None, backend=default_backend())


def sign(key, timestamp, method, path):
    msg = f"{timestamp}{method}{path}"
    sig = key.sign(
        msg.encode(),
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH),
        hashes.SHA256()
    )
    return base64.b64encode(sig).decode()


def headers(key, method, path):
    ts = str(int(time.time() * 1000))
    return {
        "KALSHI-ACCESS-KEY": API_KEY,
        "KALSHI-ACCESS-SIGNATURE": sign(key, ts, method, path),
        "KALSHI-ACCESS-TIMESTAMP": ts,
    }


def main():
    key = load_key()

    print("=" * 60)
    print("KALSHI ACCOUNT STATUS")
    print("=" * 60)

    # Balance
    path = "/trade-api/v2/portfolio/balance"
    r = requests.get(f"{REST_URL}/portfolio/balance", headers=headers(key, "GET", path))
    balance = r.json().get('balance', 0) / 100
    print(f"\n💰 Balance: ${balance:.2f}")

    # Open orders
    path = "/trade-api/v2/portfolio/orders"
    r = requests.get(f"{REST_URL}/portfolio/orders", headers=headers(key, "GET", path), params={"status": "resting"})
    orders = r.json().get('orders', [])
    print(f"\n📋 Open Orders: {len(orders)}")
    for o in orders:
        print(f"   {o.get('action').upper()} {o.get('remaining_count')} @ {o.get('yes_price')}c - {o.get('ticker')[:40]}")

    # Positions
    path = "/trade-api/v2/portfolio/positions"
    r = requests.get(f"{REST_URL}/portfolio/positions", headers=headers(key, "GET", path))
    positions = [p for p in r.json().get('market_positions', []) if p.get('position', 0) != 0]
    print(f"\n📊 Positions: {len(positions)}")
    for p in positions:
        print(f"   {p.get('ticker')[:40]}: {p.get('position')} contracts")

    # Active markets
    r = requests.get(f"{REST_URL}/markets", params={"limit": 100, "status": "open"})
    markets = r.json().get('markets', [])
    active = [m for m in markets if m.get('yes_bid', 0) > 0 or m.get('volume', 0) > 0]

    print(f"\n📡 Active Markets: {len(active)}")
    for m in active[:10]:
        bid = m.get('yes_bid', 0)
        ask = m.get('yes_ask', 0)
        spread = ask - bid if (bid and ask) else 0
        vol = m.get('volume', 0)
        print(f"   {m['ticker'][:40]}: {bid}c/{ask}c spread={spread}c vol={vol}")

    # Bot log
    print(f"\n📝 Recent Bot Activity:")
    try:
        with open('/tmp/bot_output.log', 'r') as f:
            lines = f.readlines()
            for line in lines[-10:]:
                print(f"   {line.rstrip()}")
    except:
        print("   (no log found)")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
