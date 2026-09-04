---
name: parallele-sitzung-im-arbeitsbaum
description: In Solidon arbeiten manchmal zwei Sitzungen gleichzeitig im selben Arbeitsbaum — vor dem Commit die fremden Änderungen aussortieren
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 69995218-868b-4121-bed5-89d6c8688900
  modified: 2026-08-26T18:33:46.591Z
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
  War es dort schon rot, gehört es der anderen Sitzung. **Und das gilt auch,
  wenn eine bekannte Absturzfamilie die bequeme Erklärung liefert** — die
  Familie erklärt den *Mechanismus*, nicht den *Auslöser*. Am 26.08.2026
  drei 139er als „wandernde VTK-Mine, kein Verdacht gegen den Commit"
  zugeschrieben; ces Gegenprobe (Stand davor: 73 passed, danach: rot 3/3)
  zeigte, dass seine zwei neuen Tests die Zusammensetzung gekippt hatten.
  Die Familien-Diagnose stimmte, die Freisprechung nicht — und nur die
  Gegenprobe trennt beides, für zwei Minuten Arbeitsbaum-Lauf.
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

**Nach dem Commit mit privatem Index gehört ein `git reset -- <eigene Pfade>`
hinterher — mit Pfaden, ohne `--hard`.** Am 22.08.2026 hat ein sauberer Commit über
`GIT_INDEX_FILE` den *geteilten* Index vergiftet zurückgelassen: HEAD wanderte
drei Commits weiter, der geteilte Index blieb stehen, wo er war, und zeigte
danach aktiv auf den alten Stand. `git status` meldete `MM`, und
`git diff --cached --stat` wollte 698 Zeilen Bauplan und 90 Zeilen Roadmap
**löschen**. Ein normales `git commit` der nächsten Sitzung hätte genau das
getan — die ganze Arbeit des Tages entfernt, unter einer fremden
Commit-Meldung. Der private Index schützt also den eigenen Commit, aber er
hinterlässt eine Falle für den nächsten. Zwei Zeilen verhindern es:
`git reset -- <pfade>` setzt diese Indexeinträge auf HEAD und rührt den
Arbeitsbaum nicht an; `git diff --cached` muss danach leer sein. **Warum die
Pfade nicht weggelassen werden dürfen, steht weiter unten** — ohne sie trifft
es die Vormerkungen aller anderen Sitzungen mit.

**Erst die Richtung feststellen, dann aufräumen — `git reset` ist nicht immer
richtig.** Am 23.08.2026 trug der geteilte Index bei elf Website-Dateien
`0.1.3`, während HEAD und Arbeitsbaum auf `0.1.4` standen; ein Commit ohne
Pfade hätte ein ausgeliefertes Release zurückgeschrieben und die Startseite auf
gelöschte Pakete zeigen lassen. In dem Baum arbeiteten sieben Sitzungen, und
eine hatte an denselben Dateien gearbeitet — `git reset` hätte auch ihre
Vormerkungen weggeworfen, falls sie neue gewesen wären. Die Prüfung, die das
entscheidet, ist zwei Zeilen lang und läuft je Datei:

    git diff --quiet HEAD -- <datei>          # Arbeitsbaum == HEAD?
    git diff --cached --quiet HEAD -- <datei> # Index == HEAD?

Ist der **Arbeitsbaum gleich HEAD und nur der Index anders**, ist der Index ein
Abbild eines älteren Arbeitsbaums — dann kann `git add <datei>` nichts
zerstören, denn der Inhalt, den es einträgt, ist bereits committet. Weicht der
**Arbeitsbaum** ab, liegt dort ungesicherte Arbeit, und weder `add` noch
`reset` sind ohne Rückfrage erlaubt.

**Und: im geteilten Arbeitsbaum gibt es kein `git pull --rebase` vor dem
Commit.** Alle Sitzungen teilen `.git`, die Commits der anderen *sind* der
eigene HEAD — `git rev-parse HEAD origin/main` liefert zweimal dasselbe, es
gibt nichts zu holen, und bei schmutzigen Dateien bricht es ohnehin ab. Der Rat
gilt für getrennte Klone; hier führt er in die Irre.

**Der private Index löst das Problem und erzeugt ein kleineres.** Wer mit
`GIT_INDEX_FILE` committet, rührt den geteilten Index nicht an — und der zeigt
danach für die gerade committeten Dateien noch auf den *alten* HEAD-Stand. Wer
dann ohne Pfade committet, rollt die frische Arbeit zurück. Am 24.08.2026 trug
der geteilte Index so bei 38 Dateien einen veralteten Stand; ein Commit ohne
Pfade hätte 1692 Zeilen entfernt, darunter zwei von Roberts Erinnerungen, die
unversehrt dalagen und als „gelöscht" gemeldet wurden.

**Aufgeräumt wird das mit `git reset -- <eigene Pfade>`, nicht mit `git reset`.**
Der Unterschied ist in einem Baum mit sechs Sitzungen der ganze Punkt: Ein
`reset` ohne Pfade setzt den *gesamten* geteilten Index auf HEAD und vernichtet
damit die Vormerkung jeder Sitzung, die gerade zwischen `add` und `commit`
steht. Mit Pfaden betrifft es genau die eigenen Dateien, und der Arbeitsbaum
bleibt in beiden Fällen unberührt.

**Und vorher messen, ob überhaupt etwas zu tun ist:**
`git diff --cached --stat HEAD` — leer heißt sauber, dann ist jeder Eingriff
reines Risiko ohne Nutzen. Am 24.08.2026 hatte eine andere Sitzung bereits
bereinigt; der pauschale Rat „ein `git reset` als letzter Schritt" hätte dort
nichts genützt und hätte schaden können. Auch ein gut gemeinter Rat wird beim
Weitergeben fester, nicht lockerer — siehe
[[messwerkzeug-misst-sich-selbst]].

**Wenn `git status` eine Datei meldet, die nachweislich identisch ist, ist der
stat-Cache kaputt — und dagegen hilft `git add`, nicht `reset`.** Am 24.08.2026
blockierten drei `app/examples/*.svg` einen Fast-Forward-Pull, obwohl `cmp` gegen
den HEAD-Blob keinen Unterschied fand. Die Reihenfolge, die das klärt, ohne zu
raten:

    git ls-files --eol -- <datei>      # i/lf w/lf  -> kein Zeilenenden-Problem
    git hash-object -- <datei>         # gegen  git rev-parse HEAD:<datei>

Sind beide Hashes gleich, weicht **kein Byte** ab; dann ist nur der
Zwischenspeicher aus Größe und Zeitstempel im Index verdorben.
`git update-index --refresh` und sogar `--really-refresh` scheitern in diesem
Zustand mit „needs update" und Exit 1 — sie sind also **kein** Gegenmittel, auch
wenn ihr Name das verspricht. `git reset -- <datei>` hilft ebenso wenig: Es setzt
den Eintrag auf HEAD, lässt den kaputten stat-Eintrag aber stehen.

Was wirkt, ist `git add` auf genau diese Pfade. Bei identischem Blob-Hash
schreibt das keinen neuen Inhalt, sondern nur einen frischen stat-Eintrag — und
`git diff --cached --stat HEAD` ist danach leer, es steht also nichts Gestagetes
da, das jemand versehentlich mitcommitten könnte. **Die Hash-Gleichheit ist die
Bedingung**, nicht ein Detail am Rande: Ohne sie stagt derselbe Befehl echte
Änderungen, und im geteilten Baum womöglich fremde.

Robert entscheidet, was mit fremden Änderungen passiert — nicht selbst
mitcommitten und nicht wegwerfen. Siehe [[git-identitaet-mitgeben]].

**Nachtrag 26.08.2026 — `-o` schützt nur vor dem Index, nicht vor dem Baum:**
`git commit -o -- <datei>` committet den ganzen **Dateistand des Baums**,
nicht die eigenen Zeilen. e65f1539 (Sitzung a2) nahm so die uncommittete
Schleier-Arbeit einer anderen Sitzung in `main_window.py` mit — und ließ
deren zweite Hälfte (`loading.py` mit den neuen Signalen) zurück: Der
gepushte HEAD baute daraufhin auf jeder anderen Maschine **kein Fenster
mehr**, und keiner der lokalen Torläufe sah es, weil der Baum die fehlende
Hälfte trug. Aufgefallen erst, als die bestohlene Sitzung ihre eigenen
Hunks im `git diff` vermisste.

**How to apply:** Vor einem Pfad-Commit in einer Datei, die auf einem
fremden Claim steht: `git diff -- <datei>` lesen und fremde Hunks dem
Besitzer zuordnen — sind welche da, erst absprechen (er committet zuerst,
oder man nimmt seine Hunks mit **Ansage** mit). Und nach jedem fremden
Commit in eigenen Dateien prüfen, ob die eigene Arbeit noch im Diff steht:
Fehlt sie dort, ist sie in dessen Commit — dann sofort die zugehörigen
Hälften (Signale, Tests, Gegenstücke) nachcommitten, bevor HEAD auf einer
anderen Maschine läuft.

**Zweiter Doppelfall am 26.08.2026, und die Zahl stand jedes Mal in der
eigenen Ausgabe:** bc92469a (ce, wollte 2 Zeilen aus `labels.py` löschen)
zeigte im eigenen `--stat` „145 insertions" — die 141 Zeilen einer fremden,
uncommitteten Satztabelle ritten mit, und der Push öffnete ein
Übersetzungs-Rot auf origin. Spiegelbildlich hatte 2b48f288 (46) zuvor ces
uncommitteten `panels.py`-Eintrag mitgenommen. Der private Index schützt
davor **nicht** — er hält fremde *Dateien* heraus, nicht den fremden Stand
einer *gemeinsamen* Datei.

**Der Handgriff mit Zahl:** Vor dem Commit die eigene Erwartung ansagen
(„2 Löschungen, 0 Einfügungen"), **dann** `git diff HEAD --numstat -- <pfade>`
lesen und vergleichen — in dieser Reihenfolge, sonst prüft man den Istwert
gegen sich selbst ([[sollwert-aus-dem-pruefling]]).

**Und numstat ist blind für alles, was nicht im Index steht.** Ein `-o`-Commit
nimmt nur verfolgte Dateien der Pfadliste: eine **gelöschte** Datei bleibt
liegen (`git add -u` fehlt), eine **neue** auch (`git add` fehlt) — und beides
sieht lokal richtig aus, weil der eigene Baum den Sollzustand trägt. Gemerkt
wird es erst in einem Klon ohne diesen Baum: der CI. Am 26.08.2026 zweimal an
einem Tag (ces liegengebliebene test_openscad-Löschung riss jede CI-Suite
beim Einsammeln; a2s 60 neue Handbuchbilder fehlten im Handbuch-Commit).
Zur Ansage gehören deshalb drei Glieder: numstat, `git status --porcelain |
grep "^ D"` (Löschungen), `grep "^??"` auf den eigenen Pfaden (Neues). Und wenn es passiert
ist: Zurechnung im Meldungstext des eigenen Folge-Commits geradeziehen
(History bleibt stehen), die Besitzerin sofort benachrichtigen, und prüfen,
ob der Ritt eine *halbe* Einheit hinausgetragen hat — die fehlende Hälfte
ist dann das Dringende, nicht die Zurechnung.

---

**Nachtrag 04.09.2026 — der private Index schützt nicht vor dem, was in der
genannten Datei steht.** Ich habe `app/ui/main_window.py` in einem Commit
genannt, korrekt mit privatem Index und ausdrücklichem Pfad. Die Datei trug
neben meiner Änderung die **halbe** Änderung einer anderen Sitzung: ihren
Aufruf `analysis_bar.show_problem(text, label, handler)`. Die Gegenseite in
`analysis_bar.py` blieb liegen, und damit war main kaputt — wer eine
Analysekarte auf einem Modell über 120 000 Dreiecken wählte, bekam einen
`TypeError` statt einer Meldung. Bei zehn von neunzehn echten Kundendateien.

**Why:** Der private Index löst ein anderes Problem — er verhindert, dass der
*veraltete Haupt-Index* fremde Dateien als gelöscht mitcommittet. Gegen fremde
ungestagete Arbeit **in einer Datei, die man selbst nennt**, hilft er nicht:
Git committet Dateien, nicht Zeilen, und `-o -- <pfad>` nimmt den ganzen
Arbeitsstand dieses Pfads.

**How to apply:** Vor jedem Commit im geteilten Baum `git diff HEAD -- <datei>`
über **jede** genannte Datei lesen und prüfen, ob wirklich nur das eigene
darinsteht. Das dauert Sekunden und ist die einzige Prüfung, die diesen Fall
sieht. Wer eine Datei anfasst, die eine andere Sitzung hält, sagt es vorher —
und wer eine gemeinsame Datei committet, sagt hinterher, was gelandet ist.

Und der Zwilling dazu am selben Tag: Der Haupt-Index stand auf **gelöscht** für
zwei Dateien, die es auf HEAD gibt und die auf der Platte liegen
(`perceive/relations.py`, `tests/test_relations.py`). Ein pfadloser Commit
hätte ein fremdes neues Modul samt Tests aus dem Stand genommen und über den
post-commit-Hook auf drei Maschinen geschoben. Gerichtet mit `git reset` —
nur den Index, keine Datei. Siehe [[geteilter-index-haelt-alten-stand]].
