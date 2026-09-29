#!/usr/bin/env bash
# Startet Solidon aus dem Arbeitsbaum der Gesamtprüfung, damit Robert den Stand
# des Zweigs ausprobieren kann. Gebunden ohne die Kerne 8 bis 11 (RM-272):
#   cmd //c "start /b /wait /affinity F0FF bash app_starten.sh"
cd "/f/3D Druck.gesamtfix" || exit 9
export PYTHONUTF8=1
"/f/3D Druck/.venv/Scripts/python.exe" -m app.ui.app
echo "APP-EXIT=$?"
