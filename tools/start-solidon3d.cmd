@echo off
rem Startet Solidon per Doppelklick aus dem Arbeitsbaum.
cd /d "%~dp0.."
if not exist ".venv\Scripts\python.exe" (
    echo Die virtuelle Umgebung fehlt. Einmalig anlegen:
    echo   python -m venv .venv
    echo   .venv\Scripts\python.exe tools\check_env.py --install
    pause
    exit /b 1
)
start "" ".venv\Scripts\pythonw.exe" -m app.ui.app
