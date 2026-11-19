# Flask Load Lab

Готовая учебная лаборатория нагрузочного тестирования: **Flask + Waitress → Locust → Prometheus → Grafana**. Интерфейс приложения, два дашборда и практикум — на русском. Ручное создание источников данных и импорт панелей не нужны.

## Открыть на этом компьютере

| Что открыть | Адрес |
|---|---|
| Учебное приложение | [127.0.0.1:5000](http://127.0.0.1:5000/) |
| Управление нагрузкой Locust | [127.0.0.1:8089](http://127.0.0.1:8089/) |
| Grafana: сервер Flask | [Дашборд Flask](http://127.0.0.1:3000/d/flask-load-lab) |
| Grafana: результаты Locust | [Дашборд Locust](http://127.0.0.1:3000/d/load-generator) |
| Сбор метрик | [Prometheus targets](http://127.0.0.1:9090/targets) |

Grafana доступна для просмотра без входа. Для необязательного редактирования администратором локальные реквизиты находятся в `.runtime/credentials.json` (в Git не попадают). Сохранённые результаты и ссылки на демонстрацию — в [DEMO-RESULTS.md](DEMO-RESULTS.md).

## Запуск в Windows

Откройте PowerShell в папке проекта. Здесь окружение уже установлено:

```powershell
.\scripts\Start-Lab.ps1
# Повторный вызов показывает состояние уже работающего стенда.
.\scripts\Status-Lab.ps1
```

На новом компьютере сначала выполните:

```powershell
.\scripts\Setup-Windows.ps1
.\scripts\Start-Lab.ps1 -OpenBrowser
```

Установщик загружает закреплённые версии uv, CPython, Prometheus и Grafana с официальных сайтов, сверяет SHA256 и размещает всё **внутри проекта**. Системный Python, PATH и службы Windows менять не нужно. Первое скачивание — около 650 МБ; распакованному окружению требуется несколько ГБ. Нужны Windows x64, доступ в интернет, `curl.exe` и `tar.exe` (входят в современные Windows).

Если PowerShell запрещает выполнение скрипта, можно запустить его в отдельном процессе без изменения постоянной политики:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\Start-Lab.ps1
```

На этой машине у uv возникала ошибка подключения из-за настроенного системного SOCKS-прокси. Установка прошла с `Setup-Windows.ps1 -DirectNetwork`: флаг временно задаёт `NO_PROXY=*` только для загрузки Python-зависимостей, затем восстанавливает значение. Используйте его, если требуется прямое соединение вместо вашего прокси.

Остановить стенд:

```powershell
.\scripts\Stop-Lab.ps1
```

Остановка сохраняет историю Prometheus и Grafana. Скрипт останавливает процессы только из этой папки, сверяя PID и время создания. Автозапуск после перезагрузки не установлен: снова выполните `Start-Lab.ps1`. Не переносите папку с работающими процессами; после переноса исходников создайте окружение заново.

## Первый урок

1. Откройте приложение, затем Locust и оба дашборда Grafana.
2. В Locust: Host `http://127.0.0.1:5000`, Users `10`, Spawn rate `2`, `lab-scenario` = `baseline`. Запустите на минуту и остановите.
3. Повторите со сценарием `slow`, затем `errors`. В Grafana сравните RPS, p95 и долю ошибок.
4. Выполните задания [практикума на 50–60 минут](docs/lesson.md). Для преподавателя есть [памятка и ожидаемые наблюдения](docs/instructor.md).

Для автоматического запуска с HTML и CSV:

```powershell
.\scripts\Run-LoadTest.ps1 -Scenario baseline -Users 10 -Duration 60s
.\scripts\Run-LoadTest.ps1 -Scenario slow -DelayMs 250 -Users 10 -Duration 60s
.\scripts\Run-LoadTest.ps1 -Scenario errors -ErrorRate 0.15 -Users 10 -Duration 60s
# Все три последовательно + comparison.json:
.\scripts\Run-Demo.ps1
```

Каждый запуск сохраняет `report.html`, CSV, параметры и сводку `run.json` в `reports/<UTC-время>-<сценарий>/`. Обёртка принимает 1–100 пользователей, 10 секунд — 5 минут и фиксированный localhost. Ошибки HTTP записываются в отчёт; обёртка не применяет пороги SLO и не считает намеренные 503 сбоем инфраструктуры. При запуске Locust напрямую его обычный ненулевой код при ошибках сохраняется.

В интерактивном Locust профиль выбирается перед каждым тестом. Один активный генератор за раз даёт понятное сравнение. Автоматический прогон использует exporter на 9647, интерактивный — 9646. На дашборде Locust выберите `locust_headless`, `locust` или All. Неактивный headless exporter в Prometheus имеет `up=0` — это ожидаемо.

## Учебные сценарии

| Сценарий | Маршрут | Что наблюдать |
|---|---|---|
| `baseline` | `/api/fast` | Базовое время ответа и RPS |
| `slow` | `/api/slow?delay_ms=250` | Задержка без обязательного роста CPU; очередь при нехватке потоков |
| `errors` | `/api/flaky?error_rate=0.15` | Примерно 15% HTTP 503 на достаточно большой выборке |
| `cpu` | `/api/cpu?iterations=100000` | Вычисления на запрос; зависимость от компьютера |
| `mixed` | Смесь 8:2:1:1 | Почему нужно смотреть каждый endpoint отдельно |

Flask обслуживается одним процессом Waitress с 8 потоками, debug выключен. Параметры запросов ограничены. Метрики не включают query-параметры и произвольные URL в labels. `/metrics` не засоряет статистику пользовательских запросов.

Flask histogram измеряет время внутри обработчика. Locust измеряет время со стороны клиента, включая ожидание в очереди. Серверный p95 оценивается по buckets в скользящем окне; клиентский p95 считается по статистике текущего теста. Это разные измерения. Подробнее — [контракт метрик](docs/locust-metrics.md) и [разбор дашбордов](observability/sources.md).

## Docker Compose

Вариант для компьютера с запущенным Docker Engine/Desktop:

```powershell
docker compose up --build -d
docker compose ps
docker compose logs -f
# Остановить, сохранив volumes:
docker compose down
```

Перед запуском Docker остановите нативный стенд: порты совпадают. Адреса страниц те же. Grafana provisioned автоматически, данные сохраняются в именованных volumes. Пароль администратора для Docker задаётся в `.env`, пример — `.env.example`; просмотр работает без входа. Все опубликованные порты привязаны к 127.0.0.1.

Автоматический Docker-прогон (службы стенда должны работать):

```powershell
docker compose run --rm --use-aliases loadtest
# Свои параметры, все аргументы после имени сервиса заменяют command:
docker compose run --rm --use-aliases loadtest --headless --lab-scenario slow -u 10 -r 2 -t 60s --csv /srv/flask-load-lab/reports/docker-slow --html /srv/flask-load-lab/reports/docker-slow.html
```

`--use-aliases` позволяет Prometheus найти временный генератор по имени `loadtest`. Для Linux задайте `LOCAL_UID`/`LOCAL_GID` по результатам `id -u`/`id -g`, чтобы отчёты в bind mount принадлежали вашему пользователю. По умолчанию — 1000:1000. Одновременные headless-прогоны в этой учебной конфигурации не предусмотрены.

Docker Compose проверен на корректность конфигурации. В этой сессии Docker Engine не работал; контейнерная сборка и запуск здесь не проверены. Демонстрация выполнена нативно в Windows.

## Проверка и разработка

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts/check_lab.py
docker compose config --quiet
.\.runtime\prometheus\prometheus-3.16.0.windows-amd64\promtool.exe check config observability/prometheus.yml
```

Основные версии: Python 3.13.18, Flask 3.1.3, Waitress 3.0.2, Locust 2.47.0, prometheus-client 0.26.0, Prometheus 3.16.0, Grafana 13.3.1. Прямые зависимости — `requirements*.txt`, общая фиксация транзитивных версий Windows/Linux — `requirements-lock.txt`. Обновляйте lock осознанно после проверки:

```powershell
.\.runtime\uv\uv.exe pip compile --universal --python-version 3.13 requirements-dev.txt requirements-load.txt -o requirements-lock.txt
```

Файлы: `app/` — приложение; `load_tests/` — сценарии и exporter; `observability/` — Prometheus, Grafana и источники примеров; `scripts/` — запуск и отчёты; `docs/` — материалы урока; `.github/workflows/checks.yml` — будущие проверки в GitHub Actions.

В исходниках подготовлены собственные дашборды с современными встроенными панелями. В каталоге Grafana найдены и разобраны примеры [Locust 11985](https://grafana.com/grafana/dashboards/11985-locust-test/), [Flask 16111](https://grafana.com/grafana/dashboards/16111-flask-monitoring/) и [Flask exporter 17629](https://grafana.com/grafana/dashboards/17629-prometheus-flask-exporter-dashboard/). Они используют разные exporters, поэтому их запросы адаптированы к явному контракту нашей лаборатории; сторонние JSON целиком не копируются.

## Если что-то не открывается

- Проверьте `Status-Lab.ps1`, затем `.runtime/logs/<сервис>.err.log` и `.out.log`.
- При занятом порте скрипт завершится с указанием номера; он не останавливает чужие службы.
- При первом старте Grafana выполняет миграции и может запускаться дольше минуты.
- Для графиков нужны хотя бы два scrape и реальная нагрузка. Установите диапазон последних 15 минут и обновление 5 секунд либо используйте фиксированные ссылки из `DEMO-RESULTS.md`.
- После выключения компьютера выполните `Start-Lab.ps1`; данные сохраняются 7 дней с ограничением Prometheus 1 ГБ.

## Подготовка GitHub

Проект подготовлен как локальный Git-репозиторий; публикация и подключение к вашему аккаунту не выполнялись. `.runtime/`, `.venv/`, `.env`, реквизиты Grafana и сгенерированные отчёты исключены из Git. Источники и учебные материалы входят в архив рядом с проектом.

Когда решите публиковать, создайте пустой репозиторий в своём аккаунте и выполните команды с его реальным URL:

```powershell
git remote add origin https://github.com/YOUR_ACCOUNT/flask-load-lab.git
git push -u origin main
```

Проект имеет лицензию MIT; сторонние установленные компоненты сохраняют свои лицензии.
