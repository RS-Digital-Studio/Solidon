# 0.6.1: Boolesche Operationen finden, Befehlspalette entfernen

**Stand 12.10.2026: umgesetzt für 0.6.1**, auf main mit dem Merge des Zweigs
`061/suche-und-palette` — [RM-734](../ROADMAP.md#rm-734) (`ddd82fb9b`,
`5ca7f94cb`) und [RM-735](../ROADMAP.md#rm-735) (`ea1caaf24` bis `023c9c703`).
Offen allein die Abnahme am echten Fenster beim Release (RM-213). Inventur,
Messung des Tastendrucks und die Berichte von `bedienlogik` und
`oberflaechentexte` liegen unter
[`nachweise-palette-2026-10/`](nachweise-palette-2026-10/README.md).

Entstanden am 11.10.2026 als Vorbereitung am Stand main `ee6b810fe`; Auftrag
Robert: beides in 0.6.1. Der Text darunter ist der Plan jenes Tages, ergänzt
um Roberts Entscheidung und die Funde unterwegs.

## Anlass

Fragebogen S-20261011-8c5705 (anonym, keine Rückadresse, also keine Antwort
möglich): Solidon 0.5.3 auf macOS, „Sehr gut“ 5/5. Gefehlt: „Boolesche
Operationen wären toll. Nicht jedes Objekt ist perfekt und ich hasse
Fusion 360.“

## Befund, gemessen

Die drei Booleschen Operationen gibt es seit Langem, auch in 0.5.3:
*Vereinigen* (`union_objects`, Strg+Umschalt+V), *Abziehen*
(`subtract_objects`, Strg+Umschalt+A), *Schnittmenge* (`intersect_objects`,
Strg+Umschalt+X), im Menü *Ändern → Verbinden und Abziehen*. Das Auswahlpanel
zeigt sie oben, sobald **zwei oder mehr** Körper gewählt sind
(`selection_operations.QUICK_BODIES`); bei einem Körper stehen sie dort nicht.

Der Kunde hat sie trotzdem nicht gefunden. Gemessen mit der echten Palette
(dieselbe Suche wie das Suchfeld des Auswahlpanels, `found_in_rounds`):

| Suchwort | Ergebnis |
|---|---|
| boolesch, Boolean, kombinieren, subtrahieren, Differenz, difference | „Kein Befehl passt“ |
| Boolesche Operation | *Fläche versetzen* (falsch) |
| verbinden, zusammenfügen, vereinigen, union | *Vereinigen* |
| abziehen, ausschneiden | *Abziehen* |
| schnittmenge, intersect | *Schnittmenge* |

Der Fachbegriff, den jeder CAD-Umsteiger tippt, findet nichts. Das Menü meidet
„Boolesch“ bewusst (`registry.py`, Kategorie `boolean` heißt *Verbinden und
Abziehen*), und die Kundenwörter (`registry/search.py`, `CUSTOMER_WORDS`)
kennen ihn auch nicht. Die Website nennt die drei Operationen
(`funktionen.html`), aber nie den Begriff.

Zweite Ursache: Wer aus Fusion kommt, wählt erst das Werkzeug, dann die
Körper. In Solidon wählt man erst zwei Körper; mit einem gewählten Körper
zeigt das Panel keinen Hinweis, dass es die Booleschen überhaupt gibt.

## Plan für 0.6.1

### A. Boolesche Operationen auffindbar

1. **Kundenwörter in allen sechs Sprachen** (`CUSTOMER_WORDS`, Kontext
   „Suchwörter“): für alle drei „boolesch; Boolesche Operation; Boolean;
   kombinieren“, für *Abziehen* zusätzlich „subtrahieren; Differenz“; je
   Sprache die dort üblichen Wörter (en: boolean, combine, subtract,
   difference; fr: booléen, combiner, soustraire; es/it/pt entsprechend). Das
   wirkt im Suchfeld des Auswahlpanels und in der Handbuchsuche
   (`manual_search`, Quote in `tests/test_manual_search.py` vorher und
   nachher messen). Der Agent bleibt unberührt (`customer_words=False`).
   Test zuerst: die Wörter aus der Tabelle oben in
   `tests/test_theme_and_palette.py` (`CUSTOMER_WORDS`,
   `WORDS_BY_LANGUAGE`) und ein Test „boolesch findet alle drei“.
2. **Hinweis bei einem gewählten Körper:** Stehen mindestens zwei Körper in
   der Szene und ist einer gewählt, sagt das Auswahlpanel in einer Zeile, wie
   man zu den Booleschen kommt („Zweiten Körper mit Strg+Klick wählen:
   Vereinigen, Abziehen, Schnittmenge“, Kürzel je Plattform). Keine grauen
   Knöpfe — die hat die Entscheidung vom 07.09. bewusst entfernt. Ablauf und
   Text vorher mit `bedienlogik` und `oberflaechentexte`.
3. **Website:** der Begriff „Boolesche Operationen“ auf der Funktionsseite in
   allen sechs Sprachen (`website/funktionen.html`, `website/<sprache>/
   features.html`); hochgeladen mit dem Release.
4. **Changelog** unter 0.6.1 als Eigenschaft: Die Suche findet die Booleschen
   Operationen auch unter ihrem Fachbegriff.

### B. Befehlspalette entfernen — alles über Auswahlpanel und Ansicht

Heute hängt die Palette an:

| Stelle | Was |
|---|---|
| `main_window.py`, Menü *Bearbeiten* | Eintrag *Befehlspalette …*, Strg+Umschalt+P (`_palette_action`) |
| `main_window.py`, Werkzeugleiste | Knopf *Funktion suchen … Strg+Umschalt+P* (RM-506), öffnet die Palette |
| `app/ui/command_palette.py` | der Dialog; `selection_operations.py` holt von dort `fold` und `found_in_rounds` |
| `app/ui/shortcuts_window.py` | verweist auf die Palette als Liste aller Befehle |
| Bauplan §19.2 | „Die Befehlspalette ist der Universalzugang“ |
| Handbuch (`app/core/manual.py`, `website/handbuch.html`) | „die Befehlspalette findet jede Handlung“, Wege „Befehlspalette → Auf dem Bett anordnen“, „→ Überschneidungen prüfen“ |
| Tests | `test_theme_and_palette`, `test_dialog_layout_regressions`, `test_header`, `test_interface_limits`, `test_locked_says_why`, `test_native_keys`, `test_ui`, `test_widget_lifetime` |

Ersatz ist das Suchfeld des Auswahlpanels („Weitere Operationen
durchsuchen“): Es entsteht aus dem ganzen Operationsregister und nutzt
dieselbe Suche. Vorschlag: Palette und Menüeintrag fallen weg; der
Werkzeugleistenknopf *Funktion suchen* und Strg+Umschalt+P bleiben und setzen
den Fokus ins Suchfeld des Auswahlpanels — so bleibt die Suche sichtbar
(RM-506), und es gibt nur noch eine. `fold` und `found_in_rounds` ziehen dorthin,
wo sie hingehören (`registry/search.py` oder `selection_operations.py`).

Vorher zu prüfen, Punkt für Punkt:
- **Inventur:** Jede Operation und jeder Fensterbefehl der Palette ist im
  Auswahlpanel, im Kontextmenü der Ansicht oder in einem Menü erreichbar —
  auch ohne Auswahl (*Auf dem Bett anordnen*, *Überschneidungen prüfen*) und
  an Merkmalen (`palette_entries(for_feature=…)`). Was fehlt, kommt ins
  Panel oder in die Ansicht, bevor die Palette geht.
- Bauplan §19.2 neu fassen (Ansage Robert liegt vor): Universalzugang sind
  Auswahlpanel und Ansicht.
- Handbuch-Wege, Kürzelübersicht, Tour, Website-Handbuch nachziehen; Bilder
  nur, wo die Palette darauf zu sehen ist.
- `.claude/rules/grenzen.md` (Abschnitt Suche) und `app/ui/CLAUDE.md`
  nachziehen.

### Inventur (gemessen am gebauten Fenster, [`nachweise-palette-2026-10/inventur.md`](nachweise-palette-2026-10/inventur.md))

Die Palette hat 273 Zeilen: 189 Operationen, 84 Fensterbefehle. Ohne sie:

| Ort | Zeilen |
|---|---|
| im Auswahlpanel (82 direkt, 83 als Kachel im Bausteinkatalog, 7 über Umweg) | 172 |
| nur in der Ansicht | 20 |
| nur in Menü oder Werkzeugleiste | 72 (11 Erzeuger, 61 Fensterbefehle) |
| nur über eine andere Fensterstelle (Parameterkarte, Verlauf) | 7 |
| nur per Kürzel | 1 — *Auf dem Bett anordnen* |
| nur über die Palette | 1 — *Überschneidungen prüfen* |

Das Suchfeld des Auswahlpanels kann die Palette heute nicht ersetzen:
- **Ohne Auswahl ist es verborgen** (Entscheidung Robert, `grenzen.md`:
  „Handlungen für alle Körper … ohne Suchfeld“), ebenso an acht
  Merkmalsarten und an einer Kante.
- Es durchsucht nur die Operationen der aktuellen Stufe (81 von 189); gesperrte
  verschwinden, Erzeuger, Bausteine und Fensterbefehle findet es nicht.
- Es rechnet die Treffer wie die Palette, ordnet sie aber nicht nach ihrer
  Rangfolge und zeigt die Zeile „passt nur auf einzelne Wörter“ nicht — das
  verstößt schon heute gegen `grenzen.md` (Abschnitt Suche).
- *Überschneidungen prüfen* hat im Panel einen Knopf, der auf keiner Stufe
  gezeigt wird; Szenehandlungen außer `SCENE_ACTIONS_IN_THE_CARD` stehen laut
  `grenzen.md` bewusst nur in der Palette.

### Was daraus für RM-735 folgt

1. **Ein Suchfeld, immer da.** Das Suchfeld des Auswahlpanels steht auch ohne
   Auswahl und an jeder Merkmalsart. Es durchsucht alle Operationen jeder
   Stufe, Erzeuger, Bausteine und Fensterbefehle; was zur Auswahl passt, steht
   vorn, was an ihr nicht geht, nennt seinen Sperrgrund. Rangfolge und Zeile
   „passt nur auf einzelne Wörter“ wie bisher in der Palette. *Funktion
   suchen* und Strg+Umschalt+P setzen den Fokus hinein. (Hebt die Entscheidung
   „ohne Auswahl kein Suchfeld“ auf — von Robert bestätigt, unten.)
2. **Szenehandlungen in die Karte ohne Auswahl:** alle mit `takes_whole_scene`,
   darunter *Überschneidungen prüfen* und *Auf dem Bett anordnen*;
   `SCENE_ACTIONS_IN_THE_CARD` entfällt oder umfasst alle.
3. **Erzeuger in der Ansicht oder im Panel ohne Auswahl:** Kegel, Kugel, Ring,
   Rohr, Behälter, Organizer, Profilklemme, Schraube, Schriftzug, STEP laden,
   Zeichnung hochziehen — heute nur im Menü; dazu Quader, Zylinder,
   *Modell einfügen*, *Aus Text oder Bild* und *Zeichnen*, die die Ansicht nur bei
   leerer Szene zeigt.
4. **Code:** `found_in_rounds`, `matches`, `native_key` und `fold` ziehen aus
   `command_palette.py` um, dann fällt die Datei; `surfaces._panel_place`
   nennt die Palette nicht mehr als Ort (fließt in Handbuch und
   Agentenwerkzeuge); `main_window.py`, `selection_operations.py`,
   `settings_dialog.py`, `shortcuts_window.py`. Kataloge: 13 Schlüssel je
   Sprache plus „Ort: {place}“.
5. **Unterlagen:** Bauplan §2.6, §10, §19.2, §40 P0 (Ansage Robert liegt vor);
   Handbuch (`manual.py`, Referenz „Ort: Befehlspalette → …“), Website-Handbuch
   aller Sprachen; Regeln `grenzen.md`, `oberflaeche.md`, `fenster.md`,
   `vorderseite.md`, `zeichenflaeche.md`, `agentenschicht.md`; Karten
   `app/ui/CLAUDE.md`, `app/core/registry/CLAUDE.md`; Agenten und Skills
   `solidon3d-op`, `bedienlogik`, `neue-op`, danach `tools/sync_agents.py`.
6. **Tests:** 30 Dateien, 66 Testfunktionen am fallenden Code, 37 nennen die
   Palette nur im Text (Tabelle in der Inventur).
7. **Bilder:** Ein Bild des Palettendialogs gibt es nicht; der Knopf
   *Funktion suchen … Strg+Umschalt+P* auf `main-window.png` und den
   Anleitungsbildern bleibt gültig, weil Wort und Taste bleiben.

## Entscheidung Robert (11.10.2026)

**Die Palette geht ganz.** Menüeintrag und Dialog fallen weg; der Knopf
*Funktion suchen* und Strg+Umschalt+P bleiben und setzen den Fokus ins
Suchfeld des Auswahlpanels.

**Das Suchfeld steht auch ohne Auswahl** (Punkt 1 oben). Das hebt die frühere
Entscheidung „ohne Auswahl kein Suchfeld“ auf; `grenzen.md` (Abschnitt
Auswahlpanel und Suche) wird mit RM-735 entsprechend neu gefasst.

## Funde unterwegs

| Fund | Art | Schwere | Beleg | Stand |
|---|---|---|---|---|
| Ein Wort unter vier Zeichen ohne genauen Treffer fand in der Stammrunde **alle** 273 Zeilen, ohne Lockerungszeile; Return startete die vorgewählte | Fehler, aus der Palette übernommen | mittel | `tests/test_search.py::test_a_short_word_that_matches_nothing_finds_nothing` („qqq“, „qj“, „xq“), vorher rot | behoben, `registry.search.stems_in` |
| Die Kürzelübersicht nannte *Formen*, *Skelett* und *Zeichnen* zweimal — zwei Schleifen über die obere Leiste aus zwei Sitzungen vom 08.10. | Zwilling | leicht | `tests/test_interface_limits.py::test_the_shortcut_list_names_every_row_once`, vorher rot | behoben, eine Schleife |
| Die Trefferliste brach jede zweite Zeile je Tastendruck rund zehnmal neu um | Leistung | leicht | Profil und Messung C4 (`nachweise-palette-2026-10/leistung-tastendruck.md`): Höchstwert 31,5 → 22,7 ms | behoben, Merker im Zeilenzeichner |
| Bei Suchtext rechnete `_filter` die verdeckte Karte je Tastendruck mit | Leistung | leicht | gepaarte Messung an `_filter`, je 720 Paare: Median −0,42 ms, schneller in 394/720; zweiter Lauf −0,20 ms, 469/720 | behoben, früher Ausstieg; `test_the_card_rests_while_searching_and_comes_back_at_the_new_level` |
| `test_orient.py` erwartete für *Druckoptimal ausrichten* noch die Kategorie `transform` | Test zog nicht mit | leicht | Tor vom 11.10., gepinnt nachgestellt | behoben im RM-735-Commit |

Das Review vor dem Merge (`solidon3d-review`, 12.10.) fand zwölf weitere, keinen
schweren. Die Kennungen sind die des Berichts.

| Fund | Art | Schwere | Beleg | Stand |
|---|---|---|---|---|
| F1: Die vorgewählte Trefferzeile schrieb auch Kürzel und zweite Zeile halbfett, deren letzte Zeile fiel aus dem Rechteck (`plain.font` ist eine Referenz) | Fehler | mittel | `test_search.py::test_the_chosen_hit_sets_only_its_title_in_bold`, vorher rot | behoben, Kopie der Schrift |
| F6: „Wiederholen“ wählte *Kopien in Reihe oder Kreis* vor — ein Kundenwort schlug den ganzen Titel einer anderen Zeile | Fehler | mittel | `test_search.py::test_whoever_types_a_whole_title_gets_that_row_first` (sechs Sprachen, Güte und Vorauswahl), vorher rot | behoben: der ganze Titel zählt wie Titel und Kundenwort, den Gleichstand bricht N1; die zehn übrigen Vorauswahlen aus RM-734 („bewegen“ → *Verschieben*, „laden“ → *Öffnen*, „rau“ → *Glätten* …) bleiben bewusst, dort trifft das Kundenwort nur ein Wort im fremden Titel. Gegenüber 0.6.0 wählen dazu „Neu“, „Schraube“ und „Verschieben“ die Zeile mit genau diesem Titel |
| F8: Ohne Auswahl stand die Operation `load` als „Modell einfügen“ mit eigenem Dialog neben dem gleichnamigen Befehl | Fehler, Ein Text eine Wirkung | mittel | `test_ui.py::test_the_card_without_a_selection_inserts_a_model_like_the_menu`, `test_selection_operations.py::test_the_window_command_takes_the_place_of_its_operation`, vorher rot | behoben, `add_window_action(replaces=…)` |
| F10: Ein zur Laufzeit registrierter Baustein fehlte in der Suche bis zum Neustart | Fehler | mittel | `test_selection_operations.py::test_an_operation_registered_later_is_found`, vorher rot | behoben, Zeilen aus dem Register von jetzt |
| F2: *Funktion suchen* hatte keinen Fenstertest | Testlücke | mittel | drei Tests in `test_ui.py` (Lage, Startbildschirm, Zeichnung und Reiterfenster) und *Im Handbuch suchen* | behoben |
| F3: Der Pfeiltastentest blieb grün, wenn die Pfeiltasten nichts taten | Testlücke | mittel | Gegenprobe mit stillgelegtem `_step_through_hits` jetzt rot | behoben, Wort mit fünf Treffern und Kopfzeile |
| F4: Sollwert „was zur Auswahl passt“ mit der geprüften Methode gerechnet; Zeichner der Liste ungeprüft | Testlücke | leicht | `test_interface_limits.py`, `test_the_hit_list_draws_with_its_own_rows` | behoben, Sollwert aus dem Register |
| F5: Sechs Kommentare sprachen im Präsens von der Palette | Aufräumen | leicht | Bericht | behoben |
| F7: Jede neue Lage setzte die mit Pfeiltasten gewählte Zeile zurück | Fehler | leicht | `test_a_new_report_of_the_selection_keeps_the_hit_chosen_by_arrow`, vorher rot | behoben |
| F9: Am Körper mit lauter Sperren „steht oben bei den Maßen“ (seit 0.6.0) | Fehler, Regel 17 | leicht | `test_a_body_with_every_action_locked_says_why`, vorher rot | behoben, Grund an jeder Stufe |
| F11: Return in der Trefferliste lief an die Vorfahren weiter | Fehler | leicht | `test_return_in_the_hit_list_ends_there`, vorher rot | behoben, `_HitList` nimmt die Taste |
| F12: Regel `oberflaeche.md`, Zitat in `make_workshop_videos.py`, eine Testmeldung | Unterlage | leicht | Bericht | behoben |

Die Nachprüfung der Fixe fand vier weitere.

| Fund | Art | Schwere | Beleg | Stand |
|---|---|---|---|---|
| N1: Bei gleicher bester Güte entschied das Alphabet — „Tornillo“ wählte spanisch das *Agujero para tornillo* vor, „Wandhalter“ den Zwilling ohne Kundenwort | Fehler | mittel | `test_among_equal_hits_the_place_then_the_whole_title_then_the_word_decides` (fünf Sprachen, drei Lagen), Vorauswahl im Test zu F6, vorher rot | behoben: `ranked` bricht den Gleichstand nach Lage (auch Felder des Merkmalfensters), Freigabe, ganzem Titel, Kundenwort |
| N2: Der Fix zu F7 hielt auch die selbsttätige Vorauswahl über einen Auswahlwechsel fest („hinlegen“, dann Körper: Return richtete die Szene aus) | Fehler, Rückschritt aus F7 | mittel | `test_the_preselection_follows_a_new_selection_unless_chosen_by_hand`, vorher rot; Fenstersonde 437 Wörter, drei Wechsel, keiner mit alter Wahl | behoben, nur eine Wahl von Hand bleibt |
| N3: `main_window.py` zieht 17 Byte unter der Grenze Unterlagen nach | Risiko | leicht | `test_no_source_file_pulls_more_than_its_budget` | ohne Zuwachs gehalten; der Raum entsteht mit der Codestruktur (RM-722 ff.) |
| N4: Fehlendes Leerzeichen im Zitat von `make_workshop_videos.py` | Text | leicht | Bericht | behoben |
| N5: Der Schlüssel „an der Lage“ aus N1 galt auch in den ungenauen Stufen und schlug die Wertung der Wortsuche („zurück“ am Körper wählte *Objekt entfernen*) | Fehler, Rückschritt aus N1 | mittel | `test_a_loose_hit_is_ordered_by_the_word_search_not_by_the_place`, vorher rot; Sonde über 1085 Wörter: übrig nur Treffer im Titelwort an der Lage („entfernen“ an der Bohrung → *Merkmal entfernen*) | behoben, nur unter `LOOSE_RANK` |
| N6: Der Schlüssel „frei vor gesperrt“ hatte keinen Test | Testlücke | leicht | `test_among_the_best_hits_what_works_stands_before_what_is_locked` | behoben |

Weitere Vorauswahlen gegenüber 0.6.0 aus dem ganzen Titel: „Wandhalter“ ohne
Auswahl (der eigene Körper, der Baustein an der Auswahl ist dort gesperrt),
„Dichtnut“ an der Fläche, „brep“ an Körper, Fläche und Bohrung
(*Aushöhlen*, aus RM-734). Bei gleichem Titel ohne Kundenwort entscheidet der
interne Name („Schraube“ an der Fläche wählt den eigenen Körper); das bleibt
so, bis ein Kundenwort es entscheidet.

Der Funktionsdurchgang D0 (`konzept-funktionsdurchgang-2026-10.md`) und die
Durchsicht über `welle4` fanden in der Suche diese.

| Fund | Art | Schwere | Beleg | Stand |
|---|---|---|---|---|
| FD-17: „Druckbett“, „Variable“ und „Benutzerparameter“ fanden *Auf das Bett setzen* und *Parameter anlegen* nicht vorn — kein Kundenwort trug die Wörter aus Slicer und CAD | Fehler | mittel | `test_the_word_from_the_slicer_or_the_cad_names_its_action` (sechs Sprachen), Fenstertest der Suchproben, vorher rot | behoben in `8f2c5c4d6`, Kundenwörter je Sprache |
| FD-18: Fragen in eigenen Worten („Wie setze ich das Teil auf die Druckplatte?“) fanden ihre Handlung nicht — Fragewörter zählten als Inhalt, eine gesagte Wendung wog weniger als ein seltenes Titelwort, die Vorauswahl übersprang gesperrte Treffer | Fehler | mittel | `test_a_question_in_his_own_words_leads_to_the_action`, `test_a_question_finds_what_its_words_find` (sechs Sprachen), `test_a_question_to_the_manual_finds_what_its_words_find`, vorher rot | behoben in `8f2c5c4d6`: `asked`, `_said_weight`, Vorauswahl ab `LOOSE_RANK` der erste Treffer |
| L2 (welle4-b): Das Lochwort folgte der Lage nur in vier Sprachen — „hole“ und „agujero“ wählten das *Schraubenloch*, „orificio“ am Körper die gesperrte Änderung, „foro“ und „furo“ an der Bohrung das Verschließen | Fehler | leicht | `test_the_hole_word_follows_the_place` (sechs Sprachen, Lagen aus `applies_to`, Ziel zuletzt in der Liste), vorher 8 von 13 rot; Fenstersonde über den Bestand | behoben: genau gesagte Wendung vor enthaltener bei gleicher bester Güte, Wendungen, die den Titel wiederholten, gestrichen, spanisch „Cambiar taladro“ |
| L8 (welle4-b): Der Wächter der Bittwörter prüfte erst ab drei Buchstaben | Testlücke | leicht | Gegenprobe mit „loch es“: vorher grün, jetzt rot | behoben |
