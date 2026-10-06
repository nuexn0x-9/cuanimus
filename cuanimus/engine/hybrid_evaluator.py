"""
CUANIMUS Mode C — Hybrid Autotrade Evaluator.
Coordinates Strategy Filter + AI Agent Decision confirmation.
If the strategy produces no candidate (HOLD), the AI Agent is not called,
saving API costs, eliminating noise, and ensuring high selectivity.
"""
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone

from cuanimus.common.types import TradeIntent, SignalDirection
from cuanimus.engine.models import TradingProfile, AgentDecisionResult
from cuanimus.engine.strategy_evaluator import StrategyEvaluator
from cuanimus.engine.agent_evaluator import AgentDecisionEngine

logger = logging.getLogger(__name__)


class HybridEvaluator:
    """Evaluates Mode C (Strategy Filter -> AI Agent Confirmation)."""

    def __init__(self):
        self.strategy_evaluator = StrategyEvaluator()
        self.agent_engine = AgentDecisionEngine()

    def evaluate(
        self,
        profile: TradingProfile,
        closed_candles: List[Dict[str, Any]],
        current_market_price: float,
        open_positions: List[Dict[str, Any]],
    ) -> Tuple[TradeIntent, Optional[TradeIntent], Optional[AgentDecisionResult]]:
        """
        Executes Mode C evaluation:
        1. Evaluate Strategy Template as filter.
        2. If Strategy produces HOLD -> Exit immediately, AI is NOT called.
        3. If Strategy produces candidate -> Call AI Agent for confirmation.
        Returns: (final_intent, strategy_candidate_intent, ai_decision_result)
        """
        now = datetime.now(timezone.utc)
        symbol = profile.symbol

        # Step 1: Strategy Template Filter
        strat_intent = self.strategy_evaluator.evaluate(profile, closed_candles, current_market_price)

        if strat_intent.direction == SignalDirection.HOLD:
            # AI is not called to save cost and noise
            return strat_intent, strat_intent, None

        # Step 2: Strategy produced candidate setup -> Invoke AI Agent for confirmation
        context = self.agent_engine.build_market_context(profile, closed_candles, current_market_price, open_positions)
        context["strategy_candidate"] = {
            "strategy_id": strat_intent.strategy_id,
            "direction": strat_intent.direction.value,
            "confidence": strat_intent.confidence,
            "suggested_sl": strat_intent.suggested_stop_loss,
            "suggested_tp": strat_intent.suggested_take_profit,
        }

        agent_res = self.agent_engine.evaluate_agent_decision(profile, context)

        # Check alignment: AI confirms if direction matches and confidence >= 0.60
        is_confirmed = False
        if strat_intent.direction == SignalDirection.LONG:
            is_confirmed = (agent_res.decision in ("LONG", "APPROVE")) and (agent_res.confidence >= 0.60)
        elif strat_intent.direction == SignalDirection.SHORT:
            is_confirmed = (agent_res.decision in ("SHORT", "APPROVE")) and (agent_res.confidence >= 0.60)

        if is_confirmed:
            # Confirmed by both Strategy Filter and AI Agent
            combined_conf = min(99.0, (strat_intent.confidence + (agent_res.confidence * 100.0)) / 2.0)
            final_intent = TradeIntent(
                intent_id=f"INT_HYBRID_{profile.profile_id}_{now.timestamp()}",
                symbol=symbol,
                direction=strat_intent.direction,
                timestamp=now,
                strategy_id=f"hybrid_{profile.strategy_id}_{profile.agent_id}",
                entry_price_target=current_market_price,
                suggested_stop_loss=strat_intent.suggested_stop_loss,
                suggested_take_profit=strat_intent.suggested_take_profit,
                confidence=combined_conf,
            )
            return final_intent, strat_intent, agent_res
        else:
            # AI Agent vetoed the strategy setup
            veto_reason = f"AI Agent rejected setup: {agent_res.entry_reason} (AI confidence: {agent_res.confidence:.2f})"
            final_intent = TradeIntent(
                intent_id=f"INT_HYBRID_VETO_{profile.profile_id}_{now.timestamp()}",
                symbol=symbol,
                direction=SignalDirection.HOLD,
                timestamp=now,
                strategy_id=f"hybrid_{profile.strategy_id}_{profile.agent_id}",
                entry_price_target=current_market_price,
                confidence=0.0,
            )
            return final_intent, strat_intent, agent_res
