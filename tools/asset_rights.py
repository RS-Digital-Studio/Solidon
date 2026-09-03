"""Prüft Rechtefreigaben fail-closed vor jedem Kundenpaket."""

from __future__ import annotations

import fnmatch
import hashlib
import json
import sys
import tomllib
from collections.abc import Iterable
from pathlib import Path, PurePosixPath
from typing import Any, Final

ROOT: Final = Path(__file__).resolve().parent.parent
MANIFEST: Final = ROOT / "ASSET-RIGHTS.toml"
PLATFORM_NAMES: Final = {
    "win32": "windows",
    "cygwin": "windows",
    "darwin": "macos",
    "linux": "linux",
}
APPLICATION_PLATFORMS: Final = {"windows", "macos", "linux"}
ALL_PLATFORMS: Final = APPLICATION_PLATFORMS | {"web"}
APPLICATION_ROOTS: Final = ("app/images/", "app/examples/", "packaging/")
WEBSITE_ROOT: Final = "website/"
RIGHTS_RECEIPT: Final = "Solidon3D-rights.json"
WEBSITE_EXCLUDED_ROOTS: Final = ("website/teile/",)
PATH_INPUT_ROOTS: Final = ("app/", "packaging/", "tests/", "tools/", "website/")
APPLICATION_NON_MEDIA_PATHS: Final = {
    "app/images/CLAUDE.md",
    "app/examples/CLAUDE.md",
    "app/examples/LICENSE",
}
WEBSITE_NON_MEDIA_SUFFIXES: Final = {
    "",
    ".css",
    ".html",
    ".js",
    # Betriebszustand, den die Endpunkte selbst schreiben: der Zähler legt
    # `api/.stats/<jahr>-<monat>.jsonl` an, die Freischaltung ihre
    # Ratenzähler. Kein Medium und nichts, was jemand hochlädt — aber es
    # liegt auf dem Server, und der Wächter liest den Serverindex. Ohne
    # diese Endung wies er den ganzen Upload ab (Tag-Lauf 12, 03.09.2026).
    ".jsonl",
    ".json",
    ".md",
    ".php",
    ".txt",
    ".webmanifest",
    ".xml",
}
DELIVERED_SUFFIXES: Final = {
    ".gif",
    ".icns",
    ".ico",
    ".jpeg",
    ".jpg",
    ".mp3",
    ".mp4",
    ".ogg",
    ".otf",
    ".p3d",
    ".png",
    ".svg",
    ".ttf",
    ".wav",
    ".webm",
    ".webp",
    ".woff2",
}
DELIVERY_FIELDS: Final = {
    "description",
    "scope",
    "not_a_safety_approval",
    "application_platforms",
    "application_media_identical",
    "platform_exceptions",
    "excluded",
}
ASSET_FIELDS: Final = {
    "art",
    "creator",
    "rights_holder",
    "source",
    "license",
    "generator",
    "inputs",
    "derivative_status",
    "evidence",
    "redistribution_right",
    "platforms",
    "status",
}
OPTIONAL_ASSET_FIELDS: Final = {
    "content_sha256",
    "evidence_sha256",
    "input_sha256",
    "upstream_url",
    "upstream_version",
}
ALLOWED_ART: Final = {"audio", "font", "icon", "image", "project", "video"}
ALLOWED_LICENSES: Final = {
    "LicenseRef-Solidon-Examples",
    "LicenseRef-Solidon-Proprietary",
    "OFL-1.1",
}
ALLOWED_DERIVATIVES: Final = {
    "derived_from_icon",
    "generated_from_mit_source",
    "generated_from_own_sources",
    "original",
    "third_party_unmodified",
}
ALLOWED_REDISTRIBUTION: Final = {
    "blocked",
    "confirmed_in_product",
    "confirmed_on_website",
    "confirmed_with_notice",
}
ALLOWED_STATUS: Final = {"cleared", "distribution_blocked"}
ART_SUFFIXES: Final = {
    "audio": {".mp3", ".ogg", ".wav"},
    "font": {".otf", ".ttf", ".woff2"},
    "icon": {".icns", ".ico", ".svg"},
    "image": {".gif", ".jpeg", ".jpg", ".png", ".svg", ".webp"},
    "project": {".p3d"},
    "video": {".mp4", ".png", ".webm"},
}


def _fail(path: Path, detail: str) -> RuntimeError:
    """Einen einheitlichen, handlungsorientierten Sperrgrund erzeugen."""
    return RuntimeError(
        f"{path} ist nicht freigabefähig: {detail} "
        "Rechtenachweis korrigieren und den Kundenbau erneut starten."
    )


def _asset_label(asset: dict[str, Any]) -> str:
    """Pattern oder explizite Pfade für eine verständliche Meldung benennen."""
    paths = asset.get("paths")
    if isinstance(paths, list):
        return ", ".join(str(path) for path in paths)
    return str(asset.get("pattern", "unbekannt"))


def _is_relative_posix_path(value: str) -> bool:
    """Nur kanonische Repositorypfade ohne Ausbruch zulassen."""
    pure = PurePosixPath(value)
    windows_drive = len(value) >= 2 and value[0].isalpha() and value[1] == ":"
    return (
        bool(value)
        and "\0" not in value
        and "\\" not in value
        and not windows_drive
        and not value.startswith("//")
        and not pure.is_absolute()
        and not pure.drive
        and ".." not in pure.parts
        and "." not in pure.parts
        and value == pure.as_posix()
    )


def _require_text(value: Any, *, field: str, label: str, manifest: Path) -> str:
    """Ein nicht leeres Textfeld lesen oder den Bau verständlich sperren."""
    if not isinstance(value, str) or not value.strip():
        raise _fail(manifest, f"{label}: Feld {field!r} muss nicht leeren Text enthalten.")
    return value


def _require_text_list(value: Any, *, field: str, label: str, manifest: Path) -> list[str]:
    """Eine nicht leere Liste eindeutiger, nicht leerer Texte prüfen."""
    if (
        not isinstance(value, list)
        or not value
        or any(not isinstance(item, str) or not item.strip() for item in value)
        or len(value) != len(set(value))
    ):
        raise _fail(
            manifest,
            f"{label}: Feld {field!r} muss eindeutige, nicht leere Texte enthalten.",
        )
    return value


def _require_repository_path(value: str, *, field: str, label: str, manifest: Path) -> None:
    """Repositorypfade gegen absolute Pfade und Verzeichnisausbruch absichern."""
    if not _is_relative_posix_path(value):
        raise _fail(manifest, f"{label}: {field} enthält den ungültigen Pfad {value!r}.")


def _inside_root(path: Path, root: Path) -> bool:
    """Auch nach dem Auflösen aller Symlinks im erlaubten Quellbaum bleiben."""
    try:
        return path.resolve(strict=True).is_relative_to(root.resolve(strict=True))
    except (OSError, RuntimeError):
        return False


def _has_symlink_component(path: Path, root: Path) -> bool:
    """Symlinks auch in übergeordneten Teilen eines Repositorypfads erkennen."""
    try:
        relative = path.relative_to(root)
    except ValueError:
        return True
    current = root
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            return True
    return False


def _require_repository_entry(
    value: str,
    *,
    field: str,
    label: str,
    manifest: Path,
    root: Path,
    file_only: bool,
) -> list[Path]:
    """Datei oder Pattern existent, kanonisch und ohne Symlink-Ausbruch prüfen."""
    _require_repository_path(value, field=field, label=label, manifest=manifest)
    targets = list(root.glob(value)) if any(marker in value for marker in "*?[") else [root / value]
    if not targets:
        raise _fail(manifest, f"{label}: {field} {value!r} trifft keine Datei.")
    for target in targets:
        if (
            not target.exists()
            or _has_symlink_component(target, root)
            or not _inside_root(target, root)
        ):
            raise _fail(manifest, f"{label}: {field} {value!r} fehlt oder verlässt den Quellbaum.")
        if file_only and not target.is_file():
            raise _fail(manifest, f"{label}: {field} {value!r} muss eine reguläre Datei sein.")
    return targets


def _looks_like_path(value: str) -> bool:
    """Freitext von ausdrücklich dateiartig geschriebenen Eingaben trennen."""
    return (
        value.startswith(PATH_INPUT_ROOTS)
        or "/" in value
        or "\\" in value
        or (len(value) >= 2 and value[0].isalpha() and value[1] == ":")
        or bool(PurePosixPath(value).suffix)
    )


def _require_hash_map(
    value: Any,
    *,
    field: str,
    label: str,
    manifest: Path,
    root: Path,
) -> dict[str, str]:
    """SHA-256-Zuordnungen an konkrete, unveränderte Repositorybytes binden."""
    if not isinstance(value, dict) or not value:
        raise _fail(manifest, f"{label}: {field} muss mindestens einen SHA-256-Nachweis tragen.")
    result: dict[str, str] = {}
    for path, expected in value.items():
        if not isinstance(path, str) or not isinstance(expected, str):
            raise _fail(manifest, f"{label}: {field} enthält keinen Textpfad mit SHA-256.")
        target = _require_repository_entry(
            path,
            field=field,
            label=label,
            manifest=manifest,
            root=root,
            file_only=True,
        )[0]
        normalized = expected.casefold()
        if len(normalized) != 64 or any(char not in "0123456789abcdef" for char in normalized):
            raise _fail(manifest, f"{label}: {field} enthält für {path!r} keinen SHA-256.")
        actual = hashlib.sha256(target.read_bytes()).hexdigest()
        if actual != normalized:
            raise _fail(manifest, f"{label}: Byte-Nachweis für {path!r} stimmt nicht.")
        result[path] = normalized
    return result


def _sha256(path: Path) -> str:
    """Eine Datei ohne Zeitstempel an ihre tatsächlichen Bytes binden."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_delivery(document: dict[str, Any], manifest: Path) -> None:
    """Die Bedeutung und Reichweite des Inventars unverwechselbar halten."""
    delivery = document.get("delivery")
    if not isinstance(delivery, dict) or set(delivery) != DELIVERY_FIELDS:
        raise _fail(
            manifest,
            "[delivery] muss genau die dokumentierten Felder des Schemas 1 enthalten.",
        )
    _require_text(delivery["description"], field="description", label="delivery", manifest=manifest)
    if delivery["scope"] != "copyright_and_redistribution":
        raise _fail(manifest, "delivery.scope muss 'copyright_and_redistribution' sein.")
    if delivery["not_a_safety_approval"] is not True:
        raise _fail(manifest, "delivery.not_a_safety_approval muss ausdrücklich true sein.")
    if (
        set(
            _require_text_list(
                delivery["application_platforms"],
                field="application_platforms",
                label="delivery",
                manifest=manifest,
            )
        )
        != APPLICATION_PLATFORMS
    ):
        raise _fail(
            manifest, "delivery.application_platforms muss Windows, macOS und Linux nennen."
        )
    if delivery["application_media_identical"] is not True:
        raise _fail(manifest, "delivery.application_media_identical muss ausdrücklich true sein.")
    _require_text_list(
        delivery["platform_exceptions"],
        field="platform_exceptions",
        label="delivery",
        manifest=manifest,
    )
    _require_text_list(delivery["excluded"], field="excluded", label="delivery", manifest=manifest)


def _validate_path_like_input(value: str, *, label: str, manifest: Path, root: Path) -> None:
    """Als Datei benannte Eingaben müssen im isolierten Quellbaum auffindbar sein."""
    if not _looks_like_path(value):
        return
    _require_repository_entry(
        value,
        field="inputs",
        label=label,
        manifest=manifest,
        root=root,
        file_only=False,
    )


def _validate_asset(asset: Any, index: int, manifest: Path, root: Path) -> dict[str, Any]:
    """Eine Rechtekette vollständig prüfen, bevor ihr Status ausgewertet wird."""
    if not isinstance(asset, dict):
        raise _fail(manifest, f"asset[{index}] muss eine Tabelle sein.")
    selectors = {key for key in ("pattern", "paths") if key in asset}
    if len(selectors) != 1:
        raise _fail(manifest, f"asset[{index}] muss genau pattern oder paths enthalten.")
    allowed_fields = (
        ASSET_FIELDS
        | OPTIONAL_ASSET_FIELDS
        | selectors
        | ({"blocker"} if "blocker" in asset else set())
    )
    missing = ASSET_FIELDS - set(asset)
    unknown = set(asset) - allowed_fields
    if missing or unknown:
        raise _fail(
            manifest,
            f"asset[{index}] hat fehlende Felder {sorted(missing)} oder unbekannte Felder "
            f"{sorted(unknown)}.",
        )

    if "pattern" in asset:
        pattern = _require_text(
            asset["pattern"], field="pattern", label=f"asset[{index}]", manifest=manifest
        )
        _require_repository_path(
            pattern, field="pattern", label=f"asset[{index}]", manifest=manifest
        )
    else:
        paths = _require_text_list(
            asset["paths"], field="paths", label=f"asset[{index}]", manifest=manifest
        )
        for value in paths:
            _require_repository_entry(
                value,
                field="paths",
                label=f"asset[{index}]",
                manifest=manifest,
                root=root,
                file_only=True,
            )

    label = _asset_label(asset)
    for field in (
        "art",
        "creator",
        "rights_holder",
        "source",
        "license",
        "generator",
        "derivative_status",
        "redistribution_right",
        "status",
    ):
        _require_text(asset[field], field=field, label=label, manifest=manifest)
    inputs = _require_text_list(asset["inputs"], field="inputs", label=label, manifest=manifest)
    evidence = _require_text_list(
        asset["evidence"], field="evidence", label=label, manifest=manifest
    )
    platforms = _require_text_list(
        asset["platforms"], field="platforms", label=label, manifest=manifest
    )

    for field, allowed in (
        ("art", ALLOWED_ART),
        ("license", ALLOWED_LICENSES),
        ("derivative_status", ALLOWED_DERIVATIVES),
        ("redistribution_right", ALLOWED_REDISTRIBUTION),
        ("status", ALLOWED_STATUS),
    ):
        if asset[field] not in allowed:
            raise _fail(manifest, f"{label}: unbekannter Wert {asset[field]!r} in {field}.")
    if not set(platforms) <= ALL_PLATFORMS:
        raise _fail(manifest, f"{label}: unbekannte Plattform in {platforms!r}.")

    generator = asset["generator"]
    if generator != "none":
        targets = _require_repository_entry(
            generator,
            field="generator",
            label=label,
            manifest=manifest,
            root=root,
            file_only=True,
        )
        if not generator.endswith(".py") or len(targets) != 1:
            raise _fail(
                manifest, f"{label}: Erzeuger {generator!r} fehlt oder ist keine Python-Datei."
            )
    for value in inputs:
        _validate_path_like_input(value, label=label, manifest=manifest, root=root)
    for value in evidence:
        if value.startswith("git:"):
            raise _fail(
                manifest,
                f"{label}: Nachweis {value!r} hängt von Git-Historie ab; Datei oder Hash beilegen.",
            )
        _require_repository_entry(
            value,
            field="evidence",
            label=label,
            manifest=manifest,
            root=root,
            file_only=True,
        )

    hash_maps: dict[str, dict[str, str]] = {}
    for field in ("content_sha256", "evidence_sha256", "input_sha256"):
        if field in asset:
            hash_maps[field] = _require_hash_map(
                asset[field],
                field=field,
                label=label,
                manifest=manifest,
                root=root,
            )
    if "input_sha256" in hash_maps and not set(hash_maps["input_sha256"]) <= set(inputs):
        raise _fail(manifest, f"{label}: input_sha256 nennt keine deklarierte Eingabe.")
    if "evidence_sha256" in hash_maps and not set(hash_maps["evidence_sha256"]) <= set(evidence):
        raise _fail(manifest, f"{label}: evidence_sha256 nennt keinen deklarierten Nachweis.")

    if asset["derivative_status"] == "third_party_unmodified":
        for field in ("content_sha256", "evidence_sha256", "upstream_url", "upstream_version"):
            if field not in asset:
                raise _fail(manifest, f"{label}: Fremdasset braucht {field}.")
        upstream_url = _require_text(
            asset["upstream_url"], field="upstream_url", label=label, manifest=manifest
        )
        _require_text(
            asset["upstream_version"], field="upstream_version", label=label, manifest=manifest
        )
        if not upstream_url.startswith("https://"):
            raise _fail(manifest, f"{label}: upstream_url muss eine HTTPS-Quelle sein.")
        if set(hash_maps["evidence_sha256"]) != set(evidence):
            raise _fail(manifest, f"{label}: jeder Fremdlizenz-Nachweis braucht einen SHA-256.")
    elif "upstream_url" in asset or "upstream_version" in asset:
        raise _fail(manifest, f"{label}: Upstream-Felder sind nur für unveränderte Fremdassets.")

    if asset["status"] == "distribution_blocked":
        blocker = _require_text(
            asset.get("blocker"), field="blocker", label=label, manifest=manifest
        )
        if asset["redistribution_right"] != "blocked":
            raise _fail(
                manifest, f"{label}: gesperrter Status braucht redistribution_right = 'blocked'."
            )
        if not blocker.endswith((".", "!", "?")):
            raise _fail(manifest, f"{label}: blocker muss als vollständiger Handlungssatz enden.")
    elif "blocker" in asset or asset["redistribution_right"] == "blocked":
        raise _fail(manifest, f"{label}: freigegebener Status darf keinen Sperrgrund tragen.")

    return asset


def _application_media(root: Path, manifest: Path) -> set[str]:
    """Alle physischen Medien erfassen, die ein Anwendungsbau einsammeln kann."""
    result: set[str] = set()
    for prefix in ("app/images/", "app/examples/"):
        folder = root / prefix
        if not folder.exists():
            continue
        for path in folder.rglob("*"):
            relative = path.relative_to(root).as_posix()
            if path.is_symlink():
                raise _fail(manifest, f"Symlink im Anwendungs-Lieferbaum ist gesperrt: {relative}.")
            if not path.is_file():
                continue
            if not _inside_root(path, root):
                raise _fail(manifest, f"Anwendungsdatei verlässt den Quellbaum: {relative}.")
            if path.suffix.lower() in DELIVERED_SUFFIXES:
                result.add(relative)
            elif relative not in APPLICATION_NON_MEDIA_PATHS:
                raise _fail(
                    manifest,
                    f"unbekanntes Dateiformat im Anwendungs-Lieferbaum: {relative}.",
                )
    for relative in ("packaging/solidon3d.ico", "packaging/solidon3d.icns"):
        path = root / relative
        if path.exists():
            if path.is_symlink() or not path.is_file() or not _inside_root(path, root):
                raise _fail(manifest, f"Paketmedium ist kein reguläres Medium: {relative}.")
            result.add(relative)
    return result


def _website_media(root: Path, manifest: Path) -> set[str]:
    """Öffentlich auslieferbare Website-Medien ohne private Erzeugungsquellen."""
    result: set[str] = set()
    folder = root / WEBSITE_ROOT
    if not folder.exists():
        return result
    for path in folder.rglob("*"):
        relative = path.relative_to(root).as_posix()
        if relative.startswith((*WEBSITE_EXCLUDED_ROOTS, "website/dl/")):
            continue
        if path.is_symlink():
            raise _fail(manifest, f"Symlink im Website-Lieferbaum ist gesperrt: {relative}.")
        if not path.is_file():
            continue
        if not _inside_root(path, root):
            raise _fail(manifest, f"Website-Datei verlässt den Quellbaum: {relative}.")
        suffix = path.suffix.lower()
        if suffix in DELIVERED_SUFFIXES:
            result.add(relative)
        elif suffix not in WEBSITE_NON_MEDIA_SUFFIXES:
            raise _fail(manifest, f"unbekanntes Dateiformat im Website-Lieferbaum: {relative}.")
    return result


def _remote_website_media(remote_paths: Iterable[str], manifest: Path) -> set[str]:
    """Medienpfade eines Serverindex in die Manifest-Namenswelt übersetzen."""
    result: set[str] = set()
    for value in remote_paths:
        if not isinstance(value, str) or not _is_relative_posix_path(value):
            raise _fail(manifest, f"der Serverindex enthält den ungültigen Pfad {value!r}.")
        path = PurePosixPath(value)
        if path.parts and path.parts[0] == "dl":
            continue
        suffix = path.suffix.lower()
        if suffix in DELIVERED_SUFFIXES:
            result.add(f"website/{path.as_posix()}")
        elif suffix not in WEBSITE_NON_MEDIA_SUFFIXES:
            raise _fail(manifest, f"unbekanntes Dateiformat auf dem Webserver: {value}.")
    return result


def _record_paths(asset: dict[str, Any], paths: set[str]) -> set[str]:
    """Explizite Pfade oder ein einfaches Glob gegen den Lieferbestand auflösen."""
    if "paths" in asset:
        return set(asset["paths"]) & paths
    return {path for path in paths if fnmatch.fnmatchcase(path, asset["pattern"])}


def _validate_application_coverage(
    assets: list[dict[str, Any]], manifest: Path, root: Path
) -> None:
    """Jedes Anwendungsmedium genau einer passenden Rechtekette zuordnen."""
    media = _application_media(root, manifest)
    if not media:
        raise _fail(manifest, "der Anwendungsbaum enthält keine inventarisierbaren Medien.")
    owners: dict[str, list[str]] = {path: [] for path in media}
    unused: list[str] = []
    for asset in assets:
        if not (set(asset["platforms"]) & APPLICATION_PLATFORMS):
            continue
        found = _record_paths(asset, media)
        if "paths" in asset:
            missing_paths = sorted(set(asset["paths"]) - media)
            if missing_paths:
                raise _fail(
                    manifest,
                    f"{_asset_label(asset)} nennt fehlende Anwendungsmedien: "
                    + ", ".join(missing_paths),
                )
        if not found:
            unused.append(_asset_label(asset))
        if "content_sha256" in asset and set(asset["content_sha256"]) != found:
            raise _fail(
                manifest,
                f"{_asset_label(asset)} bindet nicht genau alle getroffenen Anwendungsbytes.",
            )
        for path in found:
            owners[path].append(_asset_label(asset))
            if Path(path).suffix.lower() not in ART_SUFFIXES[asset["art"]]:
                raise _fail(manifest, f"{path} passt nicht zur Medienart {asset['art']!r}.")
            expected_platforms = APPLICATION_PLATFORMS
            if path == "packaging/solidon3d.ico":
                expected_platforms = {"windows"}
            elif path == "packaging/solidon3d.icns":
                expected_platforms = {"macos"}
            if set(asset["platforms"]) != expected_platforms:
                raise _fail(
                    manifest,
                    f"{path} nennt {asset['platforms']!r} statt {sorted(expected_platforms)!r}.",
                )

    missing = sorted(path for path, records in owners.items() if not records)
    duplicate = {path: records for path, records in owners.items() if len(records) > 1}
    if missing:
        raise _fail(manifest, "Anwendungsmedien ohne Rechtekette: " + ", ".join(missing))
    if duplicate:
        details = "; ".join(
            f"{path}: {', '.join(records)}" for path, records in sorted(duplicate.items())
        )
        raise _fail(manifest, "Anwendungsmedien mit mehreren Rechteketten: " + details)
    if unused:
        raise _fail(manifest, "leere Anwendungsselektoren: " + ", ".join(sorted(unused)))


def _validate_website_coverage(assets: list[dict[str, Any]], manifest: Path, root: Path) -> None:
    """Jedes öffentliche Website-Medium genau einer Rechtekette zuordnen."""
    media = _website_media(root, manifest)
    if not media:
        raise _fail(manifest, "der Website-Baum enthält keine inventarisierbaren Medien.")
    owners: dict[str, list[str]] = {path: [] for path in media}
    unused: list[str] = []
    for asset in assets:
        if "web" not in asset["platforms"]:
            continue
        found = _record_paths(asset, media)
        if "paths" in asset:
            missing_paths = sorted(set(asset["paths"]) - media)
            if missing_paths:
                raise _fail(
                    manifest,
                    f"{_asset_label(asset)} nennt fehlende Website-Medien: "
                    + ", ".join(missing_paths),
                )
        if not found:
            unused.append(_asset_label(asset))
        if "content_sha256" in asset and set(asset["content_sha256"]) != found:
            raise _fail(
                manifest,
                f"{_asset_label(asset)} bindet nicht genau alle getroffenen Website-Bytes.",
            )
        for path in found:
            owners[path].append(_asset_label(asset))
            if Path(path).suffix.lower() not in ART_SUFFIXES[asset["art"]]:
                raise _fail(manifest, f"{path} passt nicht zur Medienart {asset['art']!r}.")
            if asset["platforms"] != ["web"]:
                raise _fail(manifest, f"{path} muss ausschließlich die Plattform 'web' nennen.")

    missing = sorted(path for path, records in owners.items() if not records)
    duplicate = {path: records for path, records in owners.items() if len(records) > 1}
    if missing:
        raise _fail(manifest, "Website-Medien ohne Rechtekette: " + ", ".join(missing))
    if duplicate:
        details = "; ".join(
            f"{path}: {', '.join(records)}" for path, records in sorted(duplicate.items())
        )
        raise _fail(manifest, "Website-Medien mit mehreren Rechteketten: " + details)
    if unused:
        raise _fail(manifest, "leere Website-Selektoren: " + ", ".join(sorted(unused)))


def _unexpected_remote_website_assets(
    assets: list[dict[str, Any]], remote_paths: Iterable[str], manifest: Path
) -> list[str]:
    """Servermedien ohne eindeutige Rechtekette ermitteln."""
    remote_media = _remote_website_media(remote_paths, manifest)
    unexpected: list[str] = []
    duplicate: dict[str, list[str]] = {}
    for path in sorted(remote_media):
        records = [
            _asset_label(asset)
            for asset in assets
            if "web" in asset["platforms"] and path in _record_paths(asset, {path})
        ]
        if not records:
            unexpected.append(path.removeprefix("website/"))
        elif len(records) > 1:
            duplicate[path] = records
    if duplicate:
        details = "; ".join(
            f"{path}: {', '.join(records)}" for path, records in sorted(duplicate.items())
        )
        raise _fail(manifest, "Servermedien mit mehreren Rechteketten: " + details)
    return unexpected


def load_manifest(path: Path = MANIFEST, *, root: Path = ROOT) -> dict[str, Any]:
    """Lädt und validiert den Rechtenachweis aus seiner einzigen Quelle."""
    try:
        with path.open("rb") as stream:
            document = tomllib.load(stream)
    except (OSError, tomllib.TOMLDecodeError) as problem:
        raise RuntimeError(
            f"{path} fehlt oder ist ungültig. Rechtenachweis vervollständigen und erneut bauen."
        ) from problem
    if set(document) != {"schema_version", "delivery", "asset"}:
        raise _fail(
            path,
            "das Wurzelschema muss genau schema_version, delivery und asset enthalten.",
        )
    if document["schema_version"] != 1:
        raise _fail(path, "nur schema_version = 1 wird unterstützt.")
    _validate_delivery(document, path)
    raw_assets = document["asset"]
    if not isinstance(raw_assets, list) or not raw_assets:
        raise _fail(path, "mindestens eine vollständige Rechtekette ist erforderlich.")
    for index, asset in enumerate(raw_assets):
        _validate_asset(asset, index, path, root)
    return document


def application_platform(value: str = sys.platform) -> str:
    """Übersetzt Pythons Plattformnamen in die Begriffe des Rechtekatalogs."""
    try:
        return PLATFORM_NAMES[value]
    except KeyError as problem:
        raise RuntimeError(
            f"Plattform {value!r} hat keine Rechtezuordnung. ASSET-RIGHTS.toml ergänzen."
        ) from problem


def _platform_source_media(platform: str, root: Path, manifest: Path) -> set[str]:
    """Die auf einem Zielsystem tatsächlich eingesammelten eigenen Medien liefern."""
    target = application_platform(platform)
    media = _application_media(root, manifest)
    assets = load_manifest(manifest, root=root)["asset"]
    return {
        path
        for path in media
        if any(
            target in asset["platforms"] and path in _record_paths(asset, {path})
            for asset in assets
        )
    }


def _artifact_media(artifact: Path, manifest: Path) -> dict[str, Path]:
    """Eigene App-Medien im fertigen PyInstaller-Artefakt eindeutig auffinden."""
    found: dict[str, Path] = {}
    for path in artifact.rglob("*"):
        relative = path.relative_to(artifact).as_posix()
        starts = [
            index
            for prefix in ("app/images/", "app/examples/")
            for index in (0 if relative.startswith(prefix) else relative.find("/" + prefix) + 1,)
            if index >= 0 and relative[index:].startswith(prefix)
        ]
        if not starts:
            continue
        source_path = relative[min(starts) :]
        if path.is_symlink() or _has_symlink_component(path, artifact):
            raise _fail(manifest, f"Symlink im fertigen Kundenartefakt: {relative}.")
        if not path.is_file():
            continue
        suffix = path.suffix.lower()
        if suffix not in DELIVERED_SUFFIXES:
            if source_path not in APPLICATION_NON_MEDIA_PATHS:
                raise _fail(
                    manifest,
                    f"unbekanntes Dateiformat im fertigen Kundenartefakt: {relative}.",
                )
            continue
        if source_path in found:
            raise _fail(manifest, f"Kundenmedium liegt mehrfach im Artefakt: {source_path}.")
        found[source_path] = path
    return found


def _receipt_path(artifact: Path, platform: str) -> Path:
    """Den plattformüblichen Datenort des mitreisenden Rechtebelegs liefern."""
    if application_platform(platform) == "macos":
        return artifact / "Contents" / "Resources" / RIGHTS_RECEIPT
    return artifact / "_internal" / RIGHTS_RECEIPT


def _control_hashes(
    *,
    manifest: Path,
    root: Path,
    checker: Path | None,
    spec: Path | None,
) -> dict[str, str]:
    """Manifest, Prüflogik und Paketbeschreibung an denselben Bau binden."""
    controls = {
        "manifest_sha256": manifest,
        "checker_sha256": checker or Path(__file__),
        "spec_sha256": spec or root / "packaging" / "solidon3d.spec",
    }
    result: dict[str, str] = {}
    for field, path in controls.items():
        if path.is_symlink() or not path.is_file():
            raise _fail(manifest, f"Steuerdatei für {field} fehlt oder ist ein Symlink: {path}.")
        result[field] = _sha256(path)
    return result


def write_customer_artifact_receipt(
    artifact: Path,
    platform: str = sys.platform,
    *,
    manifest: Path = MANIFEST,
    root: Path = ROOT,
    checker: Path | None = None,
    spec: Path | None = None,
) -> Path:
    """Rechteprüfung und exakte Medienbytes in das fertige Artefakt schreiben."""
    require_application_assets_cleared(platform, manifest=manifest, root=root)
    if artifact.is_symlink() or not artifact.is_dir():
        raise _fail(manifest, f"Kundenartefakt fehlt oder ist ein Symlink: {artifact}.")
    source_media = _platform_source_media(platform, root, manifest)
    packaged_sources = {
        path for path in source_media if path.startswith(("app/images/", "app/examples/"))
    }
    packaged = _artifact_media(artifact, manifest)
    if set(packaged) != packaged_sources:
        missing = sorted(packaged_sources - set(packaged))
        unexpected = sorted(set(packaged) - packaged_sources)
        raise _fail(
            manifest,
            f"Medienbestand im Kundenartefakt weicht ab; fehlt={missing}, unerwartet={unexpected}.",
        )
    source_hashes = {path: _sha256(root / path) for path in sorted(source_media)}
    payload: dict[str, Any] = {
        "schema_version": 1,
        "platform": application_platform(platform),
        **_control_hashes(manifest=manifest, root=root, checker=checker, spec=spec),
        "source_sha256": source_hashes,
        "packaged_media": {
            source: {
                "artifact_path": path.relative_to(artifact).as_posix(),
                "sha256": _sha256(path),
            }
            for source, path in sorted(packaged.items())
        },
    }
    receipt = _receipt_path(artifact, platform)
    receipt.parent.mkdir(parents=True, exist_ok=True)
    receipt.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return receipt


def require_customer_artifact_cleared(
    artifact: Path,
    platform: str = sys.platform,
    *,
    manifest: Path = MANIFEST,
    root: Path = ROOT,
    checker: Path | None = None,
    spec: Path | None = None,
) -> None:
    """Ein altes oder nachträglich verändertes Kundenartefakt fail-closed sperren."""
    require_application_assets_cleared(platform, manifest=manifest, root=root)
    if artifact.is_symlink() or not artifact.is_dir():
        raise _fail(manifest, f"Kundenartefakt fehlt oder ist ein Symlink: {artifact}.")
    receipt = _receipt_path(artifact, platform)
    if receipt.is_symlink() or not receipt.is_file() or _has_symlink_component(receipt, artifact):
        raise _fail(manifest, f"Rechtebeleg fehlt im fertigen Kundenartefakt: {receipt}.")
    try:
        document = json.loads(receipt.read_text(encoding="utf-8"))
    except (OSError, ValueError) as problem:
        raise _fail(
            manifest, f"Rechtebeleg im Kundenartefakt ist unlesbar: {receipt}."
        ) from problem
    required = {
        "schema_version",
        "platform",
        "manifest_sha256",
        "checker_sha256",
        "spec_sha256",
        "source_sha256",
        "packaged_media",
    }
    if not isinstance(document, dict) or set(document) != required:
        raise _fail(manifest, "Rechtebeleg im Kundenartefakt hat ein unbekanntes Schema.")
    if document["schema_version"] != 1 or document["platform"] != application_platform(platform):
        raise _fail(manifest, "Rechtebeleg gehört nicht zu dieser Paketplattform.")
    controls = _control_hashes(manifest=manifest, root=root, checker=checker, spec=spec)
    if any(document[field] != digest for field, digest in controls.items()):
        raise _fail(manifest, "Rechtenachweis oder Paketbeschreibung wurde nach dem Bau geändert.")

    source_media = _platform_source_media(platform, root, manifest)
    source_hashes = document["source_sha256"]
    if not isinstance(source_hashes, dict) or set(source_hashes) != source_media:
        raise _fail(manifest, "Quellmedien im Rechtebeleg sind unvollständig oder veraltet.")
    for source, expected in source_hashes.items():
        if not isinstance(expected, str) or _sha256(root / source) != expected:
            raise _fail(manifest, f"Quellmedium wurde nach dem Kundenbau geändert: {source}.")

    packaged = _artifact_media(artifact, manifest)
    packaged_sources = {
        path for path in source_media if path.startswith(("app/images/", "app/examples/"))
    }
    records = document["packaged_media"]
    if (
        not isinstance(records, dict)
        or set(records) != packaged_sources
        or set(packaged) != packaged_sources
    ):
        raise _fail(manifest, "Medienbestand des fertigen Kundenartefakts ist nicht mehr derselbe.")
    for source, path in packaged.items():
        record = records[source]
        if not isinstance(record, dict) or set(record) != {"artifact_path", "sha256"}:
            raise _fail(manifest, f"Bytebeleg für {source} ist unvollständig.")
        relative = path.relative_to(artifact).as_posix()
        actual = _sha256(path)
        if (
            record["artifact_path"] != relative
            or record["sha256"] != actual
            or source_hashes[source] != actual
        ):
            raise _fail(manifest, f"Kundenmedium wurde nach dem Bau geändert: {source}.")


def blocked_application_assets(
    platform: str = sys.platform,
    *,
    manifest: Path = MANIFEST,
    root: Path = ROOT,
) -> list[dict[str, Any]]:
    """Für das Zielsystem gesperrte Assets, stabil nach Nachweis sortiert."""
    target = application_platform(platform)
    document = load_manifest(manifest, root=root)
    _validate_application_coverage(document["asset"], manifest, root)
    blocked = [
        asset
        for asset in document["asset"]
        if asset["status"] == "distribution_blocked" and target in asset["platforms"]
    ]
    return sorted(blocked, key=lambda asset: _asset_label(asset).casefold())


def blocked_website_assets(
    *,
    manifest: Path = MANIFEST,
    root: Path = ROOT,
    remote_paths: Iterable[str] | None = None,
) -> list[dict[str, Any]]:
    """Für die öffentliche Website gesperrte Assets, stabil sortiert."""
    document = load_manifest(manifest, root=root)
    _validate_website_coverage(document["asset"], manifest, root)
    if remote_paths is not None:
        unexpected = _unexpected_remote_website_assets(document["asset"], remote_paths, manifest)
        if unexpected:
            raise _fail(
                manifest,
                "nicht inventarisierte Medien liegen weiterhin auf dem Webserver: "
                + ", ".join(unexpected),
            )
    blocked = [
        asset
        for asset in document["asset"]
        if asset["status"] == "distribution_blocked" and "web" in asset["platforms"]
    ]
    return sorted(blocked, key=lambda asset: _asset_label(asset).casefold())


def unexpected_remote_website_assets(
    remote_paths: Iterable[str],
    *,
    manifest: Path = MANIFEST,
    root: Path = ROOT,
) -> list[str]:
    """Nicht inventarisierte Servermedien für einen bestätigten Löschplan liefern."""
    document = load_manifest(manifest, root=root)
    _validate_website_coverage(document["asset"], manifest, root)
    return _unexpected_remote_website_assets(document["asset"], remote_paths, manifest)


def require_application_assets_cleared(
    platform: str = sys.platform,
    *,
    manifest: Path = MANIFEST,
    root: Path = ROOT,
) -> None:
    """Stoppt ein Kundenpaket bei ungültiger oder unvollständiger Rechtekette."""
    blocked = blocked_application_assets(platform, manifest=manifest, root=root)
    if not blocked:
        return
    details = "\n".join(f"- {_asset_label(asset)}: {asset['blocker']}" for asset in blocked)
    raise RuntimeError(
        "Der Kundenbau enthält Assets ohne vollständige Rechtefreigabe:\n"
        f"{details}\n"
        "Rechtebeleg und Lizenztext vervollständigen oder das Asset aus der Auslieferung nehmen."
    )


def require_website_assets_cleared(
    *,
    manifest: Path = MANIFEST,
    root: Path = ROOT,
    remote_paths: Iterable[str] | None = None,
) -> None:
    """Stoppt einen Website-Upload bei ungültiger oder unvollständiger Rechtekette."""
    blocked = blocked_website_assets(
        manifest=manifest,
        root=root,
        remote_paths=remote_paths,
    )
    if not blocked:
        return
    details = "\n".join(f"- {_asset_label(asset)}: {asset['blocker']}" for asset in blocked)
    raise RuntimeError(
        "Der Website-Upload enthält Medien ohne vollständige Rechtefreigabe:\n"
        f"{details}\n"
        "Rechtebeleg vervollständigen oder das Medium aus der Website nehmen."
    )
