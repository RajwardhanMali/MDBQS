// init-mongo/init_orders.js
db = db.getSiblingDB('mdbs');

print('Seeding orders collection...');

const orders = [
  { order_id: "o1", customer_id: "cust1", amount: 120.0, order_date: "2025-10-01" },
  { order_id: "o2", customer_id: "cust1", amount: 30.0, order_date: "2025-09-01" },
  { order_id: "o3", customer_id: "cust2", amount: 75.0, order_date: "2025-10-05" },
  { order_id: "o4", customer_id: "cust1", amount: 54.0, order_date: "2025-08-21" },
  { order_id: "o5", customer_id: "cust3", amount: 200.0, order_date: "2025-10-10" }
];

if (db.orders.countDocuments({}) === 0) {
  db.orders.insertMany(orders);
  print('Inserted ' + orders.length + ' orders');
} else {
  print('Orders collection already has data; skipping seeding.');
}
