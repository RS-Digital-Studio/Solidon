@echo off
rem Startet Solidon aus dem Arbeitsverzeichnis heraus — zum Doppelklicken,
rem solange es noch keine gebaute Installationsdatei gibt (die kommt in P8).
cd /d "%~dp0.."
if not exist ".venv\Scripts\python.exe" (
    echo Die virtuelle Umgebung fehlt. Einmalig anlegen:
    echo   python -m venv .venv
    echo   .venv\Scripts\python.exe -m pip install -c constraints.txt -e ".[dev,geom,ui]"
    pause
    exit /b 1
)
start "" ".venv\Scripts\pythonw.exe" -m app.ui.app
