"""
CUANIMUS Agent Trading Policy & Execution Boundary Enforcement.
Provides autonomous trading boundary checks, leverage ceilings, pair whitelisting,
rate limits, and mandatory risk invariance before any intent touches the Risk Engine.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any
import collections


class PolicyViolationError(ValueError):
    """Raised when an agent attempts an action that breaches trading policy."""
    pass


@dataclass
class PolicyEvaluationResult:
    """Result of agent trading policy evaluation."""
    is_approved: bool
    reason: Optional[str] = None
    policy_name: str = "default_policy"
    evaluated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_approved": self.is_approved,
            "reason": self.reason,
            "policy_name": self.policy_name,
            "evaluated_at": self.evaluated_at.isoformat(),
        }


@dataclass
class AgentTradingPolicy:
    """
    Independent policy governing autonomous trade actions by an AI agent.
    Acts as the first-line gateway before CuaniMus core RiskEngine.
    """
    policy_name: str = "standard_paper_policy"
    allowed_environments: List[str] = field(default_factory=lambda: ["paper", "testnet"])
    allowed_symbols: List[str] = field(default_factory=lambda: [
        "BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT", "BNB/USDT:USDT", "XRP/USDT:USDT"
    ])
    allowed_strategies: List[str] = field(default_factory=lambda: [
        "v2_pullback", "baseline_v0", "conservative_ema", "breakout_v1", "bollinger_mean_reversion"
    ])
    max_risk_per_trade_pct: float = 2.0
    max_leverage: float = 5.0
    max_daily_loss_pct: float = 3.0
    max_orders_per_minute: int = 10
    require_two_step_intent: bool = True
    require_mandatory_stop_loss: bool = True

    # Platform immutable constraints
    PLATFORM_MAX_LEVERAGE_CEILING: float = 10.0
    PLATFORM_MAX_RISK_CEILING_PCT: float = 5.0

    def __post_init__(self):
        # Enforce safety invariant ceilings immediately
        if self.max_leverage > self.PLATFORM_MAX_LEVERAGE_CEILING:
            raise PolicyViolationError(
                f"Policy max_leverage ({self.max_leverage}x) exceeds institutional platform ceiling ({self.PLATFORM_MAX_LEVERAGE_CEILING}x)"
            )
        if self.max_risk_per_trade_pct > self.PLATFORM_MAX_RISK_CEILING_PCT:
            raise PolicyViolationError(
                f"Policy max_risk_per_trade_pct ({self.max_risk_per_trade_pct}%) exceeds platform ceiling ({self.PLATFORM_MAX_RISK_CEILING_PCT}%)"
            )
        # Live trading is strictly rejected
        for env in self.allowed_environments:
            if env.lower() == "live":
                raise PolicyViolationError("CRITICAL SAFETY INVARIANT: Live real-capital trading cannot be enabled in agent policy!")
        if not self.require_mandatory_stop_loss:
            raise PolicyViolationError("CRITICAL SAFETY INVARIANT: Mandatory stop loss cannot be disabled in agent policy!")

        self._recent_order_timestamps: collections.deque = collections.deque()

    def evaluate_intent(
        self,
        symbol: str,
        strategy_id: str,
        leverage: float,
        stop_loss: Optional[float],
        environment: str = "paper",
        stake_usdt: Optional[float] = None,
        account_balance: Optional[float] = None,
    ) -> PolicyEvaluationResult:
        """
        Evaluates trade parameters against policy boundaries.
        Returns PolicyEvaluationResult.
        """
        now = datetime.now(timezone.utc)

        # 1. Environment check
        if environment.lower() not in [env.lower() for env in self.allowed_environments]:
            return PolicyEvaluationResult(
                is_approved=False,
                reason=f"Environment '{environment}' is not permitted by policy. Allowed: {self.allowed_environments}",
                policy_name=self.policy_name,
            )
        if environment.lower() == "live" and "live" not in [env.lower() for env in self.allowed_environments]:
            return PolicyEvaluationResult(
                is_approved=False,
                reason="FATAL: Real capital live trading is not permitted by current agent policy.",
                policy_name=self.policy_name,
            )

        # 2. Symbol whitelisting
        if symbol not in self.allowed_symbols:
            return PolicyEvaluationResult(
                is_approved=False,
                reason=f"Symbol '{symbol}' is not in policy whitelist: {self.allowed_symbols}",
                policy_name=self.policy_name,
            )

        # 3. Strategy whitelisting
        if strategy_id not in self.allowed_strategies:
            return PolicyEvaluationResult(
                is_approved=False,
                reason=f"Strategy '{strategy_id}' is not in policy whitelist: {self.allowed_strategies}",
                policy_name=self.policy_name,
            )

        # 4. Leverage limit
        if leverage > self.max_leverage:
            return PolicyEvaluationResult(
                is_approved=False,
                reason=f"Requested leverage {leverage}x exceeds policy limit of {self.max_leverage}x",
                policy_name=self.policy_name,
            )

        # 5. Mandatory stop loss
        if self.require_mandatory_stop_loss and (stop_loss is None or stop_loss <= 0):
            return PolicyEvaluationResult(
                is_approved=False,
                reason="Policy requires mandatory positive stop loss level for all autonomous trade intents.",
                policy_name=self.policy_name,
            )

        # 6. Sizing / balance check if provided
        if stake_usdt is not None and account_balance is not None and account_balance > 0:
            stake_pct = (stake_usdt / account_balance) * 100.0
            # Sizing percentage ceiling
            if stake_pct > 50.0:  # Hard cap single stake to 50% equity
                return PolicyEvaluationResult(
                    is_approved=False,
                    reason=f"Stake {stake_usdt} USDT ({stake_pct:.1f}% balance) exceeds single trade allocation policy ceiling (50%)",
                    policy_name=self.policy_name,
                )

        # 7. Rate limiting (sliding window of 60 seconds)
        cutoff = now - timedelta(seconds=60)
        while self._recent_order_timestamps and self._recent_order_timestamps[0] < cutoff:
            self._recent_order_timestamps.popleft()

        if len(self._recent_order_timestamps) >= self.max_orders_per_minute:
            return PolicyEvaluationResult(
                is_approved=False,
                reason=f"Rate limit exceeded: {len(self._recent_order_timestamps)} orders submitted in the last 60 seconds (max {self.max_orders_per_minute}/min)",
                policy_name=self.policy_name,
            )

        return PolicyEvaluationResult(
            is_approved=True,
            reason=None,
            policy_name=self.policy_name,
        )

    def record_order_submission(self) -> None:
        """Records an approved order execution into rate limiting window."""
        self._recent_order_timestamps.append(datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "policy_name": self.policy_name,
            "allowed_environments": self.allowed_environments,
            "allowed_symbols": self.allowed_symbols,
            "allowed_strategies": self.allowed_strategies,
            "max_risk_per_trade_pct": self.max_risk_per_trade_pct,
            "max_leverage": self.max_leverage,
            "max_daily_loss_pct": self.max_daily_loss_pct,
            "max_orders_per_minute": self.max_orders_per_minute,
            "require_two_step_intent": self.require_two_step_intent,
            "require_mandatory_stop_loss": self.require_mandatory_stop_loss,
            "platform_max_leverage_ceiling": self.PLATFORM_MAX_LEVERAGE_CEILING,
            "platform_max_risk_ceiling_pct": self.PLATFORM_MAX_RISK_CEILING_PCT,
        }
