@echo off
cd /d "%~dp0"

if not exist venv_api\Scripts\activate (
  echo [ERRO] Ambiente virtual venv_api nao encontrado.
  exit /b 1
)

call venv_api\Scripts\activate

echo ==========================================
echo   Scheduler Windows (Fallback)
echo   Preferencial: executar no WSL via run_scheduler.sh
echo ==========================================

python scheduler.py
pause
