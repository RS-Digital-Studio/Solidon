"""Wo der Renderer der 3D-Ansicht gebaut wird — und ob er hier kann (§18).

Gezeichnet wird mit pygfx über wgpu (Vulkan, DX12, Metal; in einer virtuellen
Maschine WARP beziehungsweise lavapipe, soweit vom System bereitgestellt).
``vtk`` bleibt als kopflose Geometriebibliothek der Bereichsprüfung
(``app/core/knowledge/parts/range_check.py``).

Alles, was einen Renderer baut, geht über :func:`make_renderer` — der
Viewport, seine Bildaufnahme und die Ansichten für den Agenten —, damit ein
Wechsel an genau einer Stelle stattfindet. Ob die Maschine überhaupt einen
wgpu-Adapter hat, fragt :func:`available` **vor** dem Aufbau: Ein Renderer
ohne Adapter stirbt nicht höflich, sondern mit dem Prozess.

**Die Frage wird einmal je Prozess gestellt, und möglichst nicht im
Hauptthread.** Sie kostet Zeit, und zwar viel: gemessen am 14.09.2026 auf
einem Windows-11-Rechner mit RTX 4080 unter Fremdlast **763 ms** im
Hauptthread (Median aus drei Läufen), dazu weitere 668 ms, bis
:func:`make_renderer` steht — zusammen fast anderthalb Sekunden, in denen das
Fenster nicht zeichnet, gegen ein Startbudget von drei Sekunden (§31). Auf
Roberts Maschine waren es im guten Fall 5 bis 7,8 s und unter Last Minuten.
Bis dahin stellte jeder Viewport sie neu, und der Sprachwechsel baut einen
zweiten.

Zwei Dinge ändern das, beide gemessen:

* **Die Antwort bleibt liegen** (:func:`available`). Der zweite Viewport
  fragt nicht mehr.
* **Gefragt wird nebenan.** ``app.ui.app`` startet :func:`probe` beim
  Anwendungsstart in einem Arbeiter, während Einstellungen, Erscheinungsbild
  und Fenster entstehen; :func:`available` findet die Antwort dann vor. Der
  wgpu-Instanzzeiger ist prozessweit, und der Aufwand steckt in seinem
  Aufbau: Nach der Frage im Nebenthread kostete dieselbe Frage im Hauptthread
  noch 376 statt 763 ms, und der Renderer baute und zeichnete unverändert
  (Offscreen-Bild 240 auf 320 auf 3 in allen drei Läufen).

Und sie bekommt eine **Frist**. Eine Frage, die auf einem fremden Treiber
Minuten dauern kann, darf das Fenster nicht so lange halten: Nach
:data:`ADAPTER_TIMEOUT_SECONDS` meldet sich die Ansicht mit dem Satz ab, den
sie für einen fehlenden Adapter ohnehin hat (§27). Das gilt nur, solange ein
anderer Thread die Frage bereits gestellt hat — wo niemand vorgearbeitet hat
(Suite, Kommandozeile), wird wie bisher gewartet, bis die Antwort da ist.
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Final

from app.ui.render.api import Renderer

_log = logging.getLogger(__name__)

#: Wie lange :func:`available` höchstens auf eine **laufende** Adapterfrage
#: wartet, bevor die Ansicht sich abmeldet.
#:
#: Gemessen (14.09.2026, Windows 11, RTX 4080, Fremdlast aus vier Agenten):
#: die erste Frage im Prozess 0,76 bis 1,12 s, jede weitere 0,26 bis 0,35 s.
#: Roberts Maschine meldete im guten Fall 5 bis 7,8 s. Die Frist liegt bei
#: rund dem Zweieinhalbfachen des schlechtesten *guten* Falls — weit genug,
#: dass ein langsamer Treiber seine Ansicht behält, und eng genug, dass ein
#: hängender keine Minuten bekommt.
ADAPTER_TIMEOUT_SECONDS: Final = 20.0

#: Die Antwort für diesen Prozess, sobald sie einmal feststeht.
_answer: bool | None = None
#: Ob gerade jemand fragt. Zwei gleichzeitige Fragen bauen wgpus prozessweite
#: Instanz doppelt auf; die Antwort gilt ohnehin für die ganze Maschine.
_asking = False
_state = threading.Condition()


def _adapter_present() -> bool:
    """Die eigentliche Frage an wgpu. Antwortet mit ja oder nein, nie mit einer Ausnahme."""
    try:
        import wgpu

        adapter = wgpu.gpu.request_adapter_sync(power_preference="high-performance")
    except Exception as problem:  # pragma: no cover - hängt an der Maschine
        _log.info("pygfx steht nicht zur Verfügung: %s", problem)
        return False
    return adapter is not None


def _ask_now() -> bool:
    """Stellt die Frage und weckt jeden, der auf ihre Antwort wartet.

    Der Aufrufer hat ``_asking`` bereits unter der Sperre gesetzt — gefragt
    wird **außerhalb** davon, damit ein Wartender seine Frist zählen kann,
    statt an der Sperre zu hängen.
    """
    global _answer, _asking
    found = _adapter_present()
    with _state:
        if _answer is None:
            _answer = found
        _asking = False
        _state.notify_all()
        return bool(_answer)


def probe() -> bool:
    """Fragt den wgpu-Adapter und merkt sich die Antwort — einmal je Prozess.

    Gedacht für einen Thread neben dem Fensteraufbau (siehe Modul-Docstring).
    Ohne Frist: Wer hier wartet, wartet an einer Stelle, an der niemand
    zusieht. Die Frist gehört zu :func:`available`.
    """
    global _asking
    with _state:
        if _answer is not None:
            return _answer
        if _asking:
            _state.wait_for(lambda: _answer is not None)
            return bool(_answer)
        _asking = True
    return _ask_now()


def available() -> bool:
    """Ob pygfx auf dieser Maschine zeichnen kann: ein wgpu-Adapter ist da.

    Steht die Antwort schon fest, kostet der Aufruf nichts. Läuft die Frage
    gerade in einem anderen Thread, wartet dieser Aufruf höchstens
    :data:`ADAPTER_TIMEOUT_SECONDS` darauf und meldet sich danach mit ``False``
    ab. Fragt niemand, wird hier gefragt — wie bisher und ohne Frist.
    """
    global _asking
    with _state:
        if _answer is not None:
            return _answer
        if _asking:
            if not _state.wait_for(lambda: _answer is not None, ADAPTER_TIMEOUT_SECONDS):
                _log.warning(
                    "Der wgpu-Adapter hat sich in %.0f s nicht gemeldet; die Ansicht bleibt aus.",
                    ADAPTER_TIMEOUT_SECONDS,
                )
                return False
            return bool(_answer)
        _asking = True
    return _ask_now()


def forget() -> None:
    """Vergisst die gemerkte Antwort — für Tests, die beide Lagen fahren."""
    global _answer
    with _state:
        _answer = None


def make_renderer(
    parent: Any = None,
    *,
    offscreen: bool = False,
    size: tuple[int, int] = (640, 480),
) -> Renderer:
    """Der Renderer — mit Qt-Widget unter ``parent`` oder ohne Fenster."""
    from app.ui.render.gfx_renderer import GfxRenderer

    return GfxRenderer(parent, offscreen=offscreen, size=size)
