@AGENTS.md

# Formwerk — Anweisungen für Claude Code

`AGENTS.md` oben ist die Hausordnung und gilt vollständig. Diese Datei ergänzt,
was nur Claude Code betrifft: Befehle, Werkzeuge, und die Stellen, an denen
meine globalen Vorgaben auf dieses Projekt nicht passen.

## Was dieses Projekt ist

Formwerk — eine Desktop-Anwendung in **Python 3.11 mit PySide6**, kein
Avalonia/.NET. Die globale `~/.claude/CLAUDE.md` beschreibt meine Haltung und
Arbeitsweise; ihre Stack-Angaben (Avalonia, `dotnet build`, MVVM, RESX,
Android) gelten hier **nicht**. Wo sie sich widersprechen, gewinnt für den
Stack diese Datei, für die Haltung die globale.

Die Unterlagen in ihrer Rangfolge:

| Datei | Beantwortet |
|---|---|
| `3d-agent-bauplan.md` | **Was** gebaut wird — die Spezifikation, §-Nummern sind verbindlich |
| `AGENTS.md` | **Wie** gearbeitet wird — 22 harte Regeln, jede mit Test |
| `ROADMAP.md` | **Was als Nächstes** — Arbeitsliste, unten die Funde der Durchsichten |
| `README.md` | Was der Nutzer sieht |

Bei Widerspruch gilt der Bauplan. Eine Aussage ohne §-Beleg ist eine Vermutung.

## Sprache — die wichtigste Falle

Dieses Projekt dreht meine globale Vorgabe für den Code um:

- **Code, Docstrings, Kommentare: Englisch.** `tests/test_language_rules.py`
  lehnt deutsche Stämme in Bezeichnern ab. Ein deutscher Docstring in `app/`
  fällt nicht auf, ist aber trotzdem falsch.
- **Oberflächentexte: über `tr()`**, deutsch und englisch in
  `app/i18n/locales/`. Keine feste Zeichenkette in der Oberfläche.
- **Doku, Bauplan, Roadmap, Commit-Meldungen: Deutsch**, mit echten Umlauten.
- **Gespräch mit Robert: Deutsch.**

<!-- Die Tabelle in AGENTS.md nennt Commits englisch, die gelebte Praxis ist
     deutsch (alle bisherigen Commits). Hier steht die gelebte Praxis. -->

Commit-Meldungen dieses Projekts sind eine Aussage, kein Etikett: „Hohle
Querschnitte kamen als nichts zurück", nicht „fix: section". Diesen Ton halten.

## Befehle

Alles läuft über die virtuelle Umgebung, nie über das System-Python:

```
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m ruff format --check .
.venv\Scripts\python.exe -m mypy
```

Diese vier sind zusammen das Tor: rot heißt nicht fertig. `/pruefen` fasst sie
zusammen. Weiteres:

```
.venv\Scripts\python.exe -m pytest tests/test_parts.py -q      # eine Datei
.venv\Scripts\python.exe -m pytest -q -m "not slow"             # ohne die langen
.venv\Scripts\python.exe -m pytest -q -m performance            # Budget §31
.venv\Scripts\python.exe -m app.ui.app                          # Anwendung starten
.venv\Scripts\python.exe -m app.cli.main --help                 # Kommandozeile
.venv\Scripts\python.exe tools/run_agent_suite.py               # kostet Geld, kein Testlauf
```

Erstaufbau: `python -m venv .venv` und
`.venv\Scripts\python.exe -m pip install -e ".[dev,geom,ui,agent,brep]"`.

Qt-Tests brauchen kein Bild: `QT_QPA_PLATFORM=offscreen` setzt
`tests/conftest.py` selbst. Dieselbe Datei biegt die Nutzerverzeichnisse in
einen Temp-Ordner um (§38) — läuft ein Test außerhalb der Suite, fehlt ihm das.

## Karte

```
app/core/     kein Qt, keine Dialoge — Kommunikation nur über OpContext
  registry/   Register der Ops, Parameterschema, Flächenzuordnung
  scene/      Szene, Stapel, Auswertung, Projektdatei, Parameter, Passungen
  geom/       Ops gegen manifold3d/trimesh, Boolesche Rückfallkette, Reparatur
  brep/       zweiter Kern (OpenCASCADE) — optional, meldet sich ab wenn er fehlt
  slice/      Schichtanalyse, nie ein G-Code-Slicer
  ingest/     Einlesen, Einheitenerkennung, 3MF als Baugruppe
  perceive/   Feature-Erkennung, stabile IDs, Analysekarten, Steckbrief
  knowledge/  Profile, Normteile, Regelsammlung, Kalibrierung, parts/ Bausteine
  agent/      LLM-Schicht: Sitzung, Vorschlag als eine Transaktion, Prüfungen
  backends/   LLM, OpenSCAD, Mesh-Erzeuger — alles extern, alles abschaltbar
  export/     STL/3MF/STEP, Plattenbelegung
app/ui/       PySide6 — darf core benutzen, nie umgekehrt
app/cli/      Kommandozeile auf core
tests/        eine Datei je Testart, data/ ist der Referenzkorpus
tools/        Hilfsprogramme, nicht Teil der Anwendung
3D Drucker/   physische Druckprojekte, eigene CLAUDE.md, nicht im Repository
```

Gebietsregeln liegen in `.claude/rules/` und laden sich selbst, sobald ich
Dateien des Gebiets anfasse — Kerntrennung, Operationen, Bausteine, Oberfläche,
Agentenschicht, Tests, Druckteile.

## Werkzeuge in diesem Projekt

Agents (`.claude/agents/`) — die globalen .NET-Agents passen hier nicht:

| Agent | Wofür |
|---|---|
| `formwerk-review` | Review gegen die 22 harten Regeln, vor jedem Commit |
| `formwerk-op` | Neue oder geänderte Operation, ganze Checkliste |
| `formwerk-baustein` | Bausteinbibliothek und Normteile |
| `formwerk-geometrie` | Netz kaputt, Boolesche Op scheitert, Rückfallkette |
| `formwerk-oberflaeche` | PySide6-Fenster, Viewport, Dialoge |
| `formwerk-agentenschicht` | LLM-Schicht, Regelsammlung, Agenten-Suite |
| `formwerk-schicht` | Schichtanalyse, Druckbarkeit, Leistungsbudget |
| `formwerk-sprache` | Übersetzungen, Sprachregelung, tr() |
| `formwerk-auslieferung` | Paket, Lizenzen, CI, Veröffentlichung |
| `konzept` | Soll das überhaupt so gebaut werden? Bauplan-Treue |
| `bedienlogik` | Interaktionsentwurf gegen §2 und §19 |
| `oberflaechentexte` | Texte, Fehler als Vorschlag, Ton |
| `druck-berater` | Material, Drucker, Druckeinstellungen |
| `druckteil-konstrukteur` | Parametrische Teile für den Ordner `3D Drucker/` |

Befehle (`.claude/skills/`): `/pruefen`, `/regelcheck`, `/neue-op`,
`/neuer-baustein`, `/bauplan`, `/roadmap`, `/liefern`, `/neues-druckteil`.

## Arbeitsweise hier

- **Kleine Schritte, Suite nach jedem.** Ein Schritt, der sie rot lässt, wird
  nicht auf den nächsten gestapelt.
- **Bei Geometrie zuerst der Test.** Erwartete Kennzahlen gegen eine Datei aus
  `tests/data/`, dann die Umsetzung.
- **Kein Revert.** Vorwärts fixen, keine Datei-Resets.
- **Selbstständig committen**, in logischen Einheiten, mit `Co-Authored-By`.
- **Nie stillschweigend raten.** Mehrdeutigkeit hält an und fragt (Regel 21).
- **Nach Pattern-Änderungen**: die betroffene Regel in `.claude/rules/`
  nachziehen, `ROADMAP.md` fortschreiben, Bauplan nur mit Ansage ändern.
