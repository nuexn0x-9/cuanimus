"""
CUANIMUS True Bar-Level Replay & Multi-Timeframe Simulation Engine.
Implements:
- Strict Event Clock & Information Boundary (t <= T, zero lookahead)
- Multi-Timeframe Alignment (15m execution uses strictly closed 1h/4h context)
- Causal feature extraction & confirmed structure/order block tracking
- True bar-by-bar execution simulation with limit fills, adverse slippage, fees, and funding
"""
import os
import math
import json
import csv
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple

from cuanimus.common.types import (
    TradeIntent,
    SignalDirection,
    OrderRequest,
    OrderSide,
    OrderType,
    OrderState,
    Position,
    PortfolioState,
    RegimeContext,
    MarketRegimeType,
)
from cuanimus.common.exceptions import LookaheadViolationError
from cuanimus.risk.engine import RiskEngine
from cuanimus.strategy.base import BaseStrategy
from cuanimus.strategy.features import (
    compute_closed_candle_atr,
    evaluate_trend_feature,
    compute_closed_candle_rsi,
    compute_closed_candle_adx,
)
from cuanimus.strategy.structure import (
    detect_swing_points,
    filter_confirmed_swings,
    detect_order_blocks,
    filter_confirmed_order_blocks,
    compute_fibonacci_levels,
)
from cuanimus.validation.metrics import compute_performance_metrics


@dataclass
class ReplaySlippageModel:
    model_name: str = "BASE"  # BASE (0.05%), CONSERVATIVE (0.10%), STRESS (0.25%)
    taker_slippage_pct: float = 0.05


@dataclass
class ReplayFeeModel:
    maker_fee_pct: float = 0.02
    taker_fee_pct: float = 0.05


@dataclass
class ReplayConfig:
    initial_capital: float = 65.0
    fee_model: ReplayFeeModel = field(default_factory=ReplayFeeModel)
    slippage_model: ReplaySlippageModel = field(default_factory=ReplaySlippageModel)
    unfilled_timeout_bars: int = 4  # 4 x 15m = 60 min
    max_open_positions: int = 2
    modeled_execution: bool = True


class StrictEventClock:
    """Enforces that no data with timestamp t > current_time can be accessed."""
    def __init__(self, start_time: datetime):
        self.current_time = start_time

    def tick(self, new_time: datetime):
        if new_time < self.current_time:
            raise LookaheadViolationError(f"Clock retreated backwards from {self.current_time} to {new_time}")
        self.current_time = new_time

    def assert_no_lookahead(self, data_time: datetime, label: str = "data"):
        if data_time > self.current_time:
            raise LookaheadViolationError(
                f"STRICT INFORMATION BOUNDARY BREACH: {label} timestamp ({data_time}) is in the future relative to event clock ({self.current_time})!"
            )


class MultiTimeframeAlignmentManager:
    """
    Enforces that 15m execution only has access to closed 15m bars,
    and 1h context only has access to the latest CLOSED 1h bar.
    """
    @staticmethod
    def get_latest_closed_htf_bar(
        htf_bars: List[Dict[str, Any]],
        current_execution_close_time: datetime,
    ) -> Optional[Dict[str, Any]]:
        """
        Returns the latest 1h bar whose close time is <= current_execution_close_time.
        If a 1h bar is still forming (close time > current_execution_close_time), it is excluded.
        """
        closed_candidates = []
        for b in htf_bars:
            b_date = datetime.fromisoformat(b["date"].replace("Z", "+00:00")) if isinstance(b["date"], str) else b["date"]
            # A 1h bar labeled b_date opens at b_date and closes at b_date + 1h
            bar_close_time = b_date + timedelta(hours=1)
            if bar_close_time <= current_execution_close_time:
                closed_candidates.append(b)

        return closed_candidates[-1] if closed_candidates else None


class TrueBarReplayEngine:
    """
    Replays quantitative strategies candle-by-candle across raw OHLCV.
    No future proxy, no lookahead, explicit fees, slippage, and funding.
    """
    def __init__(
        self,
        strategy: BaseStrategy,
        risk_engine: RiskEngine,
        config: ReplayConfig,
    ):
        self.strategy = strategy
        self.risk_engine = risk_engine
        self.config = config

    def run(
        self,
        symbol: str,
        bars_15m: List[Dict[str, Any]],
        bars_1h: Optional[List[Dict[str, Any]]] = None,
        funding_records: Optional[List[Dict[str, Any]]] = None,
        atr_multiplier: float = 2.0,
    ) -> Dict[str, Any]:
        equity = self.config.initial_capital
        available_balance = equity
        peak_equity = equity
        daily_loss = 0.0
        consecutive_losses = 0
        pair_losses = {symbol: 0}

        closed_trades = []
        equity_curve = [{"timestamp": bars_15m[0]["date"], "equity": equity, "drawdown_pct": 0.0}]

        active_position: Optional[Position] = None
        pos_take_profit: Optional[float] = None
        bars_held = 0

        pending_order: Optional[Dict[str, Any]] = None
        order_age_bars = 0

        # Build funding lookup map by date
        funding_map: Dict[str, float] = {}
        if funding_records:
            for fr in funding_records:
                funding_map[fr["date"][:13]] = fr["funding_rate"]

        # Parse bar timestamps
        parsed_bars = []
        for b in bars_15m:
            dt = datetime.fromisoformat(b["date"].replace("Z", "+00:00")) if isinstance(b["date"], str) else b["date"]
            parsed_bars.append({
                "date": dt,
                "open": float(b["open"]),
                "high": float(b["high"]),
                "low": float(b["low"]),
                "close": float(b["close"]),
                "volume": float(b["volume"]),
            })

        clock = StrictEventClock(parsed_bars[0]["date"])

        # Pre-parse 1h bars with close timestamps for O(1) causal alignment
        parsed_bars_1h = []
        if bars_1h:
            for b in bars_1h:
                b_dt = datetime.fromisoformat(b["date"].replace("Z", "+00:00")) if isinstance(b["date"], str) else b["date"]
                parsed_bars_1h.append({
                    "bar": b,
                    "close_time": b_dt + timedelta(hours=1),
                })
        htf_ptr = 0
        latest_closed_1h_bar = None

        # History buffers for feature computation (at least 50 bars needed for EMA50)
        history_highs = []
        history_lows = []
        history_closes = []

        for i, bar in enumerate(parsed_bars):
            bar_date = bar["date"]
            clock.tick(bar_date)

            history_highs.append(bar["high"])
            history_lows.append(bar["low"])
            history_closes.append(bar["close"])

            # 1. EVALUATE ACTIVE POSITION EXITS FIRST (Causal Intra-Bar Check)
            if active_position is not None:
                bars_held += 1
                pos_exit = None

                # Funding Rate Payment Check (Binance Futures pays funding at 00:00, 08:00, 16:00 UTC)
                if bar_date.hour in (0, 8, 16) and bar_date.minute == 0:
                    key = bar_date.isoformat()[:13]
                    f_rate = funding_map.get(key, 0.0001)  # Default nominal 0.01% if unrecorded
                    funding_fee = active_position.size * bar["close"] * f_rate
                    if active_position.side == SignalDirection.LONG:
                        active_position.accumulated_funding += funding_fee
                    else:
                        active_position.accumulated_funding -= funding_fee

                # Check Stop Loss & Take Profit
                high_p = bar["high"]
                low_p = bar["low"]
                open_p = bar["open"]

                is_long = active_position.side == SignalDirection.LONG
                sl_price = active_position.current_stop_loss
                tp_price = pos_take_profit

                sl_hit = (low_p <= sl_price) if is_long else (high_p >= sl_price)
                tp_hit = (tp_price is not None) and ((high_p >= tp_price) if is_long else (low_p <= tp_price))

                # PESSIMISTIC CONSERVATIVE POLICY:
                # If both SL and TP are breached in the same bar, Stop Loss triggers FIRST!
                if sl_hit:
                    # Taker exit with adverse slippage
                    slip = self.config.slippage_model.taker_slippage_pct / 100.0
                    fill_p = (sl_price * (1.0 - slip)) if is_long else (sl_price * (1.0 + slip))
                    gross_pnl = (fill_p - active_position.entry_price) * active_position.size if is_long else (active_position.entry_price - fill_p) * active_position.size
                    fee = fill_p * active_position.size * (self.config.fee_model.taker_fee_pct / 100.0)
                    pos_exit = {"reason": "stop_loss", "exit_price": fill_p, "pnl": gross_pnl, "fee": fee}

                elif tp_hit and tp_price is not None:
                    # Maker exit at limit TP price
                    fill_p = tp_price
                    gross_pnl = (fill_p - active_position.entry_price) * active_position.size if is_long else (active_position.entry_price - fill_p) * active_position.size
                    fee = fill_p * active_position.size * (self.config.fee_model.maker_fee_pct / 100.0)
                    pos_exit = {"reason": "take_profit", "exit_price": fill_p, "pnl": gross_pnl, "fee": fee}

                if pos_exit:
                    net_pnl = pos_exit["pnl"] - (active_position.accumulated_fees + pos_exit["fee"]) - active_position.accumulated_funding
                    stake = (active_position.size * active_position.entry_price) / active_position.leverage
                    profit_pct = (net_pnl / stake) * 100.0 if stake > 0 else 0.0

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
                        "open_date": bar_date - timedelta(minutes=15 * bars_held),
                        "close_date": bar_date,
                        "profit_pct": profit_pct,
                        "profit_abs": net_pnl,
                        "gross_pnl": pos_exit["pnl"],
                        "stake_amount": stake,
                        "fee_cost": active_position.accumulated_fees + pos_exit["fee"],
                        "funding_cost": active_position.accumulated_funding,
                        "duration_min": bars_held * 15,
                        "exit_reason": pos_exit["reason"],
                        "is_short": 1 if not is_long else 0,
                        "entry_price": active_position.entry_price,
                        "exit_price": pos_exit["exit_price"],
                    })

                    active_position = None
                    pos_take_profit = None
                    bars_held = 0

            # Record equity snapshot
            dd_pct = ((peak_equity - equity) / peak_equity * 100.0) if peak_equity > 0 else 0.0
            equity_curve.append({"timestamp": bar_date.isoformat(), "equity": equity, "drawdown_pct": dd_pct})

            # 2. CHECK PENDING ORDER FILLS & TIMEOUTS
            if pending_order is not None and active_position is None:
                order_age_bars += 1
                req = pending_order["request"]
                # Limit order fills if bar traded through price
                can_fill = (bar["low"] <= req.price) if req.side == OrderSide.BUY else (bar["high"] >= req.price)

                if can_fill:
                    # Maker fill
                    fee = req.price * req.amount * (self.config.fee_model.maker_fee_pct / 100.0)
                    active_position = Position(
                        position_id=f"POS_{i}",
                        symbol=symbol,
                        side=SignalDirection.LONG if req.side == OrderSide.BUY else SignalDirection.SHORT,
                        size=req.amount,
                        entry_price=req.price,
                        current_stop_loss=req.stop_loss,
                        leverage=req.leverage,
                        accumulated_fees=fee,
                    )
                    pos_take_profit = pending_order["take_profit"]
                    margin_used = (req.amount * req.price) / req.leverage
                    available_balance -= margin_used
                    pending_order = None
                    order_age_bars = 0
                elif order_age_bars >= self.config.unfilled_timeout_bars:
                    # Expire unfilled limit order
                    pending_order = None
                    order_age_bars = 0

            # 3. EVALUATE STRATEGY INTENT ON COMPLETED CLOSED BARS
            # Requires at least 50 historical closed bars for EMA50
            if i >= 50 and active_position is None and pending_order is None:
                closed_highs = history_highs[:i]
                closed_lows = history_lows[:i]
                closed_closes = history_closes[:i]

                # Strict boundary assertion: exactly i closed bars
                assert len(closed_closes) == i

                # Compute causal ATR on recent closed bars (80 bars is plenty for ATR 14)
                window_atr = min(i, 80)
                atr_val = compute_closed_candle_atr(
                    closed_highs[-window_atr:],
                    closed_lows[-window_atr:],
                    closed_closes[-window_atr:],
                    period=14
                )

                # Compute causal EMAs
                ema20_val = sum(closed_closes[-20:]) / 20.0
                ema50_val = sum(closed_closes[-50:]) / 50.0

                # Compute causal Stochastics (14)
                recent_low = min(closed_lows[-14:])
                recent_high = max(closed_highs[-14:])
                stoch_k = ((closed_closes[-1] - recent_low) / (recent_high - recent_low) * 100.0) if recent_high > recent_low else 50.0
                stoch_d = stoch_k  # Fast smoothing

                # Causal Swing detection over recent 40 closed bars
                window_sw = min(i, 40)
                swings = detect_swing_points(closed_highs[-window_sw:], closed_lows[-window_sw:], window=2)
                # In local window of length W, the last confirmed bar is at index W - 3 (needs 2 bars right)
                confirmed_swings = filter_confirmed_swings(swings, current_index=window_sw - 3)


                latest_sh = confirmed_swings["swing_highs"][-1].price if confirmed_swings["swing_highs"] else None
                latest_sl = confirmed_swings["swing_lows"][-1].price if confirmed_swings["swing_lows"] else None

                # Multi-Timeframe Alignment: Fetch strictly closed 1h bar using causal pointer
                htf_bias = "NEUTRAL"
                if parsed_bars_1h:
                    while htf_ptr < len(parsed_bars_1h) and parsed_bars_1h[htf_ptr]["close_time"] <= bar_date:
                        latest_closed_1h_bar = parsed_bars_1h[htf_ptr]["bar"]
                        htf_ptr += 1
                    if latest_closed_1h_bar:
                        htf_bias = "BULLISH" if latest_closed_1h_bar["close"] > latest_closed_1h_bar["open"] else "BEARISH"

                # Compute causal RSI & ADX on closed candles
                window_ind = min(i, 80)
                rsi_val = compute_closed_candle_rsi(closed_closes[-window_ind:], period=14)
                adx_val = compute_closed_candle_adx(
                    closed_highs[-window_ind:],
                    closed_lows[-window_ind:],
                    closed_closes[-window_ind:],
                    period=14,
                )

                features = {
                    "ema20": ema20_val,
                    "ema50": ema50_val,
                    "rsi": rsi_val,
                    "adx": adx_val,
                    "btc_rsi": 50.0,
                    "eth_rsi": 50.0,
                    "stoch_k": stoch_k,
                    "stoch_d": stoch_d,
                    "volume": bar["volume"],
                    "volume_avg": sum(b["volume"] for b in parsed_bars[i-20:i]) / 20.0,
                    "swing_high": latest_sh,
                    "swing_low": latest_sl,
                    "atr": atr_val,
                }

                regime_context = RegimeContext(
                    regime=MarketRegimeType.TRENDING_BULL if ema20_val > ema50_val else MarketRegimeType.TRENDING_BEAR,
                    trend_strength_adx=adx_val,
                    volatility_atr=atr_val,
                    volatility_percentile=50.0,
                    htf_bias=htf_bias,
                    confidence=80.0,
                )

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
                        current_time=bar_date,
                        atr_multiplier=atr_multiplier,
                    )

                    if risk_eval.is_approved:
                        side = OrderSide.BUY if intent.direction == SignalDirection.LONG else OrderSide.SELL
                        order_req = OrderRequest(
                            client_order_id=f"CNMS_TRUE_{i}",
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
            "equity_curve": equity_curve,
            "final_equity": equity,
        }


def export_experiment_artifacts(output_dir: str, result: Dict[str, Any], metadata: Dict[str, Any]):
    """Exports full suite of experiment artifacts: metadata, trades.csv, metrics.json, equity_curve.csv, report.md."""
    os.makedirs(output_dir, exist_ok=True)

    # 1. metadata.json
    with open(os.path.join(output_dir, "metadata.json"), "w") as f:
        json.dump(metadata, f, indent=2)

    # 2. metrics.json
    with open(os.path.join(output_dir, "metrics.json"), "w") as f:
        json.dump(result["metrics"], f, indent=2, default=str)

    # 3. trades.csv
    trades_path = os.path.join(output_dir, "trades.csv")
    closed_trades = result.get("closed_trades", [])
    if closed_trades:
        keys = list(closed_trades[0].keys())
        with open(trades_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            for t in closed_trades:
                writer.writerow(t)

    # 4. equity_curve.csv
    eq_path = os.path.join(output_dir, "equity_curve.csv")
    eq_curve = result.get("equity_curve", [])
    if eq_curve:
        keys = list(eq_curve[0].keys())
        with open(eq_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            for row in eq_curve:
                writer.writerow(row)

    # 5. report.md
    m = result["metrics"]
    report_content = f"""# TRUE BAR-LEVEL REPLAY EXPERIMENT REPORT: {metadata.get('experiment_id', 'EXPERIMENT')}

**Strategy:** {metadata.get('strategy_name', 'N/A')}  
**Execution Timeframe:** 15m (Bar-by-Bar Replay)  
**Information Boundary:** Strict (t <= T, Zero Future Leakage)  
**Execution Model:** MODELED Limit Entry + Taker Stop-Loss with Adverse Slippage  
**Date Range:** {metadata.get('date_range', '2026-06-25 to 2026-10-02')}  

## Performance Scorecard
- **Total Trades:** {m.get('total_trades', 0)}
- **Win Rate:** {m.get('win_rate', 0.0):.2f}% ({m.get('win_count', 0)} W / {m.get('loss_count', 0)} L)
- **Net Realized PnL:** {m.get('total_net_pnl', 0.0):.2f} USDT
- **Profit Factor:** {m.get('profit_factor', 0.0):.3f}
- **Expectancy:** {m.get('expectancy_pct', 0.0):.3f}% per trade
- **Max Drawdown:** {m.get('max_drawdown_pct', 0.0):.2f}% ({m.get('max_drawdown_abs', 0.0):.2f} USDT)
- **Max Consecutive Losses:** {m.get('max_consecutive_losses', 0)}
- **Total Commissions Paid:** {m.get('total_fees', 0.0):.4f} USDT
- **Total Capital Turnover:** {m.get('total_turnover', 0.0):.2f} USDT
- **Average Trade Duration:** {m.get('avg_duration_minutes', 0.0):.1f} minutes
"""
    with open(os.path.join(output_dir, "report.md"), "w") as f:
        f.write(report_content)
