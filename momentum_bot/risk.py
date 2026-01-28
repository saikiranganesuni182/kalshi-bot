"""
Risk management module.
Handles position limits, stop-losses, and circuit breakers.
"""

import time
import threading
from typing import Dict, Optional, Tuple
from .models import Position, OrderSide
from .config import Config


class RiskManager:
    """
    Manages risk across all positions.

    Features:
    - Position limits per market
    - Total exposure limits
    - Daily loss circuit breaker
    - Cooldown periods
    """

    def __init__(self, config: Config):
        self.config = config
        self.lock = threading.Lock()

        # Track positions by ticker
        self.positions: Dict[str, Position] = {}

        # Daily P&L tracking
        self.daily_realized_pnl: float = 0.0
        self.daily_start_time: float = time.time()

        # Cooldowns: ticker -> last trade time
        self.cooldowns: Dict[str, float] = {}

        # Circuit breaker state
        self.circuit_breaker_tripped: bool = False

    def check_can_trade(self, ticker: str, size: int, price: int) -> Tuple[bool, str]:
        """
        Check if a trade is allowed under risk rules.

        Args:
            ticker: Market ticker
            size: Number of contracts
            price: Price in cents

        Returns:
            Tuple of (allowed, reason)
        """
        with self.lock:
            # Check circuit breaker
            if self.circuit_breaker_tripped:
                return (False, "circuit_breaker_tripped")

            # Check daily loss
            if self.daily_realized_pnl <= -self.config.max_daily_loss:
                self.circuit_breaker_tripped = True
                return (False, f"max_daily_loss_exceeded: ${self.daily_realized_pnl:.2f}")

            # Check cooldown
            if ticker in self.cooldowns:
                elapsed = time.time() - self.cooldowns[ticker]
                if elapsed < self.config.cooldown_seconds:
                    return (False, f"cooldown: {self.config.cooldown_seconds - elapsed:.1f}s remaining")

            # Check position limit for this market
            current_pos = self.positions.get(ticker)
            if current_pos and current_pos.quantity + size > self.config.max_position_per_market:
                return (False, f"max_position_per_market: {current_pos.quantity} + {size} > {self.config.max_position_per_market}")

            # Check total exposure
            total_exposure = sum(
                p.quantity * p.avg_entry_price / 100
                for p in self.positions.values()
                if p.is_open
            )
            new_exposure = size * price / 100
            if total_exposure + new_exposure > self.config.max_total_exposure:
                return (False, f"max_total_exposure: ${total_exposure:.2f} + ${new_exposure:.2f} > ${self.config.max_total_exposure:.2f}")

            return (True, "ok")

    def record_entry(
        self,
        ticker: str,
        side: OrderSide,
        quantity: int,
        price: int,
        stop_loss_price: int,
        trailing_stop_price: int
    ):
        """Record a new position entry."""
        with self.lock:
            self.positions[ticker] = Position(
                ticker=ticker,
                side=side,
                quantity=quantity,
                avg_entry_price=price,
                stop_loss_price=stop_loss_price,
                trailing_stop_price=trailing_stop_price,
                highest_price_seen=price
            )
            self.cooldowns[ticker] = time.time()

    def record_exit(self, ticker: str, exit_price: int) -> float:
        """
        Record position exit and calculate P&L.

        Returns realized P&L in dollars.
        """
        with self.lock:
            position = self.positions.get(ticker)
            if not position or not position.is_open:
                return 0.0

            pnl = position.calculate_pnl(exit_price)
            self.daily_realized_pnl += pnl

            # Clear position
            position.quantity = 0
            self.cooldowns[ticker] = time.time()

            return pnl

    def update_trailing_stop(self, ticker: str, current_price: int):
        """Update trailing stop for a position."""
        with self.lock:
            position = self.positions.get(ticker)
            if position and position.is_open:
                position.update_trailing_stop(current_price, self.config.trailing_stop_cents)

    def get_position(self, ticker: str) -> Optional[Position]:
        """Get position for a ticker."""
        with self.lock:
            pos = self.positions.get(ticker)
            if pos:
                # Return a copy to avoid threading issues
                return Position(
                    ticker=pos.ticker,
                    side=pos.side,
                    quantity=pos.quantity,
                    avg_entry_price=pos.avg_entry_price,
                    entry_time=pos.entry_time,
                    stop_loss_price=pos.stop_loss_price,
                    trailing_stop_price=pos.trailing_stop_price,
                    highest_price_seen=pos.highest_price_seen
                )
            return None

    def get_all_positions(self) -> Dict[str, Position]:
        """Get all open positions."""
        with self.lock:
            return {
                ticker: Position(
                    ticker=pos.ticker,
                    side=pos.side,
                    quantity=pos.quantity,
                    avg_entry_price=pos.avg_entry_price,
                    entry_time=pos.entry_time,
                    stop_loss_price=pos.stop_loss_price,
                    trailing_stop_price=pos.trailing_stop_price,
                    highest_price_seen=pos.highest_price_seen
                )
                for ticker, pos in self.positions.items()
                if pos.is_open
            }

    def get_summary(self) -> dict:
        """Get risk summary."""
        with self.lock:
            open_positions = [p for p in self.positions.values() if p.is_open]
            total_exposure = sum(p.quantity * p.avg_entry_price / 100 for p in open_positions)

            return {
                'open_positions': len(open_positions),
                'total_exposure': total_exposure,
                'daily_pnl': self.daily_realized_pnl,
                'circuit_breaker': self.circuit_breaker_tripped,
                'max_daily_loss': self.config.max_daily_loss,
                'max_exposure': self.config.max_total_exposure
            }

    def reset_daily(self):
        """Reset daily tracking (call at market open)."""
        with self.lock:
            self.daily_realized_pnl = 0.0
            self.daily_start_time = time.time()
            self.circuit_breaker_tripped = False
