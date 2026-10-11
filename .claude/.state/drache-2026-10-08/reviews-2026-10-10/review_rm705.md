# Review RM-705 — Abdruck der Verbrauchsbuchung über Updates stabil (Zweig `fix/verbrauch-abdruck`)

Gegenstand: Worktree `F:\sl-abdruck`, Stand `85ae9583a` auf welle3 `083dab2f6`, Diff
`083dab2f6..85ae9583a` (16 Dateien). Scratch: `scratchpad\rv705\`. Codekopien per `git archive`:
`k053` = v0.5.3, `k051` = v0.5.1, `kw3` = welle3 `083dab2f6`, `kzw` = Zweig, `kmerge` = Zweig +
RM-704 (merge-tree `9c33cea3c`), `kmut` = `kmerge` mit Mutation, `kD` = Paket D
`origin/claude/lauf-d` `fa5aaa036`. Sonden: `sonde.py`, `sonde_spule.py`, `sonde_grundlage.py` +
`grundlage_matrix.py`, `sonde_appweg.py`, `sonde_soll.py`; Läufe `lauf1..7.sh`, gepinnt FFFFF0FF.
Nichts im Worktree geändert (Tests mit `PYTHONDONTWRITEBYTECODE`, ohne Cacheprovider; ruff
`--no-cache`, mypy-Cache im Scratch). Begonnen 11:40, Urteil 12:15.

## Urteil

**Kann landen nach M1 und M2.** Beide betreffen Texte und Unterlagen, Code muss sich dafür
nicht ändern. Der Kern hält, was er verspricht, an einer eigenen Stichprobe gemessen:
Buchungen aus 0.5.2 und 0.5.3 werden bei unveränderten Netzen und unveränderter Grundlage genau
wiedererkannt, auch mit eigener Wahl, übernommenem Vorschlag und Spulenwerten. Der Abdruck ist
deterministisch, die Sollwerte kommen von außen, der Korpus ist echt, und der Wächter fängt
RM-704 ohne Zutun.

L1 bis L4 sind klein und lohnen sich vor der Landung, blockieren aber nicht (L1 und L3 je ein
Test, L2 zwei Sätze, L4 eine Zeile). **Nachprüfung:** kurz und nur über Changelog, Regel und
Archiv. Nötig ist sie, weil es zwei mittlere Befunde sind. Bei der Landung: Mit RM-704 kollidiert
nur `ROADMAP-ARCHIV.md`, weil beide ans Ende anhängen; gegen welle3 von heute (`b8cf40a0d`) ist
der Merge konfliktfrei.

## Antworten auf die Prüffragen

### 1. Richtigkeit gegen 0.5.3

**Sollwerte von außen: ja.** Alle vier an meinen eigenen Kopien der Tags nachgerechnet
(`sonde_soll.py`, gleicher Weg wie im Test): Würfel 0.5.3 `158d8f5d34a2…` = `CUBE_053`,
Buchung 0.5.3 `aa373e5e86b4…` = `BOOKED_053`, Würfel 0.5.1 `3cae285a9a19…` = `CUBE_051`,
Buchung 0.5.1 `c62cddf4e25e…` = `BOOKED_051`.

**Eigene Stichprobe, Tabelle.** Vier Szenarien, **von v0.5.3 geschrieben** (Format 46,
`app_version` 0.5.3), dann an drei Ständen auf dem Kundenweg gelesen (laden, `on_base` über
`resolve`, auswerten, `prepare`):

| Szenario | 0.5.3 | welle3 ohne Fix | Zweig |
|---|---|---|---|
| MK4S × PETG, Fein, Zylinder; eigene Wahl Fülldichte, Stütze Baum, Brim + Breite | `07b42ce26fc2` | `77142e5106d8` | `07b42ce26fc2` |
| X1C × ABS, Entwurf; übernommener Vorschlag Wände 4; Spulenwerte Temperatur + Kühlung | `08704c8607df` | `63efe0b044ac` | `08704c8607df` |
| K1 × TPU 95A, Standard; Spulenwerte nur Kühlung | `0eaf70808348` | `ac7f3db2a851` | `0eaf70808348` |
| Neptune 4 × PLA, Fest, zwei Körper; eigene Wahl Lüfter, Stütze Gitter | `87aa10ca08d6` | `b83ee8bb82d9` | `87aa10ca08d6` |

Ergebnis: am Zweig 4/4 gleich, ohne Fix 0/4. Die Spulenwerte in den Dateien tragen nur die
sechs Kühlfelder von 0.5.3 (im `project.json` nachgesehen).

**Slicer, die die Matrix des Bauagenten nicht fuhr** (`grundlage_matrix.py`: Zweig wählt die
Einrichtung, 0.5.3 liest dieselben Profile):

| Slicer | Fälle | Ergebnis |
|---|---|---|
| PrusaSlicer, MK4S | PLA Standard, PETG Fein | 2/2 gleich |
| Bambu Studio, X1C | PLA Standard, PETG Fein | 2/2 gleich |
| Cura, K1 | PLA Standard, PETG Standard | 2/2 gleich |
| Cura, Generic 220 | PLA **Fein**, PETG **Entwurf** | **verschieden**: `support.z_gap` 0,2 → 0,12 bzw. 0,2 → 0,28 mm |

Die Ursache liegt nicht in RM-705, sondern in RM-583 (`fafcd4841`): `manufacturer._base_settings`
rechnet für Cura den Stützabstand jetzt in ganzen Schichten aus dem Materialziel, 0.5.3 nahm
ihn aus der Tabelle. 0.6.0 druckt dort also wirklich anders; daraus folgt M2.

**Slicer-Update ändert einen Grundwert.** Für ein Feld nach 0.5.3 bleibt der Abdruck stabil:
Es zählt ohne eigene Wahl nicht (`test_every_later_field_at_its_base_keeps_the_fingerprint`).
Für ein Feld von 0.5.3 kippt er, wie schon bisher. **Ob er das soll:** Für die späteren Felder
ja. Das entspricht 0.5.3, das diese Werte nie sah, und dem Grundsatz von `on_base` („wer nur
nachsieht, hat nichts am Projekt geändert“). Derselbe Grundsatz spräche dafür, die Grundlage
auch bei den alten Feldern auszulassen. Ohne Bruch gegen 0.5.3 geht das heute nicht, denn 0.5.3
hat die Grundlage mitgehasht. Siehe Vorschlag N3 für RM-706.

### 2. „Weicht vom Herstellerprofil ab“: eindeutig und deterministisch?

**Deterministisch: ja.** `_without_later_fields` liest nur gespeicherte Daten (`explicit`, die
Spulenwerte) und eine Code-Konstante (`PrintSettings()`). Kein Slicer, keine Plattform und keine
Uhr gehen ein. Gleiche Buchung und gleiche Grundlage ergeben auf jedem Rechner denselben Abdruck,
auch mit Solidons Tabelle und ohne Slicer. Der Weg der Anwendung
(`manufacturer.effective(stored, base_settings(profile, quality, None))`, wie
`MainWindow.effective_print_settings`) und der Weg des Tests (`on_base(stored, resolve(...))`)
ergeben für das Korpusprojekt an 0.5.3 und am Zweig beide `aa373e5e…` (`sonde_appweg.py`).

**Eindeutig: nicht ganz.** Den Vergleich mit dem Herstellerprofil gibt es im Code nicht wirklich.
Als Stellvertreter dienen „eigene Wahl oder Vorschlag“ (eindeutig) und „Spulenwert abseits der
**Dataclass-Vorgabe**“. Letzteres ist nicht eindeutig (L2), und die Vorgabe wird damit tragend
(L1).

**Kann derselbe Abdruck zwei verschiedene Drucke treffen?** Ja, in zwei Fällen:

- (a) **Gewollt:** Zwei Drucke, die sich nur in der Grundlage eines späteren Felds
  unterscheiden, zum Beispiel nach einem Slicer-Update. Das war in 0.5.3 genauso. Folgen: Die
  Ausgabe gilt als dieselbe; im Buchungsdialog steht „schon gebucht“; *Ohne Rückfrage buchen*
  bucht nicht neu (`_auto_book` reicht die bekannte Vorgangskennung an `filaments.book`, das bei
  gleichen Positionen den alten Vorgang zurückgibt). Das ist dasselbe wie beim zweiten Export
  eines unveränderten Projekts. Ein echter zweiter Druck braucht dort ohnehin die ausdrückliche
  Wiederholung. Für den Zweck des Abdrucks halte ich das für vertretbar.
- (b) **Nicht gewollt** (L2): Eine Spule setzt ein späteres Feld genau auf die Dataclass-Vorgabe,
  die Grundlage hat einen anderen Wert. Gemessen: Die Grundlage hat `cooling.minimum_speed` 20,
  die Spule setzt 10, wirksam ist 10 statt 20, aber der Abdruck ist derselbe (`69efe7df…`). Mit
  12 an der Spule entsteht ein anderer. Das ist ein schmaler Randfall.

### 3. Wächter

- Der Wächter zählt über `print_settings.all_paths()`, also jedes Feld jeder Gruppe, und hält
  eine Untergrenze ein (`len(paths) >= 6`, keine leere Menge). Neue Kopfschlüssel fängt
  `TOP_053`.
- **Unterstrukturen:** In einer Gruppe kann keine verschachtelte Dataclass stehen, sonst
  scheitert `digest` schon an `json.dumps` (`_canonical` reicht sie unverändert durch). Tupel
  deckt `other_value` ab. `plate_choices` (Pfad → Wert) zählt ohnehin als Wahl. `slot_overrides`,
  `spool_bindings` und `slot_profiles` fallen weg und wirken über `mine` und die
  Slot-Identität. Abgedeckt ist also alles, was in den Abdruck kommt.
- **RM-704, `git merge-tree`:** Zweig + `origin/einstellungen/drache-druck3` (`076965bfe`)
  kollidiert nur in `ROADMAP-ARCHIV.md`. In der Kopie des gemergten Baums laufen
  `test_filament_usage_fingerprint_history.py` und `test_filament_usage_gap_history.py` mit
  55 passed, Exit 0.
- **Gegenprobe:** Eine Mutation (`kmut`) lässt nur `support.tip_diameter` als Grundlage im
  Abdruck. Ergebnis: 4 failed, 51 passed, Exit 1 (Würfel, Wächter, Spule, Kundenweg). Der Wächter
  fängt das neue Feld also ohne Zutun, nennt dabei aber das falsche Feld (L3).

### 4. Datei- und Kundenweg

- **Korpus echt:** `usage_booking_v46.p3d` trägt Format 46 und `app_version` 0.5.3; Kühl- und
  Stützgruppe haben genau die Felder von 0.5.3. Meine eigene Rechnung an v0.5.3 über genau diese
  Datei ergibt `aa373e5e…`, den Abdruck der Buchung im Korpuslager (`operation_id`
  `rm705-druck`, 8,6 g von Hand). Der Zweig ergibt dasselbe, welle3 ohne Fix `f55f287eb7e4…`.
  0.5.1 lehnt Format 46 ab, wie es soll. Meine unabhängig von 0.5.3 erzeugte Buchung
  (`sonde_soll.py`) trifft ebenfalls `aa373e5e…`.
- **Fenster:** `test_filament_usage_ui.py` 45 passed und `test_filament_workflow.py` 36 passed,
  beide mit Fenster und Exit 0. Kein Fenstertest öffnet das Projekt aus 0.5.3. Der Kundenwegtest
  ruft die Helfer des Dialogs auf (`_previous`, `_legacy_bookings`), und der Einstellungsweg der
  Anwendung ist gemessen gleich (siehe 2). Einen Fenstertest halte ich für die Landung nicht für
  nötig; er sollte aber am Weg der Anwendung hängen (L4).

### 5. Unterlagen, Changelog, Läufe

- **Regel `verbrauch.md`:** Frontmatter mit `description` und `paths:` ist in Ordnung; sie lädt
  bei `filament_usage.py`, `knowledge/filaments.py`, `print_fields.py` und
  `ui/filament_usage.py`. Ein neues Feld berührt `print_fields.py`, die Regel greift also. Es
  fehlen die Grenzen (M2).
- **Karte** `app/core/CLAUDE.md` und `karte-tests.md` sind in Ordnung. Die README-Zeile im
  Korpus ist da.
- **Archiv:** Der Eintrag ist ausführlich, im Register stand RM-705 nicht. Es fehlen die Grenzen
  (M2), und der Satz „im Changelog als Eigenschaft“ müsste mit M1 angepasst werden.
- **Changelog:** Sechs Sprachen, 78–120 Zeichen, `test_changelog` und `test_text_length` sind
  grün. Inhaltlich trifft der Satz aber nicht zu (M1).
- Läufe: siehe Tabelle unten. ruff, format und mypy sind grün.

### 6. Geometrieteil bitgenau (Frage des Koordinators)

**Muss RM-705 die `fit_to_size`-Grenze aus Paket D in Archiv und Regel nennen? Ja** (M2), und
mit ihr jede andere Bitänderung eines Netzes.

Gemessen habe ich die zwölf Beispielprojekte **aus v0.5.3** an 0.5.3, am Zweig (welle3
`083dab2f6` einschließlich L3) und an Paket D. Die Prüfsumme je Körper wird wie in `prepare`
gebildet:

| Stand | Abdrücke gleich 0.5.3 | Körper bitgleich |
|---|---|---|
| Zweig | 11 von 12 | 19 von 21 |
| Paket D (nur Netzbits vergleichbar, Abdruckcode vor RM-705) | — | 19 von 21 |

Die einzige Abweichung ist `gehaeuse-mit-bausteinen` (637 → 634 und 224 → 221 Punkte). Sie
kommt von **bewussten Bausteinänderungen**: `LIBRARY_VERSION` 23 → 27, Mutternfalle
`PartChange` 25 und 26. Gemeldet wird sie beim Öffnen; es ist ein anderer Druck.

- **Was häufiger trifft als Paket D:** genau diese Bausteinänderungen. Jedes Projekt aus 0.5.3
  mit Mutternfalle (25/26), Gewinde (24, ganze Umläufe) oder Lasche (24) bekommt neue Netzbits
  und wird nicht wiedererkannt.
- **Paket D** trifft nur einen `fit_to_size` auf fast das schon bestehende Maß. Der Weg 3 von
  0.5.3 setzt beim Übernehmen genau einen `fit_to_size` auf das Arbeitsmaß, mit einem Faktor
  weit von 1 (`k053/app/core/generate.py:292`); das Weg-3-Beispiel aus 0.5.3 bleibt unter D
  bitgleich.
- **Aus den Einstellungen statt aus den Netzen:** Cura mit den Stufen Fein und Entwurf (siehe 1).
- **Nicht gemessen** ist, was bis zum Schnitt um 22:00 noch auf welle3 landet (N2).

**Verlangt der neue Punkt des Bauagenten etwas vor 0.6.0?** Ja, die Grenze gehört benannt in
Regel und Archiv (M2) und ein Lauf der Beispielsonde vor dem Tag (N2). Den Umbau selbst kann
RM-706 in welle4 übernehmen; das trägt die Messung.

## Befunde

### M1 (mittel) — Der Changelog erzählt eine Nicht-Differenz und verspricht mehr, als gilt

`changelog/*.md` (de:127; en, es, fr, it, pt je der neue Punkt unter „Drucken und Übergabe“):
„Ein vor dem Update gebuchter Druck wird danach im Filamentlager wiedererkannt.“

- **Gegen den Tag ist es keine Änderung.** Eine Buchung aus 0.5.2 oder 0.5.3 erkennt schon 0.5.3
  wieder: Seit 0.5.2 sind die Felder gleich, und die Kette 0.5.2 → 0.5.3 bestätigt der Bauagent.
  Der Bruch, den RM-705 behebt, kam erst nach `v0.5.3` und war nie draußen. Nach Roberts
  Prüfstein ist das ein Punkt, „der einem Kunden erzählt, was er schon hat“.
- **Er gilt außerdem nicht allgemein.** Gemessen: 0.5.0 wird nicht erkannt, 0.5.1 nur als
  Hinweis; Cura auf Fein und Entwurf wird nicht erkannt; Projekte mit geänderten Bausteinen
  ebenso; dazu kommt der Fall aus Paket D.
- **Neu und kundenspürbar ist etwas anderes:** Buchungen aus 0.5.1 erscheinen wieder als
  frühere Buchung zur Prüfung, auch im Modus *Ohne Rückfrage buchen*. Diesen Bruch hat
  `51c19d2f0` gebracht (`plate_choices` im Abdruck, `git tag --contains` → v0.5.2, v0.5.3). Das
  ist also eine echte Behebung.

**Fix:** Den Punkt in allen sechs Sprachen ersetzen, zum Beispiel de: „Eine Buchung aus Solidon
0.5.1 erkennt das Filamentlager wieder als frühere Buchung und fragt nach, bevor es denselben
Druck erneut abbucht.“ Alternativ den Punkt streichen. Im Archiv den Satz „im Changelog als
Eigenschaft“ entsprechend ändern.

### M2 (mittel) — Regel und Archiv nennen nicht, was den Abdruck trotzdem kippt

`.claude/rules/verbrauch.md` und `ROADMAP-ARCHIV.md`, Abschnitt RM-705. Die Regel friert Feldnamen
ein und verbietet Umbenennen, Umtypen und anderes Runden. Sie schweigt zu drei Wegen, die gemessen
in 0.6.0 schon greifen oder künftig greifen:

1. **Netzbits** (`prepare`, sha256 über `vertices`/`faces`): bewusste Bausteinänderungen
   (gemessen, siehe 6), jede Op, deren Bits sich ändern, und ausdrücklich jede *druckgleiche*
   Beschleunigung, die Roberts neue Regel 6 gerade fordert. Dazu gehört Paket D mit
   `fit_to_size` innerhalb von `PRINT_LIMIT`. Die Folgearbeit ist RM-706 (welle4).
2. **Eine geänderte Grundlage eines eingefrorenen Felds durch Solidon selbst**, nicht nur durch
   ein Slicer-Update: Seit RM-583 rechnet Cura `support.z_gap` neu (gemessen 0,2 → 0,12 mm auf
   Fein, 0,2 → 0,28 mm auf Entwurf). Das wirkt wie ein Umbenennen, und die Regel nennt es nicht.
3. **Die Dataclass-Vorgabe eines späteren Felds trägt die Spulenklausel** (L1).

Ohne diese Sätze fährt die nächste Sitzung eine druckgleiche Beschleunigung oder eine bessere
Grundlage nach Regel und bricht die Wiedererkennung still.

**Fix:** In `verbrauch.md` drei Punkte unter „Was den Abdruck trotzdem ändert“, je ein Satz mit
Verweis (RM-706, RM-583, L1). Im Archiv ein Absatz „Grenzen“ mit den Messungen: Beispiele 11/12
und 19/21 Körper; Cura 2/4; Paket D trifft die Beispiele aus 0.5.3 nicht.

### L1 (leicht) — Die Vorgabe eines späteren Felds ist tragend und von keinem Test gehalten

`app/core/filament_usage.py:128` (`_DEFAULTS = PrintSettings()`) und `:249–251`. Die
Spulenklausel vergleicht mit der **aktuellen** Dataclass-Vorgabe.

- **Gemessen** (`sonde_spule.py`, Fall 2): Eine Spule, angelegt in 0.6.0 auf der Tabelle, trägt
  `minimum_speed` 10. Steigt die Vorgabe später auf 15, kippt ihr Abdruck (`6337c64f…` →
  `88decc6c…`), ohne dass sich am Druck etwas geändert hat.
- **Keine Prüfung hält das:** Der Spulentest liest die Vorgabe zur Laufzeit
  (`_defaults(later)` über `CoolingSettings()`), der Würfeltest sieht die Vorgabe nicht.
- **Spulengruppen:** Der Spulentest deckt nur `cooling.*` ab (Zeile 210). Ein späteres Feld in
  Temperatur, Rückzug oder Filament liefe ungeprüft durch die Spulenklausel.

**Fix:** Ein Test, der für jedes spätere Feld die Vorgabe festschreibt (Tabelle im Test, Werte
aus dem Commit der Einführung). Ein neues Feld verlangt dann einen Eintrag, eine geänderte
Vorgabe eine Entscheidung. Den Spulentest über alle vier Spulengruppen laufen lassen. Dazu ein
Satz in der Regel.

### L2 (leicht) — Spulenklausel: eine Kollision und ein unbenannter Zwilling

`app/core/filament_usage.py:249–251`.

- **Gemessen** (`sonde_spule.py`, Fall 1): Die Grundlage hat 20, die Spule setzt 10 (die
  Vorgabe). Wirksam sind 10 statt 20, der Abdruck ist aber derselbe wie ohne Spule (`69efe7df…`).
- **Zwilling:** `handover._for_the_slot` beantwortet dieselbe Frage („weicht diese Spule in
  diesem Feld ab?“) anders, nämlich gegen den Wert ohne die Spule. Danach entscheidet die
  Übergabe, was an den Slicer geht.
- **Die Abweichung ist gewollt** (Kompatibilität mit 0.5.3, weil der Leser fehlende Felder mit
  der Vorgabe füllt). Nach `.claude/rules/zwillinge.md` muss sie dann aber als Entscheidung
  benannt sein. Sie hängt an N1: Wird N1 behoben, muss die Spulenklausel mitziehen.

**Fix:** Im Docstring von `_without_later_fields` und in der Regel einen Satz, der die
entschiedene Abweichung von `_for_the_slot` nennt, die Kollision als Grenze festhält und auf N1
verweist.

### L3 (leicht) — Der Wächter nennt beim Fehlschlag das falsche Feld

`tests/test_filament_usage_fingerprint_history.py:188–192`. Der Test vergleicht jeden Pfad mit
`CUBE_053`. Ist schon der Grundabdruck falsch, scheitert er am **ersten** Pfad. In der Gegenprobe
(nur `support.tip_diameter` rutscht durch) meldete er `cooling.minimum_speed`. Wer den Wächter
nach einem neuen Feld rot sieht, sucht so am falschen Feld.

**Fix:** Den unveränderten Abdruck einmal gegen `CUBE_053` prüfen, dann je Pfad gegen den
unveränderten Abdruck vergleichen und **alle** abweichenden Pfade in einer Liste melden.

### L4 (leicht) — Der Kundenwegtest hängt nicht am Einstellungsweg der Anwendung

`tests/test_filament_usage_fingerprint_history.py:260` benutzt
`print_settings.on_base(stored, print_settings.resolve(...))`. Die Anwendung rechnet
`manufacturer.effective(stored, manufacturer.base_settings(profile, quality, setup))`
(`MainWindow.effective_print_settings`, `main_window.py:25641`), einschließlich `measured_on`.
Heute ist das Ergebnis gleich (gemessen, `aa373e5e…`). Weicht `effective` aber künftig ab, etwa
durch eine Messung auf dem Raster, merkt der Test es nicht (Testart „Anschluss“).

**Fix:** Die Zeile auf
`manufacturer.effective(stored, manufacturer.base_settings(profile, stored.quality, None))`
umstellen.

## Neue Punkte (nicht aus diesem Diff; Vorschlag, keine Nummer vergeben)

### N1 (mittel) — Spulenwerte aus 0.5.3 überschreiben nach dem Update neue Felder des Herstellerprofils

`serialise._group_from_data` (`:804`) füllt ein fehlendes Feld einer Spulengruppe mit der
Dataclass-Vorgabe. `handover._for_the_slot` schreibt dann jedes Feld, das von der Grundlage ohne
Spule abweicht, als Abweichung an den Slicer.

- **Gemessen** (`sonde_spule.py`, Fall 3): Eine Spule aus 0.5.3 (Kühlung ohne `minimum_speed`)
  auf einer Grundlage mit 20 (wie Elegoo) ergibt die Spulenpfade `cooling.minimum_speed` und
  `temperature.nozzle`. Ins Orca-Filament geschrieben werden `slow_down_min_speed = 10` und
  `nozzle_temperature = 215`.
- 0.5.3 hat `slow_down_min_speed` nie geschrieben (dort nur eine Schlüsselliste,
  `k053/app/core/export/handover.py:160`), es galten die 20 von Elegoo.
- Dasselbe gilt für `cooling.support_interface_cooling` (wird False statt des Profilwerts).
- **Folge:** Ein Kunde mit Spulenwerten aus 0.5.3 und einem Herstellerprofil darunter druckt nach
  dem Update still mit anderen Werten, ohne etwas getan zu haben.
- **Entstanden** mit `5f68e51d8` (`minimum_speed`) und `fafcd4841` (RM-583).
- **Vorschlag:** Ein Feld, das in der Datei einer Spule fehlt, gilt als nicht übersteuert, etwa
  über einen Satz ausdrücklich gesetzter Felder je Spulengruppe oder eine Migration auf die
  Grundlage beim Öffnen. Danach die Spulenklausel von RM-705 auf „weicht vom Wert ohne Spule ab“
  umstellen, also dieselbe Auskunft wie `_for_the_slot` (siehe L2). Vor 0.6.0 entscheiden.

### N2 — Vor dem Schnitt die Beispielsonde an welle3 fahren

Etwa eine Minute. Die Codekopie per `git archive origin/welle3` nach
`scratchpad\rv705\kw3final`, dann
`python -I -B scratchpad\rv705\sonde.py <kopie> beispiele <ordner> w3final scratchpad\rv705\k053\app\examples`
und die Prüfsummen je Körper mit `beisp\ergebnis.k053.beispiele.json` vergleichen.

- Jeder Körper, der außer den beiden in `gehaeuse-mit-bausteinen` abweicht, ist ein Bruch der
  Wiedererkennung gegen 0.5.3, der in Archiv und Changelog gehört.
- Achtung: Pfade mit Schrägstrichen übergeben. `\\$k` in der Befehlszeile oder im Heredoc wird
  zu `\$k`, die Sonde importiert dann den Hauptbaum. Die Prüfung von `app.__file__` hält sie in
  dem Fall an.

### N3 — Vorschlag für RM-706: auch die Einstellungen aus den gespeicherten Eingängen

Bildet RM-706 den Geometrieteil aus den gespeicherten Eingängen, sollte derselbe Schritt die
Einstellungen über `print_settings.own_part` nehmen (eigene Wahl, Vorschläge, Stufe, Spulen)
statt über die wirksamen Werte. Der heutige Abdruck bleibt dann als Altabdruck erhalten. Damit
kippen Slicer-Updates und Solidons eigene Grundlagen (Cura, RM-583) keinen Abdruck mehr, und N1
und L1 entfallen von selbst.

## Läufe

Alle gepinnt (FFFFF0FF); der Exit-Code ist im Skript direkt nach dem Befehl gelesen.

| Lauf | Ergebnis | Exit |
|---|---|---|
| Worktree, ohne Fenster: `test_filament_usage_fingerprint_history`, `_gap_history`, `test_filament_usage`, `test_filament_usage_ui`, `test_filament_inventory`, `test_filaments`, `test_project`, `test_print_settings`, `test_corpus`, `test_core_isolation`, `test_language_rules` | 1892 passed, 5 skipped, 54 deselected (1951 gesammelt) | 0 |
| Worktree: `test_directory_docs`, `test_roadmap`, `test_changelog`, `test_text_length`, `test_wording`, `test_agent_mirror`, `test_translations` | 370 passed, 4 skipped, 8 deselected | 0 |
| Worktree, Fenster: `test_filament_usage_ui.py` | 45 passed | 0 |
| Worktree, Fenster: `test_filament_workflow.py` | 36 passed | 0 |
| `ruff check --no-cache .` | All checks passed | 0 |
| `ruff format --no-cache --check .` | 1208 files already formatted | 0 |
| `mypy` (Cache im Scratch) | no issues in 374 source files | 0 |
| `kmerge` (Zweig + RM-704): beide Verlaufstests | 55 passed | 0 |
| `kmut` (Mutation `tip_diameter`) | 4 failed, 51 passed | 1 (erwartet) |
| Sonden `lauf1`, `lauf2`, `lauf4`, `lauf5`, `lauf7`, `sonde_spule`, `sonde_appweg`, `sonde_soll` | siehe oben | je 0 |

`tools/affected_tests.py` wählt für `filament_usage.py` 200 Dateien, also praktisch die Suite.
Deshalb habe ich gezielt gewählt wie der Bauagent, dazu die Fensterdatei des Buchungsablaufs.

## Gelesen

Jede Zeile des Diffs: `filament_usage.py`, beide Testdateien, `verbrauch.md`,
`app/core/CLAUDE.md`, `karte-tests.md`, `tests/data/README.md`, Archiv, sechs Changelogs und beide
Korpusdateien. Dazu der Weg des Abdrucks:

- `handover`: `_resolve_slot`, `settings_for_slot`, `override_for`, `_for_the_slot`,
  `_orca_filament`
- `serialise`: `print_settings_to_data`, `_group_from_data`, `_override_from_data`
- `hashing`: `digest`, `_canonical`, `_profile_parts`
- `manufacturer`: `base_settings`, `effective`
- `ui/filament_usage`: `_previous`, `_legacy_bookings`, `_auto_book`
- `filaments.book` und `MainWindow.effective_print_settings`

Seit v0.5.3 quelltextgleich (`fnvergleich.py`) sind alle Funktionen auf diesem Weg, außer
`_resolve_slot`, das nur mit `setup` anders rechnet, und `prepare` übergibt keines. Ebenso
gleich: `resolve`, `on_base`, `slot_identity`, `merge_slots`, `as_mesh_data` und die Tabellen
der alten Felder (`print_settings.toml`, `printers.toml`; `materials.toml` nur mit neuen
Stützwerten, die `resolve` nicht liest).
