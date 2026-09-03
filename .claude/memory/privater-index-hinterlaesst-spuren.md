---
name: privater-index-hinterlaesst-spuren
description: Ein Commit mit privatem Index legt eine neue Datei an — im Haupt-Index steht sie danach als gelöscht; und die Umfangs-Sollprobe zählt Zeilen, nicht Urheber
metadata:
  type: feedback
---

Der private Index (`GIT_INDEX_FILE`) hält fremde Dateien aus dem eigenen
Commit heraus. Er hinterlässt dabei zwei Spuren, die man nicht sieht, wenn man
nur auf den Commit schaut.

## Eine neue Datei wird im Haupt-Index zur Löschung

**Legt der Commit eine Datei an, die es vorher nicht gab, steht sie danach im
Haupt-Index als gelöscht.** Sie liegt im Baum, sie liegt in HEAD — und der
nächste pfadlose `git commit -a` einer beliebigen Sitzung nimmt sie wieder
heraus.

Am 30.08.2026 mit `tools/make_showpiece.py` passiert; gefunden hat es 15 bei
ihrer Schlusskontrolle, nicht ich. Der Grund ist einfach: Der Haupt-Index
kennt die Datei nicht (sie stand nie darin), HEAD kennt sie jetzt — also liest
Git die Differenz als Löschung.

**Die Kontrolle kostet eine Sekunde, und sie gehört ans Ende jeder Kette:**

```
unset GIT_INDEX_FILE          # ohne das misst man den privaten weiter
git status --short | grep "^D "
```

Was dort steht und im Baum liegt, wird mit `git reset -- <pfad>` entschärft.
Es trifft **immer die neuen Dateien** — wer nur bestehende ändert, sieht das
Muster nie.

## Die Sollprobe zählt Zeilen, keine Urheber

**Und die zweite Spur geht in die andere Richtung.** Am selben Abend nahm mein
Commit in `tests/test_website.py` einen fremden, ungestagten Test mit
(`test_every_page_closes_the_tags_it_opens`, 15s Arbeit). Die Umfangsprobe
war grün: Ich hatte 131 Zeilen erwartet und 131 gesehen.

Genau daran scheitert sie. Eine Zahl sagt, **wie viel** dazukam, nicht **was**.
Bei einer geteilten Datei gehört deshalb der Diff gelesen, nicht die Zahl
verglichen:

```
git diff HEAD -- <datei> | grep "^+" | grep -oE "def [a-z_]+" | sort -u
```

Stehen dort Namen, die man nicht selbst geschrieben hat, ist fremde Arbeit
dabei — und dann hilft nur die Blob-Fassung aus dem unmittelbaren HEAD plus
den eigenen Zeilen.

## Fünf Sekunden vor jedem Tag, und danach

Am 03.09.2026 standen **zweimal** Dateien im Haupt-Index als gelöscht, die
im Baum unversehrt lagen — einmal zwei Erinnerungen, einmal zwei
Erinnerungen plus zwei Dateien unter `.claude/.state/`. Alle mit demselben
Hash wie in HEAD. Der zweite Fall lag **eine Viertelstunde vor dem Tag
`v0.3.1`**.

```
git status --short | grep "^D "
```

Steht dort etwas, das im Baum liegt, gehört es zurückgenommen, **bevor**
ein Tag den Stand einfriert oder jemand ohne privaten Index committet:

```
git reset -- <die genannten Pfade>      # nicht ohne Pfade, siehe unten
```

**Warum die Blob-Prüfung nicht reicht**, obwohl sie näherliegt: Die
Sitzung, die die Spur erzeugt hatte, hatte sie selbst bemerkt und als
blob-identisch mit HEAD gemessen — also für harmlos gehalten. Das
stimmt für den **Ist-Zustand** und nicht für das **Risiko**: Harmlos
ist die Spur nur, solange niemand ohne privaten Index committet. Wer es tut,
nimmt die Löschung mit, und im Paket fehlen die Dateien, ohne dass es
jemandem auffällt. Der Statusblick sieht das Risiko, die Blob-Prüfung
nur den Augenblick.

**Und `git reset` ohne Pfade ist die falsche Antwort**, auch wenn viel im
Index steht. Am selben Tag trug er 86 gestagte Einträge; wer die wegwirft,
nimmt jedem, der bewusst vorbereitet hat, seine Arbeit ab — und der merkt
es erst beim Commit. Zwei falsche Einträge rechtfertigen nicht,
vierundachtzig richtige mitzunehmen (Selbstkorrektur 3d-druck-a0, `5c656052`).

Dazu kann ein **verwaistes `.git/index.lock`** danebenliegen und den Reset
blockieren. Es blockiert sonst nichts, weil private Indizes keines brauchen —
also fällt es nur hier auf. Reihenfolge: Alter messen (23 Minuten sind kein
laufender Commit), sichern, dann entfernen.

Beides zusammen: [[commit-o-nimmt-den-dateistand]] (der fremde *Stand* einer
gemeinsamen Datei), [[index-altert-zwischen-lesen-und-commit]] (der Index ist
einen Commit zu alt), [[sicherung-ist-eine-zeitmaschine]] (die Kopie vom
Anfang) — vier Gestalten desselben Satzes: **Was einen ganzen Stand trägt,
trägt auch den fremden Teil davon.**


## Und damit ist `git diff HEAD` als Endkontrolle untauglich

**Die Spur oben macht die Frage kaputt, mit der man sie finden würde.**
`git diff HEAD` heißt „Arbeitsbaum gegen HEAD", und man liest es als Frage nach
ungestagter Arbeit. Git zieht dafür aber den Index als Zwischenspeicher heran
und zeigt dessen Löschung mit — **auch wenn die Datei im Baum liegt und
bytegleich mit HEAD ist.**

Am 03.09.2026 an der Release-Schwelle: Die Endkontrolle meldete „3 Dateien, 56
Löschungen" in `.claude/memory/`, darunter eine Notiz, die eine Stunde vorher
wiederhergestellt worden war. Sie war nie weg. Zwei Sitzungen hätten nachts um
zwei nach drei verschwundenen Dateien gesucht, die alle drei danebenlagen.

Die Frage, die trägt, fragt den Index nicht:

    git status --porcelain -- <pfad>        # was Git für geändert hält
    git show HEAD:<datei> | sha256sum       # und dann: stimmt der Inhalt?

Oder kurz: **Inhalt gegen HEAD-Blob.** Wer belegen will, dass nichts Halbes im
Baum liegt, vergleicht Bytes und nicht Zustände.

**Die Verschärfung liegt darin, wer darauf hereinfällt.** Diese Notiz gibt es
seit dem 30.08., und ich habe am selben 03.09. mehrfach anderen Sitzungen
geschrieben, `git diff HEAD` sei „die richtige Frage" — als Gegenmittel gegen
den *anderen* Fall, in dem `git diff` ohne HEAD gegen den veralteten Index
vergleicht. Beide Sätze stimmen für ihren Fall, und der zweite habe ich für
allgemein gehalten. Siehe [[der-nachbar-findet-den-fehler]]: richtig gemessen,
an der falschen Stelle geglaubt.
