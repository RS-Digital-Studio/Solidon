---
name: commit-o-nimmt-den-dateistand
description: "Der private Index hält fremde Dateien heraus, nicht den fremden Stand einer gemeinsamen — und die Zahl steht im eigenen Diff-Stat."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 33442ae8-b3cf-4eef-bce4-cf827af80603
  modified: 2026-08-30T13:50:46.256Z
---

`git commit -o -- <pfad>` committet die Datei, **wie sie im Baum liegt** — samt
allem, was eine andere Sitzung darin ungespeichert stehen hat. Der private
Index (`GIT_INDEX_FILE`) schützt nur davor, dass fremde **Dateien** mitgehen.

Am 26.08.2026 in beide Richtungen zugeschnappt, innerhalb einer Stunde: Mein
Commit nahm 145 Zeilen aus `labels.py` mit, an denen 43 gerade schrieb; 46s
Commit nahm umgekehrt meinen `panels.py`-Eintrag mit.

**Why:** Der Schaden ist selten inhaltlich — HEAD war beide Male stimmig. Er
ist die Zurechnung, und schlimmer: eine **halbe** Einheit kann hinausreiten.
Meine 67 mitgenommenen `tr()`-Quellen machten `origin/main` rot, bis die
Kataloge nachkamen — ein Fenster, das der Urheber der Kataloge nicht geöffnet
hatte.

**Und die Regel gilt nicht dem Befehl, sondern der Frage. Am 30.08.2026 (5d)
ist sie mir genau daran durchgerutscht:** Ich habe nicht `commit -o` benutzt,
sondern `git update-index --add <datei>` in einem privaten Index — und
deshalb diese Notiz für nicht anwendbar gehalten. `update-index --add` nimmt
den Dateistand aber genauso; jeder Weg, der eine **Datei** in den Index legt,
tut es. Die Frage lautet nie „benutze ich `-o`?", sondern **„lege ich Zeilen
oder eine Datei ab?"**

Der Preis war höher als eine Zurechnung: Mitgereist sind zwei Rot-Proben einer
Nachbarsitzung, die auf ihren noch ungebauten Fix warteten. Damit standen zwei
rote Tests auf `origin/main` — dieselbe halbe Einheit wie oben, nur diesmal
von der Testseite her.

**Der Guard lief und hat mich nicht gehalten**, und das ist der Kern: Er zeigte
`69/4`, wo ich `35/3` gebaut hatte. Ich habe die Zahl gelesen und committet;
dass sie nicht stimmte, fiel mir erst danach auf. Der Zweischritt oben stand
da, ich habe nur seine Reihenfolge umgedreht.

> **Ein Guard ohne vorher genannte Erwartung ist eine Anzeige, keine Prüfung.**

Praktisch heißt das: Die erwartete Zahl gehört **aufgeschrieben**, bevor der
Befehl läuft — in die Ansage an die anderen, ins Skript, notfalls in eine
`echo`-Zeile darüber. Eine Erwartung, die nur im Kopf steht, wird von einem
Istwert überschrieben, ohne dass es auffällt.

**How to apply:** Vor jedem `-o`-Commit ein Zweischritt, und die Reihenfolge
ist der ganze Punkt: **erst die eigene Zahl ansagen** („ich lösche zwei
Zeilen, füge keine ein"), **dann** `git diff HEAD --numstat -- <pfade>`
dagegenhalten. Wer erst die Zahlen liest, nickt den Istwert ab. Bei zwei
gelöschten Zeilen schreit „145 insertions" schon beim Ansagen.

Und die Ansage zählt **Zeilen, nicht Dateien** — dasselbe gilt für
`git add <pfad>` auf privatem Index, das denselben Dateistand nimmt. Am
26.08.2026 ein drittes Mal zugeschnappt (`9869a090`): Die Kontrolle prüfte
„genau 1 Datei" und war erfüllt, während in derselben Datei 60 fremde
Zeilen lagen; die zu große Zahl bekam die bequeme Falscherklärung („der
Formatter war's"). Wenn der Istwert von der Ansage abweicht, ist die
Erklärung zu **belegen** (Diff ansehen), nicht zu erraten.

**Und die Kehrseite des Auswegs: Wer am Dateistand vorbei committet, zieht
den Arbeitsbaum nach.** `git hash-object -w` plus `update-index --cacheinfo`
schreibt eine Fassung in den Index, die es im Baum nie gab — richtig, um
fremde Zwischenstände draußen zu halten, und die Datei im Baum trägt danach
weiter den alten Inhalt. Am 26.08.2026 zugeschnappt: Ein so committetes
Löschen (`845e87a2`, toter Katalogschlüssel) kam beim nächsten Schreiben in
dieselbe Datei zurück, weil das Skript den **Baum** las. Gefangen hat es die
Ansage — vier Einfügungen statt der angesagten drei —, nicht der Zufall.

**Und die Rettung, die man dagegen baut, ist mit `-o` wirkungslos** — gemessen
von d1 am 27.08.2026, dreimal hintereinander vorbeigelaufen. Ein Blob, den man
mit `update-index --cacheinfo` in den privaten Index legt, wird von
`git commit -o` **überschrieben**: `--only` heißt „nimm den Stand genau dieser
Pfade", und dieser Stand ist die Datei auf der Platte. Blob-Verfahren und `-o`
schließen sich aus; wer beides kombiniert, glaubt sich doppelt gesichert und
ist es gar nicht.

Schlimmer war die Kontrolle davor: `git diff --cached HEAD --numstat` gab
jedes Mal genau die angesagte Zahl — und stimmte auch, **für den Index**.
Committet wurde der Baum. Eine Prüfung, die gegen die eigene Annahme läuft,
bestätigt sie, statt sie zu prüfen ([[messwerkzeug-misst-sich-selbst]]).

Der Weg, der hält: Blob in den privaten Index legen und `git commit` **ohne**
`-o` — nach `git read-tree HEAD` steht der Index auf HEAD, was man
hineinlegt, ist genau die eigene Änderung, und `git commit` nimmt den Index
als Baum. Und die einzige Prüfung, die etwas taugt, ist die **nach** dem
Commit: `git show <commit> --numstat`. Nicht `--cached`, nicht `diff HEAD`.

Ist es passiert: History stehen lassen. Zuerst prüfen, ob eine halbe Einheit
hinausgeritten ist — das ist dringender als die Zurechnung —, dann den
Besitzer benachrichtigen, dann die Zurechnung im eigenen Folge-Commit
geradeziehen. Ausführlich in [[was-die-suite-nicht-findet]] benachbart; die
Regel steht in `.claude/rules/tests.md`.

**Und die Ansage muss je Datei stehen, nicht als Summe** — am 29.08.2026 von
ce zugeschnappt, obwohl diese Notiz „Zeilen, nicht Dateien" bereits sagte und
`git add <pfad>` bereits nannte. Die Sollprobe lautete „24 Dateien, kein
fremder Pfad", und beides stimmte: 24 Dateien, die Namensliste gegen ein
Muster gefiltert blieb leer. In der Zeile darunter stand
`app/ui/main_window.py | 41 ++++`, wo drei zu erwarten waren — vier fremde
Hunks einer Sitzung, die zwischen Messung und `git add` in dieselbe Datei
geschrieben hatte. Sie ritten mit hinaus und machten HEAD bei
`ruff format --check` rot.

Eine Gesamtsumme verschluckt den Ausreißer: 171 Einfügungen über 24 Dateien
lesen sich plausibel, gleich ob eine davon 3 oder 41 beiträgt. Die Prüfung,
die trägt, hält **je Datei** den angesagten Wert gegen den Istwert — und die
Ansage dazu entsteht aus der eigenen Arbeit („zwei Hunks in main_window"),
nicht aus dem Diff.

**Der Zeitpunkt ist die zweite Hälfte.** Zwischen `git diff HEAD --numstat`
und `git add` liegen im geteilten Baum Minuten, und eine fremde Sitzung
schreibt in dieser Zeit. Wer vorher misst und danach staged, prüft einen
Stand, den er nicht committet — deshalb steht oben, dass nur `git show
<commit> --numstat` **nach** dem Commit etwas taugt. Ce hat sie nicht
gefahren und den Fund erst über einen `ruff format`-Lauf gegen HEAD gemacht.

**Die MEMORY.md-Gestalt, 30.08.2026:** Der Dateistand einer geteilten
Indexdatei kann **Verweise auf Dateien** mitnehmen, die es in HEAD nicht
gibt. Mein `MEMORY.md`-Commit trug 3as frische Indexzeile mit, während ihre
verlinkte `.md` untracked blieb — ein toter Link in HEAD, den erst ihr
nächster Commit schloss. Wer `MEMORY.md` committet, prüft die verlinkten
Ziele in einer Sekunde mit:

```
git ls-files --error-unmatch $(grep -oE '\(([a-z0-9-]+\.md)\)' \
    .claude/memory/MEMORY.md | tr -d '()')
```

Jede Datei, die der Befehl nicht kennt, ist entweder fremde ungelandete
Arbeit (Zeile herauslassen — Blob-Technik) oder die eigene vergessene
Neuanlage (Datei mitcommitten).

**Die Sitzungsstart-Gestalt, 30.08.2026 (53, `6c705a64`):** Noch älter als
ces „zwischen Messung und add liegen Minuten" — die Freiheits-Prüfung
(„labels.py steht bei niemandem im Status") stammte vom **Sitzungsstart**,
Stunden vor dem `update-index --add`. Dazwischen hatte 3a zwei Blöcke
geschrieben, und sie ritten mit hinaus: Quellen in HEAD, Kataloge nicht,
origin fünffach rot. Zwei Dinge trugen, eines nicht: Der Guard davor gab
`labels.py +36/−1`, wo die eigene Funktion ~29 Zeilen maß — und die Zahl
wurde als plausibel **abgenickt** statt gegen eine vorher notierte Ansage
gehalten (genau der Fehler aus dem Kopf dieser Notiz). Gefangen hat es der
**Probe-Worktree auf dem Commit-Stand** — der Baum war grün, nur der Commit
rot, und diesen Unterschied sieht kein Lauf im geteilten Baum. Also: Die
Freiheits-Prüfung läuft unmittelbar vor dem `update-index` (dieselbe
Kausalitäts-Regel wie beim Schloss: die Antwort muss den Befehl noch ändern
können), die Zeilen-Ansage steht **vorher notiert** da, und nach jedem
Commit mit Dateistands-Anteil läuft die Probe auf dem Commit — nicht auf
dem Baum.
