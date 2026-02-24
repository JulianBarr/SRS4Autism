#!/bin/bash
# start_app.sh - Robust Version
# 1. Kills processes
# 2. WAITS for ports to actually clear
# 3. Starts app

# --- Helper to kill a specific port holder ---
kill_port() {
    PORT=$1
    PID=$(lsof -ti:$PORT)
    if [ -n "$PID" ]; then
        echo "   🔪 Killing process on port $PORT (PID: $PID)..."
        kill -9 $PID
    fi
}

echo "🧹 Cleaning up old processes..."

# 1. Kill by name (just in case)
pkill -f "electron"
pkill -f "python.*run.py"
pkill -f "uvicorn"

# 2. Kill by port (The most accurate way)
kill_port 8000
kill_port 3000

# 3. VERIFICATION LOOP (The Fix)
# We wait up to 10 seconds for the OS to release the ports
echo "⏳ Verifying ports are clear..."
MAX_RETRIES=10
count=0

while lsof -ti:8000 >/dev/null || lsof -ti:3000 >/dev/null; do
    echo "   ... waiting for ports to release (attempt $((count+1))/$MAX_RETRIES)"
    
    # Aggressively kill again if it's still there
    kill_port 8000
    kill_port 3000
    
    sleep 1
    count=$((count+1))
    if [ $count -ge $MAX_RETRIES ]; then
        echo "❌ ERROR: Port 8000 or 3000 is STUCK. Please reboot or run 'kill -9 <PID>' manually."
        exit 1
    fi
done

echo "✅ Ports are clear!"

# 4. Set Proxy Settings (ShadowsocksX-NG)
echo "🌐 Setting up proxy..."
export http_proxy=socks5://127.0.0.1:56435
export https_proxy=socks5://127.0.0.1:56435
export HTTP_PROXY=socks5://127.0.0.1:56435
export HTTPS_PROXY=socks5://127.0.0.1:56435
export NO_PROXY=localhost,127.0.0.1,0.0.0.0
export BROWSER=none

# 5. Start the App
echo "🚀 Starting SRS4Autism..."
cd frontend
npm run electron:dev
