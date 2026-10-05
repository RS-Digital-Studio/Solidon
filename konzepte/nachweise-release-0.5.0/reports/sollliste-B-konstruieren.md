# Sollliste Teil B — Konstruieren, Bausteine (Unterprüfer der Sollliste, 22.09.2026)

34 Versprechen gegen HEAD 9307a844. Klar nicht eingelöst: B13 (Kontextmenü einer Fläche ohne Bausteine), B15 (Bereichstest über alle Bausteine läuft nirgends). Sonden unter `…\scratchpad\B\`. Fenstertests nicht gefahren.

| ID | Einlösung | Urteil | Beleg bzw. was fehlt | Risiko |
|---|---|---|---|---|
| B1 | Werkzeuge `sketch_editor.py:4919-4940`; 15 Bedingungsarten + Konzentrisch `:283-301`; Freiheitsgrade `status_text` `:1750-1820` | teilweise | „unten steht jederzeit, was noch frei ist": bei aktivem Zeichenwerkzeug steht dort der Werkzeughinweis (`:1762-1775`). Website „gleiche Länge", App „Gleich groß". §30.1 fehlen fünf Arten (RM-175). | gering |
| B2 | sketch_extrude/pocket/revolve/sweep/loft (`sketch/ops.py:454/738/963/1086/1228`) | eingelöst (Kern), Fenster offen | Führen mit gezeichneter Bahn, Überblenden mit gezeichnetem Umriss nie am Fenster (RM-183). | mittel |
| B3 | Skizzen-Ops exakt (`sketch/ops.py:470` `require()`) | teilweise | STL/3MF/OBJ facettiert (≤0,05 mm, `units.py:51`); spätere Netz-Op macht Netz; ohne Kern verweigert. | gering |
| B4 | Rasterfang, Maß am Zeiger, Zeichenebene | eingelöst (Code) | Fensterabnahme RM-183. | gering |
| B5 | `_does_phrase` `sketch_editor.py:611-652`; `drawing_hint :1861-1934` | teilweise | **Vieleck und Langloch ohne Zweig in `drawing_hint`**; Satz nur im Tooltip (`:4668-4669`); kein Test, dass jedes Werkzeug einen Hinweis hat. | mittel |
| B6 | „Auf dieser Fläche zeichnen" `panels.py:2530-2560` | eingelöst | | |
| B7 | Sonde `dose-mit-deckel.p3d` wand 2,4→3,6 | eingelöst | Dose 34 682→51 954 mm³, Deckel 31 693→29 897 mm³, Passung bleibt. | |
| B8 | ParameterPanel | eingelöst | | |
| B9 | „Ändern …" Grenzen | eingelöst | | |
| B10 | Verlauf Mehrfachauswahl, „Schritt löschen …" | teilweise | **Verschieben/Umsortieren gibt es nicht** (P7.2 offen); Website fk:290 verspricht es. | mittel |
| B11 | `ValueField` fx `op_dialog.py:147-176` | teilweise | (a) Beispiel `schraube_m4 + spiel` wird abgewiesen, Namen brauchen `@` (`expressions.py:15,114`); richtig `=@schraube_m4 + @spiel`. (b) Anzahl-Feld (`produces_from`) ohne fx (`op_dialog.py:2362-2368`). (c) „Vorn zwei bis drei Werte": 60 von 136 Ops 4–8 Felder vorn. | mittel |
| B12 | 136 Ops; CLI; Chat | teilweise | „Kontextmenü sieht dieselbe Deklaration" stimmt nicht mehr (Rechtsklick ohne Ops seit 11.09.); ix:107/922 betroffen. | mittel |
| B13 | Kontextmenü `panels.py:2375-2403` („Keine Operationen mehr", 86c4975a); Bausteine über Knopf rechts, Datei → Bausteinkatalog, Strg+K, Palette | **nicht eingelöst** | fk:330-332, ix:640-642 (Stand 26.08.) bewerben Bausteine per Rechtsklick an der Fläche. Bauplan §2.6, cl:337, Test sagen das Gegenteil. | hoch (Website überholt) |
| B14 | 35 Bausteine in 6 Gruppen; 51 Normeinträge | eingelöst (Zahlen) | „Geprüft" hängt an B15; RM-017; RM-138. | mittel |
| B15 | `range_check.check_part :1491` ohne Aufrufer in app/tools; Komplettlauf seit 4bcb0272 (03.09.) gefallen | **nicht eingelöst** | Kein Test/Werkzeug/gespeichertes Ergebnis fährt die 35 über den Bereich; 8 neue Bausteine nie gefahren. **Katalog unterdrückt die Warnung bei mitgelieferten Bausteinen mit falscher Begründung** („wird in der Suite über seinen ganzen Bereich gefahren", `catalog.py:923-949`). RM-206 zählt „27". | hoch |
| B16 | Absage mit Vorschlag `parts/ops.py:1491-1523`; Katalogsperre | teilweise | Solidon fragt nicht nach: Vorschau auf größte nach oben zeigende Fläche (`placement_flow.py:2289-2295`). | gering |
| B17 | „Diesen Schritt ändern" | eingelöst | | |
| B18 | „Auswahl als Baustein speichern …" | eingelöst | Dialog fragt Name, Gruppe, Beschreibung, Lizenz, Autor + Maße + Stellen; Alt-Text nennt Lizenz/Autor nicht. | gering |
| B19 | apply_texture, Prüfung vor dem Rechnen | eingelöst | | |
| B20 | Relief, Gitter füllen | eingelöst | nur Körper mit Hohlraum | |
| B21 | exakte Grundkörper, Boolesche, drill_hole | eingelöst | | |
| B22 | Transformationen, Muster, align | eingelöst | | |
| B23 | hollow, thicken, lid, screw_lid, shell_exact, thread_exact | eingelöst | Website „verdicken", App „Offene Fläche schließen" (`mesh_ops.py:1500`). | gering |
| B24 | Profilklemmen | teilweise | „Zur gewählten Normgröße": **nur M4** (`profile_clamp_ops.py:185-188`, `profile_clamps.py:243-246`). | gering–mittel |
| B25 | create_seal | eingelöst (Kern), Fenster offen | RM-184. | mittel |
| B26 | blend, subdivide, sculpt (6 Pinsel), pose | eingelöst | „ein Schritt": nur die Formsitzung; `website/teile/weg4-stein-formen.p3d` zwei Formschritte, kein Verschmelzen. | gering |
| B27 | label_text, 8 Schriften, Slots | eingelöst | Fett/Kursiv nur für 6 der 8 Schriften. | gering |
| B28 | Organizer | eingelöst | | |
| B29 | Lochfeld | eingelöst | | |
| B30 | SVG/DXF | eingelöst | | |
| B31 | Agent set_parameter | nicht prüfbar ohne LLM | Neu rechnen nach Maßänderung Dose 1,0 s. | mittel |
| B32 | `website/teile/*.p3d` | teilweise | Gehäuse 13 Schritte, nicht „zwölf" (Schritt 13 seit 05645f54). Dateien Format 19 / 0.2.2 (aktuell 29). | gering |
| B33 | Schnittansicht, Explosion, Messen | eingelöst (Code) | | |
| B34 | Menüwege | teilweise | Falsch: „Teil wählen → rechts Prüfstück erzeugen" — `test_piece` nur bei gewählter Bohrung/Zapfen/Fläche. | gering–mittel |

## Widersprüche Text ↔ App
1. Kontextmenü (fk:330-332, ix:640-642, ix:107/922, fk:597-599) — App: nur „Diesen Schritt ändern", „Auf dieser Fläche zeichnen", Ausblenden.
2. „Jeder Baustein über seinen ganzen Bereich getestet" (fk:339-341, ix:646-648) — Lauf fällt seit 03.09.; catalog.py-Docstring behauptet ihn.
3. `schraube_m4 + spiel` (fk:593) — abgewiesen.
4. „Vorn zwei bis drei Werte" (fk:595) — 60/136 Ops 4–8.
5. „Zwölf Schritte" Gehäuse (ix:533) — 13.
6. „Jedes Werkzeug sagt, was der nächste Klick bewirkt" (ix FAQ) — Vieleck/Langloch nicht.
7. „Verschiebung" mehrerer Verlaufsschritte (fk:290) — gibt es nicht.
8. „Zur gewählten Normgröße" Profilklemme (fk:772) — nur M4.
9. Namen: „gleiche Länge"/„Gleich groß"; „verdicken"/„Offene Fläche schließen"; README:345 „Dezimieren … Neu vernetzen" vs „Dreiecke verringern", „Glätten", „Dreiecke angleichen", „Kanten verfeinern"; README Prüfstück-Weg.
10. „Fragt nach" (fk:342) — Vorschau auf Oberseite, Kern sagt ab.
11. „Kein Vieleck" (fk:260-262, ix:656-659) — gilt für Modell/STEP, nicht STL/3MF.
12. „Der ganze Vorgang bleibt ein Schritt" (ix:509-510) — nur Formsitzung; Fett/Kursiv 6 von 8 Schriften.

## Lücken nach Schwere
1. B15 Bereichsnachweis fehlt, Katalog verschweigt es.
2. B13/B12 Rechtsklick-Weg existiert nicht mehr.
3. B11 Formelbeispiel scheitert.
4. B10 Verschieben von Verlaufsschritten fehlt.
5. B5 Vieleck/Langloch ohne Hinweis.
6. Fensterabnahmen RM-183, RM-184.
7. B32, B24, B16, B34.
8. RM-017, RM-138, RM-175.
