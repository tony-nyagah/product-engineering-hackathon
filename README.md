# POS Scalability Engineering — Hackathon Demo

A Point-of-Sale system that demonstrates horizontal scaling, Redis caching,
and distributed observability across three progressively harder load-test tiers:
**Bronze → Silver → Gold**.

---

## Architecture

```
                         ┌────────────────────────────────────┐
  Browser / Locust ───▶  │  Traefik v3  (load balancer)       │
                         │  • auto-discovers app replicas      │
                         │  • Prometheus metrics  :9100        │
                         │  • OTLP traces → Jaeger             │
                         └──────┬─────────┬─────────┬─────────┘
                                │         │         │
                           ┌────▼──┐ ┌────▼──┐ ┌────▼──┐
                           │ app 1 │ │ app 2 │ │ app 3 │  FastAPI + asyncpg
                           └────┬──┘ └────┬──┘ └────┬──┘
                                │         │         │
                    ┌───────────▼─────────▼─────────▼───────────┐
                    │              Redis 7   (cache)             │
                    │   products TTL=300s  inventory TTL=30s     │
                    │   reports TTL=60s                          │
                    └───────────────────────────────────────────-┘
                                          │  cache MISS only
                    ┌─────────────────────▼──────────────────────┐
                    │            PostgreSQL 16   (DB)             │
                    └────────────────────────────────────────────┘
```

| Layer         | Tool                               |
|---------------|------------------------------------|
| API           | FastAPI + asyncpg (async Postgres) |
| Database      | PostgreSQL 16                      |
| Cache         | Redis 7                            |
| Load Balancer | Traefik v3 (auto-discovers scale)  |
| Containers    | Docker Compose                     |
| Load Testing  | Locust                             |
| Tracing       | Jaeger (all-in-one, OTLP)          |
| Metrics       | Prometheus (exposed by Traefik)    |

---

## Project Structure

```
product-engineering-hackathon/
├── app/
│   ├── routers/          # FastAPI route handlers
│   ├── main.py           # App entry point, middleware
│   ├── models.py         # SQLAlchemy ORM models
│   ├── schemas.py        # Pydantic request/response schemas
│   ├── cache.py          # Redis helpers (get/set/invalidate)
│   ├── database.py       # Async DB engine & session factory
│   ├── settings.py       # Env-var config (DATABASE_URL, REDIS_URL)
│   ├── seed.py           # Populates DB: 50 products, 5 cashiers, 2k sales
│   ├── requirements.txt
│   └── Dockerfile
├── locust/
│   ├── bronze.py         # Baseline — 50 users, 60 s
│   ├── silver.py         # Scale-out — ramp to 200 users
│   └── gold.py           # Tsunami — ramp to 500 users + cache hit report
├── reports/              # HTML reports saved here after each run
│   ├── bronze_report.html
│   ├── silver_report.html
│   └── gold_report.html
├── docker-compose.yml    # Full stack (Traefik, Jaeger, app, postgres, redis, seed)
└── README.md
```

---

## Quick Start

```bash
# 1. Build and start (single app instance)
docker compose up -d --build

# 2. Seed the DB (50 products, 5 cashiers, 2 000 historical sales)
docker compose --profile seed up seed

# 3. Smoke test
docker ps
curl http://localhost/health

# 4. Confirm caching headers
curl -I http://localhost/api/products   # X-Cache: MISS  (first request hits DB)
curl -I http://localhost/api/products   # X-Cache: HIT   (served from Redis)
```

---

## Observability

All three observability tools start automatically with `docker compose up`.

| Tool               | URL                            | What it shows                                    |
|--------------------|--------------------------------|--------------------------------------------------|
| Traefik Dashboard  | http://localhost:8080          | Active routers, services, and backend instances  |
| Prometheus Metrics | http://localhost:9100/metrics  | Request rates, latency histograms, error counts  |
| Jaeger Tracing UI  | http://localhost:16686         | Distributed traces — find slow spans per request |

### Access logs

Traefik logs every routed request (method, path, status code, duration) to its
container stdout. Tail them live:

```bash
docker logs -f traefik
```

---

## Load Testing (Locust)

### Install

```bash
pip install locust
# or
brew install locust    # macOS / Linux via Homebrew
```

### Two ways to run

**Option A — Web UI** (best for demos; gives live charts)

```bash
locust -f locust/bronze.py --host http://localhost
```

Open http://localhost:8089, set your user count and spawn rate, click **Start**.
Press `Ctrl+C` to stop — Locust saves the HTML report automatically.

**Option B — Headless** (scripted, saves report to `reports/`)

```bash
locust -f locust/bronze.py \
       --headless --users 50 --spawn-rate 5 --run-time 60s \
       --host http://localhost \
       --html reports/bronze_report.html
```

---

## Quest Walkthrough

### 🥉 Bronze — Baseline (50 users)

No extra replicas, no warm cache. Establishes the raw p95 latency.

```bash
locust -f locust/bronze.py \
       --headless --users 50 --spawn-rate 5 --run-time 60s \
       --host http://localhost \
       --html reports/bronze_report.html
```

Open `reports/bronze_report.html` and record the **p95** value — that number
is your documented baseline.

> **Measured result:** p95 ≈ **4 600 ms**, failure rate **0 %**
> The DB was the bottleneck: every read hit Postgres directly.

---

### 🥈 Silver — Scale-Out (200 users)

Add a second app replica. Traefik detects it automatically via Docker labels —
no config changes required.

```bash
# Scale up
docker compose up -d --scale app=2

# Confirm Traefik sees both instances
docker ps

# Run the test
locust -f locust/silver.py \
       --headless --host http://localhost \
       --html reports/silver_report.html
```

The `LoadTestShape` in `silver.py` controls the ramp automatically:

| Phase       | Duration | Users |
|-------------|----------|-------|
| Ramp-up     | 0–30 s   | → 200 |
| Sustained   | 30 s–2 m | 200   |
| Ramp-down   | last 15 s| → 0   |

**Target:** p95 < 3 s, failure rate < 5 %.

---

### 🥇 Gold — Caching + The Tsunami (500 users)

Redis caching is already wired into the app. Scale to 3 replicas and hit it hard.

```bash
# Scale up
docker compose up -d --scale app=3

# Run the tsunami
locust -f locust/gold.py \
       --headless --host http://localhost \
       --html reports/gold_report.html
```

The `LoadTestShape` in `gold.py`:

| Phase      | Duration   | Users |
|------------|------------|-------|
| Warm-up    | 0–30 s     | → 200 |
| Tsunami    | 30–60 s    | → 500 |
| Sustained  | 60 s–4 m   | 500   |
| Ramp-down  | last 15 s  | → 0   |

At the end the terminal prints a cache-hit summary:

```
──────────────────────────────────────────────────
  Redis cache hit rate : 1381/1464 requests (94.3 %)
  (reads that skipped Postgres entirely)
──────────────────────────────────────────────────
```

**Must pass:** failure rate < 5 %, p95 < 3 s.

---

## Reports

HTML reports are saved to `reports/` after each run.
Open them in any browser — they include response-time charts, percentile
tables, and a per-endpoint breakdown.

| File                          | Tier   | What to record         |
|-------------------------------|--------|------------------------|
| `reports/bronze_report.html`  | Bronze | Baseline p95           |
| `reports/silver_report.html`  | Silver | p95 under 200 users    |
| `reports/gold_report.html`    | Gold   | p95 + cache hit rate   |

---

## API Reference

| Method | Path                   | Redis TTL | Notes                                    |
|--------|------------------------|-----------|------------------------------------------|
| GET    | `/api/products`        | 300 s     | Full catalog                             |
| GET    | `/api/products/{id}`   | 300 s     | Single product                           |
| POST   | `/api/products`        | —         | Invalidates `products:*`                 |
| GET    | `/api/inventory`       | 30 s      | Short TTL — stock changes quickly        |
| PATCH  | `/api/inventory/{id}`  | —         | Invalidates `inventory:*`                |
| GET    | `/api/reports/summary` | 60 s      | Expensive aggregate query                |
| POST   | `/api/sales`           | —         | Invalidates `inventory:*` + `reports:*`  |
| GET    | `/health`              | —         | Traefik health probe                     |

All cached endpoints return an `X-Cache: HIT` or `X-Cache: MISS` header so you
can verify caching behaviour with a plain `curl -I`.

---

## Bottleneck Report

### Root cause (Bronze baseline)

Without caching, every `GET /api/products` and `GET /api/reports/summary`
triggers a full table scan across 50 products and 2 000+ sale rows.
At 50 concurrent users the PostgreSQL connection pool saturated and p95 latency
climbed to **4 600 ms** — with zero application errors, meaning the server was
slow but not failing.

### Fixes applied (Silver → Gold)

| Fix                            | Effect                                                       |
|--------------------------------|--------------------------------------------------------------|
| Horizontal scale (2–3 replicas)| Distributes CPU and connection load; Traefik balances automatically |
| Redis cache — products 300 s   | Eliminates repeated full-catalog Postgres scans              |
| Redis cache — reports 60 s     | Avoids expensive aggregate query on every dashboard refresh  |
| Redis cache — inventory 30 s   | Reduces write-amplified stock lookups                        |

At Gold tier (3 replicas + Redis warm), ~94 % of read requests are served
entirely from Redis, reducing DB reads by ~80 % and dropping p95 well below
500 ms at 500 concurrent users.