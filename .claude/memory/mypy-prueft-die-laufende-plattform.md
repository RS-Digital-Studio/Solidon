---
name: mypy-prueft-die-laufende-plattform
description: "Ohne --platform prüft mypy die Plattform, auf der es läuft — Windows-Tor und Linux-CI sehen verschiedene Fehler, und beide können grün sein, während der andere rot ist."
metadata: 
  node_type: memory
  type: project
  originSessionId: d52f0866-6a6b-49d3-a8c5-73c0be546ada
  modified: 2026-08-27T15:40:27.596Z
---

`pyproject.toml` setzt keine `platform`-Einstellung für mypy. Also prüft jede
Maschine ihre eigene: die drei Arbeitsrechner Windows, die CI Linux.

**Beide Richtungen sind möglich, und eine ist am 27.08.2026 eingetreten.**
`ca18e5a8` brachte in `export/slicer_profiles.py` eine Kette:

```python
if sys.platform == "win32":
    return os.environ.get("APPDATA", "")
if sys.platform == "darwin":          # <- Zeile 127
    ...
```

Auf Windows weiß mypy, dass der erste Zweig immer greift, und meldet den
zweiten als `Statement is unreachable`. Gemessen am selben Stand:

| Lauf | Ergebnis |
|---|---|
| `mypy` (laufende Plattform = Windows) | 1 Fehler |
| `mypy --platform linux` | Success, 223 Dateien |

**Why:** Ein grüner CI-Lauf ist kein Beleg dafür, dass das lokale Tor grün
ist — und umgekehrt. Wer „bei mir läuft es" oder „die CI ist grün" als
Zusicherung nimmt, hat die Plattform nicht mitgedacht. Dieselbe Familie wie
[[lokale-umgebung-python-version]], nur eine Ebene tiefer: Dort ist es die
Version, hier das Betriebssystem.

**How to apply:**

- **Plattformzweige sind ein Verdachtsfall.** Wer `sys.platform` in einer
  Kette abfragt, prüft danach beide Seiten:
  `mypy` und `mypy --platform linux`.
- **Ein Fehler, den nur eine Plattform sieht, rutscht durch die CI.** Er
  blockiert dann jede lokale Sitzung, während der Bau grün meldet.
- **Beim Melden die Plattform dazusagen** — sonst sucht die Gegenseite einen
  Fehler, den ihr Lauf nicht zeigt.
