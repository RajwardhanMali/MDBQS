#!/bin/bash

# MDBQS - Run All Servers Script
# Starts Docker containers (PostgreSQL, MongoDB, Neo4j, Milvus) and FastAPI backend

echo "================================"
echo "MDBQS - Starting All Servers"
echo "================================"
echo ""

# Check if Docker is running
echo "[1/3] Checking Docker..."
if ! docker ps > /dev/null 2>&1; then
    echo "ERROR: Docker daemon is not running. Please start Docker."
    exit 1
fi
echo "✓ Docker is running"

echo ""

# Start Docker containers
echo "[2/3] Starting Docker containers (PostgreSQL, MongoDB, Neo4j, Milvus)..."
docker-compose up -d
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to start Docker containers."
    exit 1
fi
echo "✓ Docker containers started"

echo ""

# Wait for databases to be ready
echo "[3/3] Waiting for databases to be healthy (30 seconds)..."
sleep 5

# Check PostgreSQL
echo "  • Checking PostgreSQL..."
maxAttempts=10
attempt=0
while [ $attempt -lt $maxAttempts ]; do
    if docker-compose exec -T postgres pg_isready -U postgres 2>&1 | grep -q "accepting connections"; then
        echo "    ✓ PostgreSQL is ready"
        break
    fi
    ((attempt++))
    sleep 2
done

if [ $attempt -eq $maxAttempts ]; then
    echo "    ⚠ PostgreSQL may not be ready yet"
fi

# Check MongoDB
echo "  • Checking MongoDB..."
attempt=0
while [ $attempt -lt $maxAttempts ]; do
    if docker-compose exec -T mongo mongo --eval "db.adminCommand('ping')" 2>&1 | grep -q "ok"; then
        echo "    ✓ MongoDB is ready"
        break
    fi
    ((attempt++))
    sleep 2
done

if [ $attempt -eq $maxAttempts ]; then
    echo "    ⚠ MongoDB may not be ready yet"
fi

# Check Neo4j
echo "  • Checking Neo4j..."
if docker-compose logs neo4j 2>&1 | grep -q "started"; then
    echo "    ✓ Neo4j is ready"
else
    echo "    ⚠ Neo4j may not be ready yet"
fi

echo ""
echo "================================"
echo "Backend Startup"
echo "================================"
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "ERROR: Virtual environment not found. Please run:"
    echo "  python3 -m venv venv"
    echo "  source venv/bin/activate"
    echo "  pip install -r requirements.txt"
    exit 1
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

echo ""
echo "Starting FastAPI backend on http://localhost:8000"
echo "Swagger UI: http://localhost:8000/docs"
echo "ReDoc: http://localhost:8000/redoc"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Start FastAPI
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
