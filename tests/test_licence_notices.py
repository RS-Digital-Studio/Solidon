"""Reproduzierbare vollständige Drittanbieter-Beilage für Zielpakete."""

from __future__ import annotations

import hashlib
import json
import sysconfig
import tomllib
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import pytest

from app.branding import APP_VERSION
from app.core.knowledge import licences
from tools import make_licence_notices


def test_openssl_uses_the_canonical_apache_text_without_foreign_attribution() -> None:
    """Die Laufzeit darf nicht das Copyright der OCP-Beilage übernehmen."""
    records = make_licence_notices._fixed_records("runtime")
    notices = [notice for _versions, notice in records["openssl"]]
    assert len(notices) == 1
    assert notices[0].name == "Apache-2.0.txt"
    assert "Copyright [yyyy] [name of copyright owner]" in notices[0].content
    assert "OCP contributors" not in notices[0].content


def test_appimage_and_glib_use_the_same_canonical_lgpl_source() -> None:
    """Dieselbe GNU-Quelle bezeichnet dieselben Bytes, nicht die ältere OCCT-Kopie."""
    records = make_licence_notices._fixed_records("runtime")
    source = "https://www.gnu.org/licenses/old-licenses/lgpl-2.1.txt"
    appimage = next(
        notice for _versions, notice in records["appimage-type2-runtime"] if notice.source == source
    )
    glib = next(notice for _versions, notice in records["glib"] if notice.source == source)
    assert appimage.content == glib.content
    assert appimage.sha256 == glib.sha256


def test_fixed_licence_sources_do_not_follow_development_branches() -> None:
    """Eine Lizenzakte darf nicht unbemerkt dem nächsten Entwicklungsstand folgen."""
    with make_licence_notices.FIXED_MANIFEST.open("rb") as stream:
        records = tomllib.load(stream)["text"]
    moving = [
        record["path"]
        for record in records
        if any(
            marker in record["source"]
            for marker in ("/master/", "/main/", "?h=master", "?h=main", "/HEAD/")
        )
    ]
    assert not moving, moving


@pytest.mark.parametrize("family", ["Liberation", "Comfortaa", "DancingScript"])
def test_font_licence_corruption_is_rejected(
    family: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Auch reine Schriftbeilagen müssen den gehashten Quelltext behalten."""
    from app.core.geom.label_ops import BUNDLED_FONT_LICENCES

    filename = BUNDLED_FONT_LICENCES[family]
    manifest = make_licence_notices.FIXED_MANIFEST.read_text(encoding="utf-8")
    matching = [
        block
        for block in manifest.split("[[text]]")[1:]
        if f'path = "third_party_licenses/{filename}"' in block
    ]
    assert len(matching) == 1, filename
    manifest_path = tmp_path / "third_party_licenses.toml"
    manifest_path.write_text("[[text]]" + matching[0], encoding="utf-8")
    target = tmp_path / "third_party_licenses" / filename
    target.parent.mkdir()
    target.write_bytes(
        (make_licence_notices.FIXED_ROOT / "third_party_licenses" / filename).read_bytes()
    )
    monkeypatch.setattr(make_licence_notices, "FIXED_MANIFEST", manifest_path)
    monkeypatch.setattr(make_licence_notices, "FIXED_ROOT", tmp_path)
    assert make_licence_notices._fixed_records() == {}
    target.write_text("Lizenztext wurde abgeschnitten.\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="Prüfen Sie Quelle und Manifest gemeinsam"):
        make_licence_notices._fixed_records()


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


def test_the_notice_names_whether_native_artifact_families_are_present() -> None:
    """Eine Wheel-Vorschau behauptet nicht den Inhalt einer fertigen Paketbeilage."""
    wheels = make_licence_notices.collect_components()
    preview = make_licence_notices.render_notices(wheels).split("| Paket |")[0]
    assert "Entwicklungsvorschau" in preview
    assert "erst in der Beilage des gebauten Pakets" in preview
    native = make_licence_notices.ComponentNotice(
        name="CPython runtime",
        version="3.14.0",
        expression="Python-2.0",
        source_url="https://www.python.org/",
        texts=(),
    )
    artifact = make_licence_notices.render_notices((*wheels, native)).split("| Paket |")[0]
    assert "Entwicklungsvorschau" not in artifact
    assert "Quelle sind" in artifact and "Stückliste (SBOM) des gebauten Pakets" in artifact


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


class _RenumberedDistribution:
    """Dieselbe installierte Distribution unter einer anderen Wheel-Version."""

    def __init__(self, wrapped: Any, version: str) -> None:
        self._wrapped = wrapped
        self.version = version

    def __getattr__(self, name: str) -> Any:
        return getattr(self._wrapped, name)


def _renumber_wheel(monkeypatch: pytest.MonkeyPatch, package: str, version: str) -> None:
    """Lässt ``package`` als neue Wheel-Fassung mit unveränderter Bibliothek erscheinen."""
    original = make_licence_notices.metadata.distribution

    def distribution(name: str) -> Any:
        found = original(name)
        if licences.normalise(name) == licences.normalise(package):
            return _RenumberedDistribution(found, version)
        return found

    monkeypatch.setattr(make_licence_notices.metadata, "distribution", distribution)


def test_a_wheel_patch_with_the_verified_native_library_keeps_its_notice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Der HarfBuzz-Text gilt der eingebetteten HarfBuzz-Fassung, nicht der Wheel-Nummer.

    Am 22.09.2026 war der Versionswächter rot, weil uharfbuzz 0.56.2 erschien:
    Der Text war an die Wheel-Version 0.56.1 gebunden, obwohl er die
    mitgelieferte Bibliothek beschreibt. Eine neue Wheel-Fassung mit derselben,
    geprüften Bibliothek hat denselben Lizenztext.
    """
    _renumber_wheel(monkeypatch, "uharfbuzz", "0.56.99")
    component = next(
        entry
        for entry in make_licence_notices.collect_components()
        if licences.normalise(entry.name) == "uharfbuzz"
    )
    assert component.version == "0.56.99"
    assert "HarfBuzz-14.4.0-COPYING.txt" in {text.name for text in component.texts}


def test_an_unverified_native_library_stops_the_notice_with_a_way_out(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bringt ein Wheel eine ungeprüfte Bibliothek mit, bleibt die Beilage rot —
    und sagt, welche Fassung es ist und was zu tun ist."""
    from tools import make_sbom

    original = make_sbom.native_library_version

    def native(slug: str, package: Any) -> str:
        return "99.0.0" if slug == "uharfbuzz-native" else original(slug, package)

    monkeypatch.setattr(make_sbom, "native_library_version", native)
    with pytest.raises(RuntimeError, match="passt nicht") as caught:
        make_licence_notices.collect_components()
    message = str(caught.value)
    assert "99.0.0" in message
    assert "third_party_licenses.toml" in message and "vergleichen" in message


def test_native_text_pins_and_runtime_families_name_the_same_versions() -> None:
    """Ein an die Bibliothek gebundener Text und ihre Laufzeitfamilie halten
    dieselbe geprüfte Liste — sonst ist die Beilage grün und die Paketakte rot."""
    with make_licence_notices.FIXED_MANIFEST.open("rb") as stream:
        document = tomllib.load(stream)
    policies = make_licence_notices._runtime_policies()
    bound = [entry for entry in document["text"] if entry.get("native")]
    assert {entry["native"] for entry in bound} >= {
        "uharfbuzz-native",
        "freetype-py-native",
        "wgpu-native",
    }
    for entry in bound:
        policy = policies[entry["native"]]
        assert set(entry["versions"]) == set(policy.versions), entry["path"]
        assert {licences.normalise(name) for name in entry["packages"]} == {
            licences.normalise(policy.notice_package)
        }, entry["path"]


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


@pytest.mark.parametrize(
    ("version", "reviewed"), [("6.22.2", True), ("6.22.3", True), ("6.22.4", False)]
)
def test_pyinstaller_uses_the_reviewed_versions_own_wheel_notice(
    version: str, reviewed: bool, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Latest darf seinen geprüften neuen Text liefern; unbekannte Fassungen halten an."""
    dist_info = tmp_path / f"pyinstaller-{version}.dist-info"
    notice = dist_info / "licenses" / "COPYING.txt"
    notice.parent.mkdir(parents=True)
    content = f"Lizenztext aus dem Test-Wheel {version}.\n"
    notice.write_text(content, encoding="utf-8")
    (dist_info / "METADATA").write_text(
        f"Metadata-Version: 2.1\nName: pyinstaller\nVersion: {version}\n", encoding="utf-8"
    )
    (dist_info / "RECORD").write_text(
        f"{dist_info.name}/licenses/COPYING.txt,,\n", encoding="utf-8"
    )
    package = make_licence_notices.metadata.Distribution.at(dist_info)
    monkeypatch.setattr(make_licence_notices.metadata, "distribution", lambda _name: package)
    monkeypatch.setattr(make_licence_notices, "collect_components", lambda: ())
    sbom = {
        "components": [
            {
                "type": "library",
                "name": "PyInstaller bootloader",
                "version": version,
                "purl": f"pkg:generic/pyinstaller-bootloader@{version}",
                "licenses": [
                    {"expression": "GPL-2.0-or-later WITH PyInstaller Bootloader Exception"}
                ],
            }
        ]
    }
    if not reviewed:
        with pytest.raises(RuntimeError, match="passt nicht zur geprüften Quellenfassung"):
            make_licence_notices.collect_artifact_components(sbom)
        return

    components = make_licence_notices.collect_artifact_components(sbom)

    assert len(components) == 1
    assert components[0].version == version
    assert components[0].source_url == "https://github.com/pyinstaller/pyinstaller"
    assert len(components[0].texts) == 1
    assert components[0].texts[0].content == content
    assert components[0].texts[0].sha256 == hashlib.sha256(content.encode("utf-8")).hexdigest()


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

    sbom: dict[str, Any] = {
        "metadata": {
            "component": {"version": APP_VERSION},
            "properties": [{"name": "solidon:target-platform", "value": "linux-x86_64"}],
        },
        "components": [],
    }
    with pytest.raises(RuntimeError, match="AppImage type-2 runtime fehlt"):
        make_licence_notices._verify_release_evidence(evidence, sbom, artifact_kind="appimage")
    # Der App-Baum und das Flatpak tragen den Kern nicht und müssen ihn auch
    # nicht nennen: Bis zum 22.09.2026 verlangte die Prüfung ihn von jeder
    # Linux-Stückliste, und die Linux-Releaseakte war ohne Ausweg rot.
    make_licence_notices._verify_release_evidence(evidence, sbom)


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


def test_the_appimage_content_names_its_runtime_and_passes_the_release_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der Weg des AppImage: App-Baum kopieren, Laufzeitkern eintragen, prüfen.

    ``make_linux_packages.embed_appimage_runtime`` schreibt Stückliste und
    Beilage des AppImage-Inhalts; ``verify_release`` mit ``appimage`` nimmt
    sie an, ohne diese Sorte weist er dieselbe Stückliste ab. Die Beilage
    nennt jeden statisch eingebundenen Bestandteil mit seinem Text.
    """
    from tools import make_linux_packages, make_sbom

    artifact = tmp_path / "artifact"
    for binary in (artifact / "Solidon3D.exe", artifact / "_internal" / "python313.dll"):
        binary.parent.mkdir(parents=True, exist_ok=True)
        binary.write_bytes(b"MZ\x90\x00native")
    runtime_policy = make_licence_notices._runtime_policies()["cpython"]
    sbom = make_sbom.build_bom(
        customer_artifact=artifact,
        platform="win-amd64",
        python_version=min(runtime_policy.versions),
    )
    sbom_path = artifact / "_internal" / "Solidon3D.cdx.json"
    sbom_path.write_text(json.dumps(sbom), encoding="utf-8")
    (artifact / "THIRD-PARTY-NOTICES.md").write_text("vorher\n", encoding="utf-8")
    runtime = tmp_path / "runtime-x86_64"
    runtime.write_bytes(b"\x7fELF-Laufzeitkern")
    monkeypatch.setattr(
        make_sbom, "APPIMAGE_RUNTIME_SHA256", hashlib.sha256(runtime.read_bytes()).hexdigest()
    )

    written = make_linux_packages.embed_appimage_runtime(artifact, runtime)

    document = json.loads(written.read_text(encoding="utf-8"))
    runtime_entry = next(
        entry
        for entry in document["components"]
        if entry.get("purl") == "pkg:generic/appimage-type2-runtime@20251108"
    )
    static = [
        item["value"]
        for item in runtime_entry["properties"]
        if item["name"] == "solidon:static-component"
    ]
    assert [value.split(" ", 1)[0] for value in static] == [
        "libfuse",
        "squashfuse",
        "zstd",
        "zlib",
        "musl",
        "mimalloc",
    ]
    notice = (artifact / "THIRD-PARTY-NOTICES.md").read_text(encoding="utf-8")
    for text in (
        "AppImage-type2-runtime-dd6cebe.txt",
        "LGPL-2.1.txt",
        "squashfuse-0.5.2.txt",
        "zstd-1.5.5.txt",
        "zlib-1.3.txt",
        "musl-1.2.5.txt",
        "mimalloc-2.1.7.txt",
    ):
        assert f"#### {text}" in notice, text
    evidence = _release_evidence(tmp_path, document)
    offers = json.loads(evidence.read_text(encoding="utf-8"))
    offers["source_provisions"].append(
        {
            "component_id": "appimage-type2-runtime",
            "version": "20251108",
            "issuer": "RS Digital",
            "contact": "opensource@rs-digital.example",
            "method": "written-offer",
            "offer_text": "Quelltext auf Anfrage.",
            "relink_method": "shared-library-replacement",
            "available_until": "2030-09-01",
        }
    )
    evidence.write_text(json.dumps(offers), encoding="utf-8")

    make_licence_notices.verify_release(artifact, written, evidence, artifact_kind="appimage")
    with pytest.raises(RuntimeError, match="kein AppImage-Inhalt"):
        make_licence_notices.verify_release(artifact, written, evidence)


def test_a_foreign_appimage_runtime_is_refused(tmp_path: Path) -> None:
    """Ein anderer Laufzeitkern trüge andere statische Bestandteile."""
    from tools import make_sbom

    runtime = tmp_path / "runtime-x86_64"
    runtime.write_bytes(b"anderer Kern")
    with pytest.raises(RuntimeError, match="SHA-256"):
        make_sbom.with_appimage_runtime(
            {"metadata": {"component": {"bom-ref": "x"}}, "components": [], "dependencies": []},
            runtime,
        )


def test_a_missing_notice_distribution_names_the_install_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Die Releaseakte 0.4.4 starb auf Linux und macOS mit einem Stapelabzug,
    weil ``pyinstaller`` in der Prüfumgebung fehlte (Lauf 35464068433)."""
    original = make_licence_notices.metadata.distribution

    def without_pyinstaller(name: str) -> Any:
        if licences.normalise(name) == "pyinstaller":
            raise make_licence_notices.metadata.PackageNotFoundError(name)
        return original(name)

    monkeypatch.setattr(make_licence_notices.metadata, "distribution", without_pyinstaller)
    policy = make_licence_notices._runtime_policies()["pyinstaller-bootloader"]
    with pytest.raises(RuntimeError, match=r"pip install -c constraints\.txt pyinstaller"):
        make_licence_notices._runtime_texts(policy, "6.22.2")
