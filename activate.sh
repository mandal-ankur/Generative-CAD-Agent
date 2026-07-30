#!/usr/bin/env zsh
# activate.sh — Activate the shared .env virtual environment for this project.
#
# Usage:
#   source activate.sh        # activates .env and sets UV_PROJECT_ENVIRONMENT
#
# This tells uv to always use .env (symlinked to ../docs/.env) and never
# auto-create a .venv directory.

SCRIPT_DIR="${0:A:h}"
export UV_PROJECT_ENVIRONMENT="${SCRIPT_DIR}/.env"

source "${SCRIPT_DIR}/.env/bin/activate"

echo "✅ Activated: ${VIRTUAL_ENV}"
echo "   Python: $(python --version)"
echo "   UV_PROJECT_ENVIRONMENT=${UV_PROJECT_ENVIRONMENT}"
