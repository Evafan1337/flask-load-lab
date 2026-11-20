#!/bin/sh
set -eu

plan=${1:-smoke}
case "$plan" in
    smoke|load) ;;
    *) echo 'Usage: docker compose run --rm jmeter smoke|load [-JNAME=value ...]' >&2; exit 2 ;;
esac
if [ "$#" -gt 0 ]; then shift; fi

bounded_integer() {
    value=$1
    maximum=$2
    case "$value" in
        ''|*[!0-9]*) return 1 ;;
    esac
    [ "$value" -ge 1 ] 2>/dev/null && [ "$value" -le "$maximum" ] 2>/dev/null
}

if [ "$plan" = smoke ] && [ "$#" -gt 0 ]; then
    echo 'Smoke использует фиксированные запросы. Параметры принимает план load.' >&2
    exit 2
fi
for argument in "$@"; do
    case "$argument" in
        -JPATH=/api/*|-JMETHOD=GET|-JMETHOD=POST|-JBODY=*) ;;
        -JUSERS=*)
            bounded_integer "${argument#*=}" 50 || { echo 'USERS: от 1 до 50.' >&2; exit 2; }
            ;;
        -JDURATION=*)
            bounded_integer "${argument#*=}" 300 || { echo 'DURATION: от 1 до 300 секунд.' >&2; exit 2; }
            ;;
        *)
            echo 'План load принимает PATH (внутри /api/), METHOD (GET или POST), BODY, USERS и DURATION через -J.' >&2
            exit 2
            ;;
    esac
done

stamp=$(date -u +%Y%m%dT%H%M%SZ)
output=$(mktemp -d "/reports/jmeter-${plan}-${stamp}-XXXXXX")
jmeter -n -t "/plans/$plan.jmx" -JHOST=flask -JPORT=5000 \
    -l "$output/results.jtl" -j "$output/jmeter.log" \
    -e -o "$output/html" "$@"
test -s "$output/html/index.html" || { echo "Отчёт JMeter не создан. Журнал: $output/jmeter.log" >&2; exit 1; }
echo "HTML: reports/${output##*/}/html/index.html"

if [ "$plan" = smoke ]; then
    awk -F, '
        NR == 1 {
            for (i = 1; i <= NF; i++) {
                if ($i == "success") success = i
                if ($i == "responseCode") code = i
            }
            next
        }
        success && code && $success == "true" && $code == (NR == 7 ? "201" : "200") { passed++ }
        END { if (NR != 7 || passed != 6) exit 1 }
    ' "$output/results.jtl" || { echo 'Smoke: ожидались пять HTTP 200 и один HTTP 201 с корректными ответами.' >&2; exit 1; }
fi
