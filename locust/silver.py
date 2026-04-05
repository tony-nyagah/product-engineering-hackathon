"""
SILVER — Scale-Out: ramp to 200 concurrent users
══════════════════════════════════════════════════
Pre-requisites:
    docker compose up -d --scale app=2

Run headless:
    locust -f locust/silver.py \
           --headless --host http://localhost \
           --html reports/silver_report.html

The LoadTestShape below controls the ramp automatically.
No --users flag needed — the shape overrides it.

Target: p95 < 3 s, failure rate < 5 %
"""

import random

from locust import HttpUser, LoadTestShape, constant, task


class SilverShape(LoadTestShape):
    """
    Drives the user count over time.
    tick() is called every second — return (target_users, spawn_rate) or None to stop.

    Timeline:
        0 s  → 30 s  : ramp up to 200 users  (10 new users/sec)
        30 s → 150 s : hold at 200 users      (2 minutes of sustained load)
        150 s → 165 s: ramp down to 0         (15 s cool-down)
    """

    stages = [
        {"until": 30, "users": 200, "spawn_rate": 10},
        {"until": 150, "users": 200, "spawn_rate": 10},
        {"until": 165, "users": 0, "spawn_rate": 20},
    ]

    def tick(self):
        t = self.get_run_time()
        for stage in self.stages:
            if t <= stage["until"]:
                return stage["users"], stage["spawn_rate"]
        return None  # returning None stops the test cleanly


class CashierUser(HttpUser):
    wait_time = constant(1)
    host = "http://localhost"

    @task(2)
    def browse_products(self):
        with self.client.get(
            "/api/products", name="GET /api/products", catch_response=True
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"Expected 200, got {resp.status_code}")

    @task(1)
    def check_inventory(self):
        with self.client.get(
            "/api/inventory", name="GET /api/inventory", catch_response=True
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"Expected 200, got {resp.status_code}")

    @task(1)
    def create_sale(self):
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
