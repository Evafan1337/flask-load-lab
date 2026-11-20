#!/bin/sh
set -eu

plan=${1:-smoke}
case "$plan" in
    smoke|load) ;;
    *) echo 'Usage: docker compose run --rm jmeter smoke|load [-JNAME=value ...]' >&2; exit 2 ;;
esac
if [ "$#" -gt 0 ]; then shift; fi

stamp=$(date -u +%Y%m%dT%H%M%SZ)
output=$(mktemp -d "/reports/jmeter-${plan}-${stamp}-XXXXXX")
jmeter -n -t "/plans/$plan.jmx" -JHOST=flask -JPORT=5000 \
    -l "$output/results.jtl" -j "$output/jmeter.log" \
    -e -o "$output/html" "$@"
test -s "$output/html/index.html" || { echo "Отчёт JMeter не создан. Журнал: $output/jmeter.log" >&2; exit 1; }
echo "HTML: reports/${output##*/}/html/index.html"

if [ "$plan" = smoke ]; then
    awk -F, '
        NR == 1 { for (i = 1; i <= NF; i++) if ($i == "success") col = i; next }
        col && $col == "true" { passed++ }
        END { if (NR != 5 || passed != 4) exit 1 }
    ' "$output/results.jtl" || { echo 'Smoke: ожидались четыре успешных запроса.' >&2; exit 1; }
fi
