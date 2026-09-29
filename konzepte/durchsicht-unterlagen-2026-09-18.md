# Durchsicht der Unterlagen — 18.09.2026

**Anlass:** Der Vergleich mit dem Schwesterprojekt Assist (`can3Dng`), dessen
`.claude/`-Ebene neunzehn Regeln in 148 KB führt, während Solidon vierzehn in
564 KB führte. Geprüft wurde, was eine Sitzung ungefragt mitliest, bevor sie
eine Zeile Code sieht — und ob die Pyramide ihr eigenes Versprechen hält:
*jedes Gebiet eine Karte und eine Regel, und keine wiederholt die andere.*

**Umgesetzt am selben Tag.** Was unten als Befund steht, ist der Ausgangsstand;
die Abschlussnotiz steht am Ende.

## Maßstab und Umfang

Gemessen mit `tools/docs_scan.py` (an diesem Tag entstanden, Selbsttest in
`tests/test_docs_scan.py`), über 49 Unterlagen mit zusammen 1003 KB und 664
Quelldateien in `app/`, `tools/` und `tests/`. Gezählt wird je Quelldatei: die
Karte ihres Verzeichnisses, `CLAUDE.md` und `AGENTS.md` der Wurzel, und jede
Regel, deren `paths:` sie trifft. Die Karten **darüber** sind nicht mitgezählt
— die Zahlen sind damit Untergrenzen.

Dies ist keine inhaltliche Prüfung aller Aussagen in 1 MB Prosa. Geprüft sind
Umfang, Überschneidung, Geltungsbereiche und Verweise.

## Befund 1 — Die Ladelast, und wo sie herkommt

| | vorher | nachher |
|---|---|---|
| Schwerste Quelldatei | **359 KB** (elf Dateien gleichauf) | 309 KB (`viewport.py` allein) |
| Mittel über 663 Quelldateien | 121 KB | 114 KB |
| `app/ui/cursors.py`, `analysis_bar.py`, `explode_bar.py` … | 359 KB | **265 KB** |
| `.claude/rules/` gesamt | 564 KB | 588 KB in 19 Dateien |

Die Regeln sind in der Summe **größer** geworden, und das ist der Punkt: Es
ging nie um Zeilen, sondern darum, **wer sie zu sehen bekommt**. Zwei Gebiete
galten für zwei Dateien und luden für dreiundzwanzig.

Was geschnitten wurde:

| Aus | Neu | KB | Lädt bei |
|---|---|---|---|
| `ansicht.md` (117 KB) | `griffe.md` | 26 | 3 Dateien |
| `ansicht.md` | `kamera.md` | 18 | 6 Dateien |
| `oberflaeche.md` (99 KB) | `grenzen.md` | 25 | 11 Dateien, darunter das Register |
| `oberflaeche.md` | `fenster.md` | 29 | 23 Dateien |

`ansicht.md` steht danach bei 75 KB, `oberflaeche.md` bei 47 — halbiert, und
sie lädt für jede der vierundachtzig Dateien unter `app/ui/`.

**Nicht geschnitten**, und zwar mit Grund:

* `tests.md` (54 KB, 307 Dateien) ist thematisch homogen. Die Hälfte handelt
  vom **Fahren** der Suite, nicht vom Schreiben eines Tests — dafür gibt es
  keinen Pfad-Schnitt, der greift. Ein Schnitt, der eine Regel unauffindbar
  macht, ist keine Verbesserung.
* `zeichenflaeche.md` (51 KB) gilt für genau eine Datei. Das ist der engste
  Geltungsbereich, den es gibt.
* `app/ui/CLAUDE.md` mit 101 KB ist inzwischen der **größte Einzelposten** der
  Ladelast. Eine Karte je Verzeichnis ist von `test_directory_docs.py`
  erzwungen; bei vierundachtzig beschriebenen Dateien sind das 1,2 KB je
  Datei. Das ist kein Missstand, aber der nächste Hebel, falls einer gebraucht
  wird.

## Befund 2 — Die Pyramide hält ihr Versprechen

**Kein einziger Absatz steht in zwei Unterlagen.** Geprüft über alle 49
Dateien (Fließtext ab 120 Zeichen, Tabellen und Überschriften ausgenommen).
Der Verdacht, dass sich Karte und Regel bei dieser Menge zwangsläufig
wiederholen, ist damit widerlegt — bei Solidon trennt die Pyramide sauber
zwischen *was liegt hier* und *was ist einzuhalten*.

## Befund 3 — Verweise

Vier Verweise auf Quelldateien gehen ins Leere, und alle vier zu Recht: Sie
erzählen, wie etwas **früher** hieß (`slot_bar.py` bis zum 11.09.2026,
`scripted.py` im alten Kundenpaket) oder sind Platzhalter
(`test_way_one/two/three/four.py`). Kein Handlungsbedarf.

Die erste Fassung der Prüfung meldete zehn weitere — `feedback.json`,
`filaments.json`, `trial.json`, `salt.json`, `fdmprinter.def.json` —, und alle
zehn waren Falschalarme: Diese Dateien entstehen zur Laufzeit im Nutzerordner
oder liegen beim Kunden. Die Vorschrift liest seither nur `.md` und `.py`.

**Der Schnitt selbst hat fünf Verweise gebrochen**, gefunden mit einer
eigenen Prüfung über Zitate der Form ``regel.md`` … „Abschnitt": vier im
Quelltext (`main_window.py` zweimal, `placement_flow.py` zweimal,
`test_analysis_ui.py`) und einer in `griffe.md`. Alle sind auf ihr neues Ziel
umgebogen.

## Befund 4 — Geltungsbereiche

Neunzehn Regeln, 44 `paths:`-Muster, **eines ohne Treffer**: `3D Drucker/**`
in `druckteile.md`. Das ist richtig so — der Ordner hat sein eigenes
Repository und steht hier in `.gitignore`. Die Regel gilt trotzdem für den,
der dort arbeitet.

## Befund 5 — Was fehlte

| Lücke | Behoben durch |
|---|---|
| Die projektübergreifende Arbeitsanweisung verweist auf `.claude/rules/parallele-codepfade.md`. **Die Datei gab es hier nicht** — der Begriff kam in keiner Regel vor, obwohl das Projekt das Thema unter „Zwillinge" gemessen und ein Werkzeug dafür eingecheckt hat | `zwillinge.md` (7 KB, lädt über ganz `app/`): die vier Klassen mit ihren Pflichten, die sechs Entstehungswege, und warum ein Skript die gefährlichen nicht sieht |
| Keine Regel sagte, worum es in ihr geht, ohne dass man sie öffnet | `description:` im Frontmatter aller neunzehn |
| Kein Wegweiser über die `.claude/`-Ebene: was liegt hier, wer ist die Quelle, was ist eingecheckt | `.claude/README.md` |
| Keine Durchsicht der Unterlagen selbst — nur `test_directory_docs.py` prüft mechanisch die Vollständigkeit | dieses Dokument, und `tools/docs_scan.py` für den nächsten Lauf |

Die Zwillingsfunde des Konzepts vom 07.09.2026 wurden dabei **gegen den Code
nachgemessen**, statt sie abzuschreiben: Von elf ungewollten sind sieben
zusammengelegt, vier stehen noch. Die Liste steht in `zwillinge.md`.

## Befund 6 — Neunundvierzig Konzepte in einem flachen Verzeichnis

Assist teilt seine Konzepte in acht Themenordner plus `archiv/`. **Für Solidon
wurde das nicht übernommen**, und zwar gemessen: Sechsundachtzig Stellen
zitieren Konzepte beim Dateinamen — zwölf im Quelltext von `app/`, `tools/`
und `tests/`, vierundvierzig im Roadmap-Archiv. Ein Umzug bräche sie alle, und
der Gewinn wäre Auffindbarkeit.

Die gibt es billiger: `konzepte/README.md` trägt jetzt **zusätzlich zur
Statustabelle einen Index nach Thema** — neun Gruppen von „Konstruieren,
Geometrie, Kerne" bis „Arbeitsweise am Code". Die Statustabelle beantwortet
weiter die andere Frage: wem darf ich noch glauben.

**Vier Durchsichten sind gelöscht** (145 KB), alle vier belegt abgearbeitet
und im Roadmap-Archiv nachgewiesen: `konzept-durchsicht-2026-08-14`,
`durchsicht-2026-08-16`, `konzept-live-durchsicht-2026-08`,
`konzept-p15-konstruieren-und-zeigen`. Ihre fünf eingehenden Verweise sind
nachgezogen; die Namen bleiben im Roadmap-Archiv stehen, wo sie Geschichte
sind, und der Abschnitt „Was gelöscht wurde" im Konzept-README erklärt sie.

**Nicht gelöscht**, obwohl erledigt: `oberflaechen-durchsicht-2026-08-20`
führt unter „Bewusst offen" und „Acht Gebiete sind nie gelaufen" Punkte, deren
Register-Zuordnung nicht geprüft ist, und `geogram-als-zweiter-kern` ist zwar
erledigt, trägt aber die Begründung, warum **kein** zweiter Kern kommt.

## Abschlussnotiz

Umgesetzt am 18.09.2026, in dieser Reihenfolge: `description:` in alle Regeln
· `.claude/README.md` · `zwillinge.md` mit nachgemessenen Funden ·
`tools/docs_scan.py` und sein Selbsttest · der Schnitt in vier neue Regeln ·
fünf umgebogene Verweise · Themenindex und vier gelöschte Durchsichten.

Was offen bleibt: die Ladelast der Karte `app/ui/CLAUDE.md`, und die Frage, ob
`tests.md` einen zweiten Ort für das Fahren der Suite bekommt. Beides ist eine
Umfangsentscheidung, keine Nachlässigkeit.

**Das Tor ist zu diesem Stand nicht gefahren worden** (Entscheidung Robert,
18.09.2026 — „kein Tor, einfach commit und push"). Gelaufen sind der
Selbsttest des neuen Werkzeugs, `ruff`, `ruff format --check` und `mypy` über
die berührten Dateien.
