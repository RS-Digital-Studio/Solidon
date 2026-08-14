@AGENTS.md

# Solidon — Anweisungen für Claude Code

`AGENTS.md` oben ist die Hausordnung und gilt vollständig. Diese Datei ergänzt,
was nur Claude Code betrifft: Befehle, Werkzeuge, und die Stellen, an denen
meine globalen Vorgaben auf dieses Projekt nicht passen.

## Was dieses Projekt ist

Solidon — eine Desktop-Anwendung in **Python 3.13 mit PySide6**, kein
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

Die Sprachregelung steht verbindlich in `AGENTS.md`; hier die Kurzform:

- **Bezeichner, Dateinamen, Modulnamen: Englisch.**
  `tests/test_language_rules.py` lehnt deutsche Stämme in Bezeichnern ab.
- **Docstrings und Kommentare: Deutsch** — seit „Doku nachziehen" (b2e6e28),
  der Bestand ist vollständig nachgezogen. Neues wird deutsch geschrieben.
- **Oberflächentexte: über `tr()`**, deutsche Quelle und je ein Katalog in
  `app/i18n/locales/` — derzeit `en`, `es`, `fr`, `it`, `pt`. Keine feste
  Zeichenkette in der Oberfläche.
- **Doku, Bauplan, Roadmap, Commit-Meldungen: Deutsch**, mit echten Umlauten.
- **Gespräch mit Robert: Deutsch.**

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
.venv\Scripts\python.exe tools/make_figures.py                  # Bildschirmfotos fürs Handbuch
.venv\Scripts\python.exe tools/make_manual.py                   # Handbuch als Website und PDF
.venv\Scripts\python.exe tools/make_icon.py                     # Anwendungssymbol rastern: ICO und Website-Favicon
.venv\Scripts\python.exe tools/make_installer.py                # Setup-Datei aus dist/Solidon, braucht Inno Setup 6
```

Die letzten beiden laufen **nicht** offscreen und dürfen es nicht: unter
`QT_QPA_PLATFORM=offscreen` hat Qt auf dieser Maschine null Schriftfamilien,
und jede Beschriftung in jedem Bild wird zu einem leeren Kästchen. Wer ein
erzeugtes Bild prüft, prüft es aus demselben Grund unter der echten Plattform.

Erstaufbau: `python -m venv .venv` und
`.venv\Scripts\python.exe -m pip install -c constraints.txt -e ".[dev,geom,ui,agent,brep]"`.
Das `-c` ist kein Beiwerk: ohne es zieht ein frischer Klon andere Fassungen als
die CI, und die Suite wird rot, ohne dass eine Zeile Code sich geändert hat.

Qt-Tests brauchen kein Bild: `QT_QPA_PLATFORM=offscreen` setzt
`tests/conftest.py` selbst. Dieselbe Datei biegt die Nutzerverzeichnisse in
einen Temp-Ordner um (§38) — läuft ein Test außerhalb der Suite, fehlt ihm das.

## Karte

```
app/core/     kein Qt, keine Dialoge — Kommunikation nur über OpContext
  registry/   Register der Ops, Parameterschema, Flächenzuordnung
  scene/      Szene, Stapel, Auswertung, Projektdatei, Parameter, Passungen
  geom/       Ops gegen manifold3d/trimesh, Boolesche Rückfallkette, Reparatur
  sketch/     Skizzen mit Zwangsbedingungen (§30.1): Löser, Profile, Ebenen
  brep/       zweiter Kern (OpenCASCADE) — optional, meldet sich ab wenn er fehlt
  slice/      Schichtanalyse und G-Code lesen, nie G-Code schreiben;
              advise.py schließt aus der Geometrie auf Druckeinstellungen
  ingest/     Einlesen, Einheitenerkennung, 3MF als Baugruppe
  perceive/   Feature-Erkennung, stabile IDs, Analysekarten, Steckbrief
  knowledge/  Profile, Normteile, Regelsammlung, Kalibrierung, parts/ Bausteine,
              print_settings.py löst Stufe + Material + Drucker auf
  agent/      LLM-Schicht: Sitzung, Vorschlag als eine Transaktion, Prüfungen
  backends/   LLM, OpenSCAD, Mesh-Erzeuger — alles extern, alles abschaltbar
  export/     STL/3MF/STEP, Plattenbelegung, Übergabe an den Slicer
              (handover.py ruft ihn, slicer_keys.py übersetzt die Namen)
  activation/ Freischaltung: Testlauf, Schlüssel, Demo-Frist (store.py)
  manual.py   Handbuch: geschriebene Seiten, Referenz aus dem Register erzeugt
  figures.py  Abbildungskatalog — gezeichnet, gerendert, aufgenommen
  drawing.py  SVG ohne Qt: Maßlinien, Schemata, Netzprojektion
  markup.py   Markdown → HTML, nur die selbst erzeugte Teilmenge
app/ui/       PySide6 — darf core benutzen, nie umgekehrt
app/images/   Bildschirmfotos fürs Handbuch, je Sprache ein Ordner
app/cli/      Kommandozeile auf core
tests/        eine Datei je Testart, data/ ist der Referenzkorpus
tools/        Hilfsprogramme, nicht Teil der Anwendung
website/      öffentliche Seiten; handbuch.html und en/manual.html erzeugt
              tools/make_manual.py, alles andere ist von Hand gepflegt
3D Drucker/   physische Druckprojekte, eigene CLAUDE.md, nicht im Repository
```

Gebietsregeln liegen in `.claude/rules/` und laden sich selbst, sobald ich
Dateien des Gebiets anfasse — Kerntrennung, Operationen, Bausteine, Oberfläche,
Agentenschicht, Tests, Druckteile.

## Werkzeuge in diesem Projekt

Agents (`.claude/agents/`) — die globalen .NET-Agents passen hier nicht.
Befehle liegen in `.claude/skills/`. Beide Listen stehen bereits in der
Auflistung der Sitzung; hier stünden sie ein drittes Mal.

Wie die Sitzung selbst bedienbar sein soll, steht in
`.claude/bedienkonzept-ueberblick.md` (die Sitzung als Ganzes) und
`.claude/bedienkonzept-funktionen.md` (sechzehn Funktionen einzeln). Entwurf,
noch nicht Praxis — was daraus umgesetzt ist, steht dort in der Schlusstabelle.

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
