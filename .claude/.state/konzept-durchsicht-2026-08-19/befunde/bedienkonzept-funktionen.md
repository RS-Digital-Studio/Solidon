# Sondierung: .claude/bedienkonzept-funktionen.md

**Titel:** Bedienkonzepte je Funktion
**Stand laut Dokument:** Sitzung vom 31.07./01.08.2026, 21 Commits, mehrere hundert Werkzeugaufrufe (kein eigenes Stand-Datum, nur dieser Beleg-Zeitraum)
**Zweck:** Beschreibt sechzehn Funktionen der Arbeitssitzung einzeln (Wozu, Auslöser, Ablauf, Was schiefging, Regel) und leitet aus einer belegten Sitzung sechzehn Regeln für Werkzeuge, Einstellungen und Haltung ab.

**Alterung:** 4/5 — Das Dokument ist ein Sitzungsprotokoll mit harten Zahlen (21 Commits, 15 Agenten, 583/1627 Bausteine, 3 Minuten Testlauf, ein Gedächtniseintrag) und einer Mängelliste gegen den damaligen Stand von settings.json, Skills und Agenten. Jede dieser Zahlen und jeder Mangel kann durch eine einzige Änderung im Repository überholt sein — die Regeln selbst und die Beobachtungen zum Werkzeugverhalten altern langsamer, aber auch Claude Code ändert Meldungstexte und MCP-Verhalten.

## Gliederung

- Bedienkonzepte je Funktion
- Teil A — Was der Nutzer auslöst
- Teil B — Was der Agent auslöst
- Teil C — Was von selbst läuft
- Teil D — Die Werkzeuge der Arbeit
- Zusammenfassung: was daraus folgt

## Extern prüfbare Behauptungen (12)

- **[mittel/funktionsumfang] Claude Code (Anthropic) — Skills/Slash-Befehle** — Skill-Dateien besitzen ein Feld `argument-hint`, das Argumente an einen Slash-Befehl beschreibt  
  _Ort:_ A1, Abschnitt Regel (Z. 42-46)
- **[mittel/funktionsumfang] Claude Code (Anthropic) — Todo-/Task-Werkzeug** — Claude Code erinnert wiederholt mit dem Wortlaut „The task tools haven't been used recently"  
  _Ort:_ B1, Was schiefging (Z. 155-158)
- **[mittel/funktionsumfang] Claude Code (Anthropic) — PostToolUse-Hook** — Claude Code meldet „PostToolUse hook modified X after your edit (likely a formatter)"  
  _Ort:_ C1, Was schiefging (Z. 266-270)
- **[hoch/funktionsumfang] Claude Code (Anthropic) — Edit/Write-Werkzeug** — Claude Code meldet „the file had been modified on disk since you last read it" ohne den Verursacher zu nennen  
  _Ort:_ D1, Was schiefging + Regel (Z. 376-384)
- **[niedrig/funktionsumfang] Claude Code (Anthropic) — Bash-Werkzeug** — Hintergrundläufe sind über `run_in_background` verfügbar  
  _Ort:_ C3, Auslöser (Z. 309)
- **[hoch/funktionsumfang] Claude Code (Anthropic) — MCP-Anbindung** — MCP-Server melden Verbinden, Trennen, Wiederverbinden und Anmeldepflicht ungefragt und mehrfach pro Sitzung  
  _Ort:_ C4, Was schiefging (Z. 344-349) — trägt die als schwerwiegendste bezeichnete Regel
- **[niedrig/api] MCP-Server amplitude / asana / bigquery / pagerduty** — Es existieren MCP-Server namens amplitude, asana, bigquery, pagerduty in der Umgebung  
  _Ort:_ C4, Was schiefging (Z. 346-347)
- **[hoch/funktionsumfang] ruff (Astral) und mypy** — ruff und mypy lassen eine ungültige Escape-Sequenz durch  
  _Ort:_ B3, Was schiefging (Z. 205-208) — trägt die Gedächtnis-Regel
- **[mittel/funktionsumfang] ruff — Regeln F401, F821** — Der ruff-Hook fängt F401 und F821 beim Schreiben  
  _Ort:_ C1, Was schiefging (Z. 266-268)
- **[mittel/funktionsumfang] ruff format** — `ruff format` ändert Dateien nachträglich, wenn es als Hook läuft  
  _Ort:_ C1, Regel (Z. 272-276)
- **[hoch/funktionsumfang] CPython unter Windows / Codepage cp1252** — Windows-Konsolen-Ausgabe deutscher und chinesischer Zeichen scheitert mit UnicodeEncodeError aus cp1252; `PYTHONIOENCODING=utf-8` behebt es  
  _Ort:_ D2, Was schiefging + Regel (Z. 401-410)
- **[niedrig/funktionsumfang] Qt / PySide6** — Qt braucht `QT_QPA_PLATFORM=offscreen` für kopflose Testläufe  
  _Ort:_ D2, Regel (Z. 409-410)

## Intern prüfbare Behauptungen (14)

- **[mittel]** Die Belegsitzung umfasste 21 Commits  
  _Prüfen:_ git log --since=2026-07-31 --until=2026-08-02 --oneline | wc -l  
  _Ort:_ Vorspann (Z. 9), A2 (Z. 67), D4 (Z. 452)
- **[hoch]** `/pruefen` kann nur den vollen Lauf, keine Teilmenge — der argument-hint wird vom Ablauf nicht genutzt  
  _Prüfen:_ Datei .claude/skills/pruefen (SKILL.md) lesen: gibt es argument-hint und wird das Argument im Ablauf verwendet?  
  _Ort:_ A1, Was schiefging + Regel (Z. 36-46)
- **[hoch]** Es gibt fünfzehn definierte Subagenten, darunter `solidon3d-sprache`  
  _Prüfen:_ Dateien in .claude/agents/ zählen und Namen prüfen  
  _Ort:_ B4, Was schiefging (Z. 232-234)
- **[hoch]** Freigegeben in settings.json sind pytest, ruff, mypy, git diff|status|log|show — nicht sed -i, Heredocs, python - <<PY  
  _Prüfen:_ .claude/settings.json und settings.local.json auf permissions.allow prüfen  
  _Ort:_ A3, Was schiefging (Z. 98-101)
- **[mittel]** tests/ hat 583 englische Bausteine; insgesamt 1627 Bausteine in 142 Dateien  
  _Prüfen:_ Zählskript der Sitzung nachbauen (AST + Wortliste) oder gegen tests/test_language_rules.py prüfen; Dateizahl per Glob app/ tests/ tools/  
  _Ort:_ A2 (Z. 68-75), D3 (Z. 430)
- **[mittel]** Die Zahlenreihe der Übersetzung endete bei 0 (Bestand vollständig übersetzt)  
  _Prüfen:_ Zählskript erneut laufen lassen; CLAUDE.md/AGENTS.md bestätigen „vollständig nachgezogen"  
  _Ort:_ D3, Was schiefging (Z. 427-430)
- **[hoch]** Der volle Testlauf dauert drei Minuten  
  _Prüfen:_ Measure-Command { .venv\Scripts\python.exe -m pytest -q }  
  _Ort:_ C3, Was schiefging (Z. 320-322) — trägt die Zwei-Minuten-Regel
- **[mittel]** Im Gedächtnis steht genau ein Eintrag (parallele Sitzungen — nur eigene Pfade stagen)  
  _Prüfen:_ Gedächtnisverzeichnis unter .claude/ bzw. dem Memory-Ordner auflisten  
  _Ort:_ B3, Was schiefging (Z. 203-208)
- **[mittel]** `app/cli/main.py` enthält `_speak_utf8` als gelöste cp1252-Falle  
  _Prüfen:_ grep -n "_speak_utf8" app/cli/main.py  
  _Ort:_ D2, Was schiefging (Z. 403-405)
- **[hoch]** PYTHONIOENCODING=utf-8 fehlt in den Projekt-Einstellungen  
  _Prüfen:_ grep PYTHONIOENCODING .claude/settings.json .claude/settings.local.json  
  _Ort:_ D2, Regel (Z. 407-410)
- **[mittel]** Die Arbeitsliste ist für den Nutzer nur sichtbar, wenn sie angefasst wird; eine Sitzungsleiste (Überblick §3) existiert nicht  
  _Prüfen:_ .claude/bedienkonzept-ueberblick.md §3 und dessen Schlusstabelle zum Umsetzungsstand lesen  
  _Ort:_ B1, Was schiefging + Regel (Z. 157-163)
- **[niedrig]** Verweise auf Überblick §3, §4, §8 — Nummerierung des Überblicksdokuments  
  _Prüfen:_ Abschnittsnummern in .claude/bedienkonzept-ueberblick.md gegenprüfen  
  _Ort:_ B1 (Z. 163), B2 (Z. 175), D4 (Z. 446)
- **[hoch]** Schlusstabelle: zwölf von sechzehn Regeln brauchen kein neues Werkzeug, vier gehören ins Werkzeug — Umsetzungsstand implizit „noch nichts davon umgesetzt"  
  _Prüfen:_ Je Zeile prüfen: .claude/skills/ auf schmale Formen, settings.json auf Freigaben und PYTHONIOENCODING; CLAUDE.md nennt das Konzept ausdrücklich „Entwurf, noch nicht Praxis"  
  _Ort:_ Zusammenfassung, Tabelle + Schlussabsatz (Z. 466-488)
- **[mittel]** Innere Rechnung der Zusammenfassung: sieben Haltung + drei Dateien ergeben zehn, nicht die genannten zwölf  
  _Prüfen:_ Spalte „Wo umzusetzen"/„Aufwand" der Tabelle auszählen (keiner = 8, klein = 3, — = 4, mittel = 1)  
  _Ort:_ Zusammenfassung (Z. 485-486)