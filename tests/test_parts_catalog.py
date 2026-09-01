"""Katalog, Vorschau, SCAD-Ausgabe, eigene Bausteine, Versionierung (Bauplan §24.3–24.5)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.knowledge.parts import PARTS, preview, scad, user
from app.core.knowledge.parts import check as part_check
from app.core.knowledge.parts.registry import LIBRARY_VERSION, PartRegistry, used_parts
from app.core.scene import History, OperationDraft
from app.core.scene.project import load, new_project, save
from app.core.types import Document, Operation, Source

MESHES = Path(__file__).parent / "data" / "meshes"


# --- previews (§24.3) --------------------------------------------------------------


@pytest.mark.parametrize("spec", PARTS.all(), ids=lambda spec: spec.name)
def test_every_part_renders_a_preview(spec: object) -> None:
    """§24.3: die Bilder kommen aus den Bausteinen, nicht aus einem Ordner."""
    image = preview.render(spec)  # type: ignore[arg-type]

    assert image.svg.startswith("<svg")
    assert image.svg.count("<polygon") == image.triangles
    assert image.triangles > 0


def test_a_subtractive_part_looks_different() -> None:
    """Eine Form, die Material wegnimmt, wird nicht gezeichnet wie eine, die
    welches hinzufügt (§19.1).
    """
    hole = preview.render(PARTS.get("screw_hole"))
    rib = preview.render(PARTS.get("rib"))

    assert hole.svg != rib.svg


def test_a_preview_can_be_written(tmp_path: Path) -> None:
    path = tmp_path / "rib.svg"
    preview.render(PARTS.get("rib")).write(path)

    assert path.read_text(encoding="utf-8").startswith("<svg")


# --- SCAD output (§24.1) ------------------------------------------------------------


def test_a_part_can_be_written_as_scad() -> None:
    text = scad.to_scad(PARTS.get("latch"))

    assert "module latch()" in text
    assert "polyhedron(" in text
    assert text.rstrip().endswith("latch();")


def test_the_scad_file_names_its_parameters() -> None:
    """Die Werte stehen in der Datei zum Lesen, auch wenn der Körper ein
    festes Netz ist.
    """
    text = scad.to_scad(PARTS.get("screw_hole"))

    assert 'size = "M3";' in text
    assert "countersink = true;" in text
    assert "kein parametrischer Nachbau" in text, "and it says what it is not"


def test_scad_follows_the_parameters() -> None:
    spec = PARTS.get("dowel")
    thin = scad.to_scad(spec, spec.params(diameter=3.0))
    thick = scad.to_scad(spec, spec.params(diameter=8.0))

    assert thin != thick


# --- own parts (§24.5) ---------------------------------------------------------------


OWN_PART = '''
"""An own part, as a user would write it."""

from app.core.knowledge.parts.build import bore, result
from app.core.knowledge.parts.registry import PartChange, register_part
from app.core.knowledge.parts.shapes import cylinder
from app.core.registry import op_params, param
from app.core.types import BaseParams, PartResult


@op_params
class OwnParams(BaseParams):
    diameter: float = param(title="Durchmesser", default=6.0, unit="mm", minimum=1.0)


@register_part(
    name="eigenbau",
    title="Eigenbau",
    group="fasteners",
    params=OwnParams,
    subtractive=True,
    features=["bore"],
    doc="Ein selbst geschriebener Baustein.",
    changes=[PartChange(version="1", date="2026-07-28", reason="Erste Version.")],
)
def eigenbau(raw: BaseParams) -> PartResult:
    body = cylinder(raw.diameter, 10.0)
    return result(body, bore("bore_1", raw.diameter, (0.0, 0.0, 5.0), depth=10.0))
'''


def test_an_own_part_is_loaded_and_marked(tmp_path: Path) -> None:
    """§24.5: dieselbe Registrierung, aber der Katalog sagt, woher er kam."""
    (tmp_path / "eigenbau.py").write_text(OWN_PART, encoding="utf-8")
    registry = PartRegistry()

    import app.core.knowledge.parts.registry as registry_module

    original = registry_module.PARTS
    try:
        registry_module.PARTS = registry  # type: ignore[misc]
        result = user.load(tmp_path, registry)
    finally:
        registry_module.PARTS = original  # type: ignore[misc]

    assert result.loaded == ("eigenbau",)
    assert registry.get("eigenbau").own
    assert registry.get("eigenbau").source == "user"


def test_a_broken_own_part_is_reported_not_fatal(tmp_path: Path) -> None:
    (tmp_path / "kaputt.py").write_text("this is not python", encoding="utf-8")

    result = user.load(tmp_path, PartRegistry())

    assert result.loaded == ()
    assert result.findings and result.findings[0].code == "parts.user_failed"


def test_a_missing_directory_is_not_an_error(tmp_path: Path) -> None:
    assert user.load(tmp_path / "gibtsnicht", PartRegistry()).loaded == ()


def test_an_own_part_never_travels_with_the_project(tmp_path: Path) -> None:
    """§24.5, §32: eine hereinkommende Datei darf keinen Code tragen — also
    trägt sie keinen.
    """
    project = new_project("centauri-carbon-2", "petg")
    project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/cube_clean.stl", sha256=""
    )
    project.sources["src_1"] = (MESHES / "cube_clean.stl").read_bytes()
    History(project.document).apply(
        "Laden", [OperationDraft(op="load", params={"source": "src_1", "unit": "mm"})]
    )

    path = save(project, tmp_path / "projekt.p3d")
    import zipfile

    with zipfile.ZipFile(path) as container:
        names = container.namelist()

    assert not [name for name in names if name.endswith(".py")], "no code in a project file"


# --- versioning (§24.4) ---------------------------------------------------------------


def test_saving_records_the_library_version(tmp_path: Path) -> None:
    project = new_project("centauri-carbon-2", "petg")
    project.document.parts_version = "0"

    save(project, tmp_path / "projekt.p3d")

    assert project.document.parts_version == LIBRARY_VERSION
    assert load(tmp_path / "projekt.p3d").document.parts_version == LIBRARY_VERSION


def test_the_used_parts_are_read_off_the_stack() -> None:
    """§24.4: welche Bausteine ein Projekt benutzt, folgt aus seinem Stapel
    und sonst nichts.
    """
    from app.core.types import Operation

    document = Document(format_version=2, app_version="0.0.1")
    document.ops = [
        Operation(id=1, op="load", outputs=("obj_1",)),
        Operation(id=2, op="insert_screw_hole", inputs=("obj_1",), outputs=("obj_1",)),
        Operation(id=3, op="insert_rib", inputs=("obj_1",), outputs=("obj_1",)),
    ]

    assert used_parts(document.ops) == ("rib", "screw_hole")


def test_a_project_from_an_older_library_is_told_what_moved() -> None:
    """§24.4: welche *benutzten* Bausteine sich geändert haben, nicht nur dass
    sich etwas geändert hat.
    """
    from app.core.types import Operation

    document = Document(format_version=2, app_version="0.0.1", parts_version="0")
    document.ops = [
        Operation(id=1, op="load", outputs=("obj_1",)),
        Operation(id=2, op="insert_screw_hole", inputs=("obj_1",), outputs=("obj_1",)),
    ]

    findings = part_check.check(document)

    assert [finding.code for finding in findings] == ["parts.changed"]
    assert "screw_hole" in str(findings[0].values["parts"])


def test_a_library_12_project_is_told_about_all_three_geometry_fixes() -> None:
    """Die drei Maßkorrekturen aus Stand 13 erreichen die Projektmeldung."""
    from app.core.types import Operation

    document = Document(format_version=2, app_version="0.0.1", parts_version="12")
    document.ops = [
        Operation(id=2, op="insert_barrel_hinge", inputs=("obj_1",), outputs=("obj_1",)),
        Operation(id=3, op="insert_dowel", inputs=("obj_1",), outputs=("obj_1",)),
        Operation(id=4, op="insert_foot", inputs=("obj_1",), outputs=("obj_1",)),
    ]

    findings = part_check.check(document)

    assert [finding.code for finding in findings] == ["parts.changed"]
    assert findings[0].values["parts"] == "barrel_hinge, dowel, foot"


def test_a_project_of_the_current_library_says_nothing() -> None:
    from app.core.types import Operation

    document = Document(format_version=2, app_version="0.0.1", parts_version=LIBRARY_VERSION)
    document.ops = [Operation(id=2, op="insert_rib", inputs=("obj_1",), outputs=("obj_1",))]

    assert part_check.check(document) == []


def test_a_project_with_an_unknown_part_is_an_error() -> None:
    """§24.5: ein eigener Baustein von einer anderen Maschine hält die Kette
    an — still ist keine Option.
    """
    from app.core.types import Operation

    document = Document(format_version=2, app_version="0.0.1", parts_version=LIBRARY_VERSION)
    document.ops = [Operation(id=2, op="insert_eigenbau", inputs=("obj_1",), outputs=("obj_1",))]

    findings = part_check.check(document)

    assert findings[0].code == "parts.missing"
    assert findings[0].severity == "error"
    assert "eigenbau" in str(findings[0].values["parts"])


def test_load_user_parts_reports_a_broken_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """§24.5 stand nur auf dem Papier: `parts/user.py::load()` hatte keinen
    Aufrufer im Produkt — eigene Bausteine wurden nie geladen, ihr
    Katalogzweig war unerreichbar. `bootstrap.load_user_parts` ist der
    Aufrufer; eine kaputte Datei wird Befund, nie Startabbruch."""
    from app.core import bootstrap
    from app.core.knowledge.parts import user

    broken = tmp_path / "kaputt.py"
    broken.write_text("raise RuntimeError('absichtlich')", encoding="utf-8")
    monkeypatch.setattr(user, "user_parts_dir", lambda: tmp_path)
    monkeypatch.setattr(bootstrap, "_user_loaded", False)
    monkeypatch.setattr(bootstrap, "_user_findings", ())

    findings = bootstrap.load_user_parts()

    assert [entry.code for entry in findings] == ["parts.user_failed"]
    assert bootstrap.load_user_parts() == findings, "der zweite Aufruf lädt nicht erneut"


def _own_part_registry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> PartRegistry:
    """Lädt ``OWN_PART`` aus einem Nutzerverzeichnis und gibt sein Register."""
    (tmp_path / "eigenbau.py").write_text(OWN_PART, encoding="utf-8")
    registry = PartRegistry()

    import app.core.knowledge.parts.registry as registry_module

    monkeypatch.setattr(registry_module, "PARTS", registry)
    user.load(tmp_path, registry)
    return registry


def _document_using(part: str) -> Document:
    """Ein Dokument, das genau einen Baustein benutzt."""
    return Document(
        format_version=1,
        app_version="test",
        parts_version=LIBRARY_VERSION,
        ops=[Operation(id=1, op=f"insert_{part}")],
    )


def test_a_changed_own_part_is_reported_when_the_project_opens(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§24.4 gilt auch für Bausteine, die kein Update begleitet (§24.5).

    ``changed_since_library`` vergleicht gepflegte Änderungsverläufe — und die
    pflegt beim Ausprobieren niemand. Wer am Maß seiner eigenen Magnettasche
    schraubt, ändert weder Name noch Parameter noch ``version``; das Projekt
    rechnet beim nächsten Öffnen anders, und gemeldet wurde es nicht. Das
    bricht Leitprinzip 4 an der einzigen Stelle, an der die Bibliothek keine
    Version führt.

    Die zweite Quelle ist ein Abdruck der Datei, geschrieben beim Speichern.
    Geprüft wird hier die ganze Kette: Der Stempel legt ihn an, eine geänderte
    Datei wird gemeldet, eine unveränderte nicht — und ein Projekt ohne
    Abdruck schweigt, statt zu raten.
    """
    registry = _own_part_registry(tmp_path, monkeypatch)
    document = _document_using("eigenbau")

    part_check.stamp(document, registry)
    abdruck = document.libs.get(f"{user.FINGERPRINT_KEY}eigenbau")
    assert abdruck, "der Stempel hält den eigenen Baustein fest"

    assert not [
        finding
        for finding in part_check.check(document, registry)
        if finding.code == "parts.own_changed"
    ], "unverändert ist kein Befund"

    (tmp_path / "eigenbau.py").write_text(
        OWN_PART.replace("cylinder(raw.diameter, 10.0)", "cylinder(raw.diameter, 12.0)"),
        encoding="utf-8",
    )
    findings = [
        finding
        for finding in part_check.check(document, registry)
        if finding.code == "parts.own_changed"
    ]

    assert findings, "eine geänderte eigene Datei wird beim Öffnen gemeldet"
    assert findings[0].values["parts"] == "eigenbau"
    assert findings[0].severity == "info", "ein Hinweis mit einer Wahl, kein Abbruch (§24.4)"


def test_a_project_without_a_fingerprint_says_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die Gegenprobe zur Prüfung darüber, und sie ist die wichtigere Hälfte.

    Jedes Projekt, das vor dieser Änderung gespeichert wurde, hat keinen
    Abdruck. Meldete die Prüfung dort „geändert", wäre sie bei **jedem** alten
    Projekt mit eigenem Baustein rot — ein Falschbefund, der schlimmer ist als
    die Lücke, die er schließen soll. Fehlender Abdruck heißt „keine Aussage
    möglich", nicht „hat sich geändert".
    """
    registry = _own_part_registry(tmp_path, monkeypatch)
    document = _document_using("eigenbau")

    (tmp_path / "eigenbau.py").write_text(
        OWN_PART.replace("cylinder(raw.diameter, 10.0)", "cylinder(raw.diameter, 12.0)"),
        encoding="utf-8",
    )

    assert not [
        finding
        for finding in part_check.check(document, registry)
        if finding.code == "parts.own_changed"
    ], "ohne Abdruck wird nicht geraten"


def test_the_stamp_forgets_a_part_the_project_no_longer_uses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein Abdruck, den niemand mehr liest, wird mit jedem Speichern älter und
    sieht irgendwann wie eine Aussage aus.
    """
    registry = _own_part_registry(tmp_path, monkeypatch)
    document = _document_using("eigenbau")
    part_check.stamp(document, registry)

    document.ops = []
    part_check.stamp(document, registry)

    assert not [key for key in document.libs if key.startswith(user.FINGERPRINT_KEY)]


def test_saving_a_project_really_records_the_own_parts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Nicht „der Kern kann es", sondern „die Anwendung tut es" (§35).

    **Warum dieser Test neben den dreien darüber steht.** Die prüfen
    ``stamp()`` und ``check()`` direkt und wären auch dann grün, wenn niemand
    sie riefe. Genau so lag der Plattencache aus §38 monatelang da:
    vollständig gebaut, vollständig geprüft, in der Anwendung nie benutzt —
    und in dieser Datei ist derselbe Fehler schon zweimal aufgetreten
    (``user.load()`` hatte keinen Aufrufer, ``travelling_parts()`` hat bis
    heute keinen). Der Riss sitzt nicht in einem Modul, sondern **zwischen**
    zweien, und dorthin sieht keine der Testarten aus §35.

    Gefahren wird deshalb der echte Weg: ``project.save()`` — dieselbe
    Funktion, die die Oberfläche ruft. Was danach in der Datei steht,
    entscheidet.

    Gepatcht ist nur das Register, und zwar dort, wo die Frage sitzt: in den
    Modulen, die ``PARTS`` bereits importiert haben. Ein Patch auf
    ``registry.PARTS`` ginge daran vorbei, weil ``from … import PARTS`` eine
    eigene Referenz hält — der Fall, den §35 unter „wer messen will, wickelt
    dort ein, wo die Frage sitzt" beschreibt.
    """
    registry = _own_part_registry(tmp_path, monkeypatch)
    monkeypatch.setattr(part_check, "PARTS", registry)
    monkeypatch.setattr(user, "PARTS", registry)

    project = new_project("centauri-carbon-2", "petg")
    project.document.ops = [Operation(id=1, op="insert_eigenbau")]

    save(project, tmp_path / "projekt.p3d")
    wieder = load(tmp_path / "projekt.p3d")

    abdruck = wieder.document.libs.get(f"{user.FINGERPRINT_KEY}eigenbau")
    assert abdruck, "die gespeicherte Datei hält den Stand des eigenen Bausteins"
    assert abdruck == user.fingerprint("eigenbau", registry)

    # Und die Kette bis zum Befund: geänderte Datei, geöffnetes Projekt.
    (tmp_path / "eigenbau.py").write_text(
        OWN_PART.replace("cylinder(raw.diameter, 10.0)", "cylinder(raw.diameter, 12.0)"),
        encoding="utf-8",
    )
    codes = [finding.code for finding in part_check.check(wieder.document, registry)]

    assert "parts.own_changed" in codes


def test_a_project_with_an_own_part_warns_before_it_leaves_the_machine(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regel 13: der eigene Baustein reist nicht mit — und der Absender erfährt
    es, solange er noch etwas tun kann (§24.5).

    Ohne diese Auskunft bekommt der Empfänger ein Projekt, das bei ihm anhält
    (§15.2), und der Grund liegt auf einem Rechner, an den dann niemand mehr
    herankommt. Die Warnung gehört deshalb an die Stellen, an denen die Datei
    **weggeht** — nicht an jedes Speichern, wo sie zwanzigmal am Abend
    erschiene und beim einundzwanzigsten Mal weggeklickt würde.
    """
    registry = _own_part_registry(tmp_path, monkeypatch)
    document = _document_using("eigenbau")

    findings = part_check.check_outgoing(document, registry)

    assert [finding.code for finding in findings] == ["parts.travelling"]
    assert findings[0].values["parts"] == "eigenbau"
    assert findings[0].severity == "warning"
    assert "Bausteinordner" in str(findings[0].message), "die Meldung nennt eine Handlung (§2.7)"


def test_a_project_without_own_parts_says_nothing_on_the_way_out() -> None:
    """Die Gegenprobe: Ein mitgelieferter Baustein reist mit der Anwendung, und
    darüber ist nichts zu sagen.

    Ohne sie wäre die Prüfung auch dann grün, wenn sie **jedes** Projekt
    warnte — und eine Warnung, die immer kommt, ist keine.
    """
    document = _document_using("magnet_pocket")

    assert part_check.check_outgoing(document) == []
