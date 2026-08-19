"""Die drei Beispielprojekte (Bauplan §37.2, §40 für P8).

„Die drei Beispielprojekte öffnen und rechnen fehlerfrei" — das ist das
Abnahmekriterium, und das hier ist es. Sie sind Dokumentation und Abnahmetest
zugleich, eine Änderung, die eines von ihnen bricht, scheitert also hier statt
vor einem neuen Nutzer.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core import examples
from app.core.knowledge import profiles
from app.core.registry import REGISTRY
from app.core.scene import evaluate
from app.core.scene.project import ProjectSources, load
from app.core.types import Profile


def test_there_is_one_example_per_way() -> None:
    """§2.2 hat vier Wege, und §37.2 will genau die vier als Beispiele.

    Der vierte kam mit P16 dazu: eine Figur formen. Die weiteren Projekte sind
    keine fünften Wege — sie zeigen, was auf den vieren an Werkzeug
    bereitliegt. Die vier müssen aber da sein und vorn stehen: sie beantworten
    „wie fange ich an", und das ist die erste Frage.
    """
    ways = [entry.way for entry in examples.EXAMPLES if entry.way]

    assert ways == ["1", "2", "3", "4"]
    assert len({entry.id for entry in examples.EXAMPLES}) == len(examples.EXAMPLES)
    for entry in examples.EXAMPLES:
        assert str(entry.title).strip()
        assert str(entry.doc).strip()


def test_the_examples_reach_most_of_the_catalogue() -> None:
    """Drei Beispiele zeigten acht von zweiundsechzig Operationen (§25).

    Das ist genug, um die Wege zu erklären, und zu wenig, um das Werkzeug zu
    zeigen: die Bausteinbibliothek, die Beschriftung und die Kalibrierung waren
    in keinem davon zu sehen. Die Zahl hier ist kein Selbstzweck — sie hält
    fest, dass ein neuer Bereich auch ein Beispiel bekommt.
    """
    used: set[str] = set()
    for entry in examples.EXAMPLES:
        project = load(examples.directory() / entry.filename)
        used.update(operation.op for operation in project.document.ops)

    categories = {REGISTRY.get(name).category for name in used if REGISTRY.has(name)}

    assert len(used) >= 20, f"nur {len(used)} Operationen in allen Beispielen"
    assert {"parts", "label", "prepare", "holes", "repair", "import"} <= categories


def test_all_three_are_installed() -> None:
    found = {path.name for path in examples.paths()}

    assert found == {entry.filename for entry in examples.EXAMPLES}


@pytest.mark.parametrize("example", examples.EXAMPLES, ids=lambda entry: entry.id)
def test_an_example_opens_and_computes(example: examples.Example, profile: Profile) -> None:
    path = examples.directory() / example.filename
    project = load(path)

    result = evaluate(
        project.document,
        profiles.make_profile(
            project.document.printer or "centauri-carbon-2",
            project.document.material or "petg",
        ),
        sources=ProjectSources(project),
    )

    assert result.complete, [str(f.message) for f in result.scene.report.findings]
    assert result.scene.objects
    for entry in result.scene.objects.values():
        assert entry.mesh.volume > 0.0


def test_the_second_way_really_uses_parameters() -> None:
    """§2.2 Weg 2: an einer Zahl drehen, das Modell folgt — es muss also
    Zahlen geben.
    """
    project = load(examples.directory() / "weg2-halter-konstruieren.p3d")

    assert set(project.document.parameters) >= {"breite", "tiefe", "staerke"}
    bound = [
        entry
        for entry in project.document.ops
        if any(str(value).startswith("=@") for value in entry.params.values())
    ]
    assert bound, "the operations are tied to the parameters, not to fixed numbers"


def test_the_second_way_uses_the_library() -> None:
    """§39: Bausteine vor Primitiven — das Beispiel zeigt es, statt es zu
    sagen.
    """
    project = load(examples.directory() / "weg2-halter-konstruieren.p3d")
    names = [entry.op for entry in project.document.ops]

    assert names.count("insert_screw_hole") == 2
    assert "insert_rib" in names


def test_the_third_way_says_where_its_geometry_came_from() -> None:
    """§16.3: ein erzeugtes Netz ist als erzeugt markiert, nicht als
    gezeichnet.
    """
    project = load(examples.directory() / "weg3-generiert-aufbereiten.p3d")

    kinds = {source.kind for source in project.document.sources.values()}
    assert kinds == {"generated"}


def test_turning_a_parameter_changes_the_second_example(profile: Profile) -> None:
    """Das Versprechen von Weg 2, geprüft am Beispiel, das es vorführt."""
    import dataclasses

    project = load(examples.directory() / "weg2-halter-konstruieren.p3d")
    sources = ProjectSources(project)
    before = evaluate(project.document, profile, sources=sources)

    parameters = project.document.parameters
    parameters["breite"] = dataclasses.replace(parameters["breite"], value=90.0)
    after = evaluate(project.document, profile, sources=sources)

    assert after.complete
    assert (
        after.scene.objects["obj_1"].mesh.bounds.size[0]
        > (before.scene.objects["obj_1"].mesh.bounds.size[0])
    )


def test_the_written_documents_count_the_ways_and_examples_right() -> None:
    """Bauplan und README behaupten Zahlen — hier stehen sie neben der Quelle.

    Beide waren gedriftet: Der Bauplan führte §2.2 als „Drei Hauptwege",
    während der vierte längst gebaut war (P16, `weg4-figur-formen`), und die
    README sprach von drei Wegen und acht Beispielprojekten, als es vier und
    neun waren. Der Test darüber wusste es besser als beide Unterlagen — er
    prüft seit P16 auf vier Wege.

    Gezählt wird gegen ``EXAMPLES``, denn das ist die Quelle: Was dort liegt,
    liegt beim Start bereit.
    """
    wurzel = Path(__file__).resolve().parent.parent
    wege = sum(1 for entry in examples.EXAMPLES if entry.way)
    zahlwort = {3: "drei", 4: "vier", 5: "fünf"}[wege]

    bauplan = (wurzel / "3d-agent-bauplan.md").read_text(encoding="utf-8")
    assert f"### 2.2 {zahlwort.capitalize()} Hauptwege" in bauplan, (
        f"§2.2 nennt nicht {zahlwort} Hauptwege, obwohl {wege} Beispiele einen Weg tragen."
    )

    readme = (wurzel / "README.md").read_text(encoding="utf-8")
    assert f"## Die {zahlwort} Wege" in readme, f"Die README zählt nicht {zahlwort} Wege."

    # Die Unterlagen schreiben Zahlen aus — „neun Beispielprojekte", nicht „9".
    zahlen = {7: "sieben", 8: "acht", 9: "neun", 10: "zehn", 11: "elf", 12: "zwölf"}
    wort = zahlen.get(len(examples.EXAMPLES), str(len(examples.EXAMPLES)))
    assert f"{wort} Beispielprojekte" in readme, (
        f"Die README nennt nicht {wort} ({len(examples.EXAMPLES)}) Beispielprojekte."
    )

    # Und jedes Beispiel steht mit seiner Datei in der Tabelle — eine Zeile,
    # die fehlt, ist ein Projekt, von dem der Leser nichts erfährt.
    fehlen = [entry.id for entry in examples.EXAMPLES if f"{entry.id}.p3d" not in readme]
    assert not fehlen, f"Diese Beispiele fehlen in der README-Tabelle: {fehlen}"
