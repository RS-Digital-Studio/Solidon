---
name: parallele-sitzung-im-arbeitsbaum
description: In Solidon arbeiten manchmal zwei Sitzungen gleichzeitig im selben Arbeitsbaum — vor dem Commit die fremden Änderungen aussortieren
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 69995218-868b-4121-bed5-89d6c8688900
  modified: 2026-08-21T17:25:53.058Z
---

Am 21.08.2026 lief eine zweite Claude-Sitzung parallel im selben Arbeitsbaum
`C:\Users\rober\Documents\Solidon`. Arbeitsbaum **und** Git-Index sind dabei
geteilt: Die andere Sitzung committete zwischendurch, legte eigene Dateien in
den Index und änderte dieselben Dateien (`app/ui/dialogs.py`,
`app/ui/main_window.py`, `app/core/errors.py`, `tests/test_ui.py`, `ROADMAP.md`).

**Warum:** Ein `git add` nimmt dann fremde, halbfertige Arbeit mit, und ein
`git commit` ohne Pfadliste committet, was die andere Sitzung gerade vorgemerkt
hat. Einmal hätte ein Commit ihre neuen Dateien gelöscht, weil ihr Indexstand
älter war als der neue HEAD.

**Der schlimmste Fall ist eingetreten, zweimal:** Am Abend des 21.08.2026 haben
sich beide Sitzungen abwechselnd überschrieben (`fac701b` nahm 882 Zeilen aus
`840a557`/`3f44f21` zurück, `ac5ea69` daraufhin 1830 Zeilen aus `fac701b`).
Verloren war nichts — beide Commits lagen in der Ablage —, aber die Reparatur
kostete beide Sitzungen eine halbe Stunde, und sie machten sie doppelt.

**How to apply:** Vor dem Commit `git status --short` und `git diff --cached
--name-only` lesen und jede Datei zuordnen — fremde Themen haben eigene Wörter,
danach lässt sich grep-en. Dann:

- **Den Commit-Inhalt aus dem *aktuellen* HEAD bauen**, nicht aus einer Kopie,
  die vor einer Viertelstunde gelesen wurde. Zwischen Lesen und Schreiben
  committet die andere Sitzung.
- **`git diff HEAD --stat` vor dem Commit lesen und die Löschzahl prüfen.** Ein
  Commit, der nichts entfernen will und 882 Zeilen entfernt, ist ein
  Zusammenstoß. Das ist die eine Zahl, die den Fehler sofort zeigt.
- **Privaten Index benutzen:** `GIT_INDEX_FILE=<temp> git read-tree HEAD`, dort
  `git add`/`git update-index --cacheinfo`, dann `git commit-tree` und
  `git update-ref refs/heads/main <neu> <alt>` — **mit** dem alten Wert, denn
  dann bricht es ab, wenn HEAD zwischenzeitlich gewandert ist. Genau das hat
  einen dritten Zusammenstoß verhindert.
- **Geteilte Dateien trennen**, indem die Fassung „HEAD + nur meine Änderung"
  gebaut wird. Richtung nach der kleineren Änderung: ist meine klein, von HEAD
  aus aufbauen; ist die fremde klein, sie aus der Arbeitsbaumfassung entfernen.
- **Einen Zusammenstoß mit Git auflösen, nicht von Hand.** Der echte gemeinsame
  Vorfahre steht im Graphen falsch (die fremde Fassung hat einen jüngeren
  Elternteil, als ihr Inhalt hergibt). Also einen Hilfscommit bauen —
  `git commit-tree <ihr-tree> -p <echter-vorfahre>` — und dann
  `git merge-tree --write-tree <mein-commit> <hilfscommit>`. Beim Zusammenstoß
  vom 21.08. lief das **ohne einen einzigen Konflikt** durch, weil die zwei
  Arbeiten in verschiedenen Verzeichnissen lagen.
- **Nachweis führen:** `git worktree add --detach <temp> <commit>` und die
  betroffenen Tests dort fahren — der committete Stand ist eine Kombination,
  die im gemeinsamen Arbeitsbaum so nie gelaufen ist. `python -m pytest` mit
  dem Interpreter des Hauptbaums und `cwd` im Worktree; `tools/run_suite_isolated.py`
  geht dort nicht, es sucht `.venv` relativ.
- **Rote Tests zuordnen:** dieselben Tests am Commit *vor* dem eigenen fahren.
  War es dort schon rot, gehört es der anderen Sitzung.
- **Abstürze ohne Ausgabe sind meist keine Funde.** Exit `-1073740791`
  (0xC0000409) oder „cannot get C stack" nach „N passed" ist der bekannte
  Absturz beim Herunterfahren (offener Punkt in `ROADMAP.md`). Dieselbe Datei
  einzeln gefahren ist grün.
- **Der schnellste Nachweis für ein Messartefakt: derselbe Stand zweimal.** Am
  21.08. lieferten zwei Läufe von `tests/test_performance.py` am identischen
  Commit mit derselben `.performance.json` **3** und dann **4** rote Tests — und
  teils andere. Wer eine Regression vermutet, fährt also nicht den
  Vorgängerstand, sondern denselben Stand ein zweites Mal: Schwankt die Menge,
  ist es Last und kein Code. Das kostet eine Minute statt eines Worktrees.
- **`tests/.performance.json` mitkopieren** — und trotzdem nichts darauf
  gründen, solange die andere Sitzung rechnet. Am 21.08. fielen zehn
  Leistungstests, am selben Stand im zweiten Lauf keiner. Die Fehlermenge
  wandert; nur ein Lauf bei ruhiger Maschine sagt etwas.
- **Auch eine Messung veraltet.** Am 21.08. hatte ich sechs unübersetzte Sätze
  gemessen und alle sechs übersetzt — fünf davon hatte die andere Sitzung in der
  Zwischenzeit selbst übersetzt, und mein Eintrag hätte ihre Fassung
  überschrieben. Gegen HEAD neu gemessen war es genau einer. Vor dem Schreiben
  neu messen, nicht nur vor dem Prüfen.
- **Der Einsammler liest den Arbeitsbaum, nicht HEAD.** `python -m
  app.i18n.extract` nimmt damit die Oberflächentexte der anderen Sitzung mit in
  die Kataloge, und `tests/test_translations.py` meldet sie am eingecheckten
  Stand als verwaist. Nachziehen: extract im Prüf-Worktree laufen lassen und die
  fünf JSON-Dateien von dort als Patch übernehmen.

**Der schwerste Fehler ist der Index gegen ein veraltetes HEAD.** Am 21.08.
passierte es dreimal hintereinander: Mein Commit nahm 24 Dateien der anderen
Sitzung zurück, ihr nächster nahm dafür alle 16 meinen, mein darauf folgender
wieder zwei von ihnen. Ursache jedes Mal dieselbe — `GIT_INDEX_FILE` gegen
`HEAD` gebaut, dann eine halbe Stunde Beweislauf, und beim `git commit` stand
`HEAD` zwei Commits weiter. Der Index kennt die neuen Commits nicht, also
schreibt er sie zurück, und `git commit` warnt dabei mit keinem Wort.

**Reihenfolge, die das verhindert:** Beweislauf am *Inhalt* fahren (eigener
Worktree, Patches drauf, Tests) — und danach den Index **neu** gegen den
aktuellen `HEAD` bauen und im *selben* Bash-Aufruf committen. Zwischen
`read-tree` und `commit` darf nichts liegen, was Minuten kostet.

**Und der härtere Grund für „derselbe Aufruf": `GIT_INDEX_FILE` überlebt den
Bash-Aufruf nicht.** Jeder Aufruf ist eine eigene Shell; die Variable ist im
nächsten weg, und Git nimmt dann still den Standard-Index. Am 22.08.2026 hat
die parallele Sitzung genau so zwei Commits leergeschrieben — die Umbenennungen
waren drin, sämtliche Inhaltsänderungen fehlten. Aufgefallen ist es an einer
Zahl: Die Ähnlichkeitswerte der Umbenennungen sprangen beim Amend von 94 % auf
**100 %**, und 100 % heißt „unverändert verschoben". Wer eine geänderte Datei
verschiebt und 100 % liest, hat seinen Index verloren. Nach jedem Commit mit
privatem Index prüfen, ob der Inhalt wirklich drinsteht (`git show --stat`),
statt es anzunehmen. Danach
`git log --format="%h ← %p" -1` lesen: Ist der Parent nicht der `HEAD`, den man
gebaut hat, ist Arbeit gefallen.

**Reparieren geht verlustfrei und ohne History-Umschreiben:** Die fremden
Dateien liegen in ihrem eigenen Commit. `git rev-parse <ihrCommit>:<datei>`
gibt den Blob, `git update-index --cacheinfo` legt ihn in einen privaten Index,
ein Commit darauf stellt sie wieder her — kein `reset`, kein `revert`, und der
Arbeitsbaum bleibt unberührt (er trug die fremde Arbeit die ganze Zeit weiter).
Bei Dateien, an denen beide gearbeitet haben, ihren Stand als Grundlage nehmen
und die eigene Änderung als `difflib`-Patch darauf anwenden.

**Nach dem Commit mit privatem Index gehört ein `git reset` hinterher — ohne
Pfade, ohne `--hard`.** Am 22.08.2026 hat ein sauberer Commit über
`GIT_INDEX_FILE` den *geteilten* Index vergiftet zurückgelassen: HEAD wanderte
drei Commits weiter, der geteilte Index blieb stehen, wo er war, und zeigte
danach aktiv auf den alten Stand. `git status` meldete `MM`, und
`git diff --cached --stat` wollte 698 Zeilen Bauplan und 90 Zeilen Roadmap
**löschen**. Ein normales `git commit` der nächsten Sitzung hätte genau das
getan — die ganze Arbeit des Tages entfernt, unter einer fremden
Commit-Meldung. Der private Index schützt also den eigenen Commit, aber er
hinterlässt eine Falle für den nächsten. Zwei Zeilen verhindern es:
`git reset` setzt die Indexeinträge auf HEAD und rührt den Arbeitsbaum nicht
an; `git diff --cached` muss danach leer sein.

**Und: im geteilten Arbeitsbaum gibt es kein `git pull --rebase` vor dem
Commit.** Alle Sitzungen teilen `.git`, die Commits der anderen *sind* der
eigene HEAD — `git rev-parse HEAD origin/main` liefert zweimal dasselbe, es
gibt nichts zu holen, und bei schmutzigen Dateien bricht es ohnehin ab. Der Rat
gilt für getrennte Klone; hier führt er in die Irre.

Robert entscheidet, was mit fremden Änderungen passiert — nicht selbst
mitcommitten und nicht wegwerfen. Siehe [[git-identitaet-mitgeben]].
