[CmdletBinding()]
param([switch]$OpenBrowser)
. "$PSScriptRoot\Common.ps1"
Assert-LabEnvironment
$records = @(Get-LabState | Where-Object { Test-LabProcess $_ })
if ($records.Count -gt 0) {
    $requiredNames = @('flask','locust','prometheus','grafana')
    $runningServices = @($records | Where-Object { $_.name -in $requiredNames } | Select-Object -ExpandProperty name -Unique)
    if ($runningServices.Count -eq 4) {
        & "$PSScriptRoot\Status-Lab.ps1"
        if ($OpenBrowser) { Start-Process 'http://127.0.0.1:5000/' }
        return
    }
    throw 'Some lab processes are already running. Run Stop-Lab.ps1, then Start-Lab.ps1.'
}
foreach ($port in @(5000,8089,9646,9090,3000)) { Assert-PortAvailable $port }
$prometheus = Get-ChildItem (Join-Path $script:Runtime 'prometheus') -Filter prometheus.exe -Recurse | Select-Object -First 1
$grafana = Get-ChildItem (Join-Path $script:Runtime 'grafana') -Filter grafana.exe -Recurse | Select-Object -First 1
if (-not $prometheus -or -not $grafana) { throw 'Run Setup-Windows.ps1 first.' }
$grafanaHome = Split-Path -Parent (Split-Path -Parent $grafana.FullName)
$nativeProvisioning = Join-Path $script:Runtime 'provisioning'
New-Item -ItemType Directory -Path "$nativeProvisioning\datasources","$nativeProvisioning\dashboards" -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $script:Runtime 'grafana-data'),(Join-Path $script:Runtime 'grafana-plugins') -Force | Out-Null
$rootForward = $script:LabRoot.Replace('\','/')
$runtimeForward = $script:Runtime.Replace('\','/')
@"
apiVersion: 1
datasources:
  - name: Prometheus
    uid: prometheus
    type: prometheus
    access: proxy
    url: http://127.0.0.1:9090
    isDefault: true
    editable: true
    jsonData:
      timeInterval: 5s
"@ | Set-Content "$nativeProvisioning\datasources\prometheus.yml" -Encoding UTF8
@"
apiVersion: 1
providers:
  - name: Flask Load Lab
    orgId: 1
    folder: Flask Load Lab
    type: file
    disableDeletion: false
    updateIntervalSeconds: 10
    allowUiUpdates: false
    options:
      path: '$rootForward/observability/grafana/dashboards'
"@ | Set-Content "$nativeProvisioning\dashboards\lab.yml" -Encoding UTF8
@"
global:
  scrape_interval: 5s
  evaluation_interval: 5s
scrape_configs:
  - job_name: flask
    static_configs:
      - targets: ['127.0.0.1:5000']
  - job_name: locust
    static_configs:
      - targets: ['127.0.0.1:9646']
  - job_name: locust_headless
    static_configs:
      - targets: ['127.0.0.1:9647']
  - job_name: prometheus
    static_configs:
      - targets: ['127.0.0.1:9090']
"@ | Set-Content (Join-Path $script:Runtime 'prometheus.yml') -Encoding UTF8
$credentialPath = Join-Path $script:Runtime 'credentials.json'
if (-not (Test-Path -LiteralPath $credentialPath)) {
    @{user='admin';password=([guid]::NewGuid().ToString('N'))} | ConvertTo-Json | Set-Content $credentialPath -Encoding UTF8
}
$credentials = Get-Content $credentialPath -Raw | ConvertFrom-Json
@"
[paths]
data = $runtimeForward/grafana-data
logs = $runtimeForward/logs
plugins = $runtimeForward/grafana-plugins
provisioning = $runtimeForward/provisioning
[server]
http_addr = 127.0.0.1
http_port = 3000
root_url = http://127.0.0.1:3000/
[security]
admin_user = $($credentials.user)
admin_password = $($credentials.password)
[users]
allow_sign_up = false
[auth.anonymous]
enabled = true
org_role = Viewer
[analytics]
reporting_enabled = false
check_for_updates = false
check_for_plugin_updates = false
[plugins]
preinstall_disabled = true
[dashboards]
default_home_dashboard_path = $rootForward/observability/grafana/dashboards/flask-load-lab.json
"@ | Set-Content (Join-Path $script:Runtime 'grafana.ini') -Encoding UTF8
$envNames = @('PYTHONUTF8','LAB_METRICS_HOST','LAB_METRICS_PORT','LAB_TARGET_HOST','LAB_METRICS_ENABLED')
$savedEnvironment = @{}
foreach ($name in $envNames) { $savedEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, 'Process') }
try {
    $env:PYTHONUTF8 = '1'
    $env:LAB_METRICS_HOST = '127.0.0.1'
    $env:LAB_METRICS_PORT = '9646'
    $env:LAB_METRICS_ENABLED = '1'
    $env:LAB_TARGET_HOST = 'http://127.0.0.1:5000'
    $records += Start-LabProcess 'flask' $script:Python @('-m','app','--host','127.0.0.1','--port','5000','--threads','8')
    Save-LabState $records
    Wait-LabUrl 'http://127.0.0.1:5000/health'
    $records += Start-LabProcess 'locust' $script:Python @('-m','locust','-f','load_tests/locustfile.py','--host','http://127.0.0.1:5000','--web-host','127.0.0.1','--web-port','8089')
    Save-LabState $records
    $records += Start-LabProcess 'prometheus' $prometheus.FullName @(('--config.file=' + (Join-Path $script:Runtime 'prometheus.yml')),('--storage.tsdb.path=' + (Join-Path $script:Runtime 'prometheus-data')),'--storage.tsdb.retention.time=7d','--storage.tsdb.retention.size=1GB','--web.listen-address=127.0.0.1:9090')
    Save-LabState $records
    $records += Start-LabProcess 'grafana' $grafana.FullName @('server','--homepath',$grafanaHome,'--config',(Join-Path $script:Runtime 'grafana.ini'))
    Save-LabState $records
    Wait-LabUrl 'http://127.0.0.1:8089/'
    Wait-LabUrl 'http://127.0.0.1:9646/metrics'
    Wait-LabUrl 'http://127.0.0.1:9090/-/ready'
    Wait-LabUrl 'http://127.0.0.1:3000/api/health' 120
    Wait-LabUrl 'http://127.0.0.1:3000/api/dashboards/uid/flask-load-lab'
    Wait-LabUrl 'http://127.0.0.1:3000/api/dashboards/uid/load-generator'
    $scrapeDeadline = (Get-Date).AddSeconds(20)
    do {
        $targets = (Invoke-RestMethod 'http://127.0.0.1:9090/api/v1/targets' -TimeoutSec 3).data.activeTargets
        $upJobs = @($targets | Where-Object { $_.health -eq 'up' } | ForEach-Object { $_.labels.job })
        $scrapesReady = ('flask' -in $upJobs) -and ('locust' -in $upJobs)
        if (-not $scrapesReady) { Start-Sleep -Milliseconds 500 }
    } while (-not $scrapesReady -and (Get-Date) -lt $scrapeDeadline)
    if (-not $scrapesReady) { throw 'Flask and Locust scrape targets did not become UP.' }
} catch {
    Write-Warning 'Startup did not finish; stopping processes started by this lab.'
    & "$PSScriptRoot\Stop-Lab.ps1"
    throw
} finally {
    foreach ($name in $envNames) { [Environment]::SetEnvironmentVariable($name, $savedEnvironment[$name], 'Process') }
}
& "$PSScriptRoot\Status-Lab.ps1"
if ($OpenBrowser) { Start-Process 'http://127.0.0.1:5000/' }
