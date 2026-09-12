"""Nachbarschaften zwischen Merkmalen: was zusammengehört (§21.1, §21.2).

Die Erkennung einzelner Merkmale prüft ``test_features.py``. Hier steht die
Frage danach: Gehören zwei davon zusammen, und was folgt daraus?
"""

from __future__ import annotations

import dataclasses
import math
from pathlib import Path

import trimesh

from app.core.geom.mesh import MeshData, read_mesh
from app.core.ingest.loader import normalise
from app.core.perceive.features import detect
from app.core.perceive.relations import (
    SLEEVE_OVERLAP,
    Sleeve,
    bore_and_widening_at,
    sleeve_at,
)
from app.core.types import Feature, is_a_cavity

MESHES = Path(__file__).parent / "data" / "meshes"


def _corpus(name: str) -> MeshData:
    return normalise(read_mesh((MESHES / name).read_bytes(), ".stl"), "mm").mesh


def _tube() -> MeshData:
    """Ein Rohr mit 6 mm Wand — Ø 16 innen, Ø 28 außen, 20 hoch.

    Derselbe Prüfkörper, mit dem ``test_features.py`` festhält, dass ein
    Zapfen keine Senkung ist. Er trägt beide Merkmale und ist damit der
    kleinste Körper, an dem die Frage überhaupt entsteht.
    """
    return MeshData.of(trimesh.creation.annulus(r_min=8.0, r_max=14.0, height=20.0, sections=96))


def test_a_bore_inside_material_is_a_sleeve() -> None:
    """Die Wand steht in keinem der beiden Merkmale — sie entsteht aus beiden."""
    features = detect(_tube())
    bore = next(f for f in features.values() if f.kind == "hole")
    found = sleeve_at(bore, features)

    assert found is not None, "die Bohrung im Zapfen findet ihre Wand nicht"
    assert found.bore == bore.id
    assert abs(found.thickness - 6.0) < 0.1, (
        f"Wand {found.thickness:.3f} mm statt 6,0 — (28 − 16) / 2"
    )
    assert found.overlap > 0.9, f"Überdeckung {found.overlap:.2f}, erwartet nahe 1"


def test_the_sleeve_answers_from_both_sides() -> None:
    """Der Kunde klickt auf die Bohrung **oder** auf den Zapfen.

    Eine Auskunft, die nur eine der beiden Richtungen kennt, ist an der
    anderen Hälfte der Klicks stumm — und beide stehen im Objektbaum.
    """
    features = detect(_tube())
    bore = next(f for f in features.values() if f.kind == "hole")
    pin = next(f for f in features.values() if f.kind == "pin")

    from_inside = sleeve_at(bore, features)
    from_outside = sleeve_at(pin, features)

    assert from_inside == from_outside, (
        f"von innen {from_inside}, von außen {from_outside} — dasselbe Rohr"
    )


def test_the_sleeve_uses_the_same_axis_tolerance_from_both_sides() -> None:
    """Die Auswahlseite darf die geometrische Beziehung nicht verändern."""
    features = detect(_tube())
    bore = next(f for f in features.values() if f.kind == "hole")
    pin = next(f for f in features.values() if f.kind == "pin")
    centre = tuple(float(value) for value in pin.params["centre"])
    shifted = dataclasses.replace(
        pin,
        params={**pin.params, "centre": (centre[0] + 2.5, centre[1], centre[2])},
    )
    shifted_features = {**features, pin.id: shifted}

    from_inside = sleeve_at(bore, shifted_features)
    from_outside = sleeve_at(shifted, shifted_features)

    assert from_inside == from_outside


def test_the_sleeve_uses_the_bore_axis_from_both_sides() -> None:
    """Auch innerhalb der Winkelschwelle darf die Aufrufseite die Überdeckung nicht ändern."""
    angle = math.radians(1.9)
    bore = Feature(
        id="bore",
        kind="hole",
        provenance="recognised",
        params={
            "diameter": 16.0,
            "depth": 20.0,
            "centre": (0.0, 0.0, 0.0),
            "axis": (0.0, 0.0, 1.0),
        },
    )
    wall = Feature(
        id="wall",
        kind="pin",
        provenance="recognised",
        params={
            "diameter": 28.0,
            "depth": 20.0,
            "centre": (2.0, 0.0, 9.97),
            "axis": (math.sin(angle), 0.0, math.cos(angle)),
        },
    )
    features = {bore.id: bore, wall.id: wall}

    from_inside = sleeve_at(bore, features)
    from_outside = sleeve_at(wall, features)

    assert from_inside is not None, "entlang der Bohrungsachse überdeckt sich das Paar knapp"
    assert from_inside == from_outside


def test_a_post_above_a_bore_is_not_a_sleeve() -> None:
    """Die Gegenprobe zu :data:`SLEEVE_OVERLAP`, und sie ist eigens gebaut.

    Eine Platte mit Sackloch Ø 16 auf fünf Millimetern, darauf auf derselben
    Achse ein Zapfen Ø 28. Vier der fünf Bedingungen treffen zu — gleiche
    Achse, Mitten auf einer Linie, der Zapfen weiter, genau einer ein
    Hohlraum. Er umgibt die Bohrung trotzdem nicht: Zwischen beiden liegen
    fünf Millimeter massives Material.

    **Der Prüfkörper ist eigens dafür gebaut, und das ist der Punkt.** Der
    erste Anlauf nahm die Senkungen des Korpus, und mit ausgebauter Bedingung
    blieb er grün — eine Senkung führt gar keine ``depth`` und scheidet eine
    Bedingung früher aus. Ein Test, der eine Mutation überlebt, prüft die
    Zeile nicht, die er zu prüfen glaubt.
    """
    plate = trimesh.creation.box(extents=[60.0, 60.0, 10.0])
    plate.apply_translation([0.0, 0.0, 5.0])
    bore = trimesh.creation.cylinder(radius=8.0, height=12.0, sections=96)
    bore.apply_translation([0.0, 0.0, -1.0])
    post = trimesh.creation.cylinder(radius=14.0, height=10.0, sections=96)
    post.apply_translation([0.0, 0.0, 15.0])
    body = trimesh.boolean.union([trimesh.boolean.difference([plate, bore]), post])

    features = detect(MeshData.of(body))
    bores = [f for f in features.values() if f.kind == "hole"]
    posts = [f for f in features.values() if f.kind == "pin"]
    assert bores and posts, (
        f"der Prüfkörper trägt nicht beides — Bohrungen {[b.id for b in bores]}, "
        f"Zapfen {[p.id for p in posts]}; dann prüft der Test nichts"
    )

    for feature in features.values():
        assert sleeve_at(feature, features) is None, (
            f"{feature.id}: der Zapfen über der Bohrung gilt als ihre Wand"
        )


def test_a_countersink_is_not_a_sleeve() -> None:
    """Und die Senkung ebenso wenig — sie scheitert an der fehlenden Tiefe.

    Steht hier neben der Gegenprobe darüber und nicht an ihrer Stelle: Beide
    Fälle sind echt, sie scheiden nur an verschiedenen Bedingungen aus. Wer
    eine davon streicht, verliert die Zusage für den anderen nicht mit.
    """
    for name in ("plate_countersunk.stl", "plate_countersunk_blind.stl"):
        features = detect(_corpus(name))
        found = {
            feature.id: sleeve_at(feature, features)
            for feature in features.values()
            if sleeve_at(feature, features) is not None
        }
        assert not found, f"{name}: Senkung als Rohr gelesen — {found}"


def test_a_bore_and_its_countersink_answer_from_both_sides() -> None:
    """Bohrung und Senkung bleiben ein Paar, gleich welche Seite gewählt ist.

    Der Objektbaum zeigt die Senkung unter ihrer Bohrung. Eine Operation darf
    dieselbe Beziehung deshalb nicht nur von der Bohrung aus kennen: Im
    Merkmalsfenster lassen sich beide Zeilen anklicken.
    """
    features = detect(_corpus("plate_countersunk.stl"))
    bore = next(feature for feature in features.values() if feature.kind == "hole")
    widening = next(feature for feature in features.values() if feature.kind == "cone")

    expected = (bore, widening)
    assert bore_and_widening_at(bore, features) == expected
    assert bore_and_widening_at(widening, features) == expected


def test_plain_bores_have_no_wall_to_speak_of() -> None:
    """Vier Bohrungen in einer Platte sind vier Bohrungen.

    Kein Zapfen umgibt sie, also gibt es nichts zu melden. Ein Befund an dieser
    Stelle wäre der teuerste Fehler dieser Auskunft: Sie liefe an jedem
    gebohrten Teil an und sagte nichts.
    """
    features = detect(_corpus("plate_holes.stl"))
    for feature in features.values():
        assert sleeve_at(feature, features) is None, f"{feature.id} hat angeblich eine Wand"


def test_the_thinnest_wall_wins() -> None:
    """Ein Rohr im Rohr: gemeldet wird die Wand, die als Erste zu dünn wird.

    Ein abgesetztes Rohr: Bohrung Ø 16 durch 30 mm, außen unten Ø 60 auf zehn
    Millimetern und oben Ø 28 auf zwanzig. Um dieselbe Bohrung stehen damit
    zwei Hüllen — 22 mm Wand unten, 6 mm oben. Welche von beiden die Antwort
    ist, darf nicht von der Reihenfolge im Verzeichnis abhängen.

    Zwei getrennte Ringe taugen dafür nicht: Sie sind zwei Komponenten, die
    Erkennung nimmt eine davon, und der Prüfkörper trüge gar keine Bohrung
    mehr — der erste Anlauf war genau deshalb rot.
    """
    low = trimesh.creation.annulus(r_min=8.0, r_max=30.0, height=10.0, sections=96)
    low.apply_translation([0.0, 0.0, -5.0])
    high = trimesh.creation.annulus(r_min=8.0, r_max=14.0, height=20.0, sections=96)
    high.apply_translation([0.0, 0.0, 10.0])
    features = detect(MeshData.of(trimesh.util.concatenate([low, high])))
    bores = [f for f in features.values() if f.kind == "hole"]
    assert bores, "der Prüfkörper trägt keine Bohrung — dann prüft der Test nichts"
    assert len([f for f in features.values() if f.kind == "pin"]) == 2, (
        "der Prüfkörper trägt nicht zwei Hüllen — dann gibt es nichts zu wählen"
    )

    found = sleeve_at(bores[0], features)
    assert found is not None, "die Bohrung findet keine Wand"
    assert abs(found.thickness - 6.0) < 0.1, (
        f"Wand {found.thickness:.2f} mm — erwartet 6,0, die dünnere der beiden"
    )


def test_the_overlap_is_what_separates_the_two_cases() -> None:
    """Die Schwelle liegt zwischen den Fällen, nicht auf einem von ihnen.

    Ein Wert, den die Wirklichkeit knapp verfehlt, ist eine Zahl auf Abruf.
    Gemessen: Das Rohr überdeckt zu 1,0, die Senkung zu 0,0 — die Schwelle darf
    dazwischen stehen, wo sie will, und keiner der beiden Fälle wandert.
    """
    assert 0.0 < SLEEVE_OVERLAP < 1.0

    features = detect(_tube())
    bore = next(f for f in features.values() if f.kind == "hole")
    found = sleeve_at(bore, features)
    assert isinstance(found, Sleeve)
    assert found.overlap - SLEEVE_OVERLAP > 0.4, (
        f"Überdeckung {found.overlap:.2f} liegt zu nah an der Schwelle {SLEEVE_OVERLAP}"
    )


def test_each_condition_of_the_sleeve_rule_separates_something() -> None:
    """Jede der sechs Bedingungen trennt einen Fall — einzeln nachgewiesen.

    **Der Anlass ist eine Messung, nicht die Vorsicht.** Die vier Tests
    darüber halten das Rohr fest, und trotzdem blieben fünf der sechs
    Bedingungen grün, als ich sie einzeln herausnahm: Ein Prüfkörper mit genau
    einem Paar aus Bohrung und Zapfen hat nur einen Kandidaten, und bei einem
    einzigen findet ihn jede Bedingung — gleich welche man streicht. Der
    Docstring von :func:`sleeve_at` behauptete sechs gemessene Bedingungen,
    gemessen war eine. (Dieselbe Lücke fand 3d-druck-f9 zur selben Stunde in
    ``widening_at_the_mouth``, von der anderen Seite.)

    Ausgegangen wird deshalb vom echten Rohr, und je Durchgang wird **genau
    ein Wert** des Zapfens abgewandelt. Was danach noch als Wand gemeldet
    wird, ist eine Bedingung, die nichts tut.
    """
    features = detect(_tube())
    bore = next(f for f in features.values() if f.kind == "hole")
    pin = next(f for f in features.values() if f.kind == "pin")
    assert sleeve_at(bore, features) is not None, (
        "der Ausgangsfall ist kein Rohr — dann prüft der Test nichts"
    )

    abwandlungen = {
        "Achse gekippt": dataclasses.replace(pin, params={**pin.params, "axis": (0.0, 0.35, 0.94)}),
        "quer daneben": dataclasses.replace(pin, params={**pin.params, "centre": (9.0, 0.0, 0.0)}),
        "längs weit weg": dataclasses.replace(
            pin, params={**pin.params, "centre": (0.0, 0.0, 40.0)}
        ),
        "enger als die Bohrung": dataclasses.replace(pin, params={**pin.params, "diameter": 12.0}),
        "selbst ein Hohlraum": dataclasses.replace(pin, kind="hole"),
    }

    for was, abgewandelt in abwandlungen.items():
        geändert = {**features, pin.id: abgewandelt}
        von_innen = sleeve_at(geändert[bore.id], geändert)
        von_außen = sleeve_at(abgewandelt, geändert)
        assert von_innen is None, f"{was}: von der Bohrung aus gilt es weiter als Rohr"
        assert von_außen is None, f"{was}: vom Zapfen aus gilt es weiter als Rohr"


def _merkmal(kind: str, **params: object) -> Feature:
    """Ein Merkmal ohne Netz — für die Fragen, die nur Art und Werte lesen."""
    return Feature(id=f"{kind}_1", kind=kind, provenance="detected", params=params)


def test_hole_and_pin_answer_without_recess_and_cone_and_sphere_with_it() -> None:
    """Hohlraum oder Materie — vier Arten, eine Antwortquelle.

    ``hole`` ist immer ein Hohlraum, ``pin`` immer Materie, und beide fragen
    ``recess`` gar nicht: Eine Bohrung mit ``recess=False`` bleibt ein
    Hohlraum. Bei Kegel und Kugel entscheidet ``recess`` allein — eine
    Senkung ist ein Kegel nach innen, eine Kuppe einer nach außen.
    """
    assert is_a_cavity(_merkmal("hole")) is True
    assert is_a_cavity(_merkmal("hole", recess=False)) is True
    assert is_a_cavity(_merkmal("pin")) is False
    assert is_a_cavity(_merkmal("pin", recess=True)) is False
    for art in ("cone", "sphere", "torus"):
        assert is_a_cavity(_merkmal(art, recess=True)) is True, art
        assert is_a_cavity(_merkmal(art, recess=False)) is False, art
        assert is_a_cavity(_merkmal(art)) is False, f"{art} ohne Angabe ist Materie"


def test_the_geometry_layer_asks_this_question_instead_of_answering_it() -> None:
    """Die Frage wird an **einer** Stelle beantwortet, nicht an zwei.

    **Der Anlass ist ein Zwilling, der einen Wächter behauptete, den es nicht
    gab** (07.09.2026). ``geom.prepare_ops._feature_is_a_cavity`` stand
    wortgleich neben :func:`app.core.types.is_a_cavity`, und der Docstring
    dort sagte, ``tests/test_features.py`` halte beide zusammen — kein Test
    nannte je eine der beiden Funktionen. Seine zweite Begründung, die
    Wahrnehmung dürfe die Geometrie nicht importieren, war am Code widerlegt:
    ``perceive/relations.py`` importiert ``geom.mesh`` in seiner dritten
    Importzeile.

    Dieser Wächter prüft deshalb den Quelltext und nicht das Verhalten: Wer in
    ``app/core/geom`` ``recess`` liest, beantwortet die Frage neu — und zwar
    an einer Stelle, an der die nächste Änderung sie nicht findet. Die Antwort
    steht seit dem 07.09.2026 in ``app/core/types.py``, bei dem Ding, über das
    sie etwas sagt: Sie liest nur ``kind`` und ``params["recess"]``, und damit
    kosteten die sieben Aufrufer in ``prepare_ops`` je einen trägen Import
    gegen die Paketrichtung, den niemand brauchte.
    """
    geometrie = Path(__file__).resolve().parents[1] / "app" / "core" / "geom"
    dateien = sorted(geometrie.rglob("*.py"))
    assert len(dateien) > 20, f"nur {len(dateien)} Dateien gefunden — sucht der Test noch etwas?"

    stellen = [
        f"{datei.name}:{nummer}"
        for datei in dateien
        for nummer, zeile in enumerate(datei.read_text(encoding="utf-8").splitlines(), 1)
        if '"recess"' in zeile and not zeile.lstrip().startswith(("#", "*", '"""'))
    ]
    assert not stellen, (
        "die Hohlraumfrage wird in der Geometrieschicht beantwortet statt über "
        f"perceive.relations.is_a_cavity gestellt: {', '.join(stellen)}"
    )


# --- die Wand um ein Langloch (RM-152) ------------------------------------------------


def _pin_with_slot() -> MeshData:
    """Ein Zapfen Ø 20 mit einem durchgehenden Langloch Ø 8 auf 14 mm.

    Die Zahlen sind die aus RM-152, und sie sind mit Absicht so gewählt, dass
    die beiden Antworten weit auseinanderliegen: An den Flanken stehen 6 mm
    Wand, an den **Enden** 3. Wandstärke ist druckkritisch, also gilt die
    dünnste Stelle — die doppelte Zahl zu nennen wäre schlimmer als zu
    schweigen.
    """
    pin = trimesh.creation.cylinder(radius=10.0, height=20.0, sections=96)
    travel = 14.0 - 8.0
    middle = trimesh.creation.box(extents=(travel, 8.0, 30.0))
    tool = middle
    for side in (-travel / 2.0, travel / 2.0):
        cap = trimesh.creation.cylinder(radius=4.0, height=30.0, sections=64)
        cap.apply_translation((side, 0.0, 0.0))
        tool = tool.union(cap)
    return MeshData.of(pin.difference(tool))


def test_the_wall_around_a_slot_is_measured_where_it_is_thinnest() -> None:
    """Ein Langloch hat keine gleichmäßige Wand — die Enden entscheiden.

    Der halbe Unterschied zweier Durchmesser gilt, wo die Wand rundum gleich
    ist. Hier ergäbe er 6,0 mm und läge damit um das Doppelte über der Stelle,
    an der das Teil wirklich reißt.
    """
    features = detect(_pin_with_slot())
    slot = next(f for f in features.values() if f.kind == "slot")

    found = sleeve_at(slot, features)

    assert found is not None, "das Langloch im Zapfen findet seine Wand nicht"
    assert found.bore == slot.id
    assert abs(found.thickness - 3.0) < 0.2, (
        f"Wand {found.thickness:.3f} mm statt 3,0 — (20 − 8) / 2 abzüglich des halben Wegs"
    )


def test_a_slot_counts_as_a_cavity() -> None:
    """Ohne diese Antwort trüge *Merkmal verschieben* an der alten Stelle ab
    statt zu füllen — und das Volumen bliebe dabei gleich (RM-153)."""
    features = detect(_pin_with_slot())
    slot = next(f for f in features.values() if f.kind == "slot")

    assert is_a_cavity(slot), "ein Langloch ist ein Hohlraum wie eine Bohrung"
