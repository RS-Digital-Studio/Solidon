---
name: zusage-ueber-die-umgebung
description: "Zwei Tag-Läufe scheiterten an Zusagen über die Umgebung — jeder nur auf einer der drei Plattformen, weil die Zusage auf den anderen zufällig hielt."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 1b79d3f9-e57d-4e8a-ac31-2b25393cae9e
  modified: 2026-09-03T17:45:41.490Z
---

Ein Test, der die Umgebung **voraussetzt** statt sie herzustellen, ist auf
jeder Plattform grün, auf der sie zufällig stimmt — und fällt nur auf der
einen, auf der sie es nicht tut.

Gemessen am 03.09.2026 im Tag-Lauf für 0.3.1, zwei Fälle an einem Abend:

| Fall | rot auf | grün auf, weil |
|---|---|---|
| `assert not animations_enabled()` | **Linux** | macOS und Windows setzen `QT_QPA_PLATFORM=offscreen`, Linux fährt Xvfb (`build.yml:194`, `:214`) |
| `THIRD-PARTY-NOTICES.md` nennt 0.3.0 | **Windows** | der Lizenztest überspringt sich auf den anderen beiden absichtlich |

Der erste war meiner: Die Zusicherung sollte verhindern, dass der Test gegen
einen leeren Zweig läuft — richtig gedacht, aber sie *verlangte* offscreen,
statt den Zustand zu **setzen**. Der Schalter, den auch ein Kunde hat
(`SOLIDON3D_MOTION=aus`), greift überall:

    QT_QPA_PLATFORM   ohne Schalter   mit "aus"
    offscreen         False           False
    xcb               True            False
    windows           True            False

**Why:** Eine Zusicherung, die eine Eigenschaft der Testumgebung ausnutzt,
sieht aus wie eine Zusicherung über die Sache. Sie hält, solange alle
Maschinen dieselbe Eigenschaft haben — und in dem Moment, in dem eine es
nicht tut, meldet sie einen Fehler, der keiner ist. Beide Fälle waren
monatelang unauffällig.

**How to apply:** Bei einer Zusicherung über den Zustand fragen: *Stelle ich
ihn her oder setze ich ihn voraus?* Herstellen heißt, den Weg zu nehmen, den
auch ein Kunde hätte — einen Schalter, eine Einstellung, ein `monkeypatch`.
Voraussetzen heißt, sich auf `conftest.py`, die Plattform oder eine
CI-Variable zu verlassen.

**Und der Satz, der über beide Fälle hinausgeht** (von 3d-druck-81): *Ein Bau
auf einer Plattform hätte keinen von beiden gefunden.* Wer die
Plattformmatrix für Redundanz hält, irrt sich — sie ist die einzige Stelle,
an der solche Zusagen auffallen. Verwandt: [[mypy-prueft-die-laufende-plattform]],
[[messung-traegt-nur-am-ort-ihrer-messung]].
