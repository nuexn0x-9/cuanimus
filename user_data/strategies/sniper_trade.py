import os
import json
import re
import logging
import requests

from datetime import datetime
from pandas import DataFrame

from freqtrade.strategy import IStrategy
import talib.abstract as ta

#from utils.risk_management import calculate_position_size

logger = logging.getLogger(__name__)
ENABLE_GEMINI = False

MARKET_BIAS_FILE = "/freqtrade/user_data/market_bias.json"

class SNIPER_TRADE(IStrategy):

    INTERFACE_VERSION = 3

    timeframe = "15m"
    can_short = True

    minimal_roi = {
        "0": 0.030,
        "30": 0.020,
        "60": 0.010,
        "120": 0
    }

    stoploss = -0.015

    startup_candle_count = 100

    process_only_new_candles = True

    _last_candle_time = {}
    _cached_decision = {}

    #########################################
    # MARKET BIAS
    #########################################

    def get_market_bias(self):

        try:

            with open(MARKET_BIAS_FILE, "r") as f:
                data = json.load(f)

            return (
                data.get("market_bias", "NEUTRAL"),
                int(data.get("confidence", 0))
            )

        except Exception:

            return ("NEUTRAL", 0)
        
    def get_market_data(self):

        try:

            with open(MARKET_BIAS_FILE, "r") as f:
                data = json.load(f)

            return data

        except Exception:

            return {
                "market_bias": "NEUTRAL",
                "confidence": 0,
                "btc_rsi": 50,
                "eth_rsi": 50,
                "btc_adx": 0,
                "eth_adx": 0
            }

    #########################################
    # LEVERAGE
    #########################################
    def leverage(
        self,
        pair: str,
        current_time: datetime,
        current_rate: float,
        proposed_leverage: float,
        max_leverage: float,
        entry_tag: str | None,
        side: str,
        **kwargs
    ) -> float:

        logger.info(
            f"[{pair}] LEVERAGE CALLED "
            f"proposed={proposed_leverage} "
            f"max={max_leverage}"
        )

        return min(5.0, max_leverage)
    
    #########################################
    # INDICATORS
    #########################################

    def populate_indicators(
        self,
        dataframe: DataFrame,
        metadata: dict
    ) -> DataFrame:

        dataframe["ema20"] = ta.EMA(dataframe, timeperiod=20)
        dataframe["ema50"] = ta.EMA(dataframe, timeperiod=50)

        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)

        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)

        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)

        return dataframe

    #########################################
    # GEMINI
    #########################################

    def ask_gemini(self, prompt_text: str):

        api_key = os.environ.get("GEMINI_API_KEY")

        if not api_key:
            logger.error("GEMINI_API_KEY tidak ditemukan")

            return {
                "decision": "HOLD",
                "confidence": 0,
                "reason": "NO_API_KEY"
            }

        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"gemini-2.5-flash:generateContent?key={api_key}"
        )

        headers = {
            "Content-Type": "application/json"
        }

        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": prompt_text
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 300
            }
        }

        try:

            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=15
            )

            logger.info(
                f"GEMINI STATUS={response.status_code}"
            )

            logger.info(
                f"GEMINI RAW={response.text[:500]}"
            )

            if response.status_code != 200:

                return {
                    "decision": "HOLD",
                    "confidence": 0,
                    "reason": f"HTTP_{response.status_code}"
                }

            data = response.json()

            parts = (
                data.get("candidates", [{}])[0]
                .get("content", {})
                .get("parts", [{}])
            )

            if parts and "text" in parts[0]:

                raw_text = parts[0]["text"].strip()

                raw_text = raw_text.replace(
                    "```json",
                    ""
                )

                raw_text = raw_text.replace(
                    "```",
                    ""
                )

                raw_text = raw_text.strip()

                match = re.search(
                    r"\{.*\}",
                    raw_text,
                    re.DOTALL
                )

                if match:

                    clean_json = match.group(0)

                    result = json.loads(
                        clean_json
                    )

                    return {
                        "decision": str(
                            result.get(
                                "decision",
                                "HOLD"
                            )
                        ).upper(),
                        "confidence": int(
                            result.get(
                                "confidence",
                                0
                            )
                        ),
                        "reason": str(
                            result.get(
                                "reason",
                                ""
                            )
                        )
                    }

        except Exception as e:

            logger.error(
                f"GEMINI ERROR={str(e)}"
            )

        return {
            "decision": "HOLD",
            "confidence": 0,
            "reason": "FALLBACK"
        }

    #########################################
    # POSITION SIZE
    #########################################

    def custom_stake_amount(
        self,
        pair: str,
        current_time: datetime,
        current_rate: float,
        proposed_stake: float,
        min_stake: float,
        max_stake: float,
        leverage: float,
        entry_tag: str,
        side: str,
        **kwargs
    ) -> float:

        stake = 10.0

        logger.info(
            f"[{pair}] Fixed Stake={stake} USDT"
        )

        return stake

    #########################################
    # ENTRY
    #########################################

    def populate_entry_trend(
        self,
        dataframe: DataFrame,
        metadata: dict
    ) -> DataFrame:

        dataframe["enter_long"] = 0
        dataframe["enter_short"] = 0

        pair = metadata["pair"]

        current_hour_utc = datetime.utcnow().hour
        current_hour_wib = (current_hour_utc + 7) % 24

        logger.info(
            f"[{pair}] "
            f"UTC={current_hour_utc}"
            f"WIB={current_hour_wib}"
        )

        if dataframe.empty:
            return dataframe

        last = dataframe.iloc[-1]

        ema20 = float(last["ema20"])
        ema50 = float(last["ema50"])

        rsi = float(last["rsi"])
        adx = float(last["adx"])

        trend_bull = ema20 > (ema50 * 1.003)
        trend_bear = ema20 < (ema50 * 0.997)

        decision = "HOLD"
        confidence = 0


        market_data = self.get_market_data()

        market_bias = market_data.get(
            "market_bias",
            "NEUTRAL"
        )

        market_confidence = int(
            market_data.get(
                "confidence",
                0
            )
        )
        btc_rsi = float(
            market_data.get(
                "btc_rsi",
                50
            )
        )

        eth_rsi = float(
            market_data.get(
                "eth_rsi",
                50
            )
        )

        logger.info(
            f"[{pair}] "
            f"MARKET={market_bias} "
            f"CONF={market_confidence} "
            f"BTC_RSI={btc_rsi:.2f} "
            f"ETH_RSI={eth_rsi:.2f}"
        )

        if ENABLE_GEMINI and adx > 15:

            try:

                result = self.ask_gemini(
                    f"""
PAIR={pair}

EMA20={ema20}
EMA50={ema50}

RSI={rsi}
ADX={adx}

Balas JSON MURNI:

{{
"decision":"LONG/SHORT/HOLD",
"confidence":80,
"reason":"..."
}}
"""
                )

                decision = str(
                    result.get(
                        "decision",
                        "HOLD"
                    )
                ).upper()

                confidence = int(
                    result.get(
                        "confidence",
                        0
                    )
                )

            except Exception:
                pass

        logger.info(
            f"[{pair}] "
            f"RSI={rsi:.2f} "
            f"ADX={adx:.2f} "
            f"AI={decision} "
            f"CONF={confidence}"
        )

        #################################
        # LONG
        #################################

        long_signal = False

        if (
            not (
                market_bias == "BEARISH"
                and market_confidence >= 70
            )

            and btc_rsi < 70
            and eth_rsi < 70

            and trend_bull
            and rsi > 62
            and adx > 25
        ):
            long_signal = True

        elif (
            decision == "LONG"
            and confidence >= 60
        ):
            logger.info("AI confirms LONG")

        #################################
        # SHORT
        #################################

        short_signal = False

        if (
            not (
                market_bias == "BULLISH"
                and market_confidence >= 70
            )

            and btc_rsi > 30
            and eth_rsi > 30

            and trend_bear
            and rsi < 38
            and rsi > 30
            and adx > 25
        ):
            short_signal = True

        elif (
            decision == "SHORT"
            and confidence >= 60
        ):
            logger.info("AI confirms SHORT")

        #################################
        # EXECUTE
        #################################

        if long_signal:

            dataframe.loc[
                dataframe.index[-1],
                "enter_long"
            ] = 1

            logger.info(
                f"[{pair}] LONG ENTRY"
            )

        elif short_signal:

            dataframe.loc[
                dataframe.index[-1],
                "enter_short"
            ] = 1

            logger.info(
                f"[{pair}] SHORT ENTRY"
            )

        return dataframe

    #########################################
    # EXIT
    #########################################

    def populate_exit_trend(
        self,
        dataframe: DataFrame,
        metadata: dict
    ) -> DataFrame:

        dataframe["exit_long"] = 0
        dataframe["exit_short"] = 0

        return dataframe