"""
CUANIMUS MCP Portfolio & Account Telemetry Tools.
Provides real-time visibility into equity, positions, margin, exposure,
realized/unrealized PnL, and historical drawdown metrics.
"""
from typing import Dict, Any, List
from cuanimus.agent.identity import AgentPermission
from cuanimus.mcp.registry import McpRegistry
from cuanimus.common.types import PortfolioState


# Simulated portfolio state for Paper/Testnet
_global_portfolio_state = {
    "equity": 10000.0,
    "available_balance": 9500.0,
    "margin_used": 500.0,
    "peak_equity": 10250.0,
    "drawdown_pct": 2.44,
    "max_drawdown_pct": 3.80,
    "realized_pnl_today": 120.50,
    "unrealized_pnl": 45.00,
    "win_rate_pct": 62.5,
    "total_trades": 16,
    "positions": [
        {
            "position_id": "pos_eth_01",
            "symbol": "ETH/USDT:USDT",
            "side": "LONG",
            "size_contracts": 1.5,
            "entry_price": 3120.0,
            "mark_price": 3150.0,
            "current_stop_loss": 3050.0,
            "leverage": 3.0,
            "unrealized_pnl": 45.0,
            "liquidation_price": 2100.0,
        }
    ],
    "open_orders": [],
}


def tool_portfolio_get_balance(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Returns wallet balance, available balance, equity, and margin used."""
    return {
        "wallet_currency": "USDT",
        "equity": _global_portfolio_state["equity"],
        "available_balance": _global_portfolio_state["available_balance"],
        "margin_used": _global_portfolio_state["margin_used"],
        "margin_ratio_pct": round((_global_portfolio_state["margin_used"] / _global_portfolio_state["equity"]) * 100, 2),
    }


def tool_portfolio_get_positions(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Returns list of active positions."""
    return {
        "positions": _global_portfolio_state["positions"],
        "open_position_count": len(_global_portfolio_state["positions"]),
    }


def tool_portfolio_get_orders(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Returns active and recent orders."""
    return {
        "open_orders": _global_portfolio_state["open_orders"],
        "open_order_count": len(_global_portfolio_state["open_orders"]),
    }


def tool_portfolio_get_exposure(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Returns gross and net exposures across trading pairs."""
    positions = _global_portfolio_state["positions"]
    pair_exposures = {}
    gross_notional = 0.0

    for p in positions:
        notional = p["size_contracts"] * p["mark_price"]
        pair_exposures[p["symbol"]] = round(notional, 2)
        gross_notional += notional

    equity = _global_portfolio_state["equity"]
    exposure_pct = round((gross_notional / equity) * 100.0, 2) if equity > 0 else 0.0

    return {
        "gross_exposure_notional": round(gross_notional, 2),
        "gross_exposure_pct": exposure_pct,
        "pair_breakdown": pair_exposures,
        "max_exposure_allowed_pct": 80.0,
    }


def tool_portfolio_get_pnl(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Returns realized, unrealized, and win-rate metrics."""
    return {
        "realized_pnl_today": _global_portfolio_state["realized_pnl_today"],
        "unrealized_pnl": _global_portfolio_state["unrealized_pnl"],
        "win_rate_pct": _global_portfolio_state["win_rate_pct"],
        "total_trades": _global_portfolio_state["total_trades"],
    }


def tool_portfolio_get_drawdown(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Returns drawdown metrics and historical peak."""
    return {
        "current_drawdown_pct": _global_portfolio_state["drawdown_pct"],
        "peak_equity": _global_portfolio_state["peak_equity"],
        "max_historical_drawdown_pct": _global_portfolio_state["max_drawdown_pct"],
        "drawdown_limit_pct": 15.0,
    }


def register_portfolio_tools() -> None:
    McpRegistry.register_tool(
        name="portfolio.get_balance",
        description="Get account equity, wallet balance, and available margin.",
        input_schema={"type": "object", "properties": {}},
        permission_required=AgentPermission.READ_PORTFOLIO,
        handler=tool_portfolio_get_balance,
    )
    McpRegistry.register_tool(
        name="portfolio.get_positions",
        description="Get currently active open futures positions.",
        input_schema={"type": "object", "properties": {}},
        permission_required=AgentPermission.READ_PORTFOLIO,
        handler=tool_portfolio_get_positions,
    )
    McpRegistry.register_tool(
        name="portfolio.get_orders",
        description="Get active open limit/stop orders.",
        input_schema={"type": "object", "properties": {}},
        permission_required=AgentPermission.READ_PORTFOLIO,
        handler=tool_portfolio_get_orders,
    )
    McpRegistry.register_tool(
        name="portfolio.get_exposure",
        description="Get gross and net exposure per pair and total portfolio exposure.",
        input_schema={"type": "object", "properties": {}},
        permission_required=AgentPermission.READ_PORTFOLIO,
        handler=tool_portfolio_get_exposure,
    )
    McpRegistry.register_tool(
        name="portfolio.get_pnl",
        description="Get realized and unrealized profit & loss and win-rate statistics.",
        input_schema={"type": "object", "properties": {}},
        permission_required=AgentPermission.READ_PORTFOLIO,
        handler=tool_portfolio_get_pnl,
    )
    McpRegistry.register_tool(
        name="portfolio.get_drawdown",
        description="Get current and peak portfolio drawdown metrics.",
        input_schema={"type": "object", "properties": {}},
        permission_required=AgentPermission.READ_PORTFOLIO,
        handler=tool_portfolio_get_drawdown,
    )
