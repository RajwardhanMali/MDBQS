CREATE (a:Customer {id: 'cust1', name: 'Alice Kumar', email: 'alice@example.com'});
CREATE (b:Customer {id: 'cust2', name: 'Bob Singh', email: 'bob@example.com'});
CREATE (c:Customer {id: 'cust3', name: 'Charlie Rao', email: 'charlie@example.com'});

CREATE (a)-[:REFERRED {since: date('2024-10-01')}]->(b);
CREATE (a)-[:REFERRED {since: date('2024-11-01')}]->(c);
