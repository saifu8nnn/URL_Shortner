"""Non-invasive connection-pool / resource monitor for the Locust benchmark.

Run this on the host *while* Locust is running (or against an idle stack). It
polls PostgreSQL's own ``pg_stat_activity`` view and Docker's container stats.
It never imports or modifies the application, so it cannot change the
behaviour being measured.

What it can show:
    * how many PostgreSQL connections the API holds (pool_size + overflow)
    * how many of them are actually executing a query
    * how many sessions are waiting on a lock or on the client
    * API and PostgreSQL container CPU / memory usage

What it cannot show:
    * SQLAlchemy's in-process ``checkedout()`` / ``overflow()`` counters, and
      therefore the time a request spends waiting for a pool connection.
      Those are only visible inside the API process. A pool checkout event's
      duration is *not* the time spent waiting for a connection, so we do not
      report it as such. A maximum connection count alone is not evidence of
      contention either; contention would additionally require checkout waits.

Usage:
    python scripts/monitor_pool.py --output reports/<date>/pool_monitor.csv \
        --interval 2 --duration 600
"""

import argparse
import csv
import os
import subprocess
import sys
import time
from datetime import datetime, timezone

PSQL_QUERY = (
    "SELECT now(), count(*) AS total, "
    "count(*) FILTER (WHERE state = 'active') AS active, "
    "count(*) FILTER (WHERE state = 'idle') AS idle, "
    "count(*) FILTER (WHERE wait_event_type = 'Lock') AS lock_waiting, "
    "count(*) FILTER (WHERE wait_event_type = 'Client') AS client_waiting "
    "FROM pg_stat_activity WHERE datname = current_database()"
)

CONTAINERS = ("url_shortener_api", "url_shortener_db")
FIELDS = [
    "timestamp_utc",
    "pg_total",
    "pg_active",
    "pg_idle",
    "pg_lock_waiting",
    "pg_client_waiting",
    "api_cpu_pct",
    "api_mem_usage",
    "db_cpu_pct",
    "db_mem_usage",
]


def _run(cmd: list[str]) -> str:
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise RuntimeError(
            f"command failed ({' '.join(cmd)}): {result.stderr.strip()}"
        )
    return result.stdout.strip()


def sample_postgres() -> list[str]:
    # $POSTGRES_USER / $POSTGRES_DB are read inside the db container itself;
    # no credentials are read from or written to the host.
    out = _run(
        [
            "docker", "compose", "exec", "-T", "db",
            "sh", "-c",
            f'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAF "|" -c "{PSQL_QUERY}"',
        ]
    )
    line = next((ln for ln in out.splitlines() if ln.strip()), "")
    if not line:
        raise RuntimeError("empty pg_stat_activity sample")
    # psql unaligned output: timestamp|total|active|idle|lock|client
    parts = line.split("|")
    return parts[1:6]


def sample_docker() -> dict[str, tuple[str, str]]:
    out = _run(
        ["docker", "stats", "--no-stream", "--format",
         "{{.Name}}|{{.CPUPerc}}|{{.MemUsage}}", *CONTAINERS]
    )
    stats: dict[str, tuple[str, str]] = {}
    for line in out.splitlines():
        name, cpu, mem = line.split("|", 2)
        stats[name.strip()] = (cpu.strip(), mem.strip())
    return stats


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--interval", type=float, default=2.0)
    parser.add_argument("--duration", type=float, default=600.0)
    args = parser.parse_args()

    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    deadline = time.time() + args.duration
    rows = 0
    errors = 0

    with open(args.output, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        handle.flush()

        while time.time() < deadline:
            row = {
                "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "pg_total": "", "pg_active": "", "pg_idle": "",
                "pg_lock_waiting": "", "pg_client_waiting": "",
                "api_cpu_pct": "", "api_mem_usage": "",
                "db_cpu_pct": "", "db_mem_usage": "",
            }
            try:
                total, active, idle, lock_waiting, client_waiting = sample_postgres()
                row.update(
                    pg_total=total.strip(),
                    pg_active=active.strip(),
                    pg_idle=idle.strip(),
                    pg_lock_waiting=lock_waiting.strip(),
                    pg_client_waiting=client_waiting.strip(),
                )
            except Exception as exc:  # keep sampling; report errors at the end
                errors += 1
                print(f"[monitor] postgres sample failed: {exc}", file=sys.stderr)
            try:
                stats = sample_docker()
                api_cpu, api_mem = stats.get("url_shortener_api", ("", ""))
                db_cpu, db_mem = stats.get("url_shortener_db", ("", ""))
                row.update(
                    api_cpu_pct=api_cpu, api_mem_usage=api_mem,
                    db_cpu_pct=db_cpu, db_mem_usage=db_mem,
                )
            except Exception as exc:
                errors += 1
                print(f"[monitor] docker sample failed: {exc}", file=sys.stderr)

            writer.writerow(row)
            handle.flush()
            rows += 1
            time.sleep(args.interval)

    print(f"[monitor] wrote {rows} samples to {args.output} ({errors} sample errors)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
