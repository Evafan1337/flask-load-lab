"""Contract tests for units, counter names, aggregate labels and test resets."""

from types import SimpleNamespace

from prometheus_client import CollectorRegistry, generate_latest

from load_tests.metrics import LocustCollector


def make_environment(request_count=10):
    entry = SimpleNamespace(
        method="GET", name="/api/products", num_requests=request_count,
        num_failures=2 if request_count else 0, current_rps=3.5 if request_count else 0,
        last_request_timestamp=1234 if request_count else None,
        avg_response_time=125, get_response_time_percentile=lambda q: 250,
    )
    total = SimpleNamespace(**vars(entry))
    total.method = None
    total.name = "Aggregated"
    return SimpleNamespace(
        runner=SimpleNamespace(user_count=5, state="running"),
        stats=SimpleNamespace(entries={(entry.name, entry.method): entry}, total=total),
    )


def render(environment):
    registry = CollectorRegistry()
    registry.register(LocustCollector(environment))
    return generate_latest(registry).decode("utf-8")


def test_exporter_units_and_aggregate_labels():
    metrics = render(make_environment())
    assert 'locust_requests_total{method="GET",name="/api/products"} 10.0' in metrics
    assert 'locust_requests_total{method="ALL",name="Aggregated"} 10.0' in metrics
    assert 'locust_failures_total{method="GET",name="/api/products"} 2.0' in metrics
    assert 'locust_response_time_avg_seconds{method="ALL",name="Aggregated"} 0.125' in metrics
    assert 'locust_response_time_seconds{method="ALL",name="Aggregated",quantile="0.95"} 0.25' in metrics
    assert 'locust_users 5.0' in metrics
    assert 'locust_running 1.0' in metrics


def test_empty_run_exposes_zero_counts_without_invented_percentiles():
    environment = make_environment(0)
    environment.runner.state = "stopped"
    metrics = render(environment)
    assert 'locust_requests_total{method="ALL",name="Aggregated"} 0.0' in metrics
    assert 'locust_running 0.0' in metrics
    assert 'locust_response_time_seconds{' not in metrics


def test_statistics_reset_is_visible_as_counter_reset():
    environment = make_environment()
    assert 'locust_requests_total{method="ALL",name="Aggregated"} 10.0' in render(environment)
    environment.stats.total.num_requests = 0
    environment.stats.total.num_failures = 0
    assert 'locust_requests_total{method="ALL",name="Aggregated"} 0.0' in render(environment)
