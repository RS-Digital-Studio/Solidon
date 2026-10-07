@AGENTS.md

# Solidon — Unterlagen, Befehle, Karte

`AGENTS.md` oben ist die Hausordnung und gilt vollständig. Diese Datei ergänzt
sie um Unterlagen, Befehle, Karte, Werkzeuge und Arbeitsweise. Sie gilt für
Claude Code und Codex gleich: Claude Code lädt `AGENTS.md` über die erste
Zeile, Codex liest diese Datei nach `AGENTS.md`, „Paketstruktur“.

## Was dieses Projekt ist

Solidon — eine Desktop-Anwendung in **Python (3.14 oder neuer) mit PySide6**.
Die Untergrenze steht in `pyproject.toml`; die CI und damit jedes Paket
verwenden CPython 3.14.8, die Arbeitsplätze noch 3.14.7 (RM-468).

| Datei | Beantwortet |
|---|---|
| `3d-agent-bauplan.md` | **Was** gebaut wird — die Spezifikation, §-Nummern sind verbindlich |
| `AGENTS.md` | **Wie** gearbeitet wird — 22 harte Regeln und wer sie prüft |
| `ROADMAP.md` | **Was als Nächstes** — oben das Register der offenen Punkte |
| `ROADMAP-ARCHIV.md` | **Was schon versucht wurde** — Befunde und Nachweise |
| `konzepte/README.md` | **Warum** — Index der Konzepte und Durchsichten mit ihrem Stand |
| `README.md` | Was der Nutzer sieht |
| `<verzeichnis>/CLAUDE.md` | **Was wo liegt** — lädt, sobald eine Datei darin angefasst wird |
| `.claude/rules/*.md` | **Was einzuhalten ist** — lädt über `paths:` |

Eine Aussage ohne §-Beleg ist eine Vermutung.
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
.venv\Scripts\python.exe tools/affected_tests.py --run                     # alle Änderungen gegen HEAD
```

Ohne Dateiliste nimmt es alle Änderungen gegenüber HEAD — gestaged,
ungestaged und neu, auch fremde.
Meldet es „das ist die Suite" (`i18n`, `types.py`, `errors.py`, `log.py`),
gleich das Tor fahren.

**Vor dem Commit** das Entwicklungstor, zusammengefasst in `/pruefen`:

```
bash .claude/scripts/suite-getrennt.sh
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m ruff format --check .
.venv\Scripts\python.exe -m mypy
```

**Fenster-, Renderer- und Leistungsprüfungen nur beim Release** (`AGENTS.md`,
„Arbeitsweise“). `pytest -q` am Stück kommt nicht durch (nativer Abriss im
Fensterteil); das Tor trennt Fenster und Renderer ab:

```
bash .claude/scripts/suite-getrennt.sh --release
.venv\Scripts\python.exe -m pytest -q -m performance   # Budget §31, Referenzmaschine
```

**Das Ergebnis ist der Exit-Code**, direkt nach dem Befehl gelesen, dazu die
Zahl gelaufener gegen gesammelter Tests. Jeder Nichtnull-Ausgang ist rot, auch
nach „passed". Wie Fenster und Renderer abgetrennt werden und wie ein Lauf gelesen
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
app/core/     kopfloser Kern: kein Qt, keine Dialoge, Kommunikation nur über
              OpContext — Unterpakete und Module in app/core/CLAUDE.md
app/ui/       PySide6 — darf core benutzen, nie umgekehrt
app/cli/      Kommandozeile auf core
app/i18n/     tr() ohne Qt und die Sprachkataloge (locales/)
app/examples/ die zwölf Beispielprojekte, erzeugt von tools/make_examples.py
app/images/   Bildschirmfotos fürs Handbuch, je Sprache ein Ordner
tests/        eine Datei je Testart, data/ ist der Referenzkorpus
tools/        Hilfsprogramme, nicht Teil der Anwendung
packaging/    Vorlagen für Spec, Installer und Linux-/Mac-Pakete
website/      öffentliche Seiten; erzeugt wird, was die tools/make_*.py nennen,
              api/ gehört nach httpdocs/api/
changelog/    was im Update-Fenster steht, je Sprache eine Datei. Hier liegt
              bewusst keine CLAUDE.md: Test und make_download.py lesen jeden
              Dateinamen des Ordners als Sprache
konzepte/     das Warum: Konzepte, Durchsichten, Nachweise, begruendungen/,
              archiv/ für Erledigtes und Abgelöstes
Signierung/   Übergabe der Windows-Signatur (README.md)
.github/      CI-Workflows; .githooks/ pre-commit, commit-msg, post-commit
.claude/      Regeln, Agenten, Skills, Hooks — was davon mitreist: .claude/README.md
Releases/     lokale Pakete; nur die veröffentlichten Handbuch-PDFs versioniert
output/, tmp/ örtliche Prüfstände und Sicherungen, nicht versioniert
marketing/    Pressetexte und Kampagnen, nur örtlich, nicht versioniert
3D Drucker/   physische Druckprojekte, eigenes Repository, nicht versioniert;
              fehlt auf manchem Rechner hier, auf einem liegt es unter
              F:\3D Dateien\3D Drucker
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
  stehen in `.claude/settings.json` und `.codex/hooks.json`, mit denselben
  Aufgaben und Zeitgrenzen (`AGENTS.md`, „Claude und Codex bleiben gleich“).
  Sie melden, sie fragen und sperren nicht. Codex verlangt je
  Hook-Definition eine Freigabe über `/hooks`, nach jeder Änderung erneut.
  Testmarken sind Erinnerungen, kein Nachweis eines Tors.
- **`pyright-lsp`** gibt Sprachhilfe, bei Claude und Codex als Plugin
  (Einrichtung je Rechner in `/erzeugen`); die verbindliche Typprüfung bleibt mypy.
- **`context7`** liefert Bibliotheksdoku, bei Claude als Plugin, bei Codex
  über `.codex/config.toml`. Gefragt wird nach Bibliothek und Fachfrage — nie
  mit Projektcode oder Zugangsdaten.

## Arbeitsweise hier

Kleine Schritte, Test zuerst bei Geometrie, kein Revert, nie stillschweigend
raten — das steht in `AGENTS.md`. Dazu:

- **Nach jedem abgeschlossenen Punkt committen und pushen**, sobald das Tor
  grün und das Review behoben ist — in logischen Einheiten, nur die eigenen
  Pfade, mit `Co-Authored-By`, ohne Rückfrage (Entscheidung Robert).
  Zusammengeführt wird per Merge; `/liefern` bündelt das.
- **Vor jedem Push nach main ein Review** (Entscheidung Robert, jede Sitzung,
  auch für Unterlagen und Review-Fixes) mit dem Agenten `solidon3d-review`,
  danach eigene Worktrees und Zweige abbauen; wie, steht in `/liefern`.
- **`.githooks/post-commit` pusht** jeden Commit, weil auf drei Maschinen
  gearbeitet wird. Er holt und rebasiert nicht — ist die Gegenstelle weiter,
  scheitert er und sagt es. `SOLIDON_KEIN_PUSH=1` hält einen Commit lokal,
  wenn Robert ausdrücklich „nicht pushen" sagt.
- **`.githooks/pre-commit`** fährt bei Änderungen an `app/` oder `tools/` die
  Bezeichnerprüfung und `tools/check_new_texts.py`; Befunde an Dateien dieses
  Commits halten ihn an. Die Zuordnung vergleicht vollständige Repositorypfade;
  nur eindeutig fremde Testbefunde dürfen passieren. Ein ausgefallener oder
  nicht auswertbarer Prüflauf hält den Commit an.
- **`.githooks/commit-msg`** prüft die Meldung auf Ersatzschreibung statt
  Umlaut (`tools/check_message.py`). `SOLIDON_KEIN_TOR=1` schaltet ihn und
  `pre-commit` für einen Lauf ab.
- Alle drei Hooks laufen nur mit `core.hooksPath = .githooks` (`check_env`
  meldet es) und suchen ihren Interpreter am Hauptklon, auch aus einem Worktree.
- **Nach einer Muster- oder Entscheidungsänderung** die Regel in
  `.claude/rules/` nachziehen und `ROADMAP.md` fortschreiben; den Bauplan nur
  mit Ansage ändern.

## Erinnerungen

Wo sie liegen, sagt `AGENTS.md` („Paketstruktur“), warum nicht im
Repository, `.claude/README.md`. Fehlen sie nach einem Pull, holt der
Sitzungsstart den letzten versionierten Stand zurück.

- **Eine Datei je Thema.** Eine neue Erkenntnis kommt als Abschnitt in das
  passende Thema aus `MEMORY.md`; eine neue Datei nur für ein neues Thema. Der
  Schreib-Hook nennt einer neuen Datei die nächstliegenden Themen.
- Was jede Sitzung auf jedem Rechner braucht, gehört in eine Regel oder Karte —
  nicht in die Erinnerungen. Geheimnisse gehören in keines von beiden.
