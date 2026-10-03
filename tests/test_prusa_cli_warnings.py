"""RM-484: echte gespeicherte Ausgaben am Rückweg, ohne externen Slicer.

Die Proben nutzen gespeicherte native Ausgaben. Der Prozess ist vollständig
ersetzt; seine kleine Druckdatei dient dem Rückweg bis SliceOutcome.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest
import trimesh

from app.core import activation
from app.core.export import handover
from app.core.geom.mesh import MeshData
from app.core.knowledge import print_settings, profiles
from app.core.slice import gcode

# Gespeicherte native PrusaSlicer-2.9.6-Ausgaben, Pilz und Würfel mit Raft.
NATIVE_OUTPUTS = {
    "prusa-mk4s": (
        "10 => Processing triangulated mesh\r\n20 => Generating perimeters\r\n"
        "30 => Preparing infill\r\n45 => Making infill\r\n65 => Searching supp"
        "ort spots\r\n69 => Alert if supports needed\r\nprint warning: Detecte"
        "d print stability issues:\r\n\r\nmushroom\r\nFloating bridge anchors, L"
        "oose extrusions, Long bridging extrusions\r\n\r\nConsider enabling su"
        "pports.\r\n88 => Estimating curled extrusions\r\n89 => Calculating ov"
        "erhanging perimeters\r\n88 => Generating skirt and brim\r\n90 => Expo"
        "rting G-code to F:\\solidon-review-reports\\gcode\\rest\\codex_A_484_"
        "baseline\\arbeit\\prusa__prusa-mk4s\\pilz__E-support.style-none__pla"
        "__standard\\solidon.gcode\r\nSlicing result exported to F:\\solidon-r"
        "eview-reports\\gcode\\rest\\codex_A_484_baseline\\arbeit\\prusa__prusa"
        "-mk4s\\pilz__E-support.style-none__pla__standard\\solidon.gcode\r\n"
    ),
    "prusa-mini": (
        "10 => Processing triangulated mesh\r\n20 => Generating perimeters\r\n"
        "30 => Preparing infill\r\n45 => Making infill\r\n65 => Searching supp"
        "ort spots\r\n69 => Alert if supports needed\r\nprint warning: Detecte"
        "d print stability issues:\r\n\r\nmushroom\r\nFloating bridge anchors, L"
        "oose extrusions, Long bridging extrusions\r\n\r\nConsider enabling su"
        "pports.\r\n88 => Estimating curled extrusions\r\n89 => Calculating ov"
        "erhanging perimeters\r\n88 => Generating skirt and brim\r\n90 => Expo"
        "rting G-code to F:\\solidon-review-reports\\gcode\\rest\\codex_A_484_"
        "baseline\\arbeit\\prusa__prusa-mini\\pilz__E-support.style-none__pla"
        "__standard\\solidon.gcode\r\nSlicing result exported to F:\\solidon-r"
        "eview-reports\\gcode\\rest\\codex_A_484_baseline\\arbeit\\prusa__prusa"
        "-mini\\pilz__E-support.style-none__pla__standard\\solidon.gcode\r\n"
    ),
    "sovol-sv06": (
        "10 => Processing triangulated mesh\r\n20 => Generating perimeters\r\n"
        "30 => Preparing infill\r\n45 => Making infill\r\n65 => Searching supp"
        "ort spots\r\n69 => Alert if supports needed\r\nprint warning: Detecte"
        "d print stability issues:\r\n\r\nmushroom\r\nFloating bridge anchors, L"
        "oose extrusions, Long bridging extrusions\r\n\r\nConsider enabling su"
        "pports.\r\n88 => Estimating curled extrusions\r\n89 => Calculating ov"
        "erhanging perimeters\r\n88 => Generating skirt and brim\r\n90 => Expo"
        "rting G-code to F:\\solidon-review-reports\\gcode\\rest\\codex_A_484_"
        "baseline\\arbeit\\prusa__sovol-sv06\\pilz__E-support.style-none__pla"
        "__standard\\solidon.gcode\r\nSlicing result exported to F:\\solidon-r"
        "eview-reports\\gcode\\rest\\codex_A_484_baseline\\arbeit\\prusa__sovol"
        "-sv06\\pilz__E-support.style-none__pla__standard\\solidon.gcode\r\n"
    ),
    "empty": (
        "10 => Processing triangulated mesh\r\n20 => Generating perimeters\r\n"
        "30 => Preparing infill\r\n45 => Making infill\r\n65 => Searching supp"
        "ort spots\r\n69 => Alert if supports needed\r\n70 => Generating suppo"
        "rt material\r\n88 => Estimating curled extrusions\r\n89 => Calculatin"
        "g overhanging perimeters\r\n88 => Generating skirt and brim\r\n90 => "
        "Exporting G-code to F:\\solidon-review-reports\\gcode\\rest\\codex_A_"
        "484_baseline\\arbeit\\prusa__sovol-sv06\\wuerfel__B__pla__standard\\s"
        "olidon.gcode\r\nprint warning: Empty layer between 0.48 and 0.92.\r\n"
        "\r\nObject name: cube_clean\r\n\r\nMake sure the object is printable. T"
        "his is usually caused by negligibly small extrusions or by a faul"
        "ty model. Try to repair the model or change its orientation on th"
        "e bed.\r\nSlicing result exported to F:\\solidon-review-reports\\gcod"
        "e\\rest\\codex_A_484_baseline\\arbeit\\prusa__sovol-sv06\\wuerfel__B__"
        "pla__standard\\solidon.gcode\r\n"
    ),
    "corrected": (
        "10 => Processing triangulated mesh\r\n20 => Generating perimeters\r\n"
        "30 => Preparing infill\r\n45 => Making infill\r\n65 => Searching supp"
        "ort spots\r\n69 => Alert if supports needed\r\n70 => Generating suppo"
        "rt material\r\n88 => Estimating curled extrusions\r\n89 => Calculatin"
        "g overhanging perimeters\r\n88 => Generating skirt and brim\r\n90 => "
        "Exporting G-code to F:\\solidon-review-reports\\gcode\\rest\\codex_A_"
        "484_gap_probe\\arbeit\\prusa__sovol-sv06\\wuerfel__B__pla__standard\\"
        "solidon.gcode\r\nSlicing result exported to F:\\solidon-review-repor"
        "ts\\gcode\\rest\\codex_A_484_gap_probe\\arbeit\\prusa__sovol-sv06\\wuer"
        "fel__B__pla__standard\\solidon.gcode\r\n"
    ),
}

PAYLOAD = "G90\nM83\nG0 X10 Y10 Z0.2\nG1 X20 E1 F600\n"
STABILITY = (
    "Detected print stability issues:\n\nmushroom\n"
    "Floating bridge anchors, Loose extrusions, Long bridging extrusions\n\n"
    "Consider enabling supports."
)
EMPTY = (
    "Empty layer between 0.48 and 0.92.\n\nObject name: cube_clean\n\n"
    "Make sure the object is printable. This is usually caused by negligibly small "
    "extrusions or by a faulty model. Try to repair the model or change its "
    "orientation on the bed."
)


@pytest.fixture
def run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    """Der echte Übergabeweg mit isolierter Prozess- und Gerätefreischaltung."""
    for variable in (
        "APPDATA",
        "LOCALAPPDATA",
        "XDG_DATA_HOME",
        "XDG_CONFIG_HOME",
        "XDG_CACHE_HOME",
    ):
        monkeypatch.setenv(variable, str(tmp_path / "user-data"))
    monkeypatch.setattr(activation, "require", lambda *_args, **_kwargs: None)
    model = tmp_path / "model.stl"
    mesh = trimesh.creation.box(extents=(1.0, 1.0, 1.0))
    model.write_bytes(mesh.export(file_type="stl"))
    executable = tmp_path / "PrusaSlicer.exe"
    executable.write_bytes(b"")

    def invoke(
        stdout: str | bytes = "",
        stderr: str | bytes = "",
        comments: tuple[str, ...] = (),
        printer: str = "prusa-mk4s",
    ) -> handover.SliceOutcome:
        profile = profiles.make_profile(printer, "pla")
        setup = handover.SlicerSetup(executable=executable, flavour="prusa")
        calls = []

        def finished(command: list[str], *_args: Any, **_kwargs: Any) -> Any:
            calls.append(command)
            Path(command[command.index("--output") + 1]).write_text(
                "".join(f"; WARNING: {comment}\n" for comment in comments) + PAYLOAD,
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(
                command,
                0,
                stdout.encode("utf-8") if isinstance(stdout, str) else stdout,
                stderr.encode("utf-8") if isinstance(stderr, str) else stderr,
            )

        monkeypatch.setattr(handover, "_run_slicer", finished)
        outcome = handover.slice_model(
            model,
            print_settings.resolve(profile),
            profile,
            setup,
            output_dir=tmp_path,
            model_meshes=(MeshData(mesh),),
        )
        assert len(calls) == 1, "genau ein ersetzter Prozess, kein echter Slicer"
        assert outcome.gcode_path.is_file()
        return outcome

    return invoke


def warning_entries(outcome: handover.SliceOutcome) -> list[Any]:
    entries = [finding for finding in outcome.findings if finding.code == "gcode.warning"]
    assert all(entry.source == "gcode" and entry.suggestions for entry in entries)
    assert tuple(entry.values["text"] for entry in entries) == outcome.metrics.warnings
    return entries


@pytest.mark.parametrize("printer", ["prusa-mk4s", "prusa-mini", "sovol-sv06"])
@pytest.mark.parametrize("stream", ["stdout", "stderr"])
def test_real_mushroom_warning_reaches_the_report(run: Any, printer: str, stream: str) -> None:
    entries = warning_entries(run(**{stream: NATIVE_OUTPUTS[printer]}, printer=printer))
    assert len(entries) == 1
    assert entries[0].values["text"] == STABILITY
    assert entries[0].severity == "warning"


def test_real_empty_layer_warning_is_an_error(run: Any) -> None:
    entries = warning_entries(run(NATIVE_OUTPUTS["empty"], printer="sovol-sv06"))
    assert len(entries) == 1
    assert entries[0].values["text"] == EMPTY
    assert entries[0].severity == "error"


def test_existing_empty_layer_gcode_comment_is_also_an_error() -> None:
    metrics = gcode.analyze("; WARNING: Empty layer between 0.48 and 0.92.\n" + PAYLOAD).metrics
    entries = [entry for entry in gcode.findings_for(metrics) if entry.code == "gcode.warning"]
    assert len(entries) == 1
    assert entries[0].severity == "error"
    assert entries[0].source == "gcode"


@pytest.mark.parametrize(
    "end", ["88 => Estimating curled extrusions", "Slicing result exported to private/output.gcode"]
)
def test_progress_and_result_lines_end_the_block(run: Any, end: str) -> None:
    output = f"print warning: {STABILITY}\n{end}\nPrivate unrelated progress\n"
    entries = warning_entries(run(output))
    assert [entry.values["text"] for entry in entries] == [STABILITY]


def test_a_new_warning_starts_a_separate_block(run: Any) -> None:
    entries = warning_entries(run(f"print warning: {STABILITY}\nprint warning: {EMPTY}\n"))
    assert [entry.values["text"] for entry in entries] == [STABILITY, EMPTY]
    assert [entry.severity for entry in entries] == ["warning", "error"]


def test_both_streams_and_gcode_share_one_complete_warning(run: Any) -> None:
    flat = " ".join(STABILITY.split())
    entries = warning_entries(
        run(f"print warning: {STABILITY}\n", f"print warning: {STABILITY}\n", (flat,))
    )
    assert [entry.values["text"] for entry in entries] == [STABILITY]


def test_a_summary_comment_does_not_hide_the_object_and_action(run: Any) -> None:
    entries = warning_entries(
        run(f"print warning: {STABILITY}\n", comments=(STABILITY.splitlines()[0],))
    )
    assert [entry.values["text"] for entry in entries] == [STABILITY]


@pytest.mark.parametrize("name", ["second_object", "Mushroom"])
def test_two_objects_with_the_same_warning_heading_remain_separate(run: Any, name: str) -> None:
    second = STABILITY.replace("mushroom", name)
    entries = warning_entries(
        run(
            f"print warning: {STABILITY}\nprint warning: {second}\n",
            comments=(STABILITY.splitlines()[0],),
        )
    )
    assert [entry.values["text"] for entry in entries] == [STABILITY, second]


def test_a_long_block_keeps_its_beginning_and_final_action(run: Any) -> None:
    warning = STABILITY.replace("mushroom", "mushroom_" + "x" * 2400)
    output = "version information\n" * 500 + f"print warning: {warning}\n88 => Progress\n"
    entries = warning_entries(run(output))
    assert [entry.values["text"] for entry in entries] == [warning]


def test_a_stream_ends_its_block_before_the_other_stream(run: Any) -> None:
    entries = warning_entries(
        run(f"print warning: {STABILITY}\n", "unrelated stderr diagnostics\n")
    )
    assert [entry.values["text"] for entry in entries] == [STABILITY]


@pytest.mark.parametrize(
    "output", ["", "69 => Alert if supports needed\n", "ordinary warning text\n"]
)
def test_output_without_a_print_warning_is_no_warning(run: Any, output: str) -> None:
    assert not warning_entries(run(output))


def test_gcode_only_warning_keeps_its_text_and_origin(run: Any) -> None:
    entries = warning_entries(run(comments=("Existing warning without console counterpart",)))
    assert len(entries) == 1
    assert entries[0].values["text"] == "Existing warning without console counterpart"
    assert entries[0].severity == "warning"


def test_saved_corrected_gap_output_has_no_warning(run: Any) -> None:
    assert not warning_entries(run(NATIVE_OUTPUTS["corrected"], printer="sovol-sv06"))


@pytest.fixture(autouse=True)
def no_processes(monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("Die Gegenprobe darf keinen Prozess starten.")

    monkeypatch.setattr(subprocess, "Popen", forbidden)


@pytest.mark.parametrize(
    "name", ["88 => bridge", "Slicing result exported to bridge", "print warning: bridge"]
)
@pytest.mark.parametrize("by_issue", [False, True])
def test_native_two_line_paragraph_keeps_control_like_object_name(name, by_issue):
    body = f"Floating bridge anchors\n{name}" if by_issue else f"{name}\nFloating bridge anchors"
    warning = f"Detected print stability issues:\n\n{body}\n\nConsider enabling supports."
    output = f"print warning: {warning}\n88 => Estimating curled extrusions\nother output\n"
    assert handover._print_warnings(output.encode()) == (warning,)


@pytest.mark.parametrize("name", ["Consider enabling supports.", "Also consider enabling brim."])
def test_action_like_object_name_and_later_object_are_kept(name):
    warning = (
        "Detected print stability issues:\n\n"
        f"{name}\nFloating bridge anchors\n\n"
        "88 => bridge\nLoose extrusions\n\n"
        "Consider enabling supports.\nAlso consider enabling brim."
    )
    assert handover._print_warnings(f"print warning: {warning}\n88 => Exporting\n".encode()) == (
        warning,
    )


@pytest.mark.parametrize(
    "names",
    [("clip  left", "clip left"), ("clip\u00a0left", "clip left"), ("clip\tleft", "clip left")],
)
def test_different_inline_whitespace_keeps_both_objects(names):
    warnings = tuple(STABILITY.replace("mushroom", name) for name in names)
    assert handover._merged_warnings(warnings, warnings) == warnings


def test_flattening_does_not_merge_two_different_multiline_blocks():
    first = "Heading\n\nleft right\nissue\n\nAction"
    second = "Heading\n\nleft\nright issue\n\nAction"
    assert handover._merged_warnings((first, second)) == (first, second)


def test_output_budget_is_shared_between_streams(monkeypatch):
    first = b"print warning: first\n"
    second = b"print warning: second\n"
    monkeypatch.setattr(handover, "SLICER_OUTPUT_LIMIT", len(first) + len(second))
    assert handover._print_warnings(first, second + b"print warning: outside budget\n") == (
        "first",
        "second",
    )


def test_a_full_stdout_budget_does_not_read_stderr(monkeypatch):
    text = b"print warning: first\n"
    monkeypatch.setattr(handover, "SLICER_OUTPUT_LIMIT", len(text))
    assert handover._print_warnings(text, b"print warning: outside budget\n") == ("first",)
