-- create table and seed sample customers (idempotent with ON CONFLICT)
CREATE TABLE IF NOT EXISTS customers (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  email TEXT NOT NULL,
  embedding JSONB
);

INSERT INTO customers (id, name, email, embedding) VALUES
('cust1','Alice Kumar','alice@example.com','[0.1, 0.2, 0.3]') ON CONFLICT (id) DO NOTHING,
('cust2','Bob Singh','bob@example.com','[0.0, 0.2, 0.7]') ON CONFLICT (id) DO NOTHING,
('cust3','Charlie Rao','charlie@example.com','[0.9, 0.1, 0.0]') ON CONFLICT (id) DO NOTHING;
