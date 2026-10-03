"""Erstschichtabsagen am Sliceranschluss, mit nativen Meldungen und Prozessattrappe."""

from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
import trimesh

from app.core import activation
from app.core.errors import ExternalToolError, OperationCancelled
from app.core.export import handover
from app.core.geom.mesh import MeshData
from app.core.knowledge import print_settings, profiles
from app.core.process import ProcessOutputLimitExceeded
from app.core.scene.cancel import CancelSignal
from app.core.types import SceneObject
from app.ui import print_settings_dialog as pd

# Native stderr-Absagen von SuperSlicer und PrusaSlicer,
# jeweils MINI/Cat2, MINI/Cat3 und MINI/Segel. Die Prozessattrappe gibt
# genau diese Ursache zurück; sie ist kein erneuter echter Slicer-Nachweis.
NATIVE = [
    {
        "combo": "superslicer__prusa-mini",
        "model": "katze2",
        "commands": [
            {
                "returncode": 1,
                "stdout_tail": "",
                "stderr_tail": "Detected technology \x01\r\n"
                "There is an object with no extrusions in the first layer.\n"
                "Object name: Cica_2\n",
            }
        ],
        "acceptance": {"expected_part": "Cica_2"},
    },
    {
        "combo": "superslicer__prusa-mini",
        "model": "katze3",
        "commands": [
            {
                "returncode": 1,
                "stdout_tail": "",
                "stderr_tail": "Detected technology \x01\r\n"
                "There is an object with no extrusions in the first layer.\n"
                "Object name: Cica_3\n",
            }
        ],
        "acceptance": {"expected_part": "Cica_3"},
    },
    {
        "combo": "superslicer__prusa-mini",
        "model": "segel",
        "commands": [
            {
                "returncode": 1,
                "stdout_tail": "",
                "stderr_tail": "Detected technology \x01\r\n"
                "There is an object with no extrusions in the first layer.\n"
                "Object name: obj_9_ship sails 3d model.stl_8\n",
            }
        ],
        "acceptance": {"expected_part": "obj_9_ship sails 3d model.stl_8"},
    },
    {
        "combo": "prusa__prusa-mini",
        "model": "katze2",
        "commands": [
            {
                "returncode": 1,
                "stdout_tail": "",
                "stderr_tail": "There is an object with no extrusions in the first layer.\r\n"
                "Object name: Cica_2\r\n",
            }
        ],
        "acceptance": {"expected_part": "Cica_2"},
    },
    {
        "combo": "prusa__prusa-mini",
        "model": "katze3",
        "commands": [
            {
                "returncode": 1,
                "stdout_tail": "",
                "stderr_tail": "There is an object with no extrusions in the first layer.\r\n"
                "Object name: Cica_3\r\n",
            }
        ],
        "acceptance": {"expected_part": "Cica_3"},
    },
    {
        "combo": "prusa__prusa-mini",
        "model": "segel",
        "commands": [
            {
                "returncode": 1,
                "stdout_tail": "",
                "stderr_tail": "There is an object with no extrusions in the first layer.\r\n"
                "Object name: obj_9_ship sails 3d model.stl_8\r\n",
            }
        ],
        "acceptance": {"expected_part": "obj_9_ship sails 3d model.stl_8"},
    },
]
CAUSE = b"There is an object with no extrusions in the first layer."
GCODE = b"G90\nM82\nG92 E0\nG1 Z0.2 F300\nG1 X80 Y80 E1 F600\nG1 X90 Y80 E2\n"


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    for variable in (
        "APPDATA",
        "LOCALAPPDATA",
        "XDG_DATA_HOME",
        "XDG_CONFIG_HOME",
        "XDG_CACHE_HOME",
    ):
        monkeypatch.setenv(variable, str(tmp_path / "userdata"))
    monkeypatch.setattr(activation, "require", lambda *args, **kwargs: None)


def native_record(name="Cat", newline="\n"):
    return CAUSE + newline.encode() + b"Object name: " + name.encode() + newline.encode()


def prepare(tmp_path, program="PrusaSlicer.exe", flavour="prusa"):
    body = trimesh.creation.box(extents=(8, 8, 8))
    body.apply_translation((0, 0, 4))
    mesh = MeshData.of(body)
    model = tmp_path / "model.stl"
    model.write_bytes(trimesh.exchange.stl.export_stl(body))
    executable = tmp_path / program
    executable.write_bytes(b"")
    profile = profiles.make_profile("prusa-mini", "pla")
    return mesh, model, profile, handover.SlicerSetup(executable, flavour)


def attempt(
    tmp_path,
    monkeypatch,
    *,
    stdout=b"",
    stderr=b"",
    code=1,
    written=None,
    program="PrusaSlicer.exe",
    flavour="prusa",
):
    mesh, model, profile, setup = prepare(tmp_path, program, flavour)
    output = tmp_path / "gcode"

    def answer(command, *args, **kwargs):
        if written is not None:
            Path(command[command.index("--output") + 1]).write_bytes(written)
        return subprocess.CompletedProcess([], code, stdout, stderr)

    monkeypatch.setattr(handover, "_run_slicer", answer)
    return handover.slice_model(
        model,
        print_settings.resolve(profile),
        profile,
        setup,
        model_meshes=(mesh,),
        output_dir=output,
    )


def refusal(tmp_path, monkeypatch, **kwargs):
    with pytest.raises(ExternalToolError) as raised:
        attempt(tmp_path, monkeypatch, **kwargs)
    return raised.value


def assert_empty(problem, name):
    assert problem.values.get("constraint") == "empty_first_layer"
    assert problem.values.get("field") == "adhesion.kind"
    if name is None:
        assert "part_name" not in problem.values
        assert "eines Teils" in str(problem.detail)
    else:
        assert problem.values["part_name"] == name
        assert name in str(problem.detail)
    actions = {entry.id for entry in problem.suggestions}
    assert {"show_locations", "place_on_bed", "open_print_settings", "show_output"} <= actions
    assert "check_profile" not in actions


@pytest.mark.parametrize("case", NATIVE, ids=lambda case: case["combo"] + "-" + case["model"])
def test_six_real_native_errors_reach_the_specific_model_action(tmp_path, monkeypatch, case):
    command = case["commands"][-1]
    error = refusal(
        tmp_path,
        monkeypatch,
        program="SuperSlicer.exe" if case["combo"].startswith("superslicer") else "PrusaSlicer.exe",
        code=command["returncode"],
        stdout=command["stdout_tail"].encode(),
        stderr=command["stderr_tail"].encode(),
    )
    assert_empty(error, case["acceptance"]["expected_part"])

    from app.core.errors import OPEN_PRINT_SETTINGS
    from app.ui.dialogs import offered_actions

    shown = offered_actions(error, {OPEN_PRINT_SETTINGS.id: lambda _error: None})
    assert len(shown) == 1
    assert shown[0].id == OPEN_PRINT_SETTINGS.id
    assert str(shown[0].label) == "Brim oder Raft prüfen …"
    assert error.values["field"] == "adhesion.kind"
    assert str(OPEN_PRINT_SETTINGS.label) == "Druckeinstellungen öffnen"


@pytest.mark.parametrize("code", [0, 1, -1073741819])
@pytest.mark.parametrize("written", [None, b"", b"; header only\nG90\n"])
def test_first_layer_cause_survives_exit_status_and_missing_or_inert_file(
    tmp_path, monkeypatch, code, written
):
    error = refusal(tmp_path, monkeypatch, stderr=native_record(), code=code, written=written)
    assert_empty(error, "Cat")


@pytest.mark.parametrize("code", [0, 1])
def test_a_real_extruding_file_keeps_the_success_path_despite_console_text(
    tmp_path, monkeypatch, code
):
    result = attempt(tmp_path, monkeypatch, stderr=native_record(), code=code, written=GCODE)
    assert result.gcode_path.read_bytes() == GCODE


@pytest.mark.parametrize("newline", ["\n", "\r\n", "\r"])
@pytest.mark.parametrize("stream", ["stdout", "stderr"])
def test_full_stream_retains_the_exact_unicode_name_before_tail_truncation(
    tmp_path, monkeypatch, newline, stream
):
    name = '  Äußeres Teil: "日本語"  '
    native = b"prefix\n" * 600 + native_record(name, newline) + b"suffix\n" * 600
    error = refusal(tmp_path, monkeypatch, **{stream: native})
    assert_empty(error, name)
    assert len(error.values["output"]) > 800
    assert native.decode() in error.values["output"]


@pytest.mark.parametrize(
    "stdout,stderr,expected",
    [
        (CAUSE, b"Object name: Wrong\n", None),
        (CAUSE + b"\nWarning\nObject name: Wrong\n", b"", None),
        (native_record("A"), native_record("B"), None),
        (native_record("A") + native_record("B"), b"", None),
        (native_record("A"), CAUSE, None),
        (native_record("Same"), native_record("Same"), "Same"),
        (native_record("Cat"), native_record("cat"), None),
        (CAUSE + b"\nObject name: \xff\n", b"", None),
        (
            native_record("Name contains No layers were detected"),
            b"",
            "Name contains No layers were detected",
        ),
    ],
)
def test_names_are_stream_local_exact_unambiguous_and_valid_utf8(
    tmp_path, monkeypatch, stdout, stderr, expected
):
    assert_empty(refusal(tmp_path, monkeypatch, stdout=stdout, stderr=stderr), expected)


@pytest.mark.parametrize(
    "stderr",
    [
        b"Object name: Cat\n",
        b"print warning: " + CAUSE + b"\nObject name: Cat\n",
        b"unknown option\n",
    ],
)
def test_unrelated_lines_keep_the_existing_error_path(tmp_path, monkeypatch, stderr):
    error = refusal(tmp_path, monkeypatch, stderr=stderr)
    assert error.values.get("constraint") != "empty_first_layer"


def test_known_first_layer_error_precedes_a_volume_phrase_inside_its_part_name(
    tmp_path, monkeypatch
):
    name = "All objects are outside of the print volume"
    assert_empty(refusal(tmp_path, monkeypatch, stderr=native_record(name)), name)


def test_the_existing_process_boundary_stays_bounded_before_any_diagnosis(tmp_path, monkeypatch):
    options = {}

    def exceed(command, **kwargs):
        options.update(kwargs)
        raise ProcessOutputLimitExceeded(command, kwargs["output_limit"])

    monkeypatch.setattr(handover, "run_limited", exceed)
    setup = handover.SlicerSetup(tmp_path / "PrusaSlicer.exe", "prusa")
    with pytest.raises(ExternalToolError) as raised:
        handover._run_slicer([str(setup.executable)], tmp_path, 3.0, setup, None)
    assert options["output_limit"] == handover.SLICER_OUTPUT_LIMIT == 8 * 1024 * 1024
    assert raised.value.values.get("constraint") != "empty_first_layer"
    assert "mehr Ausgabe" in str(raised.value.detail)


@pytest.mark.parametrize("flavour", ["orca", "cura"])
def test_other_families_do_not_borrow_a_prusa_diagnosis(tmp_path, monkeypatch, flavour):
    # Konfiguration und Aufruf werden hier gestellt; der Fehlerzweig von
    # slice_model bleibt echt, ohne einen installierten Slicer zu verwenden.
    monkeypatch.setattr(
        handover,
        "write_config",
        lambda *args, **kwargs: SimpleNamespace(
            paths=(), written={}, findings=[], origin_at_centre=False, machine_shift=None
        ),
    )
    monkeypatch.setattr(handover, "_command", lambda *args, **kwargs: [])
    monkeypatch.setattr(handover, "_orca_cli_tower_position", lambda config, *args: config)
    monkeypatch.setattr(handover, "_readback_materials", lambda *args: ({}, {}))
    error = refusal(
        tmp_path,
        monkeypatch,
        stderr=native_record(),
        flavour=flavour,
        program="OrcaSlicer.exe" if flavour == "orca" else "CuraEngine.exe",
    )
    assert error.values.get("constraint") != "empty_first_layer"


class SignalLog:
    def __init__(self):
        self.calls = []

    def emit(self, *args):
        self.calls.append(args)


@pytest.mark.parametrize(
    "name",
    [
        "Same",
        "Line\nTwo",
        "Cat [one]",
        "Äußeres Teil",
        "  A  B  ",
        "A\u00a0B",
        "<b>Teil</b> & \"Name\" 'X'",
    ],
)
def test_real_parser_and_worker_bind_the_actual_cli_copy_together(tmp_path, monkeypatch, name):
    mesh, _model, profile, setup = prepare(tmp_path)
    objects = (
        SceneObject("one", name, mesh),
        SceneObject("two", name, mesh),
        SceneObject("reserved", name + " [two]", mesh),
    )
    job = pd._PlateJob(
        objects=objects,
        plates=(0,),
        folder=tmp_path,
        name="RM483",
        setup=setup,
        settings=print_settings.resolve(profile),
        profile=profile,
        slot_profiles={},
        with_settings=False,
    )
    run = pd._prepare_plate(job, 0)
    # Die Prusa-Beilage ist die Quelle für die nächste native Antwort.
    from xml.etree import ElementTree as ET
    from zipfile import ZipFile

    with ZipFile(run.model) as archive:
        xml = ET.fromstring(archive.read("Metadata/Slic3r_PE_model.config"))
    exported = xml.findall("object/metadata[@key='name']")[1].get("value")
    monkeypatch.setattr(
        handover,
        "_run_slicer",
        lambda *args, **kwargs: subprocess.CompletedProcess([], 1, b"", native_record(exported)),
    )
    host = SimpleNamespace(
        _runs=[run],
        _settings=job.settings,
        _profile=profile,
        _setup=setup,
        _usage={},
        cancelled=CancelSignal(),
        step=SignalLog(),
        failed=SignalLog(),
        done=SignalLog(),
    )
    pd._SliceWorker.work(host)
    delivered = host.failed.calls[0][0]
    assert delivered.object_id == "two"
    assert delivered.values["part_name"] == name
    assert name in str(delivered.detail) and name in str(delivered)
    assert not host.done.calls


def test_cancellation_still_stops_before_the_specific_error(tmp_path, monkeypatch):
    def cancel(*args, **kwargs):
        raise OperationCancelled()

    monkeypatch.setattr(handover, "_run_slicer", cancel)
    mesh, model, profile, setup = prepare(tmp_path)
    with pytest.raises(OperationCancelled):
        handover.slice_model(
            model, print_settings.resolve(profile), profile, setup, model_meshes=(mesh,)
        )


@pytest.mark.parametrize(
    "first,second",
    [
        ("Part", " Part"),
        ("Part", "Part "),
        ("A B", "A  B"),
        ("A B", "A\u00a0B"),
        ("A B", "A\tB"),
        ("Part", "part"),
        ("Teil", "<b>Teil</b> & \"Name\" 'X'"),
    ],
)
def test_near_names_stay_distinct_in_xml_parser_and_worker(tmp_path, monkeypatch, first, second):
    mesh, _model, profile, setup = prepare(tmp_path)
    objects = (SceneObject("one", first, mesh), SceneObject("two", second, mesh))
    job = pd._PlateJob(
        objects=objects,
        plates=(0,),
        folder=tmp_path,
        name="RM483",
        setup=setup,
        settings=print_settings.resolve(profile),
        profile=profile,
        slot_profiles={},
        with_settings=False,
    )
    run = pd._prepare_plate(job, 0)
    from xml.etree import ElementTree as ET
    from zipfile import ZipFile

    with ZipFile(run.model) as archive:
        xml = ET.fromstring(archive.read("Metadata/Slic3r_PE_model.config"))
        model_xml = ET.fromstring(archive.read("3D/3dmodel.model"))
    written = [entry.get("value") for entry in xml.findall("object/metadata[@key='name']")]
    assert written == [first, second]
    assert [entry.get("name") for entry in model_xml.findall("{*}resources/{*}object")] == [
        first,
        second,
    ]
    monkeypatch.setattr(
        handover,
        "_run_slicer",
        lambda *args, **kwargs: subprocess.CompletedProcess([], 1, b"", native_record(written[1])),
    )
    host = SimpleNamespace(
        _runs=[run],
        _settings=job.settings,
        _profile=profile,
        _setup=setup,
        _usage={},
        cancelled=CancelSignal(),
        step=SignalLog(),
        failed=SignalLog(),
        done=SignalLog(),
    )
    pd._SliceWorker.work(host)
    delivered = host.failed.calls[0][0]
    assert delivered.object_id == "two"
    assert delivered.values["part_name"] == second
    assert second in str(delivered.detail)
    assert objects[0].name == first and objects[1].name == second
