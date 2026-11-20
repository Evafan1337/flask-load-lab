$ErrorActionPreference = 'Stop'
$script:LabRoot = Split-Path -Parent $PSScriptRoot
$script:Runtime = Join-Path $script:LabRoot '.runtime'
$script:Python = Join-Path $script:LabRoot '.venv\Scripts\python.exe'

function Assert-LabEnvironment {
    if (-not (Test-Path -LiteralPath $script:Python)) {
        throw 'Run scripts/Setup-Windows.ps1 first.'
    }
}

function Get-LabState {
    $path = Join-Path $script:Runtime 'processes.json'
    if (Test-Path -LiteralPath $path) {
        $records = Get-Content -LiteralPath $path -Raw | ConvertFrom-Json
        foreach ($record in $records) {
            $record
        }
    }
}

function Test-LabProcess($Record) {
    $process = Get-Process -Id $Record.pid -ErrorAction SilentlyContinue
    if (-not $process) { return $false }
    try {
        return ($process.StartTime.ToUniversalTime().Ticks.ToString() -eq [string]$Record.startedTicks) -and
            $process.Path.StartsWith(($script:LabRoot.TrimEnd('\') + '\'), [StringComparison]::OrdinalIgnoreCase)
    } catch { return $false }
}

function Save-LabState($Records) {
    New-Item -ItemType Directory -Path $script:Runtime -Force | Out-Null
    ConvertTo-Json -InputObject @($Records) -Depth 5 | Set-Content -LiteralPath (Join-Path $script:Runtime 'processes.json') -Encoding UTF8
}

function Assert-PortAvailable([int]$Port) {
    $listener = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
    if ($listener) { throw "Port $Port is already in use. Stop the other server, or run scripts/Stop-Lab.ps1 for this lab." }
}

function Start-LabProcess([string]$Name, [string]$Executable, [string[]]$Arguments, [ref]$ProcessHandle) {
    New-Item -ItemType Directory -Path (Join-Path $script:Runtime 'logs') -Force | Out-Null
    # Start-Process joins its arguments; quote each argument to preserve paths with spaces.
    $quoted = @($Arguments | ForEach-Object { '"' + $_.Replace('"', '\"') + '"' })
    $options = @{
        FilePath = $Executable
        ArgumentList = $quoted
        WorkingDirectory = $script:LabRoot
        WindowStyle = 'Hidden'
        PassThru = $true
        RedirectStandardOutput = (Join-Path $script:Runtime "logs\$Name.out.log")
        RedirectStandardError = (Join-Path $script:Runtime "logs\$Name.err.log")
    }
    $process = Start-Process @options
    Start-Sleep -Milliseconds 250
    $process.Refresh()
    if ($process.HasExited) { throw "$Name exited. See .runtime/logs/$Name.err.log" }
    if ($null -ne $ProcessHandle) { $ProcessHandle.Value = $process }
    return [PSCustomObject]@{name=$Name; pid=$process.Id; startedTicks=$process.StartTime.ToUniversalTime().Ticks.ToString()}
}

function Wait-LabUrl([string]$Url, [int]$Seconds = 45) {
    $deadline = (Get-Date).AddSeconds($Seconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2
            if ($response.StatusCode -eq 200) { return }
        } catch { }
        Start-Sleep -Milliseconds 500
    }
    throw "Timed out waiting for $Url. See .runtime/logs."
}
