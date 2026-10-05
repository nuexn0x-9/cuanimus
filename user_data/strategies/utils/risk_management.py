# user_data/strategies/utils/risk_management.py
import logging

logger = logging.getLogger(__name__)

def calculate_position_size(open_rate: float, stop_loss_pct: float, total_wallet_balance: float, risk_per_trade_pct: float, leverage: float) -> float:
    """
    Menghitung ukuran posisi (stake amount) otomatis berdasarkan tingkat risiko per trade.
    Sesuai prinsip: Modal = 30 USDT, Risk = 3%, Max loss/trade = 0.9 USDT.
    """
    try:
        # 1. Hitung maksimal uang yang boleh hilang (Risk Amount)
        max_loss_amount = total_wallet_balance * (risk_per_trade_pct / 100.0)
        
        # 2. Hitung jarak stop loss dalam persentase absolut terhadap leverage
        # stop_loss_pct dari Freqtrade bernilai negatif (misal: -0.015 untuk 1.5%)
        sl_distance = abs(stop_loss_pct)
        
        if sl_distance == 0:
            return 14.0 # Fallback aman jika SL tidak terdefinisi
            
        # 3. Hitung total nilai posisi (Position Size) yang mengacu pada batas Max Loss
        # Formula: Max Loss / Jarak SL di pasar riil
        total_position_value = max_loss_amount / sl_distance
        
        # 4. Hitung modal (margin) yang dibutuhkan setelah dibagi leverage
        stake_amount = total_position_value / leverage
        
        # Batasan keamanan: Jangan melebihi saldo dompet yang tersedia
        if stake_amount > total_wallet_balance:
            stake_amount = total_wallet_balance * 0.9 # Gunakan maksimal 90% saldo
            
        logger.info(f"[RISK] Saldo: {total_wallet_balance} USDT | Risk: {risk_per_trade_pct}% | Max Loss: {max_loss_amount:.2f} USDT")
        logger.info(f"[RISK] Rekomendasi Stake Amount: {stake_amount:.2f} USDT dengan Leverage {leverage}x")
        
        return round(stake_amount, 2)
        
    except Exception as e:
        logger.error(f"[RISK] Gagal menghitung position sizing: {str(e)}")
        return 14.0 # Fallback ke nilai bawaan jika terjadi error kalkulasi