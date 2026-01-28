"""
Momentum convergence strategy.

Detects when YES/NO prices are converging (gap shrinking) and generates trading signals.
"""

import time
from typing import Optional, Tuple
from .models import MarketState, Signal, MomentumSignal, Position, OrderSide
from .config import Config


class MomentumStrategy:
    """
    Momentum convergence detection strategy.

    Theory:
    - YES price + NO price should equal ~100 cents
    - When there's a gap (e.g., YES=30, NO=60, gap=10), one side will converge
    - If YES is rising (gap shrinking), there's bullish momentum
    - If NO is rising (gap shrinking), there's bearish momentum

    Entry:
    - Enter when gap shrinks by threshold over window
    - Buy YES on bullish signal, buy NO on bearish signal

    Exit:
    - Stop loss at entry price + fee
    - Trailing stop as position moves in favor
    """

    def __init__(self, config: Config):
        self.config = config

    def analyze(self, state: MarketState) -> Optional[MomentumSignal]:
        """
        Analyze market state and generate signal if momentum detected.

        Args:
            state: Current market state with price history

        Returns:
            MomentumSignal if momentum detected, None otherwise
        """
        # Need price history
        if len(state.price_history) < 3:
            return None

        # Calculate changes over momentum window
        gap_change = state.get_gap_change(self.config.momentum_window_seconds)
        yes_change = state.get_yes_price_change(self.config.momentum_window_seconds)

        if gap_change is None or yes_change is None:
            return None

        # Determine signal
        signal = Signal.NEUTRAL
        confidence = 0.0

        # Gap shrinking (negative change) with YES rising = BULLISH
        # Gap shrinking with YES falling = BEARISH (NO is rising)
        if gap_change < -self.config.convergence_threshold_pct:
            if yes_change >= self.config.entry_threshold_cents:
                signal = Signal.BULLISH
                confidence = min(1.0, abs(yes_change) / 5)  # Scale confidence
            elif yes_change <= -self.config.entry_threshold_cents:
                signal = Signal.BEARISH
                confidence = min(1.0, abs(yes_change) / 5)

        # Also detect pure price momentum even without gap change
        if signal == Signal.NEUTRAL:
            if yes_change >= self.config.entry_threshold_cents * 1.5:
                signal = Signal.BULLISH
                confidence = min(0.8, abs(yes_change) / 6)
            elif yes_change <= -self.config.entry_threshold_cents * 1.5:
                signal = Signal.BEARISH
                confidence = min(0.8, abs(yes_change) / 6)

        if signal == Signal.NEUTRAL:
            return None

        return MomentumSignal(
            ticker=state.ticker,
            signal=signal,
            gap_change=gap_change,
            yes_price_change=yes_change,
            current_yes_price=int(state.yes_mid),
            current_no_price=int(state.no_mid),
            confidence=confidence
        )

    def should_enter(self, signal: MomentumSignal, position: Optional[Position]) -> Tuple[bool, str, str, int]:
        """
        Determine if we should enter based on signal.

        Args:
            signal: Detected momentum signal
            position: Current position (if any)

        Returns:
            Tuple of (should_enter, side, action, price)
        """
        # Don't enter if we already have a position in this direction
        if position and position.is_open:
            return (False, "", "", 0)

        if signal.signal == Signal.BULLISH:
            # Buy YES - price is rising
            entry_price = signal.current_yes_price + 1  # Slightly aggressive
            return (True, "yes", "buy", entry_price)

        elif signal.signal == Signal.BEARISH:
            # Buy NO - YES price is falling, NO is rising
            entry_price = signal.current_no_price + 1
            return (True, "no", "buy", entry_price)

        return (False, "", "", 0)

    def calculate_stop_loss(self, entry_price: int, side: str) -> int:
        """
        Calculate stop loss price.
        Stop loss = entry price - stop_loss_cents (for buys)
        We include the Kalshi fee to ensure we don't lose money.
        """
        total_buffer = self.config.stop_loss_cents + self.config.kalshi_fee_cents
        return max(1, entry_price - total_buffer)

    def calculate_initial_trailing_stop(self, entry_price: int) -> int:
        """Calculate initial trailing stop price."""
        return max(1, entry_price - self.config.trailing_stop_cents)

    def should_exit(self, position: Position, current_price: int) -> Tuple[bool, str]:
        """
        Check if position should be exited.

        Args:
            position: Current position
            current_price: Current market price

        Returns:
            Tuple of (should_exit, reason)
        """
        if not position.is_open:
            return (False, "")

        # Check stop loss
        if current_price <= position.stop_loss_price:
            return (True, "stop_loss")

        # Check trailing stop
        if position.trailing_stop_price > 0 and current_price <= position.trailing_stop_price:
            return (True, "trailing_stop")

        return (False, "")

    def should_reverse(
        self,
        current_signal: MomentumSignal,
        position: Position
    ) -> Tuple[bool, str]:
        """
        Check if we should reverse position.

        If we're long YES and signal turns BEARISH, close and go long NO.

        Args:
            current_signal: Current momentum signal
            position: Current position

        Returns:
            Tuple of (should_reverse, reason)
        """
        if not position.is_open:
            return (False, "")

        # Long YES but signal is now bearish
        if position.side == OrderSide.YES and current_signal.signal == Signal.BEARISH:
            if current_signal.confidence >= 0.5:  # Need decent confidence to reverse
                return (True, "bearish_reversal")

        # Long NO but signal is now bullish
        if position.side == OrderSide.NO and current_signal.signal == Signal.BULLISH:
            if current_signal.confidence >= 0.5:
                return (True, "bullish_reversal")

        return (False, "")
