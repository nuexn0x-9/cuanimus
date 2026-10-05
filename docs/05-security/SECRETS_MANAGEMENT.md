# Security Specification: Secrets Governance & Audit Report
## Project: CUANIMUS — Enterprise Security Architecture

- **Document Version:** 1.0.0
- **Date:** 2026-10-03
- **Status:** COMPLETED / ACTION REQUIRED (ROTATION)
- **Classification:** CRITICAL SECURITY NOTICE

---

## 1. Executive Summary & Audit Findings

An exhaustive forensic scan of the codebase and its commit history was conducted. Multiple active production credentials were discovered hardcoded in plaintext:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        SECRET AUDIT FINDINGS                           │
├─────────────────────┬──────────────────┬──────────────┬────────────────┤
│ Secret Type         │ Location Found   │ Git Commit   │ Status         │
├─────────────────────┼──────────────────┼──────────────┼────────────────┤
│ Binance Futures Key │ config.json      │ 5b080e7      │ COMPROMISED    │
│ Binance Secret      │ config_agresif   │ 20d47d1      │ COMPROMISED    │
├─────────────────────┼──────────────────┼──────────────┼────────────────┤
│ Gemini API Key      │ docker-compose   │ 5b080e7      │ COMPROMISED    │
├─────────────────────┼──────────────────┼──────────────┼────────────────┤
│ Telegram Bot Token  │ config_agresif   │ 20d47d1      │ COMPROMISED    │
│ Telegram Chat ID    │ config_agresif   │ 20d47d1      │ COMPROMISED    │
├─────────────────────┼──────────────────┼──────────────┼────────────────┤
│ API Server Password │ config.json      │ 5b080e7      │ COMPROMISED    │
│ JWT Secret Key      │ config_agresif   │ 20d47d1      │ COMPROMISED    │
└─────────────────────┴──────────────────┴──────────────┴────────────────┘
```

> [!CAUTION]
> **COMPROMISED CREDENTIAL ADVISORY:**
> Because these secrets exist in the git commit object database (`5b080e7` and `20d47d1`), removing them from the working tree does **NOT** protect them if this repository is pushed to a remote remote (GitHub, GitLab, etc.).
> 
> **Immediate Action Required by Operator:**
> 1. **Binance API:** Log into Binance, immediately **DELETE** the compromised API key, and generate a new key pair. Ensure "Enable Withdrawals" remains **DISABLED**.
> 2. **Google AI Studio:** Revoke the exposed Gemini API key and create a new project key.
> 3. **Telegram:** Message `@BotFather`, revoke the existing bot token, and generate a new token.

---

## 2. Remediation Architecture

The repository has been restructured to enforce zero-secret persistence:

1. **Environment Variable Injection:**
   - All credentials are extracted into `.env` (ignored by git).
   - `.env.example` provides the canonical template with documentation for operators.
2. **Configuration Sanitization:**
   - `docker-compose.yml` uses `env_file: .env` rather than inline environment values.
   - `user_data/config.example.json` provides a clean reference template using `${VAR}` substitution syntax.
3. **Repository Defense:**
   - `.gitignore` explicitly blocks `.env*`, `config.json`, `config_agresif.json`, and database files.

---

## 3. Pre-Commit Secret Scanner Configuration

To prevent future regression, contributors must run automated secret scanners before committing:
```bash
# Install Gitleaks pre-commit hook
pip install pre-commit
cat << 'EOF' > .pre-commit-config.yaml
repos:
  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.18.2
    hooks:
      - id: gitleaks
EOF
pre-commit install
```
