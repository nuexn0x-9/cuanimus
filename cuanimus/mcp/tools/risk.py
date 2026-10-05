"""
CUANIMUS MCP Risk Management & Guardrail Tools.
Provides visibility into active risk thresholds, cooldowns, emergency kill locks,
independent trade assessment, and mathematical position sizing calculations.
"""
from typing import Dict, Any, Optional
from cuanimus.agent.identity import AgentPermission
from cuanimus.mcp.registry import McpRegistry
from cuanimus.risk.engine import RiskEngine
from cuanimus.risk.sizing import calculate_position_size
from cuanimus.common.types import TradeIntent, SignalDirection, PortfolioState


_global_risk_engine = RiskEngine()


def tool_risk_get_status(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Returns active risk state, emergency lock, and cooldowns."""
    return {
        "emergency_stop_active": _global_risk_engine.emergency_stop_active,
        "base_risk_pct": _global_risk_engine.base_risk_pct,
        "max_leverage": _global_risk_engine.max_leverage,
        "max_daily_loss_pct": _global_risk_engine.max_daily_loss_pct,
        "max_drawdown_pct": _global_risk_engine.max_drawdown_pct,
        "pair_cooldowns_active": len(_global_risk_engine._pair_cooldown_until),
        "portfolio_cooldown_active": _global_risk_engine._portfolio_cooldown_until is not None,
    }


def tool_risk_get_limits(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Returns institutional risk limits configured for this deployment."""
    return {
        "base_risk_pct": _global_risk_engine.base_risk_pct,
        "max_leverage": _global_risk_engine.max_leverage,
        "max_daily_loss_pct": _global_risk_engine.max_daily_loss_pct,
        "max_drawdown_pct": _global_risk_engine.max_drawdown_pct,
        "max_pair_exposure_pct": _global_risk_engine.max_pair_exposure_pct,
        "max_total_exposure_pct": _global_risk_engine.max_total_exposure_pct,
        "consecutive_loss_pair_threshold": _global_risk_engine.consecutive_loss_pair_threshold,
        "consecutive_loss_portfolio_threshold": _global_risk_engine.consecutive_loss_portfolio_threshold,
        "platform_hard_leverage_ceiling": 10.0,
    }


def tool_risk_assess_trade(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Simulates Risk Engine evaluation for a candidate trade.
    Returns whether the trade is approved or vetoed with exact reasons.
    """
    symbol = args.get("symbol", "ETH/USDT:USDT")
    direction = args.get("direction", "LONG")
    entry_price = float(args.get("entry_price", 3120.0))
    stop_loss = float(args.get("stop_loss", 3050.0))
    atr_value = float(args.get("atr_value", 25.0))
    strategy_id = args.get("strategy_id", "v2_pullback")

    intent = TradeIntent(
        intent_id="sim_intent",
        symbol=symbol,
        direction=SignalDirection(direction.upper()),
        timestamp=None,
        strategy_id=strategy_id,
        entry_price_target=entry_price,
        suggested_stop_loss=stop_loss,
    )

    portfolio = PortfolioState(
        equity=10000.0,
        available_balance=10000.0,
        peak_equity=10000.0,
        drawdown_pct=0.0,
        daily_realized_loss=0.0,
        consecutive_losses=0,
    )

    eval_result = _global_risk_engine.evaluate_intent(
        intent=intent,
        portfolio=portfolio,
        atr_value=atr_value,
    )

    return {
        "is_approved": eval_result.is_approved,
        "veto_reason": eval_result.veto_reason,
        "approved_stake": eval_result.approved_stake,
        "approved_contracts": eval_result.approved_contracts,
        "approved_leverage": eval_result.approved_leverage,
        "calculated_stop_loss": eval_result.stop_loss_price,
        "calculated_take_profit": eval_result.take_profit_price,
        "max_loss_usdt": eval_result.max_loss_usdt,
        "sl_distance_pct": eval_result.sl_distance_pct,
    }


def tool_risk_calculate_position_size(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Computes exact mathematical position sizing given wallet balance and SL distance."""
    wallet_balance = float(args.get("wallet_balance", 10000.0))
    risk_per_trade_pct = float(args.get("risk_per_trade_pct", 1.5))
    entry_price = float(args.get("entry_price", 3120.0))
    stop_loss_price = float(args.get("stop_loss_price", 3050.0))
    leverage = float(args.get("leverage", 3.0))

    sizing = calculate_position_size(
        wallet_balance=wallet_balance,
        risk_per_trade_pct=risk_per_trade_pct,
        entry_price=entry_price,
        stop_loss_price=stop_loss_price,
        leverage=leverage,
    )

    return sizing


def register_risk_tools() -> None:
    McpRegistry.register_tool(
        name="risk.get_status",
        description="Get current Risk Engine status, cooldown states, and kill-switch status.",
        input_schema={"type": "object", "properties": {}},
        permission_required=AgentPermission.READ_RISK,
        handler=tool_risk_get_status,
    )
    McpRegistry.register_tool(
        name="risk.get_limits",
        description="Get configured risk limits (max risk, leverage, max daily loss, max drawdown).",
        input_schema={"type": "object", "properties": {}},
        permission_required=AgentPermission.READ_RISK,
        handler=tool_risk_get_limits,
    )
    McpRegistry.register_tool(
        name="risk.assess_trade",
        description="Assess trade intent through Risk Engine guardrails and position sizing.",
        input_schema={
            "type": "object",
            "required": ["symbol", "entry_price", "stop_loss"],
            "properties": {
                "symbol": {"type": "string"},
                "direction": {"type": "string", "description": "LONG or SHORT"},
                "entry_price": {"type": "number"},
                "stop_loss": {"type": "number"},
                "atr_value": {"type": "number"},
            },
        },
        permission_required=AgentPermission.ANALYZE,
        handler=tool_risk_assess_trade,
    )
    McpRegistry.register_tool(
        name="risk.calculate_position_size",
        description="Mathematically calculate contracts, stake USDT, and risk metrics for a trade.",
        input_schema={
            "type": "object",
            "required": ["wallet_balance", "entry_price", "stop_loss_price"],
            "properties": {
                "wallet_balance": {"type": "number"},
                "risk_per_trade_pct": {"type": "number"},
                "entry_price": {"type": "number"},
                "stop_loss_price": {"type": "number"},
                "leverage": {"type": "number"},
            },
        },
        permission_required=AgentPermission.READ_RISK,
        handler=tool_risk_calculate_position_size,
    )
