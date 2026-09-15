---
name: kurze-texte-in-der-app
description: "Robert will in der Anwendung kürzere Texte, die trotzdem verständlich bleiben — Befunde, Panel-Sätze, Absagen: ein bis zwei kurze Sätze, der Rückweg dabei"
metadata:
  node_type: memory
  type: feedback
  originSessionId: ff13e034-c33c-4f89-a613-b869d0c1b6bd
  modified: 2026-09-15T14:00:00.000Z
---

Robert am 15.09.2026, mitten in der Durchsicht der Merkmalserkennung: „achja
kürzere Texte, aber trotzdem verständlich wäre auch besser bei allem in der
app." Gemeint sind Befunde im Prüfbericht, die grauen Zeilen des
Merkmalspanels, Absagesätze der Operationen, Parameterhilfen — alles, was
der Kunde in der Oberfläche liest.

**Why:** Ein Befund wie „Nach diesem Schritt zerfällt der Körper in Teile, die
einander nicht berühren. Prüfen Sie das Ergebnis; Strg+Z nimmt den Schritt
zurück." sagt in 20 Wörtern, was „Der Körper zerfällt nach diesem Schritt in
lose Teile. Strg+Z nimmt ihn zurück." in 13 sagt. Der Prüfbericht zeigt viele
Zeilen untereinander; jede lange verdrängt die nächste.

**How to apply:** Neue Kundentexte (`_()`-Strings in `app/`) auf ein bis zwei
kurze Sätze bringen: erster Satz, was ist; zweiter Satz, was zu tun ist —
mit dem Rückweg (Strg+Z, „Diesen Schritt ändern“), wo es einen gibt. Keine
Nebensätze mit „die einander …“, keine doppelten Handlungsvorschläge. Alle
sechs Kataloge in `app/i18n/locales/` ziehen mit (kurz auch dort). Bestand
nicht in einem Zug umschreiben — Robert hat den Bestand nicht beauftragt —,
aber jeden Text, der ohnehin angefasst wird, kürzen. Siehe
[[aus-kundensicht-perfekt]] und [[nicht-nach-ki-klingen]].
