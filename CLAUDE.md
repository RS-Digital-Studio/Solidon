@AGENTS.md

# Solidon — Anweisungen für Claude Code

`AGENTS.md` oben ist die Hausordnung und gilt vollständig. Diese Datei ergänzt,
was nur Claude Code betrifft: Unterlagen, Befehle, Werkzeuge, Arbeitsweise.

## Was dieses Projekt ist

Solidon — eine Desktop-Anwendung in **Python (3.14 oder neuer) mit PySide6**.
Die Untergrenze steht in `pyproject.toml`; Arbeitsumgebung und CI verwenden
CPython 3.14.7.

| Datei | Beantwortet |
|---|---|
| `3d-agent-bauplan.md` | **Was** gebaut wird — die Spezifikation, §-Nummern sind verbindlich |
| `AGENTS.md` | **Wie** gearbeitet wird — 22 harte Regeln, jede mit Test |
| `ROADMAP.md` | **Was als Nächstes** — oben das Register der offenen Punkte |
| `ROADMAP-ARCHIV.md` | **Was schon versucht wurde** — Befunde und Nachweise |
| `konzepte/README.md` | **Warum** — Index der Konzepte und Durchsichten mit ihrem Stand |
| `README.md` | Was der Nutzer sieht |
| `<verzeichnis>/CLAUDE.md` | **Was wo liegt** — lädt, sobald eine Datei darin angefasst wird |
| `.claude/rules/*.md` | **Was einzuhalten ist** — lädt über `paths:` |

Bei Widerspruch gilt der Bauplan; eine Aussage ohne §-Beleg ist eine Vermutung.
**Offene Arbeit steht im Register von `ROADMAP.md` und nirgends sonst.** Die
Statustabellen der Konzepte altern — ein „offen" dort wird am Code geprüft und,
wenn es stimmt, ins Register übernommen.

Gespräch mit Robert auf Deutsch. Commit-Meldungen sind eine Aussage, kein
Etikett: „Hohle Querschnitte kamen als nichts zurück", nicht „fix: section".

## Befehle

Alles über die virtuelle Umgebung, nie über das System-Python. Beide Editoren
setzen `PYTHONUTF8=1` für ihre Unterprozesse.

**Je Schritt** die betroffenen Tests — der Importgraph wählt sie aus:

```
.venv\Scripts\python.exe tools/affected_tests.py app/core/units.py --run   # Dateien nennen
.venv\Scripts\python.exe tools/affected_tests.py --run                     # alle ungestageten Änderungen
```

Ohne Dateiliste nimmt es alle ungestageten Änderungen im Baum, auch fremde.
Meldet es „das ist die Suite" (`i18n`, `types.py`, `errors.py`, `log.py`),
gleich das Tor fahren.

**Vor dem Commit** das Entwicklungstor, zusammengefasst in `/pruefen`:

```
bash .claude/scripts/suite-getrennt.sh
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m ruff format --check .
.venv\Scripts\python.exe -m mypy
```

**Fenstertests und Leistungsprüfungen laufen ausschließlich beim Release** —
auch nicht als betroffene Teilmenge. `pytest -q` am Stück kommt nicht durch
(nativer Abriss nach rund 700 Fenstern); das Tor trennt die Fenstergruppe ab:

```
bash .claude/scripts/suite-getrennt.sh --release
.venv\Scripts\python.exe -m pytest -q -m performance   # Budget §31, Referenzmaschine
```

**Das Ergebnis ist der Exit-Code**, direkt nach dem Befehl gelesen, dazu die
Zahl gelaufener gegen gesammelter Tests. Jeder Nichtnull-Ausgang ist rot, auch
nach „passed". Wie die Fenstergruppe abgetrennt wird und wie ein Lauf gelesen
wird, steht in `/pruefen` und `.claude/rules/tests.md`.

Weiteres:

```
.venv\Scripts\python.exe -m app.ui.app                    # Anwendung starten
.venv\Scripts\python.exe -m app.cli.main --help           # Kommandozeile
.venv\Scripts\python.exe tools/run_agent_suite.py         # kostet Geld, kein Testlauf
```

Was **nicht Code** erzeugt — Bildschirmfotos, Handbuch, Website-Bilder, SEO,
Symbol, Pakete, Download-Kasten, ComfyUI, Upload — und Umgebung und Version
über `check_env.py`: `/erzeugen`.

Qt-Tests brauchen kein Bild: `tests/conftest.py` setzt
`QT_QPA_PLATFORM=offscreen` und biegt die Nutzerverzeichnisse in einen
Temp-Ordner (§38) — außerhalb der Suite fehlt beides.

## Karte

```
app/core/     kein Qt, keine Dialoge — Kommunikation nur über OpContext
  registry/   Register der Ops, Parameterschema, Flächenzuordnung
  scene/      Szene, Stapel, Auswertung, Projektdatei, Parameter, Passungen
  geom/       Ops gegen manifold3d/trimesh, Boolesche Rückfallkette, Reparatur
  sketch/     Skizzen mit Zwangsbedingungen (§30.1): Löser, Profile, Ebenen
  brep/       zweiter Kern (OpenCASCADE) — optional, meldet sich ab, wenn er fehlt
  slice/      Schichtanalyse und G-Code lesen, nie G-Code schreiben;
              advise.py schließt aus der Geometrie auf Druckeinstellungen
  ingest/     Einlesen, Einheitenerkennung, 3MF als Baugruppe
  perceive/   Feature-Erkennung, stabile IDs, Analysekarten, Steckbrief
  knowledge/  Profile, Normteile, Regelsammlung, Kalibrierung, parts/ Bausteine;
              print_settings.py löst Stufe + Material + Drucker auf
  agent/      LLM-Schicht: Sitzung, Vorschlag als eine Transaktion, Prüfungen
  backends/   LLM und Mesh-Erzeuger — extern und abschaltbar; comfy_setup.py
              und data/comfyui/ (TripoSG, MIT) liegen im Kern, weil tools/
              nicht im Paket mitreist
  export/     STL/3MF/OBJ/PLY/GLB/STEP, Plattenbelegung, Slicer-Übergabe
  activation/ Freischaltung: Kaufcode, Geräteidentität, Zertifikat, Fristen
  updates.py  Update fragen, holen, prüfen — gestartet nur auf Klick
  report.py   Fehlerbericht als Ordner — schreibt, sendet nie
  support.py  der einzige Weg hinaus: Rückmeldung an den Support, an einem Knopf
  manual.py · figures.py · drawing.py · markup.py   Handbuch, Abbildungen, SVG, Markdown
app/ui/       PySide6 — darf core benutzen, nie umgekehrt
app/images/   Bildschirmfotos fürs Handbuch, je Sprache ein Ordner
app/cli/      Kommandozeile auf core
tests/        eine Datei je Testart, data/ ist der Referenzkorpus
tools/        Hilfsprogramme, nicht Teil der Anwendung
website/      öffentliche Seiten; erzeugt wird, was die tools/make_*.py nennen,
              api/ gehört nach httpdocs/api/
changelog/    was im Update-Fenster steht, je Sprache eine Datei. Hier liegt
              bewusst keine CLAUDE.md: Test und make_download.py lesen jeden
              Dateinamen des Ordners als Sprache
3D Drucker/   physische Druckprojekte — eigenes Repository, hier in .gitignore
output/, tmp/ örtliche Prüfstände und Sicherungen, nicht versioniert
Releases/     lokale Pakete; nur die veröffentlichten Handbuch-PDFs versioniert
```

Jedes Verzeichnis mit Code trägt seine eigene Karte; `tests/test_directory_docs.py`
prüft, dass sie da ist und ihre §-Verweise treffen.

## Die Unterlagen-Pyramide

| | `<verzeichnis>/CLAUDE.md` | `.claude/rules/<gebiet>.md` |
|---|---|---|
| Frage | **Was liegt hier?** | **Was ist einzuhalten?** |
| Inhalt | Module, Datenfluss, Einstieg | Regeln, Verbote, Stolperfallen — je mit kurzem Grund |
| Lädt | beim Anfassen einer Datei im Verzeichnis | über `paths:` im Frontmatter |
| Ändert sich | wenn Module dazukommen oder umziehen | wenn eine Entscheidung fällt |

Keine wiederholt die andere; sie verweisen aufeinander. Ändert sich der Code,
ändert sich die Karte; ändert sich eine Entscheidung, ändert sich die Regel.
**Beide bleiben knapp**, denn eine Sitzung liest sie, bevor sie Code sieht:
Messprotokolle, Anlässe, Datumsangaben und Verläufe gehören in `konzepte/`,
`ROADMAP-ARCHIV.md` oder die Git-Historie. Was in `.claude/` liegt und was
davon ins Repository gehört, sagt `.claude/README.md`.

`ruff format` formatiert auch ```` ```python ````-Blöcke in Markdown — eine
Feldliste steht deshalb als Tabelle, nicht als Codeblock.

## Werkzeuge

- **Agenten und Skills** haben je eine Quelle: `.claude/agents/*.md` und
  `.claude/skills/`. `tools/sync_agents.py` erzeugt daraus die Codex-Seite
  (`.codex/agents/`, `.agents/skills/`) — nach jeder Änderung an einer Quelle
  ausführen; `tests/test_agent_mirror.py` prüft den Spiegel. Die erzeugten
  Dateien werden nie von Hand bearbeitet.
- **Hooks** teilen sich `.claude/hooks/solidon3d_hooks.py`; die Einstiege
  stehen in `.claude/settings.json` und `.codex/hooks.json`. Codex verlangt je
  Hook-Definition eine Freigabe über `/hooks`, nach jeder Änderung erneut.
  Testmarken sind Erinnerungen, kein Nachweis eines Tors.
- **`pyright-lsp`** gibt Sprachhilfe (Einrichtung je Rechner in `/erzeugen`);
  die verbindliche Typprüfung bleibt mypy.
- **`context7`** liefert Bibliotheksdoku, bei Claude als Plugin, bei Codex
  über `.codex/config.toml`. Gefragt wird nach Bibliothek und Fachfrage — nie
  mit Projektcode oder Zugangsdaten.

## Arbeitsweise hier

Kleine Schritte, Test zuerst bei Geometrie, kein Revert, nie stillschweigend
raten — das steht in `AGENTS.md`. Dazu:

- **Nach jedem abgeschlossenen Punkt committen und pushen**, sobald das Tor
  grün ist — in logischen Einheiten, nur die eigenen Pfade, mit
  `Co-Authored-By`. Zusammengeführt wird per Merge. `/liefern` bündelt das,
  wenn Robert es ansagt.
- **`.githooks/post-commit` pusht** jeden Commit, weil auf drei Maschinen
  gearbeitet wird. Er holt und rebasiert nicht — ist die Gegenstelle weiter,
  scheitert er und sagt es. `SOLIDON_KEIN_PUSH=1` hält einen Commit lokal,
  wenn Robert ausdrücklich „nicht pushen" sagt.
- **`.githooks/pre-commit`** fährt bei Änderungen an `app/` oder `tools/` die
  Bezeichnerprüfung und `tools/check_new_texts.py`; Befunde an Dateien dieses
  Commits halten ihn an. `SOLIDON_KEIN_TOR=1` schaltet ihn für einen Lauf ab.
  Beide Hooks laufen nur mit `core.hooksPath = .githooks` (`check_env`
  meldet es) und suchen ihren Interpreter am Hauptklon, auch aus einem Worktree.
- **Nach einer Muster- oder Entscheidungsänderung** die Regel in
  `.claude/rules/` nachziehen und `ROADMAP.md` fortschreiben; den Bauplan nur
  mit Ansage ändern.

## Erinnerungen

Sie liegen in `.claude/memory/` — **nur auf dieser Maschine** (`.gitignore`),
weil das Repository zu jedem Release öffentlich wird. Der Ort im Nutzerprofil
ist eine Verknüpfung darauf (`tools/link_memory.py`); fehlen sie nach einem
Pull, holt der Sitzungsstart den letzten versionierten Stand zurück.

- **Eine Datei je Thema.** Eine neue Erkenntnis kommt als Abschnitt in das
  passende Thema aus `MEMORY.md`; eine neue Datei nur für ein neues Thema. Der
  Schreib-Hook nennt einer neuen Datei die nächstliegenden Themen.
- Was jede Sitzung auf jedem Rechner braucht, gehört in eine Regel oder Karte —
  nicht in die Erinnerungen. Geheimnisse gehören in keines von beiden.
