# Windows и дополнительная практика с Locust

Основной сценарий занятия использует [JMeter](lesson.md). Locust можно запустить для сравнения клиентских метрик магазина в реальном времени.

## Нативный запуск в Windows

Откройте PowerShell в корне проекта и выполните следующие команды.

```powershell
.\scripts\Setup-Windows.ps1
.\scripts\Start-Lab.ps1 -OpenBrowser
.\scripts\Status-Lab.ps1
```

Для установки нужны Windows x64, доступ в интернет, `curl.exe` и `tar.exe`. Скрипт сверяет SHA256 закреплённых архивов uv, CPython, Prometheus и Grafana и устанавливает инструменты в каталог проекта. Распакованное окружение требует несколько ГБ.

При ошибке политики выполнения запустите скрипт в отдельном процессе PowerShell. Этот режим действует во время запуска команды.

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\Setup-Windows.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\Start-Lab.ps1
```

При проблеме с SOCKS-прокси для загрузки Python-зависимостей запустите `Setup-Windows.ps1 -DirectNetwork`. Установщик восстановит переменную `NO_PROXY` после загрузки.

| Сервис | Адрес |
| --- | --- |
| Каталог и корзина | [Магазин](http://127.0.0.1:5000/) |
| Справка по API | [Документация](http://127.0.0.1:5000/docs) |
| Выбор сценария Locust | [Locust](http://127.0.0.1:8089/) |
| Серверные метрики | [Grafana магазина](http://127.0.0.1:3000/d/flask-load-lab) |
| Клиентские метрики | [Grafana Locust](http://127.0.0.1:3000/d/load-generator) |
| Состояние сбора | [Цели Prometheus](http://127.0.0.1:9090/targets) |

Просмотр Grafana доступен без входа. Реквизиты администратора хранятся в локальном файле `.runtime/credentials.json`. Повторный запуск `Start-Lab.ps1` показывает состояние работающего стенда. Остановка сохраняет историю метрик.

```powershell
.\scripts\Stop-Lab.ps1
```

## Сценарии магазина

| Сценарий | Запрос | Что измерять |
| --- | --- | --- |
| `baseline` | `GET /api/products` | RPS и задержку каталога |
| `slow` | `GET /api/products?delay_ms=250` | Задержку каталога и RPS при том же числе покупателей |
| `errors` | `POST /api/orders?error_rate=0.15` | Успешные 201 и ожидаемые 503 на демо-заказах |
| `cpu` | `GET /api/products/notebook?iterations=100000` | Задержку карточки и CPU процесса |
| `mixed` | Смесь сценариев с весами 8:2:1:1 | Вклад отдельных маршрутов в общие показатели |

В интерфейсе Locust выберите 10 пользователей, скорость запуска 2 пользователя в секунду и нужный `lab-scenario`. Цель для Windows — `http://127.0.0.1:5000`, для Docker — `http://flask:5000`. Детали экспериментов есть в [практикуме Locust](locust-lesson.md).

Для автоматического прогона на Windows воспользуйтесь сценариями PowerShell.

```powershell
.\scripts\Run-LoadTest.ps1 -Scenario baseline -Users 10 -Duration 60s
.\scripts\Run-LoadTest.ps1 -Scenario slow -DelayMs 250 -Users 10 -Duration 60s
.\scripts\Run-LoadTest.ps1 -Scenario errors -ErrorRate 0.15 -Users 10 -Duration 60s
.\scripts\Run-Demo.ps1
```

Каждый прогон сохраняет HTML, CSV и `run.json` в `reports/<UTC-время>-<сценарий>/`. `Run-Demo.ps1` повторяет три запуска подряд и составляет сводку. Скрипт принимает 1–100 пользователей и длительность от 10 секунд до 5 минут. Для профиля заказов смотрите на `failures` и HTTP-коды в отчёте, даже если команда завершилась успешно.

## Запуск Locust в Docker

Сначала остановите нативный стенд. Запустите профиль Locust вместе с магазином и мониторингом.

```sh
docker compose --profile locust up --build -d --wait
docker compose ps
docker compose run --rm --use-aliases loadtest
docker compose --profile locust down
```

Параметр `--use-aliases` позволяет Prometheus находить временный генератор по имени `loadtest`. В Linux можно выставить `LOCAL_UID` и `LOCAL_GID` в `.env` для записи отчёта от имени своего пользователя. Пример переменных есть в `.env.example`.

## Проверка и метрики

После запуска нативного стенда выполните проверки через PowerShell.

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts/check_lab.py --with-locust
```

В Prometheus выберите цель `locust` для браузерного генератора и `locust_headless` для отдельного запуска. Неактивный headless отображается как DOWN между тестами. Смотрите логи запуска в `.runtime/logs/`. Для сравнения выбирайте одинаковые временные интервалы и запускайте по одному генератору.

Flask обслуживает запросы через Waitress с восемью потоками. Flask измеряет время в приложении по гистограмме, Locust — со стороны клиента. [Контракт метрик Locust](locust-metrics.md) · [Обзор дашбордов](../observability/sources.md)
