"""Aufeinanderfolgende gleichartige Züge werden ein Verlaufsschritt (§15.5).

Wer ein Teil an seinen Platz schiebt, zieht selten einmal: ziehen, nachsehen,
nachziehen. Bisher stand jeder Zug einzeln im Verlauf, für eine einzige
Absicht — und ein Strg+Z nahm ein Drittel zurück.

Gebündelt wird **eng**, und die Gegenproben sind hier wichtiger als die
Zusagen: Zwei Drehungen um verschiedene Achsen lassen sich nicht zu einer
zusammenfassen, und wer es doch tut, baut einen stillen Geometriefehler, den
erst der Druck zeigt. Bündeln ist deshalb **opt-in je Operation** — wer keine
Kumulationsregel hat, bekommt einen eigenen Schritt.
"""

from __future__ import annotations

import pytest

from app.core.bootstrap import load_operations
from app.core.scene import bundling
from app.core.scene.history import History, OperationDraft
from app.core.scene.project import new_project


@pytest.fixture
def history() -> History:
    load_operations()
    # Über new_project, nicht über Document(): Ein Dokument von Hand
    # zusammenzusetzen hieße, Formatversion und Anwendungsversion selbst zu
    # setzen — und dann prüft der Test einen Stand, den kein Kunde hat.
    return History(new_project("centauri-carbon-2", "petg").document)


def _box(history: History) -> str:
    """Ein Quader als Ausgangslage — über den Stapel, wie ein Kunde ihn anlegt."""
    history.apply(
        "Kasten",
        [
            OperationDraft(
                op="create_box",
                inputs=(),
                params={"width": 10.0, "depth": 10.0, "height": 10.0},
            )
        ],
    )
    return history.document.ops[-1].outputs[0]


def _shift(history: History, target: str, dx: float, *, bundle: bool = True) -> None:
    history.apply(
        "Direkt bewegt",
        [OperationDraft(op="translate_object", inputs=(target,), params={"dx": dx})],
        bundle=bundle,
    )


def test_two_shifts_in_a_row_become_one_step(history: History) -> None:
    """Zweimal geschoben ist einmal geschoben — und die Summe stimmt.

    Gemessen wird an **beidem**: an der Zahl der Schritte und am Wert. Nur die
    Schritte zu zählen ließe offen, ob der zweite Zug überhaupt angekommen
    ist; nur den Wert zu prüfen ließe offen, ob er zwei Einträge kostete.
    """
    target = _box(history)
    vorher = len(history.document.transactions)

    _shift(history, target, 3.0)
    _shift(history, target, 4.0)

    assert len(history.document.transactions) == vorher + 1, (
        "zwei aufeinanderfolgende Züge haben zwei Schritte erzeugt — "
        f"{[one.title for one in history.document.transactions]}"
    )
    assert history.document.ops[-1].params["dx"] == pytest.approx(7.0), (
        f"die Summe der Züge fehlt: {history.document.ops[-1].params}"
    )


def test_one_undo_takes_the_whole_bundle(history: History) -> None:
    """Und ein Strg+Z nimmt das Bündel, nicht seinen letzten Zug.

    Das ist die eigentliche Zusage. Zwei Schritte für eine Handlung heißen:
    Der Kunde nimmt zurück, sieht das Teil auf halbem Weg stehen und weiß
    nicht, was er da halb rückgängig gemacht hat.
    """
    target = _box(history)
    vorher = len(history.document.transactions)

    _shift(history, target, 3.0)
    _shift(history, target, 4.0)
    history.undo()

    assert len(history.document.transactions) == vorher, (
        "nach einem Undo steht noch ein Teil des Bündels da: "
        f"{[one.title for one in history.document.transactions]}"
    )


def test_two_turns_about_different_axes_stay_two_steps(history: History) -> None:
    """**Die wichtigste Gegenprobe.** Zwei Achsen sind zwei Schritte.

    Es gibt keine gemeinsame Drehung um X und Y, und der Versuch, eine zu
    bilden, wäre schlimmer als zwei Einträge im Verlauf: Er ergäbe eine Lage,
    die niemand angefragt hat, ohne Fehler und ohne Meldung.
    """
    target = _box(history)
    vorher = len(history.document.transactions)

    for axis in ("x", "y"):
        history.apply(
            "Direkt bewegt",
            [
                OperationDraft(
                    op="rotate_object", inputs=(target,), params={"axis": axis, "angle": 30.0}
                )
            ],
            bundle=True,
        )

    assert len(history.document.transactions) == vorher + 2, (
        "zwei Drehungen um verschiedene Achsen wurden zusammengefasst — "
        "das ergibt eine Lage, die niemand angefragt hat"
    )


def test_two_turns_about_the_same_axis_become_one(history: History) -> None:
    """Um dieselbe Achse dagegen ist es eine Winkelsumme."""
    target = _box(history)
    vorher = len(history.document.transactions)

    for angle in (30.0, 15.0):
        history.apply(
            "Direkt bewegt",
            [
                OperationDraft(
                    op="rotate_object", inputs=(target,), params={"axis": "z", "angle": angle}
                )
            ],
            bundle=True,
        )

    assert len(history.document.transactions) == vorher + 1
    assert history.document.ops[-1].params["angle"] == pytest.approx(45.0)


def test_scaling_does_not_bundle_yet(history: History) -> None:
    """Skalieren bündelt nicht — und das ist eine Entscheidung, kein Versäumnis.

    Multiplikativ wäre es rechenbar. Der Kundenfall ist aber „dreimal
    nachgeschoben", und was hier fehlt, kann jederzeit dazukommen; umgekehrt
    wäre es ein Rückbau. Bündeln ist **opt-in je Operation**, und wer keine
    Regel hat, bekommt einen eigenen Schritt.
    """
    target = _box(history)
    vorher = len(history.document.transactions)

    for factor in (1.5, 1.2):
        history.apply(
            "Direkt bewegt",
            [OperationDraft(op="scale_object", inputs=(target,), params={"factor": factor})],
            bundle=True,
        )

    assert len(history.document.transactions) == vorher + 2
    assert not bundling.bundles("scale_object")


def test_another_operation_between_ends_the_bundle(history: History) -> None:
    """Jede andere Handlung schließt das Bündel.

    Ohne diese Grenze wäre eine ganze Sitzung ein Schritt. Sie braucht keine
    Zeitmessung: Eine andere Operation legt eine andere Transaktion an, und
    die passt beim nächsten Zug nicht mehr.
    """
    target = _box(history)
    _shift(history, target, 3.0)
    history.apply(
        "Auf das Bett setzen",
        [OperationDraft(op="place_on_bed", inputs=(target,))],
    )
    vorher = len(history.document.transactions)

    _shift(history, target, 4.0)

    assert len(history.document.transactions) == vorher + 1, (
        "der Zug nach einer anderen Operation gehört nicht mehr ins alte Bündel"
    )


def test_end_bundle_closes_it_without_an_operation(history: History) -> None:
    """Und ein Werkzeugwechsel auch — der legt keine Transaktion an.

    ``end_bundle`` ist der Weg für Handlungen, die keinen Schritt erzeugen und
    trotzdem eine Zäsur sind. Ohne sie hinge der erste Zug nach dem Wechsel am
    letzten davor.
    """
    target = _box(history)
    _shift(history, target, 3.0)
    vorher = len(history.document.transactions)

    history.end_bundle()
    _shift(history, target, 4.0)

    assert len(history.document.transactions) == vorher + 1, (
        "nach end_bundle muss ein Zug einen eigenen Schritt beginnen"
    )


def test_a_shift_without_the_offer_never_bundles(history: History) -> None:
    """Ohne ``bundle=True`` bleibt alles, wie es war.

    Die Gegenprobe zur ganzen Sache: Ein Dialog, ein Menüweg, der Agent — sie
    alle legen weiter Einzeltransaktionen an, und §15.5 gilt für sie
    unverändert.
    """
    target = _box(history)
    vorher = len(history.document.transactions)

    _shift(history, target, 3.0, bundle=False)
    _shift(history, target, 4.0, bundle=False)

    assert len(history.document.transactions) == vorher + 2
