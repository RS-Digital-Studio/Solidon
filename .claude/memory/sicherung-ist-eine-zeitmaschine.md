---
name: sicherung-ist-eine-zeitmaschine
description: Eine Kopie für Mutationsproben, die am Anfang einer Serie entsteht und am Ende zurückgespielt wird, nimmt jede fremde Änderung mit, die inzwischen entstand
metadata:
  type: feedback
---

**Eine Sicherung ist kein Rückbau, sondern ein Zustand.** Wer vor einer Reihe
von Mutationsproben `cp datei.py sicherung.py` macht und nach jeder Mutation
zurückkopiert, spielt nicht seine eigene Änderung zurück — er spielt den
**ganzen Dateistand von damals** zurück. Im geteilten Arbeitsbaum ist das eine
Zeitmaschine: Alles, was eine Nachbarsitzung inzwischen in dieselbe Datei
geschrieben hat, ist danach weg, und zwar lautlos.

Am 30.08.2026 an `app/ui/viewport.py` dreimal zurückkopiert, während 50 in
derselben Datei arbeitete. Es ist gutgegangen — **weil meine Sicherung zufällig
jünger war als ihr Commit.** Das ist Glück und kein Verfahren. Aufgefallen ist
es erst, als 50 von sich aus meldete, dass ihr Commit meine Zeilen mitgenommen
hatte; erst dabei habe ich in die andere Richtung nachgesehen.

**Drei Wege, aufsteigend gut:**

1. Die Sicherung **unmittelbar vor** der einzelnen Mutation anlegen und sofort
   danach zurückspielen. Das Fenster schrumpft auf Sekunden, verschwindet aber
   nicht.
2. Statt einer Dateikopie den **Patch** zurücknehmen: die Mutation als
   `replace(neu, alt)` rückgängig machen, nicht die Datei ersetzen. Dann bleibt
   fremder Text unberührt, auch wenn er inzwischen dazukam.
3. **Eigener Worktree** (der Weg von 72). Mutationsproben verändern den
   Bestand, und ein Bestand, den vier Sitzungen teilen, ist der falsche Ort
   dafür — dieselbe Begründung wie in [[sonde-im-geteilten-baum]], nur für die
   Probe statt für die Messung.

Und der Rückbau selbst kann scheitern: 50s `finally` fiel an einem OSError aus,
die Mutation blieb stehen ([[rueckbau-kann-scheitern]]). Wer zurückspielt,
**prüft danach**, dass der Stand wirklich der erwartete ist — ein Testlauf, der
danach grün ist, beweist nur, dass die Datei kompiliert.

Verwandt: [[probe-worktree-altert]] (ein Worktree ist ebenfalls ein Zustand und
altert), [[geteilter-index-haelt-alten-stand]] und
[[commit-o-nimmt-den-dateistand]] — dreimal dieselbe Familie: **Was einen
ganzen Stand trägt, trägt auch den fremden Teil davon.**


## Dasselbe mit einem Git-Blob, und dort hilft der HEAD-Vergleich nicht

Am 03.09.2026 in einer zweiten Gestalt: Ein Commit hatte fremde Arbeit
zurückgerollt (der Index war zwischen zwei Shell-Aufrufen gealtert), und die
Reparatur schrieb die betroffenen Blobs aus dem überrollten Commit zurück —
`git rev-parse <commit>:<pfad>` in den Index, sauber vorwärts statt per Revert.
Die acht Dateien stimmten danach bitgleich mit dem Zielcommit.

**Und genau das war das Problem.** In fünf der acht Dateien lagen zu diesem
Zeitpunkt drei ungestagte Zeilen einer dritten Sitzung. Der zurückgeschriebene
Blob trug den vollständigen Stand seines Zeitpunkts — einschließlich der
**Abwesenheit** von allem, was seither dazugekommen war. Zehn Minuten später
standen dort 0 von 3.

> **Ein wiederhergestellter Blob ist kein Rückbau einer Änderung, sondern ein
> Zustand — mit allem, was darin fehlt** (3d-druck-c7, 03.09.2026).

Der Unterschied zu der Falle, die ihn ausgelöst hat, ist der ganze Punkt:

| | fängt | fängt nicht |
|---|---|---|
| HEAD-Vergleich vor dem Commit | einen **Commit**, der dazwischenkam | ungestagte Arbeit |
| `git diff --stat -- <pfade>` vor dem Zurückschreiben | beides | — |

Ein HEAD-Vergleich kann ungestagte Arbeit prinzipiell nicht sehen: Sie steht in
keinem Commit. Wer einen Blob zurückschreibt, liest deshalb **vorher** den
Arbeitsbaum — steht dort etwas, gehört es in die wiederhergestellte Fassung
hinein und nicht darunter.

**Bei den Sprachkatalogen ist das der Normalfall und kein Randfall.** Fünf
Dateien, an denen jede Sitzung nur Zeilen anhängt, sind der Ort im Repository,
an dem am häufigsten ungestagte Fremdarbeit liegt — siehe
[[privater-index-schuetzt-die-kataloge-nicht]] für die Gegenrichtung desselben
Problems.

Und weil ein Zurückschreiben den Bestand unter einem laufenden Torlauf ändert:
**vorher ansagen.** `gate_lock.py status` nennt in einer Sekunde, wer gerade
misst; ein Katalog, der sich unter `test_translations` ändert, erzeugt einen
roten Befund, der mit der Arbeit des Messenden nichts zu tun hat.
