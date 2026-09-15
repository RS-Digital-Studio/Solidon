"""Native Slicer-Werkzeuge sind eine andere Zuordnung als Standard-3MF-Farben."""

from __future__ import annotations

import json
import zipfile
from io import BytesIO
from xml.etree import ElementTree as ET

import pytest
import trimesh

from app.core.errors import BooleanFailedError, ValidationError
from app.core.export import threemf as writer
from app.core.geom.mesh import MeshData
from app.core.ingest import threemf as reader
from app.core.scene import History, OperationDraft, evaluate
from app.core.scene.project import Project, ProjectSources, new_project
from app.core.types import Finding, MaterialSlot, Profile, Source
from app.i18n import TranslatableText, _


def _parts() -> list[writer.AssemblyPart]:
    return [
        writer.AssemblyPart(
            MeshData(trimesh.creation.box(), (0,) * 12),
            str(index),
            (MaterialSlot(0, name, colour=colour),),
        )
        for index, (name, colour) in enumerate(
            [("Rot", (1.0, 0.0, 0.0)), ("Blau", (0.0, 0.0, 1.0))]
        )
    ]


def test_export_object_extruders_follow_global_slot_order_and_keep_gaps() -> None:
    parts = _parts()
    payload = writer.write_assembly(parts[1:], across=parts, prusa_config={"layer_height": "0.2"})
    with zipfile.ZipFile(BytesIO(payload)) as archive:
        for file in (writer.SETTINGS_PATH, writer.PRUSA_MODEL_CONFIG_PATH):
            config = ET.fromstring(archive.read(file))
            assert config.find("object/metadata[@key='extruder']").get("value") == "2"


def test_export_face_paint_uses_native_whole_triangle_states() -> None:
    slots = tuple(MaterialSlot(i, f"F{i}") for i in range(4))
    part = writer.AssemblyPart(MeshData(trimesh.creation.box(), tuple(range(4)) * 3), slots=slots)
    with zipfile.ZipFile(BytesIO(writer.write_assembly([part]))) as archive:
        model = ET.fromstring(archive.read(writer.MODEL_PATH))
        faces = model.findall(f".//{{{writer.CORE_NAMESPACE}}}triangle")
        assert [f.get("paint_color") for f in faces[:4]] == ["4", "8", "0C", "1C"]
        assert [
            f.get("{http://schemas.slic3r.org/3mf/2017/06}mmu_segmentation") for f in faces[:4]
        ] == ["4", "8", "0C", "1C"]


def _native(
    *,
    paint: str = "",
    prusa: bool = False,
    part_override: bool = True,
    paint_at: dict[int, str] | None = None,
    part_extra: str = "",
    extra: dict[str, tuple[str, trimesh.Trimesh]] | None = None,
) -> bytes:
    """Eine Box als native Slicer-Datei: ``paint`` bemalt die ersten sechs
    Dreiecke, ``paint_at`` einzelne nach Index, ``part_extra`` steht als
    Rohtext im ``part``-Eintrag der Slicer-Konfiguration, ``extra`` hängt
    weitere Teile mit ihrer Art (``subtype``) an dasselbe Objekt.
    """
    ns = reader.CORE_NAMESPACE
    body = trimesh.creation.box()
    root = ET.Element("model", {"xmlns": ns, "unit": "millimeter"})
    resources = ET.SubElement(root, "resources")
    parent = ET.SubElement(resources, "object", {"id": "20"})
    components = ET.SubElement(parent, "components")
    ET.SubElement(components, "component", {"objectid": "2"})
    for identifier in extra or {}:
        ET.SubElement(components, "component", {"objectid": identifier})
    obj = ET.SubElement(resources, "object", {"id": "2", "type": "model"})
    mesh = ET.SubElement(obj, "mesh")
    vertices = ET.SubElement(mesh, "vertices")
    for x, y, z in body.vertices:
        ET.SubElement(vertices, "vertex", {"x": str(x), "y": str(y), "z": str(z)})
    triangles = ET.SubElement(mesh, "triangles")
    for index, (a, b, c) in enumerate(body.faces):
        attrs = {"v1": str(a), "v2": str(b), "v3": str(c)}
        code = (paint_at or {}).get(index, paint if index < 6 else "")
        if code:
            attrs[
                "{http://schemas.slic3r.org/3mf/2017/06}mmu_segmentation"
                if prusa
                else "paint_color"
            ] = code
        ET.SubElement(triangles, "triangle", attrs)
    for identifier, (_kind, shape) in (extra or {}).items():
        other = ET.SubElement(resources, "object", {"id": identifier, "type": "model"})
        other_mesh = ET.SubElement(other, "mesh")
        other_vertices = ET.SubElement(other_mesh, "vertices")
        for x, y, z in shape.vertices:
            ET.SubElement(other_vertices, "vertex", {"x": str(x), "y": str(y), "z": str(z)})
        other_triangles = ET.SubElement(other_mesh, "triangles")
        for a, b, c in shape.faces:
            ET.SubElement(other_triangles, "triangle", {"v1": str(a), "v2": str(b), "v3": str(c)})
    ET.SubElement(ET.SubElement(root, "build"), "item", {"objectid": "20"})
    metadata = '<config><object id="20"><metadata key="extruder" value="1"/>'
    if part_override:
        metadata += (
            '<part id="2" subtype="normal_part"><metadata key="extruder" value="3"/>'
            + part_extra
            + "</part>"
        )
    for identifier, (kind, _shape) in (extra or {}).items():
        metadata += (
            f'<part id="{identifier}" subtype="{kind}">'
            f'<metadata key="name" value="Teil {identifier}"/></part>'
        )
    metadata += "</object></config>"
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(writer.MODEL_PATH, ET.tostring(root))
        archive.writestr(writer.SETTINGS_PATH, metadata)
        if prusa:
            archive.writestr(
                writer.PRUSA_CONFIG_PATH, "; config\n; filament_colour = #FF0000;#0000FF;#00FF00\n"
            )
        else:
            archive.writestr(
                writer.PROJECT_SETTINGS_PATH,
                json.dumps(
                    {
                        "filament_colour": ["#FF0000", "#0000FF", "#00FF00"],
                        "filament_type": ["PLA", "PETG", "TPU"],
                    }
                ),
            )
    return buffer.getvalue()


def test_native_part_tool_overrides_parent_and_keeps_its_palette() -> None:
    part = reader.read_objects(_native())[0]
    assert part.mesh.slots == (0,) * 12
    assert len(part.slots) == 1
    assert part.slots[0].colour == (0.0, 1.0, 0.0)
    assert part.slots[0].material_type == "TPU"


@pytest.mark.parametrize("prusa", [False, True])
def test_native_face_paint_overrides_object_tool(prusa: bool) -> None:
    part = reader.read_objects(_native(paint="8", prusa=prusa, part_override=False))[0]
    assert part.mesh.slots == (1,) * 6 + (0,) * 6
    assert [slot.colour for slot in part.slots] == [(1.0, 0.0, 0.0), (0.0, 0.0, 1.0)]


@pytest.mark.parametrize(
    ("paint", "reason"),
    [
        ("18C", "Unvollständige oder überzählige Flächenbemalung"),
        ("ZZ", "Ungültige Flächenbemalung"),
        ("9C", "Werkzeugnummer außerhalb der Filamentpalette"),
    ],
)
def test_unreadable_native_paint_keeps_the_body_in_one_colour(paint: str, reason: str) -> None:
    """Bis zum 14.09.2026 hielt jeder dieser Gründe den ganzen Import an —
    ein Kunde bekam so ein Modell von MakerWorld nicht auf (Support-Vorgang
    S-20260914-e4b6d7). Jetzt kommt der Körper, einfarbig, und der Grund
    steht mit demselben Rat als Befund daneben.
    """
    findings: list[Finding] = []
    parts = reader.read_objects(_native(paint=paint), findings)
    assert len(parts) == 1
    assert parts[0].mesh.triangle_count == 12
    assert parts[0].slots == ()
    assert parts[0].mesh.slots == ()
    assert [entry.code for entry in findings] == ["ingest.colours_dropped"]
    finding = findings[0]
    assert finding.severity == "warning"
    detail = finding.values["reason"]
    assert isinstance(detail, TranslatableText), "eigene Fehlergründe bleiben übersetzbar"
    assert detail.translate("de") == reason
    sentence = finding.message.translate("de")
    assert reason in sentence
    # Im Satz, nicht in ``suggestions``: Für „im Slicer aufteilen" gibt es
    # keinen Handler, und der Prüfbericht zeigt nur Handlungen mit einem —
    # als Vorschlag angehängt käme der Rat nie an.
    assert "im Slicer nach Filamenten" in sentence
    assert finding.suggestions == ()


def test_an_unreadable_palette_keeps_every_body_and_says_so() -> None:
    findings: list[Finding] = []
    payload = _changed(
        _native(paint="8"),
        {writer.PROJECT_SETTINGS_PATH: b'{"filament_colour": "rot"}'},
    )
    parts = reader.read_objects(payload, findings)
    assert len(parts) == 1
    assert parts[0].slots == ()
    assert [entry.code for entry in findings] == ["ingest.palette_dropped"]
    assert findings[0].values["reason"].translate("de") == "Ungültige Filamentfarbliste"
    assert "im Slicer nach Filamenten" in findings[0].message.translate("de")
    assert reader.count_objects(payload) == 1


def test_a_tool_problem_hits_only_its_own_object() -> None:
    """Zwei Objekte teilen ein Mesh; das erste nennt eine Werkzeugnummer, die
    keine ist. Es kommt einfarbig — das zweite behält seine Farbe.
    """
    payload = _native()
    with zipfile.ZipFile(BytesIO(payload)) as source:
        model = ET.fromstring(source.read(writer.MODEL_PATH))
    ns = reader.CORE_NAMESPACE
    parent = ET.SubElement(model.find(f"{{{ns}}}resources"), f"{{{ns}}}object", {"id": "21"})
    components = ET.SubElement(parent, f"{{{ns}}}components")
    ET.SubElement(components, f"{{{ns}}}component", {"objectid": "2"})
    ET.SubElement(model.find(f"{{{ns}}}build"), f"{{{ns}}}item", {"objectid": "21"})
    config = (
        b'<config><object id="20"><metadata key="extruder" value="x"/>'
        b'</object><object id="21"><part id="2">'
        b'<metadata key="extruder" value="3"/></part></object></config>'
    )
    findings: list[Finding] = []
    parts = reader.read_objects(
        _changed(payload, {writer.MODEL_PATH: ET.tostring(model), writer.SETTINGS_PATH: config}),
        findings,
    )
    assert [part.slots for part in parts] == [
        (),
        (MaterialSlot(0, "Slot 2", colour=GREEN, material_type="TPU"),),
    ]
    assert [entry.code for entry in findings] == ["ingest.colours_dropped"]
    assert findings[0].values["reason"].translate("de") == "Ungültige Werkzeugnummer"


def test_slicer_helper_parts_are_not_bodies() -> None:
    """Ein Modifikator und ein Stützblocker sind Anweisungen an den Slicer,
    keine Geometrie des Drucks. Sie kommen nicht als Körper — und der
    Zählweg, der die Objekt-IDs vergibt, zählt sie ebenso wenig.
    """
    findings: list[Finding] = []
    payload = _native(
        extra={
            "3": ("modifier_part", trimesh.creation.box(extents=(0.5, 0.5, 0.5))),
            "4": ("support_blocker", trimesh.creation.box(extents=(0.2, 0.2, 0.2))),
        }
    )
    parts = reader.read_objects(payload, findings)
    assert len(parts) == 1
    assert parts[0].mesh.volume == pytest.approx(1.0)
    assert reader.count_objects(payload) == 1
    assert [entry.code for entry in findings] == ["ingest.helper_skipped"] * 2
    kinds = [entry.values["kind"].translate("de") for entry in findings]
    assert kinds == ["Modifikator", "Stützblocker"]
    assert [entry.values["name"] for entry in findings] == ["Teil 3", "Teil 4"]


def test_a_negative_part_is_cut_from_its_body() -> None:
    """Ein ``negative_part`` ist eine Aussparung, die der Slicer beim Slicen
    abzieht. Ein halber Würfel von 0,5 mm Kante, zur Hälfte im Körper: Das
    Volumen sinkt um 0,25 × 0,5 × 0,5.
    """
    findings: list[Finding] = []
    cutter = trimesh.creation.box(extents=(0.5, 0.5, 0.5))
    cutter.apply_translation((0.5, 0.0, 0.0))
    payload = _native(extra={"3": ("negative_part", cutter)})
    parts = reader.read_objects(payload, findings)
    assert len(parts) == 1
    assert parts[0].mesh.volume == pytest.approx(1.0 - 0.25 * 0.5 * 0.5)
    assert parts[0].mesh.is_watertight
    assert parts[0].slots[0].colour == GREEN, "die Farbe des Körpers bleibt"
    assert reader.count_objects(payload) == 1
    assert [entry.code for entry in findings] == ["ingest.negative_carved"]
    assert findings[0].values["cutter"] == "Teil 3"
    assert findings[0].values["name"] == parts[0].name
    assert "Teil 3" in findings[0].message.translate("de")
    # Die Stufe der Rückfallkette reist mit (§17.2): am Befund und am Körper,
    # damit die ``load``-Operation die tiefste aller Körper melden kann.
    assert parts[0].solver is not None
    assert findings[0].values["solver"] == parts[0].solver.strategy == "direct"


def test_a_negative_part_touches_only_the_body_it_reaches() -> None:
    """Ein Objekt aus zwei Teilen, eine Aussparung an einem davon: Das andere
    behält sein Netz und bekommt keinen Befund über einen Schnitt, der
    keiner war.
    """
    findings: list[Finding] = []
    apart = trimesh.creation.box()
    apart.apply_translation((3.0, 0.0, 0.0))
    cutter = trimesh.creation.box(extents=(0.5, 0.5, 0.5))
    cutter.apply_translation((0.5, 0.0, 0.0))
    payload = _native(extra={"3": ("normal_part", apart), "4": ("negative_part", cutter)})
    parts = reader.read_objects(payload, findings)
    assert len(parts) == 2
    assert reader.count_objects(payload) == 2
    assert [round(part.mesh.volume, 4) for part in parts] == [0.9375, 1.0]
    assert parts[1].mesh.triangle_count == 12, "unberührt heißt: das Netz der Datei"
    assert [entry.code for entry in findings] == ["ingest.negative_carved"]
    assert findings[0].values["name"] == parts[0].name


def test_every_edge_split_from_both_sides_leaves_nothing_to_close() -> None:
    """Alle zwölf Dreiecke der Box dreifach geteilt: Jede Kante ist von
    beiden Seiten halbiert, kein T-Stoß bleibt — und die leere Liste der
    geschlossenen Dreiecke riss ``vstack`` mit der Form ``(0,)`` (gemessen
    am 14.09.2026, bevor der Test da war).
    """
    payload = _native(paint_at=dict.fromkeys(range(12), "04843"), part_override=False)
    part = reader.read_objects(payload, [])[0]
    assert part.mesh.triangle_count == 12 * 4
    assert part.mesh.is_watertight
    assert part.mesh.volume == pytest.approx(1.0)
    assert part.mesh.area == pytest.approx(6.0)


@pytest.mark.parametrize(
    "kind", ["normal_part", "modifier_part", "support_blocker", "negative_part", "seam_painting"]
)
def test_the_scan_counts_exactly_what_the_reader_returns(kind: str) -> None:
    """§11: Die Körperzahl steht fest, bevor gerechnet wird — für jede Art,
    auch eine, die keiner kennt. Zwei Listen an zwei Stellen liefen hier
    auseinander: Der Zählweg zählte nur ``normal_part``, der Leser
    übersprang nur, was er kannte, und eine neue Slicer-Art hätte die
    Auswertung mit ``evaluate.object_count`` angehalten.
    """
    apart = trimesh.creation.box()
    apart.apply_translation((3.0, 0.0, 0.0))
    payload = _native(extra={"3": (kind, apart)})
    findings: list[Finding] = []
    parts = reader.read_objects(payload, findings)
    assert len(parts) == reader.count_objects(payload)
    if kind == "seam_painting":
        assert len(parts) == 2, "unbekannt heißt: geladen, nicht verschluckt"
        assert [entry.code for entry in findings] == ["ingest.unknown_part_kind"]
        assert findings[0].values == {"name": "Teil 3", "kind": "seam_painting"}


def test_a_prusa_volume_that_is_no_model_part_gets_its_own_sentence() -> None:
    """PrusaSlicer führt Modifikator und Aussparung als Dreiecksbereich im
    selben Netz. Der Körper kommt einfarbig — aber der Satz sagt, was
    wirklich passiert ist: Der Bereich ist als Material geladen. „Farben
    nicht gelesen" wäre die halbe Wahrheit (Regel 21). Und gefunden wird das
    Problem unter der Objekt-ID, unter der PrusaSlicer es notiert — dem
    Mesh-Objekt, nicht dem Build-Objekt darüber.
    """
    config = (
        b'<config><object id="2"><volume firstid="0" lastid="5">'
        b'<metadata key="volume_type" value="ModelPart"/><metadata key="extruder" value="2"/>'
        b'</volume><volume firstid="6" lastid="11">'
        b'<metadata key="volume_type" value="NegativeVolume"/>'
        b'<metadata key="extruder" value="3"/></volume></object></config>'
    )
    payload = _changed(
        _native(prusa=True, part_override=False), {writer.PRUSA_MODEL_CONFIG_PATH: config}
    )
    findings: list[Finding] = []
    parts = reader.read_objects(payload, findings)
    assert len(parts) == 1
    assert parts[0].slots == (), "kein halb gelesener Bereich bleibt als Farbe stehen"
    assert [entry.code for entry in findings] == ["ingest.foreign_volume"]
    assert findings[0].values == {"name": parts[0].name, "kind": "NegativeVolume"}
    assert "NegativeVolume" in findings[0].message.translate("de")


def test_a_paint_code_nested_too_deep_is_a_finding_not_a_crash() -> None:
    """Tausend Ebenen rissen den Import als ``RecursionError`` — ein
    Dateiproblem im Gewand eines Programmfehlers. Ab :data:`MAX_PAINT_DEPTH`
    kommt der Körper einfarbig, mit dem Grund daneben.
    """
    # Strom vorwärts: je Ebene eine Teilung, deren zweites Kind tiefer geht
    # und deren erstes ein Blatt ist; die Zeichenkette steht rückwärts.
    depth = reader.MAX_PAINT_DEPTH + 40
    stream = "1" * depth + "4" + "4" * depth
    payload = _native(paint_at={0: stream[::-1]}, part_override=False)
    findings: list[Finding] = []
    parts = reader.read_objects(payload, findings)
    assert len(parts) == 1
    assert parts[0].mesh.triangle_count == 12
    assert [entry.code for entry in findings] == ["ingest.colours_dropped"]
    assert findings[0].values["reason"].translate("de") == "Flächenbemalung zu tief verschachtelt"
    # Und knapp unter der Grenze wird gelesen — sie ist eine Grenze, kein Verbot.
    depth = reader.MAX_PAINT_DEPTH - 1
    stream = "1" * depth + "4" + "4" * depth
    node = reader._decode_paint(stream[::-1])
    assert isinstance(node, reader._PaintSplit)


def test_a_failed_cut_keeps_the_kernels_way_out(monkeypatch: pytest.MonkeyPatch) -> None:
    """Scheitert die Rückfallkette, sagt ``BooleanFailedError``, ob Maße oder
    Netz das Problem sind — und der Befund trägt ihre Handlungen (Regel 17),
    nicht nur den Satz, dass es nicht ging.
    """
    from app.core.geom import boolean as chain

    def failing(*args: object, **kwargs: object) -> object:
        raise BooleanFailedError(detail=_("erzwungen"), attempted=("direct", "welded"))

    monkeypatch.setattr(chain, "boolean", failing)
    cutter = trimesh.creation.box(extents=(0.5, 0.5, 0.5))
    cutter.apply_translation((0.5, 0.0, 0.0))
    findings: list[Finding] = []
    parts = reader.read_objects(_native(extra={"3": ("negative_part", cutter)}), findings)
    assert parts[0].mesh.volume == pytest.approx(1.0), "ohne Aussparung, aber da"
    assert parts[0].solver is None
    assert [entry.code for entry in findings] == ["ingest.negative_kept_out"]
    assert findings[0].suggestions, "der Ausweg des Rechenkerns reist mit"
    assert findings[0].values["detail"]


def test_a_negative_part_that_touches_nothing_is_said_so() -> None:
    """Die eine Stelle, an der der Leser sonst schweigend entschiede: Eine
    Aussparung neben allen Körpern ihres Objekts schneidet nichts — im Slicer
    ebenso. Gesagt wird es trotzdem.
    """
    cutter = trimesh.creation.box(extents=(0.5, 0.5, 0.5))
    cutter.apply_translation((5.0, 0.0, 0.0))
    findings: list[Finding] = []
    parts = reader.read_objects(_native(extra={"3": ("negative_part", cutter)}), findings)
    assert parts[0].mesh.volume == pytest.approx(1.0)
    assert parts[0].mesh.triangle_count == 12, "unberührt heißt: das Netz der Datei"
    assert [entry.code for entry in findings] == ["ingest.negative_without_effect"]
    assert findings[0].values == {"cutter": "Teil 3"}


def _project_of(payload: bytes) -> Project:
    project = new_project("centauri-carbon-2", "petg")
    project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/native.3mf", sha256=""
    )
    project.sources["src_1"] = payload
    return project


def _asks_never(question: str, choices: list[str]) -> str:
    raise AssertionError(f"gefragt, obwohl die Datei es sagt: {question}")


def test_the_load_operation_carries_the_readers_findings_into_the_report(
    profile: Profile,
) -> None:
    """Der Anschluss: Was der Leser meldet, kommt über die ``load``-Operation
    in den Prüfbericht — sonst stünde der Grund nur im Protokoll, und der
    Kunde sähe ein einfarbiges Modell ohne ein Wort dazu. Geprüft an der
    Stelle, die es einlöst, nicht am Leser allein.
    """
    cutter = trimesh.creation.box(extents=(0.5, 0.5, 0.5))
    cutter.apply_translation((0.5, 0.0, 0.0))
    project = _project_of(_native(paint="ZZ", extra={"3": ("negative_part", cutter)}))
    history = History(project.document)
    history.apply(_("Laden"), [OperationDraft(op="load", params={"source": "src_1"})])

    result = evaluate(project.document, profile, sources=ProjectSources(project), ask=_asks_never)

    assert result.complete
    assert list(result.scene.objects) == ["obj_1"]
    body = result.scene.objects["obj_1"]
    assert body.material_slots == [], "einfarbig, weil die Bemalung keine ist"
    assert body.mesh.volume == pytest.approx(1.0 - 0.25 * 0.5 * 0.5)
    by_code = {entry.code: entry for entry in result.scene.report.findings}
    assert {"ingest.colours_dropped", "ingest.negative_carved"} <= set(by_code)
    dropped = by_code["ingest.colours_dropped"]
    assert dropped.severity == "warning"
    assert "Ungültige Flächenbemalung" in dropped.message.translate("de")
    assert "im Slicer nach Filamenten" in dropped.message.translate("de")


def test_a_file_of_nothing_but_a_negative_part_is_refused_not_read_as_a_body() -> None:
    """Eine leere Liste hieße für ``load``: keine lesbare 3MF, also der
    allgemeine Leser — und der lüde die Aussparung als Körper, neben dem
    Befund, sie sei nicht geladen. Deshalb eine Absage mit Ausweg.
    """
    payload = _native(extra={"3": ("negative_part", trimesh.creation.box())})
    with zipfile.ZipFile(BytesIO(payload)) as source:
        model = ET.fromstring(source.read(writer.MODEL_PATH))
    ns = reader.CORE_NAMESPACE
    components = model.find(f".//{{{ns}}}object[@id='20']/{{{ns}}}components")
    assert components is not None
    components.remove(components.find(f"{{{ns}}}component[@objectid='2']"))
    payload = _changed(payload, {writer.MODEL_PATH: ET.tostring(model)})
    assert reader.count_objects(payload) == 0
    with pytest.raises(ValidationError) as caught:
        reader.read_objects(payload, [])
    assert caught.value.constraint == "no_printable_part"
    assert caught.value.values["skipped"] == 1
    assert caught.value.suggestions


def _changed(payload: bytes, replacements: dict[str, bytes]) -> bytes:
    """Unabhängige native Metadaten in dieselbe Testgeometrie einsetzen."""
    buffer = BytesIO()
    with zipfile.ZipFile(BytesIO(payload)) as source, zipfile.ZipFile(buffer, "w") as target:
        for path in source.namelist():
            target.writestr(path, replacements.pop(path, source.read(path)))
        for path, content in replacements.items():
            target.writestr(path, content)
    return buffer.getvalue()


def test_reused_part_ids_keep_each_parent_object_tool() -> None:
    payload = _native()
    with zipfile.ZipFile(BytesIO(payload)) as source:
        model = ET.fromstring(source.read(writer.MODEL_PATH))
    ns = reader.CORE_NAMESPACE
    parent = ET.SubElement(model.find(f"{{{ns}}}resources"), f"{{{ns}}}object", {"id": "21"})
    components = ET.SubElement(parent, f"{{{ns}}}components")
    ET.SubElement(components, f"{{{ns}}}component", {"objectid": "2"})
    ET.SubElement(model.find(f"{{{ns}}}build"), f"{{{ns}}}item", {"objectid": "21"})
    config = (
        b'<config><object id="20"><part id="2"><metadata key="extruder" value="2"/>'
        b'</part></object><object id="21"><part id="2">'
        b'<metadata key="extruder" value="3"/></part></object></config>'
    )
    parts = reader.read_objects(
        _changed(
            payload,
            {
                writer.MODEL_PATH: ET.tostring(model),
                writer.SETTINGS_PATH: config,
            },
        )
    )
    assert [part.slots[0].colour for part in parts] == [(0.0, 0.0, 1.0), (0.0, 1.0, 0.0)]


def test_prusa_volume_ranges_and_single_mesh_reader_keep_native_tools() -> None:
    config = (
        b'<config><object id="2"><volume firstid="0" lastid="5">'
        b'<metadata key="extruder" value="2"/></volume><volume firstid="6" lastid="11">'
        b'<metadata key="extruder" value="3"/></volume></object></config>'
    )
    payload = _changed(
        _native(prusa=True, part_override=False),
        {
            writer.PRUSA_MODEL_CONFIG_PATH: config,
        },
    )
    part = reader.read_objects(payload)[0]
    assert part.mesh.slots == (0,) * 6 + (1,) * 6
    groups = reader.read(payload, 12)
    assert groups is not None
    assert groups.slots == part.mesh.slots
    assert [slot.colour for slot in groups.materials] == [(0.0, 0.0, 1.0), (0.0, 1.0, 0.0)]


@pytest.mark.parametrize(
    ("code", "tool"),
    [
        ("0", None),
        ("4", 0),
        ("8", 1),
        ("0C", 2),
        ("EC", 16),
        ("0FC", 17),
        ("7FC", 24),
        ("9FC", 26),
        ("EFC", 31),
    ],
)
def test_extended_native_leaf_codes(code: str, tool: int | None) -> None:
    node = reader._decode_paint(code)
    assert isinstance(node, reader._PaintLeaf)
    assert reader._leaf_tool(node) == tool
    if tool is not None:
        assert writer._paint_code(tool) == code


@pytest.mark.parametrize("code", ["FC", "FFC", "09FC", "18C"])
def test_incomplete_or_oversized_native_code_is_refused(code: str) -> None:
    with pytest.raises(reader._MaterialError) as caught:
        reader._decode_paint(code)
    assert caught.value.reason.translate("de") == "Unvollständige oder überzählige Flächenbemalung"


def _shares(node: reader._PaintNode) -> dict[int, float]:
    """Flächenanteil je Zustand, allein aus dem Baum: Eine Seite teilt in
    zwei Hälften, zwei Seiten in ein Viertel, ein Viertel und eine Hälfte,
    drei Seiten in vier Viertel — die Sollwerte, an denen die Geometrie
    gemessen wird, ohne sie zu kennen.
    """
    if isinstance(node, reader._PaintLeaf):
        return {node.state: 1.0}
    weights = {1: (0.5, 0.5), 2: (0.25, 0.25, 0.5), 3: (0.25, 0.25, 0.25, 0.25)}[node.sides]
    found: dict[int, float] = {}
    for weight, child in zip(weights, node.children, strict=True):
        for state, share in _shares(child).items():
            found[state] = found.get(state, 0.0) + weight * share
    return found


@pytest.mark.parametrize(
    ("code", "tree"),
    [
        # Eine Seite geteilt: Kinder in umgekehrter Reihenfolge im Strom —
        # children[1] ist Filament 1, children[0] Filament 2.
        ("841", reader._PaintSplit(1, 0, (reader._PaintLeaf(2), reader._PaintLeaf(1)))),
        # Drei Seiten geteilt; das erste Kind erbt, die anderen wechseln ab.
        (
            "04843",
            reader._PaintSplit(
                3,
                0,
                (
                    reader._PaintLeaf(0),
                    reader._PaintLeaf(1),
                    reader._PaintLeaf(2),
                    reader._PaintLeaf(1),
                ),
            ),
        ),
        # Ein Blatt mit erweitertem Zustand 7 (``4C``) neben einem einfachen.
        (
            "84C1",
            reader._PaintSplit(1, 0, (reader._PaintLeaf(2), reader._PaintLeaf(7))),
        ),
    ],
)
def test_split_paint_codes_decode_to_the_slicers_tree(code: str, tree: reader._PaintNode) -> None:
    assert reader._decode_paint(code) == tree


def _area_by_slot(part: reader.Part) -> dict[tuple[float, float, float], float]:
    areas = part.mesh.raw.area_faces
    found: dict[tuple[float, float, float], float] = {}
    for slot, area in zip(part.mesh.slots, areas, strict=True):
        colour = part.slots[slot].colour
        assert colour is not None
        found[colour] = found.get(colour, 0.0) + float(area)
    return found


RED = (1.0, 0.0, 0.0)
BLUE = (0.0, 0.0, 1.0)
GREEN = (0.0, 1.0, 0.0)


def test_a_triangle_painted_on_one_side_is_split_where_the_slicer_split_it() -> None:
    """``841``: Dreieck 0 der Box wird an einer Seite halbiert, die Hälften
    tragen Filament 1 und 2. Der Nachbar über der geteilten Kante bekommt
    denselben Mittelpunkt — sonst bliebe ein T-Stoß und das Netz offen.
    """
    part = reader.read_objects(_native(paint_at={0: "841"}, part_override=False))[0]
    mesh = part.mesh
    assert mesh.triangle_count == 12 - 1 + 2 + 1
    assert mesh.is_watertight
    assert mesh.volume == pytest.approx(1.0)
    assert mesh.area == pytest.approx(6.0)
    assert len(mesh.slots) == mesh.triangle_count
    assert _area_by_slot(part) == pytest.approx({RED: 5.75, BLUE: 0.25})


def test_a_triangle_split_on_three_sides_keeps_every_quarter() -> None:
    part = reader.read_objects(_native(paint_at={0: "04843"}))[0]
    mesh = part.mesh
    # Drei Kanten geteilt: drei Nachbarn bekommen je einen Mittelpunkt.
    assert mesh.triangle_count == 12 - 1 + 4 + 3
    assert mesh.is_watertight
    assert mesh.volume == pytest.approx(1.0)
    # Das Teil selbst steht auf Filament 3 (grün); das erbende Viertel auch.
    assert _area_by_slot(part) == pytest.approx({GREEN: 5.5 + 0.125, RED: 0.25, BLUE: 0.125})


@pytest.mark.parametrize(
    "code",
    [
        "5C5C5C05C5C35C5C35C5C3",
        "5C5C005C5C5C3005C0335C5C300005C5C5C35C05C00335C5C5C05C5C35C305C00330005C0035C5C5C3033",
        "05C5C05C165C25C5C5C3",
    ],
)
def test_deep_real_paint_trees_keep_shape_and_share(code: str) -> None:
    """Drei Codes aus einer Datei von MakerWorld, bis zu neun Ebenen tief.
    Volumen und Oberfläche bleiben, das Netz bleibt dicht, und die Fläche je
    Filament ist der Anteil, den der Baum vorgibt.
    """
    colours = ["#F2F2F2"] * 8
    colours[7] = "#F07316"
    payload = _changed(
        _native(paint_at={0: code, 5: code}, part_override=False),
        {writer.PROJECT_SETTINGS_PATH: json.dumps({"filament_colour": colours}).encode()},
    )
    part = reader.read_objects(payload)[0]
    mesh = part.mesh
    assert mesh.is_watertight
    assert mesh.volume == pytest.approx(1.0)
    assert mesh.area == pytest.approx(6.0)
    assert mesh.triangle_count > 12
    shares = _shares(reader._decode_paint(code))
    painted = 2 * 0.5 * shares[8]
    orange = (240 / 255, 115 / 255, 22 / 255)
    by_colour = _area_by_slot(part)
    assert by_colour[orange] == pytest.approx(painted)
    assert sum(by_colour.values()) == pytest.approx(6.0)


def test_neighbours_of_different_depth_close_along_the_shared_edge() -> None:
    """Dreieck 0 und 1 der Box liegen auf einer Seite und teilen eine Kante.
    Wird das eine dreifach, das andere gar nicht geteilt, entsteht auf der
    gemeinsamen Kante ein Punkt, den nur eine Seite kennt — der Leser
    schließt ihn. Wird das andere zusätzlich in anderer Tiefe geteilt,
    liegen auf der Kante Punkte beider Seiten, und beide werden geschlossen.
    """
    box = trimesh.creation.box()
    assert [0, 1] in box.face_adjacency.tolist()
    deep = "04843"
    # Der Strom vorwärts: die Wurzel dreifach, jedes Kind dreifach, die
    # Blätter abwechselnd — als Zeichenkette rückwärts geschrieben.
    deeper = ("3" + "34848" * 4)[::-1]
    for codes in ({0: deep}, {0: deep, 1: deeper}, {0: deeper, 1: deep}):
        part = reader.read_objects(_native(paint_at=codes, part_override=False))[0]
        assert part.mesh.is_watertight, codes
        assert part.mesh.volume == pytest.approx(1.0)
        assert part.mesh.area == pytest.approx(6.0)


def test_a_slicer_shape_entry_without_its_namespace_does_not_stop_the_import() -> None:
    """Bambu Studio und der Elegoo-Slicer schreiben ein SVG-Relief als
    ``<slic3rpe:shape …/>`` in die Modellkonfiguration, ohne den Präfix je
    zu deklarieren — sie lesen die Datei selbst ohne Namensräume. Drei von
    sechzehn Dateien aus Roberts Downloads-Ordner blieben daran hängen, und
    die Geometrie war in jeder davon vollständig.
    """
    shape = (
        '<metadata key="name" value="Relief"/>'
        '<slic3rpe:shape filepath="C:\\x.svg" filepath3mf="3D/x.svg" '
        'scale="1e-06" depth="10" transform="1 0 0 0 1 0 0 0 1 0 0 4.98" />'
    )
    payload = _native(part_extra=shape)
    parts = reader.read_objects(payload)
    assert len(parts) == 1
    assert parts[0].name == "Relief", "auch die Namen kommen aus dieser Datei"
    assert parts[0].slots[0].colour == GREEN, "der Werkzeugeintrag des Teils bleibt lesbar"
    assert reader.count_objects(payload) == 1


def test_real_extended_leaf_keeps_count_geometry_and_colour() -> None:
    """9FC aus der Taschentuchbox bedeutet Farbe 27, keine Dreiecksteilung."""
    colours = ["#F2F2F2"] * 27
    colours[26] = "#F07316"
    payload = _changed(
        _native(paint="9FC", part_override=False),
        {writer.PROJECT_SETTINGS_PATH: json.dumps({"filament_colour": colours}).encode()},
    )
    parts = reader.read_objects(payload)
    assert reader.count_objects(payload) == len(parts) == 1
    assert parts[0].mesh.triangle_count == 12
    assert parts[0].mesh.slots == (1,) * 6 + (0,) * 6
    assert parts[0].slots[1].colour == pytest.approx((240 / 255, 115 / 255, 22 / 255))
    groups = reader.read(payload, 12)
    assert groups is not None
    assert groups.slots == parts[0].mesh.slots


@pytest.mark.parametrize("tool", [-1, 32])
def test_native_writer_rejects_unrepresentable_colour_number(tool: int) -> None:
    with pytest.raises(ValidationError) as caught:
        writer._paint_code(tool)
    assert caught.value.suggestions
