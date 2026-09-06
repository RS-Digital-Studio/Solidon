---
name: commit-o-nimmt-den-dateistand
description: "Der private Index hält fremde Dateien heraus, nicht den fremden Stand einer gemeinsamen — und die Zahl steht im eigenen Diff-Stat."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 33442ae8-b3cf-4eef-bce4-cf827af80603
  modified: 2026-09-06T15:41:19.402Z
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

## Siebter und achter Fall: die Meldung stimmte, der Inhalt nicht (03.09.2026)

Zwei Commits an einem Abend, dieselbe Ursache, und beide sind an einer Stelle
vorbeigekommen, die diese Notiz schon beschreibt — weil eine **Fehlermeldung in
die falsche Richtung geschickt hat**.

`61588789` trug meine Changelog-Meldung und enthielt genau eine Datei:
`app/ui/viewport.py`, 76 hinzu, 37 weg — die Größenkorrektur des Bewegen-Griffs
einer Nachbarsitzung, zurückgebaut. Keine einzige meiner eigenen Dateien war
darin. Der Baum kam aus meinem Index (`read-tree` auf einen HEAD von vorhin),
der Elternteil war der inzwischen weitergewanderte HEAD; alles dazwischen steht
damit als Rücknahme im Commit.

**Warum ich es nicht gemerkt habe, ist der eigentliche Fund.** Der Aufruf endete
mit

    fatal: cannot lock ref 'HEAD': is at 61588789 but expected d3b6b973

und ich habe das als „der Commit ist nicht zustande gekommen" gelesen. Er war da
und das Ref gesetzt; die Meldung kam von einem zweiten Schritt danach. Das ist
dieselbe Gestalt wie der abgebrochene Merge in `.claude/skills/liefern/SKILL.md`
— **ein Eingriff, kein Nichts** —, und sie ist gefährlicher als eine Meldung,
die einen ratlos lässt: Sie gibt eine Antwort, und die ist falsch.

> **Ein Fehlschlag am Ref ist kein Fehlschlag am Commit.** Nach jedem Aufruf,
> der mit `cannot lock ref` endet, gehört `git log -1` gefragt — nicht
> geschlossen.

Der achte Fall kam zwei Stunden später und zeigt, dass die Probe danach nicht
genügt, wenn sie das Falsche fragt. `050ecca7` trägt die Meldung „0.3.2 ist
aufgemacht" und enthält den Abschnitt **nicht**: wieder der Unterschied zweier
fremder Stände, diesmal drei Dateien, die mir nicht gehören. Meine Probe hatte
gefragt, ob HEAD meine Meldung trägt — und sie tat es.

> **Die Probe danach fragt nach den eigenen Dateien, nicht nach der eigenen
> Meldung.** Eine Meldung kann richtig auf einem falschen Inhalt stehen.

Praktisch, und beides zusammen in einer Schleife, weil bei acht Sitzungen im
Baum der Hook ein bis zwei Minuten läuft und in dieser Zeit regelmäßig jemand
committet:

    for i in 1 2 3 4 5; do
      export GIT_INDEX_FILE=/tmp/idx_$i
      git read-tree HEAD || continue
      git add -A -- $PATHS || continue
      git commit -F "$MSG" >/dev/null 2>&1
      DRIN=$(git show HEAD --numstat --format="" | awk '{print $3}' | grep -c "^<eigene datei>$")
      [ "$DRIN" = "1" ] && break
    done

Beim dritten Anlauf saß es. Die zwei davor haben nichts kaputtgemacht, weil die
Prüfung sie als Fehlschlag erkannt hat — genau dafür ist sie da.

**Und die Zurechnung ist damit nicht erledigt.** Eine irreführende Meldung im
Verlauf bleibt stehen; korrigiert wird sie im Folge-Commit, nicht durch
Umschreiben. `f15e10f9` sagt deshalb im ersten Satz, was `050ecca7` nicht
enthält.

## Neunter bis zwölfter Fall: die Prüfung fragte HEAD statt sich selbst (03.09.2026)

Vier Fehlgriffe in zwei Stunden, alle mit privatem Index und `read-tree`, alle
bei sorgfältiger Anwendung dieser Notiz. Betroffen waren `viewport.py` einer
Nachbarsitzung, `test_prepare.py` mit 33 Zeilen und — beim **Reparieren** dieser
33 Zeilen — vier weitere Dateien mit zusammen rund 111 Zeilen.

**Das ist kein Bedienfehler mehr.** Der pre-commit-Hook läuft in diesem Baum ein
bis zwei Minuten, und bei acht gleichzeitigen Sitzungen committet in dieser Zeit
fast immer jemand. Das Fenster zwischen `read-tree` und dem geschriebenen Commit
ist damit strukturell offen; wer es durch schnelleres Arbeiten schließen will,
verliert das Rennen gegen sieben andere.

**Die Prüfung danach hat trotzdem versagt, und zwar an zwei verschiedenen
Stellen — beide sind eigene Sätze wert.**

> **Sie fragt den eigenen Commit-Hash, nicht HEAD.** HEAD sagt, was zuletzt
> passiert ist; der eigene Hash sagt, was **ich** getan habe. Eine Schleife, die
> `git show HEAD --numstat` liest, prüft bei einem gescheiterten eigenen Commit
> den Commit einer Nachbarsitzung — und findet ihn sauber. Dreimal so
> abgenickt.

> **Und sie stellt beide Fragen, nicht abwechselnd eine.** „Steht meine Datei
> drin?" schützt mich, „steht sonst nichts drin?" schützt die anderen. Ich habe
> sie an zwei aufeinanderfolgenden Commits abwechselnd gestellt und jedes Mal
> die andere Hälfte verloren: einmal meine Datei plus vier fremde, einmal keine
> fremde und meine auch nicht.

**Der zwölfte Fall gehört 3d-druck-81 und ist die Falle in der Reparatur
selbst:**

    for i in 1 2 3; do git read-tree HEAD && git commit ... | tail -2 && break; done

Der Commit scheiterte an `cannot lock ref`, `tail -2` gelang, `&&` sah einen
Erfolg, `break` brach ab. **Die Pipeline verschluckt den Fehler** — dieselbe
Falle, die `CLAUDE.md` für Testläufe an erster Stelle nennt, hier in eine
Wiederholschleife eingebaut, die genau davor schützen sollte.

Die Kette, die getragen hat, in einem Stück:

    for i in 1 2 3 4; do
      export GIT_INDEX_FILE=/tmp/idx_$i
      BEFORE=$(git rev-parse HEAD)
      git read-tree HEAD || continue
      git add -A -- "$DATEI" || continue
      git commit -F "$MSG" >/dev/null 2>&1        # kein Pipe
      NEU=$(git rev-parse HEAD)
      [ "$NEU" = "$BEFORE" ] && continue          # gar nichts entstanden
      case "$(git log -1 --format='%s')" in "Mein Betreff"*) ;; *) continue;; esac
      MEIN=$(git show $NEU --numstat --format="" | awk '{print $3}' | grep -c "^$DATEI$")
      FREMD=$(git show $NEU --numstat --format="" | awk '{print $3}' | grep -vc "^$DATEI$")
      [ "$MEIN" = "1" ] && [ "$FREMD" = "0" ] && break
    done

Vier Prüfungen, und jede fängt einen anderen Fall: Ist überhaupt etwas
entstanden, ist es meines, ist meine Datei darin, ist sonst nichts darin.

**Und die Lehre über der Lehre:** Drei der vier Fälle haben Nachbarsitzungen
zurückgeholt, bevor Schaden entstand — weil sie gemeldet wurden. Ein stiller
Mitnahme-Commit ist der schlechteste Fall (siehe oben); an diesem Abend haben
vier Sitzungen ihre eigenen Fehlgriffe gemeldet, und deshalb steht der Baum
vollständig da.

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


## Fünfter Fall: die Kette stimmte, die Prüfung nicht (03.09.2026, zwei Stunden später)

`56c2a559` nahm zwei Registerpunkte einer Nachbarsitzung mit — und diesmal lief
**alles richtig, was beim vierten Fall falsch gelaufen war**: die ganze Kette in
einem Aufruf, `read-tree HEAD`, ein HEAD-Vergleich unmittelbar vor dem Commit.
Der Index war keine Sekunde alt.

**Er war auch nicht das Problem.** `git add -- ROADMAP.md` nimmt den
Dateistand, und in der Datei lagen zwei fremde Absätze, die zwei Minuten vorher
dazugekommen waren. Die Kette in einem Aufruf schützt gegen einen alternden
Index; gegen den Dateistand schützt sie nichts.

Was dagegen geschützt hätte, stand im selben Befehl — als `echo`:

    IST=$(git diff --cached HEAD --numstat) && echo "gemessen: $IST" && …commit

85 Zeilen für einen Registerpunkt sahen plausibel aus. Sie waren es auch — nur
gehörten davon rund vierzig jemand anderem. **Eine Zahl ohne vorher genannte
Erwartung ist eine Anzeige und keine Prüfung**, und dieser Satz steht seit dem
30.08.2026 in dieser Notiz, drei Absätze weiter oben.

Daraus die vollständige Regel, weil jede Hälfte für sich nicht reicht:

| Gefahr | Gegenmittel |
|---|---|
| Der Index altert zwischen zwei Aufrufen | die ganze Kette in **einem** Aufruf |
| Die Datei trägt fremde Zeilen | die **Sollprobe mit vorher genannter Zahl** |
| Ein Blob trägt den Stand seines Zeitpunkts | `git diff` **vor** dem Zurückschreiben |

Und für die drei Dateien, an denen jede Sitzung anhängt — `ROADMAP.md`,
`MEMORY.md`, die fünf Sprachkataloge — gibt es einen Weg, der alle drei
Gefahren zugleich umgeht: **die eigene Änderung als Skript schreiben und auf
`git show HEAD:<datei>` anwenden**, dann den Blob hashen und in den Index
legen. Was dabei entsteht, ist HEAD plus die eigene Änderung und sonst nichts —
unabhängig davon, was im Arbeitsbaum liegt. `katalog_blobs.py` aus dieser
Sitzung ist die Vorlage; an den Katalogen hat es zweimal getragen, an
`ROADMAP.md` habe ich es nicht angewandt und prompt den fünften Fall gebaut.


## Sechster Fall: `read-tree` im Aufruf davor, und die Zahl stand in einem `echo` (03.09.2026)

`7f7ad380` löschte 150 Zeilen Viewport-Arbeit — 83 in `app/ui/viewport.py`, 67
in `tests/test_viewport_decisions.py` —, und diesmal war **die ganze Kette
richtig gebaut**: privater Index, `read-tree HEAD`, eine Sollprobe mit vorher
genannter Zahl, und die Sollprobe stand im selben Aufruf wie der Commit.

Nur lief `read-tree` im Aufruf **davor**. Dazwischen committete eine andere
Sitzung. Damit zeigte der Index einen HEAD, den es nicht mehr gab, und
`git diff --cached HEAD` rechnete gegen den neuen: Alles, was der neue HEAD
trug und der Index nicht, stand als **Löschung** im Commit.

**Und die Zahl stand auf dem Schirm.** Soll war „8 Dateien, 123 Einfügungen, 3
Löschungen", ausgegeben wurde „10 Dateien, 123, 153". Sie stand in einem
`echo`, und danach lief der Commit über `&&` weiter — `echo` gelingt immer.
Das ist derselbe Fehler, den `CLAUDE.md` für Testläufe beschreibt (der
Shell-Status ist der des letzten Befehls), an einer anderen Stelle:

> **Eine Zahl auszugeben ist keine Prüfung. Eine Prüfung bricht ab.**

    IST=$(git diff --cached HEAD --shortstat | tr -d ' ')
    if [ "$IST" = "2fileschanged,150insertions(+)" ]; then git commit …; else echo ABBRUCH; fi

Damit sind es drei Fälle an einem Tag, und **keine zwei hatten dieselbe
Ursache**:

| Fall | Ursache | was gefangen hätte |
|---|---|---|
| `bc3a8b12` | Index zwischen zwei Aufrufen gealtert | die Kette in einem Aufruf |
| `56c2a559` | `git add` nahm den Dateistand mit fremden Zeilen | Sollprobe, die abbricht |
| `7f7ad380` | `read-tree` gegen einen HEAD von vorher | **beides zusammen** |

Die Regel, die alle drei fängt, ist eine: **`read-tree`, Sollprobe und Commit
gehören in einen Aufruf, und die Sollprobe muss abbrechen können.** Zwei von
drei ist nichts — beim sechsten Fall waren zwei davon erfüllt.

Die Reparatur ging vorwärts und war einfach, weil der Arbeitsbaum die Dateien
unversehrt hatte: Ich hatte sie nie angefasst, nur ihr Fehlen im Index
committet. `git add` auf die zwei Pfade, bitgleich nachgerechnet gegen
`7f7ad380^`, fertig. **Das gilt nicht allgemein** — siehe
[[sicherung-ist-eine-zeitmaschine]] für den Fall, in dem der Arbeitsbaum
weitergelaufen war.


## Siebter Fall: die Sollprobe griff, und der Commit ging trotzdem daneben (03.09.2026)

Ein Commit nahm `.claude/memory/begrenzt-am-falschen-mass.md` mit — 56 Zeilen
einer Notiz, die eine andere Sitzung Minuten vorher angelegt hatte. **Und die
Gegenmaßnahme aus Fall sechs war diesmal da und hat sogar ausgelöst:** Die
Sollprobe brach ab, weil ich 2 Zeilen erwartet hatte und 3 gemessen wurden.
Ich habe die Zahl korrigiert und den Aufruf wiederholt.

In den anderthalb Minuten dazwischen committete eine Sitzung. Der zweite
Anlauf lief gegen einen HEAD, den es beim `read-tree` noch gab — und nahm
alles mit, was der neue HEAD trug und mein Index nicht.

**Daraus folgt nicht „noch sorgfältiger prüfen".** Die Sorgfalt war da; sie
hat den ersten Anlauf gefangen und den zweiten ermöglicht. Das Fenster
zwischen Messung und Commit lässt sich mit keiner Prüfung schließen, weil die
Prüfung selbst davor liegt.

Was es schließt, ist eine andere Mechanik:

    git commit -o -F <meldung> -- <pfad> [<pfad> …]

`-o` (`--only`) committet **genau die genannten Pfade**, unabhängig davon, was
der Index sonst führt. Ein HEAD, der sich unterwegs bewegt, ist damit
bedeutungslos — es gibt nichts, was versehentlich mitgehen könnte.

**Und das steht scheinbar gegen den Titel dieser Notiz.** Es tut es nicht, weil
`-o` zwei getrennte Eigenschaften hat, und nur eine ist eine Falle:

| Eigenschaft | Wirkung |
|---|---|
| nimmt den **Dateistand** der Pfade | die Falle: fremde ungestagte Zeilen in einer geteilten Datei gehen mit (Fall vier) |
| nimmt **nur die genannten** Pfade | die Rettung: nichts anderes kann mitgehen, egal was Index und HEAD tun |

Die Regel, die beides zusammenbringt: **`-o` für Dateien, die mir allein
gehören** — dort ist der Dateistand meiner. Für die drei geteilten Dateien
(`ROADMAP.md`, `MEMORY.md`, die Sprachkataloge) bleibt der Blob-Weg richtig:
HEAD lesen, die eigene Änderung darauf anwenden, hashen, in den Index legen.

Ein Nachtrag zur Bedienung: `-o` nimmt nur Pfade, die Git kennt. Eine Datei,
die im HEAD **gelöscht** ist, muss erst `git add` bekommen — dort hilft `-o`
also nicht, und genau dort lag die Reparatur dieses Falls.

**Und eine neue Datei genauso — auch hinter einem Verzeichnis-Pathspec
(06.09.2026).** `git commit -o -F msg -- website` nahm 47 geänderte Dateien
unter `website/` und ließ die neue `website/api/day_zone.php` liegen, ohne
Warnung: `--only` staged nur, was der Index schon kennt. Der Commit war damit
kaputt — `count.php` und `stats.php` verlangten eine Datei, die es in HEAD
nicht gab. Gefangen hat es die Sollprobe „Rest im Baum muss leer sein" nach
der Kette (`git status --short` zeigte `??`). Regel: Vor einer `-o`-Kette
`git status --short | grep '^??'` lesen und jede eigene neue Datei vorher
`git add`; oder die Kette mit `git add -N <neu>` beginnen.
