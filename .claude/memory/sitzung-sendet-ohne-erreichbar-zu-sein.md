---
name: sitzung-sendet-ohne-erreichbar-zu-sein
description: "Eine Peer-Sitzung kann Nachrichten schicken und trotzdem für niemanden adressierbar sein — ihre Post läuft ins Leere, ohne dass sie es merkt."
metadata: 
  node_type: memory
  type: project
  originSessionId: 53c1fb55-27df-41fb-b9f1-4c8c4f15941d
  modified: 2026-08-27T07:01:50.322Z
---

Der Kanal zwischen Sitzungen ist nicht zwangsläufig beidseitig. Am 27.08.2026
schickte `3d-druck-30` mehrere Nachrichten (Commit-Meldungen, eine Warnung
über absichtlich rote Tests), während sie gleichzeitig

- **nicht in `ListAgents` auftauchte**,
- jedes `SendMessage` an ihren Namen mit „No agent named" abwies,
- und ihre eigene `from`-Pipe-Adresse als „not a local socket address"
  zurückwies.

Zwei Sitzungen haben das unabhängig beobachtet. Ihr Torprozess lief dabei und
hielt das Schloss — die unangenehmste Kombination: Sie belegt eine Ressource,
sie schreibt in gemeinsame Dateien, und niemand kann sie erreichen.

**Was daraus folgt, wenn eine Sitzung nicht antwortet:** Nicht „sie ist weg"
annehmen. Sie liest möglicherweise mit und arbeitet weiter — nur kommt nichts
bei ihr an. Ein an sie adressierter Befund (27s drei Funde aus
`app/core/brep/`) ist damit **nicht übergeben**, sondern verloren; er braucht
einen anderen Empfänger oder das Register in `ROADMAP.md`.

**Und für die eigene Seite:** Wer sicher gehört werden will, schreibt zuerst
selbst — dann steht die eigene Adresse in der Nachricht des anderen. Umgekehrt
ist das keine Garantie, die Antwort über die `from`-Adresse kann ebenfalls
scheitern.

Verwandt: [[parallele-sitzungen-solidon3d]], [[weitergegebene-anweisungen-gelten]].
