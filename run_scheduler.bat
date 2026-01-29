@echo off
cd /d "%~dp0"
call venv_api\Scripts\activate
echo ==========================================
echo   Iniciando Scheduler - Sync Usinas/Clientes
echo   (Roda a cada 1 hora)
echo ==========================================
python scheduler.py
pause
