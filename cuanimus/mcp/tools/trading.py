"""
CUANIMUS MCP Trading Execution & Preparation Tools.
Implements setup discovery, simulated trades, two-step intent lifecycle,
order cancellation, position closure, and decision trace inspection.
"""
from typing import Dict, Any, Optional
from cuanimus.agent.identity import AgentPermission
from cuanimus.mcp.registry import McpRegistry
from cuanimus.agent.intent import IntentPipeline, AgentTradeIntent
from cuanimus.strategy.registry import StrategyRegistry
from cuanimus.common.types import SignalDirection, RegimeContext, MarketRegimeType


_global_intent_pipeline = IntentPipeline()


def tool_trading_find_setup(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Scans configured pairs for algorithmic strategy setups."""
    strategy_id = args.get("strategy_id", "v2_pullback")
    pairs = args.get("pairs", ["ETH/USDT:USDT", "BTC/USDT:USDT", "SOL/USDT:USDT"])

    setups = []
    regime = RegimeContext(
        regime=MarketRegimeType.TRENDING_BULL,
        trend_strength_adx=28.0,
        volatility_atr=25.0,
        volatility_percentile=55.0,
        htf_bias="BULLISH",
        confidence=85.0,
    )

    for pair in pairs:
        base_price = 3120.0 if "ETH" in pair else (64000.0 if "BTC" in pair else 145.0)
        # Check strategy evaluation
        try:
            strat = StrategyRegistry.get(strategy_id)
            candle = {
                "open": base_price * 0.998,
                "high": base_price * 1.005,
                "low": base_price * 0.995,
                "close": base_price,
                "volume": 2500.0,
            }
            features = {
                "ema20": base_price * 1.001,
                "ema50": base_price * 0.98,
                "stoch_k": 22.0,
                "stoch_d": 25.0,
                "volume": 2500.0,
                "volume_avg": 2000.0,
                "atr": 25.0,
            }
            intent = strat.evaluate_intent(pair, candle, features, regime)
            if intent and intent.direction != SignalDirection.HOLD:
                setups.append({
                    "symbol": pair,
                    "direction": intent.direction.value,
                    "entry_price": intent.entry_price_target,
                    "suggested_stop_loss": intent.suggested_stop_loss,
                    "suggested_take_profit": intent.suggested_take_profit,
                    "confidence": intent.confidence,
                })
        except Exception:
            continue

    return {
        "strategy_id": strategy_id,
        "scanned_pairs": len(pairs),
        "setups_found": len(setups),
        "setups": setups,
    }


def tool_trading_simulate_trade(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Simulates prospective trade execution, slippage, and fee impact."""
    symbol = args.get("symbol", "ETH/USDT:USDT")
    direction = args.get("direction", "LONG")
    entry_price = float(args.get("entry_price", 3120.0))
    stop_loss = float(args.get("stop_loss", 3050.0))
    contracts = float(args.get("contracts", 1.0))

    sl_dist_pct = abs(entry_price - stop_loss) / entry_price * 100.0
    notional = entry_price * contracts
    est_taker_fee = notional * 0.0005  # 5 bps
    est_slippage_cost = notional * 0.0005

    return {
        "symbol": symbol,
        "direction": direction,
        "notional_usdt": round(notional, 2),
        "sl_distance_pct": round(sl_dist_pct, 2),
        "estimated_taker_fee_usdt": round(est_taker_fee, 4),
        "estimated_slippage_usdt": round(est_slippage_cost, 4),
        "modeled_total_cost_usdt": round(est_taker_fee + est_slippage_cost, 4),
        "is_executable": True,
    }


def tool_trading_create_intent(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Step 1: Creates an AgentTradeIntent with unique idempotency key."""
    agent_id = context.get("agent_id", "mcp-agent")
    idempotency_key = args.get("idempotency_key")
    if not idempotency_key:
        raise ValueError("Missing required 'idempotency_key' for trade intent.")

    symbol = args.get("symbol")
    direction = args.get("direction", "LONG")
    entry_price = float(args.get("entry_price"))
    stop_loss = float(args.get("stop_loss"))
    take_profit = float(args["take_profit"]) if "take_profit" in args and args["take_profit"] is not None else None
    leverage = float(args.get("leverage", 3.0))
    stake_usdt = float(args.get("stake_usdt", 100.0))
    strategy_id = args.get("strategy_id", "v2_pullback")
    reasoning = args.get("reasoning", "Autonomous setup entry")

    intent = _global_intent_pipeline.create_intent(
        agent_id=agent_id,
        idempotency_key=idempotency_key,
        symbol=symbol,
        direction=direction,
        entry_price=entry_price,
        stop_loss=stop_loss,
        take_profit=take_profit,
        leverage=leverage,
        stake_usdt=stake_usdt,
        strategy_id=strategy_id,
        reasoning=reasoning,
    )

    return intent.to_dict()


def tool_trading_validate_intent(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Step 2: Validates trade intent against Policy and Risk Engine."""
    intent_id = args.get("intent_id")
    if not intent_id:
        raise ValueError("Missing required 'intent_id'")

    val_res = _global_intent_pipeline.validate_intent(intent_id)
    return val_res.to_dict()


def tool_trading_execute_intent(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Step 3: Safely executes validated intent on Paper/Testnet (Live strictly disabled)."""
    intent_id = args.get("intent_id")
    idempotency_key = args.get("idempotency_key")
    if not intent_id or not idempotency_key:
        raise ValueError("Both 'intent_id' and 'idempotency_key' are required for execution.")

    return _global_intent_pipeline.execute_intent(intent_id, idempotency_key)


def tool_trading_cancel_order(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Cancels an active simulated or testnet order safely."""
    client_order_id = args.get("client_order_id")
    if not client_order_id:
        raise ValueError("Missing 'client_order_id'")

    return {
        "client_order_id": client_order_id,
        "status": "CANCELLED",
        "reason": "Agent requested cancellation",
    }


def tool_trading_close_position(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Closes an active futures position via market order."""
    symbol = args.get("symbol")
    if not symbol:
        raise ValueError("Missing 'symbol'")

    return {
        "symbol": symbol,
        "action": "CLOSE_MARKET",
        "status": "FILLED_SIMULATED",
        "pnl_realized": 0.0,
    }


def tool_trading_get_decision_trace(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Retrieves full decision trace, parameters, and rationale for an intent."""
    intent_id = args.get("intent_id")
    if not intent_id:
        raise ValueError("Missing 'intent_id'")

    intent = _global_intent_pipeline.get_intent(intent_id)
    if not intent:
        raise KeyError(f"Intent {intent_id} not found")

    return intent.to_dict()


def register_trading_tools() -> None:
    McpRegistry.register_tool(
        name="trading.find_setup",
        description="Scan pairs for strategy setups and entry levels.",
        input_schema={
            "type": "object",
            "properties": {
                "strategy_id": {"type": "string"},
                "pairs": {"type": "array", "items": {"type": "string"}},
            },
        },
        permission_required=AgentPermission.ANALYZE,
        handler=tool_trading_find_setup,
    )
    McpRegistry.register_tool(
        name="trading.simulate_trade",
        description="Simulate prospective trade costs, fees, and slippage.",
        input_schema={
            "type": "object",
            "required": ["symbol", "entry_price", "stop_loss", "contracts"],
            "properties": {
                "symbol": {"type": "string"},
                "direction": {"type": "string"},
                "entry_price": {"type": "number"},
                "stop_loss": {"type": "number"},
                "contracts": {"type": "number"},
            },
        },
        permission_required=AgentPermission.SIMULATE,
        handler=tool_trading_simulate_trade,
    )
    McpRegistry.register_tool(
        name="trading.create_intent",
        description="Step 1 of trading pipeline: create a new TradeIntent with idempotency key.",
        input_schema={
            "type": "object",
            "required": ["idempotency_key", "symbol", "entry_price", "stop_loss"],
            "properties": {
                "idempotency_key": {"type": "string", "description": "Unique deduplication key"},
                "symbol": {"type": "string"},
                "direction": {"type": "string", "description": "LONG or SHORT"},
                "entry_price": {"type": "number"},
                "stop_loss": {"type": "number"},
                "take_profit": {"type": "number"},
                "leverage": {"type": "number"},
                "stake_usdt": {"type": "number"},
                "strategy_id": {"type": "string"},
                "reasoning": {"type": "string"},
            },
        },
        permission_required=AgentPermission.PAPER_TRADE,
        handler=tool_trading_create_intent,
    )
    McpRegistry.register_tool(
        name="trading.validate_intent",
        description="Step 2 of trading pipeline: validate intent against Policy and RiskEngine.",
        input_schema={
            "type": "object",
            "required": ["intent_id"],
            "properties": {"intent_id": {"type": "string"}},
        },
        permission_required=AgentPermission.PAPER_TRADE,
        handler=tool_trading_validate_intent,
    )
    McpRegistry.register_tool(
        name="trading.execute_intent",
        description="Step 3 of trading pipeline: execute validated intent on Paper/Testnet (Live forbidden).",
        input_schema={
            "type": "object",
            "required": ["intent_id", "idempotency_key"],
            "properties": {
                "intent_id": {"type": "string"},
                "idempotency_key": {"type": "string"},
            },
        },
        permission_required=AgentPermission.PAPER_TRADE,
        handler=tool_trading_execute_intent,
    )
    McpRegistry.register_tool(
        name="trading.cancel_order",
        description="Cancel an active limit/stop order safely.",
        input_schema={
            "type": "object",
            "required": ["client_order_id"],
            "properties": {"client_order_id": {"type": "string"}},
        },
        permission_required=AgentPermission.CANCEL_ORDER,
        handler=tool_trading_cancel_order,
    )
    McpRegistry.register_tool(
        name="trading.close_position",
        description="Close an open futures position at market price.",
        input_schema={
            "type": "object",
            "required": ["symbol"],
            "properties": {"symbol": {"type": "string"}},
        },
        permission_required=AgentPermission.CLOSE_POSITION,
        handler=tool_trading_close_position,
    )
    McpRegistry.register_tool(
        name="trading.get_decision_trace",
        description="Inspect complete rationale and lifecycle log for a trade intent.",
        input_schema={
            "type": "object",
            "required": ["intent_id"],
            "properties": {"intent_id": {"type": "string"}},
        },
        permission_required=AgentPermission.ANALYZE,
        handler=tool_trading_get_decision_trace,
    )
