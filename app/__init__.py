"""A deliberately small application for repeatable load-testing exercises."""

import math
import os
import random
import time

import psutil
from flask import Flask, Response, g, jsonify, render_template, request
from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Counter, Gauge, Histogram, generate_latest
from prometheus_client.core import CounterMetricFamily, GaugeMetricFamily


class ProcessMetrics:
    """psutil keeps process metrics available on Windows as well as Linux."""

    def __init__(self):
        self.process = psutil.Process(os.getpid())

    def collect(self):
        with self.process.oneshot():
            cpu = self.process.cpu_times()
            yield CounterMetricFamily(
                "flask_process_cpu_seconds", "CPU seconds consumed by the Flask process.",
                value=cpu.user + cpu.system,
            )
            yield GaugeMetricFamily(
                "flask_process_resident_memory_bytes", "Resident memory of the Flask process in bytes.",
                value=self.process.memory_info().rss,
            )
            yield GaugeMetricFamily(
                "flask_process_threads", "Current thread count of the Flask process.",
                value=self.process.num_threads(),
            )


def create_app(test_config=None):
    app = Flask(__name__)
    app.json.sort_keys = False
    if test_config:
        app.config.update(test_config)

    # A separate registry per app also makes repeated factory calls safe in tests.
    registry = CollectorRegistry()
    registry.register(ProcessMetrics())
    requests = Counter(
        "flask_http_requests_total", "Completed HTTP requests.",
        ["method", "endpoint", "status"], registry=registry,
    )
    duration = Histogram(
        "flask_http_request_duration_seconds", "Application HTTP latency, in seconds.",
        ["method", "endpoint", "status"],
        buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10), registry=registry,
    )
    inflight = Gauge(
        "flask_http_requests_in_progress", "Requests currently executing in the Flask application.",
        ["method", "endpoint"], registry=registry,
    )
    app.extensions["metrics_registry"] = registry

    @app.before_request
    def start_request():
        if request.path == "/metrics":
            return
        g.metric_endpoint = request.url_rule.rule if request.url_rule else "unmatched"
        # Unknown HTTP method tokens must not create unbounded label values.
        known_methods = {"GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "TRACE", "CONNECT"}
        g.metric_method = request.method if request.method in known_methods else "OTHER"
        g.metric_started = time.perf_counter()
        inflight.labels(g.metric_method, g.metric_endpoint).inc()

    @app.after_request
    def finish_request(response):
        if hasattr(g, "metric_started"):
            elapsed = time.perf_counter() - g.metric_started
            labels = (g.metric_method, g.metric_endpoint, str(response.status_code))
            requests.labels(*labels).inc()
            duration.labels(*labels).observe(elapsed)
            inflight.labels(g.metric_method, g.metric_endpoint).dec()
        response.headers["Cache-Control"] = "no-store"
        return response

    def integer_argument(name, default, minimum, maximum):
        raw = request.args.get(name, str(default))
        try:
            value = int(raw)
        except (TypeError, ValueError):
            raise ValueError(f"{name}: требуется целое число от {minimum} до {maximum}")
        if not minimum <= value <= maximum:
            raise ValueError(f"{name}: допустимый диапазон {minimum}–{maximum}")
        return value

    @app.errorhandler(ValueError)
    def invalid_argument(error):
        return jsonify(error="invalid_parameter", message=str(error)), 400

    @app.errorhandler(404)
    def not_found(_error):
        return jsonify(error="not_found", message="Маршрут не найден"), 404

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/health")
    def health():
        return jsonify(status="ok", service="flask-load-lab")

    @app.get("/api/fast")
    def fast():
        return jsonify(scenario="fast", message="Быстрый ответ без искусственной задержки")

    @app.get("/api/slow")
    def slow():
        delay_ms = integer_argument("delay_ms", 250, 0, 3000)
        time.sleep(delay_ms / 1000)
        return jsonify(scenario="slow", delay_ms=delay_ms)

    @app.get("/api/cpu")
    def cpu():
        iterations = integer_argument("iterations", 100000, 1000, 2000000)
        # Pure Python intentionally demonstrates contention under the GIL.
        checksum = 0
        for value in range(iterations):
            checksum = (checksum + value * value) % 1000000007
        return jsonify(scenario="cpu", iterations=iterations, checksum=checksum)

    @app.get("/api/flaky")
    def flaky():
        try:
            error_rate = float(request.args.get("error_rate", "0.2"))
        except (TypeError, ValueError):
            raise ValueError("error_rate: требуется число от 0 до 1")
        if not math.isfinite(error_rate) or not 0 <= error_rate <= 1:
            raise ValueError("error_rate: допустимый диапазон 0–1")
        if random.random() < error_rate:
            return jsonify(scenario="flaky", error="simulated_failure", error_rate=error_rate), 503
        return jsonify(scenario="flaky", status="ok", error_rate=error_rate)

    @app.get("/metrics")
    def metrics():
        return Response(generate_latest(registry), content_type=CONTENT_TYPE_LATEST)

    return app
