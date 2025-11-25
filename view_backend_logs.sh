#!/bin/bash
# Script to view backend logs

# Find the backend process
BACKEND_PID=$(ps aux | grep -E "python.*backend/run.py|uvicorn.*main:app" | grep -v grep | awk '{print $2}' | head -1)

if [ -z "$BACKEND_PID" ]; then
    echo "❌ Backend process not found. Is the backend running?"
    exit 1
fi

echo "📋 Backend process found: PID $BACKEND_PID"
echo "📍 Terminal: $(ps -p $BACKEND_PID -o tty= 2>/dev/null || echo 'unknown')"
echo ""
echo "To view logs, you can:"
echo ""
echo "1. Find the terminal window (look for terminal with 'backend/run.py' in title)"
echo ""
echo "2. Or tail the process output (if redirected to a file):"
echo "   tail -f /path/to/logfile"
echo ""
echo "3. Or check recent print statements by looking at the process:"
echo "   strace -p $BACKEND_PID -e write 2>&1 | grep --line-buffered '^ |' | cut -c11-"
echo ""
echo "4. Or restart backend with log file:"
echo "   cd /Users/maxent/src/SRS4Autism/backend"
echo "   python run.py 2>&1 | tee backend.log"
echo ""
echo "Current process info:"
ps -p $BACKEND_PID -o pid,ppid,tty,command

