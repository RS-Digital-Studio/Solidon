@AGENTS.md

# Solidon — Anweisungen für Claude Code

`AGENTS.md` oben ist die Hausordnung und gilt vollständig. Diese Datei ergänzt,
was nur Claude Code betrifft: Befehle, Werkzeuge, und die Stellen, an denen
meine globalen Vorgaben auf dieses Projekt nicht passen.

## Was dieses Projekt ist

Solidon — eine Desktop-Anwendung in **Python (3.13 oder neuer) mit PySide6**,
kein Avalonia/.NET. Die Untergrenze steht in `pyproject.toml`; die
Arbeitsumgebung fährt derzeit 3.14, die CI 3.13.

Die Unterlagen in ihrer Rangfolge:

| Datei | Beantwortet |
|---|---|
| `3d-agent-bauplan.md` | **Was** gebaut wird — die Spezifikation, §-Nummern sind verbindlich |
| `AGENTS.md` | **Wie** gearbeitet wird — 22 harte Regeln, jede mit Test |
| `ROADMAP.md` | **Was als Nächstes** — Arbeitsliste, oben das Register der offenen Punkte |
| `ROADMAP-ARCHIV.md` | **Was schon versucht wurde** — die abgeschlossenen Abschnitte, datiert |
| `konzepte/README.md` | **Warum** — Index der neunzehn Konzepte und Durchsichten, mit dem Stand je Dokument |
| `README.md` | Was der Nutzer sieht |

Bei Widerspruch gilt der Bauplan. Eine Aussage ohne §-Beleg ist eine Vermutung.

**Offene Arbeit steht im Register von `ROADMAP.md` und nirgends sonst.** Die
Konzepte tragen Statustabellen, und die altern: von zwölf Punkten, die sie am
22.08.2026 als offen führten, waren sieben längst behoben. Wer „offen" in einem
Konzept liest, prüft es am Code, bevor er es glaubt — und trägt es ins Register
nach, wenn es stimmt.

## Sprache — die wichtigste Falle

Die Sprachregelung steht verbindlich in `AGENTS.md`; hier die Kurzform:

- **Bezeichner, Dateinamen, Modulnamen: Englisch** — in `app/` und `tools/`.
  Der Grund ist die Auslieferung: Dort steht Code, den jemand liest, der das
  Projekt nicht kennt. **In `tests/` gilt der Bestand der Datei**, wie bei den
  Assert-Meldungen (`AGENTS.md`). `tests/test_language_rules.py` prüft genau
  diese beiden Verzeichnisse, und seine `GERMAN_STEMS` sind eine **kuratierte
  Liste**: Wer ein deutsches Wort in einem Bezeichner findet, trägt den Stamm
  dort ein.
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
zusammen.

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

Das Skript sucht die Fensterdateien selbst (`grep -lE "MainWindow|Viewport|pyvista"`),
eine neue braucht also keinen Eintrag. Es liegt unter `.claude/.state/` und ist
seit dem 22.08.2026 eingecheckt — vorher schloss `.gitignore` den ganzen Ordner
aus, und ein frischer Klon hatte damit den einzigen Weg nicht, auf dem das Tor
durchläuft.

Erst beides zusammen mit ruff, `ruff format --check` und mypy ist das Tor.

Drei Fallen dabei, alle drei am 22.08.2026 einmal zugeschnappt:

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
- **Ein Abriss beim Abbau ist kein roter Test.** `suite-getrennt.sh` gab an
  jenem Tag Exit 3, obwohl jeder Test grün war: drei Fensterdateien melden
  „passed" und stürzen danach beim Aufräumen (`0xC0000409`). Der Fall steht in
  `ROADMAP.md` unter „Der Changelog schickte den Kunden ins Handbuch, und dort
  war nichts"; wer ihn nicht kennt, hält einen grünen Stand für rot. Zwei
  Fensterdateien enden inzwischen mit **127** statt mit dem bekannten Code, und
  zwar einzeln gefahren auch — das ist ein eigener offener Punkt und nicht
  derselbe Absturz.
- **„Keine Tests gesammelt" ist kein Fehllauf.** Das Skript sucht seine
  Fensterdateien im *Text* (`grep -lE "MainWindow|Viewport|pyvista"`), damit eine
  neue keinen Eintrag braucht. Es erwischt damit auch eine Datei, die über eine
  Ansicht **schreibt**, statt eine zu bauen: `tests/test_performance.py` landete
  wegen zweier Docstrings in der Fenstergruppe, lief dort mit
  `-m "not performance"`, sammelte nichts und endete mit **Exit 5**. Das Skript
  wertet das nicht mehr als Fehllauf — wer einen eigenen Lauf baut, sollte es
  auch nicht.

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
  backends/   LLM, OpenSCAD, Mesh-Erzeuger — alles extern, alles abschaltbar
              comfy_setup.py richtet ein fremdes ComfyUI für Weg 3 ein,
              data/comfyui/ sind die Knoten dazu (TripoSG, MIT): beides im
              Kern, weil tools/ im gebauten Paket nicht mitreist
  export/     STL/3MF/STEP, Plattenbelegung, Übergabe an den Slicer
              (handover.py ruft ihn, slicer_keys.py übersetzt die Namen)
  activation/ Freischaltung: Testlauf, Schlüssel, Demo-Frist (store.py)
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
website/      öffentliche Seiten; handbuch.html und en/manual.html erzeugt
              tools/make_manual.py, die Rechtstexte tools/make_legal.py,
              robots/sitemap/llms tools/make_seo.py — der Rest von Hand
              api/support.php nimmt die Rückmeldungen an; muss nach
              httpdocs/api/ hochgeladen werden, sonst scheitert das Senden
              bilder/ Schaustücke von Hand, beleg-*.png von tools/make_web_images.py
              dl/ die Pakete, von tools/make_download.py angelegt
changelog/    was im Update-Fenster steht, je Sprache eine Datei — Auswahl
              in Kundensprache, keine Liste der Änderungen
3D Drucker/   physische Druckprojekte, eigene CLAUDE.md — kein Programmcode
              und **nicht** in diesem Repository: der Ordner hat sein eigenes
              `.git` und steht hier in `.gitignore`. Wer dort committet, tut
              es in seinem eigenen Repository
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
- **Bei zwei Sitzungen im selben Arbeitsbaum**: vorher sagen, welche Dateien
  man anfasst, und mit privatem Index committen (`GIT_INDEX_FILE`,
  `git commit -o -- <pfade>`). Sonst nimmt der eigene Commit fremde Arbeit
  mit — dreimal passiert am 19./20.08.2026.
- **Nach Pattern-Änderungen**: die betroffene Regel in `.claude/rules/`
  nachziehen, `ROADMAP.md` fortschreiben, Bauplan nur mit Ansage ändern.
