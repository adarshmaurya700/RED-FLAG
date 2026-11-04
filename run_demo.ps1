param([switch]$Native, [ValidateRange(1024, 65535)][int]$WebPort = 3000)
$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
Set-Location -LiteralPath $projectRoot
if (-not $Native) {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        Write-Host 'Docker Desktop is not installed. Install it from https://www.docker.com/products/docker-desktop/ or use .\run_demo.ps1 -Native.'
        exit 1
    }
    & docker compose up --build
    exit $LASTEXITCODE
}
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) { throw 'Install uv from https://docs.astral.sh/uv/ and run this command again.' }
if (-not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) { throw 'Install Node.js 24 LTS from https://nodejs.org/.' }
Push-Location -LiteralPath (Join-Path $projectRoot 'backend')
try {
    if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
        & uv venv --python 3.12 .venv
        if ($LASTEXITCODE -ne 0) { throw 'Python environment setup failed.' }
    }
    & uv pip install --python .venv\Scripts\python.exe -r requirements.lock
    if ($LASTEXITCODE -ne 0) { throw 'Backend dependency installation failed.' }
} finally { Pop-Location }
& npm.cmd ci --no-audit --no-fund
if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
& (Join-Path $projectRoot 'backend\.venv\Scripts\python.exe') (Join-Path $projectRoot 'scripts\native_demo.py') --port $WebPort
exit $LASTEXITCODE
