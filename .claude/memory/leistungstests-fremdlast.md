---
name: leistungstests-fremdlast
description: Rote §31-Leistungstests und Suite-Abstürze am Lauf-Ende erst gegen die Fremdlast prüfen — Spiel, Suite selbst oder eine zweite Claude-Sitzung; fallen alle Marken gleichmäßig um 1,4–1,7, ist es die Maschine.
metadata: 
  node_type: memory
  type: project
  originSessionId: 4c47107c-d31c-406e-b4b0-401bb3afd6bb
  modified: 2026-08-20T16:40:00.000Z
---

Auf Roberts Maschine (i9-13900K) läuft während der Sitzungen öfter ein Spiel
(beobachtet: Palworld, ~35–40 % CPU-Grundlast). Die absoluten §31-Budgets in
`tests/test_performance.py` (z. B. `orient_200` < 20 s, dort sonst ~16 s)
reißen dann, ohne dass der Code langsamer wurde — auch mit hoher
Prozesspriorität, vermutlich Takt-/Speicherbandbreiten-Konkurrenz.

**Why:** Die Budgets meinen eine unbelastete Referenzmaschine; die CI läuft
absichtlich `-m "not performance"`. Ein roter Lauf unter Spielelast ist keine
Regression.

**Dasselbe gilt für den Abriss am Lauf-Ende.** `pytest tests/ -q` endet unter
Spielelast mit „Windows fatal exception: access violation" **nachdem** alle
Tests bestanden sind — das Aufräumen der VTK-Objekte hängt an der
Grafikkarte, und die gehört gerade dem Spiel. Erkennbar daran, dass derselbe
Stand mit `-v` durchläuft und der Abriss auch nach `git stash` bleibt.

**Die Fremdlast kommt oft aus der Suite selbst, nicht von einem Spiel.** Am
14.08.2026 lief `sketch_solve_200` im vollen Lauf auf 162 ms und einzeln auf
114/113/114 — achtunddreißig Prozent, verursacht allein von `test_slice.py`
unmittelbar davor. Wer nur nach einem Spiel sucht, findet nichts und hält den
Wert dann für echt. Die entscheidende Gegenprobe ist deshalb nicht
`Get-Process`, sondern **die eine Marke allein fahren**:
`-m performance -k "<name>" -s`.

**How to apply:** Bei rotem Leistungstest oder Abriss am Ende zuerst
`Get-Process` / `LoadPercentage` prüfen und ob der gemessene Pfad überhaupt ein
Diff hat. Drei Gegenproben, die schnell entscheiden: die Marke allein statt im
Verbund, derselbe Lauf mit `-v`, und derselbe Lauf nach `git stash`. Bleibt es,
gehört es nicht der eigenen Änderung. Die maschinenunabhängige
Regressionsschwelle (25 %) ist das belastbare Signal — seit dem 14.08.2026
misst sie gegen den **schnellsten** bekannten Lauf statt gegen den letzten, so
dass ein verrauschter Lauf die Marke nicht mehr anhebt und eine echte
Verschlechterung nicht mehr darin verschwindet. Endgültige Messung trotzdem
auf unbelasteter Maschine — notfalls per Monitor auf das Spielende warten.

**Die schnellste Unterscheidung ist die Gleichmäßigkeit.** Am 20.08.2026
fielen elf von neunzehn Marken auf einmal — und zwar alle um Faktor 1,4 bis
1,7: `ingest_dense` 1,43, `detect_medium` 1,56, `slice_medium` 1,59,
`sketch_solve_200` 1,73. Einlesen, Erkennen, Schneiden und der Löser haben
keinen gemeinsamen Codepfad; eine Änderung kann sie nicht gleichmäßig treffen,
eine langsamere Maschine schon. Der I/O-lastige `read_dense` blieb dabei
unverändert (430 gegen 425 ms) — nur die rechnenden Marken litten. Wer diese
Signatur sieht, braucht gar nicht erst zu suchen.

Verursacher war eine **zweite Claude-Sitzung im selben Arbeitsbaum**, die
Bilder rendert (Python-Prozess mit ~2,9 GB). `LoadPercentage` zeigte dabei
8–20 % und `CurrentClockSpeed` den Nennwert — beides sagt hier nichts: Der
i9-13900K hat P- und E-Kerne, und wenn die P-Kerne belegt sind, landet der
Messprozess auf einem E-Kern. Genau das ergibt 1,4 bis 1,7.

**Bei paralleler Sitzung ist `git stash` als Gegenprobe verboten** — er nimmt
die fremde Arbeit mit weg. Übrig bleiben die beiden anderen: die Marke allein
fahren (drei Läufe, nicht einer) und prüfen, ob der gemessene Pfad überhaupt
einen Diff hat.

Nicht jeder solche Abriss ist Fremdlast: eine Referenzschleife zwischen Python
und VTK erzeugt dasselbe Bild und ist echt. Siehe
[[vtk-qt-referenzen-halten-zu-lange]] und [[parallele-sitzungen-solidon3d]].

**Die Unterscheidung liefert ein eigener Arbeitsbaum, nicht `git stash`** —
hier stand zwei Absätze über dem Verbot noch der Rat, denselben `git stash` zu
nehmen. `git worktree add --detach <pfad> HEAD` plus eine Kopie der `.venv`
gibt einen Stand ohne die eigene Änderung, ohne im geteilten Baum etwas
anzufassen. Zwei Fallen dabei, beide am 23.08.2026 gemessen: Der Kopie fehlt
das `__pycache__` des Projekts, und sie kann sich anders verhalten als der
Hauptbaum — prüfen, ob dort überhaupt etwas Grünes läuft (`test_leash.py` und
`test_errors.py` gehen ohne Fenster), bevor man ihre Zahlen glaubt.

**Auch ein *gescheiterter* `git merge` frisst Arbeit.** Er legt einen
Autostash an, bewegt HEAD, schreibt Dateien — und wenn er abbricht, steht
„Index was not unstashed" in der Meldung, und der Stash bleibt liegen. Am
23.08.2026 hat das die ungespeicherte Arbeit einer anderen Sitzung
zurückgesetzt. Nach jedem abgebrochenen Merge: `git status` **und**
`git stash list`.

**Auf dieser Maschine läuft dauerhaft ComfyUI mit rund einem Gigabyte** — es
gehört Robert, keine Sitzung startet es, und es steht bei jeder
Fremdlastbewertung mit in der Prozessliste. Wer ihm 22 CPU-Sekunden zuschreibt
und sie einer Sitzung anrechnet, misst das Falsche.

**`py-spy` liegt nicht in der `.venv`**, sondern unter
`~/AppData/Roaming/Python/Python313/Scripts/py-spy.exe`. `dump --pid N
--native` zeigt Python- **und** C-Stack; bei einem Hänger sagt erst der native
Teil, worauf gewartet wird.

**Und die Marke reist nicht mit.** `tests/.performance.json` ist **nicht
eingecheckt** — sie hält je Kontext `{"best": Sekunden, "strikes": n}`. Ein
frischer Arbeitsbaum hat sie also gar nicht, sein erster Lauf legt sie an, und
darum ist er **immer grün**. Am 24.08.2026 sah eine Gegenprobe deshalb wie eine
Entlastung aus und war keine: „mit meiner Änderung grün, ohne sie grün" hieß
bloß, dass in dem Baum noch keine Marke stand.

Brauchbar wird der Vergleich erst über die **absoluten** Zahlen: in beiden
Ständen `.performance.json` löschen, je drei Läufe fahren, danach `best`
auslesen. Die Alternative ist, die Marke des Hauptbaums mitzukopieren.

**Und dieselbe Falle schnappt auf der Referenzseite zu.** So gemessen standen
2005 gegen 2001 ms, und daraus wurde der Schluss „dann liegt es im
Commit-Stand" — falsch. Er stützte sich auf einen *früheren* Lauf in einem
frischen Baum, der grün war, weil dort noch keine Marke stand. Zwei
Nachbarsitzungen haben es unabhängig widerlegt: vier Stände über den ganzen
Tag, alle bei ~2050 bis 2150 ms, im Wechsel gemessen sogar der ältere Stand
langsamer. Ein A/B im selben Baum sagt nur, dass die geprüfte Änderung
unschuldig ist — **wer schuldig ist, sagt es nicht.**

**Wenn die Maschine nicht ruhig zu bekommen ist, misst man im Wechsel.** „Die
Marke allein fahren" ist der beste Rat und an manchen Tagen keiner — am
24.08.2026 arbeiteten vier Sitzungen gleichzeitig. Dann fährt man A und B
**abwechselnd in derselben Schleife** statt in zwei Blöcken:

    Runde 1:  mit 2147 ms   |   ohne 2112 ms
    Runde 2:  mit 2130 ms   |   ohne 2094 ms
    Runde 3:  mit 2094 ms   |   ohne 2131 ms

So trifft jede Laständerung beide Seiten, und der Vergleich trägt, obwohl die
absoluten Zahlen es nicht tun. Zwei Blöcke nacheinander hätten hier eine
Aussage über die Uhrzeit ergeben.

**Und `strikes` zählt die eigenen Prüfläufe mit.** Der Zähler steigt bei jedem
roten Lauf, auch bei denen, mit denen man den roten Lauf untersucht: Am
24.08.2026 stand er auf 9, davon drei aus der Messung selbst. Wer eine Zahl
nennt, die er gerade hochgezählt hat, sagt es dazu.

Die Startzeitmarke von 1233 ms wird auf dieser Maschine heute nicht mehr
erreicht; sie ist der kleinste je gemessene Wert, und der Docstring des Tests
nennt selbst eine Spanne von 2500 bis 13 764 ms. Zurückgesetzt wird sie
trotzdem nicht — das verstecke die nächste echte Regression.
