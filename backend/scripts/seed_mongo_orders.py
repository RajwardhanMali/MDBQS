# scripts/seed_mongo_orders.py
import os
from datetime import datetime, timedelta
from pymongo import MongoClient

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "mdbs")

NUM_CUSTOMERS = 150
ORDERS_PER_CUSTOMER = 8  # 150 * 8 = 1200 orders approx


def main():
    client = MongoClient(MONGO_URI)
    db = client[MONGO_DB]
    coll = db["orders"]

    docs = []
    base_date = datetime(2025, 1, 1)

    for c in range(1, NUM_CUSTOMERS + 1):
        cid = f"cust{c:03d}"
        for j in range(ORDERS_PER_CUSTOMER):
            idx = (c - 1) * ORDERS_PER_CUSTOMER + j + 1
            order_id = f"o{idx:04d}"
            amount = round(20 + (c % 10) * 5 + j * 1.25, 2)
            order_date = (base_date + timedelta(days=idx % 365)).strftime("%Y-%m-%d")
            docs.append(
                {
                    "order_id": order_id,
                    "customer_id": cid,
                    "amount": amount,
                    "order_date": order_date,
                }
            )

    if docs:
        coll.delete_many({})  # optional: clear existing
        coll.insert_many(docs)

    print(f"Seeded orders collection. Total docs: {coll.count_documents({})}")


if __name__ == "__main__":
    main()
