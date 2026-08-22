---
name: fehlertexte-ohne-platzhalter
description: "Ein {platzhalter} in AppError.detail oder title bleibt wörtlich stehen — Werte gehören in values, nicht in den Satz."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 493de4ef-2355-4029-9d86-1e68996c4909
  modified: 2026-08-07T05:39:21.938Z
---

In Formwerk formatiert **einen Fehlertext niemand nach**. `show_details` in
`app/ui/dialogs.py` zeigt `str(error.detail)`, wie es ist, und hängt die
`values` als eigene `key: value`-Zeilen darunter. Ein `{platzhalter}` in
`detail` oder `title` erscheint dem Nutzer also mit geschweiften Klammern.

In der Oberfläche ist derselbe Platzhalter **richtig**: dort steht ein
`.format` dahinter — `tr("{grams} g").format(grams=...)`,
`tr("Bauraum {x} × {y}").format(...)`. Nur die Fehlerpfade aus dem Kern haben
das nicht.

**Warum:** Ich bin am 07.08.2026 zweimal hintereinander in dieselbe Falle
getappt, weil die 15 vorhandenen Message-IDs mit Platzhaltern wie ein Beleg
aussehen, dass es geht. Sie sind alle aus der Oberfläche.

**Wie anwenden:** Wert in `values={...}`, Satz ohne Klammern. Seit „Fällt
ComfyUI weg" (cbef2f7) sucht `tests/test_errors.py` im ganzen `app/core/`
danach — der Test ist der eigentliche Merker, diese Notiz erklärt nur, warum
er da ist.

Verwandt: [[comfyui-installation-d-ai]].
