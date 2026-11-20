# Отчёты запусков

Каждый запуск JMeter создаёт папку `jmeter-…` с результатами `results.jtl`,
журналом `jmeter.log` и отчётом `html/index.html`.

Для дополнительной практики Locust `scripts/Run-LoadTest.ps1` сохраняет CSV,
HTML и `run.json`. `scripts/Run-Demo.ps1` выполняет baseline, slow и errors,
затем создаёт `comparison.json` и `demo-summary.md`.

Сгенерированные файлы исключены из Git. Результаты характеризуют конкретный
компьютер и параметры прогона.
