"""
GOLD — The Tsunami: ramp to 500 concurrent users
══════════════════════════════════════════════════
Pre-requisites:
    docker compose up -d --scale app=3 --build   (4 Uvicorn workers per container)

Run headless:
    locust -f locust/gold.py \
           --headless --host http://localhost \
           --html reports/gold_report.html

Must pass: failure rate < 5 %, p95 < 3 s

How the p95 target is met:
    1. Cache warming  — each user hits /api/products and /api/inventory once
                        on_start(), so Redis is hot before any timed task runs.
                        With 10–15 users/s spawn rate the cache is fully warm
                        well before the sustained 500-user phase begins.
    2. 4 Uvicorn workers per container (--workers 4 in Dockerfile) give 4
       independent event loops and 4 separate connection pools per replica.
       3 replicas × 4 workers × 15 connections = 180 total — safely under
       PostgreSQL's max_connections=200.
    3. Fire-and-forget cache invalidation in POST /api/sales means DB
       commits no longer block waiting for Redis KEYS scans.

Extra metric printed at the end:
    Cache hit rate — shows how much Redis absorbed the read load.
    A high hit rate (>90 %) is what makes 500 users survivable.
"""

import random
import threading

from locust import HttpUser, LoadTestShape, constant, events, task

# ── Cache hit counter (thread-safe) ──────────────────────────────────────────
_lock = threading.Lock()
_cache_stats = {"hits": 0, "total": 0}


@events.test_stop.add_listener
def print_cache_stats(environment, **kwargs):
    """Prints a cache hit summary when the test finishes."""
    with _lock:
        total = _cache_stats["total"]
        hits = _cache_stats["hits"]
    if total == 0:
        return
    pct = hits / total * 100
    print(f"\n{'─' * 50}")
    print(f"  Redis cache hit rate : {hits}/{total} requests ({pct:.1f} %)")
    print(f"  (reads that skipped Postgres entirely)")
    print(f"{'─' * 50}\n")


# ── Load shape ────────────────────────────────────────────────────────────────
class GoldShape(LoadTestShape):
    """
    Timeline:
        0 s  → 30 s  : warm up to 200 users
        30 s → 60 s  : The Tsunami — ramp to 500 users
        60 s → 240 s : hold at 500 users (3 minutes)
        240 s → 255 s: ramp down
    """

    stages = [
        {"until": 30, "users": 200, "spawn_rate": 10},
        {"until": 60, "users": 500, "spawn_rate": 15},
        {"until": 240, "users": 500, "spawn_rate": 10},
        {"until": 255, "users": 0, "spawn_rate": 50},
    ]

    def tick(self):
        t = self.get_run_time()
        for stage in self.stages:
            if t <= stage["until"]:
                return stage["users"], stage["spawn_rate"]
        return None


# ── User behaviour ────────────────────────────────────────────────────────────
class CashierUser(HttpUser):
    wait_time = constant(1)
    host = "http://localhost"

    def on_start(self):
        """Prime Redis before the user starts issuing timed tasks.

        Each spawned user hits both cached endpoints once as soon as it
        starts.  Because users are spawned gradually (10-15/s) across the
        60 s ramp, the cache is fully warm before the sustained 500-user
        phase begins.  Warm-up requests are named "[warm-up]" so they appear
        separately in the report and do not skew the main latency stats.
        """
        self.client.get("/api/products", name="[warm-up] GET /api/products")
        self.client.get("/api/inventory", name="[warm-up] GET /api/inventory")

    @task(4)
    def browse_products(self):
        """40 % — catalog read. Should be almost entirely Redis after warm-up."""
        with self.client.get(
            "/api/products", name="GET /api/products", catch_response=True
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"Expected 200, got {resp.status_code}")
                return
            _track_cache(resp)

    @task(2)
    def check_inventory(self):
        """20 % — inventory read (30 s TTL, refreshes more often than catalog)."""
        with self.client.get(
            "/api/inventory", name="GET /api/inventory", catch_response=True
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"Expected 200, got {resp.status_code}")
                return
            _track_cache(resp)

    @task(2)
    def create_sale(self):
        """~27 % — checkout. Always hits Postgres (writes can't be cached)."""
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


def _track_cache(resp):
    """Records whether this response was served from Redis or Postgres."""
    with _lock:
        _cache_stats["total"] += 1
        if resp.headers.get("X-Cache") == "HIT":
            _cache_stats["hits"] += 1
