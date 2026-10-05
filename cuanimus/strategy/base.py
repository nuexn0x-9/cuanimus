"""
CUANIMUS Strategy Engine Base Interface.
"""
from abc import ABC, abstractmethod
from typing import Dict
from cuanimus.common.types import TradeIntent, RegimeContext

class BaseStrategy(ABC):
    @property
    @abstractmethod
    def strategy_id(self) -> str:
        pass

    @property
    @abstractmethod
    def timeframe(self) -> str:
        pass

    @abstractmethod
    def evaluate_intent(
        self,
        symbol: str,
        current_candle: Dict[str, float],
        features: Dict[str, float],
        regime: RegimeContext,
    ) -> TradeIntent:
        pass

