@AGENTS.md

# Solidon — Anweisungen für Claude Code

`AGENTS.md` oben ist die Hausordnung und gilt vollständig. Diese Datei ergänzt,
was nur Claude Code betrifft: Befehle, Werkzeuge, und die Stellen, an denen
meine globalen Vorgaben auf dieses Projekt nicht passen.

## Was dieses Projekt ist

Solidon — eine Desktop-Anwendung in **Python (3.14 oder neuer) mit PySide6**,
kein Avalonia/.NET. Die Untergrenze steht in `pyproject.toml`; die
Arbeitsumgebung und CI verwenden CPython 3.14.7.

Die Unterlagen in ihrer Rangfolge:

| Datei | Beantwortet |
|---|---|
| `3d-agent-bauplan.md` | **Was** gebaut wird — die Spezifikation, §-Nummern sind verbindlich |
| `AGENTS.md` | **Wie** gearbeitet wird — 22 harte Regeln, jede mit Test |
| `ROADMAP.md` | **Was als Nächstes** — Arbeitsliste, oben das Register der offenen Punkte |
| `ROADMAP-ARCHIV.md` | **Was schon versucht wurde** — die abgeschlossenen Abschnitte, datiert |
| `konzepte/README.md` | **Warum** — vollständiger Index der Konzepte und Durchsichten, mit dem Stand je Dokument |
| `README.md` | Was der Nutzer sieht |
| `<verzeichnis>/CLAUDE.md` | **Was wo liegt** — die Karte des Gebiets; lädt mit, sobald ich eine Datei darin anfasse |
| `.claude/rules/*.md` | **Was dort einzuhalten ist** — greift über `paths:`, quer zu den Verzeichnissen |

Bei Widerspruch gilt der Bauplan. Eine Aussage ohne §-Beleg ist eine Vermutung.

**Offene Arbeit steht im Register von `ROADMAP.md` und nirgends sonst.** Die
Konzepte tragen Statustabellen, und die altern: von zwölf Punkten, die sie am
22.08.2026 als offen führten, waren sieben längst behoben. Wer „offen" in einem
Konzept liest, prüft es am Code, bevor er es glaubt — und trägt es ins Register
nach, wenn es stimmt.

## Sprache — die wichtigste Falle

Die Sprachregelung steht verbindlich in `AGENTS.md` und lädt über `@AGENTS.md`
in jeder Sitzung mit — Bezeichner, Docstrings, Oberflächentexte, Kataloge und
die kuratierte Stammliste stehen dort vollständig. Hier nur, was dort fehlt:

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
zusammen — **vor dem Commit**, nicht nach jedem Schritt. Je Schritt laufen nur
die Tests der berührten Dateien (Entscheidung Robert, 02.09.2026):

```
.venv\Scripts\python.exe tools/affected_tests.py                      # geändert + neu gegenüber HEAD
.venv\Scripts\python.exe tools/affected_tests.py app/core/units.py     # oder die Dateien ausdrücklich
.venv\Scripts\python.exe tools/affected_tests.py --run                 # fahren, Exit-Code direkt gelesen
```

`--why` nennt je Testdatei den Grund, `--split` zeigt die Aufrufe
(Fensterdateien einzeln). **Ohne Argumente nimmt es alle ungestageten
Änderungen im Baum — bei mehreren Sitzungen also auch fremde**; wer nur seine
Dateien meint, nennt sie. Bei Änderungen an `i18n`, `types.py`, `errors.py`
oder `log.py` meldet es „das ist die Suite" — dann direkt `/pruefen`.

**`pytest -q` am Stück kommt seit dem 16.08.2026 nicht mehr durch.** Rund 22
Minuten, dann ein nativer Abriss bei über 3 GB, ohne Ergebniszeile — die Suite
baut in einem Prozess über siebenhundert VTK-Fenster nacheinander auf, und
irgendwann reißt eine Grenze. Gefahren wird sie deshalb wie in der CI: **ein
Prozess je Fensterdatei**, alles übrige in einem Zug. Dazu kommen die
Leistungstests, die der geteilte Lauf mit `-m "not performance"` ausdrücklich
auslässt:

```
bash .claude/.state/oberflaechen-durchsicht-2026-08-19/suite-getrennt.sh
.venv\Scripts\python.exe -m pytest -q -m performance   # was dabei fehlt (§31)
```

Das Skript sucht die Fensterdateien selbst (`tools/list_windowed_tests.py` liest
den Fixture-Graphen: jede Datei mit einem `qt_app`-Test), eine neue braucht
also keinen Eintrag. Es liegt unter `.claude/.state/` und ist
seit dem 22.08.2026 eingecheckt — vorher schloss `.gitignore` den ganzen Ordner
aus, und ein frischer Klon hatte damit den einzigen Weg nicht, auf dem das Tor
durchläuft.

Erst beides zusammen mit ruff, `ruff format --check` und mypy ist das Tor.

Drei Fallen dabei, alle drei am 22.08.2026 einmal zugeschnappt — die erste in einer zweiten Gestalt am 24.08.2026 noch einmal:

- **Auf den Exit-Code sehen, nicht auf eine Schlusszeile — und den Exit-Code
  nicht durch eine Pipeline lesen.** Wer `FAILED` grept, liest die
  Zusammenfassung, und die schreibt pytest erst am Ende; im laufenden
  Fortschritt bleiben zwei `F` unsichtbar. Eine Pipeline dagegen meldet den
  Status ihres letzten Glieds, und `tail` gelingt immer:
  `suite-getrennt.sh … | tail -30` berichtete „Exit 0" über einem
  `Läufe mit Fehler: 4`. Wer beides zusammen falsch macht, liest eine gültige
  Zahl und glaubt ihr — wer nur eine der beiden Fallen kennt, verlässt sich
  ausgerechnet auf die andere. Sicher ist: **Ausgabe in eine Datei, danach
  lesen.** Das gibt den Code **und** die Namen. `set -o pipefail` oder
  `${PIPESTATUS[0]}` retten nur den Code — gemessen, sie wirken, aber sie sagen
  nicht, *welche* vier Läufe es waren.

  **Und nicht nur die Pipeline verdeckt den Code: alles, was danach kommt,
  auch.** Am 24.08.2026 meldete eine Sitzung „exit code 0", während in ihrer
  Ausgabedatei `Läufe mit Fehler: 4` stand — kein `tail` diesmal, sondern ein
  eigenes `echo` als letzter Befehl der Kette. Der Shell-Status ist immer der
  des **letzten** Befehls, und `echo` gelingt so zuverlässig wie `tail`. Wer
  den Code braucht, liest ihn unmittelbar (`befehl > datei; echo "Exit: $?"`),
  bevor irgendetwas anderes läuft — nicht am Ende einer Kette.
- **Jeder Nichtnull-Prozessausgang macht das Tor rot**, auch nach „passed"
  oder vollständigen Fortschrittszeichen. Ein nativer Abbruch und eine
  fehlgeschlagene Zusicherung sind unterschiedliche Ursachen, aber beide
  verhindern die Abnahme. Die Shell kann verschiedene Windows-Nativcodes
  als 127 melden; zur Diagnose zählt der direkte Prozessausgang.
- **Diagnosewiederholungen löschen keinen früheren Fehler.** Das geteilte
  Tor halbiert weiterhin Portionen mit fehlenden Tests. Es zählt den
  ursprünglichen Abbruch vor der Teilung und endet insgesamt mit Exit 1.
  Ein späterer sauberer Lauf ist ein eigener Nachweis.
- **Sammlungsfehler werden nicht übergangen.** Die Fenstergruppe kommt aus
  Pytests Fixture-Graphen, einschließlich mittelbarer `qt_app`-Abhängigkeiten.
  Scheitert die Gruppen- oder Testnamensammlung, bleibt das Tor rot; eine
  teilweise ausgegebene Liste wird nicht als vollständig gefahren. Ein
  ausdrücklich gesetztes `SUITE_PYTHON` wird nie still ersetzt.

Weiteres:

```
.venv\Scripts\python.exe -m pytest tests/test_parts.py -q      # eine Datei
.venv\Scripts\python.exe -m pytest -q -m "not slow"             # ohne die langen
.venv\Scripts\python.exe -m pytest -q -m performance            # Budget §31
.venv\Scripts\python.exe -m app.ui.app                          # Anwendung starten
.venv\Scripts\python.exe -m app.cli.main --help                 # Kommandozeile
.venv\Scripts\python.exe tools/run_agent_suite.py               # kostet Geld, kein Testlauf
```

Was **nicht Code** erzeugt — Bildschirmfotos, Handbuch, Website-Bilder,
SEO-Dateien, Symbol, Installationsdatei, Linux-Pakete, Download-Kasten,
ComfyUI, Website-Upload — dazu Erstaufbau und Versionspflege über
`check_env.py`: `/erzeugen`. Dort stehen auch die Reihenfolge, der eigene
Arbeitsbaum fürs Paketieren und die Falle mit den fehlenden Schriften.

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
  backends/   LLM und Mesh-Erzeuger — beides extern, beides abschaltbar
              comfy_setup.py richtet ein fremdes ComfyUI für Weg 3 ein,
              data/comfyui/ sind die Knoten dazu (TripoSG, MIT): beides im
              Kern, weil tools/ im gebauten Paket nicht mitreist
  export/     STL/3MF/OBJ/PLY/GLB/STEP, Plattenbelegung, Slicer-Übergabe
              (handover.py ruft ihn, slicer_keys.py übersetzt die Namen)
  activation/ Freischaltung: Kaufcode, Geräteidentität, signiertes Zertifikat,
              Demo- und optionale Testfrist
  updates.py  Update: fragen, holen, prüfen — gestartet wird nur auf Klick,
              die Punkte dazu stehen in changelog/<sprache>.md
  report.py   Fehlerbericht als Ordner — schreibt, sendet nie
  support.py  der einzige Weg hinaus: Rückmeldung an den Support, an einem Knopf
  manual.py   Handbuch: geschriebene Seiten, Referenz aus dem Register erzeugt
  figures.py  Abbildungskatalog — gezeichnet, gerendert, aufgenommen
  drawing.py  SVG ohne Qt: Maßlinien, Schemata, Netzprojektion
  markup.py   Markdown → HTML, nur die selbst erzeugte Teilmenge
app/ui/       PySide6 — darf core benutzen, nie umgekehrt
app/images/   Bildschirmfotos fürs Handbuch, je Sprache ein Ordner
app/cli/      Kommandozeile auf core
tests/        eine Datei je Testart, data/ ist der Referenzkorpus
tools/        Hilfsprogramme, nicht Teil der Anwendung
website/      öffentliche Seiten; handbuch.html und <sprache>/manual.html erzeugt
              tools/make_manual.py, die Rechtstexte tools/make_legal.py,
              Changelog-Seiten tools/make_changelog.py,
              robots/sitemap/llms tools/make_seo.py — der Rest von Hand
              api/support.php nimmt Rückmeldungen an; die activation-Endpunkte
              aktivieren und deaktivieren Geräte, api/operator.php nimmt nur
              die lokale Support-Verwaltung mit externem Token an; alles muss
              nach httpdocs/api/
              bilder/ Schaustücke von Hand, beleg-*.png von tools/make_web_images.py
              dl/ die Pakete, von tools/make_download.py angelegt
changelog/    was im Update-Fenster steht, je Sprache eine Datei — Auswahl
              in Kundensprache, keine Liste der Änderungen. **Hier liegt keine
              CLAUDE.md**, und zwar bewusst: Test und `make_download.py`
              sammeln den Ordner über `glob("*.md")` und lesen jeden Stem als
              Sprache. Eine Fremddatei wird dort zur Sprache „CLAUDE" — in der
              Prüfung und in der ausgelieferten `version.json`
3D Drucker/   physische Druckprojekte, eigene CLAUDE.md — kein Programmcode
              und **nicht** in diesem Repository: der Ordner hat sein eigenes
              `.git` und steht hier in `.gitignore`. Wer dort committet, tut
              es in seinem eigenen Repository
```

**Jedes dieser Verzeichnisse trägt eine eigene `CLAUDE.md`** mit der
Architektur seines Gebiets — sie lädt mit, sobald ich eine Datei darin anfasse.
Wie die Ebenen zusammenspielen, steht im nächsten Abschnitt.

## Die Unterlagen-Pyramide

Zwei Sorten Datei begleiten jedes Gebiet, und sie beantworten
**verschiedene Fragen**:

| | `<verzeichnis>/CLAUDE.md` | `.claude/rules/<gebiet>.md` |
|---|---|---|
| Frage | **Was liegt hier?** | **Was ist einzuhalten?** |
| Inhalt | Karte, Datenfluss, Einstieg, Muster | Regeln, Verbote, Stolperfallen |
| Lädt | beim Anfassen einer Datei im Verzeichnis | über `paths:` im Frontmatter |
| Ändert sich | wenn Module dazukommen oder umziehen | wenn eine Entscheidung fällt |

Die Karte sagt „`boolean.py` löst die Rückfallkette"; die Regel sagt „die
benutzte Stufe wird in die Operation geschrieben". **Keine wiederholt die
andere** — die Karte verweist auf die Regel und umgekehrt.

Von oben nach unten:

```
~/.claude/CLAUDE.md      WIE ich arbeite — projektübergreifend
   └─ AGENTS.md          die 22 harten Regeln, jede mit Test
   └─ CLAUDE.md (hier)   Befehle, Karte, Werkzeuge, Arbeitsweise
        └─ app/CLAUDE.md          die vier Schichten und ihre Richtung
             └─ app/core/CLAUDE.md         Verträge, OpContext, Unterpakete
                  └─ app/core/geom/CLAUDE.md    die Rückfallkette, 31 Module
        └─ tests/ tools/ website/ konzepte/ changelog/ packaging/
```

Dazu die Regeldateien, die quer dazu greifen: `kern.md` deckt ganz
`app/core/**`, `operationen.md` zusätzlich `geom/`, `registry/` und `scene/`,
`dateiformat.md` `ingest/`, `export/` und `scene/project*.py`. In `app/ui/`
sind es vier, nach dem, was man anfasst: `oberflaeche.md` immer, dazu
`ansicht.md` beim Viewport, `wartezeit.md` bei allem, was rechnen lässt, und
`zeichenflaeche.md` beim Skizzeneditor.

**Wohin etwas gehört**, in einem Satz: Ändert sich der Code, ändert sich die
Karte; ändert sich eine Entscheidung, ändert sich die Regel. Datums-Marker,
Phasenberichte und Verifikations-Stände gehören in **keines** von beiden — sie
stehen in `ROADMAP.md`, `ROADMAP-ARCHIV.md` und der Git-History.

Vier Verzeichnisse haben **keine** eigene Regeldatei und nur eine Karte:
`app/cli/`, `tools/`, `website/` und `packaging/`. Für sie gilt `AGENTS.md`
unmittelbar.

**Eine Falle beim Schreiben einer Karte:** `ruff format` formatiert
Python-Blöcke **innerhalb** von Markdown mit. Ein ```` ```python ````-Block mit
ausgerichteten Kommentaren macht das Tor rot, ohne dass eine Zeile Code
betroffen wäre. Wer eine Feldliste zeigen will, nimmt eine Tabelle — sie liest
sich ohnehin besser und hält still.

Dass die Karten vollständig bleiben und ihre §-Verweise treffen, prüft
`tests/test_directory_docs.py`.

## Werkzeuge in diesem Projekt

Agents (`.claude/agents/`) — die globalen .NET-Agents passen hier nicht.
Befehle liegen in `.claude/skills/`. Beide Listen stehen bereits in der
Auflistung der Sitzung; hier stünden sie ein drittes Mal.

Wie die Sitzung selbst bedienbar sein soll, steht in
`.claude/bedienkonzept-ueberblick.md` (die Sitzung als Ganzes) und
`.claude/bedienkonzept-funktionen.md` (sechzehn Funktionen einzeln). **Entwurf,
und zwar vollständig:** Umgesetzt ist von den sechs Konzepten und sechzehn
Regeln bis heute keines.

Den **Stand** nennt im Überblick eine vierte Spalte der Schlusstabelle (§10);
bei den Funktionen eine **eigene Tabelle darunter** — deren Schlusstabelle
selbst nennt nur Ort und Aufwand. Beide Dateien vermerken den Unterschied
inzwischen selbst; wer den Stand sucht, sucht die Tabelle mit der Spalte
„Stand" und nicht die letzte der Datei.

## Arbeitsweise hier

Kleine Schritte, Test zuerst bei Geometrie, kein Revert, nie stillschweigend
raten: das steht in `AGENTS.md` und gilt unverändert. Dazu kommt hier:

- **Selbstständig committen**, in logischen Einheiten, mit `Co-Authored-By`.
  `/liefern` führt das aus — Tor laufen lassen, in Einheiten aufteilen,
  deutsche Meldungen. Der Skill ruft sich nicht selbst auf
  (`disable-model-invocation`), er wird angesagt.
- **Jeder Commit geht sofort hinaus.** `.githooks/post-commit` pusht ihn, weil
  auf drei Maschinen gearbeitet wird und ein liegengebliebener Commit auf den
  anderen zweien nicht existiert. Der Hook holt und rebasiert **nicht** — ist
  die Gegenstelle weiter, scheitert er und sagt, was zu tun ist.
  `SOLIDON_KEIN_PUSH=1` schaltet ihn für einen Lauf ab.
- **Vor jedem Commit an `app/` oder `tools/` laufen die zwei
  Sprachprüfungen.** `.githooks/pre-commit` fährt `test_language_rules` und
  `test_translations` — rund zehn Sekunden — und bricht ab, wenn eine Datei
  **aus diesem Commit** darin genannt ist. Der Anlass: Am 30.08.2026 ging
  dreimal derselbe Fehler nach origin, weil er im eigenen Diff unsichtbar ist
  — ein fehlender Katalogeintrag steht in fünf Dateien, die man gerade *nicht*
  angefasst hat. Liegt der Befund in **fremder** Arbeit im geteilten Baum,
  lässt er durch und sagt es; `SOLIDON_KEIN_TOR=1` schaltet ihn ganz ab.
  Beides läuft nur, wenn `core.hooksPath` auf `.githooks` zeigt — `check_env`
  meldet es beim Sitzungsstart, und `tests/test_toolchain.py` prüft zusätzlich,
  dass jeder Hook im Repository ausführbar ist.
- **Bei zwei Sitzungen im selben Arbeitsbaum**: vorher sagen, welche Dateien
  man anfasst, und mit privatem Index committen (`GIT_INDEX_FILE`,
  `git commit -o -- <pfade>`). Sonst nimmt der eigene Commit fremde Arbeit
  mit — dreimal passiert am 19./20.08.2026. Die Fallen dabei — der alternde
  Haupt-Index, `-o` und der Dateistand — stehen im `liefern`-Skill.
- **Nach Pattern-Änderungen**: die betroffene Regel in `.claude/rules/`
  nachziehen, `ROADMAP.md` fortschreiben, Bauplan nur mit Ansage ändern.
