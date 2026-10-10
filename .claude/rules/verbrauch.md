---
description: "Verbrauchsbuchung — der Abdruck eines Drucks bleibt über Updates gleich: eingefrorene Felder von 0.5.3, ein neues Einstellungsfeld zählt nur als Abweichung, Spulenwerte, Altabdrücke und was den Abdruck trotzdem kippt"
paths:
  - "app/core/filament_usage.py"
  - "app/core/knowledge/filaments.py"
  - "app/core/knowledge/print_fields.py"
  - "app/core/scene/serialise.py"
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
  übernommener Vorschlag (`explicit`), oder ein Wert einer Spule, der vom Wert
  ohne die Spule abweicht. Als Grundlage fällt es heraus, auch abseits der
  Dataclass-Vorgabe — das Herstellerprofil bringt seinen eigenen (Elegoo:
  `cooling.minimum_speed` 20 statt 10), und unter 0.5.3 nahm der Slicer ihn
  ebenso. `_without_later_fields` tut das für jedes Feld, ohne Liste.
- **Die Spulenklausel ist die Auskunft von `handover._for_the_slot`**: dieselbe
  Frage, derselbe Vergleich, damit Abdruck und Übergabe nie verschieden
  beantworten, ob eine Spule abweicht.
- **Ein Feld, das die Datei einer Spule nicht kennt, übersteuert sie nicht**
  (`SlotOverride.inherited`, RM-707): Es folgt dem Wert ohne Spule, wird nicht
  geschrieben und bleibt so über Speichern und Öffnen. Wer eine Spulengruppe
  neu baut, trägt `inherited` mit oder nimmt einen gesetzten Pfad heraus.
- **Ein neuer Kopfschlüssel in `print_settings_to_data`** braucht eine eigene
  Entscheidung in `prepare`; der Wächter hält bis dahin an.
- **Altabdrücke sind Kandidaten, keine Gleichheit** (`legacy_fingerprints`,
  `_LEGACY_SHAPES`): Sie melden eine frühere Buchung zur Prüfung und buchen
  nie still. So wiedererkannt wird 0.5.1; 0.5.0 bleibt unerkannt.
- **Sollwerte von außen**: Ein Abdruck im Test kommt aus einer Codekopie des
  Tags (`git archive`), nie aus dem neuen Code; der Kundenweg liest Projekt
  und Lager, die das alte Programm selbst schrieb
  (`test_filament_usage_fingerprint_history.py`).

## Was den Abdruck trotzdem ändert

- **Netzbits**: Die Geometrie geht als Prüfsumme der Punkte ein. Jede
  Bausteinänderung und jede druckgleiche Beschleunigung, die Bits eines Netzes
  verschiebt, macht aus einem gebuchten Druck einen neuen — den Umbau auf
  gespeicherte Eingänge trägt RM-706.
- **Eine neue Grundlage eines eingefrorenen Felds**, auch durch Solidon selbst:
  Seit RM-583 rechnet Cura `support.z_gap` in ganzen Schichten, und Fein wie
  Entwurf bekommen einen anderen Abdruck. Wer eine Grundlage ändert, misst die
  Wiedererkennung gegen den letzten Tag und nennt den Bruch im Archiv.
- **Ein Slicer-Update**, das einen Wert eines eingefrorenen Felds ändert, wie
  schon unter 0.5.3.
