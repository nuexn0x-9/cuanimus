import json
import ccxt
import pandas as pd
import talib

OUTPUT_FILE = "/freqtrade/user_data/market_bias.json"

exchange = ccxt.binance({
    "enableRateLimit": True
})


def get_trend(pair):

    ohlcv = exchange.fetch_ohlcv(
        pair,
        timeframe="1h",
        limit=250
    )

    df = pd.DataFrame(
        ohlcv,
        columns=[
            "timestamp",
            "open",
            "high",
            "low",
            "close",
            "volume"
        ]
    )

    df["ema50"] = talib.EMA(
        df["close"],
        timeperiod=50
    )

    df["ema200"] = talib.EMA(
        df["close"],
        timeperiod=200
    )

    df["rsi"] = talib.RSI(
        df["close"],
        timeperiod=14
    )

    df["adx"] = talib.ADX(
        df["high"],
        df["low"],
        df["close"],
        timeperiod=14
    )

    last = df.iloc[-1]

    ema50 = float(last["ema50"])
    ema200 = float(last["ema200"])

    rsi = float(last["rsi"])
    adx = float(last["adx"])

    print(
        f"{pair} EMA50={ema50:.2f} "
        f"EMA200={ema200:.2f}"
        f"RSI={rsi:.2f} "
        f"ADX={adx:.2f}"
    )

    if ema50 > ema200:
        trend = "BULLISH"
    else:
        trend = "BEARISH"
    
    return {
        "trend": trend,
        "rsi": rsi,
        "adx": adx   
    }


btc = get_trend("BTC/USDT")
eth = get_trend("ETH/USDT")

btc_trend = btc["trend"]
eth_trend = eth["trend"]

#########################################
# CONFIDENCE CALCULATION
#########################################

confidence = 50

if btc["adx"] > 25:
    confidence += 10

if eth["adx"] > 25:
    confidence += 10

if btc["adx"] > 40:
    confidence += 10

if eth["adx"] > 40:
    confidence += 10

if btc["rsi"] < 35 or btc["rsi"] > 65:
    confidence += 5

if eth["rsi"] < 35 or eth["rsi"] > 65:
    confidence += 5

confidence = min(confidence, 95)

#########################################
# MARKET BIAS
#########################################

if btc_trend == "BULLISH" and eth_trend == "BULLISH":

    result = {
        "market_bias": "BULLISH",
        "confidence": confidence,

        "btc_rsi": round(btc["rsi"], 2),
        "btc_adx": round(btc["adx"], 2),

        "eth_rsi": round(eth["rsi"], 2),
        "eth_adx": round(eth["adx"], 2)
    }

elif btc_trend == "BEARISH" and eth_trend == "BEARISH":

    result = {
        "market_bias": "BEARISH",
        "confidence": confidence,

        "btc_rsi": round(btc["rsi"], 2),
        "btc_adx": round(btc["adx"], 2),

        "eth_rsi": round(eth["rsi"], 2),
        "eth_adx": round(eth["adx"], 2)
    }

else:

    result = {
        "market_bias": "NEUTRAL",
        "confidence": confidence,

        "btc_rsi": round(btc["rsi"], 2),
        "btc_adx": round(btc["adx"], 2),

        "eth_rsi": round(eth["rsi"], 2),
        "eth_adx": round(eth["adx"], 2)
    }

result["updated"] = (
    pd.Timestamp.now("UTC")
    .strftime("%Y-%m-%d %H:%M:%S UTC")
)

with open(
    OUTPUT_FILE,
    "w"
) as f:

    json.dump(
        result,
        f,
        indent=4
    )

print(result)