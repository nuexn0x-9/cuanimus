"""
CUANIMUS Binance Exchange Adapter
Handles all calls to Binance Futures public API.
NEVER exposes API keys to browser/frontend.
"""
import os
import time
import logging
import threading
import urllib.request
import urllib.error
import json as json_lib
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# Binance Futures base URL
BINANCE_FAPI_BASE = "https://fapi.binance.com"

def to_binance_symbol(symbol: str) -> str:
    """Convert internal symbol format to Binance symbol format.
    e.g. ETH/USDT:USDT -> ETHUSDT, BTC/USDT:USDT -> BTCUSDT
    """
    base = symbol.split(":")[0]  # ETH/USDT
    return base.replace("/", "").upper()  # ETHUSDT

def from_binance_symbol(symbol: str) -> str:
    """Convert Binance symbol to internal format (e.g. ETHUSDT -> ETH/USDT:USDT)."""
    if symbol.endswith("USDT"):
        base = symbol[:-4]
        return f"{base}/USDT:USDT"
    return symbol

# Timeframe mapping: internal -> Binance interval
TIMEFRAME_MAP = {
    "1m": "1m", "3m": "3m", "5m": "5m", "15m": "15m", "30m": "30m",
    "1h": "1h", "2h": "2h", "4h": "4h", "6h": "6h", "8h": "8h", "12h": "12h",
    "1d": "1d", "3d": "3d", "1w": "1w", "1M": "1M",
}


class BinanceAPIError(Exception):
    """Raised when Binance API returns an error or is unreachable."""
    pass


class BinancePublicAdapter:
    """
    Handles public Binance Futures API calls.
    No authentication required for public market data.
    Implements in-memory thread-safe cache to conserve rate limit.
    """

    _cache: Dict[str, Dict] = {}
    _cache_lock = threading.Lock()

    # Cache TTLs in seconds
    TICKER_TTL = 5        # 5s for single ticker
    WATCHLIST_TTL = 10    # 10s for full watchlist
    KLINES_TTL = 15       # 15s for candles
    EXCHANGE_INFO_TTL = 3600  # 1h for exchange info

    def __init__(self, timeout: int = 10):
        self.timeout = timeout
        self.base_url = BINANCE_FAPI_BASE

    def _get(self, path: str, params: Optional[Dict] = None) -> Any:
        """Make a GET request to Binance Futures API."""
        url = f"{self.base_url}{path}"
        if params:
            qs = "&".join(f"{k}={v}" for k, v in params.items())
            url = f"{url}?{qs}"
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "Accept": "application/json",
                    "User-Agent": "CUANIMUS-Trading-Engine/1.0"
                }
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = resp.read().decode("utf-8")
                return json_lib.loads(body)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            raise BinanceAPIError(f"HTTP {e.code} from Binance: {body[:200]}")
        except urllib.error.URLError as e:
            raise BinanceAPIError(f"Network error reaching Binance: {e.reason}")
        except Exception as e:
            raise BinanceAPIError(f"Unexpected error: {e}")

    def _cached(self, key: str, ttl: float, fetcher):
        """Return cached value if fresh, else call fetcher() and cache result."""
        with self._cache_lock:
            entry = self._cache.get(key)
            if entry and (time.time() - entry["ts"]) < ttl:
                return entry["data"]
        # Fetch outside lock
        data = fetcher()
        with self._cache_lock:
            self._cache[key] = {"data": data, "ts": time.time()}
        return data

    def get_ticker(self, symbol: str) -> Dict[str, Any]:
        """
        Get 24hr ticker stats for a symbol.
        symbol: internal format (e.g. ETH/USDT:USDT) or Binance format (ETHUSDT)
        """
        b_sym = to_binance_symbol(symbol) if "/" in symbol else symbol.upper()
        cache_key = f"ticker:{b_sym}"
        def fetch():
            data = self._get("/fapi/v1/ticker/24hr", {"symbol": b_sym})
            return self._normalize_ticker(data, symbol)
        return self._cached(cache_key, self.TICKER_TTL, fetch)

    def get_watchlist_tickers(self, symbols: List[str]) -> List[Dict[str, Any]]:
        """
        Get 24hr ticker stats for multiple symbols.
        """
        cache_key = "watchlist_tickers:" + ",".join(sorted(symbols))
        def fetch():
            try:
                all_tickers = self._get("/fapi/v1/ticker/24hr")
                b_syms = {to_binance_symbol(s): s for s in symbols}
                result = []
                for t in all_tickers:
                    sym = t.get("symbol")
                    if sym in b_syms:
                        internal = b_syms[sym]
                        result.append(self._normalize_ticker(t, internal))
                # Maintain order of requested symbols
                order_map = {s: i for i, s in enumerate(symbols)}
                result.sort(key=lambda x: order_map.get(x["symbol"], 999))
                return result
            except BinanceAPIError as err:
                logger.warning(f"Bulk ticker fetch error: {err}, falling back to single calls")
                result = []
                for sym in symbols:
                    try:
                        result.append(self.get_ticker(sym))
                    except BinanceAPIError as e:
                        logger.warning(f"Failed ticker for {sym}: {e}")
                return result
        return self._cached(cache_key, self.WATCHLIST_TTL, fetch)

    def _normalize_ticker(self, data: Dict, internal_symbol: str) -> Dict[str, Any]:
        """Normalize Binance ticker response to internal format."""
        price = float(data.get("lastPrice", 0))
        price_change_pct = float(data.get("priceChangePercent", 0))
        volume = float(data.get("volume", 0))
        quote_volume = float(data.get("quoteVolume", 0))
        high = float(data.get("highPrice", 0))
        low = float(data.get("lowPrice", 0))
        count = int(data.get("count", 0))
        return {
            "symbol": internal_symbol,
            "binance_symbol": data.get("symbol", ""),
            "price": round(price, 8 if price < 0.001 else (4 if price < 1 else 2)),
            "change_24h_pct": round(price_change_pct, 2),
            "volume_24h_base": round(volume, 2),
            "volume_24h_usd": round(quote_volume, 2),
            "high_24h": round(high, 2),
            "low_24h": round(low, 2),
            "trade_count_24h": count,
            "timestamp": int(data.get("closeTime", time.time() * 1000)),
        }

    def get_klines(self, symbol: str, timeframe: str = "15m", limit: int = 80) -> List[Dict]:
        """
        Get OHLCV candlestick data from Binance Futures.
        """
        b_sym = to_binance_symbol(symbol) if "/" in symbol else symbol.upper()
        interval = TIMEFRAME_MAP.get(timeframe, timeframe)
        cache_key = f"klines:{b_sym}:{interval}:{limit}"

        def fetch():
            data = self._get("/fapi/v1/klines", {
                "symbol": b_sym,
                "interval": interval,
                "limit": min(limit, 1000),
            })
            candles = []
            for k in data:
                ts = int(k[0])
                dt_str = time.strftime("%Y-%m-%d %H:%M", time.gmtime(ts / 1000))
                candles.append({
                    "date": dt_str,
                    "timestamp": ts,
                    "open": float(k[1]),
                    "high": float(k[2]),
                    "low": float(k[3]),
                    "close": float(k[4]),
                    "volume": float(k[5]),
                    "quote_volume": float(k[7]),
                    "trades": int(k[8]),
                })
            return candles

        return self._cached(cache_key, self.KLINES_TTL, fetch)

    def get_exchange_info(self) -> Dict[str, Any]:
        """
        Get all active Binance Futures USDT perpetual pairs.
        Cached for 1 hour.
        """
        def fetch():
            data = self._get("/fapi/v1/exchangeInfo")
            usdt_perps = []
            for s in data.get("symbols", []):
                if s.get("quoteAsset") == "USDT" and s.get("contractType") == "PERPETUAL" and s.get("status") == "TRADING":
                    step_size = round(10.0 ** (-int(s.get("quantityPrecision", 3))), 8)
                    tick_size = round(10.0 ** (-int(s.get("pricePrecision", 2))), 8)
                    min_qty = step_size
                    min_notional = 5.0
                    for f in s.get("filters", []):
                        ftype = f.get("filterType")
                        if ftype == "LOT_SIZE":
                            step_size = float(f.get("stepSize", step_size))
                            min_qty = float(f.get("minQty", min_qty))
                        elif ftype == "PRICE_FILTER":
                            tick_size = float(f.get("tickSize", tick_size))
                        elif ftype in ("MIN_NOTIONAL", "NOTIONAL"):
                            min_notional = float(f.get("notional", min_notional))
                    usdt_perps.append({
                        "symbol": s["symbol"],
                        "internal": from_binance_symbol(s["symbol"]),
                        "base": s["baseAsset"],
                        "quote": s["quoteAsset"],
                        "status": s["status"],
                        "price_precision": s.get("pricePrecision", 2),
                        "qty_precision": s.get("quantityPrecision", 3),
                        "step_size": step_size,
                        "min_qty": min_qty,
                        "tick_size": tick_size,
                        "min_notional": min_notional,
                    })
            return {
                "pairs": usdt_perps,
                "total": len(usdt_perps),
                "timestamp": int(time.time() * 1000),
            }
        return self._cached("exchange_info", self.EXCHANGE_INFO_TTL, fetch)

    def get_symbol_filter(self, symbol: str) -> Dict[str, float]:
        """Returns step_size, min_qty, tick_size, min_notional dynamically for a symbol."""
        b_sym = to_binance_symbol(symbol) if "/" in symbol else symbol.upper()
        try:
            info = self.get_exchange_info()
            for p in info.get("pairs", []):
                if p["symbol"] == b_sym or p.get("internal") == symbol:
                    return {
                        "step_size": float(p.get("step_size", 0.001)),
                        "min_qty": float(p.get("min_qty", 0.001)),
                        "tick_size": float(p.get("tick_size", 0.01)),
                        "min_notional": float(p.get("min_notional", 5.0)),
                    }
        except Exception as e:
            logger.warning(f"Could not load symbol filter for {symbol}: {e}")
        return {"step_size": 0.001, "min_qty": 0.001, "tick_size": 0.01, "min_notional": 5.0}

    def get_order_book(self, symbol: str, limit: int = 10) -> Dict[str, Any]:
        """Get order book depth."""
        b_sym = to_binance_symbol(symbol) if "/" in symbol else symbol.upper()
        cache_key = f"orderbook:{b_sym}:{limit}"
        def fetch():
            data = self._get("/fapi/v1/depth", {"symbol": b_sym, "limit": limit})
            return {
                "symbol": symbol,
                "bids": [[float(p), float(q)] for p, q in data.get("bids", [])],
                "asks": [[float(p), float(q)] for p, q in data.get("asks", [])],
                "timestamp": int(time.time() * 1000),
            }
        return self._cached(cache_key, 3, fetch)

    def get_mark_price(self, symbol: str) -> Dict[str, Any]:
        """Get mark price and funding rate."""
        b_sym = to_binance_symbol(symbol) if "/" in symbol else symbol.upper()
        cache_key = f"mark:{b_sym}"
        def fetch():
            data = self._get("/fapi/v1/premiumIndex", {"symbol": b_sym})
            return {
                "symbol": symbol,
                "mark_price": float(data.get("markPrice", 0)),
                "index_price": float(data.get("indexPrice", 0)),
                "funding_rate": float(data.get("lastFundingRate", 0)),
                "next_funding_time": int(data.get("nextFundingTime", 0)),
                "timestamp": int(data.get("time", time.time() * 1000)),
            }
        return self._cached(cache_key, 5, fetch)


# Singleton
_public_adapter: Optional[BinancePublicAdapter] = None
_adapter_lock = threading.Lock()

def get_binance_adapter() -> BinancePublicAdapter:
    """Get or initialize the singleton BinancePublicAdapter."""
    global _public_adapter
    if _public_adapter is None:
        with _adapter_lock:
            if _public_adapter is None:
                _public_adapter = BinancePublicAdapter()
    return _public_adapter
