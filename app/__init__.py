"""Учебный интернет-магазин и метрики нагрузочного тестирования."""

import math
import os
import random
import time
from uuid import uuid4

import psutil
from flask import Flask, Response, abort, g, jsonify, render_template, request
from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Counter, Gauge, Histogram, generate_latest
from prometheus_client.core import CounterMetricFamily, GaugeMetricFamily

from .catalog import CATEGORIES, MAX_QUANTITY, PRODUCTS


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
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024
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

    def quote_cart():
        body = request.get_json(silent=True)
        raw_items = body.get("items") if isinstance(body, dict) else None
        if not isinstance(raw_items, list) or len(raw_items) > len(PRODUCTS):
            raise ValueError("В JSON должен быть массив items с товарами из каталога.")

        used_ids = set()
        lines = []
        for entry in raw_items:
            if not isinstance(entry, dict):
                raise ValueError("Каждая позиция должна содержать id и quantity.")
            product_id = entry.get("id")
            quantity = entry.get("quantity")
            if not isinstance(product_id, str) or product_id not in PRODUCTS:
                raise ValueError("Товар не найден в каталоге.")
            if product_id in used_ids:
                raise ValueError("Объедините повторяющиеся товары в одну позицию.")
            if type(quantity) is not int or not 1 <= quantity <= MAX_QUANTITY:
                raise ValueError(f"Количество должно быть целым числом от 1 до {MAX_QUANTITY}.")
            used_ids.add(product_id)
            product = PRODUCTS[product_id]
            lines.append({
                "id": product_id,
                "name": product["name"],
                "price": product["price"],
                "quantity": quantity,
                "subtotal": product["price"] * quantity,
            })
        return {
            "items": lines,
            "quantity": sum(line["quantity"] for line in lines),
            "total": sum(line["subtotal"] for line in lines),
        }

    @app.errorhandler(ValueError)
    def invalid_argument(error):
        return jsonify(error="invalid_parameter", message=str(error)), 400

    @app.errorhandler(404)
    def not_found(_error):
        return jsonify(error="not_found", message="Страница или товар не найдены."), 404

    @app.errorhandler(413)
    def payload_too_large(_error):
        return jsonify(error="payload_too_large", message="Слишком большой запрос."), 413

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/docs")
    def documentation():
        return render_template("docs.html")

    @app.get("/health")
    def health():
        return jsonify(status="ok", service="flask-load-lab")

    @app.get("/api/categories")
    def categories():
        return jsonify(categories=CATEGORIES)

    @app.get("/api/products")
    def products():
        query = request.args.get("q", "").strip().casefold()
        category = request.args.get("category", "")
        sort = request.args.get("sort", "default")
        delay_ms = integer_argument("delay_ms", 0, 0, 3000)
        if len(query) > 100:
            raise ValueError("Строка поиска должна содержать не более 100 символов.")
        if sort not in {"default", "low", "high"}:
            raise ValueError("sort принимает default, low или high.")

        matched = [
            {"id": product_id, **product}
            for product_id, product in PRODUCTS.items()
            if query in product["name"].casefold()
            and (not category or product["category"] == category)
        ]
        if sort != "default":
            matched.sort(key=lambda product: product["price"], reverse=sort == "high")
        if delay_ms:
            time.sleep(delay_ms / 1000)
        return jsonify(products=matched)

    @app.get("/api/products/<product_id>")
    def product_detail(product_id):
        product = PRODUCTS.get(product_id)
        if product is None:
            abort(404)
        iterations = integer_argument("iterations", 0, 0, 2000000)
        if iterations:
            # Имитация вычислительно дорогой проверки скидок для CPU-профиля.
            sum(value * value for value in range(iterations))
        return jsonify(product={"id": product_id, **product})

    @app.post("/api/cart")
    def cart():
        return jsonify(quote_cart())

    @app.post("/api/orders")
    def create_order():
        quote = quote_cart()
        if not quote["items"]:
            raise ValueError("Добавьте хотя бы один товар для оформления заказа.")
        try:
            error_rate = float(request.args.get("error_rate", "0"))
        except (TypeError, ValueError):
            raise ValueError("error_rate: требуется число от 0 до 1") from None
        if not math.isfinite(error_rate) or not 0 <= error_rate <= 1:
            raise ValueError("error_rate: допустимый диапазон 0–1")
        if random.random() < error_rate:
            return jsonify(
                error="simulated_failure",
                message="Сервис оформления заказа временно недоступен.",
            ), 503
        return jsonify(order_number=uuid4().hex[:12].upper(), **quote), 201

    @app.get("/metrics")
    def metrics():
        return Response(generate_latest(registry), content_type=CONTENT_TYPE_LATEST)

    return app
