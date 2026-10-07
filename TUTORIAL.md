# Panduan Lengkap Penggunaan CUANIMUS
### Systematic Quant Research, Air-Gapped Paper Trading & AI Agent Automation

Selamat datang di **CUANIMUS**! Dokumen ini adalah panduan praktis langkah-demi-langkah dari instalasi, konfigurasi, backtesting, simulasi paper trading, hingga integrasi AI Agent (Google Antigravity, Claude, Cursor, Hermes) menggunakan Model Context Protocol (MCP).

---

## DAFTAR ISI

1. [Prinsip Dasar & Aturan Keselamatan](#1-prinsip-dasar--aturan-keselamatan)
2. [Kebutuhan Sistem (Prerequisites)](#2-kebutuhan-sistem-prerequisites)
3. [Instalasi & Diagnostik Sistem](#3-instalasi--diagnostik-sistem)
4. [Manajemen Konfigurasi](#4-manajemen-konfigurasi)
5. [Backtesting & Validasi Kuantitatif](#5-backtesting--validasi-kuantitatif)
6. [Simulasi Paper Trading](#6-simulasi-paper-trading)
7. [Integrasi AI Agent via Model Context Protocol (MCP)](#7-integrasi-ai-agent-via-model-context-protocol-mcp)
8. [Panduan Menghubungkan AI Client (Antigravity, Claude, Cursor)](#8-panduan-menghubungkan-ai-client-antigravity-claude-cursor)
9. [Protokol Keamanan & Emergency Kill Switch](#9-protokol-keamanan--emergency-kill-switch)
10. [Perintah CLI Cheatsheet](#10-perintah-cli-cheatsheet)
11. [Deployment Server & Docker Stack](#11-panduan-deployment-server-produksi--akses-remote)
12. [Autonomous Trading Engine & 3 Decision Modes](#12-autonomous-trading-engine--trading-profiles)
13. [Web Control Center & Terminal Trading Manual](#13-web-control-center--terminal-trading-manual)
14. [Bot Telegram Mobile Interaktif](#14-bot-telegram-mobile-interaktif)

---

## 1. Prinsip Dasar & Aturan Keselamatan

> [!CAUTION]
> **Real-Capital Live Trading STRICTLY DISABLED (NO-GO)**
> Platform ini dibangun untuk riset kuantitatif, reproduktibilitas backtest tanpa *lookahead bias*, dan forward paper trading. Sistem secara tegas mengunci eksekusi uang sungguhan untuk melindungi modal Anda.

1. **Independent Risk Authority**: Strategy hanya memproduksi niat transaksi (`TradeIntent`). Besaran kontrak (sizing) dan persetujuan sepenuhnya dipegang oleh `RiskEngine`.
2. **Mandatory Stop-Loss**: Setiap transaksi wajib memiliki level stop-loss valid. Perdagangan tanpa stop-loss akan langsung ditolak oleh sistem.
3. **Plafon Leverage Maksimal**: Leverage dibatasi maksimal **10.0x** (institutional ceiling). Permintaan leverage di atas 10x akan diveto secara otomatis.
4. **Default-Deny AI Access**: AI Agent tidak memiliki akses langsung ke API exchange (Binance) atau database mentah. Seluruh interaksi melewati gateway MCP.

---

## 2. Kebutuhan Sistem (Prerequisites)

- **Sistem Operasi**: Linux (Ubuntu 20.04+, Debian, Arch), macOS, atau Windows (WSL2 direkomendasikan).
- **Python**: Versi `3.10` atau lebih baru (`python3 --version`).
- **Git**: Untuk cloning dan pembaruan repositori.
- **Docker** *(Opsional)*: Jika Anda ingin menjalankan container terisolasi atau bot dry-run Freqtrade bawaan.

> [!NOTE]
> **Apakah Perlu Install Freqtrade via pip?**
> **TIDAK PERLU.** CUANIMUS Core dirancang murni mandiri (*standalone*). Seluruh CLI (`./cuanimus-cli`), Risk Engine, Causal Backtester, dan MCP AI Server berjalan langsung dari `requirements.txt`.
> Jika Anda ingin menjalankan container Freqtrade lawas, cukup jalankan `docker-compose up -d` (Docker otomatis mendownload image yang sudah lengkap dengan binary C TA-Lib tanpa perlu meng-compile pip freqtrade di laptop/server Anda).

---

## 3. Instalasi & Diagnostik Sistem

### Langkah 1: Clone Repositori
```bash
git clone https://github.com/nuexn0x-9/cuanimus.git
cd cuanimus
```

### Langkah 2: Buat Virtual Environment & Install Dependensi
```bash
# Buat virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependensi
pip install -r requirements.txt
```

### Langkah 3: Beri Izin Eksekusi pada CLI
```bash
chmod +x ./cuanimus-cli
```

### Langkah 4: Jalankan System Doctor Diagnostics
Jalankan pemeriksaan kesehatan 12 poin untuk memastikan environment siap digunakan:
```bash
./cuanimus-cli doctor
```

Output yang diharapkan:
```text
======================================================================
              CUANIMUS SYSTEM DOCTOR DIAGNOSTIC
======================================================================
Category       | Check Name                | Status | Diagnostic Details
Runtime        | Python Version (>= 3.10)  | [PASS] | Python 3.10.12 on linux
Storage        | Database Connectivity     | [PASS] | SQLite write probe successful
Security       | Secret Quarantine         | [PASS] | Zero active API credentials exposed
Config         | Configuration Hierarchy   | [PASS] | Balanced profile valid (PAPER_SAFE)
Strategy       | Strategy Plugin Registry  | [PASS] | 5 strategies registered
Risk           | Risk Profile Registry     | [PASS] | 3 risk profiles active
AI             | AI Provider Decoupling    | [PASS] | Providers available: mock, gemini, disabled
Safety         | Live Capital Safety Guard | [PASS] | Real-capital trading STRICTLY DISABLED
======================================================================
```

---

## 4. Manajemen Konfigurasi

CUANIMUS menggunakan sistem konfigurasi modular berbasis YAML di dalam folder `config/`.

### Inisialisasi Konfigurasi Awal
Gunakan setup wizard untuk memilih profil bawaan (`beginner`, `conservative`, `balanced`, atau `aggressive`):
```bash
./cuanimus-cli init --preset balanced
```
File konfigurasi pengguna `cuanimus.user.yaml` akan dibuat secara otomatis.

### Memvalidasi Konfigurasi
Sebelum menjalankan engine, pastikan konfigurasi lulus verifikasi skema dan aturan keselamatan:
```bash
./cuanimus-cli config validate
```

### Menjelaskan Parameter Tertentu
Jika Anda ingin memahami fungsi, batasan nilai, dan level risiko dari suatu parameter:
```bash
./cuanimus-cli config explain risk.risk_per_trade_pct
./cuanimus-cli config explain execution.pessimistic_sl_precedence
```

### Melihat Struktur Konfigurasi yang Aktif
```bash
./cuanimus-cli config show --format yaml
```

---

## 5. Backtesting & Validasi Kuantitatif

CUANIMUS menerapkan prinsip **Strict Information Boundaries**:
- Menggunakan closed bars secara kausal ($t \le T$).
- Tidak ada lookahead bias pada indikator teknikal (EMA, RSI, ADX).
- Swing point fractal hanya dikonfirmasi setelah penutupan bar $i + \text{window}$.
- Pemodelan slippage realistis dan pemisahan maker/taker fee.

### Menjalankan Backtest
```bash
# Menjalankan backtest dengan profil balanced
./cuanimus-cli backtest --profile balanced

# Menjalankan backtest dengan strategi spesifik (misal: v2_pullback)
./cuanimus-cli backtest --strategy v2_pullback --profile conservative
```

### Melihat Hasil Backtest
Hasil metriks kuantitatif (Expectancy, Win Rate, Profit Factor, Max Drawdown, Fee Drag) akan ditampilkan di terminal dan tersimpan di folder `experiments/`.

---

## 6. Simulasi Paper Trading

Forward Paper Trading mensimulasikan pergerakan order limit dan stop secara real-time tanpa menyentuh saldo uang nyata di exchange.

### Memulai Sesi Paper Trading
```bash
./cuanimus-cli paper start --profile balanced
```

Sesi akan menampilkan:
- Lingkungan aktif: `PAPER`
- Status pengaman: `ACTIVE (dry_run=True)`
- Live Execution: `STRICTLY BLOCKED`
- Pasangan trading: `BTC/USDT:USDT`, `ETH/USDT:USDT`, dll.

### Menghentikan Sesi Paper Trading
Buka terminal baru atau tekan `Ctrl + C`, atau jalankan:
```bash
./cuanimus-cli paper stop
```

---

## 7. Integrasi AI Agent via Model Context Protocol (MCP)

CUANIMUS menyediakan **46 MCP Tools** yang dapat diakses oleh AI Agent (Antigravity, Claude, Cursor, Codex, Hermes).

### Langkah 1: Inisialisasi Kebijakan Agent (Policy)
Buat kebijakan trading yang membatasi wewenang AI Agent:
```bash
# Pilihan preset: advisory, paper_auto, testnet_auto
./cuanimus-cli agent init --preset paper_auto
```

File kebijakan akan dibuat di `config/agents/agent.yaml`.

### Langkah 2: Validasi Kebijakan Agent
Pastikan kebijakan tidak melanggar aturan plafon platform:
```bash
./cuanimus-cli agent validate --config config/agents/paper_auto.yaml
```

### Langkah 3: Menjalankan MCP Server
Ada 2 mode transport yang didukung:

#### Mode A: `stdio` (Untuk Antigravity CLI / Claude Desktop / Cursor)
```bash
./cuanimus-cli mcp start --transport stdio
```

#### Mode B: `http` (Untuk Background Worker / Web API)
```bash
./cuanimus-cli mcp start --transport http --port 8000
```

### Memeriksa Status & Tool MCP
```bash
./cuanimus-cli mcp status
./cuanimus-cli mcp tools
```

---

## 8. Panduan Menghubungkan AI Client

### A. Google Antigravity & Claude Desktop
Tambahkan konfigurasi berikut ke file konfigurasi MCP Anda (`claude_desktop_config.json` atau pengaturan Antigravity):

```json
{
  "mcpServers": {
    "cuanimus": {
      "command": "/usr/bin/python3",
      "args": [
        "-m",
        "cuanimus.cli",
        "mcp",
        "start",
        "--transport",
        "stdio"
      ],
      "env": {}
    }
  }
}
```

### B. Cursor IDE
Tambahkan ke `.cursor/mcp.json` di root workspace:
```json
{
  "mcpServers": {
    "cuanimus": {
      "command": "python3",
      "args": [
        "-m",
        "cuanimus.cli",
        "mcp",
        "start",
        "--transport",
        "stdio"
      ]
    }
  }
}
```

### Contoh Interaksi Natural Language dengan AI
Setelah terhubung, Anda dapat mengetik instruksi langsung ke AI:

1. **Audit Risiko**:
   > *"Tolong audit pengaturan risiko CUANIMUS saat ini dan jelaskan apakah sudah aman untuk paper trading."*
   > *(AI akan memanggil `system.get_safety_status` dan `risk.get_limits`)*

2. **Assisted Config Tuning**:
   > *"Ubah risk per trade menjadi 1% dan gunakan strategi v2_pullback untuk time frame 15m."*
   > *(AI akan memanggil `config.preview`, menghasilkan delta diff, dan meminta persetujuan Anda)*

3. **Analisis Pasar**:
   > *"Analisis kondisi pasar ETH/USDT:USDT saat ini dan klasifikasikan market regimemya."*
   > *(AI akan memanggil `market.get_regime` dan `market.get_funding`)*

4. **Automated Trading**:
   > *"Mulai sesi autonomous paper trading selama 1 jam dengan batas maksimal 5 transaksi."*
   > *(AI akan memanggil `session.create` dan `session.start`)*

---

## 9. Protokol Keamanan & Emergency Kill Switch

### 1. Independent Human Kill Switch
Jika pasar mengalami anomali atau Anda ingin menghentikan AI seketika tanpa persetujuan AI:
- Jalankan di terminal:
  ```bash
  ./cuanimus-cli paper stop
  ```
- Atau jika menggunakan MCP / API:
  Panggil tool `session.emergency_stop`. Seluruh sesi otomatis dihentikan dan Risk Engine akan terkunci.

### 2. Log Audit Anti-Bocor Kredensial
Seluruh aksi AI, pembuatan intent, validasi risiko, dan simulasi order dicatat secara append-only di:
`logs/agent_audit.jsonl`

Semua token sensitif (API key Binance, Telegram token, Gemini key) otomatis disanitasi (`[REDACTED_SECRET]`).

---

## 10. Web Control Center & Antarmuka Trading Interaktif (Phase 8)

CUANIMUS menyediakan antarmuka web modern kelas workstation yang **100% tanpa build (zero-dependency)**:

### Menjalankan Web Control Center
```bash
# 1. Cek status Web Control Center
./cuanimus-cli ui status

# 2. Jalankan HTTP server daemon (default: port 8080)
./cuanimus-cli ui start --port 8080

# 3. Buka browser Anda:
# http://127.0.0.1:8080/
```

### Fitur Utama di Web Browser:
1. **Operational Dashboard**: Pantau total equity, unrealized PnL, open positions, status AI agent, dan kesehatan seluruh subsistem (*RiskEngine, Strategy, Execution, Telegram, MCP*).
2. **Trading Terminal & Canvas Chart**: Grafik Candlestick berbasis HTML5 Canvas dengan timeframe (5m, 15m, 1h, 4h), garis EMA20/50, indikator ATR, Order Block zone, serta visualisasi level Stop Loss dan Take Profit.
3. **Causal Decision Trace**: Setiap trade dapat diinspeksi urutan kausalnya:
   $$\text{Market Context} \longrightarrow \text{Regime} \longrightarrow \text{Strategy Signal} \longrightarrow \text{Agent Decision} \longrightarrow \text{Risk Approval} \longrightarrow \text{Execution FSM} \longrightarrow \text{Fill}$$
4. **Risk Center**: Grafik visual batas risiko (*Daily Loss Meter*, *Drawdown Meter*, *Total Capital Exposure*, *Circuit Breakers*).
5. **Research & Backtest Lab**: Form interaktif untuk menjalankan simulasi backtest seketika dan membandingkan performa model (*V0, V1, V2A, V2B, V2C*) pada partisi *Out-of-Sample*.
6. **Integrasi Telegram & Notifikasi**:
   - Status bot Telegram ditampilkan langsung di menu **Settings**.
   - Dilengkapi tombol **"Send Test Alert"** untuk menguji koneksi bot secara langsung dari browser.
   - Mengirimkan alert otomatis untuk *Order Fill*, *Stop Loss*, *Take Profit*, *Risk Veto*, dan *Emergency Stop*.
7. **AI Configuration Copilot**:
   - Ketik instruksi natural language (contoh: *"Setup conservative ETH paper trading with 0.5% risk"*).
   - Sistem akan menyusun proposal konfigurasi, menampilkan visual diff perubahannya, dan menerapkan konfigurasi dengan 1 klik.
8. **Emergency Kill Switch**: Tombol merah permanen di header untuk memicu kill-switch seketika yang menghentikan seluruh sesi agent dan mengunci Risk Engine.
9. **Command Palette (`Ctrl+K` / `Cmd+K`)**: Navigasi cepat ala IDE profesional langsung dengan keyboard.

---

## 11. Perintah CLI Cheatsheet

| Kategori | Perintah | Fungsi |
| :--- | :--- | :--- |
| **Sistem** | `./cuanimus-cli doctor` | Diagnosis kesehatan sistem dan environment |
| | `./cuanimus-cli status` | Status platform dan safety lock aktif |
| **Web UI** | `./cuanimus-cli ui bootstrap` | Bootstrap kredensial administrator awal |
| | `./cuanimus-cli ui start --daemon` | Menjalankan Web Control Center di background (port 8888) |
| | `./cuanimus-cli ui stop` | Menghentikan daemon Web Control Center |
| | `./cuanimus-cli ui status` | Status endpoint dan sesi Web Control Center |
| **Config** | `./cuanimus-cli init --preset <name>` | Inisialisasi konfigurasi profil |
| | `./cuanimus-cli config validate` | Validasi skema & keselamatan konfigurasi |
| | `./cuanimus-cli config show` | Tampilkan konfigurasi aktif |
| | `./cuanimus-cli config explain <key>` | Penjelasan parameter konfigurasi |
| **Strategi**| `./cuanimus-cli strategy list` | Daftar plugin strategi kuantitatif |
| | `./cuanimus-cli strategy inspect <id>`| Detail parameter strategi |
| **Risiko** | `./cuanimus-cli risk list` | Daftar profil risiko |
| | `./cuanimus-cli risk inspect <name>` | Detail limit risiko & cooldown |
| **Trading** | `./cuanimus-cli backtest` | Menjalankan replay historis deterministik |
| | `./cuanimus-cli paper start` | Memulai sesi forward paper trading |
| | `./cuanimus-cli paper stop` | Menghentikan sesi paper trading |
| **Agent** | `./cuanimus-cli agent init` | Buat kebijakan agent & config MCP client |
| | `./cuanimus-cli agent validate` | Validasi aturan kebijakan agent |
| | `./cuanimus-cli agent list` | Daftar agent dan preset kebijakan |
| | `./cuanimus-cli agent token-list` | Daftar token bearer MCP AI Agent |
| | `./cuanimus-cli agent token-rotate` | Rotasi token bearer untuk agent tertentu |
| | `./cuanimus-cli agent token-revoke` | Cabut akses token bearer agent seketika |
| | `./cuanimus-cli agent test-connection`| Uji autentikasi dan status koneksi agent |
| **MCP** | `./cuanimus-cli mcp start --transport http --daemon` | Jalankan MCP JSON-RPC Server di background |
| | `./cuanimus-cli mcp stop` | Menghentikan daemon MCP server |
| | `./cuanimus-cli mcp status` | Status MCP server & safety mode |
| | `./cuanimus-cli mcp tools` | Daftar 46 tool MCP |
| **Backup** | `./cuanimus-cli backup create` | Buat snapshot atomic database & konfigurasi |
| | `./cuanimus-cli backup verify` | Verifikasi integritas bit-exact SHA256 backup |
| | `./cuanimus-cli backup list` | Daftar riwayat snapshot backup |

---

## 11. Panduan Deployment Server Produksi & Docker Stack

CUANIMUS mendukung deployment server Linux dan kontainer Docker terisolasi:

### A. Menggunakan Docker Compose (Direkomendasikan)
Stack resmi CUANIMUS terdiri atas 3 container:
1. **`cuanimus_app`** (`:8888`): Web UI, REST API, Autonomous Engine & Telegram Poller.
2. **`cuanimus_mcp`** (`:8889`): Dedicated Standalone MCP Server.
3. **`cuanimus_db`** (`:5432`): Database PostgreSQL 16.

```bash
# Jalankan seluruh stack container di background
docker compose up -d

# Cek status kesehatan container
docker compose ps

# Pantau log aktif
docker compose logs -f cuanimus
```

### B. Menjalankan Langsung via Host Python (Tanpa Docker)
```bash
# 1. Jalankan di background
./cuanimus-cli ui start --daemon --port 8888

# 2. Cek status
./cuanimus-cli ui status

# 3. Akses via SSH Tunnel (bila di VPS):
ssh -N -L 8888:127.0.0.1:8888 user@ip-server
# Buka http://localhost:8888/ di browser
```

---

## 12. Autonomous Trading Engine & 3 Decision Modes

CUANIMUS menyediakan **Autonomous Trading Engine** kontinu yang memantau market secara otomatis tanpa perlu intervensi klik manual setiap candle.

### Tiga Decision Mode Resmi:
1. **MODE A — STRATEGY AUTOTRADE:**
   Keputusan 100% deterministik dari template strategi kuantitatif (misal: `hybrid_v2c`, `pullback_v2a`).
   `Market Data -> Strategy -> Signal -> Risk Engine -> Execution Engine`
2. **MODE B — AI AGENT AUTOTRADE:**
   AI Agent (misal: Gemini, Hermes, Claude) bertindak sebagai analis & pengambil keputusan terstruktur JSON.
   `Market Context -> AI Agent -> Structured Decision -> Policy Engine -> Risk Engine -> Execution Engine`
3. **MODE C — HYBRID AUTOTRADE:**
   Strategi kuantitatif menjadi **filter sinyal**, dan AI Agent menjadi **konfirmator/decision-maker**. AI hanya dipanggil saat strategi mendeteksi setup, menghemat kuota token AI dan menyaring false signal.
   `Market Data -> Strategy Filter -> AI Confirmation -> Policy Engine -> Risk Engine -> Execution Engine`

### Trading Profiles:
User mengatur autonomous trading melalui **Trading Profiles**:
* **Pair & Timeframe:** (e.g. `BTC/USDT:USDT` • `15m`)
* **Decision Mode:** `Strategy`, `AI Agent`, atau `Hybrid`
* **Risk Profile:** `conservative` (0.5% risk, 3x lev), `balanced`, atau `aggressive`
* **Execution Environment:** `PAPER` atau `LIVE`
* **Idempotensi Candle Tertutup:** Evaluasi strictly dieksekusi pada closed candle terakhir (`timestamp <= T`), mencegah kebocoran sinyal (future leakage).

Profil dapat dibuat, dikloning (*Clone Profile*), di-start, di-pause, atau dihentikan langsung melalui tab **Autonomous Engine** di Web UI atau via Telegram.

---

## 13. Web Control Center & Terminal Trading Manual

Web Control Center (`http://localhost:8888/`) menyediakan antarmuka lengkap tanpa build tool (Zero npm/Node):

### 1. Sinkronisasi Akun Super Admin dari `.env`
Saat server boot pertama kali, kredensial administrator otomatis disinkronkan dari `.env`:
* **Username:** `admin_gemini` (dari `API_SERVER_USERNAME`)
* **Password:** `change_this_to_secure_password` (dari `API_SERVER_PASSWORD`)
* **Keamanan:** PBKDF2-HMAC-SHA256 (100.000 iterasi) dengan salt unik. Token sesi tersimpan aman di `localStorage` browser.

### 2. Quick Manual Order Entry
Di tab **Trading Terminal**, tersedia kotak pemesanan cepat:
* Pilihan **BUY (Long)** atau **SELL (Short)**
* Tipe Order: **LIMIT** atau **MARKET**
* Input: Jumlah Koin, Harga, Stop Loss %, Take Profit %, dan Leverage
* Tombol **Submit Order**: Melewati validasi Risk Engine dan dieksekusi secara instan.

### 3. Kontrol Posisi & Ekspor Data Riil
* **Tutup Posisi 1-Klik:** Tombol merah `Close` pada tabel Active Positions untuk menutup posisi seketika dengan perhitungan PnL riil otomatis.
* **Batal Order:** Tombol `Cancel` pada open orders.
* **Ekspor CSV:** Tombol `📥 Export CSV` di riwayat Closed Trades yang langsung men-stream seluruh rekaman transaksi ke format `.csv`.
* **Mobile Drawer:** Responsif di layar ponsel dengan menu hamburger `☰` dan overlay backdrop.

---

## 14. Bot Telegram Mobile Interaktif

CUANIMUS terintegrasi langsung dengan Telegram Bot dua-arah via long-polling:

### 1. Navigasi Dropdown Kompak
Menggunakan `InlineKeyboardMarkup` yang terbagi rapi ke beberapa kategori:
* **📊 Portofolio & Pasar:** Status platform, Saldo/Equity, Watchlist harga Binance, Posisi terbuka, Kinerja harian, Riwayat order.
* **⚡ Sinyal & Strategi:** Sinyal ETH/BTC/SOL, Katalog strategi, Autonomous Engine.
* **🤖 AI Copilot & Agent:** Status AI & tools MCP, Konsultasi pasar.
* **🛡️ Risiko & Proteksi:** Status Risk Engine, Aktifkan/Reset Kill Switch darurat.
* **🗄️ Database & Sistem:** Status ledger database, switch SQLite/PostgreSQL.

### 2. Kontrol Posisi & Auto Engine 1-Ketukan
* Saat melihat posisi via `/positions`, muncul tombol inline interaktif: `[❌ Tutup BTC #739]` dan `[🚨 Tutup Semua Posisi]`.
* Saat melihat autonomous engine via `/auto`, muncul tombol: `[▶️ Mulai Profil]`, `[⏹️ Hentikan Profil]`, dan `[⚡ Force Eval (Tick)]`.

### 3. Perintah Cepat via Chat:
* `/close [trade_id|all]` — Tutup posisi terbuka tertentu atau seluruhnya.
* `/buy <PAIR> <AMOUNT> [PRICE]` — Buka posisi BUY/LONG manual.
* `/sell <PAIR> <AMOUNT> [PRICE]` — Buka posisi SELL/SHORT manual.
* `/cancel <ORDER_ID>` — Batalkan order limit.
* `/auto_start <PROFILE_ID>` — Jalankan profil trading otomatis.
* `/auto_stop <PROFILE_ID>` — Hentikan profil trading otomatis.
* `/kill` — Emergency Kill Switch seketika.

---

*Selamat meriset, memantau, dan membangun sistem kuantitatif dengan aman bersama CUANIMUS!*
