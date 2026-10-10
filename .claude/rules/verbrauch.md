---
description: "Verbrauchsbuchung — der Abdruck eines Drucks bleibt über Updates gleich: eingefrorene Felder von 0.5.3, ein neues Einstellungsfeld zählt nur als Abweichung, Altabdrücke"
paths:
  - "app/core/filament_usage.py"
  - "app/core/knowledge/filaments.py"
  - "app/core/knowledge/print_fields.py"
  - "app/ui/filament_usage.py"
---

# Regeln für die Verbrauchsbuchung

Der Abdruck (`filament_usage.prepare`) benennt einen Druck im Lager. Ändert er
sich für denselben Druck, findet Solidon die Buchung von davor nicht mehr —
nach einem Update bei jedem Kunden zugleich (RM-705).

## Ein neues Einstellungsfeld lässt alte Abdrücke stehen

- **Die Felder von 0.5.3 sind eingefroren** (`FINGERPRINT_FIELDS`). Die Menge
  wächst nie; ein Feld daraus wird nicht umbenannt, umgetypt oder anders
  gerundet, ohne den alten Abdruck als Altabdruck mitzuführen.
- **Ein späteres Feld zählt nur, wo es abweichen soll**: eigene Wahl oder
  übernommener Vorschlag (`explicit`), oder ein Wert einer Spule abseits der
  Vorgabe der Dataclass. Als Grundlage fällt es heraus, auch wenn der Wert
  nicht die Vorgabe ist — das Herstellerprofil bringt seinen eigenen (Elegoo:
  `cooling.minimum_speed` 20 statt 10), und unter 0.5.3 nahm der Slicer ihn
  ebenso. `_without_later_fields` tut das für jedes Feld, ohne Liste.
- **Ein neuer Kopfschlüssel in `print_settings_to_data`** braucht eine eigene
  Entscheidung in `prepare`; der Wächter hält bis dahin an.
- **Altabdrücke sind Kandidaten, keine Gleichheit** (`legacy_fingerprints`,
  `_LEGACY_SHAPES`): Sie melden eine frühere Buchung zur Prüfung und buchen
  nie still. Ein Stand, der nur so wiedererkannt wird: 0.5.1 (ohne Brim-,
  Raftabstand und Wahl der Platte). 0.5.0 bleibt unerkannt.
- **Sollwerte von außen**: Ein Abdruck im Test kommt aus einer Codekopie des
  Tags (`git archive`), nie aus dem neuen Code; der Kundenweg liest Projekt
  und Lager, die das alte Programm selbst schrieb
  (`test_filament_usage_fingerprint_history.py`).
