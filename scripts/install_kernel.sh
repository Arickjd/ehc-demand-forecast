#!/usr/bin/env bash
# Registra o kernel do venv do projeto no Jupyter (para aparecer no seletor de kernel)
set -euo pipefail

cd "$(dirname "$0")/.."

.venv/bin/python -m ipykernel install --user \
  --name ehc-demand-forecast \
  --display-name "Python (ehc-demand-forecast)"

echo "Kernel 'ehc-demand-forecast' registrado."
