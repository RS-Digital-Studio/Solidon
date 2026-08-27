---
name: patchskript-schneidet-fremdes-weg
description: "Ein Patchskript, das ab einer Marke ersetzt, löscht alles dahinter — auch was eine Nachbarsitzung dort gerade eingefügt hat; --stat sieht aus wie Umformatierung."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: d52f0866-6a6b-49d3-a8c5-73c0be546ada
  modified: 2026-08-27T14:58:17.047Z
---

Wer eine Datei mit `text[:text.index(marke)] + neu` umschreibt, ersetzt nicht
den eigenen Block, sondern **alles ab der Marke bis zum Dateiende**. In einem
geteilten Arbeitsbaum steht dort mit einiger Wahrscheinlichkeit fremde Arbeit.

Am 27.08.2026 zugeschnappt: Zwei Wächter einer Nachbarsitzung in
`tests/test_updates.py` verschwanden in meinem Commit. Sie waren entstanden,
während ich an derselben Datei schrieb.

**Die Zahl stand da und wurde falsch gelesen.** `git show --stat` meldete
`76 insertions, 92 deletions`. Netto minus sechzehn Zeilen bei einem Zusatz von
gut hundert — das hätte reichen müssen. Ich hielt es für Umformatierung durch
`ruff format`, weil das dieselbe Signatur erzeugt.

**Why:** Bei einer geteilten Datei zählt nicht, ob die eigene Änderung stimmt,
sondern **was am Ende dasteht**. Dieselbe Familie wie
[[commit-o-nimmt-den-dateistand]] und [[privater-index-fester-name]], nur eine
Ebene höher: Dort nimmt der Index fremden Inhalt mit, hier nimmt ihn das
Schreibwerkzeug weg.

**How to apply:**

- **Nie „ab Marke bis Ende" ersetzen.** Den zu ersetzenden Block **beidseitig**
  begrenzen (Anfang *und* Ende), oder mit `str.replace(alt, neu)` gegen den
  vollständigen alten Wortlaut arbeiten — der schlägt fehl, wenn sich etwas
  geändert hat, und das ist die gewünschte Antwort.
- **Nach jedem Commit an einer geteilten Datei prüfen, was verschwunden ist**,
  nicht nur wie viel:

  ```
  git show HEAD -- <datei> | grep "^-def \|^-class "
  ```

  Eine leere Ausgabe ist der Beleg. `--stat` allein ist keiner — Umformatierung
  und Verlust sehen dort gleich aus.
- **Wiederherstellen aus dem richtigen Elternteil.** Nach zwei eigenen Commits
  ist der Stand davor `HEAD~2`, nicht `HEAD~1`; ein Fehlgriff meldet
  „substring not found" und sieht aus, als hätte es die Funktion nie gegeben.
- Beim Zurückholen **prüfen, ob die fremde Fassung die bessere ist.** Zwei der
  wiederhergestellten deckten sich mit eigenen; einmal konnte die fremde mehr,
  und dann entfällt die eigene, statt beide zu behalten.
