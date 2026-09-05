---
name: fremder-zwischenstand-statt-repository
description: "Wer im geteilten Baum eine Frage über das Projekt beantwortet, misst leicht die unfertige Arbeit einer anderen Sitzung — die Antwort gilt dann für niemanden."
metadata:
  node_type: memory
  type: feedback
  originSessionId: b1dd44d4-c9b3-4917-8859-7f095e8dcd4b
  modified: 2026-09-04T15:05:41.624Z
---

Am 04.09.2026 hat Robert vier Registerpunkte zum Nachprüfen gegeben. Beim
vierten — „importierte Gewinde erzeugen weiterhin falsche Merkmale" — ergab
meine Messung im Arbeitsbaum: **ein Gewindemerkmal, null Phantome**, also
Punkt widerlegt. Falsch. `app/core/perceive/helix.py` war *untracked* und
`_threads_instead_of_phantoms` stand nicht in HEAD; ich hatte f9s
ungespeicherte Arbeit gemessen. Auf HEAD gemessen: M6 → zwei Zapfen, ein
Kegel, eine Kugel, kein Gewinde. Der Punkt stand.

Dieselbe Falle danach zweimal in anderer Gestalt: aus fremdem `$TEMP` einen
mypy-Fehler gelesen, den f9 eine halbe Stunde zuvor behoben hatte; und zwei
Lint-Befunde aus Hook-Meldungen weitergegeben, die beim Lesen schon erledigt
waren — eine andere Sitzung hätte darauf ihren grünen Torlauf für rot
gehalten.

**Why:** Die drei verwandten Notizen decken das nicht ab.
[[parallele-sitzung-im-arbeitsbaum]] warnt vor dem *Committen* fremder Arbeit,
[[temp-dateien-sind-maschinenweit]] vor *alten eigenen* Zahlen,
[[messung-galt-fuer-den-stand-davor]] vor der *eigenen* Messung nach einem
Umbau, und [[fremde-zwischenstaende-verfaelschen-messungen]] vor dem Lauf,
den fremde Arbeit **rot** macht — hier wird er **grün**. Hier ist das **Messobjekt** selbst fremd und unfertig: Die Messung ist
sauber, das Werkzeug richtig, die Zahl echt — sie gilt nur für einen Baum, den
es in keinem Repository gibt. Und sie fällt nicht auf, weil ein *besseres*
Ergebnis nach Fortschritt aussieht und nicht nach Fehler
([[bestaetigung-verstaerkt-die-fehlannahme]]).

**How to apply:** Eine Frage über *das Projekt* wird auf HEAD beantwortet, in
einem eigenen Baum: `git worktree add --detach <pfad> HEAD`, dort
`git status --short` (muss leer sein), dann messen — und hinterher wieder
entfernen ([[worktrees-enden-auf-main]]). Vor jeder Aussage „das ist behoben"
prüfen, ob die Behebung überhaupt in HEAD steht (`git show HEAD:<datei> | grep`
oder `git status --short` auf Untracked). Wer einen Befund über *fremde*
Dateien weitergibt, schreibt die **Uhrzeit** dazu; hier altert er in Minuten.

**Und die schärfere Gestalt davon, gemessen von 3d-druck-11 am selben Tag:**
Ein Schreibvorgang ist kein Zeitpunkt, sondern ein **Fenster**. Werkzeuge, die
automatisch nach jedem Befehl laufen — Hooks, Formatierer, Linter —, treffen
es irgendwann und melden dann einen Befund über eine halb geschriebene Datei.
Der ist echt gemessen und trotzdem über nichts: `tools/make_video.py` galt
zweimal als unformatiert und war es nie; die Datei wurde seit dem
Schreibvorgang nicht mehr angefasst.

**Zwei Signaturen verraten es, ohne dass man nachmisst** — beide kann ein
Formatierer nicht erzeugen: ein Diff mit einer identischen `-`/`+`-Zeile, und
ein Diff, der mitten in einem Ausdruck abbricht. Ein halb geschriebener
Python-File ist nicht nur unformatiert, er ist syntaktisch kaputt, und jedes
Werkzeug in diesem Fenster meldet *irgendetwas*.

**Und aus einer Störung folgt nicht die Ungültigkeit.** Fremde Arbeit im Baum
entwertet den eigenen Lauf nur, wo die Dateimengen sich berühren. Sind sie
disjunkt und führt kein Importpfad von der einen zur anderen, ist das Ergebnis
eine gültige Aussage über die **eigenen** Dateien und keine über den Baum —
„Messung mit bekanntem blinden Fleck" statt „wertlos". Wer die Frage nicht
stellt, wirft eine gute Messung weg.
