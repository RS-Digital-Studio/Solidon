"""Die Werkzeugzeile unter der Ansicht — dass kein Werkzeug tot aufgeht.

**Eigene Datei, und zwar für eine Zusage quer über alle Werkzeuge.** Was ein
einzelnes tut, steht bei ihm: der Schnitt in ``test_section_bar.py``, die
Schichten in ``test_analysis_ui.py``, das Trennen in ``test_split_tool.py``.
Hier steht, was für **jedes** gilt — und genau solche Zusagen fehlten, als der
Schnitt auf ein leeres Bild öffnete (V1) und die Schichten ohne Auswahl stumm
blieben (V4). Beide Male war das einzelne Werkzeug geprüft und die Regel
darüber nicht.

**Eine Zusage, und sie gilt der Zukunft, nicht der Vergangenheit.** Wer ein
Werkzeug öffnet, muss etwas sehen, das ihm sagt, was jetzt geht — eine
benutzbare Bedienung oder einen Satz, der den fehlenden Schritt nennt. Ein
Werkzeug, das aufgeht und schweigt, wirkt wie ein Fehler des Kunden.

**Zwei Zusagen mehr standen hier und sind an der Gegenprobe gescheitert.** Der
Auftrag zu dieser Datei nahm an, ein Test über alle Werkzeuge hätte V1 (der
Schnitt öffnet auf ein leeres Bild) und V4 (die Schichten bleiben stumm)
gefangen. Gemessen trifft das nicht zu, und beide Male aus einem Grund, der
sich lohnt aufzuschreiben:

* **V1 ist kein Anschlagsproblem.** „Kein Regler öffnet am Anschlag" klang
  allgemein und war es nicht — bei der Explosion ist die Null der richtige
  Anfang. Eingeschränkt auf den Schnitt blieb der Test dann trotzdem grün: Der
  Regler bekommt einen Rand (``low - margin``), also liegt 0 bei einem Teil von
  0 bis 8 mm nicht am Anschlag, sondern zwischen −1 und 9. Der Fehler war
  „außerhalb des **Teils**", nicht „am Ende des **Reglers**" — und die
  Teilgrenzen kennt nur, wer die Leiste füttert. Geprüft wird das deshalb dort,
  wo es hingehört: ``test_section_bar.py`` misst die Lage über ``plane()``.
* **V4 braucht eine Lage, die diese Datei nicht herstellt** — mehrere Körper,
  keiner gewählt. Sie steht in ``test_analysis_ui.py``, mit dem Hinweisfeld,
  das dafür gebaut wurde.

Was bleibt, ist die eine Zusage oben. Sie hätte keinen der beiden Fälle
gefangen, und sie fängt den nächsten, der eine Leiste ohne Bedienung und ohne
Satz aufmacht. Das ist weniger, als der Auftrag erwartete, und mehr wert als
zwei Zusicherungen, die grün bleiben, wenn man den Fehler wieder einbaut.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QApplication,
    QCheckBox,
    QComboBox,
    QLabel,
    QPushButton,
    QSlider,
)

from app.ui.main_window import MainWindow
from app.ui.session import Session
from app.ui.settings import UiSettings

MESHES = Path(__file__).parent / "data" / "meshes"

#: Die Werkzeuge der Zeile. Von Hand geführt und gegen das Fenster geprüft —
#: ``test_the_list_of_tools_is_complete`` unten hält beides zusammen, damit ein
#: neues Werkzeug nicht stillschweigend ungeprüft bleibt.
TOOLS = ("section", "measure", "transform", "analysis", "layers", "explode", "split")


@pytest.fixture
def window(qt_app: QApplication) -> Iterator[MainWindow]:
    """Ein Fenster mit einem geladenen Teil — die Lage, in der ein Kunde ein
    Werkzeug aufmacht.

    Kein ``close()`` am Ende: Das fragt bei ungesicherten Änderungen modal
    nach, und der Test hängt dann an einem Fenster, das niemand sieht.
    """
    view = MainWindow(Session(), UiSettings())
    view.open_path(MESHES / "plate_holes.stl")
    view.session.wait_for_idle()
    result = view.session.evaluate_now()
    # **Das Teil ist angeklickt.** Ohne das bekommt die Schnittleiste nie ihre
    # Spannen und steht auf der Vorgabe (-50 bis 50, Regler auf 0) — also
    # ausgerechnet in der Mitte, wo nichts auffallen kann. Die Gegenprobe hat
    # das gefangen: V1 zurückgedreht blieb der Test grün, weil er eine Lage
    # prüfte, in der der Fehler gar nicht entstehen konnte.
    view.object_tree.select_object(next(iter(result.scene.objects)))
    view.session.wait_for_idle()
    yield view
    view.wait_for_workers()


def _bar_of(window: MainWindow, key: str) -> object:
    return window.tools._tools[key].bar


def test_the_list_of_tools_is_complete(window: MainWindow) -> None:
    """Was das Fenster anmeldet, steht auch in dieser Datei.

    Ohne diese Zeile prüfte ein neues Werkzeug niemand — die Liste oben altert
    still, und die beiden Zusagen darunter gälten für sechs von sieben.
    """
    assert set(window.tools._tools) == set(TOOLS), (
        f"the strip offers {sorted(window.tools._tools)}, this file checks {sorted(TOOLS)}"
    )


@pytest.mark.parametrize("key", TOOLS)
def test_no_tool_opens_without_saying_anything(window: MainWindow, key: str) -> None:
    """Jedes Werkzeug zeigt beim Öffnen entweder Bedienung oder einen Grund.

    Die Schichten taten weder das eine noch das andere: ein Regler, der sich
    ziehen ließ und nichts bewegte, und der Grund stand als „Keine Auswahl" in
    der Statuszeile am unteren Fensterrand — also nicht dort, wo der Kunde
    gerade hinsieht (V4).

    Geprüft wird an der **Leiste**, nicht am Fenster: Was anderswo steht, mag
    stimmen und erreicht ihn hier nicht.
    """
    window.tools.activate(key)
    QApplication.processEvents()
    bar = _bar_of(window, key)

    usable = [
        widget
        for kind in (QSlider, QComboBox, QPushButton, QCheckBox, QAbstractSpinBox)
        for widget in bar.findChildren(kind)  # type: ignore[attr-defined]
        if widget.isEnabled() and not widget.isHidden()
    ]
    spoken = [
        label.text().strip()
        for label in bar.findChildren(QLabel)  # type: ignore[attr-defined]
        if label.text().strip() and not label.isHidden()
    ]

    assert usable or spoken, (
        f"the {key!r} bar opens with nothing to use and nothing to read — "
        "a tool that says neither what to do nor what is missing looks broken"
    )
