# app/mcp_plugins/mcp_sql_sample/main.py
from fastapi import FastAPI
import asyncpg
import os
import json
from dotenv import load_dotenv

app = FastAPI()
load_dotenv()
DATABASE_URL = os.getenv("POSTGRES_DSN")

@app.on_event("startup")
async def startup():
    print(f"Connecting to: {DATABASE_URL}")
    app.state.pool = await asyncpg.create_pool(DATABASE_URL)

@app.post("/get_schema")
async def get_schema():
    """
    Describe this MCP's schema in a generic way.
    """
    return {
        "mcp_id": "sql_customers",
        "db_type": "sql",
        "entities": [
            {
                "name": "customers",
                "kind": "table",
                "semantic_tags": ["entity:customer", "canonical", "contact"],
                "default_id_field": "id",
                "fields": [
                    {
                        "name": "id",
                        "type": "text",
                        "semantic_tags": ["id", "customer_id"],
                    },
                    {
                        "name": "name",
                        "type": "text",
                        "semantic_tags": ["name", "customer_name"],
                    },
                    {
                        "name": "email",
                        "type": "text",
                        "semantic_tags": ["email", "contact", "primary_email"],
                    },
                    {
                        "name": "embedding",
                        "type": "vector",
                        "semantic_tags": ["embedding", "similarity"],
                    },
                ],
            }
        ],
    }


def normalize_embedding(emb_value):
    """
    Normalize embedding from various JSONB formats to a list of floats.
    Returns None if normalization fails.
    """
    if emb_value is None:
        return None
    
    # Handle string representation of JSONB
    if isinstance(emb_value, str):
        try:
            emb_value = json.loads(emb_value)
        except json.JSONDecodeError as e:
            print(f"Warning: Could not parse embedding string: {str(emb_value)[:50]}... Error: {e}")
            return None
    
    # Extract vector from nested structures
    if isinstance(emb_value, dict):
        # Try common JSONB patterns
        if "vector" in emb_value:
            emb_value = emb_value["vector"]
        elif "values" in emb_value:
            emb_value = emb_value["values"]
        elif "data" in emb_value:
            emb_value = emb_value["data"]
        else:
            # If dict but no known key, try to get first list value
            for v in emb_value.values():
                if isinstance(v, (list, tuple)):
                    emb_value = v
                    break
            else:
                # No list found in dict
                print(f"Warning: Dict embedding has no recognized format: {list(emb_value.keys())}")
                return None
    
    # Ensure it's a list of numbers
    if isinstance(emb_value, (list, tuple)):
        try:
            result = [float(x) for x in emb_value]
            print(f"Successfully normalized embedding: {len(result)} dimensions")
            return result
        except (ValueError, TypeError) as e:
            print(f"Warning: Could not convert embedding to floats: {e}")
            return None
    else:
        print(f"Warning: Unexpected embedding format after processing: {type(emb_value)}")
        return None


@app.post("/execute_sql")
async def execute_sql(payload: dict):
    print("=" * 60)
    print("SQL MCP received payload:", json.dumps(payload, indent=2))

    query = payload.get("query")
    params = payload.get("params")

    # Normalize params - can be dict or list
    if params is None:
        params = []
    elif isinstance(params, dict):
        # Convert dict to list - extract values in order they appear in query
        # For queries with ? placeholders, we need ordered params
        params = list(params.values())

    if not query or not isinstance(query, str):
        return {
            "rows": [],
            "meta": {
                "source_id": "sql_customers",
                "source_type": "SQL",
                "error": "Missing or invalid 'query' field",
            },
        }

    print(f"Query: {query}")
    print(f"Params: {params}")

    # VERY SIMPLE: only allow SELECT for MVP
    if not query.strip().lower().startswith("select"):
        return {
            "rows": [],
            "meta": {
                "source_id": "sql_customers",
                "source_type": "SQL",
                "error": "Only SELECT allowed in MVP",
            },
        }

    # If params are provided and query uses "?" placeholders, translate to $1, $2, ...
    if params and "?" in query:
        out = []
        param_index = 1
        for ch in query:
            if ch == "?":
                out.append(f"${param_index}")
                param_index += 1
            else:
                out.append(ch)
        query = "".join(out)
        print(f"Rewritten query for Postgres: {query}")

    async with app.state.pool.acquire() as conn:
        try:
            if params:
                rows = await conn.fetch(query, *params)
            else:
                rows = await conn.fetch(query)

            print(f"Fetched {len(rows)} rows from database")
            
            result = []
            for i, r in enumerate(rows):
                row = dict(r)
                
                print(f"Row {i} raw data: {row}")

                # Normalize JSONB embedding column (if present)
                if "embedding" in row:
                    raw_embedding = row["embedding"]
                    print(f"Row {i} raw embedding type: {type(raw_embedding)}")
                    print(f"Row {i} raw embedding value: {raw_embedding}")
                    
                    normalized = normalize_embedding(raw_embedding)
                    row["embedding"] = normalized
                    
                    if normalized:
                        print(f"Row {i} normalized embedding: {len(normalized)} dimensions")
                    else:
                        print(f"Row {i} embedding normalization failed")

                result.append(row)

            print(f"Returning {len(result)} rows")
            print("=" * 60)
            
            return {
                "rows": result,
                "meta": {
                    "source_id": "sql_customers",
                    "source_type": "SQL",
                },
            }
        except Exception as e:
            print(f"Error executing SQL: {e}")
            import traceback
            traceback.print_exc()
            return {
                "rows": [],
                "meta": {
                    "source_id": "sql_customers",
                    "source_type": "SQL",
                    "error": str(e),
                },
            }