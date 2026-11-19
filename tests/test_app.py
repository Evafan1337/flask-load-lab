"""Behavior checks for bounded workloads and useful Prometheus labels."""

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


def test_landing_and_health(client):
    page = client.get("/")
    assert page.status_code == 200
    assert '<html lang="ru">' in page.get_data(as_text=True)
    assert client.get("/health").json == {"status": "ok", "service": "flask-load-lab"}


def test_slow_waits_and_returns_requested_delay(client):
    started = time.perf_counter()
    response = client.get("/api/slow?delay_ms=30")
    assert response.status_code == 200
    assert response.json["delay_ms"] == 30
    assert time.perf_counter() - started >= 0.025


@pytest.mark.parametrize("url", [
    "/api/slow?delay_ms=-1", "/api/slow?delay_ms=3001", "/api/slow?delay_ms=bad",
    "/api/cpu?iterations=999", "/api/cpu?iterations=2000001", "/api/cpu?iterations=1.2",
    "/api/flaky?error_rate=-0.01", "/api/flaky?error_rate=1.01",
    "/api/flaky?error_rate=nan", "/api/flaky?error_rate=inf", "/api/flaky?error_rate=bad",
])
def test_invalid_workloads_are_rejected(client, url):
    response = client.get(url)
    assert response.status_code == 400
    assert response.json["error"] == "invalid_parameter"


def test_flaky_extremes_are_deterministic_and_observable(client):
    assert client.get("/api/flaky?error_rate=0").status_code == 200
    failure = client.get("/api/flaky?error_rate=1")
    assert failure.status_code == 503
    assert failure.json["error"] == "simulated_failure"
    counts = samples(client, "flask_http_requests_total")
    assert any(sample.labels["endpoint"] == "/api/flaky" and sample.labels["status"] == "503" and sample.value == 1 for sample in counts)


def test_cpu_work_produces_repeatable_result(client):
    response = client.get("/api/cpu?iterations=1000")
    assert response.status_code == 200
    assert response.json["iterations"] == 1000
    assert response.json["checksum"] == sum(value * value for value in range(1000)) % 1000000007


def test_labels_collapse_parameters_and_unknown_routes(client):
    client.get("/api/slow?delay_ms=0")
    client.get("/api/slow?delay_ms=1")
    client.get("/unmatched-a")
    client.get("/unmatched-b")
    counts = samples(client, "flask_http_requests_total")
    slow = [sample for sample in counts if sample.labels["endpoint"] == "/api/slow"]
    unmatched = [sample for sample in counts if sample.labels["endpoint"] == "unmatched"]
    assert len(slow) == 1 and slow[0].value == 2
    assert len(unmatched) == 1 and unmatched[0].value == 2
    assert not any("?" in sample.labels["endpoint"] or sample.labels["endpoint"] == "/metrics" for sample in counts)


def test_unknown_http_methods_have_one_bounded_label(client):
    client.open("/api/fast", method="CUSTOM_A")
    client.open("/api/fast", method="CUSTOM_B")
    counts = samples(client, "flask_http_requests_total")
    assert len(counts) == 1
    assert counts[0].labels == {"method": "OTHER", "endpoint": "unmatched", "status": "405"}
    assert counts[0].value == 2


def test_duration_histogram_and_inflight_return_to_zero(client):
    client.get("/api/fast")
    durations = samples(client, "flask_http_request_duration_seconds_count")
    assert any(sample.labels["endpoint"] == "/api/fast" and sample.value == 1 for sample in durations)
    inflight = samples(client, "flask_http_requests_in_progress")
    assert all(sample.value == 0 for sample in inflight)


def test_process_metrics_are_available_on_windows_and_linux(client):
    assert samples(client, "flask_process_resident_memory_bytes")[0].value > 0
    assert samples(client, "flask_process_cpu_seconds_total")[0].value >= 0
    assert samples(client, "flask_process_threads")[0].value >= 1


def test_factories_have_independent_metrics_registries():
    first = create_app({"TESTING": True}).test_client()
    second = create_app({"TESTING": True}).test_client()
    first.get("/api/fast")
    assert samples(first, "flask_http_requests_total")
    assert samples(second, "flask_http_requests_total") == []
