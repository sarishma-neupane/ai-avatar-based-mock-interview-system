#!/bin/bash

# Script to start Django backend server
# Usage: ./start_server.sh

echo "🚀 Starting Django Backend Server..."
echo ""

# Check if virtual environment exists
if [ -d "env" ]; then
    echo "📦 Activating virtual environment (env)..."
    source env/bin/activate
elif [ -d "venv" ]; then
    echo "📦 Activating virtual environment (venv)..."
    source venv/bin/activate
else
    echo "⚠️  No virtual environment found. Using system Python."
fi

# Check if port 8000 is in use
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null ; then
    echo "⚠️  Port 8000 is already in use!"
    echo "   Killing existing process..."
    lsof -ti:8000 | xargs kill -9
    sleep 1
fi

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "⚠️  Warning: .env file not found!"
    echo "   Please create a .env file with GEMINI_API_KEY"
fi

# Run migrations
echo ""
echo "🔄 Running database migrations..."
python manage.py migrate --noinput

# Start server
echo ""
# should be localhost:8000
echo "✅ Starting Django development server on http://localhost:8000"
echo "   Press Ctrl+C to stop the server"
echo ""
python manage.py runserver

