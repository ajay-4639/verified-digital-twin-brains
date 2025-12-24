#!/bin/bash
# Local Development Script (Linux/Mac)
# Starts backend and frontend concurrently for local testing

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

echo ""
echo "========================================"
echo "  Local Development Environment"
echo "========================================"
echo ""

# Check for backend .env
if [ ! -f "$REPO_ROOT/backend/.env" ]; then
    echo "[!] backend/.env not found"
    echo "    Copy backend/.env.example to backend/.env and add your keys"
    read -p "Create from .env.example now? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        cp "$REPO_ROOT/backend/.env.example" "$REPO_ROOT/backend/.env"
        echo "    Created backend/.env - please edit and add your keys"
    fi
fi

# Check for frontend .env.local
if [ ! -f "$REPO_ROOT/frontend/.env.local" ]; then
    echo "[!] frontend/.env.local not found - creating..."
    cat > "$REPO_ROOT/frontend/.env.local" << EOF
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
NEXT_PUBLIC_SUPABASE_URL=your-supabase-url
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-supabase-anon-key
EOF
    echo "    Created frontend/.env.local - please edit and add your Supabase keys"
fi

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "Stopping services..."
    kill $BACKEND_PID 2>/dev/null || true
    kill $FRONTEND_PID 2>/dev/null || true
    exit 0
}
trap cleanup SIGINT SIGTERM

# Start Backend
echo ""
echo "[Backend] Starting on port 8000..."
cd "$REPO_ROOT/backend"

# Activate venv if exists
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

pip install -r requirements.txt -q
uvicorn main:app --reload --port 8000 &
BACKEND_PID=$!

# Wait for backend to start
sleep 3

# Start Frontend
echo ""
echo "[Frontend] Starting on port 3000..."
cd "$REPO_ROOT/frontend"
npm install --silent
npm run dev &
FRONTEND_PID=$!

echo ""
echo "========================================"
echo "  Services Running"
echo "========================================"
echo ""
echo "  Backend:  http://localhost:8000"
echo "  Frontend: http://localhost:3000"
echo "  Swagger:  http://localhost:8000/docs"
echo ""
echo "  Press Ctrl+C to stop all services"
echo ""

# Open browser
sleep 5
if command -v open &> /dev/null; then
    open http://localhost:3000
elif command -v xdg-open &> /dev/null; then
    xdg-open http://localhost:3000
fi

# Wait for processes
wait
