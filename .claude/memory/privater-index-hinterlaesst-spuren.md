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

Beides zusammen: [[commit-o-nimmt-den-dateistand]] (der fremde *Stand* einer
gemeinsamen Datei), [[index-altert-zwischen-lesen-und-commit]] (der Index ist
einen Commit zu alt), [[sicherung-ist-eine-zeitmaschine]] (die Kopie vom
Anfang) — vier Gestalten desselben Satzes: **Was einen ganzen Stand trägt,
trägt auch den fremden Teil davon.**
