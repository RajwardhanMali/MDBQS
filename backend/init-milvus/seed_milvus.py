# init-milvus/seed_milvus.py
from pymilvus import connections, FieldSchema, CollectionSchema, DataType, Collection
import os

MILVUS_HOST = os.getenv("MILVUS_HOST", "localhost")
MILVUS_PORT = os.getenv("MILVUS_PORT", "19530")

connections.connect("default", host=MILVUS_HOST, port=MILVUS_PORT)

collection_name = "customer_embeddings"

# check whether collection exists
if Collection.exists(collection_name):
    print(f"Collection '{collection_name}' already exists. Skipping creation.")
else:
    fields = [
        FieldSchema(name="cust_id", dtype=DataType.VARCHAR, is_primary=True, max_length=64),
        FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=3),
        FieldSchema(name="name", dtype=DataType.VARCHAR, max_length=128),
        FieldSchema(name="email", dtype=DataType.VARCHAR, max_length=128),
    ]
    schema = CollectionSchema(fields, description="Customer embeddings")
    coll = Collection(name=collection_name, schema=schema)
    print(f"Created collection '{collection_name}'")

    # insert simple records
    cust_ids = ["cust1","cust2","cust3"]
    embeddings = [
        [0.1,0.2,0.3],
        [0.0,0.2,0.7],
        [0.9,0.1,0.0],
    ]
    names = ["Alice Kumar","Bob Singh","Charlie Rao"]
    emails = ["alice@example.com","bob@example.com","charlie@example.com"]

    entities = [cust_ids, embeddings, names, emails]
    res = coll.insert(entities)
    coll.flush()
    print("Inserted data:", res.primary_keys)
