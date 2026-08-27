---
name: session-apply-meldet-statt-zu-werfen
description: Session.apply fängt jeden AppError und schickt ihn per Signal — ein try um den Aufruf läuft ins Leere.
metadata:
  type: project
---

`app/ui/session.py` — `Session.apply` fängt jeden `AppError` und schickt ihn
über das Signal `failed` an die Oberfläche. Es **wirft nicht**. Ein
`try`/`except` um den Aufruf greift deshalb nie.

Gefunden am 26.08.2026 beim Reparieren einer liegengebliebenen Quelle nach
abgelehntem Import (`1dbddbb4`): Mein erster Fixversuch war genau so ein
`try`, und der Test blieb rot mit „DID NOT RAISE".

**Why:** Von außen sieht ein abgelehnter Aufruf aus wie „nichts passiert" —
keine Ausnahme, keine Operation. Dabei kann sehr wohl etwas geschrieben worden
sein, das vorher entstand (hier: die eingebettete Quelle, hunderte Megabyte,
ohne dass `_dirty` gesetzt wurde — der Kunde schließt ohne Nachfrage).

**How to apply:** Nach dem **Ergebnis** fragen, nicht nach dem Grund:

    before = len(self.project.document.ops)
    self.apply(titel, [draft])
    if len(self.project.document.ops) == before:
        # abgelehnt — aufräumen, was vorher entstand

Das trägt jeden Ablehnungsgrund, der noch dazukommt, und ist unabhängig davon,
ob eine spätere Fassung wirft oder meldet. Wo mehrere Transaktionen folgen
(`core/generate.py`), ist die Grenze **vor** dem Schreiben zu fragen statt
hinterher aufzuräumen. Das Warnschild steht auch in
`konzepte/konzept-aktivierungsserver-2026-08.md`, Teil A.
