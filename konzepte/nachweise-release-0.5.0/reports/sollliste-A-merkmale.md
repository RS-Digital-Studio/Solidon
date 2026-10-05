# Sollliste Teil A — Merkmale, Muster, exakter Körper (Unterprüfer der Sollliste, 22.09.2026)

Die meisten Versprechen hält der Code, oft mit Einschränkungen. Das Kernversprechen der Presse hält er nicht: Aus einer heruntergeladenen STL, OBJ oder 3MF wird kein exakter Körper, und STEP gibt es dafür nicht. Alle 26 Presse-Mails sind noch Entwürfe (`X-Unsent: 1`), lassen sich also vor dem Versand korrigieren.

| ID | Einlösung | Urteil | Beleg bzw. was fehlt | Risiko |
|---|---|---|---|---|
| A1 | Erkennung beim Auswerten, `app/core/types.py:51-65`; Namen `app/ui/labels.py:2113-2154`; `tests/test_features.py`, `test_matching*.py` | teilweise | Alle genannten Arten gibt es (Kehle = Torus-Nut, Hohlkehle = konkave Verrundung). „Die Kennung überlebt" gilt nicht allgemein: RM-210, RM-211, RM-189. An überwiegend gekrümmten Modellen lässt der Freiformfilter Kugeln, Ringe, Kegel und Verrundungen weg. | Passung auf Verrundung kann nach Drehung still umspringen. |
| A2 | `resize_hole` Felder Durchmesser, Änderungsumfang, X/Y/Z (`prepare_ops.py:4308-4392`); Vorschau `Session.preview_async` | teilweise | An einer erkannten STL-Bohrung ist die **Tiefe kein Feld**, nur Auskunft (`app/ui/CLAUDE.md:217-219`). Website-Bild (`funktionen.html:153-155`) zeigt sie als Feld. „Achse" nur x/y/z beim Drehen. | Kunde sucht Tiefenfeld. |
| A3 | move/rotate/duplicate/remove/resize; `test_exact_feature_ops.py` | eingelöst | Absagen mit Grund (`HOLE_IS_NOT_EMPTY`, `NO_OWN_BODY`). An STL bleibt Netz. | gering |
| A4 | `bore_advice` (`app/core/scene/placement.py:251-348`), `panels.py:5554` | **an STL nicht eingelöst** | „Durchgangsloch für M5" nur bei nativer Quelle (`placement.py:307-327`). Sonde Netzbohrung Ø 5,19: „Bohrungsmaß: 5.19 mm (geschätzt). Eine passende Schraubengröße ist damit nicht sicher bestimmt." Test `test_matching.py::test_bore_advice_distinguishes_a_measurement_from_a_known_screw` schreibt `"M5" not in text` fest. | Aufmacher der Funktionsseite („In einer fremden STL") nicht erlebbar. |
| A5 | „Auf alle N gleichartigen", `relations.alike_for_actions` | eingelöst | Gruppen nur bei belegter gleicher Form/Rolle. | verrauschte STLs evtl. ohne Gruppe |
| A6 | `FeaturePanel.show_pair` | eingelöst | Mitte zu Mitte. | Verwechslung mit Wandabstand |
| A7 | `applies_to`; `actions.fillet_blocked` | teilweise, Text falsch | „Kehlen ausgenommen" überholt (Kehle = Torus, alle fünf Handlungen; Hohlkehle zwischen zwei Ebenen bearbeitbar). | Website vs Changelog |
| A8 | `Viewport._show_ghost` | eingelöst | | |
| A9 | `_drag_shadow`, `_fade_selection` | eingelöst | | |
| A10 | `TransformBar.limit_roles` | eingelöst | | |
| A11 | PlacementFlow, `FeaturePanel.set_measuring` | umgesetzt, Abnahme offen | RM-197/199, P0.3/P0.4, P5.1; nur Bohrungsweg im Bild. | frisch umgebaut |
| A12 | `resize_hole.entrance_mode` keep/follow | eingelöst, auch an STL | | |
| A13 | `patterns_instead_of_cells` (`patterns.py:341`) | teilweise | Erkennung in fremden Netzen an ebenen Trägern belegt. **Neu setzen nur bei acht eigenen Stilen im Solidon-Gitter**; sonst `other`, nur entfernbar. Muster um Zylinder nur an `apply_texture`-Ausgaben getestet. | Testanleitung der Presse scheitert wahrscheinlich |
| A14 | `texture_actions`, `texture_steps_of` | eingelöst | nur ebene Fläche | gering |
| A15 | exakter Körper, Bausteine exakt | eingelöst am exakten Körper | Bausteine nur auf exaktem Träger exakt; gemischter Eingang → Netz. Changelog „Kuppe", Oberfläche „Kuppel". | STL-Nutzer hat nichts davon |
| A16 | keiner | **nicht eingelöst** | Keine Umwandlung Netz → exakt unter 136 Ops; `load` ohne Option; P4.0–P4.3 offen. STEP im Exportdialog nur bei exaktem Körper (`main_window.py:6807-6815`), Schreiber lehnt Netz ab (`writer.py:665-668, 696-727, 1500-1511`). | **Hoch.** Kunde erwartet STEP aus STL |
| A17 | `thread_size_for`, `thread_counterpart_draft` (`counterpart.py:364-412`) | teilweise | Gegenstück nur mit Solidon-erzeugten Gewinden getestet. Gangzahl/Händigkeit nur am exakten Körper; am Netz Gangzahl fehlt, Händigkeit geraten (`helix.py:558-570`). Linksgewinde → Absage. | STL-Mutter bekommt weniger als versprochen |
| A18 | `measure_sources`, `measure_qualifier`, `measure_explanation` (`actions.py:43-85`) | teilweise | Sichtbar nur „geschätzt", „Vorgabemaß", „Maßherkunft nicht bestimmt"; „gemessen / eingepasst / aus dem Schritt" nirgends. | Wortlaut weicht ab |
| A19 | `reserved_feature_ids` | teilweise | RM-210/211/189 widerlegen „jedes Merkmal bleibt unter seinem Namen". | Passungen wechseln Bezug |
| A20 | fillet/chamfer/bead/push_face/draft ohne `requires_kind` | eingelöst | | |
| A21 | `detect_region`, `local.detect_local` | eingelöst (Netz) | | |
| A22 | `MIN_CYLINDER_DIAMETER = 0.5` (`features.py:156-167`) | teilweise, irreführend | Keine Prozesslogik je Drucker (Presse 16 behauptet sie). | |
| A23 | Leistungstests | überwiegend Einzelmessungen | siehe unten | Redaktionen messen anders |

## Leistungszahlen (A23)
- cl:47 Erkennung 200 000 Dreiecke in 1 s: Lochplatte 0,99 s (RM-208), RM-132 1,1 s; organisch 3,83 s (RM-193); §31 verlangt beide < 1 s.
- cl:55 Bohrungsklick ein Viertel: nur Review-Block ROADMAP.md:1727.
- cl:60 Noppenfeld 4 statt 12 s: nur Commit 0b4e604a.
- cl:79 Volumen „in Millisekunden": gemessen 0,2 s.
- cl:80 Gewinde und Bolzen: ROADMAP-ARCHIV; als Operation 0,55 s.
- cl:112 Formabweichung Dose 11,8 s → 98 ms: kein Test.
- cl:114 Orientierung 1 M Dreiecke 35 → 5,4 s: Leistungstest misst anderes.
- cl:135/136 Verschieben 0,5 s, Drehen 0,6 s, Undo 0,2 s: kein Test.
- cl:137 Vorschau „ein Achtel": nicht belegt (0,57 → 0,13 s unter Fremdlast, an anderer Stelle 0,04 s).
- cl:138 Aushöhlen ein Fünftel schneller: Commit 75e36a02 misst 7–25 %.
- Kein Leistungslauf für 0.5.0 im Register; P5.3 offen.

## Widersprüche zwischen Texten
1. Exakter Körper aus dem Netz: Presse pr 01:23-28, 07:38-40, 09:24-28, 13:29, 16:34-35, `marketing/presse-0.5.0/README.md:33`, pr 04:25-26 — gegen Website `funktionen.html:756, 831-833` und ROADMAP. Richtig nur pr 18:36 und `changelog/de.md:71`.
2. „Kehle": Website „Kehlen … ausgenommen" (`funktionen.html:135-136`, `index.html:914-916`) vs Changelog `de.md:72`.
3. „Durchgangsloch für M5" im STL-Abschnitt; Code sagt „geschätzt … nicht sicher bestimmt".
4. Maßherkunft: cl:51 und Presse 09/15/18 „gemessen / eingepasst / aus dem Schritt" vs UI.
5. Importierte Gewinde: cl:50, pr 13/15/18 Gangzahl und Händigkeit „am Netz".
6. Auflösungsgrenze: pr 16 Druckverfahren vs Code profilunabhängig.
7. Muster neu setzen: pr 01, 07, README an jedem Rändel.
8. Kuppe/Kuppel; Tiefenfeld im Website-Bild; Leistungszahlen.

## Nebenbefunde
- `FEATURE_TITLES` (`app/core/registry/registry.py:517-532`) fehlt „torus"; Agent-Ortsangabe (`app/core/agent/tools.py:381`) sagt wörtlich „…torus…".
- `bore_advice(ask=True)` bietet an Netzbohrung Ø 5,19 „M4, M6" an, nicht M5 (`_sizes_around`, `placement.py:388-399`); latent, beide Aufrufer `ask=False`.
