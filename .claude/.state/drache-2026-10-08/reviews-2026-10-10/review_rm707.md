# Review RM-707 und Nachprüfung RM-705 (Zweig `fix/verbrauch-abdruck`)

Gegenstand: Worktree `F:\sl-abdruck`, Stand `a33b58a19` (welle3 `997ce9fcd` enthalten). Commits
`80e2ca386` (RM-707 + Reviewfixes RM-705 M1, M2, L1–L4), Merges `9b4526a56`, `a33b58a19`.
Scratch: `scratchpad\rv707\`. Begonnen 12:47; nach dem Abbruch am Nutzungslimit galt die Frist
16:30, abgeschlossen 16:45. Im Worktree wurde nichts geändert (`git status` sauber).

## Stand der Arbeit

- 12:47 Auftrag, Bauagentenbericht und Erstreview gelesen; Worktree sauber.
- 13:10 Codekopien per `git archive`: `k053` = v0.5.3, `kw3` = welle3 `997ce9fcd` (vor RM-707),
  `kzw` = Zweig `a33b58a19`, `kmut` = Kopie von `kzw` für Mutationen. APPDATA der Sonden zeigt
  auf eine Kopie der Herstellerbündel von Elegoo und Orca in `rv707\appdata` (Roberts Ordner nur
  gelesen). Lauf 1 (gepinnt FFFFF0FF, alle Exit 0): Prüfprojekte, Rundreisen, Ausgänge je Stand.

### Lauf 1 — Ausgänge je Slicer (Sonde `sonde_ausgaenge.py`, Zusammenfassung `zeige.py`)

Projekte (`daten\`): `spule_053` = Korpus `usage_spool_v46.p3d` (0.5.3); `spule_teil` = dasselbe,
die Kühlgruppe der Spule trägt `minimum_speed` 12, `support_interface_cooling` fehlt;
`spule_06` = von welle3 geschrieben (Format 51, Spule mit allen Feldern, Düse 220, Lüfter 0,7);
`ohne_spule_053` = Korpus `usage_booking_v46.p3d`. Grundlage wie `effective_print_settings`
(`manufacturer.effective` über `base_settings`), Einrichtung aus `standard_choice` des Zweigs,
dieselbe Wahl für welle3 und 0.5.3 (`aus\wahl.json`). Ausgänge: 3MF-Beilage
(`project_settings`), Filamentdatei des Konsolenlaufs (`write_config`), `prusa_values`, Cura
(`settings_for_handover` + `as_mapping`).

| Projekt | welle3 → Zweig | 0.5.3 → Zweig |
|---|---|---|
| `spule_053` | Elegoo (CC2), Orca (X1C), Bambu (X1C), Creality (K1), Anycubic (Kobra 2): in 3MF **und** Konsolendatei nur `slow_down_min_speed` 10 → 20; Prusa (MK4S): nur `min_print_speed` 10 → 20; Cura, Tabelle: gleich | alle Ausgänge gleich, außer Cura: `cool_min_speed` 10 und `support_fan_enable` false kommen dazu (neue Felder 0.6.0, Curas eigene Vorgabe, auch ohne Spule) |
| `spule_teil` | gleich (12 eigener Wert, `support_interface_cooling` überall Grundlage false) | erwartet verschieden (0.5.3 kennt das Feld nicht) |
| `spule_06` | gleich in jedem Ausgang | — (0.5.3 lehnt Format 51 ab) |
| `ohne_spule_053` | gleich in jedem Ausgang | gleich, außer denselben zwei Cura-Schlüsseln |

Abdrücke `spule_053` am Zweig = 0.5.3 in allen acht Fällen (Tabelle `613fd553…`, Elegoo
`0a885d1b…`, Orca `58dd65b8…`, Bambu `5c9c82ab…`, Creality `6e778094…`, Anycubic `27b3d5b5…`,
Prusa `ae4d3a1b…`, Cura `49ed9153…`).

### Lauf 1 — Speichern → Öffnen → Speichern (`rundreise.py`, Zweig)

| Projekt | `inherited` nach Öffnen | geschriebene Kühlgruppe der Spule | 2. Speicherung gegen 1. |
|---|---|---|---|
| `spule_053` | `minimum_speed`, `support_interface_cooling` | sechs Felder von 0.5.3 | gleich (ganze `project.json`) |
| `spule_teil` | `support_interface_cooling` | sieben Felder (mit `minimum_speed`) | gleich |
| `spule_06` | leer | acht Felder | gleich; Druckeinstellungen gleich der Eingabe |
| `ohne_spule_053` | — | — | gleich |

welle3 schreibt `spule_053` mit `minimum_speed`/`support_interface_cooling` aus der Vorgabe —
der Fehler vor RM-707, wie erwartet.

### Lauf 2/5 — echter ElegooSlicer (`sonde_elegoo.py`, gepinnt)

ElegooSlicer, CC2, Einrichtung aus `wahl.json` (dieselbe für alle drei Stände), Projekt
`spule_053`, Platte wie der Dialog (`_prepare_plate`), `slice_model`; verglichen wird der ganze
Konfigurationsblock des G-Codes (627 Schlüssel, ohne Zeit-/Mengenangaben).

| Stand | `slow_down_min_speed` | `slow_down_layer_time` | `support_material_interface_fan_speed` | Spule weicht ab in |
|---|---|---|---|---|
| 0.5.3 | 20 | 8 | -1 | Lüfter, Mindestschichtzeit, Düse, Düse erste Schicht |
| welle3 | **10** | 8 | -1 | dazu `cooling.minimum_speed` |
| Zweig | 20 | 8 | -1 | wie 0.5.3 |

Ganzer Block: welle3 → Zweig nur `slow_down_min_speed`; **0.5.3 → Zweig kein einziger Unterschied.**

### Lauf 2/5 — Spulendialog (`test_rv707_sonde.py` in der Kopie `kzw`, offscreen, 4 passed)

- **Alte Werte übernehmen** (Spule aus Format ≤ 19, ungebunden): Vor dem Klick zeigt
  `minimum_speed` 20 (Projekt), nach `_take_legacy_values` **10** (Vorgabe der Dataclass);
  `override()` lässt nur `support_interface_cooling` geerbt, die Spule übersteuert
  `minimum_speed` = 10, `_for_the_slot` schreibt es an den Slicer. → Befund M1 unten.
- **PETG-Spule im PLA-Projekt**, Spule aus 0.5.3: Der Dialog zeigt im geerbten Feld 20
  (Projektwert), gedruckt werden 10 (Wert ohne Spule, PETG aus der Tabelle). → L2 unten.
- **Geerbtes Feld, gezeigten Wert selbst getippt**: bleibt geerbt (gewollt: unverändert heißt
  geerbt); 10 getippt → eigener Wert.
- **Vorbestehend:** Eine Gruppe einer PETG-Spule (ohne Werte) eingeschaltet belegt der Dialog
  mit den PLA-Werten des Projekts vor: Düse 210 statt 240, Bett 60 statt 80. → neuer Punkt N1.

### Lauf 6 — Buchung aus 0.5.1 (`pruefe_051.py`, Lager über `read_snapshot`)

Projekt und Lager aus `rm705\buchung_v0.5.1` (von einer Kopie von 0.5.1 geschrieben; Sollwert
`c62cddf4…` hat das Erstreview an eigener Kopie nachgerechnet):

| Stand | Ergebnis | Dialog `_previous` / `_legacy_bookings` |
|---|---|---|
| 0.5.1 | genau | 1 / — |
| 0.5.3 | **nicht** (weder Abdruck noch Altabdruck) | 0 / 0 |
| Zweig | als frühere Buchung | 0 / 1 |

`git tag --contains 51c19d2f0` → v0.5.2, v0.5.3. Der Changelogsatz stimmt also.

### Weitere Dialogsonde (`test_confirming_an_unchanged_053_spool`)

Spule aus 0.5.3 im Dialog ohne Änderung übernommen: `override() == existing` falsch,
Einstellungen ungleich; Datei gleich, gedruckte Gruppen gleich, Spulenpfade gleich. Der rohe
Wert des geerbten Felds springt von 10 auf 20 (Projektwert). → L2 unten.

### Lauf 3 — Worktree (ohne Caches im Worktree, gepinnt; `git status` danach sauber)

| Lauf | Ergebnis | Exit |
|---|---|---|
| `affected_tests.py` (types, serialise, handover, filament_usage, Dialog) | „439 von 451 — das ist die Suite“ → gezielt gewählt | 0 |
| ohne Fenster: slot_override_inherited, fingerprint/gap/atomic/raft-Verlauf, filament_usage, filament_inventory, filaments, project, print_settings, corpus, core_isolation, export, export_readback, manufacturer, cache, **text_length, shared_constants, language_rules, registry_consistency**, changelog, roadmap, directory_docs, wording, translations | 4378 passed, 9 skipped, 17 deselected | 0 |
| Fenster `test_print_settings_ui.py` | 335 passed | 0 |
| Fenster `test_filament_usage_ui.py` | 45 passed | 0 |
| Fenster `test_filament_workflow.py` | 36 passed | 0 |
| Fenster `test_locked_says_why.py` | 47 passed | 0 |
| `ruff check --no-cache .` / `ruff format --no-cache --check .` / `mypy` (Cache im Scratch) | grün, 1209 Dateien, 374 Dateien | 0 / 0 / 0 |

### Lauf 4 — Gegenproben per Mutation (Kopie `kmut`, je eine Stelle, danach zurück)

Ausgangslage der Kopie: Kern 1175 passed; Fenster 381 passed, 1 rot
(`test_locked_says_why::…[AiDisclosureDialog]`, nur in der Kopie — fehlende Wurzeldateien; im
Worktree grün). Diese eine Rotmeldung zählt unten nicht.

| Mutation | rot |
|---|---|
| Leser markiert nichts (`inherited=frozenset()`) | 4 |
| Schreiber schreibt geerbte Felder | 1 |
| `override_section` übergeht `inherited` | 5 |
| Dialog zeigt rohe Gruppe (Zeile 801 alt) | 1 (UI-Test RM-707) |
| Dialog trägt die Marke nicht weiter | 1 |
| **Vorschlag je Spule lässt den Pfad geerbt** (`_apply_advice`) | **0 — überlebt** → L1 |
| **Ausnahme der Lüfterkurve entfernt** (`_override_from_data`) | **0 — überlebt** → L6 |

`git merge-tree a33b58a19 b8f42046c` (welle3 mit Paket D): Exit 0, kein Konflikt.

## Teil 1 — Nachprüfung RM-705

- **M1 Changelog: behoben und wahr.** Sechs Sprachen, 135–147 Zeichen, unter „Drucken und
  Übergabe“. Gemessen (Lauf 6): 0.5.1 erkennt seine Buchung genau, 0.5.3 gar nicht, der Zweig als
  frühere Buchung; Ursache `51c19d2f0` in v0.5.2/v0.5.3. „fragt nach“ trägt der Code:
  `_auto_book` hält mit „Frühere Filamentbuchung prüfen“ an, der Dialog zeigt den Hinweis und
  „Weiteren Druck buchen“. RM-707 steht zu Recht nicht im Changelog (`5f68e51d8`, `fafcd4841`
  in keinem Tag).
- **M2 Grenzen: behoben.** `verbrauch.md` „Was den Abdruck trotzdem ändert“ (Netzbits/RM-706,
  Cura `z_gap`/RM-583, Slicer-Update), Archiv „Grenzen“ mit den Messungen.
- **L1 ohne Vorgabentest: Begründung stimmt.** `_DEFAULTS` ist weg; die Spulenklausel vergleicht
  mit dem Wert ohne Spule, ein geerbtes Feld folgt ihm. Die Vorgabe geht nur noch als
  Tabellengrundlage ein, und die fällt als Grundlage heraus. Spulentest über `SLOT_GROUPS`.
- **L2, L3, L4: behoben** (Docstring und Regel, Wächter mit Liste aller Abweichler, Kundenweg
  über `manufacturer.effective`). Zu L2 siehe Präzisierung L7 unten.

## Teil 2 — Review RM-707: Antworten

- **Jeder Ausgang:** 3MF und Konsolendatei für Elegoo, Orca, Bambu, Creality und Anycubic,
  dazu Prusa und Cura: welle3 → Zweig ändert genau `slow_down_min_speed`/`min_print_speed` von
  10 auf den Herstellerwert. 0.5.3 → Zweig gleich, außer Curas zwei neuen Schlüsseln auf Curas
  eigener Vorgabe. Am echten ElegooSlicer ist der Konfigurationsblock (627 Schlüssel) gleich dem
  von 0.5.3.
- **Speichern → Öffnen → Speichern:** Marke bleibt, zweite Speicherung gleich der ersten.
  Ein Projekt aus 0.6.0 ohne `inherited` (`spule_06`) kommt unverändert heraus, alle Ausgänge
  gleich welle3. Bei teils gesetzten Feldern bleibt `minimum_speed` 12 eigen und geht an jeden
  Slicer, `support_interface_cooling` erbt.
- **Bewusst gesetzter Wert gleich der Vorgabe:** Er geht nicht verloren. Die Marke entsteht nur
  aus fehlenden Schlüsseln, und ein eigener Wert wird immer geschrieben. Der Dialog vergleicht
  nur mit dem gezeigten Projektwert. Ein geerbtes Feld, in das der Kunde genau diesen Wert tippt,
  bleibt geerbt, wie gewollt (Sonde `gleich_getippt`). Verloren geht die Marke nur auf dem Weg
  „Alte Filamentwerte übernehmen“ (M1).
- **Dateiformat ohne Formatschritt: trägt.** 0.5.3 lehnt Format 51 ab. Die Schritte 46→51
  berühren keine Spulengruppe. Ein fehlender Schlüssel hieß in jeder veröffentlichten Fassung
  „kannte das Feld nicht“, und genau so liest ihn RM-707 jetzt. Eine Migration könnte in
  Dateien unveröffentlichter 0.6-Stände die gepinnte Vorgabe nicht von einer Wahl unterscheiden.
- **Offene Produktfrage: kein Rückschritt, kein Fund für 0.6.0.** 0.5.3 schrieb für dieselbe
  Spule ebenso `slow_down_layer_time = 8`, gemessen am echten ElegooSlicer und in allen
  Ausgängen. Der Block ist gleich, die Spulenpfade auch. Dazu kommt: Der Dialog von 0.5.3 belegte
  mit `effective_print_settings()` vor (`k053 main_window.py:8810`). Tabellenwerte trägt also nur
  eine Spule, die ohne Slicer angelegt wurde. Ob eine unveränderte Vorbelegung als geerbt gelten
  soll, kann welle4 entscheiden.

## Befunde

### M1 (mittel) — „Alte Filamentwerte übernehmen“ pinnt die Vorgabe der Dataclass

`app/ui/print_settings_dialog.py:937` (`_take_legacy_values`):
`source = own or getattr(self.settings, group)`. Das ist der Zwilling von Zeile 801, den
RM-707 nicht mitgenommen hat. Beleg: Sonde `test_legacy_values_of_an_old_spool`. Eine Spule aus
Format ≤ 19 hat eine Kühlgruppe mit vier Feldern, das Projekt 20 mm/s. Vor dem Klick zeigt der
Dialog 20, danach 10. `override()` lässt nur `support_interface_cooling` geerbt, die Spule fährt
10, und `_for_the_slot` schreibt `cooling.minimum_speed` an den Slicer. Damit tritt der Fehler,
den RM-707 behebt, auf diesem Weg wieder auf, beschriftet als „alte Werte“. Selten (Altspule ohne
Materialkennung an einer Spule mit Materialart), aber falsch gedruckt.
**Fix:** `source = handover.override_section(self._legacy, group, getattr(self.settings, group))`.
Dazu ein Test: Altspule mit geerbtem Feld, nach dem Übernehmen zeigt der Editor den Projektwert
und `override()` behält die Marke. Am alten Stand muss er rot sein.

### L1 (leicht) — Der Vorschlag je Spule (`_apply_advice`) ist ungeprüft

`app/ui/print_settings_dialog.py:8686–8688`. Die Mutation `inherited=previous.inherited` lässt
alle Tests grün. Ohne die Zeile ginge ein angenommener Vorschlag für ein geerbtes Feld still
verloren. Der Druckrat schlägt genau so ein Feld vor: `cooling.support_interface_cooling` für
PETG (`advise.py:1241`). **Fix:** Test mit einer Spule aus 0.5.3: Vorschlag je Spule annehmen,
dann muss der Wert in `settings_for_slot` und `_for_the_slot` ankommen.

### L2 (leicht) — Übernehmen ohne Änderung markiert das Projekt als geändert

`print_settings_dialog.py:994`: Ein geerbtes, unverändertes Feld bekommt in der Gruppe den
gezeigten Projektwert als Rohwert. Beleg: `test_confirming_an_unchanged_053_spool`.
`override() == existing` ist falsch, Datei, Druck und Spulenpfade bleiben gleich, aber
`Session.set_print_settings` vergleicht mit `==` und markiert das Projekt als geändert.
**Fix:** Für Felder, die geerbt bleiben, den Rohwert von `section` behalten. Test:
`dialog.override() == existing`.

### L3 (leicht) — Das geerbte Feld zeigt den Projektwert, gedruckt wird der Wert ohne Spule

Zeile 801 mit `main_window.py:9621` (`effective_print_settings()`, Projektebene). Beleg: Sonde
`anderes_material`, PETG-Spule im PLA-Projekt. Der Dialog zeigt 20, gedruckt werden 10. Vor
RM-707 zeigte er die falsche, aber gedruckte 10. Dasselbe gilt für eine Spule mit eigenem
Filamentprofil (Rücklesung). Gehört zur Ursache von N1, **Fix mit N1**: Der Dialog bekommt die
Werte der Spule ohne Übersteuerung (`settings_for_slot` ohne sie, mit Einrichtung).

### L4 (leicht) — Archiv RM-707: „ebenso `cooling.support_interface_cooling`“ ist nicht gemessen

Am ElegooSlicer steht vorher wie nachher `-1`, denn die Grundlage ist dort aus. Das gilt für alle
sieben Grundlagen der Sonde. **Fix:** „träfe es ebenso, sobald die Grundlage ihn einschaltet
(Projektwahl, Vorschlag) — am gemessenen Profil steht er aus.“

### L5 (leicht) — Die Regel zu `inherited` lädt nicht dort, wo Spulengruppen gebaut werden

`.claude/rules/verbrauch.md`, `paths:` nennt weder `print_settings_dialog.py` noch `handover.py`
oder `types.py`. Genau dort lag der übersehene Zwilling (M1). **Fix:** die drei Pfade ergänzen.

### L6 (leicht) — Die Ausnahme der Lüfterkurve ist ungeprüft

`serialise.py:876–877`. Wer die Mutation entfernt, sieht alles grün. **Fix:** Test mit einer
Spule ohne Kurvenfelder: Die Kurve kommt aus dem Material und ist nicht geerbt.

### L7 (leicht) — „derselbe Vergleich wie `_for_the_slot`“ stimmt nur ohne Slicer

`filament_usage.py:234`, `verbrauch.md`. `prepare` rechnet ohne Einrichtung, also ohne
Filamentprofil-Rücklesung. Bei einer Spule mit eigenem Profil können beide verschieden
antworten. Der Abdruck bleibt deterministisch, deshalb kein Verhaltensfehler. **Fix:** „dieselbe
Frage, ohne Slicer gerechnet“.

## Neuer Punkt (vorbestehend, keine Nummer vergeben)

**N1 — Der Spulendialog belegt eine Spule anderen Materials mit den Projektwerten vor.** Eine
PETG-Spule im PLA-Projekt druckt ohne eigene Werte 240/80. Wer „Temperaturen“ einschaltet und
übernimmt, bekommt 210/60, ohne etwas geändert zu haben. Gemessen in der Sonde
`vorbelegung_anderes_material`, gleich in 0.5.3 (`k053 print_settings_dialog.py:767`). Der
Einleitungssatz „Ausgeschaltete Bereiche benutzen die Projektwerte“ stimmt für solche Spulen
nicht. Vorschlag: vorbelegen mit den Werten der Spule ohne Übersteuerung (zusammen mit L3), für
welle4.

## Urteil

**Kann landen nach M1.** Der Fix ist eine Zeile und ein Test. L1, L2 und L6 sind klein und
lohnen sich vor dem Schnitt. L3 geht mit N1, L4, L5 und L7 sind Unterlagen. Der Kern von RM-707
hält gemessen, was er verspricht: An jedem Ausgang und am echten ElegooSlicer druckt eine Spule
aus 0.5.3 wieder wie unter 0.5.3, der Abdruck bleibt gleich, die Datei überlebt die Rundreise,
und Projekte aus 0.6.0 ändern sich nicht. **Weitere Prüfung:** nicht nötig, weil es nur ein
mittlerer Befund ist. Es reicht, dass der neue M1-Test am alten Stand rot und danach grün ist.
Mit welle3 `b8f42046c` (Paket D) ist kein Merge-Konflikt absehbar.
