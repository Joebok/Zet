@echo off
cd /d "%~dp0"
python3 -B -m zet.web.app --config config.toml --host 127.0.0.1 --port 8080
