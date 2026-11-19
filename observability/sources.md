# Примеры дашбордов и принципы адаптации

Проверено 19 ноября 2026 года: страницы и метаданные получены напрямую по HTTPS с `grafana.com` (API каталога). Каталог может меняться. Все JSON в `grafana/dashboards/` написаны для этого проекта; чужие JSON не скопированы, сторонние панели не требуются.

## Найденные примеры из интернета

| Пример | Для чего полезен | Совместимость с лабораторией |
| --- | --- | --- |
| [Locust test, ID 11985](https://grafana.com/grafana/dashboards/11985-locust-test/) | Пользователи, RPS, failures, время ответа, ошибки по endpoint | Ожидает метрики `ContainerSolutions/locust_exporter`, содержит старые типы `graph`, `table-old`, `singlestat`. Прямой импорт не гарантирует заполнение панелей. В лаборатории установлен современный dashboard `02 · Locust` с аналогичными учебными показателями и нашим явным контрактом метрик. |
| [Flask Monitoring, ID 16111](https://grafana.com/grafana/dashboards/16111-flask-monitoring/) | RED: requests, errors, duration; разбор сервиса и endpoint | Это вариант через StatsD; ожидает `flask_request_status_total` и другое именование. В лаборатории метрики экспортируются прямо из Python без StatsD. |
| [Prometheus Flask exporter dashboard, ID 17629](https://grafana.com/grafana/dashboards/17629-prometheus-flask-exporter-dashboard/) | Простой старт для Flask и Prometheus | Ориентирован на другой exporter и старые панели. Лабораторный `01 · Flask` использует современные встроенные панели и наши route labels. |

Метаданные можно проверить по адресам `https://grafana.com/api/dashboards/11985`, `https://grafana.com/api/dashboards/16111`, `https://grafana.com/api/dashboards/17629`. Название/показатель найденного dashboard не гарантируют совместимость с любыми метриками: всегда сравнивайте PromQL, labels и единицы измерения.

## Что развёрнуто локально

- [01 · Flask — нагрузка и качество](http://127.0.0.1:3000/d/flask-load-lab): серверная RED-панель, p50/p95/p99, ошибки 5xx, активные запросы, CPU и память.
- [02 · Locust — пользователи и результаты](http://127.0.0.1:3000/d/load-generator): пользователи, состав нагрузки, RPS, failures и клиентские процентили.

Дашборды автоматически загружаются из JSON. Источник данных имеет стабильный UID `prometheus`; ручной импорт и выбор datasource не нужны. Время показано в часовом поясе браузера. Начальный диапазон — последние 15 минут, обновление — каждые 5 секунд. На dashboard Locust фильтр «Генератор» позволяет выбрать `locust` (интерактивное окно), `locust_headless` (автоматический прогон) или All. При All процентили остаются отдельными линиями по генератору: их нельзя корректно складывать или усреднять. Опциональный headless-сервис имеет `up=0`, пока не запущен.

## Официальная документация для объяснения ученику

- [Grafana: provisioning](https://grafana.com/docs/grafana/latest/administration/provisioning/) — автоматическая настройка datasource и dashboard.
- [Grafana: Prometheus query editor и `$__rate_interval`](https://grafana.com/docs/grafana/latest/datasources/prometheus/query-editor/) — почему окно rate должно учитывать интервал scrape.
- [Prometheus: histograms and summaries](https://prometheus.io/docs/practices/histograms/) — buckets, `histogram_quantile` и погрешность оценки процентилей.
- [Prometheus: `rate` и `histogram_quantile`](https://prometheus.io/docs/prometheus/latest/querying/functions/) — сначала rate счётчиков, затем агрегация и вычисление quantile.
- [Locust: writing a locustfile](https://docs.locust.io/en/stable/writing-a-locustfile.html) — виртуальные пользователи, задачи и think time.

## Как читать различия

1. Flask измеряет обработку внутри сервера. Locust видит клиентское время, включая сеть и ожидание свободного соединения. В очереди Waitress запрос может ещё не попасть в обработчик Flask.
2. Серверный p95 — оценка по histogram за скользящее окно `rate`. Клиентский p95 в этой лаборатории — gauge из накопленной статистики текущего теста Locust. Их окна и метод оценки различаются.
3. HTTP 5xx и Locust failures описывают разные вещи. Locust также учитывает сетевые ошибки, HTTP 4xx и проваленные пользовательские проверки.
4. При отсутствии трафика throughput равен нулю, а latency не определена. Нулевую долю ошибок нельзя воспринимать как выполненный SLO без запросов.
5. CPU процесса Flask: 100% соответствует одному логическому ядру. В Docker и при нативном запуске ограничения ресурсов могут отличаться.
6. У aggregate Locust (`method="ALL", name="Aggregated"`) те же запросы уже суммированы. Панели RPS и failures исключают его, чтобы не считать каждый запрос дважды.

Изменения, сохранённые в интерфейсе Grafana, могут быть перезаписаны очередной загрузкой файлов provisioning. Для воспроизводимого урока меняйте JSON проекта или экспортируйте свою копию dashboard.
