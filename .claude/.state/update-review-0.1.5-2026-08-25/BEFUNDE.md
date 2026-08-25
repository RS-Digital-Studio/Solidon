# Review der Änderungen seit Update 0.1.5 (ab9491f4..HEAD) — 25.08.2026

Elf lesende Durchgänge über 168 Commits, 377 Dateien (+32.169/−6.905), je Gebiet
einer. Jeder Befund ist am committeten Stand verifiziert, die meisten
nachgemessen (Skripte in den Scratchpads der Prüfläufe). Zuteilung am Ende
jeder Zeile in eckigen Klammern; „a2" ist diese Sitzung (3d-druck-a2).

Schwesterdurchsicht: `.claude/.state/gesamtreview-2026-08-25b/` (3d-druck-46,
ganze App statt Diff). Überschneidungen sind gewollt und unten vermerkt.

---

## Kritisch

1. **Gitter füllen hängt Material neben das Teil.** `geom/lattice.py:391` —
   `difference` statt Verschneidung gegen den Hohlraum: 33 freischwebende
   Stäbe bis 4,1 mm außerhalb, mit den Parametern des bestehenden Tests
   gemessen; der prüft nur `volume >` und bleibt grün. honeycomb/gyroid sauber.
   [46, geom-Paket]
2. **Der durchgehende Stopfen füllt nur die halbe Bohrung.** `geom/prepare.py:376`
   — ohne den `* 2.0`-Faktor von `drill`; gemessen: eine Seite zu, andere
   offen, kein Befund, Docstring behauptet das Gegenteil. [46]
3. **Die Rücknahme-Warnung erreicht den Kunden nie.** `agent/apply.py:258` +
   `ui/chat.py:367` — `proposal.findings` hat keinen Anzeigeweg: „Übernehmen"
   nimmt still bis zu drei fremde Schritte mit zurück (Regel 16, §26.5).
   `test_ui.py:1679` prüft die Tabelle, nicht den Weg. [a2]
4. **Der Windows-Installer kompiliert nicht mehr.** `packaging/solidon3d.iss:70-85`
   — `[Languages]` heißt `de`/`en`/…, `[CustomMessages]` trägt noch
   `german.`/… — mit lokalem ISCC gemessen: „Unknown language name", Exit 2.
   [a2]
5. **`tools/to_main.py` stirbt bei jedem Aufruf.** Zeile 180 — Argument heißt
   `nur_check`, gelesen wird `check_only` (AttributeError, verifiziert). Dazu
   Fund 27 (deutsche Bezeichner). [a2]
6. **Das Schlüsselloch lässt den Schraubenkopf nicht mehr durch.**
   `parts/mounting.py:414` — `play` kommt bei JEDEM Profil aus
   `material.clearance` (0,2 unkalibriert): M4-Öffnung 7,20 statt 7,60 bei
   Kopf 7,00; der Änderungseintrag behauptet das Gegenteil. [a2, läuft im
   Rastnasen-Paket]
7. **Regel-13/§32-Familie: Rezept-Quelltext entkommt der Prüfung** — vier
   Geschwister eines Fehlers:
   a. `parts/recipe.py:710` — `adopt()` (Reiseweg aus fremder Projektdatei)
      ruft kein `findings_for`: mitreisendes `create_from_scad` löst beim
      Öffnen keinen `project.scripted_source` aus (nur der eigene Ordner
      scannt). [a2]
   b. `ui/session.py:123-140` — der `parts.scripted_recipe`-Hinweis läuft
      NACH `run_evaluation()`: OpenSCAD startet, bevor der Kunde den Satz
      sieht; `foreign.py` verspricht „bevor er rechnen lässt". [43 — ERLEDIGT
      26.08.: der ganze part_check läuft vor run_evaluation, im Baum]
   c. `agent/tools.py:362` / `parts/check.py:99` / `scene/foreign.py:42` —
      `runs_foreign_source` sieht eine Ebene tief: Rezept B mit `insert_A`
      umgeht alle drei Sperren (Fernangebot, Auto-Übernahme, Öffnen-Hinweis).
      Fix: rekursiv über `part_of()`. [a2]
   d. `parts/check.py:96` — `parts.scripted_recipe` ohne Anschlusstest beim
      Projektöffnen. [a2, mit a–c]

## Mittel — Kern und Geometrie

8. `geom/prepare.py:341` — `_at_the_mouth` greift per `np.max` nach der
   höchsten Nachbargeometrie: Senkung wandert auf den Dom neben der Bohrung
   (gemessen, kein Befund). Zwilling des Senkungs-Fixes 74d40af5. [46]
9. `geom/prepare.py:153/384` — `drill`/`plug` entscheiden die Richtung noch am
   Hüllquader (`into_the_body`), obwohl `open_sides` daneben liegt: Platte mit
   Turm → Bohrung trägt 0,21 mm³ ab, Stopfen setzt 126 mm³ in die Luft,
   wortlos. [46]
10. `geom/prepare.py:378` — Stopfen ohne `bore_diameter`-Kompensation, Bohrung
    mit → Ringspalt 1,03 mm² über die ganze Länge. [46]
11. `sketch/profile.py:295` — `shifted()` verwirft `holes` (Zwilling des
    brep/loft-Fixes; `scaled()` nimmt sie mit): dieselbe Skizze extrudiert MIT
    Loch, schneidet als Tasche OHNE — `sketch_pocket` legt jede Region durch
    `shifted`, auch bei 0/0. [43 — ERLEDIGT 26.08.: shifted nimmt holes
    rekursiv mit, Ende-zu-Ende-Test test_a_pocket_keeps_the_drawn_island;
    im Baum]
12. `fasteners.py:540` + `parts/ops.py:517` — `_anchor` liefert für
    `at_hole`-Bausteine die Zylinder-Mitte statt der Mündung: Gewinde/Buchse
    schneiden nur die untere Hälfte der Bohrung (Ende-zu-Ende gemessen). [a2]
13. `parts/ops.py:327` — `parts.hanging_loose` rät jedem Baustein
    „Rückplatte/Rasterschritte" — Felder, die rib/hinge_eye/cable_clip nicht
    haben (Regel 17). [a2]
14. `mounting.py:689` — `hook_N`-Merkmal liegt zu 99,1 % im Material. [a2,
    Rastnasen-Paket]
15. `scene/history.py:755` — Transaktionsnummer wird nach
    Rücknahme+Speichern+Öffnen neu vergeben, während der Chat-Beitrag mit ihr
    in der Datei steht; zweite `History` (split/lid_flow) sieht den
    Redo-Stapel nicht → doppelte Op-Kennungen möglich. [a2]
16. `scene/evaluate.py:846` + `orphans.py:81` — Verweisfilter kennt
    Skizzenebenen nicht: §21.3-Frage entfällt genau bei Skizze auf Fläche;
    zudem Menge nach Objekt-ID geschlüsselt, die im Stapel wechselt. [43 —
    Skizzenebenen-Hälfte ERLEDIGT 26.08. im Baum (plane-Referenzen mit
    „irgendwo"-Objekt, Frage/Umschreiben in den Skizzentext, kein Streichen;
    fünf neue Tests). Die Schlüssel-Hälfte hat jetzt ihr eigenes Kästchen im
    Register unter „Das Fundament der Wahrnehmung"]
17. `serialise.py:59` vs. `app/examples/*.p3d` — Übersetzungsfix für
    Parametertitel erreicht die Beispiele nicht (0 von 10 mit Flag): Ein Lauf
    von `tools/make_examples.py` plus Commit der neun Dateien. [a2]
18. `slice/gcode.py:437` — `_starts_absolute` findet M83 auch im Endcode →
    ganze Datei gilt relativ, E-Werte summieren sich; trifft `support_mm3`
    und `filament_mm` über `action_check_gcode`. [a2]
19. `perceive/digest.py` (6 Stellen) + `agent/context.py` — Injektionstüren:
    Transaktionstitel, `entry.name`, Op-Parameter (voller SCAD-Quelltext),
    Passung, Druckeinstellungen, `unit` gehen roh ins LLM; `as_name` deckt
    zwei von acht Türen, und lässt selbst `"` durch. [a2]

## Mittel — Agentenschicht und Rand

20. `session.py:272`/`chat.py:590` — `stopped="truncated"/"refused"` fallen
    durch; Verweigerung → leere Chatblase. [a2]
21. `apply.py:239`/`main_window.py:5665` — `accept()` wirft
    `ValidationError(history_moved)`, kein `try/except` im Slot: Klick ohne
    Wirkung, Traceback nur auf stderr. [main_window-Hälfte 43 — ERLEDIGT
    26.08. im Baum: try/except mit show_error am Klick UND am Auto-Pfad
    (Zwilling); apply.py-Hälfte bei a2]
22. `generate_dialog.py:91` — `cancelled` nicht durchgereicht: Abbrechen lässt
    den Worker bis zu 1 h weiterpollen; §15.6 steht als abgenommen. Dazu:
    `OperationCancelled` ist kein `AppError` → käme als „crashed" an. [a2]
23. `llm.py:113` + `session.py:249` — Zugbudget zählt `cache_read` voll
    (~25k/Schritt): nach vier Schritten `stopped="tokens"`, `MAX_STEPS=8`
    unerreichbar; Kostenzeile überzeichnet. Entscheidung nötig. [a2 → Vorlage
    an Robert]
24. `comfy_setup.py:164/810` — Platzprüfung misst den ComfyUI-Datenträger,
    geladen wird nach `%LOCALAPPDATA%` (Roberts Aufbau: D:\AI gegen knappes
    C:). [a2]
25. `activation/store.py:159` — Demo-Sperre fällt bei „Marker löschen + Uhr
    zurück": gemessen 2495 Resttage. Fix: `DEMO_FROM`-Untergrenze. [a2 —
    activation steht auf 43s Board-Claim, deren Paket ist aber §2.8; geklärt:
    a2 nimmt es nach Ansage]
26. `app/cli/main.py:637` — Erstlauf ohne `settings.json`: CLI spricht Deutsch
    trotz Installer-Sprache; `installed_language()` liegt in `app/ui`, CLI
    darf es nicht importieren → in den Kern verschieben. [a2, wie 25]
27. `tools/to_main.py` — durchgehend deutsche Bezeichner; Stämme fehlen in
    `GERMAN_STEMS`. [a2, mit Fund 5]
28. `core/install.py:495` — `TimeoutExpired` wird als „ließ sich nicht
    starten" gemeldet, nach 15 Minuten Lauf (Regel 17). [a2]
29. `core/manual.py:670` + `mounting.py:558` — Handbuch/Docstring beschreiben
    die Rückplatte als Pflicht, seit e2283b90 ist sie Ausnahme. [a2 — manual.py
    ERLEDIGT im laufenden Paket, Docstring beim Rastnasen-Agenten]
30. UI-Fenster (an 43 übergeben, bestätigt): `rebuild_for_language` zeigt
    Startbildschirm statt Projekt; `close()` beim Sprachwechsel (Autosave-
    Löschung, überrolltes Abbrechen); `_exporting` nie True; Download-Abbruch
    unerreichbar; `cancel_split` lässt Balken hängen; `FileOpenListener` hält
    totes Fenster. [43 — ALLE SECHS ERLEDIGT 26.08.: _exporting/Download/
    Palettenwache sind mit e65f1539 mitgereist (siehe Vermerk dort), Rest im
    Baum; rebuild übernimmt Dokument+Auswertung, release statt close, Ende
    des Trennens meldet im finished-Pfad, Listener wird nachgeführt
    (retarget/follow). Test: test_the_rebuilt_window_shows_the_work_it_kept]
31. UI-Dialoge: `first_run`-Sprachwechsel ohne `languageChanged` über das
    Hilfemenü; Rasterweite unter 1 mm nicht tippbar (`keyboardTracking`);
    „Automatisch" wirkt im Zeichnen-Dialog nicht [alle drei 43 — ERLEDIGT
    26.08. im Baum: languageChanged in action_first_run, keyboardTracking
    aus am Rasterfeld, snapped() fällt bei 0 auf grid_step() zurück; dazu
    der Docstring 1264];
    `recipe_dialog.UNITS` und `print_settings_dialog.FIELDS` frieren die
    Sprache beim Import ein; Parametergrenzen anlegbar, nie änderbar
    (Sackgasse); abgeleitete Parameter vorgehakt freigegeben (Formel geht
    still verloren) [drei frei → a2-Folgepaket]. [43/a2]
32. ce-Gebiet (übergeben, bestätigt): `_rows()` zählt Gruppenebene nicht;
    `split_bodies` je Aufbau im Hauptthread; Palette lässt eigene Bausteine
    in die modale Sackgasse. [ce]

## Gering (Auswahl; vollständig in den Einzelberichten der Prüfläufe)

- `digest.py:52` — `as_name` lässt `"` durch. [a2, mit 19]
- `advise.py:543` vs. `analysis.py:76` — totes Band 2,00–2,55 mm bei
  0,8er-Düse (zwei Schwellen, eine Frage). [a2]
- `features.py:1841` — `detect_edge_loops` nummeriert nach Koordinaten
  (überlebt keine Drehung, §21.2). [ce-nah (perceive) — klären]
- `export/writer.py:576` — `write_plan` überspringt nach Dateiname statt
  Eintrag. [a2]
- `export/threemf.py:918` — `f"Slot {position}"` ohne `tr()` (vierte Stelle
  des Musters). [a2]
- `cli/main.py:718/651/671` — Bericht-OSError endet ohne Vorschlag; kaputte
  `settings.json` (null/[]) reißt die CLI; Befund-`values` fallen weg. [a2]
- `lid_flow.py:102` — Kragen als Ausdruck umgeht die Nullprüfung. [a2]
- `solidon3d.iss:122` — `install-language.txt` überlebt die Deinstallation. [a2]
- `sketch/edit.py:392` — `extend()` sieht nur Linien, `trim()` jede Art;
  Doppeltreffer auf Polylinien-Knoten. [43 — ERLEDIGT 26.08. im Baum: eine
  Schnittsuche `_meetings` für beide Werkzeuge, gleiche Stellen werden
  zusammengelegt; zwei neue Tests]
- `scene/evaluate.py:798/297` — zerschossener Kommentar („Gespenst
  kind_after"); Lesekopie teilt `material_slots`-Liste. [a2]
- Bausteine: drei abziehende ohne OVERLAP-Kragen; `MIN_RIB` 0,8 unter
  Mindestwand 0,84; `MAGNET_LIP_GRIP` fest statt `press`; `gusset_1` auf der
  Kante; Rezept rechnet immer „fine"; `LIBRARY_VERSION`-Kommentar endet bei 4;
  `project.py:401` `json.loads` außerhalb des try. [a2]
- Agentenschicht: `_count` ohne `OverflowError`; `undo_applied` ohne Aufrufer
  (doppelte Regel); Docstring-Widerspruch `llm.py:396`; unlesbares
  Werkzeug-JSON wird bei `consumes=0` zum stillen Vorgabekörper (Regel 21).
  [a2]
- Tests (beide Testberichte): `importorskip` fehlt in `test_recipe_dialog.py`;
  Fenster-Pin greift nicht, wenn `main_window` erst im Testrumpf importiert
  wird; `_no_user_parts_stay_loaded` räumt Registrierung nicht zurück (drei
  „vor dem nächsten Tor"); dazu 15 kleinere Prüf­lücken (Sollwert-,
  Anschluss-, Sichtbarkeitsmuster). [a2-Folgepaket]
- Sprache/Website: FR „Stelle" uneinheitlich (emplacements/endroits); IT/PT
  „Steht:" als Substantiv; zwei Alt-Texte pieza/peça [ERLEDIGT im laufenden
  Paket]. [a2]

## Bereits im laufenden Paket dieser Sitzung erledigt (25.08., uncommittet)

- Bauplan §24.3: print-in-place-Ausnahme als Deklaration (Entscheidung Robert
  über 3d-druck-46); Registerpunkt umgestellt auf die Restarbeit.
- Registernachzüge: Schlüsselloch (Fix war 45f87d8e), placement-Punkt
  (geschlossen, s. u.), Flächenmenü lief bei ce.
- placement: `screw_for_bore`/`bore_advice` + Senkungs-Kopfwahl, 35+23 Tests,
  Anschluss in `run_operation` (Freigabe 43), Kataloge in fünf Sprachen.
- `test_value_labels`-Rot am HEAD behoben (`loose`-Beschriftung, f3741de8
  hatte sie vergessen).
- Website: „In drei Schritten"-Abschnitt (6 Sprachen), Demo-Gegenwart auf
  Funktions-, Start- und KI-Modell-Seiten, Update-Hinweis, TripoSG-Nachzug,
  Kaufhinweis; 154 Website-Tests grün.
- Handbuch-Absatz Lochwand-Einhänger (manual.py + 5 Kataloge).
- Läuft noch: federnde Rastnase am Einhänger inkl. keyhole-clearance-Fix und
  hook_N-Merkmal (Agent, mounting.py + test_parts.py).

## Größere Vorlagen an Robert (keine Sitzungsentscheidung)

- Token-Budget-Zählweise (Fund 23): MAX_TOKENS anheben oder Cache gewichtet.
- `MIN_PITCH` gegen `MAX_GRID_STEPS` (stehende Wand < 0,9 mm) — Messung nötig,
  Speicher gegen Genauigkeit.
- Website, größere Hebel A–E aus `gesamtreview-2026-08-25b/berichte/00-website.md`
  (Aufmacherbild, WebM, Vergleichstabelle, Druckfotos, Kaufweg).
- Die im Register stehenden Robert-Punkte (EULA, §-Verweise, Paddle,
  Fördermodell, 3D-Drucker-Ordner-Sicherung, Flächenrückgewinnungs-Phase,
  P16.10, Intel/AMD-Weg, Tor-Umbau/Arbeitsbäume) — unverändert offen.
