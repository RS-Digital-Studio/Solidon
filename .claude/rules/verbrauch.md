---
description: "Verbrauchsbuchung — der Abdruck eines Drucks bleibt über Updates gleich: gespeicherte Eingänge statt Netzbits, was den Einstellungen gehört, Vorabdruck und Altabdrücke, eingefrorene Felder des Vorabdrucks und was den Abdruck trotzdem kippt"
paths:
  - "app/core/filament_usage.py"
  - "app/core/knowledge/filaments.py"
  - "app/core/knowledge/print_fields.py"
  - "app/core/scene/serialise.py"
  - "app/core/scene/migrations.py"
  - "app/core/export/handover.py"
  - "app/core/types.py"
  - "app/ui/print_settings_dialog.py"
  - "app/ui/filament_usage.py"
---

# Regeln für die Verbrauchsbuchung

Der Abdruck (`filament_usage.prepare`) benennt einen Druck im Lager. Ändert er
sich für denselben Druck, findet Solidon die Buchung von davor nicht mehr —
nach einem Update bei jedem Kunden zugleich (RM-705, RM-706).

## Der Abdruck liest, was das Projekt gespeichert hat

- **Wer bucht, gibt die Eingänge mit** (`prepare(..., inputs=StoredInputs)`):
  Export und beide Slicerwege über `StoredInputs.snapshot`. Ohne sie ist der
  Abdruck der über die Netze — nur für Mengen ohne Buchung; die Fenstertests
  in `test_filament_workflow.py` halten den Anschluss.
- **Kein ausgewertetes Netz im Abdruck**: Druckgleich (Bauplan §11.2) darf
  Bits, Dreiecksfolge und Datentyp ändern. Ein Körper heißt nach seinen
  Schritten, ihren gespeicherten Werten, Startwerten, Quellen (Prüfsumme des
  Inhalts) und gelesenen Projektmaßen (`StoredInputs.bodies`); `mesh.slots`
  bleibt draußen, weil es der Dreiecksfolge folgt.
- **Keine Fassung einer Umsetzung** (`cache_version`, Löserstand): Sie steigt
  bei jeder Beschleunigung. Gezählt wird nur, was eine Maßänderung ausweist —
  die Fassung des Bausteins (`PartSpec.version`, `PartChange`).
- **Liest ein Schritt neben seinen Eingängen**, gehört die Lesart in
  `_read_beside` wie in `evaluate._with_nested_context` — sonst tragen zwei
  verschiedene Drucke einen Abdruck.
- **Gespeicherte Antworten zählen als Entscheidung** (`_answers`): Kanten- und
  Merkmalsantworten mit dem Rang des gewählten Kandidaten nach Lage, ohne
  `scope` und Rohkoordinaten — eine gleich beantwortete neue Frage bleibt.
- **Die Einstellungen zählen mit dem, was dem Projekt gehört**
  (`_owned_settings`): Stufe, eigene Wahl und Vorschläge mit Wert, Wahl der
  Platte, eigene Spulenwerte ohne geerbte Felder. Die Grundlage des
  Herstellers zählt nicht — ein Slicer-Update ist kein neuer Druck.
- **Drucker und Material zählen wie im Cache-Schlüssel** (`profile_key` ohne
  Prozesswerte, je Körper sein Material, dazu jedes Material eines
  Schrittfelds): Eine Kalibrierung (§28.3) ändert Spiel und Lochzugabe und ist
  ein anderer Druck. Grob mit Absicht — lieber kippt der Abdruck einmal zu oft.
- **Plattformgleich**: Nur gespeicherte Angaben und Konstanten des Codes, kein
  aufgelöster Ausdruck, Pfade mit `/` getrennt. `PINNED_BOOKING` in
  `test_filament_usage_stored_inputs.py` hält die Bildung fest.

## Frühere Abdrücke

- **Der Vorabdruck ist dieselbe Buchung** (`former_fingerprints`): der Abdruck
  von 0.5.2 bis 0.6.0 über Netze und wirksame Werte. Wer nach Buchungen
  fragt, fragt `UsageRequest.identities`; ein bestehender Vorgang bucht mit
  seinem eigenen Abdruck nach (`_booking_fingerprint`).
- **Ändert sich die Bildung** (`STORED_INPUTS`), wird der alte Abdruck zum
  Vorabdruck — nie still ersetzen.
- **Altabdrücke sind Kandidaten, keine Gleichheit** (`legacy_fingerprints`,
  `_LEGACY_SHAPES`): Sie melden eine frühere Buchung zur Prüfung und buchen
  nie still. So wiedererkannt wird 0.5.1; 0.5.0 bleibt unerkannt.
- **Sollwerte von außen**: Ein Vor- oder Altabdruck im Test kommt aus einer
  Codekopie des Tags (`git archive`), nie aus dem neuen Code; der Kundenweg
  liest Projekt und Lager, die das alte Programm selbst schrieb
  (`test_filament_usage_fingerprint_history.py`).

## Der Vorabdruck rechnet wie 0.6.0

- **Die Felder von 0.5.3 sind eingefroren** (`FINGERPRINT_FIELDS`). Die Menge
  wächst nie; ein Feld daraus wird nicht umbenannt, umgetypt oder anders
  gerundet.
- **Ein späteres Feld zählt dort nur, wo es abweichen soll**: eigene Wahl oder
  übernommener Vorschlag, oder ein Wert einer Spule, der vom Wert ohne die
  Spule abweicht (`_without_later_fields`, dieselbe Frage wie
  `handover._for_the_slot`, ohne Slicer gerechnet).
- **Ein Feld, das die Datei einer Spule nicht kennt, übersteuert sie nicht**
  (`SlotOverride.inherited`, RM-707): Es folgt dem Wert ohne Spule, wird nicht
  geschrieben und bleibt so über Speichern und Öffnen. Wer eine Spulengruppe
  neu baut oder anzeigt, geht über `handover.override_section`, trägt
  `inherited` mit und behält den Rohwert geerbter Felder; ein gesetzter Pfad
  fällt heraus (`with_slot_advice`).
- **Ein neuer Kopfschlüssel in `print_settings_to_data`** braucht eine eigene
  Entscheidung in `prepare`; der Wächter hält bis dahin an.

## Was den Abdruck trotzdem ändert

- **Eine Migration, die gespeicherte Schrittwerte umschreibt**, ändert den
  Abdruck jedes Körpers dahinter. Wer so migriert, misst die Wiedererkennung
  am Kundenweg und nennt den Bruch im Archiv.
- **Eine Maßänderung eines Bausteins** (`PartChange`) und ein geänderter
  eigener Baustein: gewollt, es ist ein anderer Druck.
- **Eine neue Lesart am Register** (`reads_other_bodies`, ein Schalter mit
  `reads_scene`) ändert den Abdruck der Schritte, die sie tragen.
- **Der Vorabdruck** kippt weiter mit jeder Bitänderung, Grundlage und jedem
  Slicer-Update — Buchungen aus 0.6.0 und früher bleiben nur so lange erkannt.
