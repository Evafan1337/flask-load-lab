"""Create a readable demo summary and fixed-time Grafana links from real runs."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    runs = json.loads((ROOT / "reports/comparison.json").read_text(encoding="utf-8-sig"))
    start = min(datetime.fromisoformat(run["summary"]["started_utc"]) for run in runs)
    end = max(datetime.fromisoformat(run["summary"]["finished_utc"]) for run in runs)
    from_ms = int((start.timestamp() - 5) * 1000)
    to_ms = int((end.timestamp() + 5) * 1000)
    samara = timezone(timedelta(hours=4))
    local_start, local_end = start.astimezone(samara), end.astimezone(samara)
    lines = [
        "# Результаты демонстрации Locust",
        "",
        f"Реальные прогоны {local_start:%d.%m.%Y}, {local_start:%H:%M:%S}–{local_end:%H:%M:%S} (Самара, UTC+4).",
        "Все компоненты работали на одном компьютере в Windows.",
        "",
        "| Сценарий | Пользователи | Длительность | Запросы | Ошибки | Среднее, мс | p95, мс | RPS |",
        "|---|---:|---|---:|---:|---:|---:|---:|",
    ]
    for run in runs:
        row = run["summary"]
        failure_pct = 100 * row["failures"] / row["requests"] if row["requests"] else 0
        lines.append(f"| {row['scenario']} | {row['users']} | {row['duration']} | {row['requests']} | {row['failures']} ({failure_pct:.1f}%) | {row['mean_ms']:.2f} | {row['p95_ms']:g} | {row['rps']:.2f} |")
    lines += [
        "",
        "Ожидаемые различия: baseline отвечает быстро; slow добавляет 250 мс; errors намеренно возвращает HTTP 503 примерно в 15% запросов. Доли на конечной выборке могут отличаться от заданной вероятности.",
        "",
        "## Показать сохранённый интервал",
        "",
        f"- [Grafana: Flask — все три прогона](http://127.0.0.1:3000/d/flask-load-lab?from={from_ms}&to={to_ms})",
        f"- [Grafana: Locust — все три прогона](http://127.0.0.1:3000/d/load-generator?from={from_ms}&to={to_ms}&var-generator=locust_headless)",
        "",
        "Ссылки открывают выбранный интервал в Grafana на компьютере с данными этого прогона.",
        "",
        "## Отчёты",
        "",
    ]
    for run in runs:
        # Only the report directory name is shared; do not embed a user's absolute path.
        folder = run["folder"].replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]
        label = run["summary"]["scenario"]
        lines.append(f"- {label}: [HTML]({folder}/report.html), [параметры и результат]({folder}/run.json), CSV в той же папке.")
    output = ROOT / "reports/demo-summary.md"
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
