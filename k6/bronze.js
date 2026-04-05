/**
 * BRONZE -- Baseline: 50 concurrent users for 60 seconds
 *
 * Run:    k6 run k6/bronze.js
 * Record: p(95) from http_req_duration  +  error_rate
 */
import http from "k6/http";
import { check, sleep } from "k6";
import { Rate, Trend } from "k6/metrics";

const errorRate = new Rate("error_rate");
const productLatency = new Trend("product_latency_ms", true);
const saleLatency = new Trend("sale_latency_ms", true);

export const options = {
  vus: 50,
  duration: "60s",
  thresholds: {
    http_req_duration: ["p(95)<3000"],
    error_rate: ["rate<0.05"],
  },
};

const BASE = "http://localhost";

export default function () {
  const roll = Math.random();

  if (roll < 0.5) {
    // 50% -- Browse product catalog (cacheable)
    const start = Date.now();
    const res = http.get(`${BASE}/api/products`);
    productLatency.add(Date.now() - start);
    errorRate.add(!check(res, { "products 200": (r) => r.status === 200 }));
  } else if (roll < 0.75) {
    // 25% -- Check inventory levels
    const res = http.get(`${BASE}/api/inventory`);
    errorRate.add(!check(res, { "inventory 200": (r) => r.status === 200 }));
  } else {
    // 25% -- Create a sale (DB write)
    const start = Date.now();
    const res = http.post(
      `${BASE}/api/sales`,
      JSON.stringify({
        cashier_id: Math.ceil(Math.random() * 5),
        items: [{ product_id: Math.ceil(Math.random() * 50), quantity: 1 }],
      }),
      { headers: { "Content-Type": "application/json" } },
    );
    saleLatency.add(Date.now() - start);
    errorRate.add(!check(res, { "sale 201": (r) => r.status === 201 }));
  }

  sleep(1);
}
