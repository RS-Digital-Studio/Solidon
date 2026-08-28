---
name: durchsicht-je-version
description: "Roberts Anweisung: je Version ein Durchsicht-HTML (Artifact), und jede neue Durchsicht beginnt mit dem Übertrag — jeder offene Punkt der Vorversion wird am Code nachgemessen, nicht aus dem alten Bericht geglaubt."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 4b04ef49-824b-4a2f-b73f-e5a5b3ebc8a1
  modified: 2026-08-28T06:21:25.319Z
---

Robert am 28.08.2026, nach der Durchsicht v0.2.1: Das Durchsicht-HTML gibt es
ab jetzt **für jede Version**, „mit kontrolle ob von der vorherigen version
noch etwas offen ist".

Der Prozess:

1. **Je Version ein eigener Bericht** (eigene Datei → eigene Artifact-URL),
   Titel „Durchsicht v<version>". Der Bericht der v0.2.1 lief unter
   https://claude.ai/code/artifact/a4b10e16-9762-40cb-a39b-6b0ff1ca35bd —
   Aufbau und Tonlage dort sind der Maßstab (Robert: „das mit dem durchsicht
   html ist aber gut kannst du beibehalten"): je Befund Schwere, Fundstelle,
   Messverfahren und Verifikationsstand; Kacheln oben; „geprüft und in
   Ordnung" als eigener Block.
2. **Erster Abschnitt jeder neuen Durchsicht ist der Übertrag**: jeden
   offenen Punkt des Vorgänger-Berichts am Code **nachmessen** — behoben oder
   weiter offen — und das Ergebnis ausweisen. Nicht den alten Status
   abschreiben: zwischen zwei Versionen arbeiten mehrere Sitzungen, und ein
   Bericht altert wie die Statustabellen der Konzepte.
3. Der Bericht wird während der Durchsicht **fortgeschrieben** (gleiche URL,
   Redeploy) — Befunde wandern auf „behoben", sobald der Fix freigegeben und
   committet ist.

**Why:** Ohne den Übertrag verlässt sich die nächste Version darauf, dass
„offen" im alten Bericht noch stimmt — dieselbe Falle wie die Statustabellen
der Konzepte (von zwölf als offen geführten Punkten waren sieben längst
behoben). Der Bericht ist die Review-Sicht je Version; das Register in
ROADMAP.md bleibt die einzige Quelle offener **Arbeit**.

**How to apply:** Beim ersten Review-Auftrag nach einem neuen Tag (oder vor
einem Release-Bau): alten Bericht öffnen (Artifact-Liste), offene Befunde
herausziehen, jeden am aktuellen Code messen, neues Artifact „Durchsicht
v<neu>" mit Übertrags-Abschnitt anlegen. Befunde, die offen bleiben und nicht
sofort bearbeitet werden, gehören zusätzlich ins ROADMAP-Register — der
Bericht ersetzt das Register nicht ([[erinnerungen-liegen-im-repository]],
Registerregel in CLAUDE.md).
