# `app/core/knowledge/` — was die Anwendung weiß

Profile, Normteile, Regelsammlung, Kalibrierung, Filamentlager — und in
`parts/` die Bausteinbibliothek (§24, §38, §39). **Der Agent setzt geprüfte
Bausteine zusammen, statt Geometrie zu erfinden** (§24): Was hier liegt, ist
Teil des Rechenwegs, nicht Beiwerk. Einzuhalten sind
`.claude/rules/bausteine.md` und `kern.md`; die Messreihen stehen in
`konzepte/begruendungen/karte-app-core-knowledge.md`.

## Die Karte

| Datei | Rolle |
|---|---|
| `profiles.py` | Drucker- und Materialprofile (§38) — **hier stehen die Toleranzen** hinter `auto:<material>`. Ein Drucker trägt sein Verfahren (`technology`: `fdm` oder `resin`, ohne Angabe FDM), ein Material seines (`MaterialProfile.fits`); `default_material_for` und `material_for` halten beide zusammen — PLA gegen Harz nur beim Verfahrenswechsel. `project_profile` gibt das Paar eines Projekts samt mitgereistem Drucker, ohne es anzumelden (für die Migration). Resin hat Düse, Bahn und Heiztemperaturen auf **null**, dafür `pixel_size` und `minimum_wall` (`RESIN_*`, `DEFAULT_RESIN_PRINTER`). Eigene Drucker schreibt `save_printer` in die Nutzerdatei `printers.toml` (Name und positive, endliche Maße geprüft, andere Profile erhalten, ersetzt erst nach vollständigem Schreiben); `user_printer_profiles` gilt unabhängig vom Slicer, `printer_profiles` verbindet mit dem Startbestand |
| `standards.py` | Normteilmaße (§24.2) — M3, M4, Einpressbuchsen, Lager |
| `strength.py` | Blattfederrechnung für Schnapphaken und Klemmzungen aus E-Modul, Streckgrenze und `layer_bond_ratio` des Materials; die Lage entscheidet, ob der Schichtabschlag gilt, ohne bekannte Druckrichtung Querbelastung; ein fehlender Kennwert ergibt keine erfundene Tragfähigkeit |
| `print_settings.py` | Stufe + Material + Drucker → Einstellungen (§29); das Tempo des Herstellers gilt für „Standard“, gedeckelt auf den Volumenstrom (`flow_speed_limit`, dieselbe Rechnung liest `slice/advise.py`). Herkunft je Wert: `with_choice`, `with_accepted`, `without_choice`, `on_base` (Grundlage plus Abweichung), `own_part`, `legacy_choices` (Einordnung vor Format 36, gegen `resolve` von heute und `resolve(legacy=True)` wie bis 0.5.0). Eine gewählte Haftungsart bringt ihr Maß mit (`ADHESION_MEASURES`). Grundlage ohne Herstellerprofil ist `resolve`, sonst `export.manufacturer.base_settings` |
| `rules.py` | Die Regelsammlung für den Agenten (§39); ein neuer Eintrag gehört in `data/rules.toml` |
| `calibration.py` | Selbstkalibrierung (§28.3) |
| `filaments.py` | Örtliches Filamentlager: Spulen mit beständiger Kennung, optionale Mengen und Angaben, Journal ganzer Druckvorgänge (§20) |
| `licences.py` | Lizenzprüfung der Abhängigkeiten (§36) |
| `tables.py` | Der eine TOML-Leser für Dateien, die auch von Hand geschrieben sein können — ein Syntaxfehler wird ein Satz mit Dateinamen (Regel 17); Profile, Druckeinstellungen und Kalibrierung rufen ihn mit ihrem Titel |
| `parts/` | Die Bausteinbibliothek — eigene Karte, **eigene Lizenz** |
| `data/` | **Wo das Wissen steht**: die TOML-Dateien und Lizenztexte — eigene Karte |

**Zahlen stehen in `data/`, nicht im Code** — sie ändern sich, ohne dass der
Code sich ändert; eine Toleranz im Baustein ist ein Fehler (Regel 7,
Checkliste Baustein Punkt 6). **Eine Regeländerung wird gemessen** nach der
Checkliste „Regelsammlung ändern“ in `AGENTS.md`; die Agenten-Suite
(`tools/run_agent_suite.py`) kostet Geld und rund anderthalb Stunden je Modell
und ist kein Testlauf.

## Druckproben gelten für ihren Prozess

- `calibration.apply(..., process=...)` speichert Mindestwand und
  Überhanggrenze mit Druckerkennung, Düse, Schichthöhe und Linienbreite;
  `profiles.for_process` nimmt das Druckraster aus den Projekteinstellungen.
  `Profile` nutzt Messwerte nur bei passendem Prozess, sonst zwei
  Linienbreiten und `PrinterProfile.overhang_limit`, ohne ihn die Startregel;
  derselbe Winkel geht als Stützgrenze in die Übergabe
  (`print_settings.resolve`).
- Ein Wechsel des Messprozesses nimmt keine Messung des anderen Felds mit;
  nicht gewählte Messfelder bleiben beim Speichern unverändert. Kalibrierung
  schreibt TOML-Kennungen als zitierte Literale — Leerraum, Punkte und
  Anführungszeichen in Materialkennungen bleiben lesbar.
- `analysis_limits` verbindet die Materialien: größte Mindestwand, kleinster
  Überhangwinkel; unbekannte Materialarten übernehmen keine fremde
  Kalibrierung. Wer die Analyse zwischenspeichert, nimmt die wirksamen Grenzen
  in den Schlüssel.

## Das Filamentlager ist örtlicher Bestand

- **Spulen**: `filaments.save` speichert nach Kennung, eine leere legt ein neues
  Exemplar an, Namen dürfen sich wiederholen. Bearbeitungen behalten die
  gelesene `revision` (Konflikt → Handlung `RELOAD`). Eine geänderte
  `remaining_grams` ist eine Bestandsfeststellung (`stock_revision` springt) —
  der Spulendialog gibt den gespeicherten Wert unverändert zurück, solange
  niemand den Bestandsblock anfasst, sonst zählte seine Rundung als Zählung.
  Archivieren erhält Kennung und Verlauf; `remember`/`forget` bearbeiten nur
  eindeutige Treffer. `valid_date` ist die eine Datumsprüfung.
- **`synchronise`** (Übernahme aus dem Slicer) erkennt eine übernommene Spule
  an Profil und Farbe, ohne Profil an Name, Farbe und Materialart zugleich
  (`_same_slicer_spools`); alles andere wird neu mit unbekannter Menge, eine
  Mehrdeutigkeit hält den Rest nicht auf, eine Handspule gleichen Namens wird
  nie umgefärbt (Regel 21).
- **Bis zu vier Farben je Spule** (`MAX_COLOURS`, Entscheidung Robert):
  `colour` bleibt die erste, `extra_colours` die weiteren, `colours` alle —
  ebenso `MaterialSlot.extra_colours`, der Parameter `colour` von *Filament
  zuweisen* (Leerzeichen dazwischen) und `filament_multi_colour` in der
  Orca-Familie; PrusaSlicer, Cura, STL und die Ansicht bekommen die erste.
- **Die Datei** `filaments.json` ist versioniert: Lesen, Prüfen und atomarer
  Tausch unter einer Betriebssystemsperre; die Migration alter Kataloge
  speichert Lager- und Spulenkennungen im selben Vorgang, die Lagerkennung
  bei der ersten Abfrage. Leser teilen eine unveränderliche
  `InventorySnapshot`, erneuert bei geänderter Identität, Größe oder Zeit;
  ein Lesefehler ist nie eine leere Liste. Eine nötige Migration wartet im
  Leser nicht auf fremde Sperren. Windows tauscht über `FileRenameInfoEx`
  (offene Leser behalten den alten Stand); wo das Dateisystem ablehnt (FAT32,
  exFAT, SMB ohne die Fähigkeit, Windows vor 1709), tauscht
  `_replace_snapshot` gewöhnlich und meldet Konkurrenz als wiederholbaren
  Schreibfehler.
- **Kein Schreibweg überschreibt eine beschädigte oder neuere Datei** (neuer:
  `too_new`). `_write` legt den ersetzten Stand als `filaments.json.bak`
  daneben (`backup_path`); ein Lesefehler bietet Handlungen statt Rat:
  `RESTORE_BACKUP` (nur mit Sicherung; die kaputte Datei wird
  `filaments.json.damaged-<Zeit>`), `SET_ASIDE_FILE` (immer; ein heiler Stand
  wird nie weggeräumt), `RETRY` — nicht den Vorschlag einer `ValidationError`.
- **`book` nimmt einen ganzen Vorgang**: Seine Kennung macht Zustellungen
  idempotent, gleicher Fingerabdruck mit neuer Kennung ist ein wiederholter
  Druck; jede Position trägt Herkunft und Druckfilamentidentität. G-Code
  ersetzt eine Schätzung mit dokumentierter Differenz. Der Bestand zählt ab
  der letzten Feststellung, deren `stock_revision` jüngere Kenntnis vor alten
  Korrekturen schützt; eine bestätigte Unterdeckung bleibt unbekannt, ein
  negativer Rest in Maschinenrundung ist null.
- **Rücknahme und Korrektur**: `reverse_booking` nimmt alle Positionen zurück,
  `restore_booking` stellt sie wieder her; eine jüngere Feststellung sperrt
  beide. Nach einem Bestandskonflikt darf eine bestätigte Rücknahme
  `preserve_newer_counts=True` setzen (`preserved_counts` dokumentiert es).
  Eine Handmenge ersetzt nur `correct_manual_allocation=True` mit
  `expected_booking_updated_at` — nie eine automatische G-Code-Übernahme; eine
  neuere Aufteilung wird abgewiesen. Beim Lesen werden auch frühere
  Positionen, Revisionen und Rücknahmebelege vollständig geprüft.
- **Was ein Schreibvorgang kostet**: Jeder Schreibweg liest unter der Sperre
  neu, prüft vollständig und schreibt ganz — das bleibt. `_booked_grams`
  ordnet die Mengen einmal nach Spule und Bestandsstand (summiert mit
  `math.fsum` erst beim Abruf), `_encoded` schreibt über `json.dumps`, `_plain`
  ersetzt `asdict` (Datei bytegleich:
  `test_the_file_keeps_its_bytes_when_the_writer_gets_faster`), und
  `_remember_written` macht das Geschriebene zur Momentaufnahme der Leser.
  Geschrieben wird neben dem Hauptthread (`CatalogueWrites`,
  `InventoryView._run`, §2.8).
