"""
BRONZE — Baseline: 50 concurrent users for 60 seconds
══════════════════════════════════════════════════════
Run with web UI (recommended for first time):
    locust -f locust/bronze.py --host http://localhost
    → open http://localhost:8089
    → set Users = 50, Spawn Rate = 5, click Start

Run headless (for screenshots / CI):
    locust -f locust/bronze.py \
           --headless --users 50 --spawn-rate 5 \
           --run-time 60s --host http://localhost \
           --html reports/bronze_report.html

Record from the output:
    - p95 latency  (Response Time column)
    - Failure rate (Failures/s column)
"""

import random

from locust import HttpUser, constant, task


class CashierUser(HttpUser):
    """
    Simulates one cashier terminal:
      - browses the product catalog (most common)
      - checks stock levels
      - rings up a sale (least common, always hits the DB)
    """

    wait_time = constant(1)  # 1-second pause between actions, same as k6's sleep(1)
    host = "http://localhost"

    @task(2)
    def browse_products(self):
        """50 % of requests — product catalog (Redis-cacheable, 300 s TTL)"""
        with self.client.get(
            "/api/products", name="GET /api/products", catch_response=True
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"Expected 200, got {resp.status_code}")

    @task(1)
    def check_inventory(self):
        """25 % of requests — stock levels (Redis-cacheable, 30 s TTL)"""
        with self.client.get(
            "/api/inventory", name="GET /api/inventory", catch_response=True
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"Expected 200, got {resp.status_code}")

    @task(1)
    def create_sale(self):
        """25 % of requests — checkout transaction (always writes to Postgres)"""
        with self.client.post(
            "/api/sales",
            json={
                "cashier_id": random.randint(1, 5),
                "items": [{"product_id": random.randint(1, 50), "quantity": 1}],
            },
            name="POST /api/sales",
            catch_response=True,
        ) as resp:
            if resp.status_code != 201:
                resp.failure(f"Expected 201, got {resp.status_code}")
