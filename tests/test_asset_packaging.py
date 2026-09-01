"""Prüft die Rechtefreigabe an der tatsächlichen Paketgrenze."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from tools import asset_rights

DELIVERY = """
[delivery]
description = "Isolierter Rechtenachweis für den Pakettest."
scope = "copyright_and_redistribution"
not_a_safety_approval = true
application_platforms = ["windows", "macos", "linux"]
application_media_identical = true
platform_exceptions = ["ICO nur unter Windows; ICNS nur unter macOS."]
excluded = ["Tests und Arbeitsdateien werden nicht ausgeliefert."]
"""


def _toml(value: str | list[str] | dict[str, str]) -> str:
    """Einfache JSON-Texte als gültige TOML-Werte serialisieren."""
    if isinstance(value, dict):
        pairs = (f"{json.dumps(key)} = {json.dumps(item)}" for key, item in value.items())
        return "{" + ", ".join(pairs) + "}"
    return json.dumps(value, ensure_ascii=False)


def _asset(
    selector: str,
    *,
    paths: bool = False,
    status: str = "cleared",
    platforms: tuple[str, ...] = ("windows", "macos", "linux"),
    art: str = "image",
    evidence: tuple[str, ...] = ("evidence.txt",),
    inputs: tuple[str, ...] = ("eigene Testquelle",),
    license_name: str = "LicenseRef-Solidon-Proprietary",
    derivative_status: str = "original",
    extra: dict[str, str | dict[str, str]] | None = None,
    missing: str | None = None,
) -> str:
    """Eine vollständige Rechtekette für isolierte Grenztests erzeugen."""
    fields: dict[str, str | list[str] | dict[str, str]] = {
        "paths" if paths else "pattern": [selector] if paths else selector,
        "art": art,
        "creator": "RS Digital",
        "rights_holder": "RS Digital",
        "source": "Eigene Testquelle",
        "license": license_name,
        "generator": "none",
        "inputs": list(inputs),
        "derivative_status": derivative_status,
        "evidence": list(evidence),
        "redistribution_right": "blocked"
        if status == "distribution_blocked"
        else "confirmed_in_product",
        "platforms": list(platforms),
        "status": status,
    }
    if status == "distribution_blocked":
        fields["blocker"] = "Urheberschaft belegen."
    if extra:
        fields.update(extra)
    if missing is not None:
        fields.pop(missing)
    lines = ["[[asset]]"]
    lines.extend(f"{key} = {_toml(value)}" for key, value in fields.items())
    return "\n".join(lines) + "\n"


def _manifest(tmp_path: Path, assets: list[str], *, media: tuple[str, ...]) -> Path:
    """Einen vollständigen isolierten Quellbaum samt Rechtenachweis anlegen."""
    (tmp_path / "evidence.txt").write_text("Nachweis", encoding="utf-8")
    for relative in media:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"test")
    path = tmp_path / "rights.toml"
    if assets:
        content = "schema_version = 1\n" + DELIVERY + "\n".join(assets)
    else:
        content = "schema_version = 1\nasset = []\n" + DELIVERY
    path.write_text(content, encoding="utf-8")
    return path


def _require(platform: str, manifest: Path, root: Path) -> None:
    """Das Produktions-Gate mit dem isolierten Quellbaum aufrufen."""
    asset_rights.require_application_assets_cleared(platform, manifest=manifest, root=root)


def _require_website(manifest: Path, root: Path) -> None:
    """Das Website-Produktions-Gate mit dem isolierten Quellbaum aufrufen."""
    asset_rights.require_website_assets_cleared(manifest=manifest, root=root)


def _built_artifact(
    tmp_path: Path,
    platform: str,
) -> tuple[Path, Path, Path, Path, Path]:
    """Einen minimalen, aber bytegetreuen PyInstaller-Bau nachbilden."""
    root = tmp_path / "root"
    root.mkdir()
    source = "app/examples/frei.svg"
    manifest = _manifest(root, [_asset(source)], media=(source,))
    spec = root / "packaging" / "solidon3d.spec"
    spec.parent.mkdir(parents=True, exist_ok=True)
    spec.write_text("# Test-Spec\n", encoding="utf-8")
    checker = root / "tools" / "asset_rights.py"
    checker.parent.mkdir(parents=True)
    checker.write_text("# Test-Prüfung\n", encoding="utf-8")
    artifact = tmp_path / "artifact"
    if platform == "darwin":
        packaged = artifact / "Contents" / "Frameworks" / source
    else:
        packaged = artifact / "_internal" / source
    packaged.parent.mkdir(parents=True)
    packaged.write_bytes(b"test")
    return root, manifest, spec, checker, artifact


def test_the_real_manifest_passes_the_production_gate_for_every_target() -> None:
    """Der echte Kundenbau bleibt auf allen drei Zielsystemen freigegeben."""
    for platform in ("win32", "darwin", "linux"):
        asset_rights.require_application_assets_cleared(platform)
    asset_rights.require_website_assets_cleared()


def test_an_application_blocker_stops_every_named_target_platform(tmp_path: Path) -> None:
    """Eine fehlende Rechtekette darf auf keiner Kundensystemart mitreisen."""
    manifest = _manifest(
        tmp_path,
        [_asset("app/examples/unklar.svg", status="distribution_blocked")],
        media=("app/examples/unklar.svg",),
    )

    for platform in ("win32", "darwin", "linux"):
        with pytest.raises(RuntimeError, match=r"app/examples/unklar\.svg") as problem:
            _require(platform, manifest, tmp_path)
        assert "Urheberschaft belegen" in str(problem.value)


def test_a_website_only_blocker_does_not_stop_the_application_package(tmp_path: Path) -> None:
    """Paket- und Website-Tor behalten ihre jeweilige Reichweite."""
    manifest = _manifest(
        tmp_path,
        [
            _asset("app/examples/frei.svg"),
            _asset(
                "website/bilder/unklar.webp",
                status="distribution_blocked",
                platforms=("web",),
            ),
        ],
        media=("app/examples/frei.svg", "website/bilder/unklar.webp"),
    )

    _require("win32", manifest, tmp_path)
    with pytest.raises(RuntimeError, match=r"website/bilder/unklar\.webp"):
        _require_website(manifest, tmp_path)


def test_explicit_path_blocker_names_every_affected_file(tmp_path: Path) -> None:
    """Fail-closed Pfadlisten bleiben an der Paketgrenze verständlich."""
    paths = ("app/examples/eins.svg", "app/examples/zwei.svg")
    manifest = _manifest(
        tmp_path,
        [
            _asset(paths[0], paths=True, status="distribution_blocked").replace(
                _toml([paths[0]]), _toml(list(paths)), 1
            )
        ],
        media=paths,
    )

    with pytest.raises(RuntimeError) as problem:
        _require("win32", manifest, tmp_path)

    message = str(problem.value)
    assert "app/examples/eins.svg, app/examples/zwei.svg" in message
    assert "Urheberschaft belegen" in message


def test_empty_asset_list_stops_the_production_gate(tmp_path: Path) -> None:
    """Ein syntaktisch gültiges, aber leeres Inventar ist keine Freigabe."""
    manifest = _manifest(tmp_path, [], media=("app/examples/neu.svg",))

    with pytest.raises(RuntimeError, match="mindestens eine vollständige Rechtekette"):
        _require("win32", manifest, tmp_path)


def test_unknown_status_stops_the_production_gate(tmp_path: Path) -> None:
    """Ein Tippfehler im Status darf nie wie eine Freigabe wirken."""
    manifest = _manifest(
        tmp_path,
        [_asset("app/examples/neu.svg", status="freigegeben")],
        media=("app/examples/neu.svg",),
    )

    with pytest.raises(RuntimeError, match="unbekannter Wert 'freigegeben'"):
        _require("win32", manifest, tmp_path)


def test_missing_required_field_stops_the_production_gate(tmp_path: Path) -> None:
    """Eine unvollständige Rechtekette bleibt auch ohne Blockerstatus gesperrt."""
    manifest = _manifest(
        tmp_path,
        [_asset("app/examples/neu.svg", missing="creator")],
        media=("app/examples/neu.svg",),
    )

    with pytest.raises(RuntimeError, match=r"fehlende Felder.*creator"):
        _require("win32", manifest, tmp_path)


def test_unlisted_application_medium_stops_the_production_gate(tmp_path: Path) -> None:
    """Neue Dateien im Paket brauchen vor dem Bau eine eigene Rechtekette."""
    manifest = _manifest(
        tmp_path,
        [_asset("app/examples/frei.svg")],
        media=("app/examples/frei.svg", "app/images/neu.png"),
    )

    with pytest.raises(
        RuntimeError,
        match=r"Anwendungsmedien ohne Rechtekette.*app/images/neu\.png",
    ):
        _require("win32", manifest, tmp_path)


def test_missing_explicit_application_path_stops_the_production_gate(tmp_path: Path) -> None:
    """Eine Pfadliste darf fehlende Dateien nicht über einen gültigen Nachbarn verstecken."""
    present = "app/examples/frei.svg"
    missing = "app/examples/fehlt.svg"
    manifest = _manifest(
        tmp_path,
        [
            _asset(present, paths=True).replace(
                _toml([present]),
                _toml([present, missing]),
                1,
            )
        ],
        media=(present,),
    )

    with pytest.raises(RuntimeError, match=r"paths.*fehlt\.svg.*fehlt"):
        _require("win32", manifest, tmp_path)


def test_duplicate_application_coverage_stops_the_production_gate(tmp_path: Path) -> None:
    """Zwei widersprechende Rechteketten dürfen dieselbe Datei nicht freigeben."""
    manifest = _manifest(
        tmp_path,
        [
            _asset("app/examples/*.svg"),
            _asset("app/examples/frei.svg", paths=True),
        ],
        media=("app/examples/frei.svg",),
    )

    with pytest.raises(RuntimeError, match="Anwendungsmedien mit mehreren Rechteketten"):
        _require("win32", manifest, tmp_path)


def test_unlisted_website_medium_stops_the_upload_gate(tmp_path: Path) -> None:
    """Eine neue Website-Datei darf nicht ohne Rechtekette hochgeladen werden."""
    manifest = _manifest(
        tmp_path,
        [_asset("app/examples/frei.svg")],
        media=("app/examples/frei.svg", "website/bilder/neu.webp"),
    )

    with pytest.raises(RuntimeError, match=r"Website-Medien ohne Rechtekette.*neu\.webp"):
        _require_website(manifest, tmp_path)


def test_duplicate_website_coverage_stops_the_upload_gate(tmp_path: Path) -> None:
    """Zwei Rechteketten für dasselbe Webmedium sind keine eindeutige Freigabe."""
    manifest = _manifest(
        tmp_path,
        [
            _asset("app/examples/frei.svg"),
            _asset("website/bilder/*.webp", platforms=("web",)),
            _asset("website/bilder/frei.webp", paths=True, platforms=("web",)),
        ],
        media=("app/examples/frei.svg", "website/bilder/frei.webp"),
    )

    with pytest.raises(RuntimeError, match="Website-Medien mit mehreren Rechteketten"):
        _require_website(manifest, tmp_path)


def test_uninventoried_remote_medium_stops_the_upload_gate(tmp_path: Path) -> None:
    """Lokal gelöschte Medien bleiben auf dem Server eine reale Weitergabe."""
    manifest = _manifest(
        tmp_path,
        [
            _asset("app/examples/frei.svg"),
            _asset("website/bilder/frei.webp", platforms=("web",)),
        ],
        media=("app/examples/frei.svg", "website/bilder/frei.webp"),
    )

    with pytest.raises(RuntimeError, match=r"weiterhin auf dem Webserver.*alt\.webp"):
        asset_rights.require_website_assets_cleared(
            manifest=manifest,
            root=tmp_path,
            remote_paths=("bilder/frei.webp", "bilder/alt.webp"),
        )
    assert asset_rights.unexpected_remote_website_assets(
        ("bilder/frei.webp", "bilder/alt.webp"),
        manifest=manifest,
        root=tmp_path,
    ) == ["bilder/alt.webp"]


def test_git_history_is_not_accepted_as_distribution_evidence(tmp_path: Path) -> None:
    """Ein flacher oder exportierter Quellbaum muss dieselbe Freigabe prüfen können."""
    manifest = _manifest(
        tmp_path,
        [_asset("app/examples/frei.svg", evidence=("git:1234567",))],
        media=("app/examples/frei.svg",),
    )

    with pytest.raises(RuntimeError, match="hängt von Git-Historie ab"):
        _require("win32", manifest, tmp_path)


@pytest.mark.parametrize(
    "selector",
    (
        "C:/Windows/system32/icon.png",
        "//server/share/icon.png",
        r"\\server\share\icon.png",
        "../icon.png",
    ),
)
def test_non_repository_paths_are_rejected(tmp_path: Path, selector: str) -> None:
    """Windows-, UNC- und Ausbruchspfade dürfen nie Repositorynachweise sein."""
    manifest = _manifest(tmp_path, [_asset(selector)], media=())

    with pytest.raises(RuntimeError, match="ungültigen Pfad"):
        _require("win32", manifest, tmp_path)


def test_an_evidence_directory_is_not_accepted_as_a_document(tmp_path: Path) -> None:
    """Ein Verzeichnisname ist kein prüfbarer Lizenz- oder Herkunftsnachweis."""
    (tmp_path / "evidence-directory").mkdir()
    manifest = _manifest(
        tmp_path,
        [_asset("app/examples/frei.svg", evidence=("evidence-directory",))],
        media=("app/examples/frei.svg",),
    )

    with pytest.raises(RuntimeError, match="muss eine reguläre Datei sein"):
        _require("win32", manifest, tmp_path)


def _symlink_or_skip(link: Path, target: Path, *, directory: bool = False) -> None:
    """Symlink-Härtung auf Systemen ohne Symlink-Recht gezielt überspringen."""
    try:
        link.symlink_to(target, target_is_directory=directory)
    except OSError as problem:
        pytest.skip(f"Symlinks sind in dieser Testumgebung nicht verfügbar: {problem}")


def test_an_evidence_symlink_cannot_escape_the_repository(tmp_path: Path) -> None:
    """Ein Nachweis darf nicht über einen Dateisymlink außerhalb des Quellbaums zeigen."""
    repository = tmp_path / "repository"
    repository.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("fremd", encoding="utf-8")
    manifest = _manifest(
        repository,
        [_asset("app/examples/frei.svg")],
        media=("app/examples/frei.svg",),
    )
    (repository / "evidence.txt").unlink()
    _symlink_or_skip(repository / "evidence.txt", outside)

    with pytest.raises(RuntimeError, match="verlässt den Quellbaum"):
        _require("win32", manifest, repository)


def test_a_directory_symlink_cannot_hide_external_evidence(tmp_path: Path) -> None:
    """Auch ein Symlink in einem übergeordneten Pfadteil bleibt gesperrt."""
    repository = tmp_path / "repository"
    repository.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "evidence.txt").write_text("fremd", encoding="utf-8")
    manifest = _manifest(
        repository,
        [_asset("app/examples/frei.svg", evidence=("linked/evidence.txt",))],
        media=("app/examples/frei.svg",),
    )
    _symlink_or_skip(repository / "linked", outside, directory=True)

    with pytest.raises(RuntimeError, match="verlässt den Quellbaum"):
        _require("win32", manifest, repository)


def test_a_web_only_record_cannot_clear_application_media(tmp_path: Path) -> None:
    """Eine Freigabe für die Website darf nicht still das Kundenpaket freigeben."""
    manifest = _manifest(
        tmp_path,
        [_asset("app/examples/frei.svg", platforms=("web",))],
        media=("app/examples/frei.svg",),
    )

    with pytest.raises(RuntimeError, match="Anwendungsmedien ohne Rechtekette"):
        _require("win32", manifest, tmp_path)


def test_unknown_local_media_format_stops_the_upload_gate(tmp_path: Path) -> None:
    """Neue Medienendungen müssen bewusst klassifiziert statt übersehen werden."""
    manifest = _manifest(
        tmp_path,
        [_asset("website/bilder/frei.webp", platforms=("web",))],
        media=("website/bilder/frei.webp", "website/bilder/neu.avif"),
    )

    with pytest.raises(RuntimeError, match=r"unbekanntes Dateiformat.*neu\.avif"):
        _require_website(manifest, tmp_path)


def test_unknown_remote_media_format_stops_the_upload_gate(tmp_path: Path) -> None:
    """Auch ein nur noch remote vorhandenes neues Format bleibt fail-closed."""
    manifest = _manifest(
        tmp_path,
        [_asset("website/bilder/frei.webp", platforms=("web",))],
        media=("website/bilder/frei.webp",),
    )

    with pytest.raises(RuntimeError, match=r"unbekanntes Dateiformat.*neu\.avif"):
        asset_rights.require_website_assets_cleared(
            manifest=manifest,
            root=tmp_path,
            remote_paths=("bilder/frei.webp", "bilder/neu.avif"),
        )


def test_third_party_bytes_and_licence_evidence_are_immutable(tmp_path: Path) -> None:
    """Fremdschrift und Lizenztext müssen exakt den freigegebenen Bytes entsprechen."""
    font = "website/fonts/test.woff2"
    content_hash = hashlib.sha256(b"test").hexdigest()
    evidence_hash = hashlib.sha256(b"Nachweis").hexdigest()
    manifest = _manifest(
        tmp_path,
        [
            _asset(
                font,
                platforms=("web",),
                art="font",
                license_name="OFL-1.1",
                derivative_status="third_party_unmodified",
                extra={
                    "content_sha256": {font: content_hash},
                    "evidence_sha256": {"evidence.txt": evidence_hash},
                    "upstream_url": "https://example.invalid/font",
                    "upstream_version": "1.0",
                },
            )
        ],
        media=(font,),
    )
    _require_website(manifest, tmp_path)

    (tmp_path / font).write_bytes("verändert".encode())
    with pytest.raises(RuntimeError, match="Byte-Nachweis"):
        _require_website(manifest, tmp_path)

    (tmp_path / font).write_bytes(b"test")
    (tmp_path / "evidence.txt").write_text("verändert", encoding="utf-8")
    with pytest.raises(RuntimeError, match="Byte-Nachweis"):
        _require_website(manifest, tmp_path)


@pytest.mark.parametrize(
    ("platform", "receipt_path"),
    (
        ("win32", "_internal/Solidon3D-rights.json"),
        ("linux", "_internal/Solidon3D-rights.json"),
        ("darwin", "Contents/Resources/Solidon3D-rights.json"),
    ),
)
def test_every_customer_artifact_carries_a_verified_byte_receipt(
    tmp_path: Path,
    platform: str,
    receipt_path: str,
) -> None:
    """Windows, Linux und macOS binden dieselben freigegebenen Medienbytes."""
    root, manifest, spec, checker, artifact = _built_artifact(tmp_path, platform)

    written = asset_rights.write_customer_artifact_receipt(
        artifact,
        platform,
        manifest=manifest,
        root=root,
        checker=checker,
        spec=spec,
    )

    assert written.relative_to(artifact).as_posix() == receipt_path
    asset_rights.require_customer_artifact_cleared(
        artifact,
        platform,
        manifest=manifest,
        root=root,
        checker=checker,
        spec=spec,
    )


def test_a_source_change_makes_an_existing_dist_stale(tmp_path: Path) -> None:
    """Neue Quellbytes dürfen nie unter einem alten dist-Ordner ausgeliefert werden."""
    root, manifest, spec, checker, artifact = _built_artifact(tmp_path, "win32")
    asset_rights.write_customer_artifact_receipt(
        artifact, "win32", manifest=manifest, root=root, checker=checker, spec=spec
    )
    (root / "app/examples/frei.svg").write_bytes(b"neu")

    with pytest.raises(RuntimeError, match="Quellmedium wurde nach dem Kundenbau geändert"):
        asset_rights.require_customer_artifact_cleared(
            artifact, "win32", manifest=manifest, root=root, checker=checker, spec=spec
        )


def test_a_packaged_media_change_stops_the_final_package(tmp_path: Path) -> None:
    """Auch nach PyInstaller ausgetauschte Medienbytes bleiben gesperrt."""
    root, manifest, spec, checker, artifact = _built_artifact(tmp_path, "linux")
    asset_rights.write_customer_artifact_receipt(
        artifact, "linux", manifest=manifest, root=root, checker=checker, spec=spec
    )
    (artifact / "_internal/app/examples/frei.svg").write_bytes(b"ausgetauscht")

    with pytest.raises(RuntimeError, match="Kundenmedium wurde nach dem Bau geändert"):
        asset_rights.require_customer_artifact_cleared(
            artifact, "linux", manifest=manifest, root=root, checker=checker, spec=spec
        )


def test_an_added_packaged_medium_stops_the_final_package(tmp_path: Path) -> None:
    """Ein nach dem Bau hineinkopiertes Medium darf keine Rechtekette umgehen."""
    root, manifest, spec, checker, artifact = _built_artifact(tmp_path, "linux")
    asset_rights.write_customer_artifact_receipt(
        artifact, "linux", manifest=manifest, root=root, checker=checker, spec=spec
    )
    added = artifact / "_internal/app/images/zusatz.png"
    added.parent.mkdir(parents=True)
    added.write_bytes(b"zusatz")

    with pytest.raises(RuntimeError, match="Medienbestand des fertigen Kundenartefakts"):
        asset_rights.require_customer_artifact_cleared(
            artifact, "linux", manifest=manifest, root=root, checker=checker, spec=spec
        )


@pytest.mark.parametrize("control", ("manifest", "spec", "checker"))
def test_a_control_change_invalidates_the_existing_dist(tmp_path: Path, control: str) -> None:
    """Manifest, Prüflogik und Spec dürfen nicht nach einem Bau auseinanderlaufen."""
    root, manifest, spec, checker, artifact = _built_artifact(tmp_path, "darwin")
    asset_rights.write_customer_artifact_receipt(
        artifact, "darwin", manifest=manifest, root=root, checker=checker, spec=spec
    )
    path = {"manifest": manifest, "spec": spec, "checker": checker}[control]
    path.write_text(path.read_text(encoding="utf-8") + "\n# geändert\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="nach dem Bau geändert"):
        asset_rights.require_customer_artifact_cleared(
            artifact, "darwin", manifest=manifest, root=root, checker=checker, spec=spec
        )


def test_a_later_rights_blocker_stops_an_existing_dist(tmp_path: Path) -> None:
    """Eine nachträgliche Sperre setzt sich gegen einen früheren Beleg durch."""
    root, manifest, spec, checker, artifact = _built_artifact(tmp_path, "win32")
    asset_rights.write_customer_artifact_receipt(
        artifact, "win32", manifest=manifest, root=root, checker=checker, spec=spec
    )
    text = manifest.read_text(encoding="utf-8")
    text = text.replace(
        'redistribution_right = "confirmed_in_product"',
        'redistribution_right = "blocked"',
    ).replace(
        'status = "cleared"',
        'status = "distribution_blocked"\nblocker = "Weitergabe stoppen."',
    )
    manifest.write_text(text, encoding="utf-8")

    with pytest.raises(RuntimeError, match="Weitergabe stoppen"):
        asset_rights.require_customer_artifact_cleared(
            artifact, "win32", manifest=manifest, root=root, checker=checker, spec=spec
        )


def test_the_pyinstaller_spec_checks_rights_before_analysis() -> None:
    """Eine Prüfung nach dem Einsammeln wäre nur ein Bericht über einen roten Bau."""
    spec = (asset_rights.ROOT / "packaging" / "solidon3d.spec").read_text(encoding="utf-8")

    assert spec.index("require_application_assets_cleared") < spec.index("analysis = Analysis(")
    assert spec.index("write_customer_artifact_receipt") > spec.index("_artifact = Path(DISTPATH)")


def test_every_final_packager_rechecks_the_built_customer_artifact() -> None:
    """Installer dürfen den Beleg des PyInstaller-Laufs nicht nur voraussetzen."""
    required = {
        "tools/make_installer.py": 'require_customer_artifact_cleared(SOURCE_DIR, "win32")',
        "tools/make_linux_packages.py": 'require_customer_artifact_cleared(SOURCE_DIR, "linux")',
        "tools/make_macos_package.py": 'require_customer_artifact_cleared(BUNDLE, "darwin")',
    }
    for relative, call in required.items():
        source = (asset_rights.ROOT / relative).read_text(encoding="utf-8")
        assert call in source, f"{relative} prüft den fertigen Medienbeleg nicht"


def test_the_uploader_checks_website_rights_before_network_access() -> None:
    """Der Web-Gate muss vor dem ersten FTPS-Verbindungsversuch liegen."""
    uploader = (asset_rights.ROOT / "tools" / "upload_website.py").read_text(encoding="utf-8")
    main = uploader[uploader.index("def main()") :]

    local_gate = main.index("require_website_assets_cleared()")
    connection = main.index("connect(access)")
    remote_index = main.index('remote = remote_index(session, "/" + root)')
    remote_gate = main.index("require_website_assets_cleared(remote_paths=remote)")
    upload = main.index("upload(session, access, path)")

    assert local_gate < connection < remote_index < remote_gate < upload
    assert "--medium-entfernen" in main
    removal = main[main.index("if arguments.remove_media:") : remote_gate]
    assert removal.index("if not arguments.confirm:") < removal.index("session.delete(")
