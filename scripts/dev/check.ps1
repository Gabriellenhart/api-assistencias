$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $ProjectRoot

if (Test-Path ".venv") {
    & ".\.venv\Scripts\Activate.ps1"
}

if (-not $env:FLASK_ENV) { $env:FLASK_ENV = "development" }
if (-not $env:SECRET_KEY) { $env:SECRET_KEY = "dev-secret" }
if (-not $env:JWT_SECRET_KEY) { $env:JWT_SECRET_KEY = "dev-jwt-secret" }
if (-not $env:DEV_DATABASE_URI) { $env:DEV_DATABASE_URI = "postgresql://assistencias_dev:assistencias_dev@localhost:5432/assistencias_dev" }
if (-not $env:TEST_DATABASE_URI) { $env:TEST_DATABASE_URI = "postgresql://assistencias_test:assistencias_test@localhost:5432/assistencias_test" }
if (-not $env:CORS_ORIGINS) { $env:CORS_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000" }

Write-Host "[dev check] importando aplicacao"
python -c "from api import create_app; app = create_app('development'); print(app.name)"

Write-Host "[dev check] validando sintaxe"
python -m compileall api scraper scripts config.py run.py

Write-Host "[dev check] rodando pytest"
python -m pytest

Write-Host "[dev check] verificando migrations"
$PreviousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$DbCurrentOutput = & python -m flask --app run.py db current 2>&1
$ErrorActionPreference = $PreviousErrorActionPreference
if ($LASTEXITCODE -ne 0) {
    Write-Host "[dev check] aviso: nao foi possivel consultar flask db current. Verifique PostgreSQL e .env."
} else {
    $DbCurrentOutput
}

Write-Host "[dev check] OK"
