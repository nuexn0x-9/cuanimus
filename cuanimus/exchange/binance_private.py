"""
CUANIMUS Binance Private Exchange Adapter
Handles authenticated Binance Futures API operations (Account, Positions, Balance, Orders).
Supports both TESTNET and LIVE environments using HMAC-SHA256 signatures.
Zero credentials exposure to browser/frontend.
"""
import os
import time
import hmac
import hashlib
import logging
import threading
import urllib.request
import urllib.parse
import urllib.error
import json as json_lib
from typing import Dict, Any, List, Optional, Tuple

from cuanimus.exchange.binance_adapter import to_binance_symbol, from_binance_symbol, BinanceAPIError

logger = logging.getLogger(__name__)

# Base URLs
BINANCE_TESTNET_FAPI_BASE = "https://testnet.binancefuture.com"
BINANCE_LIVE_FAPI_BASE = "https://fapi.binance.com"


def get_binance_credentials(environment: str = "testnet") -> Tuple[Optional[str], Optional[str]]:
    """
    Resolves API credentials based on environment.
    Strictly isolates testnet and live variables while supporting fallback.
    """
    env = (environment or "testnet").lower().strip()
    if env == "live":
        api_key = os.environ.get("BINANCE_LIVE_API_KEY") or os.environ.get("BINANCE_API_KEY")
        api_secret = os.environ.get("BINANCE_LIVE_API_SECRET") or os.environ.get("BINANCE_API_SECRET")
    else:
        api_key = os.environ.get("BINANCE_TESTNET_API_KEY") or os.environ.get("BINANCE_API_KEY")
        api_secret = os.environ.get("BINANCE_TESTNET_API_SECRET") or os.environ.get("BINANCE_API_SECRET")
    return api_key, api_secret


class BinancePrivateAdapter:
    """
    Authenticated adapter for Binance Futures.
    Manages signed requests (HMAC-SHA256), order lifecycle, account balance,
    and exchange-level protective stop-loss/take-profit orders.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        environment: str = "testnet",
        timeout: int = 10,
        recv_window: int = 5000,
    ):
        self.environment = environment.lower().strip()
        self.timeout = timeout
        self.recv_window = recv_window

        # Resolve credentials if not explicitly passed
        resolved_key, resolved_secret = get_binance_credentials(self.environment)
        self.api_key = api_key or resolved_key
        self.api_secret = api_secret or resolved_secret

        if self.environment == "live":
            self.base_url = BINANCE_LIVE_FAPI_BASE
        else:
            self.base_url = BINANCE_TESTNET_FAPI_BASE

    def has_credentials(self) -> bool:
        """Checks if valid non-empty API credentials are provided."""
        return bool(self.api_key and self.api_secret and len(self.api_key.strip()) >= 16)

    def _sign_payload(self, params: Dict[str, Any]) -> str:
        """Appends timestamp, recvWindow, and signs parameters using HMAC-SHA256."""
        if not self.api_secret:
            raise BinanceAPIError("Cannot sign Binance request: API Secret is missing.")

        clean_params = {k: v for k, v in params.items() if v is not None}
        clean_params["timestamp"] = int(time.time() * 1000)
        clean_params["recvWindow"] = self.recv_window

        query_str = urllib.parse.urlencode(clean_params)
        signature = hmac.new(
            self.api_secret.encode("utf-8"),
            query_str.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        return f"{query_str}&signature={signature}"

    def _request(self, method: str, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Executes signed authenticated HTTP request to Binance Futures."""
        if not self.has_credentials():
            raise BinanceAPIError(f"Binance {self.environment.upper()} credentials missing or invalid.")

        params = params or {}
        signed_qs = self._sign_payload(params)
        headers = {
            "Accept": "application/json",
            "User-Agent": "CUANIMUS-Autonomous-Trading/2.0",
            "X-MBX-APIKEY": self.api_key,
        }

        if method in ("GET", "DELETE"):
            url = f"{self.base_url}{path}?{signed_qs}"
            req_data = None
        else:
            url = f"{self.base_url}{path}"
            req_data = signed_qs.encode("utf-8")
            headers["Content-Type"] = "application/x-www-form-urlencoded"

        try:
            req = urllib.request.Request(url, data=req_data, headers=headers, method=method)
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = resp.read().decode("utf-8")
                return json_lib.loads(body)
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            try:
                err_json = json_lib.loads(err_body)
                code = err_json.get("code")
                msg = err_json.get("msg")
                raise BinanceAPIError(f"Binance HTTP {e.code} (Code: {code}): {msg}")
            except Exception:
                raise BinanceAPIError(f"Binance HTTP {e.code}: {err_body[:200]}")
        except urllib.error.URLError as e:
            raise BinanceAPIError(f"Network error contacting Binance {self.environment}: {e.reason}")
        except Exception as e:
            raise BinanceAPIError(f"Unexpected Binance error: {e}")

    # -------------------------------------------------------------------------
    # Account & Portfolio
    # -------------------------------------------------------------------------

    def get_account(self) -> Dict[str, Any]:
        """Fetches account state including margin, equity, and positions (GET /fapi/v2/account)."""
        return self._request("GET", "/fapi/v2/account")

    def get_balance(self) -> List[Dict[str, Any]]:
        """Fetches asset balances (GET /fapi/v2/balance)."""
        return self._request("GET", "/fapi/v2/balance")

    def get_usdt_balance(self) -> Dict[str, float]:
        """Fetches normalized USDT balances."""
        balances = self.get_balance()
        for b in balances:
            if b.get("asset") == "USDT":
                return {
                    "balance": float(b.get("balance", 0.0)),
                    "available_balance": float(b.get("availableBalance", 0.0)),
                    "cross_wallet_balance": float(b.get("crossWalletBalance", 0.0)),
                    "unrealized_pnl": float(b.get("crossUnPnl", 0.0)),
                }
        return {"balance": 0.0, "available_balance": 0.0, "cross_wallet_balance": 0.0, "unrealized_pnl": 0.0}

    def get_positions(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetches position risk and open position state (GET /fapi/v2/positionRisk)."""
        params = {}
        if symbol:
            params["symbol"] = to_binance_symbol(symbol)
        raw = self._request("GET", "/fapi/v2/positionRisk", params)
        res = []
        for p in raw:
            amt = float(p.get("positionAmt", 0.0))
            if abs(amt) > 0 or symbol:
                res.append({
                    "symbol": from_binance_symbol(p.get("symbol", "")),
                    "binance_symbol": p.get("symbol"),
                    "position_amt": amt,
                    "entry_price": float(p.get("entryPrice", 0.0)),
                    "mark_price": float(p.get("markPrice", 0.0)),
                    "unrealized_pnl": float(p.get("unRealizedProfit", 0.0)),
                    "liquidation_price": float(p.get("liquidationPrice", 0.0)),
                    "leverage": int(p.get("leverage", 1)),
                    "margin_type": p.get("marginType", "cross"),
                    "position_side": p.get("positionSide", "BOTH"),
                })
        return res

    def get_position_mode(self) -> bool:
        """Returns True if Dual-Side (Hedge Mode) is enabled, False for One-Way Mode."""
        data = self._request("GET", "/fapi/v1/positionSide/dual")
        return bool(data.get("dualSidePosition", False))

    # -------------------------------------------------------------------------
    # Order Execution Lifecycle
    # -------------------------------------------------------------------------

    def create_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float,
        price: Optional[float] = None,
        stop_price: Optional[float] = None,
        client_order_id: Optional[str] = None,
        time_in_force: Optional[str] = None,
        reduce_only: bool = False,
        close_position: bool = False,
        position_side: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Submits order to Binance Futures (POST /fapi/v1/order).
        Supports MARKET, LIMIT, STOP_MARKET, TAKE_PROFIT_MARKET.
        """
        b_sym = to_binance_symbol(symbol)
        b_side = side.upper().strip()
        b_type = order_type.upper().strip()

        params: Dict[str, Any] = {
            "symbol": b_sym,
            "side": b_side,
            "type": b_type,
        }

        if close_position:
            params["closePosition"] = "true"
        else:
            params["quantity"] = quantity

        if b_type == "LIMIT":
            if price is None:
                raise ValueError("Price is required for LIMIT order")
            params["price"] = price
            params["timeInForce"] = time_in_force or "GTC"
        elif time_in_force:
            params["timeInForce"] = time_in_force

        if b_type in ("STOP_MARKET", "TAKE_PROFIT_MARKET", "STOP", "TAKE_PROFIT"):
            if stop_price is None:
                raise ValueError(f"Stop price is required for {b_type} order")
            params["stopPrice"] = stop_price

        if client_order_id:
            params["newClientOrderId"] = client_order_id

        if reduce_only and not close_position:
            params["reduceOnly"] = "true"

        if position_side:
            params["positionSide"] = position_side.upper()

        return self._request("POST", "/fapi/v1/order", params)

    def cancel_order(
        self,
        symbol: str,
        order_id: Optional[int] = None,
        orig_client_order_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Cancels an order (DELETE /fapi/v1/order)."""
        params: Dict[str, Any] = {"symbol": to_binance_symbol(symbol)}
        if order_id:
            params["orderId"] = order_id
        if orig_client_order_id:
            params["origClientOrderId"] = orig_client_order_id
        return self._request("DELETE", "/fapi/v1/order", params)

    def get_order(
        self,
        symbol: str,
        order_id: Optional[int] = None,
        orig_client_order_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Queries order status (GET /fapi/v1/order)."""
        params: Dict[str, Any] = {"symbol": to_binance_symbol(symbol)}
        if order_id:
            params["orderId"] = order_id
        if orig_client_order_id:
            params["origClientOrderId"] = orig_client_order_id
        return self._request("GET", "/fapi/v1/order", params)

    def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Queries open orders (GET /fapi/v1/openOrders)."""
        params: Dict[str, Any] = {}
        if symbol:
            params["symbol"] = to_binance_symbol(symbol)
        return self._request("GET", "/fapi/v1/openOrders", params)

    def set_leverage(self, symbol: str, leverage: int) -> Dict[str, Any]:
        """Sets initial leverage for a symbol (POST /fapi/v1/leverage)."""
        params = {
            "symbol": to_binance_symbol(symbol),
            "leverage": int(leverage),
        }
        return self._request("POST", "/fapi/v1/leverage", params)

    def set_margin_type(self, symbol: str, margin_type: str = "ISOLATED") -> Dict[str, Any]:
        """Sets margin type (ISOLATED or CROSSED) (POST /fapi/v1/marginType)."""
        params = {
            "symbol": to_binance_symbol(symbol),
            "marginType": margin_type.upper(),
        }
        try:
            return self._request("POST", "/fapi/v1/marginType", params)
        except BinanceAPIError as e:
            # Code -4046 means "No need to change margin type" (already set)
            if "-4046" in str(e) or "No need to change" in str(e):
                return {"code": 200, "msg": "Already set"}
            raise

    # -------------------------------------------------------------------------
    # Preflight Validation
    # -------------------------------------------------------------------------

    def validate_connection(self) -> Dict[str, Any]:
        """
        Performs non-destructive preflight validation of API credentials,
        permissions, and connection latency.
        """
        if not self.has_credentials():
            return {
                "valid": False,
                "environment": self.environment,
                "error": "Credentials missing or empty.",
            }

        start_time = time.time()
        try:
            acc = self.get_account()
            lat_ms = round((time.time() - start_time) * 1000, 2)
            can_trade = acc.get("canTrade", False)
            total_margin = float(acc.get("totalWalletBalance", 0.0))

            return {
                "valid": True,
                "environment": self.environment,
                "endpoint": self.base_url,
                "can_trade": can_trade,
                "total_wallet_balance": total_margin,
                "latency_ms": lat_ms,
                "positions_count": len([p for p in acc.get("positions", []) if abs(float(p.get("positionAmt", 0))) > 0]),
            }
        except Exception as e:
            return {
                "valid": False,
                "environment": self.environment,
                "endpoint": self.base_url,
                "error": str(e),
            }


# Thread-safe Singletons per environment
_private_adapters: Dict[str, BinancePrivateAdapter] = {}
_private_lock = threading.Lock()


def get_binance_private_adapter(environment: str = "testnet") -> BinancePrivateAdapter:
    """Returns singleton BinancePrivateAdapter for the given environment."""
    env = (environment or "testnet").lower().strip()
    global _private_adapters
    with _private_lock:
        if env not in _private_adapters:
            _private_adapters[env] = BinancePrivateAdapter(environment=env)
        return _private_adapters[env]
