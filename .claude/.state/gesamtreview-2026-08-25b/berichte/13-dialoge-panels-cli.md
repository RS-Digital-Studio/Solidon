# Gebietsbericht: Dialoge, Panels, Einstellungen, CLI

Grundlage: `AGENTS.md`, `.claude/rules/oberflaeche.md`, Bauplan §19, §2.7, §29, §37.2. Offscreen gemessen, Skripte unter `review-ui3\`. Registerpunkte ausgelassen.

## Hoch

### 1 [hoch] „Erzeugen" ist klickbar und tut wortlos nichts — VERIFIZIERT
`generate_dialog.py:436` (`_start`) gegen `:382-384` (`_update_state`) — `_update_state` gibt den Knopf frei, sobald der Generator nicht `ABSENT` ist; `_start` beginnt mit `if not self.available: return` (`available = READY`). Gemessen: bei `UNKNOWN`/`NO_NODES`/`NO_MODEL` Knopf aktiv, Klick → kein Balken, kein Arbeiter, kein Satz. Trifft jeden mit laufendem ComfyUI ohne eingerichtete Knoten. Zwilling der Fixes in `catalog.py`/`ActivationDialog`. **Fix:** in `_start` `if self._readiness is mesh.Readiness.ABSENT: return`, dann sagt `_on_failed` mit Vorschlag, woran es scheitert.

### 2 [hoch] Drucker-/Materialwechsel wirft die Druckeinstellungen des Projekts weg — VERIFIZIERT
`print_settings_dialog.py:1252-1264` (`_scene_profile_changed`) — `self.settings = resolve(...)` ersetzt den ganzen Satz; weg ist das gerade Eingestellte **und** das mitgebrachte. Der eigene `__init__`-Docstring sagt das Gegenteil zu. Verlust dauerhaft, weil `main_window.py:3426` nach `exec()` bedingungslos `set_print_settings` schreibt. Gemessen: Fülldichte 45 %→15 % nach Materialwechsel; Projekt bringt 62 % mit, nach Druckerwechsel 15 %. Trifft den Normalfall (Drucker/Material stehen oben in der Zeile). **Fix:** nur profilabhängige Pfade neu auflösen (Temperaturen, Bauraum), übersteuerte Werte behalten — oder Verlust wie bei der Stufe ansagen.

### 3 [hoch] Slot-Filamentwahl speichert den Anzeigetitel statt des Profilnamens — VERIFIZIERT
`print_settings_dialog.py:1677` (`chosen = box.currentText()`) — der Text trägt bei eigenem Profil `` (eigenes)`` (übersetzt!); wandert in `PrintSettings.slot_profiles` (→ Projektdatei) und über `handover` als `base_filament`. `profile_file` (`handover.py:160`) sucht `entry.name == chosen` und trifft nie. Gemessen: „Meine Spule (eigenes)" gespeichert, Slicer bekommt kein Profil, fährt Basisfilament — der Zustand, den `with_slot_profiles` beheben sollte. Zusätzlich sprachabhängig, `findText` findet ihn auf anderer Sprache nicht. **Fix:** gewähltes `SlicerProfile` über `currentData()` nachschlagen, dessen `name` speichern.

### 4 [hoch] Parameterleiste rundet gemessene Werte still weg — VERIFIZIERT
`panels.py:1454-1463` (`ParameterPanel.show_document`) — `setDecimals(2)`, kein `setSingleStep`. Ein Parameter 0,075 mm (Normalfall nach Kalibrierdruck §28.3) steht als 0,07, der erste Griff schreibt ihn dauerhaft; Drehknopf-Schrittweite 1,0 → Sprung 0,07→1,07. `ParameterDialog` nimmt `setDecimals(3)`. Der Fall ist im Operationsdialog schon behoben (`_FINE_BELOW`, `op_dialog.py:53-56`), die Leiste hat weder Feinheitsregel noch `_core`-Schutz. **Fix:** `_decimals_for` aus `op_dialog` mitbenutzen, `setSingleStep` an der Größenordnung.

## Mittel

### 5 [mittel] Bestätigung nach dem Senden wird gesetzt und im selben Atemzug weggeschlossen — VERIFIZIERT
`support_dialog.py:640-654` (`_sent`) — `state.setText("Angekommen … Vorgang: SUP-…")` 14 Zeilen vor `accept()`; modal, nie gemalt; kein Aufrufer liest `receipt`. Der Kunde sieht den Dialog verschwinden, die Vorgangsnummer erreicht ihn nie. Zwilling von `RecipeDialog.saved` (`recipe_dialog.py:321-328`). **Fix:** Signal (Nummer + Erfolg) nach draußen, Statusleiste — oder Dialog stehen lassen, Knopf auf „Schließen".

### 6 [mittel] Vorschlagszeile des Chats nennt Registernamen statt Titel — VERIFIZIERT
`chat.py:537` (`_named`) — gemessen: „Operation: drill_hole, create_box" statt „Bohrung setzen, Quader anlegen". Das ist die Zeile über „Übernehmen/Verwerfen", auf die §26.5 die Entscheidung stützt. Behoben im Verlauf (`panels.py:323-337`, `_op_title`). **Fix:** `panels._op_title` in `chat._named` benutzen.

### 7 [mittel] Acht-Felder-Grenze §19 fällt beim Wiederöffnen, kein Test sieht es — VERIFIZIERT
`op_dialog.py:765-770` (`decided`) gegen `test_interface_limits.py:92-97` — der Test zählt `placement=="front"` im **Schema**; der Dialog holt jeden abweichenden übergebenen Wert nach vorn, und `edit_operation` übergibt `values=entry.params`. Gemessen: `insert_pegboard_hook` Schema 6/Dialog 9, `apply_texture` 7/10; mit allen abweichend reißen 26 Ops die Grenze. **Fix:** Grenze im Dialog durchsetzen (nach 8 bleibt der Rest hinten), Test am gebauten Dialog messen.

### 8 [mittel] Kontextmenüs häufen sich an, jedes hält seinen Baum fest — VERIFIZIERT
`panels.py:1089` (`context_menu`), `:1271-1273`, `:1624`, `:2124` — `QMenu(self)` bei jedem Rechtsklick neu, nie zerstört; Aktions-Lambda schließt den Baum über die C++-Grenze ein (von `oberflaeche.md` verboten). Gemessen: 20 Rechtsklicks → 20 QMenu-Kinder, 160 QMenu unter dem Baum, je bis 57 QAction; Baum wird nie freigegeben. **Fix:** `WA_DeleteOnClose`/`deleteLater()` nach `exec`, Rückrufe über `weak_slot`.

## Gering
- **9** Unbekannter Auswahlwert wird still ersetzt statt gezeigt (`op_dialog.py:1089-1091`); `apply_texture.pattern="voelliger_unsinn"` → `'rib'`. Die vier anderen Feldarten machen es richtig. Regel 21. VERIFIZIERT.
- **10** Haken „Modell laden" altert beim Ordnerwechsel (`comfy_dialog.py:121-125` vs `:169-174`) — bei zwei Installationen „Modell ist schon da" über leerem Ordner. PLAUSIBEL.
- **11** Zwei Felder, die niemand liest: `_pending_findings` (nie befüllt, Weg läuft über `PlateRun.findings`) und `box.setProperty("wanted")` (`print_settings_dialog.py:1163,1647`). Entfernen.
- **12** Docstring beschreibt eine Grenze, die es nicht mehr gibt (`settings_dialog.py:240-248`, Sprachwechsel wirkt sofort). Umschreiben.
- **13** CLI baut ihre Quelle an der einen Stelle vorbei (`cli/main.py:294-301`, leere Prüfsumme, doppelt gebildete Kennung); `Session.add_source` hat genau das behoben. Fix: `sha256=checksum(payload)`, besser gemeinsame Kernfunktion.
- **14** Windows-Pfad wird als Operationsname behandelt (`cli/main.py:621`, Rückwärtsschrägstrich fehlt): `solidon3d run C:\Projekte\halter` → „Diese Operation gibt es nicht". Fix: `or "\\" in wanted`.
- **15** §18.8 verlangt Umbenennen und Farbe im Objektbaum — beides fehlt dort (`panels.py:1077-1118`); `rename_object` nur über die allgemeine Liste, `set_object_colour` existiert nicht. Entweder Zeilenbearbeitung + Farbeintrag oder §18.8 mit Ansage kürzen (Robert-Entscheidung).

## Geprüft und in Ordnung
Eingabeauswertung Operationsdialog (Komma/Punkt, Ausdruck bleibt wörtlich + Hinweis rechnet, Zoll-Rundlauf exakt, Grenzen geklemmt); Auflösung Stufe×Material×Drucker über 16×6 gegen 56 Felder ohne Rundungsverlust; Symbolkatalog vollständig; jedes `UiSettings`-Feld hat einen Leser + Migration am rohen Wörterbuch; `WorkerLeash` hält jeden Arbeiter, alle elf Klassen mit `release()`; Längenfelder der Leisten über `value_mm()`; `support.send()` genau ein Aufrufer am Knopf; `chat` Regel 16 (genau ein Rückgängig-Knopf).

**Kann das so rein: nein** — die vier hohen Funde trifft ein Kunde auf normalem Weg, alle vier sind anderswo im Projekt schon behoben, drei ändern Daten dauerhaft.
