# Programm 2026-10: Stand

Eine Sitzung, die übernimmt, liest zuerst diese Datei und dann das Konzept der
laufenden Phase. Neueste Zeile oben unter „Verlauf“.

## Auftrag Robert (11.10.2026), verbindlich

Drei Konzepte in fester Reihenfolge, jedes bis zu seiner Abnahme (Abschnitt
„Abnahme“ im Konzept). Was dort als Entscheidung Robert steht, gilt.

| Konzept | Unterlagen |
|---|---|
| 0.6.1 (RM-734, RM-735) | `konzepte/konzept-suche-und-palette-2026-10.md`, `konzepte/nachweise-palette-2026-10/`; Auftrag und Einzelstand in der Git-Historie (`git log --diff-filter=D -- .claude/.state/rm-734-735`) |
| Funktionsdurchgang | Zweig `doc/funktionsdurchgang`, `.claude/.state/funktionsdurchgang-2026-10/konzept.md`, `LIESMICH.md`, Prüfberichte |
| Codestruktur | `konzepte/konzept-codestruktur-2026-10.md`, `konzept-codestruktur-funde-2026-10.md` (auf main, sobald main steht, vorher `origin/nach/0.6.0`); RM-722 bis RM-733 |

**Nach main** erst, wenn Robert „main steht“ sagt; dann `origin/main` per
Merge hereinholen. Den Kopf `## 0.6.1` im Changelog legt diese Arbeit selbst
an, in allen Sprachen. Release, Version und Tag nur auf Auftrag.

**Phase 1:** 0.6.1 — RM-734, dann RM-735 auf main; Robert Bescheid geben.

**Phase 2:** Funktionsdurchgang nach `LIESMICH.md` ablegen, RM-736 (Programm)
und RM-737 bis RM-749 (Pakete D0 bis D12) ins Register. Dann D0 (Prüfstand).
Dann Codestruktur Schritt 0 mit den Funden, die es vorher behebt (CS-2, CS-9,
CS-10, CS-11, CS-12, die `raising=False`).

**Phase 3, bis zum Verkaufskandidaten am 25.11.2026:** D1, D9, D8; dann
Codestruktur Schritte 1, 2, 3 (prepare_ops, panels, features); dann D3 und D4.
Daneben die vom Umbau unabhängigen Funde CS-3, CS-6, CS-13, CS-14, CS-15.
Kundenpakete haben Vorrang; wird es eng, werden Codestruktur-Schritte gekürzt,
nicht die Kundenpakete. Robert rechtzeitig sagen, ob der Kandidat bereit ist
oder was fehlt.

**Phase 4, nach dem Start am 01.12.2026:** CS-16, dann Schritte 4a bis 4d, 5
und 6 (Komponenten von MainWindow und den übrigen großen Fensterklassen), dann
Schritt 7 (weitere große Dateien; Bauplanänderung bei `analysis.py`,
Neunachweis der Befestiger bei `geom/prepare.py`), zuletzt Schritt 8
(`handover.py` und Grenzdateien, mit `solidon3d-auslieferung`). Dazu D2, D5,
D6, D7, D10; D11 und D12 jeweils nach den Komponenten der Klassen, die sie
berühren.

**Funde:** mit Art, Schwere und Beleg in die Funddatei des Konzepts. Schwer
sofort, mittel vor dem Ende der Phase, je eigene Commits; leicht als
Registerpunkt, spätestens in Phase 4. Am Ende jeder Phase kein Fund ohne Commit
oder Registerpunkt.

**Fertig** ist ein Konzept mit erfüllter Abnahme: Status in
`konzepte/README.md`, Nachweise und Funddatei unter `konzepte/`, Zustandsordner
unter `.claude/.state/` entfernt, eigene Worktrees und Zweige abgebaut.

**Arbeitsweise:** je Registerpunkt Test zuerst, betroffene Tests, ruff, format,
mypy; Review mit `solidon3d-review`, Funde beheben, bei mehreren mittleren oder
schweren Nachprüfung; Tor vor jedem Stand nach main; Merge, Commit, Push;
Agentenberichte sofort als Datei. Lokale Fenstertests nur, wo die Konzepte es
erlauben (Codestruktur-Oberflächenschritte: was `tools/ci_selection.py` für den
Diff nennt; Durchgang: je Fund die eine Datei). Neue Schätzungen an Robert nach
D1 (Durchgang) und nach Schritt 4d (Codestruktur). Fragen nur bei Geld,
Veröffentlichung, Rechten, schwer Umkehrbarem oder einer Alternative größer als
das Konzept.

## Verlauf

- 12.10.2026, 07:45, Phase 1 gelandet: 0.6.1 (RM-734, RM-735) per
  `--no-ff` auf main und gepusht; kein Release, keine Version. Review in drei
  Durchgängen (Berichte örtlich unter
  `F:\3D Druck\output\review\rm-734-735-2026-10-11\`), achtzehn Funde, keiner
  schwer, alle behoben (`4fc557327`, `d330cb7f0`, `76faa9be7`; Tabelle im
  Konzept). Tor gepinnt auf `76faa9be7`: 28 120 bestanden, 137 übersprungen,
  Exit 0. Offen allein die Abnahme am echten Fenster beim Release (RM-213).
  Worktree `F:\sl-suche` und Zweig `061/suche-und-palette` werden nach dem
  Merge abgebaut. **Als Nächstes Phase 2, Schritt 1:** Funktionsdurchgang nach
  `LIESMICH.md` auf `origin/doc/funktionsdurchgang` ablegen (Konzept nach
  `konzepte/konzept-funktionsdurchgang-2026-10.md`, Berichte nach
  `konzepte/nachweise-funktionsdurchgang-2026-10/`, Indexzeile, RM-736 und
  RM-737 bis RM-749 ins Register — die Nummern sind auf origin/main frei),
  dann D0, dann Codestruktur Schritt 0.
- 12.10.2026, 05:45, Phase 1, angehalten auf Wunsch Robert (Wechsel in die
  Desktop-App): Changelog `## 0.6.1` in sechs Sprachen steht (`1543a076f`).
  **Offen vor main, in dieser Reihenfolge:** (1) Review mit `solidon3d-review`
  über `git diff origin/main...HEAD` im Worktree `F:\sl-suche` — der erste Lauf
  wurde ohne Bericht gestoppt, also neu starten; Bericht nach
  `F:\3D Druck\output\review\rm-734-735-2026-10-11\review.md`; (2) Funde
  beheben, bei mehreren mittleren oder schweren eine Nachprüfung; (3) volles
  Tor (`bash .claude/scripts/suite-getrennt.sh`, auf diesem i9 gepinnt über
  `start /affinity FFFFF0FF`, Ergebnis aus der Ausgabedatei, nicht aus `$?`),
  ruff, format, mypy; (4) vorher `git fetch` und, falls main weiter ist,
  origin/main erneut hereinmergen; (5) in `F:\3D Druck` auf main
  `git merge --no-ff origin/061/suche-und-palette`, Push; kein Release, kein
  Tag, keine Version; (6) Worktree `F:\sl-suche` und Zweig abbauen, Robert
  Bescheid geben; dann Phase 2. Das Tor vom 11.10. war rot nur durch die
  Maschine und den behobenen `test_orient.py`-Fund; das Frühtor vom 12.10.
  wurde mit dem Halt abgebrochen.
- 12.10.2026, Phase 1: „main steht“ (Robert). origin/main hereingeholt
  (`21d1407e4`), RM-734 und RM-735 im Register (`[~]`, offen die Abnahme am
  echten Fenster, RM-213), Konzept und Nachweise unter `konzepte/`,
  Zustandsordner entfernt. Als Nächstes Changelog `## 0.6.1`, Review, Tor,
  Merge nach main.
- 12.10.2026, Phase 1: RM-734 und RM-735 auf dem Zweig fertig und gepusht
  (bis `023c9c703`); die fünf Funde unterwegs sind behoben (Tabelle am Ende
  von `konzepte/konzept-suche-und-palette-2026-10.md`).
- 11.10.2026, Phase 1: RM-734 auf dem Zweig fertig (`ddd82fb9b`, `5ca7f94cb`),
  RM-735 in Arbeit (Suchfeld der Karte ersetzt die Befehlspalette). Nichts auf
  main. Einzelstand in `.claude/.state/rm-734-735/STAND.md`.
