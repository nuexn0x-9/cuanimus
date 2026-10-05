"""
CUANIMUS Common Types & Domain Entities.
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional, List


class SignalDirection(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    HOLD = "HOLD"
    EXIT_LONG = "EXIT_LONG"
    EXIT_SHORT = "EXIT_SHORT"


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    LIMIT = "limit"
    MARKET = "market"
    STOP_MARKET = "stop_market"
    TAKE_PROFIT_MARKET = "take_profit_market"


class OrderState(str, Enum):
    CREATED = "CREATED"
    SUBMITTED = "SUBMITTED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLING = "CANCELLING"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    FAILED = "FAILED"


class MarketRegimeType(str, Enum):
    TRENDING_BULL = "TRENDING_BULL"
    TRENDING_BEAR = "TRENDING_BEAR"
    RANGING = "RANGING"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    LOW_VOLATILITY = "LOW_VOLATILITY"
    UNCERTAIN = "UNCERTAIN"


@dataclass(frozen=True)
class TradeIntent:
    intent_id: str
    symbol: str
    direction: SignalDirection
    timestamp: datetime
    strategy_id: str
    entry_price_target: float
    features_snapshot: Dict[str, float] = field(default_factory=dict)
    suggested_stop_loss: Optional[float] = None
    suggested_take_profit: Optional[float] = None
    confidence: float = 1.0


@dataclass(frozen=True)
class RiskEvaluation:
    is_approved: bool
    veto_reason: Optional[str]
    approved_stake: float
    approved_contracts: float
    approved_leverage: float
    stop_loss_price: float
    take_profit_price: Optional[float]
    max_loss_usdt: float
    sl_distance_pct: float
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class OrderRequest:
    client_order_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    amount: float
    price: float
    stop_loss: float
    leverage: float
    timeout_seconds: int = 600


@dataclass
class Order:
    client_order_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    amount: float
    price: float
    state: OrderState = OrderState.CREATED
    exchange_order_id: Optional[str] = None
    filled: float = 0.0
    remaining: float = 0.0
    average_fill_price: Optional[float] = None
    fee_cost: float = 0.0
    cancel_reason: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self):
        if self.remaining == 0.0 and self.amount > 0.0:
            self.remaining = self.amount


@dataclass
class Position:
    position_id: str
    symbol: str
    side: SignalDirection
    size: float
    entry_price: float
    current_stop_loss: float
    leverage: float
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    accumulated_fees: float = 0.0
    accumulated_funding: float = 0.0
    opened_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class PortfolioState:
    equity: float
    available_balance: float
    peak_equity: float
    drawdown_pct: float
    daily_realized_loss: float
    consecutive_losses: int
    pair_consecutive_losses: Dict[str, int] = field(default_factory=dict)
    active_exposures: Dict[str, float] = field(default_factory=dict)
    total_exposure_notional: float = 0.0


@dataclass(frozen=True)
class RegimeContext:
    regime: MarketRegimeType
    trend_strength_adx: float
    volatility_atr: float
    volatility_percentile: float
    htf_bias: str
    confidence: float
    ai_bias: Optional[str] = None
    ai_confidence: Optional[float] = None
    ai_valid_until: Optional[datetime] = None

