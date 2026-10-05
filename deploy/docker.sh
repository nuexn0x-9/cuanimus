#!/usr/bin/env bash
# ==============================================================================
# CUANIMUS — Docker Control & Lifecycle Helper Script
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${PROJECT_ROOT}"

show_help() {
    cat <<EOF
CUANIMUS Docker Control Helper

Usage: ./deploy/docker.sh [command]

Commands:
  start          Build and start CUANIMUS, Database, and MCP services in background
  stop           Stop all CUANIMUS Docker containers
  restart        Restart all CUANIMUS Docker containers
  status         Show status and health of running containers
  logs           Follow logs of all services (or specify service: cuanimus | cuanimus-db | cuanimus-mcp)
  doctor         Run CUANIMUS System Doctor diagnostic inside the container
  cli <args>     Execute any cuanimus-cli command inside the container
  build          Force rebuild the CUANIMUS Docker image
  shell          Open an interactive bash shell inside the cuanimus container

Examples:
  ./deploy/docker.sh start
  ./deploy/docker.sh status
  ./deploy/docker.sh doctor
  ./deploy/docker.sh logs cuanimus
  ./deploy/docker.sh cli status
EOF
}

cmd="${1:-status}"

case "${cmd}" in
    start)
        echo "--> Building and starting CUANIMUS Docker services..."
        docker compose up -d --build
        echo ""
        echo "[OK] Services started."
        docker compose ps
        ;;
    stop)
        echo "--> Stopping CUANIMUS Docker services..."
        docker compose down
        echo "[OK] All services stopped."
        ;;
    restart)
        echo "--> Restarting CUANIMUS Docker services..."
        docker compose restart
        docker compose ps
        ;;
    status)
        echo "--> CUANIMUS Docker Container Status:"
        docker compose ps
        ;;
    logs)
        shift || true
        target="${1:-}"
        if [ -n "${target}" ]; then
            docker compose logs -f "${target}"
        else
            docker compose logs -f
        fi
        ;;
    doctor)
        echo "--> Running CUANIMUS Doctor inside Docker container:"
        docker compose exec cuanimus python3 -m cuanimus.cli doctor
        ;;
    cli)
        shift
        docker compose exec cuanimus python3 -m cuanimus.cli "$@"
        ;;
    build)
        echo "--> Building CUANIMUS Docker image..."
        docker compose build
        ;;
    shell)
        echo "--> Opening bash shell in cuanimus container:"
        docker compose exec -it cuanimus bash
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        echo "Unknown command: ${cmd}"
        show_help
        exit 1
        ;;
esac
