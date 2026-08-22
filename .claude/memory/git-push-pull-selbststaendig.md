---
name: git-push-pull-selbststaendig
description: "Robert will, dass ich push und pull immer selbst mache — ohne zu fragen, aber erst nach grüner Suite."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: e828bb8c-574f-465c-baa0-bfcac75d3cde
  modified: 2026-08-18T07:04:22.807Z
---

`git pull` und `git push` mache ich in diesem Repository **selbstständig**,
ohne Rückfrage (gesagt am 18.08.2026).

**Warum:** Robert arbeitet oft in mehreren Sitzungen am selben Repository
([[parallele-sitzungen-solidon3d]]); ein Stand, der nur lokal liegt, ist für
die anderen Sitzungen nicht da. Nachfragen kostet einen Zug und bringt keine
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
