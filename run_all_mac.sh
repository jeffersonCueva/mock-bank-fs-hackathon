#!/usr/bin/env bash
set -euo pipefail

# Adjust if your venv folder name is different
VENV_DIR=".venv"

if [[ ! -d "${VENV_DIR}" ]]; then
  echo "Venv directory '${VENV_DIR}' not found."
  exit 1
fi

VENV_PY="${VENV_DIR}/bin/python"

if [[ ! -x "${VENV_PY}" ]]; then
  echo "Python not found at '${VENV_PY}'."
  exit 1
fi

osascript <<EOF
tell application "Terminal"
  do script "cd \"${PWD}\"; export BANK_NAME=gcash; \"${VENV_PY}\" -m uvicorn run_bank_gcash:app --port 8000 --reload"
  do script "cd \"${PWD}\"; export BANK_NAME=bpi; \"${VENV_PY}\" -m uvicorn run_bank_bpi:app --port 8001 --reload"
  do script "cd \"${PWD}\"; \"${VENV_PY}\" -m uvicorn clearing_house.main:app --port 9000 --reload"
  activate
end tell
EOF

echo "All services started."
