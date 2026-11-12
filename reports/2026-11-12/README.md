# Locust benchmark — 2026-11-12

Canonical 15,000-request benchmark of the URL Shortener API, run against the
application as it exists on `main` at commit `da411c8`, with the connection
pool left at its current configuration.

## Summary

| Metric | Result |
|---|---|
| Total requests (aggregate) | **15,000** ✅ |
| Failed requests | **0** |
| Error rate | **0.00 %** |
| Average response time | **1,211.43 ms** |
| Median response time | **1,200 ms** |
| P95 response time | **2,200 ms** |
| P99 response time | **2,900 ms** |
| Maximum response time | **4,351.55 ms** |
| Average throughput | **90.93 req/s** |
| Peak throughput (max 1 s interval) | **103.20 req/s** |
| Test duration | 165.0 s (166.25 s wall clock incl. shutdown) |
| Connection exceptions | 0 |
| Application 5xx responses | 0 |
| Test-runner errors | None (Locust exit code 0) |

The request budget terminated the run at exactly 15,000 Locust request events:
`slots_reserved = 15000`, `requests_completed = 15000`,
`num_requests_recorded_by_locust = 15000`. See `run_summary.json`.

## Did the old résumé figures reproduce?

| Résumé claim | This run | Reproduced? |
|---|---|---|
| 15,000+ requests | 15,000 | Yes (exact target) |
| 0 % error rate | 0 failures / 15,000 | Yes |
| Peak 135.17 req/s | 103.20 req/s | **No** (−23.7 %) |
| P99 ≈ 7.5 s | 2.9 s | **No** (much lower) |

The new run is faster in the tail and slower in peak throughput than the résumé
numbers. Nothing was edited to change that. The prior figures cannot be
reconciled from what is in this repository: the only recovered November 3
numbers are two very short runs (1,150 requests at 15.33 ms average / 34 ms P99,
and 1,837 requests at 23.15 ms / 260 ms P99), which do not resemble a
300-user sustained run at all. To explain the gap we would need the original
Locust HTML/CSV for the 135.17 req/s run, its exact command, user count and
spawn rate, the machine it ran on, the database host, and the pool settings in
effect that day.

The gap is plausible without any code change: peak RPS depends on user count,
wait time, hardware and the database round-trip, and a 7.5 s P99 implies
substantially heavier contention (or a remote/slower database) than the local
stack measured here. This run therefore does not confirm the 135.17 req/s /
7.5 s P99 pair, and it should not be described as reproducing it.

## Test environment

- **Date/time (UTC):** 2026-11-12T16:58:53Z → 2026-11-12T17:01:38Z
- **Git:** `main` @ `da411c864ac76732fd1b24401a9d7b19ca7ff987`, working tree had one
  uncommitted change: the Dockerfile `CMD` fix to run uvicorn on port 8000
  (required for the compose port mapping; committed in this benchmark branch).
- **Host:** HP Victus 16-e0xxx, AMD Ryzen 5 5600H (6C/12T), 7.3 GB RAM,
  Windows 11 10.0.26300.
- **Docker Desktop:** 29.5.3 / Compose v5.1.4; VM with 12 CPUs and 3.5 GiB RAM.
  No container CPU/memory limits are configured in `docker-compose.yml`.
- **Python (host / Locust):** 3.12.7 / Locust 2.44.4 (gevent 25.9.1)
- **Python (API container):** 3.12.16
- **FastAPI:** 0.115.6 — **Uvicorn:** 0.32.1 — **SQLAlchemy:** 2.0.36 —
  **psycopg2:** 2.9.13 — **Pydantic:** 2.10.3
- **PostgreSQL:** 16.14 (`postgres:16-alpine`), `max_connections = 100`, port
  5433 on the host.

## Workload (unchanged from `locustfile.py`)

| Method | Endpoint | Expected status | Weight |
|---|---|---|---|
| GET | `/api/v1/r/enqLbP` (reported as `/api/v1/r/[short_code]`) | 302, redirect not followed | 2 |
| GET | `/health` | 200 | 1 |

- Simulated users: **300**, spawn rate **30 users/s**
- Wait time: uniform **1–3 s**
- Request timeout: **10 s** (`network_timeout`), so a hung request becomes a
  recorded failure instead of hanging the run
- Single Locust process. Distributed (`--worker`) mode is **not supported** by
  the exact-request gate: each worker would get its own budget.
- Preflight: `/health` returned 200 with `database: healthy`; the short code
  `enqLbP` existed and returned 302 (`Location: https://example.com/`). No test
  data was created or modified.

## Exact-request termination

`locustfile_15000.py` reserves a slot under a `threading.Lock` immediately
before each HTTP request. Once 15,000 slots are reserved, every user raises
`StopUser`. The runner quits only after the last reserved request has completed
(a `finally` block releases the slot, after Locust has already recorded the
request event). This counts successes, non-302 responses, connection exceptions
and timeouts as attempts; it does not use `--run-time`.

The gate was smoke-tested at a 20-request budget (20/20 recorded) before the
15,000-request run.

## Connection pool and saturation

Current configuration (unchanged, introduced in commit `73e2ebe`):

```
engine = create_engine(
    db_url,
    echo=settings.is_development,   # True here: SQL logged twice per statement
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)                                   # => at most 30 pooled connections
```

`pool_timeout` is **not** configured, so SQLAlchemy's 30 s default applies.
`pool_recycle` is **not** configured (default `-1`, disabled). The app uses one
shared engine; `get_db()` closes sessions in `finally` and rolls back on
exceptions; all route handlers are synchronous and run in Uvicorn's threadpool
(default ~40 threads).

`scripts/monitor_pool.py` sampled `pg_stat_activity` and `docker stats` every
2 s during the run (`pool_monitor.csv`, 47 samples):

- PostgreSQL sessions: 6 → **32** (avg 25.7); the count includes the monitor's
  own psql session and possible transient healthcheck connections, and 32 is
  at/above the API's 30-connection ceiling.
- Active sessions peaked at **24**; sessions waiting on a heavyweight lock
  peaked at **23** (avg 14.0).
- API container CPU: avg **100 %**, peak **135 %**; PostgreSQL CPU: avg 33 %,
  peak 60 %.
- API memory 60.8 → 73.4 MiB; PostgreSQL 45.6 → 91.1 MiB.

The pool reached its ceiling, but **pool checkout contention is not confirmed**:
there were no `QueuePool` timeout errors and no 5xx. Checkout wait time was not
measured — SQLAlchemy's checkout counters live inside the API process, and the
monitor's own psql latency is not pool wait time, so it is not reported as such.

A short diagnostic sampling of `wait_event` during load showed where the
blocking actually was:

| wait_event_type / wait_event | Session-samples |
|---|---:|
| `Lock` / `transactionid` | 900 |
| `CPU` / – | 62 |
| `Lock` / `tuple` | 56 |
| `LWLock` / `LockManager` | 15 |
| `IO` / `WALSync` | 7 |

Every redirect fetches the URL row and commits `url_entry.clicks += 1`, so all
redirects serialize on an `UPDATE` of the **same row** for `enqLbP`. That row
lock — not the pool — is the dominant measured source of latency. This is an
observation from Postgres wait events, not a claim that the pool is innocent;
proving pool wait would require in-process instrumentation of
`engine.pool` checkout events.

### Diagnostic/repeat run (not merged with the canonical result)

`reports/2026-11-12/diagnostics/` holds a second run that was intended to be a
short 1,500-request wait-event probe. The target override was omitted, so it ran
the default 15,000 requests under the identical configuration and workload:

15,000 requests, 0 failures, average 988.80 ms, median 1,000 ms, P95 1,800 ms,
P99 2,200 ms, max 3,466.31 ms, average 97.82 req/s, peak 105.40 req/s.

It is kept only as a repeatability check. Its statistics are **never** combined
with the canonical run above, and it is not the reported benchmark. Its
wait-event sampling only covered roughly the first 55 seconds.

## Reproduce

```bash
# 1. Stack (never use `docker compose down -v`; it destroys the DB volume)
docker compose up -d --build

# 2. Preflight
curl -i http://127.0.0.1:8000/health
curl -i http://127.0.0.1:8000/api/v1/r/enqLbP   # expect 302, Location: https://example.com/

# 3. Optional resource/pool monitoring (separate process)
python scripts/monitor_pool.py --output reports/2026-11-12/pool_monitor.csv \
  --interval 2 --duration 900

# 4. Benchmark — the request budget, not --run-time, ends the test
LOCUST_SUMMARY_PATH=reports/2026-11-12/run_summary.json \
python -m locust -f locustfile_15000.py --headless \
  --host http://127.0.0.1:8000 \
  --users 300 --spawn-rate 30 \
  --csv reports/2026-11-12/urlshortener_15000 --csv-full-history \
  --html reports/2026-11-12/urlshortener_15000.html \
  --stop-timeout 60
```

On Windows, use `venv/Scripts/python.exe`. Verify
`stats.total.num_requests == 15000` in `run_summary.json` and in the
`Aggregated` row of `urlshortener_15000_stats.csv`; anything else is an
incomplete run and must not be presented as this report.

## Artifacts

| File | Contents |
|---|---|
| `urlshortener_15000.html` | Locust HTML report for this run |
| `urlshortener_15000_stats.csv` | Aggregate + per-endpoint statistics |
| `urlshortener_15000_stats_history.csv` | Full per-second history (peak RPS source) |
| `urlshortener_15000_failures.csv` | Failure table (header only — no failures) |
| `urlshortener_15000_exceptions.csv` | Exception table (header only) |
| `run_summary.json` | Gate counters written by the Locust listener |
| `pool_monitor.csv` | `pg_stat_activity` + container CPU/memory samples |
| `diagnostics/wait_events.csv` | Active-session wait events during load |
| `diagnostics/diag_*` | Separate repeat run (not merged) |
| `benchmark_metadata.json` | Machine-readable record of all values above |
