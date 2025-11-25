#!/bin/bash
# Restart backend server

cd /Users/maxent/src/SRS4Autism

# Stop existing backend
pkill -f "python.*run.py"
sleep 2

# Start backend with venv
source venv/bin/activate
cd backend
nohup python run.py > ../data/logs/backend.log 2>&1 &
BACKEND_PID=$!

echo "Backend started with PID: $BACKEND_PID"
echo "Logs: data/logs/backend.log"
echo "View with: tail -f data/logs/backend.log"

