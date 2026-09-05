---
name: geteilter-index-haelt-alten-stand
description: "Der geteilte Index kann einen Stand vor HEAD halten — dann zeigt git status fremde Arbeit an, wo der Arbeitsbaum identisch mit HEAD ist."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 7fe92054-2daa-4d76-92ed-67a2464096bd
  modified: 2026-08-27T18:21:14.263Z
---

`git status` zeigte am 27.08.2026 fünf Dateien als `MM` — ROADMAP.md,
`app/core/geom/difference.py`, `standards.toml`, `test_difference.py`,
`test_parts.py`. Gelesen als „eine Nachbarsitzung arbeitet gerade daran". War
es nicht: Der **Index** hielt einen Stand *vor* dem letzten Commit
(`7e5b1df6`), der Arbeitsbaum war bei allen fünf **identisch mit HEAD**.

Erkennbar an der Symmetrie der beiden Diffs: `git diff --cached --stat` zeigte
278 Zeilen als gelöscht, `git diff --stat` genau dieselben 278 als hinzugefügt.
Das ist kein Doppelfund, das ist ein Index, der zurückliegt.

**Warum:** Wer dort `git commit` ohne privaten Index fährt, committet 278
Zeilen fremder Arbeit **als gelöscht** — und der Diff sieht aus wie eine
Aufräumung. Zwei Sitzungen sind an einem Tag darüber gestolpert, eine davon
hatte vorher `--numstat` gelesen und nur „plausible Zeilenzahlen" gesehen,
weil die Zahlen ja stimmen; falsch ist das Vorzeichen.

**Am 30.08.2026 dieselbe Sache in groß, und mit zwei Verschärfungen.** Der
Haupt-Index lag bei **95 Dateien** hinter HEAD, nicht bei fünf — ROADMAP.md mit
512 Zeilen, `handover.py` mit 210, `manual.py` mit 169, dazu alles, was eine
Stunde zuvor frisch committet worden war.

**Erste Verschärfung: `git diff --numstat` misst gegen den Index, nicht gegen
HEAD.** Das ist an einem gesunden Baum dasselbe und an einem alten Index nicht.
Ich habe an einem Nachmittag zweimal eine Zahl gemessen, sie „gegen HEAD"
beschriftet und einer anderen Sitzung gemeldet — 124/1 und 154/1, während die
Datei gegen HEAD 74/5 trug. Aufgefallen ist es erst, weil die Gegenseite eine
andere Zahl hatte und **die Minus-Seite nicht zusammenpasste**: Eine Datei, die
nur wächst, ändert ihre Minus-Seite nicht. Wer das nicht bemerkt, schreibt die
falsche Zahl in eine Commit-Meldung, wo sie stehenbleibt.

| Befehl | Vergleicht | Taugt für |
|---|---|---|
| `git diff --numstat` | Baum ↔ **Index** | nichts, solange der Index alt ist |
| `git diff --numstat HEAD` | Baum ↔ **HEAD** | jede Zahl, die man ansagt |
| `git diff --numstat --cached HEAD` | Index ↔ HEAD | den Schaden sichtbar machen |

**Zweite Verschärfung — und die Lehre daran ist nicht die, die ich zuerst
gezogen habe.** Vier Dateien lebten ausschließlich im Index, weder in HEAD noch
im Arbeitsbaum: `app/ui/command_band.py` (7 433 Bytes),
`tests/test_command_band.py` (3 414) und zwei Artefakte eines Betriebsreviews.
Ich las das als angefangene Arbeit, die jemand gestaget und im Baum verloren
hatte, sicherte alle vier aus dem Objektspeicher und meldete, hier brauche es
eine Entscheidung von Robert, bevor irgendwer aufräumt.

**Es war das Gegenteil.** Beide Dateien waren am selben Tag auf Roberts
ausdrücklichen Auftrag gelöscht worden:

```
git log --oneline --diff-filter=D -1 -- app/ui/command_band.py
  5d68c933 Das abgelehnte Befehlsband hinterließ ein Modul ohne Anschluss
  3350341f Eine Betriebsreview-Präsentation lag neben pyproject.toml
```

Die Index-Einträge waren Reste von **vor** diesen Lösch-Commits — genau das,
was ein alter Index eben enthält. Meine Rettung war folgenlos, meine Anfrage an
Robert überflüssig, und die Erzählung „ein Zwischenstand, den jemand angelegt
hat" war plausibel und ungeprüft.

Was bleibt, ist der Reflex ohne die Erzählung: **erst nachsehen, was nur im
Index lebt — und dann im Log fragen, warum.**

```
git diff --name-status --cached HEAD | grep ^A        ← was nur dort lebt
git log --oneline --diff-filter=D -1 -- <pfad>        ← wurde es absichtlich gelöscht?
```

Die zweite Zeile antwortet in einer Sekunde und entscheidet den Fall. Sichern
kostet nichts und schadet nie — aber es ersetzt die Frage nicht, und eine
Sicherung, die man für einen Fund hält, erzeugt Arbeit bei anderen.

**Dritte Beobachtung, selber Tag: Die Heilung ist keine einmalige.** Der
Haupt-Index altert nach **jedem** Commit-Schub erneut — wer ihn mittags mit
`read-tree HEAD` geheilt hat, findet ihn nach den nächsten zwei Commits wieder
zurückliegend. Bei **Binärdateien ohne diff-Attribut** sieht das im Stat wie
`-> 0 bytes`-Artefakte aus (sechs PNG „weichen ab", die byte-identisch mit
HEAD sind); der Textdiff hilft dort nicht, der **Blob-Hash-Vergleich**
entscheidet in Sekunden:

```
git hash-object <datei>                       ← Baum
git rev-parse HEAD:<pfad>                     ← HEAD
```

Gleicher Hash = Phantom, der Index ist alt. Vor der Heilung des Haupt-Index
weiterhin prüfen, ob echtes fremdes Staging darin liegt (siehe die Warnung im
liefern-Skill) — erst aussortieren, dann heilen.

**Und am 30.08.2026 die scharfe Gestalt davon: bei einer *neuen* Datei wird
aus dem alten Index eine vorgemerkte Löschung.** Nach einem Neustart standen
zwei frisch committete Erinnerungen so da:

```
D  .claude/memory/zufallsziehung-ist-keine-zuordnung.md   ← Index: Löschung vorgemerkt
??                    dieselbe Datei                       ← Baum: da, 44 Zeilen
```

Beide in HEAD, beide im Baum — und der nächste `git commit` **ohne Pfadliste**
hätte sie aus dem Repository entfernt.

**Die Ursache ist das private-Index-Verfahren selbst**, also genau das, was
dieses Projekt zum Schutz fremder Arbeit vorschreibt. Wer über
`GIT_INDEX_FILE` committet, bringt die Datei nach HEAD, ohne dass der
Haupt-Index je von ihr erfährt — belegt an einer Kopie des Index vor der
Reparatur: `git ls-files` auf die beiden Pfade antwortete leer. Eine Datei in
HEAD, die im Index fehlt, **ist** definitionsgemäß eine vorgemerkte Löschung.

Der Unterschied zum Fall oben ist der, auf den es ankommt:

| im Haupt-Index fehlt | Status | Folge eines pfadlosen Commits |
|---|---|---|
| eine **Änderung** an bekannter Datei | `MM` | Zeilen fallen zurück — sichtbar im Diff |
| eine **neue** Datei | `D ` + `??` | die Datei wird **gelöscht** |

**Nach jedem privaten-Index-Commit, der eine neue Datei anlegt**, deshalb eine
Zeile:

```
git diff --name-only --diff-filter=D --cached HEAD
```

Steht dort etwas, das gerade erst committet wurde, ist es diese Mine.
Entschärft wird sie mit `git reset -- <pfad>` — nur Index, Arbeitsbaum
unberührt. **Vorher** aber `git hash-object` auf Baum und HEAD vergleichen: Nur
wenn beide identisch sind, ist die Reparatur verlustfrei. Und `.git/index`
kopieren, bevor man ihn anfasst — er gehört allen Sitzungen, und die Kopie
beantwortet hinterher die Frage, wie es dazu kam.

**Und ein Werkzeug daneben verdeckt genau diesen Fall — mir am selben Tag
passiert.** Um zu trennen, welche `MM`-Dateien echte Arbeit tragen und welche
nur Index-Alterung sind, lief bei mir `git diff --quiet HEAD -- <pfad>` über
die Statusliste. Für die zwei **neuen** Dateien meldete es „identisch mit
HEAD", und damit hätte ich sie beinahe als unauffällig abgehakt — dieselben
zwei, die als Löschung vorgemerkt waren. In einem Wegwerf-Repo nachgestellt:

| Lage | `git diff --quiet HEAD -- <pfad>` | wahr ist |
|---|---|---|
| Datei gleich wie HEAD | Exit 0 | gleich |
| Datei **unversioniert** | Exit 0 | git kennt sie nicht |
| Datei **existiert gar nicht** | Exit 0 | es gibt sie nicht |

Drei Lagen, eine Antwort. Der Befehl kann die Frage für zwei davon gar nicht
stellen und sagt trotzdem „kein Unterschied" — dieselbe Familie wie
[[suche-prueft-ihre-eigene-trefferzahl]], nur mit einem Wahrheitswert statt
einer Trefferzahl. Wer versioniert-oder-nicht wissen will, fragt danach:
`git ls-files --error-unmatch <pfad>`.

**Vorbeugen ist derselbe Befehl wie Reparieren**, und er wirkt punktuell:
`git reset -- <die eigenen neuen Pfade>` **ohne** `GIT_INDEX_FILE`,
unmittelbar nach dem privaten Commit. Das setzt genau diese Einträge auf HEAD
und lässt jeden anderen in Ruhe.

**Die naheliegende größere Lösung — `git read-tree HEAD` auf den Haupt-Index —
beruht auf einer Annahme, die nicht hält:** „Wer mit privatem Index arbeitet,
hat im Haupt-Index ohnehin nichts stehen." Am 30.08.2026 gemessen, zweimal
dieselbe Frage: Am Abend lagen dort **vier** Einträge, die es nur dort gab
(`command_band.py`, `test_command_band.py`, zwei Präsentations-Artefakte); am
Morgen danach **keiner**. Die vier waren harmlos — Reste vor bewussten
Lösch-Commits —, aber das wusste man erst nach `git log --diff-filter=D`, und
ein pauschales `read-tree` fragt nicht. Nicht jede Hand am Baum benutzt einen
privaten Index: ein fremder Worktree, ein Codex-Lauf, Robert selbst.

**Wie anwenden:** Bevor man ein `MM` für fremde Arbeit hält, die eine Zeile
fahren, die es entscheidet:

```
for f in <pfade>; do git diff --quiet HEAD -- "$f" && echo "$f == HEAD"; done
```

Steht dort `== HEAD`, gehört die Datei niemandem — der Index ist alt. Aufräumen
mit `git reset -- <pfade>` (nur Index, Arbeitsbaum unberührt); danach prüfen,
dass der Arbeitsbaum unverändert ist.

**Pfadweise auch dann, wenn es wie Totalschaden aussieht.** Am 03.09.2026 stand
der Haupt-Index mit 131 Dateien und 12 305 Löschungen aus einem Stand von
dreieinhalb Stunden vorher da, und ich habe `git reset` **ohne** Pfade
gefahren — zweimal. Die Anweisung hier stand längst da. Die Zahl der falschen
Einträge ist kein Grund, die richtigen mitzunehmen: Wer 86 gestagte Einträge
wegwirft, nimmt jedem, der bewusst vorbereitet hat, seine Arbeit ab, und er
merkt es erst beim Commit. 3d-druck-7b hat es am selben Tag richtig gemacht und
genau die zwei falsch stehenden Pfade zurückgesetzt. Privater Index bleibt trotzdem Pflicht,
solange der Baum geteilt ist — siehe [[privater-index-fester-name]] und
[[commit-o-nimmt-den-dateistand]]. Verwandt:
[[parallele-sitzung-im-arbeitsbaum]], [[geteilter-baum-misst-zeitpunkt]].

## Und damit ist `git diff HEAD` kein Messinstrument mehr

Die Folgerung fehlte hier, und sie hat am 30.08.2026 abends eine halbe Stunde
gekostet. `git diff HEAD --numstat` meldete:

    0  207  app/core/geom/sketch_solid.py
    0  360  tests/test_sketch_solid.py

Beide Dateien waren **committet und vorhanden**, mit genau diesen Zeilenzahlen.
Der Haupt-Index führte sie als gelöscht, weil sie über private Indizes
entstanden waren — und `git diff HEAD` liest den Index mit. Daneben standen
Zahlen für fremde Dateien, die ebenso wenig stimmten.

**Wer im gemeinsamen Baum misst, misst mit einem eigenen Index:**

    GIT_INDEX_FILE=<eigener> git read-tree HEAD && git diff HEAD --numstat

Erst damit kamen plausible Zahlen — und erst darin war zu erkennen, dass 165
Zeilen in `main_window.py` und 79 in `tests/test_ui.py` fremde laufende Arbeit
waren. Zehn rote Tests hatte ich vorher der bekannten VTK-Familie zugeschrieben;
sie waren der halbe Bau einer Nachbarsitzung. Siehe
[[geteilter-baum-misst-zeitpunkt]] — die Regel gilt, aber sie nützt nichts, wenn
das Messgerät selbst verstellt ist.

**Den Haupt-Index dabei nicht heilen.** Ein `read-tree` darauf würde
Vormerkungen anderer Sitzungen wegwerfen. Der eigene Index kostet eine Zeile
und fasst nichts an.

---

**Am 31.08.2026 hat derselbe Index dreimal an einem Vormittag gelogen, und
zweimal davon nicht beim Committen, sondern beim *Zuordnen*.**

* Ein Guard, den ich gerade erst gebaut hatte, um fremde Arbeit vom Commit
  fernzuhalten, meldete **36 fremde Dateien, die es nicht gab** — darunter
  meine eigene `boerse.js` mit 27 Zeilen und `impressum.html` mit 16, beide
  längst gelandet. Hätte ich ihm geglaubt, hätte ich 36 Dateien liegen lassen
  und das Tor für alle rot.
* Eine Nachbarsitzung suchte den Urheber einer angeblich halbfertigen Änderung
  (`NAME_PATTERN` in `parts/registry.py`) und fragte **drei** Sitzungen. Alle
  drei sahen in ihrem eigenen `git diff` nach, fanden nichts und verneinten —
  richtig gemessen, falsche Quelle. Die Arbeit lag seit **acht Stunden** auf
  `origin`, in zwei Commits zwei Minuten auseinander. Beinahe wäre daraus ein
  „verwaister Punkt" im Protokoll geworden.
* Und beim Lesen derselben Frage zeigte mir `git diff` ein Feld als frische
  Zeile, das seit acht Stunden committet war.

**Die Lehre ist enger als „nimm einen eigenen Index":** Bei jeder Frage nach
*Herkunft* — wer hat das gemacht, ist das noch offen, gehört das mir? — ist
`git status`/`git diff` das falsche Werkzeug, weil es einen **Zustand**
beschreibt und keine **Geschichte**. Was die Frage wirklich beantwortet:

    git diff HEAD -- <pfad>              # ist es offen?
    git log -S '<das Symbol>' -- <pfad>  # wann kam es, in welchem Commit?

Das zweite ist sogar die bessere Antwort, denn es nennt Hash, Uhrzeit und
Commit-Meldung. Damit ist die Zuordnung ein **Beleg** statt einer Vermutung —
und sie funktioniert auch dann, wenn der Fragende und der Urheber verschiedene
Indexstände sehen.

Verwandt: [[verursacher-wird-gemessen-nicht-gelesen]] (dieselbe Bewegung:
nicht die naheliegende Anzeige lesen, sondern die Frage messen),
[[messung-galt-fuer-den-stand-davor]].


---

## Es gibt einen Beweis, und damit ist „nicht heilen" eine Frage statt einer Regel

Oben steht zweimal, `read-tree HEAD` auf den Haupt-Index sei zu grob, weil es
fremde Vormerkungen wegwirft — mit dem Fall vom 03.09.2026, an dem jemand
zweimal pfadlos zurückgesetzt und 86 gestagte Einträge mitgenommen hat. Der
Einwand ist richtig und er hat eine Lücke: Er sagt, man **wisse** nicht, ob
dort Arbeit liegt. Man kann es wissen.

    git write-tree                          # den Baum des Index schreiben
    git rev-parse <commit>^{tree}           # und gegen die letzten Commits halten

Ist der Index-Baum **bitgleich** mit dem Baum irgendeines Commits, enthält der
Index genau diesen Stand und keinen einzigen abweichenden Eintrag — dann ist er
reine Veraltung, und `read-tree HEAD` verliert nachweislich nichts. Weicht er
ab, steht dort etwas, das kein Commit hat: dann pfadweise, wie oben.

Am 04.09.2026 angewandt: Der Haupt-Index führte 2299 Löschungen über 30
Dateien, darunter zwei fremde Testdateien und zwei gerade committete eigene.
`git write-tree` ergab einen Baum, der mit dem von `31e08835` identisch war —
zwölf Commits alt und ohne eine einzige Vormerkung. Danach `read-tree HEAD`,
`git diff --cached` leer, nichts verloren.

**Why:** Ohne diesen Griff bleibt nur die Wahl zwischen zwei Fehlern — die Mine
liegen lassen (und irgendwer löscht später fremde Dateien, ohne dass ein Diff
es zeigt) oder pauschal heilen (und fremde Vorbereitung wegwerfen). Der
Baumvergleich beantwortet in zwei Sekunden, welcher der beiden Fälle vorliegt.
Er antwortet dabei **exakt**: Ein Baumhash deckt jeden Eintrag, jeden Modus und
jeden Pfad ab; es gibt kein „fast gleich".

**How to apply:** Vor jedem Eingriff am Haupt-Index den Baum schreiben und
gegen `git log --format=%H -20` vergleichen. Trifft er, heilen und es den
anderen Sitzungen **sagen** — sie sehen den Index nicht als ihren, aber sie
committen damit. Trifft er nicht, die abweichenden Pfade einzeln ansehen
(`git diff --name-status --cached HEAD`) und nur die eigenen zurücksetzen.
