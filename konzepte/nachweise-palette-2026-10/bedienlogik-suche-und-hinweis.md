# Bericht bedienlogik: Hinweis zu den Booleschen (RM-734) und Suchfeld statt Palette (RM-735), 11.10.2026

Nur gelesen, aus dem Code abgeleitet; Zahlen zu Palette und Panel aus der Inventur.

## Befunde am Ist (nicht in der Inventur)

- F1 Escape im Suchfeld läuft zur Fensteraktion (`main_window.py:3390`, `_escape`): an einem Merkmal mit Maßen `_leave_the_measures()` → Entwurf verworfen, alles abgewählt (Z. 12542).
- F2 Return/Escape aus dem Feld können eine laufende Platzierung bedienen (`placement_flow.py:1598-1604`, Filter `:5258-5283` nimmt ShortcutOverride/KeyPress der rechten Zone ab). Am Fenster zu prüfen.
- F3 Bleibt der Fokus nach dem Ausführen im Feld, verschluckt QLineEdit Strg+Z (eigenes Rückgängig).
- F4 Bei einem Körper in der Szene verlangt der Sperrgrund der Booleschen „das zweite dazu mit Umschalt oder Strg und Klick“ — es gibt keinen zweiten. Besser: braucht zwei Körper in der Szene, Weg *Objekt duplizieren* (Strg+D), in `_reason_locked`.
- F5 *Überschneidungen prüfen* ohne Überschneidung: Verlaufsschritt, aber kein Befund und keine Antwort (`prepare_ops.py:23784-23791`).

## Entscheidungen

### A Hinweis (RM-734)
- A1 Unter der Schnellzeile, über dem Feld, Stufe `caption`; ändert sich nur bei Auswahlwechsel.
- A2 Genau ein Körper, kein Merkmal, höchstens eine markierte Merkmalszeile, ≥ 2 Körper in der Szene; Merker vom Fenster wie `rebuild=`: `pairing = objects >= 2 and not locked and not gesturing and self._halt_reason() is None`.
- A3 Kein Hinweis bei Lizenzsperre, Halt, Formen, Skelett. A4 Zeichnung: Reiter verborgen. A5 Ausgeblendete Körper zählen mit. A6 Bausteinkörper auf Körperstufe wie jeder Körper.
- A7 Reiner Text, nicht klickbar. A8 Titel aus `QUICK_BODIES` aus dem Register, Taste über `adding_key()`; Test hält den Satz an `QUICK_BODIES`.

### B1 Leeres Feld, Erzeuger
- B1a Feld auf jeder Stufe (ohne Auswahl, alle Merkmalsarten, Kante, Bausteinmerkmal); der Satz „steht oben bei den Maßen“ unter dem Feld.
- B1b Erzeuger ins Panel ohne Auswahl, nicht in die Ansicht: `create_brep_box`, `create_brep_cylinder`, `create_brep_cone`, `create_brep_sphere`, `create_brep_torus`, `create_brep_tube`, `create_container`, `create_organizer`, `create_profile_clamp_set`, `thread_exact`, `create_label`, `load_step`, `load_outline`; Zwillinge über `shown_of_twins`; ohne Skizzen-Varianten und `load`. Dritter Filter neben body/feature_operations.
- B1c Gruppen nach `_card_group`: Objekt (Szenehandlungen), Erzeugen, Grundformen (offen, 10), Transformation (Druckoptimal ausrichten).
- B1d `orient_for_print` in Kategorie `scene` (prepare_ops.py:23279).
- B1e `SCENE_ACTIONS_IN_THE_CARD` und „Gilt für alle Körper.“ fallen; `_panel_place` nennt für alle drei „Handlungen rechts (ohne Auswahl)“.
- B1f Doppelung mit der Einladung der leeren Szene hinnehmen.
- B1g Leere Szene unter Halt/Lizenz: Satz nennt den Grund statt „Bausteine gehen auch so“.

### B2 Suchtext
- B2a Flache Trefferliste über alle Zeilen (Operationen, Fensterbefehle, Einstellungen), `_Rows`; Tooltip mit „Ort: …“.
- B2b Rangfolge der Palette, bei gleicher Güte: frei und zur Stufe passend, frei, gesperrt.
- B2c Gruppentitel-Abkürzung (`in_a_group`) entfällt.
- B2d Treffer der Schnellzeile stehen in der Liste mit (Return/Pfeile arbeiten auf der Liste); Schnellzeile bleibt.
- B2e Gesperrte Treffer sichtbar, nicht wählbar, Grund als zweite Zeile; Return sagt den Grund in der Statuszeile.
- B2f Vorauswahl wie die Palette. B2g Zeile der Lockerung als nicht wählbare erste Zeile.
- B2h Platzhalter „Funktion suchen …“ mit Taste wie der Knopf.

### B3 Tastatur
- B3a Strg+Umschalt+P / Knopf: Startbildschirm → `_begin_from_the_start_screen()`; rechte Spalte einblenden (wie F9 samt Einstellung); einziger Körper wählen; Reiter *Auswahl* nach vorn (auch über verlassenen Reiter und Tour, wie `reveal(for_a_gesture=True)`); herausgezogenen Reiter aktivieren; Fokus mit `ShortcutFocusReason`, Text markieren. Spalte einblenden steht dreimal von Hand (`_show_alerts`, `_on_invitation`, Tour Z. 29048) → ein Helfer.
- B3b In der Zeichnung: Statuszeile sagt, dass die Suche nach Fertig/Verwerfen bereitsteht.
- B3c Pfeile bewegen die Vorauswahl, Return führt aus, Tab in die Liste (Mac: `return_opens`), Klick führt einmal aus (nicht itemClicked und itemActivated zugleich).
- B3d Escape im Feld: mit Text leeren, sonst Fokus an die Ansicht; Feld nimmt ShortcutOverride/KeyPress für Escape und Return selbst ab (F1, F2).
- B3e Nach dem Ausführen: Text leer, Fokus an die Ansicht, vor `launch_operation` (F3). Auswahlwechsel ohne Ausführen behält den Text.
- B3f Gesperrt per Return: Grund in die Statuszeile, Text und Fokus bleiben.
- B3g Kürzelübersicht nennt Strg+Umschalt+P als „Funktion suchen“; Aktion ohne Menü.

### B4 Einziger Körper nur beim Aufruf über Taste/Knopf, nicht bei Mausklick ins Feld oder beim Ausführen.
### B5 Bausteinmerkmal: Panel sichtbar mit Feld und Satz; an Gewinde/Bohrung weiter *Stift für Bohrung*.
### B6 Kein Treffer: „Kein Treffer — versuchen Sie ein anderes Wort.“ und Knopf *Im Handbuch suchen* (öffnet das Handbuch mit dem Wort).

### Weitere
- C1 Grund nach F4 in `_reason_locked`. C2 *Überschneidungen prüfen* sagt auch „keine gefunden“.
- C3 Vorgewählte Zeile halbfett. C4 Zeilen faul, beim ersten Zeichen, entwertet bei `set_context`; Tastendruck < 0,2 s, Messung vorher und nachher.

## Abnahmekriterien (Kurzfassung)
Feld überall; jede Zeile findet sich über ihren Titel; Rangfolge der Palette; Lockerungszeile; gesperrte Zeile mit Grund; Vorauswahl („Verrund“ legt keinen Quader an); Escape zweistufig, Auswahl bleibt; Strg+Umschalt+P aus jeder Lage; nach dem Ausführen Feld leer, Fokus Ansicht, Strg+Z wirkt; Klick einmal; Szenehandlungen und 13 Erzeuger ohne Auswahl, `menu_path` „Handlungen rechts (ohne Auswahl) → …“, kein „Befehlspalette“ mehr in Texten; Hinweis unter A2; Fachbegriffe sechs Sprachen; kein Treffer mit *Im Handbuch suchen*; Kürzelübersicht; einziger Körper; F4; F5; Zeit; keine Palette mehr.
