"""
Trade and P&L tracking with persistence.
"""

import json
import os
import time
import threading
from datetime import datetime
from typing import List, Dict, Optional
from .models import Trade


class TradeTracker:
    """
    Tracks all trades and calculates P&L.
    Persists to JSON file for recovery.
    """

    def __init__(self, save_path: str = "momentum_trades.json"):
        self.save_path = save_path
        self.lock = threading.Lock()

        # Trade history
        self.trades: List[Trade] = []

        # P&L tracking
        self.realized_pnl: float = 0.0
        self.starting_balance: float = 0.0

        # Per-market tracking
        self.market_pnl: Dict[str, float] = {}
        self.market_trades: Dict[str, int] = {}

        # Session stats
        self.session_start: float = time.time()
        self.winning_trades: int = 0
        self.losing_trades: int = 0

        # Load existing history
        self._load()

    def _load(self):
        """Load trade history from file."""
        if not os.path.exists(self.save_path):
            return

        try:
            with open(self.save_path, 'r') as f:
                data = json.load(f)

            self.realized_pnl = data.get('realized_pnl', 0.0)
            self.starting_balance = data.get('starting_balance', 0.0)
            self.market_pnl = data.get('market_pnl', {})
            self.market_trades = data.get('market_trades', {})
            self.winning_trades = data.get('winning_trades', 0)
            self.losing_trades = data.get('losing_trades', 0)

            for t in data.get('trades', []):
                self.trades.append(Trade.from_dict(t))

            print(f"[TRACKER] Loaded {len(self.trades)} trades, P&L: ${self.realized_pnl:.2f}")

        except Exception as e:
            print(f"[TRACKER] Error loading: {e}")

    def _save(self):
        """Save trade history to file."""
        try:
            data = {
                'realized_pnl': self.realized_pnl,
                'starting_balance': self.starting_balance,
                'market_pnl': self.market_pnl,
                'market_trades': self.market_trades,
                'winning_trades': self.winning_trades,
                'losing_trades': self.losing_trades,
                'trades': [t.to_dict() for t in self.trades[-1000:]],  # Keep last 1000
                'last_updated': datetime.now().isoformat()
            }
            with open(self.save_path, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"[TRACKER] Error saving: {e}")

    def set_starting_balance(self, balance: float):
        """Set starting balance for session."""
        with self.lock:
            if self.starting_balance == 0:
                self.starting_balance = balance
                self._save()

    def record_trade(
        self,
        ticker: str,
        side: str,
        action: str,
        price: int,
        quantity: int,
        order_id: str = "",
        pnl: float = 0.0
    ) -> Trade:
        """
        Record an executed trade.

        Args:
            ticker: Market ticker
            side: 'yes' or 'no'
            action: 'buy' or 'sell'
            price: Fill price in cents
            quantity: Number of contracts
            order_id: Optional order ID
            pnl: Realized P&L if closing position

        Returns:
            The recorded Trade
        """
        with self.lock:
            trade = Trade(
                ticker=ticker,
                side=side,
                action=action,
                price=price,
                quantity=quantity,
                order_id=order_id,
                pnl=pnl
            )
            self.trades.append(trade)

            # Update P&L
            if pnl != 0:
                self.realized_pnl += pnl
                if ticker not in self.market_pnl:
                    self.market_pnl[ticker] = 0.0
                self.market_pnl[ticker] += pnl

                if pnl > 0:
                    self.winning_trades += 1
                else:
                    self.losing_trades += 1

            # Update trade count
            if ticker not in self.market_trades:
                self.market_trades[ticker] = 0
            self.market_trades[ticker] += 1

            self._save()
            return trade

    def get_summary(self) -> dict:
        """Get trading summary."""
        with self.lock:
            total_trades = len(self.trades)
            session_duration = time.time() - self.session_start

            return {
                'total_trades': total_trades,
                'realized_pnl': self.realized_pnl,
                'starting_balance': self.starting_balance,
                'winning_trades': self.winning_trades,
                'losing_trades': self.losing_trades,
                'win_rate': self.winning_trades / max(1, self.winning_trades + self.losing_trades),
                'markets_traded': len(self.market_trades),
                'session_duration_minutes': session_duration / 60
            }

    def get_market_summary(self, ticker: str) -> dict:
        """Get summary for a specific market."""
        with self.lock:
            return {
                'ticker': ticker,
                'pnl': self.market_pnl.get(ticker, 0.0),
                'trades': self.market_trades.get(ticker, 0)
            }

    def print_summary(self):
        """Print formatted summary."""
        summary = self.get_summary()

        pnl = summary['realized_pnl']
        pnl_str = f"+${pnl:.2f}" if pnl >= 0 else f"-${abs(pnl):.2f}"
        emoji = "🟢" if pnl >= 0 else "🔴"

        print("\n" + "=" * 60)
        print("📊 MOMENTUM BOT - TRADE SUMMARY")
        print("=" * 60)
        print(f"{emoji} Realized P&L: {pnl_str}")
        print(f"📈 Total Trades: {summary['total_trades']}")
        print(f"✅ Winning: {summary['winning_trades']} | ❌ Losing: {summary['losing_trades']}")
        print(f"🎯 Win Rate: {summary['win_rate']*100:.1f}%")
        print(f"🏪 Markets Traded: {summary['markets_traded']}")
        print(f"⏱️ Session: {summary['session_duration_minutes']:.1f} minutes")

        # Top markets
        if self.market_pnl:
            sorted_markets = sorted(self.market_pnl.items(), key=lambda x: x[1], reverse=True)
            print("\n🏆 Top Markets:")
            for ticker, market_pnl in sorted_markets[:3]:
                if market_pnl > 0:
                    print(f"   {ticker[:35]}: +${market_pnl:.2f}")

            print("\n📉 Bottom Markets:")
            for ticker, market_pnl in sorted_markets[-3:]:
                if market_pnl < 0:
                    print(f"   {ticker[:35]}: -${abs(market_pnl):.2f}")

        print("=" * 60 + "\n")

    def reset(self):
        """Reset all tracking data."""
        with self.lock:
            self.trades = []
            self.realized_pnl = 0.0
            self.starting_balance = 0.0
            self.market_pnl = {}
            self.market_trades = {}
            self.winning_trades = 0
            self.losing_trades = 0
            self.session_start = time.time()
            self._save()
            print("[TRACKER] Reset complete")
