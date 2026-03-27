@echo off
echo Starting ASMR Video Tool...
start /B python server.py
timeout /t 2 /nobreak >nul
start http://localhost:8000
echo Server running at http://localhost:8000
pause
