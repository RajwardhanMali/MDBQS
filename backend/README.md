# MDBQS Backend - Multi-Database Query System

A sophisticated FastAPI-based backend that enables querying multiple heterogeneous databases (SQL, NoSQL, Graph, Vector) through a unified natural language interface powered by Google Gemini AI.

## 📋 Overview

**MDBQS** (Multi-Database Query System) is an intelligent query orchestration platform that:

- Accepts natural language queries from users
- Decomposes queries into database-specific execution plans using LLM-assisted planning
- Executes queries in parallel across multiple data sources (PostgreSQL, MongoDB, Neo4j, Milvus)
- Fuses heterogeneous results with provenance tracking
- Provides a schema discovery interface for field-level searching

### Key Features

✅ **Multi-source query execution** — SQL, Document (MongoDB), Graph (Neo4j), Vector (Milvus)  
✅ **LLM-powered planning** — Google Gemini 2.5 Flash for intelligent query decomposition  
✅ **Parallel execution** — Async task orchestration for fast result aggregation  
✅ **Schema indexing** — Searchable field registry across all data sources  
✅ **Provenance tracking** — Trace which source contributed each data element  
✅ **Model Context Protocol (MCP)** — Plugin architecture for data source integration  

---

## 🏗️ Project Structure

```
backend/
├─ app/
│  ├─ main.py                        # FastAPI app setup, middleware, router registration
│  ├─ api/
│  │  └─ v1/
│  │     ├─ query.py                 # POST /api/v1/query endpoint
│  │     └─ schema.py                # GET /api/v1/schema/search endpoint
│  ├─ core/
│  │  ├─ config.py                   # Settings & environment variables
│  │  └─ llm/
│  │     ├─ gemini_client.py         # Gemini API wrapper
│  │     └─ prompts.py               # Prompt templates
│  ├─ services/
│  │  ├─ planner.py                  # Query decomposition (LLM-based)
│  │  ├─ execution.py                # Parallel execution against MCPs
│  │  ├─ fusion.py                   # Result aggregation & provenance
│  │  ├─ schema_index.py             # Schema registry & search
│  │  └─ mcp_manager.py              # MCP plugin lifecycle management
│  ├─ models/
│  │  └─ state.py                    # Pydantic models (PlanNode, ExecutionTask, LangGraphState)
│  ├─ mcp_plugins/
│  │  ├─ mcp_sql_sample/             # SQL/PostgreSQL plugin entry
│  │  ├─ mcp_nosql_sample/           # NoSQL/MongoDB plugin entry
│  │  ├─ mcp_graph_sample/           # Graph/Neo4j plugin entry
│  │  └─ mcp_vector_sample/          # Vector/Milvus plugin entry
│  └─ tests/
│     ├─ test_unit_planner.py        # Planner logic tests
│     ├─ test_unit_fusion.py         # Fusion logic tests
│     └─ test_end_to_end.py          # Full query pipeline tests
├─ requirements.txt                  # Python dependencies
├─ docker-compose.yml                # Multi-container orchestration (PostgreSQL, MongoDB, Neo4j, Milvus)
├─ .env                              # Environment configuration
├─ init-postgres/                    # PostgreSQL initialization scripts
├─ init-mongo/                       # MongoDB initialization scripts
├─ init-neo4j/                       # Neo4j initialization scripts
└─ init-milvus/                      # Milvus initialization scripts
```

---

## 🔌 Core Components

### 1. **Planner** (`app/services/planner.py`)
- **Role**: Decomposes natural language queries into database-specific tasks
- **Technology**: Google Gemini 2.5 Flash LLM + deterministic fallback rules
- **Output**: List of `PlanNode` objects with:
  - Capability type (`query.sql`, `query.document`, `query.graph`, `query.vector`)
  - Natural language subquery
  - Preferred data source
  - Dependency graph (e.g., orders depend on customer lookup)

### 2. **Execution** (`app/services/execution.py`)
- **Role**: Orchestrates parallel execution of plan nodes across MCPs
- **Process**:
  1. Execute SQL node first (usually customer lookup)
  2. Use results as context for dependent nodes
  3. Run non-blocking queries in parallel (orders, referrals, similar customers)
  4. Collect results into `ExecutionTask` objects
- **Async**: Leverages `asyncio.gather()` for concurrency

### 3. **Fusion** (`app/services/fusion.py`)
- **Role**: Aggregates and enriches results from multiple sources
- **Provenance Tracking**: Each field includes metadata about its source
- **Output Structure**:
  ```json
  {
    "customer": {"id": "...", "name": {"value": "...", "provenance": [...]}},
    "recent_orders": [...],
    "referrals": [...],
    "similar_customers": [...],
    "explain": ["Customer info from sql_customers", "Orders from orders_mongo", ...]
  }
  ```

### 4. **Schema Index** (`app/services/schema_index.py`)
- **Role**: Maintains searchable registry of all database schemas
- **Indexed Artifacts**:
  - SQL tables & columns
  - MongoDB collections & fields
  - Neo4j node labels & properties
  - Milvus vector indices & metadata fields
- **Search**: Substring matching with relevance scoring

### 5. **MCP Manager** (`app/services/mcp_manager.py`)
- **Role**: Lifecycle management for Model Context Protocol plugins
- **Functions**: Register MCPs, route calls to correct plugin, handle failures

---

## 📡 API Endpoints

### **POST `/api/v1/query`**
Execute a multi-database query.

**Request:**
```json
{
  "user_id": "user123",
  "nl_query": "Find all customers named John and their recent orders",
  "context": {}
}
```

**Response:**
```json
{
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "COMPLETE",
  "fused_data": {
    "customer": {
      "id": "cust_001",
      "name": {"value": "John Doe", "provenance": [{"source": "sql_customers", "field": "name"}]},
      "email": {"value": "john@example.com", "provenance": [{"source": "sql_customers", "field": "email"}]}
    },
    "recent_orders": [
      {"order_id": "ord_123", "amount": 99.99, "created_at": "2025-11-28T10:30:00Z"},
      {"order_id": "ord_124", "amount": 149.99, "created_at": "2025-11-27T14:15:00Z"}
    ],
    "referrals": [],
    "similar_customers": [],
    "explain": [
      "Customer info from sql_customers",
      "Orders from orders_mongo"
    ]
  }
}
```

### **GET `/api/v1/schema/search`**
Search for fields across all registered schemas.

**Query:**
```
GET /api/v1/schema/search?q=customer
```

**Response:**
```json
{
  "q": "customer",
  "hits": [
    {
      "id": "sql_customers.customers.id",
      "mcp": "sql_customers",
      "parent": "customers",
      "field": "id",
      "score": 1.0
    },
    {
      "id": "orders_mongo.orders.customer_id",
      "mcp": "orders_mongo",
      "parent": "orders",
      "field": "customer_id",
      "score": 1.0
    }
  ]
}
```

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.10+**
- **Docker & Docker Compose** (for databases)
- **Google Gemini API Key** (optional; deterministic fallback available)

### Step 1: Clone & Install

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Step 2: Start Databases

```powershell
docker-compose up -d
```

This will start:
- **PostgreSQL** (5432) — customer master data
- **MongoDB** (27017) — order documents
- **Neo4j** (7687) — referral graph
- **Milvus** (19530) — customer embeddings

**Note:** Initial scripts in `init-*/` directories will populate sample data.

### Step 3: Configure Environment

Create or update `.env`:

```dotenv
# SQL (PostgreSQL)
POSTGRES_DSN=postgresql://postgres:postgrespassword@localhost:5432/mdbs

# NoSQL (MongoDB)
MONGO_URI=mongodb://localhost:27017
MONGO_DB=mdbs

# Graph (Neo4j)
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=neo4jpassword

# Vector DB (Milvus)
MILVUS_HOST=localhost
MILVUS_PORT=19530

# LLM (Google Gemini)
GEMINI_API_KEY=your_api_key_here

# App
APP_ENV=development
```

### Step 4: Run the Backend

```powershell
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Visit **http://localhost:8000/docs** (Swagger UI) or **http://localhost:8000/redoc** (ReDoc).

---

## 💻 Example Usage

### Via cURL

```powershell
$payload = @{
    user_id = "user_42"
    nl_query = "Show me customer John Smith and their orders"
    context = @{}
} | ConvertTo-Json

curl -X POST "http://localhost:8000/api/v1/query" `
  -Header "Content-Type: application/json" `
  -Body $payload
```

### Via Python

```python
import httpx
import asyncio

async def main():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/v1/query",
            json={
                "user_id": "user_42",
                "nl_query": "Find customer John Smith and their recent orders",
                "context": {}
            }
        )
        print(response.json())

asyncio.run(main())
```

---

## 📦 Dependencies

| Category | Packages |
|----------|----------|
| **Web Framework** | FastAPI, Uvicorn, httpx |
| **Data Models** | Pydantic, Pydantic-Settings |
| **Database Drivers** | psycopg2-binary (PostgreSQL), pymongo (MongoDB), neo4j (Neo4j), motor (async MongoDB) |
| **Vector DB** | qdrant-client, sentence-transformers |
| **LLM** | langchain, langgraph, google-generativeai, langchain-google-genai |
| **Utilities** | python-dotenv, numpy, networkx, redis, tenacity |
| **Testing** | pytest, pytest-asyncio, pytest-cov |

See `requirements.txt` for exact versions.

---

## 🏃 Quick Start Checklist

- [ ] Python 3.10+ installed
- [ ] Cloned repository
- [ ] Created & activated virtual environment
- [ ] Installed dependencies (`pip install -r requirements.txt`)
- [ ] Docker & Docker Compose running
- [ ] Started databases (`docker-compose up -d`)
- [ ] Configured `.env` with valid database credentials & Gemini API key
- [ ] Started backend (`python -m uvicorn app.main:app --reload`)
- [ ] Verified docs at `http://localhost:8000/docs`
- [ ] Ran tests (`pytest -v`)

---