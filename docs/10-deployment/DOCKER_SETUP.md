# Panduan Menjalankan CUANIMUS di Docker

Dokumen ini menjelaskan cara menjalankan **CUANIMUS Web Control Center**, **PostgreSQL Relational Database**, dan **Model Context Protocol (MCP) Server** di dalam Docker menggunakan Docker Compose.

---

## 1. Arsitektur Layanan Docker

CUANIMUS diorkestrasi menggunakan `docker-compose.yml` dengan arsitektur modular:

| Layanan | Container Name | Port | Deskripsi |
| :--- | :--- | :--- | :--- |
| **`cuanimus`** | `cuanimus_app` | `8888` | **Web Control Center UI + Control Plane REST API + Integrated MCP Endpoint (`/mcp`)** |
| **`cuanimus-mcp`** | `cuanimus_mcp` | `8889` | **Dedicated Standalone MCP JSON-RPC 2.0 Server** untuk agen AI eksternal |
| **`cuanimus-db`** | `cuanimus_db` | `5432` | **PostgreSQL 16 Relational Database** dengan inisialisasi skema kuantitatif (`trades`, `orders`, `wallet_history`, `agent_sessions`, `audit_logs`) |
| **`freqtrade_gemini`** | `freqtrade_gemini_futures` | Host | *Opsional/Legacy executor* (dinonaktifkan secara default via Docker Compose profile `freqtrade`) |

---

## 2. Persistensi Volume & Data

Seluruh data state trading dan konfigurasi dipetakan ke persistent volumes di host:
- `./user_data:/app/user_data` — Database SQLite (`tradesv3.dryrun.sqlite`, `cuanimus.sqlite`), market candle futures, dan state wallet.
- `./data:/app/data` — Dataset kuantitatif dan catalog manifest dengan verifikasi SHA256.
- `./config:/app/config` — Definisi konfigurasi strategi dan risk profile.
- `./.cuanimus:/app/.cuanimus` — Kredensial autentikasi Web admin dan token MCP AI Agent.
- `./logs:/app/logs` — Audit log kriptografis AI Agent (`agent_audit.jsonl`).
- `./experiments:/app/experiments` — Catatan revalidasi backtest kuantitatif.
- `cuanimus_pgdata` — Volume PostgreSQL untuk relasional query jangka panjang.

---

## 3. Cara Penggunaan Cepat

### A. Menggunakan Helper Script (`deploy/docker.sh`)

Script pembantu telah disediakan di `deploy/docker.sh`:

```bash
# Menjalankan seluruh layanan di background (build + up)
./deploy/docker.sh start

# Memeriksa status kesehatan container
./deploy/docker.sh status

# Menjalankan diagnostic System Doctor di dalam container
./deploy/docker.sh doctor

# Melihat live logs (seluruh layanan)
./deploy/docker.sh logs

# Melihat live logs layanan spesifik
./deploy/docker.sh logs cuanimus
./deploy/docker.sh logs cuanimus-db
./deploy/docker.sh logs cuanimus-mcp

# Menghentikan seluruh container
./deploy/docker.sh stop
```

---

### B. Menggunakan Perintah Standar `docker compose`

```bash
# 1. Build image dan jalankan container di background
docker compose up -d --build

# 2. Cek status container
docker compose ps

# 3. Jalankan command CLI di dalam container cuanimus
docker compose exec cuanimus python3 -m cuanimus.cli status
docker compose exec cuanimus python3 -m cuanimus.cli doctor

# 4. Stop seluruh container
docker compose down
```

---

## 4. Endpoints & Akses Jaringan

Setelah container aktif:
- **Web Control Center UI**: `http://<IP_HOST>:8888/`
- **Control Plane Health Check**: `http://<IP_HOST>:8888/health`
- **Integrated MCP Endpoint**: `http://<IP_HOST>:8888/mcp`
- **Dedicated Standalone MCP Endpoint**: `http://<IP_HOST>:8889/` (Health check: `http://<IP_HOST>:8889/health`)
- **PostgreSQL Database**: `localhost:5432` (Database: `cuanimus`, User: `cuanimus`)

---

## 5. Menjalankan Legacy Freqtrade (Opsional)

Jika Anda ingin menjalankan container eksekutor legacy Freqtrade bersamaan:

```bash
docker compose --profile freqtrade up -d
```

---

## 6. Pengalihan Database (SQLite vs PostgreSQL)

Secara default, CUANIMUS beroperasi menggunakan **SQLite** (`user_data/tradesv3.dryrun.sqlite`) tanpa konfigurasi rumit. Namun, Anda dapat mengalihkan database ke **PostgreSQL** kapan saja dengan data migration otomatis:

### A. Cek Status Database Saat Ini
```bash
./deploy/docker.sh cli db status
```
Output akan menampilkan backend aktif (`SQLITE` atau `POSTGRESQL`), koneksi, dan jumlah record tabel.

### B. Migrasi Data dari SQLite ke PostgreSQL
Sebelum atau sesudah beralih, salin seluruh 734 trade, 1.579 order, dan wallet history yang ada di SQLite ke PostgreSQL secara aman dan idempotent:
```bash
./deploy/docker.sh cli db migrate
```

### C. Alihkan Aktif ke PostgreSQL
```bash
./deploy/docker.sh cli db switch postgres
```
Perintah ini otomatis memperbarui file konfigurasi `cuanimus.user.yaml` dan mengarahkan seluruh pembacaan/penulisan runtime ke container PostgreSQL (`cuanimus-db:5432`).

### D. Alihkan Kembali ke SQLite
Jika ingin kembali ke SQLite default:
```bash
./deploy/docker.sh cli db switch sqlite
```
