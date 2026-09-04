"""Was ein gedrucktes Gewinde in den Objektbaum schreibt — und was nicht (§21.1).

Ein Gewinde entsteht in einem Baustein und meldet sich selbst als Merkmal
``thread``. Die Erkennung sieht diese Art nicht; sie sieht eine Wendel und
passt darauf ein, was sie kennt. Alles, was sie dabei findet, steht **neben**
dem Gewinde im Baum, und nichts davon existiert im Teil.

Der Anlass ist ein Kunden-Screenshot vom 04.09.2026: ein M6-Bolzen auf einer
Platte 60 × 40 × 6, im Baum als „Zapfen · Ø 5,79 mm". Nachgestellt mit Spiel
0,20 und Länge 14,99 stimmen Höhe (20,99 mm), Volumen (14,7 cm³) und der
Zapfen (Ø 5,79) mit dem Bild überein.

**Was diese Übereinstimmung wert ist, und was nicht.** Länge und Spiel sind aus
Höhe und Durchmesser zurückgerechnet — zwei freie Größen gegen zwei
Beobachtungen, das Volumen als schwache Bestätigung daneben. Es ist also *eine*
Lage, die sein Bild erklärt, und nicht der Beweis, dass es seine war. Der
Befund hängt nicht daran: Die erfundenen Merkmale entstehen über die ganze
Größentabelle, auf hier erzeugten und nachweislich sauberen Netzen, ganz ohne
seine Datei.

Geprüft wird über die **Auswertung** und nicht über ``detect``: Was der Kunde
im Baum liest, ist das Ergebnis von Provenienz und Erkennung zusammen, und
genau dort wird die Zusage eingelöst.
"""

from __future__ import annotations

import pytest

from app.core.bootstrap import load_operations
from app.core.knowledge import profiles
from app.core.scene import History, OperationDraft, evaluate
from app.core.scene.project import ProjectSources, new_project
from app.core.types import Feature

#: Arten, die die Erkennung an einer Wendel erfindet. Eine Platte mit einem
#: aufgesetzten Gewinde hat keine davon: kein Loch, keinen Zapfen, keinen
#: Kegel, keine Kugel, keinen Ring.
INVENTED = ("hole", "pin", "cone", "sphere", "torus", "fillet")


def _with_thread(
    size: str,
    length: float,
    *,
    play: float | None = None,
    width: float = 60.0,
    depth: float = 40.0,
    height: float = 6.0,
) -> dict[str, Feature]:
    """Eine Platte mit einem aufgesetzten Gewindebolzen, ausgewertet.

    Dieselbe Kette wie in der Anwendung — Verlauf, Auswertung, Szene — weil
    die Unterdrückung der Phantome dort sitzt, wo erzeugte und erkannte
    Merkmale zusammenkommen, und nicht in der Einpassung.
    """
    load_operations()
    project = new_project("centauri-carbon-2", "petg")
    params: dict[str, object] = {
        "size": size,
        "length": length,
        "internal": False,
        "z": height,
    }
    if play is not None:
        params["play"] = play
    History(project.document).apply(
        "Gewinde",
        [
            OperationDraft(
                op="create_box",
                params={"width": width, "depth": depth, "height": height},
            ),
            OperationDraft(op="insert_printed_thread", inputs=("obj_1",), params=params),
        ],
    )
    result = evaluate(
        project.document,
        profiles.make_profile("centauri-carbon-2", "petg"),
        sources=ProjectSources(project),
    )
    entry = next(iter(result.scene.objects.values()))
    return dict(entry.features)


def _invented(features: dict[str, Feature]) -> list[str]:
    """Die Einträge, die der Kunde im Baum liest und nicht erklären kann."""
    return sorted(
        f"{name}: {feature.kind} Ø{feature.params.get('diameter', '?')}"
        for name, feature in features.items()
        if feature.kind in INVENTED
    )


@pytest.mark.parametrize("size", ["M3", "M4", "M5", "M6", "M8"])
@pytest.mark.parametrize("length", [8.0, 15.0])
def test_no_size_of_thread_invents_a_feature(size: str, length: float) -> None:
    """Über die ganze Größentabelle steht neben dem Gewinde nichts.

    **Der bestehende Test traf die eine Größe, bei der es ohnehin ging.**
    ``test_a_thread_is_not_a_stack_of_eight_pins`` prüft M6 bei Länge 12 und
    verbietet dort ``pin`` — und genau dort greift der Gangfilter, weil die
    Einpassung elf Zylinder liefert, die auf fünf verschmelzen und damit über
    seiner Schranke von drei liegen. M4, M5 und M8 kommen mit **zwei** an,
    rutschen darunter durch und melden zwei Zapfen. Eine Zusage, die an einem
    Punkt geprüft wird, gilt an einem Punkt.

    Und ``pin`` allein reicht nicht: An M6 bleiben zwei Kegel stehen, an M3
    neunzehn Kugeln. Verboten ist deshalb jede erfundene Art, nicht die eine,
    die zuerst auffiel.
    """
    features = _with_thread(size, length)

    assert [f.kind for f in features.values()].count("thread") == 1, (
        f"{size}: das Gewinde selbst muss bleiben — {sorted(features)}"
    )
    assert not _invented(features), f"{size} L{length}: {_invented(features)}"


def test_the_customer_screenshot_has_no_pin() -> None:
    """Alexanders Fall, mit seinen Zahlen (Kunden-Screenshot 04.09.2026).

    Er sah „Zapfen · Ø 5,79 mm" an einem M6-Bolzen und fragte, ob ein
    genaueres Bild helfe. Es half: Höhe 20,99 mm und 14,7 cm³ auf dem Bild,
    20,99 mm und 14,73 cm³ im Nachbau — und in dieser Lage derselbe Zapfen,
    den es nicht gibt.

    Die 14,99 sind kein krummer Wert um seiner selbst willen: Sie sind die
    Länge, bei der die Wendel auf 20,99 mm Gesamthöhe zurückgeschnitten wird.

    Wie belastbar die Nachstellung ist, steht oben im Modul-Docstring — sie
    ist gefittet und nicht bewiesen. Dieser Test hält deshalb nicht fest,
    *dass* es seine Parameter waren, sondern dass diese Lage keinen Zapfen
    mehr meldet.
    """
    features = _with_thread("M6", 14.99, play=0.20)

    pins = [name for name, feature in features.items() if feature.kind == "pin"]
    assert not pins, f"der Gewindekamm ist kein Zapfen: {pins}"
    assert not _invented(features), _invented(features)


def test_a_real_bore_under_a_thread_survives() -> None:
    """Die Gegenprobe: Was koaxial unter dem Bolzen liegt, bleibt.

    Die Unterdrückung darf nicht radial raten. Ein Gewindebolzen auf einer
    Platte, durch die an derselben Achse eine Bohrung geht, ist ein
    gewöhnliches Teil — eine Durchführung mit aufgesetztem Anschluss. Fiele
    die Bohrung mit den Phantomen weg, wäre der Fix teurer als der Fehler:
    Eine Passung, die auf sie zeigt, verlöre ihr Ziel (§21.3).
    """
    load_operations()
    project = new_project("centauri-carbon-2", "petg")
    History(project.document).apply(
        "Bohrung unter dem Bolzen",
        [
            OperationDraft(
                op="create_box",
                params={"width": 60.0, "depth": 40.0, "height": 6.0},
            ),
            # Durch die Platte hindurch, auf derselben Achse wie der Bolzen —
            # also genau dort, wo eine radiale Abgrenzung sie mitnähme.
            OperationDraft(
                op="drill_hole",
                inputs=("obj_1",),
                params={
                    "diameter": 4.0,
                    "depth": 6.0,
                    "x": 0.0,
                    "y": 0.0,
                    "z": 6.0,
                    "axis": "z",
                },
            ),
            OperationDraft(
                op="insert_printed_thread",
                inputs=("obj_1",),
                params={"size": "M6", "length": 12.0, "internal": False, "z": 6.0},
            ),
        ],
    )
    result = evaluate(
        project.document,
        profiles.make_profile("centauri-carbon-2", "petg"),
        sources=ProjectSources(project),
    )
    entry = next(iter(result.scene.objects.values()))
    holes = [
        feature
        for feature in entry.features.values()
        if feature.kind == "hole" and abs(float(feature.params.get("diameter", 0.0)) - 4.0) < 0.3
    ]

    assert [f.kind for f in entry.features.values()].count("thread") == 1, sorted(entry.features)
    assert holes, (
        "die koaxiale Bohrung Ø 4 unter dem Bolzen ist verschwunden: "
        f"{sorted((f.kind, f.params.get('diameter')) for f in entry.features.values())}"
    )


def test_a_cross_hole_through_the_bolt_survives() -> None:
    """Die zweite Gegenprobe, und sie hat den ersten Entwurf widerlegt.

    Ein Splintloch quer durch den Gewindebolzen liegt **vollständig** in der
    Hülle des Gewindes — Achse, Länge und Durchmesser umschließen es. Die erste
    Fassung der Unterdrückung nahm es deshalb mit, und das wäre ein teurerer
    Fehler gewesen als der, den sie behebt: Die Bohrung ist da, der Kunde sieht
    sie, und sein Merkmal dazu wäre verschwunden.

    **Über die Achsrichtung ließ es sich nicht trennen.** Gemessen über 60
    Fälle weicht ein Phantom-Kegel bis zu 72,8 Grad von der Gewindeachse ab,
    die Querbohrung 90 — eine Schwelle dazwischen wäre geraten.

    Getrennt wird an der Schale: Ein Gewinde ist eine Oberfläche zwischen Grund
    und Kamm. Was in der Mitte des Bolzens liegt, gehört nicht dazu.
    """
    load_operations()
    project = new_project("centauri-carbon-2", "petg")
    History(project.document).apply(
        "Splintloch",
        [
            OperationDraft(
                op="create_box",
                params={"width": 60.0, "depth": 40.0, "height": 6.0},
            ),
            OperationDraft(
                op="insert_printed_thread",
                inputs=("obj_1",),
                params={"size": "M8", "length": 16.0, "internal": False, "z": 6.0},
            ),
            # Quer durch den Bolzen, vier Millimeter unter seinem Ende.
            OperationDraft(
                op="drill_hole",
                inputs=("obj_1",),
                params={
                    "diameter": 2.5,
                    "depth": 20.0,
                    "x": 0.0,
                    "y": 20.0,
                    "z": 18.0,
                    "axis": "y",
                },
            ),
        ],
    )
    result = evaluate(
        project.document,
        profiles.make_profile("centauri-carbon-2", "petg"),
        sources=ProjectSources(project),
    )
    entry = next(iter(result.scene.objects.values()))
    quer = [
        feature
        for feature in entry.features.values()
        if feature.kind == "hole" and abs(float(feature.params.get("diameter", 0.0)) - 2.5) < 0.3
    ]

    vorhanden = sorted((f.kind, f.params.get("diameter")) for f in entry.features.values())
    assert quer, (
        f"das Splintloch Ø 2,5 quer durch den Bolzen ist mit den Phantomen weg: {vorhanden}"
    )
    # Und die Phantome desselben Körpers fallen trotzdem.
    assert not [f for f in entry.features.values() if f.kind in ("pin", "sphere")], _invented(
        dict(entry.features)
    )
