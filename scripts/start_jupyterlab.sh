#!/usr/bin/env bash
# Sobe o JupyterLab usando o venv do projeto e as variáveis do .env
set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
  echo "ERRO: .env não encontrado. Rode: cp .env.example .env" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1091
source .env
set +a

HOST="${JUPYTERLAB_HOST:-127.0.0.1}"
PORT="${JUPYTERLAB_PORT:-8888}"
TOKEN="${JUPYTERLAB_TOKEN:-}"

exec .venv/bin/jupyter lab \
  --ip="$HOST" \
  --port="$PORT" \
  --no-browser \
  --notebook-dir="$(pwd)" \
  --IdentityProvider.token="$TOKEN" \
  --ServerApp.allow_origin='*' \
  --ServerApp.disable_check_xsrf=True
