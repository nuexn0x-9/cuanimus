"""
CUANIMUS Independent Risk Engine.
"""
import logging
from typing import Optional, Dict
from datetime import datetime, timedelta

from cuanimus.common.types import (
    TradeIntent,
    RiskEvaluation,
    PortfolioState,
    SignalDirection,
)
from cuanimus.risk.sizing import calculate_position_size
from cuanimus.risk.stop_loss import compute_stop_loss, compute_take_profit, StopLossModel

logger = logging.getLogger(__name__)

class RiskEngine:
    def __init__(
        self,
        base_risk_pct: float = 1.5,
        max_leverage: float = 5.0,
        max_daily_loss_pct: float = 3.0,
        max_drawdown_pct: float = 15.0,
        max_pair_exposure_pct: float = 30.0,
        max_total_exposure_pct: float = 80.0,
        consecutive_loss_pair_threshold: int = 3,
        consecutive_loss_pair_cooldown_hours: float = 4.0,
        consecutive_loss_portfolio_threshold: int = 5,
        consecutive_loss_portfolio_cooldown_hours: float = 12.0,
    ):
        self.base_risk_pct = base_risk_pct
        self.max_leverage = max_leverage
        self.max_daily_loss_pct = max_daily_loss_pct
        self.max_drawdown_pct = max_drawdown_pct
        self.max_pair_exposure_pct = max_pair_exposure_pct
        self.max_total_exposure_pct = max_total_exposure_pct
        self.consecutive_loss_pair_threshold = consecutive_loss_pair_threshold
        self.consecutive_loss_pair_cooldown_hours = consecutive_loss_pair_cooldown_hours
        self.consecutive_loss_portfolio_threshold = consecutive_loss_portfolio_threshold
        self.consecutive_loss_portfolio_cooldown_hours = consecutive_loss_portfolio_cooldown_hours

        self.emergency_stop_active: bool = False
        self._pair_cooldown_until: Dict[str, datetime] = {}
        self._portfolio_cooldown_until: Optional[datetime] = None

    def trigger_emergency_stop(self, reason: str = "Operator manual kill switch"):
        self.emergency_stop_active = True
        logger.critical(f"EMERGENCY STOP TRIGGERED: {reason}")

    def reset_emergency_stop(self):
        self.emergency_stop_active = False
        logger.info("Emergency stop cleared.")

    def evaluate_intent(
        self,
        intent: TradeIntent,
        portfolio: PortfolioState,
        atr_value: float,
        swing_low: Optional[float] = None,
        swing_high: Optional[float] = None,
        current_time: Optional[datetime] = None,
        atr_multiplier: float = 2.0,
    ) -> RiskEvaluation:
        now = current_time or datetime.utcnow()

        if self.emergency_stop_active:
            return self._veto("EMERGENCY_STOP_ACTIVE")

        if self._portfolio_cooldown_until and now < self._portfolio_cooldown_until:
            return self._veto(f"PORTFOLIO_CONSECUTIVE_LOSS_COOLDOWN_UNTIL_{self._portfolio_cooldown_until.isoformat()}")

        pair_cooldown = self._pair_cooldown_until.get(intent.symbol)
        if pair_cooldown and now < pair_cooldown:
            return self._veto(f"PAIR_{intent.symbol}_COOLDOWN_UNTIL_{pair_cooldown.isoformat()}")

        daily_loss_ratio = portfolio.daily_realized_loss / portfolio.equity if portfolio.equity > 0 else 1.0
        if (daily_loss_ratio * 100.0) >= self.max_daily_loss_pct:
            return self._veto(f"DAILY_LOSS_LIMIT_REACHED_{daily_loss_ratio*100:.2f}%")

        if portfolio.drawdown_pct >= self.max_drawdown_pct:
            return self._veto(f"MAX_PORTFOLIO_DRAWDOWN_BREACHED_{portfolio.drawdown_pct:.2f}%")

        portfolio_losses = portfolio.consecutive_losses
        if portfolio_losses >= self.consecutive_loss_portfolio_threshold:
            self._portfolio_cooldown_until = now + timedelta(hours=self.consecutive_loss_portfolio_cooldown_hours)
            return self._veto(f"PORTFOLIO_CONSECUTIVE_LOSSES_{portfolio_losses}_TRIGGERED_COOLDOWN")

        pair_losses = portfolio.pair_consecutive_losses.get(intent.symbol, 0)
        if pair_losses >= self.consecutive_loss_pair_threshold:
            self._pair_cooldown_until[intent.symbol] = now + timedelta(hours=self.consecutive_loss_pair_cooldown_hours)
            return self._veto(f"PAIR_{intent.symbol}_CONSECUTIVE_LOSSES_{pair_losses}_TRIGGERED_COOLDOWN")

        pair_exposure = portfolio.active_exposures.get(intent.symbol, 0.0)
        if (pair_exposure / portfolio.equity * 100.0) >= self.max_pair_exposure_pct:
            return self._veto(f"PAIR_{intent.symbol}_MAX_EXPOSURE_REACHED")

        if (portfolio.total_exposure_notional / portfolio.equity * 100.0) >= self.max_total_exposure_pct:
            return self._veto("TOTAL_PORTFOLIO_MAX_EXPOSURE_REACHED")

        effective_risk_pct = self.base_risk_pct
        effective_leverage = self.max_leverage

        if portfolio.drawdown_pct >= 10.0:
            effective_risk_pct = self.base_risk_pct * 0.5
            effective_leverage = min(2.0, self.max_leverage)
            logger.warning(f"Drawdown warning ({portfolio.drawdown_pct:.1f}%): Scaling risk to {effective_risk_pct}% and leverage to {effective_leverage}x")

        stop_loss_price = compute_stop_loss(
            direction=intent.direction,
            entry_price=intent.entry_price_target,
            atr_value=atr_value,
            atr_multiplier=atr_multiplier,
            swing_low=swing_low,
            swing_high=swing_high,
            model=StopLossModel.HYBRID,
        )

        take_profit_price = compute_take_profit(
            direction=intent.direction,
            entry_price=intent.entry_price_target,
            stop_loss_price=stop_loss_price,
            risk_reward_ratio=2.0,
        )

        sizing = calculate_position_size(
            wallet_balance=portfolio.available_balance,
            risk_per_trade_pct=effective_risk_pct,
            entry_price=intent.entry_price_target,
            stop_loss_price=stop_loss_price,
            leverage=effective_leverage,
            symbol=intent.symbol,
        )

        if not sizing.get("approved", False):
            return self._veto(sizing.get("reason", "SIZING_REJECTED"))

        return RiskEvaluation(
            is_approved=True,
            veto_reason=None,
            approved_stake=sizing["stake_amount"],
            approved_contracts=sizing["contracts"],
            approved_leverage=effective_leverage,
            stop_loss_price=stop_loss_price,
            take_profit_price=take_profit_price,
            max_loss_usdt=sizing["max_risk_usdt"],
            sl_distance_pct=sizing["sl_distance_pct"],
            timestamp=now,
        )

    def _veto(self, reason: str) -> RiskEvaluation:
        logger.info(f"[RISK VETO] {reason}")
        return RiskEvaluation(
            is_approved=False,
            veto_reason=reason,
            approved_stake=0.0,
            approved_contracts=0.0,
            approved_leverage=1.0,
            stop_loss_price=0.0,
            take_profit_price=None,
            max_loss_usdt=0.0,
            sl_distance_pct=0.0,
        )

