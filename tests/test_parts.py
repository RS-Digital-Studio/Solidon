"""Die Bausteinbibliothek und ihre Bereichsprüflogik (Bauplan §24).

Die Bibliothek wird bei Änderungen von Hand über ihre Parametergrenzen
gerechnet. Diese Datei prüft die Deklarationen, den Anschluss an die gemeinsame
Bereichsprüfung sowie Wandmessung, Selbstdurchdringung und benannte Merkmale.
Sie führt keinen vollständigen Bereichslauf über sämtliche Bausteine aus.
"""

from __future__ import annotations

import dataclasses
import itertools
import json
from pathlib import Path
from typing import Any
from unittest import mock

import numpy as np
import pytest

from app.core.geom.boolean import boolean
from app.core.geom.mesh import MeshData, as_mesh_data
from app.core.knowledge import profiles, standards
from app.core.knowledge.parts import LIBRARY_VERSION, PARTS, changed_since, missing_parts, shapes
from app.core.knowledge.parts import ops as part_ops
from app.core.knowledge.parts.range_check import (
    FeatureRequirement,
    WallRequirement,
    has_self_intersections,
    local_wall_thickness,
)
from app.core.knowledge.parts.range_check import (
    check as check_range,
)
from app.core.knowledge.parts.range_check import (
    corners as core_corners,
)
from app.core.knowledge.parts.registry import PartRegistry, PartSpec, register_part
from app.core.registry import REGISTRY, op_params, param
from app.core.scene import History, OperationDraft, evaluate
from app.core.scene.project import Project, ProjectSources, new_project
from app.core.types import BaseParams, PartResult, Profile
from app.i18n.catalog import available_languages
from tests.helpers import plate_project as project_with_plate

MESHES = Path(__file__).parent / "data" / "meshes"


def ids(spec: PartSpec) -> str:
    return spec.name


def test_part_measures_distinguish_parameters_from_measured_facets() -> None:
    """Eine Buchse verspricht Vorgabemaße; die gerundete Schale misst ihre Bodenfläche."""
    from app.core.types import measure_status

    insert_spec = PARTS.get("heatset_m4")
    insert = insert_spec.fn(insert_spec.params(size="M4"))
    bore = next(feature for feature in insert.features.values() if feature.kind == "hole")
    assert bore.params["diameter"] == pytest.approx(standards.insert("M4").hole)
    assert measure_status(bore, "diameter").source == "parameter"
    tray_spec = PARTS.get("organizer_tray")
    tray = tray_spec.fn(tray_spec.params())
    floor = tray.features["floor"]
    assert measure_status(floor, "area").source == "facets"
    assert measure_status(floor, "centre").source == "parameter"
    assert floor.params["area"] > 0.0


def test_declared_measure_sources_keep_the_complete_parameter_value() -> None:
    """Die Maßdeklaration rundet weder Längen noch Fläche oder Steigung im Kern."""
    from app.core.knowledge.parts import build
    from app.core.types import measure_status

    value = 8.123456789
    point = (1.23456789, -2.34567891, 3.45678912)
    made = (
        build.bore("bore", value, point, depth=value)[1],
        build.pin("pin", value, point, length=value)[1],
        build.face("face", value, point)[1],
        build.thread("thread", value, value, point, length=value)[1],
    )
    for feature in made:
        assert feature.params["centre"] == point
        for name in ("diameter", "depth", "area", "pitch", "length"):
            if name in feature.params:
                assert feature.params[name] == pytest.approx(value, rel=0.0, abs=1e-12)
                assert measure_status(feature, name).source == "parameter"


def corners(spec: PartSpec) -> list[dict[str, Any]]:
    """Die Ecken des Parameterbereichs — seit dem 25.08.2026 aus dem Kern.

    Die Fassung mit der ganzen Geschichte (warum kein kartesisches Produkt,
    was der 24er-Schnitt gekostet hat) steht in
    :func:`app.core.knowledge.parts.range_check.corners` — dort läuft sie
    beim Kunden, wenn er ein Rezept anlegt (§24.5), hier läuft sie in der
    Suite. Eine Regel, ein Ort; die Kopie, die hier stand, wäre beim
    nächsten Nachbessern auseinandergelaufen. Die Grenze kommt aus der Herkunft
    (``corner_limit``, RM-578).
    """
    from app.core.knowledge.parts.range_check import corner_limit

    return core_corners(spec.params, corner_limit(spec.source))


def required_defaults(spec: PartSpec) -> dict[str, Any]:
    """Pflichtwerte, die eine Vorgabe tragen — die Auswertung setzt sie nicht ein.

    Eine Vorgabe macht ein Feld nicht optional (``registry/params.py``, seit dem
    27.08.2026): Ein Pflichtfeld ohne Wert hält die Kette an, auch wenn eine
    Vorgabe dasteht. Klemmschale, Einlage, Dichtnut und Dichtung tragen ihre
    Zeichnung so — Pflicht, mit einem Kreis als Startpunkt. Der Katalogdialog
    sammelt jeden Wert ein und schickt ihn mit; wer hier ohne Dialog aufruft,
    tut dasselbe.
    """
    return {
        entry.name: entry.default
        for entry in spec.params.spec()
        if entry.required and entry.default not in (None, "")
    }


# --- die Bibliothek ---------------------------------------------------------------


def test_registered_range_check_uses_every_declared_requirement(profile: Profile) -> None:
    """Der Registerweg reicht auch optionale Pflichten und Abbruch zum gemeinsamen Prüfer."""
    from app.core.knowledge.parts import range_check
    from app.core.scene.cancel import CancelSignal

    spec = dataclasses.replace(
        PARTS.get("heatset_m4"),
        joined_by_host=True,
        bodies=2,
        feasible=lambda values: values["size"] != "M2",
    )
    progress = mock.Mock()
    cancelled = CancelSignal()
    report = range_check.RangeReport(checked=1)
    with mock.patch.object(range_check, "check", return_value=report) as checker:
        seen = range_check.check_part(spec, profile, progress=progress, cancelled=cancelled)
    assert seen is report
    checker.assert_called_once_with(
        spec.params,
        spec.fn,
        profile,
        progress=progress,
        cancelled=cancelled,
        joined_by_host=True,
        bodies=2,
        wall=spec.wall,
        features=spec.feature_requirements,
        feasible=spec.feasible,
        limit=range_check.LIBRARY_MAX_CORNERS,
    )


def test_the_library_has_the_first_set_from_the_plan() -> None:
    """§24.1 nennt dreizehn Bausteine für die erste Auslieferung, dazu elf.

    Die Kalibrierkörper aus §28.3 sind auch Bausteine, gehören aber nicht zu
    diesem Satz — sie sind Werkzeuge für den Drucker, nicht für das Modell, und
    sie haben ihre eigene Gruppe im Katalog.

    **Elf stehen nicht in der Erstbestückung**, und alle elf sind eine Ansage
    und kein Versehen. Wer die Zahl hier ändert, ändert die Bibliothek, und das soll
    auffallen.

    ``snap_connector`` ist am 14.08.2026 dazugekommen, weil das Trennwerkzeug
    einen Verbinder brauchte, der einrastet. Die ``snap_fit`` des Plans ist etwas
    anderes — ein Arm, den man an eine Wand setzt; dieser hier ist ein Paar aus
    Arm und Tasche, bemaßt aus dem Durchmesser, den eine Naht hergibt.

    ``profile_tongue`` kam am 20.08.2026 dazu, und der Anlass lag nicht an einem
    Werkzeug, sondern in der Tabelle: Die Aluprofil-Nutmaße stehen seit der
    Erstbestückung in ``standards.toml``, weil §24.2 sie verlangt, und gelesen
    hat sie kein Baustein. Nachschlagen konnte man sie, verbauen nicht. Die zwei
    Maße, die eine Feder darüber hinaus braucht — Stegdicke und Kammertiefe —
    sind mit ihr in die Tabelle gekommen; sie ist seither auf Version 2.

    ``cable_clip`` kam am 24.08.2026 dazu, und der Anlass war eine Zählung. Die
    Gruppe „Kabel und Schläuche" hatte **einen** Eintrag, und der ist ein Loch
    (die Durchführung), kein Halter — während Kabelmanagement die
    meistgenannte Kategorie der Modellportale ist. Dieselbe Sorte Lücke wie bei
    ``profile_tongue``: Die Schlauchmaße standen seit der Erstbestückung in
    ``standards.toml``, und gelesen hat sie genau ein Baustein.

    ``pegboard_hook`` kam am 25.08.2026 dazu, und der Anlass war eine
    Kundenanfrage: an ein heruntergeladenes Modell IKEA-SKÅDIS-Haken hängen,
    ohne es nachzukonstruieren. Mit ihm kam eine neue Tabellenart — Lochwände
    sind keine Normteile, ihre Maße veröffentlicht niemand, und **gegeben sind
    sie trotzdem**: Wer einen Einhänger baut, hat sie nicht zu wählen, sondern
    zu treffen.

    ``gusset`` kam am 25.08.2026 dazu, aus derselben Durchsicht wie der
    Kabelclip: Die Versteifungsrippe hält **eine** Wand, und die Ecke zwischen
    zweien blieb offen — ein Eckwinkel steht auf jeder Liste häufig gedruckter
    Funktionsteile, und die Gruppe „Struktur" hatte zwei Einträge.

    ``foot`` kam am 25.08.2026 dazu, aus derselben Liste: Was auf dem Tisch
    steht, steht sonst auf seiner Druckkante. Er kann beides — ein gedruckter
    Fuß und die Tasche für einen gekauften aus Gummi —, und das ist kein
    Doppelbaustein, sondern dieselbe Form zweimal gelesen (``subtractive_on``,
    wie beim Passstift).

    ``hinge_eye`` kam am 25.08.2026 dazu. Das Filmscharnier **biegt**, dieses
    hier **dreht** — zwei Augen und ein Passstift ergeben ein Gelenk, das hält.

    ``barrel_hinge`` kam am 27.08.2026 dazu und ist das Scharnier, das das Auge
    damals nicht sein durfte: eines, das schon beim Drucken beweglich ist. Es
    besteht aus zwei Teilen, und bis dahin musste ein Baustein einer sein —
    nicht laut Bauplan, sondern laut Test. §24.3 trägt die Ausnahme seit dem
    25.08.2026 als **Deklaration** (Entscheidung Robert): Wer mehrere Körper
    baut, sagt wie viele, und dann prüft der Bereichstest die gebaute Zahl
    gegen die erklärte. Unerklärtes Zerfallen bleibt rot. Er ist der erste
    Nutzer von ``bodies`` und damit der Beleg, dass die Deklaration trägt.

    Die gedruckte Schraube und Mutter kamen am 28.08.2026 aus einer
    Supportmeldung hinzu. Sie benutzen dieselbe Normtabelle und dasselbe
    Materialspiel wie das druckbare Gewinde, damit ein Behältergewinde, sein
    Deckel und eine lösbare Schraubverbindung nicht drei unvereinbare Maße
    bekommen.

    ``bearing_seat`` kam am 28.08.2026 dazu. Lagermaße standen schon in der
    Normteiltabelle, waren aber im Katalog nicht benutzbar. Der Lagersitz macht
    daraus eine einfache Auswahl: Lagernummer wählen und entscheiden, ob das
    Lager wechselbar oder fest eingepresst sein soll.

    ``profile_clamp_shell`` und ``profile_clamp_liner`` kamen am 16.09.2026
    aus dem Dateiaudit (RM-183): eine Klemmschale und eine wechselbare Einlage
    mit gezeichneter Gegenkontur, die zusammen den Vierkörperweg von
    ``create_profile_clamp_set`` bilden. Beide brauchen eine Zeichnung und
    ein ausdrückliches Material — Vorgaben gibt es dafür nicht.

    ``seal_groove`` und ``seal_gasket`` kamen am selben Tag dazu: die
    abtragende Dichtnut und die separate Dichtung aus demselben geschlossenen
    Weg, dieselbe Bauart mit Zeichnung und Materialrolle.

    ``lug`` und ``pipe_clamp`` kamen am 02.10.2026 aus dem Nachbau-Test
    (RM-398): Laschen mit Loch und die Klemmschelle entstanden dort je aus
    Grundkörpern, Verschieben und Bohrungen, an Schraubendreherhalter,
    Kartuschendeckel und Klemmschelle.

    ``holder_u``, ``holder_ring``, ``holder_fork`` und ``holder_shelf`` kamen
    am 02.10.2026 aus RM-399: die Halter-Vorlage, je Form ein Baustein, damit
    jeder Bereich unter der Eckengrenze bleibt.

    Acht kamen am 04.10.2026 aus dem Dateiaudit (RM-184): ``bayonet`` und
    ``detent_disc`` (Verschlüsse, die man dreht, je ein Paar über ``kind``),
    ``rod_connector`` (Steckhülse und Zwei- bis Vierwegeverbinder),
    ``hose_barb`` und ``channel_joint`` (Schlauchtülle und Kanalnaht) und
    ``room_floor``, ``room_wall`` und ``room_pane`` (Raum- und Plattenvorlage).

    ``threaded_rod`` kam am 08.10.2026 dazu (Robert zu RM-562: „Beim Baustein
    Schraube und Bolzen sind schon Unterschiede“): Gewindestange oder
    Stiftschraube als eigenes Teil, aus demselben Gewindekern wie das Gewinde.
    """
    building = [spec for spec in PARTS.all() if spec.group != "calibration"]

    assert len(building) == 47
    assert len([spec for spec in PARTS.all() if spec.group == "calibration"]) == 3


def test_every_part_is_completely_declared() -> None:
    for spec in PARTS.all():
        assert str(spec.title).strip(), f"{spec.name} has no title"
        assert str(spec.doc).strip(), f"{spec.name} has no documentation"
        assert spec.features, f"{spec.name} names no provenance features"
        assert spec.changes, f"{spec.name} has no change log (§24.4)"


def test_a_part_without_features_is_refused() -> None:
    """§24.1: Provenienz-Merkmale sind der Sinn eines Bausteins, keine
    Nettigkeit.
    """
    from app.core.errors import InternalError

    registry = PartRegistry()

    @op_params
    class Params(BaseParams):
        size: float = param(title="x", default=1.0)

    with pytest.raises(InternalError):

        @register_part(
            name="nameless", title="x", group="fasteners", params=Params, registry=registry
        )
        def nameless(raw: BaseParams) -> PartResult:  # pragma: no cover - läuft nie
            raise AssertionError


# --- Der Bereichstest, den §24.3 verlangt -----------------------------------------


def test_range_corners_are_the_complete_cartesian_boundary() -> None:
    """§24.3 meint auch das Zusammenspiel der Grenzen, nicht nur jede einzeln.

    Die zyklische Fassung lieferte für diesen Satz drei Zeilen und ließ neun
    Kombinationen aus. Vorgaben gehören nicht zu den Grenzen: Sie werden im
    Reproduzierbarkeitstest gefahren und würden hier aus 2·2·3 unnötig 3·3·3
    machen.
    """

    @op_params
    class BoundaryParams(BaseParams):
        width: float = param(title="Breite", default=5.0, minimum=1.0, maximum=9.0)
        count: int = param(title="Zahl", default=3, minimum=1, maximum=5)
        side: str = param(title="Seite", default="a", choices=("a", "b", "c"))

    plan = core_corners(BoundaryParams)

    assert len(plan) == 12
    assert plan[0] == {"width": 1.0, "count": 1, "side": "a"}
    assert plan[-1] == {"width": 9.0, "count": 5, "side": "c"}
    assert not any(entry["width"] == 5.0 for entry in plan)
    assert len({tuple(entry.items()) for entry in plan}) == len(plan)


def test_the_library_really_has_16814_cartesian_boundaries() -> None:
    """Vollständige Grenzen einschließlich der 120 Organizer-Kombinationen.

    Die 312 seit dem 16.09.2026 sind die Klemmschale (32), ihre Einlage (256),
    die Dichtnut (8) und die Dichtung (16) — gezählt je Baustein, nicht aus
    dem Prüfling abgelesen. Seit dem 22.09.2026 kommen 120 dazu: Die
    Klemmschale bietet vier Schraubengrößen statt einer (32 → 128), und der
    Überhangfächer hat für Breite und Auskraglänge eine Obergrenze (8 → 32).
    Die Lasche mit Loch (RM-398) bringt 40: fünf Schrauben mal Breite, Länge
    und Dicke an je zwei Grenzen. Die Rohrschelle bringt 512: acht Rohre mal
    vier Schrauben mal eigener Durchmesser, Breite, Wand und Spiel an je zwei.
    Seit dem 02.10.2026 die 1536 der vier Halter (RM-399): U-Form und Ablage
    je 512, rund und Gabel je 256 — vier Befestigungen mal sieben oder sechs
    zweiwertige Felder. Seit dem 03.10.2026 kommen 32 dazu: Die Profilnutfeder
    trägt zwei Herstellerprofile (RM-017), fünf Größen statt drei (48 → 80).
    Seit dem 04.10.2026 die 2320 der acht Audit-Bausteine (RM-184):
    Bajonett und Raumboden je 512, Stangenverbinder 384, Kanalnaht,
    Rastdrehscheibe und Raumwand je 256, Schlauchtülle 128, Fensterscheibe 16.
    Seit dem 06.10.2026 kommen 200 dazu: Das druckbare Gewinde hat ein eigenes
    Maß mit Durchmesser und Steigung an je zwei Grenzen (56 → 256). Am selben
    Tag 1076 mehr: Die Normteiltabelle reicht von M1.6 bis M64 (27 Größen),
    Schraubenloch, Mutternfalle, Schraube, Mutter und Einpressbuchse haben ein
    eigenes Maß, Wandhalter und Klemmschale nehmen je sechzehn Größen; zugleich zählt ein
    Feld ohne Wirkung keine Ecken mehr (Gewinde 768 → 216, Schraubenloch 1536 →
    400, auch Lagersitz, Kanalnaht, die Halter, Raumboden und Dichtung).
    Seit dem 08.10.2026 kommen 496 dazu: der Gewindebolzen, 27 Größen mal
    Länge, Gewindelänge, Fase und Spiel an je zwei Grenzen, dazu das eigene
    Maß mit Durchmesser und Steigung. Mit RM-578 (Grenze der Bibliothek 4096)
    7936 mehr: Wandhalter bis M64 (512 → 832), Rohrschelle bis M64 (512 →
    3072), Klemmschale bis M64 (512 → 768), die Halter mit wählbarer Schraube
    (U und Ablage 320 → 1920, rund und Gabel 160 → 960).
    """

    assert sum(len(corners(spec)) for spec in PARTS.all()) == 16814


def test_the_library_checks_up_to_4096_corners_and_an_own_part_512() -> None:
    """RM-578: Die 512er-Grenze gilt nur noch für eigene Bausteine des Kunden.

    Die mitgelieferte Bibliothek wird einmal bei uns nachgewiesen; ihre Grenze
    richtet sich nach der Rechenzeit des Nachweises. Ein Bereich mit 1024 Ecken
    ist für ein Rezept zu groß und für die Bibliothek nicht — voll geprüft in
    beiden Fällen, ohne Stichprobe.
    """
    from app.core.errors import ValidationError
    from app.core.knowledge.parts.range_check import (
        LIBRARY_MAX_CORNERS,
        MAX_CORNERS,
        corner_limit,
    )

    assert (MAX_CORNERS, LIBRARY_MAX_CORNERS) == (512, 4096)
    assert corner_limit("shipped") == LIBRARY_MAX_CORNERS
    assert {corner_limit(source) for source in ("recipe", "imported", "user")} == {MAX_CORNERS}

    @op_params
    class Wide(BaseParams):
        a: float = param(title="a", default=1.0, minimum=1.0, maximum=2.0)
        b: float = param(title="b", default=1.0, minimum=1.0, maximum=2.0)
        c: float = param(title="c", default=1.0, minimum=1.0, maximum=2.0)
        d: float = param(title="d", default=1.0, minimum=1.0, maximum=2.0)
        e: float = param(title="e", default=1.0, minimum=1.0, maximum=2.0)
        f: float = param(title="f", default=1.0, minimum=1.0, maximum=2.0)
        g: float = param(title="g", default=1.0, minimum=1.0, maximum=2.0)
        h: float = param(title="h", default=1.0, minimum=1.0, maximum=2.0)
        i: float = param(title="i", default=1.0, minimum=1.0, maximum=2.0)
        j: float = param(title="j", default=1.0, minimum=1.0, maximum=2.0)

    with pytest.raises(ValidationError):
        core_corners(Wide)
    assert len(core_corners(Wide, LIBRARY_MAX_CORNERS)) == 1024


def test_every_offered_screw_size_is_buildable_up_to_m64() -> None:
    """RM-578: Wandhalter, Rohrschelle, Klemmschale und Halter nehmen die Tabelle bis M64.

    Bis dahin endeten sie bei M27, M6 und M33, weil 512 Ecken nicht mehr Größen
    trugen. Angeboten wird nur, was an einer Ecke des Bereichs baut: Schellenbreite
    und Klemmtiefe reichen für die Scheibe und Mutter der größten Größe, sonst
    stünde der Vorschlag „größer wählen“ ins Leere.
    """
    from app.core.knowledge.parts.mounting import _CLAMP_SCREWS, WALL_SCREWS
    from app.core.knowledge.parts.profile_clamps import CLAMP_DEPTH_LIMIT, SCREW_SIZES
    from app.core.sketch import shapes as sketch_shapes
    from app.core.sketch.serialize import sketch_to_text

    assert WALL_SCREWS[0] == "M2" and WALL_SCREWS[-1] == "M64"
    assert _CLAMP_SCREWS[0] == "M3" and _CLAMP_SCREWS[-1] == "M64"
    assert SCREW_SIZES[0] == "M3" and SCREW_SIZES[-1] == "M64"
    pipe = PARTS.get("pipe_clamp")
    widest = next(entry.maximum for entry in pipe.params.spec() if entry.name == "width")
    for size in _CLAMP_SCREWS:
        assert pipe.feasible(pipe.params(screw_size=size, width=widest, play=0.2)) is None, size
    shell = PARTS.get("profile_clamp_shell")
    seat = sketch_to_text(sketch_shapes.circle(20.0))
    for size in SCREW_SIZES:
        values = shell.params(seat_sketch=seat, screw_size=size, depth=CLAMP_DEPTH_LIMIT, play=0.2)
        assert shell.feasible(values) is None, size
    for name, values in (
        ("wall_mount", {"size": "M64"}),
        ("pipe_clamp", {"screw_size": "M64", "width": widest, "play": 0.2}),
    ):
        spec = PARTS.get(name)
        built = as_mesh_data(spec.fn(spec.params(**values)).mesh)
        assert built.is_watertight and built.component_count == 1, name


def test_a_field_without_effect_does_not_multiply_the_corners() -> None:
    """Ein Feld, dessen Bedingung in einer Ecke nicht erfüllt ist, steht dort auf seiner Vorgabe.

    Der Baustein verwirft seinen Wert (``depends_on``); ihn an beiden Grenzen
    zu bauen, baute dieselbe Ecke zweimal. Zwei Tabellengrößen und ein eigenes
    Maß mit Durchmesser, dazu ein Haken, der nur bei eigenem Maß wirkt und
    selbst eine Tiefe wirksam macht, und eine Länge ohne Bedingung:
    (1 + 1 + 2 · (2 + 1)) · 2 = 16 statt 3 · 2 · 2 · 2 · 2 = 48.
    """

    @op_params
    class SizedParams(BaseParams):
        size: str = param(title="Größe", default="a", choices=("a", "b", "own"))
        diameter: float = param(
            title="Maß", default=5.0, minimum=1.0, maximum=9.0, depends_on=("size", ("own",))
        )
        flag: bool = param(title="Haken", default=False, depends_on=("size", ("own",)))
        depth: float = param(
            title="Tiefe", default=2.0, minimum=1.0, maximum=3.0, depends_on=("flag", (True,))
        )
        length: float = param(title="Länge", default=4.0, minimum=2.0, maximum=6.0)

    from app.core.knowledge.parts import range_check

    plan = core_corners(SizedParams)

    assert len(plan) == range_check.corner_count(SizedParams) == 16
    assert len({tuple(entry.items()) for entry in plan}) == len(plan)
    assert all(list(entry) == ["size", "diameter", "flag", "depth", "length"] for entry in plan)
    for entry in plan:
        if entry["size"] != "own":
            # Ohne eigenes Maß wirkt keines der drei Felder: alle auf ihrer Vorgabe.
            assert (entry["diameter"], entry["flag"], entry["depth"]) == (5.0, False, 2.0)
        elif not entry["flag"]:
            assert entry["depth"] == 2.0
    own = [entry for entry in plan if entry["size"] == "own"]
    assert {entry["diameter"] for entry in own} == {1.0, 9.0}
    assert {entry["depth"] for entry in own if entry["flag"]} == {1.0, 3.0}


def test_a_range_limit_is_checked_before_materialising_combinations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ein großer Bereich wird vollständig abgewiesen, bevor das Produkt wächst."""
    from app.core.errors import ValidationError
    from app.core.knowledge.parts import range_check

    schema = op_params(
        type(
            "WideRangeParams",
            (BaseParams,),
            {
                "__annotations__": {f"dimension_{i}": float for i in range(32)},
                **{
                    f"dimension_{i}": param(title="Maß", default=1.0, minimum=1.0, maximum=2.0)
                    for i in range(32)
                },
            },
        )
    )

    def must_not_materialise(*_args: Any) -> None:
        raise AssertionError("the limit must precede the Cartesian product")

    monkeypatch.setattr(range_check.itertools, "product", must_not_materialise)
    with pytest.raises(ValidationError) as caught:
        core_corners(schema)
    assert caught.value.values["count"] == 2**32
    assert caught.value.values["limit"] == 512
    assert caught.value.suggestions


def test_local_wall_measurement_finds_a_thin_appendage_on_a_large_body() -> None:
    """Ein Hüllquader misst das Teil, nicht seine lokale Wandstärke."""
    import trimesh

    large = trimesh.creation.box(extents=(10.0, 10.0, 10.0))
    thin = trimesh.creation.box(extents=(8.0, 2.0, 0.4))
    thin.apply_translation((0.0, 5.5, 0.0))
    joined = trimesh.boolean.union([large, thin])
    mesh = MeshData.of(joined)

    assert min(mesh.bounds.size) >= 10.0, "die alte Hüllquaderprüfung bliebe grün"
    assert local_wall_thickness(mesh) == pytest.approx(0.4, abs=0.01)


def test_local_wall_measurement_ignores_a_tip_without_an_opposing_face() -> None:
    """Ein Kegel läuft spitz zu, aber keine seiner Flächen liegt der anderen gegenüber.

    RM-050: Der Ersatz für VTKs ``vtkStaticCellLocator`` prüft weiterhin die
    Normale des getroffenen Dreiecks und nicht nur seinen Abstand — sonst
    meldete die Spitze eine erfundene Wandstärke von null statt „kein
    gegenüberliegendes Material".
    """
    import trimesh

    cone = trimesh.creation.cone(radius=5.0, height=10.0)
    mesh = MeshData.of(cone)

    assert local_wall_thickness(mesh) is None


def test_self_intersection_is_measured_in_the_mesh_not_in_its_flags() -> None:
    """Zwei geschlossene Hüllen können einander trotzdem durchdringen."""
    import trimesh

    left = trimesh.creation.box(extents=(10.0, 10.0, 10.0))
    right = trimesh.creation.box(extents=(10.0, 10.0, 10.0))
    right.apply_translation((4.0, 0.0, 0.0))
    crossing = MeshData.of(trimesh.util.concatenate([left, right]))
    separate = right.copy()
    separate.apply_translation((20.0, 0.0, 0.0))
    clean = MeshData.of(trimesh.util.concatenate([left, separate]))

    assert crossing.is_watertight and clean.is_watertight
    assert has_self_intersections(crossing)
    assert not has_self_intersections(clean)


def test_self_intersection_is_independent_of_face_order_and_ignores_topological_contacts() -> None:
    """Partition, gemeinsame Kanten und doppelte Vertex-Indizes ändern den Befund nicht."""
    from types import SimpleNamespace

    import trimesh

    left = trimesh.creation.box(extents=(10.0, 10.0, 10.0))
    right = trimesh.creation.box(extents=(10.0, 10.0, 10.0))
    right.apply_translation((4.0, 0.0, 0.0))
    crossing = trimesh.util.concatenate([left, right])
    reversed_crossing = crossing.copy()
    reversed_crossing.faces = reversed_crossing.faces[::-1]

    box = trimesh.creation.box()
    triangles = box.vertices[box.faces]
    duplicated = trimesh.Trimesh(
        vertices=triangles.reshape(-1, 3),
        faces=np.arange(len(triangles) * 3).reshape(-1, 3),
        process=False,
    )

    assert has_self_intersections(SimpleNamespace(raw=crossing))
    assert has_self_intersections(SimpleNamespace(raw=reversed_crossing))
    assert not has_self_intersections(SimpleNamespace(raw=box))
    assert not has_self_intersections(SimpleNamespace(raw=duplicated))


def test_shared_edge_roundoff_in_a_manifold_block_is_not_an_intersection(
    capfd: pytest.CaptureFixture[str],
) -> None:
    """Ein Rundungsversatz an einer gemeinsamen Kante macht sie nicht ungültig."""
    spec = PARTS.get("heatset_m4")
    result = spec.fn(spec.params(size="M2", lead_in=True, extra_depth=0.0))

    assert result.mesh.is_watertight
    assert not has_self_intersections(result.mesh)
    captured = capfd.readouterr()
    assert "WARN|" not in captured.err


def test_shared_vertex_roundoff_in_a_manifold_block_is_not_an_intersection() -> None:
    """Ein um Rundung versetzter Eckpunkt bleibt der gemeinsame Eckkontakt."""
    spec = PARTS.get("cable_gland")
    result = spec.fn(
        spec.params(
            size="ptfe-4x2",
            diameter=100.0,
            wall=1.0,
            play=0.25,
            strain_relief=True,
            relief_gap=0.0,
        )
    )

    assert result.mesh.is_watertight
    assert not has_self_intersections(result.mesh)


def test_shared_vertex_does_not_hide_an_intersection_through_both_faces() -> None:
    """Ein gemeinsamer Eckpunkt entschuldigt keine zusätzliche Schnittstrecke."""
    from types import SimpleNamespace

    import trimesh

    mesh = trimesh.Trimesh(
        vertices=np.asarray(
            [
                (0.0, 0.0, 0.0),
                (2.0, 0.0, 0.0),
                (0.0, 2.0, 0.0),
                (1.0, 1.0, -1.0),
                (1.0, 1.0, 1.0),
            ]
        ),
        faces=np.asarray(((0, 1, 2), (0, 3, 4))),
        process=False,
    )

    assert has_self_intersections(SimpleNamespace(raw=mesh))


def test_float32_contact_deduplication_keeps_a_short_real_intersection() -> None:
    """Eine kurze Strecke über der Float32-Auflösung bleibt ein echter Schnitt."""
    from types import SimpleNamespace

    import trimesh

    origin = 100.0
    offset = 0.001
    mesh = trimesh.Trimesh(
        vertices=np.asarray(
            [
                (origin, origin, 0.0),
                (origin + 2.0 * offset, origin, 0.0),
                (origin, origin + 2.0 * offset, 0.0),
                (origin + offset, origin + offset, -1.0),
                (origin + offset, origin + offset, 1.0),
            ]
        ),
        faces=np.asarray(((0, 1, 2), (0, 3, 4))),
        process=False,
    )

    assert has_self_intersections(SimpleNamespace(raw=mesh))


@pytest.mark.parametrize(
    ("vertices", "faces", "expected"),
    (
        (
            ((0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (0.0, 2.0, 0.0), (1.0, 1.0, -1.0), (1.0, 1.0, 1.0)),
            ((0, 1, 2), (0, 3, 4)),
            True,
        ),
        (
            (
                (0.0, 0.0, 0.0),
                (2.0, 0.0, 0.0),
                (0.0, 2.0, 0.0),
                (-1.0, -1.0, -1.0),
                (-1.0, -1.0, 1.0),
            ),
            ((0, 1, 2), (0, 3, 4)),
            False,
        ),
        (
            (
                (0.0, 0.0, 0.0),
                (2.0, 0.0, 0.0),
                (0.0, 2.0, 0.0),
                (0.5, 0.5, 0.0),
                (2.5, 0.5, 0.0),
                (0.5, 2.5, 0.0),
            ),
            ((0, 1, 2), (3, 4, 5)),
            True,
        ),
        (
            (
                (0.0, 0.0, 0.0),
                (1.0, 0.0, 0.0),
                (0.0, 1.0, 0.0),
                (3.0, 0.0, 0.0),
                (4.0, 0.0, 0.0),
                (3.0, 1.0, 0.0),
            ),
            ((0, 1, 2), (3, 4, 5)),
            False,
        ),
    ),
    ids=("shared-corner-crossing", "shared-corner-apart", "coplanar-overlap", "coplanar-apart"),
)
def test_self_intersection_separates_contact_crossing_and_overlap(
    vertices: tuple[tuple[float, float, float], ...],
    faces: tuple[tuple[int, int, int], ...],
    expected: bool,
) -> None:
    """Berührung, Schnitt und Flächenüberdeckung, je ein Fall mit und ohne Treffer."""
    from types import SimpleNamespace

    import trimesh

    mesh = trimesh.Trimesh(vertices=np.asarray(vertices), faces=np.asarray(faces), process=False)
    assert has_self_intersections(SimpleNamespace(raw=mesh)) is expected


def test_manifold_thread_union_is_not_a_self_intersection() -> None:
    """Kern und aufliegender Gewindegang bilden nach der Vereinigung eine Hülle."""
    spec = PARTS.get("printed_thread")
    built = spec.fn(spec.params(size="M2", length=2.0, internal=False, play=0.25)).mesh
    section = built.raw.section(plane_origin=(0.0, 0.0, 0.1), plane_normal=(0.0, 0.0, 1.0))

    assert built.is_watertight and built.component_count == 1 and built.volume > 0.0
    assert section is not None and len(section.discrete) == 1
    assert np.allclose(section.discrete[0][0], section.discrete[0][-1])
    assert not has_self_intersections(built)


@pytest.mark.parametrize("size", ["M2", "M8"])
def test_supported_thread_crests_stay_connected_to_their_core_or_shell(size: str) -> None:
    """Gestützte Kämme sind keine freistehende Wand, bleiben aber volumetrisch verbunden."""
    thread = PARTS.get("printed_thread")
    screw = PARTS.get("printed_screw")
    nut = PARTS.get("printed_nut")
    built = (
        thread.fn(thread.params(size=size, length=2.0, internal=False, play=1.0)).mesh,
        screw.fn(screw.params(size=size, length=2.0, countersunk=False, play=1.0)).mesh,
        nut.fn(nut.params(size=size, play=1.0)).mesh,
    )
    # Schraube und Mutter stehen um das Spiel über ihrer Fläche (RM-276): Der
    # Schnitt liegt deshalb in der Mitte des Gewindes bzw. der Mutter, nicht
    # an einer festen Höhe.
    sections = (
        built[0].raw.section(plane_origin=(0.0, 0.0, 1.0), plane_normal=(0.0, 0.0, 1.0)),
        built[1].raw.section(
            plane_origin=(0.0, 0.0, built[1].bounds.minimum[2] + 1.0),
            plane_normal=(0.0, 0.0, 1.0),
        ),
        built[2].raw.section(
            plane_origin=(0.0, 0.0, built[2].bounds.minimum[2] + built[2].bounds.size[2] / 2.0),
            plane_normal=(0.0, 0.0, 1.0),
        ),
    )

    assert all(mesh.is_watertight and mesh.component_count == 1 for mesh in built)
    assert sections[0] is not None and len(sections[0].discrete) == 1
    assert sections[1] is not None and len(sections[1].discrete) == 1
    assert sections[2] is not None and len(sections[2].discrete) == 2
    assert all(
        PARTS.get(name).wall.reason for name in ("printed_thread", "printed_screw", "printed_nut")
    )


def test_self_intersection_result_does_not_depend_on_hook_count_or_position() -> None:
    """Dieselbe saubere Hakenform bleibt sauber, gleich wie viele Haken und wo."""
    spec = PARTS.get("pegboard_hook")
    variants = (
        {"latch": False, "plate": 0.0, "play": 1.5, "lip": 0.0},
        {"latch": True, "plate": 10.0, "play": 0.25, "lip": 0.0},
        {"latch": True, "plate": 10.0, "play": 1.5, "lip": 6.0},
    )

    for variant in variants:
        for count in (1, 2, 6):
            built = spec.fn(
                spec.params(
                    system="skadis",
                    count=count,
                    steps=1,
                    upright=True,
                    **variant,
                )
            ).mesh

            assert built.is_watertight
            assert not has_self_intersections(built), f"count={count}, {variant}"


def test_coplanar_triangle_overlap_is_a_self_intersection() -> None:
    """Ein Schnittlinientest übersieht Flächenüberdeckung; der Vertrag darf es nicht."""
    from types import SimpleNamespace

    import trimesh

    mesh = trimesh.Trimesh(
        vertices=np.asarray(
            [
                (0.0, 0.0, 0.0),
                (2.0, 0.0, 0.0),
                (0.0, 2.0, 0.0),
                (0.5, 0.5, 0.0),
                (2.5, 0.5, 0.0),
                (0.5, 2.5, 0.0),
            ]
        ),
        faces=np.asarray(((0, 1, 2), (3, 4, 5))),
        process=False,
    )

    assert has_self_intersections(SimpleNamespace(raw=mesh))


def test_self_intersection_ignores_empty_and_degenerate_faces_and_can_cancel() -> None:
    """Nullflächen sind kein Treffer; jeder Rekursionsschritt bleibt abbrechbar."""
    from types import SimpleNamespace

    import trimesh

    empty = trimesh.Trimesh(
        vertices=np.empty((0, 3)), faces=np.empty((0, 3), dtype=int), process=False
    )
    box = trimesh.creation.box()
    vertices = np.vstack([box.vertices, [[2.0, 2.0, 2.0]]])
    faces = np.vstack([box.faces, [[len(vertices) - 1] * 3]])
    degenerate = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)

    class CancelDuringPartition:
        calls = 0

        @property
        def is_cancelled(self) -> bool:
            self.calls += 1
            return self.calls > 2

    assert not has_self_intersections(SimpleNamespace(raw=empty))
    assert not has_self_intersections(SimpleNamespace(raw=degenerate))
    assert not has_self_intersections(
        SimpleNamespace(raw=trimesh.creation.icosphere(subdivisions=3)),
        CancelDuringPartition(),
    )


def test_self_intersection_cancels_before_the_sweep() -> None:
    """Ein Abbruch vor dem Start sortiert nicht einmal die Hüllquader."""
    from types import SimpleNamespace

    import trimesh

    class CancelNow:
        @property
        def is_cancelled(self) -> bool:
            return True

    many_faces = SimpleNamespace(raw=trimesh.creation.icosphere(subdivisions=3))
    with mock.patch("numpy.argsort", side_effect=AssertionError("Sweep trotz Abbruch")):
        assert not has_self_intersections(many_faces, CancelNow())


def test_self_intersection_cancels_on_one_connected_199516_face_body() -> None:
    """Der Maximalfall — ein zusammenhängendes, ebenes Netz — hält beim ersten Abbruch an."""
    from types import SimpleNamespace

    import trimesh

    columns = 31
    rows = 3218
    x, y = np.meshgrid(np.arange(columns + 1), np.arange(rows + 1))
    vertices = np.column_stack((x.ravel(), y.ravel(), np.zeros(x.size)))
    lower_left = (np.arange(rows)[:, None] * (columns + 1) + np.arange(columns)[None, :]).ravel()
    lower_right = lower_left + 1
    upper_left = lower_left + columns + 1
    upper_right = upper_left + 1
    faces = np.vstack(
        (
            np.column_stack((lower_left, lower_right, upper_left)),
            np.column_stack((lower_right, upper_right, upper_left)),
        )
    )
    body = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)

    class CancelAfterOneBlock:
        calls = 0

        @property
        def is_cancelled(self) -> bool:
            self.calls += 1
            return self.calls >= 3

    token = CancelAfterOneBlock()
    assert len(body.faces) == 199_516
    assert not has_self_intersections(SimpleNamespace(raw=body), token)
    assert token.calls == 3, "nach dem Abbruch fragt niemand weiter"


@pytest.mark.parametrize("phase", ["_candidates", "_pairs_that_cross"])
def test_self_intersection_cancels_in_each_phase(phase: str) -> None:
    """Kandidatensuche und genaue Prüfung fragen beide nach dem Abbruch und hören darauf."""
    import sys
    from types import SimpleNamespace

    import trimesh

    class CancelAtPhase:
        triggered = False

        @property
        def is_cancelled(self) -> bool:
            if sys._getframe(2).f_code.co_name == phase:
                self.triggered = True
            return self.triggered

    token = CancelAtPhase()
    # Ein Ring mit ebenen Stirnflächen: Dort bleiben nach der Trennprüfung
    # Paare für die genaue Prüfung. An einer Ikosphäre trennt die
    # Nachbarprüfung seit RM-568 jedes Paar vorher, und die zweite Phase
    # käme nie an die Reihe.
    raw = trimesh.creation.annulus(r_min=2.0, r_max=4.0, height=3.0)
    assert not has_self_intersections(SimpleNamespace(raw=raw), token)
    assert token.triggered


def test_self_intersection_finds_a_pair_whose_boxes_only_touch_on_one_axis() -> None:
    """Zwei Dreiecke derselben Ebene zwischen 512 fernen: Ihre Hüllen haben die Dicke null."""
    from types import SimpleNamespace

    import trimesh

    vertices: list[tuple[float, float, float]] = []
    faces: list[tuple[int, int, int]] = []

    def add_triangle(points: tuple[tuple[float, float, float], ...]) -> None:
        start = len(vertices)
        vertices.extend(points)
        faces.append((start, start + 1, start + 2))

    for index in range(256):
        x = -1000.0 - index
        add_triangle(((x, 100.0, 0.0), (x + 0.1, 100.0, 0.0), (x, 100.1, 0.0)))
    add_triangle(((-2.0, -2.0, 0.0), (2.0, -2.0, 0.0), (-0.3, 4.0, 0.0)))
    # Beide Zielkörper liegen koplanar auf z=0. Ihre Hüllquader **berühren**
    # sich auf dieser Achse und überdecken sich trotzdem positiv. Wird der
    # Filter der Kandidaten von ``>`` zu ``>=`` mutiert, verschwindet genau
    # dieses Paar.
    add_triangle(((-0.5, -0.5, 0.0), (2.5, -0.5, 0.0), (-1.7, 3.0, 0.0)))
    for index in range(256):
        x = 1000.0 + index
        add_triangle(((x, 100.0, 0.0), (x + 0.1, 100.0, 0.0), (x, 100.1, 0.0)))

    mesh = trimesh.Trimesh(vertices=np.asarray(vertices), faces=np.asarray(faces), process=False)

    assert len(mesh.faces) == 514
    assert has_self_intersections(SimpleNamespace(raw=mesh))


def test_self_intersection_skips_the_pair_check_without_any_aabb_pair(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ohne überdeckende Hüllquader rechnet die genaue Prüfung kein einziges Paar."""
    from types import SimpleNamespace

    import trimesh

    from app.core.geom import intersections

    face_count = 512
    x = np.arange(face_count, dtype=float) * 2.0
    vertices = np.empty((face_count, 3, 3), dtype=float)
    vertices[:, 0] = np.column_stack((x, np.zeros(face_count), np.zeros(face_count)))
    vertices[:, 1] = vertices[:, 0] + (0.1, 0.0, 0.0)
    vertices[:, 2] = vertices[:, 0] + (0.0, 0.1, 0.0)
    mesh = trimesh.Trimesh(
        vertices=vertices.reshape(-1, 3),
        faces=np.arange(face_count * 3).reshape(-1, 3),
        process=False,
    )

    def unexpected_pair_work(*_args: Any) -> Any:
        raise AssertionError("getrennte Hüllquader dürfen die Paarprüfung nicht erreichen")

    monkeypatch.setattr(intersections, "crossing_pairs", unexpected_pair_work)

    assert not has_self_intersections(SimpleNamespace(raw=mesh))


def test_self_intersection_sweeps_along_a_helix_on_every_axis() -> None:
    """Der Sweep läuft entlang der Achse der Wendel, gleich wie sie liegt.

    Entlang einer Querachse gezählt träfe jeder Umlauf jeden anderen — eine
    Wendel ist quer zu ihrer Achse rund. Dieselbe Form bekommt deshalb in allen
    drei Lagen dieselbe Zahl Kandidaten, und der Hindernisquader, der durch
    sie läuft, wird gefunden.
    """
    import math
    from types import SimpleNamespace

    import trimesh

    from app.core.geom import intersections

    def helix(axis: int) -> trimesh.Trimesh:
        turns = np.linspace(0.0, 8.0 * np.pi, 256)
        radius = 10.0
        pitch = 2.0
        centres = np.column_stack((radius * np.cos(turns), radius * np.sin(turns), pitch * turns))
        radial = np.column_stack((np.cos(turns), np.sin(turns), np.zeros(len(turns))))
        tangent = np.column_stack(
            (-radius * np.sin(turns), radius * np.cos(turns), np.full(len(turns), pitch))
        )
        tangent /= np.linalg.norm(tangent, axis=1)[:, None]
        side = np.cross(tangent, radial)
        side /= np.linalg.norm(side, axis=1)[:, None]
        around = np.linspace(0.0, 2.0 * np.pi, 8, endpoint=False)
        rings = centres[:, None, :] + 0.45 * (
            np.cos(around)[None, :, None] * radial[:, None, :]
            + np.sin(around)[None, :, None] * side[:, None, :]
        )
        vertices = rings.reshape(-1, 3).tolist()
        faces: list[tuple[int, int, int]] = []
        for row in range(len(turns) - 1):
            for column in range(8):
                first = row * 8 + column
                next_first = row * 8 + (column + 1) % 8
                second = (row + 1) * 8 + column
                next_second = (row + 1) * 8 + (column + 1) % 8
                faces.extend(((first, second, next_first), (next_first, second, next_second)))
        for row, reverse in ((0, True), (len(turns) - 1, False)):
            centre = len(vertices)
            vertices.append(centres[row].tolist())
            for column in range(8):
                face = (centre, row * 8 + (column + 1) % 8, row * 8 + column)
                faces.append(face if reverse else face[::-1])
        mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
        if axis == 0:
            mesh.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2.0, [0, 1, 0]))
        elif axis == 1:
            mesh.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2.0, [1, 0, 0]))
            mesh.faces = mesh.faces[::-1]
        return mesh

    counts = []
    for axis in range(3):
        mesh = helix(axis)
        surface = intersections._surface(mesh.vertices, mesh.faces)
        assert surface is not None
        search = intersections._Search()
        counts.append(
            sum(len(first) for first, _second in intersections._candidates(surface, None, search))
        )
        assert not has_self_intersections(SimpleNamespace(raw=mesh))
    assert counts[0] == counts[1] == counts[2]
    assert counts[0] < math.comb(len(helix(2).faces), 2) * 0.01

    crossing = helix(2)
    obstacle = trimesh.creation.box(extents=(2.0, 2.0, 2.0))
    obstacle.apply_translation((10.0, 0.0, 0.0))
    assert has_self_intersections(
        SimpleNamespace(raw=trimesh.util.concatenate([crossing, obstacle]))
    )


def test_features_are_checked_at_the_boundary_where_they_disappear(profile: Profile) -> None:
    """Ein Merkmal nur an der Vorgabe zu prüfen ließ genau diesen Fall durch."""
    import trimesh

    from app.core.types import Feature

    @op_params
    class FeatureParams(BaseParams):
        width: float = param(title="Breite", default=1.5, minimum=1.0, maximum=2.0)

    def built(values: BaseParams) -> PartResult:
        features = (
            {
                "seat_1": Feature(
                    id="seat_1",
                    kind="face",
                    provenance="generated",
                    params={"area": 100.0},
                )
            }
            if values.width < 2.0  # type: ignore[attr-defined]
            else {}
        )
        return PartResult(
            mesh=MeshData.of(trimesh.creation.box(extents=(10.0, 10.0, 10.0))),
            features=features,
        )

    report = check_range(
        FeatureParams,
        built,
        profile,
        features=(FeatureRequirement("seat"),),
    )

    assert report.checked == 2
    missing = [failure for failure in report.failures if failure.values["width"] == 2.0]
    assert missing and "seat" in missing[0].reason


def test_wall_exemption_needs_a_written_reason() -> None:
    """Kalibrierkörper sind ein Vertrag, kein stiller Namenssonderfall."""
    with pytest.raises(ValueError):
        WallRequirement.not_applicable("   ")


def test_a_named_thin_wall_may_undercut_but_never_raise_the_profile_limit(
    profile: Profile,
) -> None:
    """Der Parameter erklärt die dünne Stelle, nicht jede Lasche des Körpers."""
    requirement = WallRequirement.from_parameter("film")

    assert requirement.minimum({"film": 0.2}, profile) == pytest.approx(0.2)
    assert requirement.minimum({"film": 15.0}, profile) == pytest.approx(
        profile.minimum_wall_thickness
    )


def test_missing_wall_measurement_is_a_failure_without_an_explicit_exemption(
    profile: Profile,
) -> None:
    """``None`` ist nur mit begründetem WallRequirement ein bestandener Vertrag."""
    import trimesh

    @op_params
    class SolidParams(BaseParams):
        pass

    def tetrahedron(_values: BaseParams) -> PartResult:
        return PartResult(
            mesh=MeshData.of(
                trimesh.Trimesh(
                    vertices=np.asarray(
                        ((0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (0.0, 2.0, 0.0), (0.0, 0.0, 2.0))
                    ),
                    faces=np.asarray(((0, 2, 1), (0, 1, 3), (0, 3, 2), (1, 2, 3))),
                    process=False,
                )
            )
        )

    required = check_range(SolidParams, tetrahedron, profile)
    exempt = check_range(
        SolidParams,
        tetrahedron,
        profile,
        wall=WallRequirement.not_applicable("Analytischer Gegenkörper ohne Wandpaar."),
    )

    assert any("Wandstärke" in failure.reason for failure in required.failures)
    assert exempt.passed


def test_wall_measurement_uses_geometry_epsilon_not_display_rounding(
    profile: Profile,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """0,835 mm erfüllen keine zugesagten 0,840 mm."""
    import trimesh

    from app.core.knowledge.parts import range_check

    @op_params
    class SolidParams(BaseParams):
        pass

    def solid(_values: BaseParams) -> PartResult:
        return PartResult(mesh=MeshData.of(trimesh.creation.box(extents=(2.0, 2.0, 2.0))))

    monkeypatch.setattr(range_check, "local_wall_thickness", lambda _mesh, _token: 0.835)
    monkeypatch.setattr(range_check, "has_self_intersections", lambda _mesh, _token: False)

    report = check_range(SolidParams, solid, profile)

    assert not report.passed
    assert any("0.835 mm < 0.840 mm" in failure.reason for failure in report.failures)


def wall_requirement(spec: PartSpec) -> WallRequirement:
    """Der Test liest denselben Registervertrag wie der Laufzeitweg."""
    return spec.wall


@pytest.mark.parametrize(
    ("name", "values", "expected_wall"),
    (
        (
            "latch",
            {"width": 2.0, "depth": 0.4, "height": 30.0, "negative": True, "play": 0.25},
            None,
        ),
        (
            "living_hinge",
            {"width": 5.0, "leaf": 3.0, "thickness": 0.8, "film": 0.4, "gap": 0.5},
            0.4,
        ),
        (
            "snap_connector",
            {"diameter": 4.0, "length": 8.0, "kind": "pin", "play": 0.25},
            0.8,
        ),
        (
            "snap_fit",
            {"width": 2.0, "length": 4.0, "thickness": 0.6, "hook": 0.2, "lead_angle": 60.0},
            None,
        ),
    ),
    ids=("abtragende-rastnase", "filmscharnier", "schnappverbinder", "schnapphaken"),
)
def test_thin_mechanisms_have_an_explicit_wall_contract(
    name: str,
    values: dict[str, Any],
    expected_wall: float | None,
    profile: Profile,
) -> None:
    """Dünne Funktionsstellen werden erklärt und an ihrem eigenen Maß geprüft."""
    from app.core.units import EPS_DISPLAY

    spec = PARTS.get(name)
    built = spec.fn(spec.params(**values)).mesh
    required = wall_requirement(spec).minimum(values, profile)

    assert built.is_watertight and built.component_count == 1
    assert required is None, "der allgemeine Profilwert beschreibt diesen Funktionskörper nicht"
    if expected_wall is not None:
        measured = local_wall_thickness(built)
        assert measured is not None
        assert measured >= expected_wall - EPS_DISPLAY


def test_the_smallest_snap_fit_hook_protrudes_without_intersecting_its_arm() -> None:
    """Die Hakenfläche und die sichtbare Geometrie müssen auf derselben Seite liegen."""
    from app.core.units import EPS_DISPLAY

    spec = PARTS.get("snap_fit")
    values = spec.params(width=2.0, length=4.0, thickness=0.6, hook=0.2, lead_angle=10.0)
    built = spec.fn(values)

    assert built.mesh.is_watertight and built.mesh.component_count == 1
    assert not has_self_intersections(built.mesh)
    assert float(built.mesh.bounds.maximum[1]) == pytest.approx(
        values.thickness / 2.0 + values.hook,
        abs=EPS_DISPLAY,
    )
    assert built.features["hook_1"].params["centre"][1] == pytest.approx(
        values.thickness / 2.0 + values.hook / 2.0,
        abs=EPS_DISPLAY,
    )


def test_a_snap_fit_hook_ramps_at_the_tip_and_catches_towards_the_root() -> None:
    """Das Gegenstück kommt von der Spitze: Dort beginnt die Schräge, darunter hält es.

    Gemessen am Querschnitt knapp unter der Spitze und knapp über der
    Haltefläche: Oben steht der Haken kaum über den Arm hinaus, unten um den
    vollen Überstand — und die benannte Hakenfläche liegt dort, wo er endet.
    Bis zum 22.09.2026 war es umgekehrt.
    """
    import math

    spec = PARTS.get("snap_fit")
    values = spec.params(width=8.0, length=16.0, thickness=1.6, hook=1.2, lead_angle=35.0)
    built = spec.fn(values)
    hook_height = values.hook / math.tan(math.radians(values.lead_angle))
    catch = 16.0 - hook_height

    def reach(z: float) -> float:
        section = built.mesh.raw.section(plane_origin=(0.0, 0.0, z), plane_normal=(0, 0, 1))
        assert section is not None
        return float(section.vertices[:, 1].max())

    assert reach(16.0 - 0.01) < values.thickness / 2.0 + 0.05, "Spitze: kaum Überstand"
    assert reach(catch + 0.01) == pytest.approx(values.thickness / 2.0 + values.hook, abs=0.02)
    assert reach(catch - 0.01) == pytest.approx(values.thickness / 2.0, abs=1e-6)
    assert built.features["hook_1"].params["centre"][2] == pytest.approx(catch)


@pytest.mark.parametrize("kind", ["pin", "bore"])
def test_a_dowel_chamfer_never_changes_its_length_or_foot(kind: str) -> None:
    """Eine Fase länger als der Stift verkürzt ihn nicht und bohrt nicht tiefer.

    Gemessen an der Ecke Ø 30, Länge 1, Fase 3: Bis zum 22.09.2026 maß der Fuß
    des Stifts Ø 26 statt 30, und die Bohrung reichte drei Millimeter tief.
    """
    spec = PARTS.get("dowel")
    values = spec.params(diameter=30.0, length=1.0, chamfer=3.0, kind=kind, play=0.2)
    mesh = spec.fn(values).mesh
    diameter = 30.0 if kind == "pin" else 30.2

    if kind == "pin":
        assert mesh.bounds.minimum[2] == pytest.approx(0.0, abs=1e-6)
        foot = mesh.raw.section(plane_origin=(0.0, 0.0, 0.001), plane_normal=(0, 0, 1))
    else:
        assert mesh.bounds.minimum[2] == pytest.approx(-1.0, abs=1e-6), "so tief wie verlangt"
        foot = mesh.raw.section(plane_origin=(0.0, 0.0, -0.999), plane_normal=(0, 0, 1))
    assert foot is not None
    reach = float(np.hypot(foot.vertices[:, 0], foot.vertices[:, 1]).max())
    assert 2.0 * reach == pytest.approx(diameter, abs=0.05)


def test_a_flat_large_snap_fit_hook_extends_the_arm_instead_of_crossing_its_base() -> None:
    """Der Anlaufkeil darf bei einer kurzen Vorgabe nicht unter die Ansatzfläche wachsen."""
    import math

    from app.core.units import EPS_DISPLAY

    spec = PARTS.get("snap_fit")
    values = spec.params(width=2.0, length=4.0, thickness=0.6, hook=6.0, lead_angle=10.0)
    built = spec.fn(values)
    expected_length = max(
        values.length,
        values.thickness * 10.0,
        values.hook / math.tan(math.radians(values.lead_angle)),
    )

    assert built.mesh.is_watertight and built.mesh.component_count == 1
    assert not has_self_intersections(built.mesh)
    assert float(built.mesh.bounds.minimum[2]) == pytest.approx(0.0, abs=EPS_DISPLAY)
    assert float(built.mesh.bounds.maximum[2]) == pytest.approx(expected_length, abs=EPS_DISPLAY)
    assert built.features["arm_1"].params["area"] == pytest.approx(
        values.width * expected_length,
        abs=EPS_DISPLAY,
    )


def test_the_snap_connector_declares_each_conditional_feature_and_its_change() -> None:
    """§24.4 meldet auch einen korrigierten Merkmalsvertrag an alte Projekte."""
    spec = PARTS.get("snap_connector")
    pin_result = spec.fn(spec.params(kind="pin"))
    bore_result = spec.fn(spec.params(kind="bore"))

    assert spec.features == ("arm", "hook", "catch")
    assert sorted(pin_result.features) == ["arm_1", "hook_1"]
    assert sorted(bore_result.features) == ["catch_1"]
    assert int(spec.version) >= 13
    assert any(change.version == "13" for change in spec.changes)
    assert spec.changes[-1].effect
    assert changed_since({"snap_connector": "5"}) == ("snap_connector",)


def feature_requirements(spec: PartSpec) -> tuple[FeatureRequirement, ...]:
    """Der Test liest denselben Registervertrag wie der Laufzeitweg."""
    return spec.feature_requirements


@pytest.mark.parametrize("steps", [3, 4, 7])
def test_the_fit_ladder_face_is_centred_on_its_pin_rail(steps: int) -> None:
    """Der Flächenbezug kommt aus der Leiste, nicht aus der Tiefe ihrer Beschriftung."""
    spec = PARTS.get("fit_ladder")
    made = spec.fn(spec.params(steps=steps))
    rail = min(made.mesh.raw.split(), key=lambda part: float(part.bounds[0, 1]))
    expected_xy = rail.bounds[:, :2].mean(axis=0)
    assert made.features["face_1"].params["centre"][:2] == pytest.approx(expected_xy)
    assert made.features["face_1"].params["centre"][2] == pytest.approx(3.0)


def test_inserting_two_snap_arms_reports_the_same_load_warning_once(profile: Profile) -> None:
    """Mehrere Ziele einer Operation vervielfachen keinen ortsunabhängigen Materialhinweis."""
    import trimesh

    from app.core.scene.cancel import NeverCancelled
    from app.core.types import Feature, OpContext, Scene, SceneObject

    source = SceneObject(
        id="obj_1",
        name="Platte",
        mesh=MeshData.of(trimesh.creation.box((100, 60, 5))),
        features={
            name: Feature(
                id=name,
                kind="face",
                provenance="generated",
                params={"centre": (x, 0.0, 2.5), "normal": (0.0, 0.0, 1.0), "area": 6000.0},
            )
            for name, x in (("left", -25.0), ("right", 25.0))
        },
    )
    spec = REGISTRY.get("insert_snap_fit")
    outcome = spec.fn(
        OpContext(
            scene=Scene(objects={source.id: source}),
            inputs=[source],
            params=spec.params(length=21.0, thickness=2.0, hook=1.2, at_features=("left", "right")),
            profile=profiles.make_profile("centauri-carbon-2", "pla"),
            quality="draft",
            seed=None,
            progress=lambda fraction, text: None,
            ask=lambda question, choices: choices[0],
            cancelled=NeverCancelled(),
        )
    )
    warnings = [entry for entry in outcome.findings if entry.code == "part.spring_overloaded"]
    assert len(warnings) == 1
    assert warnings[0].values["limit"] == pytest.approx(30.0)
    assert outcome.outputs[0].mesh.volume > source.mesh.volume
    assert {"snap_fit_arm_1", "snap_fit_arm_1_2"} <= set(outcome.outputs[0].features)


def test_a_part_hands_back_no_triangles_of_the_host_it_no_longer_has(profile: Profile) -> None:
    """Die Merkmale des Wirts kommen ohne die Dreiecke des alten Netzes zurück.

    Die Boolesche Operation nummeriert neu; bis zum 21.09.2026 trugen die
    mitgereichten Wirtsmerkmale die Nummern des Eingangsnetzes — an der Dose
    mit Deckel bis über die letzte hinaus, und der Plattencache verwarf den
    Eintrag bei jedem Öffnen (Review Leistung B3). Ort und Maß bleiben; die
    Oberfläche gibt die Auswertung an der neuen Erkennung zurück.
    """
    import trimesh

    from app.core.perceive.features import detect
    from app.core.scene.cancel import NeverCancelled
    from app.core.types import OpContext, Scene, SceneObject

    mesh = MeshData.of(trimesh.creation.box((100, 60, 5)))
    detected = detect(mesh)
    assert detected and all(feature.face_indices for feature in detected.values())
    source = SceneObject(id="obj_1", name="Platte", mesh=mesh, features=detected)
    spec = REGISTRY.get("insert_screw_hole")
    outcome = spec.fn(
        OpContext(
            scene=Scene(objects={source.id: source}),
            inputs=[source],
            params=spec.params(size="M4", x=10.0, y=5.0, z=5.0),
            profile=profile,
            quality="draft",
            seed=None,
            progress=lambda fraction, text: None,
            ask=lambda question, choices: choices[0],
            cancelled=NeverCancelled(),
        )
    )
    made = outcome.outputs[0]
    assert made.mesh.triangle_count != mesh.triangle_count, "die Vorbedingung: ein neues Netz"
    for name, feature in detected.items():
        carried = made.features[name]
        assert carried.params == feature.params, name
        assert carried.face_indices == () and carried.surface_patches == (), (
            f"{name} trägt Dreiecke eines Netzes, das die Operation nicht ausgibt"
        )
    assert all(
        max(feature.face_indices, default=-1) < made.mesh.triangle_count
        for feature in made.features.values()
    )


def test_multiple_targets_keep_findings_with_distinct_locations(
    profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Gleicher Text an verschiedenen Stellen bleibt zweimal anklickbar."""
    from app.core.scene.cancel import NeverCancelled
    from app.core.types import Finding, OpContext, OpResult, Scene, SceneObject

    spec = PARTS.get("snap_fit")
    source = SceneObject(id="obj_1", name="Platte", mesh=spec.fn(spec.params()).mesh)
    params = REGISTRY.get("insert_snap_fit").params(at_features=("left", "right"))

    def placed(ctx: OpContext, _spec: PartSpec) -> OpResult:
        target = str(ctx.params.at_feature)  # type: ignore[attr-defined]
        return OpResult(
            outputs=[source],
            findings=[
                Finding(
                    code="test.warning",
                    severity="warning",
                    message="Stelle prüfen.",
                    feature_ids=(target,),
                    location=(-1.0 if target == "left" else 1.0, 0.0, 0.0),
                )
            ],
        )

    monkeypatch.setattr(part_ops, "_insert_at", placed)
    outcome = part_ops.insert(
        OpContext(
            scene=Scene(objects={source.id: source}),
            inputs=[source],
            params=params,
            profile=profile,
            quality="draft",
            seed=None,
            progress=lambda fraction, text: None,
            ask=lambda question, choices: choices[0],
            cancelled=NeverCancelled(),
        ),
        spec,
    )
    assert [entry.feature_ids for entry in outcome.findings] == [("left",), ("right",)]
    assert outcome.findings[0].location != outcome.findings[1].location


@pytest.mark.parametrize(
    ("name", "axis", "code"),
    [
        ("living_hinge", "x", "parts.standing_on_edge"),
        ("living_hinge", "z", ""),
        ("pegboard_hook", "z", "parts.up_points_nowhere"),
        ("pegboard_hook", "y", ""),
        ("snap_fit", "z", "part.spring_overloaded"),
    ],
)
def test_standalone_parts_run_their_orientation_and_material_guards(
    profile: Profile, name: str, axis: str, code: str
) -> None:
    """Die Erzeugeroperation löst dieselben Druckbedingungen ein wie Einsetzen."""
    from app.core.scene.cancel import NeverCancelled
    from app.core.types import OpContext, Scene

    spec = dataclasses.replace(PARTS.get(name), standalone=True)
    registry = type(REGISTRY)()
    parts = PartRegistry()
    parts.register(spec)
    part_ops.register_all(parts, registry)
    operation = registry.get(f"create_{name}")
    values: dict[str, Any] = {"axis": axis}
    if name == "snap_fit":
        values.update(length=21.0, thickness=2.0, hook=1.2)
    outcome = operation.fn(
        OpContext(
            scene=Scene(),
            inputs=[],
            params=operation.params(**values),
            profile=profiles.make_profile("centauri-carbon-2", "pla"),
            quality="draft",
            seed=None,
            progress=lambda fraction, text: None,
            ask=lambda question, choices: choices[0],
            cancelled=NeverCancelled(),
        )
    )
    warnings = [
        entry
        for entry in outcome.findings
        if entry.code
        in {"parts.standing_on_edge", "parts.up_points_nowhere", "part.spring_overloaded"}
    ]
    assert [entry.code for entry in warnings] == ([code] if code else [])
    assert outcome.outputs[0].mesh.is_watertight


def test_parts_without_host_tools_declare_every_feature() -> None:
    """Ohne Trägerwerkzeug gehört jedes Merkmal zum geprüften Bausteinkörper.

    Ein host_cut darf zusätzliche Merkmale erst am Träger erzeugen; sie
    werden nicht am eigenständigen Bausteinkörper verlangt.
    """
    for spec in PARTS.all():
        if spec.host_cut is not None:
            continue
        assert set(spec.features) <= {entry.name for entry in spec.feature_requirements}, spec.name


@pytest.mark.parametrize("depth", [0.0, 2.0])
def test_the_screw_head_room_is_declared_exactly_when_it_is_built(depth: float) -> None:
    """Eine zylindrische Kopfzone über null ist ein erlaubtes und gefordertes Merkmal."""
    spec = PARTS.get("screw_hole")
    values = dataclasses.asdict(spec.params(head_room=depth))
    result = spec.fn(spec.params(head_room=depth))
    declared = [entry for entry in spec.feature_requirements if entry.name == "head_room"]
    assert len(declared) == 1
    assert declared[0].applies(values) is (depth > 0.0)
    assert ("head_room_1" in result.features) is (depth > 0.0)


@pytest.mark.parametrize(
    "stage", ["mesh", "wall", "measurement", "intersection", "gap", "features", "feasible"]
)
def test_a_broken_check_reports_its_corner_and_continues(
    profile: Profile, monkeypatch: pytest.MonkeyPatch, stage: str
) -> None:
    """Auch nach dem Bau darf ein einzelner Prüffehler den Bericht nicht verlieren."""
    import trimesh

    from app.core.geom import mesh as mesh_module
    from app.core.knowledge.parts import range_check
    from app.core.types import Feature

    @op_params
    class PairParams(BaseParams):
        size: float = param(title="Maß", default=1.0, minimum=1.0, maximum=2.0)

    body = MeshData.of(trimesh.load(MESHES / "cube_clean.stl"))
    result = PartResult(
        mesh=body,
        features={
            "face_1": Feature(
                id="face_1", kind="face", provenance="generated", params={"area": 400.0}
            )
        },
    )
    built: list[float] = []

    def build(values: BaseParams) -> PartResult:
        built.append(float(values.size))  # type: ignore[attr-defined]
        return result

    calls = 0

    def first_fails(*args: Any, **kwargs: Any) -> Any:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise ValueError("Prüfsonde: Parameter oder Geometrie korrigieren.")
        return original(*args, **kwargs)

    targets = {
        "mesh": (mesh_module, "as_mesh_data"),
        "wall": (WallRequirement, "minimum"),
        "measurement": (range_check, "local_wall_thickness"),
        "intersection": (range_check, "has_self_intersections"),
        "gap": (range_check, "printable_gap"),
        "features": (FeatureRequirement, "applies"),
    }
    feasible = None
    if stage == "feasible":

        def original(_values: BaseParams) -> str:
            return ""

        feasible = first_fails
    else:
        target, name = targets[stage]
        original = getattr(target, name)
        monkeypatch.setattr(target, name, first_fails)
    report = check_range(
        PairParams,
        build,
        profile,
        feasible=feasible,
        bodies=2 if stage == "gap" else 1,
        features=(FeatureRequirement("face"),),
    )

    assert report.checked == 2
    assert built[-1] == pytest.approx(2.0)
    matching = [failure for failure in report.failures if "Prüfsonde" in failure.reason]
    assert len(matching) == 1
    assert matching[0].values == {"size": 1.0}
    assert not report.passed


@pytest.mark.parametrize("during_build", [True, False])
def test_an_explicit_range_cancellation_does_not_turn_into_a_failed_corner(
    profile: Profile, monkeypatch: pytest.MonkeyPatch, during_build: bool
) -> None:
    """Auch ein geworfener Kernabbruch ohne äußeres Token erhält nur den Teilbericht."""
    from app.core.errors import OperationCancelled
    from app.core.knowledge.parts import range_check

    @op_params
    class PairParams(BaseParams):
        size: float = param(title="Maß", default=1.0, minimum=1.0, maximum=2.0)

    calls = 0

    def stop(*args: Any, **kwargs: Any) -> Any:
        nonlocal calls
        calls += 1
        raise OperationCancelled

    spec = PARTS.get("gusset")
    build = stop if during_build else lambda _values: spec.fn(spec.params())
    if not during_build:
        monkeypatch.setattr(range_check, "local_wall_thickness", stop)
    report = check_range(PairParams, build, profile)
    assert calls == 1
    assert report.checked == 0
    assert len(report.failures) == 1
    assert "abgebrochen" in report.failures[0].reason.lower()
    assert not report.passed


def test_cancelling_after_a_failed_corner_keeps_both_failure_and_progress(profile: Profile) -> None:
    """Ein vorhandener Fehler verschluckt nicht, dass der Rest ungeprüft blieb."""
    from app.core.errors import OperationCancelled

    @op_params
    class PairParams(BaseParams):
        size: float = param(title="Maß", default=1.0, minimum=1.0, maximum=2.0)

    calls = 0

    def build(_values: BaseParams) -> PartResult:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise ValueError("Erste Ecke: Geometrie korrigieren.")
        raise OperationCancelled

    report = check_range(PairParams, build, profile)
    assert report.checked == 1
    assert len(report.failures) == 2
    assert report.failures[0].values == {"size": 1.0}
    assert "abgebrochen" in report.failures[1].reason.lower()
    assert "1 von 2" in report.failures[1].reason
    assert not report.passed


def test_an_invalid_wall_declaration_is_reported_at_each_corner(profile: Profile) -> None:
    """Ein fehlender Wandparameter bleibt ein Vertragsfehler im Bereichsbericht."""
    import trimesh

    @op_params
    class PairParams(BaseParams):
        size: float = param(title="Maß", default=1.0, minimum=1.0, maximum=2.0)

    body = MeshData.of(trimesh.load(MESHES / "cube_clean.stl"))
    report = check_range(
        PairParams,
        lambda _values: PartResult(mesh=body),
        profile,
        wall=WallRequirement.from_parameter("missing_wall"),
    )
    assert report.checked == 2
    assert len(report.failures) == 2
    assert all("missing_wall" in entry.reason for entry in report.failures)
    assert not report.passed


def test_range_check_cancels_inside_local_geometry_and_keeps_progress_monotonic(
    profile: Profile,
) -> None:
    """2.114 Ecken dürfen lang dauern, aber nie unabbrechbar sein."""
    import trimesh

    @op_params
    class ManyFaces(BaseParams):
        size: float = param(title="Maß", default=8.0, minimum=6.0, maximum=10.0)

    class CancelInsideWall:
        calls = 0

        @property
        def is_cancelled(self) -> bool:
            self.calls += 1
            return self.calls > 20

        def raise_if_cancelled(self) -> None:
            return None

    def sphere(values: BaseParams) -> PartResult:
        return PartResult(
            mesh=MeshData.of(
                # RM-050: Die Wandstärke fragt seither ``ray_hits_batch``, blockweise
                # über die Dreiecksachse statt einmal je Dreieck (VTKs Locator vorher).
                # Bei 1280 Dreiecken (``subdivisions=3``) reichte ein einziger Block,
                # und der Abbruch griff erst in der zweiten Ecke statt in der ersten.
                # Vier Unterteilungen (5120 Dreiecke) geben genug Blöcke, damit der
                # Abbruch wieder mitten in der ersten Ecke greift.
                trimesh.creation.icosphere(subdivisions=4, radius=float(values.size))  # type: ignore[attr-defined]
            ),
            features={
                "face_1": Feature(
                    id="face_1",
                    kind="face",
                    provenance="generated",
                    params={"area": 1.0},
                )
            },
        )

    from app.core.types import Feature

    seen: list[float] = []
    report = check_range(
        ManyFaces,
        sphere,
        profile,
        cancelled=CancelInsideWall(),
        progress=lambda value, _text: seen.append(value),
        features=(FeatureRequirement("face"),),
    )

    assert report.checked == 0, "eine halb geprüfte Ecke zählt nicht"
    assert seen == sorted(seen)
    assert seen and seen[-1] < 1.0


@pytest.mark.parametrize("spec", PARTS.all(), ids=ids)
def test_a_part_names_the_features_it_promised(spec: PartSpec) -> None:
    """§24.1: was die Deklaration verspricht, muss aus der Funktion
    herauskommen. Leitprinzip 4 verlangt dieselbe Geometrie beim zweiten Bau.

    Beide Aufrufe bekommen frische Parameter; nur das erste Ergebnis trägt
    zusätzlich die Merkmalsprüfung, statt dafür ein drittes Mal zu bauen.
    """
    first = spec.fn(spec.params())
    second = spec.fn(spec.params())

    # Beide Zusagen melden zusammen; eine rote Merkmalsliste verdeckt keine
    # fehlende Reproduzierbarkeit.
    problems = [] if first.features else [f"{spec.name} returned no features"]
    for name, feature in first.features.items():
        if feature.id != name:
            problems.append(f"{spec.name}.{name} carries the id {feature.id!r}")
        if feature.provenance != "generated":
            problems.append(f"{spec.name}.{name} has provenance {feature.provenance!r}")
        if not feature.params:
            problems.append(f"{spec.name}.{name} carries no dimensions")
    if first.mesh.volume != pytest.approx(second.mesh.volume, rel=1e-9):
        problems.append(f"{spec.name}: volume {first.mesh.volume} != {second.mesh.volume}")
    if first.mesh.triangle_count != second.mesh.triangle_count:
        problems.append(
            f"{spec.name}: {first.mesh.triangle_count} != {second.mesh.triangle_count} triangles"
        )
    assert not problems, "\n".join(problems)


def by_direction(subtractive: bool) -> list[tuple[PartSpec, BaseParams]]:
    """Je Baustein und Richtung ein Paar aus Bauplan und Werten.

    **Drei Bausteine fielen durch beide Netze.** Passstift, Standfuß und
    Schnappverbinder entscheiden die Richtung über einen Parameter; sie sind
    weder ``spec.subtractive`` (das gilt nur für die fest abtragenden) noch
    ``not cuts(spec, None)`` (ohne Werte zählt ein umschaltbarer als
    abtragend). Der subtraktive Test kannte sie damit nicht und der additive
    auch nicht — gemessen am 25.08.2026 prüfte niemand, ob die Fußtasche
    überhaupt ins Material reicht.

    **Der Fehler, der dort tatsächlich saß, wäre auch damit nicht aufgefallen:**
    Der Sitz der Tasche war um zwei Fasen zu eng für den Fuß, für den sie
    gedacht ist, und ins Material reichte sie trotzdem. Ein geschlossenes Netz
    ist keine geprüfte Zusage; dafür steht
    :func:`test_the_pocket_takes_the_foot_it_is_meant_for` daneben. Das Loch
    hier zu schließen ist trotzdem richtig — ein Loch **zwischen** zwei Listen
    ist schlechter als eines in einer: Beide sahen vollständig aus, und was
    dazwischen durchfiel, tauchte in keiner Fehlliste auf.

    Die Richtung kommt deshalb aus derselben Quelle wie für die Operation
    selbst (``cuts_by_parameter``) und nicht aus einer Eigenschaft, die sie nur
    halb beschreibt.
    """
    pairs: list[tuple[PartSpec, BaseParams]] = []
    for spec in PARTS.all():
        choice = part_ops.cuts_by_parameter(spec.params)
        if choice is None:
            if spec.subtractive is subtractive:
                pairs.append((spec, spec.params()))
            continue
        name, cutting = choice
        entry = next(item for item in spec.params.spec() if item.name == name)
        # **Ein Schalter hat keine ``choices`` und trotzdem zwei Stellungen.**
        # ``printed_thread`` entscheidet über ``internal: bool``, und die erste
        # Fassung dieser Funktion las nur ``entry.choices`` — für einen
        # bool-Parameter ist das ``None``, und der Baustein fiel damit erneut
        # durch beide Netze, obwohl die Funktion genau dagegen geschrieben war.
        values = entry.choices or ((False, True) if entry.kind == "bool" else ())
        for value in values:
            if (value in cutting) is subtractive:
                pairs.append((spec, spec.params(**{name: value})))
    return pairs


def direction_ids(pair: tuple[PartSpec, BaseParams]) -> str:
    spec, values = pair
    choice = part_ops.cuts_by_parameter(spec.params)
    if choice is None:
        return spec.name
    return f"{spec.name}[{getattr(values, choice[0])}]"


SUBTRACTIVE = by_direction(subtractive=True)


@pytest.mark.parametrize("pair", SUBTRACTIVE, ids=direction_ids)
def test_a_subtractive_part_reaches_into_the_material(
    pair: tuple[PartSpec, BaseParams],
) -> None:
    """§24.1: der Ursprung ist die Mündung, das Werkzeug geht nach unten.

    Wer eine Fläche anklickt, bekommt ihre Höhe in die Position eingetragen.
    Ein Werkzeug, das von dort nach *oben* wächst, steht in der Luft und trägt
    nichts ab — genau das taten Magnettasche, Schlüsselloch und
    Kabeldurchführung, bis die Bibliothek auf Version 2 ging.

    Gemessen wird an der Wirkung, nicht an den Koordinaten: der Baustein sitzt
    auf der Oberseite einer Platte, und danach hat sie weniger Volumen.

    **Die Mutternfalle baut nach oben**, weil die Mutter im Material sitzt; an
    einer Fläche spiegelt die Operation sie (``ops._builds_upward_on_a_face``),
    und genau so wird sie hier gesetzt. Bis RM-631 trug sie auch ungespiegelt
    ab — mit dem Schraubenloch, das 10 mm unter die Tasche reichte.
    """
    spec, values = pair
    plate = shapes.box(60.0, 60.0, 20.0)
    made = as_mesh_data(spec.fn(values).mesh)
    flip = part_ops._extends_above_mouth(made)
    tool = shapes.moved(part_ops._place(made, values, flip=flip), (0.0, 0.0, 20.0))
    cut = boolean("difference", [plate, tool])

    assert cut.mesh.volume < plate.volume - 1.0, (
        f"{direction_ids(pair)} trägt an der angeklickten Fläche nichts ab"
    )


@pytest.mark.parametrize("pair", SUBTRACTIVE, ids=direction_ids)
def test_a_subtractive_part_reaches_past_its_mouth(pair: tuple[PartSpec, BaseParams]) -> None:
    """Ein Werkzeug endet nicht in der Fläche, die es schneidet (§39).

    ``ops._insert_at`` senkt abtragende Bausteine nicht ein, weil ihr
    Werkzeug „ohnehin über die Fläche hinausreicht" — bis zum 22.09.2026
    stimmte das für fünf nicht: Passbohrung, Fußtasche (ihr Änderungsverlauf
    versprach es seit Version 2), Innengewinde, Rasttasche und Dichtnut
    endeten genau bei z = 0.
    """
    from app.core.geom.boolean import BOOLEAN_OVERLAP

    spec, values = pair
    mesh = spec.fn(values).mesh
    assert float(mesh.bounds.maximum[2]) >= BOOLEAN_OVERLAP - 1e-9, direction_ids(pair)


@pytest.mark.parametrize("spec", PARTS.all(), ids=ids)
def test_a_named_face_lies_on_the_face_it_names(spec: PartSpec, profile: Profile) -> None:
    """Die Mitte einer benannten Fläche liegt auf ihr, und die Normale stimmt.

    Ein Merkmal ist eine Zusage an den nächsten Schritt (§24.1). Bis zum
    22.09.2026 lagen sechs daneben: Rippe und Nutfeder nannten einen Punkt
    im Material, Wandhalter und Scharnier einen in der Mitte der Platte, die
    Wandleiter einen unter einer Wand, der Schnappverbinder einen in der
    Mitte seines Arms. Geprüft werden die Flächen, die ein Baustein aus seinen
    Maßen erklärt; wer Dreiecke mitbringt (``face_indices``), benennt eine
    gemessene Fläche, deren Schwerpunkt bei einem Ring in der Öffnung liegt.
    An einem Werkzeug ist die Fläche die des Trägers und schaut in das
    Werkzeug hinein.
    """
    import math

    import trimesh

    values = {"play": profile.material.clearance} if "play" in _names(spec) else {}
    built = spec.fn(spec.params(**values))
    mesh = built.mesh.raw
    tool = part_ops.cuts(spec, spec.params(**values))
    for name, feature in built.features.items():
        if feature.kind != "face" or feature.face_indices:
            continue
        centre = np.asarray(feature.params["centre"], dtype=float)
        nearest = trimesh.triangles.closest_point(
            mesh.triangles, np.repeat(centre[None, :], len(mesh.triangles), axis=0)
        )
        distance = np.linalg.norm(nearest - centre, axis=1)
        assert float(distance.min()) <= 1e-6, f"{spec.name}.{name}: {distance.min():.4f} mm daneben"
        touching = distance <= 1e-6
        normal = np.asarray(feature.params["normal"], dtype=float)
        agreement = mesh.face_normals[touching] @ normal
        expected = -1.0 if tool else 1.0
        # Eine Rundung ist am Netz ein Vieleck: Die Facette neben dem Punkt darf
        # um eine halbe Segmentbreite geneigt sein.
        facet = 1.0 - math.cos(math.pi / shapes.SEGMENTS) + 1e-6
        assert np.any(np.isclose(agreement, expected, atol=facet)), (
            f"{spec.name}.{name}: keine anliegende Fläche schaut nach {tuple(normal)}"
        )


def _names(spec: PartSpec) -> set[str]:
    return {entry.name for entry in spec.params.spec()}


# --- was die drei Neuen versprechen -------------------------------------------------
#
# Sie hatten keinen Test ihrer Zusage, und deshalb kamen drei Fehler durch, die
# jede Kennzahl bestanden: Die Fußtasche war zu eng für ihren Fuß, ihr Merkmal
# meldete einen anderen Durchmesser als das Loch, und die Fase des Fußes saß am
# falschen Ende. Volumen, Wasserdichtheit, Komponentenzahl und Hüllquader waren
# bei allen dreien in Ordnung.


def _section_diameter(mesh: Any, height: float) -> float:
    """Der größte Durchmesser eines Querschnitts auf dieser Höhe.

    Über einen Schnitt und nicht über die Eckpunkte: Ein extrudierter oder
    gedrehter Körper hat zwischen seinen Enden keine.
    """
    cut = mesh.raw.section(plane_origin=[0.0, 0.0, height], plane_normal=[0.0, 0.0, 1.0])
    assert cut is not None, f"nothing to measure at z={height}"
    points = np.asarray(cut.vertices, dtype=float)
    return 2.0 * float(np.hypot(points[:, 0], points[:, 1]).max())


@pytest.mark.parametrize(("height", "diameter"), [(5.0, 10.0), (30.0, 10.0), (3.0, 25.0)])
def test_the_foot_tapers_towards_the_table_and_not_towards_the_part(
    height: float, diameter: float
) -> None:
    """Die Verjüngung gehört ans Standende, sonst steht der Fuß auf seiner Kante.

    Ein Zylinder mit scharfer Kante bekommt beim Drucken einen Elefantenfuß:
    Die erste Schicht quetscht breiter als die zweite und steht als Grat vor.
    Ein Kegelstumpf, der zum Tisch hin schmaler wird, hat den Grat dort, wo
    ohnehin Luft ist.

    **Die erste Fassung setzte ihn ans Anbau-Ende** — genau umgekehrt zu dem
    Absatz, den ihr eigener Docstring schon so enthielt. Keine Kennzahl
    bemerkte es: Volumen, Wasserdichtheit und Hüllquader sind bei beiden Lagen
    identisch. Gemessen wird deshalb an zwei Querschnitten, und die Richtung
    steht zwischen ihnen.
    """
    spec = PARTS.get("foot")
    built = spec.fn(spec.params(kind="foot", diameter=diameter, height=height)).mesh

    at_part = _section_diameter(built, 0.15)
    at_table = _section_diameter(built, height - 0.15)
    assert at_table < at_part - 0.1, (
        f"h={height} d={diameter}: {at_part:.2f} mm at the part and {at_table:.2f} mm "
        "at the table — the foot stands on its sharp edge"
    )


@pytest.mark.parametrize(("height", "diameter"), [(5.0, 10.0), (30.0, 10.0), (3.0, 25.0)])
def test_the_pocket_takes_the_foot_it_is_meant_for(height: float, diameter: float) -> None:
    """Eine Tasche für einen Ø-10-Gummifuß muss zehn Millimeter weit sein.

    **Sie war es nicht.** Der Schaft wurde mit dem *schmalen* Kegeldurchmesser
    gebaut, also um zwei Fasen zu eng: Ein Ø-10-Fuß fand ein Loch von 9,05 mm
    vor, und an der Bereichsecke (Höhe 30, Ø 10) maß der Sitz noch einen
    einzigen Millimeter. Eine Einführschräge weitet die Mündung, sie verengt
    nicht den Sitz.

    Gemessen wird an der Stelle, an der der Fuß sitzt — am tiefen Ende, nicht
    an der Mündung, wo die Schräge das Ergebnis freundlich aussehen lässt.
    """
    spec = PARTS.get("foot")
    values = spec.params(kind="pocket", diameter=diameter, height=height, play=0.25)
    built = spec.fn(values).mesh

    seat = _section_diameter(built, -height + 0.15)
    assert seat >= diameter, f"h={height}: the seat measures {seat:.2f} mm for a {diameter} mm foot"

    mouth = _section_diameter(built, -0.15)
    assert mouth >= seat, "the lead-in chamfer narrows the mouth instead of widening it"
    assert mouth < seat + 4.0, (
        f"h={height}: the mouth flares to {mouth:.2f} mm over a {seat:.2f} mm seat — "
        "a lead-in chamfer is a bevel, not a funnel"
    )


def test_the_pocket_names_the_hole_it_actually_cuts() -> None:
    """Was das Merkmal meldet, muss das Loch auch messen.

    Ein Merkmal ist eine Zusage an den nächsten Schritt: Wer daran ausrichtet,
    rechnet mit der Zahl, die dort steht. ``foot_1`` nannte den vollen
    Durchmesser, während das Loch zwei Fasen enger war — eine Passung, die auf
    dem Papier stimmte und im Druck geklemmt hätte.
    """
    spec = PARTS.get("foot")
    values = spec.params(kind="pocket", diameter=10.0, height=5.0, play=0.25)
    built = spec.fn(values)
    named = built.features["foot_1"].params["diameter"]

    assert _section_diameter(built.mesh, -5.0 + 0.15) == pytest.approx(named, abs=0.15), (
        f"the feature promises {named:.2f} mm, the hole is something else"
    )


@pytest.mark.parametrize("chamfer", [0.0, 10.0], ids=("automatisch", "volle-vorgabe"))
def test_the_shortest_foot_has_no_internal_shelf(chamfer: float) -> None:
    """Die Fase darf die zugesagte Höhe nicht als dünne Ringschulter hinterlassen."""
    from app.core.units import EPS_DISPLAY

    spec = PARTS.get("foot")
    built = spec.fn(spec.params(kind="foot", diameter=3.0, height=0.6, chamfer=chamfer)).mesh
    measured = local_wall_thickness(built)

    assert built.is_watertight and built.component_count == 1
    assert float(built.bounds.size[2]) == pytest.approx(0.6, abs=EPS_DISPLAY)
    assert measured is not None
    assert measured >= 0.6 - EPS_DISPLAY


def test_the_gusset_names_the_middle_of_its_face_and_not_its_edge() -> None:
    """``gusset_1`` ist eine Fläche, und eine Fläche hat eine Mitte.

    Der Keil steht mit seiner Unterseite auf der Wand: in x über die Dicke
    zentriert, in y von 0 bis zum Schenkel (``shapes.wedge``). Genannt wurde als
    Mitte ``(0, 0, 0)`` — das ist die Vorderkante dieser Fläche und nicht ihr
    Mittelpunkt. Wer daran ausrichtet, setzt einen halben Schenkel daneben, bei
    der Vorgabe also 6 mm; §24.1 macht ein Merkmal aber zur Zusage an den
    nächsten Schritt.

    Geprüft wird gegen die Geometrie und nicht gegen die Formel: Der genannte
    Punkt muss auf der Auflagefläche liegen, und zwar in ihrem Inneren. Die alte
    Angabe lag auf ihrem Rand — ein Unterschied, den kein Volumen und kein
    Hüllquader zeigt.
    """
    from shapely.geometry import Point

    from app.core.slice.analysis import cross_section

    spec = PARTS.get("gusset")
    legs = 12.0
    built = spec.fn(spec.params(legs=legs, thickness=3.0))
    centre = built.features["gusset_1"].params["centre"]
    normal = built.features["gusset_1"].params["normal"]

    assert normal == (0.0, 0.0, -1.0), "die Auflagefläche schaut nach unten"
    assert centre[2] == pytest.approx(0.0), "sie liegt auf z = 0"

    # Ein Haar über der Fläche, weil ein Schnitt genau auf ihr entartet.
    footprint = cross_section(built.mesh, 0.01)
    assert footprint is not None and not footprint.is_empty, "nothing to stand on"

    assert footprint.contains(Point(centre[0], centre[1])), (
        f"gusset_1 nennt {centre[:2]}, und dort ist die Fläche nicht — "
        f"ihr Umriss reicht von y={footprint.bounds[1]:.2f} bis y={footprint.bounds[3]:.2f}"
    )
    assert centre[1] == pytest.approx(legs / 2.0)


def test_the_hinge_eye_names_the_axis_its_bore_actually_runs_on() -> None:
    """Die Drehachse liegt quer, nicht senkrecht.

    ``lying()`` legt den Zylinder um, damit die Achse parallel zur Fläche
    läuft — das ist der Sinn eines Scharniers. Das Merkmal sagte trotzdem
    ``(0, 0, 1)``, weil das die Vorgabe von :func:`bore` ist und niemand sie
    überschrieb. Ein Passstift, an ``eye_1`` ausgerichtet, stünde damit
    senkrecht aus dem Auge heraus statt hindurch.

    Geprüft wird beides gegeneinander: die genannte Achse und die, auf der das
    Loch wirklich liegt. Eine Angabe, die nur mit sich selbst übereinstimmt,
    ist keine.
    """
    spec = PARTS.get("hinge_eye")
    values = spec.params(pin=4.0, width=10.0, reach=8.0)
    built = spec.fn(values)
    named = tuple(built.features["eye_1"].params["axis"])

    assert named == pytest.approx((1.0, 0.0, 0.0)), f"eye_1 claims the axis is {named}"

    # Und das Loch liegt wirklich dort: Quer zur genannten Achse geschnitten
    # zeigt sich der Ring um die Bohrung — als zwei getrennte Konturen.
    across = built.mesh.raw.section(
        plane_origin=[0.0, values.reach, 0.0], plane_normal=[1.0, 0.0, 0.0]
    )
    assert across is not None, "nothing crosses the eye at all"
    assert len(across.entities) >= 2, (
        "a cut across the named axis shows one contour — the bore does not run there"
    )


def test_the_hinge_eye_lets_the_pin_through_that_it_asks_for() -> None:
    """Ein Auge für einen 4er Bolzen muss einen 4er Bolzen durchlassen.

    Die Zusage steht im Parameter: ``pin`` ist der Durchmesser des Bolzens, der
    hindurchgeht. Das Loch muss ihn samt Spiel aufnehmen, und es muss **durch**
    gehen — ein Sackloch hielte das Gegenstück nur auf einer Seite.

    **Gemessen wird das Loch, nicht das Merkmal.** Bis zum 26.08.2026 stand
    hier nur, was ``eye_1`` verspricht — ein Wert, den derselbe Baustein selbst
    hineinschreibt. Ein Subtraktionszylinder, der statt ``pin + play`` nur
    ``pin`` nimmt, hätte diese Prüfung bestanden und den Bolzen klemmen
    lassen: Das Merkmal wäre unverändert richtig geblieben. Quer zur Drehachse
    geschnitten zeigen sich zwei Konturen; der kleinere Zug ist die Bohrung,
    und ihre Weite ist die Antwort (dieselbe Art Messung wie beim Fuß, nur um
    die liegende Achse gedreht).
    """
    spec = PARTS.get("hinge_eye")
    for pin in (2.0, 4.0, 8.0):
        values = spec.params(pin=pin, width=10.0, reach=8.0, play=0.2)
        built = spec.fn(values)
        assert built.features["eye_1"].params["diameter"] >= pin, (
            f"pin={pin}: the bore is narrower than the pin it names"
        )
        assert built.features["eye_1"].params.get("through") is True, (
            f"pin={pin}: the bore does not go through, so no pin can pass"
        )
        assert built.mesh.is_watertight and built.mesh.component_count == 1, (
            f"pin={pin}: the eye falls apart"
        )

        across = built.mesh.raw.section(plane_origin=[0.0, 0.0, 0.0], plane_normal=[1.0, 0.0, 0.0])
        assert across is not None, f"pin={pin}: nothing crosses the eye at all"
        contours = [np.asarray(entry, dtype=float) for entry in across.discrete]
        assert len(contours) == 2, (
            f"pin={pin}: a cut across the axis shows {len(contours)} contours, "
            "so there is no ring to measure"
        )
        bore = min(contours, key=lambda entry: float(np.ptp(entry[:, 1])))
        assert float(np.ptp(bore[:, 1])) == pytest.approx(pin + values.play, abs=0.05), (
            f"pin={pin}: the hole measures {float(np.ptp(bore[:, 1])):.2f} mm, "
            f"a {pin} mm pin with {values.play} mm play needs {pin + values.play:.2f}"
        )


def test_the_smallest_hinge_eye_keeps_its_declared_wall() -> None:
    """Die polygonale Kreisannäherung darf die zugesagte Wand nicht unterschreiten."""
    from app.core.geom.mesh import as_mesh_data
    from app.core.units import EPS_GEOM

    spec = PARTS.get("hinge_eye")
    values = spec.params(pin=1.0, width=2.0, reach=1.0, wall=0.8, play=0.0)
    measured = local_wall_thickness(as_mesh_data(spec.fn(values).mesh))

    assert int(spec.version) >= 13
    assert any(change.version == "13" for change in spec.changes) and spec.changes[-1].effect
    assert measured is not None
    assert measured >= values.wall - EPS_GEOM


def test_the_gusset_fills_the_corner_it_is_put_into() -> None:
    """Ein Eckwinkel, der die Ecke nicht berührt, hält nichts.

    Die Zusage ist eine Diagonale zwischen zwei Wänden: Der Körper muss an
    beiden anliegen und dazwischen Material haben. Ein Dreieck, das die Ecke
    verfehlt, sieht im Hüllquader genauso aus.
    """
    spec = PARTS.get("gusset")
    for wall in (0.8, 2.0, 5.0):
        built = spec.fn(spec.params(wall=wall)).mesh
        low = built.bounds.minimum

        assert built.is_watertight and built.component_count == 1, f"wall={wall}: falls apart"
        # Beide Schenkel beginnen an der Ecke, nicht daneben.
        assert abs(float(low[1])) < 0.05, f"wall={wall}: the gusset does not touch the wall"
        assert abs(float(low[2])) < 0.05, f"wall={wall}: the gusset does not touch the floor"

        # Und es ist eine Rampe, kein Quader: weiter unten als oben.
        high = float(built.bounds.maximum[2])
        near = built.raw.section(plane_origin=[0.0, 0.0, high * 0.1], plane_normal=[0.0, 0.0, 1.0])
        far = built.raw.section(plane_origin=[0.0, 0.0, high * 0.9], plane_normal=[0.0, 0.0, 1.0])
        assert near is not None, f"wall={wall}: nothing at the base"
        reach_near = float(np.asarray(near.vertices, dtype=float)[:, 1].max())
        reach_far = (
            float(np.asarray(far.vertices, dtype=float)[:, 1].max()) if far is not None else 0.0
        )
        assert reach_far < reach_near, (
            f"wall={wall}: the gusset reaches {reach_far:.1f} mm out at the top and "
            f"{reach_near:.1f} mm at the base — that is a block, not a brace"
        )


def test_the_keyhole_slot_runs_the_way_the_part_falls() -> None:
    """Ein Schlüsselloch mit waagerechtem Schlitz hält nicht.

    Die Schraube muss sich beim Absinken im schmalen Teil **verklemmen**. Liegt
    der Schlitz quer, wandert sie darin seitlich hin und her und hält das Teil
    nur, solange niemand dagegenstößt.

    **Der Baustein lag drei Wochen lang quer, und sein Docstring sagte das
    Gegenteil**: „Der Schlitz läuft in -Y." Der Versatz in Y stand auch
    richtig da — nur baut ``shapes.slot`` seine Länge immer in **X**, und ein
    Verschieben ist kein Drehen. Gemessen an ``keyhole(drop=8)`` waren es
    15,58 mm in X gegen 7,60 in Y, und 15,58 ist ``head + 0,6 + drop``, also
    der Schlitz selbst.

    Geprüft wird die Länge gegen die Breite, nicht der Quelltext: Ein Docstring
    hat hier schon einmal etwas anderes behauptet als der Code darunter.
    """
    spec = PARTS.get("keyhole")
    for drop in (4.0, 8.0, 16.0):
        built = spec.fn(spec.params(drop=drop)).mesh
        along = float(built.bounds.size[1])
        across = float(built.bounds.size[0])
        assert along > across, (
            f"drop={drop}: the keyhole measures {across:.2f} mm across and {along:.2f} mm "
            "along the direction it falls — the slot lies crosswise"
        )
        # Und der Schlitz wächst mit ``drop``: Er *ist* der Weg der Schraube.
        assert along == pytest.approx(across + drop, abs=0.2), (
            f"drop={drop}: the slot is {along:.2f} mm long, expected about "
            f"{across + drop:.2f} — the drop does not end up in the slot"
        )


def test_the_keyhole_puts_the_screw_above_the_hole_it_went_through() -> None:
    """Wo die Schraube endet, entscheidet, ob das Teil hängt.

    Der Kopf geht durch das runde Ende, dann sinkt das Teil — und die Schraube
    steht danach **relativ höher**, weil sich das Teil an ihr vorbei nach unten
    bewegt hat. Sitzt es umgekehrt, fällt das Teil beim Loslassen herunter.

    Im eigenen System des Bausteins heißt „oben" **-Y**: die Konvention von
    ``axis="y"``, dem auch ``PartSpec.keeps_up`` folgt. Geprüft wird an den
    benannten Merkmalen, denn genau die liest, wer das Gegenstück ausrichtet.
    """
    spec = PARTS.get("keyhole")
    built = spec.fn(spec.params(drop=8.0))

    mouth = built.features["pocket_1"].params["centre"]
    seat = built.features["bore_1"].params["centre"]
    assert float(seat[1]) < float(mouth[1]) - 1.0, (
        f"the screw ends at y={float(seat[1]):.1f} and the head goes in at "
        f"y={float(mouth[1]):.1f} — the part would drop off when let go"
    )
    # Der Kopf braucht mehr Platz als der Schaft, sonst kommt er nicht hinein.
    assert (
        built.features["pocket_1"].params["diameter"]
        > (built.features["bore_1"].params["diameter"])
    ), "the head opening is no wider than the shaft slot"


@pytest.mark.parametrize("kind", ["keyhole", "pegboard_hook", "lug"])
def test_a_part_that_knows_up_hangs_the_right_way_on_every_wall(kind: str) -> None:
    """``keeps_up`` gilt beiden gleich — und beinahe hätte es sie gegeneinander
    ausgespielt.

    Die Aufrichtung entstand für den Lochwand-Einhänger, und der baute sein
    Oben nach **+Y**. So kam es in die Funktion. Das Schlüsselloch baut seit je
    nach -Y und hatte damit recht: ``axis="y"`` dreht das eigene +Y nach
    Welt-unten, seit es diesen Weg gibt. Für einen Nachmittag richtete die
    Bibliothek deshalb die Bauweise **eines** Bausteins zur Regel für alle auf,
    und das Schlüsselloch hing verkehrt herum — Schraubensitz unten,
    Kopfdurchlass oben.

    Dieser Test prüft beide über dieselbe Frage: Was oben liegen soll, muss
    nach dem Setzen an eine senkrechte Wand **oben** liegen.
    """
    spec = PARTS.get(kind)
    assert spec.keeps_up, f"{kind} does not declare that it knows up"

    profile = profiles.make_profile("centauri-carbon-2", "petg")

    for face in ("face_4", "face_6"):
        # Je Fläche ein frisches Projekt: Zwei Bausteine nacheinander in
        # denselben Körper wären ein anderer Test.
        project = new_project("centauri-carbon-2", "petg")
        History(project.document).apply("Quader", [OperationDraft(op="create_box", params={})])
        History(project.document).apply(
            kind,
            [
                OperationDraft(
                    op=part_ops.op_name(kind), inputs=("obj_1",), params={"at_feature": face}
                )
            ],
        )
        result = evaluate(project.document, profile, sources=ProjectSources(project))
        assert result.complete, (
            f"{kind} at {face}: {[f.message for f in result.scene.report.findings]}"
        )

        placed = result.scene.objects["obj_1"].features
        # Was im eigenen System bei -Y liegt, muss in der Welt oben liegen.
        own = spec.fn(spec.params())
        upper = min(own.features, key=lambda name: float(own.features[name].params["centre"][1]))
        lower = max(own.features, key=lambda name: float(own.features[name].params["centre"][1]))
        if upper == lower:
            continue
        top = next(f for name, f in placed.items() if name.endswith(upper))
        bottom = next(f for name, f in placed.items() if name.endswith(lower))
        assert float(top.params["centre"][2]) > float(bottom.params["centre"][2]), (
            f"{kind} at {face}: '{upper}' should sit above '{lower}' and sits below"
        )


def test_every_change_log_climbs() -> None:
    """Eine Version, die nicht steigt, warnt niemanden.

    ``PartSpec.version`` wird aus dem **letzten** Eintrag des Verlaufs gelesen,
    nicht aus dem höchsten — das ist richtig so, denn der letzte Eintrag ist
    der Stand. Es setzt aber voraus, dass die Einträge aufsteigen, und das
    prüfte nichts.

    **Zweimal an einem Tag ging es schief, beide Male beim Beheben von etwas
    anderem.** Die Rippe stand auf 4; ein neuer Eintrag mit „2" senkte sie auf
    2, und ``changed_since`` meldete einem Projekt mit Stand 4 nichts mehr —
    die Maßänderung an dünnen Wänden wäre still durchgerechnet worden. Das
    Schlüsselloch stand auf 4 und bekam einen Eintrag mit „4": gleicher Stand,
    also keine Meldung, obwohl sich die Richtung seines Schlitzes gedreht
    hatte. Beide Bausteine sahen dabei völlig gesund aus, ihre Verläufe waren
    vollständig, jeder Eintrag hatte Datum, Grund und Wirkung.

    Und beide Fehler entstanden aus derselben Bequemlichkeit: einen neuen
    Eintrag zu schreiben, ohne den vorletzten zu lesen.

    **Ein dritter kam dazu, den niemand geschrieben hatte.** Der
    Schnappverbinder stand auf 4 und bekam ``FACE_GIVES_DIRECTION`` angehängt —
    einen Eintrag, den sechs Bausteine teilen und der die Version 4 trägt. Für
    die fünf anderen war das ein Schritt nach oben, für ihn keiner. Ein
    geteilter Eintrag trägt **eine** Zahl, und die passt nur, wenn alle, die
    ihn führen, vom selben Stand kommen. Geprüft wird das hier nicht eigens:
    Wo es nicht passt, steigt die Kette nicht, und das steht schon in der
    Bedingung darüber.
    """
    for spec in PARTS.all():
        versions = [change.version for change in spec.changes]
        assert versions, spec.name
        numbers = [int(version) for version in versions]
        for older, newer in itertools.pairwise(numbers):
            assert newer > older, (
                f"{spec.name}: the change log goes {' -> '.join(versions)} — "
                f"version {newer} does not climb past {older}, so a project saved "
                f"at {older} is never told the part moved"
            )
        assert spec.version == versions[-1], (
            f"{spec.name}: reports version {spec.version} but its log ends at {versions[-1]}"
        )


def test_the_nut_trap_takes_the_nut_it_is_named_after() -> None:
    """Eine M5-Falle muss eine M5-Mutter aufnehmen — ganz, nicht fast.

    **Sie tat es nicht, und zwar bei der verbreitetsten Größe.** Die
    Mutternhöhen der Tabelle waren die der zurückgezogenen DIN 934, und die
    weicht von ISO 4032 in genau drei Größen ab: M5 stand auf 4,00 statt 4,70,
    M6 auf 5,00 statt 5,20, M8 auf 6,50 statt 6,80. Für M2 bis M4 sind beide
    Normen gleich — deshalb fiel es an keiner Stelle auf, an der jemand
    nachgemessen hätte.

    Geprüft wird gegen die Norm und nicht gegen die Tabelle: Wer die Erwartung
    aus derselben Quelle nimmt wie den Prüfling, prüft nur, ob sich etwas
    geändert hat.
    """
    #: Höhe m max nach ISO 4032, abgeschrieben aus der Norm und nicht aus
    #: ``standards.toml`` — sonst prüfte sich die Tabelle selbst.
    iso_4032 = {"M2": 1.6, "M2.5": 2.0, "M3": 2.4, "M4": 3.2, "M5": 4.7, "M6": 5.2, "M8": 6.8}

    spec = PARTS.get("nut_trap")
    for size, height in iso_4032.items():
        if size not in standards.nut_sizes():
            continue
        assert standards.nut(size).height >= height - 0.01, (
            f"{size}: the table says the nut is {standards.nut(size).height} mm tall, "
            f"ISO 4032 says {height} — a real nut does not fit the pocket"
        )
        built = spec.fn(spec.params(size=size)).mesh
        deep = float(built.bounds.size[2])
        assert deep >= height, f"{size}: the trap is {deep:.2f} mm deep for a {height} mm nut"


@pytest.mark.parametrize("play", [0.0, 0.2, 0.35])
def test_the_magnet_lip_is_narrower_than_the_magnet(play: float) -> None:
    """Eine Haltelippe, die nichts festhält, ist ein Wort im Dialog.

    **Sie hielt in keiner Einstellung.** Der Kegel stand neben dem
    Taschenzylinder und wurde mit ihm vereinigt — und ein Volumen, das man
    einem anderen hinzufügt, kann es nur weiter machen, nie enger. Das Werkzeug
    war über die ganze Höhe zylindrisch, die Lippe verschwand darin. Dazu
    verengte sie um feste 0,2 mm gegenüber der bereits um das Profilspiel
    aufgeweiteten Tasche, also um weniger als nichts: Bei den 0,20 bis 0,35 mm
    der Materialprofile wäre die Öffnung selbst dann weiter als der Magnet
    gewesen, wenn die Boolesche Operation mitgespielt hätte. Zwei Fehler
    übereinander, und beide zeigten dieselbe harmlose Zahl.

    Gemessen wird an der **engsten** Stelle, und die liegt an der Mündung: Ein
    Querschnitt durch die Mitte des Kegels zeigt den Mittelwert und damit ein
    freundlicheres Bild, als das Teil verdient — die erste Fassung dieser
    Messung tat genau das und meldete „hält nicht" für einen Stand, der hielt.
    """
    from app.core.knowledge import standards

    spec = PARTS.get("magnet_pocket")
    entry = standards.magnet("6x3")
    built = spec.fn(spec.params(size="6x3", play=play, press_lip=True)).mesh

    cut = built.raw.section(plane_origin=[0.0, 0.0, -0.02], plane_normal=[0.0, 0.0, 1.0])
    assert cut is not None, "nothing at the mouth of the pocket"
    points = np.asarray(cut.vertices, dtype=float)
    mouth = 2.0 * float(np.hypot(points[:, 0], points[:, 1]).max())

    assert mouth < entry.diameter, (
        f"play={play}: the mouth is {mouth:.2f} mm wide for a {entry.diameter} mm magnet — "
        "the lip holds nothing"
    )
    # Und sie sperrt nicht: Der Magnet muss sich hineindrücken lassen.
    assert mouth > entry.diameter - 0.4, (
        f"play={play}: the mouth is {mouth:.2f} mm — that is a press the customer "
        "cannot push through"
    )


@pytest.mark.parametrize("grip", [0.05, 0.1, 0.3])
def test_the_magnet_lip_grips_by_the_amount_it_is_given(grip: float) -> None:
    """Das Übermaß der Haltelippe ist ein Wert, keine Zahl im Code.

    Es stand als feste 0,1 daneben, mit der Begründung, ein Übermaß sei keine
    Toleranz aus dem Profil. Genau das ist es aber: Das Materialprofil führt
    ``press`` (PLA und PETG -0,05, ABS und ASA -0,06, TPU -0,10), der Wert wird
    kalibriert (§28.3), und eine Zahl daneben untergräbt die Kalibrierung —
    dieselbe Tasche liest ihr Spiel längst aus dem Profil (Regel 7).

    Gemessen wird an der **engsten** Stelle, also an der Mündung: Der Kegel
    zeigt in seiner Mitte den Mittelwert und damit ein freundlicheres Bild, als
    das Teil verdient. Und gegen den Magneten, nicht gegen die Tasche — die ist
    um das Profilspiel weiter, und ein Übermaß dagegen wäre keines.
    """
    from app.core.knowledge import standards

    spec = PARTS.get("magnet_pocket")
    entry = standards.magnet("6x3")
    built = spec.fn(spec.params(size="6x3", play=0.25, press_lip=True, grip=grip)).mesh

    # Ein Tausendstel unter der Fläche und nicht zwei Hundertstel: Der Kegel
    # wird über 0,4 mm eng, ein Schnitt 0,02 tiefer liegt fünf Prozent seiner
    # Spanne daneben — bei 0,3 mm Übermaß sind das 0,03 mm, also mehr als die
    # Zusage selbst. Der Test darüber misst gröber, weil er nur „enger als der
    # Magnet" fragt; hier steht eine Zahl.
    cut = built.raw.section(plane_origin=[0.0, 0.0, -0.001], plane_normal=[0.0, 0.0, 1.0])
    assert cut is not None, "nothing at the mouth of the pocket"
    points = np.asarray(cut.vertices, dtype=float)
    mouth = 2.0 * float(np.hypot(points[:, 0], points[:, 1]).max())

    assert mouth == pytest.approx(entry.diameter - grip, abs=0.02), (
        f"grip={grip}: the mouth is {mouth:.2f} mm for a {entry.diameter} mm magnet — "
        "the lip does not grip by the amount it was given"
    )


def test_the_magnet_lip_falls_back_when_no_profile_reaches_the_part() -> None:
    """Null im Feld heißt „aus dem Profil" — und ohne Profil nicht „keine Lippe".

    ``PartSpec.fn`` bekommt kein Profil; eingefüllt wird der Wert erst vom
    Bausteinaufruf, so wie beim Spiel. Wo das nicht geschieht, muss die Lippe
    trotzdem halten: Null als Übermaß wäre eine Mündung so weit wie der Magnet,
    also der Zustand, den Version 5 gerade behoben hat.
    """
    from app.core.knowledge import standards
    from app.core.knowledge.parts.mounting import MAGNET_LIP_GRIP

    spec = PARTS.get("magnet_pocket")
    entry = standards.magnet("6x3")
    built = spec.fn(spec.params(size="6x3", play=0.25, press_lip=True)).mesh

    cut = built.raw.section(plane_origin=[0.0, 0.0, -0.001], plane_normal=[0.0, 0.0, 1.0])
    assert cut is not None
    points = np.asarray(cut.vertices, dtype=float)
    mouth = 2.0 * float(np.hypot(points[:, 0], points[:, 1]).max())

    assert mouth == pytest.approx(entry.diameter - MAGNET_LIP_GRIP, abs=0.02)


def test_a_part_that_needs_a_face_says_so_instead_of_guessing(profile: Profile) -> None:
    """Regel 21: nie stillschweigend raten — auch nicht über die Stelle.

    **Gefunden über die Oberfläche, nicht hier.** Im Bausteinkatalog wählt man
    einen *Baustein*, keine Fläche; „An Merkmal" steht dann auf „— keines —".
    Bestätigt man so, lief die Operation durch und setzte den Baustein in den
    Nullpunkt des Objekts: halb im Körper, halb unter dem Druckbett. Am
    Lochwand-Einhänger gemessen — 717 mm³ statt 2358, dazu vier Befunde, von
    denen keiner sagte, was fehlt.

    Kein Test hat das gesehen, und der Grund ist derselbe wie immer: **Jeder
    Test setzte ``at_feature``, weil jeder Test wusste, dass es gebraucht
    wird.** Der Kunde weiß es nicht.

    Was **nicht** verlangt wird, ist ein Merkmal um jeden Preis: Wer die
    Position von Hand einträgt, hat gewählt. Die ausgelieferten Beispiele tun
    genau das (siehe :func:`~app.core.knowledge.parts.ops._placed_by_hand`),
    und eine Prüfung nur auf das Merkmal hielt sieben von ihnen an.
    """
    project = new_project("centauri-carbon-2", "petg")
    History(project.document).apply("Quader", [OperationDraft(op="create_box", params={})])

    for spec in PARTS.all():
        if not (spec.at_face or spec.at_hole):
            continue
        step = new_project("centauri-carbon-2", "petg")
        History(step.document).apply("Quader", [OperationDraft(op="create_box", params={})])
        History(step.document).apply(
            spec.name,
            [
                OperationDraft(
                    op=part_ops.op_name(spec.name),
                    inputs=("obj_1",),
                    params=required_defaults(spec),
                )
            ],
        )
        result = evaluate(step.document, profile, sources=ProjectSources(step))

        assert not result.complete, (
            f"{spec.name} was placed without a face and without a position — "
            "it sits in the origin and nobody was asked"
        )
        messages = [str(finding.message) for finding in result.scene.report.findings]
        assert any("Position" in text or "Fläche" in text for text in messages), (
            f"{spec.name} stopped, but the report does not say what is missing: {messages}"
        )


def test_a_part_placed_by_hand_needs_no_feature(profile: Profile) -> None:
    """Wer die Position einträgt, hat gewählt — und wird nicht gefragt.

    Die Gegenprobe zur Prüfung darüber, und sie ist die wichtigere: Ohne sie
    wäre die Regel „ein Baustein braucht ein Merkmal", und das ist falsch. Die
    Mutternfalle des Beispielgehäuses steht auf (-25, -15, 4) mit leerem
    ``at_feature``, seit Monaten, und sie soll dort stehen bleiben.
    """
    project = new_project("centauri-carbon-2", "petg")
    History(project.document).apply("Quader", [OperationDraft(op="create_box", params={})])
    History(project.document).apply(
        "Rippe",
        [
            OperationDraft(
                op=part_ops.op_name("rib"), inputs=("obj_1",), params={"x": 5.0, "z": 2.0}
            )
        ],
    )
    result = evaluate(project.document, profile, sources=ProjectSources(project))

    assert result.complete, (
        "a part positioned by hand was refused: "
        f"{[str(f.message) for f in result.scene.report.findings]}"
    )


@pytest.mark.parametrize("spec", [s for s in PARTS.all() if s.joined_by_host], ids=lambda s: s.name)
def test_a_part_held_by_its_host_becomes_one_with_it(spec: PartSpec, profile: Profile) -> None:
    """Wer den Träger zum Zusammenhalten braucht, wird dort geprüft.

    Der Bereichstest verlangt sonst ``component_count == 1`` vom Baustein
    allein. Für einen Lochwand-Einhänger ohne Rückplatte stimmt das nicht: Zwei
    Haken sind zwei Zapfen, und verbunden werden sie von dem Teil, an das sie
    kommen — genau dafür sind sie da.

    **Die Zusage wandert damit, sie verschwindet nicht.** Was der Baustein
    allein nicht leisten muss, muss er am Träger leisten, und zwar in der
    Stellung, die am schwächsten ist: ohne Platte, mit mehreren Haken, am
    weitesten auseinander. Ein Test, der die Prüfung nur ausnimmt, hätte hier
    nichts mehr gesagt.
    """
    project = new_project("centauri-carbon-2", "petg")
    History(project.document).apply(
        "Quader",
        [OperationDraft(op="create_box", params={"width": 200.0, "depth": 120.0, "height": 20.0})],
    )
    History(project.document).apply(
        spec.name,
        [
            OperationDraft(
                op=part_ops.op_name(spec.name),
                inputs=("obj_1",),
                params={"at_feature": "face_top", "count": 3, "steps": 2, "plate": 0.0},
            )
        ],
    )
    result = evaluate(project.document, profile, sources=ProjectSources(project))

    assert result.complete, [str(f.message) for f in result.scene.report.findings]
    body = result.scene.objects["obj_1"].mesh
    assert body.component_count == 1, (
        f"{spec.name}: three hooks on a plate two grid steps apart do not become one body with it"
    )
    assert body.is_watertight, f"{spec.name}: the result is not printable"


def test_the_library_version_covers_every_part() -> None:
    """Die Bibliotheksversion muss den höchsten Baustein abdecken.

    ``changed_since_library`` fragt: Was hat sich seit dem Stand geändert, mit
    dem dieses Projekt gespeichert wurde? Verglichen wird gegen
    ``LIBRARY_VERSION`` — und wenn die hinter einem Baustein zurückbleibt,
    meldet die Prüfung eine Änderung und nennt dazu zwei gleiche Zahlen:
    „parts: rib, saved: 4, now: 4". Ein Befund, den niemand einordnen kann.

    **Am 25.08.2026 war es genau so.** Sieben Bausteine wanderten an einem Tag
    auf 5 und einer auf 6, die Bibliothek blieb auf 4. Jede einzelne Erhöhung
    war richtig und dokumentiert; mitzuziehen war nur diese eine Zahl, und sie
    steht in einer anderen Datei als die Änderungsverläufe.

    Der Test schließt die Lücke, die drei ähnliche Lücken heute schon hatten:
    eine Zahl, die von Hand mitwandern muss, wandert irgendwann nicht mit.
    """
    highest = max(int(spec.version) for spec in PARTS.all())
    assert int(LIBRARY_VERSION) >= highest, (
        f"the library says {LIBRARY_VERSION}, but a part is already at {highest} — "
        "changed_since_library would report a change and name two equal numbers"
    )


def _pinned(params: type[BaseParams], **fest: Any) -> type[BaseParams]:
    """Dieselbe Parameterklasse mit festgenagelten Grenzen.

    ``corners`` bildet je Zahlenfeld ``[minimum, maximum]`` und wirft
    Duplikate weg — wo beide gleich sind, bleibt **ein** Wert. Damit lässt
    sich ein Bereichstest auf die Ecke einschränken, um die es geht, ohne den
    Kern anzufassen oder die Prüfung zu verkürzen: Es sind dieselben
    Rechnungen an weniger Stellen.

    Bools bleiben zweiwertig — ``corners`` kennt für sie keine Grenzen —, und
    das ist richtig so: Wer eine Ecke festnagelt, soll nicht versehentlich
    einen Schalter mit festnageln, den er nicht bedacht hat.

    Gebaut über ``__param_spec__``, weil ``BaseParams.spec()`` genau das
    liest; die Dataclass-Felder bleiben unberührt, ein ``params(**werte)``
    funktioniert unverändert.
    """
    verengt = tuple(
        dataclasses.replace(entry, minimum=fest[entry.name], maximum=fest[entry.name])
        if entry.name in fest
        else entry
        for entry in params.spec()
    )
    unbekannt = set(fest) - {entry.name for entry in params.spec()}
    assert not unbekannt, f"kein solches Feld: {sorted(unbekannt)}"
    return type(f"{params.__name__}Pinned", (params,), {"__param_spec__": verengt})


def test_the_range_check_knows_which_parts_their_host_holds_together(
    profile: Profile,
) -> None:
    """Das Feld muss dort wirken, wo der Kunde die Folge sieht.

    ``joined_by_host`` stand einen Tag lang nur in einem Test. Der Bereichstest
    des **Kerns** kannte es nicht, und der ist der, dessen Bericht am
    Katalogeintrag hängt (§24.5): Ein Kunde hätte über dem Lochwand-Einhänger
    „zerfällt in Teile" gelesen — über einem Baustein, der im Einsatz tadellos
    ist.

    Das ist „eine Kette endet am letzten Glied“
    in Reinform: Ein Feld einzuführen ist nicht dasselbe, wie es zu lesen. Ich
    hatte beim Einbauen sogar den richtigen Satz geschrieben — „statt eine
    Ausnahme in den Test zu schreiben" — und dann genau das getan.
    """
    from app.core.knowledge.parts.range_check import check

    spec = PARTS.get("pegboard_hook")
    assert spec.joined_by_host, "der Einhänger deklariert es nicht mehr"

    # **Vier Ecken statt hundertachtundzwanzig, und das ist keine Verkürzung
    # der Zusage.** Sie gilt der *Wirkung des Schalters*, nicht dem Durchlaufen
    # des Parameterbereichs: `joined_by_host` muss im Kern ankommen, sonst
    # trüge der Katalogeintrag eine Warnung über einen tadellosen Baustein.
    # Dafür genügt die Ecke, an der der Einhänger zerfällt — gemessen am
    # 03.09.2026: `count=2, plate=0.0` gibt zwei Komponenten, mit Platte eine,
    # mit einem Haken eine.
    #
    # Der volle Bereich kostete hier 128 Ecken **zweimal** (streng und
    # nachsichtig), über 400 CPU-Sekunden, und blockierte einen ganzen
    # Torlauf allein — gemessen von 7b am selben Tag, sieben von acht Arbeitern
    # fertig, einer in `has_self_intersections`. Der Bereichstest über alle
    # Bausteine ist aus demselben Grund gefallen (`4bcb0272`); dieser hier
    # bleibt, weil er als einziger prüft, dass der Schalter wirkt.
    schmal = _pinned(spec.params, count=2, steps=1, plate=0.0, play=0.0, lip=0.0)

    strict = check(
        schmal,
        spec.fn,
        profile,
        wall=spec.wall,
        features=spec.feature_requirements,
    )
    assert not strict.passed, (
        "ohne den Schalter müsste der Einhänger an einer Ecke zerfallen — "
        "sonst prüft dieser Test nichts"
    )
    assert any("zerfällt" in failure.reason for failure in strict.failures), (
        f"unerwarteter Grund: {[f.reason for f in strict.failures]}"
    )

    lenient = check(
        schmal,
        spec.fn,
        profile,
        joined_by_host=True,
        wall=spec.wall,
        features=spec.feature_requirements,
    )
    assert lenient.passed, (
        f"mit dem Schalter darf nichts übrig bleiben: {[f.reason for f in lenient.failures]}"
    )
    assert lenient.checked == strict.checked, "es wurden verschieden viele Ecken gefahren"


@pytest.mark.parametrize(
    ("width", "steps", "loose"),
    [(20.0, 1, True), (60.0, 1, False), (60.0, 2, True), (200.0, 2, False)],
)
def test_a_part_beside_the_object_says_so(
    width: float, steps: int, loose: bool, profile: Profile
) -> None:
    """Was neben dem Teil hängt, wird gemeldet — auf Fehlerstufe.

    **Robert hat es an seinem Würfel gesehen.** Zwei Haken im Vierzigerraster
    stehen ±22,5 mm von der Mitte; auf einem 20 mm breiten Würfel berühren sie
    ihn nicht. Heraus kamen drei lose Stücke, wasserdicht und mit plausiblem
    Volumen, und der Prüfbericht führte „3 Teile" als **Angabe**: null Fehler,
    null Warnungen, zwei Hinweise. Wer nicht weiß, dass dort eine Eins stehen
    müsste, druckt sie.

    Seit die Rückplatte die Ausnahme ist, ist das der Preis dafür — und
    Roberts Entscheidung dazu war eindeutig: melden, und die Platte empfehlen.

    Gemessen wird am **Ergebnis**, nicht an der Breite der Zielfläche. Eine
    Fläche ist schnell nachgerechnet, trifft aber nicht jeden Fall: eine
    schmale Fläche auf einem breiten Teil, ein Loch dazwischen, eine Rundung —
    da stimmt die Rechnung und der Körper zerfällt trotzdem. Die vier Fälle
    hier decken beide Richtungen ab, damit die Prüfung nicht bloß immer
    „Fehler" sagt.
    """
    project = new_project("centauri-carbon-2", "petg")
    History(project.document).apply(
        "Quader",
        [OperationDraft(op="create_box", params={"width": width, "depth": width, "height": 20.0})],
    )
    History(project.document).apply(
        "Einhänger",
        [
            OperationDraft(
                op="insert_pegboard_hook",
                inputs=("obj_1",),
                params={"at_feature": "face_top", "count": 2, "steps": steps},
            )
        ],
    )
    result = evaluate(project.document, profile, sources=ProjectSources(project))
    assert result.complete, [str(f.message) for f in result.scene.report.findings]

    errors = [f for f in result.scene.report.findings if f.severity == "error"]
    hanging = [f for f in errors if f.code == "parts.hanging_loose"]
    body = result.scene.objects["obj_1"].mesh

    if loose:
        assert hanging, (
            f"width={width} steps={steps}: {body.component_count} Teile und kein Fehler — "
            "der Kunde druckt lose Stücke"
        )
        assert "Rückplatte" in str(hanging[0].message), (
            "der Befund empfiehlt die Rückplatte nicht (Regel 17)"
        )
    else:
        assert not hanging, (
            f"width={width} steps={steps}: Fehlalarm bei {body.component_count} Teilen"
        )
        assert body.component_count == 1, "der Träger hält den Baustein doch nicht"


def test_the_advice_for_a_loose_part_names_fields_that_part_has(profile: Profile) -> None:
    """Regel 17: ein Vorschlag, der trägt — und nicht einer, der ins Leere zeigt.

    ``parts.hanging_loose`` gilt für **jeden** anbauenden Baustein, und der
    Satz nannte trotzdem die Felder des Lochwand-Einhängers: „Geben Sie eine
    Rückplatte an … oder verringern Sie die Rasterschritte." Eine Rippe hat
    weder eine Rückplatte noch Rasterschritte, ein Scharnierauge und ein
    Kabelclip auch nicht — wer den Satz befolgen wollte, suchte zwei Felder,
    die es in seinem Dialog nicht gibt.

    Gefragt wird das Parameterschema des Bausteins, nicht sein Name: Der
    Zusatz erscheint dort, wo er einzulösen ist.
    """
    project = new_project("centauri-carbon-2", "petg")
    History(project.document).apply(
        "Quader",
        [OperationDraft(op="create_box", params={"width": 20.0, "depth": 20.0, "height": 20.0})],
    )
    History(project.document).apply(
        "Rippe",
        [OperationDraft(op="insert_rib", inputs=("obj_1",), params={"x": 100.0})],
    )
    result = evaluate(project.document, profile, sources=ProjectSources(project))

    assert result.complete, [str(f.message) for f in result.scene.report.findings]
    hanging = [f for f in result.scene.report.findings if f.code == "parts.hanging_loose"]
    assert hanging, "eine Rippe 100 mm neben dem Würfel hängt in der Luft und niemand sagt es"

    message = str(hanging[0].message)
    assert "Rückplatte" not in message and "Rasterschritte" not in message, (
        f"die Rippe hat weder das eine noch das andere Feld: {message}"
    )
    assert "Merkmal" in message or "Position" in message, (
        f"und ohne einen Weg nach vorn endet der Befund mit „fehlgeschlagen“: {message}"
    )


# --- die Normteiltabelle -----------------------------------------------------------


def test_the_table_answers_the_question_from_the_plan() -> None:
    """§24.2: „Loch für eine M4-Einpressbuchse" muss ein Nachschlagen sein."""
    assert standards.insert("M4").hole == pytest.approx(5.6)
    assert standards.screw("M4").clearance == pytest.approx(4.5)
    assert standards.nut("M4").width == pytest.approx(7.0)


def test_every_screw_size_has_a_matching_standard_washer() -> None:
    """Eine angebotene Schraube darf nicht erst beim Scheibensitz aus der Tabelle fallen."""
    assert set(standards.washer_sizes()) == set(standards.screw_sizes())


def test_heatset_entries_name_the_real_product_variant() -> None:
    """Eine Gewindegröße allein unterscheidet lange und kurze Buchsen nicht."""
    regular = standards.insert("M4")
    short = standards.insert("M4S")

    assert regular.thread == short.thread == "M4"
    assert regular.length == pytest.approx(8.1)
    assert short.length == pytest.approx(4.0)
    assert regular.outer == short.outer == pytest.approx(6.3, abs=0.01)


@pytest.mark.parametrize("lead_in", [False, True])
def test_the_m25_heatset_seat_uses_the_manufacturers_four_millimetre_hole(
    lead_in: bool,
) -> None:
    """Ruthex RX-M2,5x5,7: d1=4,6, d3=4,0 und L=5,7 im Herstellerdatenblatt."""
    entry = standards.insert("M2.5")
    spec = PARTS.get("heatset_m4")
    built = spec.fn(spec.params(size="M2.5", lead_in=lead_in, extra_depth=0.0))

    assert entry.outer == pytest.approx(4.6)
    assert entry.length == pytest.approx(5.7)
    assert entry.hole == pytest.approx(4.0)
    assert built.features["bore_1"].params["diameter"] == pytest.approx(4.0)
    assert built.mesh.bounds.size[:2] == pytest.approx((5.0, 5.0) if lead_in else (4.0, 4.0))
    assert built.mesh.is_watertight and built.mesh.component_count == 1


def test_every_heatset_insert_is_wider_than_its_installation_hole() -> None:
    """`outer == hole` war zweimal dieselbe Bohrung, kein Buchsenmaß."""
    for size in standards.insert_sizes():
        entry = standards.insert(size)
        assert entry.outer > entry.hole
        assert entry.thread in standards.screw_sizes()


def test_the_bearing_table_covers_small_and_common_housings() -> None:
    """Der Lagersitz soll nicht nur die eine Skateboardgröße anbieten."""
    assert {"623", "624", "625", "626", "608", "6800", "6000", "6001"} <= set(
        standards.bearing_sizes()
    )


def test_bearing_choices_are_ordered_by_the_shaft_they_fit() -> None:
    """Die Lagersitz-Auswahl steigt nach Wellendurchmesser, bei Gleichstand nach Nummer."""
    sizes = standards.bearing_sizes()
    assert len(sizes) >= 8
    assert sizes == tuple(sorted(sizes, key=lambda size: (standards.bearing(size).inner, size)))


def test_every_screw_has_the_holes_that_belong_to_it() -> None:
    for size in standards.screw_sizes():
        entry = standards.screw(size)
        assert entry.tap < entry.nominal < entry.clearance < entry.countersink
        assert entry.pitch > 0.0


def test_every_table_can_be_looked_up_by_its_kind() -> None:
    """§24.2 verlangt jede Tabelle als Nachschlagewert, und der Weg dorthin
    geht über ``standards.TABLES``.

    Die Zuordnung Art → Tabelle lag in ``agent/session.py``, mit einem
    ``getattr`` daneben — eine neunte Tabelle hätte also zwei Dateien
    gebraucht, und die zweite vergisst man still. Sie steht jetzt neben den
    Tabellen, und dieser Test hält beides zusammen: Jedes Feld von ``Tables``
    ist über eine Art erreichbar, und jede Art zeigt auf ein Feld, das es
    gibt.
    """
    import dataclasses

    tables = standards.load()
    fields = {
        field.name
        for field in dataclasses.fields(tables)
        if isinstance(getattr(tables, field.name), dict)
    }

    assert set(standards.TABLES.values()) == fields, (
        "Tabelle ohne Art oder Art ohne Tabelle — "
        f"benannt {sorted(standards.TABLES.values())}, vorhanden {sorted(fields)}"
    )
    for kind in standards.TABLES:
        found = standards.table(kind)
        assert found, f"{kind} liefert keine Tabelle"
    assert standards.table("kein-normteil") is None


def test_agent_and_table_offer_the_same_standard_kinds() -> None:
    """Eine neue Tabellenart erreicht Agent und Oberfläche ohne zweite Liste."""
    from app.core.agent.tools import STANDARD_KINDS

    assert tuple(standards.TABLES) == STANDARD_KINDS
    assert "board" in STANDARD_KINDS, "Lochwandmaße sind hinterlegt und müssen lesbar sein"


def test_every_typed_standard_table_offers_its_sizes() -> None:
    """Scheiben und Lager sind keine Tabellen zweiter Klasse."""
    assert standards.washer_sizes() == tuple(standards.load().washers)
    assert standards.bearing_sizes() == tuple(standards.load().bearings)


def test_duplicate_standard_sizes_are_rejected(tmp_path: Path) -> None:
    """Ein Tippfehler darf keinen älteren Datensatz still überschreiben."""
    table = tmp_path / "standards.toml"
    table.write_text(
        """
version = "test"

[[magnets]]
size = "8x3"
diameter = 8.0
height = 3.0

[[magnets]]
size = "8x3"
diameter = 9.0
height = 3.0
""".strip(),
        encoding="utf-8",
    )

    from app.core.errors import ValidationError

    with pytest.raises(ValidationError) as raised:
        standards.load(table)
    assert raised.value.values["size"] == "8x3"


def test_impossible_standard_dimensions_are_rejected(tmp_path: Path) -> None:
    """Innendurchmesser, Außenmaß und Verweise werden beim Laden geprüft."""
    table = tmp_path / "standards.toml"
    table.write_text(
        """
version = "test"

[[bearings]]
size = "verkehrt"
inner = 12.0
outer = 10.0
width = 4.0
""".strip(),
        encoding="utf-8",
    )

    from app.core.errors import ValidationError

    with pytest.raises(ValidationError) as raised:
        standards.load(table)
    assert raised.value.values["size"] == "verkehrt"


def test_an_unknown_size_says_what_is_known() -> None:
    from app.core.errors import ValidationError

    # M60 führt DIN 912 nicht als Zylinderschraube; die Tabelle springt von M56 auf M64.
    with pytest.raises(ValidationError) as raised:
        standards.screw("M60")
    assert "M56" in str(raised.value.values["known"])


# --- Die Operationen, die aus den Bausteinen entstehen ----------------------------


def test_every_part_became_an_operation() -> None:
    """§10, Leitprinzip 3: einmal deklariert, und jede Oberfläche folgt."""
    for spec in PARTS.all():
        assert REGISTRY.has(part_ops.op_name(spec.name)), spec.name


def test_a_part_operation_carries_its_own_parameters_and_a_place() -> None:
    spec = REGISTRY.get("insert_screw_hole")
    names = {entry.name for entry in spec.params.spec()}

    assert {"size", "depth", "countersink"} <= names, "the part's own parameters"
    assert {"x", "y", "z", "axis", "angle"} <= names, "and where it goes"
    assert spec.category == "parts"


def test_a_subtractive_part_removes_material(profile: Profile) -> None:
    project = project_with_plate()
    sources = ProjectSources(project)
    before = evaluate(project.document, profile, sources=sources).scene.objects["obj_1"]

    History(project.document).apply(
        "Buchse",
        [
            OperationDraft(
                op="insert_heatset_m4",
                inputs=("obj_1",),
                params={"size": "M3", "x": 0.0, "y": 0.0, "z": 4.0},
            )
        ],
    )
    result = evaluate(project.document, profile, sources=sources)

    assert result.complete, [f.message for f in result.scene.report.findings]
    after = result.scene.objects["obj_1"]
    assert after.mesh.volume < before.mesh.volume, "a pressed-in insert needs a hole"


def _plate_and(name: str, params: dict[str, Any], profile: Profile) -> tuple[Any, Any]:
    """Die Platte vorher und nachher, mit einem Baustein dazwischen."""
    project = project_with_plate()
    sources = ProjectSources(project)
    before = evaluate(project.document, profile, sources=sources).scene.objects["obj_1"]
    History(project.document).apply(
        name, [OperationDraft(op=name, inputs=("obj_1",), params=params)]
    )
    result = evaluate(project.document, profile, sources=sources)
    assert result.complete, [f.message for f in result.scene.report.findings]
    return before, result.scene.objects["obj_1"]


@pytest.mark.parametrize(
    ("name", "params"),
    [
        ("insert_dowel", {"diameter": 8.0, "length": 6.0, "shape": "hex"}),
        ("insert_snap_connector", {}),
    ],
)
def test_a_bore_removes_material_and_a_pin_adds_it(
    name: str, params: dict[str, Any], profile: Profile
) -> None:
    """Beide Bausteine sind ein **Paar**, und welche Hälfte gemeint ist,
    entscheidet der Parameter *Art* — nicht der Baustein.

    Gefunden beim Nachbau einer Sechskantverbindung: die Passbohrung rechnete
    ihr Spiel dazu, gab ein ``bore``-Merkmal zurück und setzte **+411,7 mm³**
    auf, also einen etwas dickeren Zapfen als der Zapfen. Beim
    Schnappverbinder war die „Tasche mit der Rastkante" +108,5 mm³, obwohl ihr
    Docstring seit je sagt: „was hier fehlt, bleibt im Bauteil stehen".
    """
    top = {"x": 0.0, "y": 0.0, "z": 8.0}

    before, gebohrt = _plate_and(name, {**params, **top, "kind": "bore"}, profile)
    _, gestiftet = _plate_and(name, {**params, **top, "kind": "pin"}, profile)

    assert gebohrt.mesh.volume < before.mesh.volume, "eine Bohrung nimmt weg"
    assert gestiftet.mesh.volume > before.mesh.volume, "ein Stift setzt auf"
    assert gebohrt.mesh.is_watertight and gestiftet.mesh.is_watertight
    assert gebohrt.mesh.component_count == 1, "die Bohrung zerlegt den Körper nicht"


def test_the_smallest_dovetail_pin_keeps_its_printable_cross_section(profile: Profile) -> None:
    """Der Umkreis bleibt Nennmaß, ohne den Formschluss unter zwei Bahnen zu drücken."""
    from app.core.units import EPS_DISPLAY

    spec = PARTS.get("dowel")
    diameter = 1.0
    built = spec.fn(
        spec.params(
            diameter=diameter,
            length=1.0,
            kind="pin",
            shape="dovetail",
            chamfer=0.0,
            play=profile.material.clearance,
        )
    ).mesh
    measured = local_wall_thickness(built)
    radial = np.hypot(built.raw.vertices[:, 0], built.raw.vertices[:, 1])

    assert built.is_watertight and built.component_count == 1
    assert float(radial.max()) <= diameter / 2.0 + EPS_DISPLAY
    assert measured is not None
    assert measured >= profile.minimum_wall_thickness - EPS_DISPLAY


def test_the_direction_is_declared_at_the_parameter() -> None:
    """§24: die Angabe steht dort, wo die Wahl getroffen wird — wie
    ``depends_on``.

    Drei Stellen lesen sie, und ohne eine Quelle hätte jede ihre eigene
    Version: die Operation (welche Boolesche Op), der Registereintrag (ob ein
    Flächenklick den Baustein anbietet) und die Vorschau (welche Farbe).
    """
    for name in ("dowel", "snap_connector"):
        spec = PARTS.get(name)
        assert part_ops.cuts_by_parameter(spec.params) == ("kind", ("bore",)), name
        assert part_ops.cuts(spec, spec.params(kind="bore")) is True, name
        assert part_ops.cuts(spec, spec.params(kind="pin")) is False, name
        # Ohne Werte gilt „kann abtragen": ``applies_to`` ist eine Reihenfolge
        # und keine Sperre, und beide Hälften werden auf eine Fläche gesetzt.
        assert part_ops.cuts(spec, None) is True, name
        assert "face" in REGISTRY.get(part_ops.op_name(name)).applies_to, name


def test_a_part_without_the_declaration_keeps_its_own_direction() -> None:
    """Die Gegenprobe — sonst hätte der neue Weg den alten überschrieben."""
    for name, subtractive in (("magnet_pocket", True), ("rib", False), ("heatset_m4", True)):
        spec = PARTS.get(name)
        assert part_ops.cuts_by_parameter(spec.params) is None, name
        assert part_ops.cuts(spec, spec.params()) is subtractive, name


def test_a_changed_bore_is_announced_to_old_projects() -> None:
    """§24.4: ein Baustein, dessen Maße sich ändern, wird beim Öffnen gemeldet.

    Hier ändert sich mehr als ein Maß — aus einem Buckel wird ein Loch. Wer die
    Bohrung bisher benutzt hat, muss das erfahren.

    Der Schnapper steht auf 4, weil Version 3 nur halb stimmte: Sie schob die
    Tasche unter ihre Mündung und nahm die Rastkante mit ans falsche Ende.
    """
    for name in ("dowel", "snap_connector"):
        spec = PARTS.get(name)
        letzte = spec.changes[-1]
        assert spec.version == letzte.version, name
        assert letzte.effect, name

    # **Und die Zusicherung, die keine feste Zahl braucht.** Vorher standen
    # hier zwei — „dowel" auf 2, „snap_connector" auf 4 —, und beide waren
    # der Stand vom Tag des Schreibens. Der erste Eintrag, der alle achtzehn
    # Bausteine zugleich betraf, machte sie falsch, obwohl an der Sache nichts
    # falsch war. Was gilt, ist die Übereinstimmung, nicht die Ziffer.
    for spec in PARTS.all():
        assert spec.changes, spec.name
        assert spec.version == spec.changes[-1].version, spec.name
        assert spec.changes[-1].effect or spec.changes[-1].version == "1", spec.name
        assert changed_since({name: "1"}) == (name,) or name in changed_since({name: "1"})


def test_an_additive_part_adds_material(profile: Profile) -> None:
    project = project_with_plate()
    sources = ProjectSources(project)
    before = evaluate(project.document, profile, sources=sources).scene.objects["obj_1"]

    History(project.document).apply(
        "Rippe",
        [
            OperationDraft(
                op="insert_rib",
                inputs=("obj_1",),
                params={"length": 20.0, "height": 6.0, "wall": 3.0, "z": 4.0},
            )
        ],
    )
    result = evaluate(project.document, profile, sources=sources)

    assert result.complete
    assert result.scene.objects["obj_1"].mesh.volume > before.mesh.volume


def test_the_features_of_a_part_reach_the_scene(profile: Profile) -> None:
    """§24.1, §21.1: eine Bohrung aus der Bibliothek ist von Anfang an
    benannt.
    """
    project = project_with_plate()
    History(project.document).apply(
        "Magnet",
        [
            OperationDraft(
                op="insert_magnet_pocket",
                inputs=("obj_1",),
                params={"size": "8x3", "x": 10.0, "y": 0.0, "z": 4.0},
            )
        ],
    )
    result = evaluate(project.document, profile, sources=ProjectSources(project))

    assert result.complete
    features = result.scene.objects["obj_1"].features
    assert "magnet_pocket_pocket_1" in features
    pocket = features["magnet_pocket_pocket_1"]
    assert pocket.provenance == "generated"
    assert pocket.params["centre"][0] == pytest.approx(10.0, abs=0.01)


def test_a_magnet_pocket_in_a_mesh_is_a_bore_with_its_lip(profile: Profile) -> None:
    """Am Netz ist die Magnettasche Bohrung und Haltelippe wie am exakten Körper (ERKENNUNG-11).

    Wand und Lippe knicken um 20,5 Grad gegeneinander, unter der Knickgrenze
    von 30 Grad, und lagen in einem Fleck, auf den weder Zylinder noch Kegel
    passte. Im Baum stand unter „Magnettasche“ eine „Gerundete Seite innen“,
    und die Tasche selbst trug keine Dreiecke — im Bild nicht zu treffen, von
    *Bohrung ändern* nicht zu finden. Die fünfte Runde teilt an der Naht: Die
    Tasche trägt die Wand, die Lippe ist ein Kegel an ihrer Mündung, und keine
    gerundete Seite bleibt übrig.
    """
    import math

    project = project_with_plate()
    History(project.document).apply(
        "Magnet",
        [
            OperationDraft(
                op="insert_magnet_pocket",
                inputs=("obj_1",),
                # Die Lochplatte liegt mittig: Oberseite bei z = 4.
                params={"size": "8x3", "x": 0.0, "y": 0.0, "z": 4.0},
            )
        ],
    )
    result = evaluate(project.document, profile, sources=ProjectSources(project))

    assert result.complete
    features = result.scene.objects["obj_1"].features
    pocket = features["magnet_pocket_pocket_1"]
    assert pocket.recognised and pocket.face_indices, "die Tasche ist im Bild zu treffen"
    at_the_pocket = {
        name: feature
        for name, feature in features.items()
        if "centre" in feature.params
        and math.dist(feature.params["centre"][:2], pocket.params["centre"][:2]) < 1.0
    }
    assert not [name for name, f in at_the_pocket.items() if f.kind == "curved_face"]
    lips = [feature for feature in at_the_pocket.values() if feature.kind == "cone"]
    assert len(lips) == 1, at_the_pocket
    assert set(lips[0].face_indices).isdisjoint(pocket.face_indices)


@pytest.mark.parametrize("box", ["create_box", "create_brep_box"])
def test_the_lip_of_a_magnet_pocket_is_a_narrowing_on_both_kernels(
    profile: Profile, box: str
) -> None:
    """Die Haltelippe heißt Verengung, am Netz wie am exakten Körper (R3).

    Der Baum nannte die Tasche „Sackbohrung 1 mit Senkung“ und die Lippe
    „Senkung“ — eine Senkung weitet die Mündung für einen Schraubenkopf, die
    Lippe macht sie enger, damit der Magnet nicht herausfällt. Die Erkennung
    trägt die Richtung in den Kegel (``narrowing``, ``opening``), und Baum,
    Maßspalte und Steckbrief nennen sie mit demselben Wort. Beide Kerne gleich:
    Am exakten Körper fragt ``brep.features.features_of`` dieselbe Regel an
    seiner Tessellierung.
    """
    from app.core.bootstrap import load_operations
    from app.core.geom.mesh import as_mesh_data
    from app.core.perceive.digest import _feature_line
    from app.core.perceive.relations import cavity_chains
    from app.ui.labels import cavity_name, feature_measure, feature_name, length

    load_operations()
    project = new_project("centauri-carbon-2", "petg")
    history = History(project.document)
    history.apply(
        "Quader",
        [OperationDraft(op=box, params={"width": 40.0, "depth": 40.0, "height": 10.0})],
    )
    history.apply(
        "Magnet",
        [
            OperationDraft(
                op="insert_magnet_pocket",
                inputs=("obj_1",),
                params={"size": "8x3", "x": 0.0, "y": 0.0, "z": 10.0},
            )
        ],
    )
    result = evaluate(project.document, profile, sources=ProjectSources(project))

    assert result.complete
    entry = result.scene.objects["obj_1"]
    features = entry.features
    pocket = features["magnet_pocket_pocket_1"]
    lips = [feature for feature in features.values() if feature.kind == "cone"]
    assert len(lips) == 1, features
    lip = lips[0]
    assert lip.params.get("narrowing") is True
    # Die Mündung ist enger als die Tasche und als der Magnet: Magnet minus
    # Übermaß der Lippe — die Zahl, die die Maßspalte jetzt nennt.
    assert 7.5 < lip.params["opening"] < 8.0 < pocket.params["diameter"]
    assert feature_name(lip.id, lip) == "Verengung"
    assert f"Ø{length(lip.params['opening'])}" in feature_measure(lip)
    chain = next(chain for chain in cavity_chains(features, as_mesh_data(entry.mesh)))
    assert cavity_name(chain[0].id, chain[0], chain) == "Sackbohrung 1 mit Verengung"
    line = _feature_line(lip.id, lip)
    assert "Verengung" in line and "Öffnung Ø " in line and "Senkung" not in line


@pytest.mark.parametrize("box", ["create_box", "create_brep_box"])
def test_a_chain_action_never_turns_the_lip_into_a_countersink(profile: Profile, box: str) -> None:
    """Kettenhandlungen an einer Magnettasche behalten die Lippe (R3).

    Der Einlauf einer Bohrung kannte nur den Kegel, der sich zur Mündung
    weitet (``prepare_ops._entrance_side``): *Bohrung ändern* mit Einlauf
    machte an beiden Kernen aus der Lippe eine Senkung (Mündung Ø 8,75 über
    der Tasche Ø 8,49), am exakten Körper ebenso *Merkmal verschieben* und
    *verdoppeln* — ohne einen Satz, und der Magnet hielt nicht mehr. Danach
    sagte der Einlauf an einer Verengung ab; seit der Durchsicht 0.5.1
    (rest-lippe) liest er sie mit ihrem eigenen Profil, die Verengung als
    letzten Abschnitt. *Bohrung ändern* nur an der Bohrung lässt ihre Öffnung,
    wo sie war, und sagt es — ohne *Senkung mitziehen*, das an ihr absagte;
    erst eine Tasche, die nicht weiter ist als die Öffnung, lässt sie
    verschwinden. Versetzen geht an **beiden** Kernen über die eigenen Flächen
    der Tasche (am exakten Körper ``prepare_ops._exact_chain_own_cavity``,
    BOHRUNG-13): Danach steht an der neuen Stelle genau eine Verengung.
    """
    from app.core.bootstrap import load_operations
    from app.core.errors import CORRECT_INPUT, RESIZE_THE_WIDENING, SHOW_FEATURE
    from app.core.geom.mesh import as_mesh_data
    from app.core.geom.prepare_ops import bore_entrance
    from app.core.perceive.features import detect, forget_cache

    load_operations()

    def pocket() -> tuple[Project, History]:
        project = new_project("centauri-carbon-2", "petg")
        history = History(project.document)
        size = {"width": 40.0, "depth": 40.0, "height": 10.0}
        history.apply("Quader", [OperationDraft(op=box, params=size)])
        history.apply(
            "Magnet",
            [
                OperationDraft(
                    op="insert_magnet_pocket",
                    inputs=("obj_1",),
                    params={"size": "8x3", "x": 0.0, "y": 0.0, "z": 10.0},
                )
            ],
        )
        return project, history

    project, history = pocket()
    entry = evaluate(project.document, profile, sources=ProjectSources(project)).scene.objects[
        "obj_1"
    ]
    entrance = bore_entrance(entry.mesh, entry.features["magnet_pocket_pocket_1"], entry.features)
    assert entrance is not None and entrance.sections[-1].narrowing
    assert 2.0 * entrance.sections[-1].outer_radius == pytest.approx(7.95, abs=0.01)

    def lips_at(mesh: object) -> list[Any]:
        forget_cache()
        found = detect(as_mesh_data(mesh))
        forget_cache()
        return [
            feature
            for feature in found.values()
            if feature.kind == "cone" and abs(float(feature.params["centre"][0])) < 0.1
        ]

    for diameter, code in ((8.5, "resize.narrowing_kept"), (7.8, "resize.narrowing_swallowed")):
        project, history = pocket()
        history.apply(
            "Ändern",
            [
                OperationDraft(
                    op="resize_hole",
                    inputs=("obj_1",),
                    params={"at_feature": "magnet_pocket_pocket_1", "diameter": diameter},
                )
            ],
        )
        result = evaluate(project.document, profile, sources=ProjectSources(project))
        assert result.complete, [str(f.message) for f in result.scene.report.findings]
        told = [f for f in result.scene.report.findings if f.code.startswith("resize.")]
        assert [f.code for f in told] == [code], diameter
        assert RESIZE_THE_WIDENING not in told[0].suggestions
        lips = lips_at(result.scene.objects["obj_1"].mesh)
        if code == "resize.narrowing_kept":
            # Die Öffnung bleibt, wo sie war, und die Lippe setzt an der weiteren Tasche an.
            assert told[0].suggestions == (SHOW_FEATURE,)
            assert len(lips) == 1 and lips[0].params.get("narrowing") is True, lips
            assert float(lips[0].params["opening"]) == pytest.approx(7.95, abs=0.05)
        else:
            assert told[0].severity == "warning" and CORRECT_INPUT in told[0].suggestions
            assert lips == []

    project, history = pocket()
    history.apply(
        "Versetzen",
        [
            OperationDraft(
                op="move_feature",
                inputs=("obj_1",),
                params={"at_feature": "cone_1", "x": 10.0, "y": 0.0, "z": 9.6},
            )
        ],
    )
    result = evaluate(project.document, profile, sources=ProjectSources(project))
    assert result.complete, [str(f.message) for f in result.scene.report.findings]
    forget_cache()
    lips = [
        feature
        for feature in detect(as_mesh_data(result.scene.objects["obj_1"].mesh)).values()
        if feature.kind == "cone" and abs(float(feature.params["centre"][0]) - 10.0) < 0.1
    ]
    forget_cache()
    assert len(lips) == 1 and lips[0].params.get("narrowing") is True


def test_the_play_comes_from_the_material_profile(profile: Profile) -> None:
    """AGENTS.md Regel 7: nie eine feste Zahl in der Datei."""
    project = project_with_plate()
    History(project.document).apply(
        "Passbohrung",
        [
            OperationDraft(
                op="insert_dowel",
                inputs=("obj_1",),
                params={"kind": "bore", "diameter": 4.0, "length": 6.0, "z": 4.0, "play": 0.0},
            )
        ],
    )
    result = evaluate(project.document, profile, sources=ProjectSources(project))

    assert result.complete
    bore = result.scene.objects["obj_1"].features["dowel_bore_1"]
    assert bore.params["diameter"] == pytest.approx(4.0 + profile.material.clearance, abs=0.01)


@pytest.mark.parametrize(
    "spec",
    list(PARTS.all()),
    ids=lambda spec: part_ops.op_name(spec.name),
)
def test_every_part_operation_runs_on_a_body(spec: PartSpec, profile: Profile) -> None:
    """Ein Lauf je Operation — eine Deklaration, die nie jemand aufgerufen
    hat, ist nicht fertig.
    """
    name = part_ops.op_name(spec.name)
    project = project_with_plate()
    History(project.document).apply(
        name,
        [OperationDraft(op=name, inputs=("obj_1",), params={"z": 4.0, **required_defaults(spec)})],
    )

    result = evaluate(project.document, profile, sources=ProjectSources(project))

    assert result.complete, [f.message for f in result.scene.report.findings]
    assert result.scene.objects["obj_1"].mesh.volume > 0.0


def test_a_part_that_misses_the_body_says_so(profile: Profile) -> None:
    """Der Fall, der einen Satz Deckel gekostet hat (Regel 17, §2.7).

    Eine Magnettasche neben dem Körper schnitt nichts und meldete nichts: keine
    Ausnahme, kein Befund, kein Hinweis. Im Verlauf stand ein Schritt, im
    Viewport lag dasselbe Teil, und gesucht wurde der Fehler in der Geometrie
    statt in der Position. Gemessen wurde es an einer Platte 60 × 60 × 20:
    0,0 mm³ abgetragen, null Befunde.
    """
    project = project_with_plate()
    History(project.document).apply(
        "Daneben",
        [
            OperationDraft(
                op="insert_magnet_pocket",
                inputs=("obj_1",),
                params={"size": "6x3", "x": 200.0, "y": 0.0, "z": 4.0},
            )
        ],
    )

    result = evaluate(project.document, profile, sources=ProjectSources(project))

    assert result.complete, "die Operation ist gelaufen — sie hat nur nichts bewirkt"
    codes = {finding.code for finding in result.scene.report.findings}
    assert "boolean.without_effect" in codes


def test_a_part_that_hits_the_body_stays_quiet(profile: Profile) -> None:
    """Und der Normalfall meldet nichts — sonst stünde die Warnung unter jedem
    Baustein und wäre nach dem dritten Mal unsichtbar.

    Die Tasche sitzt auf z = 0, der Mitte der Platte. Auf ihrer Oberkante
    (z = 4) träfe sie nichts, und das ist kein Zufall dieses Tests, sondern ein
    eigener Fund: die Magnettasche und das Schlüsselloch werden **über** ihrem
    Anker gebaut, das Schraubenloch darunter. Wer eine Fläche anklickt, trifft
    also je nach Baustein oder nicht — das gehört zusammengeführt und steht
    unter A2 im Konzept.
    """
    project = project_with_plate()
    History(project.document).apply(
        "Getroffen",
        [
            OperationDraft(
                op="insert_magnet_pocket",
                inputs=("obj_1",),
                params={"size": "6x3", "x": 0.0, "y": 0.0, "z": 0.0},
            )
        ],
    )

    result = evaluate(project.document, profile, sources=ProjectSources(project))

    codes = {finding.code for finding in result.scene.report.findings}
    assert "boolean.without_effect" not in codes


@pytest.mark.parametrize("box", ["create_box", "create_brep_box"])
def test_a_pocket_that_opens_away_from_the_part_says_so_on_both_kernels(
    profile: Profile, box: str
) -> None:
    """Eine Magnettasche, eingetippt auf der Unterseite eines Deckels 80 × 60 × 5
    (z = 0), ohne angeklickte Fläche: Ihre Richtung ist dann die Achse Z, die
    Öffnung zeigt nach oben, und die Tasche hing unter dem Deckel in der Luft.
    Abgetragen wurden 0,5 mm³ — die Haut von einem Hundertstel, mit der jede
    Öffnung über ihre Fläche reicht —, und weil das mehr ist als ein Stück
    Extrusionsbahn, sagte ``boolean.without_effect`` nichts, an beiden Kernen
    (Durchsicht 0.5.1, Prüfer bohrung).

    Gemessen wird die Wirkung, nicht der Treffer (``operationen.md``): Über den
    Querschnitt des Bausteins verteilt ist das keine Schicht tief, und was
    unter einer Schicht bleibt, entsteht im Druck nicht. Gegenproben: dieselbe
    Stelle mit der Richtung der Unterseite trägt die ganze Tasche ab und
    schweigt, ebenso die Tasche von oben.
    """
    from app.core.errors import CORRECT_INPUT
    from app.core.geom.mesh import as_mesh_data

    def inserted(**placement: float) -> tuple[float, list[Any]]:
        project = new_project("centauri-carbon-2", "petg")
        history = History(project.document)
        history.apply(
            "Deckel",
            [OperationDraft(op=box, params={"width": 80.0, "depth": 60.0, "height": 5.0})],
        )
        history.apply(
            "Magnet",
            [
                OperationDraft(
                    op="insert_magnet_pocket",
                    inputs=("obj_1",),
                    params={"size": "8x3", "x": -30.0, "y": -20.0, **placement},
                )
            ],
        )
        result = evaluate(project.document, profile, sources=ProjectSources(project))
        assert result.complete, [str(f.message) for f in result.scene.report.findings]
        volume = float(as_mesh_data(result.scene.objects["obj_1"].mesh).volume)
        return 80.0 * 60.0 * 5.0 - volume, list(result.scene.report.findings)

    removed, findings = inserted(z=0.0)
    assert removed < 1.0, removed
    warned = [finding for finding in findings if finding.code == "parts.cuts_no_layer"]
    assert len(warned) == 1, [finding.code for finding in findings]
    assert warned[0].severity == "warning"
    assert CORRECT_INPUT in warned[0].suggestions
    assert "boolean.without_effect" not in {finding.code for finding in findings}

    # Eine Richtung, die ebenso hinauszeigt, sagt dasselbe.
    _removed, findings = inserted(z=0.0, nz=1.0)
    assert "parts.cuts_no_layer" in {finding.code for finding in findings}

    for placement in ({"z": 0.0, "nz": -1.0}, {"z": 5.0}):
        removed, findings = inserted(**placement)
        assert removed > 150.0, (placement, removed)
        codes = {finding.code for finding in findings}
        assert not codes & {"parts.cuts_no_layer", "boolean.without_effect"}, (placement, codes)


#: Abtragende Bausteine mit dem Halbmesser, bis zu dem ihre Öffnung frei sein
#: muss — die Magnettasche an ihrer Lippe (Ø 7,95), das Schraubenloch M3 an
#: seiner Bohrung (Ø 3,4), der Lagersitz 608 an seinem Sitz (Ø 22).
SLANTED_CASES: list[tuple[str, dict[str, Any], float]] = [
    ("magnet_pocket", {"size": "8x3"}, 3.975),
    ("screw_hole", {"size": "M3", "depth": 8.0}, 1.7),
    ("bearing_seat", {"size": "608"}, 11.0),
]


def _slanted(
    profile: Profile, box: str, name: str, values: dict[str, Any], angle: float, z: float = 10.0
) -> tuple[MeshData, np.ndarray]:
    """Quader 40 × 40 × 10, der Baustein bei (0, 0, ``z``), Richtung Z um ``angle`` um X gekippt."""
    from app.core.geom.mesh import as_mesh_data

    result, axis = _slanted_result(profile, box, name, values, angle, z)
    return as_mesh_data(result.scene.objects["obj_1"].mesh), axis


def _slanted_result(
    profile: Profile, box: str, name: str, values: dict[str, Any], angle: float, z: float = 10.0
) -> tuple[Any, np.ndarray]:
    """Wie :func:`_slanted`, mit der ganzen Auswertung samt Befunden."""
    axis = np.array([0.0, -np.sin(np.radians(angle)), np.cos(np.radians(angle))])
    project = new_project("centauri-carbon-2", "petg")
    history = History(project.document)
    history.apply(
        "Quader",
        [OperationDraft(op=box, params={"width": 40.0, "depth": 40.0, "height": 10.0})],
    )
    placement = {"x": 0.0, "y": 0.0, "z": z, "nx": 0.0, "ny": float(axis[1]), "nz": float(axis[2])}
    history.apply(
        name,
        [
            OperationDraft(
                op=part_ops.op_name(name), inputs=("obj_1",), params={**values, **placement}
            )
        ],
    )
    result = evaluate(project.document, profile, sources=ProjectSources(project))
    assert result.complete, [str(f.message) for f in result.scene.report.findings]
    return result, axis


@pytest.mark.parametrize("box", ["create_box", "create_brep_box"])
@pytest.mark.parametrize("case", SLANTED_CASES, ids=[case[0] for case in SLANTED_CASES])
def test_a_pocket_set_at_a_slant_opens_to_the_face(
    profile: Profile, box: str, case: tuple[str, dict[str, Any], float]
) -> None:
    """Schräg zur Fläche eingesetzt, bleibt die Öffnung frei — an beiden Kernen.

    Durchsicht 0.5.1 (Prüfer rest-lippe, rest-schraube): Mit einer Richtung,
    die nicht senkrecht auf der Fläche steht (von Hand, vom Assistenten, von
    der Kommandozeile), reichte das Werkzeug nur ein Hundertstel über seine
    Mündung. Die gekippte Fläche liegt auf der tiefen Seite um bis zu
    R · tan 10° darüber, und dort blieb ein Keil Material über gut der Hälfte
    der Öffnung stehen: 17 von 36 Strahlen entlang der Achse trafen Material,
    an der Magnettasche, am Schraubenloch und am Lagersitz 608 (1,9 mm Keil),
    ohne Befund. Der Magnet, die Schraube, das Lager kamen nicht hinein.
    """
    from tests.helpers import contains

    name, values, radius = case
    angle = 10.0
    body, axis = _slanted(profile, box, name, values, angle)

    first = np.cross(axis, [1.0, 0.0, 0.0])
    first /= np.linalg.norm(first)
    second = np.cross(axis, first)
    mouth = np.array([0.0, 0.0, 10.0])
    reach = radius * np.tan(np.radians(angle)) + 0.5
    along = np.arange(-1.0, reach, 0.1)
    blocked = []
    for phi in np.linspace(0.0, 2.0 * np.pi, 12, endpoint=False):
        offset = 0.85 * radius * (np.cos(phi) * first + np.sin(phi) * second)
        if contains(body, mouth + offset + np.outer(along, axis)).any():
            blocked.append(round(float(np.degrees(phi))))
    assert not blocked, f"Material über der Öffnung bei {blocked}°"
    assert body.is_watertight


@pytest.mark.parametrize("box", ["create_box", "create_brep_box"])
def test_a_slanted_pocket_below_the_face_stays_below_it(profile: Profile, box: str) -> None:
    """Die Verlängerung gilt der Fläche **an der Mündung**, nicht dem Körper darüber.

    Eine Tasche, deren Mündung 5 mm tief im Quader liegt, trifft keine Fläche;
    sie bleibt ein eingeschlossener Hohlraum wie gerade eingesetzt und wird
    nicht bis zur Deckfläche durchgezogen.
    """
    upright, _axis = _slanted(profile, box, "magnet_pocket", {"size": "8x3"}, 0.0, z=5.0)
    slanted, _axis = _slanted(profile, box, "magnet_pocket", {"size": "8x3"}, 10.0, z=5.0)

    assert slanted.volume == pytest.approx(upright.volume, abs=0.5)


@pytest.mark.parametrize("box", ["create_box", "create_brep_box"])
@pytest.mark.parametrize("angle", [0.0, 5.0, 6.0, 10.0])
def test_a_magnet_pocket_set_at_a_slant_says_its_lip_holds_on_one_side(
    profile: Profile, box: str, angle: float
) -> None:
    """RM-277: Schräg zur Fläche gesetzt, verliert die Haltelippe auf der tiefen Seite ihren Halt.

    Durchsicht 0.5.1 (rest-schraube): Die Lippe liegt 0 bis 0,4 mm unter der
    Mündung, und auf der Seite, auf der die Fläche abfällt, liegt diese am
    Taschenrand um ``R · tan(Neigung)`` darunter. Unter 10° fehlte die Lippe auf
    31 % des Umfangs, unter 20° auf 41 %, und kein Befund sagte es. Die Grenze
    kommt aus der Geometrie, nicht aus einer Gradzahl: Die Lippe fehlt auf einem
    Teil des Umfangs, sobald ``R · tan(Neigung)`` die Lippenhöhe übersteigt —
    bei 8×3 in PETG ``atan(0,4 / 4,125)`` = 5,54°. Darunter ist sie ringsum da,
    nur auf einer Seite niedriger.
    """
    from app.core.errors import CORRECT_INPUT

    result, _axis = _slanted_result(profile, box, "magnet_pocket", {"size": "8x3"}, angle)
    said = [f for f in result.scene.report.findings if f.code == "parts.lip_on_a_slant"]

    radius = (standards.magnet("8x3").diameter + profile.material.clearance) / 2.0
    limit = np.degrees(np.arctan(0.4 / radius))
    assert limit == pytest.approx(5.54, abs=0.01)
    if angle <= limit:
        assert not said, [str(f.message) for f in said]
        return
    assert len(said) == 1, [f.code for f in result.scene.report.findings]
    assert said[0].severity == "warning"
    assert said[0].suggestions == (CORRECT_INPUT,)
    assert said[0].values["angle_deg"] == pytest.approx(angle, abs=0.1)
    assert "Haltelippe" in str(said[0].message)


@pytest.mark.parametrize("box", ["create_box", "create_brep_box"])
@pytest.mark.parametrize("angle", [0.0, 5.0, 10.0])
def test_a_keyhole_set_at_a_slant_says_its_ledge_holds_on_one_side(
    profile: Profile, box: str, angle: float
) -> None:
    """RM-277, der Zwilling: Die Rückhaltekante des Schlüssellochs fehlt schräg gesetzt ebenso.

    ``keeps_up`` dreht den Schlitz zur Seite, auf der die Fläche unter der
    Mündung liegt; bei den Vorgaben (M4, Einhängeweg 8, Tiefe 4, Kopftiefe 2,5)
    ist die Kante 1,5 mm dick, und der Kopfrand reicht 8 + 3,5 mm von der
    Einstiegsöffnung — ab ``atan(1,5 / 11,5)`` = 7,4° fehlt sie dort
    (Sonde ``schraube/s2_lippe``: unter 10° an 52 statt 17 von 72 Richtungen
    am Kopfrand, die 17 sind der Schlitz des Schafts).
    """
    from app.core.errors import CORRECT_INPUT

    result, _axis = _slanted_result(profile, box, "keyhole", {"size": "M4"}, angle)
    said = [f for f in result.scene.report.findings if f.code == "parts.lip_on_a_slant"]

    limit = np.degrees(np.arctan((4.0 - 2.5) / (8.0 + standards.screw("M4").head / 2.0)))
    if angle <= limit:
        assert not said, [str(f.message) for f in said]
        return
    assert len(said) == 1
    assert said[0].suggestions == (CORRECT_INPUT,)
    assert "Rückhaltekante" in str(said[0].message)


# --- versioning (§24.4) -------------------------------------------------------------


def test_the_library_has_a_version() -> None:
    assert LIBRARY_VERSION


def test_a_changed_part_is_named(profile: Profile) -> None:
    used = {"screw_hole": "0", "rib": PARTS.get("rib").version}

    assert changed_since(used) == ("screw_hole",)


def test_a_part_that_is_gone_is_named() -> None:
    """§24.5: ein eigener Baustein von einer anderen Maschine fehlt, er wird
    nicht still übersprungen.
    """
    assert missing_parts({"eigenbau": "1", "rib": "1"}) == ("eigenbau",)


def test_the_change_log_says_what_moved() -> None:
    for spec in PARTS.all():
        for change in spec.changes:
            assert change.date and change.reason


@pytest.mark.parametrize("pair", by_direction(subtractive=False), ids=direction_ids)
def test_an_added_part_has_the_component_count_it_declares(
    pair: tuple[PartSpec, BaseParams], profile: Profile
) -> None:
    """Ein aufgesetzter Baustein verbindet sich — außer als lösbares Gegenstück.

    Die Rastnase wurde es nicht: sie sitzt mit 6 × 1 mm auf der Fläche auf, und
    zwei Volumen, die sich nur in einer Fläche berühren, sind das eine, woran
    eine boolesche Operation zuverlässig scheitert (§39). Heraus kam ein
    wasserdichtes Netz aus zwei Komponenten — beim nächsten Bohren waren es
    drei. Die breiteren Bausteine fielen nie auf, weil manifold sie verschmolz.

    **Aus dem Register statt aus einer Liste**, seit dem 25.08.2026. Hier
    standen fünf Namen von Hand, und die letzten beiden Bausteine — Kabelclip
    und Lochwand-Einhänger — waren nicht darunter; niemand hatte es vergessen,
    es fällt nur schlicht nicht auf. Eine Liste, die man beim Anlegen eines
    Bausteins mitpflegen muss, ist beim übernächsten unvollständig.

    Und seit demselben Tag **je Richtung**: Wer die Liste aus
    ``not cuts(spec, None)`` zog, ließ die drei umschaltbaren Bausteine
    draußen, weil sie ohne Werte als abtragend zählen (siehe
    :func:`by_direction`).
    """
    spec, values = pair
    name = part_ops.op_name(spec.name)
    choice = part_ops.cuts_by_parameter(spec.params)
    params: dict[str, Any] = {"at_feature": "face_top", **required_defaults(spec)}
    if choice is not None:
        params[choice[0]] = getattr(values, choice[0])

    project = new_project("centauri-carbon-2", "petg")
    History(project.document).apply("Quader", [OperationDraft(op="create_box", params={})])
    History(project.document).apply(
        name, [OperationDraft(op=name, inputs=("obj_1",), params=params)]
    )

    result = evaluate(project.document, profile, sources=ProjectSources(project))

    assert result.complete, [f.message for f in result.scene.report.findings]
    body = result.scene.objects["obj_1"].mesh
    expected = 2 if spec.separate_from_host else 1
    assert body.component_count == expected, direction_ids(pair)
    assert body.is_watertight, direction_ids(pair)


#: Die lösbaren Bausteine aus dem Register, je mit den Werten, unter denen sie
#: eingesetzt werden — die Schraube zusätzlich mit Senkkopf, weil nur dann ihr
#: Träger im selben Schritt gesenkt wird (``host_cut``).
SEPARATE_CASES: list[tuple[str, dict[str, Any]]] = [
    (spec.name, required_defaults(spec)) for spec in PARTS.all() if spec.separate_from_host
] + [("printed_screw", {"size": "M5", "length": 6.0, "countersunk": True})]


def _separate_ids(case: tuple[str, dict[str, Any]]) -> str:
    name, values = case
    return f"{name}-countersunk" if values.get("countersunk") else name


def _with_a_separate_part(
    profile: Profile,
    box: str,
    name: str,
    values: dict[str, Any],
    size: tuple[float, float, float] = (40.0, 40.0, 10.0),
) -> tuple[Any, Any]:
    """Quader, darauf mittig der lösbare Baustein — Auswertung davor und danach."""
    project = new_project("centauri-carbon-2", "petg")
    history = History(project.document)
    history.apply(
        "Quader",
        [OperationDraft(op=box, params={"width": size[0], "depth": size[1], "height": size[2]})],
    )
    before = evaluate(project.document, profile, sources=ProjectSources(project))
    op = part_ops.op_name(name)
    top = {"x": 0.0, "y": 0.0, "z": size[2], "nx": 0.0, "ny": 0.0, "nz": 1.0}
    history.apply(name, [OperationDraft(op=op, inputs=("obj_1",), params={**values, **top})])
    after = evaluate(project.document, profile, sources=ProjectSources(project))
    assert after.complete, [str(f.message) for f in after.scene.report.findings]
    return before, after


def test_every_separate_part_is_named_in_the_cases() -> None:
    """Die Fälle kommen aus dem Register — und es sind die drei, die es heute gibt."""
    names = {name for name, _values in SEPARATE_CASES}
    assert {"printed_screw", "printed_nut", "seal_gasket"} <= names


def test_the_registry_says_which_operations_leave_separate_parts() -> None:
    """Die Auskunft hat eine Quelle: ``PartSpec.separate_from_host``.

    Die Auswertung fragt die Operation, nicht den Namen eines Bausteins — eine
    Liste in ``evaluate`` wäre beim nächsten lösbaren Teil unvollständig.
    """
    for spec in PARTS.all():
        operation = REGISTRY.get(part_ops.op_name(spec.name))
        assert operation.leaves_separate_parts is spec.separate_from_host, spec.name


@pytest.mark.parametrize("box", ["create_box", "create_brep_box"])
@pytest.mark.parametrize("case", SEPARATE_CASES, ids=_separate_ids)
def test_a_separate_part_does_not_say_the_body_falls_apart(
    profile: Profile, box: str, case: tuple[str, dict[str, Any]]
) -> None:
    """Eine gedruckte Schraube ist gewollt ein eigenes Teil — kein Zerfall.

    Durchsicht 0.5.1 (Prüfer rest-bohrung, rest-schraube): Schraube, Mutter
    und separate Dichtung meldeten an beiden Kernen „Der Körper zerfällt nach
    diesem Schritt in lose Teile. Strg+Z nimmt ihn zurück.“ Der Satz riet dem
    Kunden, einen gewollten Schritt zurückzunehmen. Die Teilezahl steigt, und
    genau darum geht es beim lösbaren Teil (``separate_from_host``).
    """
    name, values = case
    _before, after = _with_a_separate_part(profile, box, name, values)

    codes = [finding.code for finding in after.scene.report.findings]
    assert "feature.body_split" not in codes, codes
    body = after.scene.objects["obj_1"].mesh
    assert body.component_count >= 2
    # Träger und Teil bleiben je für sich geschlossen, auch wo sie sich
    # berühren — der Senkkopf liegt bündig in seiner Senkung.
    assert body.is_watertight, name


@pytest.mark.parametrize("box", ["create_box", "create_brep_box"])
def test_a_host_that_a_separate_part_cuts_apart_still_says_so(profile: Profile, box: str) -> None:
    """Die gewollten Teile zählen nicht — der Träger zählt weiter.

    Ein Streifen 40 × 6 × 1,5: Die Senkung einer M5 ist breiter als er und
    reicht durch ihn hindurch, der Träger zerfällt in zwei Hälften. Das ist
    der Zerfall, den der Satz meint, und er bleibt, auch wenn daneben eine
    Schraube liegt.
    """
    _before, after = _with_a_separate_part(
        profile,
        box,
        "printed_screw",
        {"size": "M5", "length": 6.0, "countersunk": True},
        size=(40.0, 6.0, 1.5),
    )

    split = [f for f in after.scene.report.findings if f.code == "feature.body_split"]
    assert len(split) == 1, [f.code for f in after.scene.report.findings]
    assert split[0].severity == "warning"
    assert split[0].object_id == "obj_1"
    assert split[0].op_id == 2, "am Schritt der Schraube, damit Strg+Z ihn meint"
    assert split[0].values["before"] == 1 and split[0].values["after"] == 2


def test_the_part_keeps_the_size_it_promises(profile: Profile) -> None:
    """Eingesenkt wird um den Überlappungswert, nicht um einen Millimeter.

    Die Nase steht mit ihrem Überstand von 3 mm über der Fläche; was im Körper
    verschwindet, ist ein Hundertstel und liegt unter dem, was die Anzeige
    unterscheidet.
    """
    project = new_project("centauri-carbon-2", "petg")
    History(project.document).apply("Quader", [OperationDraft(op="create_box", params={})])
    History(project.document).apply(
        "Nase",
        [
            OperationDraft(
                op="insert_latch",
                inputs=("obj_1",),
                params={"at_feature": "face_top", "depth": 3.0},
            )
        ],
    )

    result = evaluate(project.document, profile, sources=ProjectSources(project))

    top = result.scene.objects["obj_1"].mesh.bounds.maximum[2]
    assert top == pytest.approx(13.0, abs=0.02), "10 mm Quader plus 3 mm Nase"


def test_a_part_on_a_side_wall_grows_into_that_wall(profile: Profile) -> None:
    """Die angeklickte Fläche bestimmt die Richtung, nicht nur den Ort.

    ``_anchor`` las von einem Merkmal ausschließlich ``centre``. Die Richtung
    kam aus dem Feld *Achse*, und dessen Vorgabe ist Z — also stand jeder
    Baustein senkrecht, gleich welche Fläche man angeklickt hatte. Für den
    Kunden war das der häufigste Handgriff überhaupt: Man zeigt auf eine Wand,
    und was man bekommt, steckt in der Decke.

    **Gemessen wird über zwei Überstände, und das ist keine Umständlichkeit.**
    Bei 3 mm stimmt die Zahl auch im falschen Zustand: Die Nase ist 6 mm
    breit, eine senkrecht stehende reicht also 3 mm nach -X — dieselbe Zahl,
    aus der Breite statt aus dem Überstand. Ein Test, der nur diesen einen Wert
    prüft, ist grün und beweist nichts. Erst wenn der Ausschlag mit dem
    Überstand **mitwächst**, misst er die Richtung.
    """
    for depth, expected in ((3.0, -23.0), (5.0, -25.0)):
        project = new_project("centauri-carbon-2", "petg")
        History(project.document).apply("Quader", [OperationDraft(op="create_box", params={})])
        History(project.document).apply(
            "Nase",
            [
                OperationDraft(
                    op="insert_latch",
                    inputs=("obj_1",),
                    # face_5 schaut nach -X; der Quader steht dort bei x = -20.
                    params={"at_feature": "face_5", "depth": depth},
                )
            ],
        )

        result = evaluate(project.document, profile, sources=ProjectSources(project))

        assert result.complete, [f.message for f in result.scene.report.findings]
        bounds = result.scene.objects["obj_1"].mesh.bounds
        assert bounds.minimum[0] == pytest.approx(expected, abs=0.02), f"depth {depth}"
        assert bounds.maximum[2] == pytest.approx(10.0, abs=0.02), "und nichts nach oben"


def test_a_latch_rests_on_its_base_with_the_ramp_on_top(profile: Profile) -> None:
    """Die Rastnase liegt mit ihrer ganzen Grundfläche an der Wand, die Schräge oben.

    Bis zum 22.09.2026 stand sie auf ihrer Spitze: Einen halben Hundertstel
    vor der Wand maß ihr Querschnitt 0,03 mm² statt Breite mal Höhe, und als
    Aussparung wuchs sie aus der Wand heraus (+12,3 mm³), statt eine Tasche zu
    schneiden. Geprüft wird an einer senkrechten Wand, denn nur dort hat die
    Nase ein Oben.
    """
    width, height, depth = 6.0, 3.0, 1.0
    volumes = {}
    for negative in (False, True):
        project = new_project("centauri-carbon-2", "petg")
        History(project.document).apply("Quader", [OperationDraft(op="create_box", params={})])
        before = evaluate(project.document, profile, sources=ProjectSources(project))
        History(project.document).apply(
            "Nase",
            [
                OperationDraft(
                    op="insert_latch",
                    inputs=("obj_1",),
                    params={"at_feature": "face_5", "negative": negative},
                )
            ],
        )
        result = evaluate(project.document, profile, sources=ProjectSources(project))
        assert result.complete, [f.message for f in result.scene.report.findings]
        mesh = result.scene.objects["obj_1"].mesh
        volumes[negative] = mesh.volume - before.scene.objects["obj_1"].mesh.volume
        if negative:
            continue
        # face_5 schaut nach -X und steht bei x = -20.
        touching = mesh.raw.section(plane_origin=(-20.005, 0.0, 0.0), plane_normal=(1, 0, 0))
        assert touching is not None
        contact = touching.to_2D()[0]
        assert contact.area == pytest.approx(width * height, rel=0.02), "die Nase liegt voll auf"
        assert mesh.bounds.minimum[0] == pytest.approx(-20.0 - depth, abs=0.02)
        # Ganz draußen ist nur die Haltefläche: Sie liegt unten, die Schräge
        # läuft darüber zur Wand zurück.
        tip = mesh.raw.section(plane_origin=(-20.9, 0.0, 0.0), plane_normal=(1, 0, 0))
        assert tip is not None
        z_tip = tip.vertices[:, 2]
        z_base = touching.vertices[:, 2]
        assert z_tip.min() == pytest.approx(z_base.min(), abs=0.02), "Haltefläche unten"
        assert z_tip.max() < z_base.max() - 2.0, "die Schräge läuft oben zur Wand zurück"

    assert volumes[False] == pytest.approx(width * height * depth / 2.0, rel=0.02)
    assert volumes[True] < -width * height * depth / 2.0, "die Aussparung trägt mehr ab"


def test_a_bore_in_a_side_wall_runs_through_that_wall(profile: Profile) -> None:
    """Dasselbe an dem Baustein, für den es am meisten zählt.

    Ein Schraubenloch bringt seine Bohrung als benanntes Merkmal mit, und
    deren Achse ist die Zahl, an der sich „durch die Wand" von „durch den
    Deckel" unterscheiden lässt. Der Betrag des Skalarprodukts mit der
    Flächennormalen ist 1, wenn beide dieselbe Gerade meinen — die Richtung
    entlang dieser Geraden ist Sache der Bohrung, nicht des Tests.
    """
    project = new_project("centauri-carbon-2", "petg")
    History(project.document).apply("Quader", [OperationDraft(op="create_box", params={})])
    before = evaluate(project.document, profile, sources=ProjectSources(project))
    wall = before.scene.objects["obj_1"].features["face_5"]
    History(project.document).apply(
        "Loch",
        [
            OperationDraft(
                op="insert_screw_hole", inputs=("obj_1",), params={"at_feature": "face_5"}
            )
        ],
    )

    result = evaluate(project.document, profile, sources=ProjectSources(project))

    assert result.complete, [f.message for f in result.scene.report.findings]
    normal = np.asarray(wall.params["normal"], dtype=float)
    bores = [
        np.asarray(entry.params["axis"], dtype=float)
        for entry in result.scene.objects["obj_1"].features.values()
        if entry.kind == "hole" and entry.params.get("axis") is not None
    ]
    assert bores, "the part brings a named bore"
    assert all(abs(float(axis @ normal)) == pytest.approx(1.0, abs=1e-3) for axis in bores), (
        f"bore axes {bores} against wall normal {normal}"
    )


def _plate_with_a_through_bore() -> Project:
    """Eine 10 mm dicke Platte mit einer durchgehenden Bohrung Ø 6.

    Gebohrt wird ohne Materialzugabe, damit die gemessenen Durchmesser unten
    nicht vom Profil abhängen: Die Bohrung misst 6,00 mm, und alles darüber
    kommt vom Baustein.
    """
    project = new_project("centauri-carbon-2", "petg")
    History(project.document).apply(
        "Platte",
        [OperationDraft(op="create_box", params={"width": 40.0, "depth": 40.0, "height": 10.0})],
    )
    History(project.document).apply(
        "Bohrung",
        [
            OperationDraft(
                op="drill_hole",
                inputs=("obj_1",),
                params={"diameter": 6.0, "depth": 0.0, "compensate": False},
            )
        ],
    )
    return project


def _widest_bore(mesh: Any, height: float) -> float:
    """Der weiteste Durchmesser des mittigen Lochs auf dieser Höhe.

    Gemessen wird nur, was innerhalb von 15 mm um die Achse liegt — die
    Außenkontur der Platte steht bei 20 mm und würde jede Zahl überdecken.
    """
    cut = mesh.raw.section(plane_origin=[0.0, 0.0, height], plane_normal=[0.0, 0.0, 1.0])
    assert cut is not None, f"z={height}: der Schnitt trifft die Platte nicht"
    points = np.asarray(cut.vertices, dtype=float)
    radii = np.hypot(points[:, 0], points[:, 1])
    inner = radii[radii < 15.0]
    assert inner.size, f"z={height}: auf dieser Höhe ist gar kein Loch"
    return 2.0 * float(inner.max())


def test_a_tool_in_a_bore_starts_at_its_mouth(profile: Profile) -> None:
    """Ein Gewinde in einer Bohrung schneidet die **ganze** Bohrung.

    ``_anchor`` gab für ein Bohrungsmerkmal ``centre`` zurück — die *Mitte* des
    Zylinders. Ein abtragender Baustein liegt aber unter seiner Mündung
    (§24.1), also fing das Werkzeug in halber Materialstärke an: Auf einer
    10 mm dicken Platte trug ein Innengewinde mit 12 mm Länge unten zwischen
    z = 0 und z = 5 ab und ließ die obere Hälfte glatt — gemessen 6,25 mm
    Gewindeaußenmaß bei z = 1 und 3 gegen glatte 6,00 mm bei z = 7 und 9.
    Sieben von zwölf Millimetern Werkzeug hingen unter der Platte in der Luft.

    Über eine **Fläche** gesetzt war derselbe Handgriff immer richtig, und
    genau deshalb ist es niemandem aufgefallen: Der Weg, den jeder Test ging,
    war der heile. Der zweite Fall unten hält ihn fest — er darf sich nicht
    ändern.
    """
    for feature, threaded in (("hole_1", "die Bohrung"), ("face_top", "die Fläche")):
        project = _plate_with_a_through_bore()
        History(project.document).apply(
            "Gewinde",
            [
                OperationDraft(
                    op="insert_printed_thread",
                    inputs=("obj_1",),
                    params={
                        "at_feature": feature,
                        "internal": True,
                        "size": "M6",
                        "length": 12.0,
                    },
                )
            ],
        )
        result = evaluate(project.document, profile, sources=ProjectSources(project))

        assert result.complete, [str(f.message) for f in result.scene.report.findings]
        mesh = result.scene.objects["obj_1"].mesh
        smooth = [
            height for height in (1.0, 3.0, 5.0, 7.0, 9.0) if _widest_bore(mesh, height) < 6.1
        ]
        assert not smooth, (
            f"an {feature} gesetzt ({threaded}) blieb die Bohrung auf z={smooth} glatt — "
            "dort greift keine Schraube"
        )


def test_an_external_thread_post_and_an_internal_bore_are_a_matching_pair(
    profile: Profile,
) -> None:
    """Gewindebolzen und Gewindebohrung benutzen dieselben Nenndaten.

    Das ist bewusst **nicht** der Behälterweg: Ein Gewindebolzen auf einer
    ebenen Fläche hat einen massiven Kern. Für eine offene Dose baut
    ``screw_lid`` stattdessen einen ringförmigen Hals und den passenden Deckel
    gemeinsam; dessen Durchgang wird in ``test_lid.py`` geometrisch geprüft.
    """
    post = new_project("centauri-carbon-2", "petg")
    History(post.document).apply(
        "Träger",
        [OperationDraft(op="create_box", params={"width": 30.0, "depth": 30.0, "height": 10.0})],
    )
    History(post.document).apply(
        "Außengewinde",
        [
            OperationDraft(
                op="insert_printed_thread",
                inputs=("obj_1",),
                params={"at_feature": "face_top", "size": "M6", "length": 12.0},
            )
        ],
    )
    post_result = evaluate(
        post.document,
        profile,
        sources=ProjectSources(post),
    )

    lid = _plate_with_a_through_bore()
    History(lid.document).apply(
        "Innengewinde",
        [
            OperationDraft(
                op="insert_printed_thread",
                inputs=("obj_1",),
                params={"at_feature": "hole_1", "size": "M6", "length": 12.0, "internal": True},
            )
        ],
    )
    lid_result = evaluate(lid.document, profile, sources=ProjectSources(lid))

    assert post_result.complete and lid_result.complete
    outer = next(
        feature
        for feature in post_result.scene.objects["obj_1"].features.values()
        if feature.kind == "thread"
    )
    inner = next(
        feature
        for feature in lid_result.scene.objects["obj_1"].features.values()
        if feature.kind == "thread"
    )
    assert not outer.params["internal"] and inner.params["internal"]
    assert outer.params["nominal"] == inner.params["nominal"] == 6.0
    # Gebaut je um das Spiel des Materials daneben, und so nennen es die Merkmale.
    play = profile.material.clearance
    assert outer.params["diameter"] == pytest.approx(6.0 - play)
    assert inner.params["diameter"] == pytest.approx(6.0 + play)
    assert outer.params["pitch"] == inner.params["pitch"]


@pytest.mark.parametrize("countersunk", [False, True])
def test_a_printed_screw_sits_in_its_bore_and_prepares_a_countersink(
    profile: Profile, countersunk: bool
) -> None:
    """Das Gegenstück sitzt an der Mündung und senkt sie auf Wunsch gleich mit.

    Es bleibt absichtlich ein eigener Körper: Eine echte Schraube soll sich
    lösen lassen. Die Senkung gehört trotzdem in dieselbe Operation und damit
    in denselben Undo-Schritt — ein Einsteiger soll nicht erst eine zweite
    Operation suchen und deren Kopfdurchmesser übertragen müssen.
    """
    project = _plate_with_a_through_bore()
    History(project.document).apply(
        "Schraube",
        [
            OperationDraft(
                op="insert_printed_screw",
                inputs=("obj_1",),
                params={
                    "at_feature": "hole_1",
                    "size": "M6",
                    "length": 12.0,
                    "countersunk": countersunk,
                },
            )
        ],
    )
    result = evaluate(project.document, profile, sources=ProjectSources(project))

    assert result.complete, [str(f.message) for f in result.scene.report.findings]
    entry = result.scene.objects["obj_1"]
    if countersunk:
        assert entry.mesh.bounds.maximum[2] == pytest.approx(10.0, abs=0.02), (
            "der Senkkopf sitzt bündig statt auf der ungesenkten Fläche"
        )
    else:
        assert entry.mesh.bounds.maximum[2] > 10.0, "der Sechskantkopf liegt über der Platte"
    assert entry.mesh.bounds.minimum[2] < 0.0, "der Schaft reicht durch die Bohrung"
    assert entry.mesh.component_count == 2, "Schraube und Werkstück bleiben lösbar"
    from app.core.units import EPS_GEOM

    components = list(entry.mesh.raw.split(only_watertight=False))
    screw = max(components, key=lambda mesh: float(mesh.bounds[1][2]))
    points = np.asarray(screw.vertices, dtype=float)
    radii = np.hypot(points[:, 0], points[:, 1])
    if countersunk:
        plate = min(components, key=lambda mesh: float(mesh.bounds[1][2]))
        mouth = _widest_bore(MeshData.of(plate), 9.9)
        # Um das Spiel senkrecht zur 90°-Flanke weiter als der Kopf (RM-276).
        play = profile.material.clearance
        expected = standards.screw("M6").countersink + 2.0 * np.sqrt(2.0) * play
        assert mouth == pytest.approx(expected, abs=0.25), (
            "der Haken formt den Kopf, hat die gewählte Bohrung aber nicht mitgesenkt"
        )
        assert any(feature.kind == "cone" for feature in entry.features.values()), (
            "die automatisch erzeugte Senkung bleibt als Merkmal bearbeitbar"
        )
    else:
        inside_plate = (points[:, 2] > EPS_GEOM) & (points[:, 2] < 10.0 - EPS_GEOM)
        outside_bore = radii > 3.0 + EPS_GEOM
        assert not np.any(inside_plate & outside_bore), (
            "eine lösbare Schraube darf nicht in das Werkstück hineinragen"
        )
    threads = [feature for feature in entry.features.values() if feature.kind == "thread"]
    assert any(not feature.params["internal"] for feature in threads)
    assert not any(
        finding.code == "parts.hanging_loose" for finding in result.scene.report.findings
    )


@pytest.mark.parametrize("countersunk", [False, True])
def test_a_separate_printed_screw_keeps_existing_material_slots(
    profile: Profile,
    countersunk: bool,
) -> None:
    """Ein nachträglich eingesetztes Teil entfärbt das Werkstück nicht.

    Die Schraube bleibt geometrisch getrennt. Beim Senkkopf wird vorher die
    Senkung boolesch abgetragen, beim Sechskantkopf nicht; beide Wege müssen
    die vorhandene Zuordnung und den neuen Standard-Slot zusammenführen.
    """
    project = _plate_with_a_through_bore()
    History(project.document).apply(
        "Filament",
        [
            OperationDraft(
                op="assign_slot",
                inputs=("obj_1",),
                params={"slot": 2, "name": "PETG Rot", "colour": "#C53D38"},
            )
        ],
    )
    History(project.document).apply(
        "Schraube",
        [
            OperationDraft(
                op="insert_printed_screw",
                inputs=("obj_1",),
                params={
                    "at_feature": "hole_1",
                    "size": "M6",
                    "length": 12.0,
                    "countersunk": countersunk,
                },
            )
        ],
    )

    result = evaluate(project.document, profile, sources=ProjectSources(project))

    assert result.complete, [str(f.message) for f in result.scene.report.findings]
    mesh = result.scene.objects["obj_1"].mesh
    assert len(mesh.slots) == mesh.triangle_count
    assert 2 in mesh.slots, "das zugewiesene Filament des Werkstücks bleibt erhalten"
    assert 0 in mesh.slots, "das neue, noch nicht zugewiesene Teil bleibt als Standard erkennbar"


def test_printed_nut_has_the_matching_internal_thread() -> None:
    """Schraube und Mutter sind ein Paar, nicht zwei ähnlich benannte Körper."""
    screw = PARTS.get("printed_screw").fn(PARTS.get("printed_screw").params(size="M5", length=12.0))
    nut = PARTS.get("printed_nut").fn(PARTS.get("printed_nut").params(size="M5"))

    external = next(feature for feature in screw.features.values() if feature.kind == "thread")
    internal = next(feature for feature in nut.features.values() if feature.kind == "thread")
    assert external.params["diameter"] == internal.params["diameter"] == 5.0
    assert external.params["pitch"] == internal.params["pitch"]
    assert not external.params["internal"] and internal.params["internal"]


@pytest.mark.parametrize(
    ("size", "diameter"),
    [("M3", 20.0), ("M5", 20.0), ("M8", 20.0), ("M20", 20.0), ("custom_size", 11.0)],
)
def test_a_printed_screw_turns_through_its_printed_nut(
    size: str, diameter: float, profile: Profile
) -> None:
    """Schraube und Mutter überdecken sich an keiner Stelle ihres Wegs.

    Ein Gewindepaar wird an der Differenz geprüft, nicht daran, dass beide
    Hälften für sich sauber sind. Die Mutter wird dafür in Phase mit dem Gang
    der Schraube gesetzt — beide Gänge beginnen an ihrem unteren Ende bei
    Winkel null — und über die ganze Gewindelänge geschoben, vom Eintritt an der
    Spitze bis unter den Kopf. Bis zum 22.09.2026 fehlte dem Netzgewinde der
    Gang unter seinem ersten Umlauf: An der Unterseite der Mutter stand
    Material im Gang, bei M8 und 0,2 mm Spiel 2,3 mm³ Überdeckung. Seit der
    Tabellenversion 13 auch eine Größe über M8 und ein Paar mit eigenem Maß
    Ø 11, dessen Mutter abgeleitet ist und dessen Steigung die Regelsteigung.
    """
    from app.core.geom.boolean import BOOLEAN_OVERLAP
    from app.core.units import EPS_GEOM

    play = profile.material.clearance
    if size == "custom_size":
        pitch = standards.regular_pitch(diameter)
        height = standards.derived_nut(diameter).height
    else:
        pitch = standards.screw(size).pitch
        height = standards.nut(size).height
    screw_spec, nut_spec = PARTS.get("printed_screw"), PARTS.get("printed_nut")
    length = max(12.0, height + 4.0 * pitch)
    screw = screw_spec.fn(
        screw_spec.params(size=size, diameter=diameter, length=length, countersunk=False, play=play)
    ).mesh
    nut = nut_spec.fn(nut_spec.params(size=size, diameter=diameter, play=play)).mesh
    # Der Gang der Schraube beginnt bei -length + OVERLAP, der der Mutter bei
    # -OVERLAP: Um die Differenz verschoben laufen beide in Phase.
    start = -length + 2.0 * BOOLEAN_OVERLAP
    # Bis unter den Kopf, nicht in ihn: Die Mutter steht um zwei Überdeckungen über
    # ihrem Gang hinaus, und eine Länge aus ganzen Steigungen träfe den Kopf.
    turns = int((length - height - 2.0 * BOOLEAN_OVERLAP) // pitch)
    for turn in (0, turns // 2, turns):
        placed = nut.raw.copy()
        placed.apply_translation((0.0, 0.0, start + turn * pitch))
        overlap = boolean("intersection", [screw, MeshData.of(placed)], allow_empty=True)
        tolerance = EPS_GEOM * (screw.raw.area + placed.area)
        assert overlap.mesh.volume <= tolerance, f"{size}, Umlauf {turn}: {overlap.mesh.volume}"


# --- Normteile in jeder Größe (Tabellenversion 13) --------------------------------


def _radial_extent(mesh: Any) -> float:
    """Der größte Abstand einer Ecke von der Z-Achse — das gebaute Maß eines Rundteils."""
    vertices = as_mesh_data(mesh).raw.vertices
    return float(np.hypot(vertices[:, 0], vertices[:, 1]).max())


def test_an_m12_screw_hole_drills_the_medium_clearance_of_13_5() -> None:
    """ISO 273, mittlere Reihe: Das Durchgangsloch einer M12 misst 13,5 mm."""
    spec = PARTS.get("screw_hole")
    built = spec.fn(spec.params(size="M12", countersink=False))
    assert built.features["bore_1"].params["diameter"] == pytest.approx(13.5)
    assert 2.0 * _radial_extent(built.mesh) == pytest.approx(13.5, abs=0.01)
    assert not built.findings, "eine Normgröße ist nicht abgeleitet"


def test_an_m64_head_room_is_the_iso_4762_head_of_96() -> None:
    """ISO 4762: Der Zylinderkopf einer M64 hat dk = 96 mm, und so weit wird ausgespart."""
    spec = PARTS.get("screw_hole")
    built = spec.fn(spec.params(size="M64", countersink=False, head_room=5.0))
    assert built.features["head_room_1"].params["diameter"] == pytest.approx(96.0)
    assert 2.0 * _radial_extent(built.mesh) == pytest.approx(96.0, abs=0.01)


def test_field_limits_follow_the_largest_size_of_the_series() -> None:
    """Kopftiefe und Laschenbreite reichen bis zur größten Größe (Review RM-532 Runde 2, N6).

    Fest 50 und 100 mm: Der Zylinderkopf der M64 (64 mm) ließ sich nicht ganz
    versenken, und die Lasche der M56 und M64 folgt ohne Angabe ihrer Scheibe
    (105, 115 mm), die ein eingetragenes Maß nicht erreichte.
    """
    from app.core.knowledge import standards

    def maximum(part: str, field: str) -> float:
        entry = next(e for e in PARTS.get(part).params.spec() if e.name == field)
        assert entry.maximum is not None
        return float(entry.maximum)

    head = standards.screw("M64").head_height + standards.washer("M64").thickness
    assert maximum("screw_hole", "head_room") >= head
    lug = PARTS.get("lug")
    sizes = next(e for e in lug.params.spec() if e.name == "size").choices or ()
    assert sizes
    for size in sizes:
        assert maximum("lug", "width") >= standards.washer(str(size)).outer, size


def test_a_printed_screw_of_custom_size_has_a_wrench_sized_head() -> None:
    """Der Sechskantkopf einer Schraube Ø 9 misst 15 mm über die Flächen, nicht 14,5.

    Abgeleitet lag er zwischen M8 (13) und M10 (16) auf 14,5 mm — keine
    Schlüsselweite (Review RM-532 Runde 2, K-N2). Die Tabellengrößen behalten
    ihren Kopf.
    """
    spec = PARTS.get("printed_screw")
    built = spec.fn(spec.params(size="custom_size", diameter=9.0, countersunk=False))
    extent = as_mesh_data(built.mesh).raw.extents
    assert min(float(extent[0]), float(extent[1])) == pytest.approx(15.0, abs=0.01)
    table = spec.fn(spec.params(size="M8", countersunk=False))
    extent = as_mesh_data(table.mesh).raw.extents
    assert min(float(extent[0]), float(extent[1])) == pytest.approx(13.0, abs=0.01)


def test_m60_says_that_only_its_head_is_derived() -> None:
    """Ø 60 trifft abgeleitet die Normmaße von Steigung, Löchern, Mutter und Scheibe.

    Der Befund nannte es „nicht genormt“ wie jedes andere eigene Maß; nur die
    Zylinderschraube führt DIN 912 dort nicht (Review RM-532 Runde 2, K-N3).
    """
    spec = PARTS.get("nut_trap")
    sixty = spec.fn(spec.params(size="custom_size", diameter=60.0))
    [said] = [entry for entry in sixty.findings if entry.code == "parts.derived_size"]
    assert "Normmaße" in str(said.message) and "Kopf" in str(said.message)
    other = spec.fn(spec.params(size="custom_size", diameter=61.0))
    [said] = [entry for entry in other.findings if entry.code == "parts.derived_size"]
    assert "nicht genormt" in str(said.message) and "Normmaße" not in str(said.message)


def test_a_countersink_without_a_standard_head_says_so() -> None:
    """DIN 7991 endet bei M24 — darüber ist die Senkung gerechnet, und das wird gesagt.

    Die Regel 2·d gab jeder Größe eine Senkung, ab M14 größer als der genormte
    Senkkopf (M24: 48 statt 39) und über M24 für einen Kopf, den es nicht gibt
    (Review RM-532 Runde 2, N3). Die M24 senkt jetzt nach DIN 7991 und schweigt,
    die M30 sagt, dass ihre Senkung abgeleitet ist; ohne Senkkopf nichts.
    """
    spec = PARTS.get("screw_hole")
    normed = spec.fn(spec.params(size="M24"))
    assert normed.features["countersink_1"].params["diameter"] == pytest.approx(39.0)
    assert not normed.findings
    derived = spec.fn(spec.params(size="M30"))
    assert [finding.code for finding in derived.findings] == ["parts.countersink_derived"]
    assert derived.findings[0].values["field"] == "countersink"
    assert derived.findings[0].suggestions
    assert not spec.fn(spec.params(size="M30", countersink=False)).findings


def test_an_m20_nut_trap_takes_the_iso_4032_width_of_30(profile: Profile) -> None:
    """ISO 4032: Die Mutter M20 hat Schlüsselweite 30; die Tasche ist 30 plus Spiel breit."""
    play = profile.material.clearance
    spec = PARTS.get("nut_trap")
    built = spec.fn(spec.params(size="M20", slide=0.0, screw_hole=False, play=play))
    assert built.features["pocket_1"].params["diameter"] == pytest.approx(30.0 + play)
    extent = as_mesh_data(built.mesh).bounds.size
    # Ein Sechskant ist über die Flächen schmaler als über die Ecken.
    assert float(min(extent[0], extent[1])) == pytest.approx(30.0 + play, abs=0.01)
    assert float(extent[2]) == pytest.approx(18.0 + play / 2.0, abs=0.01)


def test_a_screw_hole_of_its_own_measure_is_derived_and_says_so() -> None:
    """Ø 11 liegt zwischen M10 und M12: Durchgangsloch 12,25, und der Befund nennt es abgeleitet.

    Ø 12 als eigenes Maß ist die M12 selbst — gleiche Geometrie, kein Befund.
    """
    spec = PARTS.get("screw_hole")
    own = spec.fn(spec.params(size="custom_size", diameter=11.0, countersink=False))
    assert own.features["bore_1"].params["diameter"] == pytest.approx(12.25)
    assert [finding.code for finding in own.findings] == ["parts.derived_size"]
    assert own.findings[0].severity == "info"
    assert "abgeleitet" in str(own.findings[0].message)

    twelve = spec.fn(spec.params(size="custom_size", diameter=12.0, countersink=False))
    table = spec.fn(spec.params(size="M12", countersink=False))
    assert not twelve.findings
    assert twelve.features["bore_1"].params == table.features["bore_1"].params
    assert as_mesh_data(twelve.mesh).volume == pytest.approx(as_mesh_data(table.mesh).volume)


def test_a_heatset_insert_of_its_own_measure_takes_hole_and_length_from_its_datasheet() -> None:
    """Eine Buchse, die nicht in der Tabelle steht: Bohrung und Länge, wie eingetragen."""
    spec = PARTS.get("heatset_m4")
    built = spec.fn(
        spec.params(size="custom_size", hole=14.0, length=15.0, extra_depth=1.0, lead_in=False)
    )
    bore = built.features["bore_1"].params
    assert bore["diameter"] == pytest.approx(14.0)
    assert bore["depth"] == pytest.approx(16.0)
    assert 2.0 * _radial_extent(built.mesh) == pytest.approx(14.0, abs=0.01)


def test_the_new_heatset_inserts_drill_the_hole_of_their_datasheet() -> None:
    """Ruthex RX-M8x12,7: d3 = 9,6; CNC Kitchen M10 × 12,7: D2 = 12,0."""
    spec = PARTS.get("heatset_m4")
    for size, hole in (("M8", 9.6), ("M10", 12.0), ("M3x5x4", 4.4)):
        built = spec.fn(spec.params(size=size, lead_in=False))
        assert built.features["bore_1"].params["diameter"] == pytest.approx(hole), size


def test_a_bore_beyond_the_table_still_gets_a_nut_trap_and_says_it_is_derived() -> None:
    """Weiter als das Durchgangsloch der M64 (70): eine Mutter mit eigenem Maß.

    Das kleinste eigene Maß, dessen abgeleitetes Durchgangsloch die Bohrung
    aufnimmt — bei 80 mm Ø 73,14 —, und der Satz über dem Dialog nennt es
    abgeleitet. Eine Buchse dagegen wählt nichts vor, sie nennt den Weg.
    """
    from app.core.knowledge.parts.fasteners import (
        CUSTOM_SIZE,
        insert_advice,
        nut_trap_advice,
        size_for_insert,
        size_for_nut_trap,
    )

    assert size_for_nut_trap(70.0) == {"size": "M64"}
    chosen = size_for_nut_trap(80.0)
    assert chosen["size"] == CUSTOM_SIZE
    assert chosen["diameter"] == pytest.approx(80.0 * 64.0 / 70.0)
    assert standards.derived_screw(chosen["diameter"]).clearance == pytest.approx(80.0)
    assert "abgeleitet" in str(nut_trap_advice(80.0))
    assert size_for_insert(12.5) == {}
    assert "Eigenes Maß" in str(insert_advice(12.5))


def test_a_thread_without_a_core_is_a_declared_exclusion() -> None:
    """Ø 1,6 mit 20 mm Steigung lässt keinen Kern stehen — erklärt, aus derselben Rechnung.

    Der volle Bereichsnachweis zählte genau diese Ecken als Bruch: Der Bau
    lehnte richtig ab, aber der Baustein erklärte es nicht.
    """
    from app.core.errors import ValidationError

    spec = PARTS.get("printed_thread")
    assert spec.feasible is not None
    for internal in (True, False):
        for play in (0.2, 1.0):
            params = spec.params(
                size="custom_size", diameter=1.6, pitch=20.0, internal=internal, play=play
            )
            reason = spec.feasible(params)
            assert reason is not None
            with pytest.raises(ValidationError) as caught:
                spec.fn(params)
            assert caught.value.constraint == "no_core"
            assert str(caught.value.detail) == str(reason)
    for values in ({"size": "M1.6", "play": 1.0}, {"size": "custom_size", "diameter": 1.6}):
        assert spec.feasible(spec.params(**values, internal=False)) is None, values


def _thread_in_a_tube(
    profile: Profile, outer: float, inner: float, extra: dict[str, Any] | None = None
) -> list[tuple[str, str]]:
    """Ein Rohr und ein Gewinde in seiner Bohrung, vorgewählt wie beim Klick."""
    from app.core.scene import ResultCache
    from app.core.scene.placement import values_for

    document = new_project("centauri-carbon-2", "petg").document
    History(document).apply(
        "Rohr",
        [
            OperationDraft(
                op="create_tube",
                params={
                    "outer_diameter": outer,
                    "inner_given": True,
                    "inner_diameter": inner,
                    "height": 20.0,
                    "segments": 192,
                },
            )
        ],
    )
    cache = ResultCache()
    first = evaluate(document, profile, cache=cache)
    hole = next(f for f in first.scene.objects["obj_1"].features.values() if f.kind == "hole")
    prefill = values_for(REGISTRY.get("insert_printed_thread"), hole)
    History(document).apply(
        "Gewinde",
        [
            OperationDraft(
                op="insert_printed_thread",
                inputs=("obj_1",),
                params={**prefill, **(extra or {}), "length": 12.0},
            )
        ],
    )
    result = evaluate(document, profile, cache=cache)
    assert result.stopped_at is None
    return [(finding.code, finding.severity) for finding in result.scene.report.findings]


def test_an_internal_thread_through_a_thin_tube_wall_is_reported(profile: Profile) -> None:
    """Die Restwand um ein Gewinde in einer Rohrbohrung wird gemessen und gemeldet.

    Bis dahin blieb ein Gewinde, das eine Rohrwand bis auf 0,1 mm abtrug, ohne
    Befund (Review RM-532, F2). Am Rohr ist die Außenwand kein Merkmal, und die
    Prüfung am Endstand (``relations.thinnest_sleeve``) sieht sie nicht; das
    Gewinde misst sie deshalb beim Setzen am Träger
    (``fasteners.thread_at_hole``). Das Rohr 65/60 bekommt die M64, ihr Gang
    reicht bis Ø 64,2 — 0,4 mm Wand. 72/60 lässt 3,9 mm und bleibt still.
    """
    thin = _thread_in_a_tube(profile, 65.0, 60.0)
    assert ("parts.thread_thin_wall", "warning") in thin, thin
    thick = _thread_in_a_tube(profile, 72.0, 60.0)
    assert not any("thin_wall" in code for code, _severity in thick), thick


def test_following_the_thin_wall_advice_clears_the_finding(profile: Profile) -> None:
    """Der Rat des Restwand-Befunds wirkt (Review RM-532 Runde 2, N2).

    Er riet zu einer feineren Steigung — die ändert die Wand nicht, sie hängt am
    Außenmaß des Gangs. Jetzt rät er zu einem kleineren Nennmaß mit feinerer
    Steigung: Ø 62,2 × 2 ist Kernloch der 60er-Bohrung und lässt dem Rohr 65/60
    1,3 mm Wand. Der Knopf öffnet das Feld, das das Maß trägt.
    """
    import trimesh

    from app.core.geom.mesh import MeshData
    from app.core.knowledge.parts.fasteners import thread_at_hole
    from app.core.types import Feature

    followed = _thread_in_a_tube(
        profile, 65.0, 60.0, {"size": "custom_size", "diameter": 62.2, "pitch": 2.0}
    )
    assert not any("thin_wall" in code for code, _severity in followed), followed
    assert not any("bore_widened" in code for code, _severity in followed), followed

    spec = PARTS.get("printed_thread")
    tube = MeshData(raw=trimesh.creation.annulus(r_min=30.0, r_max=32.5, height=20.0, sections=192))
    bore = Feature(
        id="hole_1",
        kind="hole",
        provenance="detected",
        params={"diameter": 60.0, "depth": 20.0},
    )
    table = thread_at_hole(
        spec.params(size="M64", internal=True, play=0.2), bore, tube, profile, (0, 0, 10), (0, 0, 1)
    )
    assert [finding.values["field"] for finding in table] == ["size"], table
    own = thread_at_hole(
        spec.params(size="custom_size", diameter=64.0, pitch=2.0, internal=True, play=0.2),
        bore,
        tube,
        profile,
        (0, 0, 10),
        (0, 0, 1),
    )
    assert [finding.code for finding in own] == ["parts.thread_thin_wall", "parts.bore_widened"]
    assert {finding.values["field"] for finding in own} == {"diameter"}


def test_a_finer_pitch_that_drills_the_hole_out_says_so(profile: Profile) -> None:
    """Nur die Steigung feiner, Nenndurchmesser gleich: Das Werkzeug bohrt die Bohrung auf.

    Ø 66,6 mit Steigung 2 in einer 60-mm-Bohrung schneidet bei 64,6 an; der
    Befund nennt den Nenndurchmesser, mit dem die Bohrung Kernloch bleibt
    (60 + 2,2 = 62,2). Vorher geschah das still (Review RM-532, F3).
    """
    from app.core.knowledge.parts.fasteners import thread_at_hole
    from app.core.types import Feature

    def bore(diameter: float) -> Feature:
        return Feature(
            id="hole_1", kind="hole", provenance="detected", params={"diameter": diameter}
        )

    widened = _thread_in_a_tube(
        profile, 72.0, 60.0, {"size": "custom_size", "diameter": 66.6, "pitch": 2.0}
    )
    assert ("parts.bore_widened", "warning") in widened, widened
    spec = PARTS.get("printed_thread")
    [finding] = thread_at_hole(
        spec.params(size="custom_size", diameter=66.6, pitch=2.0, internal=True, play=0.2),
        bore(60.0),
        None,
        profile,
    )
    assert finding.values["fitting_mm"] == pytest.approx(62.2)
    assert finding.suggestions
    fitting = spec.params(size="custom_size", diameter=62.2, pitch=2.0, internal=True, play=0.2)
    assert thread_at_hole(fitting, bore(60.0), None, profile) == []
    assert (
        thread_at_hole(spec.params(size="M64", internal=True, play=0.2), bore(58.0), None, profile)
        == []
    )


def test_two_inserts_of_the_same_thread_and_length_are_told_apart_by_their_outside() -> None:
    """Ruthex M3S und M3x5x4 sind beide M3 × 4 — sie unterscheidet ihr Außendurchmesser."""
    from app.core.registry.surfaces import choice_label

    short, voron = choice_label("M3S"), choice_label("M3x5x4")
    assert short != voron
    assert "4,60" in short and "5,00" in voron
    assert choice_label("M4S") == "M4 · 4,00 mm"
    assert choice_label("M8") == "M8"


def test_an_external_thread_turns_into_the_internal_thread_of_the_same_size(
    profile: Profile,
) -> None:
    """Gewindebolzen und Gewindeloch derselben Größe: Luft über die ganze Länge.

    Der Bolzen ist doppelt so lang wie das Loch und läuft unten hinaus — genau
    dort stand bis zum 22.09.2026 der letzte Umlauf Material im Gang.
    """
    from app.core.knowledge.parts.build import subtract
    from app.core.units import EPS_GEOM

    spec = PARTS.get("printed_thread")
    play = profile.material.clearance
    length = 10.0
    bolt = spec.fn(spec.params(size="M6", length=2.0 * length, internal=False, play=play)).mesh
    tool = spec.fn(spec.params(size="M6", length=length, internal=True, play=play)).mesh
    plate = shapes.moved(shapes.box(20.0, 20.0, length), (0.0, 0.0, -length))
    hole = subtract(plate, tool)
    # Das Loch reicht von -length bis null, sein Gang beginnt unten; der Bolzen
    # beginnt eine ganze Zahl von Steigungen darunter und läuft damit in Phase.
    placed = bolt.raw.copy()
    placed.apply_translation((0.0, 0.0, -2.0 * length))
    overlap = boolean("intersection", [hole, MeshData.of(placed)], allow_empty=True)

    assert overlap.mesh.volume <= EPS_GEOM * (hole.raw.area + placed.area)


@pytest.mark.parametrize(
    ("bore", "size", "nominal"), [(60.0, "M64", 64.0), (70.0, "custom_size", 76.6)]
)
def test_a_pipe_of_sixty_takes_an_internal_thread_and_its_bolt_turns_through(
    profile: Profile, bore: float, size: str, nominal: float
) -> None:
    """Der Kundenvorschlag S-20261006-c66299: ein Innengewinde in einem Rohr mit 60 mm.

    Das Rohr mit 8 mm Wand bekommt das Gewinde, das ``size_for_thread`` an
    seiner Bohrung vorwählt: in 60 mm seit Tabellenversion 13 die Normgröße
    M64 (Kernloch 58, Nennmaß 64), in 70 mm, wo keine Normgröße mehr passt, ein
    eigenes Maß Ø 76,6 mit der Regelsteigung 6. Gemessen wird, was der Kunde
    braucht: Das Rohr bleibt ein geschlossenes Teil mit Wand um die Gänge, die
    Gänge schneiden in die Wand, und ein Bolzen desselben Maßes läuft über die
    ganze Länge hindurch, ohne irgendwo Material zu treffen.
    """
    from app.core.knowledge.parts.build import subtract
    from app.core.knowledge.parts.fasteners import size_for_thread, thread_measure
    from app.core.units import EPS_GEOM

    chosen = size_for_thread(bore)
    assert chosen["size"] == size
    assert thread_measure(
        chosen["size"], chosen.get("diameter", 0.0), chosen.get("pitch", 0.0)
    ) == (pytest.approx(nominal), pytest.approx(6.0))
    spec = PARTS.get("printed_thread")
    play = profile.material.clearance
    length = 18.0
    outer = bore + 16.0
    tool = spec.fn(spec.params(**chosen, length=length, play=play)).mesh
    bolt_values = {**chosen, "internal": False}
    bolt = spec.fn(spec.params(**bolt_values, length=2.0 * length, play=play)).mesh
    pipe = subtract(shapes.cylinder(outer, length), shapes.cylinder(bore, length + 1.0))
    pipe = subtract(shapes.moved(pipe, (0.0, 0.0, -length)), tool)

    assert pipe.is_watertight and pipe.component_count == 1
    radial = np.hypot(pipe.raw.vertices[:, 0], pipe.raw.vertices[:, 1])
    inner = radial[radial < outer / 2.0 - 1.0]
    # Die Gänge reichen bis zum Nennmaß plus Spiel in die Wand, die Wand dahinter bleibt.
    assert float(inner.max()) * 2.0 == pytest.approx(nominal + play, abs=0.05)
    assert outer - float(inner.max()) * 2.0 > 2.0 * 2.0, "um die Gänge steht Wand"
    # Wie beim Tabellenpaar: Der Bolzen beginnt eine ganze Zahl von Steigungen
    # unter dem Gewinde und läuft in Phase hindurch.
    placed = bolt.raw.copy()
    placed.apply_translation((0.0, 0.0, -2.0 * length))
    overlap = boolean("intersection", [pipe, MeshData.of(placed)], allow_empty=True)
    assert overlap.mesh.volume <= EPS_GEOM * (pipe.raw.area + placed.area)


@pytest.mark.parametrize("size", ["M2", "M3", "M6", "M8"])
@pytest.mark.parametrize("length", [2.0, 200.0])
def test_a_countersunk_printed_screw_keeps_its_whole_thread_below_the_head(
    size: str,
    length: float,
) -> None:
    """Kopfhöhe und Gewindelänge sind zwei aufeinanderfolgende Abschnitte."""
    spec = PARTS.get("printed_screw")
    screw = standards.screw(size)
    play = 0.25
    built = spec.fn(spec.params(size=size, length=length, countersunk=True, play=play)).mesh
    thread_top = -(screw.countersink - (screw.nominal - play)) / 2.0
    section = built.raw.section(
        plane_origin=(0.0, 0.0, thread_top - length + screw.pitch / 2.0),
        plane_normal=(0.0, 0.0, 1.0),
    )

    assert built.is_watertight and built.component_count == 1
    assert built.bounds.minimum[2] == pytest.approx(thread_top - length, abs=0.02)
    assert section is not None, "der unterste Gewindegang fehlt"
    assert 2.0 * float(np.hypot(section.vertices[:, 0], section.vertices[:, 1]).max()) > (
        screw.nominal - play - screw.pitch * 0.25
    )


@pytest.mark.parametrize("size", ["M2", "M8"])
def test_a_printed_countersink_is_a_named_clean_host_cut(size: str) -> None:
    """Die Senkung gehört zum Träger und darf nicht am Schraubennetz hängen."""
    spec = PARTS.get("printed_screw")

    assert spec.host_cut is not None
    built = spec.host_cut(spec.params(size=size, length=2.0, countersunk=True, play=0.25))

    assert built is not None
    assert built.mesh.is_watertight and built.mesh.component_count == 1
    assert not has_self_intersections(built.mesh)
    assert set(built.features) == {"countersink_1"}
    assert built.features["countersink_1"].kind == "cone"


def _separate_part_and_host(box: str, drafts: list[OperationDraft], profile: Profile) -> Any:
    """Quader 40 × 40 × 10 aus ``box``, dann ``drafts``: lösbares Teil und Träger getrennt.

    Das kleinste Netzstück ist nicht allein das Teil — der Senkkopf bleibt am exakten Kern
    ein Verbund aus Kegel und Gang —, also ist alles außer dem größten Stück das Teil.
    """
    import trimesh

    from app.core.geom.mesh import as_mesh_data

    project = new_project("centauri-carbon-2", "petg")
    history = History(project.document)
    history.apply(
        "Quader",
        [OperationDraft(op=box, params={"width": 40.0, "depth": 40.0, "height": 10.0})],
    )
    for draft in drafts:
        history.apply(draft.op, [draft])
    result = evaluate(project.document, profile, sources=ProjectSources(project))
    assert result.complete, [str(f.message) for f in result.scene.report.findings]
    pieces = sorted(
        as_mesh_data(result.scene.objects["obj_1"].mesh).raw.split(only_watertight=False),
        key=lambda piece: abs(float(piece.volume)),
    )
    assert len(pieces) >= 2, "das lösbare Teil liegt als eigenes Stück neben dem Träger"
    return trimesh.util.concatenate(pieces[:-1]), pieces[-1]


def _least_distance(points: Any, surface: Any) -> float:
    """Der kleinste Abstand der Punkte zur Oberfläche (ohne ``rtree``, ``geom.mesh``)."""
    from app.core.geom.mesh import on_surface

    _closest, distance, _triangle = on_surface(surface, np.asarray(points, dtype=float))
    return float(distance.min())


@pytest.mark.parametrize("box", ["create_box", "create_brep_box"])
@pytest.mark.parametrize("countersunk", [False, True], ids=["hexagon", "countersunk"])
def test_a_printed_screw_keeps_the_profile_play_to_its_seat(
    profile: Profile, box: str, countersunk: bool
) -> None:
    """RM-276: Zwischen Kopf und Sitz steht das Spiel aus dem Materialprofil.

    Durchsicht 0.5.1 (rest-schraube): Der Senkkopf lag bündig in seiner Senkung —
    dieselbe 90°-Flanke, derselbe Außendurchmesser, 42 deckungsgleiche Ecken —,
    der Sechskantkopf stand ohne Abstand auf der Fläche; Spiel hatte nur das
    Gewinde. An Ort und Stelle in einem Stück gedruckt verschweißte der Kopf mit
    dem Träger. Gemessen in Einbaulage an beiden Kernen: der kleinste Abstand
    zwischen den Ecken des Kopfes (außerhalb der Bohrung) und dem Träger, und
    umgekehrt. Am exakten Kern misst das an der Tessellation, deren Sehnen
    höchstens ``MAX_FACET_SAG`` von der Fläche abweichen.
    """
    from app.core.units import EPS_DISPLAY, MAX_FACET_SAG

    play = profile.material.clearance
    bore = 5.5  # Durchgangsloch M5: Die Größe kommt aus der Bohrung.
    screw, host = _separate_part_and_host(
        box,
        [
            OperationDraft(
                op="drill_hole",
                inputs=("obj_1",),
                params={"diameter": bore, "depth": 0.0, "compensate": False},
            ),
            OperationDraft(
                op="insert_printed_screw",
                inputs=("obj_1",),
                params={"at_feature": "hole_1", "length": 12.0, "countersunk": countersunk},
            ),
        ],
        profile,
    )
    centre = (np.asarray(host.bounds[0]) + np.asarray(host.bounds[1]))[:2] / 2.0
    outside = bore / 2.0 + 0.02
    head = np.asarray(screw.vertices, dtype=float)
    head = head[np.hypot(*(head[:, :2] - centre).T) > outside]
    seat = np.asarray(host.vertices, dtype=float)
    seat = seat[(np.hypot(*(seat[:, :2] - centre).T) > outside) & (seat[:, 2] > 5.0)]
    seat = seat[np.hypot(*(seat[:, :2] - centre).T) < 8.0]

    # Die ebene Deckfläche hat unter dem Sechskantkopf keine Ecken; dort misst
    # nur die eine Richtung.
    gaps = [_least_distance(head, host)]
    if len(seat):
        gaps.append(_least_distance(seat, screw))
    gap = min(gaps)

    assert gap == pytest.approx(play, abs=MAX_FACET_SAG), f"Kopf ↔ Sitz {gap:.4f} mm"
    if countersunk:
        assert float(screw.bounds[1][2]) == pytest.approx(10.0, abs=EPS_DISPLAY), (
            "der Senkkopf bleibt bündig mit der Fläche"
        )
    else:
        assert float(head[:, 2].min()) == pytest.approx(10.0 + play, abs=EPS_DISPLAY), (
            "der Sechskantkopf steht um das Spiel über der Fläche"
        )


@pytest.mark.parametrize("box", ["create_box", "create_brep_box"])
def test_a_printed_nut_keeps_the_profile_play_to_its_face(profile: Profile, box: str) -> None:
    """RM-276, der Zwilling: Die gedruckte Mutter lag ebenso ohne Abstand auf ihrer Fläche."""
    from app.core.units import EPS_DISPLAY

    play = profile.material.clearance
    nut, host = _separate_part_and_host(
        box,
        [
            OperationDraft(
                op="insert_printed_nut",
                inputs=("obj_1",),
                params={"size": "M5", "x": 0.0, "y": 0.0, "z": 10.0, "nz": 1.0},
            )
        ],
        profile,
    )
    top = np.asarray(host.vertices, dtype=float)
    top = top[top[:, 2] > 5.0]

    gap = min(_least_distance(nut.vertices, host), _least_distance(top, nut))

    assert gap == pytest.approx(play, abs=EPS_DISPLAY), f"Mutter ↔ Fläche {gap:.4f} mm"
    assert float(nut.bounds[0][2]) == pytest.approx(10.0 + play, abs=EPS_DISPLAY)


def test_a_part_that_reaches_upwards_keeps_the_middle_of_the_bore(profile: Profile) -> None:
    """Die Gegenprobe, und ohne sie wäre die Regel oben falsch.

    Nicht jeder Baustein an einer Bohrung liegt unter seinem Ursprung: Die
    Mutternfalle baut ihre Tasche **nach oben**, weil die Mutter im Material
    sitzt und nicht an der Oberfläche. An die Mündung gesetzt stünde sie
    vollständig über der Platte und trüge nichts ab — aus einem halben Fehler
    wäre ein ganzer geworden.

    Gemessen wird an der Tasche selbst: Auf halber Höhe muss sie da sein, und
    dicht unter der Oberfläche darf sie es nicht.
    """
    project = _plate_with_a_through_bore()
    History(project.document).apply(
        "Mutternfalle",
        [
            OperationDraft(
                op="insert_nut_trap",
                inputs=("obj_1",),
                params={"at_feature": "hole_1", "size": "M3", "slide": 12.0},
            )
        ],
    )
    result = evaluate(project.document, profile, sources=ProjectSources(project))

    assert result.complete, [str(f.message) for f in result.scene.report.findings]
    mesh = result.scene.objects["obj_1"].mesh
    assert _widest_bore(mesh, 5.5) > 6.5, "die Tasche liegt nicht mehr im Material"
    assert _widest_bore(mesh, 9.5) < 6.5, "die Tasche ist an die Oberfläche gewandert"


def test_a_nut_trap_on_a_top_face_sinks_into_the_material(profile: Profile) -> None:
    """Die Mutternfalle an einer Fläche baut ihre Tasche ins Material (§24.1).

    Sie ist der einzige abtragende Baustein, der nach oben baut — die Mutter
    sitzt im Material, nicht an der Oberfläche. An eine Bohrung gesetzt bleibt
    sie deshalb in deren Mitte (:func:`test_a_part_that_reaches_upwards_keeps_
    the_middle_of_the_bore`); an eine **Deckfläche** gesetzt stand sie vorher
    vollständig über der Platte und trug nichts ab — ``boolean.without_effect``,
    unverändertes Volumen. Jetzt wird sie entgegen der Normalen ins Material
    gebaut, die Öffnung an der Fläche.

    Gemessen wird an drei Dingen: der Befund darf nicht mehr kommen, das
    Volumen muss sinken, und dicht unter der Deckfläche muss der Sechskant
    stehen — ohne über die Fläche hinauszuwachsen.
    """
    project = new_project("centauri-carbon-2", "petg")
    History(project.document).apply("Quader", [OperationDraft(op="create_box", params={})])
    before = evaluate(project.document, profile, sources=ProjectSources(project))
    plate_volume = before.scene.objects["obj_1"].mesh.raw.volume

    History(project.document).apply(
        "Mutternfalle",
        [
            OperationDraft(
                op="insert_nut_trap",
                inputs=("obj_1",),
                params={"at_feature": "face_top", "size": "M6", "slide": 0.0, "screw_hole": False},
            )
        ],
    )
    result = evaluate(project.document, profile, sources=ProjectSources(project))

    assert result.complete, [str(f.message) for f in result.scene.report.findings]
    codes = [f.code for f in result.scene.report.findings]
    assert "boolean.without_effect" not in codes, "die Tasche liegt neben dem Körper statt darin"
    mesh = result.scene.objects["obj_1"].mesh
    assert mesh.raw.volume < plate_volume - 1.0, "die Mutternfalle hat nichts abgetragen"
    # Die Deckfläche liegt bei z = 10; die Tasche sitzt darunter, ihre Öffnung an ihr.
    assert _widest_bore(mesh, 9.5) > 6.5, "dicht unter der Fläche fehlt die Tasche"
    assert mesh.bounds.maximum[2] == pytest.approx(10.0, abs=0.02), (
        "die Tasche wächst über die Fläche hinaus statt ins Material"
    )


@pytest.mark.parametrize("screw", [False, True])
@pytest.mark.parametrize(("height", "floor"), [(10.0, 10.0), (8.0, 4.0)])
def test_a_nut_trap_set_by_hand_cuts_its_pocket(
    profile: Profile, height: float, floor: float, screw: bool
) -> None:
    """RM-591: Von Hand gesetzt, ohne Fläche und Richtung, schnitt die Mutternfalle nichts.

    Mit nur einer Stelle — über Chat, Kommandozeile oder den Dialog ohne Fläche —
    zeigte sie entlang Z, und auf der Deckfläche stand ihre Tasche ganz
    darüber: Der Körper verlor nur das Schraubenloch, und *Stift für Bohrung*
    baute an Tasche und Bohrung in die Luft (Review G). Soll: Auf der Deckfläche
    (z = 10) liegt die Tasche darunter, ihre Öffnung an der Fläche. Im Material
    gesetzt — das Gehäuse-Beispiel setzt seine Mutternfalle in die Mitte des
    8 mm dicken Bodens — bleibt sie über der Stelle, wo sie war.

    **Auch mit Schraubenloch.** Die erste Fassung fragte die Luft auf halber
    Höhe des ganzen Bausteins, und das Schraubenloch reicht über jeden Boden
    hinaus: Im Gehäuse-Beispiel rückte die Tasche um 2,5 mm nach unten, bei
    gleichem Volumen — gesehen erst an der neu gerenderten Vorschau. Gemessen
    wird an der Schlüsselweite der M6-Mutter (10 mm, ISO 4032): Wo die Tasche
    liegt, ist das Loch weiter, darunter bleibt nur das Schraubenloch.
    """
    project = new_project("centauri-carbon-2", "petg")
    History(project.document).apply(
        "Quader",
        [OperationDraft(op="create_box", params={"width": 40.0, "depth": 40.0, "height": height})],
    )
    History(project.document).apply(
        "Mutternfalle",
        [
            OperationDraft(
                op="insert_nut_trap",
                inputs=("obj_1",),
                params={"size": "M6", "slide": 0.0, "screw_hole": screw, "z": floor},
            )
        ],
    )
    result = evaluate(project.document, profile, sources=ProjectSources(project))

    assert result.complete, [str(f.message) for f in result.scene.report.findings]
    codes = [f.code for f in result.scene.report.findings]
    assert "boolean.without_effect" not in codes, "die Tasche liegt neben dem Körper statt darin"
    mesh = result.scene.objects["obj_1"].mesh
    assert mesh.raw.volume < 40.0 * 40.0 * height - 1.0, "die Mutternfalle hat nichts abgetragen"
    assert mesh.bounds.maximum[2] == pytest.approx(height, abs=0.02)
    across_flats = 10.0
    if floor == height:
        assert _widest_bore(mesh, floor - 0.5) > across_flats, "unter der Fläche fehlt die Tasche"
        return
    assert _widest_bore(mesh, floor + 1.0) > across_flats, "über der Stelle fehlt die Tasche"
    if screw:
        assert _widest_bore(mesh, floor - 1.0) < across_flats, "die Tasche rückte unter die Stelle"
        return
    cut = mesh.raw.section(plane_origin=[0.0, 0.0, floor - 1.0], plane_normal=[0.0, 0.0, 1.0])
    inner = np.hypot(*np.asarray(cut.vertices, dtype=float)[:, :2].T)
    assert (inner >= 15.0).all(), "unter der Stelle ist kein Loch, die Tasche bleibt oben"


# --- RM-631: Eine Durchgangsbohrung geht genau durch das Teil -------------------------

#: Ein Hauch neben der Achse, damit kein Messpunkt auf der Diagonale einer Deckfläche liegt.
_BESIDE_THE_AXIS = (0.013, 0.017)


def _rm631_carrier(kind: str, shape: str) -> Any:
    """Der Träger der RM-631-Fälle, von Hand gebaut, in X und Y um null.

    ``block12`` und ``block40``: Quader 40 × 40 × 12 bzw. × 40. ``thin3``: eine
    3 mm dicke Platte. ``clamp``: eine Klammer — unterer Backen z = 0 … 8,
    Spalt bis 12, oberer Backen z = 12 … 20, hinten bei y = 14 … 20 verbunden.
    """
    from app.core.types import SceneObject

    blocks = {
        "block12": [(40.0, 40.0, 12.0, 0.0, 0.0)],
        "block40": [(40.0, 40.0, 40.0, 0.0, 0.0)],
        "thin3": [(40.0, 40.0, 3.0, 0.0, 0.0)],
        "touching": [(40.0, 40.0, 6.0, 0.0, 0.0), (40.0, 40.0, 6.0, 0.0, 6.0)],
        "clamp": [
            (40.0, 40.0, 8.0, 0.0, 0.0),
            (40.0, 40.0, 8.0, 0.0, 12.0),
            (40.0, 6.0, 20.0, 17.0, 0.0),
        ],
    }[shape]
    if kind == "brep":
        from tests.helpers import exact_kernel

        edit = exact_kernel()
        solids = [
            edit.moved(edit.box(width, depth, height), (0.0, y, z))
            for width, depth, height, y, z in blocks
        ]
        if shape == "touching":
            # Zwei Platten in einem Objekt, als Verbund — wie eine eingelesene Baugruppe.
            from app.core.knowledge.parts.exact import compound

            return SceneObject(id="obj_1", name="Träger", mesh=compound(*solids), kind="brep")
        solid = solids[0] if len(solids) == 1 else edit.unified(edit.boolean("union", solids))
        return SceneObject(id="obj_1", name="Träger", mesh=solid, kind="brep")
    import trimesh

    meshes = []
    for width, depth, height, y, z in blocks:
        box = trimesh.creation.box(extents=(width, depth, height))
        box.apply_translation((0.0, y, z + height / 2.0))
        meshes.append(MeshData.of(box))
    if shape == "touching":
        # Zwei Schalen, die sich berühren — nicht vereinigt.
        joined = trimesh.util.concatenate([entry.raw for entry in meshes])
        return SceneObject(id="obj_1", name="Träger", mesh=MeshData.of(joined))
    mesh = meshes[0] if len(meshes) == 1 else as_mesh_data(boolean("union", meshes).mesh)
    return SceneObject(id="obj_1", name="Träger", mesh=mesh)


def _rm631_insert(kind: str, shape: str, part: str, top: float, **params: Any) -> Any:
    """Den Baustein von Hand auf die Fläche bei ``top`` setzen, Richtung +Z."""
    from app.core.bootstrap import load_operations
    from tests.helpers import run_operation

    load_operations()
    profile = profiles.make_profile("centauri-carbon-2", "petg")
    placed = {"x": 0.0, "y": 0.0, "z": top, "nx": 0.0, "ny": 0.0, "nz": 1.0, **params}
    return run_operation(f"insert_{part}", _rm631_carrier(kind, shape), profile, **placed)


def _material_on_the_axis(entry: Any, heights: Any) -> list[bool]:
    """Ob auf der Z-Achse (ein Hauch daneben) in diesen Höhen Material liegt."""
    from app.core.perceive.features import _point_inside_shell, _triangle_bounds

    triangles = np.asarray(as_mesh_data(entry.mesh).raw.triangles, dtype=np.float64)
    bounds = _triangle_bounds(triangles)
    x, y = _BESIDE_THE_AXIS
    return [
        bool(_point_inside_shell(np.array([x, y, float(height)]), triangles, bounds))
        for height in heights
    ]


def _bore_ends(feature: Any) -> tuple[list[float], Any]:
    """Die beiden Enden einer erklärten Bohrung, sortiert, und ihre Achse als Einheitsvektor."""
    axis = np.asarray(feature.params["axis"], dtype=float)
    axis /= float(np.linalg.norm(axis))
    centre = np.asarray(feature.params["centre"], dtype=float)
    half = float(feature.params["depth"]) / 2.0
    return sorted([centre - axis * half, centre + axis * half], key=lambda p: float(p @ axis)), axis


@pytest.mark.parametrize("kind", ["mesh", "brep"])
def test_a_nut_trap_bores_through_a_carrier_thicker_than_its_old_reach(kind: str) -> None:
    """RM-631: In einem 40 mm dicken Quader blieb die Schraubenbohrung ein Sackloch.

    Das Werkzeug reichte 10 mm unter die Tasche, die Bohrung endete bei
    z = 27,485, darunter stand Material bis z = 0 — und erklärt war sie als
    Durchgang (``through=True``). Der Parametertext verspricht das Loch für die
    Schraube durch das Teil. Soll: durch den ganzen Quader, z = 0 bis 40, als
    Durchgang erklärt, entlang der Achse kein Material mehr.
    """
    result = _rm631_insert(kind, "block40", "nut_trap", 40.0, size="M3", slide=0.0)
    carrier = result.outputs[0]
    bore = carrier.features["nut_trap_bore_1"]
    ends, _axis = _bore_ends(bore)
    assert sorted(float(end[2]) for end in ends) == pytest.approx([0.0, 40.0], abs=0.05)
    assert bore.params["through"] is True
    assert not any(_material_on_the_axis(carrier, [0.5, 10.0, 20.0, 27.0, 30.0, 39.0]))


@pytest.mark.parametrize("kind", ["mesh", "brep"])
def test_a_nut_trap_on_the_floor_of_a_gap_leaves_the_jaw_above_alone(kind: str) -> None:
    """RM-631: Das Werkzeug reichte 10 mm über die Fläche und bohrte, was dort stand.

    Auf dem Boden eines 4 mm hohen Spalts gesetzt, ging das Schraubenloch durch
    den Spalt hindurch 6 mm in den Backen darüber (Material dort danach erst ab
    z = 18). Soll: Der Backen über dem Spalt bleibt voll, die Bohrung geht durch
    den unteren Backen, z = 0 bis 8, und ist als Durchgang erklärt.
    """
    result = _rm631_insert(kind, "clamp", "nut_trap", 8.0, size="M3", slide=0.0)
    carrier = result.outputs[0]
    assert all(_material_on_the_axis(carrier, [12.5, 14.0, 16.0, 18.0, 19.5])), "oberer Backen"
    assert not any(_material_on_the_axis(carrier, [0.5, 3.0, 5.0, 7.5]))
    bore = carrier.features["nut_trap_bore_1"]
    ends, _axis = _bore_ends(bore)
    assert sorted(float(end[2]) for end in ends) == pytest.approx([0.0, 8.0], abs=0.05)
    assert bore.params["through"] is True


@pytest.mark.parametrize("kind", ["mesh", "brep"])
@pytest.mark.parametrize(("depth", "through", "low"), [(10.0, False, 2.0), (14.0, True, 0.0)])
def test_a_screw_hole_with_a_set_depth_says_whether_it_goes_through(
    kind: str, depth: float, through: bool, low: float
) -> None:
    """RM-631: *Schraubenloch mit Senkung*, 10 mm tief in 12 mm, hieß Durchgang.

    Mit eingetragener Tiefe ist die Bohrung so tief wie eingetragen — ein
    Sackloch, wo der Träger dicker ist, und so erklärt (Karte: „Sackloch“).
    Reicht die Tiefe durch, endet die Erklärung an der Unterseite (RM-598).
    """
    result = _rm631_insert(kind, "block12", "screw_hole", 12.0, size="M3", depth=depth)
    bore = result.outputs[0].features["screw_hole_bore_1"]
    ends, _axis = _bore_ends(bore)
    assert sorted(float(end[2]) for end in ends) == pytest.approx([low, 12.0], abs=0.05)
    assert bore.params["through"] is through


@pytest.mark.parametrize("kind", ["mesh", "brep"])
@pytest.mark.parametrize(
    ("part", "params", "name"),
    [
        ("keyhole", {}, "keyhole_bore_1"),
        ("cable_gland", {"strain_relief": False}, "cable_gland_bore_1"),
        ("hose_barb", {}, "hose_barb_passage_1"),
    ],
)
@pytest.mark.parametrize(
    ("shape", "top", "through"), [("block40", 40.0, False), ("thin3", 3.0, True)]
)
def test_a_cut_through_bore_of_set_length_is_blind_in_a_thicker_carrier(
    kind: str, part: str, params: dict[str, Any], name: str, shape: str, top: float, through: bool
) -> None:
    """RM-631: Dasselbe Erklärungsmuster an jedem abtragenden Baustein mit fester Länge.

    Schlüsselloch, Kabeldurchführung und Schlauchanschluss bohren so tief, wie
    ihre Maße sagen (Tiefe, Wandstärke). Im 40-mm-Quader blieb jede Bohrung ein
    Sackloch und hieß Durchgang; in einer 3 mm dicken Platte geht sie durch.
    Die Kabeldurchführung ohne Zugentlastung: Mit ihr öffnet die Bohrung in den
    Klemmkanal dahinter, und gefragt wird je Bohrung, ob hinter ihren Enden
    Material liegt.
    """
    result = _rm631_insert(kind, shape, part, top, **params)
    bore = result.outputs[0].features[name]
    assert bore.params["through"] is through


@pytest.mark.parametrize("kind", ["mesh", "brep"])
def test_a_nut_trap_laid_in_from_below_has_its_pocket_under_the_face(kind: str) -> None:
    """RM-631: *Von unten eingelegt* lag die Tasche halb über der Fläche, die Bohrung quer.

    Gedreht wurde nur der Körper: Der Schlitz lief von der Tasche weg tiefer ins
    Material, die Tasche saß mittig auf der Fläche, die Schraubenachse in der
    Fläche selbst — und erklärt waren Tasche und Bohrung entlang Z wie beim
    Einschieben. Soll: Der Schlitz führt von der Fläche hinunter zur Tasche, die
    Schraube liegt quer in der Tiefe des Einschubwegs und geht durch den ganzen
    Quader; Tasche und Bohrung sind dort erklärt, wo sie liegen.
    """
    slide = 12.0
    result = _rm631_insert(
        kind, "block40", "nut_trap", 40.0, size="M3", slide=slide, direction="bottom"
    )
    carrier = result.outputs[0]
    bore = carrier.features["nut_trap_bore_1"]
    ends, axis = _bore_ends(bore)
    assert abs(float(axis[2])) < 1e-9, "die Schraube liegt quer zur Fläche"
    assert float(ends[0][2]) == pytest.approx(40.0 - slide, abs=0.05)
    assert sorted(abs(float(end @ axis)) for end in ends) == pytest.approx([20.0, 20.0], abs=0.05)
    assert bore.params["through"] is True
    pocket = carrier.features["nut_trap_pocket_1"]
    assert float(pocket.params["centre"][2]) == pytest.approx(40.0 - slide, abs=0.05)
    nut = standards.nut("M3")
    assert as_mesh_data(carrier.mesh).bounds.maximum[2] == pytest.approx(40.0, abs=0.02)
    # Auf halbem Einschubweg ist nur der Schlitz da, so breit wie die Mutter über die Flächen.
    cut = as_mesh_data(carrier.mesh).raw.section(
        plane_origin=[0.0, 0.0, 40.0 - slide / 2.0], plane_normal=[0.0, 0.0, 1.0]
    )
    inner = np.asarray(cut.vertices, dtype=float)
    inner = inner[np.hypot(inner[:, 0], inner[:, 1]) < 15.0]
    assert float(np.abs(inner[:, 0]).max()) == pytest.approx(
        (nut.width + _profile_clearance()) / 2.0, abs=0.02
    )


def _profile_clearance() -> float:
    """Das Spiel des PETG-Profils, mit dem die RM-631-Fälle rechnen."""
    return profiles.make_profile("centauri-carbon-2", "petg").material.clearance


@pytest.mark.parametrize("kind", ["mesh", "brep"])
def test_a_nut_trap_laid_in_from_below_does_not_sit_across_a_bore(kind: str) -> None:
    """RM-631: An einer Bohrung stünde die Schraube *von unten eingelegt* quer zu ihr.

    Die Mutternfalle sitzt in der Mitte der Bohrung, und ihre Schraube gehört in
    deren Achse. Von unten eingelegt liegt sie quer — durch den ganzen Träger
    hindurch. Soll: Die Operation sagt ab, mit dem Weg zurück in den Schritt.
    """
    from app.core.errors import ValidationError
    from tests.helpers import run_operation

    drilled, hole = _drilled_plate(kind, 12.0, 3.4)
    profile = profiles.make_profile("centauri-carbon-2", "petg")
    with pytest.raises(ValidationError) as refusal:
        run_operation(
            "insert_nut_trap", drilled, profile, at_feature=hole, size="M3", direction="bottom"
        )
    assert refusal.value.constraint == "feasible"
    assert refusal.value.field == "direction", "Nachprüfung G, N-9: der Cursor gehört ins Feld"
    assert refusal.value.suggestions


def _drilled_plate(
    kind: str, height: float, diameter: float, depth: float = 0.0
) -> tuple[Any, str]:
    """Platte 40 × 40 × ``height`` mit einer Bohrung durch die Mitte, ausgewertet, und ihr Name."""
    from app.core.bootstrap import load_operations

    load_operations()
    if kind == "brep":
        from tests.helpers import exact_kernel

        exact_kernel()
    profile = profiles.make_profile("centauri-carbon-2", "petg")
    project = new_project("centauri-carbon-2", "petg")
    History(project.document).apply(
        "Platte mit Bohrung",
        [
            OperationDraft(
                op="create_box" if kind == "mesh" else "create_brep_box",
                params={"width": 40.0, "depth": 40.0, "height": height},
            ),
            OperationDraft(
                op="drill_hole",
                inputs=("obj_1",),
                params={"diameter": diameter, "depth": depth, "z": height, "compensate": False},
            ),
        ],
    )
    evaluated = evaluate(project.document, profile, sources=ProjectSources(project))
    assert evaluated.complete
    drilled = evaluated.scene.objects["obj_1"]
    (hole,) = [name for name, feature in drilled.features.items() if feature.kind == "hole"]
    return drilled, hole


@pytest.mark.parametrize("kind", ["mesh", "brep"])
@pytest.mark.parametrize(("diameter", "widened"), [(2.5, 3.4), (6.0, 6.0)])
def test_a_nut_trap_in_a_bore_takes_its_screw_hole_along_the_bore(
    kind: str, diameter: float, widened: float
) -> None:
    """RM-631: In einer Bohrung reicht das Schraubenloch durch das Teil, erklärt bis zu ihren Enden.

    Die Mutternfalle sitzt in der Mitte der Bohrung einer 20 mm dicken Platte
    (Tasche z = 10 bis 12,5). Erklärt war das Schraubenloch fest von z = 0 bis
    22,525, 2,5 mm über die Fläche hinaus. Soll: von z = 0 bis 20, als Durchgang;
    eine engere Bohrung (Ø 2,5) wird auf das Durchgangsloch der M3 (Ø 3,4)
    aufgebohrt, eine weitere (Ø 6) bleibt, wie sie ist.
    """
    from tests.helpers import run_operation

    drilled, hole = _drilled_plate(kind, 20.0, diameter)
    profile = profiles.make_profile("centauri-carbon-2", "petg")
    result = run_operation("insert_nut_trap", drilled, profile, at_feature=hole, size="M3")
    carrier = result.outputs[0]
    bore = carrier.features["nut_trap_bore_1"]
    ends, _axis = _bore_ends(bore)
    assert sorted(float(end[2]) for end in ends) == pytest.approx([0.0, 20.0], abs=0.05)
    assert bore.params["through"] is True
    for height in (2.0, 18.0):
        assert _widest_bore(as_mesh_data(carrier.mesh), height) == pytest.approx(widened, abs=0.02)


@pytest.mark.parametrize("kind", ["mesh", "brep"])
@pytest.mark.parametrize(
    ("part", "name"),
    [("cable_gland", "cable_gland_bore_1"), ("hose_barb", "hose_barb_passage_1")],
)
@pytest.mark.parametrize(
    ("shape", "top", "thick"), [("block40", 40.0, True), ("thin3", 3.0, False)]
)
def test_a_part_built_for_a_thinner_wall_says_so(
    kind: str, part: str, name: str, shape: str, top: float, thick: bool
) -> None:
    """RM-633: Die Kabeldurchführung im dicken Träger hieß Durchgang und schwieg.

    Kabeldurchführung und Schlauchanschluss bohren durch eine Wand der
    eingetragenen Stärke (3 mm) und bauen dahinter auf. Im 40-mm-Quader lag der
    Klemmkanal eingeschlossen im Material, die Bohrung öffnete in ihn und hieß
    Durchgang, ohne Befund. Soll: Sackloch, und ein Befund nennt die gemessene
    Wand (40 mm) und öffnet das Feld ``wall``. In der 3-mm-Platte bleibt alles,
    wie es war.
    """
    result = _rm631_insert(kind, shape, part, top)
    bore = result.outputs[0].features[name]
    said = [finding for finding in result.findings if finding.code == "parts.wall_thicker"]
    if not thick:
        assert bore.params["through"] is True
        assert not said
        return
    assert bore.params["through"] is False
    (finding,) = said
    assert finding.severity == "warning"
    assert finding.values["field"] == "wall"
    assert finding.values["wall_mm"] == pytest.approx(40.0, abs=0.05)
    assert [action.id for action in finding.suggestions] == ["change_step"]


@pytest.mark.parametrize("kind", ["mesh", "brep"])
def test_a_cable_gland_in_a_slightly_thicker_wall_cuts_through_the_rest(kind: str) -> None:
    """RM-633, Gegenprobe: Ein paar Zehntel mehr Wand schneidet der Klemmkanal mit.

    Die ausgehöhlte Dose im Beispiel hat an ihrer linken Wand 2,8 statt 2,4 mm
    (Raster der Aushöhlung). Die Bohrung endet 0,4 mm vor der Innenseite, der
    Kanal dahinter geht durch den Rest — kein Sackloch, kein Befund. Die erste
    Fassung fragte den Träger direkt hinter der Bohrung und meldete hier eine
    Wand, die das Kabel nicht aufhält.
    """
    result = _rm631_insert(kind, "thin3", "cable_gland", 3.0, wall=2.6)
    bore = result.outputs[0].features["cable_gland_bore_1"]
    assert bore.params["through"] is True
    assert not [finding for finding in result.findings if finding.code == "parts.wall_thicker"]


@pytest.mark.parametrize("kind", ["mesh", "brep"])
@pytest.mark.parametrize("diameter", [6.0, 2.5])
def test_a_nut_trap_at_a_blind_bore_bores_on_through_the_part(kind: str, diameter: float) -> None:
    """Nachprüfung G, N-1: An einer Sackbohrung blieb unter ihrem Boden alles stehen.

    Platte 20 mm, Sackbohrung 6 mm tief von oben, die Mutternfalle M3 an ihr.
    Ø 6 (weiter als das Durchgangsloch Ø 3,4): Der Ring lag knapp unter der
    Tasche in der Luft der Bohrung, gebohrt wurde nichts, erklärt z = 14 bis 20,
    Sackloch. Ø 2,5 (enger): gebohrt richtig, erklärt aber nur z = 0 bis 14,
    weil die Kürzung auf der Achse in der alten Bohrung Luft sah. Soll: In
    beiden Fällen z = 0 bis 20, als Durchgang, ohne Material in der Achse.
    """
    from tests.helpers import run_operation

    drilled, hole = _drilled_plate(kind, 20.0, diameter, depth=6.0)
    profile = profiles.make_profile("centauri-carbon-2", "petg")
    result = run_operation("insert_nut_trap", drilled, profile, at_feature=hole, size="M3")
    carrier = result.outputs[0]
    bore = carrier.features["nut_trap_bore_1"]
    ends, _axis = _bore_ends(bore)
    assert sorted(float(end[2]) for end in ends) == pytest.approx([0.0, 20.0], abs=0.05)
    assert bore.params["through"] is True
    assert not any(_material_on_the_axis(carrier, [1.0, 6.0, 10.0, 13.0]))


@pytest.mark.parametrize("kind", ["mesh", "brep"])
def test_a_nut_trap_on_two_touching_plates_bores_through_both(kind: str) -> None:
    """Nachprüfung G, N-2: An zwei sich berührenden Platten endete das Schraubenloch dazwischen.

    Zwei Platten 40 × 40 × 6 in einem Objekt, die sich bei z = 6 berühren — wie
    eine eingelesene Baugruppe. Vor RM-631 bohrte der feste Stummel durch beide;
    danach endete die Bohrung an der Berührfläche, die untere Platte blieb zu.
    Eine Berührung ist kein Spalt. Soll: z = 0 bis 12, durch beide.
    """
    result = _rm631_insert(kind, "touching", "nut_trap", 12.0, size="M3", slide=0.0)
    carrier = result.outputs[0]
    bore = carrier.features["nut_trap_bore_1"]
    ends, _axis = _bore_ends(bore)
    assert sorted(float(end[2]) for end in ends) == pytest.approx([0.0, 12.0], abs=0.05)
    assert bore.params["through"] is True
    assert not any(_material_on_the_axis(carrier, [1.0, 3.0, 5.5, 7.0, 9.0]))


@pytest.mark.parametrize("kind", ["mesh", "brep"])
def test_a_nut_trap_at_the_edge_says_that_its_screw_hole_is_missing(kind: str) -> None:
    """Nachprüfung G, N-6: Am Rand fiel das Schraubenloch weg, gesagt wurde nur die Kante.

    Bei x = 18,8 ragt das Schraubenloch 0,5 mm aus der Seitenwand des 40-mm-
    Quaders. Die Verlängerung unterbleibt — sie zöge eine Rinne —, und der
    Kunde las nur „über den Rand“. Soll: ein eigener Befund mit Weg.
    """
    result = _rm631_insert(kind, "block12", "nut_trap", 12.0, size="M3", slide=0.0, x=18.8)
    said = [finding for finding in result.findings if finding.code == "parts.through_cut_short"]
    assert len(said) == 1
    assert [action.id for action in said[0].suggestions] == ["correct_input"]
    inside = _rm631_insert(kind, "block12", "nut_trap", 12.0, size="M3", slide=0.0, x=18.0)
    assert not [f for f in inside.findings if f.code == "parts.through_cut_short"]


@pytest.mark.parametrize("kind", ["mesh", "brep"])
@pytest.mark.parametrize("slide", [0.0, 2.0])
def test_a_nut_trap_laid_in_from_below_needs_a_slide_past_its_corners(
    kind: str, slide: float
) -> None:
    """Nachprüfung G, N-5: Mit kurzem Einschubweg ragte die Tasche über die Fläche.

    Von unten eingelegt liegt die Mitte der Tasche so tief wie der Einschubweg;
    die Ecken reichen die halbe Eckweite (bei M3 3,3 mm) darüber. Bei 0 lag die
    Schraube in der Fläche, bei 2 ragte die Tasche 1,3 mm heraus, ohne Befund.
    Soll: eine Absage am Feld *Einschubweg*; bei 4 mm rechnet es.
    """
    from app.core.errors import ValidationError

    with pytest.raises(ValidationError) as refusal:
        _rm631_insert(kind, "block40", "nut_trap", 40.0, size="M3", slide=slide, direction="bottom")
    assert refusal.value.field == "slide"
    assert refusal.value.constraint == "feasible"
    assert refusal.value.suggestions
    made = _rm631_insert(
        kind, "block40", "nut_trap", 40.0, size="M3", slide=4.0, direction="bottom"
    )
    assert as_mesh_data(made.outputs[0].mesh).bounds.maximum[2] == pytest.approx(40.0, abs=0.02)


def test_head_room_cuts_below_the_mouth_not_above_it(profile: Profile) -> None:
    """Die Kopffreiheit trägt Material ab, und zwar unter der Fläche (§24.1).

    ``head_room`` baute seinen Zylinder bei z = 0 nach +Z — über die Mündung,
    in die Luft über der Fläche. Der Baustein ist abtragend und liegt unter
    seiner Mündung; nach oben gebaut trug der Zylinder nichts ab, und der
    versenkte Kopf stand vor. Jetzt liegt die zylindrische Aussparung in
    Kopfbreite unter der Deckfläche, die Senkung um denselben Betrag tiefer.

    Gemessen wird auf halber Kopffreiheit (1,5 mm unter der Fläche), wo der
    alte Stand nichts abtrug: dort steht jetzt der Kopfdurchmesser, und die
    Gegenprobe ohne Kopffreiheit zeigt an derselben Stelle nur die schmale
    Senkung.
    """

    def bore_at(head_room: float, height: float) -> float:
        project = new_project("centauri-carbon-2", "petg")
        History(project.document).apply("Quader", [OperationDraft(op="create_box", params={})])
        History(project.document).apply(
            "Loch",
            [
                OperationDraft(
                    op="insert_screw_hole",
                    inputs=("obj_1",),
                    params={
                        "at_feature": "face_top",
                        "size": "M4",
                        "depth": 10.0,
                        "countersink": True,
                        "head_room": head_room,
                    },
                )
            ],
        )
        result = evaluate(project.document, profile, sources=ProjectSources(project))
        assert result.complete, [str(f.message) for f in result.scene.report.findings]
        mesh = result.scene.objects["obj_1"].mesh
        assert mesh.bounds.maximum[2] == pytest.approx(10.0, abs=0.02), (
            "die Kopffreiheit steht über der Fläche vor statt sie zu versenken"
        )
        return _widest_bore(mesh, height)

    countersink = float(standards.screw("M4").countersink)
    with_room = bore_at(3.0, 8.5)
    without_room = bore_at(0.0, 8.5)
    assert with_room >= countersink - 0.1, (
        f"die Kopffreiheit misst {with_room:.2f} mm, der Kopf braucht {countersink:.2f} mm"
    )
    assert without_room < with_room - 1.0, (
        f"ohne Kopffreiheit ist das Loch dort {without_room:.2f} mm — die Aussparung "
        "trägt nichts Neues ab"
    )


def test_a_round_screw_head_gets_its_own_diameter() -> None:
    """„Senkung aus“ meint einen Zylinderkopf, nicht einen breiten Senkkopf."""
    spec = PARTS.get("screw_hole")
    built = spec.fn(
        spec.params(
            size="M4",
            depth=10.0,
            countersink=False,
            head_room=3.0,
        )
    )

    diameter = built.mesh.bounds.size[0]
    screw = standards.screw("M4")
    assert diameter == pytest.approx(screw.head, abs=0.1)
    assert diameter < screw.countersink - 0.5, "die runde Aussparung nimmt das Senkkopfmaß"


def test_the_screw_head_choice_only_promises_the_supported_round_head() -> None:
    """Der Dialog darf einen Linsenkopf nicht mit dem Zylinderkopfmaß gleichsetzen."""
    countersink = next(
        entry for entry in PARTS.get("screw_hole").params.spec() if entry.name == "countersink"
    )

    assert "Zylinderkopf" in str(countersink.doc)
    assert "Linsenkopf" not in str(countersink.doc)


def test_a_screw_hole_can_recess_its_standard_washer() -> None:
    """Die Tabellenmaße der Scheibe müssen als passende Tasche nutzbar sein."""
    spec = PARTS.get("screw_hole")
    washer = standards.washer("M4")
    built = spec.fn(
        spec.params(
            size="M4",
            depth=10.0,
            countersink=False,
            head_room=0.0,
            washer=True,
            play=0.2,
        )
    )

    recess = built.features["washer_1"]
    assert recess.params["diameter"] == pytest.approx(washer.outer + 0.2)
    assert recess.params["depth"] == pytest.approx(washer.thickness)
    assert built.mesh.bounds.size[0] == pytest.approx(washer.outer + 0.2, abs=0.02)


def test_a_recessed_washer_follows_the_screw_head_depth() -> None:
    """Kopftiefe senkt die Scheibenauflage mit ab, statt unter ihr leer zu enden."""
    spec = PARTS.get("screw_hole")
    washer = standards.washer("M4")
    head_depth = 3.0
    built = spec.fn(
        spec.params(
            size="M4",
            depth=10.0,
            countersink=False,
            head_room=head_depth,
            washer=True,
            play=0.2,
        )
    )

    recess = built.features["washer_1"]
    assert recess.params["centre"][2] == pytest.approx(-head_depth - washer.thickness / 2.0)
    assert recess.params["depth"] == pytest.approx(washer.thickness)


def test_a_recessed_washer_remains_reachable_from_the_surface() -> None:
    """Die Scheibe darf nicht hinter einer engeren Kopftasche eingeschlossen sein."""
    spec = PARTS.get("screw_hole")
    washer = standards.washer("M4")
    head_depth = 3.0
    play = 0.2
    built = spec.fn(
        spec.params(
            size="M4",
            depth=10.0,
            countersink=False,
            head_room=head_depth,
            washer=True,
            play=play,
        )
    )

    # In der Mitte der Kopftiefe muss die ganze Scheibe hindurchpassen. Eine
    # nur kopfbreite Öffnung über einer größeren Scheibentasche wäre ein
    # unsichtbarer Hinterschnitt: druckbar, aber nicht montierbar.
    access = _section_diameter(built.mesh, -head_depth / 2.0)
    assert access == pytest.approx(washer.outer + play, abs=0.02)


def test_the_deepest_small_screw_hole_stays_clean_with_all_hidden_choices() -> None:
    """Auch eine ausgeblendete Scheibenwahl darf den Senkkopf nicht beschädigen."""
    spec = PARTS.get("screw_hole")
    built = spec.fn(
        spec.params(
            size="M2.5",
            depth=200.0,
            countersink=True,
            washer=True,
            play=0.25,
            head_room=50.0,
        )
    )

    assert built.mesh.is_watertight and built.mesh.component_count == 1
    assert not has_self_intersections(built.mesh)
    assert "bore_1" in built.features and "countersink_1" in built.features
    assert "washer_1" not in built.features


def test_short_and_regular_heatset_inserts_cut_their_named_depth() -> None:
    """Im Feld wählt man die gekaufte Länge; dieselbe muss im Modell ankommen."""
    spec = PARTS.get("heatset_m4")
    regular = spec.fn(spec.params(size="M4", extra_depth=0.0))
    short = spec.fn(spec.params(size="M4S", extra_depth=0.0))

    assert regular.mesh.bounds.size[2] == pytest.approx(8.1, abs=0.02)
    assert short.mesh.bounds.size[2] == pytest.approx(4.0, abs=0.02)


def test_a_bearing_seat_uses_the_bearing_and_material_fit() -> None:
    """Außenmaß und Breite kommen aus der Tabelle, die Passung aus dem Profil."""
    spec = PARTS.get("bearing_seat")
    bearing = standards.bearing("608")
    removable = spec.fn(
        spec.params(size="608", removable=True, play=0.25, grip=0.05, extra_depth=0.0)
    )
    pressed = spec.fn(
        spec.params(size="608", removable=False, play=0.25, grip=0.05, extra_depth=0.0)
    )

    assert removable.mesh.bounds.size[0] == pytest.approx(bearing.outer + 0.25, abs=0.02)
    assert pressed.mesh.bounds.size[0] == pytest.approx(bearing.outer - 0.05, abs=0.02)
    assert removable.mesh.bounds.size[2] == pytest.approx(bearing.width, abs=0.02)
    seat = removable.features["seat_1"]
    assert seat.params["diameter"] == pytest.approx(bearing.outer + 0.25)
    assert seat.params["depth"] == pytest.approx(bearing.width)


def test_a_bearing_seat_only_offers_the_fit_value_that_has_an_effect() -> None:
    """Niemand soll einen sichtbaren Passungswert eintragen, den der Sitz ignoriert."""
    fields = {entry.name: entry for entry in PARTS.get("bearing_seat").params.spec()}

    assert fields["play"].depends_on == ("removable", (True,))
    assert fields["grip"].depends_on == ("removable", (False,))


def test_a_custom_magnet_size_reaches_the_pocket() -> None:
    """Ein gemessener Magnet darf benutzt werden, ohne eine Normbezeichnung zu kennen."""
    spec = PARTS.get("magnet_pocket")
    built = spec.fn(
        spec.params(
            size="6x3",
            diameter=9.0,
            height=4.0,
            play=0.2,
            press_lip=False,
            cover=0.0,
        )
    )

    pocket = built.features["pocket_1"]
    assert pocket.params["diameter"] == pytest.approx(9.2)
    assert pocket.params["depth"] == pytest.approx(4.0)
    assert built.mesh.bounds.size[2] == pytest.approx(4.0, abs=0.02)


def test_a_shallow_custom_magnet_keeps_its_depth_with_a_lip() -> None:
    """Eine Haltelippe darf aus einer flachen Sondergröße keine tiefere Tasche machen."""
    spec = PARTS.get("magnet_pocket")
    built = spec.fn(
        spec.params(
            size="6x3",
            diameter=6.0,
            height=0.2,
            play=0.0,
            press_lip=True,
            grip=0.1,
            cover=0.0,
        )
    )

    assert built.features["pocket_1"].params["depth"] == pytest.approx(0.2)
    assert built.mesh.bounds.size[2] == pytest.approx(0.2, abs=0.02)


def test_a_custom_magnet_too_narrow_for_its_lip_gets_a_clear_error() -> None:
    """Ein unmögliches Übermaß darf keine negative Öffnung an die Geometrie reichen."""
    from app.core.errors import ValidationError

    spec = PARTS.get("magnet_pocket")
    with pytest.raises(ValidationError) as caught:
        spec.fn(
            spec.params(
                size="6x3",
                diameter=0.1,
                height=1.0,
                press_lip=True,
                grip=0.1,
                cover=0.0,
            )
        )

    assert caught.value.field == "diameter"
    assert caught.value.suggestions, "Regel 17: die Korrektur braucht eine Handlung"


def test_a_custom_cable_diameter_reaches_gland_and_clip() -> None:
    """Ein gemessenes Kabelmaß gilt in beiden Kabelbausteinen gleich."""
    gland = PARTS.get("cable_gland")
    gland_built = gland.fn(
        gland.params(
            size="cable-5",
            diameter=9.0,
            play=0.2,
            strain_relief=False,
        )
    )
    assert gland_built.features["bore_1"].params["diameter"] == pytest.approx(9.2)

    clip = PARTS.get("cable_clip")
    clip_values = clip.params(size="cable-5", diameter=9.0, play=0.2, width=8.0)
    clip_built = clip.fn(clip_values)
    assert clip_built.features["seat_1"].params["area"] == pytest.approx(9.2 * 8.0)


def test_every_play_field_defaults_to_the_profile() -> None:
    """Regel 7: `_part_values` füllt das Spiel nur bei **null** aus dem
    Materialprofil — jede andere Vorgabe ist eine feste Zahl, die die
    Kalibrierung (§28.3) nie erreicht. `nut_trap` (0,2) und `printed_thread`
    (0,15) waren genau das: ein TPU-Projekt baute die Mutternfalle mit
    PLA-Spiel."""
    from app.core.knowledge.parts import PARTS

    checked = 0
    for spec in PARTS.all():
        play = next((entry for entry in spec.params.fields() if entry.name == "play"), None)
        if play is None:
            continue
        checked += 1
        assert play.default == 0.0, (
            f"{spec.name}: Vorgabe {play.default} statt Verweis ins Materialprofil"
        )
    assert checked >= 8, "die Prüfung muss die Bausteine mit Spiel wirklich sehen"


@pytest.mark.parametrize("size", list(standards.profile_sizes()))
@pytest.mark.parametrize("play", [0.0, 0.15, 0.3, 1.0])
def test_the_tongue_leaves_air_in_the_slot_it_is_made_for(size: str, play: float) -> None:
    """Eine Passung wird an der **Differenz** gemessen, nicht daran, dass beide
    Hälften für sich stimmen.

    Geprüft wird gegen die Nut, wie die Tabelle sie beschreibt: in der Breite
    gegen den Kerndurchmesser, in der Tiefe gegen Steg plus Kammer. In beiden
    Richtungen muss genau das Spiel übrig bleiben.

    Die Tiefe ist der Fall, an dem es schiefging: Der Hals rechnete
    ``lip + play`` und der Kopf ``depth - play``, und damit kürzte sich das
    Spiel weg — die Feder war exakt so hoch wie die Nut tief und stieß mit null
    Luft auf dem Nutgrund auf. Ein gedruckter Kopf klemmt so, bevor er am Steg
    trägt, und gerade das soll er.
    """
    from app.core.knowledge.parts import PARTS

    spec = PARTS.get("profile_tongue")
    entry = standards.profile_slot(size)

    body = spec.fn(spec.params(size=size, play=play, length=20.0)).mesh
    width, _, height = (float(value) for value in body.bounds.size)

    assert entry.core - width == pytest.approx(play, abs=1e-6), (
        f"{size}: Kopf {width:.2f} in einer Kammer von {entry.core:.2f} — "
        f"{entry.core - width:.2f} Luft statt {play:.2f}"
    )
    assert entry.lip + entry.depth - height == pytest.approx(play, abs=1e-6), (
        f"{size}: Feder {height:.2f} hoch in einer Nut von "
        f"{entry.lip + entry.depth:.2f} — {entry.lip + entry.depth - height:.2f} "
        f"Luft über dem Nutgrund statt {play:.2f}"
    )


@pytest.mark.parametrize("size", list(standards.profile_sizes()))
def test_the_tongue_reaches_behind_the_lip(size: str) -> None:
    """Der Kopf muss hinter dem Steg sitzen, sonst hält die Feder nichts.

    Gemessen am Querschnitt und nicht am Hüllquader: In Steghöhe darf die Feder
    nur den Hals breit sein, darunter den Kopf. Ein Riegel, der über die ganze
    Höhe Kopfbreite hat, hätte denselben Hüllquader und ließe sich nicht
    einschieben.
    """
    from app.core.knowledge.parts import PARTS

    spec = PARTS.get("profile_tongue")
    entry = standards.profile_slot(size)
    body = spec.fn(spec.params(size=size, play=0.15, length=20.0)).mesh

    # Ein dünner Schnitt mitten durch den Steg und einer mitten durch die Kammer
    plate = shapes.box(60.0, 60.0, 0.2)
    through_lip = boolean("intersection", [body, shapes.moved(plate, (0.0, 0.0, entry.lip / 2.0))])
    in_chamber = boolean(
        "intersection",
        [body, shapes.moved(plate, (0.0, 0.0, entry.lip + entry.depth / 2.0))],
    )

    neck = float(through_lip.mesh.bounds.size[0])
    head = float(in_chamber.mesh.bounds.size[0])

    assert neck == pytest.approx(entry.slot - 0.15, abs=0.01), (
        f"{size}: im Steg {neck:.2f} breit, die Öffnung ist {entry.slot:.2f}"
    )
    assert head > neck + 1.0, (
        f"{size}: der Kopf ({head:.2f}) ist nicht breiter als der Hals ({neck:.2f}) — "
        "die Feder greift nicht hinter den Steg"
    )


@pytest.mark.parametrize("kernel", ("mesh", "brep"))
@pytest.mark.parametrize("play", (0.1, 0.15, 0.25, 0.4, 1.0))
def test_manufacturer_tongues_fit_independently_measured_sections(kernel, play) -> None:
    """RM017: Die schrägen Kammerwände kommen aus Herstellerdaten, nicht der Bausteintabelle."""
    import json

    from tests.helpers import exact_kernel

    if kernel == "brep":
        exact_kernel()
    measurements = json.loads(
        (MESHES.parent / "profile_slot_motedis.json").read_text(encoding="utf-8")
    )
    spec = PARTS.get("profile_tongue")
    for sample in measurements["profiles"]:
        with shapes.building(kernel):
            built = spec.fn(spec.params(size=sample["size"], play=play))
        body = as_mesh_data(built.mesh)
        assert body.is_watertight
        assert body.component_count == 1
        assert body.bounds.maximum[2] == pytest.approx(
            sample["lip"] + sample["depth"] - play, abs=1e-6
        )
        for depth, width in sample["sections"]:
            section = body.raw.section(plane_origin=(0, 0, depth), plane_normal=(0, 0, 1))
            if section is not None:
                assert np.max(np.abs(section.vertices[:, 0])) < width / 2
        for feature in built.features.values():
            assert feature.params["centre"][2] == pytest.approx(sample["lip"] + play)


@pytest.mark.parametrize("size,volume", (("2020", 996.13), ("3030", 1540.0), ("4040", 1540.0)))
def test_legacy_tongue_geometry_keeps_its_dimensions(size: str, volume: float) -> None:
    """Die benannten Herstellerprofile verändern alte gespeicherte Größen nicht."""
    spec = PARTS.get("profile_tongue")
    body = spec.fn(spec.params(size=size, play=0.25)).mesh
    # Die alten Werte werden vor dem Umbau am unveränderten Baustein gemessen.
    assert body.volume == pytest.approx(volume, abs=1e-6)


@pytest.mark.parametrize("size", ("motedis-2020-b6", "motedis-3030-b8"))
@pytest.mark.parametrize("kernel", ("mesh", "brep"))
def test_shorter_tongue_head_keeps_the_chamber_flanks(size, kernel) -> None:
    """Eine kürzere Kopfhöhe schneidet die geprüfte Form ab, ohne die Flanken zu verschieben."""
    from tests.helpers import exact_kernel

    if kernel == "brep":
        exact_kernel()
    spec = PARTS.get("profile_tongue")
    entry = standards.profile_slot(size)
    with shapes.building(kernel):
        full = spec.fn(spec.params(size=size, play=0.25)).mesh
        short = spec.fn(spec.params(size=size, play=0.25, head=1.0)).mesh
        cutting_box = shapes.box(50, 50, entry.lip + 0.25 + 1.0)
        from app.core.knowledge.parts.build import intersect

        expected = intersect(full, cutting_box)
    assert short.volume == pytest.approx(expected.volume, rel=1e-9)
    assert short.bounds.maximum[2] == pytest.approx(entry.lip + 1.25)


@pytest.mark.parametrize("size", ("motedis-2020-b6", "motedis-3030-b8"))
def test_tongue_rejects_a_head_that_would_hit_the_slot_floor(size: str) -> None:
    """Eine ausdrücklich zu große Kopfhöhe wird mit Rückweg erklärt, nicht gekappt."""
    from app.core.errors import ValidationError

    spec = PARTS.get("profile_tongue")
    values = spec.params(size=size, play=0.25, head=standards.profile_slot(size).depth)
    assert spec.feasible is not None and spec.feasible(values) is not None
    with pytest.raises(ValidationError) as raised:
        spec.fn(values)
    assert raised.value.field == "head"
    assert raised.value.suggestions


def test_the_tongue_takes_every_dimension_from_the_table() -> None:
    """§24.2, und die Regel dahinter: Normteilmaße stehen nie im Baustein.

    Gemessen, indem die Tabelle verstellt wird — vier Maße, vier Wirkungen.
    Eine Zahl, die der Baustein selbst mitbringt, fällt hier auf, weil sie sich
    nicht mitbewegt.
    """
    from app.core.knowledge.parts import PARTS

    spec = PARTS.get("profile_tongue")
    before = spec.fn(spec.params(size="2020", play=0.0, length=20.0)).mesh.bounds.size
    entry = standards.profile_slot("2020")
    wider = dataclasses.replace(entry, slot=entry.slot + 1.0, core=entry.core + 2.0)
    deeper = dataclasses.replace(entry, lip=entry.lip + 1.0, depth=entry.depth + 3.0)

    with mock.patch.object(standards, "profile_slot", return_value=wider):
        grown = spec.fn(spec.params(size="2020", play=0.0, length=20.0)).mesh.bounds.size
    with mock.patch.object(standards, "profile_slot", return_value=deeper):
        taller = spec.fn(spec.params(size="2020", play=0.0, length=20.0)).mesh.bounds.size

    assert float(grown[0]) - float(before[0]) == pytest.approx(2.0, abs=1e-6), "core wirkt nicht"
    assert float(taller[2]) - float(before[2]) == pytest.approx(4.0, abs=1e-6), (
        "lip oder depth wirkt nicht"
    )


def test_the_lead_in_narrows_the_ends_and_leaves_a_middle_that_bears() -> None:
    """Die Einführschräge nimmt Material an den Enden, nicht die ganze Feder.

    Gekappt auf ein Drittel der Länge, und das ist eine Entscheidung über die
    Konstruktion und nicht eine über die Robustheit: Ein Kopf ohne
    volle-Breite-Mitte greift kaum noch hinter den Steg. Gemessen wird deshalb
    am Querschnitt in der Mitte, nicht am Volumen — das fiele auch, wenn die
    Schräge die Mitte auffräße.
    """
    from app.core.knowledge.parts import PARTS

    spec = PARTS.get("profile_tongue")
    entry = standards.profile_slot("2020")

    straight = spec.fn(spec.params(size="2020", lead_in=0.0, length=20.0)).mesh
    tapered = spec.fn(spec.params(size="2020", lead_in=4.0, length=20.0)).mesh

    assert tapered.volume < straight.volume, "die Schräge nimmt nichts weg"
    assert tapered.bounds.size[1] == pytest.approx(20.0, abs=1e-6), "die Länge hat sich geändert"

    # Die kürzeste Feder mit der größten Schräge — dort greift die Kappung
    plate = shapes.box(60.0, 0.2, 60.0)
    extreme = spec.fn(spec.params(size="2020", lead_in=6.0, length=6.0, play=0.0)).mesh
    middle = boolean("intersection", [extreme, plate])

    assert float(middle.mesh.bounds.size[0]) == pytest.approx(entry.core, abs=0.01), (
        f"in der Mitte nur {float(middle.mesh.bounds.size[0]):.2f} statt {entry.core:.2f} breit — "
        "die Schräge hat den tragenden Teil aufgefressen"
    )


@pytest.mark.parametrize("length", [6.0, 6.6, 12.0])
def test_a_tapered_bar_holds_at_every_taper_not_just_at_the_corners(length: float) -> None:
    """Die entartete Fläche liegt **mitten** im Bereich, nicht an seinem Ende.

    Genau auf ``taper == length / 2`` fällt die Schulter auf null, und damit
    fallen an jedem Ende zwei Ecken des Umrisses aufeinander. Vor der Abfrage in
    ``shapes.tapered_bar`` kam dort ein Körper aus fünf Teilen heraus, der nicht
    wasserdicht war — bei Schräge 2, 4 und 6 derselben Länge ging es gut.

    Deshalb fährt dieser Test in Zehntelschritten und nicht über Ecken: Der
    Bereichstest aus §24.3 nimmt Minimum, Maximum und Vorgabe jedes Parameters,
    und diese Stelle ist keines der drei. Ein Eckenraster hätte sie nie
    gefunden, und gefunden hat sie erst die Gegenprobe.
    """
    for step in range(int(length * 10) + 1):
        taper = step / 10.0
        body = shapes.tapered_bar(10.6, 6.0, length, 4.3, taper)

        assert body.is_watertight, f"Länge {length}, Schräge {taper} ist nicht wasserdicht"
        assert body.component_count == 1, (
            f"Länge {length}, Schräge {taper} fällt in {body.component_count} Teile"
        )
        assert body.volume > 0.0, f"Länge {length}, Schräge {taper} hat kein Volumen"


def test_insert_profile_tongue_grows_a_tongue_on_a_real_body(profile: Profile) -> None:
    """Der Weg des Nutzers: nicht die Bausteinfunktion, sondern die Operation.

    Zwischen beiden liegt einiges — ``_part_values`` füllt das Spiel aus dem
    Materialprofil, ``_anchor`` setzt die Feder an ein Merkmal, und die
    Vereinigung mit dem Körper läuft über die Boolesche Rückfallkette. Ein
    Baustein, der für sich rechnet und im Fenster nichts tut, ist die Sorte
    Fehler, die drei Bausteine schon einmal hatten (§24.1, MOUTH_AT_ORIGIN).
    """
    project = project_with_plate()
    sources = ProjectSources(project)
    before = evaluate(project.document, profile, sources=sources).scene.objects["obj_1"]

    History(project.document).apply(
        "Nutfeder",
        [
            OperationDraft(
                op="insert_profile_tongue",
                inputs=("obj_1",),
                params={"size": "2020", "length": 20.0, "z": 4.0},
            )
        ],
    )
    result = evaluate(project.document, profile, sources=sources)
    after = result.scene.objects["obj_1"]

    assert result.complete, "die Auswertung hält an: " + " | ".join(
        f"{f.code}: {f.message}" for f in result.scene.report.findings
    )
    assert "boolean.without_effect" not in {f.code for f in result.scene.report.findings}, (
        "die Feder sitzt neben der Platte statt auf ihr"
    )
    assert after.mesh.volume > before.mesh.volume, "die Feder hat nichts angebaut"
    assert after.mesh.is_watertight, "der Körper ist danach nicht mehr geschlossen"

    grown = float(after.mesh.bounds.maximum[2] - before.mesh.bounds.maximum[2])
    entry = standards.profile_slot("2020")
    # Steg plus Kammer, abzüglich des Spiels aus dem Materialprofil — dieselbe
    # Rechnung wie im Baustein, hier aber über die Operation gemessen.
    expected = entry.lip + entry.depth - profile.material.clearance
    assert grown == pytest.approx(expected, abs=0.05), (
        f"die Feder steht {grown:.2f} mm über der Platte, erwartet {expected:.2f}"
    )


def test_a_part_can_carry_a_caveat() -> None:
    """Ein Baustein darf sagen, wann er die falsche Wahl ist (§25.4).

    **Bis zum 23.08.2026 konnte er das nicht**, und deshalb trug keiner der
    zwanzig einen ``caveat`` — nicht aus Nachlässigkeit, sondern weil
    ``register_part`` das Feld nicht kannte. Zwölf Operationen außerhalb der
    Bibliothek hatten längst einen; die Bausteine fielen durch eine Lücke in der
    Schnittstelle, und die sah man nur, wenn man einen setzen wollte.

    Geprüft wird die ganze Kette, nicht das Feld: ``register_part`` nimmt ihn,
    ``PartSpec`` hält ihn, und ``_register_one`` reicht ihn an die Operation
    weiter — dort liest ihn die Oberfläche. Ein Test auf ``PartSpec.caveat``
    allein wäre grün geblieben, während die Weitergabe fehlt.
    """
    from app.core.bootstrap import load_operations
    from app.core.knowledge.parts.ops import op_name
    from app.core.knowledge.parts.registry import PARTS
    from app.core.registry import REGISTRY

    load_operations()
    tragen = [spec for spec in PARTS.all() if spec.caveat]
    assert tragen, "kein Baustein trägt einen caveat — dann prüft dieser Test nichts"

    for spec in tragen:
        eintrag = REGISTRY.get(op_name(spec.name))
        assert str(eintrag.caveat) == str(spec.caveat), (
            f"{spec.name}: der caveat kommt am Register nicht an — "
            "_register_one reicht ihn nicht weiter"
        )


def test_parts_that_need_a_bore_are_offered_at_one() -> None:
    """Wer eine Bohrung anklickt, bekommt die drei angeboten, die hineingehören.

    Vor dem 23.08.2026 speiste nur ``subtractive`` das Kontextmenü, und zwar
    ausschließlich an Flächen: An einer Bohrung standen vier Einträge, das
    Gewinde stand nirgends. Der Unterschied zwischen „bringt sein Loch mit" und
    „braucht eines" war nicht ausgedrückt.
    """
    from app.core.bootstrap import load_operations

    load_operations()

    an_bohrung = {spec.name for spec in REGISTRY.for_feature("hole")}
    for name in ("printed_thread", "nut_trap", "heatset_m4"):
        spec = PARTS.get(name)
        assert spec.at_hole, f"{name} gehört in eine Bohrung und sagt es nicht"
        assert part_ops.op_name(name) in an_bohrung, (
            f"{name} ist als at_hole markiert, steht aber nicht im Kontextmenü "
            "einer Bohrung — _applies_to reicht es nicht weiter"
        )

    for spec in PARTS.all():
        if spec.at_hole:
            continue
        assert part_ops.op_name(spec.name) not in an_bohrung, (
            f"{spec.name} steht an einer Bohrung, ohne dafür gedacht zu sein: "
            "wirken ist nicht dasselbe wie sinnvoll sein"
        )


def test_every_group_has_a_title_and_every_title_a_tile() -> None:
    """Die Anschlussprüfung, die beim Umbau der Bohrungs-Bausteine fehlte.

    **Zwei Richtungen, und beide waren am 24.08.2026 ungeprüft.** Der Katalog
    zeichnet seine Kacheln nach ``spec.group`` und beschriftet die Abschnitte
    aus ``GROUPS``. Wer eine Gruppe verschiebt, muss beides anfassen — und
    keine Zusicherung hielt die zwei zusammen:

    * **Eine Gruppe ohne Titel** liest der Kunde als englischen Schlüssel.
      ``GROUPS.get(gruppe, gruppe)`` fällt auf den Schlüssel zurück, und dann
      steht „inserts" über den Kacheln statt „Einlegeteile" — eine feste
      Zeichenkette in der Oberfläche, die nie durch ``tr()`` gelaufen ist
      (Regel 20).
    * **Ein Titel ohne Kachel** ist ein leerer Abschnitt. Genau das entsteht,
      wenn ein Baustein die Gruppe wechselt und ihr Titel stehen bleibt — und
      es fällt nur auf, wenn jemand den Katalog aufmacht.

    Der Anlass: `heatset_m4` stand allein in `inserts`, und beim Auflösen
    dieser Gruppe wanderten Baustein **und** Titel — zwei Änderungen in zwei
    Dateien, deren Zusammenhang niemand geprüft hätte. Beim nächsten Mal prüft
    ihn dieser Test.

    Nicht geprüft wird, wie **viele** Kacheln eine Gruppe braucht: Ob eine
    Einzelgruppe zusammengelegt wird, ist eine Entscheidung über die Oberfläche
    und keine über die Konsistenz — sie gehört nicht in einen Test.
    """
    from app.core.knowledge.parts import GROUPS

    benutzt = {spec.group for spec in PARTS.all()}
    assert benutzt, "ohne Bausteine prüft dieser Test nichts"
    assert GROUPS, "und ohne Gruppentitel auch nicht"

    ohne_titel = sorted(benutzt - set(GROUPS))
    assert not ohne_titel, (
        f"Gruppen ohne Titel in GROUPS: {ohne_titel} — der Katalog zeigt dann den Schlüssel"
    )

    ohne_kachel = sorted(set(GROUPS) - benutzt)
    assert not ohne_kachel, (
        f"Gruppentitel ohne einen einzigen Baustein: {ohne_kachel} — ein leerer Abschnitt"
    )


# --- Die Lasche mit Loch (insert_lug, RM-398) ---------------------------------------


def _carrier_with(
    profile: Profile, carrier: OperationDraft, part: str, values: dict[str, Any]
) -> Any:
    """Ein Träger aus einem Grundkörper, daran ein Baustein — über Verlauf und Auswertung."""
    project = new_project("centauri-carbon-2", "petg")
    History(project.document).apply("Träger", [carrier])
    History(project.document).apply(
        part,
        [OperationDraft(op=part_ops.op_name(part), inputs=("obj_1",), params=values)],
    )
    result = evaluate(project.document, profile, sources=ProjectSources(project))
    assert result.complete, [str(finding.message) for finding in result.scene.report.findings]
    return result.scene.objects["obj_1"]


def _lug_hole(body: Any) -> Any:
    hole = next(f for name, f in body.features.items() if name.endswith("bore_1"))
    assert hole.kind == "hole"
    return hole


@pytest.mark.parametrize(
    ("case", "carrier", "values", "size", "check"),
    [
        # Schraubendreherhalter aus dem Nachbau: Wandlasche mit Ø 4,5, an der
        # Seitenwand bündig mit der Standfläche.
        pytest.param(
            "seitenwand",
            OperationDraft(op="create_box", params={"width": 40.0, "depth": 30.0, "height": 20.0}),
            {"x": -20.0, "y": 0.0, "z": 0.0, "nx": -1.0, "ny": 0.0, "nz": 0.0},
            "M4",
            "flat",
            id="schraubendreherhalter",
        ),
        # Kartuschendeckel aus dem Nachbau: radiale Lasche am runden Rand einer
        # Scheibe Ø 74,4 mal 2,4, so dick wie die Scheibe.
        pytest.param(
            "rand",
            OperationDraft(
                op="create_cylinder", params={"diameter": 74.4, "height": 2.4, "segments": 96}
            ),
            {"x": 37.2, "y": 0.0, "z": 0.0, "nx": 1.0, "ny": 0.0, "nz": 0.0, "thickness": 2.4},
            "M3",
            "flat",
            id="kartuschendeckel",
        ),
        # Öse auf der Oberseite, mit eingetragener Breite und Länge.
        pytest.param(
            "oben",
            OperationDraft(op="create_box", params={"width": 40.0, "depth": 30.0, "height": 20.0}),
            {"x": 0.0, "y": 0.0, "z": 20.0, "width": 16.0, "length": 20.0, "thickness": 5.0},
            "M5",
            "upright",
            id="oese",
        ),
    ],
)
def test_a_lug_carries_the_hole_of_its_screw_on_every_kind_of_face(
    profile: Profile,
    case: str,
    carrier: OperationDraft,
    values: dict[str, Any],
    size: str,
    check: str,
) -> None:
    """Abnahme RM-398 an drei Fällen: Seitenwand, runder Rand, Oberseite.

    Die Lasche wird mit ihrem Träger ein Körper, das Loch ist das
    Durchgangsloch der Normteiltabelle, und an einer senkrechten Fläche liegt
    sie flach mit senkrechtem Loch — die Unterseite im Ansatzpunkt, also bündig
    mit der Standfläche, wenn der Ansatzpunkt an der Unterkante sitzt.
    """
    body = _carrier_with(profile, carrier, "lug", {**values, "size": size})
    mesh = body.mesh
    assert mesh.is_watertight and mesh.component_count == 1, case
    hole = _lug_hole(body)
    screw = standards.screw(size)
    assert hole.params["diameter"] == pytest.approx(screw.clearance), case
    # Die Maße von außen: ohne Eintrag die Unterlegscheibe aus der Tabelle.
    washer = standards.washer(size).outer
    width = float(values.get("width", 0.0)) or washer
    length = float(values.get("length", 0.0)) or (width + washer) / 2.0
    axis = np.abs(np.asarray(hole.params["axis"], dtype=float))
    if check == "flat":
        # Senkrechtes Loch, Lasche von null bis zu ihrer Dicke über dem Bett.
        assert axis == pytest.approx((0.0, 0.0, 1.0), abs=1e-6), case
        assert float(hole.params["centre"][2]) == pytest.approx(
            float(values.get("thickness", 4.0)) / 2.0, abs=1e-6
        )
        outward = float(values["x"]) + float(values["nx"]) * length
        reach = float(mesh.bounds.minimum[0] if values["nx"] < 0 else mesh.bounds.maximum[0])
        assert reach == pytest.approx(outward, abs=0.05), case
        assert float(mesh.bounds.minimum[2]) == pytest.approx(0.0, abs=1e-6), case
    else:
        # Auf der Oberseite steht sie als Öse: Loch waagerecht, Scheitel oben.
        assert axis[2] == pytest.approx(0.0, abs=1e-6), case
        assert float(mesh.bounds.maximum[2]) == pytest.approx(20.0 + length, abs=0.05), case
        assert width == 16.0


def test_a_lug_follows_the_washer_of_its_screw_without_a_dimension() -> None:
    """Die Maßreihe statt eines Einzelmaßes: Ohne Breite und Länge folgt die Lasche
    der Unterlegscheibe (ISO 7089) jeder Größe von M3 bis M64 — so breit wie sie,
    so lang, dass sie neben der Fläche liegt, das Loch in der Mitte des runden Endes.
    """
    spec = PARTS.get("lug")
    sizes = next(entry for entry in spec.params.spec() if entry.name == "size").choices
    assert tuple(sizes) == tuple(
        size for size in standards.screw_sizes() if standards.screw(size).nominal >= 3.0
    )
    assert sizes[0] == "M3" and sizes[-1] == "M64"
    for size in sizes:
        washer = standards.washer(size).outer
        built = spec.fn(spec.params(size=size))
        bounds = built.mesh.bounds
        assert float(bounds.size[0]) == pytest.approx(washer, abs=1e-6), size
        assert float(bounds.maximum[2]) == pytest.approx(washer, abs=0.05), size
        assert built.features["bore_1"].params["centre"][2] == pytest.approx(washer / 2.0)
        assert built.features["bore_1"].params["diameter"] == standards.screw(size).clearance


@pytest.mark.parametrize(
    ("values", "field"),
    [
        ({"size": "M8", "width": 10.0}, "width"),
        ({"size": "M8", "width": 20.0, "length": 12.0}, "length"),
    ],
)
def test_a_lug_that_cannot_carry_its_screw_is_refused_with_advice(
    values: dict[str, Any], field: str
) -> None:
    """Schmaler als der Schraubenkopf oder so kurz, dass er an die Fläche stieße."""
    from app.core.errors import ValidationError

    spec = PARTS.get("lug")
    params = spec.params(**values)
    assert spec.feasible is not None and spec.feasible(params) is not None
    with pytest.raises(ValidationError) as caught:
        spec.fn(params)
    assert caught.value.field == field
    assert caught.value.constraint == "feasible"


# --- Die Rohrschelle (insert_pipe_clamp, create_pipe_clamp, RM-398) ---------------


def test_a_pipe_clamp_holds_the_klemmschelle_of_the_rebuild_on_a_side_wall(
    profile: Profile,
) -> None:
    """Abnahme RM-398, Fall 1: die Klemmschelle aus dem Nachbau, Ring Ø 16,9 innen.

    An eine senkrechte Wand gesetzt steht die Rohrachse senkrecht (``keeps_up``)
    — wie im Original, und so laufen die Schichten mit dem Ring, nicht quer.
    Das Spiel kommt aus dem Profil: 16,65 mm Rohr und PETG ergeben die 16,9.
    """
    values = {
        "x": -20.0,
        "y": 0.0,
        "z": 10.0,
        "nx": -1.0,
        "ny": 0.0,
        "nz": 0.0,
        "size": "15",
        "diameter": 16.65,
        "width": 30.0,
        "wall": 3.0,
        "screw_size": "M5",
    }
    carrier = OperationDraft(op="create_box", params={"width": 40.0, "depth": 30.0, "height": 20.0})
    body = _carrier_with(profile, carrier, "pipe_clamp", values)
    assert body.mesh.is_watertight and body.mesh.component_count == 1
    seat = next(f for name, f in body.features.items() if name.endswith("seat_1"))
    assert seat.params["diameter"] == pytest.approx(16.65 + profile.material.clearance)
    assert seat.params["diameter"] == pytest.approx(16.9)
    assert np.abs(np.asarray(seat.params["axis"], dtype=float)) == pytest.approx((0.0, 0.0, 1.0))
    bolt = next(f for name, f in body.features.items() if name.endswith("pipe_clamp_bore_1"))
    assert bolt.params["diameter"] == pytest.approx(standards.screw("M5").clearance)


def test_a_pipe_clamp_stands_alone_for_the_broom_handle_of_the_corpus(profile: Profile) -> None:
    """Abnahme RM-398, Fall 2: der Besenhalter Ø 35 aus ``F:\\3D Dateien`` als eigenes Teil.

    35 mm steht nicht in der Rohrreihe; der eigene Durchmesser trägt es. Die
    Schelle steht mit dem Fuß auf dem Bett, die Rohrachse waagerecht.
    """
    project = new_project("centauri-carbon-2", "petg")
    History(project.document).apply(
        "Schelle",
        [
            OperationDraft(
                op="create_pipe_clamp",
                params={"size": "32", "diameter": 35.0, "width": 20.0, "screw_size": "M4"},
            )
        ],
    )
    result = evaluate(project.document, profile, sources=ProjectSources(project))
    assert result.complete, [str(finding.message) for finding in result.scene.report.findings]
    clamp = result.scene.objects["obj_1"]
    assert clamp.mesh.is_watertight and clamp.mesh.component_count == 1
    assert float(clamp.mesh.bounds.minimum[2]) == pytest.approx(0.0, abs=1e-6)
    seat = next(f for name, f in clamp.features.items() if name.endswith("seat_1"))
    assert seat.params["diameter"] == pytest.approx(35.0 + profile.material.clearance)
    assert abs(float(seat.params["axis"][2])) == pytest.approx(0.0, abs=1e-6)


def test_a_pipe_clamp_for_a_copper_pipe_sits_on_a_top_face(profile: Profile) -> None:
    """Abnahme RM-398, Fall 3: Kupferrohr 22 aus der Rohrreihe auf einer Oberseite.

    Das Rohr läuft parallel zur Fläche, der Ring wird mit dem Träger ein
    Körper, und die Klemmschraube liegt über dem Ring, nicht im Rohr.
    """
    values = {"x": 0.0, "y": 0.0, "z": 20.0, "size": "22", "screw_size": "M4"}
    carrier = OperationDraft(op="create_box", params={"width": 40.0, "depth": 30.0, "height": 20.0})
    body = _carrier_with(profile, carrier, "pipe_clamp", values)
    assert body.mesh.is_watertight and body.mesh.component_count == 1
    seat = next(f for name, f in body.features.items() if name.endswith("seat_1"))
    bolt = next(f for name, f in body.features.items() if name.endswith("pipe_clamp_bore_1"))
    assert seat.params["diameter"] == pytest.approx(22.0 + profile.material.clearance)
    assert abs(float(seat.params["axis"][2])) == pytest.approx(0.0, abs=1e-6)
    pipe_top = float(seat.params["centre"][2]) + 11.0
    bolt_bottom = float(bolt.params["centre"][2]) - float(bolt.params["diameter"]) / 2.0
    assert bolt_bottom > pipe_top + 3.0, "zwischen Rohr und Schraube steht die Ringwand"


def test_a_pipe_clamp_leaves_a_gap_of_the_play_and_the_clamping_travel() -> None:
    """Der Spalt schließt das Spiel (π mal Spiel) und klemmt danach noch einen
    Millimeter — gemessen am Netz, in Höhe der Ohren, an zwei Spielen."""
    from app.core.slice.analysis import cross_section

    spec = PARTS.get("pipe_clamp")
    for play in (0.2, 0.35):
        params = spec.params(size="22", wall=3.0, width=15.0, screw_size="M4", play=play)
        mesh = spec.fn(params).mesh
        # Ein waagerechter Schnitt knapp unter der Oberkante trifft nur die
        # Ohren: zwei Rechtecke, zwischen ihnen der Spalt.
        top = float(mesh.bounds.maximum[2])
        section = cross_section(mesh, top - 0.5)
        assert section is not None
        ears = sorted(getattr(section, "geoms", [section]), key=lambda ear: ear.bounds[0])
        assert len(ears) == 2, f"play {play}: zwei Ohren, nicht {len(ears)}"
        gap = float(ears[1].bounds[0]) - float(ears[0].bounds[2])
        assert gap == pytest.approx(np.pi * play + 1.0, abs=1e-6), f"play {play}"


def test_a_pipe_clamp_narrower_than_its_washer_is_refused_with_advice() -> None:
    from app.core.errors import ValidationError

    spec = PARTS.get("pipe_clamp")
    params = spec.params(size="22", width=8.0, screw_size="M6", play=0.25)
    assert spec.feasible is not None and spec.feasible(params) is not None
    with pytest.raises(ValidationError) as caught:
        spec.fn(params)
    assert caught.value.field == "width"
    assert caught.value.constraint == "feasible"
    assert spec.fn(spec.params(size="22", width=12.0, screw_size="M6", play=0.25)).mesh.volume > 0


# --- Der Kabelclip (insert_cable_clip) ------------------------------------------


@pytest.mark.parametrize("size", ["cable-5", "cable-7", "ptfe-4x2", "ptfe-6x3"])
def test_the_clip_lets_the_cable_lie_but_not_drop_in(size: str) -> None:
    """Die Zusage des Clips ist ein Widerspruch, und beide Hälften sind messbar:
    Das Kabel **liegt im Bügel**, und es **kommt nicht senkrecht hinein**.

    Genau daran hängt, ob ein Clip hält. Ist die Öffnung so weit wie das Kabel,
    fällt es wieder heraus; ist der Innenraum zu eng, drückt der Bügel es platt.

    Gefragt wird über die Boolesche Operation, und **nichts ist die
    Antwort**: Eine leere Schnittmenge ist bei ``allow_empty`` ein Ergebnis
    der ersten Stufe und keine Ausnahme. Bis zum 21.09.2026 fragte der Test
    ohne den Schalter und ließ die Kette alle vier Stufen bis zur
    Voxelisierung durchlaufen, um „Es bleibt kein Körper übrig" zu hören —
    sieben Sekunden je Größe für eine Tatsache, die die erste Stufe in
    Millisekunden kennt.

    **Warum die Probe neunzig Prozent misst und nicht hundert.** Der Sitz ist
    so groß wie das Kabel, also berühren sich beide in einer Fläche — und
    darauf ist keine Boolesche Operation zu bauen (§39). Gemessen, wie weit die
    Zahl davon abhängt: Bei 98 % kamen für vier Größen 8,6 · 10,4 · 9,3 ·
    9,4 mm³ heraus, **absolut konstant statt proportional**, und die Kette
    meldete dabei „jittered". Das ist kein Eindringen, das ist das Werkzeug,
    das sich selbst misst. Bei neunzig Prozent ist die Antwort eindeutig, und
    die Zusage — der Sitz ist für das Kabel gebaut — prüft sie immer noch.
    """
    from app.core.geom.boolean import boolean
    from app.core.knowledge import standards
    from app.core.knowledge.parts import PARTS, shapes

    spec = PARTS.get("cable_clip")
    values = spec.params(size=size)
    built = spec.fn(values)
    entry = standards.tube(size)

    # Wo das Kabel liegt, sagt der Baustein selbst: ``seat_1`` ist die Auflage,
    # und das Kabel liegt mit seinem Radius darüber. Nicht aus der Formel des
    # Bausteins gerechnet — die prüft sich sonst selbst.
    axis = built.features["seat_1"].params["centre"][2] + entry.outer / 2.0

    def cable(height: float, share: float) -> MeshData:
        upright = shapes.cylinder(entry.outer * share, values.width * 4.0)
        centred = shapes.moved(upright, (0.0, 0.0, -values.width * 2.0))
        lying = shapes.turned(centred, 90.0, (1.0, 0.0, 0.0))
        return shapes.moved(lying, (0.0, 0.0, height))

    lying = boolean("intersection", [built.mesh, cable(axis, 0.90)], allow_empty=True)
    assert lying.mesh.triangle_count == 0, f"{size}: the seat presses into the cable"

    # Und der Weg von oben ist versperrt: ein Kabel, das über der Öffnung steht
    # und heruntergedrückt würde, trifft auf Material. Hier ist der Schnitt
    # groß und die Antwort eindeutig.
    blocked = boolean("intersection", [built.mesh, cable(axis + entry.outer, 1.0)]).mesh
    assert blocked.volume > 0.0, (
        f"{size}: the opening is as wide as the cable — nothing holds it in"
    )


def test_the_clip_keeps_its_grip_over_the_whole_range() -> None:
    """Gültige Öffnungen bleiben offen; unmögliche Verengungen sind **erklärt**.

    Eine Ablehnung innerhalb der Einzelgrenzen gibt es nur mit Erklärung am
    Vertrag (``PartSpec.feasible``): Der Bereichstest fährt diese Ecken als
    Ausschluss, und der Baustein wirft dort denselben Satz.
    """
    from app.core.errors import ValidationError
    from app.core.knowledge.parts import PARTS

    spec = PARTS.get("cable_clip")
    assert spec.feasible is not None
    for grip in (0.0, 0.2, 1.9):
        assert spec.feasible(spec.params(size="ptfe-4x2", grip=grip)) is None
        built = spec.fn(spec.params(size="ptfe-4x2", grip=grip))
        assert built.mesh.is_watertight
        assert built.mesh.component_count == 1
    for grip in (2.0, 2.5, 5.0):
        reason = spec.feasible(spec.params(size="ptfe-4x2", grip=grip))
        assert reason is not None, "die geschlossene Öffnung ist am Vertrag erklärt"
        with pytest.raises(ValidationError) as caught:
            spec.fn(spec.params(size="ptfe-4x2", grip=grip))
        assert caught.value.field == "grip"
        assert caught.value.suggestions
        assert str(reason) in str(caught.value.detail)


@pytest.mark.parametrize(
    ("name", "values", "field"),
    [
        ("overhang_fan", {"first": 80.0, "step": 30.0, "steps": 10}, "steps"),
        ("keyhole", {"size": "M8", "drop": 2.0, "play": 2.0}, "drop"),
        ("keyhole", {"size": "M4", "head_room": 20.0, "depth": 10.0}, "head_room"),
    ],
)
def test_declared_conditions_reject_exactly_where_they_say(
    name: str, values: dict[str, Any], field: str
) -> None:
    """Jede Ablehnung innerhalb der Grenzen hat ihre Erklärung am Vertrag — und umgekehrt."""
    from app.core.errors import ValidationError
    from app.core.knowledge.parts import PARTS

    spec = PARTS.get(name)
    assert spec.feasible is not None, f"{name} lehnt innerhalb der Grenzen ab, ohne es zu erklären"
    params = spec.params(**values)
    reason = spec.feasible(params)
    assert reason is not None
    with pytest.raises(ValidationError) as caught:
        spec.fn(params)
    assert caught.value.field == field
    assert str(reason) in str(caught.value.detail)
    # Die Vorgabe des Bausteins ist baubar und unerklärt.
    assert spec.feasible(spec.params()) is None


def test_the_range_check_counts_declared_exclusions_apart_from_failures(
    profile: Profile,
) -> None:
    """Ein erklärter Ausschluss ist kein Bruch; eine falsche Erklärung ist einer."""
    from app.core.errors import ValidationError
    from app.core.knowledge.parts import range_check
    from app.core.registry import op_params, param

    @op_params
    class PairParams(BaseParams):
        wide: float = param(title="wide", default=4.0, unit="mm", minimum=2.0, maximum=6.0)
        narrow: float = param(title="narrow", default=1.0, unit="mm", minimum=1.0, maximum=8.0)

    def declared(raw: BaseParams) -> str | None:
        return "zu eng" if raw.narrow >= raw.wide else None  # type: ignore[attr-defined]

    def honest(raw: BaseParams) -> Any:
        if declared(raw):
            raise ValidationError("narrow", "zu eng")
        from app.core.knowledge.parts import shapes

        return PartResult(mesh=shapes.box(raw.wide, raw.wide, raw.wide))  # type: ignore[attr-defined]

    report = range_check.check(PairParams, honest, profile, feasible=declared)
    assert report.checked == 4
    assert report.passed, [failure.reason for failure in report.failures]
    # Zwei Ecken sind erklärt: das enge Maß am Maximum gegen beide weiten.
    assert len(report.excluded) == 2
    assert all(entry.values["narrow"] == 8.0 for entry in report.excluded)

    def careless(raw: BaseParams) -> Any:
        from app.core.knowledge.parts import shapes

        return PartResult(mesh=shapes.box(raw.wide, raw.wide, raw.wide))  # type: ignore[attr-defined]

    report = range_check.check(PairParams, careless, profile, feasible=declared)
    assert not report.passed
    assert any("erklärt" in failure.reason for failure in report.failures)
    assert not report.excluded

    report = range_check.check(PairParams, honest, profile)
    assert not report.passed, "ohne Erklärung bleibt dieselbe Ablehnung ein Bruch"


@pytest.mark.parametrize(
    ("diameter", "play"),
    ((0.0, 0.25), (100.0, 2.0)),
    ids=("smallest-radius", "largest-radius"),
)
def test_the_cable_clip_keeps_its_declared_wall(diameter: float, play: float) -> None:
    """Facetten und Float32-Rundung dürfen die zugesagte Bügelwand nicht verkürzen."""
    from app.core.geom.mesh import as_mesh_data
    from app.core.units import EPS_GEOM

    spec = PARTS.get("cable_clip")
    values = spec.params(
        size="ptfe-4x2", diameter=diameter, width=2.0, wall=0.8, grip=0.0, play=play
    )
    measured = local_wall_thickness(as_mesh_data(spec.fn(values).mesh))

    assert int(spec.version) >= 13
    assert any(change.version == "13" for change in spec.changes) and spec.changes[-1].effect
    assert measured is not None
    assert measured >= values.wall - EPS_GEOM


def test_an_attachment_stands_in_the_face_menu_and_a_test_body_does_not() -> None:
    """``at_face`` wirkt bis ins Register — die Regression von sechs aus achtzehn.

    Am 24.08.2026 fehlten Wandhalter, Nutfeder, Rippe, Rastnase,
    Schnappverbindung und Filmscharnier in jedem Kontextmenü einer Fläche,
    weil die Fläche aus „trägt Material ab" geraten wurde. Der Fix (074e5d0)
    kam ohne Wache; wer die Ableitung anfasst, konnte die sechs wieder
    verlieren, ohne dass ein Lauf rot wird.

    Geprüft wird über das Register, nicht über die Menüs: ``applies_to`` ist
    die eine Quelle, aus der Kontextmenü und Palette lesen. Und die Gegenseite
    gehört dazu — ein Prüfkörper steht für sich, und an einer Fläche hätte er
    nichts verloren.
    """
    for spec in PARTS.all():
        expected = spec.at_face
        got = "face" in REGISTRY.get(part_ops.op_name(spec.name)).applies_to
        assert got == expected, (
            f"{spec.name}: at_face={expected}, aber das Register bietet die Fläche "
            f"{'nicht ' if expected else ''}an"
        )
    # Und die Erklärung ist keine leere Menge auf einer Seite: Es gibt beide.
    assert any(spec.at_face for spec in PARTS.all())
    assert any(not spec.at_face for spec in PARTS.all()), (
        "ohne einen Prüfkörper prüft die Gegenseite nichts"
    )


# --- Der Lochwand-Einhänger (insert_pegboard_hook) ------------------------------


@pytest.mark.parametrize("count", [1, 2, 4])
def test_the_hook_goes_through_the_slot_and_catches_behind_it(count: int) -> None:
    """Zwei Zusagen, und ein Einhänger, der eine davon bricht, hängt nicht.

    **Er muss hinein**: Zapfen und Nase zusammen sind der Weg durch den Schlitz,
    und der ist bei SKÅDIS fünfzehn Millimeter hoch und fünf breit. Passt der
    Haken nicht hindurch, liegt das Teil daneben statt zu hängen.

    **Und er muss hinter die Platte greifen**: Die Nase sitzt jenseits der
    Plattendicke, sonst rutscht das Teil beim ersten Anstoßen heraus.

    Gemessen wird an der Geometrie, die herauskommt, und an den benannten
    Merkmalen — **nicht an der Formel des Bausteins**. Dieser Docstring
    versprach das schon, während die Prüfung darunter
    ``slot_width + 2 * slot_width`` nachrechnete, also die Randformel der
    Rückplatte rückwärts. Als der Rand ein eigenes Maß bekam, wurde der Test
    rot, obwohl der Baustein besser geworden war — er hatte die Aktualität der
    Formel geprüft und nie ihre Richtigkeit.
    """
    from app.core.knowledge import standards
    from app.core.knowledge.parts import PARTS

    spec = PARTS.get("pegboard_hook")
    values = spec.params(count=count)
    built = spec.fn(values)
    board = standards.board(values.system)

    kanten = built.mesh.bounds
    tief = float(kanten.size[2])

    # Der Haken ragt hinter die Rückplatte, und zwar über die Plattendicke
    # hinaus — sonst greift die Nase ins Leere.
    assert tief > values.plate + board.thickness, (
        f"count={count}: the hook is {tief:.1f} mm deep, which does not reach past "
        f"the {board.thickness} mm board behind the {values.plate} mm plate"
    )

    # Und die Haken sitzen im Raster: zwischen zwei benachbarten liegt genau
    # eine Rasterweite, sonst passen sie in keine zwei Schlitze. Die Merkmale
    # sagen, wo sie stehen — die Rückplatte darum herum ist eine andere Frage.
    zapfen = sorted(
        f.params["centre"][0] for name, f in built.features.items() if name.startswith("hook_")
    )
    assert len(zapfen) == count, f"count={count}: {len(zapfen)} hooks named"
    for links, rechts in itertools.pairwise(zapfen):
        assert rechts - links == pytest.approx(board.pitch, abs=0.01), (
            f"count={count}: neighbouring hooks sit {rechts - links:.2f} mm apart, "
            f"the grid says {board.pitch}"
        )

    # **Eine bestellte Rückplatte trägt jeden Zapfen, mit Rand ringsum.** Ein
    # Zapfen an der Plattenkante hätte kein Material, das ihn hält.
    #
    # Ohne Platte gibt es nichts zu umschließen — seit dem 25.08.2026 ist sie
    # die Ausnahme statt die Vorgabe, und die Haken hängen dann an dem Teil, an
    # das sie kommen. Der Baustein misst dort genau so breit wie seine Zapfen,
    # und das ist richtig; geprüft wird der Zusammenhalt am Träger
    # (``test_a_part_held_by_its_host_becomes_one_with_it``).
    ordered = spec.fn(spec.params(count=count, plate=2.0)).mesh
    breit = float(ordered.bounds.size[0])
    assert breit > (zapfen[-1] - zapfen[0]) + board.slot_width, (
        f"count={count}: the plate is {breit:.1f} mm wide and does not reach around the outer hooks"
    )


def fits_the_slot(points: np.ndarray, board: Any, shift: float) -> bool:
    """Passt dieser Punkthaufen durch den Schlitz, wenn er um ``shift`` steigt?

    **Gegen die Öffnung, nicht gegen ihren Hüllquader.** Ein Schlitz hat runde
    Enden; ein Rechteck, das in 5 mal 15 passt, passt deshalb noch lange nicht
    in das Loch (der Docstring des Bausteins rechnet es vor). Geprüft wird
    darum gegen die Stadionform: innerhalb des geraden Stücks zählt nur die
    Breite, an den Enden der Abstand zum Mittelpunkt des Halbkreises.

    ``shift`` ist die Höhe, in der das Teil gerade hängt. Dass die Frage über
    **alle** Höhen gestellt werden muss, ist der Kern der Sache: Ein Einhänger
    ohne Rastzunge passt bei einer davon hindurch, und genau dort nimmt ihn
    jemand versehentlich ab.
    """
    radius = board.slot_width / 2.0
    straight = board.slot_height / 2.0 - radius
    x = points[:, 0]
    y = points[:, 1] + shift
    inside = (np.abs(x) <= radius + 1e-9) & (
        (np.abs(y) <= straight + 1e-9) | (x**2 + (np.abs(y) - straight) ** 2 <= radius**2 + 1e-9)
    )
    return bool(inside.all())


def slot_heights(points: np.ndarray, board: Any) -> list[float]:
    """Bei welchen Höhen der Punkthaufen durch den Schlitz ginge."""
    return [
        float(shift)
        for shift in np.arange(-board.slot_height, board.slot_height, 0.05)
        if fits_the_slot(points, board, float(shift))
    ]


def behind_the_board(built: Any, board: Any) -> np.ndarray:
    """Die Punkte jenseits der Plattenrückseite — was hinter der Wand liegt.

    Die Lochwand liegt zwischen der angeklickten Fläche und ihrer eigenen
    Dicke; eine bestellte Rückplatte steckt **im** Teil und damit unter null.
    Gezählt wird deshalb ab der Plattendicke und nicht ab der Rückplatte.
    """
    points = np.asarray(built.mesh.raw.vertices, dtype=float)
    return points[points[:, 2] > board.thickness + 0.05]


def through_the_board(built: Any, board: Any) -> np.ndarray:
    """Der Querschnitt im Brett — was durch den Schlitz muss.

    Als Schnitt und nicht über die Eckpunkte: Zapfen und Zunge sind Prismen
    durch das ganze Brett, die haben zwischen ihren Enden keine.
    """
    cut = built.mesh.raw.section(
        plane_origin=[0.0, 0.0, board.thickness / 2.0], plane_normal=[0.0, 0.0, 1.0]
    )
    assert cut is not None, "nothing goes through the board at all"
    return np.asarray(cut.vertices, dtype=float)


def spring_gap(mesh: Any, height: float) -> float:
    """Der größte freie Abstand in Y auf dieser Höhe — der Weg der Zunge.

    Am Schnitt gemessen und nicht an einer Formel: Wo Zunge und Zapfen zwei
    getrennte Umrisse sind, ist der größte Sprung zwischen zwei Umrisskanten
    genau der Spalt, in den die Zunge ausweichen kann.
    """
    cut = mesh.raw.section(plane_origin=[0.0, 0.0, height], plane_normal=[0.0, 0.0, 1.0])
    assert cut is not None, f"nothing to measure at z={height}"
    values = np.unique(np.round(np.asarray(cut.vertices, dtype=float)[:, 1], 4))
    return float(np.diff(values).max()) if len(values) > 1 else 0.0


def loose_at(mesh: Any, height: float) -> bool:
    """Ob die Zunge auf dieser Höhe frei ist — zwei Umrisse statt einem."""
    cut = mesh.raw.section(plane_origin=[0.0, 0.0, height], plane_normal=[0.0, 0.0, 1.0])
    return cut is not None and len(cut.discrete) > 1


def solid_fraction(mesh: Any, centre: Any, size: float = 0.4) -> float:
    """Wie viel eines kleinen Würfels um diesen Punkt im Material liegt.

    Ein Merkmal ist ein Anhaltspunkt an der Oberfläche. Liegt sein Mittelpunkt
    mitten im Körper, findet die Zuordnung dort nichts, worauf sie zeigen
    könnte — und keine Kennzahl merkt es. Ein halber Würfel heißt: auf einer
    Fläche. Ein ganzer heißt: im Material.
    """
    probe = shapes.moved(
        shapes.box(size, size, size),
        (float(centre[0]), float(centre[1]), float(centre[2]) - size / 2.0),
    )
    # ``allow_empty``, weil leer hier eine Antwort ist: Ein Würfel in der Luft
    # schneidet nichts, und genau danach wird für die Richtung gefragt. Ohne
    # das Wort hält die Rückfallkette den leeren Schnitt für ihr eigenes
    # Versagen und wirft.
    schnitt = boolean("intersection", [mesh, probe], allow_empty=True).mesh
    return float(schnitt.volume / size**3)


def shoulder_step(built: Any, board: Any) -> float:
    """Um wie viel die Rastschulter über den Querschnitt im Brett hinaussteht.

    Das ist der Federweg, den die Zunge beim Einführen zurücklegen muss, und
    zugleich das Maß, mit dem sie hinter der Platte sperrt — gemessen am Netz
    und nicht an der Formel, die ihn ausrechnet.
    """
    return float(
        through_the_board(built, board)[:, 1].min() - behind_the_board(built, board)[:, 1].min()
    )


def test_the_hook_fits_the_slot_it_is_made_for() -> None:
    """Was durch den Schlitz muss, muss durch den Schlitz passen.

    Gemessen wird am gebauten Netz und gegen die Tabelle: Alle Punkte, die im
    Brett liegen, gehören zu dem Teil, das durch das Loch geht, und sie müssen
    bei irgendeiner Höhe hineinpassen. Tun sie es nicht, liegt das Teil daneben
    statt zu hängen.

    **Die Grenze verläuft seit der Rastzunge an der Plattenrückseite, nicht an
    der Rückplatte.** Vorher maß dieser Test alles jenseits der Rückplatte —
    also Zapfen, Nase und Zunge zusammen — gegen die Schlitzhöhe. Was hinter
    der Wand liegt, *soll* aber höher sein als der Schlitz: Genau das ist die
    Verriegelung. Durch das Loch geht nur, was im Loch steckt.

    **Ohne Boolesche Operation, und das ist kein Umweg.** Der erste Versuch
    stellte eine Platte mit Schlitz daneben und fragte nach der Schnittmenge.
    Sie ist nie leer: Die Rückplatte des Hakens liegt an der Lochwand an, und
    zwar flächig — das ist keine Klemmung, sondern der Zweck. Wer hier eine
    Boolesche Operation befragt, misst die Berührung und nicht die Passung.
    """
    spec = PARTS.get("pegboard_hook")
    values = spec.params(count=1, play=0.2)
    built = spec.fn(values)
    board = standards.board(values.system)

    im_schlitz = through_the_board(built, board)
    assert len(im_schlitz), "nothing reaches into the board at all"
    assert slot_heights(im_schlitz, board), (
        f"the hook is {np.ptp(im_schlitz[:, 0]):.2f} by {np.ptp(im_schlitz[:, 1]):.2f} mm and "
        f"goes into no {board.slot_width} by {board.slot_height} slot at any height"
    )

    # Und er soll den Schlitz auch ausnutzen: Ein Haken, der nur halb so hoch
    # ist wie das Loch, hält beim ersten Anstoßen nicht.
    hoch = float(im_schlitz[:, 1].max() - im_schlitz[:, 1].min())
    assert hoch > board.slot_height / 2.0, (
        f"the hook only uses {hoch:.2f} mm of the {board.slot_height} mm slot"
    )

    # **Und das Spiel ist wirklich abgezogen.** ``fits_the_slot`` fragt „passt
    # es hinein" — und das täte ein Zapfen in voller Schlitzbreite auch, auf
    # den Hundertstel genau. Ein Baustein, der ``play`` vergisst, käme damit
    # durch und klemmte beim Kunden in einer Wand, deren Schlitze nie exakt
    # fünf Millimeter breit sind. Also gegen die Zahl und nicht gegen die
    # Grenze.
    breit = float(np.ptp(im_schlitz[:, 0]))
    assert breit == pytest.approx(board.slot_width - values.play, abs=0.05), (
        f"the shank is {breit:.2f} mm wide in a {board.slot_width} mm slot — "
        f"with {values.play} mm play it should be {board.slot_width - values.play:.2f}"
    )


@pytest.mark.parametrize("latch", [True, False])
def test_the_latch_leaves_no_height_at_which_the_hook_comes_off(latch: bool) -> None:
    """Die Zusage der Rastzunge, in einem Satz: **es gibt keine solche Höhe.**

    Ein Einhänger löst sich, indem man ihn anhebt, bis die Nase frei ist, und
    dann herauszieht. Beides zusammen ist eine einzige Frage an die Geometrie:
    Gibt es eine Höhe, bei der alles hinter der Platte durch den Schlitz
    zurückpasst? Ohne Zunge gibt es sie — sonst ließe sich das Teil gar nicht
    erst einhängen. Mit Zunge darf es sie nicht geben, in **keiner** Höhe.

    Gemessen wird an der Richtung und nicht nur an der Berührung
    (``.claude/rules/bausteine.md``): Die Rastschulter muss am **oberen** Ende
    sitzen, dort, wo der Haken beim Anheben hinwandert. Eine gleich große
    Schulter am unteren Ende sperrte nichts — sie wanderte beim Anheben in den
    Schlitz hinein.
    """
    spec = PARTS.get("pegboard_hook")
    values = spec.params(count=1, latch=latch)
    built = spec.fn(values)
    board = standards.board(values.system)

    dahinter = behind_the_board(built, board)
    assert len(dahinter), "nothing reaches behind the board at all"
    passend = slot_heights(dahinter, board)

    if not latch:
        assert passend, (
            "without the latch the hook must come out again — otherwise it could "
            "never have gone in, and this test would prove nothing"
        )
        return

    assert not passend, (
        f"the latched hook slips back through the slot at {len(passend)} heights, "
        f"first at {passend[:1]}"
    )

    # Die Richtung: Die Sperre sitzt oben. Der höchste Punkt hinter der Platte
    # liegt über dem, was im Brett steckt — die Schulter steht also dorthin
    # hinaus, wo der Haken beim Anheben hinwill.
    im_schlitz = through_the_board(built, board)
    assert float(dahinter[:, 1].min()) < float(im_schlitz[:, 1].min()) - 0.3, (
        f"the shoulder sits at y={dahinter[:, 1].min():.2f} and the shank reaches to "
        f"{im_schlitz[:, 1].min():.2f} — it does not stand out at the top end"
    )
    # Und unten steht sie nicht über: Dort greift die Nase, und mehr braucht
    # es nicht.
    assert float(dahinter[:, 1].max()) == pytest.approx(
        float(spec.fn(spec.params(count=1, latch=False)).mesh.bounds.maximum[1]), abs=0.01
    ), "the latch changed the lower end of the hook, where the nose already holds"


def test_the_latched_hook_still_goes_into_the_slot() -> None:
    """Eine Verriegelung, die das Einhängen verhindert, ist keine.

    Der Querschnitt im Brett — Zapfen und Zunge nebeneinander — muss durch das
    Loch gehen, und zwar bei einer Höhe, bei der auch die Nase hindurchkommt.
    Die Zunge selbst federt dabei ein; **hier** wird gemessen, dass sie das
    ohne die Schulter überhaupt tun könnte: Was im Brett liegt, ist die
    eingefederte Gestalt.
    """
    spec = PARTS.get("pegboard_hook")
    for play in (0.0, 0.2, 1.5):
        values = spec.params(count=1, play=play)
        built = spec.fn(values)
        board = standards.board(values.system)
        im_schlitz = through_the_board(built, board)
        assert slot_heights(im_schlitz, board), (
            f"play={play}: shank and tongue together measure "
            f"{np.ptp(im_schlitz[:, 0]):.2f} by {np.ptp(im_schlitz[:, 1]):.2f} mm and fit "
            f"no {board.slot_width} by {board.slot_height} slot"
        )


def test_the_tongue_has_room_to_spring() -> None:
    """Eine Zunge ohne Spalt ist ein Vorsprung, kein Federarm.

    Sie muss um ihre Rastschulter ausweichen können, sonst kommt der Haken
    nicht durch den Schlitz. Gemessen am Schnitt durch den Arm: der freie
    Abstand zwischen Zunge und Zapfen gegen den Überstand der Schulter, den der
    Hüllquader verrät.
    """
    spec = PARTS.get("pegboard_hook")
    board = standards.board("skadis")

    for play, plate, lip in ((0.0, 0.0, 0.0), (1.5, 0.0, 6.0), (0.0, 10.0, 0.0)):
        values = spec.params(count=1, play=play, plate=plate, lip=lip)
        built = spec.fn(values)
        step = shoulder_step(built, board)
        gap = spring_gap(built.mesh, board.thickness / 2.0)
        assert gap >= step > 0.2, (
            f"play={play} plate={plate} lip={lip}: the shoulder stands {step:.2f} mm proud "
            f"and the tongue has {gap:.2f} mm to give way"
        )


def test_the_tongue_stays_under_the_strain_a_printed_arm_survives() -> None:
    """Der Federweg kommt aus dem Arm, in dem er entsteht — nachgerechnet.

    Für einen Rechteckquerschnitt ist die Randdehnung an der Wurzel
    ``ε = 3·t·δ/(2·L²)``. Alle drei Größen stehen am gebauten Körper: die
    Armstärke als Dicke der Zunge, der Federweg als Überstand der Schulter, die
    freie Länge als der Bereich, in dem Zunge und Zapfen zwei getrennte Umrisse
    sind. Was herauskommt, muss unter ``LATCH_STRAIN`` bleiben — sonst bricht
    der Arm beim ersten Einrasten, und der Baustein verspricht etwas, das er
    nicht hält.

    **Nicht mit der Formel des Bausteins gerechnet.** Die Erwartung kommt aus
    der Biegemechanik und die Messwerte aus dem Netz; wer den Sollwert aus dem
    Prüfling zöge, prüfte die Aktualität der Formel und nicht ihre Richtigkeit.
    """
    from app.core.knowledge.parts.mounting import LATCH_STRAIN

    spec = PARTS.get("pegboard_hook")
    board = standards.board("skadis")
    values = spec.params(count=1)
    built = spec.fn(values)

    step = shoulder_step(built, board)
    schulter = float(behind_the_board(built, board)[:, 2].min())
    hoehen = np.arange(0.05, schulter, 0.05)
    frei = [float(z) for z in hoehen if loose_at(built.mesh, float(z))]
    assert frei, "the tongue is fused to the shank over its whole length"
    length = schulter - frei[0]

    cut = built.mesh.raw.section(
        plane_origin=[0.0, 0.0, frei[len(frei) // 2]], plane_normal=[0.0, 0.0, 1.0]
    )
    umriss = min(cut.discrete, key=lambda ring: np.asarray(ring)[:, 1].min())
    thickness = float(np.ptp(np.asarray(umriss)[:, 1]))

    strain = 3.0 * thickness * step / (2.0 * length**2)
    assert strain <= LATCH_STRAIN, (
        f"the tongue is {thickness:.2f} mm thick, {length:.2f} mm long and has to give "
        f"way {step:.2f} mm — that is {strain * 100:.1f} % strain at the root"
    )
    # Und nicht beliebig weich: Ein Arm, der zehnmal so lang ist wie nötig,
    # federt nicht mehr zurück. Ein Zehntel der zulässigen Dehnung wäre einer.
    assert strain > LATCH_STRAIN / 10.0, (
        f"only {strain * 100:.2f} % strain — this arm is a flag, not a spring"
    )


@pytest.mark.parametrize("values", corners(PARTS.get("pegboard_hook")), ids=str)
def test_the_latched_hook_holds_over_the_whole_range(values: dict[str, Any]) -> None:
    """§24.3 für die Zunge: jede Ecke des Bereichs, Zunge eingeschaltet.

    Der Bereichstest der Datei fährt die Ecken zyklisch, und ein Schalter
    bekommt dabei abwechselnd beide Stellungen — die Ecke mit dem größten Spiel
    und der tiefsten Nase liefe also ohne Zunge. Hier wird sie eingeschaltet
    erzwungen: Was an den Rändern bricht, bricht nicht in der Mitte.
    """
    spec = PARTS.get("pegboard_hook")
    board = standards.board("skadis")
    werte = spec.params(**{**values, "latch": True})
    built = spec.fn(werte)
    mesh = built.mesh

    assert mesh.is_watertight, f"{values} is not watertight"
    assert mesh.volume > 0.0, f"{values} has no volume"
    # Ein Haken je Zapfen, und die Zunge gehört zu ihrem: mehr Teile hieße,
    # sie hängt an nichts. Mit Rückplatte sind es keine zwei mehr — die Platte
    # verbindet, wozu sonst der Träger da ist.
    erwartet = 1 if werte.plate > 0.0 else werte.count
    assert mesh.component_count == erwartet, (
        f"{values} falls into {mesh.component_count} pieces, expected {erwartet}"
    )
    assert sorted(built.features) == sorted(
        [f"hook_{i + 1}" for i in range(werte.count)]
        + [f"latch_{i + 1}" for i in range(werte.count)]
    ), f"{values} names {sorted(built.features)}"

    dahinter = behind_the_board(built, board)
    assert not slot_heights(dahinter, board), f"{values}: the latched hook slips back out"


def test_without_the_latch_the_hook_is_the_shape_it_was() -> None:
    """Abgeschaltet muss die alte Form herauskommen, aufs Zehntel.

    §24.4 lebt davon, dass ein alter Stand erreichbar bleibt: Wer die Meldung
    beim Öffnen liest und lieber weiterrechnet wie bisher, schaltet die Zunge
    ab. Die Maße stehen hier aus der Tabelle und der Aufteilung des Docstrings
    — halbe Schlitzhöhe Zapfen, ein Viertel Nase, ein Viertel Weg —, nicht aus
    dem Baustein.
    """
    spec = PARTS.get("pegboard_hook")
    board = standards.board("skadis")
    values = spec.params(count=1, latch=False)
    built = spec.fn(values)

    lip = board.thickness * (2.0 / 3.0)
    hoch = board.slot_height * 3.0 / 4.0
    size = built.mesh.bounds.size
    assert float(size[0]) == pytest.approx(board.slot_width, abs=0.01)
    # Die runden Enden eines Langlochs sind ein Vieleck; dessen äußerster Punkt
    # liegt ein Hundertstel innerhalb der Rundung.
    assert float(size[1]) == pytest.approx(hoch, abs=0.02)
    assert float(size[2]) == pytest.approx(board.thickness + lip, abs=0.02)
    assert sorted(built.features) == ["hook_1"], "a hook without a latch names no latch"


def test_the_hook_names_its_features_on_faces_that_exist() -> None:
    """Ein Merkmal mitten im Material ist kein Anhaltspunkt.

    ``hook_1`` lag auf der Höhe der Plattenrückseite und damit **im** Zapfen:
    gemessen zu 99 % innen, mit der Fläche eines Rechtecks, das der Haken gar
    nicht hat. Derselbe Fehler wie beim Plattenmerkmal, das aus demselben Grund
    verschwunden ist — und keine Kennzahl des Bereichstests bemerkt ihn.

    Gemessen wird mit einem kleinen Würfel um den Mittelpunkt: halb im
    Material heißt „auf einer Fläche", ganz im Material heißt „daneben
    gegriffen". Dazu die Richtung — einen halben Millimeter in Richtung der
    Normalen muss Luft sein.
    """
    spec = PARTS.get("pegboard_hook")
    built = spec.fn(spec.params(count=1))
    mesh = built.mesh

    for name, feature in built.features.items():
        centre = np.asarray(feature.params["centre"], dtype=float)
        normal = np.asarray(feature.params["normal"], dtype=float)
        anteil = solid_fraction(mesh, centre)
        assert 0.2 < anteil < 0.8, (
            f"{name} sits {anteil * 100:.0f} % inside the body — that is not a face"
        )
        draussen = solid_fraction(mesh, centre + 0.5 * normal, size=0.2)
        assert draussen < 0.2, f"{name} points into the material, not out of it"


def test_a_board_without_room_for_a_tongue_says_so() -> None:
    """Regel 21: wo es nicht geht, wird es gesagt — nicht halb gebaut.

    Die Tabelle führt heute eine einzige Lochwand, und in deren Schlitz ist
    reichlich Platz. Eine Zeile mehr ist eine Datenänderung, keine
    Codeänderung: Sie käme ohne Test durch und ergäbe eine Zunge, die keinen
    Federweg hat. Der Baustein hält dann an und nennt den Ausweg — die Zunge
    abzuschalten —, statt einen Vorsprung zu bauen, der sich nicht eindrücken
    lässt.
    """
    from app.core.errors import ValidationError

    spec = PARTS.get("pegboard_hook")
    eng = standards.Board(size="eng", slot_width=4.0, slot_height=6.0, pitch=20.0, thickness=3.0)

    with mock.patch.object(standards, "board", return_value=eng):
        with pytest.raises(ValidationError) as gefangen:
            spec.fn(spec.params(count=1))
        # Ohne Zunge geht dieselbe Lochwand durch — sonst wäre die Meldung ein
        # Rat ins Leere.
        assert spec.fn(spec.params(count=1, latch=False)).mesh.is_watertight

    assert gefangen.value.suggestions, "Regel 17: eine Ausnahme ohne Handlungsvorschlag"


def test_the_changed_parts_report_themselves_to_old_projects() -> None:
    """§24.4: wer die Maße ändert, sagt es den Projekten, die sie benutzt haben.

    Einhänger, Schlüsselloch und Wandhalterung haben seit Bibliotheksstand 6
    ihre Geometrie geändert. Ein altes Projekt muss alle drei genannt bekommen.
    """
    from app.core.knowledge.parts.registry import changed_since_library

    gemeldet = changed_since_library("6", ["pegboard_hook", "keyhole", "wall_mount"])
    assert set(gemeldet) == {"pegboard_hook", "keyhole", "wall_mount"}, gemeldet

    # **Und zwar jede der beiden Änderungen einzeln.** Gegen 6 gefragt genügt
    # dem Einhänger sein älterer Eintrag; die Zunge wäre dabei stumm geblieben,
    # und die Gegenprobe hat genau das gezeigt: Der Test blieb grün, als ihr
    # Eintrag entwertet wurde. Gefragt wird deshalb gegen den Stand unmittelbar
    # davor — dort spricht nur noch der jüngste Eintrag. Der Stand kommt aus der
    # Version des Einhängers selbst, nicht aus ``LIBRARY_VERSION``: sobald ein
    # späterer Baustein die Bibliothek weiterschiebt (die Kopffreiheit auf 9),
    # ist der Zungen-Eintrag nicht mehr der jüngste der Bibliothek, wohl aber
    # der des Einhängers.
    vorher = str(int(PARTS.get("pegboard_hook").version) - 1)
    assert changed_since_library(vorher, ["pegboard_hook"]) == ("pegboard_hook",), (
        f"a project computed at library {vorher} is never told the hook grew a latch"
    )


def test_additional_size_fields_do_not_claim_that_old_geometry_changed() -> None:
    """Neue optionale Eingaben sind kein Maßwechsel für bestehende Projekte.

    Gemessen an der Funktion, die das Öffnen einer Datei fragt: Zwischen den
    Sondermaßen (Version 12) und der Materialzuordnung (Version 15) meldet sie
    für Kabelverschraubung und Magnettasche nichts; die 15 meldet sie — das
    ist die eigene, ausdrückliche Maßänderung (``MATERIAL_OF_TARGET``).
    Danach ändert Version 16 ausdrücklich den Klemmaufbau der Kabeldurchführung.
    """
    from app.core.knowledge.parts.registry import MATERIAL_OF_TARGET, changed_since_library

    unchanged = ["cable_gland", "magnet_pocket"]
    assert changed_since_library("12", unchanged) == tuple(unchanged), (
        "die Materialzuordnung ist eine Maßänderung und wird gemeldet"
    )
    assert changed_since_library(MATERIAL_OF_TARGET.version, unchanged) == ("cable_gland",)
    assert changed_since_library("16", unchanged) == ()
    assert all(
        not any(11 < int(change.version) < 15 for change in PARTS.get(name).changes)
        for name in unchanged
    ), "zwischen 12 und 15 gibt es für diese beiden keinen Eintrag"
    assert changed_since_library("11", ["screw_hole"]) == ("screw_hole",)


@pytest.mark.parametrize("size", ["M3", "M4", "M6"])
def test_the_keyhole_head_falls_through_with_a_profile(size: str, profile: Profile) -> None:
    """Der Kopf soll hindurchfallen — auch mit unkalibriertem Material.

    **Er tat es nicht.** Version 6 schrieb ``params.play or HEAD_CLEARANCE``,
    und ``ops.insert`` füllt das Spiel bei *jedem* Profil aus dem Material ein,
    nicht erst bei einem kalibrierten. Damit ersetzte ein Spiel von 0,25 mm das
    Durchgangsmaß von 0,6: Ein M4-Kopf von 7,00 mm fand eine Öffnung von
    7,25 mm vor, und gedruckt geht er da nicht mehr durch.

    Gemessen wird auf dem Weg, den die Anwendung geht — mit den Werten, die
    ``insert_part`` dem Baustein reicht —, und nicht mit einer eigenen
    Nachbildung davon.
    """
    spec = PARTS.get("keyhole")
    werte = part_ops._part_values(spec, spec.params(size=size), profile)
    built = spec.fn(spec.params(**werte))
    screw = standards.screw(size)

    from app.core.knowledge.parts.mounting import HEAD_CLEARANCE

    weite = float(built.features["pocket_1"].params["diameter"])
    assert weite >= screw.head + HEAD_CLEARANCE, (
        f"{size}: the head is {screw.head} mm and the opening {weite} mm — printed it "
        "no longer goes through"
    )
    assert weite == pytest.approx(screw.head + HEAD_CLEARANCE + profile.material.clearance)


def test_a_part_may_declare_how_many_bodies_it_prints_as(profile: Profile) -> None:
    """Print-in-place: mehrere Körper, aber nur so viele wie erklärt (§24.3).

    Ein Scharnier, das schon beim Drucken beweglich ist, besteht aus zwei
    Teilen. Der Bereichstest verlangte `component_count == 1` — und die
    Einteiligkeit steht nicht im Bauplan: §24.3 nennt wasserdicht,
    Mindestwandstärke, keine Selbstdurchdringung, benannte Merkmale. Der Test
    hatte sie hinzugefügt, aus gutem Anlass (die Rastnase zerfiel, weil sie
    die Fläche nur berührte). Gemeint war „zerfällt nicht **versehentlich**".

    Entschieden am 25.08.2026 (Robert): Deklaration statt stiller Ausnahme.
    Der Unterschied ist der ganze Punkt — die Prüfung wird nicht schwächer,
    sondern genauer: Zwei statt zwei ist die Zusage, drei statt zwei fällt.
    """
    from types import SimpleNamespace

    import trimesh

    from app.core.geom.mesh import MeshData
    from app.core.knowledge.parts.range_check import check
    from app.core.registry import op_params, param
    from app.core.types import BaseParams

    @op_params
    class TwoPartParams(BaseParams):
        size: float = param(title="Maß", default=10.0, unit="mm", minimum=8.0, maximum=12.0)

    def two_bodies(values: BaseParams) -> Any:
        """Zwei getrennte Würfel — ein Gelenk im Kleinen."""
        left = trimesh.creation.box(extents=(4.0, 4.0, 4.0))
        right = trimesh.creation.box(extents=(4.0, 4.0, 4.0))
        right.apply_translation((10.0, 0.0, 0.0))
        return SimpleNamespace(mesh=MeshData.of(trimesh.util.concatenate([left, right])))

    declared = check(TwoPartParams, two_bodies, profile, bodies=2)
    assert declared.passed, [entry.reason for entry in declared.failures]

    # Die Gegenprobe, und sie ist der Punkt: Ohne Deklaration ist derselbe
    # Baustein ein Fehler — unerklärtes Zerfallen bleibt rot.
    undeclared = check(TwoPartParams, two_bodies, profile)
    assert not undeclared.passed
    assert "2 Teile statt 1" in undeclared.failures[0].reason


def test_a_printed_joint_needs_a_gap_the_printer_can_hold(profile: Profile) -> None:
    """Bei einem print-in-place-Teil ist der Spalt die ganze Sache.

    Zu eng verschweißt beim Drucken, und aus zwei Körpern wird einer — davon
    sähe der Bereichstest nichts, weil er die Geometrie **vor** dem Drucker
    prüft. Gemessen wird deshalb der engste Abstand zwischen den Teilen, gegen
    das kalibrierte Material und nie gegen eine Zahl im Code (Regel 7).

    Die Toleranz ist `EPS_DISPLAY` und nicht `EPS_GEOM`: eine Fertigungsfrage,
    kein Rechenvergleich. Ein facettierter Zylinder zeigt seine Sehne und nicht
    den Bogen, der gemessene Spalt fällt also um Bruchteile kleiner aus —
    0,2499 bei eingestellten 0,25. Mit dem Rechenepsilon meldete die Prüfung
    ein Scharnier, das genau richtig gebaut war.

    **Zwei Ecken je Frage, nicht zweiunddreißig.** Bis zum 21.09.2026 fuhr
    der erste Schritt den ganzen Bereich des Scharniers — fünf Maße, 32
    Ecken, jede mit Wandmessung, Selbstdurchdringung und Spaltmaß: 51 s, für
    eine Zusage, die an zwei Ecken genauso steht. Der volle Bereichslauf ist
    seit dem 03.09.2026 nicht mehr Teil des Tors (AGENTS.md, Checkliste
    Baustein, Punkt 5); hier zählt nur, dass der Profilwert eingesetzt wird
    und der Spalt danach hält — am dünnsten und am dicksten Bolzen.
    """
    from app.core.knowledge.parts import PARTS
    from app.core.knowledge.parts.range_check import check
    from app.core.registry import op_params, param
    from app.core.types import BaseParams

    hinge = PARTS.get("barrel_hinge")

    @op_params
    class AsDelivered(BaseParams):
        pin: float = param(title="Bolzen", default=4.0, unit="mm", minimum=3.0, maximum=5.0)
        play: float = param(title="Spiel", default=0.0, unit="mm", minimum=0.0, maximum=0.0)

    def built_as_delivered(values: Any) -> Any:
        """So, wie der Kunde es bekommt: `play` bleibt null, der Bereichstest
        setzt den Profilwert ein — wie `insert_part` es tut."""
        return hinge.fn(hinge.params(pin=values.pin, play=values.play))

    delivered = check(AsDelivered, built_as_delivered, profile, bodies=hinge.bodies)
    assert delivered.checked == 2, "der dünnste und der dickste Bolzen, sonst nichts"
    assert delivered.passed, [failure.reason for failure in delivered.failures]

    @op_params
    class TooTight(BaseParams):
        pin: float = param(title="Bolzen", default=4.0, unit="mm", minimum=3.0, maximum=5.0)

    def built_too_tight(values: BaseParams) -> Any:
        """Dasselbe Scharnier, aber mit einem Spiel, das nicht aus dem Profil kommt."""
        return hinge.fn(hinge.params(pin=values.pin, play=0.05))

    tight = check(TooTight, built_too_tight, profile, bodies=2)
    assert not tight.passed, "ein Spalt von 0,05 mm verschweißt beim Drucken"
    assert "0.05" in tight.failures[0].reason


@pytest.mark.parametrize(
    "values",
    [
        {"pin": 2.0, "width": 8.0, "reach": 4.0, "wall": 1.0, "play": 0.25},
        {"pin": 20.0, "width": 8.0, "reach": 4.0, "wall": 1.0, "play": 2.0},
        {"pin": 20.0, "width": 120.0, "reach": 4.0, "wall": 1.0, "play": 2.0},
    ],
    ids=("kleinste-wand", "kurz-und-weites-spiel", "breit-und-weites-spiel"),
)
def test_the_barrel_hinge_keeps_wall_bodies_and_gap_at_critical_boundaries(
    values: dict[str, float],
) -> None:
    """Die drei vormals brechenden §24.3-Grenzen als Geometrievertrag."""
    from app.core.geom.mesh import as_mesh_data
    from app.core.knowledge.parts.range_check import printable_gap
    from app.core.units import EPS_DISPLAY

    hinge = PARTS.get("barrel_hinge")
    mesh = as_mesh_data(hinge.fn(hinge.params(**values)).mesh)
    pieces = mesh.raw.split(only_watertight=False)
    measured_wall = local_wall_thickness(mesh)
    measured_gap = printable_gap(mesh)

    assert len(pieces) == hinge.bodies
    assert all(piece.is_watertight and piece.volume > 0.0 for piece in pieces)
    assert measured_wall is not None
    assert measured_wall >= values["wall"] - EPS_DISPLAY
    assert measured_gap is not None
    assert measured_gap >= values["play"] - EPS_DISPLAY


def test_the_three_geometry_fixes_are_reported_to_older_projects() -> None:
    """§24.4 führt alle drei maßändernden Bausteine auf Bibliotheksstand 13."""
    from app.core.knowledge.parts.registry import changed_since_library

    changed = ("barrel_hinge", "dowel", "foot")

    for name in changed:
        spec = PARTS.get(name)
        assert int(spec.version) >= 13, name
        assert any(change.version == "13" for change in spec.changes), name
        assert spec.changes[-1].effect, name
    assert changed_since({"barrel_hinge": "1"}) == ("barrel_hinge",)
    assert changed_since({"dowel": "4", "foot": "4"}) == ("dowel", "foot")
    assert changed_since_library("12", changed) == changed
    assert changed_since_library(LIBRARY_VERSION, changed) == ()


#: Was ein Messschieber an einer echten SKÅDIS-Platte hergibt.
#:
#: Erste Messung am 27.08.2026 (ein Kunde): Schlitzbreite 4,9 bis
#: 5,1 mm, Schlitzhöhe 14,9 bis 15,1 mm. Die **Nennmaße** der Tabelle sind
#: damit bestätigt — neu ist die Toleranz, die keine Zeichnung hergibt.
#:
#: Hier steht die **untere** Grenze, denn nur sie kann klemmen. Wer die Zahl
#: ändert, hat gemessen; wer sie ohne Messung ändert, verschiebt eine Zusage
#: ins Blaue.
NARROWEST_MEASURED_SLOT = 4.9
NARROWEST_MEASURED_SLOT_HEIGHT = 14.9


@pytest.mark.parametrize("material", ["pla", "petg", "abs", "tpu-95a"])
def test_the_hook_still_fits_the_narrowest_slot_that_was_measured(material: str) -> None:
    """Ein Teil, das in neun von zehn Platten passt, ist kaputt.

    Die Tabelle führt Nennmaße: 5,0 × 15,0. Eine echte Platte hält sie nicht
    auf den Hundertstel — gemessen wurden 4,9 bis 5,1 und 14,9 bis 15,1. Für
    den Einhänger zählt allein das **untere** Ende: Ein Zapfen, der genau
    5,0 misst, geht in einen 4,9er Schlitz nicht hinein.

    Getragen wird das vom Spiel aus dem Materialprofil (Regel 7), und dieser
    Test hält fest, dass es dafür reicht — in **jedem** Material, nicht nur in
    dem, mit dem gerade jemand gedruckt hat. Am knappsten wird es bei PLA, das
    das kleinste Spiel führt: dort bleiben 0,10 mm.

    Ohne diese Zusage wäre die Toleranz eine Notiz in einer Tabelle, die
    niemand nachrechnet — und die erste Platte, die 0,05 mm enger ausfällt,
    fiele beim Kunden auf statt hier.
    """
    from app.core.knowledge import standards
    from app.core.knowledge.parts import PARTS
    from app.core.knowledge.profiles import material_profiles

    board = standards.board("skadis")
    spiel = material_profiles()[material].clearance

    # Dieselbe Rechnung wie im Baustein; ``play`` kommt bei null aus dem
    # Profil (``parts/ops.py``, ``PLAY_FIELD``).
    zapfen = board.slot_width - spiel
    nutzbar = board.slot_height - spiel

    assert zapfen <= NARROWEST_MEASURED_SLOT, (
        f"{material}: Zapfen {zapfen:.2f} mm passt nicht in den engsten "
        f"gemessenen Schlitz ({NARROWEST_MEASURED_SLOT} mm)"
    )
    assert nutzbar <= NARROWEST_MEASURED_SLOT_HEIGHT, (
        f"{material}: {nutzbar:.2f} mm Weg passt nicht in die engste "
        f"gemessene Schlitzhöhe ({NARROWEST_MEASURED_SLOT_HEIGHT} mm)"
    )

    # Und die Gegenprobe zur Zusage selbst: Der Baustein baut wirklich mit
    # diesem Maß, statt dass hier eine Formel neben ihm herrechnet.
    #
    # **Ein einzelner Haken, und nur seine Breite.** Zwei Haken stehen im
    # Rasterabstand, ihr Hüllquader misst 44,75 mm — das ist 40 plus eine
    # Zapfenbreite und sagt nichts über die Passung. Und gemessen wird X:
    # In der Höhe ragt die federnde Rastzunge absichtlich über den Zapfen
    # hinaus, sie liegt *vor* der Platte. Was durch den Schlitz muss, prüft
    # der Test darüber (``goes_through_the_slot_and_catches_behind_it``).
    spec = PARTS.get("pegboard_hook")
    gebaut = spec.fn(spec.params(count=1, play=spiel))
    breite = gebaut.mesh.bounds.size[0]
    assert breite <= NARROWEST_MEASURED_SLOT + 1e-6, (
        f"{material}: gebauter Zapfen ist {breite:.2f} mm breit und passt nicht "
        f"in den engsten gemessenen Schlitz ({NARROWEST_MEASURED_SLOT} mm)"
    )


def _klappbox(achse: str) -> object:
    """Die Klappbox der Galerie, mit wählbarer Achse fürs Scharnier."""
    project = new_project("centauri-carbon-2", "petg")
    History(project.document).apply(
        "Box",
        [OperationDraft(op="create_box", params={"width": 90.0, "depth": 60.0, "height": 28.0})],
    )
    History(project.document).apply(
        "Aushöhlen",
        [
            OperationDraft(
                op="hollow_object",
                inputs=("obj_1",),
                params={"wall": 2.0, "open_top": True, "vents": 0},
            )
        ],
    )
    History(project.document).apply(
        "Scharnier",
        [
            OperationDraft(
                op="insert_living_hinge",
                inputs=("obj_1",),
                params={
                    "width": 90.0,
                    "leaf": 26.0,
                    "thickness": 2.0,
                    "film": 0.4,
                    "axis": achse,
                    "y": -30.0,
                    "z": 28.0,
                },
            )
        ],
    )
    return project


def test_a_hinge_standing_on_edge_says_that_it_will_break(profile: Profile) -> None:
    """**Der Fall, an dem die Klappbox aus der Galerie flog** (31.08.2026).

    Ihr Rezept setzt das Filmscharnier mit ``axis="x"``, weil das nach der
    Biegeachse klingt. ``axis`` ist aber die Richtung, in die der Baustein
    *zeigt*: Die Hülle der Box sprang damit von 28 mm Höhe auf 90 — das
    Scharnier stand hochkant, seine Schichten liefen längs der Biegung statt
    quer, und es bricht beim ersten Öffnen.

    Das steht seit jeher in seinem ``caveat``, und die Einsetz-Operation wusste
    nichts davon: kein Fehler, kein Befund, ein wasserdichter Körper. Genau der
    Fall für Regel 21 — dieselbe Familie wie der Einhänger, dessen Oben nirgends
    hinzeigte, nur schlimmer: Der hält nicht, dieses hier *bricht*, und zwar
    später beim Kunden.
    """
    project = _klappbox("x")
    result = evaluate(project.document, profile, sources=ProjectSources(project))

    assert result.complete, [str(f.message) for f in result.scene.report.findings]
    edge = [f for f in result.scene.report.findings if f.code == "parts.standing_on_edge"]
    assert edge, "das Scharnier steht hochkant und niemand sagt, dass es beim ersten Öffnen bricht"
    message = str(edge[0].message)
    assert "waagerecht" in message and "Achse" in message, (
        f"beide Wege nach vorn müssen im Satz stehen, Regel 17: {message}"
    )


def test_a_hinge_lying_flat_stays_silent(profile: Profile) -> None:
    """Die Gegenprobe: Was flach liegt, wird nicht angemeckert.

    Ein Befund, der auch im guten Fall erscheint, ist schlimmer als keiner —
    der Kunde lernt, ihn zu überlesen.
    """
    project = _klappbox("z")
    result = evaluate(project.document, profile, sources=ProjectSources(project))

    assert result.complete, [str(f.message) for f in result.scene.report.findings]
    edge = [f for f in result.scene.report.findings if f.code == "parts.standing_on_edge"]
    assert not edge, f"Fehlalarm bei flach liegendem Scharnier: {[str(f.message) for f in edge]}"


def test_only_a_part_whose_strength_depends_on_direction_is_checked(
    profile: Profile,
) -> None:
    """Dieselbe Achse an einem Baustein ohne ``lies_flat`` schweigt.

    Sonst prüfte die Operation nicht die Eigenschaft, sondern den Zufall: Eine
    Rippe darf liegen, wie die Fläche es vorgibt, und ein Fuß ebenso. Der
    Befund gehört an die Bausteine, deren Festigkeit an der Druckrichtung
    hängt — heute genau einer.
    """
    project = new_project("centauri-carbon-2", "petg")
    History(project.document).apply(
        "Box",
        [OperationDraft(op="create_box", params={"width": 90.0, "depth": 60.0, "height": 28.0})],
    )
    History(project.document).apply(
        "Rippe",
        [
            OperationDraft(
                op="insert_rib",
                inputs=("obj_1",),
                params={"axis": "x", "y": -30.0, "z": 28.0},
            )
        ],
    )
    result = evaluate(project.document, profile, sources=ProjectSources(project))

    edge = [f for f in result.scene.report.findings if f.code == "parts.standing_on_edge"]
    assert not edge, "eine Rippe darf hochkant stehen — sie bricht davon nicht"


def test_a_chosen_face_does_not_excuse_a_standing_hinge() -> None:
    """**Der Unterschied zum Einhänger, und der Grund für die zweite Hälfte.**

    Bei ``keeps_up`` löst eine angeklickte Fläche das Problem: Sie trägt die
    Richtung, und der Baustein richtet sich daran auf. Hier nicht — eine
    senkrechte Wand legt das Scharnier genau so hin, wie es nicht darf. Ein
    Befund, der bei gewählter Fläche schwiege, ließe den halben Fehler durch.

    Geprüft wird die Funktion direkt, weil die Lage über ein echtes Projekt ein
    Merkmal an einer senkrechten Wand bräuchte — das prüfte dann die
    Merkmalszuordnung mit und nicht mehr diese Entscheidung.
    """
    from types import SimpleNamespace

    from app.core.knowledge.parts.ops import _standing_on_edge

    spec = SimpleNamespace(lies_flat=True, name="living_hinge")
    params = SimpleNamespace(axis="z")

    senkrecht = _standing_on_edge(spec, params, (1.0, 0.0, 0.0))
    assert senkrecht is not None, "an einer senkrechten Wand liegt das Scharnier hochkant"

    waagerecht = _standing_on_edge(spec, params, (0.0, 0.0, 1.0))
    assert waagerecht is None, "auf einer waagerechten Fläche liegt es richtig"

    kopfueber = _standing_on_edge(spec, params, (0.0, 0.0, -1.0))
    assert kopfueber is None, "unter einer Decke ebenso — die Schichten laufen quer"

    andere = SimpleNamespace(lies_flat=False, name="rib")
    assert _standing_on_edge(andere, params, (1.0, 0.0, 0.0)) is None


def test_a_hook_placed_by_hand_says_that_its_up_points_nowhere(profile: Profile) -> None:
    """Ein Einhänger auf getippten Koordinaten hält nichts — und sagte es nicht.

    **Robert am Bild, 30.08.2026:** „eigentlich sind sie falsch gesetzt und man
    könnte sie so nie einhaken." Nachgemessen an einem 120x60x45-Halter mit
    zwei Haken auf *y = -30, z = 30*: hinter der Lochwand standen 0,8 mm
    Material — die Rundung des Zapfens. Mit gewählter Fläche sind es 3,7 mm,
    und das ist die Nase, die hinter den Steg unter dem Schlitz greift.

    Die Ursache ist keine Geometrie, sondern eine Vorgabe. ``keeps_up`` richtet
    die Oberseite entlang einer **Richtung** auf, und eine Richtung liefert nur
    die gewählte Fläche; wer die Position eintippt, behält *Achse = Z*. Um Z
    gedreht kommt das eigene -Y aber nie nach oben — es liegt in der Ebene, in
    der es sich bewegt. Der Haken war also nicht knapp daneben, sondern
    grundsätzlich anders herum, und das Ergebnis sah heil aus: wasserdicht, ein
    Körper, plausibles Volumen. Genau der Fall für Regel 21.
    """
    project = new_project("centauri-carbon-2", "petg")
    History(project.document).apply(
        "Halter",
        [OperationDraft(op="create_box", params={"width": 120.0, "depth": 60.0, "height": 45.0})],
    )
    History(project.document).apply(
        "Einhänger",
        [
            OperationDraft(
                op="insert_pegboard_hook",
                inputs=("obj_1",),
                params={"system": "skadis", "count": 2, "y": -30.0, "z": 30.0},
            )
        ],
    )
    result = evaluate(project.document, profile, sources=ProjectSources(project))

    assert result.complete, [str(f.message) for f in result.scene.report.findings]
    flat = [f for f in result.scene.report.findings if f.code == "parts.up_points_nowhere"]
    assert flat, (
        "zwei Haken liegen waagerecht an der Rückwand und niemand sagt, dass sie so nichts halten"
    )
    message = str(flat[0].message)
    assert "Fläche" in message and "Achse" in message, (
        f"beide Wege nach vorn müssen im Satz stehen, Regel 17: {message}"
    )


def test_the_two_ways_to_stand_a_hook_upright_stay_silent(profile: Profile) -> None:
    """Und die Gegenprobe: Was richtig steht, wird nicht angemeckert.

    Ein Befund, der auch im guten Fall erscheint, ist schlimmer als keiner —
    der Kunde lernt, ihn zu überlesen. Beide Wege stehen hier, weil beide
    gelten: die angeklickte Fläche (sie trägt die Richtung) und *Achse = Y*
    (sie legt das eigene +Y nach unten, also -Y nach oben).
    """
    for params in (
        {"system": "skadis", "count": 2, "steps": 2, "at_feature": "face_3"},
        {"system": "skadis", "count": 2, "axis": "y", "y": -30.0, "z": 30.0},
    ):
        project = new_project("centauri-carbon-2", "petg")
        History(project.document).apply(
            "Halter",
            [
                OperationDraft(
                    op="create_box", params={"width": 120.0, "depth": 60.0, "height": 45.0}
                )
            ],
        )
        History(project.document).apply(
            "Einhänger",
            [OperationDraft(op="insert_pegboard_hook", inputs=("obj_1",), params=params)],
        )
        result = evaluate(project.document, profile, sources=ProjectSources(project))

        assert result.complete, [str(f.message) for f in result.scene.report.findings]
        flat = [f for f in result.scene.report.findings if f.code == "parts.up_points_nowhere"]
        assert not flat, f"{params} steht aufrecht und wird trotzdem gemeldet: {flat}"


def test_a_named_thread_says_how_long_its_helix_is() -> None:
    """Ohne die Strecke lässt sich ein Gewinde nur radial abgrenzen.

    **Wozu die Angabe da ist.** Die Erkennung sieht eine Wendel als das, was
    sie geometrisch ist: eine Folge von Zylinder-, Kegel- und Kugelflecken. An
    einem gedruckten Gewinde werden daraus Phantommerkmale — ein „Zapfen
    Ø 5,79" an einem M6-Bolzen, den niemand gesetzt hat (Kundenbild,
    gemessen von 3d-druck-4d über sechs Größen: kein Fall ohne
    Phantom). Was innerhalb der Hülle des benannten Gewindes liegt, ist ein
    Artefakt der Wendel; Provenienz schlägt Erkennung (§21.2).

    Der Durchmesser allein reicht dafür nicht: Ohne die Strecke längs der
    Achse verschluckt dieselbe Unterdrückung eine echte Bohrung, die koaxial
    unter einem Gewindebolzen sitzt.

    Geprüft wird deshalb beides — dass die Zahl dasteht und dass
    ``centre ± length/2`` wirklich die bewendelte Strecke trifft. Beim Bolzen
    mit Kopf endet sie unter dem Kopf, und genau das ist gewollt: Der Schaft
    gehört nicht zum Gewinde.
    """
    faelle = (
        ("printed_thread", {"size": "M6", "length": 14.99, "play": 0.20}, 14.99, (0.0, 14.99)),
        ("printed_thread", {"size": "M8", "length": 12.0, "play": 0.15}, 12.0, (0.0, 12.0)),
        # Der Sechskantkopf steht um das Spiel über der Fläche, das Gewinde mit ihm (RM-276).
        ("printed_screw", {"size": "M5", "length": 12.0, "play": 0.15}, 12.0, (-11.85, 0.15)),
    )
    for name, werte, erwartet, strecke in faelle:
        spec = PARTS.get(name)
        built = spec.fn(spec.params(**werte))
        threads = [f for f in built.features.values() if f.kind == "thread"]
        assert threads, f"{name} nennt sein Gewinde nicht"
        for feature in threads:
            assert feature.params["handedness"] == "right"
            # Ein Wort des Bausteins, kein Messwert: Ohne diese Quelle las der
            # Steckbrief „rechtsgängig" wie ein gemessenes Maß (21.09.2026).
            assert feature.measure_sources.get("handedness") == "parameter"
            length = float(feature.params.get("length", 0.0))
            centre = feature.params["centre"]
            assert length == pytest.approx(erwartet), (
                f"{name}: Gewindelänge {length} statt {erwartet}"
            )
            unten, oben = centre[2] - length / 2.0, centre[2] + length / 2.0
            assert (unten, oben) == pytest.approx(strecke, abs=0.02), (
                f"{name}: Strecke {unten:.3f}…{oben:.3f} statt {strecke}"
            )

    # Die Mutter führt ihr Innengewinde über die volle Höhe — hier ist die
    # Länge kein Parameter, sondern das Normmaß.
    spec = PARTS.get("printed_nut")
    built = spec.fn(spec.params(size="M6", play=0.15))
    thread = next(f for f in built.features.values() if f.kind == "thread")
    assert float(thread.params["length"]) == pytest.approx(built.mesh.bounds.size[2], abs=0.02), (
        "das Innengewinde der Mutter geht durch, also ist seine Länge die Mutternhöhe"
    )


def test_the_same_part_three_times_keeps_three_named_features() -> None:
    """Derselbe Baustein zweimal eingefügt nahm dem ersten seinen Namen.

    Der Docstring von ``_placed_features`` sagte Kollisionsfreiheit zu —
    „Bausteinname und Position machen es eindeutig" —, und im Namen stand nur
    der Bausteinname. Drei Gewinde auf einer Platte bekamen dreimal
    ``printed_thread_thread_1``, und ``features.update`` beim Aufrufer behielt
    das letzte. **Ohne Befund, ohne Meldung.**

    Der Anlass ist die Projektdatei eines Kunden (M4, M6 und M8 auf einer
    Platte 100 × 60 × 10, 04.09.2026). Bei zehn Millimetern Länge fiel der
    Verlust kaum auf, weil die Wendelerkennung für die zwei verlorenen
    einsprang; unterhalb von etwa sieben Windungen greift sie nicht mehr, und
    dann standen statt zweier Gewinde **vier Zapfen und ein Kegel** im Baum:
    Die Unterdrückung der Phantome hängt am erzeugten Merkmal, und das war
    weg. Ein Fehler deckte den anderen zu.

    Geprüft wird deshalb bei einer Länge **unter** dieser Schwelle — dort
    trägt die Zusage allein, ohne dass die Erkennung sie zufällig einlöst.
    """
    from app.core.bootstrap import load_operations
    from app.core.scene import History, OperationDraft, evaluate
    from app.core.scene.project import ProjectSources, new_project

    load_operations()
    project = new_project("bambu-a1", "pla")
    history = History(project.document)
    history.apply(
        "Platte",
        [OperationDraft(op="create_box", params={"width": 100.0, "depth": 60.0, "height": 10.0})],
    )
    for size, x in (("M4", -20.0), ("M6", 0.0), ("M8", 20.0)):
        history.apply(
            f"Gewinde {size}",
            [
                OperationDraft(
                    op="insert_printed_thread",
                    inputs=("obj_1",),
                    params={
                        "size": size,
                        "length": 5.0,
                        "internal": False,
                        "play": 0.0,
                        "x": x,
                        "y": 0.0,
                        "z": 10.0,
                        "axis": "z",
                    },
                )
            ],
        )
    result = evaluate(
        project.document,
        profiles.make_profile("bambu-a1", "pla"),
        sources=ProjectSources(project),
    )
    entry = next(iter(result.scene.objects.values()))

    # Die Tabellengröße: Gebaut ist jedes um das Spiel aus PLA enger.
    threads = {
        name: round(float(feature.params["nominal"]), 2)
        for name, feature in entry.features.items()
        if feature.kind == "thread"
    }
    assert len(threads) == 3, f"drei Gewinde, drei Namen — gefunden: {threads}"
    assert sorted(threads.values()) == [4.0, 6.0, 8.0], threads
    assert all(
        f.provenance == "generated" for f in entry.features.values() if f.kind == "thread"
    ), "jedes der drei trägt seinen Namen aus dem Baustein, nicht aus der Erkennung"

    # Und die Folge, die den Fehler erst teuer machte: Mit einem Anker je
    # Gewinde greift die Unterdrückung wieder für alle drei.
    invented = sorted(
        f"{name}: {feature.kind}"
        for name, feature in entry.features.items()
        if feature.kind in ("hole", "pin", "cone", "sphere", "torus", "fillet")
    )
    assert not invented, invented


def test_a_part_offers_its_own_actions_not_those_of_a_face() -> None:
    """Ein Schlüsselloch bietet Maße, Lage und Entfernen — an seinem Schritt.

    Gemessen an einem Quader mit ``insert_keyhole``: Der Baustein bringt zwölf
    Merkmale mit — zwei Bohrungen, **zehn Verrundungen** und die Fläche, auf
    der er sitzt. Die Verrundungen tragen für sich keine einzige Handlung
    (``REGISTRY.for_feature("fillet")`` ist leer), und an der Fläche standen
    die Handlungen einer Fläche: Bohren, Tasche, Fläche ziehen. Wer eine
    Schlitzkante anklickte, hat aber das Schlüsselloch gemeint (Befund Robert,
    10.09.2026: „hier sollten wir aber alles für das Schlüsselloch sehen").

    **Die Werte kommen aus dem Schritt, nicht aus dem Merkmal.** Das ist der
    Unterschied zu ``actions_for``, und er ist nicht kosmetisch: Ein Baustein
    rechnet aus ``size="M4"`` zwei Durchmesser — aus den gemessenen
    Durchmessern käme keine Schraubengröße zurück, und ein Zurückschreiben
    verlöre bei jedem Zug ein Stück.
    """
    from types import SimpleNamespace

    from app.core.bootstrap import load_operations
    from app.core.perceive.actions import part_actions

    load_operations()
    spec = REGISTRY.get("insert_keyhole")
    step = SimpleNamespace(id=2, op="insert_keyhole", params={"size": "M5", "drop": 9.0})

    actions = part_actions(step, spec)
    assert [str(action.title) for action in actions] == [
        "Maße ändern",
        "Baustein verschieben",
        "Baustein entfernen",
    ], "Robert: „größe ändern, löschen und verschieben sollte es geben"

    measures, moving, removing = actions
    assert all(action.step == 2 for action in actions), "alle drei gelten dem Schritt"

    # Die Maße sind die des Bausteins, und die Lage steht nicht dabei.
    named = {field.name: field.value for field in measures.fields}
    assert named["size"] == "M5", "der eingegebene Wert, nicht die Vorgabe M4"
    assert named["drop"] == 9.0
    assert not {"x", "y", "z", "nx", "at_feature"} & set(named), (
        "die Lage gehört in ihre eigene Handlung, der Ansatzpunkt in keine"
    )

    # Was im Schritt nicht steht, kommt aus der Vorgabe des Schemas — sonst
    # stünde ein leeres Feld da, und ein Zug darauf setzte es auf null.
    assert named["depth"] == next(
        entry.default for entry in spec.params.spec() if entry.name == "depth"
    )

    assert {field.name for field in moving.fields} == {"x", "y", "z"}
    assert not removing.fields, "Entfernen fragt nichts"
    assert removing.op is None, "es startet keine Operation, es nimmt den Schritt"


@pytest.mark.parametrize("op", ["create_lid", "screw_lid"])
def test_a_lid_offers_no_move_for_the_height_of_its_opening(op: str) -> None:
    """Am Deckel ist ``z`` die Höhe der Öffnung, keine Lage (Review RM-526, B1).

    Seit RM-526 ist sie leer, wenn sie Oberkante heißt. *Baustein verschieben*
    bot sie als Feld an, mit dem Wert ``None``, und das Merkmalfenster warf beim
    Klick auf Kragen oder Öffnung ``TypeError``. Verschoben wird ein Baustein in
    der Ebene; ein Schema ohne ``x`` und ``y`` hat keine Lage. Jedes angebotene
    Feld trägt einen Wert, den ein Zahlenfeld zeigen kann.
    """
    from types import SimpleNamespace

    from app.core.bootstrap import load_operations
    from app.core.perceive.actions import part_actions

    load_operations()
    spec = REGISTRY.get(op)
    for params in ({}, {"z": None}, {"thickness": 2.4}):
        actions = part_actions(SimpleNamespace(id=3, op=op, params=params), spec)
        assert "Baustein verschieben" not in [str(action.title) for action in actions]
        for action in actions:
            for field in action.fields:
                if field.kind in {"length", "angle", "count"}:
                    assert field.value is not None, f"{op}.{field.name} ohne Wert"


def test_only_a_collected_value_from_the_front_gets_a_way_of_its_own() -> None:
    """Genannt wird, was vorn stand — nicht jeder Sammelparameter.

    Was das Merkmalfenster nicht als Zahlenfeld zeigen kann, bekommt einen
    Knopf in den vollen Dialog (``FeatureAction.elsewhere``). Die Auswahl
    dafür muss dieselbe sein wie bei den Maßen daneben: **Vorderseite.**

    Gemessen am 18.09.2026: ``insert_profile_clamp_liner`` führt **zwei**
    Zeichnungen — ``counter_sketch`` vorn und ``outer_sketch`` hinter der
    Klappe. Ungefiltert hieß der Knopf „Gegenkontur, Vorhandene Außenkontur
    ändern …" und versprach damit einen Weg zu einem Wert, der im
    Merkmalfenster nie ein Feld hatte.

    Die Gegenprobe steht daneben: ``create_organizer`` führt seine
    Fachaufteilung **vorn**, und die bleibt.
    """
    from types import SimpleNamespace

    from app.core.bootstrap import load_operations
    from app.core.perceive.actions import COLLECTED_KINDS, part_actions

    load_operations()

    spec = REGISTRY.get("insert_profile_clamp_liner")
    collected = {
        entry.name: entry.placement for entry in spec.params.spec() if entry.kind in COLLECTED_KINDS
    }
    assert collected == {"counter_sketch": "front", "outer_sketch": "advanced"}, (
        "die Voraussetzung: einer vorn, einer hinter der Klappe"
    )

    step = SimpleNamespace(id=2, op="insert_profile_clamp_liner", params={})
    measures = next(action for action in part_actions(step, spec) if action.fields)
    assert [str(title) for title in measures.elsewhere] == ["Gegenkontur"], (
        "die Außenkontur steht hinter der Klappe und bekommt keinen Knopf"
    )

    organizer = REGISTRY.get("create_organizer")
    step = SimpleNamespace(id=2, op="create_organizer", params={})
    measures = next(action for action in part_actions(step, organizer) if action.fields)
    assert [str(title) for title in measures.elsewhere] == ["Fachaufteilung"], (
        "und was vorn steht, behält seinen Weg"
    )


def test_only_a_part_step_answers_for_its_features() -> None:
    """Was kein Baustein ist, behält seine eigenen Handlungen.

    Die Gegenprobe zur Zeile darüber, und sie ist der Grund, warum die Frage
    an der **Kategorie** hängt und nicht am Namen: ``drill_hole`` erzeugt auch
    eine Bohrung mit Provenienz, ist aber kein Baustein — dort ist
    ``resize_hole`` am Merkmal die richtige Antwort und nicht ein Schritt mit
    Schraubengröße.
    """
    from app.core.bootstrap import load_operations

    load_operations()
    assert REGISTRY.get("insert_keyhole").category == "parts"
    assert REGISTRY.get("drill_hole").category != "parts"
    assert REGISTRY.get("create_box").category != "parts"


def test_every_shipped_part_carries_a_current_range_proof() -> None:
    """Jeder mitgelieferte Baustein hat einen Bereichsnachweis, der zu seinem Stand passt.

    §24.3 nennt einen Baustein ohne diesen Nachweis „nicht abgenommen", und die
    Website verspricht ihn. Der Lauf selbst ist zu lang für die Suite; dieser
    Test rechnet nichts, er vergleicht den eingecheckten Nachweis
    (``data/part_ranges.toml``) mit dem Abdruck jedes Bausteins. Wird er rot,
    hat sich ein Baustein, seine Form oder seine Prüfung geändert — dann den
    Lauf wiederholen: ``python tools/check_part_ranges.py``.
    """
    from app.core.knowledge.parts import range_proof

    profile = range_proof.reference_profile()
    proofs = range_proof.load()
    states = {
        spec.name: range_proof.status(spec, profile, proofs)
        for spec in PARTS.all()
        if spec.source == "shipped"
    }
    wrong = {name: state for name, state in states.items() if state != "proven"}
    assert not wrong, (
        f"Bereichsnachweis passt nicht: {wrong} — python tools/check_part_ranges.py "
        + " ".join(sorted(wrong))
    )
    assert set(proofs) == set(states), "Einträge ohne Baustein im Nachweis"


@pytest.mark.parametrize("size", ["M2", "M8"])
def test_a_keyhole_with_the_longest_drop_does_not_cross_itself(size: str) -> None:
    """Der Kopfkanal und sein Einstieg lagen in der Kopfzone aufeinander.

    Das runde Ende des Kanals hat dieselbe Achse und denselben Durchmesser wie
    der Einstieg. Reichten beide bis zum Boden, rundete bei 60 mm Einhängeweg
    die Kanalmitte um ein Haar neben die Achse, und die Vereinigung ließ
    Dreiecke zurück, die einander außerhalb ihrer Kanten berührten: 21 Ecken
    des Bereichstests brachen, mit der alten Prüfung wie mit der neuen.
    """
    spec = PARTS.get("keyhole")
    for play in (0.2, 2.0):
        for depth, head_room in ((1.0, 0.5), (40.0, 20.0)):
            values = spec.params(size=size, drop=60.0, depth=depth, head_room=head_room, play=play)
            mesh = spec.fn(values).mesh
            assert mesh.is_watertight and mesh.component_count == 1
            assert not has_self_intersections(mesh), f"{size}, Tiefe {depth}, Spiel {play}"


def test_a_placed_part_tool_is_where_its_step_cuts_and_knows_when_it_misses(
    profile: Profile,
) -> None:
    """Der Geist beim Zug an einem Baustein ist der ganze Baustein (RM-174, Kernanteil).

    ``placed_tool`` baut das Werkzeug mit der Lage der Operation: Vom Quader
    abgezogen ergibt es genau das Ergebnis des Schritts. Verschoben landet es
    daneben, und ``lands_on`` sagt es, bevor jemand loslässt.
    """
    from dataclasses import replace

    from app.core.registry import validate

    project = new_project("centauri-carbon-2", "petg")
    History(project.document).apply("Quader", [OperationDraft(op="create_box", params={})])
    before = evaluate(project.document, profile, sources=ProjectSources(project))
    box = before.scene.objects["obj_1"]
    History(project.document).apply(
        "Loch",
        [
            OperationDraft(
                op="insert_screw_hole", inputs=("obj_1",), params={"at_feature": "face_top"}
            )
        ],
    )
    after = evaluate(project.document, profile, sources=ProjectSources(project))
    spec = PARTS.get("screw_hole")
    params = validate(REGISTRY.get("insert_screw_hole").params, project.document.ops[-1].params)

    tool = part_ops.placed_tool(box, spec, params, profile)
    cut = boolean("difference", [box.mesh, tool])
    assert cut.mesh.volume == pytest.approx(after.scene.objects["obj_1"].mesh.volume, rel=1e-9)
    assert part_ops.lands_on(box.mesh, tool)

    beside = part_ops.placed_tool(box, spec, replace(params, x=100.0), profile)
    assert float(beside.bounds.minimum[0]) == pytest.approx(
        float(tool.bounds.minimum[0]) + 100.0, abs=1e-9
    )
    assert not part_ops.lands_on(box.mesh, beside), "daneben landet der Baustein nicht"


@pytest.mark.parametrize("language", available_languages())
def test_range_wall_failure_translates_its_complete_numeric_frame(
    language: str,
    profile: Profile,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Die echte Bereichsprüfung erhält drei Nachkommastellen und Sprachabstände."""
    import trimesh

    from app.core.knowledge.parts import range_check
    from app.i18n import get_language, set_language, tr
    from app.i18n.catalog import install_language

    @op_params
    class SolidParams(BaseParams):
        pass

    def solid(_values: BaseParams) -> PartResult:
        return PartResult(mesh=MeshData.of(trimesh.creation.box(extents=(2.0, 2.0, 2.0))))

    monkeypatch.setattr(range_check, "local_wall_thickness", lambda _mesh, _token: 0.835)
    monkeypatch.setattr(range_check, "has_self_intersections", lambda _mesh, _token: False)
    previous = get_language()
    install_language(language)
    set_language(language)
    try:
        report = range_check.check(SolidParams, solid, profile)
        expected = tr(
            "dünner als druckbar: {measured} mm < {minimum} mm",
            measured="0.835",
            minimum="0.840",
        )
        assert not report.passed
        assert [failure.reason for failure in report.failures] == [expected]
        assert "0.835 mm < 0.840 mm" in expected
        if language == "fr":
            assert " : 0.835 mm < 0.840 mm" in expected
    finally:
        set_language(previous)


# --- Halter (RM-399) --------------------------------------------------------------


HOLDERS = ("holder_u", "holder_ring", "holder_fork", "holder_shelf")


def _holder(name: str, **values: Any) -> PartResult:
    """Ein Halter mit dem Spiel, das das Bezugsprofil einsetzt."""
    spec = PARTS.get(name)
    return spec.fn(spec.params(**{"play": 0.2, **values}))


def _inside(produced: PartResult, *points: tuple[float, float, float]) -> list[bool]:
    """Ob die Punkte im Körper liegen — Material oder Luft an einer Stelle, die zählt.

    Über die Umlaufzahl des geschlossenen Netzes (Raumwinkel je Dreieck), nicht
    über ``trimesh.contains``: Das braucht ``rtree``, und das liegt nicht auf
    jeder Maschine.
    """
    raw = as_mesh_data(produced.mesh).raw
    corners = np.asarray(raw.vertices, dtype=float)[np.asarray(raw.faces)]
    found = []
    for point in np.asarray(points, dtype=float):
        a, b, c = (corners[:, index, :] - point for index in range(3))
        la, lb, lc = (np.linalg.norm(vector, axis=1) for vector in (a, b, c))
        volume = np.einsum("ij,ij->i", a, np.cross(b, c))
        below = (
            la * lb * lc
            + np.einsum("ij,ij->i", a, b) * lc
            + np.einsum("ij,ij->i", b, c) * la
            + np.einsum("ij,ij->i", c, a) * lb
        )
        winding = np.sum(2.0 * np.arctan2(volume, below)) / (4.0 * np.pi)
        found.append(bool(abs(winding) > 0.5))
    return found


def test_the_holders_are_found_as_one_step_templates_in_the_catalogue() -> None:
    """Ein Kunde sucht „Halter" und findet vier Vorlagen, die frei entstehen (RM-399).

    Jede steht für sich (``standalone``) und entsteht über ``create_…`` in einem
    Schritt; ``template`` sagt dem Dialog, dass er *Maße als Parameter anlegen*
    anbietet. Die Befestigung ist in allen vieren dieselbe Wahl.
    """
    from app.core.knowledge.parts import holders

    found = {spec.name for spec in PARTS.search("Halter")}
    assert set(HOLDERS) <= found
    for name in HOLDERS:
        spec = PARTS.get(name)
        assert spec.standalone and spec.template and not spec.at_face, name
        assert spec.group == "mounting"
        creator = REGISTRY.get(part_ops.creation_name(name))
        assert creator.name == f"create_{name}"
        assert (creator.consumes, creator.produces) == (0, 1)
        mount = next(entry for entry in spec.params.spec() if entry.name == "mount")
        assert tuple(mount.choices) == holders.MOUNTS


def test_a_template_without_a_creator_is_refused() -> None:
    """Eine Vorlage ohne Erzeuger trüge einen Haken in einem Dialog, den es nicht gibt."""
    from app.core.errors import InternalError

    registry = PartRegistry()

    @op_params
    class Params(BaseParams):
        size: float = param(title="x", default=1.0)

    with pytest.raises(InternalError):

        @register_part(
            name="lonely",
            title="x",
            group="mounting",
            params=Params,
            features=["plate"],
            template=True,
            registry=registry,
        )
        def lonely(raw: BaseParams) -> PartResult:  # pragma: no cover - läuft nie
            raise AssertionError


#: Was ein Kunde für sich druckt (RM-562, Kunden-E-Mail 07.10.2026): Kabelclip,
#: Eckwinkel, Rippe, Standfuß, Wandhalter und die Teile, die wie sie ohne Träger
#: ihre Aufgabe erfüllen. Die Quelle ist ``standalone`` am Baustein; diese Liste
#: hält nur fest, dass die genannten dabei sind.
ON_THEIR_OWN = (
    "barrel_hinge",
    "cable_clip",
    "dowel",
    "foot",
    "gusset",
    "living_hinge",
    "printed_nut",
    "printed_screw",
    "rib",
    "threaded_rod",
    "wall_mount",
)


def test_the_parts_customers_print_on_their_own_stand_alone() -> None:
    """RM-562: Diese Bausteine ließen sich nur an einen gewählten Körper anfügen."""
    assert [name for name in ON_THEIR_OWN if not PARTS.get(name).standalone] == []


@pytest.mark.parametrize(
    "name", [spec.name for spec in PARTS.all() if spec.standalone], ids=lambda name: name
)
def test_every_standalone_part_makes_a_watertight_body_without_a_selection(
    name: str, profile: Profile
) -> None:
    """Ein eigenständiger Baustein braucht keinen Körper: leeres Projekt, ein Schritt, ein Teil.

    Mit den Vorgaben seines Erzeugers, so wie der Katalog ihn ohne Auswahl
    anlegt — wasserdicht, mit den erklärten Teilen und ohne Fehler. Wo der
    Kunde eine Kontur zeichnen muss, steht hier ein Kreis.
    """
    from app.core.sketch import shapes as sketch_shapes
    from app.core.sketch.serialize import sketch_to_text

    spec = PARTS.get(name)
    creator = REGISTRY.get(part_ops.creation_name(name))
    assert (creator.consumes, creator.produces) == (0, 1)
    drawn = {
        entry.name: sketch_to_text(sketch_shapes.circle(20.0))
        for entry in creator.params.spec()
        if entry.kind == "sketch" and entry.required
    }
    project = new_project("centauri-carbon-2", "petg")
    History(project.document).apply(spec.name, [OperationDraft(op=creator.name, params=drawn)])
    result = evaluate(project.document, profile, sources=ProjectSources(project))
    assert result.complete
    assert len(result.scene.objects) == 1
    body = as_mesh_data(next(iter(result.scene.objects.values())).mesh)
    assert body.is_watertight
    assert body.component_count == spec.bodies
    assert float(body.raw.bounds[0][2]) == pytest.approx(0.0, abs=1e-6), "er steht auf dem Bett"


#: Die 22 Erzeuger von vor RM-562 in fünf Lagen, gemessen am Ausgangsstand
#: ``3d900b428`` (Review B). Ein altes Projekt mit einem dieser Schritte muss
#: gleich rechnen — Hülle, Volumen und jede Merkmalskennung samt Mitte.
_CREATORS_BEFORE: dict[str, Any] = json.loads(
    (Path(__file__).parent / "data" / "creators_before_rm562.json").read_text(encoding="utf-8")
)


def _created(name: str, values: dict[str, Any], profile: Profile) -> Any:
    """Der Körper des Erzeugers in einer Lage, Zeichnungen als Kreis."""
    from app.core.sketch import shapes as sketch_shapes
    from app.core.sketch.serialize import sketch_to_text

    creator = REGISTRY.get(f"create_{name}")
    fields = part_ops.placement_fields(creator.params)
    params: dict[str, Any] = {
        entry.name: sketch_to_text(sketch_shapes.circle(20.0))
        for entry in creator.params.spec()
        if entry.kind == "sketch" and entry.required
    }
    params.update({fields.get(key, key): value for key, value in values.items()})
    project = new_project("centauri-carbon-2", "petg")
    History(project.document).apply(name, [OperationDraft(op=creator.name, params=params)])
    result = evaluate(project.document, profile, sources=ProjectSources(project))
    assert result.complete
    (body,) = result.scene.objects.values()
    return body


@pytest.mark.parametrize("name", sorted(_CREATORS_BEFORE["parts"]))
def test_every_creator_keeps_its_old_placement(name: str, profile: Profile) -> None:
    """Review G1: Ein alter Erzeugerschritt rechnet nach RM-562 wie vorher.

    Rollte das Netz der frei gesetzten Rohrschelle mit ``keeps_up``, tauschten
    ihre erkannten Flächen die Kennung — Hülle und Volumen blieben gleich, und
    ein Schritt an ``face_1`` eines alten Projekts träfe die Gegenseite. Geprüft
    werden alle 22 Erzeuger von damals in fünf Lagen.
    """
    for case, values in _CREATORS_BEFORE["cases"].items():
        before = _CREATORS_BEFORE["parts"][name][case]
        body = _created(name, values, profile)
        mesh = as_mesh_data(body.mesh)
        low, high = mesh.raw.bounds
        assert [float(v) for v in low] == pytest.approx(before["lo"], abs=2e-3), case
        assert [float(v) for v in high] == pytest.approx(before["hi"], abs=2e-3), case
        assert float(mesh.volume) == pytest.approx(before["volume"], rel=1e-5), case
        centres = {
            key: [float(v) for v in (feature.params.get("centre") or ())]
            for key, feature in body.features.items()
        }
        assert sorted(centres) == sorted(before["centres"]), case
        for key, centre in centres.items():
            assert centre == pytest.approx(before["centres"][key], abs=2e-3), (case, key)


@pytest.mark.parametrize(
    "name", [spec.name for spec in PARTS.all() if spec.standalone], ids=lambda name: name
)
def test_every_creator_keeps_its_declared_features_on_its_body(name: str, profile: Profile) -> None:
    """In jeder der fünf Lagen liegen die erklärten Merkmale am Körper, nicht daneben.

    Netz und Merkmale werden getrennt gesetzt (``_place`` und ``_placed_features``);
    rollte nur eines von beiden, stünde ein Merkmal neben dem Teil. Die
    Rohrschelle trifft das nur nicht, weil sie unter der halben Drehung
    symmetrisch ist — ein neuer eigenständiger Baustein mit ``keeps_up`` fiele
    hier auf.
    """
    for case, values in _CREATORS_BEFORE["cases"].items():
        body = _created(name, values, profile)
        low, high = as_mesh_data(body.mesh).raw.bounds
        for key, feature in body.features.items():
            centre = feature.params.get("centre")
            if not key.startswith(f"{name}_") or centre is None:
                continue
            for axis in range(3):
                assert low[axis] - 1e-3 <= float(centre[axis]) <= high[axis] + 1e-3, (case, key)


@pytest.mark.parametrize("name", ["printed_screw", "printed_nut", "rib"])
def test_the_bed_rule_holds_upright_and_turns_with_a_chosen_axis(
    name: str, profile: Profile
) -> None:
    """Review G3: Die Unterseite liegt auf der Ebene des Ursprungs — das Bett nur aufrecht.

    Ohne Richtung und mit Achse Z steht der Körper auf z = 0, die Schraube mit
    dem Kopf unten. Mit Achse X dreht die Ebene mit: Die Unterseite des
    Bausteins liegt dann auf x = 0, und unter dem Bett kann etwas hängen, wie
    bei jedem Erzeuger vor RM-562. Genau das sagt die Regel in ``bausteine.md``.
    """
    upright = as_mesh_data(_created(name, {}, profile).mesh)
    assert float(upright.raw.bounds[0][2]) == pytest.approx(0.0, abs=1e-6)
    lying = as_mesh_data(_created(name, {"axis": "x"}, profile).mesh)
    low, high = lying.raw.bounds
    assert min(abs(float(low[0])), abs(float(high[0]))) == pytest.approx(0.0, abs=1e-6), (
        "die Unterseite liegt auf der gedrehten Ebene x = 0"
    )
    assert float(low[2]) < -1e-3, "das Bett gilt nur aufrecht"


def test_a_creator_offers_no_place_list_but_an_old_step_with_one_still_loads() -> None:
    """Review B: „An mehreren Merkmalen“ stand am Erzeuger und wirkte nicht.

    Ein Erzeuger setzt an kein Merkmal; die Auswahl belegte das Feld trotzdem
    vor. Jetzt ist es ein interner Marker — nicht im Dialog, nicht beim Agenten
    —, und ein gespeicherter Schritt, der eine Liste trägt, lädt weiter.
    """
    from app.core.agent.tools import tool_schemas
    from app.core.registry import validate

    creator = REGISTRY.get("create_pipe_clamp")
    entry = next(item for item in creator.params.spec() if item.name == "at_features")
    assert entry.internal
    assert (
        next(
            item
            for item in REGISTRY.get("insert_pipe_clamp").params.spec()
            if item.name == "at_features"
        ).internal
        is False
    )
    validate(creator.params, {"at_features": ("face_1",)})
    schema = next(tool for tool in tool_schemas() if tool["name"] == "create_pipe_clamp")
    assert "at_features" not in str(schema)


@pytest.mark.parametrize("name", ["foot", "dowel"])
def test_a_standalone_creator_offers_only_the_form_that_is_a_body(name: str) -> None:
    """Ein Fuß als Tasche, ein Stift als Bohrung trägt ab — ohne Träger gibt es nichts abzutragen.

    Der Erzeuger lässt die Wahl deshalb weg, statt sie anzubieten und danach
    abzuweisen; das Einsetzen an einer Fläche behält sie.
    """
    created = {entry.name for entry in REGISTRY.get(f"create_{name}").params.spec()}
    inserted = {entry.name for entry in REGISTRY.get(f"insert_{name}").params.spec()}
    assert "kind" in inserted
    assert "kind" not in created
    assert not part_ops.cuts(PARTS.get(name), PARTS.get(name).params())


def test_a_part_that_only_cuts_cannot_stand_alone() -> None:
    """Eine Bohrung als eigenes Objekt wäre ein Zylinder, der nichts bohrt."""
    from app.core.errors import InternalError

    @op_params
    class Params(BaseParams):
        size: float = param(title="x", default=1.0)

    @op_params
    class Choice(BaseParams):
        kind: str = param(
            title="x", default="hole", choices=("hole", "pin"), subtractive_on=("hole",)
        )

    @op_params
    class Hanging(BaseParams):
        kind: str = param(
            title="x", default="pin", choices=("pin", "hole"), subtractive_on=("hole",)
        )
        chamfer: float = param(title="x", default=0.5, depends_on=("kind", ("pin",)))

    @op_params
    class Fine(BaseParams):
        kind: str = param(
            title="x", default="pin", choices=("pin", "hole"), subtractive_on=("hole",)
        )
        chamfer: float = param(title="x", default=0.5)

    # Review G4: Der Erzeuger lässt ``kind`` weg; ein Feld, das an ihm hängt,
    # stünde dort ohne seine Bedingung.
    for params, subtractive in ((Params, True), (Choice, False), (Hanging, False)):
        with pytest.raises(InternalError):

            @register_part(
                name="pit",
                title="x",
                group="mounting",
                params=params,
                features=["pit"],
                standalone=True,
                subtractive=subtractive,
                registry=PartRegistry(),
            )
            def pit(raw: BaseParams) -> PartResult:  # pragma: no cover - läuft nie
                raise AssertionError

    @register_part(
        name="pit",
        title="x",
        group="mounting",
        params=Fine,
        features=["pit"],
        standalone=True,
        registry=PartRegistry(),
    )
    def fine(raw: BaseParams) -> PartResult:  # pragma: no cover - läuft nie
        raise AssertionError


def test_the_catalogue_attaches_at_a_chosen_place_and_creates_without_one() -> None:
    """RM-562: Ohne gewählte Fläche entsteht ein eigenständiger Baustein als eigener Körper.

    Mit einer gewählten Stelle setzt er sich dort an, wie bisher — auch an
    mehreren zugleich (Review M2) und an einer gerundeten Seite (M3). Was nur an
    einem Träger wirkt, bleibt beim Einsetzen; ein Prüfkörper bleibt frei.
    """
    choose = part_ops.catalog_operation
    assert choose("rib", at=()) == "create_rib"
    assert choose("rib", at=("face",)) == "insert_rib"
    assert choose("rib", at=("face", "face", "face", "face")) == "insert_rib", "vier Flächen"
    assert choose("rib", at=("curved_face",)) == "insert_rib", "die gerundete Seite trägt ihn"
    assert choose("rib", at=("face", "edge")) == "create_rib", "nur wenn jede Stelle passt"
    assert choose("rib", at=("edge",)) == "create_rib"
    assert choose("printed_screw", at=("hole",)) == "insert_printed_screw"
    assert choose("printed_screw", at=("face",)) == "create_printed_screw", "an einer Fläche frei"
    assert choose("screw_hole", at=()) == "insert_screw_hole"
    assert choose("fit_ladder", at=("face",)) == "create_fit_ladder"


def test_a_u_holder_arises_in_one_step_and_the_parameter_bar_turns_its_inner_width(
    profile: Profile,
) -> None:
    """U-Halter mit Schlüsselloch in einem Schritt, die Leiste dreht die Breite (RM-399).

    Die Maße stehen als Projektparameter in derselben Transaktion wie der
    Schritt — so legt sie der Haken *Maße als Parameter anlegen* an. Gedreht
    wird danach nur die Zahl in der Leiste, der Schritt bleibt; ein Strg+Z je
    Transaktion nimmt alles zurück.
    """
    from app.core.knowledge.parts import holders
    from app.core.scene.history import change_for
    from app.core.types import Parameter

    project = new_project("centauri-carbon-2", "petg")
    history = History(project.document)
    created = {
        name: Parameter(name=name, value=value, unit="mm")
        for name, value in (("breite", 40.0), ("tiefe", 30.0), ("hoehe", 40.0))
    }
    history.apply(
        "Halter",
        [
            OperationDraft(
                op="create_holder_u",
                params={
                    "width": "=@breite",
                    "depth": "=@tiefe",
                    "height": "=@hoehe",
                    "mount": "keyhole",
                    "floor": False,
                    "wall": 3.0,
                },
            )
        ],
        changes=change_for(history.document, parameters=created),
    )
    assert len(history.document.ops) == 1

    def measured() -> tuple[tuple[float, float, float], frozenset[str]]:
        result = evaluate(history.document, profile, sources=ProjectSources(project))
        assert result.complete, [str(finding.message) for finding in result.scene.report.findings]
        (body,) = result.scene.objects.values()
        assert as_mesh_data(body.mesh).is_watertight
        return body.mesh.bounds.size, frozenset(body.features)

    play = profile.material.clearance
    (width, depth, height), features = measured()
    assert width == pytest.approx(40.0 + play + 2.0 * 3.0)
    assert depth == pytest.approx(holders._thickness("keyhole", 3.0) + 30.0 + play + 3.0)
    assert height == pytest.approx(40.0)
    assert {
        "holder_u_plate_1",
        "holder_u_front_1",
        "holder_u_keyhole_1",
        "holder_u_keyhole_2",
    } <= features

    history.apply(
        "Breite",
        [],
        changes=change_for(
            history.document, parameters={"breite": Parameter(name="breite", value=60.0)}
        ),
    )
    (wider, same_depth, _height), _features = measured()
    assert wider == pytest.approx(width + 20.0), "die Leiste dreht das Innenmaß"
    assert same_depth == pytest.approx(depth)
    history.undo()
    history.undo()
    assert not history.document.ops
    assert not history.document.parameters, "Schritt und Maße waren eine Transaktion"


def test_the_keyholes_open_at_the_back_and_hold_the_screw_above_the_entrance() -> None:
    """Das Schlüsselloch schneidet von der Wandseite und lässt vorn eine Wand stehen.

    Der Kopf geht unten durch den Einstieg, der Halter sinkt, und die Schraube
    sitzt oben am Ende des Schlitzes — gemessen an Luft und Material, nicht an
    einer Formel.
    """
    from app.core.knowledge.parts import holders
    from app.core.knowledge.parts.mounting import HEAD_CLEARANCE

    wall, height = 3.0, 40.0
    produced = _holder(
        "holder_u", mount="keyhole", width=40.0, depth=30.0, height=height, wall=wall, floor=False
    )
    keyhole = holders.KEYHOLE
    thickness = wall + keyhole.depth
    across = standards.screw(keyhole.size).head + HEAD_CLEARANCE + 0.2
    plate_width = produced.mesh.bounds.size[0]
    entrance = height / 2.0 - keyhole.drop / 2.0
    for side, name in ((-1.0, "keyhole_1"), (1.0, "keyhole_2")):
        x = side * (plate_width / 2.0 - wall - across / 2.0)
        centre = produced.features[name].params["centre"]
        assert centre[0] == pytest.approx(x)
        assert centre[2] == pytest.approx(entrance + keyhole.drop), "die Schraube sitzt oben"
        assert -thickness < centre[1] < -wall
        assert _inside(
            produced,
            (x, -thickness + 0.3, entrance),
            (x, -wall / 2.0, entrance),
            (x, -thickness + 0.3, entrance + keyhole.drop),
        ) == [False, True, False], "offen zur Wand, vorn geschlossen, Schlitz nach oben"
    assert produced.mesh.bounds.minimum[1] == pytest.approx(-thickness)


def test_a_narrow_holder_takes_one_centred_keyhole_and_keeps_its_width() -> None:
    """Nachbau Modell 1 (RM-443): 20 mm breit mit einem Schlüsselloch, nicht 24,7 mm.

    ``grenuttags_hallare_modell_40x47.stl`` aus dem Korpus ist 20 mm breit und
    hängt an **einem** Schlüsselloch. Die Vorlage setzte immer zwei
    nebeneinander und machte die Rückwand dafür breiter als den Halter: 24,7
    statt 20 mm. Wo zwei Löcher mit Rand nicht in die Breite passen, sitzt
    jetzt eines in der Mitte, und der Halter bleibt so breit, wie er
    eingetragen wurde.
    """
    from app.core.knowledge.parts import holders
    from app.core.knowledge.parts.mounting import HEAD_CLEARANCE

    wall, play = 3.0, 0.2
    # Außenbreite 20 mm: Innenmaß plus Spiel plus zwei Wände.
    produced = _holder(
        "holder_u", mount="keyhole", width=20.0 - 2.0 * wall - play, depth=41.0, height=53.0
    )
    assert produced.mesh.bounds.size[0] == pytest.approx(20.0)
    assert "keyhole_1" in produced.features and "keyhole_2" not in produced.features
    centre = produced.features["keyhole_1"].params["centre"]
    assert centre[0] == pytest.approx(0.0), "das eine Loch sitzt in der Mitte"
    keyhole = holders.KEYHOLE
    entrance = 53.0 / 2.0 - keyhole.drop / 2.0
    thickness = wall + keyhole.depth
    assert _inside(
        produced,
        (0.0, -thickness + 0.3, entrance),
        (0.0, -wall / 2.0, entrance),
        (0.0, -thickness + 0.3, entrance + keyhole.drop),
    ) == [False, True, False], "offen zur Wand, vorn geschlossen, Schlitz nach oben"
    mesh = as_mesh_data(produced.mesh)
    assert mesh.is_watertight and mesh.component_count == 1

    # Zwei Löcher, sobald sie mit Rand in die Breite passen — und keinen
    # Millimeter vorher.
    across = standards.screw(keyhole.size).head + HEAD_CLEARANCE + play
    both = 2.0 * across + 3.0 * wall
    fits = _holder("holder_u", mount="keyhole", width=both - 2.0 * wall - play, height=53.0)
    assert {"keyhole_1", "keyhole_2"} <= set(fits.features)
    assert fits.mesh.bounds.size[0] == pytest.approx(both)
    short = _holder("holder_u", mount="keyhole", width=both - 2.0 * wall - play - 0.5, height=53.0)
    assert "keyhole_2" not in short.features
    assert short.mesh.bounds.size[0] == pytest.approx(both - 0.5)


def test_a_holder_narrower_than_one_keyhole_grows_only_for_that_one() -> None:
    """Schmaler als ein Schlüsselloch mit Rand: Die Rückwand wächst auf genau dieses Maß.

    Ein Kopf von 7,8 mm braucht seinen Durchgang; mehr Platz als für das eine
    Loch nimmt die Rückwand nicht, und ein zweites kommt nicht dazu.
    """
    from app.core.knowledge.parts import holders
    from app.core.knowledge.parts.mounting import HEAD_CLEARANCE

    wall, play = 3.0, 0.2
    across = standards.screw(holders.KEYHOLE.size).head + HEAD_CLEARANCE + play
    produced = _holder("holder_u", mount="keyhole", width=5.0, height=40.0, wall=wall)
    assert 5.0 + play + 2.0 * wall < across + 2.0 * wall, "die Halteform allein ist zu schmal"
    assert produced.mesh.bounds.size[0] == pytest.approx(across + 2.0 * wall)
    assert "keyhole_2" not in produced.features
    mesh = as_mesh_data(produced.mesh)
    assert mesh.is_watertight and mesh.component_count == 1


def test_the_holder_plate_holds_the_whole_countersink_and_the_keyhole() -> None:
    """Die Rückwand ist eine Wandstärke dicker als die Aussparung, die in ihr sitzt.

    Die Senkungstiefe kommt aus derselben Rechnung wie in ``screw_hole`` —
    hier gegen dessen gemeldetes Merkmal gehalten, damit beide nicht
    auseinanderlaufen.
    """
    from app.core.knowledge.parts import holders

    spec = PARTS.get("screw_hole")
    tool = spec.fn(spec.params(size=holders.SCREW_SIZE, depth=10.0, countersink=True))
    sink = float(tool.features["countersink_1"].params["depth"])
    assert holders._thickness("screws", 3.0) == pytest.approx(3.0 + sink)
    assert holders._thickness("keyhole", 3.0) == pytest.approx(3.0 + holders.KEYHOLE.depth)
    assert holders._thickness("pegboard", 3.0) == pytest.approx(3.0)
    assert holders._thickness("clamp", 3.0) == pytest.approx(3.0)


@pytest.mark.parametrize("size", ["M2", "M12", "M64"])
def test_a_holder_takes_every_screw_of_the_wall_mount_and_its_tabs_grow(size: str) -> None:
    """RM-578: Die Schraube der Laschen ist wählbar wie beim Wandhalter, bis M64.

    Bis dahin stand sie fest auf M4, weil 512 Ecken je Halter für eine Wahl nicht
    reichten. Die Laschen wachsen mit der Senkung, die Bohrung hat das
    Durchgangsloch der Tabelle.
    """
    from app.core.knowledge.parts import holders
    from app.core.knowledge.parts.mounting import WALL_SCREWS

    assert size in WALL_SCREWS
    wall = 3.0
    produced = _holder(
        "holder_u",
        mount="screws",
        screw_size=size,
        width=40.0,
        depth=30.0,
        height=40.0,
        wall=wall,
        floor=True,
    )
    screw = standards.screw(size)
    tab = screw.countersink + 2.0 * wall
    assert produced.mesh.bounds.size[0] == pytest.approx(40.2 + 2.0 * wall + 2.0 * tab)
    assert produced.features["bore_1"].params["diameter"] == pytest.approx(screw.clearance)
    assert holders._thickness("screws", wall, size) > wall


def test_the_screw_holes_sit_in_tabs_beside_the_holder_with_the_countersink_in_front() -> None:
    """Hinter einer U-Form erreicht kein Schraubendreher die Rückwand — daneben schon."""
    from app.core.knowledge.parts import holders

    wall = 3.0
    produced = _holder(
        "holder_u", mount="screws", width=40.0, depth=30.0, height=40.0, wall=wall, floor=True
    )
    screw = standards.screw(holders.SCREW_SIZE)
    outer = 40.2 + 2.0 * wall
    tab = screw.countersink + 2.0 * wall
    thickness = holders._thickness("screws", wall)
    assert produced.mesh.bounds.size[0] == pytest.approx(outer + 2.0 * tab)
    for side, name in ((-1.0, "bore_1"), (1.0, "bore_2")):
        bore = produced.features[name].params
        x = side * (outer / 2.0 + tab / 2.0)
        assert bore["centre"][0] == pytest.approx(x)
        assert bore["through"] is True
        assert bore["diameter"] == pytest.approx(screw.clearance)
        radial = (screw.clearance + screw.countersink) / 4.0
        assert _inside(
            produced, (x + radial, -0.2, 20.0), (x + radial, -thickness + 0.2, 20.0)
        ) == [False, True], "die Senkung liegt vorn, hinten nur die Bohrung"


def test_the_pegboard_hooks_reach_behind_the_plate_in_the_board_grid_with_the_latch_on_top() -> (
    None
):
    """Zwei Haken im Raster der Lochwand, hinter der Rückwand, die Zunge oben."""
    from app.core.knowledge.parts import holders

    wall = 4.0
    produced = _holder(
        "holder_fork", mount="pegboard", width=25.0, depth=25.0, height=15.0, wall=wall
    )
    board = standards.board(holders.HOOKS.system)
    hooks = [produced.features[f"hook_{index}"].params for index in (1, 2)]
    latches = [produced.features[f"latch_{index}"].params for index in (1, 2)]
    assert abs(hooks[0]["centre"][0] - hooks[1]["centre"][0]) == pytest.approx(
        board.pitch * holders.HOOKS.steps
    )
    for hook, latch in zip(hooks, latches, strict=True):
        assert hook["centre"][1] < -wall - board.thickness, "die Nase greift hinter die Platte"
        assert tuple(hook["normal"]) == pytest.approx((0.0, -1.0, 0.0))
        assert latch["centre"][2] > hook["centre"][2], "die Rastzunge sitzt oben"
    mesh = as_mesh_data(produced.mesh)
    assert mesh.is_watertight and mesh.component_count == 1
    assert mesh.bounds.size[0] >= board.pitch + 2.0 * wall


def test_the_clamp_gap_is_the_entered_board_thickness() -> None:
    """Platte, Spalt, Schenkel: Der Spalt hat genau die eingetragene Stärke."""
    wall = 3.0
    for board in (12.0, 40.0):
        produced = _holder(
            "holder_ring",
            mount="clamp",
            board=board,
            diameter=60.0,
            height=40.0,
            wall=wall,
            floor=True,
        )
        clamp = produced.features["clamp_1"].params
        assert clamp["centre"][1] == pytest.approx(-(wall + board))
        assert produced.mesh.bounds.minimum[1] == pytest.approx(-(wall + board + wall))
        assert _inside(
            produced,
            (0.0, -wall - board / 2.0, 20.0),
            (0.0, -wall / 2.0, 20.0),
            (0.0, -wall - board - wall / 2.0, 20.0),
            (0.0, -wall - board / 2.0, 40.0 - wall / 2.0),
        ) == [False, True, True, True], "Luft im Spalt, Rückwand, Schenkel, Bügel"


def test_a_fork_whose_prongs_end_before_the_seat_is_refused_with_advice() -> None:
    """Zinken, die nicht über die Mitte des Grunds reichen, halten keinen Stiel."""
    from app.core.errors import ValidationError
    from app.core.knowledge.parts import holders

    spec = PARTS.get("holder_fork")
    values = spec.params(width=60.0, depth=20.0, play=0.2)
    assert spec.feasible is not None and spec.feasible(values) is holders.FORK_TOO_SHALLOW
    with pytest.raises(ValidationError) as caught:
        spec.fn(values)
    assert caught.value.constraint == "feasible"
    assert caught.value.suggestions, "Regel 17"
    assert spec.feasible(spec.params(width=40.0, depth=21.0, play=0.2)) is None


def test_the_fork_seat_is_round_and_the_prongs_hold_the_handle() -> None:
    """Ein runder Stiel liegt im halbrunden Grund und hat seitlich die Zinken."""
    wall = 4.0
    produced = _holder("holder_fork", mount="clamp", width=25.0, depth=25.0, height=15.0, wall=wall)
    radius = 25.2 / 2.0
    assert _inside(
        produced,
        (0.0, radius, 7.5),
        (radius + wall / 2.0, radius, 7.5),
        (radius * 0.9, 0.3, 7.5),
        (0.0, 0.3, 7.5),
    ) == [False, True, True, False], "Stiel frei, Zinke Material, Grund rund"
    assert produced.features["prong_1"].params["centre"][0] == pytest.approx(-(radius + wall / 2.0))


def test_the_shelf_grows_its_plate_so_the_brace_stays_at_45_degrees() -> None:
    """Die Stütze unter der Ablage steigt unter 45 Grad und druckt ohne Stützmaterial."""
    wall = 3.0
    flat = _holder(
        "holder_shelf", mount="clamp", width=30.0, depth=40.0, height=12.0, wall=wall, lip=0.0
    )
    front = 40.2
    assert flat.mesh.bounds.size[2] == pytest.approx(front + wall), "die Rückwand wächst"
    assert flat.mesh.bounds.maximum[1] == pytest.approx(front)
    assert "lip_1" not in flat.features
    # Die Schräge läuft von der Rückwand bei z = 0 bis zur Vorderkante: z = y.
    assert _inside(flat, (0.0, 20.0, 20.5), (0.0, 20.0, 19.5)) == [True, False]

    rim = _holder(
        "holder_shelf", mount="clamp", width=30.0, depth=40.0, height=60.0, wall=wall, lip=10.0
    )
    assert rim.mesh.bounds.size[2] == pytest.approx(70.0), "Z-Form: Rand über der Ablage"
    assert rim.mesh.bounds.maximum[1] == pytest.approx(front + wall)
    assert rim.features["lip_1"].params["centre"][2] == pytest.approx(70.0)
    assert rim.features["shelf_1"].params["centre"][2] == pytest.approx(60.0)
    assert _inside(rim, (0.0, front / 2.0, 65.0), (0.0, front + wall / 2.0, 65.0)) == [
        False,
        True,
    ], "auf der Ablage Luft, vorn der Rand"


def test_the_ring_keeps_a_web_from_the_plate_and_its_seat_is_the_object_plus_play() -> None:
    """Der Sitz ist der Gegenstand mit Spiel; zur Rückwand bleibt eine halbe Wand Steg."""
    from app.core.knowledge.parts import holders

    wall = 4.0
    cup = _holder("holder_ring", mount="screws", diameter=50.0, height=30.0, wall=wall, floor=True)
    seat = cup.features["seat_1"].params
    assert seat["diameter"] == pytest.approx(50.2)
    assert seat["centre"][1] == pytest.approx(holders.ring_centre(50.0, 0.2, wall))
    assert seat["centre"][1] - 25.1 == pytest.approx(wall / 2.0)
    assert seat["through"] is False and "floor_1" in cup.features
    ring = _holder(
        "holder_ring", mount="screws", diameter=50.0, height=30.0, wall=wall, floor=False
    )
    assert ring.features["seat_1"].params["through"] is True
    assert "floor_1" not in ring.features
    assert _inside(cup, (0.0, 27.1, 1.0), (0.0, 27.1, wall + 1.0)) == [True, False]
    assert _inside(ring, (0.0, 27.1, 1.0)) == [False]


@pytest.mark.parametrize("name", HOLDERS)
def test_every_holder_follows_its_dimensions(name: str) -> None:
    """Eine Parameteränderung wirkt: breiter und höher heißt breiter und höher gebaut."""
    first = "diameter" if name == "holder_ring" else "width"
    narrow = _holder(name, mount="clamp", **{first: 30.0}, height=40.0)
    wide = _holder(name, mount="clamp", **{first: 50.0}, height=60.0)
    assert wide.mesh.bounds.size[0] == pytest.approx(narrow.mesh.bounds.size[0] + 20.0)
    assert wide.mesh.bounds.size[2] > narrow.mesh.bounds.size[2]


# --- Suche nach Kundenwörtern (RM-017) ---------------------------------------------

#: Die Wörter, unter denen ein Kunde die Nutfeder sucht, je Sprache. „Nutenstein“
#: und „T-Nut“ fanden sie nicht: Das erste stand nirgends, das zweite zerfiel in
#: zwei Wörter unter der Mindestlänge. In den übrigen Sprachen traf die Mutter in
#: T-Form („tuerca en T“) nur die Mutternfalle.
CUSTOMER_WORDS_FOR_THE_TONGUE: tuple[tuple[str, str], ...] = (
    ("de", "Nutenstein"),
    ("de", "T-Nut"),
    ("de", "Aluprofil"),
    ("de", "Alu-Profil"),
    ("de", "Profil"),
    ("de", "Nutfeder"),
    ("en", "T-nut"),
    ("en", "T-slot"),
    ("en", "aluminium extrusion"),
    ("es", "tuerca en T"),
    ("es", "perfil de aluminio"),
    ("fr", "écrou en T"),
    ("fr", "profilé aluminium"),
    ("it", "dado a T"),
    ("it", "profilato di alluminio"),
    ("pt", "porca em T"),
    ("pt", "perfil de alumínio"),
)


@pytest.mark.parametrize(("language", "word"), CUSTOMER_WORDS_FOR_THE_TONGUE)
def test_the_tongue_is_found_under_the_words_customers_use(language: str, word: str) -> None:
    """Die Bausteinsuche liest Titel und Beschreibung in der Sprache der Oberfläche."""
    from app.i18n import get_language, set_language
    from app.i18n.catalog import install_language

    previous = get_language()
    if language != "de":
        install_language(language)
    set_language(language)
    try:
        found = [spec.name for spec in PARTS.search(word)]
    finally:
        set_language(previous)
    assert "profile_tongue" in found, f"[{language}] „{word}“ fand {found}"


def test_a_hyphenated_word_counts_whole_and_by_its_parts() -> None:
    """„T-Nut“ zählt als ein Wort, „Alu-Profil“ zusätzlich über „Profil“."""
    whole = {spec.name for spec in PARTS.search("T-Nut")}
    assert whole == {"profile_tongue"}, "nur die Nutfeder nennt die T-Nut"
    parts = {spec.name for spec in PARTS.search("Alu-Profil")}
    assert parts == {spec.name for spec in PARTS.search("Profil")}
    assert {spec.name for spec in PARTS.search("qwertz-uiop")} == set()


# --- RM-184: Bausteine aus dem Dateiaudit -------------------------------------------
#
# Je Baustein der Bezug zur Auditdatei und die Prüfung in Einbaulage: Ein Paar
# wird zusammengesetzt und über seinen Weg bewegt, eine Aufnahme mit ihrem
# Gegenstück gefüllt. Zwei einzeln gültige Körper belegen noch keine Passung
# (Skill ``neuer-baustein``, „Spiel und Passung“).


def _overlap(first: Any, second: Any) -> float:
    """Wie viel Volumen zwei Körper gemeinsam haben — null, wenn sie sich nicht treffen."""
    outcome = boolean("intersection", [as_mesh_data(first), as_mesh_data(second)], allow_empty=True)
    return float(outcome.mesh.volume)


def _touching(first: Any, second: Any) -> float:
    """Die Schranke für „berührt nur“: Rechenrauschen über beiden Oberflächen."""
    from app.core.units import EPS_GEOM

    return EPS_GEOM * (as_mesh_data(first).raw.area + as_mesh_data(second).raw.area)


def _rod(diameter: float, length: float, start: float, axis: str) -> Any:
    """Eine runde Stange ab ``start`` entlang einer Achse, auf der Achshöhe null."""
    body = shapes.moved(shapes.cylinder(diameter, length), (0.0, 0.0, start))
    if axis == "x":
        return shapes.turned(body, 90.0, (0.0, 1.0, 0.0))
    return body


@pytest.mark.parametrize("layout", ["elbow", "tee", "corner_3d", "cross"])
def test_rods_of_the_plant_stand_meet_at_their_stops_without_touching(
    layout: str, profile: Profile
) -> None:
    """Pflanzen-Ständerset (Audit Familie 5): Ø 16, Einstecktiefe 42, Wand 3.

    Jede Stange geht bis zum Anschlag hinein und nicht weiter; die Enden
    zweier Stangen berühren sich in keiner Bauform. Im Quellskript lag der
    Anschlag 6 mm hinter der Mitte bei 8,45 mm Bohrungsradius — in der Ecke
    stießen zwei Stangenenden ineinander.
    """
    from app.core.knowledge.parts.rods import ROD_LAYOUTS, rod_hub

    play = profile.material.clearance
    spec = PARTS.get("rod_connector")
    params = spec.params(layout=layout, rod=16.0, depth=42.0, wall=3.0, play=play)
    built = spec.fn(params)
    body = built.mesh
    hub = rod_hub(params)
    axis_height = (16.0 + play) / 2.0 + 3.0
    rods = []
    for index, direction in enumerate(ROD_LAYOUTS[layout], start=1):
        assert built.features[f"socket_{index}"].params["axis"] == direction
        if direction[2] > 0.5:
            rod = _rod(16.0, 42.0, 2.0 * hub, "z")
        else:
            rod = shapes.moved(_rod(16.0, 42.0, hub, "x"), (0.0, 0.0, axis_height))
            turn = {(1, 0): 0.0, (0, 1): 90.0, (-1, 0): 180.0, (0, -1): 270.0}[
                (round(direction[0]), round(direction[1]))
            ]
            rod = shapes.turned(rod, turn)
        assert _overlap(body, rod) <= _touching(body, rod), f"{layout}: Stange {index} klemmt"
        pushed = shapes.moved(rod, tuple(-0.5 * component for component in direction))
        assert _overlap(body, pushed) > 1.0, f"{layout}: Stange {index} ohne Anschlag"
        rods.append(rod)
    for first, second in itertools.combinations(rods, 2):
        assert _overlap(first, second) <= _touching(first, second), f"{layout}: Stangen stoßen"


def test_a_rod_sleeve_takes_its_clamp_screw_into_the_rod() -> None:
    """Die Klemmschraube schneidet ihr Gewinde in die Wand und drückt auf die Stange.

    Ein Probekörper in der Wand auf halber Einstecktiefe trifft ohne Schraube
    Material und mit Schraube das Kernloch.
    """
    spec = PARTS.get("rod_connector")
    values = {"layout": "sleeve", "rod": 16.0, "depth": 42.0, "wall": 3.0}
    with_screw = spec.fn(spec.params(screw="M5", **values))
    without = spec.fn(spec.params(screw="none", **values))
    screw = with_screw.features["screw_1"]
    assert screw.params["diameter"] == pytest.approx(standards.screw("M5").tap)
    probe = shapes.moved(shapes.cylinder(1.0, 1.0), (9.5, 0.0, 3.0 + 21.0))
    assert _overlap(with_screw.mesh, probe) <= _touching(with_screw.mesh, probe)
    assert _overlap(without.mesh, probe) > 0.5
    assert with_screw.features["socket_1"].params["depth"] == pytest.approx(42.0)


def test_a_rod_screw_thicker_than_the_rod_is_refused_with_advice() -> None:
    from app.core.errors import ValidationError

    spec = PARTS.get("rod_connector")
    params = spec.params(layout="tee", rod=4.0, screw="M5")
    assert spec.feasible is not None and spec.feasible(params) is not None
    with pytest.raises(ValidationError) as caught:
        spec.fn(params)
    assert caught.value.field == "screw"
    assert caught.value.constraint == "feasible"


def test_a_hose_barb_keeps_its_passage_open_through_the_wall(profile: Profile) -> None:
    """Pool-Wasserfall (Audit Familie 2): Schaft Ø 30, Kämme Ø 33, Durchgang Ø 24.

    Auf eine 4-mm-Wand gesetzt reicht der Durchgang von der Rückseite der Wand
    bis zur Spitze; ein Stab, zwei Zehntel enger, geht ganz hindurch, ohne
    Material zu treffen. Bund und Widerhaken sind mit dem Träger ein Körper.
    """
    values = {
        "x": 0.0,
        "y": 0.0,
        "z": 4.0,
        "hose": 30.0,
        "grip": 1.5,
        "count": 4,
        "length": 35.0,
        "wall": 3.0,
        "collar": 3.0,
        "through": 4.0,
    }
    carrier = OperationDraft(op="create_box", params={"width": 60.0, "depth": 60.0, "height": 4.0})
    body = _carrier_with(profile, carrier, "hose_barb", values)
    assert body.mesh.is_watertight and body.mesh.component_count == 1
    passage = next(f for name, f in body.features.items() if name.endswith("passage_1"))
    assert passage.params["diameter"] == pytest.approx(24.0)
    probe = shapes.moved(shapes.cylinder(23.8, 50.0), (0.0, 0.0, -5.0))
    assert _overlap(body.mesh, probe) <= _touching(body.mesh, probe)
    assert float(body.mesh.bounds.maximum[2]) == pytest.approx(4.0 + 3.0 + 35.0, abs=1e-6)


def test_a_hose_slides_over_the_ramps_and_grips_at_the_crests() -> None:
    """Der Schlauch liegt am Schaft an und wird nur an den Kämmen geweitet.

    Ein Schlauch mit dem Innendurchmesser des Schafts überdeckt sich mit der
    Tülle nur an den Widerhaken; mit dem Kammdurchmesser gar nicht mehr. Die
    steile Seite jedes Widerhakens zeigt zum Bund — bei 45 Grad druckt sie ohne
    Stütze —, die Anlaufschräge zur Spitze ist mindestens doppelt so lang.
    """
    from app.core.knowledge.parts.build import subtract as build_subtract
    from app.core.knowledge.parts.channels import hose_barb_outline

    spec = PARTS.get("hose_barb")
    params = spec.params(hose=12.0, grip=1.0, count=3, length=24.0, wall=1.5, collar=3.0)
    barb = spec.host_add(params).mesh

    def hose(inner: float) -> Any:
        tube = shapes.moved(shapes.cylinder(inner + 6.0, 24.0), (0.0, 0.0, 3.0))
        return build_subtract(tube, shapes.moved(shapes.cylinder(inner, 26.0), (0.0, 0.0, 2.0)))

    assert _overlap(barb, hose(12.0)) > 1.0
    wide = hose(14.05)
    assert _overlap(barb, wide) <= _touching(barb, wide)
    outline = hose_barb_outline(params)
    for foot, crest, end in zip(outline[3:-1:2], outline[4::2], outline[5::2], strict=False):
        assert crest[1] - foot[1] == pytest.approx(crest[0] - foot[0])
        assert end[1] - crest[1] > 2.0 * (crest[0] - end[0]) - 1e-9


def test_a_hose_barb_with_crowded_barbs_is_refused_with_advice() -> None:
    from app.core.errors import ValidationError

    spec = PARTS.get("hose_barb")
    params = spec.params(hose=12.0, grip=3.0, count=6, length=10.0)
    assert spec.feasible is not None and spec.feasible(params) is not None
    with pytest.raises(ValidationError):
        spec.fn(params)


def _channel_segment(width: float, height: float, wall: float, length: float) -> Any:
    """Ein Rinnensegment: U-Profil, offen nach oben, entlang +X ab null."""
    from app.core.knowledge.parts.build import subtract as build_subtract

    outer = shapes.moved(shapes.box(length, width, height), (length / 2.0, 0.0, 0.0))
    inside = shapes.moved(
        shapes.box(length + 2.0, width - 2.0 * wall, height), (length / 2.0, 0.0, wall)
    )
    return build_subtract(outer, inside)


def test_two_gutter_segments_meet_in_the_outside_seam_without_a_step(profile: Profile) -> None:
    """CC2-Auffangrinne (Audit Familie 8): Außenbreite 44, Seitenhöhe 25 und Boden 2.

    Beide Segmente gleiten bis zum Steg in die Hülse und nicht weiter. Ein
    Probekörper im Kanalquerschnitt läuft durch Segment, Steg und Segment, ohne
    anzustoßen: Die Naht verengt den Kanal nicht, und es steht keine Stufe
    gegen die Fließrichtung.
    """
    play = profile.material.clearance
    spec = PARTS.get("channel_joint")
    params = spec.params(
        style="outer_sleeve",
        width=44.0,
        height=27.0,
        wall=2.0,
        overlap=18.0,
        thickness=1.2,
        play=play,
    )
    sleeve = spec.fn(params).mesh
    floor = stop = 1.2
    upper = shapes.turned(_channel_segment(44.0, 27.0, 2.0, 60.0), 180.0)
    upper = shapes.moved(upper, (-stop / 2.0, 0.0, floor))
    lower = shapes.moved(_channel_segment(44.0, 27.0, 2.0, 60.0), (stop / 2.0, 0.0, floor))
    for segment in (upper, lower):
        assert _overlap(sleeve, segment) <= _touching(sleeve, segment)
    assert _overlap(sleeve, shapes.moved(lower, (-0.3, 0.0, 0.0))) > 1.0
    channel = shapes.moved(
        shapes.box(100.0, 44.0 - 4.0 - 0.1, 20.0), (0.0, 0.0, floor + 2.0 + 0.05)
    )
    for body in (sleeve, upper, lower):
        assert _overlap(body, channel) <= _touching(body, channel)


def test_the_inside_seam_lies_in_both_segments_and_says_how_much_it_narrows(
    profile: Profile,
) -> None:
    """Die Einlage aus der Rinne: Wange 1,2 mm, Rampe 8 mm, Kante 0,4 mm.

    Sie liegt in beiden Segmenten, ohne sie zu treffen, reicht bis an ihre
    Oberkante, und ihr Befund nennt den Kanal, der an der Naht bleibt.
    """
    play = profile.material.clearance
    spec = PARTS.get("channel_joint")
    params = spec.params(
        style="inner_insert",
        width=44.0,
        height=27.0,
        wall=2.0,
        overlap=18.0,
        thickness=1.2,
        ramp=8.0,
        play=play,
    )
    built = spec.fn(params)
    insert = shapes.moved(built.mesh, (0.0, 0.0, 2.0))
    upper = shapes.turned(_channel_segment(44.0, 27.0, 2.0, 60.0), 180.0)
    lower = _channel_segment(44.0, 27.0, 2.0, 60.0)
    for segment in (upper, lower):
        assert _overlap(insert, segment) <= _touching(insert, segment)
    finding = next(f for f in built.findings if f.code == "parts.channel_narrowed")
    assert finding.values["width_mm"] == pytest.approx(44.0 - 4.0 - play - 2.4)
    assert finding.values["height_mm"] == pytest.approx(27.0 - 2.0 - 1.2)
    bounds = as_mesh_data(built.mesh).bounds
    assert float(bounds.minimum[0]) == pytest.approx(-18.0)
    assert float(bounds.maximum[2]) == pytest.approx(25.0)
    ramp = built.features["ramp_1"]
    assert float(ramp.params["centre"][2]) == pytest.approx((1.2 + 0.4) / 2.0)


def _bayonet_pair(play: float, **values: Any) -> tuple[Any, Any, dict[str, float]]:
    from app.core.knowledge.parts.closures import bayonet_frame

    spec = PARTS.get("bayonet")
    socket = spec.fn(spec.params(kind="socket", play=play, **values)).mesh
    plug_params = spec.params(kind="plug", play=play, **values)
    plug = spec.fn(plug_params).mesh
    frame = bayonet_frame(plug_params)
    # Umgedreht auf die Aufnahme gesetzt: der Fuß des Kragens auf ihrem Rand.
    placed = shapes.moved(shapes.turned(plug, 180.0, (1.0, 0.0, 0.0)), (0.0, 0.0, frame["rim"]))
    return socket, placed, frame


@pytest.mark.parametrize(
    "values",
    [
        # Filterkäfig aus dem Audit: Ø 75, drei Nocken, Einführtiefe 6, Drehweg 13°.
        {
            "diameter": 75.0,
            "lugs": 3,
            "lug_width": 6.0,
            "lug_height": 3.5,
            "entry": 6.0,
            "turn": 13.0,
        },
        {
            "diameter": 24.0,
            "lugs": 2,
            "lug_width": 4.0,
            "lug_height": 2.0,
            "entry": 3.0,
            "turn": 40.0,
        },
    ],
)
def test_a_bayonet_goes_in_axially_then_turns_to_its_stop(
    values: dict[str, Any], profile: Profile
) -> None:
    """Audit Familie 3: erst axial einsetzen, dann über den ganzen Drehweg schließen.

    Geprüft wird der Weg, nicht nur die Endlage: in Schritten von oben bis auf
    den Rand, dann in Schritten um den Drehweg — nirgends Material im Weg.
    Danach hält es: weiter gedreht stößt die Nocke an, gezogen hängt sie am
    Schlitz; in der Einsetzstellung lässt es sich wieder abziehen.
    """
    play = profile.material.clearance
    socket, plug, frame = _bayonet_pair(play, wall=2.0, **values)
    limit = _touching(socket, plug)
    for lift in np.linspace(frame["collar"] + 1.0, 0.0, 6):
        lifted = shapes.moved(plug, (0.0, 0.0, float(lift)))
        assert _overlap(socket, lifted) <= limit, f"eingesetzt bis {lift:.2f} mm: Nocke stößt"
    for angle in np.linspace(0.0, values["turn"], 5):
        turned = shapes.turned(plug, float(angle))
        assert _overlap(socket, turned) <= limit, f"gedreht um {angle:.1f}°: Nocke stößt"
    locked = shapes.turned(plug, values["turn"])
    beyond = shapes.turned(plug, values["turn"] + frame["margin"] + 2.0)
    assert _overlap(socket, beyond) > 0.1, "kein Anschlag am Ende des Drehwegs"
    assert _overlap(socket, shapes.moved(locked, (0.0, 0.0, play))) > 0.01, "hält nicht"
    assert _overlap(socket, shapes.moved(plug, (0.0, 0.0, play))) <= limit


def test_a_bayonet_with_too_many_lugs_for_its_turn_is_refused() -> None:
    from app.core.errors import ValidationError

    spec = PARTS.get("bayonet")
    params = spec.params(diameter=12.0, lugs=4, lug_width=6.0, turn=60.0)
    assert spec.feasible is not None and spec.feasible(params) is not None
    with pytest.raises(ValidationError):
        spec.fn(params)


def _detent_pair(play: float, **values: Any) -> tuple[Any, Any, dict[str, float], Any]:
    from app.core.knowledge.parts.closures import detent_frame

    spec = PARTS.get("detent_disc")
    base_params = spec.params(kind="base", play=play, **values)
    base = spec.fn(base_params).mesh
    disc = spec.fn(spec.params(kind="disc", play=play, **values)).mesh
    frame = detent_frame(base_params)
    # Die Scheibe liegt auf dem Boden der Führung.
    return base, shapes.moved(disc, (0.0, 0.0, base_params.thickness)), frame, base_params


def _probe(radius: float, degrees: float, height: float) -> Any:
    """Ein dünner senkrechter Stab durch Boden und Scheibe an einem Punkt."""
    from app.core.knowledge.parts.closures import polar

    x, y, _z = polar(radius, degrees)
    return shapes.moved(shapes.cylinder(0.6, height + 2.0), (x, y, -1.0))


def test_the_detent_disc_of_the_spice_lid_opens_exactly_one_sector_per_position(
    profile: Profile,
) -> None:
    """Gewürzdeckel (Audit Familie 4): Scheibe Ø 32, 3 mm dick, Zapfen Ø 6, Arme 1,1.

    In jeder Raststellung sitzt die Scheibe ohne Durchdringung: Nase in ihrer
    Mulde, Arme unter dem Kopf. Stellung null ist zu, Stellung k gibt genau die
    Öffnung k frei und deckt die anderen ab. Zwischen zwei Stellungen drückt
    die Nase gegen den Kragen — so rastet sie.
    """
    values = {
        "diameter": 32.0,
        "thickness": 3.0,
        "positions": 3,
        "window": 60.0,
        "post": 6.0,
        "arm": 1.1,
    }
    base, disc, frame, params = _detent_pair(profile.material.clearance, **values)
    limit = _touching(base, disc)
    spacing = frame["spacing"]
    middle = (frame["window_inner"] + frame["window_outer"]) / 2.0
    height = 2.0 * params.thickness
    for position in range(3):
        turned = shapes.turned(disc, position * spacing)
        assert _overlap(base, turned) <= limit, f"Stellung {position}: Scheibe klemmt"
        for opening in range(3):
            probe = _probe(middle, opening * spacing, height)
            through = bool(
                _overlap(base, probe) <= _touching(base, probe)
                and _overlap(turned, probe) <= _touching(turned, probe)
            )
            expected = opening == position and position > 0
            assert through is expected, f"Stellung {position}, Öffnung {opening}"
        between = shapes.turned(disc, (position + 0.5) * spacing)
        assert _overlap(base, between) > 0.01, f"zwischen {position} und {position + 1}: keine Rast"
    assert frame["head"] > frame["arm_inner"], "der Kopf hält die Arme"
    assert frame["hub"] - frame["arm_outer"] >= frame["head"] - frame["arm_inner"], "Federraum"


def test_the_detent_marks_count_the_positions() -> None:
    """Tastbare Marken: Stellung k trägt k + 1 Rippen auf dem Kragen."""
    import math

    from app.core.knowledge.parts.closures import detent_frame
    from app.core.slice.analysis import cross_section

    spec = PARTS.get("detent_disc")
    params = spec.params(kind="base", positions=3, thickness=3.0, arm=1.1, play=0.25)
    base = as_mesh_data(spec.fn(params).mesh)
    frame = detent_frame(params)
    level = 2.0 * 3.0 + 0.25 + 1.1 / 2.0
    section = cross_section(base, level)
    assert section is not None
    ribs = [
        part
        for part in getattr(section, "geoms", [section])
        if math.hypot(part.centroid.x, part.centroid.y) > frame["guide"]
    ]
    assert len(ribs) == 1 + 2 + 3


def _room(profile: Profile, **values: Any) -> dict[str, Any]:
    """Boden, Rückwand und zwei Seitenwände in Raumlage, aus denselben Raummaßen."""
    from app.core.geom import transform

    length, depth, height, wall = (values[key] for key in ("length", "depth", "height", "wall"))
    thickness = values.get("thickness", wall)
    play = profile.material.clearance
    floor_spec, wall_spec = PARTS.get("room_floor"), PARTS.get("room_wall")
    floor = floor_spec.fn(
        floor_spec.params(length=length, depth=depth, thickness=thickness, wall=wall, play=play)
    ).mesh
    back = wall_spec.fn(
        wall_spec.params(
            role="room_back", width=length, height=height, wall=wall, opening_width=0.0, play=play
        )
    ).mesh
    side = wall_spec.fn(
        wall_spec.params(
            role="room_side",
            width=depth,
            height=height,
            wall=wall,
            opening="door",
            opening_width=values.get("door", 0.0),
            opening_height=values.get("door_height", 10.0),
            play=play,
        )
    ).mesh

    def placed(mesh: Any, matrix: list[list[float]]) -> Any:
        raw = as_mesh_data(mesh).raw.copy()
        transform.moved(raw, np.asarray(matrix, dtype=float))
        return MeshData.of(raw)

    # Die Platten liegen, wie sie gedruckt werden: X entlang der Wand, Y nach
    # oben, die Innenseite bei Z = Wandstärke. In Raumlage zeigt die Innenseite
    # der Rückwand nach vorn, die der Seitenwände zur Raummitte; die rechte ist
    # die gespiegelte linke.
    panel = depth - wall
    return {
        "floor": floor,
        "back": placed(
            back, [[1, 0, 0, 0], [0, 0, -1, depth / 2.0], [0, 1, 0, thickness], [0, 0, 0, 1]]
        ),
        "left": placed(
            side,
            [
                [0, 0, 1, -length / 2.0],
                [1, 0, 0, -depth / 2.0 + panel / 2.0],
                [0, 1, 0, thickness],
                [0, 0, 0, 1],
            ],
        ),
        "right": placed(
            side,
            [
                [0, 0, -1, length / 2.0],
                [1, 0, 0, -depth / 2.0 + panel / 2.0],
                [0, 1, 0, thickness],
                [0, 0, 0, 1],
            ],
        ),
    }


@pytest.mark.parametrize(
    "values",
    [
        # Puppenhaus 1:10 aus dem Audit: Raum 240, Wand 4, Tür 90 breit, 200 hoch.
        {
            "length": 240.0,
            "depth": 240.0,
            "height": 240.0,
            "wall": 4.0,
            "door": 90.0,
            "door_height": 200.0,
        },
        {"length": 120.0, "depth": 90.0, "height": 80.0, "wall": 2.0},
    ],
)
def test_a_room_of_panels_goes_together_tongue_in_groove(
    values: dict[str, Any], profile: Profile
) -> None:
    """Puppenhaus (Audit, DOCX ID 110): flach gedruckte Platten, gesteckt.

    Boden, Rückwand und beide Seitenwände aus denselben Raummaßen stehen
    ineinander, ohne sich zu durchdringen; jede Wand steht auf dem Boden, jede
    Seitenwand an der Rückwand. Außen messen die Wände genau Raumlänge und
    Raumtiefe.
    """
    room = _room(profile, **values)
    for (first_name, first), (second_name, second) in itertools.combinations(room.items(), 2):
        assert _overlap(first, second) <= _touching(first, second), f"{first_name}/{second_name}"
    for name in ("back", "left", "right"):
        lowered = shapes.moved(room[name], (0.0, 0.0, -0.1))
        assert _overlap(room["floor"], lowered) > 0.1, f"{name} schwebt"
    for name in ("left", "right"):
        pushed = shapes.moved(room[name], (0.0, 0.1, 0.0))
        assert _overlap(room["back"], pushed) > 0.01, f"{name} ohne Anschlag an der Rückwand"
    assert float(room["left"].bounds.minimum[0]) == pytest.approx(-values["length"] / 2.0)
    assert float(room["right"].bounds.maximum[0]) == pytest.approx(values["length"] / 2.0)
    assert float(room["back"].bounds.maximum[1]) == pytest.approx(values["depth"] / 2.0)


def test_a_window_pane_fits_its_rebate_and_cannot_fall_through() -> None:
    """Fenster 100 breit, 120 hoch aus dem Puppenhausplan: Die Scheibe liegt im Falz.

    Sie ist um das Spiel kleiner als der Falz und um zwei Falzbreiten größer
    als die Öffnung — eingelegt berührt sie nichts, und durchfallen kann sie
    nicht.
    """
    spec = PARTS.get("room_wall")
    values = {
        "width": 240.0,
        "height": 240.0,
        "wall": 4.0,
        "opening_width": 100.0,
        "opening_height": 120.0,
    }
    wall = spec.fn(spec.params(role="room_back", opening="window", play=0.25, **values))
    pane_spec = PARTS.get("room_pane")
    pane = pane_spec.fn(
        pane_spec.params(opening_width=100.0, opening_height=120.0, wall=4.0, play=0.25)
    ).mesh
    low = (240.0 - 120.0) / 2.0
    seated = shapes.moved(pane, (0.0, low + 60.0, 2.0))
    assert _overlap(wall.mesh, seated) <= _touching(wall.mesh, seated)
    assert _overlap(wall.mesh, shapes.moved(seated, (0.0, 0.0, -0.1))) > 0.1
    assert float(as_mesh_data(pane).bounds.size[0]) == pytest.approx(100.0 + 8.0 - 0.25)


def test_the_rm184_parts_are_found_under_their_customer_words() -> None:
    """Die Wörter aus dem Audit führen zum Baustein."""
    for word, name in (
        ("Bajonett", "bayonet"),
        ("Rastdrehscheibe", "detent_disc"),
        ("Steckhülse", "rod_connector"),
        ("Stangenverbinder", "rod_connector"),
        ("Schlauchtülle", "hose_barb"),
        ("Kanalnaht", "channel_joint"),
        ("Raumboden", "room_floor"),
        ("Raumwand", "room_wall"),
        ("Fensterscheibe", "room_pane"),
    ):
        assert name in {spec.name for spec in PARTS.search(word)}, word


def test_one_rod_parameter_turns_every_socket_of_every_connector(profile: Profile) -> None:
    """Audit Familie 5, Abnahme: Eine Änderung des Stabmaßes wirkt auf jede Aufnahme.

    Zwei Verbinder des Ständersets — T-Stück und Steckhülse — hängen am selben
    Projektparameter. Von 16 auf 20 mm gedreht, wächst jede Bohrung beider
    Teile mit; zwei Strg+Z nehmen Maß und Schritte zurück.
    """
    from app.core.scene.history import change_for
    from app.core.types import Parameter

    project = new_project("centauri-carbon-2", "petg")
    history = History(project.document)
    history.apply(
        "Stangenverbinder",
        [
            OperationDraft(
                op="create_rod_connector", params={"layout": "tee", "rod": "=@stab", "depth": 30.0}
            ),
            OperationDraft(
                op="create_rod_connector",
                params={"layout": "sleeve", "rod": "=@stab", "depth": 30.0},
            ),
        ],
        changes=change_for(
            history.document, parameters={"stab": Parameter(name="stab", value=16.0, unit="mm")}
        ),
    )

    def sockets() -> list[float]:
        result = evaluate(history.document, profile, sources=ProjectSources(project))
        assert result.complete, [str(finding.message) for finding in result.scene.report.findings]
        found = [
            float(feature.params["diameter"])
            for body in result.scene.objects.values()
            for name, feature in body.features.items()
            if "socket_" in name
        ]
        assert len(found) == 3 + 1
        return found

    play = profile.material.clearance
    assert sockets() == pytest.approx([16.0 + play] * 4)
    history.apply(
        "Stab",
        [],
        changes=change_for(
            history.document, parameters={"stab": Parameter(name="stab", value=20.0, unit="mm")}
        ),
    )
    assert sockets() == pytest.approx([20.0 + play] * 4)
    history.undo()
    history.undo()
    assert not history.document.ops and not history.document.parameters


def test_one_room_length_moves_floor_back_wall_and_their_grooves_together(
    profile: Profile,
) -> None:
    """Puppenhaus (Audit, DOCX ID 110), Abnahme: Ein Raummaß bewegt die angrenzenden Platten.

    Boden, Rückwand und Seitenwand hängen an Raumlänge, Raumtiefe, Raumhöhe und
    Wandstärke. Wird die Raumlänge von 240 auf 300 mm gedreht, werden Boden und
    Rückwand um 60 mm länger, die seitlichen Nuten des Bodens rücken mit, und
    die Seitenwand — sie steht entlang der Tiefe — bleibt, wie sie ist.
    """
    from app.core.scene.history import change_for
    from app.core.types import Parameter

    project = new_project("centauri-carbon-2", "petg")
    history = History(project.document)
    sizes = {"raum_l": 240.0, "raum_t": 240.0, "raum_h": 240.0, "wand": 4.0}
    history.apply(
        "Raum",
        [
            OperationDraft(
                op="create_room_floor",
                params={
                    "length": "=@raum_l",
                    "depth": "=@raum_t",
                    "wall": "=@wand",
                    "thickness": "=@wand",
                },
            ),
            OperationDraft(
                op="create_room_wall",
                params={
                    "role": "room_back",
                    "width": "=@raum_l",
                    "height": "=@raum_h",
                    "wall": "=@wand",
                    "opening_width": 0.0,
                },
            ),
            OperationDraft(
                op="create_room_wall",
                params={
                    "role": "room_side",
                    "width": "=@raum_t",
                    "height": "=@raum_h",
                    "wall": "=@wand",
                    "opening": "door",
                    "opening_width": 90.0,
                    "opening_height": 200.0,
                },
            ),
        ],
        changes=change_for(
            history.document,
            parameters={
                name: Parameter(name=name, value=value, unit="mm") for name, value in sizes.items()
            },
        ),
    )

    def measured() -> dict[str, tuple[float, float]]:
        result = evaluate(history.document, profile, sources=ProjectSources(project))
        assert result.complete, [str(finding.message) for finding in result.scene.report.findings]
        floor, back, side = result.scene.objects.values()
        groove = next(f for name, f in floor.features.items() if name.endswith("groove_3"))
        return {
            "floor": (float(floor.mesh.bounds.size[0]), float(groove.params["centre"][0])),
            "back": (float(back.mesh.bounds.size[0]), 0.0),
            "side": (float(side.mesh.bounds.size[0]), 0.0),
        }

    before = measured()
    assert before["floor"][1] == pytest.approx(240.0 / 2.0 - 4.0 / 2.0)
    history.apply(
        "Raumlänge",
        [],
        changes=change_for(
            history.document,
            parameters={"raum_l": Parameter(name="raum_l", value=300.0, unit="mm")},
        ),
    )
    after = measured()
    assert after["floor"][0] == pytest.approx(before["floor"][0] + 60.0)
    assert after["floor"][1] == pytest.approx(before["floor"][1] + 30.0)
    assert after["back"][0] == pytest.approx(before["back"][0] + 60.0)
    assert after["side"][0] == pytest.approx(before["side"][0])
    history.undo()
    assert measured() == before


@pytest.mark.parametrize(
    "values",
    [
        # Die kleinste baubare Tülle: Schlauch 3, ein Widerhaken, kurzer Schaft.
        {"hose": 3.0, "grip": 0.3, "count": 1, "length": 5.0, "wall": 0.8, "collar": 1.0},
        # Die größte: Schlauch 50, sechs Widerhaken, dicke Wand.
        {"hose": 50.0, "grip": 3.0, "count": 6, "length": 80.0, "wall": 6.0, "collar": 10.0},
        # Wasserfall-Tülle aus dem Audit: Schaft 30, Kämme 33, Durchgang 24.
        {"hose": 30.0, "grip": 1.5, "count": 4, "length": 35.0, "wall": 3.0, "collar": 3.0},
    ],
)
def test_the_hose_barb_body_holds_its_wall_at_the_edges_of_its_range(
    values: dict[str, Any], profile: Profile
) -> None:
    """Die Tülle ist Trägeraufbau (``host_add``), und der Bereichsnachweis fährt nur das
    Werkzeug durch die Wand. Ihr Körper wird deshalb hier an den Rändern seines Bereichs
    gemessen: geschlossen, ein Körper, keine Selbstdurchdringung, die Wand zwischen
    Durchgang und Schaft mindestens die eingetragene (höchstens die Profilgrenze)."""
    spec = PARTS.get("hose_barb")
    body = as_mesh_data(spec.host_add(spec.params(**values)).mesh)
    assert body.is_watertight and body.component_count == 1
    assert not has_self_intersections(body)
    wall = local_wall_thickness(body)
    assert wall is not None
    assert wall >= min(values["wall"], profile.minimum_wall_thickness) - 1e-6
