---
name: geteilter-baum-misst-zeitpunkt
description: "Wo mehrere Sitzungen schreiben, misst man keinen Stand, sondern einen Zeitpunkt — vor jedem Nachmessen eines Fremdbefunds git diff HEAD auf die Datei."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: fd3340f1-dc7c-45b2-a76c-25431a7a9212
  modified: 2026-08-27T09:42:52.557Z
---

Eine Messung im geteilten Arbeitsbaum beantwortet nicht „wie verhält sich der
Code", sondern „wie verhielt er sich in dieser Minute, mit allem, was gerade
ungestaged darin lag".

**Und daraus folgt die Regel für jeden Vergleich: Zwei Läufe sind nur
vergleichbar, wenn sie sich in genau einer Sache unterscheiden.** Am
30.08.2026 sah es aus, als bräche meine Änderung einen Test — 364 bestandene
gegen 365 auf HEAD. Der Unterschied war ein ganz anderer: Ich hatte meinen
Stand im **Hauptbaum** gefahren und HEAD in einem **Worktree**. Der
Fehlschlag war `test_the_history_names_only_what_differs`, eine fremde
Verlaufs-Nummerierung, die gerade ungestaged im Baum lag; meine Änderung saß
in `tool_strip.py` und hatte damit nichts zu tun.

Ein Lauf im geteilten Baum unterscheidet sich vom Vergleichslauf **in allem,
was gerade offen ist** — und das weiß man nie vollständig. Der saubere Beleg
kostet fünf Minuten: HEAD in einen Worktree, genau die eigenen Dateien
hineinkopieren, dann laufen lassen. Ergebnis dort: 365 gegen 365.

Die verwandte Falle steht in [[fix-der-nicht-gruen-macht]] — dort bleibt ein
Test nach der Behebung rot und die Diagnose war falsch; hier wird ein Test
scheinbar rot und die Zuordnung ist falsch. Beide Male rettet dieselbe Frage:
*Was genau unterscheidet die beiden Läufe?*

Am 27.08.2026: 27 meldete, die exakte Bohrung liefere bei einer Bohrung größer
als der Körper ein leeres Objekt, das man benennen und **speichern** kann. Ich
baute den Fall exakt nach — `History` + `evaluate`, beide Schalterstellungen —
und bekam einen sauberen Fehler mit Handlungsvorschlag, dazu den unversehrten
Quader im Baum. Ich schrieb ihr, ihr Fund halte nicht, und stellte ihn Robert
gegenüber unter Vorbehalt.

**Gemessen hatte ich ihren Fix.** Sie hatte die Prüfung zehn Minuten zuvor
eingebaut, ungestaged. Ihr Befund war echt; meine Gegenmessung war die
Bestätigung ihrer Reparatur und las sich wie deren Widerlegung.

**Why:** Die Falle schnappt dort zu, wo man alles richtig macht. Ich habe den
Fremdbefund nicht geglaubt, sondern nachgemessen, und dafür den Weg der
Anwendung gewählt statt den bequemen — nur war der Prüfling ein anderer als
angenommen. Und die Regel war mir bekannt: Zwei Stunden vorher hatte ich genau
deshalb angehalten, als 27s ungestagte Katalogzeile in meinen Dateien lag. Sie
griff trotzdem nicht, weil ich sie beim **Schreiben** angewandt hatte und sie
beim **Messen** genauso nötig ist. Dieselbe Wurzel wie
[[commit-o-nimmt-den-dateistand]]: dort wandert fremder Stand in den eigenen
Commit, hier in die eigene Messung. Am selben Tag traf es beide Richtungen —
27s Zeile lag in meinen Dateien, meine Übersetzungen gingen in d1s Commit.

**Und `git diff` ohne `HEAD` ist in diesem Baum nicht ungenau, sondern
unbrauchbar.** Es vergleicht gegen den **Index**, und der altert: Wer mit
privatem Index committet (`GIT_INDEX_FILE`), fasst den Haupt-Index nie an, und
der steht nach ein paar Tagen weit hinter HEAD. Gemessen am 27.08.2026 an
derselben Datei im selben Moment:

    git diff --numstat  -- app/ui/main_window.py   →  33 / 6
    git diff HEAD --numstat -- app/ui/main_window.py →   4 / 0

Die 33 zeigten fremde Arbeit an, die längst committet war; die 4 waren meine.
Ich hätte den Commit deshalb fast nicht gemacht — und 27 hat dieselbe Zahl
kurz zuvor 640 geänderte Zeilen in einer Datei melden lassen, die sie selbst
zwanzig Minuten vorher committet hatte. **Dasselbe gilt für `git status`:**
Das `MM` in der ersten Spalte heißt hier meist nur, dass der Index alt ist,
nicht dass jemand gestaged hat.

**How to apply:** Vor dem Nachmessen eines Befunds, der jemand anderem gehört:

    git diff HEAD --numstat -- <datei>

Steht dort etwas, misst man einen Zwischenstand und nicht `origin`. Soll ein
fremder Befund bestätigt oder abgesprochen werden, ist der eigene Arbeitsbaum
die vollständige Antwort:

    git worktree add -q --detach "$TEMP/rein" origin/main

Und die Regel für den Bericht: **Ein Gegenbefund gegen eine fremde Messung
braucht denselben Beleg wie die Messung selbst.** „Bei mir nicht
reproduzierbar" ist so lange keine Aussage, wie nicht feststeht, dass beide
denselben Code gefahren haben.

**Und die Kehrseite: Zwei Bäume sind zwei Umgebungen, und das ist ein Gewinn.**
Am 27.08.2026 fand mein Torlauf im eigenen Arbeitsbaum 142 Verweise mit
falschem Stempel, während derselbe Test im Hauptbaum grün war. Die Ursache lag
nicht am Stand, sondern an den **Zeilenenden**: Der eine Baum ist mit CRLF
ausgecheckt, der andere mit LF, und das Werkzeug hashte die rohen Bytes.
Schlimmer war, dass der Wächter das nie hätte finden können — er las dieselben
Bytes wie das Werkzeug, das er prüft, also irrten beide zusammen
([[sollwert-aus-dem-pruefling]]). Sichtbar wurde es allein im **Unterschied**
zwischen zwei Umgebungen. Ein eigener Arbeitsbaum vermeidet also nicht nur
Kollisionen; er ist eine zweite Maschine, die man sonst nicht hat.

Verwandt: [[gemessene-frage-ist-nicht-die-gestellte]],
[[bekannte-familie-erklaert-nicht-den-ausloeser]],
[[parallele-sitzung-im-arbeitsbaum]], [[messwerkzeug-misst-sich-selbst]].

**Und die schärfste Gestalt: `HEAD` bedeutet zwischen zwei Messungen etwas
anderes.** Am 04.09.2026 wollte 81 belegen, dass eine Zeile auf HEAD fehlte
und der Wächter dort rot war. Zwei saubere Läufe, die sich widersprachen:

    erste Messung:  git show HEAD:<datei>   → Zeile fehlt      (HEAD war b02a2110)
    zweite Messung: Worktree auf HEAD       → Wächter grün     (HEAD war fd2c852f)

Dazwischen lag mein Commit. 81 hätte daraus fast geschlossen, die Zeile sei
Kosmetik gewesen — der Beleg war in Wahrheit meine Behebung, gemessen unter
demselben Namen. **Hier lag nichts Ungestagtes im Weg; der Fehler war der Name
selbst.** Ein Worktree „auf HEAD" ist kein Vergleichsstand, sondern ein
Schnappschuss des Augenblicks, in dem er entsteht.

Wer zwei Messungen gegeneinander stellt, hält den Stand fest, statt ihn zu
benennen — `git rev-parse HEAD` vor jeder und beide Hashes danebengelegt.
Unterscheiden sie sich, vergleicht man nicht zwei Läufe, sondern zwei Tage.
