"""Expose the current single-process Locust run as Prometheus metrics.

Counters restart when the user resets Locust statistics or begins a new run.
Prometheus rate() handles those resets. Do not sum endpoint and aggregate rows.
"""

from prometheus_client.core import CounterMetricFamily, GaugeMetricFamily


class LocustCollector:
    def __init__(self, environment):
        self.environment = environment

    def collect(self):
        stats = self.environment.stats
        runner = self.environment.runner
        users = GaugeMetricFamily("locust_users", "Currently active simulated users")
        users.add_metric([], getattr(runner, "user_count", 0))
        yield users

        running = GaugeMetricFamily("locust_running", "Whether a test is running (0 or 1)")
        running.add_metric([], int(getattr(runner, "state", "ready") in {"running", "spawning"}))
        yield running

        exporter = GaugeMetricFamily("locust_exporter_up", "Embedded Locust metrics collector is available")
        exporter.add_metric([], 1)
        yield exporter

        requests = CounterMetricFamily("locust_requests", "Requests since statistics were reset", labels=["method", "name"])
        failures = CounterMetricFamily("locust_failures", "Failed requests since statistics were reset", labels=["method", "name"])
        rps = GaugeMetricFamily("locust_current_rps", "Recent requests per second as calculated by Locust", labels=["method", "name"])
        average = GaugeMetricFamily("locust_response_time_avg_seconds", "Mean request duration over the current test", labels=["method", "name"])
        percentiles = GaugeMetricFamily("locust_response_time_seconds", "Response time percentile over the current test", labels=["method", "name", "quantile"])
        last_request = GaugeMetricFamily("locust_last_request_timestamp_seconds", "Last recorded request time, Unix seconds", labels=["method", "name"])

        entries = list(stats.entries.values()) + [stats.total]
        for entry in entries:
            method = entry.method or "ALL"
            name = "Aggregated" if entry is stats.total else entry.name
            labels = [method, name]
            requests.add_metric(labels, entry.num_requests)
            failures.add_metric(labels, entry.num_failures)
            rps.add_metric(labels, entry.current_rps)
            last_request.add_metric(labels, entry.last_request_timestamp or 0)
            if entry.num_requests:
                average.add_metric(labels, entry.avg_response_time / 1000.0)
                for quantile in (0.5, 0.95, 0.99):
                    percentile = entry.get_response_time_percentile(quantile)
                    if percentile is not None:
                        percentiles.add_metric(labels + [str(quantile)], percentile / 1000.0)

        yield requests
        yield failures
        yield rps
        yield average
        yield percentiles
        yield last_request
