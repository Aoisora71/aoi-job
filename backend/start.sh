#!/bin/bash

# Script to kill any process on port 8003 and start the backend server

PORT=8003

echo "🔍 Checking for processes on port $PORT..."

# Try to find and kill process on port 8003
if command -v lsof &> /dev/null; then
    PID=$(lsof -ti:$PORT 2>/dev/null)
    if [ ! -z "$PID" ]; then
        echo "🛑 Killing process $PID on port $PORT..."
        kill -9 $PID 2>/dev/null
        sleep 1
    fi
elif command -v fuser &> /dev/null; then
    fuser -k $PORT/tcp 2>/dev/null
    sleep 1
elif command -v netstat &> /dev/null; then
    PID=$(netstat -tlnp 2>/dev/null | grep ":$PORT " | awk '{print $7}' | cut -d'/' -f1 | head -1)
    if [ ! -z "$PID" ]; then
        echo "🛑 Killing process $PID on port $PORT..."
        kill -9 $PID 2>/dev/null
        sleep 1
    fi
elif command -v ss &> /dev/null; then
    PID=$(ss -tlnp 2>/dev/null | grep ":$PORT " | awk '{print $6}' | cut -d',' -f2 | cut -d'=' -f2 | head -1)
    if [ ! -z "$PID" ]; then
        echo "🛑 Killing process $PID on port $PORT..."
        kill -9 $PID 2>/dev/null
        sleep 1
    fi
fi

# Verify port is free
if command -v lsof &> /dev/null; then
    if lsof -ti:$PORT &> /dev/null; then
        echo "⚠️  Warning: Port $PORT may still be in use"
    else
        echo "✅ Port $PORT is free"
    fi
fi

echo "🚀 Starting backend server on port $PORT..."
cd "$(dirname "$0")"
python3 main.py

