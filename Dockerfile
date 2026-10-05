# ==============================================================================
# CUANIMUS — Quantitative Trading & AI Agent Operating System
# Production Dockerfile for Web Control Center, MCP Gateway, & Trading Engine
# ==============================================================================
FROM python:3.10-slim

# Labels
LABEL maintainer="CUANIMUS Engineering Team"
LABEL description="CUANIMUS Web Control Center, Quantitative Terminal & Model Context Protocol (MCP) Server"
LABEL version="1.0.0"

# Environment configuration
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DEBIAN_FRONTEND=noninteractive \
    TZ=Asia/Jakarta \
    CUANIMUS_CONTAINERIZED=1 \
    APP_HOME=/app

WORKDIR ${APP_HOME}

# Install minimal OS dependencies for network health checks, SQLite, and building packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    sqlite3 \
    tzdata \
    gcc \
    python3-dev \
    && cp /usr/share/zoneinfo/${TZ} /etc/localtime \
    && echo "${TZ}" > /etc/timezone \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install python packages
COPY requirements.txt ${APP_HOME}/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Create runtime directory structure
RUN mkdir -p \
    ${APP_HOME}/user_data \
    ${APP_HOME}/user_data/data \
    ${APP_HOME}/data \
    ${APP_HOME}/config \
    ${APP_HOME}/.cuanimus \
    ${APP_HOME}/logs \
    ${APP_HOME}/backups \
    ${APP_HOME}/experiments

# Copy application source code
COPY cuanimus ${APP_HOME}/cuanimus
COPY config ${APP_HOME}/config
COPY data ${APP_HOME}/data
COPY docs ${APP_HOME}/docs
COPY experiments ${APP_HOME}/experiments
COPY scripts ${APP_HOME}/scripts
COPY cuanimus-cli ${APP_HOME}/cuanimus-cli
COPY cuanimus.user.yaml ${APP_HOME}/cuanimus.user.yaml

# Ensure execution permissions for CLI
RUN chmod +x ${APP_HOME}/cuanimus-cli

# Expose ports:
# 8888: Web Control Center UI, REST Control Plane API, and integrated /mcp endpoint
# 8889: Dedicated standalone MCP JSON-RPC Server
EXPOSE 8888 8889

# Default Healthcheck on UI & Control Plane API
HEALTHCHECK --interval=15s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8888/health || exit 1

# Default command: Start Web Control Center HTTP Daemon
CMD ["python3", "-m", "cuanimus.cli", "ui", "start", "--host", "0.0.0.0", "--port", "8888"]
