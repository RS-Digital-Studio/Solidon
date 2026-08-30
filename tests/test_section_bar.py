"""Die Schnittleiste unter dem Viewport — Bedienung, nicht Geometrie.

**Eigene Datei, und die AGENTS-Frage ist geprüft:** `tests/test_section.py`
prüft den Schnitt als Geometrie im Kern und kennt kein Qt; die Leiste steht
sonst nur in `tests/test_ui.py`, und die hält eine andere Sitzung. Hier steht,
was der Kunde an der Leiste tut.
"""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication

from app.ui.section_bar import SectionBar


@pytest.fixture
def bar(qt_app: QApplication) -> SectionBar:
    return SectionBar()


def test_both_number_fields_wait_for_the_typing_to_finish(bar: SectionBar) -> None:
    """Zwei gleichartige Felder dürfen sich nicht verschieden verhalten.

    Das Positionsfeld wartet das Tippen ab, das Dickenfeld tat es nicht: Wer
    „10" zu „30" änderte, schnitt erst mit 3 mm und dann mit 30 — zwei Schnitte
    für eine Eingabe, und der erste mit einer Dicke, die niemand wollte. Wer
    die Zehn löschte, stand kurz unter dem Mindestwert und sah das Feld auf
    0,1 springen (Roberts Fehlerbericht, 30.08.2026).
    """
    assert not bar.readout.keyboardTracking(), "das Positionsfeld wartet ab"
    assert not bar.thickness.keyboardTracking(), (
        "das Dickenfeld sendete bei jedem Tastendruck — zwei Schnitte je Eingabe"
    )


def test_the_slice_thickness_reaches_the_signal(bar: SectionBar) -> None:
    """Was der Kunde einstellt, muss bei der Ansicht ankommen.

    Der Weg ist Achse wählen, *Scheibe* anhaken, Dicke setzen — und erst am
    Ende steht die Zahl im Signal. Ein Feld, das seinen Wert behält, ihn aber
    nicht weitergibt, sähe von außen genauso aus wie ein kaputter Schnitt.
    """
    gesendet: list[float | None] = []
    bar.sectionChanged.connect(lambda _plane, thickness: gesendet.append(thickness))

    def settle() -> None:
        """Den Schnitt losschicken, ohne 120 ms zu warten.

        `_emit` entprellt: Ein Schieber sendet bei jedem Pixel, und ein Schnitt
        ist eine boolesche Operation je Körper. Der Test drückt den Timer
        vorzeitig ab, statt zu schlafen — gewartet würde sonst je Schritt.
        """
        bar._pending.stop()
        bar._settled()

    bar.axis.setCurrentIndex(3)  # Schnitt Z
    settle()
    assert gesendet and gesendet[-1] is None, "ohne Scheibe keine Dicke"

    bar.as_slice.setChecked(True)
    settle()
    assert gesendet[-1] == pytest.approx(10.0), "die Vorgabe reist mit"

    bar.thickness.set_value_mm(3.0)
    settle()
    assert gesendet[-1] == pytest.approx(3.0), "die eingestellte Dicke kam nicht an"


def test_the_thickness_field_opens_only_with_the_checkbox(bar: SectionBar) -> None:
    """Ein Feld, das nichts bewirkt, gehört gesperrt (§2.4).

    Ohne Achse ist alles zu, mit Achse öffnet sich die Wahl, und die Dicke
    erst mit dem Haken — sonst stellte jemand eine Zahl ein, die nirgends
    ankommt.
    """
    assert not bar.position.isEnabled()
    assert not bar.as_slice.isEnabled()
    assert not bar.thickness.isEnabled()

    bar.axis.setCurrentIndex(3)
    assert bar.position.isEnabled()
    assert bar.as_slice.isEnabled()
    assert not bar.thickness.isEnabled(), "ohne Haken bewirkt die Dicke nichts"

    bar.as_slice.setChecked(True)
    assert bar.thickness.isEnabled()


def test_choosing_an_axis_lands_the_cut_inside_the_part(bar: SectionBar) -> None:
    """Der Schnitt öffnet nicht auf ein leeres Bild.

    Das Fenster stellt die Leiste beim Öffnen auf Z — „weil eine Schicht so
    liegt, wie der Drucker sie legt". Der Regler stand dabei auf 0,0, und weil
    alles oberhalb der Ebene wegfällt, sah der Kunde einen **leeren Bauraum**.
    Wer nicht weiß, was ein Schnitt tut, hält das für einen Fehler, den er
    selbst gemacht hat — und das ist genau die Zielgruppe, für die der Knopf
    gedacht ist.

    ``_apply_range`` wollte das verhindern und tat es nicht: Es zentrierte nur,
    wenn der alte Wert **außerhalb** der neuen Spanne lag. Ein Teil auf dem
    Bett hat z von 0 bis Höhe, und 0,0 liegt darin immer. Der Kommentar über
    der Zeile beschrieb die richtige Regel bereits vollständig; die Bedingung
    darunter machte sie wirkungslos.

    Geprüft wird die **Lage der Ebene**, nicht die Zahl im Feld: Was der Kunde
    sieht, entsteht aus ``plane()``.
    """
    bar.set_ranges({"x": (0.0, 80.0), "y": (0.0, 50.0), "z": (0.0, 8.0)})

    # Genau der Griff, den das Fenster beim Öffnen tut.
    bar.axis.setCurrentIndex(3)
    QApplication.processEvents()

    plane = bar.plane()
    assert plane is not None, "an axis was chosen, so there is a plane"
    assert 0.0 < plane.position < 8.0, (
        f"the cut opens outside the part at {plane.position} — the viewport stays empty"
    )


def test_a_new_range_for_the_same_axis_leaves_the_cut_where_it_is(bar: SectionBar) -> None:
    """Die Gegenrichtung: Nicht jede neue Spanne ist ein Achswechsel.

    ``set_ranges`` kommt auch, wenn sich das Teil ändert — dort gehört der
    eingestellte Wert noch zur richtigen Achse, und ihn dann in die Mitte zu
    ziehen wäre eine Bewegung ohne Auftrag. Ohne diesen Test wäre „beim
    Achswechsel immer zentrieren" mit „immer zentrieren" zu verwechseln, und
    der Regler spränge dem Kunden unter der Hand weg.
    """
    bar.set_ranges({"z": (0.0, 8.0)})
    bar.axis.setCurrentIndex(3)
    QApplication.processEvents()

    bar.readout.set_value_mm(2.0)
    QApplication.processEvents()

    bar.set_ranges({"z": (0.0, 10.0)})
    QApplication.processEvents()

    plane = bar.plane()
    assert plane is not None
    assert abs(plane.position - 2.0) < 0.01, (
        f"a new range for the same axis moved the cut to {plane.position}"
    )
