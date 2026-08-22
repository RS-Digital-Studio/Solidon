---
name: version-vor-jedem-bau-erhoehen
description: Vor jedem ausgelieferten Bau die Fassung selbst erhöhen — nicht fragen; tools/bump_version.py macht beide Stellen.
metadata: 
  node_type: memory
  type: feedback
  originSessionId: d0bd4b75-5327-4ced-9591-8a6ee286ce59
  modified: 2026-08-20T19:52:32.430Z
---

Vor jedem Bau, der ausgeliefert wird, steigt die letzte Stelle der Fassung um
eins — **ohne Rückfrage**. Am 20.08.2026 habe ich stattdessen gefragt
(0.1.0 → 0.1.1), und Robert hat klargestellt: „du sollst das automatisch
machen".

**Why:** Die Zählregel steht im Projekt (`app/branding.py`) und in Roberts
globaler Vorgabe. Zwei Pakete mit derselben Nummer kann niemand
auseinanderhalten — nicht der Über-Dialog, nicht der Update-Hinweis
([[solidon3d-update-hinweis]]), nicht der Support vor einem Fehlerbericht. Die
vorderen Stellen sind dagegen eine Entscheidung und gehören ihm.

**How to apply:** `tools/bump_version.py` (seit 20.08.2026) fasst beide Orte
an, die die Zahl tragen — `branding.py` und `pyproject.toml`. Aufgerufen wird
es **vor** dem Prüfmodul und dem Bau; danach trüge das Paket eine Nummer, die
es schon gab. `website/version.json` bleibt dabei liegen: Sie sagt, was
veröffentlicht *ist*, und wird zuletzt hochgeladen. Der Weg steht vollständig
in der Skill `/erzeugen`.
