# scripts/seed_neo4j_referrals.py
import os
from neo4j import GraphDatabase

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "neo4jpassword")

NUM_CUSTOMERS = 150


def main():
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    with driver.session() as session:
        # clear old data
        session.run("MATCH (n:Customer) DETACH DELETE n")

        # create customers
        for i in range(1, NUM_CUSTOMERS + 1):
            cid = f"cust{i:03d}"
            name = f"Customer {i:03d}"
            email = f"customer{i:03d}@example.com"
            session.run(
                "CREATE (c:Customer {id:$id,name:$name,email:$email})",
                id=cid,
                name=name,
                email=email,
            )

        # create referral relationships
        for i in range(2, NUM_CUSTOMERS + 1):
            cid = f"cust{i:03d}"
            # This logic assigns a referrer to be 1 or 7-14 customers before the current one
            referrer = f"cust{max(1, i - (i % 7 + 1)):03d}"
            
            # --- FIX APPLIED HERE (Line 41) ---
            # Corrected to use a pure f-string for date creation.
            # The expressions are wrapped in parentheses and format specifiers are applied directly.
            month = (i % 12) or 1
            day = (i % 28) or 1
            since=f"2024-{month:02d}-{day:02d}"
            # ----------------------------------
            
            session.run(
                """
                MATCH (a:Customer {id:$referrer}), (b:Customer {id:$cid})
                MERGE (a)-[:REFERRED {since:date($since)}]->(b)
                """,
                referrer=referrer,
                cid=cid,
                since=since,
            )

    driver.close()
    print(f"Seeded {NUM_CUSTOMERS} customers and referral edges in Neo4j.")


if __name__ == "__main__":
    main()