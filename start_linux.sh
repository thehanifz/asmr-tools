#!/bin/bash
echo "Starting ASMR Video Tool..."
python3 server.py &
sleep 2
xdg-open http://localhost:8000 2>/dev/null || echo "Open browser: http://localhost:8000"
