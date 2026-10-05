"""Tatsächliche Materialbahnen gegen Druckkontur und Sperrflächen (§29)."""

from __future__ import annotations

import subprocess
from dataclasses import replace
from pathlib import Path

import pytest
from shapely.geometry import box

from app.core.export import handover
from app.core.knowledge import print_settings, profiles
from app.core.slice import gcode
from app.i18n import TranslatableText

BED = "; printable_area = 0x0,100x0,100x100,0x100\n"
EXCLUSION = "; bed_exclude_area = 40x40,60x40,60x60,40x60\n"
START = "G90\nM83\n;LAYER:0\nG0 Z0.2\n"


def test_separate_parts_do_not_print_the_gap_between_them() -> None:
    text = BED + EXCLUSION + START + "G0 X10 Y50\nG1 X20 E1\nG0 X80 Y50\nG1 X90 E1\n"
    assert handover.off_the_bed(text, profiles.make_profile(), "prusa") is None


def test_a_line_crossing_an_exclusion_is_found_even_with_endpoints_outside_it() -> None:
    text = BED + EXCLUSION + START + "G0 X20 Y50\nG1 X80 E1\n"
    finding = handover.off_the_bed(text, profiles.make_profile(), "prusa")
    assert finding is not None
    assert finding.code == "gcode.off_the_bed"
    assert finding.values["axis"] == "XY"
    assert finding.source == "gcode"
    reason = finding.values["reason"]
    assert isinstance(reason, TranslatableText)
    assert reason.translate("de") == "Druckfläche"


@pytest.mark.parametrize("arc", ["G2", "G3"])
def test_a_circular_wall_can_surround_an_exclusion(arc: str) -> None:
    text = BED + EXCLUSION + START + f"G0 X80 Y50\n{arc} X80 Y50 I-30 J0 E1\n"
    assert handover.off_the_bed(text, profiles.make_profile(), "prusa") is None


@pytest.mark.parametrize("arc", ["G2", "G3"])
def test_an_arc_crossing_a_small_exclusion_between_its_extrema_is_found(arc: str) -> None:
    # Die Sperre liegt bei 45 Grad, zwischen Start und sämtlichen Achsenextrema.
    exclusion = "; bed_exclude_area = 70x70,73x70,73x73,70x73\n"
    text = BED + exclusion + START + f"G0 X80 Y50\n{arc} X80 Y50 I-30 J0 E1\n"
    assert handover.off_the_bed(text, profiles.make_profile(), "prusa") is not None


def test_arc_intersection_is_not_limited_by_a_sampling_distance() -> None:
    # Eine nur 0,001 mm breite Sperre darf auch zwischen denkbaren Abtastpunkten liegen.
    checker = gcode.area_check(box(-20, -20, 20, 20).difference(box(7.071, 7.071, 7.072, 7.072)))
    result = gcode.analyze("M83\nG0 X10 Y0\nG3 X10 Y0 I-10 J0 E1\n", path_check=checker)
    assert result.paths_inside is False


@pytest.mark.parametrize("arc, inside", [("G3", True), ("G2", False)])
def test_a_partial_arc_checks_only_its_actual_sweep(arc: str, inside: bool) -> None:
    checker = gcode.area_check(box(-0.1, -0.1, 10.1, 10.1))
    result = gcode.analyze(f"M83\nG0 X10 Y0\n{arc} X0 Y10 I-10 J0 E1\n", path_check=checker)
    assert result.paths_inside is inside


def test_a_nonrectangular_bed_does_not_require_the_whole_bounding_box_to_fit() -> None:
    diamond = "; bed_shape = 50x0,100x50,50x100,0x50\n"
    text = diamond + START + "G0 X5 Y50\nG1 X50 Y5 E1\n"
    assert handover.off_the_bed(text, profiles.make_profile(), "prusa") is None


def test_the_effective_printer_contour_is_used_when_the_file_omits_its_bed() -> None:
    profile = profiles.make_profile()
    printer = replace(
        profile.printer,
        build_volume=(100, 100, 100),
        printable_area=((0, -50), (50, 0), (0, 50), (-50, 0)),
    )
    profile = replace(profile, printer=printer)
    inside = START + "G0 X5 Y50\nG1 X50 Y5 E1\n"
    outside = START + "G0 X5 Y5\nG1 X10 E1\n"
    assert handover.off_the_bed(inside, profile, "prusa") is None
    assert handover.off_the_bed(outside, profile, "prusa") is not None
    assert handover.off_the_bed(BED + outside, profile, "prusa") is None


def test_start_purge_in_an_exclusion_is_excluded_from_the_model_check() -> None:
    purge = "G90\nM83\nG0 X45 Y50 Z0.2\nG1 X55 E1\n"
    ring = START + "G0 X80 Y50\nG2 X80 Y50 I-30 J0 E1\n"
    assert (
        handover.off_the_bed(BED + EXCLUSION + purge + ring, profiles.make_profile(), "prusa")
        is None
    )


def test_an_area_that_contains_the_whole_extent_needs_no_replay() -> None:
    analysis = gcode.analyze(BED + START + "G0 X10 Y10\nG1 X20 E1\n")

    def forbidden_replay():
        raise AssertionError("unnecessary replay")

    assert (
        handover.off_the_bed(analysis, profiles.make_profile(), "prusa", replay=forbidden_replay)
        is None
    )


def test_the_replay_uses_the_firmware_from_the_first_analysis() -> None:
    text = (
        BED + EXCLUSION + "M83\nG90\nG0 X20 Y50\nG1 X30 E10\nG0 X70 Y50\nG1 X80 E20\nG1 X20 E19\n"
    )
    analysis = gcode.analyze(text, firmware="marlin")
    calls = []

    def replay():
        calls.append(True)
        return iter(text.splitlines())

    assert handover.off_the_bed(analysis, profiles.make_profile(), "prusa", replay=replay) is None
    assert calls == [True]


def test_the_second_read_pass_is_cancellable_between_paths() -> None:
    from app.core.errors import OperationCancelled
    from app.core.scene.cancel import CancelSignal

    text = BED + EXCLUSION + START + "G0 X80 Y50\nG2 X80 Y50 I-30 J0 E1\n"
    analysis = gcode.analyze(text)
    signal = CancelSignal()

    def replay():
        yield "M83\n"
        signal.cancel()
        yield "G0 X80 Y50\n"
        raise AssertionError("read after cancellation")

    with pytest.raises(OperationCancelled):
        handover.off_the_bed(
            analysis, profiles.make_profile(), "prusa", replay=replay, cancelled=signal
        )


@pytest.mark.parametrize("crosses", [False, True])
@pytest.mark.parametrize("ignored_exclusion", [False, True])
def test_slice_model_replays_the_real_output_for_the_contour_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, crosses: bool, ignored_exclusion: bool
) -> None:
    # Drei Punkte ergeben in der Orca-Familie kein Rechteck und sperren nichts
    # (``PartPlate::calc_bounding_boxes``); geprüft wird dann gegen das ganze Bett.
    payload = (
        BED
        + ("; bed_exclude_area = 10x10,10x10,10x10\n" if ignored_exclusion else EXCLUSION)
        + START
        + ("G0 X20 Y50\nG1 X80 E1\n" if crosses else "G0 X80 Y50\nG2 X80 Y50 I-30 J0 E1\n")
    )
    model = tmp_path / "model.stl"
    model.write_bytes(b"solid x\nendsolid x\n")
    executable = tmp_path / "prusa-slicer-console.exe"
    executable.write_bytes(b"")

    def write_output(command: list[str], *_args: object, **_kwargs: object):
        Path(command[command.index("--output") + 1]).write_text(payload, encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, b"", b"")

    monkeypatch.setattr(handover, "_run_slicer", write_output)
    profile = profiles.make_profile()
    outcome = handover.slice_model(
        model,
        print_settings.resolve(profile),
        profile,
        handover.SlicerSetup(executable=executable, flavour="prusa"),
        output_dir=tmp_path,
    )
    codes = {finding.code for finding in outcome.findings}
    assert ("gcode.off_the_bed" in codes) is (crosses and not ignored_exclusion)
    assert "gcode.invalid_build_area" not in codes
    assert outcome.gcode_path.read_text(encoding="utf-8") == payload


@pytest.mark.parametrize(
    "line",
    [
        "; bed_exclude_area = 0x0,10x10,10x0,0x10\n",
        "; bed_exclude_area = 10x10,10x10,10x10\n",
    ],
)
def test_an_odd_exclusion_in_the_file_neither_aborts_nor_warns(line: str) -> None:
    # Ein Schmetterling ließ GEOS mit einer Ausnahme abbrechen, drei gleiche
    # Punkte ergaben keine Fläche und eine Warnung. Die Orca-Familie liest je
    # vier Punkte als ihr Hüllrechteck und übergeht einen Rest: Der
    # Schmetterling sperrt 0 bis 10, die drei Punkte sperren nichts.
    text = BED + line + START + "G0 X50 Y50\nG1 X60 E1\n"
    assert handover.off_the_bed(text, profiles.make_profile(), "prusa") is None
    outside = BED + line + START + "G0 X150 Y50\nG1 X160 E1\n"
    finding = handover.off_the_bed(outside, profiles.make_profile(), "prusa")
    assert finding is not None and finding.code == "gcode.off_the_bed"


def test_a_manufacturer_purge_behind_the_printable_area_is_not_off_the_bed() -> None:
    """Die Spüllinie des Kobra S1 (Y = 255 mm bei 250 mm Druckfläche) gehört zum
    Code des Profils, nicht zum Druck; neben dem Bett liegt nur das Modell."""
    purge = (
        "; printable_area = 0x0,250x0,250x250,0x250\n"
        ";TYPE:Custom\nG90\nM83\n;LAYER_CHANGE\n;Z:0.2\n"
        "G1 X89.365 Y255 F18000\nG1 X158.835 Y255 E3.7\n"
    )
    inside = purge + ";TYPE:Outer wall\nG1 X100 Y100\nG1 X120 Y100 E1\n"
    assert handover.off_the_bed(inside, profiles.make_profile(), "orca") is None
    outside = purge + ";TYPE:Outer wall\nG1 X100 Y240\nG1 X100 Y260 E1\n"
    finding = handover.off_the_bed(outside, profiles.make_profile(), "orca")
    assert finding is not None and finding.code == "gcode.off_the_bed"


@pytest.mark.parametrize("ignored_exclusion", [False, True])
def test_a_bed_outline_without_area_falls_back_to_the_profile(ignored_exclusion: bool) -> None:
    profile = profiles.make_profile()
    printer = replace(
        profile.printer,
        build_volume=(100, 100, 100),
        printable_area=((0, -50), (50, 0), (0, 50), (-50, 0)),
    )
    profile = replace(profile, printer=printer)
    flat = "; printable_area = 0x0,100x0,50x0\n"
    if ignored_exclusion:
        flat += "; bed_exclude_area = 10x10,10x10,10x10\n"
    finding = handover.off_the_bed(flat + START + "G0 X5 Y50\nG1 X50 Y5 E1\n", profile, "prusa")
    assert finding is not None and finding.code == "gcode.invalid_build_area"
    assert finding.severity == "warning" and finding.source == "gcode"
    assert isinstance(finding.message, TranslatableText)
    assert "Bettkontur" in finding.message.translate("de")
    assert "Sperrkontur" not in finding.message.translate("de")
    outside = handover.off_the_bed(flat + START + "G0 X5 Y5\nG1 X10 E1\n", profile, "prusa")
    assert outside is not None and outside.code == "gcode.off_the_bed"
    assert isinstance(outside.values["detail"], TranslatableText)
