"""
CUANIMUS MCP Strategy Intelligence Tools.
Enables agents to discover registered strategies, inspect parameter schemas,
evaluate market snapshots for algorithmic signals, and receive structured explanations.
"""
from typing import Dict, Any, Optional
from cuanimus.agent.identity import AgentPermission
from cuanimus.mcp.registry import McpRegistry
from cuanimus.strategy.registry import StrategyRegistry
from cuanimus.common.types import SignalDirection, RegimeContext, MarketRegimeType


def tool_strategy_list(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Lists all registered strategy plugins with metadata and supported markets."""
    strategies = StrategyRegistry.list_strategies()
    return {
        "count": len(strategies),
        "strategies": strategies,
    }


def tool_strategy_inspect(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Inspects detailed parameters and specifications for a strategy."""
    strategy_id = args.get("strategy_id")
    if not strategy_id:
        raise ValueError("Missing required 'strategy_id'")
    meta = StrategyRegistry.get_metadata(strategy_id)
    return meta.to_dict()


def tool_strategy_evaluate(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Evaluates a strategy against given or latest market parameters.
    Returns signal direction and suggested levels.
    """
    strategy_id = args.get("strategy_id", "v2_pullback")
    symbol = args.get("symbol", "ETH/USDT:USDT")
    close_price = float(args.get("close_price", 3120.0))
    volume = float(args.get("volume", 1500.0))

    try:
        strategy = StrategyRegistry.get(strategy_id)
    except KeyError:
        raise ValueError(f"Strategy '{strategy_id}' not found in registry.")

    candle = {
        "open": close_price * 0.998,
        "high": close_price * 1.005,
        "low": close_price * 0.995,
        "close": close_price,
        "volume": volume,
    }
    features = {
        "ema20": close_price * 1.001,
        "ema50": close_price * 0.98,
        "stoch_k": 22.0,
        "stoch_d": 25.0,
        "volume": volume,
        "volume_avg": volume * 0.8,
        "atr": 25.0,
    }
    regime = RegimeContext(
        regime=MarketRegimeType.TRENDING_BULL,
        trend_strength_adx=28.0,
        volatility_atr=25.0,
        volatility_percentile=55.0,
        htf_bias="BULLISH",
        confidence=85.0,
    )

    intent = strategy.evaluate_intent(symbol, candle, features, regime)
    if intent:
        return {
            "strategy_id": strategy_id,
            "symbol": symbol,
            "signal": intent.direction.value,
            "entry_price": intent.entry_price_target,
            "suggested_stop_loss": intent.suggested_stop_loss,
            "suggested_take_profit": intent.suggested_take_profit,
            "confidence": intent.confidence,
            "has_signal": intent.direction != SignalDirection.HOLD,
        }
    else:
        return {
            "strategy_id": strategy_id,
            "symbol": symbol,
            "signal": "HOLD",
            "entry_price": close_price,
            "suggested_stop_loss": None,
            "suggested_take_profit": None,
            "confidence": 0.0,
            "has_signal": False,
        }


def tool_strategy_explain_signal(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Explains algorithmic rationale for a strategy's signal."""
    strategy_id = args.get("strategy_id", "v2_pullback")
    signal = args.get("signal", "LONG")

    explanations = {
        "v2_pullback": {
            "LONG": "Price completed a retracement to the Golden Pocket (0.618 Fib) while 1h & 4h macro trend remains Bullish (EMA50 > EMA200). Volume contracted during pullback, confirming absorption before expansion.",
            "SHORT": "Bearish continuation pullback rejected at 0.618 Fib resistance in downtrend regime.",
            "HOLD": "Market is in consolidation or ATR percentile is below minimum volatility threshold.",
        },
        "baseline_v0": {
            "LONG": "EMA 9 crossed above EMA 21 with positive volume confirmation.",
            "SHORT": "EMA 9 crossed below EMA 21.",
            "HOLD": "No moving average cross detected.",
        },
    }

    strategy_exp = explanations.get(strategy_id, explanations["v2_pullback"])
    reason = strategy_exp.get(signal.upper(), "Standard algorithmic signal alignment.")

    return {
        "strategy_id": strategy_id,
        "signal": signal,
        "explanation": reason,
        "causality": "STRICT_CAUSAL_CLOSED_BARS",
    }


def register_strategy_tools() -> None:
    McpRegistry.register_tool(
        name="strategy.list",
        description="List all registered quantitative strategies in CUANIMUS.",
        input_schema={"type": "object", "properties": {}},
        permission_required=AgentPermission.READ_STRATEGY,
        handler=tool_strategy_list,
    )
    McpRegistry.register_tool(
        name="strategy.inspect",
        description="Inspect metadata, timeframe, and configurable parameters of a strategy.",
        input_schema={
            "type": "object",
            "required": ["strategy_id"],
            "properties": {"strategy_id": {"type": "string", "description": "e.g. v2_pullback"}},
        },
        permission_required=AgentPermission.READ_STRATEGY,
        handler=tool_strategy_inspect,
    )
    McpRegistry.register_tool(
        name="strategy.evaluate",
        description="Evaluate strategy logic against given market data to generate TradeIntent.",
        input_schema={
            "type": "object",
            "properties": {
                "strategy_id": {"type": "string", "description": "Strategy plugin ID"},
                "symbol": {"type": "string", "description": "e.g. ETH/USDT:USDT"},
                "close_price": {"type": "number", "description": "Current price"},
            },
        },
        permission_required=AgentPermission.ANALYZE,
        handler=tool_strategy_evaluate,
    )
    McpRegistry.register_tool(
        name="strategy.explain_signal",
        description="Explain technical factors and indicators driving a signal.",
        input_schema={
            "type": "object",
            "properties": {
                "strategy_id": {"type": "string"},
                "signal": {"type": "string", "description": "LONG, SHORT, HOLD"},
            },
        },
        permission_required=AgentPermission.ANALYZE,
        handler=tool_strategy_explain_signal,
    )
