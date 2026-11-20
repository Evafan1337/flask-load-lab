"""Run with: python -m locust -f load_tests/locustfile.py.

Use LAB_SCENARIO to select baseline, mixed, slow, errors or cpu.
"""

import logging
import os
import random
from urllib.parse import urlparse

from locust import HttpUser, between, events, task
from prometheus_client import CollectorRegistry, start_http_server

from load_tests.metrics import LocustCollector

LOGGER = logging.getLogger(__name__)
SCENARIO = os.environ.get("LAB_SCENARIO", "mixed").lower()
SCENARIOS = {"baseline", "mixed", "slow", "errors", "cpu"}
if SCENARIO not in SCENARIOS:
    raise ValueError(f"LAB_SCENARIO must be one of {sorted(SCENARIOS)}, got {SCENARIO!r}")


def bounded_env(name, default, minimum, maximum, converter=int):
    value = converter(os.environ.get(name, str(default)))
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be in [{minimum}, {maximum}]")
    return value


DELAY_MS = bounded_env("LAB_DELAY_MS", 250, 0, 2000)
ERROR_RATE = bounded_env("LAB_ERROR_RATE", 0.15, 0, 1, float)
CPU_ITERATIONS = bounded_env("LAB_CPU_ITERATIONS", 100000, 1000, 1000000)
DEMO_CART = {"items": [{"id": "notebook", "quantity": 2}]}
_metrics_server = None


@events.init_command_line_parser.add_listener
def add_lab_options(parser, **kwargs):
    # Locust displays custom arguments with choices as a dropdown in its web UI.
    parser.add_argument(
        "--lab-scenario", choices=sorted(SCENARIOS), default=SCENARIO,
        env_var="LAB_SCENARIO", help="Educational workload profile",
    )


@events.init.add_listener
def start_metrics(environment, **kwargs):
    global _metrics_server
    options = environment.parsed_options
    if options and (getattr(options, "master", False) or getattr(options, "worker", False)):
        raise ValueError("This teaching exporter supports one Locust process; omit --master/--worker.")
    if os.environ.get("LAB_METRICS_ENABLED", "1") == "0":
        return
    if _metrics_server is not None:
        return
    registry = CollectorRegistry()
    registry.register(LocustCollector(environment))
    bind_address = os.environ.get("LAB_METRICS_HOST", "127.0.0.1")
    port = bounded_env("LAB_METRICS_PORT", 9646, 1024, 65535)
    _metrics_server, _ = start_http_server(port, addr=bind_address, registry=registry)
    # The exporter uses a daemon thread. Let process exit release its socket:
    # HTTPServer.shutdown() in Locust's quitting event can deadlock with gevent.
    LOGGER.info("Lab metrics: http://%s:%s/metrics; scenario=%s", bind_address, port, SCENARIO)


@events.test_start.add_listener
def check_target(environment, **kwargs):
    host = environment.host or LabUser.host
    parsed = urlparse(host)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Set a valid HTTP(S) target with --host or LAB_TARGET_HOST.")
    allowed_hosts = {"localhost", "127.0.0.1", "::1", "flask"}
    if parsed.hostname not in allowed_hosts and os.environ.get("LAB_ALLOW_REMOTE", "0") != "1":
        LOGGER.error("Target %s is not local. For your own authorized remote target, set LAB_ALLOW_REMOTE=1.", host)
        environment.process_exit_code = 2
        environment.runner.quit()
        return
    scenario = getattr(environment.parsed_options, "lab_scenario", SCENARIO)
    if scenario not in SCENARIOS:
        LOGGER.error("Unknown lab scenario: %s", scenario)
        environment.process_exit_code = 2
        environment.runner.quit()
        return
    LOGGER.info("Starting %s scenario against %s", scenario, host)


class LabUser(HttpUser):
    host = os.environ.get("LAB_TARGET_HOST", "http://127.0.0.1:5000")
    wait_time = between(0.15, 0.5)

    @task
    def request_demo_api(self):
        scenario = getattr(self.environment.parsed_options, "lab_scenario", SCENARIO)
        if scenario == "mixed":
            scenario = random.choices(
                ["baseline", "slow", "errors", "cpu"],
                weights=[8, 2, 1, 1],
                k=1,
            )[0]
        timeout = (2, 5)
        if scenario == "baseline":
            self.client.get("/api/products", name="/api/products", timeout=timeout)
        elif scenario == "slow":
            self.client.get(
                "/api/products", params={"delay_ms": DELAY_MS},
                name="/api/products", timeout=timeout,
            )
        elif scenario == "errors":
            # 503 responses intentionally count as failures in Locust and Grafana.
            self.client.post(
                "/api/orders", params={"error_rate": ERROR_RATE}, json=DEMO_CART,
                name="/api/orders", timeout=timeout,
            )
        elif scenario == "cpu":
            self.client.get(
                "/api/products/notebook", params={"iterations": CPU_ITERATIONS},
                name="/api/products/<product_id>", timeout=timeout,
            )
