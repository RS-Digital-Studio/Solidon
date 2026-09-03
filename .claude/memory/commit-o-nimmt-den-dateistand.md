---
name: commit-o-nimmt-den-dateistand
description: "Der private Index hält fremde Dateien heraus, nicht den fremden Stand einer gemeinsamen — und die Zahl steht im eigenen Diff-Stat."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 33442ae8-b3cf-4eef-bce4-cf827af80603
  modified: 2026-08-30T16:01:11.512Z
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

**Und dieser Weg altert wie jeder andere Zustand** — die Gestalt steht in
[[probe-worktree-altert]], hier nur der Anschluss: Ein Blob wird aus
`git show HEAD:<pfad>` gebaut, und dieses HEAD ist der von *jetzt*, nicht der
vom Sitzungsbeginn. Am 30.08.2026 hat ein Blob auf veraltetem Stand die fünf
Sprachkataloge um einen Eintrag zurückgesetzt, den der Quelltext längst
benutzte — fünf rote Übersetzungstests auf `origin`, und der Verursacher war
ein Commit, der selbst alles richtig gemacht hatte außer dem Zeitpunkt seiner
Vorlage. Also: `git show HEAD:` **unmittelbar** vor dem Bauen, und was der
Blob nicht kennt, prüft man am Diff gegen den aktuellen HEAD.

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


**Die Zähl-Gestalt, 30.08.2026 (3a, `b3cfd578`):** Der Guard prüfte die
**Zahl der Dateien** — zwei, wie angesagt — und den Umfang gar nicht. In
`main_window.py` standen 132 hinzugefügte Zeilen, die eigene Änderung maß
etwa die Hälfte; der Rest war 50s ungestagter Abtragen-Block, der
mitreiste. Bei den vier Commits davor war dieselbe Datei bewusst als Blob
aus HEAD gebaut worden, genau dagegen — diesmal nicht, weil „meine
Änderung ist dort die einzige" ungeprüft angenommen wurde.

**Eine Dateizahl ist keine Sollprobe, sondern eine Anzeige.** Sie stimmt
genau dann, wenn man die richtigen Pfade genannt hat — und das ist die
Frage nicht. Die Frage ist, was **in** den Dateien steht. Die Ansage muss
deshalb zwei Zahlen tragen: wie viele Dateien, und ungefähr wie viele
Zeilen je Datei. Weicht der Umfang ab, ist es fremder Stand, auch wenn die
Datei die richtige ist.

Zugute halten lässt sich nur die Reaktion: Der Umfang fiel unmittelbar nach
dem Commit auf, die Meldung ging sofort hinaus, und der Betroffene stand
gerade davor, den Widerspruch zwischen `--numstat 132/10` und einem leeren
`git diff` zu jagen. **Ein stiller Mitnahme-Commit ist der schlechteste
Fall** — der Betroffene sucht sonst später, warum sein Diff kleiner ist als
seine Arbeit.

## Der Schritt davor: die Board-Liste

Am 30.08.2026 ist mir dieselbe Sache noch einmal passiert, in der eigenen
Variante: `git update-index --add app/ui/viewport.py` nahm 3as
Beleuchtungsarbeit mit — rund 60 von 97 Zeilen. `update-index --add` nimmt den
Dateistand genauso wie `commit -o`; der private Index hält fremde **Dateien**
heraus, nicht den fremden Stand einer **gemeinsamen**.

Die erwartete Zahl hat es gefangen (35 erwartet, 97 gesehen) — aber erst
*nach* dem Commit. Davor hätte eine Sekunde gereicht:

> **`python tools/session_board.py list` vor dem Stagen**, nicht nur beim
> Ankommen. Dort steht, welche Dateien gerade jemand anderes hält. Für die
> baut man eine Blob-Fassung aus dem unmittelbaren HEAD plus den eigenen
> Zeilen; für alle übrigen genügt `update-index`.

Die Liste altert schnell — in sechs Stunden hatten fünf Sitzungen ihre Gebiete
mehrfach gewechselt. Sie beim Ankommen zu lesen und dann vier Stunden später
zu stagen, ist dasselbe wie sie nicht zu lesen.

**Am 31.08.2026 dieselbe Falle in einer Datei, die ich nicht auf der Liste
hatte: `.claude/memory/MEMORY.md`.** Ich hatte für `app/i18n/locales/` in
derselben Nacht dreimal sorgfältig das Blob-Verfahren gefahren — und dann
`git add .claude/memory/MEMORY.md` geschrieben, ohne hineinzusehen. Der Commit
nahm die Indexzeile einer Nachbarsitzung mit, deren Datei noch nicht committet
war: Die Zeile stand in HEAD, der Verweis zeigte ins Leere.

**Zwei Lehren, beide über die alte hinaus:**

- **`MEMORY.md` ist eine geteilte Datei wie die Kataloge und `ROADMAP.md`.**
  Sie liest sich wie „meine Notizen", aber jede Sitzung schreibt hinein. Wer
  eine Zeile einträgt, nimmt das Blob-Verfahren wie überall sonst.
- **Die Kettenregel fängt es nicht.** „Eigene Dateizahl gegen
  `git show --numstat HEAD`" fängt eine Datei zu viel — nicht eine **Zeile** zu
  viel in einer richtigen Datei. Bei den Katalogen hatte ich zusätzlich auf
  einen bekannten fremden Satz gegrept und deshalb null gemessen; hier nicht.
  Die Sollprobe muss den **Inhalt** prüfen, nicht die Zahl.

Und der Fall gehört zu [[benannte-falle-schuetzt-nicht]]: Diese Notiz hier
beschreibt die Falle seit einem Tag genau richtig, und ich bin in derselben
Sitzung hineingelaufen, in der ich drei Nachbarsitzungen davor gewarnt habe.

**Und `-o` nimmt keine Modusänderung mit.** Am 31.08.2026: `.githooks/commit-msg`
stand mit `100644` im Repository und lief auf Linux und macOS wortlos nicht.
`git update-index --chmod=+x` setzte den Modus im Index, `git commit -o -- <pfad>`
committete ihn nicht — `-o` nimmt den **Dateistand**, und der Inhalt war
unverändert. Der Commit ging durch, meldete Erfolg und enthielt die Datei nicht.

Das ist die gefährliche Gestalt: Er sah aus, als hätte er funktioniert. Ein
reiner Modus-Commit braucht den Index ohne `-o` (`read-tree HEAD`,
`update-index --chmod=+x`, `commit` ohne Pfadliste) — und danach `git show
--raw HEAD`, das den Moduswechsel als `:100644 100755` zeigt. Die Zeilenzahl
sagt dort nichts: Sie ist `0 0`.


## Vierter Fall, und diesmal ohne Ausrede (03.09.2026)

Diese Notiz nennt `git add <pfad>` ausdrücklich, sie nennt den Zweischritt, und
sie nennt seine Reihenfolge als „den ganzen Punkt". Ich habe sie am selben Tag
**zitiert** — einer Nachbarsitzung gegenüber, mit genau dieser Begründung, warum
sie ihre Datei erst nach meinem Commit anfassen soll. Zwei Stunden später ging
mein eigener Commit `eb979353` hinaus und nahm die Viewport-Arbeit einer
anderen Sitzung mit: `test_ui.py`, `main_window.py` und fünf Kataloge.

**Der Zweischritt lief zur Hälfte.** Ich habe `git diff --cached --stat` gelesen
— 405 Zeilen — und abgenickt. Eine Erwartung hatte ich nicht genannt. Genau
dafür steht der Satz oben da: *Wer erst die Zahlen liest, nickt den Istwert ab.*
405 sagt für sich nichts; „ich habe rund 250 gebaut" hätte den Unterschied
laut gemacht.

Zwei Sätze, die daraus folgen:

**Eine Regel, die man zitiert, ist nicht angewandt.** Das Zitieren fühlt sich
an wie Anwenden — man hat den Satz im Kopf, er war eben noch richtig, und die
eigene Lage sieht anders aus als das Beispiel darin. Verwandt mit
[[benannte-falle-schuetzt-nicht]], aber eine Stufe schärfer: Dort schützte der
Kommentar im Modul nicht, hier schützte die selbst geschriebene Notiz nicht,
nachdem sie zwei Stunden vorher aus dem eigenen Mund kam.

**Und der Zweischritt gehört ins Skript — und das Skript in den Aufruf.**
Solange die erwartete Zahl nur gedacht wird, gibt es keinen Moment, in dem sie
mit dem Istwert kollidiert; geschrieben kollidiert sie von selbst. Das ist der
Unterschied zwischen einer Anzeige und einer Prüfung.

Die zweite Hälfte des Satzes hat 3d-druck-7b noch am selben Tag ergänzt, und
sie ist die wichtigere: **Der Zweischritt steht längst im Skript.**
`.claude/skills/liefern/SKILL.md` führt ihn seit dem 31.08.2026 strenger, als
diese Notiz ihn beschreibt — wörtliche Sollprobe, Abbruch statt Bericht, die
ganze Kette in einem Shell-Aufruf und ein HEAD-Vergleich gegen das
Restfenster. Von alldem habe ich nichts benutzt: Ich habe aus dem Gedächtnis
committet, statt `/liefern` aufzurufen.

Damit ist es dieselbe Sache eine Ebene höher, dreimal hintereinander am selben
Tag: Die Notiz gelesen und nicht angewandt, die Notiz zitiert und nicht
angewandt, den Skill vorhanden und nicht aufgerufen. **Ein Werkzeug schützt
nur, solange man es zum Arbeiten ruft statt aus der Erinnerung an das zu
arbeiten, was darin steht.**

Die Diagnose gegenüber der Nachbarsitzung war dabei zuerst falsch: Ich habe ihr
geschrieben, die Notiz benenne das falsche Werkzeug (`-o` statt `add`), und
deshalb habe sie nicht gegriffen. Sie benennt beide. Eine Notiz für ungenau zu
erklären, die man nicht gelesen hat, ist die bequemere von zwei Erklärungen —
und sie hätte die Notiz verschlechtert.
