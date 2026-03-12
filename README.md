# MDBQS - Multi-Database Query System

A sophisticated full-stack application for querying multiple heterogeneous databases through a unified natural language interface powered by Google Gemini AI.

## 📋 Project Overview

**MDBQS** is an intelligent query orchestration platform that:

- ✅ Accepts natural language queries from users
- ✅ Decomposes queries into database-specific execution plans using LLM-assisted planning
- ✅ Executes queries in parallel across multiple data sources (PostgreSQL, MongoDB, Neo4j, Milvus)
- ✅ Fuses heterogeneous results with provenance tracking
- ✅ Provides a schema discovery interface for field-level searching
- ✅ Offers both REST API backend and React frontend UI

### Key Features

**Multi-source query execution** — SQL, Document (MongoDB), Graph (Neo4j), Vector (Milvus)  
**LLM-powered planning** — Google Gemini for intelligent query decomposition  
**Parallel execution** — Async task orchestration for fast result aggregation  
**Schema indexing** — Searchable field registry across all data sources  
**Provenance tracking** — Trace which source contributed each data element  
**Model Context Protocol (MCP)** — Plugin architecture for data source integration  

---

## 🏗️ Project Architecture

```
MDBQS/
├── backend/                 # FastAPI backend + multi-database support
│   ├── app/
│   │   ├── main.py                 # FastAPI app setup
│   │   ├── api/v1/                 # API endpoints (query, schema, chat, sources)
│   │   ├── services/               # Core business logic (planner, execution, fusion)
│   │   ├── mcp_plugins/            # Data source adapters (SQL, NoSQL, Graph, Vector)
│   │   ├── models/                 # Pydantic models & data structures
│   │   ├── repositories/           # Data access layer
│   │   ├── core/                   # Config & settings
│   │   └── tests/                  # Automated test suite
│   ├── docker-compose.yml          # Multi-container setup (databases + dependencies)
│   ├── init-postgres/              # PostgreSQL initialization scripts
│   ├── init-mongo/                 # MongoDB initialization scripts
│   ├── init-neo4j/                 # Neo4j initialization scripts
│   ├── init-milvus/                # Milvus initialization scripts
│   ├── scripts/                    # Database seeding scripts
│   ├── requirements.txt            # Python dependencies
│   ├── run-all-servers.ps1         # Windows script to start all services
│   ├── run-all-servers.sh          # Unix/Linux script to start all services
│   └── test.py                     # Simple test runner
│
├── frontend/                # React + Vite + TypeScript UI
│   ├── src/
│   │   ├── api/            # API utilities & services
│   │   ├── components/     # Reusable React components
│   │   ├── store/          # Zustand state management
│   │   ├── types/          # TypeScript definitions
│   │   ├── hooks/          # Custom React hooks
│   │   └── App.tsx         # Main application
│   ├── package.json        # Node.js dependencies
│   ├── vite.config.ts      # Vite configuration
│   └── tsconfig.json       # TypeScript configuration
│
└── README.md               # This file
```

---

## 🛠️ Prerequisites

### System Requirements
- **Docker & Docker Compose** — For containerized databases
- **Python 3.11+** — For the backend
- **Node.js 18+** — For the frontend
- **Git** — For version control

### Backend Requirements
- Python 3.11 or higher
- pip (Python package manager)
- Virtual environment (venv or virtualenv)

### Frontend Requirements
- Node.js 18 or higher
- npm 9+ or yarn

### API Keys
- **Grok API Key** — Required for LLM-powered query planning
  - Get it from [Groq](https://console.groq.com/keys)
  - Add it to `.env` file as `GROQ_API_KEY`

---

## 🚀 Getting Started

### Step 1: Clone the Repository

```bash
git clone <repository-url>
cd MDBQS
```

### Step 2: Setup Environment Variables

Create a `.env` file in the `backend/` directory with the following variables:

```bash
cd backend
# Example .env file
GROQ_API_KEY=your_groq_api_key_here
POSTGRES_DSN=postgresql://postgres:postgrespassword@localhost:5432/mdbs
MONGO_URI=mongodb://localhost:27017/mdbs
NEO4J_URI=neo4j://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=neo4jpassword
MILVUS_HOST=localhost
MILVUS_PORT=19530
```

---

## 🗄️ Database Setup

The project uses **Docker Compose** to orchestrate four heterogeneous databases with their dependencies.

### Step 1: Start All Databases

From the `backend/` directory:

```bash
cd backend
docker-compose up -d
```

This will start:
- ✅ **PostgreSQL 15** — Relational database (port 5432)
- ✅ **MongoDB 6.0** — Document database (port 27017)
- ✅ **Neo4j 5.11** — Graph database (port 7474, 7687)
- ✅ **Milvus 2.2.16** — Vector database (port 19530)
- ✅ **Milvus Dependencies** — Etcd and MinIO services (required for Milvus)

### Step 2: Verify Databases Are Running

```bash
docker ps
```

You should see 7 containers running:
```
CONTAINER ID   IMAGE                                          PORTS
...            postgres:15                                    5432->5432/tcp
...            mongo:6.0                                      27017->27017/tcp
...            neo4j:5.11.0-community                         7474->7474/tcp, 7687->7687/tcp
...            milvusdb/milvus:v2.2.16                        19530->19530/tcp, 9091->9091/tcp
...            quay.io/coreos/etcd:v3.5.5                     2379->2379/tcp
...            minio/minio:RELEASE.2023-03-20T20-16-18Z      9000->9000/tcp
```

### Step 3: Wait for Health Checks

Docker services include health checks. Wait 1-2 minutes for all services to be healthy:

```bash
docker-compose ps
```

Look for `(healthy)` status on all services.

### Step 4: Verify Database Connectivity

#### PostgreSQL
```bash
docker exec mdbs_postgres psql -U postgres -d mdbs -c "SELECT version();"
```

#### MongoDB
```bash
docker exec mdbs_mongo mongo --eval "db.adminCommand('ping')"
```

#### Neo4j
Visit `http://localhost:7474` in a browser (username: `neo4j`, password: `neo4jpassword`)

#### Milvus
```bash
docker logs milvus-standalone | grep "Milvus start successfully"
```

---

## 📊 Populating Databases

After databases are running, populate them with sample data using the provided seeding scripts.

### Prerequisites for Scripts
```bash
cd backend
python -m venv .venv

# Activate virtual environment
# On Windows:
.\.venv\Scripts\Activate.ps1
# On Unix/Linux/macOS:
source .venv/bin/activate

# Install requirements
pip install -r requirements.txt
```

### Seeding Scripts

All seeding scripts are in the `backend/scripts/` directory:

```bash
cd scripts
```

#### 1. PostgreSQL - Seed Customers
```bash
python seed_postgres_customers.py
```
- Creates `customers` table with 150 sample customers
- Includes customer IDs, names, emails, and embeddings
- Takes ~5-10 seconds

#### 2. MongoDB - Seed Orders
```bash
python seed_mongo_orders.py
```
- Creates `orders` collection with 500 sample orders
- Links orders to customer IDs
- Includes order amounts and timestamps
- Takes ~5-10 seconds

#### 3. Neo4j - Seed Referral Network
```bash
python seed_neo4j_referrals.py
```
- Creates referral relationships between customers
- Builds a graph of customer referral connections
- Creates ~1000 referral edges
- Takes ~10-15 seconds

#### 4. Milvus - Seed Vector Embeddings
```bash
python seed_milvus_vectors.py
```
- Creates a vector collection for customer embeddings
- Inserts 150 customer embeddings for similarity search
- Builds the search index
- Takes ~5-10 seconds

### Run All Seeding Scripts at Once
```bash
# From backend/scripts directory
python seed_postgres_customers.py && \
python seed_mongo_orders.py && \
python seed_neo4j_referrals.py && \
python seed_milvus_vectors.py
```

Or run them one at a time for better error visibility.

### Verify Data Loaded

#### PostgreSQL
```bash
docker exec mdbs_postgres psql -U postgres -d mdbs -c "SELECT COUNT(*) FROM customers;"
```
Expected output: `150`

#### MongoDB
```bash
docker exec mdbs_mongo mongo mdbs --eval "db.orders.countDocuments()"
```
Expected output: `500`

#### Neo4j
```bash
docker exec mdbs_neo4j cypher-shell -u neo4j -p neo4jpassword "MATCH (c:Customer) RETURN COUNT(c);"
```
Expected output: `150`

#### Milvus
```bash
python -c "
from pymilvus import Collection
col = Collection('customer_embeddings')
print(f'Milvus records: {col.num_entities}')
"
```
Expected output: `150`

---

## 🔧 Running Backend Services

### Setup Backend Environment

From the `backend/` directory:

```bash
# Create virtual environment (if not already done)
python -m venv .venv

# Activate virtual environment
# Windows:
.\.venv\Scripts\Activate.ps1
# Unix/Linux/macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Option 1: Start All MCP Services (Recommended)

#### On Windows (PowerShell)
```bash
./run-all-servers.ps1
```

This script automatically starts 5 parallel MCP services on ports 8000-8004.

#### On Unix/Linux/macOS
```bash
bash run-all-servers.sh
```

#### To Stop All Services
```bash
# Windows:
./run-all-servers.ps1 stop
# Unix/Linux/macOS:
bash run-all-servers.sh stop
```

### Option 2: Start Services Manually

Start each service in a separate terminal:

#### Terminal 1: Main FastAPI Server
```bash
# From backend/ directory with venv activated
uvicorn app.main:app --port 8000 --reload
```
- Main API server
- Listens on `http://localhost:8000`
- API docs available at `http://localhost:8000/docs`

#### Terminal 2-5: MCP Services
```bash
# Terminal 2
uvicorn app.mcp_plugins.mcp_sql_sample:app --port 8001 --reload

# Terminal 3
uvicorn app.mcp_plugins.mcp_nosql_sample:app --port 8002 --reload

# Terminal 4
uvicorn app.mcp_plugins.mcp_graph_sample:app --port 8003 --reload

# Terminal 5
uvicorn app.mcp_plugins.mcp_vector_sample:app --port 8004 --reload
```

### Verify Backend Services

```bash
# Check main API
curl http://localhost:8000/docs

# Test health endpoint (if available)
curl http://localhost:8000/health
```

---

## 🎨 Running Frontend

### Setup Frontend Environment

From the `frontend/` directory:

```bash
# Install Node.js dependencies
npm install
```

### Start Development Server

```bash
npm run dev
```

The application will be available at `http://localhost:5173`

### Build for Production

```bash
npm run build
```

Output will be in `frontend/dist/`

### Run Linting

```bash
npm run lint
npm run typecheck
```

---

## 🧪 Testing APIs

### Unit & Integration Tests

The backend includes comprehensive tests for all components.

#### Run All Tests
```bash
cd backend

# Make sure virtual environment is activated
# Activate with: .\.venv\Scripts\Activate.ps1 (Windows)
# Or: source .venv/bin/activate (Unix/Linux/macOS)

# Run tests with pytest
pytest
```

#### Run Specific Test Suite
```bash
# End-to-end tests
pytest app/tests/test_end_to_end.py -v

# Error contract tests
pytest app/tests/test_error_contracts.py -v

# MCP adapter tests
pytest app/tests/test_mcp_adapters.py -v

# Vector graph workflow tests
pytest app/tests/test_vector_graph_workflows.py -v

# Connectivity diagnostics
pytest app/tests/test_connectivity_diagnostics.py -v
```

#### Run Simple Test Script
```bash
python test.py
```

This runs a basic test of the query planning, execution, and fusion pipeline.

### API Testing with cURL

#### Test Query Endpoint
```bash
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Show me customers from region A with total orders > 1000"
  }'
```

#### Test Schema Search
```bash
curl http://localhost:8000/api/v1/schema/search?q=customer
```

#### Test Chat Endpoint
```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What are the top customers by order volume?"
  }'
```

### API Documentation (Interactive Swagger UI)

Once the backend is running, visit:
```
http://localhost:8000/docs
```

This provides an interactive interface to test all API endpoints with auto-generated documentation.

---

## 📈 API Endpoints Reference

### Query Endpoint
**POST** `/api/v1/query`

Executes a natural language query across all databases.

**Request:**
```json
{
  "query": "Show me similar customers to cust001",
  "include_provenance": true
}
```

**Response:**
```json
{
  "results": {
    "customer": { ... },
    "similar_customers": [ ... ],
    "orders": [ ... ],
    "referrals": [ ... ]
  },
  "provenance": [
    "Customer info from sql_customers",
    "Similar customers from milvus_vector_search",
    "Orders from nosql_orders",
    "Referrals from graph_referral_network"
  ]
}
```

### Schema Search Endpoint
**GET** `/api/v1/schema/search?q=<query>`

Searches for available fields across all databases.

**Response:**
```json
{
  "results": [
    {
      "source": "sql_customers",
      "fields": ["id", "name", "email"]
    },
    {
      "source": "nosql_orders",
      "fields": ["order_id", "customer_id", "amount"]
    }
  ]
}
```

### Chat Endpoint
**POST** `/api/v1/chat`

Multi-turn conversation interface for queries.

**Request:**
```json
{
  "message": "What are the top customers by order volume?",
  "conversation_id": "conv_123"
}
```

### Sources Endpoint
**GET** `/api/v1/sources`

Lists all connected data sources and their status.

**Response:**
```json
{
  "sources": [
    {
      "name": "sql_customers",
      "type": "sql",
      "status": "connected",
      "port": 8001
    },
    {
      "name": "nosql_orders",
      "type": "nosql",
      "status": "connected",
      "port": 8002
    }
  ]
}
```

---

## 🐛 Troubleshooting

### Databases Not Starting
```bash
# Check Docker daemon is running
docker ps

# View docker-compose logs
docker-compose logs

# Rebuild containers
docker-compose down -v
docker-compose up -d
```

### Database Connection Errors
```bash
# Check if services are healthy
docker-compose ps

# Wait for health checks to pass (2-3 minutes)
# Then try seeding again
```

### Python Virtual Environment Issues
```bash
# Delete and recreate venv
rm -rf .venv  # (rd /s .venv on Windows)
python -m venv .venv

# Reactivate and reinstall
# Windows: .\.venv\Scripts\Activate.ps1
# Unix: source .venv/bin/activate
pip install -r requirements.txt
```

### Frontend Port Already in Use
```bash
# Change port in vite.config.ts or use:
npm run dev -- --port 5174
```

### Backend Port Already in Use
```bash
# Kill process on port 8000
# Windows PowerShell:
Stop-Process -Id (Get-NetTCPConnection -LocalPort 8000).OwningProcess -Force

# Unix/Linux:
lsof -ti :8000 | xargs kill -9
```

### Tests Failing
```bash
# Ensure databases are running and healthy
docker-compose ps

# Ensure all setup scripts have been run
cd scripts
python seed_postgres_customers.py
python seed_mongo_orders.py
python seed_neo4j_referrals.py
python seed_milvus_vectors.py

# Run with verbose output
pytest -vvs
```

### Cannot Connect to Gemini API
```bash
# Verify API key in .env file
cat .env | grep GEMINI_API_KEY

# Ensure key is valid and active from Google AI Studio
# Add it to .env:
GEMINI_API_KEY=your_actual_key_here

# Restart backend service
```

---

## 📚 Development Workflow

### Local Development Setup Checklist
- [ ] Clone repository
- [ ] Create `.env` file with `GEMINI_API_KEY`
- [ ] Start Docker databases: `docker-compose up -d`
- [ ] Wait 2-3 minutes for health checks
- [ ] Run seeding scripts from `backend/scripts/`
- [ ] Activate venv and install Python dependencies
- [ ] Start backend services (all or manually)
- [ ] Install frontend dependencies: `npm install`
- [ ] Start frontend: `npm run dev`
- [ ] Open `http://localhost:5173` in browser

### Common Development Commands

```bash
# Backend
cd backend
.\.venv\Scripts\Activate.ps1                    # Windows
source .venv/bin/activate                       # Unix
uvicorn app.main:app --port 8000 --reload      # Start main server
pytest -vvs                                     # Run tests

# Frontend
cd frontend
npm install                                     # Install deps
npm run dev                                     # Start dev server
npm run build                                   # Build for production
npm run lint                                    # Check code style

# Docker
docker-compose up -d                           # Start databases
docker-compose down -v                         # Stop & remove volumes
docker-compose logs -f <service>               # View logs
```

---

## 📖 Additional Resources

### Key Files & Documentation

- **Backend Architecture:** See [backend/README.md](backend/README.md)
- **Frontend Setup:** See [frontend/README.md](frontend/README.md)
- **Configuration:** See `backend/.env` and `backend/core/config.py`
- **API Tests:** See `backend/app/tests/`

### External Documentation

- **FastAPI:** https://fastapi.tiangolo.com/
- **Docker Compose:** https://docs.docker.com/compose/
- **React + Vite:** https://vitejs.dev/
- **Google Gemini API:** https://ai.google.dev/
- **PyMilvus:** https://github.com/milvus-io/pymilvus

---

## 🤝 Contributing

When making changes:

1. Create a feature branch
2. Make your changes in a separate terminal to avoid disrupting running services
3. Run tests: `pytest`
4. Run linting: `npm run lint` (frontend) or `flake8` (backend)
5. Commit with descriptive messages
6. Push and create a pull request

---

## 📝 License

[Add your license information here]

---

## 🆘 Support

For issues or questions:

1. Check the [Troubleshooting](#-troubleshooting) section
2. Review logs: `docker-compose logs` or test output
3. Check API docs: `http://localhost:8000/docs`
4. Review test files for usage examples

Happy querying! 🚀
