/**
 * GOLD -- The Tsunami: ramp to 500 concurrent users
 *
 * Pre-requisites:  docker compose up -d --scale app=3
 * Run:             k6 run k6/gold.js
 * Must pass:       error_rate < 5%,  p95 < 3s
 */
import http from "k6/http";
import { check, sleep } from "k6";
import { Rate, Trend } from "k6/metrics";

const errorRate = new Rate("error_rate");
const cacheHitRate = new Rate("cache_hit_rate");
const reportLatency = new Trend("report_latency_ms", true);

export const options = {
  stages: [
    { duration: "30s", target: 200 }, // warm up
    { duration: "30s", target: 500 }, // The Tsunami
    { duration: "3m", target: 500 }, // hold
    { duration: "15s", target: 0 }, // ramp down
  ],
  thresholds: {
    http_req_duration: ["p(95)<3000"],
    error_rate: ["rate<0.05"], // Gold requirement: < 5% errors
  },
};

const BASE = "http://localhost";

export default function () {
  const roll = Math.random();

  if (roll < 0.4) {
    // 40% -- Product catalog (Redis TTL 300s)
    const res = http.get(`${BASE}/api/products`);
    const ok = check(res, { "products 200": (r) => r.status === 200 });
    errorRate.add(!ok);
    cacheHitRate.add(res.headers["X-Cache"] === "HIT");
  } else if (roll < 0.6) {
    // 20% -- Inventory (Redis TTL 30s)
    const res = http.get(`${BASE}/api/inventory`);
    const ok = check(res, { "inventory 200": (r) => r.status === 200 });
    errorRate.add(!ok);
    cacheHitRate.add(res.headers["X-Cache"] === "HIT");
  } else if (roll < 0.75) {
    // 15% -- Reports summary (expensive aggregate, Redis TTL 60s)
    const start = Date.now();
    const res = http.get(`${BASE}/api/reports/summary`);
    reportLatency.add(Date.now() - start);
    const ok = check(res, { "report 200": (r) => r.status === 200 });
    errorRate.add(!ok);
    cacheHitRate.add(res.headers["X-Cache"] === "HIT");
  } else {
    // 25% -- Create a sale (DB write, always hits Postgres)
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
