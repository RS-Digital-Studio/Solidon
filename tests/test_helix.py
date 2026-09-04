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
    """Unter etwa sieben Windungen ist die Steigung nicht mehr abzulesen.

    Bei fünf Millimetern überwiegt der Auslauf. Gemessen meldete ein solcher
    Bolzen ohne diese Grenze 0,42 mm statt 1,25 — eine Zahl, die schlechter
    ist als keine (Regel 21).
    """
    assert find_helices(_bolt("M8", 5.0)) == []


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
