$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $ProjectRoot

Write-Host "[dev bootstrap] criando .venv se necessario"
if (-not (Test-Path ".venv")) {
    python -m venv .venv
}

& ".\.venv\Scripts\Activate.ps1"

Write-Host "[dev bootstrap] atualizando pip e instalando requirements.txt"
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "[dev bootstrap] .env criado. Revise as variaveis de banco antes de rodar migrations."
} else {
    Write-Host "[dev bootstrap] .env ja existe; nao sera sobrescrito"
}

Write-Host "[dev bootstrap] validacao rapida"
& ".\scripts\dev\check.ps1"

Write-Host "[dev bootstrap] Para aplicar migrations, confirme o PostgreSQL local e rode:"
Write-Host "  .\.venv\Scripts\python.exe -m flask --app run.py db upgrade"
Write-Host "[dev bootstrap] Para criar admin inicial:"
Write-Host "  .\.venv\Scripts\python.exe -m flask --app run.py create-admin"
