import os
import requests
import json
import logging
import re
from freqtrade.strategy import IStrategy
from pandas import DataFrame
import talib.abstract as ta
from datetime import datetime

from utils.risk_management import calculate_position_size

logger = logging.getLogger(__name__)

class AI_Gemini_Futures_Strategy(IStrategy):
    minimal_roi = {"0": 0.05, "45": 0.025, "90": 0.01, "180": 0}
    stoploss = -0.02
    timeframe = '15m'
    can_short = True

    _last_candle_time = {}
    _cached_decision = {}

    def custom_leverage(self, pair: str, current_time: datetime, current_rate: float,
                        proposed_leverage: float, max_leverage: float, entry_tag: str, side: str,
                        **kwargs) -> float:
        return 10.0

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['ema20'] = ta.EMA(dataframe, timeperiod=20)
        dataframe['ema50'] = ta.EMA(dataframe, timeperiod=50)
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        
        stoch_rsi = ta.STOCHRSI(dataframe, timeperiod=14, fastk_period=3, fastd_period=3, fastd_matype=0)
        dataframe['stoch_k'] = stoch_rsi['fastk']
        dataframe['stoch_d'] = stoch_rsi['fastd']
        
        bollinger = ta.BBANDS(dataframe, timeperiod=20, nbdevup=2.0, nbdevdn=2.0)
        dataframe['bb_lowerband'] = bollinger['lowerband']
        dataframe['bb_upperband'] = bollinger['upperband']
        dataframe['volume_avg'] = dataframe['volume'].rolling(window=20).mean()
        
        return dataframe

    def ask_gemini_flash(self, prompt_text: str) -> dict:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            logger.error("GEMINI_API_KEY tidak ditemukan.")
            return {"decision": "HOLD", "reason": "No API Key"}

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
        headers = {'Content-Type': 'application/json'}
        payload = {
            "contents": [{"parts": [{"text": prompt_text}]}], 
            "generationConfig": {"temperature": 0.1, "maxOutputTokens": 300}
        }

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=20)
            if response.status_code == 200:
                data = response.json()
                parts = data.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])
                if parts and 'text' in parts[0]:
                    raw_text = parts[0]['text'].strip()
                    
                    # === BAGIAN PEMBERSIH TEKS (ANTI FORMAT CACAT AI) ===
                    raw_text = raw_text.replace('```json', '').replace('```', '').replace('\n', ' ')
                    
                    match = re.search(r'\{.*\}', raw_text, re.DOTALL)
                    if match:
                        clean_json = match.group(0).strip()
                        return json.loads(clean_json)
                    return json.loads(raw_text)
        except Exception as e:
            logger.error(f"Gagal memproses AI: {str(e)}")
            
        return {"decision": "HOLD", "reason": "Sistem Fallback Eksternal"}

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: float, max_stake: float,
                            leverage: float, entry_tag: str, side: str, **kwargs) -> float:
        try:
            total_wallet_balance = self.wallets.get_total_stake_amount()
            return calculate_position_size(current_rate, abs(self.stoploss), total_wallet_balance, 3.0, leverage)
        except Exception as e:
            logger.error(f"Gagal custom_stake: {str(e)}")
            return proposed_stake

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        pair = metadata['pair']
        dataframe['enter_long'] = 0
        dataframe['enter_short'] = 0

        if dataframe is None or dataframe.empty:
            return dataframe

        last_row = dataframe.iloc[-1]
        candle_time = last_row['date']

        is_uptrend = last_row['ema20'] > last_row['ema50']
        is_downtrend = last_row['ema20'] < last_row['ema50']
        
        is_stoch_oversold = last_row['stoch_k'] < 30 and last_row['stoch_d'] < 30
        is_stoch_overbought = last_row['stoch_k'] > 70 and last_row['stoch_d'] > 70
        
        is_volume_active = last_row['volume'] > (last_row['volume_avg'] * 0.8)

        potential_long = is_uptrend and is_stoch_oversold and is_volume_active
        potential_short = is_downtrend and is_stoch_overbought and is_volume_active

        if not (potential_long or potential_short):
            self._cached_decision[pair] = {"decision": "HOLD", "reason": "Menunggu Konfirmasi Trend 15m"}
            return dataframe

        if pair not in self._last_candle_time or self._last_candle_time[pair] != candle_time:
            direction_hint = "LONG" if potential_long else "SHORT"
            
            prompt = (f"Bertindaklah sebagai trader kuantitatif profesional. Analisis pair {pair} "
                      f"pada grafik timeframe 15 menit. "
                      f"Data saat ini: Harga = {last_row['close']}, RSI = {last_row['rsi']:.1f}, "
                      f"StochK = {last_row['stoch_k']:.1f}, EMA20 = {last_row['ema20']:.1f}, EMA50 = {last_row['ema50']:.1f}. "
                      f"Struktur momentum lokal menyarankan eksekusi {direction_hint}. "
                      f"Berikan evaluasi akhir dari probabilitas pergerakan ini. Jawab HANYA menggunakan "
                      f"format JSON murni tanpa backticks: "
                      f"{{\"decision\": \"LONG/SHORT/HOLD\", \"reason\": \"analisis teknikal padat maksimal 5 kata\"}}")

            self._cached_decision[pair] = self.ask_gemini_flash(prompt)
            self._last_candle_time[pair] = candle_time
            logger.info(f"[{pair}] Evaluasi AI 15m: {self._cached_decision[pair]}")

        cached_target = self._cached_decision.get(pair, {})
        decision = str(cached_target.get("decision", "HOLD")).upper().strip() if isinstance(cached_target, dict) else "HOLD"

        if decision == "LONG" and is_uptrend:
            dataframe.loc[dataframe.index[-1], 'enter_long'] = 1
        elif decision == "SHORT" and is_downtrend:
            dataframe.loc[dataframe.index[-1], 'enter_short'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['exit_long'] = 0
        dataframe['exit_short'] = 0
        return dataframe