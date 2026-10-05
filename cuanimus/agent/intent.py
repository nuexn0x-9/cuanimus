"""
CUANIMUS Agent Trade Intent Subsystem.
Implements the mandatory two-step intent preparation & execution pipeline:
  create_intent -> validate_intent -> execute_intent
Guarantees idempotency, strict TTL expiration, policy vetting, and Risk Engine veto authority.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Dict, Any, Optional, List
import uuid

from cuanimus.common.types import (
    TradeIntent,
    RiskEvaluation,
    PortfolioState,
    SignalDirection,
    OrderSide,
    OrderType,
)
from cuanimus.agent.policy import AgentTradingPolicy, PolicyEvaluationResult
from cuanimus.risk.engine import RiskEngine
from cuanimus.execution.paper_safety import PaperExecutionSafetyGuard


class IntentStatus(str, Enum):
    CREATED = "CREATED"
    VALIDATED = "VALIDATED"
    EXECUTED = "EXECUTED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


@dataclass
class IntentValidationResult:
    """Consolidated validation outcome from Policy and RiskEngine."""
    intent_id: str
    is_valid: bool
    policy_passed: bool
    risk_passed: bool
    rejection_reasons: List[str] = field(default_factory=list)
    approved_stake: float = 0.0
    approved_contracts: float = 0.0
    approved_leverage: float = 1.0
    stop_loss_price: float = 0.0
    take_profit_price: Optional[float] = None
    max_loss_usdt: float = 0.0
    validated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent_id": self.intent_id,
            "is_valid": self.is_valid,
            "policy_passed": self.policy_passed,
            "risk_passed": self.risk_passed,
            "rejection_reasons": self.rejection_reasons,
            "approved_stake": self.approved_stake,
            "approved_contracts": self.approved_contracts,
            "approved_leverage": self.approved_leverage,
            "stop_loss_price": self.stop_loss_price,
            "take_profit_price": self.take_profit_price,
            "max_loss_usdt": self.max_loss_usdt,
            "validated_at": self.validated_at.isoformat(),
        }


@dataclass
class AgentTradeIntent:
    """Representation of an autonomous trade proposal prior to submission."""
    intent_id: str
    idempotency_key: str
    agent_id: str
    symbol: str
    direction: SignalDirection
    entry_price_target: float
    stop_loss: float
    take_profit: Optional[float]
    leverage: float
    stake_usdt: float
    strategy_id: str
    reasoning: str
    status: IntentStatus = IntentStatus.CREATED
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc) + timedelta(seconds=120))
    validation_result: Optional[IntentValidationResult] = None
    execution_result: Optional[Dict[str, Any]] = None

    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) > self.expires_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent_id": self.intent_id,
            "idempotency_key": self.idempotency_key,
            "agent_id": self.agent_id,
            "symbol": self.symbol,
            "direction": self.direction.value,
            "entry_price_target": self.entry_price_target,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "leverage": self.leverage,
            "stake_usdt": self.stake_usdt,
            "strategy_id": self.strategy_id,
            "reasoning": self.reasoning,
            "status": self.status.value,
            "is_expired": self.is_expired(),
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "validation_result": self.validation_result.to_dict() if self.validation_result else None,
            "execution_result": self.execution_result,
        }


class IntentPipeline:
    """
    Coordinates Intent creation, validation against Policy and RiskEngine,
    and safe paper execution with full idempotency guarantee.
    """
    def __init__(
        self,
        policy: Optional[AgentTradingPolicy] = None,
        risk_engine: Optional[RiskEngine] = None,
        safety_guard: Optional[PaperExecutionSafetyGuard] = None,
    ):
        self.policy = policy or AgentTradingPolicy()
        self.risk_engine = risk_engine or RiskEngine()
        self.safety_guard = safety_guard or PaperExecutionSafetyGuard(dry_run=True)

        self._intents_by_id: Dict[str, AgentTradeIntent] = {}
        self._intents_by_idempotency: Dict[str, AgentTradeIntent] = {}

    def create_intent(
        self,
        agent_id: str,
        idempotency_key: str,
        symbol: str,
        direction: str,
        entry_price: float,
        stop_loss: float,
        take_profit: Optional[float] = None,
        leverage: float = 3.0,
        stake_usdt: float = 100.0,
        strategy_id: str = "v2_pullback",
        reasoning: str = "Agent autonomous signal",
        ttl_seconds: int = 120,
    ) -> AgentTradeIntent:
        """Step 1: Create trade intent with unique idempotency key."""
        # Check idempotency first
        if idempotency_key in self._intents_by_idempotency:
            return self._intents_by_idempotency[idempotency_key]

        intent_id = f"int_{uuid.uuid4().hex[:10]}"
        now = datetime.now(timezone.utc)
        sig_dir = SignalDirection(direction.upper())

        intent = AgentTradeIntent(
            intent_id=intent_id,
            idempotency_key=idempotency_key,
            agent_id=agent_id,
            symbol=symbol,
            direction=sig_dir,
            entry_price_target=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            leverage=leverage,
            stake_usdt=stake_usdt,
            strategy_id=strategy_id,
            reasoning=reasoning,
            created_at=now,
            expires_at=now + timedelta(seconds=ttl_seconds),
        )

        self._intents_by_id[intent_id] = intent
        self._intents_by_idempotency[idempotency_key] = intent
        return intent

    def validate_intent(
        self,
        intent_id: str,
        portfolio_state: Optional[PortfolioState] = None,
        atr_value: float = 100.0,
        environment: str = "paper",
    ) -> IntentValidationResult:
        """Step 2: Validate intent against Policy and RiskEngine."""
        intent = self._intents_by_id.get(intent_id)
        if not intent:
            raise KeyError(f"Trade intent '{intent_id}' not found")

        rejection_reasons: List[str] = []

        if intent.is_expired():
            intent.status = IntentStatus.EXPIRED
            rejection_reasons.append(f"Intent expired at {intent.expires_at.isoformat()}")
            result = IntentValidationResult(
                intent_id=intent_id,
                is_valid=False,
                policy_passed=False,
                risk_passed=False,
                rejection_reasons=rejection_reasons,
            )
            intent.validation_result = result
            return result

        # 1. Evaluate Agent Trading Policy
        portfolio = portfolio_state or PortfolioState(
            equity=10000.0,
            available_balance=10000.0,
            peak_equity=10000.0,
            drawdown_pct=0.0,
            daily_realized_loss=0.0,
            consecutive_losses=0,
        )

        pol_res = self.policy.evaluate_intent(
            symbol=intent.symbol,
            strategy_id=intent.strategy_id,
            leverage=intent.leverage,
            stop_loss=intent.stop_loss,
            environment=environment,
            stake_usdt=intent.stake_usdt,
            account_balance=portfolio.equity,
        )

        if not pol_res.is_approved:
            rejection_reasons.append(f"POLICY_VETO: {pol_res.reason}")

        # 2. Evaluate CUANIMUS Risk Engine
        core_intent = TradeIntent(
            intent_id=intent.intent_id,
            symbol=intent.symbol,
            direction=intent.direction,
            timestamp=intent.created_at,
            strategy_id=intent.strategy_id,
            entry_price_target=intent.entry_price_target,
            suggested_stop_loss=intent.stop_loss,
            suggested_take_profit=intent.take_profit,
        )

        risk_eval = self.risk_engine.evaluate_intent(
            intent=core_intent,
            portfolio=portfolio,
            atr_value=atr_value,
        )

        if not risk_eval.is_approved:
            rejection_reasons.append(f"RISK_VETO: {risk_eval.veto_reason}")

        is_valid = pol_res.is_approved and risk_eval.is_approved
        if is_valid:
            intent.status = IntentStatus.VALIDATED
        else:
            intent.status = IntentStatus.REJECTED

        val_result = IntentValidationResult(
            intent_id=intent_id,
            is_valid=is_valid,
            policy_passed=pol_res.is_approved,
            risk_passed=risk_eval.is_approved,
            rejection_reasons=rejection_reasons,
            approved_stake=risk_eval.approved_stake if is_valid else 0.0,
            approved_contracts=risk_eval.approved_contracts if is_valid else 0.0,
            approved_leverage=risk_eval.approved_leverage if is_valid else 1.0,
            stop_loss_price=risk_eval.stop_loss_price if is_valid else 0.0,
            take_profit_price=risk_eval.take_profit_price if is_valid else None,
            max_loss_usdt=risk_eval.max_loss_usdt if is_valid else 0.0,
        )

        intent.validation_result = val_result
        return val_result

    def execute_intent(
        self,
        intent_id: str,
        idempotency_key: str,
    ) -> Dict[str, Any]:
        """Step 3: Execute validated intent safely under PaperExecutionSafetyGuard."""
        intent = self._intents_by_id.get(intent_id)
        if not intent:
            raise KeyError(f"Trade intent '{intent_id}' not found")

        # Idempotency verification
        if intent.idempotency_key != idempotency_key:
            raise ValueError(f"Idempotency key mismatch: expected '{intent.idempotency_key}', got '{idempotency_key}'")

        if intent.status == IntentStatus.EXECUTED and intent.execution_result:
            # Return cached execution record
            return intent.execution_result

        if intent.is_expired():
            intent.status = IntentStatus.EXPIRED
            raise TimeoutError(f"Trade intent {intent_id} has expired and cannot be executed.")

        if intent.status != IntentStatus.VALIDATED or not intent.validation_result or not intent.validation_result.is_valid:
            raise ValueError(f"Cannot execute unvalidated or rejected intent. Status: {intent.status.value}")

        # Execute via Safety Guard
        side = OrderSide.BUY.value if intent.direction == SignalDirection.LONG else OrderSide.SELL.value
        exec_record = self.safety_guard.execute_paper_order(
            symbol=intent.symbol,
            side=side,
            amount=intent.validation_result.approved_contracts or 0.1,
            price=intent.entry_price_target,
            order_type="limit",
        )

        # Record policy rate limit
        self.policy.record_order_submission()

        intent.status = IntentStatus.EXECUTED
        intent.execution_result = {
            "intent_id": intent.intent_id,
            "status": "FILLED_SIMULATED",
            "order": exec_record,
            "approved_stake": intent.validation_result.approved_stake,
            "approved_leverage": intent.validation_result.approved_leverage,
            "stop_loss_price": intent.validation_result.stop_loss_price,
            "take_profit_price": intent.validation_result.take_profit_price,
            "executed_at": datetime.now(timezone.utc).isoformat(),
        }

        return intent.execution_result

    def get_intent(self, intent_id: str) -> Optional[AgentTradeIntent]:
        return self._intents_by_id.get(intent_id)
