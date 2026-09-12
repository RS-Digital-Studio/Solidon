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
def test_slice_model_replays_the_real_output_for_the_contour_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, crosses: bool
) -> None:
    payload = (
        BED
        + EXCLUSION
        + START
        + ("G0 X20 Y50\nG1 X80 E1\n" if crosses else "G0 X80 Y50\nG2 X80 Y50 I-30 J0 E1\n")
    )
    model = tmp_path / "model.stl"
    model.write_bytes(b"solid x\nendsolid x\n")
    executable = tmp_path / "prusa-slicer-console.exe"
    executable.write_bytes(b"")

    def write_output(*_args: object, **_kwargs: object):
        (tmp_path / "produced.gcode").write_text(payload, encoding="utf-8")
        return subprocess.CompletedProcess([], 0, "", "")

    monkeypatch.setattr(handover, "_run_slicer", write_output)
    profile = profiles.make_profile()
    outcome = handover.slice_model(
        model,
        print_settings.resolve(profile),
        profile,
        handover.SlicerSetup(executable=executable, flavour="prusa"),
        output_dir=tmp_path,
    )
    assert any(finding.code == "gcode.off_the_bed" for finding in outcome.findings) is crosses


@pytest.mark.parametrize(
    "line",
    [
        "; bed_exclude_area = 0x0,10x10,10x0,0x10\n",
        "; bed_exclude_area = 10x10,10x10,10x10\n",
    ],
)
def test_an_unusable_exclusion_in_the_file_does_not_abort_the_check(line: str) -> None:
    # Ein Schmetterling ließ GEOS mit einer Ausnahme abbrechen, drei gleiche
    # Punkte ergeben keine Fläche — beides stammt aus der fremden Datei und
    # darf den Lauf nach dem gelungenen Slicen nicht abreißen.
    text = BED + line + START + "G0 X50 Y50\nG1 X60 E1\n"
    assert handover.off_the_bed(text, profiles.make_profile(), "prusa") is None
    outside = BED + line + START + "G0 X150 Y50\nG1 X160 E1\n"
    assert handover.off_the_bed(outside, profiles.make_profile(), "prusa") is not None


def test_a_bed_outline_without_area_falls_back_to_the_profile() -> None:
    profile = profiles.make_profile()
    printer = replace(
        profile.printer,
        build_volume=(100, 100, 100),
        printable_area=((0, -50), (50, 0), (0, 50), (-50, 0)),
    )
    profile = replace(profile, printer=printer)
    flat = "; printable_area = 0x0,100x0,50x0\n"
    assert (
        handover.off_the_bed(flat + START + "G0 X5 Y50\nG1 X50 Y5 E1\n", profile, "prusa") is None
    )
    assert (
        handover.off_the_bed(flat + START + "G0 X5 Y5\nG1 X10 E1\n", profile, "prusa") is not None
    )
