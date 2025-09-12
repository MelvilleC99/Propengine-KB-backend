#!/bin/bash
# PropertyEngine Support Agent - Backend Startup Script

echo "🚀 Starting PropertyEngine Support Agent Backend"
echo "================================================"

# Check if we're in the right directory
if [ ! -f "main.py" ]; then
    echo "❌ Error: main.py not found. Please run this script from the backend directory."
    echo "   cd /Users/melville/Documents/Propengine-KB-backend"
    exit 1
fi

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Error: Virtual environment not found. Please run:"
    echo "   python3 -m venv venv"
    echo "   source venv/bin/activate"
    echo "   pip install -r requirements_fixed.txt"
    exit 1
fi

# Activate virtual environment
echo "🐍 Activating virtual environment..."
source venv/bin/activate

# Check if required packages are installed
if ! python -c "import fastapi" 2>/dev/null; then
    echo "❌ Error: FastAPI not installed. Installing dependencies..."
    pip install -r requirements_fixed.txt
fi

# Check credentials
echo "🔍 Checking configuration..."
if grep -q "demo_token_replace_with_real" .env; then
    echo "📝 Demo mode - Add real AstraDB credentials to .env for full functionality"
    echo "   ASTRADB_APPLICATION_TOKEN=your_real_token"
    echo "   ASTRADB_API_ENDPOINT=your_real_endpoint"
    echo "   OPENAI_API_KEY=your_real_openai_key"
fi

echo ""
echo "🎯 Starting server on http://127.0.0.1:8000"
echo "📖 API Documentation: http://127.0.0.1:8000/docs"
echo "🔗 Health Check: http://127.0.0.1:8000/api/chat/health"
echo ""
echo "Press Ctrl+C to stop the server"
echo "=================================="

# Start the server
python main.py
