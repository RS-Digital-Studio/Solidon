---
name: parallele-sitzungen-solidon3d
description: In F:\3D Druck laufen oft mehrere Claude-Sitzungen gleichzeitig — vor jedem Commit den Arbeitsbaum neu prüfen und nur eigene Pfade stagen.
metadata: 
  node_type: memory
  type: project
  originSessionId: 35e070f4-568e-44d1-b49c-f1362240ed35
  modified: 2026-08-14T06:23:09.363Z
---

Am 2026-07-31 hat eine parallel laufende Sitzung in `F:\3D Druck` mit einem
pauschalen `git add` committet und dabei die halbfertigen Dateien dieser
Sitzung (`CLAUDE.md`, `.claude/rules/`, `.claude/agents/`, `.claude/skills/`)
in ihre thematisch fremden Commits gezogen — `01e8582` und `82ffe26`.

**Warum:** Der Arbeitsbaum dieses Projekts kann sich mitten in einer Sitzung
unter den Füßen ändern; der `git status` vom Sitzungsstart ist nach wenigen
Minuten veraltet.

**How to apply:** Vor jedem Commit `git log --oneline -3` und `git status`
frisch lesen. Immer mit expliziten Pfaden stagen (`git add <pfad> ...`), nie
`git add .` oder `git add -A`. Fremde Änderungen im Baum bleiben stehen — kein
Stash, kein Reset, keine History-Korrektur ohne Rückfrage bei Robert.

Am 2026-08-01 bewährt, zwei Verschärfungen:

- **Hat die fremde Sitzung bereits gestaged** (`M ` in Spalte 1), committet ein
  nacktes `git commit` ihren ganzen Index mit. Dann `git commit --only <pfad>`
  benutzen — das committet den Arbeitsbaumstand nur dieser Pfade und lässt den
  fremden Index unberührt. Neue Dateien vorher per `git add <datei>` bekannt
  machen, `--only` nimmt sonst keine untracked Dateien.
- **Teilt man eine Datei mit der fremden Sitzung** (beide haben uncommittete
  Hunks darin), einen Mini-Patch nur mit den eigenen Zeilen schreiben und mit
  `git apply --cached --recount -C3 patch` stagen. Sind die eigenen Zeilen mit
  fremden im selben Hunk verschränkt, den Patch von Hand gegen `git show
  HEAD:<datei>` bauen statt aus `git diff` zu filtern.
- Zwei Suiten gleichzeitig auf dieser Maschine reißen die Leistungsmessungen
  (`test_performance.py`) — rote Zeit-Tests erst nach einem Wiederholungslauf
  ohne Fremdlast glauben.

Am 2026-08-04 zweimal trotzdem passiert (`d5936bb`, `5bad0bd`): eigene Pfade
sauber per `git add` gestaget, dann nacktes `git commit` — und der vorbelegte
fremde Index ging mit. `git add <meine pfade>` schützt **nicht**; es fügt nur
hinzu. Deshalb ausnahmslos:

```
git add <neue eigene dateien>   # nur falls untracked
git commit --only <pfad> <pfad> ... -F -
```

Am 2026-08-06 die umgekehrte Richtung, und sie ist schlimmer: die eigenen
Pfade lagen sauber im Index (inklusive eines gefilterten Mini-Patches für die
geteilte `main_window.py`) — dann committete die **fremde** Sitzung mit `git
add -A`, bevor der eigene `git commit` lief, und zog den fertigen eigenen Index
in ihren thematisch fremden Commit `c62917c`. Der eigene `git commit` fand
danach „no changes added to commit".

**Warum:** Nicht nur der Arbeitsbaum ist geteilt, der **Index ist es auch**.
Jede Sekunde zwischen Stagen und Committen ist ein Fenster, in dem eine fremde
Sitzung den eigenen Index mit übernimmt. `--only` hilft dagegen nicht, wenn der
andere zuerst dran ist.

**How to apply:** Nie einen Index stehen lassen. Stagen und Committen gehören
in **einen** Aufruf — `git commit --only <pfad> ... -F -` erledigt beides ohne
Fenster. Muss doch vorher gestaged werden (gefilterter Patch via `git apply
--cached`), unmittelbar danach committen, ohne Testlauf oder Prüfung
dazwischen; die laufen vorher. Ist es passiert: **nicht** per Rebase oder
Amend korrigieren — der Inhalt ist vollständig in der Historie, nur unter
falschem Titel, und die fremde Sitzung baut schon darauf auf. Robert
berichten und es dabei belassen.

Am 2026-08-08 erneut, und der Fehler war eine Aufräumaktion: eigene Hunks per
gefiltertem Patch in den Index, dann `git status`, dann `git restore --staged`
für die fremden Pfade, die die andere Sitzung inzwischen vorbelegt hatte — in
genau diesem Fenster committete sie mit allem, auch der fertigen Ladeanzeige
(`22ce4c6`).

**How to apply:** Fremde Pfade **nicht** aus dem Index nehmen. Jeder Befehl
zwischen Stagen und Committen ist das Fenster, auch ein `git status` und
besonders ein `git restore --staged`. Liegt fremdes im Index, ist
`git commit --only <eigene pfade> -F -` die einzige Antwort — es ignoriert den
fremden Index, ohne ihn anzufassen. Bei einer geteilten Datei: Patch mit
`git apply --cached` stagen und **im selben Aufruf** committen (`&&`).

Robert sagt auch dann „es gibt keine parallele Sitzung mehr", wenn eine läuft —
er meint die, von der er weiß. Der `git status` entscheidet, nicht die Ansage.
Der Prozessliste ebenso: mehrere `claude`-Prozesse mit hoher CPU-Zeit sind der
verlässlichste Hinweis, dass gerade jemand mitschreibt.

Am 2026-08-13 eine **andere Art von Kollision**, die keine Index-Regel abfängt:
nicht der Commit war betroffen, sondern der **Inhalt einer Datei, auf die
laufende Arbeit sich bezieht**. Während acht Agenten die vier neuen Sprachen
übersetzten — Teildateien, die Katalogeinträge über ihren **Index** ansprechen —
hat die parallele Sitzung `app/i18n/locales/en.json` um fünfzehn Schlüssel
erweitert (2264 → 2279). Die Schlüssel werden einsortiert, die erste Einfügung
lag bei Index 7, also verschob sich alles darüber; die Verschiebung wächst über
den Bestand von +6 auf +15 und ist damit nicht einmal pauschal herausrechenbar.
Vier der acht Agenten haben es selbst gemerkt, einer hat einen ganzen
Sprachordner eigenmächtig umnummeriert.

**Warum:** Positionsbezüge auf eine Datei, die eine andere Sitzung schreibt,
sind nur so lange gültig, wie niemand etwas einfügt. Der eigene Code muss davon
gar nichts wissen — es genügt, dass er *zählt*, wo er *benennen* könnte.

**How to apply:** Bezieht sich eine längere Arbeit auf eine Datei im
Arbeitsbaum, zuerst eine **eingefrorene Kopie** anlegen (`git show HEAD:<datei>`)
und alle Werkzeuge darauf zeigen lassen — nicht auf das lebende Original. Was
danach dazukommt, über den **Schlüssel** nachtragen, nie über die Position. Bei
verteilter Arbeit gehört die eingefrorene Basis in den Auftrag jedes Agenten,
sonst löst jeder das Problem anders. Und: Agenten, die einen gemeinsamen Bestand
anfassen, ausdrücklich auf ihre eigenen Dateien begrenzen — „korrigiere den
Bestand" ist für acht Parallele keine Anweisung, sondern ein Wettlauf.

Am 2026-08-14 dieselbe Richtung wie am 08-06, aber **ohne eigenen Index** —
und deshalb von keiner Index-Regel oben abgefangen. Die eigene Änderung an
`app/ui/main_window.py` lag nur im *Arbeitsbaum*, während Tests und
Übersetzungen liefen; in diesem Fenster committete die fremde Sitzung die
Datei (`bc7b32b`, „Die Kante, an der die Karte aufhört …") und nahm sie mit.
`git add <datei>` nimmt den Arbeitsbaumstand, gleich wer ihn geschrieben hat.

**Warum:** `git commit --only` schützt den eigenen Commit vor fremdem Inhalt.
Es schützt nicht die eigene *ungespeicherte Arbeit* davor, in einem fremden
Commit zu landen — dagegen hilft nur, das Fenster kurz zu halten.

**How to apply:** Eine Änderung an einer **geteilten** Datei (`main_window.py`,
die Sprachkataloge, `ROADMAP.md`) so früh wie möglich committen — lieber ein
Zwischencommit als eine halbe Stunde Testlauf über einer offenen Datei. Die
lange Prüfung läuft danach; wird sie rot, wird vorwärts gefixt, was ohnehin
die Regel ist. Ist es passiert: Inhalt prüfen (`grep -c` auf die eigenen
Namen), Vollständigkeit feststellen, Robert berichten — **kein** Amend, kein
Rebase, die fremde Sitzung baut schon darauf auf.

**Und wer eine geteilte Datei fortschreibt, schreibt nicht „ich".** Am
30.08.2026 hat eine fremde Sitzung meine Memory-Blöcke mitcommittet und für
ihre eigenen Fortschreibungen gehalten — nicht aus Unachtsamkeit, sondern
weil sie als Ich-Erzählung im Baum lagen und in einem geteilten Baum kein „ich"
zuordenbar ist. Die Zuordnung ließ sich nachträglich klären (`grep -c` auf die
eigenen Formulierungen, zwei Commits benannt), aber sie kostete eine Runde.

Der Preis ist nicht die Ehre, sondern die **Prüfbarkeit**: Wer einen fremden
Befund für seinen eigenen hält, kann ihn beim Weitererzählen nicht mehr an
seiner Messung prüfen — und ergänzt dann Details, die niemand gemessen hat
(siehe [[exakte-passung-ist-kein-beweis]]).

In einer Datei, die mehreren gehört, trägt deshalb jeder Befund sein **Datum**
und, wo es zählt, die Sitzung, die ihn gemessen hat: „Gemessen am 30.08.2026
(5d): …". Die Erzählung im Ich bleibt richtig für alles, was nur eine Sitzung
betrifft — die Karten und Regeln in `.claude/rules/` etwa, wo ohnehin keine
Person spricht.
