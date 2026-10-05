# Developer Guide: Building an Exchange Adapter

**Document Version:** 1.0.0  
**Target Audience:** Integration Engineers & Systems Architects  
**Status:** COMPLETE  
**Date:** October 2026  

---

## 1. Architecture Overview

In CUANIMUS, exchange connectivity is completely isolated from trading logic. Neither the strategy nor the risk engine communicates with exchange APIs directly.

```
[Strategy] ──► [Risk Engine] ──► [Order Lifecycle FSM] ──► [Exchange Adapter] ──► [Exchange REST / WS]
```

---

## 2. Exchange Adapter Interface

An exchange adapter must implement standard lifecycle methods:

```python
from abc import ABC, abstractmethod
from typing import Dict, Any, List
from cuanimus.common.types import OrderRequest, OrderResponse, Position

class ExchangeAdapter(ABC):
    @abstractmethod
    def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Fetches completed historical candlesticks."""
        pass

    @abstractmethod
    def submit_order(self, request: OrderRequest) -> OrderResponse:
        """Translates OrderRequest into exchange payload and submits."""
        pass

    @abstractmethod
    def cancel_order(self, client_order_id: str, symbol: str) -> bool:
        """Cancels open order by client order identifier."""
        pass

    @abstractmethod
    def fetch_open_positions(self) -> List[Position]:
        """Fetches active futures positions."""
        pass

    @abstractmethod
    def fetch_available_balance(self, quote_asset: str = "USDT") -> float:
        """Fetches free margin balance."""
        pass
```

---

## 3. Configuration & Secret Management

Create `config/exchanges/bybit_futures.yaml`:

```yaml
exchange:
  provider: bybit
  market_type: futures
  environment: testnet
  quote_asset: USDT
  maker_fee_pct: 0.02
  taker_fee_pct: 0.055
  rate_limit_per_minute: 1200
  timeout_seconds: 10.0
  recv_window_ms: 5000
```

> [!IMPORTANT]
> **Never put API keys or secrets in exchange YAML files!**  
> Adapters must read API keys from environment variables:
> - `BYBIT_API_KEY`
> - `BYBIT_API_SECRET`
