import os
import logging
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import re

# Import the asynchronous Neo4j driver
try:
    from neo4j import AsyncGraphDatabase
    NEO4J_AVAILABLE = True
except ImportError:
    NEO4J_AVAILABLE = False
    print("WARNING: neo4j package not installed. Graph operations will fail.")

load_dotenv()
logger = logging.getLogger("mcp_graph_sample")
logging.basicConfig(level=logging.INFO)

# --- Configuration ---
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "neo4jpassword")

class StartNode(BaseModel):
    """Schema for the preferred 'start' object in the payload."""
    property: str
    value: Any

class TraversePayload(BaseModel):
    """Schema for the traversal request payload."""
    start: Optional[StartNode] = None
    rel: str = "REFERRED"
    depth: int = 1
    start_id: Optional[str] = None
    max_depth: Optional[int] = None
    
app = FastAPI(title="Graph Database Plugin (Neo4j)")

@app.on_event("startup")
async def startup():
    """Initializes the Neo4j AsyncGraphDatabase driver and attaches it to app.state."""
    if not NEO4J_AVAILABLE:
        logger.error("Neo4j driver not available. Cannot initialize database.")
        app.state.driver = None
        return

    try:
        logger.info(f"Connecting to Neo4j at {NEO4J_URI}")
        driver = AsyncGraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        # Verify connection health
        await driver.verify_connectivity()
        app.state.driver = driver
        logger.info("✅ Neo4j connection driver initialized successfully.")
    except Exception as e:
        logger.error(f"❌ Failed to connect to Neo4j at {NEO4J_URI}: {e}")
        app.state.driver = None


@app.on_event("shutdown")
async def shutdown():
    """Closes the Neo4j driver connection on shutdown."""
    if hasattr(app.state, 'driver') and app.state.driver:
        await app.state.driver.close()
        logger.info("Neo4j connection driver closed.")


@app.get("/health")
async def health_check():
    """Checks the status of the database connection."""
    if not hasattr(app.state, 'driver') or not app.state.driver:
        raise HTTPException(status_code=503, detail="Graph database driver not initialized.")
    
    try:
        await app.state.driver.verify_connectivity()
        return {"status": "ok", "db_type": "graph", "message": "Neo4j connection is healthy."}
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail=f"Graph database connection failed: {e}")


@app.get("/debug/check_data")
async def check_data():
    """Debug endpoint to verify graph data exists."""
    if not hasattr(app.state, 'driver') or not app.state.driver:
        return {"error": "Driver not initialized"}
    
    try:
        # Count customers
        cypher_customers = "MATCH (c:Customer) RETURN count(c) as count"
        async with app.state.driver.session() as session:
            result = await session.run(cypher_customers)
            record = await result.single()
            customer_count = record["count"] if record else 0
        
        # Count relationships
        cypher_rels = "MATCH ()-[r:REFERRED]->() RETURN count(r) as count"
        async with app.state.driver.session() as session:
            result = await session.run(cypher_rels)
            record = await result.single()
            referral_count = record["count"] if record else 0
        
        # Sample customers
        cypher_sample = "MATCH (c:Customer) RETURN c.id, c.name LIMIT 5"
        sample_customers = []
        async with app.state.driver.session() as session:
            result = await session.run(cypher_sample)
            records = await result.data()
            for rec in records:
                sample_customers.append({
                    "id": rec.get("c.id"),
                    "name": rec.get("c.name")
                })
        
        # Check specific customer
        cypher_check_cust = "MATCH (c:Customer {id: $cust_id}) RETURN c"
        async with app.state.driver.session() as session:
            result = await session.run(cypher_check_cust, {"cust_id": "cust001"})
            record = await result.single()
            cust001_exists = record is not None
        
        # Check referrals for cust001
        cypher_ref = """
        MATCH (a:Customer {id: $cust_id})-[r:REFERRED]->(b:Customer)
        RETURN b.id as id, b.name as name
        """
        referrals_from_cust001 = []
        async with app.state.driver.session() as session:
            result = await session.run(cypher_ref, {"cust_id": "cust001"})
            records = await result.data()
            for rec in records:
                referrals_from_cust001.append({
                    "id": rec.get("id"),
                    "name": rec.get("name")
                })
        
        return {
            "status": "ok",
            "customer_count": customer_count,
            "referral_count": referral_count,
            "sample_customers": sample_customers,
            "cust001_exists": cust001_exists,
            "referrals_from_cust001": referrals_from_cust001,
            "referrals_from_cust001_count": len(referrals_from_cust001)
        }
    except Exception as e:
        logger.exception(f"Debug check failed: {e}")
        return {"error": str(e)}


@app.post("/get_schema")
async def get_schema():
    return {
        "mcp_id": "graph_referrals",
        "db_type": "graph",
        "entities": [
            {
                "name": "customers",
                "kind": "node",
                "semantic_tags": ["entity:customer", "referral_graph"],
                "default_id_field": "id",
                "fields": [
                    {"name": "id", "type": "text", "semantic_tags": ["id", "customer_id"]},
                    {"name": "name", "type": "text", "semantic_tags": ["name", "customer_name"]},
                    {"name": "email", "type": "text", "semantic_tags": ["email"]},
                ],
            },
            {
                "name": "REFERRED",
                "kind": "relationship",
                "semantic_tags": ["referral"],
                "fields": [
                    {"name": "since", "type": "date", "semantic_tags": ["since_date"]},
                ],
            },
        ],
    }


def _sanitize_name(name: str, type_name: str):
    """
    Sanitizes string inputs (property/relationship names) used in query construction
    to prevent Cypher injection. Allows alphanumeric and underscore characters.
    """
    if not re.fullmatch(r"[a-zA-Z0-9_]+", name):
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid {type_name}: '{name}'. Only alphanumeric characters and underscores are allowed."
        )
    return name


@app.post("/traverse")
async def traverse(payload: TraversePayload):
    """
    Traverse referral relationships with proper async Neo4j handling.
    """
    
    logger.info("="*80)
    logger.info("TRAVERSE REQUEST RECEIVED")
    logger.info(f"Payload: {payload.model_dump()}")
    logger.info("="*80)
    
    # --- 1. Normalize and Validate Payload ---
    start_value = None
    prop = "id"  # Default property
    
    if payload.start:
        prop = payload.start.property
        start_value = payload.start.value
        logger.info(f"Using start object: property={prop}, value={start_value}")
    elif payload.start_id:  # Legacy support
        start_value = payload.start_id
        logger.info(f"Using legacy start_id: {start_value}")
    
    rel = payload.rel or "REFERRED"
    depth = payload.depth if payload.depth > 0 else (payload.max_depth or 1)
    
    logger.info(f"Parsed parameters: start_value={start_value}, property={prop}, rel={rel}, depth={depth}")

    if not start_value:
        raise HTTPException(
            status_code=400, 
            detail="Missing 'start.value' or 'start_id' in payload. Cannot begin traversal."
        )

    # Sanitize inputs used in query string construction
    try:
        prop = _sanitize_name(prop, "property name")
        rel = _sanitize_name(rel, "relationship type")
    except HTTPException as e:
        logger.error(f"Sanitization failed: {e.detail}")
        return {
            "rows": [],
            "meta": {
                "source_id": "graph_referrals",
                "source_type": "query.graph",
                "error": e.detail,
            }
        }
    
    # --- 2. Build Cypher with Variable Path Length ---
    
    # Correct syntax for Neo4j variable length paths:
    # - For single hop: no path length specifier (just -[r:REL]->)
    # - For variable: *1..N or *..N (both work)
    if depth == 1:
        path_expr = ""  # Single hop
        logger.info("Using single hop traversal")
    else:
        path_expr = f"*1..{depth}"  # Variable path from 1 to depth
        logger.info(f"Using variable path: {path_expr}")
    
    # Build the Cypher query
    # CRITICAL: Use parameterized query for the value to prevent injection
    cypher = f"""
    MATCH (a:Customer)-[r:{rel}{path_expr}]->(b:Customer)
    WHERE a.{prop} = $start_value
    RETURN DISTINCT b.id AS id,
                    b.name AS name,
                    b.email AS email,
                    '{rel}' AS relationship
    """
    
    logger.info(f"Generated Cypher query:\n{cypher}")
    logger.info(f"Query parameters: {{'start_value': {start_value}}}")
    
    rows_out = []
    params = {"start_value": start_value}
    
    # --- 3. Execute query safely with async driver ---
    try:
        if not app.state.driver:
            raise Exception("Neo4j driver not initialized")
        
        logger.info("Opening Neo4j session...")
        async with app.state.driver.session() as session:
            logger.info("Executing Cypher query...")
            result = await session.run(cypher, params)
            
            logger.info("Fetching result data...")
            records = await result.data()
            
            logger.info(f"Query returned {len(records)} records")
            
            for i, rec in enumerate(records):
                logger.info(f"Record {i}: {rec}")
                rows_out.append({
                    "id": rec.get("id"),
                    "name": rec.get("name"),
                    "email": rec.get("email"),
                    "relationship": rec.get("relationship"),
                })
        
        logger.info(f"✅ Successfully processed {len(rows_out)} referrals")
        
    except Exception as e:
        error_message = str(e)
        logger.error(f"❌ Graph query error: {error_message}")
        import traceback
        logger.error(traceback.format_exc())
        
        return {
            "rows": [],
            "meta": {
                "source_id": "graph_referrals",
                "source_type": "query.graph",
                "query": cypher.strip(),
                "params": params,
                "error": error_message,
            },
        }

    logger.info("="*80)
    logger.info(f"TRAVERSE COMPLETE: {len(rows_out)} results")
    logger.info("="*80)
    
    return {
        "rows": rows_out,
        "meta": {
            "source_id": "graph_referrals",
            "source_type": "query.graph",
            "query": cypher.strip(),
            "row_count": len(rows_out),
        },
    }