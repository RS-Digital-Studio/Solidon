---
name: ocp-paketattribut-ist-nicht-das-modul
description: "monkeypatch an `from OCP import X` erreicht den Kern und bleibt nach dem Test stehen — OCP.X ist ein Stub-Paket, das Werte aus dem Paketattribut zwischenspeichert; immer `import OCP.X as X` patchen"
metadata: 
  node_type: memory
  type: project
  originSessionId: f56e0441-974f-4150-ac77-8e36658dc05b
  modified: 2026-09-20T13:18:38.336Z
---

`OCP/__init__.py` macht `from OCP.OCP import *`; jedes Untermodul liegt in
`sys.modules` als `OCP.OCP.ShapeAnalysis`, und daneben gibt es ein
**Stub-Paket** `OCP/ShapeAnalysis/__init__.py` (`from ..OCP.ShapeAnalysis
import *`), das `from OCP.ShapeAnalysis import …` bedient. Beide sind
verschiedene Modulobjekte. Ein `monkeypatch.setattr(ShapeAnalysis, …)` nach
`from OCP import ShapeAnalysis` patcht das Paketattribut; der Kern
(`brep/canonical.py`, `brep/edit.py`) importiert aus dem Stub. Der Stub
zeigt den Patch beim ersten Zugriff (er holt den Wert vom Paketattribut) und
**behält ihn nach `undo`**, weil das Zurücksetzen nur das Paketattribut trifft.

**Why:** 20.09.2026, P1.4c.2: 14 rote NURBS-Fälle in drei B-Rep-Dateien, alle
auf Worker gw3, zweimal deterministisch, einzeln grün, am HEAD grün. Ursache
war `test_narrow_nurbs_bulge_cannot_hide_behind_a_sphere_candidate`, das
`ShapeAnalysis_CanonicalRecognition` am Paketattribut patchte; durch 37 neue
Tests rutschte es in xdists Anfangsportion vor die NURBS-Tests. Gefunden über
`--collect-only`, die xdist-Verteilregel (`items//nodes//4` je Anfangsportion)
und ein Plugin, das nur eine Kennungsliste fährt — ohne xdist blieb der
Sequenzlauf grün, weil ein `ResourceWarning` meines Plugins den Leckverursacher
selbst hatte ausfallen lassen.

**How to apply:** In Tests nie `from OCP import X` zum Patchen; immer
`import OCP.X as X` und dort setzen. Bei einem Tor, das auf einem Worker rot
und einzeln grün ist: `--collect-only` mit denselben `--ignore`, die
Anfangsportion des Workers berechnen, mit `-n 1` nachfahren, dann halbieren.
Siehe [[pruefstand-misst-seine-nachstellung]] und
[[eigener-messfehler-widerlegt-den-befund-nicht]].
