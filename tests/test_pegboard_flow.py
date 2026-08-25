"""Weg 1 aus Bauplan §2.2, an der Kundenanfrage entlang, die ihn ausgelöst hat.

Ein Kunde lädt ein Modell herunter — einen Halter, einen Behälter, was auch
immer — und will es an eine Lochwand hängen, ohne es nachzukonstruieren. Das
Konzept ``konzepte/konzept-befestigungssysteme-2026-08.md`` beschreibt den Weg
in sieben Schritten; hier steht, was davon der Kern prüfen kann.

**Was hier nicht geprüft wird und warum.** Die Schritte 2 und 3 sind Klicks —
eine Fläche wählen, den Eintrag im Kontextmenü finden. Beides hängt an einem
Fenster, und ein Test, der eines baut, hebt die Abrissquote der ganzen
Testdatei (gemessen am 24.08.2026: von 2 von 9 auf 2 von 3). Dass der
Lochwand-Einhänger im Kontextmenü einer Fläche **steht**, prüft
``test_parts.py`` über ``at_face``; dass das Menü ihn erreichbar zeigt, wurde
am echten Fenster nachgesehen. Was hier bleibt, ist die Kette dazwischen: aus
einer fremden Datei wird ein Körper mit benannten Flächen, und an eine davon
setzt sich der Einhänger.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.bootstrap import load_operations
from app.core.knowledge import profiles, standards
from app.core.scene import History, OperationDraft, evaluate
from app.core.scene.project import ProjectSources, new_project
from app.core.types import Profile, Source

load_operations()

MESHES = Path(__file__).parent / "data" / "meshes"


@pytest.fixture
def profile() -> Profile:
    return profiles.make_profile("centauri-carbon-2", "petg")


def _downloaded(name: str = "bracket_inch.stl", unit: str = "in") -> tuple[object, str]:
    """Ein Projekt mit einem eingelesenen Netz — der Kunde hat es gerade geladen.

    **Die Einheit steht hier, weil ``auto`` sie nicht raten darf.** Der Halter
    ist in Zoll gezeichnet; auf ``auto`` hält die Auswertung an und meldet
    ``AmbiguityError`` — genau das, was Regel 21 verlangt, und für den Kunden
    eine Rückfrage. Was hier als Parameter steht, ist seine Antwort.

    Und es ist mehr als eine Formalie: als Millimeter gelesen misst dasselbe
    Modell **4 × 2 × 0,2 mm** und trägt zwei Flächen. Ein Einhänger von 55 mm
    Breite daran wäre ein grüner Test über einen unsinnigen Fall. In Zoll sind
    es 101,6 × 50,8 × 6,3 mm und sechs Flächen — ein Halter, wie ihn jemand
    herunterlädt.
    """
    project = new_project("centauri-carbon-2", "petg")
    project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path=f"sources/{name}", sha256=""
    )
    project.sources["src_1"] = (MESHES / name).read_bytes()
    History(project.document).apply(
        "Laden", [OperationDraft(op="load", params={"source": "src_1", "unit": unit})]
    )
    return project, "obj_1"


def test_a_model_without_a_unit_asks_instead_of_guessing(profile: Profile) -> None:
    """Schritt 1, und der Fall, in dem er nicht durchläuft (Regel 21).

    Der Halter ist in Zoll gezeichnet, und die Datei sagt es nicht — STL kennt
    keine Einheit. Auf ``auto`` **hält die Auswertung an**, statt eine zu
    wählen: Sie meldet eine Mehrdeutigkeit, und der Kunde entscheidet.

    Der Test steht hier und nicht bei den Ladeoperationen, weil er zu diesem
    Weg gehört: Wer ein fremdes Modell an eine Wand hängen will, trifft diese
    Frage als Erstes, und eine falsch geratene Antwort macht aus einem Halter
    ein Teil von vier Millimetern.
    """
    project, _obj = _downloaded(unit="auto")
    result = evaluate(project.document, profile, sources=ProjectSources(project))

    assert not result.complete, "an ambiguous unit must stop the evaluation"
    assert not result.scene.objects, "nothing should be built on a guess"
    assert result.scene.report.findings, "stopping without a finding leaves the user blind"


def test_a_downloaded_model_gets_hooks_in_one_step(profile: Profile) -> None:
    """Schritt 1 bis 5: geladen, eine Fläche gewählt, Einhänger gesetzt.

    Der Kern der Zusage steckt in einer Zahl: **ein** Schritt im Stapel. Der
    Kunde hat nicht zwei Haken einzeln gesetzt und danach vereinigt, sondern
    einmal geklickt — und ein Undo nimmt es vollständig zurück (Regel 16).
    """
    project, obj = _downloaded()
    first = evaluate(project.document, profile, sources=ProjectSources(project))
    before = first.scene.objects[obj].mesh.volume
    faces = [fid for fid, f in first.scene.objects[obj].features.items() if f.kind == "face"]
    assert faces, "the downloaded model has no named faces to hang it by"

    History(project.document).apply(
        "Einhänger",
        [
            OperationDraft(
                op="insert_pegboard_hook",
                inputs=(obj,),
                params={"at_feature": faces[0], "count": 2},
            )
        ],
    )
    result = evaluate(project.document, profile, sources=ProjectSources(project))

    assert result.complete, [f.message for f in result.scene.report.findings]
    body = result.scene.objects[obj].mesh
    assert body.volume > before, "the hooks did not add anything"
    assert body.is_watertight, "the model with hooks is not printable"
    assert body.component_count == 1, "the hooks did not grow together with the model"
    assert len(project.document.ops) == 2, "loading and hanging should be two steps, not more"


def test_the_hooks_keep_the_grid_of_the_board(profile: Profile) -> None:
    """Was der Kunde nicht nachmessen soll: den Rasterabstand.

    Zwei Einhänger an einem Modell müssen dieselbe Rasterweite haben wie die
    Platte, an die sie kommen — sonst passen sie in keine zwei Schlitze. Die
    Zahl kommt aus der Tabelle und nicht aus dem Baustein.
    """
    board = standards.board("skadis")
    project, obj = _downloaded()

    for count in (1, 2, 3):
        wide = _hook_span(project, obj, profile, count)
        expected = board.pitch * (count - 1)
        assert wide == pytest.approx(expected, abs=0.6), (
            f"{count} hooks span {wide:.1f} mm, the grid says {expected:.1f}"
        )


def _hook_span(project: object, obj: str, profile: Profile, count: int) -> float:
    """Wie weit die Einhänger auseinanderstehen, am gebauten Baustein gemessen."""
    from app.core.knowledge.parts import PARTS

    spec = PARTS.get("pegboard_hook")
    built = spec.fn(spec.params(count=count))
    board = standards.board("skadis")
    # Die Platte reicht um jeden Haken herum; abgezogen bleibt der Achsabstand.
    return float(built.mesh.bounds.size[0]) - board.slot_width - 2.0 * board.slot_width
