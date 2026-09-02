# `tests/` — die Suite

Mehr als 150 Python-Dateien und weit über 80 000 Zeilen. Eine Datei je Testart; `data/` ist der
Referenzkorpus.

Die Regeln stehen in `.claude/rules/tests.md` — dort auch die Messfallen, die
schon einmal zugeschnappt sind. Hier steht, **wie sie gefahren wird** und
**was wo geprüft wird**.

## Die Fahrweise — nicht `pytest -q` am Stück

Der ganze Lauf in einem Prozess kommt seit dem 16.08.2026 nicht mehr durch:
rund 22 Minuten, dann ein nativer Abriss bei über 3 GB, ohne Ergebniszeile.
Die Suite baut über siebenhundert VTK-Fenster nacheinander auf, und irgendwann
reißt eine Grenze.

Gefahren wird sie wie in der CI — **ein Prozess je Fensterdatei**, alles
übrige in einem Zug:

```bash
bash .claude/.state/oberflaechen-durchsicht-2026-08-19/suite-getrennt.sh
```

Die Leistungstests lässt der geteilte Lauf mit `-m "not performance"`
ausdrücklich aus, also zusätzlich:

```bash
.venv/Scripts/python.exe -m pytest -q -m performance
```

Am einfachsten: **`/pruefen`** — der Skill fährt beides plus ruff, `ruff
format --check` und mypy unter einem Schloss, damit parallele Sitzungen sich
nicht verfälschen.

## Drei Fallen beim Lesen des Ergebnisses

- **Auf den Exit-Code sehen, nicht auf eine Schlusszeile — und ihn nicht
  durch eine Pipeline lesen.** `… | tail -30` meldet den Status von `tail`,
  und `tail` gelingt immer. Dasselbe gilt für ein `echo` als letzten Befehl.
  Sicher ist: **Ausgabe in eine Datei, danach lesen.**
- **Ein Abriss beim Abbau ist kein roter Test.** Drei Fensterdateien melden
  „passed" und stürzen danach beim Aufräumen (`0xC0000409`).
- **„Keine Tests gesammelt" ist kein Fehllauf.** Exit 5 entsteht, wenn das
  Skript eine Datei in die Fenstergruppe zieht, die dort nichts zu sammeln
  hat.

## Was wo geprüft wird

| Frage | Datei |
|---|---|
| Läuft der Kern ohne Qt? | `test_core_isolation.py` |
| Öffnet jedes angebotene Modellformat dieselbe Referenzgeometrie? | `test_import_formats.py` |
| Deutsche Stämme in Bezeichnern? | `test_language_rules.py` |
| Ist jede Op vollständig registriert? | `test_registry_consistency.py` |
| Zweimal ausgewertet = identisch? | `test_evaluation.py` |
| Jede Rückfallstufe einmal erzwungen? | `test_boolean.py` |
| Sammelparameter-Ops über das Register | `test_gesture_ops.py` |
| Öffnen alte Projektdateien? | `test_project.py`, Beispiele in `data/projects/` |
| Trägt jede Ausnahme einen Vorschlag? | `test_errors.py` |
| Bedeutung allein über Farbe? | `test_theme_and_palette.py` |
| Neun Menüs, zwölf Zeilen, acht Felder | `test_interface_limits.py` |
| Sind alle Kataloge vollständig? | `test_translations.py` |
| Bleiben Käuferzuordnung und Betreiberzugang aus dem Server und arbeitet die Support-Verwaltung nur per Digest? | `test_licence_admin.py`, `test_activation_server.py` |
| Halten die PHP-Endpunkte ihre Missbrauchsgrenzen? | `test_public_php_security.py`; ohne PHP ein Skip, in der Linux-CI ein Fehler — `php_probe.py` entscheidet das für alle Endpunkttests |
| Budget §31, Schwelle 25 % | `test_performance.py` (`-m performance`) |
| Abhängigkeiten gegen die Freigabeliste | `test_licences.py` |
| Die vier Hauptwege Ende zu Ende | `test_way_one.py` … `test_way_four.py` |
| 39 Referenzanfragen an den Agenten | `test_agent_suite.py`, Fälle in `agent_cases.py` |

## Der Korpus

`data/` trägt die Modelle, gegen die Geometrie gemessen wird — `meshes/` und
`projects/`. **Ein neues Fehlerbild wird eine Datei hier**, kein Sonderfall im
Code.

Was ein Skript wiederherstellt, liegt nicht darin: Das parametrische Skript
ist die Quelle, die Datei daraus ist das Ergebnis.

## Sprache in diesem Verzeichnis

**Hier gilt der Bestand der Datei, nicht die Bezeichnerregel.** `app/` und
`tools/` reisen zum Kunden, `tests/` liest nur, wer hier arbeitet — deshalb
prüft `test_language_rules.py` genau jene zwei Verzeichnisse und dieses nicht.

Gezählt am 23.08.2026: 78 deutsche Bezeichner in 27 Dateien. Sie werden
**nicht** umbenannt — eine Massenänderung in fremden Dateien kostet mehr, als
sie einbringt. Assert-Meldungen bleiben ebenfalls beim Bestand der Datei.

## `conftest.py` tut zwei Dinge, die leicht zu übersehen sind

- Es setzt `QT_QPA_PLATFORM=offscreen` — Qt-Tests brauchen kein Bild.
- Es biegt **die Nutzerverzeichnisse in einen Temp-Ordner** um (§38), `HOME`
  eingeschlossen. Läuft ein Test außerhalb der Suite, fehlt ihm das, und er
  liest in Roberts echtem Profil.
