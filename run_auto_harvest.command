#!/bin/zsh
set -e

SCRIPT_DIR="${0:a:h}"
cd "$SCRIPT_DIR"

exec python3 -B -m zet.scripts.auto_harvest_ai_answers --config config.toml
