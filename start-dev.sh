#!/bin/bash

# PPV Fulfillment Monitor - Development Startup Script

echo "🚀 Starting PPV Fulfillment Monitor Development Environment..."

# Check if PostgreSQL is running
if ! brew services list | grep -q "postgresql@15.*started"; then
    echo "📄 Starting PostgreSQL..."
    brew services start postgresql@15
    sleep 2
fi

# Export PostgreSQL PATH
export PATH="/usr/local/opt/postgresql@15/bin:$PATH"

echo "✅ PostgreSQL running"

# Start backend in background
echo "🐍 Starting FastAPI Backend (http://localhost:8001)..."
cd backend
python3 -m uvicorn src.main:app --host 0.0.0.0 --port 8001 --reload &
BACKEND_PID=$!
cd ..

# Wait for backend to start
sleep 3

# Start frontend in background
echo "⚛️  Starting React Frontend (http://localhost:3001)..."
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

# Wait for services to fully start
sleep 5

echo "🎉 Development environment ready!"
echo ""
echo "📍 Services:"
echo "   Backend API:  http://localhost:8001"
echo "   Frontend App: http://localhost:3001"
echo "   API Docs:     http://localhost:8001/docs"
echo ""
echo "🛑 To stop: Press Ctrl+C or run ./stop-dev.sh"

# Keep script running and handle Ctrl+C
trap 'echo "🛑 Stopping services..."; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0' INT

# Wait for processes
wait