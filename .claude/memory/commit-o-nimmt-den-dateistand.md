---
name: commit-o-nimmt-den-dateistand
description: "Der private Index hält fremde Dateien heraus, nicht den fremden Stand einer gemeinsamen — und die Zahl steht im eigenen Diff-Stat."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 33442ae8-b3cf-4eef-bce4-cf827af80603
  modified: 2026-08-30T13:12:35.865Z
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
