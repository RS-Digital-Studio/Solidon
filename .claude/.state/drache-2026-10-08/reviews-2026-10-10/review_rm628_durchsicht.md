# Durchsicht RM-628 — M-a: Trennschichten im Cura-Fenster

Prüfling: Worktree `F:\sl-cura`, Zweig `einstellungen/cura-rundung-rm628`, Stand `df5eb90df`
(Merge welle3 `997ce9fcd`), Behebung `325561e46`. Vorlauf: `review_rm628_nach.md` (M-a),
Bericht `berichte-2026-10-10/rm628b.md` Abschnitte 4/5. Scratch `scratchpad\rv628d\`.
Nur gelesen und gemessen; `git status` im Worktree vor und nach allen Läufen leer.
Nach einem Abbruch am Nutzungslimit fortgesetzt, Abschluss 16:45 (Frist 15:45 überschritten).

## 1. `_cura_interface`, `_cura_window_choices`, `cura_profile_beside` gegen Curas Leselogik

**Eine Funktion für beide Wege.** `handover._cura_interface` (`handover.py:2023–2056`) gibt
Schalter und Höhen. Die Konsole holt sie in `_for_supports` (`:2174`) als Millimeter, die
obere Höhe über `CURA_MIRRORED` (`slicer_keys.py:879`). Das Fenster holt sie über
`_cura_window_choices` (`:7949–7958`) als `=layer_height * N`, die obere ausdrücklich, und
zwar für den globalen Container (`:8066–8073`) und je Extruderprofil (`:8077–8086`). Danach
kommen nur noch `_cura_accelerations`, `_without_curas_own_fan_curve`, `for_the_cura_window`
und `_without_line_break`. Diese Schritte fassen nur Beschleunigung und Ruck an,
übersetzen `true`/`false` und prüfen auf Umbrüche. Eine Formel geht unverändert durch.

**Curas Lesart (Cura 5.13, Installation):**
- `CuraProfileReader.read` → `_upgradeProfile`: Bei `version = 4` gibt es keine Aufwertung,
  die Zeichenkette geht unverändert an `InstanceContainer.deserialize`. Dort landet
  `[values]` roh in `_cached_values` (`UM/Settings/InstanceContainer.py:639`).
  `_instantiateCachedValues` (`:677–689`) ruft `setProperty`.
- `UM/Settings/SettingInstance.py:172–173`: Eine Zeichenkette mit `=` am Anfang wird zu
  `SettingFunction(value[1:])`. Beim Lesen gibt `__getattr__` (`:139–153`) ein
  Nicht-String unverändert zurück. Wahrheitswerte laufen über `ast.literal_eval`
  (`SettingDefinition.py:826`).
- `cura/Settings/CuraContainerRegistry.py:220–388` (`importProfile`): Ein einzelner
  Container wird verteilt. Jeder Schlüssel mit `settable_per_extruder` geht mit
  `getProperty`/`setProperty` ins erste Extruderprofil, die `SettingFunction` als Objekt. Alle
  sechs Schlüssel gehören dazu (`fdmprinter.def.json`, keiner trägt
  `settable_per_extruder: false`). `layer_height` ist `settable_per_extruder: false` und
  kommt daher aus dem globalen Stapel, dort steht der Wert der Einstellungsseite. Bei mehreren
  Containern werden die Extruderprofile nach `position` sortiert, der globale behält alles.

**Sonde** `rv628d\probe_window.py`: echte Cura-Installation als aktive Maschine, nur lesend.
Curas eigene `SettingFunction` wird unverändert aus `UM/Settings/SettingFunction.py`
geladen, nur `Logger` und `ContainerInterface` sind Stubs. Die Datei wird gelesen wie
`CuraProfileReader`, verteilt wie `importProfile` und ausgewertet wie `setProperty`.
Gemessen: 48 Fälle mit 72 Containern (Ender-3 V3 SE, Centauri Carbon 2, Sovol SV06 × Baum
und Gitter × oben 0/2 × unten 0/3 × eine und zwei Spulen, PETG, 0,2 mm). **Bei allen sechs
Schlüsseln gilt Fenster = Konsole = Sollwert aus der Lagenzahl.** Jede Formel ist gültig
und liest nur `layer_height`, Curas Log bleibt leer. Stellt der Kunde in Cura danach auf
0,28 mm, folgen die Höhen (0,56 und 0,84). Ausgabe: `out\probe_window.json`, `detail.txt`,
`EXIT=0`.

**Übersteuert die ausdrücklich gesetzte obere Höhe die Qualitätsprofile?** Ja. Curas
Stapel ist Nutzer → `quality_changes` (das importierte Profil) → Absicht → Qualität →
Material → Variante → `definition_changes` → Definition. Zehn Qualitätsprofile der
Installation setzen `support_roof_height = 0.45`, aber keine `support_interface_height`
(Key3D Tyro ×3, NWA3D A31 ×4, NWA3D A5 ×3). Die Nylonprofile der UltiMaker Method setzen
`=support_interface_height`. Würde nur die Elternhöhe geschrieben, käme das Kind aus der
Qualität und es gälte 0,45. Weil `support_roof_height` und `support_bottom_height` sowie
beide Schalter samt Eltern im `quality_changes` stehen, kann kein tieferer Container sie
überdecken. Weitere Kinder haben die sechs Schlüssel nicht.

## 2. Fensterprofil schaltet wie die Konsole (probe_roof, erweitert)

Messung wie bei `probe_roof.py`, aber über alle Container und mit Curas Auswertung (siehe
oben): oben 0 und 2, unten 0 und 3, eine und zwei Spulen (PETG+PLA), Baum und Gitter, drei
Drucker. Die Schalter `support_interface_enable`, `support_roof_enable` und
`support_bottom_enable` sowie die drei Höhen stimmen überall mit der Konsole überein. Der
Test `test_curas_window_switches_the_interface_like_the_console` prüft dasselbe für 0/2 ×
0/3 und eine/zwei Spulen. Er ist am Fehlen der Formel und an der Lagenzahl verankert und
lief in allen vier Fällen.

## 3. Merge in `advise._support_contact` (`advise.py:1404–1448`)

Beide Absichten sind erhalten. Den RM-628-Zweig (`elif gap_rounding(...) == "up_and_one"`)
gibt es nur für Cura (`gap_rounding`, `advise.py`: `up_and_one` nur bei `flavour == "cura"`).
Den RM-704-Rat zum Spitzendurchmesser gibt es nur für `flavour == "orca"`. Die beiden
berühren sich also nicht, und `roofs = layers` im Cura-Zweig ist nur folgerichtige
Buchführung. `support.interface_layers` bekommt dank `if/elif` höchstens einen Rat. Der
Spitzenrat hat einen eigenen Pfad, es entsteht also kein doppelter Rat.

## 4. Tore (gepinnt `FFFFF0FF`, Caches im Scratch)

| Lauf | Ergebnis | Exit |
|---|---|---|
| `ruff check --no-cache .` | All checks passed | 0 |
| `ruff format --no-cache --check .` | 1206 files already formatted | 0 |
| `mypy` | no issues in 374 source files | 0 |
| `test_print_settings.py`, `test_advise.py`, `test_text_length.py`, `test_directory_docs.py`, `test_cura_machine.py`, ohne Fenster/Renderer/Leistung/`rendered`/Slicer, `-n 6` | 1496 grün, 9 übersprungen | 0 |
| `probe_window.py` / `probe_warn.py` | 48 von 48 / 8 Fälle | 0 / 0 |

`dateiformat.md` hat am Stand `df5eb90df` 30 679 Byte (Blob gleich Datei, `.gitattributes`
erzwingt `eol=lf`), das Budget sind 30 720 Byte. Es bleiben 41 Byte Luft, bei der nächsten
Zeile dort muss etwas umziehen.

## Funde

### L-1 (leicht, aus M-a, kein Halt) — Bei „oben 0, unten > 0“ zeigt Cura an der Elternhöhe eine Warnung

- `handover.py:2048`: `support_interface_height` folgt nur der oberen Lagenzahl. Bei oben 0
  und unten 3 steht sie im Fenster auf `=layer_height * 0`. `support_interface_enable` ist
  dann eingeschaltet, also ist die Einstellung aktiv.
- Beleg `rv628d\probe_warn.out` (Curas `minimum_value_warning` `0.2 + layer_height`, mit
  Curas `SettingFunction` ausgewertet): 0 < 0,4 bei 0,2 mm, 0 < 0,3 bei 0,1 mm, beide Male
  WARNUNG. Vor M-a bekam das Fenster den Schlüssel nicht und zeigte keine Warnung. Auf den
  Druck wirkt sie nicht, denn beide Kinder stehen ausdrücklich und CuraEngine liest die
  Kinder. Der Kunde sieht aber ein gelbes Zeichen an „Support Interface Thickness 0 mm“,
  sofern die Einstellung sichtbar ist. Genau das passiert, wenn er unter Bäumen den Rat
  „obere Trennschicht“ ablehnt (unten gilt die Vorgabe 2).
- Bei 0,1 mm mit zwei oberen Lagen warnt Cura ebenfalls (0,2 < 0,3). Das ist Curas
  Schwelle gegen Solidons bewusste Wahl und kein Fund.
- **Fix:** Im Fenster die Elternhöhe nach der dickeren Seite schreiben
  (`=layer_height * max(layers, bottom)`). Das ändert den Druck nicht, weil
  `support_roof_height` und `support_bottom_height` ausdrücklich stehen. Testfall im
  vorhandenen Test bei 0/3: Elternhöhe `=layer_height * 3`, obere Höhe
  `=layer_height * 0`.

### L-2 (leicht, nicht aus M-a, neuer Punkt) — Treppenstufe unten: Konsole nach oben, Fenster nach unten

- `handover.py:2175–2176`: `support_bottom_stair_step_height = "0" if layers > 0 else 0.3`
  mit `layers` = **obere** Lagen. Curas Definition rechnet
  `0 if support_bottom_enable else 0.3` (`fdmprinter.def.json`), also nach der **unteren**.
  `_cura_computed` verspricht „je Zeile die Formel aus der Definition“.
- Beleg `probe_window.py` (Curas Formel mit den Fensterwerten): bei oben 2/unten 0 Fenster
  0,3, Konsole 0; bei oben 0/unten 3 Fenster 0, Konsole 0,3. Das betrifft 36 von 72
  Containern, bei gleicher Nullstelle beider Seiten stimmt es. Seit M-a schaltet das
  Fenster `support_bottom_enable` selbst, deshalb tritt der Unterschied jetzt in genau
  diesen Fällen auf. Wirkung nur bei Curas normaler Stütze (Gitter, automatisch, Hybrid):
  Der Stützfuß auf schrägen Flächen ist im Fenster gestuft und in der Konsole nicht, oder
  umgekehrt. Bei der Vorgabe 2/2 sind beide gleich. Auseinander laufen sie, wenn eine
  Grundlage unten 0 führt (MK4S, `types.py:1407–1410`) oder der Kunde eine Seite auf 0 setzt.
- Herkunft `f934a4221` (27.08., seit v0.1.1 in jedem Tag), also älter als die eigenen
  unteren Lagen aus RM-583. Kein Rückschritt aus diesem Zweig.
- **Fix:** `"0" if settings.support.bottom_interface_layers > 0 else f"{_STAIR_STEP:g}"`,
  am besten in `_cura_interface` (Konsole). Das Fenster rechnet die Formel selbst. Test:
  Bei 2/0 und 0/3 ist die Treppenstufe der Konsole gleich `0 if support_bottom_enable else
  0.3` mit dem geschriebenen Schalter. Kann im selben Zweig mit, sonst als neuer Punkt
  ins Register.

## Prüfpunkte ohne Fund

- Schalter als Werte (`True`/`False` im Fenster, `ast.literal_eval`), Höhen als Formel,
  ebenso je Extruderprofil. Die Konsole ist unverändert in Millimetern, und die
  Gegenproben des Bauagenten (ohne Trennschicht im Fenster 4 rot, Höhen als Zahl 4 rot)
  passen zur Testmatrix.
- Der neue Test vergleicht über einen eigenen Formelleser (`_window_number`) und nicht über
  Curas Auswertung. Die Sonde zeigt, dass Curas Auswertung zum selben Ergebnis kommt. Dass
  der Zwei-Spulen-Fall zweimal PETG nutzt, schwächt ihn nicht, denn die Trennschicht hängt
  nicht am Material.
- Nicht erneut gemessen: ein Schnitt im Fenster selbst (es lässt sich ohne Bedienung nicht
  fahren) und die Gegenproben. Belegt ist der Weg Datei → Container → Wert mit Curas Code.
- Grenze, kein Fund: Teilwerte je Netz (`CURA_DERIVED_PER_MESH`) stehen in der 3MF weiter
  in Millimetern und folgen einer in Cura geänderten Schichthöhe nicht. Das war schon vor
  M-a so und gehört nicht zu dieser Änderung.

## Kundensicht

Vorher übernahm das Fenster die Trennschicht der Maschine. Auf Sovol, Elegoo, Prusa und
Voron fehlte sie unter Bäumen, und PETG lag nach Solidons Rat 0,40 statt 0,20 über dem
Teil. Jetzt bekommt das Fenster Solidons Wahl mit derselben Zahl wie die Konsole, und die
Höhen folgen einer Schichthöhe, die der Kunde in Cura ändert. Neu sichtbar ist nur L-1,
ein gelbes Warnzeichen ohne Wirkung auf den Druck.

## Urteil

**Kann landen.** M-a ist behoben und an Curas eigener Lesart belegt: 48 Fälle mit 72
Containern, Fenster = Konsole = Sollwert, die Formel greift und übersteuert die
Qualitätsprofile, die die obere Höhe selbst setzen. Der Merge erhält beide Räte ohne
Doppelrat, alle Tore sind grün. L-1 (kosmetisch, ein Wert) und L-2 (älter als der Zweig)
halten nichts auf. Sie sollten aber behoben werden, L-1 am besten gleich im Zweig.
