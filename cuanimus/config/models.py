"""
CUANIMUS Typed Configuration Models.
Defines strongly typed, validated configuration sections:
- EnvironmentConfig
- ExchangeConfig
- MarketConfig
- StrategyConfig
- RiskConfig
- ExecutionConfig
- AIConfig
- BacktestConfig
- NotificationConfig
- ObservabilityConfig
- CuanimusConfig (Root)
"""
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional
from cuanimus.config.fields import ConfigField, RuntimePolicy, RiskLevel


@dataclass
class EnvironmentConfig:
    env_name: str = "paper"  # "research", "backtest", "paper", "testnet", "live"
    dry_run: bool = True
    live_trading_enabled: bool = False  # SAFETY INVARIANT: Real money is disabled by default
    data_dir: str = "user_data/data"
    db_url: str = "sqlite:///user_data/cuanimus.sqlite"

    @classmethod
    def get_field_specs(cls) -> Dict[str, ConfigField]:
        return {
            "env_name": ConfigField(
                name="env_name", field_type="str", default="paper",
                description="Target runtime environment mode",
                choices=["research", "backtest", "paper", "testnet", "live"],
                category="environment", risk_level=RiskLevel.CRITICAL,
                runtime_policy=RuntimePolicy.NEVER_RUNTIME_MODIFIABLE
            ),
            "dry_run": ConfigField(
                name="dry_run", field_type="bool", default=True,
                description="When true, orders are simulated in-memory and never sent to real exchange",
                category="environment", risk_level=RiskLevel.CRITICAL,
                is_safety_invariant=True, runtime_policy=RuntimePolicy.NEVER_RUNTIME_MODIFIABLE
            ),
            "live_trading_enabled": ConfigField(
                name="live_trading_enabled", field_type="bool", default=False,
                description="Master gate for real-capital live trading. Requires explicit multi-condition override",
                category="environment", risk_level=RiskLevel.CRITICAL,
                is_safety_invariant=True, runtime_policy=RuntimePolicy.NEVER_RUNTIME_MODIFIABLE
            ),
            "data_dir": ConfigField(
                name="data_dir", field_type="str", default="user_data/data",
                description="Base directory for historical market data and manifests",
                category="environment", risk_level=RiskLevel.LOW,
                runtime_policy=RuntimePolicy.RESTART_REQUIRED
            ),
            "db_url": ConfigField(
                name="db_url", field_type="str", default="sqlite:///user_data/cuanimus.sqlite",
                description="Database connection URL for state persistence and trade telemetry",
                category="environment", risk_level=RiskLevel.MEDIUM,
                runtime_policy=RuntimePolicy.NEVER_RUNTIME_MODIFIABLE
            ),
        }


@dataclass
class ExchangeConfig:
    provider: str = "binance"
    market_type: str = "futures"  # "futures", "spot"
    environment: str = "testnet"  # "testnet", "mainnet", "mock"
    quote_asset: str = "USDT"
    maker_fee_pct: float = 0.02
    taker_fee_pct: float = 0.05
    rate_limit_per_minute: int = 1200
    timeout_seconds: float = 10.0
    recv_window_ms: int = 5000

    @classmethod
    def get_field_specs(cls) -> Dict[str, ConfigField]:
        return {
            "provider": ConfigField(
                name="provider", field_type="str", default="binance",
                description="Exchange connector provider",
                choices=["binance", "bybit", "mock"],
                category="exchange", risk_level=RiskLevel.HIGH,
                runtime_policy=RuntimePolicy.NEVER_RUNTIME_MODIFIABLE
            ),
            "market_type": ConfigField(
                name="market_type", field_type="str", default="futures",
                description="Trading market category (USDT-M Perpetual Futures or Spot)",
                choices=["futures", "spot"],
                category="exchange", risk_level=RiskLevel.HIGH,
                runtime_policy=RuntimePolicy.NEVER_RUNTIME_MODIFIABLE
            ),
            "environment": ConfigField(
                name="environment", field_type="str", default="testnet",
                description="Exchange network environment (testnet vs mainnet)",
                choices=["testnet", "mainnet", "mock"],
                category="exchange", risk_level=RiskLevel.CRITICAL,
                runtime_policy=RuntimePolicy.NEVER_RUNTIME_MODIFIABLE
            ),
            "quote_asset": ConfigField(
                name="quote_asset", field_type="str", default="USDT",
                description="Base settlement asset denomination",
                category="exchange", risk_level=RiskLevel.LOW,
                runtime_policy=RuntimePolicy.RESTART_REQUIRED
            ),
            "maker_fee_pct": ConfigField(
                name="maker_fee_pct", field_type="float", default=0.02,
                description="Modeled maker fee percentage", unit="%",
                minimum=0.0, maximum=0.5, category="exchange", risk_level=RiskLevel.MEDIUM,
                runtime_policy=RuntimePolicy.RESTART_REQUIRED
            ),
            "taker_fee_pct": ConfigField(
                name="taker_fee_pct", field_type="float", default=0.05,
                description="Modeled taker fee percentage", unit="%",
                minimum=0.0, maximum=1.0, category="exchange", risk_level=RiskLevel.MEDIUM,
                runtime_policy=RuntimePolicy.RESTART_REQUIRED
            ),
            "rate_limit_per_minute": ConfigField(
                name="rate_limit_per_minute", field_type="int", default=1200,
                description="Max API request weight allowed per minute",
                minimum=60, maximum=6000, category="exchange", risk_level=RiskLevel.LOW,
                runtime_policy=RuntimePolicy.HOT_SAFE
            ),
            "timeout_seconds": ConfigField(
                name="timeout_seconds", field_type="float", default=10.0,
                description="HTTP / WebSocket request timeout in seconds", unit="s",
                minimum=1.0, maximum=60.0, category="exchange", risk_level=RiskLevel.LOW,
                runtime_policy=RuntimePolicy.HOT_SAFE
            ),
            "recv_window_ms": ConfigField(
                name="recv_window_ms", field_type="int", default=5000,
                description="Binance recvWindow timestamp drift tolerance", unit="ms",
                minimum=1000, maximum=60000, category="exchange", risk_level=RiskLevel.LOW,
                runtime_policy=RuntimePolicy.HOT_SAFE
            ),
        }


@dataclass
class MarketConfig:
    pairs: List[str] = field(default_factory=lambda: ["ADA/USDT:USDT", "ETH/USDT:USDT", "XRP/USDT:USDT"])
    base_timeframe: str = "15m"
    context_timeframe: str = "1h"
    macro_timeframe: str = "4h"

    @classmethod
    def get_field_specs(cls) -> Dict[str, ConfigField]:
        return {
            "pairs": ConfigField(
                name="pairs", field_type="list", default=["ADA/USDT:USDT", "ETH/USDT:USDT", "XRP/USDT:USDT"],
                description="Trading pair universe",
                category="market", risk_level=RiskLevel.HIGH,
                runtime_policy=RuntimePolicy.RESTART_REQUIRED
            ),
            "base_timeframe": ConfigField(
                name="base_timeframe", field_type="str", default="15m",
                description="Primary execution candle timeframe",
                choices=["1m", "5m", "15m", "1h", "4h", "1d"],
                category="market", risk_level=RiskLevel.HIGH,
                runtime_policy=RuntimePolicy.NEVER_RUNTIME_MODIFIABLE
            ),
            "context_timeframe": ConfigField(
                name="context_timeframe", field_type="str", default="1h",
                description="Secondary higher timeframe for trend alignment",
                choices=["15m", "1h", "4h", "1d"],
                category="market", risk_level=RiskLevel.MEDIUM,
                runtime_policy=RuntimePolicy.NEVER_RUNTIME_MODIFIABLE
            ),
            "macro_timeframe": ConfigField(
                name="macro_timeframe", field_type="str", default="4h",
                description="Macro regime filter timeframe",
                choices=["1h", "4h", "1d", "1w"],
                category="market", risk_level=RiskLevel.MEDIUM,
                runtime_policy=RuntimePolicy.NEVER_RUNTIME_MODIFIABLE
            ),
        }


@dataclass
class StrategyConfig:
    strategy_id: str = "v2c_hybrid"
    name: str = "Hybrid Pullback & Order Block"
    version: str = "2.0.0"
    long_enabled: bool = True
    short_enabled: bool = False
    parameters: Dict[str, Any] = field(default_factory=lambda: {
        "ema_fast": 20,
        "ema_slow": 50,
        "stoch_oversold": 30.0,
        "stoch_overbought": 70.0,
        "pullback_tolerance_pct": 0.8,
        "volume_multiplier": 1.1,
        "min_regime_adx": 20.0,
    })

    @classmethod
    def get_field_specs(cls) -> Dict[str, ConfigField]:
        return {
            "strategy_id": ConfigField(
                name="strategy_id", field_type="str", default="v2c_hybrid",
                description="Unique identifier of registered strategy plugin",
                category="strategy", risk_level=RiskLevel.HIGH,
                runtime_policy=RuntimePolicy.NEVER_RUNTIME_MODIFIABLE
            ),
            "name": ConfigField(
                name="name", field_type="str", default="Hybrid Pullback & Order Block",
                description="Human-readable strategy name",
                category="strategy", risk_level=RiskLevel.LOW,
                runtime_policy=RuntimePolicy.HOT_SAFE
            ),
            "version": ConfigField(
                name="version", field_type="str", default="2.0.0",
                description="Strategy semantic version",
                category="strategy", risk_level=RiskLevel.LOW,
                runtime_policy=RuntimePolicy.NEVER_RUNTIME_MODIFIABLE
            ),
            "long_enabled": ConfigField(
                name="long_enabled", field_type="bool", default=True,
                description="Allow opening LONG positions",
                category="strategy", risk_level=RiskLevel.MEDIUM,
                runtime_policy=RuntimePolicy.HOT_SAFE
            ),
            "short_enabled": ConfigField(
                name="short_enabled", field_type="bool", default=False,
                description="Allow opening SHORT positions",
                category="strategy", risk_level=RiskLevel.MEDIUM,
                runtime_policy=RuntimePolicy.HOT_SAFE
            ),
            "parameters": ConfigField(
                name="parameters", field_type="dict", default={},
                description="Strategy-specific indicator and threshold hyperparameters",
                category="strategy", risk_level=RiskLevel.MEDIUM,
                runtime_policy=RuntimePolicy.RESTART_REQUIRED
            ),
        }


@dataclass
class RiskConfig:
    profile_name: str = "balanced"
    risk_per_trade_pct: float = 1.0
    max_leverage: float = 5.0
    max_daily_loss_pct: float = 3.0
    max_drawdown_pct: float = 15.0
    max_pair_exposure_pct: float = 30.0
    max_total_exposure_pct: float = 80.0
    consecutive_loss_pair_threshold: int = 3
    consecutive_loss_pair_cooldown_hours: float = 4.0
    consecutive_loss_portfolio_threshold: int = 5
    consecutive_loss_portfolio_cooldown_hours: float = 12.0
    emergency_stop_enabled: bool = True  # SAFETY INVARIANT
    capital_preservation_lock: bool = True  # SAFETY INVARIANT
    drawdown_leverage_throttle_threshold_pct: float = 10.0
    drawdown_throttled_leverage: float = 2.0

    @classmethod
    def get_field_specs(cls) -> Dict[str, ConfigField]:
        return {
            "profile_name": ConfigField(
                name="profile_name", field_type="str", default="balanced",
                description="Pre-packaged risk profile template",
                choices=["conservative", "balanced", "aggressive", "custom"],
                category="risk", risk_level=RiskLevel.HIGH,
                runtime_policy=RuntimePolicy.RESTART_REQUIRED
            ),
            "risk_per_trade_pct": ConfigField(
                name="risk_per_trade_pct", field_type="float", default=1.0,
                description="Maximum risk equity percentage risked on a single trade", unit="%",
                minimum=0.1, maximum=5.0, category="risk", risk_level=RiskLevel.CRITICAL,
                runtime_policy=RuntimePolicy.RESTART_REQUIRED
            ),
            "max_leverage": ConfigField(
                name="max_leverage", field_type="float", default=5.0,
                description="Maximum allowable leverage multiplier", unit="x",
                minimum=1.0, maximum=10.0, category="risk", risk_level=RiskLevel.CRITICAL,
                is_safety_invariant=True, runtime_policy=RuntimePolicy.RESTART_REQUIRED
            ),
            "max_daily_loss_pct": ConfigField(
                name="max_daily_loss_pct", field_type="float", default=3.0,
                description="Maximum cumulative realized loss allowed in a 24h rolling period", unit="%",
                minimum=0.5, maximum=10.0, category="risk", risk_level=RiskLevel.CRITICAL,
                is_safety_invariant=True, runtime_policy=RuntimePolicy.HOT_SAFE
            ),
            "max_drawdown_pct": ConfigField(
                name="max_drawdown_pct", field_type="float", default=15.0,
                description="Circuit breaker threshold for peak-to-trough portfolio drawdown", unit="%",
                minimum=3.0, maximum=30.0, category="risk", risk_level=RiskLevel.CRITICAL,
                is_safety_invariant=True, runtime_policy=RuntimePolicy.HOT_SAFE
            ),
            "max_pair_exposure_pct": ConfigField(
                name="max_pair_exposure_pct", field_type="float", default=30.0,
                description="Maximum notional allocation permitted in a single asset pair", unit="%",
                minimum=5.0, maximum=50.0, category="risk", risk_level=RiskLevel.HIGH,
                runtime_policy=RuntimePolicy.HOT_SAFE
            ),
            "max_total_exposure_pct": ConfigField(
                name="max_total_exposure_pct", field_type="float", default=80.0,
                description="Maximum total portfolio exposure relative to equity", unit="%",
                minimum=10.0, maximum=100.0, category="risk", risk_level=RiskLevel.HIGH,
                runtime_policy=RuntimePolicy.HOT_SAFE
            ),
            "consecutive_loss_pair_threshold": ConfigField(
                name="consecutive_loss_pair_threshold", field_type="int", default=3,
                description="Consecutive losses on a single pair before triggering cooldown",
                minimum=1, maximum=10, category="risk", risk_level=RiskLevel.HIGH,
                runtime_policy=RuntimePolicy.HOT_SAFE
            ),
            "consecutive_loss_pair_cooldown_hours": ConfigField(
                name="consecutive_loss_pair_cooldown_hours", field_type="float", default=4.0,
                description="Duration of trading pause for a pair after consecutive losses", unit="h",
                minimum=0.5, maximum=48.0, category="risk", risk_level=RiskLevel.MEDIUM,
                runtime_policy=RuntimePolicy.HOT_SAFE
            ),
            "consecutive_loss_portfolio_threshold": ConfigField(
                name="consecutive_loss_portfolio_threshold", field_type="int", default=5,
                description="Consecutive portfolio losses before triggering global cooldown",
                minimum=2, maximum=15, category="risk", risk_level=RiskLevel.HIGH,
                runtime_policy=RuntimePolicy.HOT_SAFE
            ),
            "consecutive_loss_portfolio_cooldown_hours": ConfigField(
                name="consecutive_loss_portfolio_cooldown_hours", field_type="float", default=12.0,
                description="Duration of portfolio-wide trading suspension", unit="h",
                minimum=1.0, maximum=72.0, category="risk", risk_level=RiskLevel.HIGH,
                runtime_policy=RuntimePolicy.HOT_SAFE
            ),
            "emergency_stop_enabled": ConfigField(
                name="emergency_stop_enabled", field_type="bool", default=True,
                description="Enables manual operator kill switch and automatic catastrophic stop",
                category="risk", risk_level=RiskLevel.CRITICAL,
                is_safety_invariant=True, runtime_policy=RuntimePolicy.NEVER_RUNTIME_MODIFIABLE
            ),
            "capital_preservation_lock": ConfigField(
                name="capital_preservation_lock", field_type="bool", default=True,
                description="Locks out new positions if equity drops below preservation threshold",
                category="risk", risk_level=RiskLevel.CRITICAL,
                is_safety_invariant=True, runtime_policy=RuntimePolicy.NEVER_RUNTIME_MODIFIABLE
            ),
            "drawdown_leverage_throttle_threshold_pct": ConfigField(
                name="drawdown_leverage_throttle_threshold_pct", field_type="float", default=10.0,
                description="Drawdown percentage that triggers automatic leverage derisking", unit="%",
                minimum=2.0, maximum=25.0, category="risk", risk_level=RiskLevel.HIGH,
                runtime_policy=RuntimePolicy.HOT_SAFE
            ),
            "drawdown_throttled_leverage": ConfigField(
                name="drawdown_throttled_leverage", field_type="float", default=2.0,
                description="Maximum leverage forced during drawdown derisking phase", unit="x",
                minimum=1.0, maximum=3.0, category="risk", risk_level=RiskLevel.HIGH,
                runtime_policy=RuntimePolicy.HOT_SAFE
            ),
        }


@dataclass
class ExecutionConfig:
    profile_name: str = "conservative"
    entry_order_type: str = "limit"  # "limit", "market"
    exit_order_type: str = "market"
    limit_timeout_bars: int = 4
    retry_attempts: int = 3
    retry_backoff_ms: int = 500
    slippage_model: str = "CONSERVATIVE"  # "BASE", "CONSERVATIVE", "STRESS"
    slippage_pct: float = 0.10
    modeled_execution: bool = True
    pessimistic_sl_precedence: bool = True  # SAFETY INVARIANT

    @classmethod
    def get_field_specs(cls) -> Dict[str, ConfigField]:
        return {
            "profile_name": ConfigField(
                name="profile_name", field_type="str", default="conservative",
                description="Execution profile preset",
                choices=["conservative", "balanced", "aggressive", "custom"],
                category="execution", risk_level=RiskLevel.MEDIUM,
                runtime_policy=RuntimePolicy.RESTART_REQUIRED
            ),
            "entry_order_type": ConfigField(
                name="entry_order_type", field_type="str", default="limit",
                description="Order type for entering positions (limit saves taker fees)",
                choices=["limit", "market"],
                category="execution", risk_level=RiskLevel.MEDIUM,
                runtime_policy=RuntimePolicy.HOT_SAFE
            ),
            "exit_order_type": ConfigField(
                name="exit_order_type", field_type="str", default="market",
                description="Order type for stop-loss and safety exits",
                choices=["market", "limit"],
                category="execution", risk_level=RiskLevel.HIGH,
                runtime_policy=RuntimePolicy.HOT_SAFE
            ),
            "limit_timeout_bars": ConfigField(
                name="limit_timeout_bars", field_type="int", default=4,
                description="Number of bars before an unfilled limit entry order is cancelled", unit="bars",
                minimum=1, maximum=24, category="execution", risk_level=RiskLevel.MEDIUM,
                runtime_policy=RuntimePolicy.HOT_SAFE
            ),
            "retry_attempts": ConfigField(
                name="retry_attempts", field_type="int", default=3,
                description="Maximum order submission retries on network transport failure",
                minimum=0, maximum=10, category="execution", risk_level=RiskLevel.LOW,
                runtime_policy=RuntimePolicy.HOT_SAFE
            ),
            "retry_backoff_ms": ConfigField(
                name="retry_backoff_ms", field_type="int", default=500,
                description="Exponential backoff base delay between retries", unit="ms",
                minimum=100, maximum=5000, category="execution", risk_level=RiskLevel.LOW,
                runtime_policy=RuntimePolicy.HOT_SAFE
            ),
            "slippage_model": ConfigField(
                name="slippage_model", field_type="str", default="CONSERVATIVE",
                description="Adverse slippage simulation model tier",
                choices=["BASE", "CONSERVATIVE", "STRESS"],
                category="execution", risk_level=RiskLevel.MEDIUM,
                runtime_policy=RuntimePolicy.RESTART_REQUIRED
            ),
            "slippage_pct": ConfigField(
                name="slippage_pct", field_type="float", default=0.10,
                description="Modeled taker adverse slippage penalty", unit="%",
                minimum=0.0, maximum=2.0, category="execution", risk_level=RiskLevel.MEDIUM,
                runtime_policy=RuntimePolicy.RESTART_REQUIRED
            ),
            "modeled_execution": ConfigField(
                name="modeled_execution", field_type="bool", default=True,
                description="Applies realistic fill bounds and slippage instead of instant perfect fills",
                category="execution", risk_level=RiskLevel.MEDIUM,
                runtime_policy=RuntimePolicy.RESTART_REQUIRED
            ),
            "pessimistic_sl_precedence": ConfigField(
                name="pessimistic_sl_precedence", field_type="bool", default=True,
                description="Enforces Stop Loss precedence if both SL and TP price levels touch in same bar",
                category="execution", risk_level=RiskLevel.CRITICAL,
                is_safety_invariant=True, runtime_policy=RuntimePolicy.NEVER_RUNTIME_MODIFIABLE
            ),
        }


@dataclass
class AIConfig:
    enabled: bool = False
    provider: str = "gemini"  # "mock", "gemini"
    mode: str = "regime_context"  # "regime_context", "sidecar_advisor"
    model_name: str = "gemini-2.5-flash"
    cache_ttl_seconds: int = 900
    circuit_breaker_failures: int = 3
    circuit_breaker_cooldown_seconds: float = 60.0
    timeout_seconds: float = 5.0

    @classmethod
    def get_field_specs(cls) -> Dict[str, ConfigField]:
        return {
            "enabled": ConfigField(
                name="enabled", field_type="bool", default=False,
                description="Enable AI intelligence layer as an optional sidecar advisor",
                category="ai", risk_level=RiskLevel.MEDIUM,
                runtime_policy=RuntimePolicy.HOT_SAFE
            ),
            "provider": ConfigField(
                name="provider", field_type="str", default="gemini",
                description="AI intelligence provider plugin",
                choices=["gemini", "mock"],
                category="ai", risk_level=RiskLevel.LOW,
                runtime_policy=RuntimePolicy.RESTART_REQUIRED
            ),
            "mode": ConfigField(
                name="mode", field_type="str", default="regime_context",
                description="Operating mode for AI intelligence sidecar",
                choices=["regime_context", "sidecar_advisor"],
                category="ai", risk_level=RiskLevel.LOW,
                runtime_policy=RuntimePolicy.HOT_SAFE
            ),
            "model_name": ConfigField(
                name="model_name", field_type="str", default="gemini-2.5-flash",
                description="Underlying LLM model identifier",
                category="ai", risk_level=RiskLevel.LOW,
                runtime_policy=RuntimePolicy.HOT_SAFE
            ),
            "cache_ttl_seconds": ConfigField(
                name="cache_ttl_seconds", field_type="int", default=900,
                description="Cache validity duration for AI market regime intelligence", unit="s",
                minimum=60, maximum=3600, category="ai", risk_level=RiskLevel.LOW,
                runtime_policy=RuntimePolicy.HOT_SAFE
            ),
            "circuit_breaker_failures": ConfigField(
                name="circuit_breaker_failures", field_type="int", default=3,
                description="Consecutive provider failures before tripping circuit breaker",
                minimum=1, maximum=10, category="ai", risk_level=RiskLevel.MEDIUM,
                runtime_policy=RuntimePolicy.HOT_SAFE
            ),
            "circuit_breaker_cooldown_seconds": ConfigField(
                name="circuit_breaker_cooldown_seconds", field_type="float", default=60.0,
                description="Circuit breaker lockout period before attempting re-query", unit="s",
                minimum=10.0, maximum=600.0, category="ai", risk_level=RiskLevel.LOW,
                runtime_policy=RuntimePolicy.HOT_SAFE
            ),
            "timeout_seconds": ConfigField(
                name="timeout_seconds", field_type="float", default=5.0,
                description="Strict network timeout for AI provider responses", unit="s",
                minimum=1.0, maximum=30.0, category="ai", risk_level=RiskLevel.LOW,
                runtime_policy=RuntimePolicy.HOT_SAFE
            ),
        }


@dataclass
class BacktestConfig:
    initial_capital: float = 65.0
    start_date: str = "2026-06-25T00:00:00Z"
    end_date: str = "2026-10-02T23:59:59Z"
    information_boundary: str = "STRICT_CAUSAL_CLOSED_BARS"
    funding_modeled: bool = True

    @classmethod
    def get_field_specs(cls) -> Dict[str, ConfigField]:
        return {
            "initial_capital": ConfigField(
                name="initial_capital", field_type="float", default=65.0,
                description="Starting balance in USDT for simulation", unit="USDT",
                minimum=10.0, maximum=1000000.0, category="backtest", risk_level=RiskLevel.LOW,
                runtime_policy=RuntimePolicy.RESTART_REQUIRED
            ),
            "start_date": ConfigField(
                name="start_date", field_type="str", default="2026-06-25T00:00:00Z",
                description="Historical replay start timestamp (ISO8601 UTC)",
                category="backtest", risk_level=RiskLevel.LOW,
                runtime_policy=RuntimePolicy.RESTART_REQUIRED
            ),
            "end_date": ConfigField(
                name="end_date", field_type="str", default="2026-10-02T23:59:59Z",
                description="Historical replay end timestamp (ISO8601 UTC)",
                category="backtest", risk_level=RiskLevel.LOW,
                runtime_policy=RuntimePolicy.RESTART_REQUIRED
            ),
            "information_boundary": ConfigField(
                name="information_boundary", field_type="str", default="STRICT_CAUSAL_CLOSED_BARS",
                description="Causal boundary enforcement mode",
                choices=["STRICT_CAUSAL_CLOSED_BARS"],
                category="backtest", risk_level=RiskLevel.CRITICAL,
                is_safety_invariant=True, runtime_policy=RuntimePolicy.NEVER_RUNTIME_MODIFIABLE
            ),
            "funding_modeled": ConfigField(
                name="funding_modeled", field_type="bool", default=True,
                description="Simulate 8h perpetual funding rate cash transfers",
                category="backtest", risk_level=RiskLevel.MEDIUM,
                runtime_policy=RuntimePolicy.RESTART_REQUIRED
            ),
        }


@dataclass
class NotificationConfig:
    telegram_enabled: bool = False
    discord_enabled: bool = False
    alert_on_entry: bool = True
    alert_on_exit: bool = True
    alert_on_risk_veto: bool = True
    alert_on_circuit_breaker: bool = True
    alert_on_emergency_stop: bool = True

    @classmethod
    def get_field_specs(cls) -> Dict[str, ConfigField]:
        return {
            "telegram_enabled": ConfigField(
                name="telegram_enabled", field_type="bool", default=False,
                description="Dispatch alerts to Telegram bot",
                category="notification", risk_level=RiskLevel.LOW,
                runtime_policy=RuntimePolicy.HOT_SAFE
            ),
            "discord_enabled": ConfigField(
                name="discord_enabled", field_type="bool", default=False,
                description="Dispatch alerts to Discord webhook",
                category="notification", risk_level=RiskLevel.LOW,
                runtime_policy=RuntimePolicy.HOT_SAFE
            ),
            "alert_on_entry": ConfigField(
                name="alert_on_entry", field_type="bool", default=True,
                description="Notify on order fill entry",
                category="notification", risk_level=RiskLevel.LOW,
                runtime_policy=RuntimePolicy.HOT_SAFE
            ),
            "alert_on_exit": ConfigField(
                name="alert_on_exit", field_type="bool", default=True,
                description="Notify on position exit and realized PnL",
                category="notification", risk_level=RiskLevel.LOW,
                runtime_policy=RuntimePolicy.HOT_SAFE
            ),
            "alert_on_risk_veto": ConfigField(
                name="alert_on_risk_veto", field_type="bool", default=True,
                description="Notify when Risk Engine vetos a trade intent",
                category="notification", risk_level=RiskLevel.LOW,
                runtime_policy=RuntimePolicy.HOT_SAFE
            ),
            "alert_on_circuit_breaker": ConfigField(
                name="alert_on_circuit_breaker", field_type="bool", default=True,
                description="Notify when AI or Risk circuit breaker trips",
                category="notification", risk_level=RiskLevel.LOW,
                runtime_policy=RuntimePolicy.HOT_SAFE
            ),
            "alert_on_emergency_stop": ConfigField(
                name="alert_on_emergency_stop", field_type="bool", default=True,
                description="High-priority alert when emergency stop is triggered",
                category="notification", risk_level=RiskLevel.LOW,
                runtime_policy=RuntimePolicy.HOT_SAFE
            ),
        }


@dataclass
class ObservabilityConfig:
    log_level: str = "INFO"
    correlation_id_enabled: bool = True
    structured_json_logging: bool = True
    telemetry_export_interval_seconds: int = 60

    @classmethod
    def get_field_specs(cls) -> Dict[str, ConfigField]:
        return {
            "log_level": ConfigField(
                name="log_level", field_type="str", default="INFO",
                description="Engine logging verbosity",
                choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                category="observability", risk_level=RiskLevel.LOW,
                runtime_policy=RuntimePolicy.HOT_SAFE
            ),
            "correlation_id_enabled": ConfigField(
                name="correlation_id_enabled", field_type="bool", default=True,
                description="Attach unique UUIDv4 correlation ID across intent -> order -> fill trace",
                category="observability", risk_level=RiskLevel.LOW,
                runtime_policy=RuntimePolicy.HOT_SAFE
            ),
            "structured_json_logging": ConfigField(
                name="structured_json_logging", field_type="bool", default=True,
                description="Output logs in machine-parseable JSON format",
                category="observability", risk_level=RiskLevel.LOW,
                runtime_policy=RuntimePolicy.HOT_SAFE
            ),
            "telemetry_export_interval_seconds": ConfigField(
                name="telemetry_export_interval_seconds", field_type="int", default=60,
                description="Interval in seconds for writing runtime health telemetry", unit="s",
                minimum=5, maximum=3600, category="observability", risk_level=RiskLevel.LOW,
                runtime_policy=RuntimePolicy.HOT_SAFE
            ),
        }


@dataclass
class CuanimusConfig:
    """Root configuration model holding all platform subsystems."""
    environment: EnvironmentConfig = field(default_factory=EnvironmentConfig)
    exchange: ExchangeConfig = field(default_factory=ExchangeConfig)
    market: MarketConfig = field(default_factory=MarketConfig)
    strategy: StrategyConfig = field(default_factory=StrategyConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)
    ai: AIConfig = field(default_factory=AIConfig)
    backtest: BacktestConfig = field(default_factory=BacktestConfig)
    notification: NotificationConfig = field(default_factory=NotificationConfig)
    observability: ObservabilityConfig = field(default_factory=ObservabilityConfig)

    def to_dict(self) -> Dict[str, Any]:
        """Serializes configuration into a pure python dictionary."""
        return asdict(self)

    @classmethod
    def get_all_field_specs(cls) -> Dict[str, ConfigField]:
        """Collects flattened field specifications for all configuration parameters."""
        specs: Dict[str, ConfigField] = {}
        section_classes = {
            "environment": EnvironmentConfig,
            "exchange": ExchangeConfig,
            "market": MarketConfig,
            "strategy": StrategyConfig,
            "risk": RiskConfig,
            "execution": ExecutionConfig,
            "ai": AIConfig,
            "backtest": BacktestConfig,
            "notification": NotificationConfig,
            "observability": ObservabilityConfig,
        }
        for sec_name, sec_cls in section_classes.items():
            for param_name, field_spec in sec_cls.get_field_specs().items():
                specs[f"{sec_name}.{param_name}"] = field_spec
        return specs
