# Контракт метрик Locust

Встроенный exporter запускается событием Locust `init` на `127.0.0.1:9646/metrics`. В Docker адрес прослушивания меняется на `0.0.0.0` внутри контейнера; порт exporter доступен только в сети Compose и не публикуется на Windows. Экспортёр читает `environment.stats` при каждом сборе Prometheus и не опрашивает Web UI. Работает один процесс Locust; распределённые `--master` / `--worker` в этом учебном экспортёре отключены.

| Метрика | Тип | Смысл |
|---|---|---|
| `locust_users` | gauge | Активные виртуальные пользователи |
| `locust_running` | gauge | 1 при spawning/running, иначе 0 |
| `locust_exporter_up` | gauge | 1, когда сборщик доступен |
| `locust_requests_total{method,name}` | counter | Все запросы с последнего сброса статистики |
| `locust_failures_total{method,name}` | counter | Ошибки с последнего сброса |
| `locust_current_rps{method,name}` | gauge | Сглаженная текущая скорость по данным Locust |
| `locust_response_time_avg_seconds{method,name}` | gauge | Среднее время ответа за текущий тест, секунды |
| `locust_response_time_seconds{method,name,quantile}` | gauge | Перцентили 0.5, 0.95, 0.99 за текущий тест, секунды |
| `locust_last_request_timestamp_seconds{method,name}` | gauge | Время последнего запроса Unix seconds |

Каждому маршруту соответствует постоянный `name`, например `/api/slow`; параметры запросов в метку не попадают. Отдельная суммарная строка имеет `method="ALL",name="Aggregated"`. При суммировании выбирайте либо её, либо строки `method!="ALL"`, иначе запросы посчитаются дважды.

До первых запросов счётчики равны нулю, а значения времени ответа отсутствуют: exporter не подставляет вымышленные нулевые перцентили. Сброс статистики Locust обнуляет счётчики. В PromQL `rate()` и `increase()` учитывают такие сбросы; их результат за короткое окно может быть дробным из-за экстраполяции.

Примеры запросов:

```promql
# RPS по завершённым запросам, без двойного подсчёта агрегата
sum(rate(locust_requests_total{method!="ALL"}[1m]))

# Доля ошибок, проценты; при отсутствии запросов значение может отсутствовать
100 * sum(rate(locust_failures_total{method!="ALL"}[1m]))
  / sum(rate(locust_requests_total{method!="ALL"}[1m]))

# p95 текущего теста по версии клиента
locust_response_time_seconds{method="ALL",name="Aggregated",quantile="0.95"}
```

Настройки: `LAB_METRICS_HOST`, `LAB_METRICS_PORT` (9646 по умолчанию), `LAB_METRICS_ENABLED=0` для отключения экспортёра. UI Locust остаётся работоспособным при отключённом exporter. Отдельный native headless-процесс использует порт 9647, чтобы не занять порт работающего UI. Prometheus собирает его как `locust_headless` только пока идёт тест. Остановленный headless exporter будет DOWN между тестами — это ожидаемо.

Docker-служба `loadtest` использует порт 9646 внутри собственного контейнера и тот же job `locust_headless`. Запускайте её через `docker compose run --rm --use-aliases loadtest`: флаг `--use-aliases` нужен, чтобы Prometheus разрешил имя временного контейнера `loadtest`.

В исходниках exporter эти единицы и метки проверяются тестами `load_tests/test_metrics.py`. Изменяя контракт, одновременно обновите JSON дашборда и тесты.

Источники: [Locust custom arguments и event hooks](https://docs.locust.io/en/stable/extending-locust.html), [настройки CSV/HTML отчётов](https://docs.locust.io/en/stable/configuration.html), [исходник статистики Locust](https://github.com/locustio/locust/blob/master/locust/stats.py).
