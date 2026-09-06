"""Reproduzierbare vollständige Drittanbieter-Beilage für Zielpakete."""

from __future__ import annotations

import hashlib
import json
import sysconfig
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import pytest

from app.branding import APP_VERSION
from app.core.knowledge import licences
from tools import make_licence_notices


def test_every_target_component_has_version_expression_and_full_text() -> None:
    components = make_licence_notices.collect_components()
    expected = {licences.normalise(name) for name in licences.runtime_packages()}

    assert {licences.normalise(component.name) for component in components} == expected
    for component in components:
        assert component.version
        assert licences.licence_allowed(component.expression)
        assert component.texts, component.name
        for notice in component.texts:
            assert notice.content.strip()
            assert hashlib.sha256(notice.content.encode("utf-8")).hexdigest() == notice.sha256


def test_notice_generation_refuses_an_incomplete_target_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    licence_metadata = cast(Any, licences).metadata
    original = licence_metadata.distribution

    def distribution_without_numpy(name: str) -> object:
        if licences.normalise(name) == "numpy":
            raise licence_metadata.PackageNotFoundError(name)
        return original(name)

    monkeypatch.setattr(licence_metadata, "distribution", distribution_without_numpy)
    with pytest.raises(RuntimeError, match=r"numpy.*nicht installiert"):
        make_licence_notices.collect_components()


def test_notice_generation_enforces_direct_dependency_approval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    policy = licences.load_policy()
    known = {
        name: record
        for name, record in policy.known.items()
        if licences.normalise(name) != "certifi"
    }
    monkeypatch.setattr(licences, "load_policy", lambda: replace(policy, known=known))

    with pytest.raises(RuntimeError, match="direkte Abhängigkeit ohne Eintrag"):
        make_licence_notices.collect_components()


def test_checked_in_notice_is_the_deterministic_target_output() -> None:
    """Die eingecheckte Beilage ist das Erzeugnis **ihrer** Plattform, Byte für Byte.

    Sie trägt in der dritten Zeile, wofür sie erzeugt wurde — und das kann nur
    eine Plattform sein: Die Wheels unterscheiden sich (cffi, jeepney und
    SecretStorage auf Linux, pywin32-ctypes auf Windows). Bis zum 02.09.2026
    verglich der Test blind, und die Linux-CI war rot, sobald jemand die Datei
    unter Windows neu erzeugt hatte (df8fae68). Auf der falschen Plattform
    überspringt er sich jetzt und sagt es; das Kundenpaket bekommt seine
    Beilage ohnehin je Plattform aus der Endartefakt-SBOM (build.yml).
    """
    checked_in = make_licence_notices.OUTPUT.read_text(encoding="utf-8")
    head = checked_in.splitlines()[2] if checked_in.count("\n") >= 2 else ""
    here = sysconfig.get_platform()
    if f"`{here}`" not in head:
        pytest.skip(
            f"die eingecheckte Beilage wurde für eine andere Plattform erzeugt ({head.strip()}); "
            f"hier läuft {here} — sie prüft nur die Plattform, für die sie gilt"
        )
    components = make_licence_notices.collect_components()
    expected = make_licence_notices.render_notices(components)

    assert checked_in == expected
    assert make_licence_notices.render_notices(components) == expected


def test_machine_readable_manifest_has_the_same_component_and_text_records() -> None:
    components = make_licence_notices.collect_components()
    document = json.loads(make_licence_notices.render_manifest(components))

    assert document["schema"] == 2
    assert document["target"]
    assert len(document["components"]) == len(components)
    assert [entry["name"] for entry in document["components"]] == [
        component.name for component in components
    ]
    for component, entry in zip(components, document["components"], strict=True):
        assert entry["version"] == component.version
        assert entry["license_expression"] == component.expression
        assert [text["sha256"] for text in entry["texts"]] == [
            text.sha256 for text in component.texts
        ]
    # keyutils: LGPL-2.1-or-later, reist mit der Kerberos-Familie im Linux-Paket
    # (Ubuntus libkrb5 hängt daran) und braucht deshalb den Quellbeleg.
    assert document["release_gate"]["source_delivery"] == [
        "appimage-type2-runtime",
        "geos",
        "keyutils",
        "opencascade-technology",
        "qt",
    ]


def test_fixed_texts_are_hash_checked_and_tied_to_the_target_version(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    original = make_licence_notices.FIXED_MANIFEST
    text = original.read_text(encoding="utf-8").replace(
        'versions = ["6.11.2"]', 'versions = ["0.0.0"]', 1
    )
    temporary = tmp_path / "third_party_licenses.invalid.toml"
    temporary.write_text(text, encoding="utf-8")
    monkeypatch.setattr(make_licence_notices, "FIXED_MANIFEST", temporary)
    try:
        with pytest.raises(RuntimeError, match="passt nicht"):
            make_licence_notices.collect_components()
    finally:
        temporary.unlink()


def test_qt_open_source_route_contains_lgpl_and_its_gpl_basis() -> None:
    component = next(
        entry
        for entry in make_licence_notices.collect_components()
        if licences.normalise(entry.name) == "pyside6"
    )
    names = {text.name for text in component.texts}

    assert component.expression == "LGPL-3.0-only"
    assert "LGPL-3.0.txt" in names
    assert "GPL-3.0.txt" in names
    assert "LicenseRef-Qt-Commercial.txt" not in names


def test_occt_binding_has_wrapper_core_and_linking_exception_texts() -> None:
    component = next(
        entry
        for entry in make_licence_notices.collect_components()
        if licences.normalise(entry.name) == "cadquery-ocp-novtk"
    )
    names = {text.name for text in component.texts}

    assert component.expression == ("Apache-2.0 AND (LGPL-2.1-only WITH OCCT-exception-1.0)")
    assert {"OCP-Apache-2.0.txt", "OCCT-LGPL-2.1.txt", "OCCT-exception-1.0.txt"} <= names


def test_shapely_expression_includes_the_bundled_geos_library() -> None:
    component = next(
        entry
        for entry in make_licence_notices.collect_components()
        if licences.normalise(entry.name) == "shapely"
    )

    assert component.expression == "BSD-3-Clause AND LGPL-2.1-or-later"
    assert any("GEOS" in text.name.upper() for text in component.texts)


def test_bundle_paths_are_a_stable_packaging_and_cra_interface(tmp_path: Path) -> None:
    notice = tmp_path / "package" / "THIRD-PARTY-NOTICES.md"
    manifest = tmp_path / "cra" / "third-party-licenses.json"

    make_licence_notices.write_bundle(notice, manifest)

    assert notice.is_file()
    document = json.loads(manifest.read_text(encoding="utf-8"))
    assert document["schema"] == 2
    assert document["components"]


def test_every_sbom_runtime_family_has_an_explicit_notice_policy() -> None:
    assert set(make_licence_notices._runtime_policies()) == {
        "appimage-type2-runtime",
        "brotli",
        "bzip2",
        "cpython",
        "dbus",
        "e2fsprogs",
        "expat",
        "fontconfig",
        "freetype",
        "freetype-py-native",
        "gcc-runtime",
        "geos",
        "glib",
        "keyutils",
        "krb5",
        "libcap",
        "libffi",
        "libgcrypt",
        "libgpg-error",
        "libpng",
        "libselinux",
        "libuuid",
        "libx11",
        "libxcb",
        "libxkbcommon",
        "lz4",
        "microsoft-visual-cpp-runtime",
        "openblas-numpy",
        "openblas-scipy",
        "opencascade-technology",
        "openssl",
        "pcre2",
        "pyinstaller-bootloader",
        "qt",
        "systemd",
        "uharfbuzz-native",
        "util-linux",
        "vtk-native",
        "wgpu-native",
        "xcb-util",
        "xcb-util-cursor",
        "xcb-util-image",
        "xcb-util-keysyms",
        "xcb-util-renderutil",
        "xcb-util-wm",
        "xz",
        "zlib",
        "zstd",
    }


def test_linux_release_refuses_an_uninventoried_appimage_runtime(tmp_path: Path) -> None:
    package, package_hash = _write_hashed(tmp_path, "Solidon3D.AppImage", b"appimage")
    flatpak, flatpak_hash = _write_hashed(tmp_path, "Solidon3D.flatpak", b"flatpak")
    evidence = tmp_path / "release-evidence.json"
    evidence.write_text(
        json.dumps(
            {
                "schema": 1,
                "product_version": APP_VERSION,
                "target": "linux-x86_64",
                "release_date": "2026-08-31",
                "packages": [
                    {"kind": "appimage", "path": package, "path_sha256": package_hash},
                    {"kind": "flatpak", "path": flatpak, "path_sha256": flatpak_hash},
                ],
                "source_provisions": [],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="AppImage type-2 runtime fehlt"):
        make_licence_notices._verify_release_evidence(
            evidence,
            {
                "metadata": {
                    "component": {"version": APP_VERSION},
                    "properties": [{"name": "solidon:target-platform", "value": "linux-x86_64"}],
                },
                "components": [],
            },
        )


def _write_hashed(root: Path, name: str, content: bytes) -> tuple[str, str]:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return name, hashlib.sha256(content).hexdigest()


def _release_evidence(tmp_path: Path, sbom: dict[str, Any]) -> Path:
    # Ziel und Paketsorten aus der SBOM, nicht fest „win-amd64" mit einem
    # Setup: Der Prüfer hält beides gegen die SBOM, und die trägt hier die
    # laufende Plattform — auf dem Linux-Runner war der Test deshalb rot
    # (02.09.2026), lokal auf Windows grün.
    target = next(
        str(entry["value"])
        for entry in sbom["metadata"]["properties"]
        if entry["name"] == "solidon:target-platform"
    )
    packages = []
    for kind in sorted(make_licence_notices._required_package_kinds(target)):
        package, package_hash = _write_hashed(tmp_path, f"packages/{kind}.bin", kind.encode())
        packages.append({"kind": kind, "path": package, "path_sha256": package_hash})
    generic = {
        str(component["purl"]).split("/", 1)[1].rsplit("@", 1)[0]: str(component["version"])
        for component in sbom["components"]
        if str(component.get("purl", "")).startswith("pkg:generic/")
    }
    provisions = []
    for identifier in ("qt", "opencascade-technology", "geos"):
        source, source_hash = _write_hashed(
            tmp_path, f"sources/{identifier}.tar.xz", f"source:{identifier}".encode()
        )
        relink, relink_hash = _write_hashed(
            tmp_path, f"sources/{identifier}-relink.zip", f"relink:{identifier}".encode()
        )
        provisions.append(
            {
                "component_id": identifier,
                "version": generic[identifier],
                "issuer": "RS Digital",
                "contact": "opensource@rs-digital.example",
                "method": "archive",
                "source_archive": source,
                "source_archive_sha256": source_hash,
                "relink_material": relink,
                "relink_material_sha256": relink_hash,
                "available_until": "2030-09-01",
            }
        )
    evidence = {
        "schema": 1,
        "product_version": APP_VERSION,
        "target": target,
        "release_date": "2026-08-31",
        "packages": packages,
        "source_provisions": provisions,
    }
    path = tmp_path / "release-evidence.json"
    path.write_text(json.dumps(evidence), encoding="utf-8")
    return path


def test_release_evidence_is_fail_closed_for_missing_source_delivery(tmp_path: Path) -> None:
    sbom: dict[str, Any] = {
        "metadata": {
            "component": {"version": APP_VERSION},
            "properties": [{"name": "solidon:target-platform", "value": "win-amd64"}],
        },
        "components": [
            {
                "type": "library",
                "name": "Qt",
                "version": "6.11.2",
                "purl": "pkg:generic/qt@6.11.2",
            }
        ],
    }
    package, package_hash = _write_hashed(tmp_path, "Solidon3D-Setup.exe", b"setup")
    evidence = tmp_path / "release-evidence.json"
    evidence.write_text(
        json.dumps(
            {
                "schema": 1,
                "product_version": APP_VERSION,
                "target": "win-amd64",
                "release_date": "2026-08-31",
                "packages": [
                    {
                        "kind": "windows-installer",
                        "path": package,
                        "path_sha256": package_hash,
                    }
                ],
                "source_provisions": [],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="Quell-/Austauschbeleg fehlt für: qt"):
        make_licence_notices._verify_release_evidence(evidence, sbom)


def test_end_artifact_notice_sbom_and_source_archives_reconcile(tmp_path: Path) -> None:
    from tools import make_sbom

    artifact = tmp_path / "artifact"
    binaries = (
        artifact / "Solidon3D.exe",
        artifact / "_internal" / "python313.dll",
        artifact / "_internal" / "PySide6" / "QtCore.dll",
        artifact / "_internal" / "OCP" / "TKBRep.dll",
        artifact / "_internal" / "shapely" / "geos.dll",
    )
    for binary in binaries:
        binary.parent.mkdir(parents=True, exist_ok=True)
        binary.write_bytes(b"MZ\x90\x00native")
    # Die Stückliste beschreibt das Kundenartefakt, nicht diesen Interpreter:
    # Auf einer Maschine mit 3.14 scheiterte der Abgleich sonst an der
    # geprüften Quellenfassung 3.13 (02.09.2026).
    runtime = next(
        policy
        for policy in make_licence_notices._runtime_policies().values()
        if policy.name == "CPython runtime"
    )
    # **Und das Zielsystem des Artefakts, nicht das des Runners.** Der Baum
    # oben ist ein Windows-Baum (`.exe`, `.dll`); mit der laufenden Plattform
    # verlangte der Prüfer auf dem Linux-Runner die eingebettete
    # AppImage-Laufzeit, die ein Windows-Artefakt nie trägt (02.09.2026).
    sbom = make_sbom.build_bom(
        customer_artifact=artifact,
        platform="win-amd64",
        python_version=min(runtime.versions),
    )
    sbom_path = artifact / "Solidon3D.cdx.json"
    sbom_path.write_text(json.dumps(sbom), encoding="utf-8")
    components = make_licence_notices.collect_artifact_components(sbom)
    (artifact / "THIRD-PARTY-NOTICES.md").write_text(
        make_licence_notices.render_notices(components), encoding="utf-8"
    )
    evidence = _release_evidence(tmp_path, sbom)

    verified = make_licence_notices.verify_release(artifact, sbom_path, evidence)

    assert verified == components
