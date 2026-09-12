---
name: git-push-pull-selbststaendig
description: "Robert will, dass ich push und pull immer selbst mache — jeder Commit geht hinaus, außer er sagt ausdrücklich etwas anderes; erst nach grüner Suite."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: e828bb8c-574f-465c-baa0-bfcac75d3cde
  modified: 2026-09-12T17:25:13.767Z
---

`git pull` und `git push` mache ich in diesem Repository **selbstständig**,
ohne Rückfrage (gesagt am 18.08.2026). **Jeder Commit geht hinaus, außer
Robert sagt ausdrücklich etwas anderes** (bekräftigt am 11.09.2026, nachdem
`CLAUDE.md` in `5fbf101a` einen Satz bekam, wonach ein „reiner Commitauftrag
ohne Push-Freigabe" `SOLIDON_KEIN_PUSH=1` setzt — für mich gilt der Satz
**nicht**: „commit" heißt commit und push; nur ein ausdrückliches „nicht
pushen" hält den Commit lokal).

**Warum:** An Solidon wird auf drei Maschinen gearbeitet; ein Stand, der nur
lokal liegt, existiert auf den anderen zweien nicht. Nachfragen kostet einen Zug und bringt keine
Entscheidung — die Antwort ist immer dieselbe.

**How to apply:**
- Gepusht wird erst, wenn die Suite grün ist — die Hausordnung steht darüber,
  die Erlaubnis ersetzt das Tor nicht ([[rtree-abstuerze-im-langen-lauf]]:
  portionsweise fahren, sonst täuscht ein Abriss ein Ergebnis vor).
- **Zusammengeführt wird per Merge, nie per Rebase.** Der lokale Stand liegt
  regelmäßig dutzende Commits vorn; ein Rebase schriebe sie alle um. Für
  Rebase, Force-Push und History-Rewrite gilt die Rückfragepflicht weiter.
- Fremde Commits vor dem Merge ansehen (`git log main..origin/main`,
  `git diff --name-only`) — bei Überschneidung mit eigenen offenen Dateien
  erst prüfen, dann zusammenführen.
- Eigene unfertige Arbeit bleibt ungestaged aus dem Merge-Commit heraus.

**Takt (Robert, 12.09.2026, während zwei Sitzungen und eine Codex-Sitzung im
selben Baum arbeiteten):** „alle dateien bearbeiten, codex committet und pusht
nach jedem abgeschlossenen punkt wie du es machen sollst." Also: **nach jedem
abgeschlossenen Punkt ein Commit und ein Push**, nicht erst am Ende eines
Reviews — kleine Einheiten, davor die betroffenen Tests, ruff, format und
mypy; das geteilte Tor an Meilensteinen. Und **keine Dateisperre zwischen
den Sitzungen**: Jede darf jede Datei bearbeiten, weil der schnelle Takt das
Fenster für Überschneidungen klein hält. Fremde Hunks in einer geteilten
Datei reiten dann mit — Robert nimmt das in Kauf; `git diff --cached --stat`
vor dem Commit lesen und im Betreff nichts behaupten, was ein fremder Hunk
tut ([[zweite-sitzung-im-selben-baum]]).
