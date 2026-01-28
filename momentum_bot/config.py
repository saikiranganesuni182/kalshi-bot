"""
Configuration for the momentum trading bot.
"""

from dataclasses import dataclass


@dataclass
class Config:
    """Bot configuration"""

    # API Settings
    api_key: str = ""
    private_key_path: str = "private_key.pem"
    use_demo: bool = True

    # URLs
    @property
    def rest_url(self) -> str:
        if self.use_demo:
            return "https://demo-api.kalshi.co/trade-api/v2"
        return "https://trading-api.kalshi.co/trade-api/v2"

    @property
    def ws_url(self) -> str:
        if self.use_demo:
            return "wss://demo-api.kalshi.co/trade-api/ws/v2"
        return "wss://trading-api.kalshi.co/trade-api/ws/v2"

    @property
    def ws_path(self) -> str:
        return "/trade-api/ws/v2"

    # Liquidity Requirements
    min_volume: int = 100  # Minimum contract volume
    min_open_interest: int = 50  # Minimum open interest
    max_spread: int = 10  # Maximum bid-ask spread in cents
    min_bid_size: int = 10  # Minimum contracts at best bid
    min_ask_size: int = 10  # Minimum contracts at best ask

    # Momentum Detection
    momentum_window_seconds: float = 5.0  # Window to detect momentum
    entry_threshold_cents: int = 2  # Minimum price movement to trigger entry
    convergence_threshold_pct: float = 5.0  # % change in gap to signal momentum

    # Risk Management
    order_size: int = 5  # Contracts per order
    max_position_per_market: int = 50  # Max contracts per market
    max_total_exposure: float = 500.0  # Max total $ at risk
    stop_loss_cents: int = 2  # Stop loss distance from entry
    trailing_stop_cents: int = 2  # Trailing stop distance
    kalshi_fee_cents: int = 1  # Kalshi fee per contract
    max_daily_loss: float = 50.0  # Circuit breaker

    # Execution
    max_markets: int = 10  # Max markets to monitor
    order_timeout_seconds: int = 10  # Cancel unfilled orders after this
    cooldown_seconds: float = 2.0  # Wait between trades on same market
    market_scan_interval: int = 60  # Scan for new liquid markets every N seconds

    def to_dict(self) -> dict:
        return {
            'api_key': self.api_key[:8] + '...' if self.api_key else '',
            'use_demo': self.use_demo,
            'min_volume': self.min_volume,
            'max_spread': self.max_spread,
            'momentum_window_seconds': self.momentum_window_seconds,
            'entry_threshold_cents': self.entry_threshold_cents,
            'convergence_threshold_pct': self.convergence_threshold_pct,
            'order_size': self.order_size,
            'max_position_per_market': self.max_position_per_market,
            'stop_loss_cents': self.stop_loss_cents,
            'trailing_stop_cents': self.trailing_stop_cents,
            'max_markets': self.max_markets,
            'market_scan_interval': self.market_scan_interval,
        }


# Default configuration
DEFAULT_CONFIG = Config()
