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


@pytest.mark.parametrize("nozzle", [0.25, 0.4, 0.8])
def test_no_support_is_measured_as_a_strand_through_the_nozzle(nozzle):
    """„Keine Stütze“ heißt: weniger als ein Strang im Düsenquerschnitt, so lang
    wie die kürzeste Brücke, die Solidon stützen lässt — eine Grenze in Metern
    schlüge an einer 0,8er Düse an, die dieselbe Stütze mit wenigen Metern legt."""
    import math

    from app.core.slice.analysis import SPAN_INTERESTING
    from app.core.slice.estimate import support_floor

    profile = profiles.make_profile()
    profile = dataclasses.replace(
        profile, printer=dataclasses.replace(profile.printer, nozzle_diameter=nozzle)
    )
    assert support_floor(profile) == pytest.approx(SPAN_INTERESTING * math.pi * nozzle**2 / 4.0)


@pytest.mark.parametrize("blocked", [True, False])
def test_supports_switched_on_but_none_in_the_gcode_is_a_warning(blocked):
    """Die Kanalsperre nahm am Wedge-Lock dem übernommenen Stützvorschlag jede
    Stütze (0 statt 6,6 m an der 0,25er Düse), und weil die Stützmenge mit Sperre
    unbekannt ist, sagte die Gegenprobe nur „unvollständig“. Jetzt sagt sie, dass
    nichts gestützt ist, und wohin der Weg führt."""
    from app.core.errors import OPEN_PRINT_SETTINGS
    from app.core.slice.estimate import PlateComparison, plate_findings
    from app.core.slice.gcode import GcodeMetrics

    floor = 0.74
    expected = PlateComparison(
        0, None, 4, "unbekannt", support_floor_mm3=floor, channels_blocked=blocked
    )
    findings = plate_findings(expected, GcodeMetrics(support_mm3=0.0, model_layer_count=4))

    missing = [finding for finding in findings if finding.code == "gcode.support_missing"]
    assert len(missing) == 1
    assert missing[0].severity == "warning"
    assert missing[0].suggestions == (OPEN_PRINT_SETTINGS,)
    assert missing[0].source == "gcode"
    assert missing[0].values["plate"] == 1
    assert missing[0].values["measured"] == 0.0
    assert ("„Kanäle frei halten“" in str(missing[0].message)) is blocked
    assert [finding.code for finding in findings] == [
        "gcode.support_missing",
        "gcode.plate_comparison",
    ], "die Stützzeile der allgemeinen Gegenprobe sagte dasselbe ein zweites Mal"

    for printed, why in ((floor * 1.01, "ein Strang ist eine Stütze"), (None, "unbekannt")):
        quiet = plate_findings(expected, GcodeMetrics(support_mm3=printed, model_layer_count=4))
        assert "gcode.support_missing" not in {finding.code for finding in quiet}, why
    unasked = PlateComparison(0, 0.0, 4)
    zero = plate_findings(unasked, GcodeMetrics(support_mm3=0.0, model_layer_count=4))
    assert "gcode.support_missing" not in {finding.code for finding in zero}, (
        "ohne Stützbedarf ist keine Stütze die richtige Antwort"
    )


def test_the_plate_comparison_knows_when_support_is_wanted_and_blocked():
    """Die Untergrenze gilt nur, wo Stützen eingeschaltet sind und die
    Schichtanalyse sie selbst verlangt; die Sperre geht nur hinaus, wo ein
    Kanal ist. Ein Block mit einem Tunnel von 20 mm, daneben oben eine
    Kragplatte: Die Kragplatte braucht Stützen, die Tunneldecke ist Kanal. Ohne
    Kragplatte trägt sich die Tunneldecke selbst, und keine Stütze im G-Code ist
    dort die richtige Antwort."""
    import trimesh

    from app.core.geom.mesh import MeshData
    from app.core.slice.estimate import plate_comparison
    from app.core.types import SceneObject

    block = trimesh.creation.box(extents=(60.0, 40.0, 40.0))
    block.apply_translation((0.0, 0.0, 20.0))
    tunnel = trimesh.creation.box(extents=(20.0, 50.0, 20.0))
    tunnel.apply_translation((0.0, 0.0, 18.0))
    arm = trimesh.creation.box(extents=(40.0, 40.0, 5.0))
    arm.apply_translation((50.0, 0.0, 37.5))
    bare = MeshData.of(trimesh.boolean.difference([block, tunnel]))
    body = MeshData.of(trimesh.boolean.union([bare.raw, arm]))
    profile = profiles.make_profile()
    plain = print_settings.resolve(profile)
    supported = dataclasses.replace(
        plain, support=dataclasses.replace(plain.support, style="normal")
    )
    blocking = dataclasses.replace(
        supported, support=dataclasses.replace(supported.support, block_channels=True)
    )

    def compared(settings, mesh=body):
        part = (SceneObject(id="tunnel", name="Tunnel", mesh=mesh), mesh, settings)
        return plate_comparison(0, [part], profile, keep_arrangement=True, separate_objects=False)

    assert compared(plain).support_floor_mm3 is None, "ohne Stützen keine Untergrenze"
    on = compared(supported)
    assert on.support_floor_mm3 is not None and on.support_floor_mm3 > 0.0
    assert not on.channels_blocked
    assert compared(blocking).channels_blocked
    alone = compared(blocking, bare)
    assert alone.channels_blocked
    assert alone.support_floor_mm3 is None, "die Tunneldecke allein verlangt keine Stütze"


def test_a_blocker_without_space_does_not_block_the_comparison():
    """Eine Kanaldecke, unter der kein Raum zu sperren ist, ergibt keinen
    Sperrkörper — der Zeitvergleich bleibt offen, auch mit übernommener Sperre.
    Gefragt war hier bis zum Review vom 08.10.2026 nur, ob es Kanalstücke gibt:
    ein Schlitz von 0,6 mm Höhe neben einer Kragplatte hielt den Vergleich an."""
    import trimesh

    from app.core.geom.mesh import MeshData
    from app.core.slice.estimate import plate_comparison
    from app.core.types import SceneObject

    block = trimesh.creation.box(extents=(30.0, 40.0, 20.0))
    block.apply_translation((0.0, 0.0, 10.0))
    cut = trimesh.creation.box(extents=(5.0, 50.0, 0.6))
    cut.apply_translation((0.0, 0.0, 6.3))
    arm = trimesh.creation.box(extents=(20.0, 40.0, 4.0))
    arm.apply_translation((25.0, 0.0, 18.0))
    body = MeshData.of(trimesh.boolean.union([trimesh.boolean.difference([block, cut]), arm]))
    profile = profiles.make_profile()
    plain = print_settings.resolve(profile)
    blocking = dataclasses.replace(
        plain, support=dataclasses.replace(plain.support, style="normal", block_channels=True)
    )
    part = (SceneObject(id="slot", name="Schlitz", mesh=body), body, blocking)

    compared = plate_comparison(0, [part], profile, keep_arrangement=True, separate_objects=False)

    assert not compared.channels_blocked
    assert compared.support_material_mm3 is not None, "die Stützmenge bleibt bekannt"


def test_a_ledge_blocker_makes_the_support_amount_unknown():
    """Unter gesperrten Rändern druckt der Slicer keine Stütze, die Säulen der
    Zeitrechnung stünden aber da: Mit „Ränder ohne Stütze“ und ohne Kanalsperre
    warnte die Gegenprobe vor einer Abweichung um das 3,6-Fache (Review vom
    08.10.2026). Die Stützmenge ist dann unbekannt, und der Befund ohne Stütze
    nennt den richtigen Schalter."""
    import trimesh

    from app.core.geom.mesh import MeshData
    from app.core.slice.estimate import _support_missing, plate_comparison
    from app.core.types import SceneObject

    column = trimesh.creation.box(extents=(30.0, 30.0, 40.0))
    column.apply_translation((0.0, 0.0, 20.0))
    flange = trimesh.creation.box(extents=(35.0, 35.0, 1.0))
    flange.apply_translation((0.0, 0.0, 20.5))
    arm = trimesh.creation.box(extents=(15.0, 10.0, 2.0))
    arm.apply_translation((22.5, 0.0, 21.4))
    body = MeshData.of(trimesh.boolean.union([column, flange, arm]))
    profile = profiles.make_profile()
    plain = print_settings.resolve(profile)
    sparing = dataclasses.replace(
        plain, support=dataclasses.replace(plain.support, style="normal", spare_ledges=True)
    )
    part = (SceneObject(id="flange", name="Flansch", mesh=body), body, sparing)

    compared = plate_comparison(0, [part], profile, keep_arrangement=True, separate_objects=False)

    assert compared.ledges_blocked
    assert not compared.channels_blocked
    assert compared.support_material_mm3 is None, "die Stützmenge ist mit Sperre unbekannt"
    finding = _support_missing(compared, 0.0, None)
    assert "Ränder ohne Stütze" in str(finding.message)


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


def test_plate_comparison_counts_the_layers_of_a_height_curve():
    """Mit feinen Schichten (RM-586) zählt die Gegenprobe die Lagen, die der
    Slicer aus der Kurve legt — sonst meldeten alle Programme, die sie lesen,
    „Modellschichten weichen ab“ (100 gegen 129 an Kuppe und Klotz).

    Ein Klotz 2 mm hoch, 0,2 mm Raster, die Kurve fein ab 1 mm mit 0,1 mm: zehn
    Lagen gleichmäßig, mit Kurve die Oberkanten aus ``printed_tops``. Allein auf
    der Platte rechnet die Zeit mit diesen Lagen und wird länger; neben einem
    zweiten Teil ohne Kurve zählt jede Höhe einmal, und die Zeit rechnet nur
    der Slicer."""
    from app.core.slice import fine_layers
    from app.core.slice.estimate import plate_comparison
    from app.core.slice.print_time import Motion

    profile = profiles.make_profile()
    settings = print_settings.resolve(profile)
    settings = dataclasses.replace(
        settings,
        layers=dataclasses.replace(settings.layers, first_layer_height=0.2, layer_height=0.2),
    )
    curve = (0.0, 0.2, 0.2, 0.2, 0.5, 0.2, 1.0, 0.1, 2.0, 0.1)
    tops = fine_layers.printed_tops(curve)
    assert len(tops) > 10 and tops[-1] == pytest.approx(2.0, abs=0.06)
    motion = Motion(nozzle=profile.printer.nozzle_diameter)
    alone = [_plate_part("one", settings=settings)]

    plain = plate_comparison(
        0, alone, profile, keep_arrangement=True, separate_objects=True, motion=motion
    )
    curved = plate_comparison(
        0,
        alone,
        profile,
        keep_arrangement=True,
        separate_objects=True,
        motion=motion,
        heights={"one": curve},
    )
    assert plain.model_layer_count == 10
    assert curved.model_layer_count == len(tops)
    assert plain.seconds is not None and curved.seconds is not None
    assert curved.seconds > plain.seconds

    pair = [*alone, _plate_part("two", (5.0, 0.0, 0.0), settings)]
    both = plate_comparison(
        0,
        pair,
        profile,
        keep_arrangement=True,
        separate_objects=True,
        motion=motion,
        heights={"one": curve},
    )
    shared = {round(top, 6) for top in tops} | {round(0.2 * (n + 1), 6) for n in range(10)}
    assert both.model_layer_count == len(shared)
    assert both.seconds is None and both.seconds_reason
