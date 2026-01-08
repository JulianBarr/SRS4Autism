#!/bin/bash
# Restart backend server

cd /Users/maxent/src/SRS4Autism

# Stop existing backend
pkill -f "python.*run.py"
sleep 2

# Start backend with venv
source venv/bin/activate

# === ADD THESE PROXY SETTINGS ===
# ShadowsocksX-NG default HTTP port is 1087
export http_proxy=http://127.0.0.1:1087
export https_proxy=http://127.0.0.1:1087
export HTTP_PROXY=http://127.0.0.1:1087
export HTTPS_PROXY=http://127.0.0.1:1087
export NO_PROXY=localhost,127.0.0.1
# ================================

#cd backend
nohup python backend/run.py > data/logs/backend.log 2>&1 &
BACKEND_PID=$!

echo "Backend started with PID: $BACKEND_PID"
echo "Logs: data/logs/backend.log"
echo "View with: tail -f data/logs/backend.log"
