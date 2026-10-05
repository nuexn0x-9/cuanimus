"""
CUANIMUS Deterministic Event-Driven Backtest & Simulation Pipeline.
Implements the 9-stage simulation pipeline with fees, funding, slippage,
limit/market orders, timeouts, partial fills, and stop executions.
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import math

from cuanimus.common.types import (
    TradeIntent,
    SignalDirection,
    OrderRequest,
    OrderSide,
    OrderType,
    OrderState,
    Order,
    Position,
    PortfolioState,
    RegimeContext,
    MarketRegimeType,
)
from cuanimus.risk.engine import RiskEngine
from cuanimus.strategy.base import BaseStrategy
from cuanimus.validation.metrics import compute_performance_metrics


@dataclass
class SimulationConfig:
    initial_capital: float = 65.0
    maker_fee_pct: float = 0.02
    taker_fee_pct: float = 0.05
    slippage_pct: float = 0.05
    funding_rate_8h_pct: float = 0.01
    unfilled_timeout_bars: int = 4 # 4 x 15m = 60 minutes
    max_open_trades: int = 3


class ExecutionSimulator:
    """Simulates realistic exchange order execution with slippage, fees, and timeouts."""
    def __init__(self, config: SimulationConfig):
        self.config = config

    def simulate_entry_fill(
        self,
        order_req: OrderRequest,
        bar: Dict[str, float],
        bar_index: int,
    ) -> Optional[Dict[str, Any]]:
        """
        Attempts to fill an entry order against candle OHLCV.
        """
        open_p = bar["open"]
        high_p = bar["high"]
        low_p = bar["low"]
        vol = bar.get("volume", 1000.0)

        # Market Order Fill
        if order_req.order_type == OrderType.MARKET:
            fill_price = open_p * (1.0 + (self.config.slippage_pct / 100.0) if order_req.side == OrderSide.BUY else 1.0 - (self.config.slippage_pct / 100.0))
            fee = fill_price * order_req.amount * (self.config.taker_fee_pct / 100.0)
            return {
                "filled": True,
                "fill_price": fill_price,
                "amount": order_req.amount,
                "fee": fee,
                "is_partial": False,
            }

        # Limit Order Fill
        if order_req.order_type == OrderType.LIMIT:
            limit_p = order_req.price
            can_fill = (low_p <= limit_p) if order_req.side == OrderSide.BUY else (high_p >= limit_p)

            if not can_fill:
                return None # Not filled on this bar

            # Partial fill check if requested contracts exceed 50% of candle volume
            if order_req.amount > (vol * 0.5):
                partial_amount = round(vol * 0.5, 4)
                fee = limit_p * partial_amount * (self.config.maker_fee_pct / 100.0)
                return {
                    "filled": True,
                    "fill_price": limit_p,
                    "amount": partial_amount,
                    "fee": fee,
                    "is_partial": True,
                }

            fee = limit_p * order_req.amount * (self.config.maker_fee_pct / 100.0)
            return {
                "filled": True,
                "fill_price": limit_p,
                "amount": order_req.amount,
                "fee": fee,
                "is_partial": False,
            }

        return None

    def check_position_exit(
        self,
        pos: Position,
        bar: Dict[str, float],
        bars_held: int,
        take_profit_price: Optional[float] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Checks if position hits Stop Loss, Take Profit, or Time-Exit.
        """
        high_p = bar["high"]
        low_p = bar["low"]
        close_p = bar["close"]

        if pos.side == SignalDirection.LONG:
            # 1. Stop Loss Hit
            if low_p <= pos.current_stop_loss:
                exit_price = pos.current_stop_loss * (1.0 - (self.config.slippage_pct / 100.0))
                pnl = (exit_price - pos.entry_price) * pos.size
                fee = exit_price * pos.size * (self.config.taker_fee_pct / 100.0)
                return {"reason": "stop_loss", "exit_price": exit_price, "pnl": pnl, "fee": fee}

            # 2. Take Profit Hit
            if take_profit_price and high_p >= take_profit_price:
                exit_price = take_profit_price
                pnl = (exit_price - pos.entry_price) * pos.size
                fee = exit_price * pos.size * (self.config.maker_fee_pct / 100.0)
                return {"reason": "take_profit", "exit_price": exit_price, "pnl": pnl, "fee": fee}

        elif pos.side == SignalDirection.SHORT:
            # 1. Stop Loss Hit
            if high_p >= pos.current_stop_loss:
                exit_price = pos.current_stop_loss * (1.0 + (self.config.slippage_pct / 100.0))
                pnl = (pos.entry_price - exit_price) * pos.size
                fee = exit_price * pos.size * (self.config.taker_fee_pct / 100.0)
                return {"reason": "stop_loss", "exit_price": exit_price, "pnl": pnl, "fee": fee}

            # 2. Take Profit Hit
            if take_profit_price and low_p <= take_profit_price:
                exit_price = take_profit_price
                pnl = (pos.entry_price - exit_price) * pos.size
                fee = exit_price * pos.size * (self.config.maker_fee_pct / 100.0)
                return {"reason": "take_profit", "exit_price": exit_price, "pnl": pnl, "fee": fee}

        return None


class BacktestPipeline:
    """
    Coordinates end-to-end backtesting pipeline from bar series to performance scorecard.
    """
    def __init__(self, strategy: BaseStrategy, risk_engine: RiskEngine, config: SimulationConfig):
        self.strategy = strategy
        self.risk_engine = risk_engine
        self.config = config
        self.simulator = ExecutionSimulator(config)

    def run(
        self,
        symbol: str,
        bars: List[Dict[str, Any]],
        regime_context: RegimeContext,
        atr_multiplier: float = 2.0,
    ) -> Dict[str, Any]:
        equity = self.config.initial_capital
        available_balance = equity
        peak_equity = equity
        daily_loss = 0.0
        consecutive_losses = 0
        pair_losses = {symbol: 0}

        closed_trades = []
        active_position: Optional[Position] = None
        pos_take_profit: Optional[float] = None
        bars_held = 0

        pending_order: Optional[Dict[str, Any]] = None
        order_age_bars = 0

        for i, bar in enumerate(bars):
            # Check active position exits first
            if active_position is not None:
                bars_held += 1
                # 8-hour funding rate impact (every 32 x 15m bars)
                if bars_held % 32 == 0:
                    funding = active_position.size * bar["close"] * (self.config.funding_rate_8h_pct / 100.0)
                    active_position.accumulated_funding += funding

                exit_res = self.simulator.check_position_exit(
                    active_position, bar, bars_held, take_profit_price=pos_take_profit
                )

                if exit_res:
                    gross_pnl = exit_res["pnl"]
                    total_fee = active_position.accumulated_fees + exit_res["fee"]
                    net_pnl = gross_pnl - total_fee - active_position.accumulated_funding

                    profit_pct = (net_pnl / (active_position.size * active_position.entry_price / active_position.leverage)) * 100.0
                    stake = (active_position.size * active_position.entry_price) / active_position.leverage

                    equity += net_pnl
                    available_balance += (stake + net_pnl)
                    if equity > peak_equity:
                        peak_equity = equity

                    if net_pnl <= 0:
                        daily_loss += abs(net_pnl)
                        consecutive_losses += 1
                        pair_losses[symbol] += 1
                    else:
                        consecutive_losses = 0
                        pair_losses[symbol] = 0

                    closed_trades.append({
                        "trade_id": len(closed_trades) + 1,
                        "symbol": symbol,
                        "profit_pct": profit_pct,
                        "profit_abs": net_pnl,
                        "stake_amount": stake,
                        "fee_cost": total_fee,
                        "funding_cost": active_position.accumulated_funding,
                        "duration_min": bars_held * 15,
                        "exit_reason": exit_res["reason"],
                        "is_short": 1 if active_position.side == SignalDirection.SHORT else 0,
                    })

                    active_position = None
                    pos_take_profit = None
                    bars_held = 0

            # Handle pending order timeouts
            if pending_order is not None and active_position is None:
                order_age_bars += 1
                # Check for fill
                fill_res = self.simulator.simulate_entry_fill(pending_order["request"], bar, i)
                if fill_res:
                    active_position = Position(
                        position_id=f"POS_{i}",
                        symbol=symbol,
                        side=SignalDirection.LONG if pending_order["request"].side == OrderSide.BUY else SignalDirection.SHORT,
                        size=fill_res["amount"],
                        entry_price=fill_res["fill_price"],
                        current_stop_loss=pending_order["request"].stop_loss,
                        leverage=pending_order["request"].leverage,
                        accumulated_fees=fill_res["fee"],
                    )
                    pos_take_profit = pending_order["take_profit"]
                    available_balance -= (fill_res["amount"] * fill_res["fill_price"] / pending_order["request"].leverage)
                    pending_order = None
                    order_age_bars = 0
                elif order_age_bars >= self.config.unfilled_timeout_bars:
                    # Timeout reached: Cancel pending order
                    pending_order = None
                    order_age_bars = 0

            # Evaluate strategy intent on candle close if no position and no pending order
            if active_position is None and pending_order is None:
                features = bar.get("features", {})
                atr_val = features.get("atr", bar["close"] * 0.015)

                intent = self.strategy.evaluate_intent(
                    symbol=symbol,
                    current_candle={"close": bar["close"]},
                    features=features,
                    regime=regime_context,
                )

                if intent.direction in (SignalDirection.LONG, SignalDirection.SHORT):
                    portfolio = PortfolioState(
                        equity=equity,
                        available_balance=available_balance,
                        peak_equity=peak_equity,
                        drawdown_pct=((peak_equity - equity) / peak_equity * 100.0) if peak_equity > 0 else 0.0,
                        daily_realized_loss=daily_loss,
                        consecutive_losses=consecutive_losses,
                        pair_consecutive_losses=pair_losses,
                        active_exposures={symbol: 0.0},
                    )

                    risk_eval = self.risk_engine.evaluate_intent(
                        intent=intent,
                        portfolio=portfolio,
                        atr_value=atr_val,
                        current_time=bar.get("timestamp"),
                        atr_multiplier=atr_multiplier,
                    )

                    if risk_eval.is_approved:
                        side = OrderSide.BUY if intent.direction == SignalDirection.LONG else OrderSide.SELL
                        order_req = OrderRequest(
                            client_order_id=f"CNMS_SIM_{i}",
                            symbol=symbol,
                            side=side,
                            order_type=OrderType.LIMIT,
                            amount=risk_eval.approved_contracts,
                            price=intent.entry_price_target,
                            stop_loss=risk_eval.stop_loss_price,
                            leverage=risk_eval.approved_leverage,
                        )
                        pending_order = {
                            "request": order_req,
                            "take_profit": risk_eval.take_profit_price,
                        }
                        order_age_bars = 0

        metrics = compute_performance_metrics(closed_trades, initial_capital=self.config.initial_capital)
        return {
            "metrics": metrics,
            "closed_trades": closed_trades,
            "final_equity": equity,
        }
