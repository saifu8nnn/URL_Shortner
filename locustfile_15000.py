"""Exact-15,000-request Locust benchmark for the URL Shortener API.

This file keeps the workload of the original ``locustfile.py`` unchanged:

    * ``GET /api/v1/r/enqLbP``  expected HTTP 302, weight 2
    * ``GET /health``           expected HTTP 200, weight 1
    * ``wait_time = between(1, 3)``

The difference is termination: instead of ``--run-time``, a process-wide,
lock-protected request budget guarantees that no more than 15,000 HTTP
requests are ever attempted. A slot is reserved immediately before each
request and released when that request has completed (success, HTTP error,
connection exception or timeout). Once the budget is exhausted, every
remaining user raises ``StopUser`` and the runner quits only after the last
reserved request has finished, so Locust has already recorded its statistics.

Environment overrides (all optional, defaults are the benchmark values):

    LOCUST_TARGET_REQUESTS   total request attempts          (default 15000)
    LOCUST_REDIRECT_PATH     redirect path to exercise       (default /api/v1/r/enqLbP)
    LOCUST_REQUEST_TIMEOUT   per-request timeout in seconds  (default 10)
    LOCUST_SUMMARY_PATH      where to write the run summary JSON

Single-process mode only. Distributed (``--worker``) mode is not supported:
the counter lives in this process and workers would each get their own budget.
"""

import json
import os
import threading
import time

import gevent
from locust import HttpUser, between, events, task
from locust.exception import StopUser

TARGET_REQUESTS = int(os.getenv("LOCUST_TARGET_REQUESTS", "15000"))
REDIRECT_PATH = os.getenv("LOCUST_REDIRECT_PATH", "/api/v1/r/enqLbP")
REQUEST_TIMEOUT = float(os.getenv("LOCUST_REQUEST_TIMEOUT", "10"))
SUMMARY_PATH = os.getenv("LOCUST_SUMMARY_PATH", "")

_lock = threading.Lock()
_reserved = 0
_completed = 0
_in_flight = 0
_quit_scheduled = False
_started_at = None
_finished_at = None


def _reserve_slot() -> bool:
    """Atomically claim one of the TARGET_REQUESTS request slots."""
    global _reserved, _in_flight
    with _lock:
        if _reserved >= TARGET_REQUESTS:
            return False
        _reserved += 1
        _in_flight += 1
        return True


def _release_slot(user: "URLShortenerUser") -> None:
    """Mark a reserved request as finished and stop the run when done."""
    global _completed, _in_flight, _quit_scheduled, _finished_at
    schedule_quit = False
    with _lock:
        _completed += 1
        _in_flight -= 1
        # Locust updates its statistics synchronously before the task returns,
        # so _in_flight == 0 means every reserved request has been recorded.
        if _completed >= TARGET_REQUESTS and _in_flight == 0 and not _quit_scheduled:
            _quit_scheduled = True
            _finished_at = time.time()
            schedule_quit = True
    if schedule_quit:
        # Give Locust one second to flush the final request event, then quit.
        gevent.spawn_later(1.0, user.environment.runner.quit)


class URLShortenerUser(HttpUser):
    # Identical to the original workload.
    wait_time = between(1, 3)
    network_timeout = REQUEST_TIMEOUT

    def _run_request(self, func) -> None:
        if not _reserve_slot():
            # Budget exhausted: no user may issue another request.
            raise StopUser()
        try:
            func()
        finally:
            _release_slot(self)

    @task(1)
    def test_health_check(self) -> None:
        """Hits /health; expected HTTP 200 (any other status is a failure)."""
        self._run_request(
            lambda: self.client.get("/health", name="/health")
        )

    @task(2)
    def test_url_redirect(self) -> None:
        """Hits the short link; expected HTTP 302 without following it."""
        def request() -> None:
            with self.client.get(
                REDIRECT_PATH,
                name="/api/v1/r/[short_code]",
                allow_redirects=False,
                catch_response=True,
            ) as response:
                if response.status_code == 302:
                    response.success()
                else:
                    response.failure(f"Expected 302, got {response.status_code}")

        self._run_request(request)


@events.test_start.add_listener
def _on_test_start(environment, **_kwargs) -> None:
    global _started_at
    _started_at = time.time()
    print(
        f"[15000-gate] target={TARGET_REQUESTS} requests, "
        f"redirect={REDIRECT_PATH}, timeout={REQUEST_TIMEOUT}s",
        flush=True,
    )


@events.test_stop.add_listener
def _on_test_stop(environment, **_kwargs) -> None:
    stats = environment.stats.total
    duration = (time.time() - _started_at) if _started_at else 0.0
    complete = stats.num_requests == TARGET_REQUESTS
    summary = {
        "target_requests": TARGET_REQUESTS,
        "slots_reserved": _reserved,
        "requests_completed": _completed,
        "num_requests_recorded_by_locust": stats.num_requests,
        "num_failures_recorded_by_locust": stats.num_failures,
        "exact_target_reached": complete,
        "started_at_epoch": _started_at,
        "finished_at_epoch": _finished_at,
        "wall_clock_seconds": round(duration, 3),
        "redirect_path": REDIRECT_PATH,
        "request_timeout_seconds": REQUEST_TIMEOUT,
    }
    print(f"[15000-gate] {json.dumps(summary, indent=2)}", flush=True)

    if SUMMARY_PATH:
        os.makedirs(os.path.dirname(SUMMARY_PATH) or ".", exist_ok=True)
        with open(SUMMARY_PATH, "w", encoding="utf-8") as handle:
            json.dump(summary, handle, indent=2)
            handle.write("\n")

    if not complete:
        print(
            "[15000-gate] RUN INCOMPLETE: Locust recorded "
            f"{stats.num_requests} requests, expected {TARGET_REQUESTS}. "
            "Do not present this run as the canonical 15,000-request report.",
            flush=True,
        )
