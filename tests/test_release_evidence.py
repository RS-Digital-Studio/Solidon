"""Die Release-Evidenz: geschrieben von demselben Werkzeug, das sie prüft.

Bis zum 02.09.2026 gab es nur den Prüfer. ``--release-check`` verlangte
``build/release-evidence.json``, kein Schritt schrieb sie, und jeder
Releaseakte-Job wäre am ersten Aufruf mit ``FileNotFoundError`` gestorben —
auf allen drei Plattformen, unbemerkt, weil jeder Tag-Lauf seit dem Einbau
vorher abgebrochen worden war.

Geprüft wird hier der Vertrag zwischen Schreiber und Prüfer an einer kleinen
SBOM: Was der Schreiber legt, nimmt der Prüfer an; was fehlt oder gefälscht
ist, lehnt er ab.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pytest

from app.branding import APP_VERSION
from tools import make_licence_notices as notices


def _sbom(path: Path, target: str = "linux-x86_64") -> Path:
    """Eine Endartefakt-SBOM mit den Familien, die ein Quellenangebot brauchen."""
    document = {
        "metadata": {
            "component": {"name": "Solidon3D", "version": APP_VERSION},
            "properties": [{"name": "solidon:target-platform", "value": target}],
        },
        "components": [
            {"type": "library", "name": "qt", "version": "6.11.2", "purl": "pkg:generic/qt@6.11.2"},
            {
                "type": "library",
                "name": "geos",
                "version": "3.13.1",
                "purl": "pkg:generic/geos@3.13.1",
            },
            {
                "type": "library",
                "name": "appimage-type2-runtime",
                "version": "20251108",
                "purl": "pkg:generic/appimage-type2-runtime@20251108",
            },
        ],
    }
    sbom = path / "Solidon3D.cdx.json"
    sbom.write_text(json.dumps(document), encoding="utf-8")
    return sbom


def _packages(root: Path) -> dict[str, Path]:
    root.mkdir(parents=True, exist_ok=True)
    appimage = root / "Solidon3D-0.0.0-x86_64.AppImage"
    flatpak = root / "Solidon3D-0.0.0-x86_64.flatpak"
    appimage.write_bytes(b"appimage")
    flatpak.write_bytes(b"flatpak")
    return {"appimage": appimage, "flatpak": flatpak}


def test_what_the_writer_lays_down_the_checker_accepts(tmp_path: Path) -> None:
    sbom = _sbom(tmp_path)
    build = tmp_path / "build"
    evidence = build / "release-evidence.json"
    written = notices.write_release_evidence(
        sbom, evidence, _packages(build), release_date=dt.date(2026, 9, 2)
    )

    assert {entry["kind"] for entry in written["packages"]} == {"appimage", "flatpak"}
    assert {entry["component_id"] for entry in written["source_provisions"]} == {
        "qt",
        "geos",
        "appimage-type2-runtime",
    }
    for entry in written["source_provisions"]:
        assert entry["method"] == "written-offer"
        assert entry["issuer"] == "RS Digital"
        assert "@" in entry["contact"]
        assert entry["version"] in entry["offer_text"]
        assert entry["available_until"] >= "2029-09-03"
    # Der Prüfer nimmt die Datei an, wie sie liegt.
    notices._verify_release_evidence(evidence, json.loads(sbom.read_text(encoding="utf-8")))


def test_a_changed_package_is_refused(tmp_path: Path) -> None:
    """Ein Byte anders, ein anderer Hash — genau dafür steht die Zahl in der Akte."""
    sbom = _sbom(tmp_path)
    build = tmp_path / "build"
    evidence = build / "release-evidence.json"
    packages = _packages(build)
    notices.write_release_evidence(sbom, evidence, packages, release_date=dt.date(2026, 9, 2))
    packages["flatpak"].write_bytes(b"flatpak, afterwards changed")

    with pytest.raises(RuntimeError, match="SHA-256"):
        notices._verify_release_evidence(evidence, json.loads(sbom.read_text(encoding="utf-8")))


def test_a_missing_outer_package_is_refused_before_anything_is_written(tmp_path: Path) -> None:
    sbom = _sbom(tmp_path)
    build = tmp_path / "build"
    packages = _packages(build)
    del packages["flatpak"]

    with pytest.raises(RuntimeError, match="flatpak"):
        notices.write_release_evidence(sbom, build / "release-evidence.json", packages)
    assert not (build / "release-evidence.json").exists()


def test_a_package_outside_the_evidence_store_is_refused(tmp_path: Path) -> None:
    """Der Prüfer löst nur Pfade innerhalb der Ablage auf; der Schreiber sagt es vorher."""
    sbom = _sbom(tmp_path)
    packages = _packages(tmp_path / "elsewhere")

    with pytest.raises(RuntimeError, match="Evidenzablage"):
        notices.write_release_evidence(sbom, tmp_path / "build" / "release-evidence.json", packages)


def test_a_written_offer_without_text_is_no_offer(tmp_path: Path) -> None:
    sbom = _sbom(tmp_path)
    build = tmp_path / "build"
    evidence = build / "release-evidence.json"
    notices.write_release_evidence(
        sbom, evidence, _packages(build), release_date=dt.date(2026, 9, 2)
    )
    document = json.loads(evidence.read_text(encoding="utf-8"))
    document["source_provisions"][0]["offer_text"] = "   "
    evidence.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(RuntimeError, match="keinen Text"):
        notices._verify_release_evidence(evidence, json.loads(sbom.read_text(encoding="utf-8")))


def test_an_offer_shorter_than_three_years_is_refused(tmp_path: Path) -> None:
    sbom = _sbom(tmp_path)
    build = tmp_path / "build"
    evidence = build / "release-evidence.json"
    notices.write_release_evidence(
        sbom, evidence, _packages(build), release_date=dt.date(2026, 9, 2)
    )
    document = json.loads(evidence.read_text(encoding="utf-8"))
    document["source_provisions"][0]["available_until"] = "2029-09-01"
    evidence.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(RuntimeError, match="drei Jahre"):
        notices._verify_release_evidence(evidence, json.loads(sbom.read_text(encoding="utf-8")))


def test_an_archive_provision_still_needs_its_files(tmp_path: Path) -> None:
    """Wer ``archive`` sagt, legt Quellarchiv und Austauschmaterial bei — wie bisher."""
    sbom = _sbom(tmp_path)
    build = tmp_path / "build"
    evidence = build / "release-evidence.json"
    notices.write_release_evidence(
        sbom, evidence, _packages(build), release_date=dt.date(2026, 9, 2)
    )
    document = json.loads(evidence.read_text(encoding="utf-8"))
    document["source_provisions"][0]["method"] = "archive"
    evidence.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises((RuntimeError, KeyError)):
        notices._verify_release_evidence(evidence, json.loads(sbom.read_text(encoding="utf-8")))


def test_the_command_line_writes_the_same_file(tmp_path: Path) -> None:
    """Der Weg, den die CI nimmt: ``--write-evidence`` mit ``--package SORTE=PFAD``."""
    import subprocess
    import sys

    sbom = _sbom(tmp_path, target="windows-x86_64")
    build = tmp_path / "build"
    build.mkdir()
    setup = build / "Solidon3D-Setup-0.0.0.exe"
    setup.write_bytes(b"setup")
    evidence = build / "release-evidence.json"
    completed = subprocess.run(
        [
            sys.executable,
            "tools/make_licence_notices.py",
            "--write-evidence",
            "--sbom",
            str(sbom),
            "--release-evidence",
            str(evidence),
            "--package",
            f"windows-installer={setup}",
            "--release-date",
            "2026-09-02",
        ],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    document = json.loads(evidence.read_text(encoding="utf-8"))
    assert document["target"] == "windows-x86_64"
    assert document["packages"][0]["kind"] == "windows-installer"
    notices._verify_release_evidence(evidence, json.loads(sbom.read_text(encoding="utf-8")))
