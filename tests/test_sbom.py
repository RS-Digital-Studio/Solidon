"""Maschinenlesbare Laufzeit-Stückliste nach Bauplan §37.3."""

from __future__ import annotations

import re
from email.message import Message
from pathlib import Path

import pytest
from packaging.markers import default_environment
from packaging.utils import canonicalize_name

from app.branding import APP_NAME, APP_VERSION, DISTRIBUTION_NAME
from app.core.knowledge import licences
from tools import make_sbom

ROOT = Path(__file__).resolve().parent.parent

BUILD_ONLY = {
    "pytest",
    "ruff",
    "mypy",
    "pyinstaller",
    "cython",
    "setuptools",
}

# Offizieller CycloneDX-Release 1.6. Das JSON Schema ist laut Projekt die
# Referenzimplementierung; der Paketierjob prüft die erzeugte Datei vollständig
# dagegen. Dieser Test hält zusätzlich den bewusst kleinen verwendeten
# Ausschnitt eng, ohne eine zweite Schema-Umsetzung zu erfinden.
OFFICIAL_SCHEMA = (
    "https://raw.githubusercontent.com/CycloneDX/specification/"
    "55343ba19dee1785acf1ce9191540d5fd7b590db/schema/bom-1.6.schema.json"
)
PURL = re.compile(r"^pkg:pypi/[a-z0-9._-]+@[^/]+$")


class FakeDistribution:
    """Die wenigen Metadaten, die der Erzeuger aus einer Distribution liest."""

    def __init__(
        self,
        name: str,
        version: str,
        *,
        requires: tuple[str, ...] = (),
        licence: str = "MIT",
    ) -> None:
        metadata = Message()
        metadata["Name"] = name
        metadata["License-Expression"] = licence
        self.metadata = metadata
        self.version = version
        self.requires = requires


def _components(bom: dict[str, object]) -> dict[str, dict[str, object]]:
    return {
        canonicalize_name(str(component["name"])): component
        for component in bom["components"]  # type: ignore[index,union-attr]
    }


def test_the_sbom_contains_the_runtime_closure_but_not_the_build_environment() -> None:
    """Installiert heißt nicht ausgeliefert: Wurzeln sind allein Produkt und Extras."""
    bom = make_sbom.build_bom()
    actual = {
        canonicalize_name(str(component["name"]))
        for component in bom["components"]
        if str(component["purl"]).startswith("pkg:pypi/")
    }
    expected = {canonicalize_name(name) for name in licences.runtime_packages()}

    assert actual == expected
    assert actual.isdisjoint(BUILD_ONLY), sorted(actual & BUILD_ONLY)


def test_every_runtime_component_has_version_licence_purl_and_dependency_entry() -> None:
    bom = make_sbom.build_bom()
    components = _components(bom)
    dependencies = {
        str(entry["ref"]): entry["dependsOn"]
        for entry in bom["dependencies"]  # type: ignore[index,union-attr]
    }

    assert bom["bomFormat"] == "CycloneDX"
    assert bom["specVersion"] == "1.6"
    assert bom["metadata"]["component"]["name"] == APP_NAME  # type: ignore[index,union-attr]
    assert bom["metadata"]["component"]["version"] == APP_VERSION  # type: ignore[index,union-attr]
    for component in components.values():
        assert component["version"]
        assert str(component["purl"]).startswith(("pkg:pypi/", "pkg:generic/"))
        assert component["bom-ref"] == component["purl"]
        assert component["licenses"]
        assert component["bom-ref"] in dependencies


def test_native_libraries_are_owned_by_their_distributions() -> None:
    """Qt, OCCT, GEOS und VTK verschwinden nicht hinter dem Wort „Python"."""
    bom = make_sbom.build_bom()
    components = _components(bom)
    properties = {
        entry["name"]: entry["value"]
        for entry in bom["metadata"]["properties"]  # type: ignore[index,union-attr]
    }

    assert {
        "pyside6-essentials",
        "cadquery-ocp-novtk",
        "shapely",
        "vtk",
    } <= set(components)
    for package in ("pyside6", "pyside6-essentials", "pyside6-addons", "shiboken6"):
        assert components[package]["licenses"] == [{"expression": "LGPL-3.0-only"}]
    assert {
        "qt",
        "open cascade technology",
        "geos",
        "vtk native libraries",
    } <= set(components)
    assert components["qt"]["licenses"] == [{"expression": "LGPL-3.0-only"}]
    assert components["open cascade technology"]["licenses"] == [
        {"expression": "LGPL-2.1-only WITH OCCT-exception-1.0"}
    ]
    assert components["geos"]["licenses"] == [{"expression": "LGPL-2.1-or-later"}]
    assert components["vtk native libraries"]["licenses"] == [{"expression": "BSD-3-Clause"}]
    assert properties["solidon:component-boundary"] == (
        "Declared Python runtime dependency closure with bundled native components"
    )


def test_the_reviewed_policy_wins_over_a_wheels_multi_licence_offer() -> None:
    package = FakeDistribution(
        "PySide6",
        "6.10.1",
        licence="LGPL-3.0-only OR GPL-3.0-only",
    )

    assert make_sbom._licence(package) == [{"expression": "LGPL-3.0-only"}]


def test_markers_extras_and_transitive_edges_describe_the_selected_target() -> None:
    distributions = {
        "solidon3d": FakeDistribution(
            "solidon3d",
            "1.0.0",
            requires=(
                "base>=1",
                "windows-only; sys_platform == 'win32'",
                "linux-only; sys_platform == 'linux'",
                "geometry-extra; extra == 'geom'",
                "developer-only; extra == 'dev'",
            ),
        ),
        "base": FakeDistribution(
            "base",
            "2.0",
            requires=(
                "child>=1; python_version >= '3.13'",
                "old-python; python_version < '3.0'",
            ),
        ),
        "windows-only": FakeDistribution("windows-only", "3.0"),
        "geometry-extra": FakeDistribution("geometry-extra", "4.0"),
        "child": FakeDistribution("child", "5.0"),
    }

    def distribution(name: str) -> FakeDistribution:
        return distributions[canonicalize_name(name)]

    environment = default_environment()
    environment.update({"sys_platform": "win32", "python_version": "3.13"})
    graph = make_sbom.runtime_graph(
        distribution=distribution,
        extras=("geom",),
        environment=environment,
    )

    assert set(graph.distributions) == {
        "base",
        "windows-only",
        "geometry-extra",
        "child",
    }
    assert graph.edges["solidon3d"] == {"base", "windows-only", "geometry-extra"}
    assert graph.edges["base"] == {"child"}


def test_the_same_runtime_graph_always_writes_the_same_bytes() -> None:
    distributions = {
        "solidon3d": FakeDistribution("solidon3d", "1.0", requires=("zeta", "alpha")),
        "alpha": FakeDistribution("alpha", "2.0"),
        "zeta": FakeDistribution("zeta", "3.0"),
    }

    def distribution(name: str) -> FakeDistribution:
        return distributions[canonicalize_name(name)]

    first = make_sbom.render_bom(
        make_sbom.build_bom(distribution=distribution, version="1.0", platform="test-target")
    )
    second = make_sbom.render_bom(
        make_sbom.build_bom(distribution=distribution, version="1.0", platform="test-target")
    )

    assert first == second
    assert '"timestamp"' not in first
    assert '"serialNumber"' not in first
    assert first.index('"name": "alpha"') < first.index('"name": "zeta"')


def test_a_missing_runtime_package_stops_with_the_way_back() -> None:
    distributions = {
        "solidon3d": FakeDistribution("solidon3d", "1.0", requires=("missing",)),
    }

    def distribution(name: str) -> FakeDistribution:
        return distributions[canonicalize_name(name)]

    with pytest.raises(RuntimeError) as caught:
        make_sbom.runtime_graph(distribution=distribution)

    message = str(caught.value)
    assert "missing" in message
    assert "Installieren Sie" in message
    assert "constraints.txt" in message


def test_an_installed_version_outside_the_declared_range_stops_the_build() -> None:
    distributions = {
        "solidon3d": FakeDistribution("solidon3d", "1.0", requires=("base>=2",)),
        "base": FakeDistribution("base", "1.5"),
    }

    def distribution(name: str) -> FakeDistribution:
        return distributions[canonicalize_name(name)]

    with pytest.raises(RuntimeError) as caught:
        make_sbom.runtime_graph(distribution=distribution)

    message = str(caught.value)
    assert "base" in message
    assert "1.5" in message
    assert ">=2" in message
    assert "constraints.txt" in message


def test_the_pyinstaller_analysis_reduces_the_conservative_runtime_preview() -> None:
    distributions = {
        "solidon3d": FakeDistribution(
            "solidon3d",
            "1.0",
            requires=("used", "declared-but-not-packaged"),
        ),
        "used": FakeDistribution("used", "2.0"),
        "declared-but-not-packaged": FakeDistribution("declared-but-not-packaged", "3.0"),
    }

    def distribution(name: str) -> FakeDistribution:
        return distributions[canonicalize_name(name)]

    package_map = {"used_import": ("used",), "Cython": ("Cython",)}
    included = make_sbom.distributions_for_analysis(
        [
            ("used_import.module", "somewhere/used_import/module.py", "PYMODULE"),
            ("Cython.Compiler", "somewhere/Cython/Compiler.py", "PYMODULE"),
        ],
        package_map=package_map,
    )
    bom = make_sbom.build_bom(
        distribution=distribution,
        included_distributions=included,
        version="1.0",
        platform="test-target",
    )
    properties = {entry["name"]: entry["value"] for entry in bom["metadata"]["properties"]}

    assert set(_components(bom)) == {"used"}
    assert properties["solidon:component-boundary"] == (
        "PyInstaller-analyzed customer artifact with bundled native components and files"
    )


def test_the_finished_artifact_exposes_every_native_file_and_runtime_family(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Distributionen allein verschweigen Interpreter, Bootloader und Vendor-DLLs."""
    names = (
        "Solidon3D.exe",
        "_internal/python313.dll",
        "_internal/libssl-3-x64.dll",
        "_internal/libcrypto-3-x64.dll",
        "_internal/libffi-8.dll",
        "_internal/numpy.libs/libscipy_openblas64_test.dll",
        "_internal/scipy.libs/libscipy_openblas_test.dll",
        "_internal/scipy.libs/libgfortran-5.dll",
        "_internal/PySide6/Qt6Core.dll",
        "_internal/PySide6/VCRUNTIME140.dll",
        "_internal/cadquery_ocp_novtk.libs/TKernel-test.dll",
        "_internal/vtk.libs/vtkCommonCore-test.dll",
        "_internal/vendor/without-owner.dll",
    )
    for name in names:
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"MZ\x90\x00native")
    (tmp_path / "_internal" / "not-native.dll").write_text("nur Text", encoding="utf-8")
    monkeypatch.setattr(
        make_sbom,
        "_pe_file_version",
        lambda path: (
            "14.44.35211.0"
            if path.name.casefold().startswith(("msvcp", "vcruntime", "ucrtbase", "api-ms-win-crt"))
            else "unbekannt"
        ),
    )

    files = make_sbom.artifact_files(tmp_path)
    bom = make_sbom.build_bom(customer_artifact=tmp_path)
    components = {str(component["name"]): component for component in bom["components"]}
    component_names = set(components)

    assert {entry.path for entry in files} == set(names)
    assert {
        "CPython runtime",
        "PyInstaller bootloader",
        "OpenSSL",
        "libffi",
        "OpenBLAS (numpy)",
        "OpenBLAS (scipy)",
        "GCC Runtime Libraries",
        "Microsoft Visual C++ Runtime",
    } <= component_names
    assert components["Microsoft Visual C++ Runtime"]["version"] == "14.44.35211.0"
    assert (
        next(
            item["value"]
            for item in components["Microsoft Visual C++ Runtime"]["properties"]
            if item["name"] == "solidon:version-source"
        )
        == "PE FileVersion der gebündelten Laufzeitdateien"
    )
    assert set(names) <= component_names
    assert components["_internal/vendor/without-owner.dll"]["properties"] == [
        {"name": "solidon:artifact-path", "value": "_internal/vendor/without-owner.dll"},
        {"name": "solidon:bundled-by", "value": "unassigned-native"},
        {
            "name": "solidon:licence-source",
            "value": "Lizenzbeilage der Besitzerkomponente; unbekannt bleibt offen",
        },
    ]
    assert all(
        component["type"] == "file" for name, component in components.items() if name in names
    )
    assert all(
        entry["ref"]
        in {component["bom-ref"] for component in bom["components"]}
        | {bom["metadata"]["component"]["bom-ref"]}
        for entry in bom["dependencies"]
    )


def test_windows_libffi_is_bound_to_the_pinned_cpython_build() -> None:
    """ABI 8 allein darf nicht als Quellversion in der Lizenzakte landen."""
    assert make_sbom._libffi_version(target_platform="win32", python_version="3.13.14") == (
        "3.4.4",
        "CPython 3.13.14 PCbuild/python.props",
    )
    assert (
        make_sbom._libffi_version(target_platform="win32", python_version="3.13.15")[0]
        == "unbekannt"
    )


def test_the_artifact_locator_ignores_the_macos_collect_intermediate(
    tmp_path: Path,
) -> None:
    collect = tmp_path / APP_NAME / "_internal" / "Solidon3D.cdx.json"
    bundle = tmp_path / f"{APP_NAME}.app" / "Contents" / "Frameworks" / "Solidon3D.cdx.json"
    collect.parent.mkdir(parents=True)
    bundle.parent.mkdir(parents=True)
    collect.write_text("collect", encoding="utf-8")
    bundle.write_text("bundle", encoding="utf-8")

    assert make_sbom.locate_artifact_sbom(tmp_path, platform="darwin") == bundle
    assert make_sbom.locate_artifact_sbom(tmp_path, platform="win32") == collect


def test_the_artifact_locator_rejects_missing_or_duplicate_customer_sboms(
    tmp_path: Path,
) -> None:
    root = tmp_path / APP_NAME
    root.mkdir()
    with pytest.raises(RuntimeError, match="0-mal"):
        make_sbom.locate_artifact_sbom(tmp_path, platform="linux")

    first = root / "_internal" / "Solidon3D.cdx.json"
    second = root / "copy" / "Solidon3D.cdx.json"
    first.parent.mkdir()
    second.parent.mkdir()
    first.write_text("first", encoding="utf-8")
    second.write_text("second", encoding="utf-8")
    with pytest.raises(RuntimeError, match="2-mal"):
        make_sbom.locate_artifact_sbom(tmp_path, platform="linux")


def test_the_build_creates_and_bundles_the_sbom_from_the_target_environment() -> None:
    spec = (ROOT / "packaging" / "solidon3d.spec").read_text(encoding="utf-8")
    workflow = (ROOT / ".github" / "workflows" / "build.yml").read_text(encoding="utf-8")

    assert "make_sbom.distributions_for_analysis(" in spec
    assert "included_distributions=_included_distributions" in spec
    assert "customer_artifact=_artifact" in spec
    assert "Path(DISTPATH)" in spec
    assert 'analysis.datas.append((SBOM_FILE.name, str(SBOM_FILE), "DATA"))' not in spec
    assert spec.index("analysis = Analysis(") < spec.index("make_sbom.write_bom(")
    assert spec.index("collected = COLLECT(") < spec.index("make_sbom.write_bom(")
    assert spec.index("bundle = BUNDLE(") < spec.index("make_sbom.write_bom(")
    assert '"icuuc.dll"' in spec
    assert 'name.startswith("icudt")' in spec
    assert '"Cython"' in spec and '"setuptools"' in spec
    package_job = workflow.split("  package:", 1)[1]
    assert package_job.count("pyinstaller packaging/solidon3d.spec") == 1
    assert OFFICIAL_SCHEMA in package_job
    # Als Modul: `python tools/x.py` setzt sys.path auf `tools/`, und der
    # Prüfjob fiel damit über `from tools import make_sbom` (Tag-Lauf 10).
    assert "python -m tools.make_sbom --locate-artifact dist" in package_job
    assert 'Get-ChildItem -LiteralPath "dist"' not in package_job
    assert "Test-Json" in package_job


def test_the_emitted_subset_stays_inside_the_official_schema_contract() -> None:
    """Der vollständige Schema-Lauf steht im Build; hier bleibt unser Ausschnitt klein."""
    bom = make_sbom.build_bom()
    assert set(bom) == {
        "$schema",
        "bomFormat",
        "specVersion",
        "version",
        "metadata",
        "components",
        "dependencies",
    }
    assert bom["$schema"] == "https://cyclonedx.org/schema/bom-1.6.schema.json"
    assert isinstance(bom["version"], int) and bom["version"] >= 1

    metadata = bom["metadata"]
    assert set(metadata) == {"component", "properties"}
    product = metadata["component"]
    assert set(product) == {"type", "bom-ref", "name", "version", "supplier", "purl"}
    assert product["type"] == "application"
    assert PURL.fullmatch(product["purl"])
    assert product["bom-ref"] == product["purl"]
    assert set(product["supplier"]) == {"name"}
    assert all(set(entry) == {"name", "value"} for entry in metadata["properties"])

    references = {product["bom-ref"]}
    for component in bom["components"]:
        common = {"type", "bom-ref", "name", "version", "purl", "licenses"}
        assert component["type"] in {"library", "file"}
        if component["type"] == "file":
            assert set(component) == {"type", "bom-ref", "name", "version", "properties"}
            assert str(component["bom-ref"]).startswith("urn:solidon:native-file:")
            assert component["properties"]
        elif str(component["purl"]).startswith("pkg:pypi/"):
            assert set(component) == common
            assert PURL.fullmatch(component["purl"])
        else:
            assert set(component) == common | {"externalReferences", "properties"}
            assert str(component["purl"]).startswith("pkg:generic/")
            assert component["externalReferences"]
            assert component["properties"]
        if component["type"] == "library":
            assert component["bom-ref"] == component["purl"]
        references.add(component["bom-ref"])
        for choice in component.get("licenses", []):
            assert set(choice) in ({"expression"}, {"license"})
            if "license" in choice:
                assert set(choice["license"]) == {"name"}

    for dependency in bom["dependencies"]:
        assert set(dependency) == {"ref", "dependsOn"}
        assert dependency["ref"] in references
        assert set(dependency["dependsOn"]) <= references


def test_the_product_root_uses_the_declared_distribution_name() -> None:
    bom = make_sbom.build_bom()
    product = bom["metadata"]["component"]  # type: ignore[index,union-attr]

    assert product["purl"].startswith(f"pkg:pypi/{DISTRIBUTION_NAME}@")


def test_linux_and_macos_artifacts_carry_owners_for_every_native_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Das Linux-Paket 0.2.1 hatte 135 native Dateien ohne Besitzer, das
    macOS-Paket 41, das Windows-Paket 30 — und die Releaseakte lehnt jede ab.

    Vier Gestalten: CPythons Modulordner ``lib-dynload`` (vierzig auf Linux
    wie auf macOS), die vendorisierten Bibliotheken eines reparierten Wheels
    (``pillow.libs``), die Systembibliotheken, die das Paket bewusst mitnimmt
    (xcb, xkbcommon, Kerberos), und die Weiterleitungs-DLLs der
    Microsoft-Laufzeit. Dazu der Verweis: PyInstaller legt für den Lader
    Symlinks an, und ein Verweis ist keine zweite Datei.
    """
    elf = b"\x7fELF\x02\x01\x01" + b"\x00" * 9
    names = {
        "_internal/python3.13/lib-dynload/_bisect.cpython-313-x86_64-linux-gnu.so": "cpython",
        "Contents/Frameworks/python3.13/lib-dynload/math.cpython-313-darwin.so": "cpython",
        "_internal/libxcb-cursor.so.0": "xcb-util-cursor",
        "_internal/libxcb-icccm.so.4": "xcb-util-wm",
        "_internal/libxcb-render-util.so.0": "xcb-util-renderutil",
        "_internal/libxcb-randr.so.0": "libxcb",
        "_internal/libxkbcommon-x11.so.0": "libxkbcommon",
        "_internal/libgssapi_krb5.so.2": "krb5",
        "_internal/libcom_err.so.2": "e2fsprogs",
        "_internal/libkeyutils.so.1": "keyutils",
        "_internal/pillow.libs/libjpeg-31e2ca52.so.62.4.0": "pillow",
    }
    for name in names:
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(elf)
    for name in ("_internal/api-ms-win-core-file-l1-1-0.dll", "_internal/_wmi.pyd"):
        (tmp_path / name).write_bytes(b"MZ\x90\x00native")
    link: Path | None = tmp_path / "_internal" / "libxcb-randr-link.so.0"
    try:
        assert link is not None
        link.symlink_to(tmp_path / "_internal" / "libxcb-randr.so.0")
    except OSError:  # ohne Recht auf Symlinks bleibt der Fall ungeprüft, nicht rot
        link = None

    files = make_sbom.artifact_files(tmp_path)
    owners = {entry.path: entry.owner for entry in files}
    assert {path: owners[path] for path in names} == names
    assert owners["_internal/api-ms-win-core-file-l1-1-0.dll"] == "msvc-runtime"
    assert owners["_internal/_wmi.pyd"] == "cpython"
    if link is not None:
        assert "_internal/libxcb-randr-link.so.0" not in owners, "ein Verweis ist keine Datei"
    assert not [path for path, owner in owners.items() if owner == "unassigned-native"]

    monkeypatch.setattr(
        make_sbom,
        "_dpkg_version",
        lambda soname: (
            "0.1.4" if "cursor" in soname else "1.15",
            f"dpkg-query -W ({soname})",
        ),
    )
    components = {
        str(component["name"]): component
        for component in make_sbom.runtime_components(files, python_version="3.13.14")
    }
    assert {
        "xcb-util-cursor",
        "xcb-util-wm",
        "xcb-util-renderutil",
        "libxcb",
        "libxkbcommon",
        "MIT Kerberos",
        "e2fsprogs com_err",
        "keyutils",
    } <= set(components)
    assert components["xcb-util-cursor"]["version"] == "0.1.4"
    assert components["xcb-util-cursor"]["purl"] == "pkg:generic/xcb-util-cursor@0.1.4"
    assert components["keyutils"]["licenses"] == [{"expression": "LGPL-2.1-or-later"}]
    assert components["MIT Kerberos"]["licenses"] == [{"expression": "MIT"}]


def test_a_debian_package_version_is_read_from_its_library(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``dpkg-query -S`` nennt das Paket zur Datei, ``-W`` seine Fassung, und vor
    dem Bindestrich steht die des Projekts — Epoche und Debian-Revision fallen weg."""
    import subprocess

    answers = {
        "-S": "libxcb-cursor0:amd64: /usr/lib/x86_64-linux-gnu/libxcb-cursor.so.0.0.0\n"
        "libxcb-cursor0:amd64: /usr/lib/x86_64-linux-gnu/libxcb-cursor.so.0\n",
        "-W": "1:0.1.4-1build1",
    }

    def fake_run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(command, 0, stdout=answers[command[1]], stderr="")

    monkeypatch.setattr(make_sbom.shutil, "which", lambda name: "/usr/bin/dpkg-query")
    monkeypatch.setattr(make_sbom.subprocess, "run", fake_run)
    assert make_sbom._dpkg_version("libxcb-cursor.so.0") == (
        "0.1.4",
        "dpkg-query -W libxcb-cursor0 (1:0.1.4-1build1)",
    )

    monkeypatch.setattr(make_sbom.shutil, "which", lambda name: None)
    assert make_sbom._dpkg_version("libxcb-cursor.so.0") == ("unbekannt", "dpkg-query fehlt")
