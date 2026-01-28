"""
Data models for the momentum trading bot.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List
import time
import uuid


class Signal(Enum):
    """Trading signal based on momentum"""
    BULLISH = "bullish"  # YES price rising (gap shrinking toward YES)
    BEARISH = "bearish"  # NO price rising (gap shrinking toward NO)
    NEUTRAL = "neutral"  # No clear momentum


class OrderSide(Enum):
    YES = "yes"
    NO = "no"


class OrderAction(Enum):
    BUY = "buy"
    SELL = "sell"


@dataclass
class PriceSnapshot:
    """A single price observation"""
    timestamp: float
    yes_bid: int
    yes_ask: int
    no_bid: int
    no_ask: int

    @property
    def yes_mid(self) -> float:
        if self.yes_bid and self.yes_ask:
            return (self.yes_bid + self.yes_ask) / 2
        return 0

    @property
    def no_mid(self) -> float:
        if self.no_bid and self.no_ask:
            return (self.no_bid + self.no_ask) / 2
        return 0

    @property
    def gap(self) -> float:
        """
        The gap between YES and NO.
        In a perfect market: YES + NO = 100 (so gap = 0)
        Gap = 100 - yes_mid - no_mid
        Positive gap = prices haven't converged yet
        """
        if self.yes_mid and self.no_mid:
            return 100 - self.yes_mid - self.no_mid
        return 0


@dataclass
class MarketState:
    """Current state of a market with history"""
    ticker: str
    yes_bid: int = 0
    yes_ask: int = 0
    no_bid: int = 0
    no_ask: int = 0
    volume: int = 0
    last_update: float = field(default_factory=time.time)

    # Price history for momentum detection
    price_history: List[PriceSnapshot] = field(default_factory=list)
    max_history_seconds: float = 30.0  # Keep 30 seconds of history

    @property
    def yes_mid(self) -> float:
        if self.yes_bid and self.yes_ask:
            return (self.yes_bid + self.yes_ask) / 2
        return self.yes_bid or 0

    @property
    def no_mid(self) -> float:
        if self.no_bid and self.no_ask:
            return (self.no_bid + self.no_ask) / 2
        return self.no_bid or 0

    @property
    def spread(self) -> int:
        if self.yes_bid and self.yes_ask:
            return self.yes_ask - self.yes_bid
        return 0

    @property
    def gap(self) -> float:
        """Gap between YES and NO midpoints"""
        return 100 - self.yes_mid - self.no_mid

    def add_snapshot(self):
        """Record current prices to history"""
        now = time.time()
        snapshot = PriceSnapshot(
            timestamp=now,
            yes_bid=self.yes_bid,
            yes_ask=self.yes_ask,
            no_bid=self.no_bid,
            no_ask=self.no_ask
        )
        self.price_history.append(snapshot)

        # Trim old history
        cutoff = now - self.max_history_seconds
        self.price_history = [p for p in self.price_history if p.timestamp > cutoff]

    def get_gap_change(self, window_seconds: float) -> Optional[float]:
        """
        Calculate gap change over the window.
        Negative = gap shrinking = momentum detected
        Positive = gap widening = no momentum

        Returns None if insufficient data.
        """
        if len(self.price_history) < 2:
            return None

        now = time.time()
        cutoff = now - window_seconds

        # Find oldest snapshot in window
        old_snapshots = [p for p in self.price_history if p.timestamp <= cutoff]
        if not old_snapshots:
            # Use oldest available
            old_snapshot = self.price_history[0]
        else:
            old_snapshot = old_snapshots[-1]

        current_gap = self.gap
        old_gap = old_snapshot.gap

        if old_gap == 0:
            return None

        return current_gap - old_gap

    def get_yes_price_change(self, window_seconds: float) -> Optional[float]:
        """Calculate YES price change over window."""
        if len(self.price_history) < 2:
            return None

        now = time.time()
        cutoff = now - window_seconds

        old_snapshots = [p for p in self.price_history if p.timestamp <= cutoff]
        if not old_snapshots:
            old_snapshot = self.price_history[0]
        else:
            old_snapshot = old_snapshots[-1]

        return self.yes_mid - old_snapshot.yes_mid


@dataclass
class Position:
    """A position in a market"""
    ticker: str
    side: OrderSide  # YES or NO
    quantity: int = 0
    avg_entry_price: float = 0.0
    entry_time: float = field(default_factory=time.time)

    # Stop loss tracking
    stop_loss_price: int = 0
    trailing_stop_price: int = 0
    highest_price_seen: int = 0  # For trailing stop

    @property
    def is_open(self) -> bool:
        return self.quantity > 0

    def calculate_pnl(self, current_price: int) -> float:
        """Calculate unrealized P&L in dollars."""
        if self.quantity == 0:
            return 0.0
        # P&L = (current - entry) * quantity / 100
        return (current_price - self.avg_entry_price) * self.quantity / 100

    def update_trailing_stop(self, current_price: int, trail_cents: int):
        """Update trailing stop based on current price."""
        if current_price > self.highest_price_seen:
            self.highest_price_seen = current_price
            self.trailing_stop_price = current_price - trail_cents


@dataclass
class Trade:
    """Record of an executed trade"""
    trade_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    ticker: str = ""
    side: str = "yes"  # 'yes' or 'no'
    action: str = "buy"  # 'buy' or 'sell'
    price: int = 0
    quantity: int = 0
    timestamp: float = field(default_factory=time.time)
    order_id: str = ""
    pnl: float = 0.0  # Realized P&L if closing

    def to_dict(self) -> dict:
        return {
            'trade_id': self.trade_id,
            'ticker': self.ticker,
            'side': self.side,
            'action': self.action,
            'price': self.price,
            'quantity': self.quantity,
            'timestamp': self.timestamp,
            'datetime': datetime.fromtimestamp(self.timestamp).isoformat(),
            'order_id': self.order_id,
            'pnl': self.pnl
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Trade':
        return cls(
            trade_id=data.get('trade_id', ''),
            ticker=data.get('ticker', ''),
            side=data.get('side', 'yes'),
            action=data.get('action', 'buy'),
            price=data.get('price', 0),
            quantity=data.get('quantity', 0),
            timestamp=data.get('timestamp', time.time()),
            order_id=data.get('order_id', ''),
            pnl=data.get('pnl', 0.0)
        )


@dataclass
class MomentumSignal:
    """A detected momentum signal"""
    ticker: str
    signal: Signal
    gap_change: float  # Change in gap (negative = converging)
    yes_price_change: float  # Change in YES price
    current_yes_price: int
    current_no_price: int
    confidence: float = 0.0  # 0-1 confidence score
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            'ticker': self.ticker,
            'signal': self.signal.value,
            'gap_change': self.gap_change,
            'yes_price_change': self.yes_price_change,
            'current_yes_price': self.current_yes_price,
            'current_no_price': self.current_no_price,
            'confidence': self.confidence,
            'timestamp': self.timestamp
        }
