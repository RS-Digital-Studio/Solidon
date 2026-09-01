# `data/` — die Wissensbasis

Sieben TOML-Dateien und die Originaltexte der Drittanbieter-Lizenzen. **Hier
stehen die Zahlen**, die im Code nichts zu suchen haben.

| Datei | Inhalt | Wer liest |
|---|---|---|
| `printers.toml` | Druckerprofile | `profiles.py` |
| `materials.toml` | Materialprofile — **die Toleranzen** hinter `auto:<material>` | `profiles.py` |
| `print_settings.toml` | Druckeinstellungen je Stufe | `print_settings.py` |
| `standards.toml` | Normteilmaße (§24.2) | `standards.py` |
| `rules.toml` | Die Regelsammlung des Agenten (§39) | `rules.py` |
| `licences.toml` | Die Freigabeliste der Abhängigkeiten (§36) | `licences.py` |
| `third_party_licenses.toml` | Manifest der tatsächlich ausgelieferten Laufzeitpakete | `licences.py`, `tools/make_licence_notices.py` |
| `third_party_licenses/` | Inhaltstreue Lizenz- und Hinweistexte aus den Paketdistributionen | `tools/make_licence_notices.py` |

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
- **`third_party_licenses.toml` und `third_party_licenses/`** bilden die
  reproduzierbare Quelle für `THIRD-PARTY-NOTICES.md`. Jede Änderung wird mit
  `python tools/make_licence_notices.py` erzeugt und mit `--check` geprüft.
