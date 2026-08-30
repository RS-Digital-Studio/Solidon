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
