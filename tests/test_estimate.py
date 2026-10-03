"""Die Schätzung ohne Schnitt (Bauplan §22, §29).

Geprüft wird gegen analytische Körper, deren Volumen und Oberfläche man von
Hand ausrechnen kann — ein Würfel, eine Kugel, ein dünnes Blech, ein Stab.

**Und gegen vier gemessene Zahlen.** Der Rest dieser Datei hält die Rechnung an
ihren Rändern; ``test_the_estimate_stays_close_to_what_the_slicer_measured``
hält sie an der Wirklichkeit. Die Werte darin kommen aus einem Lauf gegen
PrusaSlicer 2.9.6 mit abgeschalteter Haftung — ohne diesen Test war die
Schätzung fünf bis zweiundzwanzig Prozent zu hoch, ohne dass eine Zeile davon
wusste.

Der Test daneben, ``test_a_frame_costs_far_more_than_a_block_of_the_same_size``,
hält die andere Hälfte: Es gab einen Zwischenstand, der die Schale aus den
Hüllmaßen rechnete und damit die vier Körper hier auf zwei Prozent traf — und
bei zwei Regalteilen 41 und 49 Prozent zu niedrig lag, weil ein Hüllquader
einen Rahmen für einen Klotz hält.
"""

from __future__ import annotations

import dataclasses

import pytest

from app.core.knowledge import print_settings, profiles
from app.core.slice.estimate import core_share, estimate, flow_rate, shell_thickness, total

#: Ein Würfel von 20 mm — der Körper, an dem jede Druckerrechnung anfängt.
CUBE = (20.0**3, 6 * 20.0**2)


@pytest.fixture
def settings() -> object:
    """Die aufgelösten Einstellungen für den Vorgabedrucker."""
    profile = profiles.make_profile(profiles.DEFAULT_PRINTER, profiles.DEFAULT_MATERIAL)
    return print_settings.resolve(profile)


def test_a_solid_block_never_needs_more_than_it_is(settings: object) -> None:
    """Ein Würfel von 20 mm ist 8 cm³ — mehr kann nicht hineingehen.

    Der Fall, an dem eine Schätzung als Erstes kippt: Käme die Schale aus
    „Fläche mal Dicke", wäre sie bei einem kleinen, kompakten Körper dicker als
    der Körper selbst. Als Differenz zweier Körper kann das nicht passieren —
    und das ist der Grund, warum die Deckelung von früher verschwunden ist.
    """
    result = estimate(*CUBE, settings)  # type: ignore[arg-type]

    assert result.material_mm3 <= CUBE[0], "nie mehr Material als Volumen"
    assert result.material_mm3 > 0.0
    assert result.grams > 0.0
    assert result.seconds > 0.0


def test_a_hollow_body_costs_more_than_its_volume_suggests(settings: object) -> None:
    """Der Grund, warum überhaupt zwischen Schale und Kern getrennt wird.

    Zwei Körper mit demselben Volumen: ein kompakter Würfel und ein Gehäuse,
    das dieselbe Masse auf die dreifache Kantenlänge verteilt. „Volumen mal
    Dichte" hielte sie für gleich teuer — der große ist es nicht, weil bei ihm
    fast alles Schale ist.
    """
    compact = estimate(*CUBE, settings)  # type: ignore[arg-type]
    gehaeuse = estimate(CUBE[0], 6 * 60.0**2, settings)  # type: ignore[arg-type]

    assert gehaeuse.material_mm3 > compact.material_mm3
    assert gehaeuse.grams > compact.grams


def test_a_thin_sheet_is_printed_solid(settings: object) -> None:
    """Ein Blech, dünner als seine Deckel, hat keine Füllung.

    Dann ist das Material genau das Volumen — nicht mehr (das wäre unmöglich)
    und nicht weniger (dünner als die Deckellagen wird nichts hohl gedruckt).
    """
    volume = 100.0 * 100.0 * 0.6

    result = estimate(volume, 2 * 100.0 * 100.0, settings)  # type: ignore[arg-type]

    assert result.material_mm3 == pytest.approx(volume)


def test_more_infill_costs_more(settings: object) -> None:
    """Die Fülldichte muss durchschlagen, sonst rechnet sie niemand."""
    body = (50.0**3, 6 * 50.0**2)
    sparse = dataclasses.replace(
        settings,  # type: ignore[type-var]
        infill=dataclasses.replace(settings.infill, density=0.1),  # type: ignore[attr-defined]
    )
    dense = dataclasses.replace(
        settings,  # type: ignore[type-var]
        infill=dataclasses.replace(settings.infill, density=0.9),  # type: ignore[attr-defined]
    )

    assert estimate(*body, dense).material_mm3 > estimate(*body, sparse).material_mm3


def test_nothing_costs_nothing(settings: object) -> None:
    """Ein leeres Ergebnis ist keine Null-Division und kein Fehler.

    Der Fall tritt bei jedem neuen Projekt ein — die Anzeige fragt, bevor
    etwas da ist.
    """
    empty = estimate(0.0, 0.0, settings)  # type: ignore[arg-type]
    assert (empty.material_mm3, empty.grams, empty.seconds) == (0.0, 0.0, 0.0)

    assert total([], settings).seconds == 0.0  # type: ignore[arg-type]


def test_two_bodies_cost_more_than_one(settings: object) -> None:
    """Summiert wird das Ergebnis, nicht die Eingabe.

    Zwei getrennte Körper haben zusammen mehr Schale als einer mit demselben
    Volumen — jeder bekommt seine eigene.
    """
    one = total([CUBE], settings)  # type: ignore[arg-type]
    two = total([CUBE] * 2, settings)  # type: ignore[arg-type]

    assert two.material_mm3 == pytest.approx(2 * one.material_mm3)
    assert two.seconds == pytest.approx(2 * one.seconds)


def test_the_flow_never_exceeds_what_the_filament_allows(settings: object) -> None:
    """Der Volumenstrom ist die Grenze, die kein Feld zeigt (§29).

    Eine Zeitschätzung, die darüber hinausrechnet, verspricht einen Druck,
    den die Maschine nicht liefert.
    """
    fast = dataclasses.replace(
        settings,  # type: ignore[type-var]
        speed=dataclasses.replace(settings.speed, infill=10_000.0),  # type: ignore[attr-defined]
    )
    assert flow_rate(fast) <= fast.filament.max_flow


def test_the_shell_follows_the_wall_count(settings: object) -> None:
    """Mehr Wände heißt dickere Schale — sonst ist die Zahl Zierde."""
    thick = dataclasses.replace(
        settings,  # type: ignore[type-var]
        shell=dataclasses.replace(settings.shell, wall_count=6),  # type: ignore[attr-defined]
    )
    assert shell_thickness(thick) > shell_thickness(settings)  # type: ignore[arg-type]
    assert core_share(*CUBE, thick) < core_share(*CUBE, settings)  # type: ignore[arg-type]


def test_a_frame_costs_far_more_than_a_block_of_the_same_size(settings: object) -> None:
    """Der Test, der über das Modell entschieden hat.

    Ein Regalteil ist ein flacher Rahmen aus dünnen Stegen: dasselbe Hüllmaß
    wie ein Klotz, ein Bruchteil des Volumens, und **viel** mehr Oberfläche.
    Ein Zwischenstand rechnete die Schale aus den Hüllmaßen und hielt den
    Rahmen für einen flachen Klotz — gemessen lag er damit bei zwei
    Regalteilen 41 und 49 Prozent zu niedrig.

    Über die mittlere Wanddicke ``3V/A`` kann das nicht passieren: Ein Rahmen
    aus 3 mm Stegen hat eine mittlere Dicke von 3 mm, und davon bleibt hinter
    1,26 mm Wand fast nichts als Kern übrig.
    """
    # 160 auf 231 auf 14, Stege von 3 mm — die Maße des Regalfußes.
    rahmen = estimate(52_000.0, 62_000.0, settings)  # type: ignore[arg-type]
    klotz = estimate(52_000.0, 9_000.0, settings)  # type: ignore[arg-type]

    # 89 Prozent des Volumens sind Schale — der Kern ist bei 2,5 mm mittlerer
    # Dicke hinter 1,26 mm Wand fast weg.
    assert rahmen.material_mm3 > 0.85 * 52_000.0, "ein Rahmen ist fast ganz Schale"
    assert rahmen.material_mm3 > 2.0 * klotz.material_mm3


def test_the_estimate_stays_close_to_what_the_slicer_measured(settings: object) -> None:
    """Vier Körper, vier Messungen — der einzige Test hier, der die Rechnung an
    der Wirklichkeit hält.

    Gemessen mit PrusaSlicer 2.9.6 auf einem Elegoo Centauri Carbon 2, PETG,
    Haftung ausgeschaltet, damit der Skirt die Zahl nicht mitträgt. Die
    Schätzung darf abweichen — sie kennt keine Fahrwege und keine Nahtstellen —,
    aber nicht um ein Sechstel: Genau das war der Stand, als die Schale als
    „Fläche mal Dicke" gerechnet wurde.

    | Körper | gemessen | vorher | jetzt |
    |---|---|---|---|
    | Würfel 20 mm | 4,15 g | +15 % | +5,9 % |
    | Kugel r 15 | 6,21 g | +5 % | +0,1 % |
    | Blech 60 auf 60 auf 2 | 8,61 g | +6 % | -9,0 % |
    | Stab 120 auf 12 auf 12 | 9,43 g | +22 % | +9,9 % |

    Die Schwelle steht bei zwölf Prozent und nicht bei fünf: Was der Slicer aus
    einem Körper macht, hängt an Dingen, die Solidon bewusst nicht nachbaut
    (§22) — Nahtstellen, Lückenfüllung, die Frage, ob die dritte Wand in einen
    12-mm-Querschnitt noch hineinpasst. Was sie **nicht** durchlässt, ist der
    Aufschlag von vorher: der lag bei allen vier auf derselben Seite.
    """
    petg = profiles.make_profile("centauri-carbon-2", "petg")
    fein = dataclasses.replace(
        print_settings.resolve(petg),
        adhesion=dataclasses.replace(print_settings.resolve(petg).adhesion, kind="none"),
    )
    gemessen = (
        ("Würfel", 8000.0, 2400.0, 4.15),
        ("Kugel", 14107.0, 2824.0, 6.21),
        ("Blech", 7200.0, 7680.0, 8.61),
        ("Stab", 17280.0, 6048.0, 9.43),
    )

    for name, volume, area, gramm in gemessen:
        result = estimate(volume, area, fein)
        abweichung = result.grams / gramm - 1.0
        assert abs(abweichung) < 0.12, f"{name}: {result.grams:.2f} g gegen {gramm:.2f} g gemessen"


def _plate_part(name, position=(0.0, 0.0, 0.0), settings=None):
    """Ein 2-mm-Würfel auf dem Bett mit ausdrücklich gewähltem Druckraster."""
    import trimesh

    from app.core.geom.mesh import MeshData
    from app.core.types import SceneObject

    mesh = trimesh.creation.box(extents=(2.0, 2.0, 2.0))
    mesh.apply_translation((position[0], position[1], 1.0 + position[2]))
    body = MeshData.of(mesh)
    return SceneObject(id=name, name=name, mesh=body), body, settings


def test_plate_comparison_counts_the_first_layer_and_shared_model_raster():
    """0,6 mm erste Lage, danach 0,4 mm: belegte Mitten 0,3/0,8/1,2/1,6 mm."""
    from app.core.slice.estimate import plate_comparison

    profile = profiles.make_profile()
    settings = print_settings.resolve(profile)
    settings = dataclasses.replace(
        settings,
        layers=dataclasses.replace(settings.layers, first_layer_height=0.6, layer_height=0.4),
    )
    parts = [_plate_part("one", settings=settings), _plate_part("two", (5.0, 0.0, 0.0), settings)]
    actual = plate_comparison(3, parts, profile, keep_arrangement=True, separate_objects=True)
    assert actual.plate == 3
    assert actual.model_layer_count == 4
    assert actual.support_material_mm3 == pytest.approx(0.0)


def test_plate_comparison_grounds_separate_objects_before_counting_layers():
    """Ein verschobenes 3MF-Objekt wird beim Anordnen abgesetzt, kein zweites Raster erfunden."""
    from app.core.slice.estimate import plate_comparison

    profile = profiles.make_profile()
    settings = print_settings.resolve(profile)
    settings = dataclasses.replace(
        settings,
        layers=dataclasses.replace(settings.layers, first_layer_height=0.6, layer_height=0.4),
    )
    parts = [_plate_part("one", settings=settings), _plate_part("two", (0.0, 0.0, 17.0), settings)]
    actual = plate_comparison(0, parts, profile, keep_arrangement=False, separate_objects=True)
    assert actual.model_layer_count == 4


def test_plate_comparison_unites_printed_heights_instead_of_section_centres():
    """0,2-mm-Erstlage plus 0,2/0,1-mm-Raster teilen 19 Druckhöhen bis 2 mm."""
    from app.core.slice.estimate import plate_comparison

    profile = profiles.make_profile()
    settings = print_settings.resolve(profile)
    coarse = dataclasses.replace(
        settings,
        layers=dataclasses.replace(settings.layers, first_layer_height=0.2, layer_height=0.2),
    )
    fine = dataclasses.replace(
        settings,
        layers=dataclasses.replace(settings.layers, first_layer_height=0.2, layer_height=0.1),
    )
    actual = plate_comparison(
        0,
        [_plate_part("coarse", settings=coarse), _plate_part("fine", (5.0, 0.0, 0.0), fine)],
        profile,
        keep_arrangement=True,
        separate_objects=True,
    )
    # Druckhöhen 0,2; 0,3; …; 2,0: (2,0-0,2)/0,1+1=19.
    # Die Schnittmitten0,1;0,3;… und0,1;0,25;0,35;… teilen dieses Raster nicht.
    assert actual.model_layer_count == 19


def test_plate_comparison_does_not_accept_an_advice_zero_as_support_measurement(monkeypatch):
    """Die vollständige Analyse wird ausdrücklich angefordert; Advice-Nullen reisen nicht mit."""
    from app.core.slice import findings
    from app.core.slice.estimate import plate_comparison
    from app.core.types import SliceResult

    profile = profiles.make_profile()
    settings = print_settings.resolve(profile)
    settings = dataclasses.replace(
        settings, support=dataclasses.replace(settings.support, style="normal", density=0.15)
    )
    calls = []

    def full(mesh, actual_settings, angle, wall, *, cancelled):
        calls.append((mesh, actual_settings))
        return SliceResult((), 100.0, 4.0)

    monkeypatch.setattr(findings, "analysed", full)
    actual = plate_comparison(
        0,
        [_plate_part("one", settings=settings)],
        profile,
        keep_arrangement=True,
        separate_objects=True,
    )
    assert len(calls) == 1
    assert actual.support_material_mm3 == pytest.approx(15.0)


def test_plate_comparison_uses_one_common_support_column(monkeypatch):
    """Zwei Netze derselben Platte werden gemeinsam analysiert, nicht zwei Säulen addiert."""
    from app.core.slice import findings
    from app.core.slice.estimate import plate_comparison
    from app.core.types import SliceResult

    profile = profiles.make_profile()
    settings = print_settings.resolve(profile)
    settings = dataclasses.replace(
        settings, support=dataclasses.replace(settings.support, style="normal", density=0.2)
    )
    triangles = []

    def full(mesh, actual_settings, angle, wall, *, cancelled):
        triangles.append(mesh.triangle_count)
        return SliceResult((), 100.0, 4.0)

    monkeypatch.setattr(findings, "analysed", full)
    actual = plate_comparison(
        0,
        [_plate_part("one", settings=settings), _plate_part("two", settings=settings)],
        profile,
        keep_arrangement=True,
        separate_objects=False,
    )
    assert triangles == [24]
    assert actual.support_material_mm3 == pytest.approx(20.0)


def test_plate_comparison_measures_a_real_mushroom_and_unites_duplicate_columns():
    """Der 8×8-Hut über einem 2×2-Stiel braucht Stützen; zwei gleiche Netze nicht doppelt."""
    import trimesh

    from app.core.geom.mesh import MeshData, concatenated
    from app.core.slice.estimate import plate_comparison
    from app.core.types import SceneObject

    profile = profiles.make_profile()
    settings = print_settings.resolve(profile)
    settings = dataclasses.replace(
        settings, support=dataclasses.replace(settings.support, style="normal", density=0.2)
    )
    stem = trimesh.creation.box(extents=(2.0, 2.0, 4.0))
    stem.apply_translation((0.0, 0.0, 2.0))
    cap = trimesh.creation.box(extents=(8.0, 8.0, 2.0))
    cap.apply_translation((0.0, 0.0, 5.0))
    mesh = MeshData.of(concatenated([stem, cap]))
    part = (SceneObject(id="mushroom", name="Pilz", mesh=mesh), mesh, settings)
    first = plate_comparison(0, [part], profile, keep_arrangement=True, separate_objects=False)
    second = plate_comparison(
        0, [part, part], profile, keep_arrangement=True, separate_objects=False
    )
    # Die äußerste Hülle der senkrechten Säule ist (8²-2²)*4 mm³;
    # das Mittenraster kann höchstens eine Schichthöhe darüber liegen.
    # Eine ausgelassene Analyse
    # oder doppelte Säule fällt außerhalb dieses analytischen Intervalls.
    assert (
        0.5 * (64.0 - 4.0) * 4.0 * 0.2
        < first.support_material_mm3
        < (64.0 - 4.0) * (4.0 + settings.layers.layer_height) * 0.2
    )
    assert second.support_material_mm3 == pytest.approx(first.support_material_mm3)
    assert second.model_layer_count == first.model_layer_count


def test_plate_comparison_keeps_different_overlapping_support_contracts_unknown():
    """Teilwerte dürfen nicht durch einen scheinbar passenden Plattenwert ersetzt werden."""
    from app.core.slice.estimate import plate_comparison

    profile = profiles.make_profile()
    settings = print_settings.resolve(profile)
    enabled = dataclasses.replace(
        settings, support=dataclasses.replace(settings.support, style="normal")
    )
    actual = plate_comparison(
        0,
        [_plate_part("one", settings=settings), _plate_part("two", settings=enabled)],
        profile,
        keep_arrangement=True,
        separate_objects=False,
    )
    assert actual.support_material_mm3 is None
    assert actual.support_reason
    assert actual.model_layer_count is not None


def test_plate_comparison_cancellation_publishes_no_partial_snapshot():
    """Ein Abbruch ist weder bekannte Null noch ein vollständiger Vergleich."""
    from app.core.errors import OperationCancelled
    from app.core.scene.cancel import CancelSignal
    from app.core.slice.estimate import plate_comparison

    cancelled = CancelSignal()
    cancelled.cancel()
    with pytest.raises(OperationCancelled):
        plate_comparison(
            0,
            [],
            profiles.make_profile(),
            keep_arrangement=True,
            separate_objects=True,
            cancelled=cancelled,
        )


@pytest.mark.parametrize(
    "expected,measured,code",
    [
        (0.0, 0.0, "gcode.plate_comparison"),
        (10.0, 0.0, "gcode.plate_deviation"),
        (10.0, None, "gcode.plate_comparison_unknown"),
    ],
)
def test_plate_findings_distinguish_known_zero_and_missing_measurement(expected, measured, code):
    """Nur None fehlt; der Nachweis von null Stützmaterial darf eine Warnung auslösen."""
    from app.core.errors import OPEN_PRINT_SETTINGS
    from app.core.slice.estimate import PlateComparison, plate_findings
    from app.core.slice.gcode import GcodeMetrics

    findings = plate_findings(
        PlateComparison(3, expected, 4), GcodeMetrics(support_mm3=measured, model_layer_count=4)
    )
    assert findings[0].code == code
    assert findings[0].values["plate"] == 4
    assert findings[0].values["estimated_source"] == "internal"
    assert findings[0].values["measured_source"] == "gcode"
    assert "Platte 4" in str(findings[0].message)
    assert findings[0].suggestions == (
        (OPEN_PRINT_SETTINGS,) if code == "gcode.plate_deviation" else ()
    )
    assert findings[1].code == "gcode.plate_comparison"
    assert findings[1].suggestions == ()


def test_plate_findings_preserve_selected_plate_order_and_reject_partial_mapping():
    """Platte 4 vor Platte 2, ohne Summieren oder stilles Abschneiden."""
    from app.core.slice.estimate import PlateComparison, plates_findings
    from app.core.slice.gcode import GcodeMetrics

    expected = (PlateComparison(3, 0.0, 4), PlateComparison(1, 20.0, 8))
    measured = (
        GcodeMetrics(support_mm3=0.0, model_layer_count=4),
        GcodeMetrics(support_mm3=20.0, model_layer_count=8),
    )
    findings = plates_findings(expected, measured, (False, False))
    assert [finding.values["plate"] for finding in findings] == [4, 4, 2, 2]
    assert all(finding.code == "gcode.plate_comparison" for finding in findings)
    assert len(plates_findings(expected, measured[:1], (False,))) == 1
    assert (
        plates_findings(expected, measured[:1], (False,))[0].code
        == "gcode.plate_comparison_unknown"
    )


@pytest.mark.parametrize("thresholds", [(70.0,), (70.0, 70.0), (70.0, 50.0)])
def test_plate_comparison_uses_exported_angles_despite_material_calibration(
    monkeypatch, thresholds
):
    """Wirksame Teilwinkel erreichen den Schnitt; Materialproben bestimmen weiter die Wand."""
    from app.core.export import handover
    from app.core.slice import findings
    from app.core.slice.estimate import plate_comparison

    profile = profiles.make_profile()
    settings = print_settings.resolve(profile)
    settings = print_settings.with_path(settings, "support.style", "normal")
    material = dataclasses.replace(
        profile.material,
        calibrated=True,
        overhang_angle=30.0,
        minimum_wall=0.73,
        calibration_printer=profile.printer.id,
        calibration_nozzle_diameter=profile.printer.nozzle_diameter,
        calibration_layer_height=settings.layers.layer_height,
        calibration_extrusion_width=settings.layers.line_width,
    )
    other_material = dataclasses.replace(
        material, id="other-calibrated-material", overhang_angle=60.0, minimum_wall=0.93
    )
    profile = dataclasses.replace(profile, material=material)
    original_material = profiles.material
    monkeypatch.setattr(
        profiles,
        "material",
        lambda identifier: (
            other_material if identifier == other_material.id else original_material(identifier)
        ),
    )
    parts = []
    for index, threshold in enumerate(thresholds):
        effective = print_settings.with_path(settings, "support.threshold_angle", threshold)
        entry, mesh, _settings = _plate_part(str(index), (index * 5.0, 0.0, 0.0), effective)
        if index:
            entry = dataclasses.replace(entry, material=other_material.id)
        process = profiles.for_process(profile, effective, effective=True)
        wall, calibrated_angle = profiles.analysis_limits(process, entry)
        assert calibrated_angle == pytest.approx(60.0 if index else 30.0)
        assert wall == pytest.approx(0.93 if index else 0.73)
        assert float(handover.as_mapping(effective, "prusa")["support_material_threshold"]) == (
            pytest.approx(90.0 - threshold)
        )
        parts.append((entry, mesh, effective))

    calls = []
    original_slice = findings.slice_body

    def actual_slice(mesh, *args, **kwargs):
        calls.append((mesh.triangle_count, kwargs["overhang_angle"], kwargs["bridge_from"]))
        return original_slice(mesh, *args, **kwargs)

    monkeypatch.setattr(findings, "slice_body", actual_slice)
    result = plate_comparison(0, parts, profile, keep_arrangement=True, separate_objects=True)
    expected = [(12 * len(parts), thresholds[0], 0.93 if len(parts) > 1 else 0.73)]
    if len(set(thresholds)) > 1:
        expected += [
            (12, threshold, 0.93 if index else 0.73) for index, threshold in enumerate(thresholds)
        ]
    assert len(calls) == len(expected)
    for actual, wanted in zip(calls, expected, strict=True):
        assert actual == pytest.approx(wanted)
    assert result.model_layer_count is not None
    assert result.support_material_mm3 == pytest.approx(0.0)


@pytest.mark.parametrize("role", ["support", "known_zero", "purge_zero", "purge_support"])
def test_plate_findings_respect_conditional_support_without_losing_known_amounts(role):
    """Bedingte Stütze bleibt unbekannt; eine reine Spülunsicherheit ändert die Stütze nicht."""
    import math

    from app.core.slice import gcode
    from app.core.slice.estimate import PlateComparison, plate_findings

    conditional = "M622 J1\n{}M623\n"
    commands = ""
    total_mm = 20.0
    support_mm3 = 0.0
    if role == "support":
        commands = conditional.format(";TYPE:Support\nG1 X10 E10\n")
        total_mm += 10.0
        support_mm3 = 10.0 * math.pi
    elif role.startswith("purge"):
        commands = conditional.format("; FLUSH_START\nG1 E10\n; FLUSH_END\n")
        total_mm += 10.0
        if role == "purge_support":
            commands += ";TYPE:Support\nG1 X10 E10\n"
            total_mm += 10.0
            support_mm3 = 10.0 * math.pi
    measured = gcode.analyze(
        "; generated by BambuStudio 2.0\nM83\nG0 X0 Y0 Z.2\n;LAYER_CHANGE\n"
        + commands
        + ";TYPE:Outer wall\nG1 X30 E20\n",
        diameters=(2.0,),
        densities=(1.0,),
    ).metrics
    if role == "support":
        assert measured.support_mm3 is None
    else:
        assert measured.support_mm3 == pytest.approx(support_mm3)
    expected_roles = ("support",) if role == "support" else (("purge",) if commands else ())
    assert measured.uncertain_material_roles == expected_roles
    assert measured.filament_mm == pytest.approx(total_mm)

    expected = PlateComparison(0, 0.0 if role == "support" else support_mm3, 1)
    support, layers = plate_findings(expected, measured)
    assert support.source == "gcode"
    assert support.values["estimated_source"] == "internal"
    assert support.values["measured_source"] == "gcode"
    if role == "support":
        assert support.code == "gcode.plate_comparison_unknown"
        assert "measured" not in support.values
        assert str(support.values["reason"]) == (
            "Die Druckdatei weist die vollständige Stützmenge nicht eindeutig aus."
        )
    else:
        assert support.code == "gcode.plate_comparison"
        assert support.values["measured"] == pytest.approx(support_mm3)
    assert layers.code == "gcode.plate_comparison"
    assert measured.material_cm3_by_role["support"][0] == pytest.approx(support_mm3 / 1000.0)
    assert measured.filament_mm == pytest.approx(total_mm), "Die Gesamtbuchung bleibt erhalten"


def test_plate_findings_do_not_trust_synthetic_uncertain_support_total():
    """Auch zusammengefasste oder fremd erzeugte Kennzahlen behalten ihre Unsicherheit."""
    from app.core.slice import gcode
    from app.core.slice.estimate import PlateComparison, plate_findings

    measured = gcode.GcodeMetrics(
        support_mm3=123.0, model_layer_count=1, uncertain_material_roles=("support",)
    )
    support, layers = plate_findings(PlateComparison(0, 123.0, 1), measured)
    assert support.code == "gcode.plate_comparison_unknown"
    assert "measured" not in support.values
    assert layers.code == "gcode.plate_comparison"
    assert measured.support_mm3 == pytest.approx(123.0)


@pytest.mark.parametrize(
    "commands, expected_layers",
    [
        ("G0 Z.4\n", 2),
        ("", 1),
        ("M622 J1\nG0 Z.4\nM623\n", None),
        ("M622 J1\nG0 Z.4\nM623\nG91\nG0 Z.2\nG90\n", None),
        ("M622 J1\nG0 Z.4\nM623\nG90\nG0 Z.4\n", 2),
        ("M622 J1\nG91\nM623\nG0 Z.2\n", None),
        ("M622 J1\nG91\nM623\nG90\nG0 Z.4\n", 2),
        ("G91\nM622 J1\nG90\nM623\nG0 Z.2\n", None),
        ("G91\nG0 Z.2\nG90\n", 2),
        ("M622 J1\nG92 Z.4\nM623\n", 1),
    ],
)
def test_conditional_z_only_invalidates_plate_layers_until_absolute_height_is_known(
    commands, expected_layers
):
    """Ein unbekannter Z-Zweig ist kein unbekannter Materialverbrauch."""
    import math

    from app.core.slice import gcode
    from app.core.slice.estimate import PlateComparison, plate_findings

    measured = gcode.analyze(
        "; generated by BambuStudio 2.0\nM83\nG0 X0 Y0 Z.2\n"
        ";LAYER:0\n;TYPE:Outer wall\nG1 X10 E1\n;LAYER:1\n" + commands + "G1 X20 E1\n",
        diameters=(2,),
        densities=(1,),
    ).metrics
    assert measured.filament_mm == pytest.approx(2)
    assert measured.model_material_cm3 == pytest.approx(2 * math.pi / 1000)
    assert measured.model_grams() == pytest.approx(2 * math.pi / 1000)
    assert measured.uncertain_material_roles == ()
    assert measured.model_layer_count == expected_layers
    support, layers = plate_findings(PlateComparison(0, 0.0, expected_layers or 2), measured)
    assert support.code == "gcode.plate_comparison"
    assert layers.code == (
        "gcode.plate_comparison_unknown" if expected_layers is None else "gcode.plate_comparison"
    )


@pytest.mark.parametrize(
    "commands, expected_layers",
    [
        ("G0 Z.4\nG92 Z.2\n", 2),
        ("G0 Z.4\nG92 Z.2\nG0 Z.2\n", 2),
        ("G92 Z.2\n", 1),
        ("M622 J1\nG0 Z.4\nM623\nG92 Z.2\n", None),
        ("M622 J1\nG0 Z.4\nM623\nG92 Z.2\nG0 Z.2\n", None),
        ("G92 Z0\nG0 Z.2\n", 2),
        ("G0 Z.4\nG92 Z0\nG91\nG0 Z.2\nG90\n", 2),
        ("M622 J1\nG92 Z0\nM623\nG91\nG0 Z.2\nG90\n", 2),
        ("M622 J1\nG92 Z0\nM623\nG0 Z.2\n", None),
    ],
)
@pytest.mark.parametrize("initial_zero", ["", "G92 Z0\n"])
def test_g92_counts_physical_plate_heights_and_preserves_uncertain_origins(
    commands, expected_layers, initial_zero
):
    """G92 verschiebt den Ursprung; absolute Z-Werte bewegen sich relativ dazu."""
    import math

    from app.core.slice import gcode
    from app.core.slice.estimate import PlateComparison, plate_findings

    measured = gcode.analyze(
        "; generated by BambuStudio 2.0\nG90\nM83\n"
        + initial_zero
        + "G0 X0 Y0 Z.2\n;LAYER:0\n;TYPE:Outer wall\nG1 X10 E1\n;LAYER:1\n"
        + commands
        + "G1 X20 E1\n",
        diameters=(2,),
        densities=(1,),
    ).metrics
    assert measured.model_material_cm3 == pytest.approx(2 * math.pi / 1000)
    assert measured.uncertain_material_roles == ()
    assert measured.model_layer_count == expected_layers
    _support, layers = plate_findings(PlateComparison(0, 0.0, expected_layers or 2), measured)
    assert layers.code == (
        "gcode.plate_comparison_unknown" if expected_layers is None else "gcode.plate_comparison"
    )
