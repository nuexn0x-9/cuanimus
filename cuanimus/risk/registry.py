"""
CUANIMUS Risk Profile Registry & Risk Engine Factory.
Allows configuring and extending risk management frameworks independently of strategy logic.
"""
from typing import Dict, Any, Optional, List
from cuanimus.risk.engine import RiskEngine
from cuanimus.config.models import RiskConfig


class RiskProfileRegistry:
    """Registry for pre-configured risk profiles and risk engine instances."""
    _profiles: Dict[str, RiskConfig] = {}

    @classmethod
    def register(cls, name: str, config: RiskConfig):
        cls._profiles[name.lower()] = config

    @classmethod
    def get_config(cls, name: str) -> RiskConfig:
        clean_name = name.lower()
        if clean_name not in cls._profiles:
            raise KeyError(f"Risk profile '{name}' not found. Available: {list(cls._profiles.keys())}")
        return cls._profiles[clean_name]

    @classmethod
    def build_engine(cls, config: RiskConfig) -> RiskEngine:
        """Instantiates a RiskEngine from a validated RiskConfig object."""
        return RiskEngine(
            base_risk_pct=config.risk_per_trade_pct,
            max_leverage=config.max_leverage,
            max_daily_loss_pct=config.max_daily_loss_pct,
            max_drawdown_pct=config.max_drawdown_pct,
            max_pair_exposure_pct=config.max_pair_exposure_pct,
            max_total_exposure_pct=config.max_total_exposure_pct,
            consecutive_loss_pair_threshold=config.consecutive_loss_pair_threshold,
            consecutive_loss_pair_cooldown_hours=config.consecutive_loss_pair_cooldown_hours,
            consecutive_loss_portfolio_threshold=config.consecutive_loss_portfolio_threshold,
            consecutive_loss_portfolio_cooldown_hours=config.consecutive_loss_portfolio_cooldown_hours,
        )

    @classmethod
    def list_profiles(cls) -> List[Dict[str, Any]]:
        results = []
        for name, cfg in cls._profiles.items():
            results.append({
                "profile_name": name,
                "risk_per_trade_pct": cfg.risk_per_trade_pct,
                "max_leverage": cfg.max_leverage,
                "max_daily_loss_pct": cfg.max_daily_loss_pct,
                "max_drawdown_pct": cfg.max_drawdown_pct,
            })
        return results


def register_builtin_risk_profiles():
    # 1. Conservative
    RiskProfileRegistry.register(
        "conservative",
        RiskConfig(
            profile_name="conservative",
            risk_per_trade_pct=0.5,
            max_leverage=3.0,
            max_daily_loss_pct=1.5,
            max_drawdown_pct=10.0,
            max_pair_exposure_pct=20.0,
            max_total_exposure_pct=50.0,
            consecutive_loss_pair_threshold=2,
            consecutive_loss_pair_cooldown_hours=6.0,
            consecutive_loss_portfolio_threshold=3,
            consecutive_loss_portfolio_cooldown_hours=24.0,
            drawdown_leverage_throttle_threshold_pct=6.0,
            drawdown_throttled_leverage=1.5,
        ),
    )

    # 2. Balanced
    RiskProfileRegistry.register(
        "balanced",
        RiskConfig(
            profile_name="balanced",
            risk_per_trade_pct=1.0,
            max_leverage=5.0,
            max_daily_loss_pct=3.0,
            max_drawdown_pct=15.0,
            max_pair_exposure_pct=30.0,
            max_total_exposure_pct=80.0,
            consecutive_loss_pair_threshold=3,
            consecutive_loss_pair_cooldown_hours=4.0,
            consecutive_loss_portfolio_threshold=5,
            consecutive_loss_portfolio_cooldown_hours=12.0,
            drawdown_leverage_throttle_threshold_pct=10.0,
            drawdown_throttled_leverage=2.0,
        ),
    )

    # 3. Aggressive
    RiskProfileRegistry.register(
        "aggressive",
        RiskConfig(
            profile_name="aggressive",
            risk_per_trade_pct=1.5,
            max_leverage=7.0,
            max_daily_loss_pct=5.0,
            max_drawdown_pct=20.0,
            max_pair_exposure_pct=40.0,
            max_total_exposure_pct=95.0,
            consecutive_loss_pair_threshold=4,
            consecutive_loss_pair_cooldown_hours=2.0,
            consecutive_loss_portfolio_threshold=6,
            consecutive_loss_portfolio_cooldown_hours=6.0,
            drawdown_leverage_throttle_threshold_pct=12.0,
            drawdown_throttled_leverage=3.0,
        ),
    )


# Automatically initialize built-in risk profiles
register_builtin_risk_profiles()
