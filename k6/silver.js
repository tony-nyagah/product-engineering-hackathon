/**
 * SILVER -- Scale-Out: ramp to 200 concurrent users
 *
 * Pre-requisites:  docker compose up -d --scale app=2
 * Run:             k6 run k6/silver.js
 * Target:          p95 < 3s, error rate < 5%
 */
import http from "k6/http";
import { check, sleep } from "k6";
import { Rate } from "k6/metrics";

const errorRate = new Rate("error_rate");

export const options = {
  stages: [
    { duration: "30s", target: 200 }, // ramp up
    { duration: "2m", target: 200 }, // hold
    { duration: "15s", target: 0 }, // ramp down
  ],
  thresholds: {
    http_req_duration: ["p(95)<3000"],
    error_rate: ["rate<0.05"],
  },
};

const BASE = "http://localhost";

export default function () {
  const roll = Math.random();
  if (roll < 0.5) {
    const res = http.get(`${BASE}/api/products`);
    errorRate.add(!check(res, { "products 200": (r) => r.status === 200 }));
  } else if (roll < 0.75) {
    const res = http.get(`${BASE}/api/inventory`);
    errorRate.add(!check(res, { "inventory 200": (r) => r.status === 200 }));
  } else {
    const res = http.post(
      `${BASE}/api/sales`,
      JSON.stringify({
        cashier_id: Math.ceil(Math.random() * 5),
        items: [{ product_id: Math.ceil(Math.random() * 50), quantity: 1 }],
      }),
      { headers: { "Content-Type": "application/json" } },
    );
    errorRate.add(!check(res, { "sale 201": (r) => r.status === 201 }));
  }
  sleep(1);
}
