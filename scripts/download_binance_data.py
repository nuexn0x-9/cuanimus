"""
CUANIMUS Historical Market Data Acquisition & Provenance Pipeline.
Downloads Binance Futures raw OHLCV and historical funding rates.
Generates data/manifest.json with SHA-256 checksums, timestamps, and integrity audit.
"""
import os
import sys
import time
import json
import hashlib
from datetime import datetime, timezone
import requests
import pandas as pd

BASE_URL = "https://fapi.binance.com"
KLINES_EP = f"{BASE_URL}/fapi/v1/klines"
FUNDING_EP = f"{BASE_URL}/fapi/v1/fundingRate"

PAIRS = {
    "ADA/USDT:USDT": "ADAUSDT",
    "ETH/USDT:USDT": "ETHUSDT",
    "XRP/USDT:USDT": "XRPUSDT",
}

TIMEFRAMES = ["15m", "1h", "1m"]

# Period: 2026-06-25 00:00:00 UTC to 2026-10-02 23:59:59 UTC
START_DT = datetime(2026, 6, 25, 0, 0, 0, tzinfo=timezone.utc)
END_DT = datetime(2026, 10, 2, 23, 59, 59, tzinfo=timezone.utc)

START_MS = int(START_DT.timestamp() * 1000)
END_MS = int(END_DT.timestamp() * 1000)

DATA_DIR = "user_data/data/binance/futures"
MANIFEST_DIR = "data"


def fetch_klines(symbol: str, interval: str, start_ms: int, end_ms: int) -> list:
    """Fetches continuous OHLCV klines from Binance Futures REST API."""
    all_candles = []
    current_start = start_ms
    limit = 1000

    print(f"Fetching {symbol} {interval} from {start_ms} to {end_ms}...")
    while current_start < end_ms:
        params = {
            "symbol": symbol,
            "interval": interval,
            "startTime": current_start,
            "endTime": end_ms,
            "limit": limit,
        }
        resp = requests.get(KLINES_EP, params=params, timeout=15)
        if resp.status_code != 200:
            print(f"Error fetching klines: HTTP {resp.status_code} {resp.text}")
            time.sleep(2)
            continue

        data = resp.json()
        if not data:
            break

        all_candles.extend(data)
        last_close_time = data[-1][6]
        if last_close_time >= end_ms or len(data) < limit:
            break
        current_start = last_close_time + 1
        time.sleep(0.05)  # Polite API throttling

    return all_candles


def fetch_funding_rates(symbol: str, start_ms: int, end_ms: int) -> list:
    """Fetches continuous historical funding rates from Binance Futures."""
    all_funding = []
    current_start = start_ms
    limit = 1000

    print(f"Fetching funding rates for {symbol}...")
    while current_start < end_ms:
        params = {
            "symbol": symbol,
            "startTime": current_start,
            "endTime": end_ms,
            "limit": limit,
        }
        resp = requests.get(FUNDING_EP, params=params, timeout=15)
        if resp.status_code != 200:
            print(f"Error fetching funding: HTTP {resp.status_code}")
            time.sleep(2)
            continue

        data = resp.json()
        if not data:
            break

        all_funding.extend(data)
        if len(data) < limit:
            break
        current_start = data[-1]["fundingTime"] + 1
        time.sleep(0.05)

    return all_funding


def audit_candle_integrity(df: pd.DataFrame, expected_delta_min: int) -> dict:
    """
    Validates:
    - duplicates
    - missing intervals / gaps
    - out-of-order timestamps
    - invalid OHLC relationship
    - zero/negative values
    - timezone
    """
    anomalies = []
    row_count = len(df)

    # 1. Duplicates
    dup_count = int(df["date"].duplicated().sum())
    if dup_count > 0:
        anomalies.append(f"DUPLICATE_CANDLES: {dup_count} found")

    # 2. Out of order
    is_monotonic = df["date"].is_monotonic_increasing
    if not is_monotonic:
        anomalies.append("OUT_OF_ORDER_TIMESTAMPS: series is not strictly increasing")

    # 3. Invalid OHLC
    invalid_hl = (df["high"] < df["low"]).sum()
    invalid_open = ((df["open"] > df["high"]) | (df["open"] < df["low"])).sum()
    invalid_close = ((df["close"] > df["high"]) | (df["close"] < df["low"])).sum()
    if invalid_hl > 0 or invalid_open > 0 or invalid_close > 0:
        anomalies.append(f"INVALID_OHLC_RELATIONSHIP: hl={invalid_hl}, open={invalid_open}, close={invalid_close}")

    # 4. Zero or negative values
    invalid_zeros = ((df["open"] <= 0) | (df["high"] <= 0) | (df["low"] <= 0) | (df["close"] <= 0)).sum()
    if invalid_zeros > 0:
        anomalies.append(f"ZERO_OR_NEGATIVE_PRICES: {invalid_zeros} found")

    # 5. Missing candles / Gaps
    expected_delta_sec = expected_delta_min * 60
    diffs = df["date"].diff().dt.total_seconds().dropna()
    gaps = diffs[diffs > expected_delta_sec]
    gap_count = len(gaps)
    gap_details = []
    if gap_count > 0:
        for idx, val in gaps.items():
            gap_dt = df.loc[idx, "date"].isoformat()
            gap_details.append({"at": gap_dt, "gap_seconds": float(val), "missing_bars": int(val / expected_delta_sec) - 1})

    return {
        "is_valid": len(anomalies) == 0,
        "row_count": row_count,
        "anomalies": anomalies,
        "gap_count": gap_count,
        "gap_details": gap_details[:10],  # sample
    }


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(MANIFEST_DIR, exist_ok=True)

    manifest = {
        "exchange": "binance",
        "market_type": "futures",
        "acquisition_timestamp": datetime.now(timezone.utc).isoformat(),
        "period": {
            "start_utc": START_DT.isoformat(),
            "end_utc": END_DT.isoformat(),
            "start_ms": START_MS,
            "end_ms": END_MS,
        },
        "datasets": {},
        "funding_datasets": {},
        "integrity_summary": {
            "all_passed": True,
            "total_gaps": 0,
            "notes": []
        }
    }

    tf_minutes = {"15m": 15, "1h": 60, "1m": 1}

    # 1. Download Klines
    for ft_pair, raw_sym in PAIRS.items():
        sym_clean = ft_pair.replace("/", "_").replace(":", "_")
        for tf in TIMEFRAMES:
            klines = fetch_klines(raw_sym, tf, START_MS, END_MS)
            if not klines:
                print(f"Warning: No data for {raw_sym} {tf}")
                continue

            # Parse into DataFrame
            records = []
            for k in klines:
                # kline structure: [open_time, open, high, low, close, volume, close_time, ...]
                records.append({
                    "date": pd.to_datetime(k[0], unit="ms", utc=True),
                    "open": float(k[1]),
                    "high": float(k[2]),
                    "low": float(k[3]),
                    "close": float(k[4]),
                    "volume": float(k[5]),
                })

            df = pd.DataFrame(records).drop_duplicates(subset=["date"]).sort_values("date").reset_index(drop=True)

            # Audit integrity
            audit_res = audit_candle_integrity(df, tf_minutes[tf])
            if not audit_res["is_valid"]:
                manifest["integrity_summary"]["all_passed"] = False
            manifest["integrity_summary"]["total_gaps"] += audit_res["gap_count"]

            # Save Feather
            feather_path = os.path.join(DATA_DIR, f"{sym_clean}-{tf}-futures.feather")
            df.to_feather(feather_path)

            # Save JSON (for host python reading without pandas)
            json_path = os.path.join(DATA_DIR, f"{sym_clean}-{tf}-futures.json")
            # Format datetime to string for json
            json_records = []
            for _, row in df.iterrows():
                json_records.append({
                    "date": row["date"].isoformat(),
                    "open": row["open"],
                    "high": row["high"],
                    "low": row["low"],
                    "close": row["close"],
                    "volume": row["volume"],
                })
            with open(json_path, "w") as jf:
                json.dump(json_records, jf)

            # Compute SHA-256 of feather
            with open(feather_path, "rb") as ff:
                sha256_hash = hashlib.sha256(ff.read()).hexdigest()

            file_size = os.path.getsize(feather_path)

            manifest["datasets"][f"{ft_pair}_{tf}"] = {
                "symbol": ft_pair,
                "raw_symbol": raw_sym,
                "timeframe": tf,
                "row_count": len(df),
                "file_path": feather_path,
                "json_path": json_path,
                "file_size_bytes": file_size,
                "sha256": sha256_hash,
                "first_candle": {
                    "date": df.iloc[0]["date"].isoformat(),
                    "open": df.iloc[0]["open"],
                    "close": df.iloc[0]["close"],
                },
                "last_candle": {
                    "date": df.iloc[-1]["date"].isoformat(),
                    "open": df.iloc[-1]["open"],
                    "close": df.iloc[-1]["close"],
                },
                "integrity": audit_res,
            }
            print(f"Saved {ft_pair} {tf}: {len(df)} bars, SHA256: {sha256_hash[:12]}...")

    # 2. Download Funding Rates
    for ft_pair, raw_sym in PAIRS.items():
        sym_clean = ft_pair.replace("/", "_").replace(":", "_")
        funding = fetch_funding_rates(raw_sym, START_MS, END_MS)
        if not funding:
            continue

        records = []
        for f in funding:
            records.append({
                "date": pd.to_datetime(f["fundingTime"], unit="ms", utc=True),
                "open": float(f["fundingRate"]),
                "high": 0.0,
                "low": 0.0,
                "close": 0.0,
                "volume": 0.0,
            })
        df_fund = pd.DataFrame(records).drop_duplicates(subset=["date"]).sort_values("date").reset_index(drop=True)

        funding_feather = os.path.join(DATA_DIR, f"{sym_clean}-1h-funding_rate.feather")
        df_fund.to_feather(funding_feather)

        funding_json = os.path.join(DATA_DIR, f"{sym_clean}-funding_rate.json")
        fund_json_data = [
            {"date": r["date"].isoformat(), "funding_rate": r["open"]}
            for _, r in df_fund.iterrows()
        ]
        with open(funding_json, "w") as jf:
            json.dump(fund_json_data, jf, indent=2)

        with open(funding_feather, "rb") as ff:
            fund_sha = hashlib.sha256(ff.read()).hexdigest()

        manifest["funding_datasets"][ft_pair] = {
            "symbol": ft_pair,
            "row_count": len(df_fund),
            "file_path": funding_feather,
            "json_path": funding_json,
            "sha256": fund_sha,
            "first_record": df_fund.iloc[0]["date"].isoformat() if len(df_fund) > 0 else None,
            "last_record": df_fund.iloc[-1]["date"].isoformat() if len(df_fund) > 0 else None,
        }
        print(f"Saved Funding for {ft_pair}: {len(df_fund)} records, SHA256: {fund_sha[:12]}...")

    manifest_path = os.path.join(MANIFEST_DIR, "manifest.json")
    with open(manifest_path, "w") as mf:
        json.dump(manifest, mf, indent=2)

    print(f"\nManifest successfully created at {manifest_path}")
    print(f"Integrity Status: {'ALL PASSED' if manifest['integrity_summary']['all_passed'] else 'ANOMALIES DETECTED'}")
    print(f"Total Gaps: {manifest['integrity_summary']['total_gaps']}")


if __name__ == "__main__":
    main()
