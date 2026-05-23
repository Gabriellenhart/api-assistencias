$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $ProjectRoot

if (-not (Test-Path ".venv")) {
    throw ".venv nao encontrado. Rode .\scripts\dev\bootstrap.ps1 primeiro."
}

& ".\.venv\Scripts\Activate.ps1"

$env:FLASK_APP = if ($env:FLASK_APP) { $env:FLASK_APP } else { "run.py" }
$env:FLASK_ENV = if ($env:FLASK_ENV) { $env:FLASK_ENV } else { "development" }
$env:FLASK_DEBUG = if ($env:FLASK_DEBUG) { $env:FLASK_DEBUG } else { "1" }

$HostName = if ($env:FLASK_RUN_HOST) { $env:FLASK_RUN_HOST } else { "127.0.0.1" }
$Port = if ($env:FLASK_RUN_PORT) { $env:FLASK_RUN_PORT } else { "5000" }

Write-Host "[dev run] iniciando API em http://${HostName}:${Port}"
python -m flask run --host $HostName --port $Port --debug
