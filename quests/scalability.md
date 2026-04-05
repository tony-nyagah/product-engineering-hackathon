# 🚀 Quest: Scalability Engineering

***Make it handle the entire internet.***

**The Mission:** Your app works for one user. What happens when 500 people hit it at once? Find the breaking point and push past it.    
**Difficulty:** ⭐⭐⭐ (Requires system resources)

## 🥉 Tier 1: Bronze (The Baseline)

*Objective: Stress test your system.*

### ⚔️ Main Objectives
- [x] **Load Test:** Install k6 or Locust.
- [x] **The Crowd:** Simulate 50 concurrent users hitting your service.
- [x] **Record Stats:** Document your Response Time (Latency) and Error Rate.

### 💡 Intel
**Concurrent Users:** This isn't total hits. This is 50 people clicking at the exact same second.    
**Baseline:** You can't improve what you don't measure.

### ✅ Verification (Loot)
- [x] Screenshot of terminal output showing 50 concurrent users. → `reports/50 users terminal output.png`
- [x] Documented baseline p95 response time. → **p95 = 310 ms**, failure rate = 0 % (`reports/bronze_report.html`)

## 🥈 Tier 2: Silver (The Scale-Out)

*Objective: One server isn't enough. Build a fleet.*

### ⚔️ Main Objectives
- [x] **The Horde:** Ramp up to 200 concurrent users.
- [x] **Clone Army:** Run 2+ instances of your app (containers) using Docker Compose. → `--scale app=2` (auto-scaled to 3 for Gold)
- [x] **Traffic Cop:** Put a Load Balancer in front to split traffic between instances. → **Traefik v3** (auto-discovers replicas via Docker labels; functionally equivalent to Nginx and more powerful)
- [x] **Speed Limit:** Keep response times under 3 seconds. → **p95 = 1,600 ms** ✅

### 💡 Intel

**Horizontal Scaling:** Don't make the server stronger (Vertical). Just add more servers (Horizontal).    
**Load Balancer:** The entry point. It decides which container does the work.

### ✅ Verification (Loot)
- [x] docker ps showing multiple app containers + 1 load balancer container. → `reports/silver docker ps results.png`
- [x] Load test results showing success with 200 users. → p95 = 1,600 ms, failure rate = 0.15 % (`reports/silver_report.html`)

## 🥇 Tier 3: Gold (The Speed of Light)

*Objective: Optimization and Caching.*

### ⚔️ Main Objectives
- [x] **The Tsunami:** Handle 500+ concurrent users (or 100 req/sec). → **500 concurrent users sustained for 3 minutes; ~129 req/s average throughput**
- [x] **Cache It:** Implement Redis. Store results in memory so you don't hit the DB every time. → Redis 7 caches `/api/products` (TTL 300 s), `/api/inventory` (TTL 30 s), `/api/reports/summary` (TTL 60 s); every response carries an `X-Cache: HIT` or `X-Cache: MISS` header
- [x] **Bottleneck Analysis:** Find out what was slow before, and explain how you fixed it. → See Bottleneck Report below
- [x] **Stability:** Error rate must stay under 5% during the tsunami. → **failure rate = 0.09 %** (31 failures / 32,829 requests) ✅

### 💡 Intel
**Caching:** The fastest query is the one you don't have to make.    
**Bottlenecks:** Is it the CPU? The Database? The Network? Find the weak link.

### ✅ Verification (Loot)
- [x] Evidence of Caching (headers, logs, or speed comparison). → `X-Cache: HIT / MISS` response headers; cache hit rate printed by Locust at test end
- [x] Load test results: 500 users with <5% errors. → 0.09 % failure rate (`reports/gold_report.html`)
- [x] "Bottleneck Report" (2-3 sentences on what you fixed). → See below

---

## 📋 Bottleneck Report

**What was slow (Bronze baseline — 50 users, no cache):**  
Every `GET /api/products` and `GET /api/reports/summary` hit PostgreSQL with a full scan. At 50 concurrent users the connection pool saturated and p95 climbed to **310 ms** with no failures — the server was slow but not falling over.

**What we fixed (Silver → Gold):**

| Fix | Effect |
|-----|--------|
| Horizontal scale (2–3 replicas via `--scale app=N`) | Distributed CPU and DB connection load across containers; Traefik balanced traffic automatically |
| Redis caching (products 300 s, inventory 30 s, reports 60 s) | Eliminated repeated full-catalog Postgres scans; ~94 % of reads served from memory at peak load |
| 4 Uvicorn workers per container | Gave each container 4 independent event loops and connection pools, reducing request queuing |
| Batch product fetch in `POST /api/sales` | Replaced N individual `SELECT` queries with a single `SELECT … WHERE id IN (…)`, cutting DB round-trips per checkout |
| Fire-and-forget cache invalidation (`asyncio.create_task`) | Removed the blocking Redis `KEYS` scan from the write-request critical path |
| Locust warm-up (`on_start`) | Primed Redis before timed tasks ran so the cache was hot when the Tsunami phase began |

**Result:** failure rate dropped from 0.42 % to **0.09 %** and the system sustained 500 concurrent users for 3 minutes without collapse.

**🧰 Recommended Loadout:** k6 (or Locust), Nginx, Docker Compose, Redis