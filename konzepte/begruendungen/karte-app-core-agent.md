# Begründungen zu `app/core/agent/CLAUDE.md`

> Stand 27.09.2026. Aus der Karte verschoben, als sie auf Module, den Zug und
> die Stolperfallen verdichtet wurde. Die Karte steht dort; hier stehen die
> ausführlichen Fassungen, das Warum und die Messwerte und Anlässe ihres Tages —
> wörtlich, gegliedert nach den Überschriften der Karte. *Früher unter …* nennt
> die Stelle der alten Karte.

## Vorschlag und Übernahme

*Früher unter „Er bekommt keine Sonderwege“.*

`apply.auto_acceptable()` behandelt eine belegte Umwandlung exakter Körper
als bewusste Übernahme, auch wenn der Befund nur Informationsstufe trägt.
`Finding.converts_exact_body` ist die gemeinsame fachliche Erkennung. Der
Vorschlag bleibt mit seiner Vorschau offen; seine manuelle Annahme bleibt
genau eine Transaktion und wird durch ein Undo vollständig zurückgenommen.
`checks.check()` reicht neu entstandene Konvertierungsbefunde bis an die
Werkzeugantwort und den Vorschlag weiter. Bereits vor dem Zug vorhandene
Umwandlungen sperren keinen späteren, unabhängigen Vorschlag.
`apply.changes_for()` bereitet Parameter, Passungen und Druckziel für
Vorschau und Annahme aus dem jeweils aktuellen Dokument vor.
Endet ein Zug mit ungeprüften Projektangaben, wertet `AgentSession` die
Arbeitskopie abschließend aus. Ein reiner Hauptmaß-, Passungs- oder
Druckzielwechsel erhält damit dieselben Befunde vor der automatischen
Übernahme wie ein Operationsschritt. Hat ein späterer Schritt diese Werte
bereits geprüft, entfällt die doppelte Rechnung.

## Was für alle gilt, steht im Systemprompt

*Früher unter „Was für alle gilt, steht im Systemprompt“.*

Zwei Fälle sind so gelöst: `objects` stand wortgleich in 79 Werkzeugen, die
sechs Platzierungsangaben eines Bausteins (`x`, `y`, `z`, `axis`, `angle`,
`at_feature`) in allen 27. Gemessen am 31.08.2026 fiel die Grundlast dadurch
von **24 161 auf 19 641 Token**.

*Früher unter „Was der Prompt verspricht, müssen die Werkzeuge tragen“.*

Der Systemprompt und die Werkzeugschemata sind zwei Quellen über dieselbe
Sache, und sie laufen auseinander, ohne dass etwas rot wird. Bis zum
31.08.2026 sagte der Prompt in jedem Zug „der Ort steht in jeder
Werkzeugbeschreibung (‚Menü: …')" — und `tool_schemas(compact=True)` lässt
genau diesen Ort weg: 95 Werkzeuge nennen ihn im vollen Schema, **null** im
kompakten, und das kompakte bekommt jedes lokale Modell.

## Das Angebot für ein lokales Modell

*Früher unter „Ein lokales Modell sieht jedes Werkzeug, aber nicht jedes ausführlich“.*

`session.py` entscheidet einmal, ob kompakt gefahren wird (`backend.id ==
"ollama"`), und dann baut `offer.ToolOffer` das Angebot des Zugs: jede
Operation in Registerreihenfolge, **ausführlich** — Kurzfassung der Felder aus
`tools.operation_tools(compact=True, part_placement=True)` plus „Ort: …",
Bausteine also mit ihren zehn Ortsfeldern ohne Satz — nur die gemeinten, alle
übrigen als **Kurzform** (Titel, `STUB_MARK` am Ende, keine Felder). Gemeint
heißt: `registry.search.rank_operations` über die Anfrage und die letzten
Nutzerbeiträge (dieselbe Faltung, dieselben Stämme wie die Befehlspalette,
von den Kundenwörtern nur `SYNONYMS` — die Wendungen je Sprache aus
`CUSTOMER_WORDS` bleiben der Palette, siehe `.claude/rules/agentenschicht.md`), dazu an einem gewählten Merkmal die Handlungen aus
`perceive.actions.ACTION_ORDER` und in einer leeren Szene die sichtbaren
Grundkörper — höchstens `DETAILED_LIMIT` von sich aus. Titel und Menüweg,
die das Angebot selbst in eine Beschreibung setzt, gehen durch
`tools.framed_if_foreign`: Bei einem mitgereisten Rezept enden beide mit
dessen fremdem Titel (§32). Ein versteckter Zwilling bleibt Kurzform, solange
das Modell ihn nicht anfordert; ausführlich trägt er an beiden Wegen den Satz
aus `tools.second_choice_note`, der das Werkzeug der ersten Wahl nennt.

Ruft das Modell eine Kurzform auf, **wird nichts ausgeführt**: Die Sitzung
antwortet mit `ToolOffer.introduce`, zählt den Aufruf unter
`Proposal.lookups` (nicht unter `tool_calls`, nicht unter `invalid_calls`) und
schickt ab dem nächsten Schritt das ausführliche Schema. Was `find_part`
findet, steht im nächsten Schritt ebenfalls ausführlich da. Der Prompt sagt
beides in `prompt._OFFER_HINT` (Prompt-Version 8).

Gemessen am 25.09.2026 mit qwen3:14b: 30 461 Token für die Kurzfassung aller
153 Werkzeuge gegen 7 258 für die Grundlast des Angebots.
`tests/test_tool_offer.py` hält die Zusagen: keine Operation verschwindet,
eine Kurzform führt nichts aus, das Angebot bleibt unter einem Drittel.

## Änderungen werden gemessen, nicht behauptet

*Früher unter „Änderungen werden gemessen, nicht behauptet“.*

**Er braucht einen hinterlegten Schlüssel, und der ist nicht auf jeder
Maschine da.** Ohne ihn endet der Läufer sofort mit „Kein Sprachmodell
erreichbar" (Exit 2) — geprüft wird mit `keys.read("anthropic")`. Der Weg
über Ollama steht offen, taugt für diese Frage aber nicht: Die volle Suite
endete dort bei 4 von 33 mit 17 Zeitüberschreitungen, und eine Quote, die von
der Auslastung der Maschine handelt, misst nicht den Prompt. Wer eine
Änderung nicht abnehmen kann, sagt das — „gebaut und gemessen, aber nicht
abgenommen" ist ein gültiger Stand.
