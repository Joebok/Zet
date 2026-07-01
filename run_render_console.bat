@echo off
cd /d "%~dp0"
python3 -B -m zet.render_console.app --config config.toml
