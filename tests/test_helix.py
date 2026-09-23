"""Wendelerkennung: was ein Gewinde ist, und was nur so aussieht (§21.1).

Ein eingelesenes Netz sagt nicht, dass es ein Gewinde trägt. Die Erkennung
passte auf dessen Flanke ein, was sie kennt — je nach Größe einen Kegel und
zwei Zapfen, neunzehn Kegel oder zwei Kugeln, alles Merkmale, die es nicht
gibt. :mod:`app.core.perceive.helix` misst stattdessen die Wendel selbst.

Geprüft wird beides und getrennt: dass die Gewinde **gefunden** werden, mit
ihrer Steigung, und dass alles andere **nicht** gefunden wird. Der zweite Teil
ist der teurere, denn ein Fehlalarm löscht die Merkmale unter der vermeintlichen
Wendel aus dem Baum.
"""

from __future__ import annotations

import tracemalloc
from pathlib import Path

import numpy as np
import pytest
import trimesh

from app.core.bootstrap import load_operations
from app.core.geom.mesh import MeshData
from app.core.knowledge import profiles
from app.core.perceive.features import detect
from app.core.perceive.helix import Helix, find_helices
from app.core.scene import History, OperationDraft, evaluate
from app.core.scene.project import ProjectSources, new_project

#: Der Referenzkorpus. Keine dieser Dateien trägt ein Gewinde.
CORPUS = sorted((Path(__file__).parent / "data" / "meshes").glob("*.stl"))

#: Eingecheckte Gegenfälle: scharfe Kanten, scheinbar periodische Senkungen,
#: dichter Zylindermantel, Ring und getrennte Komponenten. Lokal erzeugte
#: Leistungsmodelle gehören nicht zur notwendigen Grundmenge eines Klons.
REQUIRED_CORPUS = frozenset(
    {
        "cube_clean.stl",
        "dense_cylinder.stl",
        "plate_countersunk.stl",
        "plate_countersunk_blind.stl",
        "torus_ring.stl",
        "two_components.stl",
    }
)

#: Arten, die eine Wendel verschluckt — dieselben wie in der Erkennung.
FITTED = ("hole", "pin", "cone", "sphere", "torus", "fillet")


def _built(*drafts: OperationDraft) -> MeshData:
    """Die Operationen auswerten und das Ergebnis als rohes Netz zurückgeben.

    **Über einen Umlauf durch Ecken und Dreiecke**, damit nichts von der
    Erzeugung mitreist: Was hier herauskommt, weiß so viel über sich wie eine
    eingelesene STL-Datei, nämlich nichts.
    """
    load_operations()
    project = new_project("centauri-carbon-2", "petg")
    History(project.document).apply("Probe", list(drafts))
    result = evaluate(
        project.document,
        profiles.make_profile("centauri-carbon-2", "petg"),
        sources=ProjectSources(project),
    )
    entry = next(iter(result.scene.objects.values()))
    return MeshData(
        raw=trimesh.Trimesh(
            vertices=np.asarray(entry.mesh.raw.vertices),
            faces=np.asarray(entry.mesh.raw.faces),
        )
    )


def _bolt(size: str, length: float = 12.0) -> MeshData:
    """Eine Platte mit aufgesetztem Gewindebolzen."""
    return _built(
        OperationDraft(op="create_box", params={"width": 60.0, "depth": 40.0, "height": 6.0}),
        OperationDraft(
            op="insert_printed_thread",
            inputs=("obj_1",),
            params={"size": size, "length": length, "internal": False, "z": 6.0},
        ),
    )


def test_a_thread_axis_does_not_inherit_the_sign_of_the_svd(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Zwei gültige SVD-Vorzeichen desselben Gewindes geben dieselbe Achse aus."""
    mesh = _bolt("M6")
    first = find_helices(mesh)
    assert first
    original = np.linalg.svd

    def negative_axis(*args, **kwargs):
        left, values, directions = original(*args, **kwargs)
        if directions[0, np.argmax(np.abs(directions[0]))] > 0.0:
            directions[0] *= -1.0
            left[:, 0] *= -1.0
        return left, values, directions

    monkeypatch.setattr(np.linalg, "svd", negative_axis)
    second = find_helices(mesh)

    assert len(second) == len(first)
    for before, after in zip(first, second, strict=True):
        assert after.axis[int(np.argmax(np.abs(after.axis)))] > 0.0
        np.testing.assert_allclose(after.axis, before.axis, atol=1e-12)
        assert after.pitch == pytest.approx(before.pitch)
        assert after.length == pytest.approx(before.length)
        assert after.face_indices == before.face_indices


def _tapped(size: str, core: float) -> MeshData:
    """Ein Block mit einem Kernloch und einem Innengewinde darin.

    Das Kernloch ist **Nenndurchmesser minus Steigung**, wie in der Norm. Ein
    M8 in eine Bohrung Ø 8 gesetzt schneidet fast nichts: gemessen 0,31 mm
    Rille statt 0,68 — und das zu Recht nicht als Gewinde erkannt.
    """
    return _built(
        OperationDraft(op="create_box", params={"width": 40.0, "depth": 40.0, "height": 20.0}),
        OperationDraft(op="drill_hole", inputs=("obj_1",), params={"diameter": core}),
        OperationDraft(
            op="insert_printed_thread",
            inputs=("obj_1",),
            params={"size": size, "length": 18.0, "internal": True, "at_feature": "hole_1"},
        ),
    )


def _only(helices: list[Helix]) -> Helix:
    assert len(helices) == 1, f"expected exactly one helix, got {len(helices)}"
    return helices[0]


def test_the_helix_counterexamples_are_present() -> None:
    """Fehlende Referenzdateien dürfen keine verkürzte grüne Reihe ergeben."""
    assert {path.name for path in CORPUS} >= REQUIRED_CORPUS


def test_degenerate_facets_do_not_supply_a_helix_axis() -> None:
    """Zwei flächenlose Nachbardreiecke tragen keine gültige Abschlussnormale.

    Trimesh fasst sie trotzdem als Facette zusammen. Der kurze Gewindeprüfer
    darf deren Nullvektor weder als Achse verwenden noch ein Gewinde erfinden.
    """
    from app.core.perceive.helix import _resolved_helix

    body = trimesh.Trimesh(
        vertices=[[0, 0, 0], [1, 0, 0], [2, 0, 0], [3, 0, 0], [0, 1, 0]],
        faces=[[0, 1, 2], [1, 3, 2], [0, 4, 1]],
        process=False,
    )
    edges = np.array([[0, 1], [1, 2], [2, 3], [3, 4], [4, 0]], dtype=np.int64)
    assert len(body.facets) == 1
    np.testing.assert_array_equal(body.facets_normal, [[0.0, 0.0, 0.0]])
    before = body.vertices.copy(), body.faces.copy()

    assert _resolved_helix(body, edges) is None

    np.testing.assert_array_equal(body.vertices, before[0])
    np.testing.assert_array_equal(body.faces, before[1])


def test_pitch_search_keeps_its_workspace_bounded() -> None:
    """Eine analytische Wendel braucht keine Matrix über alle Steigungen.

    Die Achse ist Z, die Steigung 1,25 mm und der Radius 3 mm. Ihre
    Konzentration ist eins. 30 003 Punkte benötigen als Koordinaten weniger
    als ein Megabyte; 32 MiB Arbeitsraum lassen reichlich Platz für die
    Suche, aber nicht für mehrere vollständige 571-mal-30-003-Matrizen.
    """
    from app.core.perceive.helix import _best_pitch

    along = np.linspace(-12.5, 12.5, 30_003)
    angle = 2.0 * np.pi * along / 1.25
    offset = np.column_stack((3.0 * np.cos(angle), 3.0 * np.sin(angle), along))
    tracemalloc.start()
    try:
        pitch, concentration, _sharpness, handedness = _best_pitch(
            offset, np.array([0.0, 0.0, 1.0]), along
        )
        _current, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()

    assert pitch == pytest.approx(1.25, abs=0.005)
    assert concentration == pytest.approx(1.0, abs=1e-12)
    assert peak < 32 * 1024 * 1024, f"pitch workspace used {peak / 1024**2:.1f} MiB"
    assert handedness == "right"


def test_cancellation_inside_pitch_search_leaves_no_recognition_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Der echte Erkennungsweg hält während der Steigungssuche kooperativ an."""
    from app.core.errors import OperationCancelled
    from app.core.perceive import features as features_module
    from app.core.perceive import helix as helix_module
    from app.core.scene.cancel import CancelSignal

    mesh = _bolt("M5")
    before = mesh.raw.vertices.copy(), mesh.raw.faces.copy()
    features_module.forget_cache()
    signal = CancelSignal()
    original = np.cos
    processed: list[int] = []

    def cancel_after_first_block(values: np.ndarray) -> np.ndarray:
        result = original(values)
        if values.ndim == 2 and values.shape[1] > 200:
            processed.append(values.shape[0])
            signal.cancel()
        return result

    with monkeypatch.context() as patch:
        patch.setattr(helix_module.np, "cos", cancel_after_first_block)
        with pytest.raises(OperationCancelled):
            detect(mesh, check_cancelled=signal.raise_if_cancelled)

    assert len(processed) == 1
    assert processed[0] < 571, "the entire pitch matrix ran before cancellation"
    assert not features_module._FEATURE_CACHE
    assert not features_module._CACHE_INDICES
    assert not features_module._FREEFORM_DROPPED
    np.testing.assert_array_equal(mesh.raw.vertices, before[0])
    np.testing.assert_array_equal(mesh.raw.faces, before[1])


@pytest.mark.parametrize(
    ("size", "length", "pitch"),
    [("M3", 12.0, 0.5), ("M4", 25.0, 0.7), ("M5", 12.0, 0.8), ("M8", 12.0, 1.25)],
)
def test_an_imported_bolt_names_its_pitch(size: str, length: float, pitch: float) -> None:
    """Die Steigung wird gemessen, nicht geraten — auf 0,01 mm."""
    helix = _only(find_helices(_bolt(size, length)))
    assert helix.pitch == pytest.approx(pitch, abs=0.02)
    assert not helix.internal
    assert helix.turns >= 5.0


def test_a_mirrored_bolt_is_measured_left_handed() -> None:
    """Die Spiegelung desselben Bolzens ist ein Linksgewinde — und wird als eines gemessen (B1).

    Bis zum 20.09.2026 setzte die Konzentration den Rechtsgang voraus: Die
    Spiegelung ergab null Wendeln, der Netz-Zwilling eines Linksgewindes
    sagte „kein Gewinde", während der exakte Leser es maß.
    """
    mesh = _bolt("M6")
    right = _only(find_helices(mesh))
    assert right.handedness == "right"
    mirrored = mesh.raw.copy()
    mirrored.apply_transform(np.diag([1.0, -1.0, 1.0, 1.0]))
    left = _only(find_helices(MeshData(raw=mirrored)))
    assert left.handedness == "left"
    assert left.pitch == pytest.approx(right.pitch, abs=1e-9)
    assert left.internal is right.internal
    assert left.diameter == pytest.approx(right.diameter, abs=1e-6)
    assert left.turns == pytest.approx(right.turns, abs=0.05)


def _printed(size: float, pitch: float, length: float, *, mirrored: bool = False) -> MeshData:
    """Das Gewinde, das diese Anwendung selbst druckt — abgeflachter Kamm, 48 Segmente je Umlauf.

    Über Ecken und Dreiecke neu aufgebaut, damit nichts vom Baustein mitreist;
    gespiegelt an der YZ-Ebene ist es dasselbe Gewinde links herum.
    """
    from app.core.knowledge.parts import build

    built = build.threaded(size, pitch, length)
    assert isinstance(built, MeshData)
    body = trimesh.Trimesh(
        vertices=np.asarray(built.raw.vertices), faces=np.asarray(built.raw.faces)
    )
    if mirrored:
        body.apply_transform(np.diag([-1.0, 1.0, 1.0, 1.0]))
    return MeshData(raw=body)


@pytest.mark.parametrize(("length", "turns"), [(8.0, 8.0), (2.5, 2.5)])
def test_the_printed_profile_is_measured_at_its_edges(length: float, turns: float) -> None:
    """Das gedruckte Gewinde misst seine Händigkeit an den Kanten, nicht am Spektrum (P2.5).

    Ein abgeflachter Kamm trägt vier Wendeln je Gang, fast gleich über die
    Periode verteilt, und im Spektrum heben sie sich nahezu auf. Am Gewinde,
    das ``build.threaded(6, 1, 8)`` baut, stand der Gipfel deshalb bei 0,98 mm
    und **links** statt rechts, die Spiegelung umgekehrt (gemessen 21.09.2026);
    mit 2,5 Umläufen fand das Spektrum gar nichts. Die Kanten sagen es genau:
    Jede trägt den Vorschub, und das Vorzeichen ihrer Steigung ist die
    Händigkeit — die Fußkanten auch im Zickzack um ihre Wendel, denn sie sind
    Schnitte der gedrehten Flanken mit dem Vieleck des Kerns.
    """
    right = _only(find_helices(_printed(6.0, 1.0, length)))
    left = _only(find_helices(_printed(6.0, 1.0, length, mirrored=True)))
    for helix, handedness in ((right, "right"), (left, "left")):
        assert helix.measured
        assert helix.handedness == handedness
        # Die Toleranzen des exakten Nachweises (``test_thread_import.py``):
        # Teilung und Vorschub 1e-4, Radien 1e-3.
        assert helix.pitch == pytest.approx(1.0, abs=1e-4)
        assert helix.lead == pytest.approx(1.0, abs=1e-4)
        assert helix.starts == 1
        assert not helix.internal
        assert helix.diameter == pytest.approx(6.0, abs=1e-3)
        assert helix.turns == pytest.approx(turns, abs=0.05)


def test_a_measured_thread_carries_its_starts_and_an_evidenced_handedness() -> None:
    """Das Merkmal trägt Vorschub, Gangzahl und Wendelabweichung — und eine belegte Richtung.

    Belegt heißt hier ``facets``: am Netz gemessen, nicht geraten. Damit sperrt
    ein Linksgewinde am Netz das Neuschneiden wie am exakten Körper
    (``types.thread_is_left_handed``) — bis dahin hieß jede Netz-Händigkeit
    ``fit`` und wurde übergangen, weil sie am gedruckten Profil falsch sein
    konnte; ein linkes Netzgewinde wurde beim *Merkmal ändern* still rechts.
    """
    from app.core.types import thread_is_left_handed

    for mirrored, handedness in ((False, "right"), (True, "left")):
        found = detect(_printed(6.0, 1.0, 8.0, mirrored=mirrored))
        threads = [feature for feature in found.values() if feature.kind == "thread"]
        assert len(threads) == 1, sorted(found)
        thread = threads[0]
        assert thread.params["handedness"] == handedness
        assert thread.measure_sources["handedness"] == "facets"
        assert thread.params["starts"] == 1
        assert thread.params["lead"] == pytest.approx(1.0, abs=1e-4)
        assert thread.params["pitch"] == pytest.approx(1.0, abs=1e-4)
        assert 0.0 <= thread.params["uncertainty"] < 1e-3
        assert thread_is_left_handed(thread) is mirrored


def _reshaped(
    mesh: MeshData, *, radial: float = 1.0, twist: float = 0.0, span: float = 0.0
) -> MeshData:
    """Dasselbe Netz, radial gestaucht und am oberen Ende verdreht — dieselben Dreiecke.

    ``radial`` staucht alle Radien um die Achse: Die Rille wird flacher, die
    Wendeln bleiben, wo sie sind. ``twist`` dreht die Ecken der obersten
    ``span`` Millimeter zunehmend um die Achse (quadratisch bis ``twist`` im
    Bogenmaß): Der Kamm verlässt dort seine Wendel wie am Auslauf eines
    gedruckten Gewindes.
    """
    vertices = np.asarray(mesh.raw.vertices, dtype=float).copy()
    vertices[:, :2] *= radial
    if twist:
        heights = vertices[:, 2]
        start = float(heights.max()) - span
        angle = np.where(heights > start, twist * ((heights - start) / span) ** 2, 0.0)
        x, y = vertices[:, 0].copy(), vertices[:, 1].copy()
        vertices[:, 0] = np.cos(angle) * x - np.sin(angle) * y
        vertices[:, 1] = np.sin(angle) * x + np.cos(angle) * y
    return MeshData(raw=trimesh.Trimesh(vertices=vertices, faces=np.asarray(mesh.raw.faces)))


def test_a_shallow_thread_is_measured_as_well() -> None:
    """Rillentiefe 0,27 Teilungen: flach wie ein Behältergewinde, und doch ein Gewinde.

    Das Fenster der Rille lag bei 0,40 bis 1,20 Teilungen — eine Grenze für die
    Tiefe aus dem Spektrum. Die Deckel des Gewürzregals aus dem Korpus liegen bei
    0,399 und blieben ungemessen, die Schraubfüße eines Besteckkorbs bei 0,315 und
    0,242 wurden gar nicht gefunden (23.09.2026). Der Kantenleser misst den
    Abstand zweier Wendeln und prüft gegen ``MEASURED_GROOVE_RANGE``.
    """
    helix = _only(find_helices(_reshaped(_printed(6.0, 1.0, 8.0), radial=0.5)))
    assert helix.measured
    assert helix.pitch == pytest.approx(1.0, abs=1e-4)
    assert helix.handedness == "right"
    assert helix.depth / helix.pitch == pytest.approx(0.27, abs=0.01)


def test_a_crest_that_runs_out_keeps_the_thread_measured() -> None:
    """Am Ende verlässt der Kamm seine Wendel — das Gewinde bleibt gemessen.

    An der Düsenbox aus dem Korpus lief der Kamm in eine Fase aus und lag dort
    0,55 mm neben seiner Wendel; die größte Abweichung über alle Kanten
    entschied, und das ganze Gewinde blieb ungemessen (23.09.2026). Hier dreht
    sich das oberste Millimeter um bis zu einem halben Bogenmaß — 0,08 mm
    Abweichung am Ende, mehr als ``MAX_FACET_SAG``.
    """
    helix = _only(find_helices(_reshaped(_printed(6.0, 1.0, 8.0), twist=0.5, span=1.0)))
    assert helix.measured
    assert helix.lead == pytest.approx(1.0, abs=1e-4)
    assert helix.turns == pytest.approx(8.0, abs=0.05)
    assert helix.uncertainty is not None and helix.uncertainty < 0.05


def test_two_strands_of_one_crest_count_their_turns_once() -> None:
    """Die zwei Kanten eines flachen Kamms überdecken dieselbe Höhe — gezählt einmal.

    Liegen sie enger als eine Wendel breit sein darf, bilden sie eine; ihre
    Winkel zusammengezählt hatte die waagrechte Düse aus dem Korpus zwölf
    Umläufe statt sechs (23.09.2026).
    """
    from app.core.perceive.helix import _covered

    strand = np.column_stack((np.arange(0.0, 6.0, 0.1), np.arange(0.1, 6.1, 0.1)))
    assert _covered(strand) == pytest.approx(6.0)
    assert _covered(np.concatenate((strand, strand + 0.02))) == pytest.approx(6.02)
    # Eine Unterbrechung zählt nicht mit.
    assert _covered(np.concatenate((strand[:20], strand[40:]))) == pytest.approx(4.0)


def test_two_helices_bridged_by_a_few_edges_are_two_and_a_coarse_one_stays_one() -> None:
    """Dicht ist eine Wendel; was dünn dazwischen liegt, verbindet keine zwei.

    Am flachen Grund der waagrechten Düse aus dem Korpus hielten rund neunzig
    Kanten zwei Randwendeln mit je 1 630 Kanten als eine Gruppe zusammen
    (23.09.2026). Eine grob vernetzte Wendel verteilt ihre Kanten dagegen
    ungleich über benachbarte Fächer und bleibt eine.
    """
    from app.core.perceive.helix import _dense_parts

    rng = np.random.default_rng(3)
    phases = np.concatenate(
        (
            0.10 + rng.normal(0.0, 0.002, 1000),
            0.42 + rng.normal(0.0, 0.002, 1000),
            np.linspace(0.12, 0.40, 60),
        )
    )
    group = np.argsort(phases)
    parts = _dense_parts(group, phases, np.ones(len(phases)), 3.0)
    assert len(parts) == 2
    first, second = sorted(parts, key=lambda part: float(phases[part].mean()))
    assert set(range(1000)) <= set(first.tolist())
    assert set(range(1000, 2000)) <= set(second.tolist())
    # Die Brücke in der Mitte gehört zu keiner: weiter als eine Wendelbreite.
    assert len(first) + len(second) < len(phases)
    uneven = np.concatenate((np.full(100, 0.300), np.full(5, 0.316), np.full(80, 0.331)))
    assert len(_dense_parts(np.arange(len(uneven)), uneven, np.ones(len(uneven)), 2.0)) == 1


@pytest.mark.parametrize(("size", "core", "pitch"), [("M5", 4.2, 0.8), ("M8", 6.8, 1.25)])
def test_a_tapped_hole_is_found_as_an_internal_thread(size: str, core: float, pitch: float) -> None:
    """Innen ist dieselbe Wendel, gespiegelt.

    Und der Unterschied wird **bestimmt**, nicht durchprobiert: Wo das Material
    liegt, sagen die Normalen. Ein Anlauf, der beide Richtungen maß und die
    nahm, die passte, gab jedem Kantenzug zwei Chancen — und ließ den Mantel
    einer Kundendatei als Innengewinde durch.
    """
    helix = _only(find_helices(_tapped(size, core)))
    assert helix.pitch == pytest.approx(pitch, abs=0.02)
    assert helix.internal
    assert helix.diameter == pytest.approx(float(size[1:]), abs=0.4)


def test_the_pitch_is_the_largest_peak_and_not_the_highest() -> None:
    """Eine Wendel konzentriert auch bei p/2 und p/3 — und manchmal stärker.

    Am M8-Innengewinde ist der Gipfel bei der halben Steigung höher als bei der
    ganzen (0,166 gegen 0,132). Wer den höchsten nimmt, meldet 0,62 mm und
    scheitert danach an der Gangtiefe, die gegen die falsche Steigung gemessen
    das Doppelte ergibt. Vielfache konzentrieren dagegen nicht: Bei 2p liegen
    aufeinanderfolgende Windungen gegenüber und heben sich auf.
    """
    helix = _only(find_helices(_tapped("M8", 6.8)))
    assert helix.pitch == pytest.approx(1.25, abs=0.02)


def test_a_short_thread_says_nothing_rather_than_something_wrong() -> None:
    """Ein kurzes Gewinde bekommt seine richtige Steigung — oder gar keine.

    Bei fünf Millimetern (vier Windungen M8) überwiegt im Spektrum der
    Auslauf: Gemessen meldete es 0,42 mm statt 1,25 — eine Zahl, die schlechter
    ist als keine (Regel 21), und deshalb stand hier bis zum 22.09.2026 ein
    leeres Ergebnis als Soll. Seit P2.5 misst der Netzleser an den Kanten:
    Jede windende Kante trägt ihren Vorschub, und der Bolzen kommt mit 1,25
    heraus. Die Zusage bleibt dieselbe, nur ihre Hälfte hat gewechselt — wer
    ein Gewinde meldet, meldet das richtige.
    """
    helices = find_helices(_bolt("M8", 5.0))
    assert helices, "vier Windungen reichen der Kantenmessung"
    helix = _only(helices)
    assert helix.measured, "an den Kanten gemessen, nicht am Spektrum geschätzt"
    assert helix.pitch == pytest.approx(1.25, abs=1e-3)
    assert helix.handedness == "right"
    assert helix.starts == 1


@pytest.mark.parametrize("path", CORPUS, ids=lambda p: p.name)
def test_no_corpus_file_carries_a_helix(path: Path) -> None:
    """Der teurere Teil: Ein Fehlalarm löscht echte Merkmale aus dem Baum.

    Zwei dieser Dateien tragen eine echte Periodizität — die gesenkten Platten
    kommen über ihre Kantenzüge auf eine Steigung. Sie scheitern an der Rille:
    Eine Senkung hat keine Gangtiefe von einer halben Steigung.
    """
    loaded = trimesh.load(path, force="mesh")
    if not isinstance(loaded, trimesh.Trimesh):
        pytest.skip("keine einzelne Netzgeometrie")
    assert find_helices(MeshData(raw=loaded)) == []


def test_a_helix_without_a_groove_is_not_a_thread() -> None:
    """Die Rille ist die Bedingung, die trägt — nicht die Periodizität.

    Und das ist gemessen, nicht behauptet: Über den Korpus, eine Kundendatei
    und die kurzen Bolzen gibt es genau **zwei** Kantenzüge, bei denen eine
    einzige Bedingung ablehnt, und beide Male ist es die Rille. Alles andere
    scheitert an mehreren zugleich.

    Der eine der beiden ist der Mantel eines Kundenmodells: eine echte Wendel
    über 22 Windungen mit konstantem Radius, bei der allein die fehlende
    Gangtiefe verhindert, dass Solidon dem Kunden ein Gewinde meldet und die
    Merkmale darunter aus dem Baum nimmt. Der andere ist dieser hier — ein
    echtes Gewinde, vierfach in die Länge gezogen. Wendel, Kamm und
    Windungszahl bleiben, die Steigung vervierfacht sich, und damit ist die
    Rille für ihre Steigung viel zu flach.

    **Ein gestrecktes und kein geglättetes Gewinde**, denn Glätten nimmt die
    scharfen Kanten mit: Der erste Anlauf stauchte die radiale Auslenkung auf
    ein Zehntel und bekam eine Fläche ohne einen einzigen Kantenzug. Der Test
    war grün und prüfte, dass ein glatter Zylinder keine scharfen Kanten hat —
    nicht, was sein Docstring versprach.
    """
    body = _bolt("M8", 25.0).raw
    stretched = np.asarray(body.vertices, dtype=float).copy()
    stretched[:, 2] *= 4.0
    tall = trimesh.Trimesh(vertices=stretched, faces=np.asarray(body.faces))

    assert find_helices(MeshData(raw=tall)) == []


def test_axial_grooves_around_a_handle_are_not_a_thread() -> None:
    """Rillen längs der Achse winden sich nicht — sie sind kein Gewinde.

    Ein Griff Ø 30, von ``apply_texture`` über die ganze Länge berippt: Die
    Ecken der Rillenkanten liegen im Takt der Vernetzung, und das Spektrum
    fand darin ein Linksgewinde mit Teilung 0,6 und Schärfe 15,6 (23.09.2026,
    am Stand davor genauso). Die Schätzung des Spektrums gilt nur noch, wo der
    Kantenleser eine Schar windender Kanten findet.
    """
    from app.core.types import SceneObject
    from tests.test_pattern_features import CIRCUMFERENCE, CYLINDER_DIAMETER, cylinder, run_op

    entry = SceneObject(id="obj_1", name="Griff", mesh=cylinder())
    out, _findings = run_op(
        "apply_texture",
        entry,
        pattern="rib",
        pitch=3.0,
        depth=0.8,
        mode="engraved",
        width=CIRCUMFERENCE,
        height=34.0,
        wrap="cylinder",
        wrap_diameter=CYLINDER_DIAMETER,
        z=0.0,
    )
    assert not find_helices(out.mesh)
    assert not [feature for feature in out.features.values() if feature.kind == "thread"]


def test_the_tree_shows_one_thread_instead_of_a_handful_of_phantoms() -> None:
    """Was der Kunde am Ende liest — über ``detect``, nicht über den Finder.

    Vorher standen an einem eingelesenen M5-Bolzen neunzehn Kegel und ein
    Zapfen im Baum, und keiner davon existiert im Teil.
    """
    found = detect(_bolt("M5", 12.0))
    threads = [f for f in found.values() if f.kind == "thread"]
    assert len(threads) == 1
    assert threads[0].params["pitch"] == pytest.approx(0.8, abs=0.02)
    assert threads[0].provenance == "detected"

    fitted = [f for f in found.values() if f.kind in FITTED]
    assert fitted == [], f"Phantome übrig: {[(f.id, f.kind) for f in fitted]}"


def test_thread_names_do_not_follow_vertex_order() -> None:
    """M5 links und M8 rechts behalten ihre Namen nach einer anderen Speicherung."""
    from app.core.perceive.features import forget_cache

    mesh = _built(
        OperationDraft(op="create_box", params={"width": 80.0, "depth": 40.0, "height": 6.0}),
        OperationDraft(
            op="insert_printed_thread",
            inputs=("obj_1",),
            params={"size": "M5", "length": 12.0, "internal": False, "z": 6.0, "x": -20.0},
        ),
        OperationDraft(
            op="insert_printed_thread",
            inputs=("obj_1",),
            params={"size": "M8", "length": 12.0, "internal": False, "z": 6.0, "x": 20.0},
        ),
    )
    for seed in (7, 11, 23):
        order = np.random.default_rng(seed).permutation(len(mesh.raw.vertices))
        inverse = np.empty_like(order)
        inverse[order] = np.arange(len(order))
        rewritten = MeshData.of(
            trimesh.Trimesh(
                vertices=mesh.raw.vertices[order], faces=inverse[mesh.raw.faces], process=False
            )
        )
        forget_cache()
        threads = {
            str(key): value for key, value in detect(rewritten).items() if value.kind == "thread"
        }
        assert set(threads) == {"thread_1", "thread_2"}
        for identifier, diameter, x in (("thread_1", 5.0, -20.0), ("thread_2", 8.0, 20.0)):
            feature = threads[identifier]
            assert feature.params["diameter"] == pytest.approx(diameter, abs=0.4), seed
            assert feature.params["centre"][0] == pytest.approx(x, abs=0.2), seed


def test_a_body_without_a_helix_keeps_every_feature() -> None:
    """Ohne Wendel ändert sich nichts — die Unterdrückung greift nur dort.

    Gegen die naheliegende Sorge: Eine gesenkte Bohrung besteht aus zwei
    koaxialen Merkmalen auf derselben Achse, und genau das sieht einem
    Gewindestapel ähnlich.
    """
    plate = MeshData(
        raw=trimesh.load(
            Path(__file__).parent / "data" / "meshes" / "plate_holes.stl", force="mesh"
        )
    )
    found = detect(plate)
    assert [f for f in found.values() if f.kind == "thread"] == []
    assert len([f for f in found.values() if f.kind == "hole"]) == 4
