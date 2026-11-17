#!/bin/bash
M=/home/hatch/workspace/asmr-service/jobs/rain-garden-1hour.json
for i in $(seq 1 45); do
  grep -q '"videoId": "' "$M" 2>/dev/null && break
  sleep 60
done
~/workspace/projects/asmr-tools/venv/bin/python /home/hatch/workspace/asmr-service/set_publish.py "$M" "2026-11-16T12:30:00Z" >> /home/hatch/workspace/asmr-service/logs/upload_rain_garden.log 2>&1
echo "SCHEDULE-APPLIED $(date)" >> /home/hatch/workspace/asmr-service/logs/upload_rain_garden.log
