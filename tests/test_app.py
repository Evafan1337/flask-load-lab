"""Проверки API магазина и метрик запросов."""

import time

import pytest
from prometheus_client.parser import text_string_to_metric_families

from app import create_app


@pytest.fixture
def client():
    return create_app({"TESTING": True}).test_client()


def samples(client, name):
    payload = client.get("/metrics").get_data(as_text=True)
    return [sample for family in text_string_to_metric_families(payload) for sample in family.samples if sample.name == name]


def test_store_and_documentation(client):
    store = client.get("/")
    assert store.status_code == 200
    assert '<html lang="ru">' in store.get_data(as_text=True)
    assert '/docs' in store.get_data(as_text=True)
    assert "Документация магазина" in client.get("/docs").get_data(as_text=True)
    assert client.get("/health").json == {"status": "ok", "service": "flask-load-lab"}


def test_catalog_and_products(client):
    assert set(client.get("/api/categories").json["categories"]) == {"Бумага", "Письмо", "Аксессуары"}
    all_products = client.get("/api/products").json["products"]
    assert len(all_products) == 8
    pens = client.get("/api/products", query_string={"category": "Письмо", "sort": "high"}).json["products"]
    assert [product["price"] for product in pens] == [119, 49]
    match = client.get("/api/products", query_string={"q": "ТЕТРАДЬ"}).json["products"]
    assert [product["id"] for product in match] == ["notebook"]
    detail = client.get("/api/products/notebook?iterations=1000").json["product"]
    assert detail == match[0]
    assert client.get("/api/products/unknown").status_code == 404


def test_catalog_delay_preserves_data(client):
    baseline = client.get("/api/products").json
    started = time.perf_counter()
    response = client.get("/api/products?delay_ms=30")
    assert response.status_code == 200
    assert response.json == baseline
    assert time.perf_counter() - started >= 0.025


@pytest.mark.parametrize("url", [
    "/api/products?delay_ms=-1", "/api/products?delay_ms=3001", "/api/products?delay_ms=bad",
    "/api/products?sort=unknown", "/api/products?q=" + "a" * 101,
    "/api/products/pen?iterations=-1", "/api/products/pen?iterations=2000001",
    "/api/products/pen?iterations=1.2",
])
def test_invalid_catalog_parameters(client, url):
    response = client.get(url)
    assert response.status_code == 400
    assert response.json["error"] == "invalid_parameter"


def test_cart_and_checkout_use_catalog_prices(client):
    body = {"items": [{"id": "notebook", "quantity": 2, "price": 1}, {"id": "pen", "quantity": 1}]}
    quote = client.post("/api/cart", json=body)
    assert quote.status_code == 200
    assert quote.json["total"] == 207
    assert quote.json["quantity"] == 3
    assert [line["subtotal"] for line in quote.json["items"]] == [158, 49]
    order = client.post("/api/orders", json=body)
    assert order.status_code == 201
    assert len(order.json["order_number"]) == 12
    assert order.json["total"] == quote.json["total"]
    assert order.json["items"] == quote.json["items"]
    assert client.post("/api/cart", json={"items": []}).json["total"] == 0
    assert client.post("/api/orders", json={"items": []}).status_code == 400


@pytest.mark.parametrize("items", [
    None, {}, [{"id": []}], [{"id": "missing", "quantity": 1}], [{"id": "pen", "quantity": True}],
    [{"id": "pen", "quantity": 0}], [{"id": "pen", "quantity": 100}], [{"id": "pen", "quantity": 1.5}],
    [{"id": "pen", "quantity": 1}, {"id": "pen", "quantity": 2}],
])
def test_invalid_cart_items(client, items):
    response = client.post("/api/cart", json={"items": items})
    assert response.status_code == 400
    assert response.json["error"] == "invalid_parameter"


@pytest.mark.parametrize("rate", ["bad", "nan", "inf", "-0.01", "1.01"])
def test_invalid_order_error_rate(client, rate):
    body = {"items": [{"id": "notebook", "quantity": 2}]}
    assert client.post(f"/api/orders?error_rate={rate}", json=body).status_code == 400


def test_checkout_errors_are_deterministic_and_observable(client):
    body = {"items": [{"id": "pen", "quantity": 2}]}
    assert client.post("/api/orders?error_rate=0", json=body).status_code == 201
    failure = client.post("/api/orders?error_rate=1", json=body)
    assert failure.status_code == 503
    assert failure.json["error"] == "simulated_failure"
    counts = samples(client, "flask_http_requests_total")
    assert any(sample.labels["endpoint"] == "/api/orders" and sample.labels["status"] == "503" and sample.value == 1 for sample in counts)


def test_labels_collapse_parameters_and_unknown_routes(client):
    client.get("/api/products/notebook?iterations=0")
    client.get("/api/products/pen")
    client.get("/unmatched-a")
    client.get("/unmatched-b")
    counts = samples(client, "flask_http_requests_total")
    products = [sample for sample in counts if sample.labels["endpoint"] == "/api/products/<product_id>"]
    unmatched = [sample for sample in counts if sample.labels["endpoint"] == "unmatched"]
    assert len(products) == 1 and products[0].value == 2
    assert len(unmatched) == 1 and unmatched[0].value == 2
    assert not any("?" in sample.labels["endpoint"] or sample.labels["endpoint"] == "/metrics" for sample in counts)


def test_unknown_http_methods_have_one_bounded_label(client):
    client.open("/api/products", method="CUSTOM_A")
    client.open("/api/products", method="CUSTOM_B")
    counts = samples(client, "flask_http_requests_total")
    assert len(counts) == 1
    assert counts[0].labels == {"method": "OTHER", "endpoint": "unmatched", "status": "405"}
    assert counts[0].value == 2


def test_duration_histogram_and_inflight_return_to_zero(client):
    client.get("/api/products")
    durations = samples(client, "flask_http_request_duration_seconds_count")
    assert any(sample.labels["endpoint"] == "/api/products" and sample.value == 1 for sample in durations)
    assert all(sample.value == 0 for sample in samples(client, "flask_http_requests_in_progress"))


def test_process_metrics_are_available_on_windows_and_linux(client):
    assert samples(client, "flask_process_resident_memory_bytes")[0].value > 0
    assert samples(client, "flask_process_cpu_seconds_total")[0].value >= 0
    assert samples(client, "flask_process_threads")[0].value >= 1


def test_factories_have_independent_metrics_registries():
    first = create_app({"TESTING": True}).test_client()
    second = create_app({"TESTING": True}).test_client()
    first.get("/api/products")
    assert samples(first, "flask_http_requests_total")
    assert samples(second, "flask_http_requests_total") == []
