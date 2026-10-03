"""Abbruch vor dem Packer und echte Kontur beim Fensterexport, ohne Fenster."""

from __future__ import annotations

from dataclasses import replace
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import numpy as np
import pytest
import trimesh

from app.core import activation
from app.core.errors import ExternalToolError, OperationCancelled
from app.core.export import handover, writer
from app.core.geom.mesh import MeshData
from app.core.knowledge import print_settings, profiles
from app.core.scene.cancel import CancelSignal
from app.core.types import SceneObject
from app.ui import print_settings_dialog as dialog
from app.ui.dialogs import problem_text


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    for variable in (
        "APPDATA",
        "LOCALAPPDATA",
        "XDG_DATA_HOME",
        "XDG_CONFIG_HOME",
        "XDG_CACHE_HOME",
    ):
        monkeypatch.setenv(variable, str(tmp_path / "user"))
    monkeypatch.setattr(activation, "require", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        handover, "run_limited", lambda *args, **kwargs: pytest.fail("Kein Slicerstart")
    )


def body(key, size=(20, 20, 10), offset=(0, 0, 0), plate=0):
    raw = trimesh.creation.box(extents=size)
    raw.apply_translation((offset[0], offset[1], offset[2] + size[2] / 2))
    return SceneObject(key, key, MeshData.of(raw), plate=plate)


def test_cancellation_after_the_last_fit_does_not_start_the_packer(tmp_path, monkeypatch):
    profile = profiles.make_profile("prusa-mini", "pla")
    setup = handover.SlicerSetup(tmp_path / "prusa-slicer-console.exe", "prusa")
    token = CancelSignal()
    entries = [body("one"), body("two")]
    original_fit = writer._fit_cli_mesh
    original_pack = writer.arrange_on_bed
    counts = {"fit": 0, "pack": 0}

    def fitted(*args, **kwargs):
        result = original_fit(*args, **kwargs)
        counts["fit"] += 1
        if counts["fit"] == len(entries):
            token.cancel()
        return result

    def packed(*args, **kwargs):
        counts["pack"] += 1
        return original_pack(*args, **kwargs)

    monkeypatch.setattr(writer, "_fit_cli_mesh", fitted)
    monkeypatch.setattr(writer, "arrange_on_bed", packed)
    with pytest.raises(OperationCancelled):
        writer.prepare_slicer_meshes(entries, profile, setup, cancelled=token)
    assert counts == {"fit": 2, "pack": 0}
    assert list(tmp_path.iterdir()) == []


def test_failed_packing_keeps_internal_object_ids_out_of_customer_text(tmp_path):
    profile = profiles.make_profile("prusa-mini", "pla")
    setup = handover.SlicerSetup(tmp_path / "prusa-slicer-console.exe", "prusa")
    entries = [body("internal_one", (100, 100, 10)), body("internal_two", (100, 100, 10))]
    with pytest.raises(ExternalToolError) as raised:
        writer.prepare_slicer_meshes(entries, profile, setup)
    text = problem_text(raised.value)
    assert "keine Anordnung" in text
    assert all(entry.id not in text for entry in entries)


@pytest.mark.parametrize("route", ["single", "project"])
@pytest.mark.parametrize("kind", ["triangle", "wider", "higher", "lower"])
def test_window_file_uses_actual_limits_without_packing(tmp_path, monkeypatch, route, kind):
    profile = profiles.make_profile("prusa-mini", "pla")
    if kind == "triangle":
        profile = replace(
            profile,
            printer=replace(profile.printer, printable_area=((-90, -90), (90, -90), (-90, 90))),
        )
        first = body("first", offset=(70, 0, 0))
        keep = False
    elif kind == "wider":
        profile = replace(
            profile,
            printer=replace(
                profile.printer, printable_area=((-95, -95), (95, -95), (95, 95), (-95, 95))
            ),
        )
        first = body("first", size=(188, 188, 10))
        keep = True
    elif kind == "higher":
        profile = replace(profile, printer=replace(profile.printer, printable_height=200))
        first = body("first", size=(20, 20, 190))
        keep = True
    else:
        profile = replace(profile, printer=replace(profile.printer, printable_height=100))
        first = body("first", size=(20, 20, 120))
        keep = False
    entries = (
        (first,) if route == "single" else (first, body("second", offset=(-30, -30, 0), plate=1))
    )
    originals = [entry.mesh.raw.vertices.copy() for entry in entries]
    monkeypatch.setattr(
        writer,
        "_arrange_for_cli",
        lambda *args, **kwargs: pytest.fail("Fensterexport darf nicht packen"),
        raising=False,
    )
    setup = handover.SlicerSetup(tmp_path / "prusa-slicer-console.exe", "prusa")
    job = dialog._PlateJob(
        objects=entries,
        plates=(0,) if route == "single" else (0, 1),
        folder=tmp_path,
        name="Kontur",
        setup=setup,
        settings=print_settings.resolve(profile),
        profile=profile,
        slot_profiles={},
        with_settings=False,
        for_window=True,
    )
    run = dialog._prepare_plate(job, 0) if route == "single" else dialog._prepare_plates(job)
    if route == "single":
        assert run.keep_arrangement is keep
    with ZipFile(run.model) as archive:
        xml = ET.fromstring(archive.read("3D/3dmodel.model"))
    matrix = xml.find("{*}build/{*}item").get("transform")
    assert matrix == ("1 0 0 0 1 0 0 0 1 90 90 0" if keep else None)
    for node, original, entry in zip(
        xml.findall("{*}resources/{*}object"), originals, entries, strict=True
    ):
        written = np.asarray(
            [
                [float(vertex.get(axis)) for axis in "xyz"]
                for vertex in node.findall("{*}mesh/{*}vertices/{*}vertex")
            ]
        )
        np.testing.assert_allclose(written, original, rtol=0, atol=1e-5)
        np.testing.assert_array_equal(entry.mesh.raw.vertices, original)
