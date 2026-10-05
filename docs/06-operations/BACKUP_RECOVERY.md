# Operations Specification: Database Safety & Disaster Recovery
## Project: CUANIMUS — High-Reliability Operations

- **Document Version:** 1.0.0
- **Date:** 2026-10-03
- **Status:** VERIFIED & TESTED

---

## 1. Database Persistence Verification

### 1.1 Root-Cause Analysis of Persistence Flaw
In the original setup:
- `docker-compose.yml` mounted `./user_data:/freqtrade/user_data`.
- However, Freqtrade's default SQLite dry-run database was written to `/freqtrade/tradesv3.dryrun.sqlite` (outside `/freqtrade/user_data/`).
- **Consequence:** Running `docker compose down` and recreating the container would destroy all trade history.

### 1.2 Remediated Architecture
- Both `config.json` and `config_agresif.json` now explicitly declare:
  ```json
  "db_url": "sqlite:////freqtrade/user_data/tradesv3.dryrun.sqlite"
  ```
- The database is physically stored on the host filesystem at:
  `/home/zero/ai-gemini-futures-bot/user_data/tradesv3.dryrun.sqlite`.
- **Proof of Re-creation Safety:** Because `./user_data` is mounted to `/freqtrade/user_data`, any `docker compose down && docker compose up -d` cycle retains 100% of the SQLite database tables, trade history, and open orders.

---

## 2. Automated Hot-Backup Procedure

SQLite databases running in WAL (Write-Ahead Logging) mode must be backed up using the SQLite Online Backup API to prevent corrupted snapshots caused by raw file copies during active transactions.

### 2.1 Python Online Backup Script (`cuanimus.ops.backup`)
```python
import sqlite3
import os
from datetime import datetime

def perform_sqlite_backup(source_path: str, backup_dir: str = "user_data/backups") -> str:
    os.makedirs(backup_dir, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    target_path = os.path.join(backup_dir, f"tradesv3_backup_{timestamp}.sqlite")

    src = sqlite3.connect(source_path)
    dst = sqlite3.connect(target_path)
    src.backup(dst, pages=100) # Incremental 100-page slices
    dst.close()
    src.close()
    return target_path
```

---

## 3. Disaster Recovery & Restoration Verification

To restore from a backup:
1. Stop the trading container:
   ```bash
   docker compose down
   ```
2. Verify integrity of the backup file:
   ```bash
   sqlite3 user_data/backups/tradesv3_backup_XXXX.sqlite "PRAGMA integrity_check;"
   # Expected output: ok
   ```
3. Restore backup to active path:
   ```bash
   cp user_data/backups/tradesv3_backup_XXXX.sqlite user_data/tradesv3.dryrun.sqlite
   ```
4. Restart container:
   ```bash
   docker compose up -d
   ```
5. Verify logs for zero corruption warnings:
   ```bash
   docker logs --tail 50 freqtrade_gemini_futures
   ```
