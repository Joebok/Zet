@echo off
cd /d "%~dp0"
python3 -B -m zet.scripts.auto_harvest_ai_answers --config config.toml
