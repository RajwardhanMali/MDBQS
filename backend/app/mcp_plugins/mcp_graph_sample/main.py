# app/mcp_plugins/mcp_graph_sample/main.py
from dotenv import load_dotenv
from fastapi import FastAPI
import networkx as nx
from typing import Dict

load_dotenv()
app = FastAPI()

@app.on_event("startup")
async def startup():
    G = nx.DiGraph()
    # nodes have id and name
    G.add_node("cust1", id="cust1", name="Alice Kumar", email="alice@example.com")
    G.add_node("cust2", id="cust2", name="Bob Singh", email="bob@example.com")
    G.add_node("cust3", id="cust3", name="Charlie Rao", email="charlie@example.com")
    G.add_edge("cust1", "cust2", relationship="REFERRED")
    G.add_edge("cust1", "cust3", relationship="REFERRED")
    app.state.graph = G

@app.get("/schema")
async def get_schema():
    return {"mcp_id": "graph_referrals", "node_labels": ["Customer"], "relationship_types": ["REFERRED"], "node_properties": {"Customer":["id","name","email"]}}

@app.post("/traverse")
async def traverse(payload: Dict):
    start = payload.get("start", {})
    prop = start.get("property")
    value = start.get("value")
    rel = payload.get("rel", "REFERRED")
    depth = int(payload.get("depth", 1))
    G = app.state.graph
    # find start node by id
    if prop != "id":
        return {"data": [], "meta": {"source_id":"graph_referrals"}}
    if value not in G:
        return {"data": [], "meta": {"source_id":"graph_referrals"}}
    neighbors = []
    edges = []
    for nbr in G.successors(value):
        edge_data = G.get_edge_data(value, nbr)
        if edge_data.get("relationship") == rel:
            neighbors.append(dict(G.nodes[nbr]))
            edges.append({"from": value, "to": nbr, "relationship": rel})
    return {"data": {"nodes": neighbors, "edges": edges}, "meta": {"source_id":"graph_referrals"}}
