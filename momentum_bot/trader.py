"""
Per-market trader thread.
Handles momentum detection and order execution for a single market.
"""

import time
import threading
from datetime import datetime
from typing import Optional, TYPE_CHECKING

from .models import MarketState, Position, OrderSide, Signal
from .strategy import MomentumStrategy

if TYPE_CHECKING:
    from .bot import MomentumBot


class MarketTrader(threading.Thread):
    """
    Trading thread for a single market.

    Each market gets its own thread that:
    - Maintains price history
    - Runs momentum strategy
    - Manages orders and positions
    - Handles stop-loss and trailing stops
    """

    def __init__(self, ticker: str, bot: 'MomentumBot'):
        super().__init__(daemon=True)
        self.ticker = ticker
        self.bot = bot
        self.config = bot.config
        self.strategy = MomentumStrategy(bot.config)

        # Market state with price history
        self.state = MarketState(ticker=ticker)

        # Position tracking (local view)
        self.position: Optional[Position] = None

        # Order tracking
        self.pending_order_id: Optional[str] = None
        self.stop_loss_order_id: Optional[str] = None

        # Thread control
        self.running = True
        self.last_analysis_time = 0
        self.last_trade_time = 0

        # Stats
        self.stats = {
            'signals_detected': 0,
            'entries': 0,
            'exits': 0,
            'stop_losses': 0,
            'trailing_stops': 0,
            'reversals': 0
        }

    def log(self, msg: str):
        """Log with timestamp and ticker."""
        ts = datetime.now().strftime("%H:%M:%S")
        short_ticker = self.ticker[:25]
        print(f"[{ts}] [{short_ticker}] {msg}", flush=True)

    def update_price(self, data: dict):
        """
        Update market state from WebSocket data.
        Called by the main bot when price updates arrive.
        """
        if data.get('type') == 'snapshot':
            self.state.yes_bid = data.get('yes_bid', self.state.yes_bid)
            self.state.yes_ask = data.get('yes_ask', self.state.yes_ask)
            self.state.no_bid = data.get('no_bid', self.state.no_bid)
            self.state.no_ask = data.get('no_ask', self.state.no_ask)

        elif data.get('type') == 'delta':
            side = data.get('side')
            price = data.get('price', 0)

            if side == 'yes':
                self.state.yes_bid = price
            elif side == 'no':
                self.state.no_bid = price

        self.state.last_update = time.time()
        self.state.add_snapshot()

    def run(self):
        """Main thread loop."""
        self.log("🚀 Trader started")

        while self.running:
            try:
                self._tick()
                time.sleep(0.2)  # 5 Hz update rate
            except Exception as e:
                self.log(f"Error: {e}")
                time.sleep(1)

        self.log("🛑 Trader stopped")

    def _tick(self):
        """Single iteration of the trading loop."""
        now = time.time()

        # Skip if no recent price data
        if now - self.state.last_update > 10:
            return

        # Check existing position for exits
        if self.position and self.position.is_open:
            self._check_exits()

        # Run strategy analysis
        if now - self.last_analysis_time >= 0.5:  # Analyze every 500ms
            self.last_analysis_time = now
            self._analyze_and_trade()

    def _analyze_and_trade(self):
        """Run strategy and potentially enter/exit."""
        # Get momentum signal
        signal = self.strategy.analyze(self.state)

        if signal and signal.signal != Signal.NEUTRAL:
            self.stats['signals_detected'] += 1

            # Log significant signals
            if signal.confidence >= 0.3:
                direction = "📈" if signal.signal == Signal.BULLISH else "📉"
                self.log(f"{direction} Signal: {signal.signal.value} | "
                        f"Gap Δ: {signal.gap_change:+.1f} | "
                        f"YES Δ: {signal.yes_price_change:+.1f}c | "
                        f"Conf: {signal.confidence:.0%}")

            # Check if we should enter
            if not self.position or not self.position.is_open:
                self._try_enter(signal)

            # Check if we should reverse
            elif self.position and self.position.is_open:
                should_reverse, reason = self.strategy.should_reverse(signal, self.position)
                if should_reverse:
                    self._reverse_position(signal, reason)

    def _try_enter(self, signal):
        """Attempt to enter a position based on signal."""
        # Check cooldown
        if time.time() - self.last_trade_time < self.config.cooldown_seconds:
            return

        # Get entry parameters
        should_enter, side, action, price = self.strategy.should_enter(signal, self.position)
        if not should_enter:
            return

        # Check risk limits
        can_trade, reason = self.bot.risk_manager.check_can_trade(
            self.ticker,
            self.config.order_size,
            price
        )
        if not can_trade:
            self.log(f"⚠️ Risk check failed: {reason}")
            return

        # Calculate stops
        stop_loss = self.strategy.calculate_stop_loss(price, side)
        trailing_stop = self.strategy.calculate_initial_trailing_stop(price)

        # Place entry order
        self.log(f"🎯 ENTERING: {action.upper()} {side.upper()} @ {price}c | "
                f"Stop: {stop_loss}c | Trail: {trailing_stop}c")

        try:
            result = self.bot.client.place_order(
                ticker=self.ticker,
                side=side,
                action=action,
                price=price,
                count=self.config.order_size
            )

            order = result.get('order', {})
            order_id = order.get('order_id')

            if order_id:
                self.pending_order_id = order_id
                self.last_trade_time = time.time()
                self.stats['entries'] += 1

                # Create position (assume filled for simplicity)
                # In production, you'd check fill status
                self.position = Position(
                    ticker=self.ticker,
                    side=OrderSide.YES if side == 'yes' else OrderSide.NO,
                    quantity=self.config.order_size,
                    avg_entry_price=price,
                    stop_loss_price=stop_loss,
                    trailing_stop_price=trailing_stop,
                    highest_price_seen=price
                )

                # Record in risk manager
                self.bot.risk_manager.record_entry(
                    ticker=self.ticker,
                    side=self.position.side,
                    quantity=self.config.order_size,
                    price=price,
                    stop_loss_price=stop_loss,
                    trailing_stop_price=trailing_stop
                )

                # Record trade
                self.bot.tracker.record_trade(
                    ticker=self.ticker,
                    side=side,
                    action=action,
                    price=price,
                    quantity=self.config.order_size,
                    order_id=order_id
                )

                self.log(f"✅ Entry filled: {order_id[:8]}")

        except Exception as e:
            self.log(f"❌ Entry failed: {e}")

    def _check_exits(self):
        """Check if we should exit the current position."""
        if not self.position or not self.position.is_open:
            return

        # Get current price for our side
        if self.position.side == OrderSide.YES:
            current_price = int(self.state.yes_mid) if self.state.yes_mid else self.state.yes_bid
        else:
            current_price = int(self.state.no_mid) if self.state.no_mid else self.state.no_bid

        if current_price <= 0:
            return

        # Update trailing stop
        if current_price > self.position.highest_price_seen:
            self.position.highest_price_seen = current_price
            new_trail = current_price - self.config.trailing_stop_cents
            if new_trail > self.position.trailing_stop_price:
                self.position.trailing_stop_price = new_trail
                self.bot.risk_manager.update_trailing_stop(self.ticker, current_price)

        # Check exit conditions
        should_exit, reason = self.strategy.should_exit(self.position, current_price)

        if should_exit:
            self._exit_position(current_price, reason)

    def _exit_position(self, exit_price: int, reason: str):
        """Exit the current position."""
        if not self.position or not self.position.is_open:
            return

        side = 'yes' if self.position.side == OrderSide.YES else 'no'

        self.log(f"🚪 EXITING ({reason}): SELL {side.upper()} @ {exit_price}c")

        try:
            result = self.bot.client.place_order(
                ticker=self.ticker,
                side=side,
                action='sell',
                price=exit_price,
                count=self.position.quantity
            )

            order = result.get('order', {})
            order_id = order.get('order_id')

            if order_id:
                # Calculate P&L
                pnl = self.bot.risk_manager.record_exit(self.ticker, exit_price)

                # Record trade
                self.bot.tracker.record_trade(
                    ticker=self.ticker,
                    side=side,
                    action='sell',
                    price=exit_price,
                    quantity=self.position.quantity,
                    order_id=order_id,
                    pnl=pnl
                )

                self.stats['exits'] += 1
                if reason == 'stop_loss':
                    self.stats['stop_losses'] += 1
                elif reason == 'trailing_stop':
                    self.stats['trailing_stops'] += 1

                pnl_str = f"+${pnl:.2f}" if pnl >= 0 else f"-${abs(pnl):.2f}"
                emoji = "🟢" if pnl >= 0 else "🔴"
                self.log(f"{emoji} Exit filled: {reason} | P&L: {pnl_str}")

                # Clear position
                self.position.quantity = 0
                self.last_trade_time = time.time()

        except Exception as e:
            self.log(f"❌ Exit failed: {e}")

    def _reverse_position(self, signal, reason: str):
        """Close current position and enter opposite direction."""
        if not self.position or not self.position.is_open:
            return

        self.log(f"🔄 REVERSING ({reason})")

        # First exit current position
        if self.position.side == OrderSide.YES:
            exit_price = int(self.state.yes_mid) if self.state.yes_mid else self.state.yes_bid
        else:
            exit_price = int(self.state.no_mid) if self.state.no_mid else self.state.no_bid

        self._exit_position(exit_price, f"reversal_{reason}")

        # Wait briefly then enter opposite
        time.sleep(0.5)

        self.stats['reversals'] += 1

        # Now try to enter in the new direction
        self._try_enter(signal)

    def get_status(self) -> dict:
        """Get current trader status."""
        pos_info = None
        if self.position and self.position.is_open:
            current_price = int(self.state.yes_mid) if self.position.side == OrderSide.YES else int(self.state.no_mid)
            pnl = self.position.calculate_pnl(current_price) if current_price else 0

            pos_info = {
                'side': self.position.side.value,
                'quantity': self.position.quantity,
                'entry': self.position.avg_entry_price,
                'current': current_price,
                'stop_loss': self.position.stop_loss_price,
                'trailing_stop': self.position.trailing_stop_price,
                'unrealized_pnl': pnl
            }

        return {
            'ticker': self.ticker,
            'yes_bid': self.state.yes_bid,
            'yes_ask': self.state.yes_ask,
            'no_bid': self.state.no_bid,
            'gap': self.state.gap,
            'position': pos_info,
            'stats': self.stats.copy()
        }

    def stop(self):
        """Stop the trader thread."""
        self.running = False

        # Exit any open position
        if self.position and self.position.is_open:
            current_price = int(self.state.yes_mid) if self.position.side == OrderSide.YES else int(self.state.no_mid)
            if current_price > 0:
                self._exit_position(current_price, "shutdown")
