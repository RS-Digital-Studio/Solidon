---
name: hilfsmodul-verstellt-den-suchpfad
description: "tools/run_ui_audit.py setzt beim Import selbst F:\\3D Druck an sys.path[0] — jeder Prüfstand aus einem Worktree misst danach den geteilten Baum, und der eigene Fix sieht wirkungslos aus."
metadata: 
  node_type: memory
  type: project
  originSessionId: 1b79d3f9-e57d-4e8a-ac31-2b25393cae9e
  modified: 2026-09-03T09:40:54.662Z
---

`tools/run_ui_audit.py` trägt in Zeile 43 eine Zeile, die jeden Prüfstand aus
einem eigenen Arbeitsbaum still umlenkt:

```
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
```

Das ist `F:\3D Druck`, und es geschieht **beim Import**. Wer seine Bausteine
von dort holt (`from run_ui_audit import settle, await_result, …`) und
**danach** `app.*` importiert, bekommt `app` aus dem geteilten Baum — gleich
was er vorher in `sys.path` eingetragen hat, und gleich welchen Pfad er dem
Skript als Argument mitgibt.

**Wie es sich anfühlt:** Der eigene Fix greift nicht. Am 03.09.2026 eine halbe
Stunde daran gemessen: Eine Sonde bewies, dass die Bedingung `True` ist, der
Bytecode der geladenen Methode trug den neuen Text, ein isolierter Aufruf der
Bedingung gab `True` — und der Lauf zeigte weiter den alten. Der Verdacht
wanderte über `__pycache__`, eine zweite Definition derselben Methode, ein
falsch abgefragtes Attribut und die Frage, ob `Finding.code` ein Enum ist.
Nichts davon war es.

**Die Probe, die es in zehn Sekunden geklärt hätte**, gehört an den Anfang
jedes Prüfstands, der aus einem Worktree misst:

```
import app.ui.main_window as modul
print("geladen aus:", modul.__file__)
```

**Der Griff dagegen** — erst importieren, dann den Pfad richtigstellen:

```
sys.path.insert(0, r"F:\3D Druck\tools")
from run_ui_audit import await_result, settle, silence_questions, until_quiet
sys.path[:] = [p for p in sys.path if p.rstrip("\\/").lower() != r"f:\3d druck"]
sys.path.insert(0, MEIN_BAUM)
```

**pytest ist nicht betroffen** — es lädt über rootdir und conftest aus dem
Arbeitsverzeichnis. Ein `pytest`-Lauf im Worktree misst den Worktree, und die
Gegenprobe (Fix zurückgedreht → rot, Fix drin → grün) bewies das auch.
Betroffen ist nur der selbst gebaute Prüfstand.

Die allgemeine Form: **Ein Hilfsmodul, das man importiert, kann den Suchpfad
verstellt haben, bevor die eigene erste Zeile läuft.** Das ist die Schwester
von [[pruefstand-geht-den-weg-der-oberflaeche]] — dort fehlt ein Schritt, den
die Anwendung geht; hier läuft ein Schritt, den man nicht angeordnet hat.
Siehe auch [[messwerkzeug-misst-sich-selbst]] und
[[sonde-im-geteilten-baum]].
