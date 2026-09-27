# `data/` — die Wissensbasis

Acht TOML-Dateien und die Lizenztexte. **Hier stehen die Zahlen**, die im
Code nichts zu suchen haben — und ein erzeugter Nachweis.

| Datei | Inhalt | Wer liest |
|---|---|---|
| `printers.toml` | Druckerprofile, FDM und Resin nach Bauraum (`technology = "resin"`: Pixelgröße und Mindestwand statt Düse und Bahn). Aus dem Standardprozess und dem allgemeinen PLA des Herstellers: `travel_speed`, `speed_*`, die Beschleunigungen, `flow_factor`, `overhang_limit` (Stützgrenze gegen die Senkrechte), `first_layer_line_factor` (erste Bahnbreite als Vielfaches der Düse, für jeden Slicer über `print_settings.resolve`); nur für Cura `first_layer_acceleration` und `overhang_speed_factors` (Überhangstufen in Prozent der Außenwand) sowie `cura_definition`, aus der die Konsolenübergabe Start- und Endcode nimmt | `profiles.py` |
| `materials.toml` | Materialprofile — **die Toleranzen** hinter `auto:<material>`; `resin` ist das Harz (`technology = "resin"`) | `profiles.py` |
| `print_settings.toml` | Druckeinstellungen je Stufe | `print_settings.py` |
| `standards.toml` | Normteilmaße (§24.2) | `standards.py` |
| `rules.toml` | Die Regelsammlung des Agenten (§39) | `rules.py` |
| `part_ranges.toml` | Der Bereichsnachweis je mitgeliefertem Baustein (§24.3) — **erzeugt** von `tools/check_part_ranges.py`, nicht von Hand | `parts/range_proof.py`, Katalog |
| `licences.toml` | Die Freigabeliste der Abhängigkeiten (§36) | `licences.py` |
| `third_party_licenses.toml` | Feste Lizenzquellen, Hashes und Paket-/Laufzeitzuordnung einschließlich reiner Schriftbeilagen (§36) | `tools/make_licence_notices.py` |
| `third_party_licenses/` | Vollständige Lizenztexte; `README.md` beschreibt die Release-Lizenzakte | Beilagengenerator und Paketbau |

## Warum das keine Konstanten sind

Weil sie sich ändern, ohne dass der Code sich ändert — und weil eine Toleranz
im Baustein ein Fehler ist (Regel 7).

## Zwei Dateien haben Folgen über sich hinaus

- **`rules.toml`** ändert das Verhalten des Agenten. Eine Änderung wird
  gemessen: Agenten-Suite vorher und nachher, Version erhöhen, und bei
  schlechterer Quote zurücknehmen — nicht „trotzdem behalten".
- **`licences.toml`** ist die Freigabeliste. Eine neue Abhängigkeit wird
  **hier** eingetragen, bevor sie eingebaut wird. Regel 15 schließt GPL aus;
  das dort ausdrücklich genannte GCC-Laufzeitpaar wird vollständig über
  `allowed_with` geprüft. Beliebige Linking-Ausnahmen genügen nicht.
  `tests/test_licences.py` prüft erlaubte und verbotene Ausdrücke.
