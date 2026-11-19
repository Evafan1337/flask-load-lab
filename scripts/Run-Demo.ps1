[CmdletBinding()]
param([ValidateRange(1,30)][int]$Users = 10,[string]$Duration = '60s')
. "$PSScriptRoot\Common.ps1"
$runs = @()
foreach ($scenario in @('baseline','slow','errors')) {
    $result = & "$PSScriptRoot\Run-LoadTest.ps1" -Scenario $scenario -Users $Users -Duration $Duration
    $runs += $result
}
$path = Join-Path $script:LabRoot 'reports\comparison.json'
$runs | ConvertTo-Json -Depth 5 | Set-Content $path -Encoding UTF8
& $script:Python (Join-Path $PSScriptRoot 'summarize_demo.py')
if ($LASTEXITCODE -ne 0) { throw 'Could not summarize demo results.' }
Write-Host "Demo complete. Comparison: $path"
$runs | ForEach-Object { $_.summary } | Format-Table scenario,requests,failures,mean_ms,p95_ms,rps
