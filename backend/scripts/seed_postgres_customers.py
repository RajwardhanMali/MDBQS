# scripts/seed_postgres_customers.py
import asyncio
import asyncpg
import os
import math
import json

POSTGRES_DSN = os.getenv(
    "POSTGRES_DSN",
    "postgresql://postgres:postgrespassword@localhost:5432/mdbs",
)

NUM_CUSTOMERS = 150  # >= 100


async def main():
    conn = await asyncpg.connect(POSTGRES_DSN)
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS customers (
          id TEXT PRIMARY KEY,
          name TEXT NOT NULL,
          email TEXT NOT NULL,
          embedding JSONB
        )
        """
    )

    rows = []
    for i in range(1, NUM_CUSTOMERS + 1):
        cid = f"cust{i:03d}"
        name = f"Customer {i:03d}"
        email = f"customer{i:03d}@example.com"
        # simple deterministic 3D embedding
        embedding = [
            round(math.sin(i) * 0.5 + 0.5, 4),
            round(math.cos(i) * 0.5 + 0.5, 4),
            round(((i % 10) / 10.0), 4),
        ]
        rows.append((cid, name, email, json.dumps(embedding)))

    # upsert-style insert
    await conn.executemany(
        """
        INSERT INTO customers (id, name, email, embedding)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (id) DO UPDATE SET
          name = EXCLUDED.name,
          email = EXCLUDED.email,
          embedding = EXCLUDED.embedding
        """,
        rows,
    )

    total = await conn.fetchval("SELECT COUNT(*) FROM customers;")
    print(f"Seeded customers table. Total rows: {total}")
    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
