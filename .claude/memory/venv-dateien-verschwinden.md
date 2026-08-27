---
name: venv-dateien-verschwinden
description: "Aus der .venv verschwinden einzelne große Binärdateien; RECORD sagt in Sekunden, welche — und ob überhaupt eine fehlt."
metadata: 
  node_type: memory
  type: project
  originSessionId: 0586fccf-dc29-45c2-9579-8a1d8f46f0b5
  modified: 2026-08-24T17:25:54.717Z
---

Am 24.08.2026 fiel die `.venv` mitten in einer Sitzung aus. Das Bild war
verwirrend, weil es aussah wie ein Codefehler: `import pyvista` starb mit
`ModuleNotFoundError: No module named '08ae81f72d5a2b5fa9e0__mypyc'`, und
damit fielen sechs Tests in `test_viewport_decisions.py` und alles, was einen
Viewport baut. Der Grund lag nicht bei pyvista: `pyvista/typing/mypy_plugin.py`
zieht per `find_spec('mypy')` das Plugin, und **mypy** selbst war kaputt.

**Der Griff, der es in Sekunden klärt, ist der Abgleich gegen `RECORD`.** Jedes
dist-info führt jede Datei, die zur Installation gehört:

```python
import csv, pathlib

sp = pathlib.Path(".venv/Lib/site-packages")
rec = sp / "mypy-2.3.0.dist-info" / "RECORD"
fehlt = [r[0] for r in csv.reader(rec.open(encoding="utf-8")) if r and not (sp / r[0]).exists()]
```

Ergebnis war **eine** Datei von hunderten:
`08ae81f72d5a2b5fa9e0__mypyc.cp313-win_amd64.pyd`, 20 MB. Behoben mit
`pip install --force-reinstall --no-deps mypy==2.3.0`.

Zwei Dinge, die man daraus mitnimmt:

- **Große einzelne Binärdateien verschwinden, ganze Pakete eher nicht.** Der
  Verdacht ist der Virenscanner — während desselben Laufs stand ein Fenster
  „Scan wird ausgeführt …" auf dem Schirm, und eine 20-MB-`.pyd` ist ein
  klassischer Fehlalarm. Wer den Ausfall für einen Codefehler hält, sucht
  stundenlang am falschen Ende.
- **`tools/check_env.py` fängt das nicht.** Es prüft die Versionen der
  Pakete, die installiert **sind**, gegen `constraints.txt` — es meldete
  „Die Umgebung entspricht constraints.txt", während OCP gar nicht mehr
  installiert war.

**OCP ist derselbe Tag, aber ein anderer Schaden, und ein schlimmerer.**
`pip list` kannte `cadquery-ocp-novtk` nicht mehr, es gab kein dist-info, und
der Ordner `cadquery_ocp_novtk.libs`, den der delvewheel-Patch in
`OCP/__init__.py` über `os.add_dll_directory` sucht, fehlte. Übrig war die
verwaiste `OCP/OCP.cp313-win_amd64.pyd` (93 MB). Das ist schlechter als ein
sauberes Fehlen: Weil der Ordner noch daliegt, meldet der B-Rep-Kern sich
nicht ab, sondern `tests/test_brep.py` bricht beim **Sammeln** ab (Exit 2) und
reißt den ganzen `-m performance`-Lauf mit. Wer nur weiterkommen will, fährt
ihn mit `--ignore=tests/test_brep.py`; die Reparatur ist
`pip install --force-reinstall --no-deps cadquery-ocp-novtk==7.9.3.1.1` — am
24.08.2026 gefahren, **46 MB** und keine 300, wie der 93-MB-Ordner vermuten
lässt. Danach `import OCP` (7.9.3.1), BRepPrimAPI und die 95 Tests aus
`test_brep.py` und `test_operation_ui.py` wieder grün.

Siehe auch [[lokale-umgebung-python-version]] und
[[leistungstests-fremdlast]].
