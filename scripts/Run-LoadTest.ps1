[CmdletBinding()]
param(
    [ValidateSet('baseline','mixed','slow','errors','cpu')][string]$Scenario = 'mixed',
    [ValidateRange(1,100)][int]$Users = 10,
    [ValidateRange(1,20)][int]$SpawnRate = 2,
    [ValidatePattern('^\d+(s|m)$')][string]$Duration = '60s',
    [ValidateRange(0,2000)][int]$DelayMs = 250,
    [ValidateRange(0,1)][double]$ErrorRate = 0.15,
    [ValidateRange(1000,1000000)][int]$CpuIterations = 100000
)
. "$PSScriptRoot\Common.ps1"
Assert-LabEnvironment
$durationSeconds = [int]$Duration.Substring(0,$Duration.Length-1)
if ($Duration.EndsWith('m')) { $durationSeconds *= 60 }
if ($durationSeconds -lt 10 -or $durationSeconds -gt 300) { throw 'Duration must be between 10s and 5m.' }
Assert-PortAvailable 9647
Wait-LabUrl 'http://127.0.0.1:5000/health' 3
$stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
$output = Join-Path $script:LabRoot "reports\$stamp-$Scenario"
New-Item -ItemType Directory -Path $output -Force | Out-Null
$prefix = Join-Path $output 'stats'
$envNames = @('PYTHONUTF8','LAB_METRICS_ENABLED','LAB_METRICS_HOST','LAB_METRICS_PORT','LAB_SCENARIO','LAB_DELAY_MS','LAB_ERROR_RATE','LAB_CPU_ITERATIONS')
$savedEnvironment = @{}
foreach ($name in $envNames) { $savedEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, 'Process') }
$record = $null
$started = (Get-Date).ToUniversalTime().ToString('o')
try {
    $env:PYTHONUTF8 = '1'
    $env:LAB_METRICS_ENABLED = '1'
    $env:LAB_METRICS_HOST = '127.0.0.1'
    $env:LAB_METRICS_PORT = '9647'
    $env:LAB_SCENARIO = $Scenario
    $env:LAB_DELAY_MS = $DelayMs.ToString()
    $env:LAB_ERROR_RATE = $ErrorRate.ToString([Globalization.CultureInfo]::InvariantCulture)
    $env:LAB_CPU_ITERATIONS = $CpuIterations.ToString()
    $arguments = @('-m','locust','-f','load_tests/locustfile.py','--host','http://127.0.0.1:5000','--lab-scenario',$Scenario,'--headless','-u',"$Users",'-r',"$SpawnRate",'-t',$Duration,'--stop-timeout','5','--csv',$prefix,'--csv-full-history','--html',(Join-Path $output 'report.html'),'--only-summary','--exit-code-on-error','0')
    $process = $null
    $record = Start-LabProcess 'loadtest' $script:Python $arguments -ProcessHandle ([ref]$process)
    Save-LabState (@(Get-LabState) + @($record))
    Write-Host "Running $Scenario : $Users users, $Duration. Reports: $output"
    if (-not $process.WaitForExit(($durationSeconds + 40) * 1000)) { throw 'Locust exceeded the run timeout.' }
    if ($process.ExitCode -ne 0) { throw "Locust exited with code $($process.ExitCode). See .runtime/logs/loadtest.err.log" }
    $total = Import-Csv -LiteralPath "${prefix}_stats.csv" | Where-Object { $_.Name -eq 'Aggregated' } | Select-Object -First 1
    if (-not $total -or [int]$total.'Request Count' -eq 0) { throw 'No requests were recorded. See Locust logs.' }
    $summary = [ordered]@{
        scenario=$Scenario; target='http://127.0.0.1:5000'; started_utc=$started; finished_utc=(Get-Date).ToUniversalTime().ToString('o')
        users=$Users; spawn_rate=$SpawnRate; duration=$Duration; delay_ms=$DelayMs; error_rate=$ErrorRate; cpu_iterations=$CpuIterations
        requests=[int]$total.'Request Count'; failures=[int]$total.'Failure Count'
        mean_ms=[double]::Parse($total.'Average Response Time',[Globalization.CultureInfo]::InvariantCulture)
        p95_ms=[double]::Parse($total.'95%',[Globalization.CultureInfo]::InvariantCulture)
        rps=[double]::Parse($total.'Requests/s',[Globalization.CultureInfo]::InvariantCulture)
        note='HTTP failures are recorded as data; this teaching wrapper does not apply production SLO gates.'
    }
    $summary | ConvertTo-Json | Set-Content (Join-Path $output 'run.json') -Encoding UTF8
    # Preserve individual logs because the next run reuses the process name.
    Copy-Item (Join-Path $script:Runtime 'logs\loadtest.out.log') (Join-Path $output 'locust.out.log')
    Copy-Item (Join-Path $script:Runtime 'logs\loadtest.err.log') (Join-Path $output 'locust.err.log')
    Write-Host "Requests=$($summary.requests), failures=$($summary.failures), p95=$($summary.p95_ms)ms, RPS=$([Math]::Round($summary.rps,2))"
    return [PSCustomObject]@{folder=$output;summary=[PSCustomObject]$summary}
} finally {
    if ($record -and (Test-LabProcess $record)) { Stop-Process -Id $record.pid -ErrorAction SilentlyContinue }
    if ($record) { Save-LabState @(Get-LabState | Where-Object { $_.pid -ne $record.pid }) }
    foreach ($name in $envNames) { [Environment]::SetEnvironmentVariable($name, $savedEnvironment[$name], 'Process') }
}
