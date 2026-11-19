[CmdletBinding()]
param()
. "$PSScriptRoot\Common.ps1"
foreach ($record in @(Get-LabState)) {
    if (Test-LabProcess $record) {
        Stop-Process -Id $record.pid -ErrorAction SilentlyContinue
        Wait-Process -Id $record.pid -Timeout 10 -ErrorAction SilentlyContinue
        Write-Host "Stopped $($record.name) (PID $($record.pid))"
    }
}
Save-LabState @()
