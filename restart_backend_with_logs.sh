#!/bin/bash
# Restart backend with visible logging

cd /Users/maxent/src/SRS4Autism

echo "🛑 Stopping existing backend..."
# Kill existing backend
pkill -f "python.*backend/run.py" || pkill -f "uvicorn.*main:app" || echo "No existing backend found"

sleep 2

echo "🚀 Starting backend with logging..."
echo "📝 Logs will be written to: data/logs/backend.log"
echo ""

# Start backend in background with logging
cd backend
python run.py > ../data/logs/backend.log 2>&1 &
BACKEND_PID=$!

echo "✅ Backend started with PID: $BACKEND_PID"
echo ""
echo "To view logs in real-time, run:"
echo "  tail -f /Users/maxent/src/SRS4Autism/data/logs/backend.log"
echo ""
echo "Or open the log file:"
echo "  open /Users/maxent/src/SRS4Autism/data/logs/backend.log"

