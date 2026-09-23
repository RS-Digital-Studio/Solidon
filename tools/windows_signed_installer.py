"""Baut in der CI den Installer aus einer lokal signierten, gebundenen Anwendung.

Keine Schlüssel und keine Signierbefehle: Der erfolgreiche Hauptlauf, seine
Archivübergabe und die lokale Signaturakte müssen denselben Stand benennen.
Die Archiv- und Manifestprüfung bleibt bei ``sign_release``.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from app.branding import APP_VERSION
from tools import make_installer, sign_release
from tools.make_installer import _sha256 as file_sha256

CERTIFICATE_THUMBPRINT = "235C54FC71D79BD03449DBC62FFB14D0AC58AEB3"
APPLICATION_RECORD = sign_release.APPLICATION_METADATA
INSTALLER_RECORD = sign_release.INSTALLER_METADATA
ARTIFACT_NAME = sign_release.INSTALLER_ARTIFACT_NAME
_RUN_ID = re.compile(r"[1-9][0-9]*")
_COMMIT = re.compile(r"[0-9a-f]{40}")
_DIGEST = re.compile(r"[0-9a-f]{64}")
_REPOSITORY = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise sign_release.SigningError(message + " — Eingaben und Herkunft prüfen.")


def validate_request(
    repository: str, run_id: str, commit: str, version: str, release_id: str, digest: str
) -> None:
    """Prüft alle Fernbezeichner, bevor sie in einen API-Pfad gelangen."""
    _require(_REPOSITORY.fullmatch(repository) is not None, "Ungültiges Repository")
    _require(repository == sign_release.REPOSITORY, "Workflow stammt aus anderem Repository")
    _require(_RUN_ID.fullmatch(run_id) is not None, "Ungültige Quelllaufnummer")
    _require(_RUN_ID.fullmatch(release_id) is not None, "Ungültige Release-Entwurfsnummer")
    _require(_COMMIT.fullmatch(commit) is not None, "Ungültiger Quellcommit")
    _require(_DIGEST.fullmatch(digest) is not None, "Ungültige Anwendungsprüfsumme")
    _require(version == APP_VERSION, "Version weicht vom ausgeführten Quellstand ab")
    _require(
        commit == os.environ.get("GITHUB_SHA"), "Workflow und Quelllauf sind verschiedene Stände"
    )
    _require(os.environ.get("GITHUB_REF") == "refs/heads/main", "Workflow läuft nicht auf main")


def _api(repository: str, suffix: str) -> Any:
    """Liest GitHub-Metadaten ohne Shellauswertung der Bezeichner."""
    result = subprocess.run(
        ["gh", "api", f"repos/{repository}/{suffix}"],
        check=True,
        capture_output=True,
        encoding="utf-8",
        timeout=60,
    )
    return json.loads(result.stdout)


def verify_source_run(run_id: str, commit: str) -> None:
    """Ergänzt die gemeinsame Laufprüfung um den identischen Workflowstand."""
    run = sign_release.verify_ci_run(run_id, sign_release.BUILD_WORKFLOW)
    _require(
        run["head_sha"] == commit, "Quelllauf und ausgeführter Workflow haben verschiedene Commits"
    )


def _download_asset(repository: str, asset: dict[str, Any], target: Path) -> None:
    """Lädt genau eine zuvor ausgewählte numerische Asset-ID."""
    asset_id = asset.get("id")
    _require(type(asset_id) is int and asset_id > 0, "Ungültige Release-Asset-ID")
    _require(asset.get("state") == "uploaded", "Release-Asset ist nicht vollständig hochgeladen")
    with target.open("xb") as output:
        subprocess.run(
            [
                "gh",
                "api",
                "-H",
                "Accept: application/octet-stream",
                f"repos/{repository}/releases/assets/{asset_id}",
            ],
            stdout=output,
            check=True,
            timeout=300,
        )


def select_assets(release: dict[str, Any], release_id: str, commit: str) -> dict[str, Any]:
    """Verlangt einen unveröffentlichten Entwurf und eindeutige Eingänge."""
    _require(release.get("id") == int(release_id), "Anderer Release-Entwurf erhalten")
    _require(
        release.get("draft") is True, "Signiereingang ist kein unveröffentlichter Release-Entwurf"
    )
    _require(release.get("published_at") is None, "Release-Entwurf wurde bereits veröffentlicht")
    _require(
        release.get("target_commitish") == commit,
        "Release-Entwurf ist nicht an den Quellcommit gebunden",
    )
    assets = release.get("assets")
    if not isinstance(assets, list):
        raise sign_release.SigningError(
            "Release-Entwurf enthält keine Assetliste — Entwurf prüfen."
        )
    selected = {}
    for name in ("Solidon3D.exe", APPLICATION_RECORD):
        matches = [
            asset for asset in assets if isinstance(asset, dict) and asset.get("name") == name
        ]
        _require(len(matches) == 1, f"Release-Asset {name} fehlt oder ist mehrfach vorhanden")
        selected[name] = matches[0]
    return selected


def validate_record(
    record: dict[str, Any],
    *,
    run_id: str,
    commit: str,
    version: str,
    archive_digest: str,
    unsigned_digest: str,
    signed_digest: str,
) -> None:
    """Vergleicht die lokale Signaturakte mit den tatsächlichen CI-Eingängen."""
    record = sign_release.signing_metadata(record)
    expected = {
        "schema_version": 1,
        "app_version": version,
        "source_run_id": run_id,
        "source_commit": commit,
        "source_archive_sha256": archive_digest,
        "unsigned_application_sha256": unsigned_digest,
        "signed_application_sha256": signed_digest,
        "certificate_thumbprint": CERTIFICATE_THUMBPRINT,
    }
    _require(
        record == expected,
        "Signaturakte passt nicht vollständig zu Quelllauf, Anwendung und Zertifikat",
    )


def prepare(
    *,
    repository: str,
    run_id: str,
    commit: str,
    version: str,
    release_id: str,
    signed_digest: str,
    work: Path,
) -> None:
    """Prüft und bindet den App-Baum, bevor ein Installer gebaut werden darf."""
    validate_request(repository, run_id, commit, version, release_id, signed_digest)
    verify_source_run(run_id, commit)
    listing = _api(repository, f"actions/runs/{run_id}/artifacts?per_page=100")
    artifacts = listing.get("artifacts", [])
    _require(listing.get("total_count") == len(artifacts), "Artefaktliste ist unvollständig")
    matches = [item for item in artifacts if item.get("name") == sign_release.ARTIFACT_NAME]
    _require(
        len(matches) == 1 and matches[0].get("expired") is False,
        "Signierarchiv fehlt, ist mehrdeutig oder abgelaufen",
    )
    assets = select_assets(_api(repository, f"releases/{release_id}"), release_id, commit)
    work.mkdir(parents=True, exist_ok=False)
    download = work / "download"
    archive = sign_release.download_handoff(run_id, download)
    names = {
        path.relative_to(download).as_posix() for path in download.rglob("*") if path.is_file()
    }
    _require(
        names == {sign_release.ARCHIVE_NAME, sign_release.ARCHIVE_NAME + ".sha256"},
        "Unbekannte Dateien im Signierartefakt",
    )
    archive_digest = sign_release.verify_archive(archive)
    stage = work / "stage"
    sign_release.extract_archive(archive, stage)
    handoff = sign_release.load_handoff(stage)
    sign_release.verify_inputs(stage, handoff)
    _require(handoff["app_version"] == version, "Archiv trägt eine andere Produktversion")
    application = sign_release.resolve_handoff_path(stage, handoff["application"])
    unsigned_digest = file_sha256(application)
    signed = work / "signed"
    signed.mkdir()
    for name, asset in assets.items():
        _download_asset(repository, asset, signed / name)
    record = json.loads((signed / APPLICATION_RECORD).read_text(encoding="utf-8"))
    validate_record(
        record,
        run_id=run_id,
        commit=commit,
        version=version,
        archive_digest=archive_digest,
        unsigned_digest=unsigned_digest,
        signed_digest=signed_digest,
    )
    _require(
        file_sha256(signed / "Solidon3D.exe") == signed_digest,
        "Signierte Anwendung hat eine andere Prüfsumme",
    )
    # Der Signaturprüfer bleibt gemeinsam mit der lokalen Signierkette.
    sign_release.verify_file(sign_release.find_signtool(), signed / "Solidon3D.exe")
    sign_release.verify_signature_identity(signed / "Solidon3D.exe", CERTIFICATE_THUMBPRINT)
    shutil.copyfile(signed / "Solidon3D.exe", application)
    sign_release.rebind_handoff(stage, handoff)
    sign_release.verify_inputs(stage, handoff)
    # Der Entwurf darf auch während der Downloads nicht veröffentlicht worden sein.
    select_assets(_api(repository, f"releases/{release_id}"), release_id, commit)


def build(work: Path, compiler: Path, output: Path) -> None:
    """Baut mit Inno 7 und gibt exakt Installer, Prüfsumme und Herkunft weiter."""
    version = make_installer.compiler_version(compiler)
    _require(version == "7.1.0", "Der freigegebene Inno-Setup-Compiler 7.1.0 fehlt")
    stage = work / "stage"
    handoff = sign_release.load_handoff(stage)
    sign_release.verify_inputs(stage, handoff)
    record = sign_release.signing_metadata(
        json.loads((work / "signed" / APPLICATION_RECORD).read_text(encoding="utf-8"))
    )
    application = sign_release.resolve_handoff_path(stage, handoff["application"])
    _require(
        file_sha256(application) == record["signed_application_sha256"],
        "Signierte Anwendung hat sich vor dem Installerbau geändert",
    )
    setup = sign_release.build_installer(stage, handoff, compiler)
    output.mkdir(parents=True, exist_ok=False)
    delivered = output / setup.name
    shutil.copyfile(setup, delivered)
    sign_release.write_checksum(delivered)
    record["installer_sha256"] = file_sha256(delivered)
    (output / INSTALLER_RECORD).write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )


def main() -> int:
    """Liest CI-Eingaben aus der Umgebung statt aus eingebettetem Shellcode."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("prepare", "build"))
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--compiler", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        if args.phase == "prepare":
            prepare(
                repository=os.environ["GITHUB_REPOSITORY"],
                run_id=os.environ["SOURCE_RUN_ID"],
                commit=os.environ["SOURCE_COMMIT"],
                version=os.environ["SOURCE_VERSION"],
                release_id=os.environ["DRAFT_RELEASE_ID"],
                signed_digest=os.environ["SIGNED_APP_SHA256"],
                work=args.work,
            )
        else:
            if args.compiler is None or args.output is None:
                raise sign_release.SigningError(
                    "Compiler oder Ausgabe fehlt — beide Pfade angeben."
                )
            build(args.work, args.compiler, args.output)
    except (
        sign_release.SigningError,
        OSError,
        ValueError,
        KeyError,
        subprocess.SubprocessError,
    ) as exc:
        print(f"Installerbau angehalten: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
