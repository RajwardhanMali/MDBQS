# scripts/seed_milvus_vectors.py

import os
import math
from pymilvus import (
    connections,
    utility,
    FieldSchema,
    CollectionSchema,
    DataType,
    Collection,
    MilvusException # <-- Added for better error handling/clarity
)


MILVUS_HOST = os.getenv("MILVUS_HOST", "localhost")
MILVUS_PORT = os.getenv("MILVUS_PORT", "19530")
COLLECTION_NAME = "customer_embeddings"
NUM_CUSTOMERS = 150


def ensure_collection():
    """
    Ensures a fresh collection exists. Drops and recreates if it already exists.
    """
    if utility.has_collection(COLLECTION_NAME):
        print(f"Collection '{COLLECTION_NAME}' already exists. Dropping and recreating for fresh seed.")
        utility.drop_collection(COLLECTION_NAME) # <--- Drop logic moved here

    print(f"Creating new collection: {COLLECTION_NAME}")

    fields = [
        FieldSchema(
            name="cust_id",
            dtype=DataType.VARCHAR,
            is_primary=True,
            max_length=64,
            description="Customer ID",
        ),
        FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=3),
        FieldSchema(name="name", dtype=DataType.VARCHAR, max_length=128),
        FieldSchema(name="email", dtype=DataType.VARCHAR, max_length=128),
    ]

    schema = CollectionSchema(fields, description="Customer embeddings collection")
    coll = Collection(COLLECTION_NAME, schema)

    index_params = {
        "index_type": "IVF_FLAT",
        "params": {"nlist": 128},
        "metric_type": "L2",
    }
    # It's better practice to try/except index creation as it can fail on older Milvus versions
    try:
        coll.create_index("embedding", index_params)
    except MilvusException as e:
        print(f"Warning: Failed to create index. Continuing without index. Error: {e}")
        
    coll.load()
    return coll


def main():
    print(f"Connecting to Milvus at {MILVUS_HOST}:{MILVUS_PORT}...")
    try:
        connections.connect("default", host=MILVUS_HOST, port=MILVUS_PORT)
    except MilvusException as e:
        print(f"Error: Could not connect to Milvus. Ensure the server is running.")
        print(f"Details: {e}")
        return

    # --- REMOVED REDUNDANT DROP LOGIC FROM HERE ---
    # The drop logic is now solely inside ensure_collection()

    coll = ensure_collection()

    cust_ids = []
    embeddings = []
    names = []
    emails = []

    for i in range(1, NUM_CUSTOMERS + 1):
        cid = f"cust{i:03d}"
        name = f"Customer {i:03d}"
        email = f"customer{i:03d}@example.com"

        # synthetic embedding
        e = [
            round(math.sin(i) * 0.5 + 0.5, 4),
            round(math.cos(i) * 0.5 + 0.5, 4),
            round((i % 10) / 10.0, 4),
        ]

        cust_ids.append(cid)
        embeddings.append(e)
        names.append(name)
        emails.append(email)

    print("Inserting vector dataset...")
    entities = [cust_ids, embeddings, names, emails]
    insert_result = coll.insert(entities)
    coll.flush()
    print(f"Successfully inserted {coll.num_entities} vectors into Milvus")

    print("Seeding completed!")


if __name__ == "__main__":
    main()