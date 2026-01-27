"""
Market Maker Logic Demonstration
--------------------------------
This shows exactly how the buy-bid/sell-ask strategy works.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class Order:
    side: str       # "buy" or "sell"
    price: int      # cents
    quantity: int
    filled: bool = False


@dataclass
class Position:
    contracts: int = 0
    avg_cost: float = 0.0
    realized_pnl: float = 0.0


class MarketMakerSimulation:
    """Simulates market making strategy"""

    def __init__(self):
        self.position = Position()
        self.orders: list[Order] = []
        self.trade_log: list[str] = []

    def show_orderbook(self, best_bid: int, best_ask: int, bid_qty: int, ask_qty: int):
        """Display the current orderbook"""
        spread = best_ask - best_bid

        print("\n" + "=" * 50)
        print("CURRENT ORDERBOOK")
        print("=" * 50)
        print(f"""
        SELL SIDE (Asks)           BUY SIDE (Bids)
        ----------------           ---------------
        {best_ask}c [{ask_qty:,} contracts]       {best_bid}c [{bid_qty:,} contracts]

        Best Ask: {best_ask}c  |  Best Bid: {best_bid}c  |  Spread: {spread}c
        """)

    def analyze_opportunity(self, best_bid: int, best_ask: int) -> dict:
        """Analyze if there's a profitable opportunity"""
        spread = best_ask - best_bid
        fee_per_contract = 1  # Kalshi charges ~1c per side

        # Our improved prices (1c edge)
        our_bid = best_bid + 1  # We bid higher to get filled first
        our_ask = best_ask - 1  # We ask lower to get filled first

        our_spread = our_ask - our_bid
        profit_per_contract = our_spread - (fee_per_contract * 2)  # Pay fee on buy and sell

        return {
            "market_spread": spread,
            "our_bid": our_bid,
            "our_ask": our_ask,
            "our_spread": our_spread,
            "fee": fee_per_contract * 2,
            "profit_per_contract": profit_per_contract,
            "is_profitable": profit_per_contract > 0
        }

    def place_orders(self, bid_price: int, ask_price: int, quantity: int):
        """Place buy and sell orders"""
        buy_order = Order(side="buy", price=bid_price, quantity=quantity)
        sell_order = Order(side="sell", price=ask_price, quantity=quantity)

        self.orders.append(buy_order)
        self.orders.append(sell_order)

        print(f"\n📋 ORDERS PLACED:")
        print(f"   BUY  {quantity} contracts @ {bid_price}c")
        print(f"   SELL {quantity} contracts @ {ask_price}c")

        return buy_order, sell_order

    def simulate_fill(self, order: Order):
        """Simulate an order getting filled"""
        order.filled = True

        if order.side == "buy":
            # Bought contracts - add to position
            total_cost = self.position.contracts * self.position.avg_cost + order.price * order.quantity
            self.position.contracts += order.quantity
            self.position.avg_cost = total_cost / self.position.contracts if self.position.contracts > 0 else 0

            self.trade_log.append(f"BOUGHT {order.quantity} @ {order.price}c")
            print(f"\n✅ BUY FILLED: {order.quantity} contracts @ {order.price}c")

        else:
            # Sold contracts - reduce position and realize P&L
            pnl = (order.price - self.position.avg_cost) * order.quantity
            self.position.realized_pnl += pnl
            self.position.contracts -= order.quantity

            self.trade_log.append(f"SOLD {order.quantity} @ {order.price}c (P&L: {pnl:.1f}c)")
            print(f"\n✅ SELL FILLED: {order.quantity} contracts @ {order.price}c")
            print(f"   P&L on this trade: {pnl:.1f}c")

    def show_position(self):
        """Display current position and P&L"""
        print(f"\n📊 CURRENT POSITION:")
        print(f"   Contracts held: {self.position.contracts}")
        print(f"   Avg cost: {self.position.avg_cost:.1f}c")
        print(f"   Realized P&L: {self.position.realized_pnl:.1f}c")


def run_simulation():
    """Run a complete market making simulation"""

    print("=" * 60)
    print("MARKET MAKER SIMULATION")
    print("Strategy: Buy at bid, Sell at ask, capture the spread")
    print("=" * 60)

    sim = MarketMakerSimulation()

    # ============== SCENARIO 1: Good Spread ==============
    print("\n" + "▓" * 60)
    print("SCENARIO 1: Market with 5c spread")
    print("▓" * 60)

    # Current market state
    best_bid = 30  # Someone wants to buy at 30c
    best_ask = 35  # Someone wants to sell at 35c
    bid_qty = 1000
    ask_qty = 800

    sim.show_orderbook(best_bid, best_ask, bid_qty, ask_qty)

    # Analyze
    analysis = sim.analyze_opportunity(best_bid, best_ask)

    print("\n📈 ANALYSIS:")
    print(f"   Market spread: {analysis['market_spread']}c")
    print(f"   Our bid: {analysis['our_bid']}c (1c above best bid)")
    print(f"   Our ask: {analysis['our_ask']}c (1c below best ask)")
    print(f"   Our spread: {analysis['our_spread']}c")
    print(f"   Fees (buy + sell): {analysis['fee']}c")
    print(f"   Profit per contract: {analysis['profit_per_contract']}c")
    print(f"   Profitable? {'YES ✓' if analysis['is_profitable'] else 'NO ✗'}")

    if analysis['is_profitable']:
        # Place orders
        quantity = 10
        buy_order, sell_order = sim.place_orders(
            analysis['our_bid'],
            analysis['our_ask'],
            quantity
        )

        # Simulate both orders filling
        print("\n⏳ Waiting for fills...")
        sim.simulate_fill(buy_order)
        sim.simulate_fill(sell_order)

        sim.show_position()

        print(f"\n💰 RESULT: Made {analysis['profit_per_contract'] * quantity}c profit!")

    # ============== SCENARIO 2: Tight Spread ==============
    print("\n" + "▓" * 60)
    print("SCENARIO 2: Market with 2c spread (too tight)")
    print("▓" * 60)

    best_bid = 48
    best_ask = 50

    sim.show_orderbook(best_bid, best_ask, 500, 500)

    analysis = sim.analyze_opportunity(best_bid, best_ask)

    print("\n📈 ANALYSIS:")
    print(f"   Market spread: {analysis['market_spread']}c")
    print(f"   Our bid: {analysis['our_bid']}c")
    print(f"   Our ask: {analysis['our_ask']}c")
    print(f"   Our spread: {analysis['our_spread']}c")
    print(f"   Fees: {analysis['fee']}c")
    print(f"   Profit per contract: {analysis['profit_per_contract']}c")
    print(f"   Profitable? {'YES ✓' if analysis['is_profitable'] else 'NO ✗'}")

    print("\n⚠️  SKIP: Spread too tight, would lose money on fees!")

    # ============== SCENARIO 3: Wide Spread ==============
    print("\n" + "▓" * 60)
    print("SCENARIO 3: Market with 10c spread (great opportunity)")
    print("▓" * 60)

    best_bid = 40
    best_ask = 50

    sim.show_orderbook(best_bid, best_ask, 2000, 1500)

    analysis = sim.analyze_opportunity(best_bid, best_ask)

    print("\n📈 ANALYSIS:")
    print(f"   Market spread: {analysis['market_spread']}c")
    print(f"   Our bid: {analysis['our_bid']}c")
    print(f"   Our ask: {analysis['our_ask']}c")
    print(f"   Our spread: {analysis['our_spread']}c")
    print(f"   Fees: {analysis['fee']}c")
    print(f"   Profit per contract: {analysis['profit_per_contract']}c")
    print(f"   Profitable? {'YES ✓' if analysis['is_profitable'] else 'NO ✗'}")

    quantity = 50
    buy_order, sell_order = sim.place_orders(
        analysis['our_bid'],
        analysis['our_ask'],
        quantity
    )

    sim.simulate_fill(buy_order)
    sim.simulate_fill(sell_order)

    sim.show_position()

    # ============== SUMMARY ==============
    print("\n" + "=" * 60)
    print("SIMULATION COMPLETE")
    print("=" * 60)
    print(f"\n📜 TRADE LOG:")
    for trade in sim.trade_log:
        print(f"   • {trade}")

    print(f"\n💰 TOTAL REALIZED P&L: {sim.position.realized_pnl:.1f}c")
    print(f"   (That's ${sim.position.realized_pnl / 100:.2f})")

    # ============== RISK EXPLANATION ==============
    print("\n" + "=" * 60)
    print("⚠️  RISKS TO UNDERSTAND")
    print("=" * 60)
    print("""
    1. ADVERSE SELECTION
       - Informed traders may hit your orders when price is about to move
       - You buy at 31c, price drops to 20c → stuck with losing position

    2. INVENTORY RISK
       - If only your BUY fills but not your SELL
       - You're now holding a position that might lose value

    3. EXECUTION RISK
       - Market moves before both orders fill
       - Someone else gets filled before you

    4. TIMING RISK
       - Spread might narrow before you profit
       - Events happen that invalidate the market

    MITIGATION:
    - Set position limits (max contracts you'll hold)
    - Cancel unfilled orders quickly
    - Monitor for news/events
    - Only trade liquid markets
    """)


if __name__ == "__main__":
    run_simulation()
