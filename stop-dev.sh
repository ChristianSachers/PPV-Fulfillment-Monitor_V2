#!/bin/bash

# PPV Fulfillment Monitor - Stop Development Services

echo "🛑 Stopping PPV Fulfillment Monitor Development Environment..."

# Kill any running FastAPI processes on port 8001
echo "🐍 Stopping FastAPI Backend..."
lsof -ti:8001 | xargs kill -9 2>/dev/null || echo "   No backend process found"

# Kill any running Vite processes 
echo "⚛️  Stopping React Frontend..."
pkill -f "vite" 2>/dev/null || echo "   No frontend process found"

# Optional: Stop PostgreSQL (comment out if you want to keep it running)
# echo "📄 Stopping PostgreSQL..."
# brew services stop postgresql@15

echo "✅ All development services stopped"