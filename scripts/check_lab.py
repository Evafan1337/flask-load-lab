"""Check the running local stack and every dashboard's PromQL, without a browser."""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]


def get_json(url):
    with urlopen(url, timeout=10) as response:
        return json.load(response)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--require-data", action="store_true", help="Also fail when a query returns no series (run during a test).")
    parser.add_argument("--with-locust", action="store_true", help="Check the optional Locust service and dashboard too.")
    args = parser.parse_args()
    report = {"checked_utc": datetime.now(timezone.utc).isoformat(), "checks": []}
    errors = []
    checks = report["checks"]
    services = [
        ("flask", "http://127.0.0.1:5000/health"),
        ("grafana", "http://127.0.0.1:3000/api/health"),
        ("datasource", "http://127.0.0.1:3000/api/datasources/uid/prometheus/health"),
    ]
    if args.with_locust:
        services.append(("locust", "http://127.0.0.1:8089/stats/requests"))
    for name, url in services:
        result = get_json(url)
        if name == "datasource" and result.get("status") != "OK":
            errors.append(f"Grafana datasource: {result}")
        checks.append({"service": name, "http": 200})

    targets = get_json("http://127.0.0.1:9090/api/v1/targets")["data"]["activeTargets"]
    jobs = ("flask", "locust") if args.with_locust else ("flask",)
    for job in jobs:
        matches = [target for target in targets if target["labels"].get("job") == job]
        if not matches or any(target["health"] != "up" for target in matches):
            errors.append(f"Prometheus target {job} is not UP")

    query_count = 0
    with_data = 0
    for path in sorted((ROOT / "observability/grafana/dashboards").glob("*.json")):
        dashboard = json.loads(path.read_text(encoding="utf-8"))
        if not args.with_locust and dashboard["uid"] == "load-generator":
            continue
        live = get_json(f"http://127.0.0.1:3000/api/dashboards/uid/{dashboard['uid']}")
        metadata = live.get("meta", {})
        if not (metadata.get("provisioned") or metadata.get("provisionedExternalId")):
            errors.append(f"Dashboard {dashboard['uid']} is not provisioned")
        for panel in dashboard["panels"]:
            for target in panel.get("targets", []):
                expr = target["expr"].replace("$__rate_interval", "1m").replace("$endpoint", "/api/.*").replace("$generator", "locust(_headless)?")
                result = get_json("http://127.0.0.1:9090/api/v1/query?" + urlencode({"query": expr}))
                series = len(result.get("data", {}).get("result", []))
                query_count += 1
                with_data += bool(series)
                checks.append({"dashboard": dashboard["uid"], "panel": panel["id"], "ref": target["refId"], "query": expr, "status": result["status"], "series": series})
                if result["status"] != "success" or (args.require_data and not series):
                    errors.append(f"Query {dashboard['uid']}/{panel['id']}/{target['refId']}: {result}")
    report["errors"] = errors
    output = ROOT / "reports/stack-validation.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{query_count} dashboard queries; {with_data} return series; {len(errors)} errors.")
    print(output)
    if errors:
        raise SystemExit("\n".join(errors))


if __name__ == "__main__":
    main()
