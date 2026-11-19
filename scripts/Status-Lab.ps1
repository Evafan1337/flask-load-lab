[CmdletBinding()]
param()
. "$PSScriptRoot\Common.ps1"
foreach ($service in @(
    @{name='Flask';url='http://127.0.0.1:5000/health'},
    @{name='Locust';url='http://127.0.0.1:8089/'},
    @{name='Prometheus';url='http://127.0.0.1:9090/-/ready'},
    @{name='Grafana';url='http://127.0.0.1:3000/api/health'}
)) {
    try {
        $response = Invoke-WebRequest -Uri $service.url -UseBasicParsing -TimeoutSec 3
        Write-Host "$($service.name): HTTP $($response.StatusCode)"
    } catch { Write-Host "$($service.name): unavailable" }
}
Write-Host 'App:        http://127.0.0.1:5000/'
Write-Host 'Load UI:    http://127.0.0.1:8089/'
Write-Host 'Flask:      http://127.0.0.1:3000/d/flask-load-lab'
Write-Host 'Locust:     http://127.0.0.1:3000/d/load-generator'
Write-Host 'Admin credentials (optional): .runtime/credentials.json'
