"""
CUANIMUS MCP Tools Initialization.
Registers all 8 tool suites into the central McpRegistry.
"""
from cuanimus.mcp.tools.system import register_system_tools
from cuanimus.mcp.tools.configuration import register_configuration_tools
from cuanimus.mcp.tools.market import register_market_tools
from cuanimus.mcp.tools.portfolio import register_portfolio_tools
from cuanimus.mcp.tools.strategy import register_strategy_tools
from cuanimus.mcp.tools.risk import register_risk_tools
from cuanimus.mcp.tools.trading import register_trading_tools
from cuanimus.mcp.tools.sessions import register_session_tools


def register_all_tools() -> None:
    """Registers all built-in MCP tool endpoints."""
    register_system_tools()
    register_configuration_tools()
    register_market_tools()
    register_portfolio_tools()
    register_strategy_tools()
    register_risk_tools()
    register_trading_tools()
    register_session_tools()
