# Kalshi WebSocket Trading Logic - Detailed Explanation

## Overview

This document explains how the Kalshi orderbook system works and how our code processes it.

---

## 1. Authentication Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    AUTHENTICATION                           │
└─────────────────────────────────────────────────────────────┘

Step 1: Generate timestamp (milliseconds since epoch)
        timestamp = "1706385600000"

Step 2: Create message to sign
        message = timestamp + method + path
        message = "1706385600000" + "GET" + "/trade-api/ws/v2"
        message = "1706385600000GET/trade-api/ws/v2"

Step 3: Sign with RSA-PSS (your private key)
        signature = RSA_PSS_SIGN(message, private_key, SHA256)
        signature = base64_encode(signature)

Step 4: Send headers with WebSocket connection
        Headers:
        ├── KALSHI-ACCESS-KEY: "your-api-key-id"
        ├── KALSHI-ACCESS-SIGNATURE: "base64-signature"
        └── KALSHI-ACCESS-TIMESTAMP: "1706385600000"
```

**Code location:** `kalshi_websocket.py` lines 45-70

```python
def _sign_request(self, timestamp: str, method: str, path: str) -> str:
    message = f"{timestamp}{method}{path}"  # Concatenate
    signature = self.private_key.sign(
        message.encode('utf-8'),
        padding.PSS(                        # RSA-PSS padding
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.DIGEST_LENGTH
        ),
        hashes.SHA256()                     # SHA256 hash
    )
    return base64.b64encode(signature).decode('utf-8')
```

---

## 2. Market Discovery Flow

```
┌─────────────────────────────────────────────────────────────┐
│                  MARKET DISCOVERY                           │
└─────────────────────────────────────────────────────────────┘

        REST API Request
              │
              ▼
┌─────────────────────────────┐
│ GET /trade-api/v2/markets   │
│ ?status=open&limit=100      │
└─────────────────────────────┘
              │
              ▼
        Response: 100 markets
              │
              ▼
┌─────────────────────────────┐
│ FILTER: Keep only markets   │
│ where volume > 0            │
│ OR (yes_bid > 0 AND         │
│     yes_ask > 0)            │
└─────────────────────────────┘
              │
              ▼
        8 active markets
              │
              ▼
┌─────────────────────────────┐
│ SORT: By volume descending  │
│ (most active first)         │
└─────────────────────────────┘
              │
              ▼
        Top 10 tickers selected
```

**Code location:** `kalshi_websocket.py` lines 18-38

```python
def fetch_active_markets(base_url: str, limit: int = 100) -> list:
    # 1. Fetch from REST API
    response = requests.get(f"{base_url}/markets", params={"limit": limit, "status": "open"})
    markets = response.json().get("markets", [])

    # 2. Filter for activity
    active = [
        m for m in markets
        if m.get("volume", 0) > 0
        or (m.get("yes_bid", 0) > 0 and m.get("yes_ask", 0) > 0)
    ]

    # 3. Sort by volume
    active.sort(key=lambda x: x.get("volume", 0), reverse=True)

    return active
```

---

## 3. WebSocket Connection Flow

```
┌─────────────────────────────────────────────────────────────┐
│                 WEBSOCKET CONNECTION                        │
└─────────────────────────────────────────────────────────────┘

Client                                          Kalshi Server
   │                                                  │
   │  ──── WebSocket Connect + Auth Headers ────────► │
   │                                                  │
   │  ◄──────────── Connection Accepted ───────────── │
   │                                                  │
   │  ──── Subscribe to orderbook_delta ───────────► │
   │       {                                          │
   │         "id": 1,                                 │
   │         "cmd": "subscribe",                      │
   │         "params": {                              │
   │           "channels": ["orderbook_delta"],       │
   │           "market_tickers": ["TICKER1", ...]     │
   │         }                                        │
   │       }                                          │
   │                                                  │
   │  ◄──────────── Subscription Confirmed ────────── │
   │       {"type": "subscribed", ...}                │
   │                                                  │
   │  ◄──────────── Orderbook Snapshot ────────────── │
   │       (Full current state)                       │
   │                                                  │
   │  ◄──────────── Orderbook Delta ───────────────── │
   │  ◄──────────── Orderbook Delta ───────────────── │
   │  ◄──────────── Orderbook Delta ───────────────── │
   │       (Real-time updates forever)                │
```

---

## 4. Orderbook Data Structure

### 4.1 Snapshot Message (Initial State)

```json
{
  "type": "orderbook_snapshot",
  "msg": {
    "market_ticker": "KXBUNDESLIGAGAME-26JAN27SVWTSG-SVW",
    "yes": [
      [5, 12000],    // [price_in_cents, quantity]
      [6, 5000]
    ],
    "no": [
      [72, 25],
      [73, 4000],
      [81, 4974]
    ]
  }
}
```

### 4.2 Delta Message (Updates)

```json
{
  "type": "orderbook_delta",
  "msg": {
    "market_ticker": "KXBUNDESLIGAGAME-26JAN27SVWTSG-SVW",
    "price": 6,
    "delta": 1000,      // +1000 contracts added
    "side": "yes",
    "ts": "2026-01-27T20:47:13Z"
  }
}
```

---

## 5. The Core Logic: YES vs NO

```
┌─────────────────────────────────────────────────────────────┐
│                  KALSHI BINARY MARKETS                      │
└─────────────────────────────────────────────────────────────┘

Every market is a YES/NO question:
  "Will Team X win the game?"

Two ways to bet:
  • Buy YES = Bet the event WILL happen
  • Buy NO  = Bet the event WON'T happen

Price relationship:
  ┌────────────────────────────────────────┐
  │   YES price + NO price = 100 cents     │
  └────────────────────────────────────────┘

Example:
  YES trading at 30c  →  NO effectively at 70c
  YES trading at 80c  →  NO effectively at 20c
```

### 5.1 Understanding the Orderbook Sides

```
┌─────────────────────────────────────────────────────────────┐
│                    ORDERBOOK STRUCTURE                      │
└─────────────────────────────────────────────────────────────┘

"yes" array = Orders to BUY YES contracts
              These are BIDS (what buyers will pay for YES)

"no" array  = Orders to BUY NO contracts
              These become ASKS for YES (explained below)


WHY?
────
Buying NO at 72c is economically identical to Selling YES at 28c

Proof:
  • You buy NO at 72c
  • I buy YES at 28c
  • Together we paid 72c + 28c = 100c
  • One of us gets 100c payout (the winner)
  • The market matched us against each other

Therefore:
  NO bid at 72c  =  YES ask at 28c  (100 - 72 = 28)
  NO bid at 81c  =  YES ask at 19c  (100 - 81 = 19)
```

### 5.2 Visual Orderbook Representation

```
                        ORDERBOOK FOR YES CONTRACTS

         SELL SIDE (Asks)                    BUY SIDE (Bids)
         People selling YES                  People buying YES
         (via NO bids)                       (direct YES bids)

    Price │ Qty                              Price │ Qty
    ──────┼────────                          ──────┼────────
     28c  │ ████ 25        ◄── spread ──►     6c  │ ████████ 5000
     27c  │ ████████ 4000                     5c  │ ████████████ 12000
     26c  │ ██████ 1818
     19c  │ ████████████ 4974

    (from NO bids:                          (direct YES bids)
     72c, 73c, 74c, 81c)


    BEST ASK = 19c (lowest price someone will sell YES)
    BEST BID = 6c  (highest price someone will buy YES)
    SPREAD   = 19c - 6c = 13c
```

---

## 6. Processing Logic in Code

### 6.1 Storing the Snapshot

```python
def process_orderbook_snapshot(self, data: dict):
    ticker = data.get("market_ticker")

    # Store both sides
    self.orderbooks[ticker] = {
        "yes": data.get("yes", []),  # [[price, qty], ...]
        "no": data.get("no", [])     # [[price, qty], ...]
    }
```

### 6.2 Applying Deltas

```python
def process_orderbook_delta(self, data: dict):
    ticker = data.get("market_ticker")
    price = data.get("price")    # e.g., 6
    delta = data.get("delta")    # e.g., +1000 or -500
    side = data.get("side")      # "yes" or "no"

    book = self.orderbooks[ticker][side]  # Get yes or no array

    # Find the price level and update quantity
    for level in book:
        if level[0] == price:
            level[1] += delta           # Add delta to quantity
            if level[1] <= 0:
                book.remove(level)      # Remove if qty = 0
            return

    # Price level didn't exist, create it
    if delta > 0:
        book.append([price, delta])
```

### 6.3 Calculating Best Bid/Ask

```python
def _display_orderbook(self, ticker: str):
    book = self.orderbooks[ticker]

    # Sort YES bids: highest price first (best bid on top)
    yes_book = sorted(book["yes"], key=lambda x: x[0], reverse=True)

    # Sort NO bids: highest price first (becomes lowest YES ask)
    no_book = sorted(book["no"], key=lambda x: x[0], reverse=True)

    # Best bid = highest YES bid price
    best_bid = yes_book[0][0] if yes_book else None

    # Best ask = 100 - highest NO bid price
    best_ask = (100 - no_book[0][0]) if no_book else None

    # Spread
    spread = best_ask - best_bid if (best_bid and best_ask) else None
```

---

## 7. Complete Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         COMPLETE DATA FLOW                              │
└─────────────────────────────────────────────────────────────────────────┘

    ┌──────────────┐
    │  Program     │
    │  Starts      │
    └──────┬───────┘
           │
           ▼
    ┌──────────────┐      GET /markets
    │  Fetch       │ ──────────────────────► Kalshi REST API
    │  Markets     │ ◄──────────────────────
    └──────┬───────┘      JSON response
           │
           │ Filter & Sort
           ▼
    ┌──────────────┐
    │  Top 10      │
    │  Tickers     │
    └──────┬───────┘
           │
           ▼
    ┌──────────────┐      WSS + Auth Headers
    │  Connect     │ ──────────────────────► Kalshi WebSocket
    │  WebSocket   │ ◄──────────────────────
    └──────┬───────┘      Connection OK
           │
           ▼
    ┌──────────────┐      Subscribe JSON
    │  Subscribe   │ ──────────────────────►
    │  Channels    │ ◄──────────────────────
    └──────┬───────┘      Confirmed
           │
           ▼
    ┌──────────────┐
    │  Receive     │ ◄─────── orderbook_snapshot (initial state)
    │  Snapshot    │
    └──────┬───────┘
           │
           │ Store in self.orderbooks[ticker]
           ▼
    ┌──────────────┐
    │  LOOP:       │ ◄─────── orderbook_delta (updates)
    │  Receive     │ ◄─────── orderbook_delta
    │  Deltas      │ ◄─────── orderbook_delta
    └──────┬───────┘          ...forever
           │
           │ For each delta:
           ▼
    ┌──────────────┐
    │  Update      │  1. Find price level in yes/no array
    │  Orderbook   │  2. Add delta to quantity
    │  State       │  3. Remove level if qty <= 0
    └──────┬───────┘
           │
           ▼
    ┌──────────────┐
    │  Calculate   │  best_bid = max(yes prices)
    │  Bid/Ask     │  best_ask = 100 - max(no prices)
    │  Spread      │  spread = best_ask - best_bid
    └──────┬───────┘
           │
           ▼
    ┌──────────────┐
    │  Display     │  Print formatted orderbook
    └──────────────┘
```

---

## 8. Trading Strategy Concepts

### 8.1 Market Making (Profit from Spread)

```
Current market:
  Best Bid: 30c
  Best Ask: 35c
  Spread: 5c

Your strategy:
  1. Place bid at 31c (better than 30c, you're first in line)
  2. Place ask at 34c (better than 35c, you're first in line)

If both fill:
  • You bought YES at 31c
  • You sold YES at 34c
  • Profit: 3c per contract

Risk: Price moves against you before both sides fill
```

### 8.2 Spread Detection

```python
# Pseudocode for finding tight spreads
for ticker, book in orderbooks.items():
    spread = best_ask - best_bid

    if spread <= 2:  # 2 cents or less
        print(f"TIGHT SPREAD: {ticker} - {spread}c")
        # Good market making opportunity

    if spread == 0:  # Crossed market (rare)
        print(f"ARBITRAGE: {ticker}")
        # Free money if you can execute fast enough
```

### 8.3 Volume Analysis

```
High volume + tight spread = Liquid market (safe to trade)
High volume + wide spread  = Volatile (be careful)
Low volume  + tight spread = Illiquid (hard to exit)
Low volume  + wide spread  = Avoid
```

---

## 9. File Structure Summary

```
kalshi-api/
├── kalshi_websocket.py    # Main WebSocket client
│   ├── fetch_active_markets()      # REST API to get markets
│   ├── KalshiWebSocket class
│   │   ├── _sign_request()         # Authentication
│   │   ├── _get_auth_headers()     # Build headers
│   │   ├── subscribe_orderbook()   # Subscribe to channel
│   │   ├── process_orderbook_snapshot()  # Handle initial state
│   │   ├── process_orderbook_delta()     # Handle updates
│   │   └── _display_orderbook()    # Calculate & show bid/ask
│   └── main()                      # Entry point
│
├── kalshi_client.py       # REST API client (orders, balance)
├── get_markets.py         # Simple market list utility
├── private_key.pem        # Your RSA private key
└── requirements.txt       # Dependencies
```

---

## 10. Key Formulas

```
┌─────────────────────────────────────────────────────────────┐
│                     KEY FORMULAS                            │
└─────────────────────────────────────────────────────────────┘

YES + NO = 100c (always)

Implied YES ask = 100 - NO bid price

Spread = Best Ask - Best Bid

Profit per contract (market making) = Sell Price - Buy Price - Fees

Breakeven (directional bet):
  • If you buy YES at Xc, event must happen to profit
  • Your risk: Xc (what you paid)
  • Your reward: (100 - X)c if event happens
```
