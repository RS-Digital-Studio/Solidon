"""Displacement über ein Höhenfeld (Konzept P16.7, Entscheidung G).

Getrennt vom Pinsel, weil es einen anderen Charakter hat: Es ist ein **Wert**,
kein Handgriff. Ein Displacement ändert man, indem man eine Zahl ändert —
genau der Fall, für den der Stapel gemacht ist.

Es schließt an ``texture_ops`` an und ist zugleich dessen Gegenstück: Die
Texturen dort sind exakte Gitter aus gutem Grund, hier *ist* das Höhenfeld der
Zweck. Dieselbe Prüfung gilt für beide — ein Relief flacher als eine
Schichthöhe oder schmaler als die Düse wird nicht gedruckt, und das gehört
gesagt, bevor jemand eine Stunde wartet.
"""

from __future__ import annotations

import io
from pathlib import Path

import numpy as np
import pytest
import trimesh

from app.core.errors import ValidationError
from app.core.geom.displace import displaced, sample_image
from app.core.geom.mesh import MeshData
from app.core.registry import REGISTRY
from app.core.scene.cancel import NeverCancelled
from app.core.types import Feature, OpContext, OpResult, Profile, Scene, SceneObject, Source


def image_bytes(values: np.ndarray) -> bytes:
    """Ein Graustufenbild als PNG."""
    import imageio.v3 as iio

    payload = iio.imwrite("<bytes>", values.astype(np.uint8), extension=".png")
    assert isinstance(payload, bytes)
    return payload


def ramp(size: int = 64) -> bytes:
    """Ein Verlauf von schwarz nach weiß entlang der Bildbreite."""
    row = np.linspace(0, 255, size)
    return image_bytes(np.tile(row, (size, 1)))


def blocks(size: int = 64) -> bytes:
    """Halb schwarz, halb weiß — eine Stufe, deren Höhe sich ausrechnen lässt."""
    field = np.zeros((size, size))
    field[:, size // 2 :] = 255
    return image_bytes(field)


class Sources:
    """Ein Quellenspeicher, wie ihn das Projekt der Operation reicht."""

    def __init__(self, payload: bytes, name: str = "relief.png") -> None:
        self._payload = payload
        self._name = name

    def read(self, source_id: str) -> bytes:
        return self._payload

    def describe(self, source_id: str) -> Source:
        return Source(
            id=source_id, name=self._name, kind="image", checksum="", size=len(self._payload)
        )


def plate(width: float = 40.0, depth: float = 40.0, height: float = 10.0) -> MeshData:
    """Eine feine Platte — grob wäre keine Fläche zum Verschieben."""
    body = trimesh.creation.box(extents=(width, depth, height))
    body.apply_translation((0.0, 0.0, height / 2.0))
    vertices, faces = trimesh.remesh.subdivide_to_size(
        np.asarray(body.vertices, dtype=float),
        np.asarray(body.faces, dtype=np.int64),
        max_edge=1.0,
    )
    fine = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    fine.merge_vertices()
    return MeshData.of(fine)


def run(entry: SceneObject, profile: Profile, payload: bytes, **params: object) -> OpResult:
    spec = REGISTRY.get("displace_image")
    return spec.fn(
        OpContext(
            scene=Scene(objects={entry.id: entry}),
            inputs=[entry],
            params=spec.params(source="src_1", **params),
            profile=profile,
            quality="fine",
            seed=None,
            progress=lambda fraction, text: None,
            ask=lambda question, choices: choices[0],
            cancelled=NeverCancelled(),
            sources=Sources(payload),  # type: ignore[arg-type]
        )
    )


# --- das Höhenfeld selbst -------------------------------------------------------


def test_the_image_is_read_as_heights_between_zero_and_one() -> None:
    """Ein Bild ist erst einmal nur eine Zahlentabelle.

    Schwarz ist null, weiß ist eins, und was dazwischen liegt, liegt
    dazwischen — die Stärke der Operation macht daraus Millimeter.
    """
    field = sample_image(ramp())

    assert field.shape == (64, 64)
    assert field.min() == pytest.approx(0.0)
    assert field.max() == pytest.approx(1.0)
    assert field[0, 0] < field[0, -1], "der Verlauf läuft von links nach rechts"


def test_sampling_is_bilinear_between_pixels() -> None:
    """Zwischen zwei Bildpunkten wird interpoliert, nicht gerundet.

    Mit dem nächsten Nachbarn bekäme jedes Pixel eine Stufe, und aus einem
    weichen Relief würde eine Treppe mit der Auflösung des Bildes — genau der
    Vorwurf, den ``texture_ops`` an Höhenfelder richtet.
    """
    from app.core.geom.displace import at

    field = np.array([[0.0, 1.0], [0.0, 1.0]])

    assert at(field, 0.5, 0.5) == pytest.approx(0.5, abs=0.05)
    assert at(field, 0.0, 0.25) == pytest.approx(0.25, abs=0.05)


def test_an_unreadable_image_says_what_it_needs(profile: Profile) -> None:
    """Fehler als Vorschlag: Was hier ankommt, ist keine Bilddatei."""
    entry = SceneObject(id="obj_1", name="Platte", mesh=plate())

    with pytest.raises(ValidationError) as raised:
        run(entry, profile, b"kein Bild", strength=1.0)

    assert raised.value.suggestions


def test_a_wrong_call_into_imageio_is_not_a_broken_image(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``imread`` wird mit ``mode="L"`` gerufen — einem Argument, das eine
    künftige Version anders nennen kann.

    Fiele der TypeError daraus in den Handler für „je Format etwas anderes",
    bekäme der Nutzer „das ist keine Bilddatei" für ein Bild, das tadellos ist,
    und niemand suchte den Fehler im eigenen Aufruf
    (``errors.PROGRAMMING_ERRORS``).
    """
    import imageio.v3 as iio

    def wrong(*_args: object, **_kwargs: object) -> None:
        raise TypeError("imread() got an unexpected keyword argument 'mode'")

    monkeypatch.setattr(iio, "imread", wrong)

    with pytest.raises(TypeError):
        sample_image(b"was auch immer")


# --- was es mit dem Körper macht ------------------------------------------------


def test_a_ramp_lifts_one_side_more_than_the_other(profile: Profile) -> None:
    """Der Zweck, an einer Form, deren Ergebnis sich vorhersagen lässt."""
    body = plate()
    entry = SceneObject(id="obj_1", name="Platte", mesh=body)

    result = run(entry, profile, ramp(), strength=2.0, projection="planar")

    after = result.outputs[0].mesh
    assert after.volume > body.volume, "ein Relief trägt auf"
    assert after.triangle_count == body.triangle_count, "die Topologie bleibt"
    assert after.is_watertight


def test_strength_is_the_height_of_the_relief(profile: Profile) -> None:
    """Die Stärke ist ein Maß in Millimetern und keine Geschmacksangabe.

    Eine Stufe von schwarz auf weiß, zwei Millimeter stark: Der Unterschied
    zwischen der tiefsten und der höchsten Stelle der Oberseite *ist* die
    Stärke.
    """
    body = plate()
    entry = SceneObject(id="obj_1", name="Platte", mesh=body)

    result = run(entry, profile, blocks(), strength=2.0, projection="planar")

    after = result.outputs[0].mesh
    top = float(after.raw.bounds[1][2])
    assert top == pytest.approx(float(body.raw.bounds[1][2]) + 2.0, abs=0.2)


def test_zero_strength_leaves_the_body_alone(profile: Profile) -> None:
    """Der Nullpunkt — sonst wäre jede Messung darüber ohne Bezug."""
    body = plate()
    entry = SceneObject(id="obj_1", name="Platte", mesh=body)

    result = run(entry, profile, ramp(), strength=0.0)

    assert result.outputs[0].mesh.volume == pytest.approx(body.volume, rel=1e-9)


def test_the_middle_decides_what_is_up_and_what_is_down(profile: Profile) -> None:
    """Der Mittelwert legt fest, welcher Grauwert die Fläche in Ruhe lässt.

    Bei 0,5 hebt weiß und senkt schwarz — ein Relief, das um die Ausgangsfläche
    herum schwingt, statt nur aufzutragen. Das ist der Unterschied zwischen
    einem Stempel und einer Prägung.
    """
    body = plate()
    entry = SceneObject(id="obj_1", name="Platte", mesh=body)

    lifted = run(entry, profile, blocks(), strength=2.0, middle=0.0).outputs[0].mesh
    both = run(entry, profile, blocks(), strength=2.0, middle=0.5).outputs[0].mesh

    # Ohne Nulllage trägt jeder Grauwert auf, und der Körper wird größer. Mit
    # 0,5 hebt weiß und senkt schwarz — er bleibt im Mittel, wo er war.
    # Gemessen am Volumen, nicht an einer Kante. Das Relief wirkt von oben,
    # also auf der Oberseite; die Unterseite bleibt auf dem Bett.
    assert lifted.volume > body.volume
    assert abs(both.volume - body.volume) < abs(lifted.volume - body.volume)


def test_evaluating_twice_gives_the_same_body(profile: Profile) -> None:
    """Zweimal auswerten muss identisch sein."""
    entry = SceneObject(id="obj_1", name="Platte", mesh=plate())

    once = run(entry, profile, ramp(), strength=1.0)
    twice = run(entry, profile, ramp(), strength=1.0)

    assert np.array_equal(
        np.asarray(once.outputs[0].mesh.raw.vertices),
        np.asarray(twice.outputs[0].mesh.raw.vertices),
    )


# --- was der Drucker davon hält -------------------------------------------------


def test_a_relief_below_a_layer_height_is_reported(profile: Profile) -> None:
    """Dieselbe Prüfung wie bei den Texturen (E1 dort).

    Ein Relief, das flacher ist als eine Schicht, kommt nicht aus dem Drucker —
    und das ist nichts, was man am Bildschirm sieht.
    """
    entry = SceneObject(id="obj_1", name="Platte", mesh=plate())

    result = run(entry, profile, ramp(), strength=0.05)

    assert "displace.too_shallow" in {finding.code for finding in result.findings}


def test_a_relief_deep_enough_stays_quiet(profile: Profile) -> None:
    """Die Gegenprobe — sonst warnt jedes Relief und keine Warnung zählt."""
    entry = SceneObject(id="obj_1", name="Platte", mesh=plate())

    result = run(entry, profile, ramp(), strength=2.0)

    assert "displace.too_shallow" not in {finding.code for finding in result.findings}


def test_a_mesh_too_coarse_for_the_image_is_reported(profile: Profile) -> None:
    """Dieselbe Vorbedingung wie beim Pinsel (Entscheidung E).

    Ein Höhenfeld mit 64 Bildpunkten auf einem Netz mit zwölf Dreiecken hat
    nichts, woran es sich zeigen könnte. Das Ergebnis wäre nicht falsch,
    sondern leer — und niemand wüsste warum.
    """
    coarse = MeshData.of(trimesh.creation.box(extents=(40.0, 40.0, 10.0)))
    entry = SceneObject(id="obj_1", name="Klotz", mesh=coarse)

    result = run(entry, profile, ramp(), strength=2.0)

    assert "displace.too_coarse" in {finding.code for finding in result.findings}


# --- die Projektionen -----------------------------------------------------------


def test_every_projection_leaves_a_closed_body(profile: Profile) -> None:
    """Drei Arten, ein Bild auf einen Körper zu legen — keine darf ihn öffnen."""
    entry = SceneObject(id="obj_1", name="Platte", mesh=plate())

    for projection in ("planar", "cylindrical", "spherical"):
        result = run(entry, profile, ramp(), strength=1.0, projection=projection)
        after = result.outputs[0].mesh
        assert after.is_watertight, f"{projection} hat das Netz geöffnet"
        assert after.triangle_count == entry.mesh.triangle_count


def test_a_cylindrical_projection_wraps_around(profile: Profile) -> None:
    """Zylindrisch heißt: Das Bild läuft einmal um die Achse.

    An einem Rohr ist das die einzige Projektion, die keine Naht mit doppeltem
    Relief hinterlässt.
    """
    from app.core.geom.mesh_ops import remesh

    # Über ``remesh`` und nicht über ``subdivide_to_size`` direkt: Letzteres
    # lässt an der Naht zwischen verschieden oft geteilten Flächen einen Punkt
    # auf einer Kante liegen, die ihn nicht kennt — das Rohr war schon vor dem
    # Relief offen, und der Test hätte das dem Relief angelastet.
    tube = MeshData.of(trimesh.creation.cylinder(radius=10.0, height=30.0, sections=64))
    fine = remesh(tube, 1.0)
    assert fine.is_watertight, "die Vorlage ist zu, sonst prüft der Test das Falsche"
    entry = SceneObject(id="obj_1", name="Rohr", mesh=fine)

    result = run(entry, profile, blocks(), strength=1.5, projection="cylindrical")

    after = result.outputs[0].mesh
    assert after.is_watertight
    assert after.volume > fine.volume


def test_the_image_travels_in_the_project(profile: Profile) -> None:
    """Regel 12: keine absoluten Pfade in Projektdateien.

    Das Bild reist als Quelle mit, nicht als Verweis — sonst öffnet das Projekt
    auf einem anderen Rechner ohne sein Relief. Geprüft wird, dass die
    Operation nichts anderes als die Quellenkennung braucht.
    """
    spec = REGISTRY.get("displace_image")
    entry = next(item for item in spec.params.spec() if item.name == "source")

    assert entry.kind == "image", (
        "eine Quellenkennung, und zwar die eines Bildes — ein source-Feld bot "
        "jede Quelle an, also STLs in einem Feld namens Bild"
    )


def test_the_agent_may_set_the_numbers(profile: Profile) -> None:
    """Anders als beim Pinsel: Hier gibt es keine Koordinaten zu erfinden.

    Ein Displacement ist ein Wert, und Werte darf der Agent setzen
    (Leitprinzip 5 verbietet ihm Koordinaten, nicht Zahlen).
    """
    from app.core.registry import json_schema

    schema = json_schema(REGISTRY.get("displace_image").params)

    assert "strength" in schema["properties"]
    assert "projection" in schema["properties"]


def test_displacing_without_an_image_says_so(profile: Profile) -> None:
    """Eine Operation ohne Quelle ist kein Absturz, sondern eine Frage."""
    entry = SceneObject(id="obj_1", name="Platte", mesh=plate())

    with pytest.raises(ValidationError) as raised:
        run(entry, profile, b"", strength=1.0)

    assert raised.value.suggestions


def test_the_helper_takes_a_mesh_and_a_field() -> None:
    """Der Kern ohne Operation herum — dieselbe Rechnung, direkt prüfbar."""
    body = plate()
    field = sample_image(blocks())

    lifted = displaced(body, field, strength=2.0, projection="planar", middle=0.0, smooth=0)

    assert lifted.volume > body.volume
    assert io is not None  # der Import oben gehört zum Bilderzeugen


# --- auf eine erkannte Fläche ---------------------------------------------------


def slanted() -> tuple[MeshData, Feature]:
    """Eine schräge Platte mit ihrer Fläche als erkanntes Merkmal.

    Schräg mit Absicht: Auf einer waagerechten Fläche gäbe „von oben"
    dasselbe Ergebnis, und der Test bewiese nichts.
    """
    body = plate(40.0, 40.0, 6.0)
    tilted = body.raw.copy()
    tilted.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 6.0, [0, 1, 0]))
    normal = np.asarray([np.sin(np.pi / 6.0), 0.0, np.cos(np.pi / 6.0)])
    # Wie die Erkennung sie liefert: mit ihren Dreiecken und der Mitte auf der
    # Fläche. Bis zum 22.09.2026 stand hier die Mitte des Hüllquaders und kein
    # Dreieck — die Projektion las die Fläche damals gar nicht, sie verschob
    # jeden Eckpunkt des Körpers.
    top = np.flatnonzero(tilted.face_normals @ normal > 0.999)
    face = Feature(
        id="face_1",
        kind="face",
        provenance="detected",
        params={
            "area": 1600.0,
            "normal": tuple(float(value) for value in normal),
            "centre": tuple(float(value) for value in tilted.triangles_center[top].mean(axis=0)),
        },
        face_indices=tuple(int(index) for index in top),
    )
    return MeshData.of(tilted), face


def test_a_relief_can_sit_on_a_detected_face(profile: Profile) -> None:
    """Die vierte Projektion: das Bild liegt so auf, wie es aussähe, wenn man
    senkrecht auf die Fläche sieht.

    Auf einer schrägen Fläche ist das die einzige Art, die nicht verzerrt —
    „von oben" staucht sie um den Kosinus ihrer Neigung.
    """
    body, face = slanted()
    entry = SceneObject(id="obj_1", name="Platte", mesh=body, features={"face_1": face})

    result = run(entry, profile, ramp(), strength=1.5, projection="face", at_feature="face_1")

    after = result.outputs[0].mesh
    assert after.volume > body.volume
    assert after.is_watertight
    assert after.triangle_count == body.triangle_count


def test_the_face_projection_differs_from_looking_down(profile: Profile) -> None:
    """Sonst wäre die vierte Art eine Zeile Code für nichts."""
    body, face = slanted()
    entry = SceneObject(id="obj_1", name="Platte", mesh=body, features={"face_1": face})

    flat = run(entry, profile, ramp(), strength=1.5, projection="planar")
    on_face = run(entry, profile, ramp(), strength=1.5, projection="face", at_feature="face_1")

    assert not np.allclose(
        np.asarray(flat.outputs[0].mesh.raw.vertices),
        np.asarray(on_face.outputs[0].mesh.raw.vertices),
    )


def test_a_relief_on_a_face_stays_on_that_face(profile: Profile) -> None:
    """Auf eine Fläche gelegt heißt: auf diese eine, und nirgends sonst.

    Bis zum 22.09.2026 rechnete die Projektion „Auf eine Fläche" nur die
    **Bildlage** aus der Fläche und verschob dann jeden Eckpunkt des Körpers
    entlang seiner Normalen — die Rückseite der Platte trug dasselbe Relief
    gespiegelt, die Seiten wuchsen mit (gemessen an einer Platte 40 x 40 x 6:
    4 256 von 4 353 Eckpunkten der Unterseite bewegt). Jetzt wandern nur die
    Eckpunkte der gewählten Fläche, und zwar entlang ihrer Normalen.
    """
    body = plate(40.0, 40.0, 6.0)
    raw = body.raw
    top = np.flatnonzero(raw.face_normals[:, 2] > 0.99)
    face = Feature(
        id="face_1",
        kind="face",
        provenance="detected",
        params={"area": 1600.0, "normal": (0.0, 0.0, 1.0), "centre": (0.0, 0.0, 6.0)},
        face_indices=tuple(int(index) for index in top),
    )
    entry = SceneObject(id="obj_1", name="Platte", mesh=body, features={"face_1": face})

    after = run(entry, profile, ramp(), strength=1.5, projection="face", at_feature="face_1")

    moved = np.linalg.norm(after.outputs[0].mesh.raw.vertices - raw.vertices, axis=1)
    on_face = np.zeros(len(raw.vertices), dtype=bool)
    on_face[np.unique(raw.faces[top])] = True
    assert moved[on_face].max() > 1.0, "die Fläche trägt das Relief"
    assert moved[~on_face].max() == 0.0, "sonst bewegt sich nichts"
    shift = after.outputs[0].mesh.raw.vertices[on_face] - raw.vertices[on_face]
    assert np.allclose(shift[:, :2], 0.0), "entlang der Normalen der Fläche, nicht schräg"


def test_a_relief_from_above_leaves_the_underside_on_the_bed(profile: Profile) -> None:
    """„Von oben" heißt: was nach oben schaut, und in der Höhe.

    Bis zum 22.09.2026 wanderte jeder Eckpunkt entlang seiner Normalen, auch
    die der Unterseite — mit demselben Bild, nach unten. Eine Platte mit
    Relief stand danach nicht mehr eben auf dem Bett (Unterseite bis 0,98 mm
    unter null bei einem Relief von einem Millimeter), und die Oberkante
    wanderte schräg nach außen, weil die Normale an der Kante diagonal steht.
    """
    body = plate(40.0, 40.0, 6.0)
    raw = body.raw
    entry = SceneObject(id="obj_1", name="Platte", mesh=body)

    after = run(entry, profile, blocks(), strength=1.0, projection="planar").outputs[0].mesh

    bottom = raw.vertices[:, 2] < 1e-9
    assert np.array_equal(after.raw.vertices[bottom], raw.vertices[bottom]), "die Unterseite bleibt"
    shift = after.raw.vertices - raw.vertices
    assert np.allclose(shift[:, :2], 0.0), "von oben heißt senkrecht, nicht entlang der Normalen"
    assert after.raw.bounds[0] == pytest.approx(raw.bounds[0])


def test_a_relief_around_the_axis_keeps_the_ends_flat(profile: Profile) -> None:
    """Um die Achse gewickelt trägt der Mantel das Bild — nicht die Stirnflächen.

    Die Deckel eines Rohrs schauen entlang der Achse; bis zum 22.09.2026
    wurden auch sie entlang ihrer Normalen mit dem Bild verschoben, und das
    Rohr stand danach auf einem Relief statt auf seiner Stirnfläche.
    """
    from app.core.geom.mesh_ops import remesh

    tube = remesh(
        MeshData.of(trimesh.creation.cylinder(radius=10.0, height=30.0, sections=64)), 1.0
    )
    entry = SceneObject(id="obj_1", name="Rohr", mesh=tube)

    after = run(entry, profile, blocks(), strength=1.5, projection="cylindrical").outputs[0].mesh

    ends = np.abs(np.abs(tube.raw.vertices[:, 2]) - 15.0) < 1e-9
    assert np.allclose(after.raw.vertices[ends, 2], tube.raw.vertices[ends, 2]), (
        "die Enden bleiben eben"
    )
    shift = after.raw.vertices - tube.raw.vertices
    assert np.allclose(shift[:, 2], 0.0), "gewickelt heißt quer zur Achse"
    assert after.is_watertight


def test_the_face_projection_without_a_face_says_so(profile: Profile) -> None:
    """Kein stilles Ausweichen auf „von oben".

    Das Ergebnis sähe fast richtig aus und läge auf der falschen Ebene — die
    Sorte Fehler, die man erst am gedruckten Teil bemerkt.
    """
    body, face = slanted()
    entry = SceneObject(id="obj_1", name="Platte", mesh=body, features={"face_1": face})

    with pytest.raises(ValidationError) as raised:
        run(entry, profile, ramp(), strength=1.5, projection="face")

    assert raised.value.suggestions
    assert raised.value.constraint == "required"


def test_a_face_frame_survives_any_normal() -> None:
    """Der Hilfsvektor darf nirgends parallel zur Flächennormale liegen.

    Derselbe Griff wie beim Pinselring: die schwächste Achse der Normale. Ein
    fester Startvektor wäre an jeder achsparallelen Fläche entartet — und das
    sind die häufigsten.
    """
    from app.core.geom.displace import _face_frame

    for axis in ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0), (0.0, 0.0, -1.0)):
        feature = Feature(id="face_1", kind="face", provenance="detected", params={"normal": axis})
        first, second, _centre = _face_frame(feature)
        assert np.isfinite(first).all() and np.isfinite(second).all()
        assert abs(float(np.dot(first, second))) < 1e-9, "die beiden stehen senkrecht"
        assert abs(float(np.dot(first, np.asarray(axis)))) < 1e-9, "und beide in der Ebene"


def test_two_projects_with_different_images_never_share_a_cached_relief(
    tmp_path: Path, profile: Profile
) -> None:
    """Gesamtreview 05.09.2026, CORE-11: Zwei Projekte, gleiche Quader, gleiche
    Reliefoperation, je ein Bild namens ``src_1`` — aber verschiedene Bilder.
    Der Cache-Schlüssel kannte die Inhaltsprüfsumme nur für ``kind="source"``,
    und das Bild reist als ``kind="image"``: Das zweite Projekt bekam über den
    Plattencache das Relief des ersten, mit ``complete=True``. Der Fehler
    überlebte das Leeren des Sitzungscaches, weil die Platte länger lebt."""
    from app.core.bootstrap import load_operations
    from app.core.geom.mesh import MeshCodec
    from app.core.scene import History, OperationDraft, evaluate
    from app.core.scene.cache import DiskCache, ResultCache
    from app.core.scene.project import Project, ProjectSources, new_project

    load_operations()

    def project_for(values: np.ndarray) -> Project:
        project = new_project("centauri-carbon-2", "petg")
        project.document.sources["src_1"] = Source(
            id="src_1", kind="image", path="sources/relief.png", sha256=""
        )
        project.sources["src_1"] = image_bytes(values)
        History(project.document).apply(
            "Relief",
            [
                OperationDraft(op="create_box"),
                OperationDraft(
                    op="displace_image",
                    inputs=("obj_1",),
                    params={"source": "src_1", "strength": 2.0, "smooth": 0},
                ),
            ],
        )
        return project

    bright = project_for(np.array([[0.0, 1.0], [0.0, 1.0]]))
    flat = project_for(np.zeros((2, 2)))
    disk = DiskCache(codec=MeshCodec(), directory=tmp_path / "cache")

    first = evaluate(
        bright.document,
        profile,
        sources=ProjectSources(bright),
        cache=ResultCache(disk=disk),
    )
    cached = evaluate(
        flat.document,
        profile,
        sources=ProjectSources(flat),
        cache=ResultCache(disk=disk),
    )
    fresh = evaluate(flat.document, profile, sources=ProjectSources(flat))

    assert first.complete and cached.complete and fresh.complete
    volume = cached.scene.objects["obj_1"].mesh.volume
    assert volume == pytest.approx(fresh.scene.objects["obj_1"].mesh.volume), (
        "mit Plattencache dasselbe wie ohne"
    )
    assert volume != pytest.approx(first.scene.objects["obj_1"].mesh.volume), (
        "das zweite Projekt bekam das Relief des ersten"
    )
