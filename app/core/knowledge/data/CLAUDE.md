# `data/` — die Wissensbasis

Sieben TOML-Dateien und die Lizenztexte. **Hier stehen die Zahlen**, die im
Code nichts zu suchen haben.

| Datei | Inhalt | Wer liest |
|---|---|---|
| `printers.toml` | Druckerprofile | `profiles.py` |
| `materials.toml` | Materialprofile — **die Toleranzen** hinter `auto:<material>` | `profiles.py` |
| `print_settings.toml` | Druckeinstellungen je Stufe | `print_settings.py` |
| `standards.toml` | Normteilmaße (§24.2) | `standards.py` |
| `rules.toml` | Die Regelsammlung des Agenten (§39) | `rules.py` |
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
