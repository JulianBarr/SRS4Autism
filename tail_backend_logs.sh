#!/bin/bash
# Tail backend logs in real-time

echo "📋 Viewing backend logs..."
echo "Press Ctrl+C to stop"
echo ""

# Find backend process
BACKEND_PID=$(ps aux | grep -E "python.*backend/run.py" | grep -v grep | awk '{print $2}' | head -1)

if [ -z "$BACKEND_PID" ]; then
    echo "❌ Backend not running"
    exit 1
fi

echo "Backend PID: $BACKEND_PID"
echo "Terminal: ttys055"
echo ""
echo "To see logs, you can:"
echo ""
echo "1. Find the terminal window (look for 'ttys055' or 'backend/run.py')"
echo ""
echo "2. Or check if there's a log file:"
echo "   tail -f /Users/maxent/src/SRS4Autism/data/logs/backend.log"
echo ""
echo "3. Or restart backend to enable file logging:"
echo "   cd /Users/maxent/src/SRS4Autism/backend"
echo "   python run.py"
echo "   (logs will be in data/logs/backend.log)"


