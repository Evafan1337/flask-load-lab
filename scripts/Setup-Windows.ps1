[CmdletBinding()]
param([switch]$DirectNetwork)
. "$PSScriptRoot\Common.ps1"
if (-not [Environment]::Is64BitOperatingSystem) { throw 'Windows x64 is required.' }
$downloads = Join-Path $script:Runtime 'downloads'
New-Item -ItemType Directory -Path $downloads -Force | Out-Null

function Get-VerifiedFile([string]$Name, [string]$Url, [string]$Sha256) {
    $destination = Join-Path $downloads $Name
    if ((Test-Path -LiteralPath $destination) -and (Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash -eq $Sha256) { return $destination }
    Write-Host "Downloading $Name ..."
    $temporary = "$destination.partial"
    $lastError = $null
    for ($attempt = 1; $attempt -le 3; $attempt++) {
        try {
            if (Get-Command curl.exe -ErrorAction SilentlyContinue) {
                & curl.exe --location --fail --retry 2 --retry-all-errors --connect-timeout 15 --max-time 300 --silent --show-error --output $temporary $Url
                if ($LASTEXITCODE -ne 0) { throw "curl download failed for $Name" }
            } else {
                Invoke-WebRequest -Uri $Url -OutFile $temporary -UseBasicParsing -TimeoutSec 300
            }
            if ((Get-FileHash -LiteralPath $temporary -Algorithm SHA256).Hash -ne $Sha256) { throw "SHA256 mismatch for $Name" }
            Move-Item -LiteralPath $temporary -Destination $destination -Force
            return $destination
        } catch { $lastError = $_; Write-Warning "Download attempt $attempt failed: $($_.Exception.Message)" }
    }
    throw $lastError
}

$uvPath = Join-Path $script:Runtime 'uv\uv.exe'
if (-not (Test-Path -LiteralPath $uvPath)) {
    $file = Get-VerifiedFile 'uv.zip' 'https://github.com/astral-sh/uv/releases/download/0.13.9/uv-x86_64-pc-windows-msvc.zip' 'edd61f7f5728a56cc62455386661860bdfc7bab65872f39b0c25bdcc1d8e1beb'
    Expand-Archive -LiteralPath $file -DestinationPath (Join-Path $script:Runtime 'uv') -Force
}
$basePython = Join-Path $script:Runtime 'python\python\python.exe'
if (-not (Test-Path -LiteralPath $basePython)) {
    $file = Get-VerifiedFile 'python.tar.gz' 'https://github.com/astral-sh/python-build-standalone/releases/download/20261110/cpython-3.13.18%2B20261110-x86_64-pc-windows-msvc-install_only_stripped.tar.gz' '2e0fed09d48989f64c9305da9ff2d37a41c0d13ab2aa6283405b2b620dfbf805'
    New-Item -ItemType Directory -Path (Join-Path $script:Runtime 'python') -Force | Out-Null
    & tar -xzf $file -C (Join-Path $script:Runtime 'python')
    if ($LASTEXITCODE -ne 0) { throw 'Python extraction failed.' }
}
if (-not (Test-Path -LiteralPath $script:Python)) {
    & $uvPath venv --python $basePython (Join-Path $script:LabRoot '.venv')
    if ($LASTEXITCODE -ne 0) { throw 'Virtual environment creation failed.' }
}
$previousNoProxy = $env:NO_PROXY
try {
    if ($DirectNetwork) { $env:NO_PROXY = '*' }
    & $uvPath pip sync --python $script:Python (Join-Path $script:LabRoot 'requirements-lock.txt')
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed. If Windows proxy settings are broken, retry with -DirectNetwork.' }
} finally { $env:NO_PROXY = $previousNoProxy }
$prometheusExe = Get-ChildItem (Join-Path $script:Runtime 'prometheus') -Filter prometheus.exe -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $prometheusExe) {
    $file = Get-VerifiedFile 'prometheus.zip' 'https://github.com/prometheus/prometheus/releases/download/v3.16.0/prometheus-3.16.0.windows-amd64.zip' '89c03c2f24400fb58668440b6d7226f68564acda27d657e77acfbda42be32cb3'
    Expand-Archive -LiteralPath $file -DestinationPath (Join-Path $script:Runtime 'prometheus') -Force
}
# Grafana archive version, URL and hash are pinned in this manifest.
$grafanaManifest = Get-Content (Join-Path $PSScriptRoot 'grafana-release.json') -Raw | ConvertFrom-Json
$grafanaExe = Get-ChildItem (Join-Path $script:Runtime 'grafana') -Filter grafana.exe -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $grafanaExe) {
    $file = Get-VerifiedFile $grafanaManifest.file $grafanaManifest.url $grafanaManifest.sha256
    New-Item -ItemType Directory -Path (Join-Path $script:Runtime 'grafana') -Force | Out-Null
    if ($grafanaManifest.file.EndsWith('.zip')) {
        Expand-Archive -LiteralPath $file -DestinationPath (Join-Path $script:Runtime 'grafana') -Force
    } else {
        & tar -xzf $file -C (Join-Path $script:Runtime 'grafana')
        if ($LASTEXITCODE -ne 0) { throw 'Grafana extraction failed.' }
    }
}
Write-Host 'Setup complete. Run: .\scripts\Start-Lab.ps1'
