# `data/` — die Wissensbasis

Sechs TOML-Dateien. **Hier stehen die Zahlen**, die im Code nichts zu suchen
haben.

| Datei | Inhalt | Wer liest |
|---|---|---|
| `printers.toml` | Druckerprofile | `profiles.py` |
| `materials.toml` | Materialprofile — **die Toleranzen** hinter `auto:<material>` | `profiles.py` |
| `print_settings.toml` | Druckeinstellungen je Stufe | `print_settings.py` |
| `standards.toml` | Normteilmaße (§24.2) | `standards.py` |
| `rules.toml` | Die Regelsammlung des Agenten (§39) | `rules.py` |
| `licences.toml` | Die Freigabeliste der Abhängigkeiten (§36) | `licences.py` |

## Warum das keine Konstanten sind

Weil sie sich ändern, ohne dass der Code sich ändert — und weil eine Toleranz
im Baustein ein Fehler ist (Regel 7).

## Zwei Dateien haben Folgen über sich hinaus

- **`rules.toml`** ändert das Verhalten des Agenten. Eine Änderung wird
  gemessen: Agenten-Suite vorher und nachher, Version erhöhen, und bei
  schlechterer Quote zurücknehmen — nicht „trotzdem behalten".
- **`licences.toml`** ist die Freigabeliste. Eine neue Abhängigkeit wird
  **hier** eingetragen, bevor sie eingebaut wird. GPL kommt nicht hinein
  (Regel 15), `tests/test_licences.py` hält dagegen.
