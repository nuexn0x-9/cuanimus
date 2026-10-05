"""
CUANIMUS MCP Prompts.
Provides structured system prompts to assist AI agents in configuring the platform,
evaluating market regimes, and preparing risk-controlled trade proposals.
"""
from typing import Dict, Any
from cuanimus.mcp.registry import McpRegistry


def prompt_assisted_config(args: Dict[str, Any]) -> Dict[str, Any]:
    user_goal = args.get("goal", "Configure conservative risk profile with v2_pullback strategy")
    return {
        "description": "System prompt for guiding the user through safe CUANIMUS configuration.",
        "messages": [
            {
                "role": "system",
                "content": {
                    "type": "text",
                    "text": (
                        "You are the CUANIMUS Quantitative Configuration Assistant. "
                        "Your role is to understand the operator's trading goals and generate structured "
                        "configuration proposals via 'config.preview'.\n\n"
                        "STRICT PLATFORM RULES:\n"
                        "1. Live real-capital trading is STRICTLY DISABLED (NO-GO).\n"
                        "2. Never attempt to disable mandatory stop-loss.\n"
                        "3. Maximum leverage must not exceed the institutional ceiling of 10.0x.\n"
                        "4. Never edit core Python source files directly. Always use the configuration proposal tools.\n"
                        "5. Clearly explain parameter deltas and impact levels (SAFE, NOTICE, CRITICAL) to the user."
                    ),
                },
            },
            {
                "role": "user",
                "content": {
                    "type": "text",
                    "text": f"Please assist me with configuring CUANIMUS for: {user_goal}",
                },
            },
        ],
    }


def prompt_market_analysis(args: Dict[str, Any]) -> Dict[str, Any]:
    symbol = args.get("symbol", "ETH/USDT:USDT")
    return {
        "description": "Guide comprehensive multi-timeframe and regime analysis.",
        "messages": [
            {
                "role": "system",
                "content": {
                    "type": "text",
                    "text": (
                        "You are the CUANIMUS Quantitative Market Intelligence Agent. "
                        "Use 'market.get_snapshot', 'market.get_ohlcv', 'market.get_funding', and 'market.get_regime' "
                        "to deliver an objective, causal analysis. Avoid subjective hype. "
                        "Classify the regime (TRENDING_BULL, TRENDING_BEAR, RANGING, HIGH_VOLATILITY, LOW_VOLATILITY) "
                        "and verify whether conditions satisfy the active strategy's entry criteria."
                    ),
                },
            },
            {
                "role": "user",
                "content": {
                    "type": "text",
                    "text": f"Perform market intelligence analysis on {symbol}.",
                },
            },
        ],
    }


def register_all_prompts() -> None:
    McpRegistry.register_prompt(
        name="assisted-configuration",
        description="Prompt guiding AI assistant through conversational CUANIMUS configuration.",
        arguments=[{"name": "goal", "description": "Operator's configuration goal", "required": False}],
        handler=prompt_assisted_config,
    )
    McpRegistry.register_prompt(
        name="market-analysis",
        description="Prompt guiding multi-timeframe market regime and funding rate analysis.",
        arguments=[{"name": "symbol", "description": "Target trading pair", "required": False}],
        handler=prompt_market_analysis,
    )
