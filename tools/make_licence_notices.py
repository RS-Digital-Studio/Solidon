"""Vollständige Lizenzbeilage aus den Wheels der Zielumgebung erzeugen.

Der Lauf gehört in jede Paketumgebung, nachdem genau deren Laufzeit-Extras
installiert sind. Er liest keine Entwicklungsabhängigkeiten und kein Netz:
Quelle sind ausschließlich die installierten Wheel-Dateien und die mit Hash
festgeschriebenen Ergänzungen unter ``app/core/knowledge/data``.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
import sysconfig
import tomllib
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path
from typing import Any, Final
from urllib.parse import unquote

from app.branding import APP_NAME, APP_VERSION, SUPPORT_ADDRESS
from app.core.knowledge import licences

ROOT: Final = Path(__file__).resolve().parent.parent
OUTPUT: Final = ROOT / "THIRD-PARTY-NOTICES.md"
MANIFEST_OUTPUT: Final = ROOT / "build" / "third-party-licenses.json"
FIXED_ROOT: Final = ROOT / "app" / "core" / "knowledge" / "data"
FIXED_MANIFEST: Final = FIXED_ROOT / "third_party_licenses.toml"
_NOTICE_NAMES: Final = ("license", "licence", "copying", "notice", "authors")
_IGNORED_WHEEL_TEXTS: Final = {
    "pyside6": {"licenseref-qt-commercial.txt"},
    "pyside6-addons": {"licenseref-qt-commercial.txt"},
    "pyside6-essentials": {"licenseref-qt-commercial.txt"},
    "shiboken6": {"licenseref-qt-commercial.txt"},
}


@dataclass(frozen=True, slots=True)
class NoticeText:
    """Ein unveränderlicher Lizenz- oder Urheberrechtstext."""

    name: str
    source: str
    content: str
    sha256: str


@dataclass(frozen=True, slots=True)
class ComponentNotice:
    """Lizenzakte genau einer installierten Distribution."""

    name: str
    version: str
    expression: str
    source_url: str
    texts: tuple[NoticeText, ...]


@dataclass(frozen=True, slots=True)
class RuntimePolicy:
    """Belegregeln für eine native Laufzeitfamilie im Kundenartefakt."""

    identifier: str
    name: str
    source_url: str
    notice_package: str
    notice_source: str
    notice_required: bool
    source_delivery: bool
    versions: frozenset[str]


def _digest(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _normalised_text(path: Path) -> str:
    """Liest Fremdtexte mit stabilen Zeilenenden und ohne Rand-Leerraum."""
    content = path.read_text(encoding="utf-8", errors="strict").replace("\r\n", "\n")
    return "\n".join(line.rstrip() for line in content.rstrip().split("\n")) + "\n"


def _source_url(package: metadata.Distribution) -> str:
    """Bevorzugt den Quelltext-Link, dann Projektseite und Homepage."""
    project_urls: list[str] = package.metadata.get_all("Project-URL", [])
    parsed: list[tuple[str, str]] = []
    for entry in project_urls:
        label, separator, url = entry.partition(",")
        if separator and url.strip():
            parsed.append((label.strip().lower(), url.strip()))
    for wanted in ("source", "repository", "homepage"):
        for label, url in parsed:
            if label == wanted:
                return url
    homepage = str(package.metadata.get("Home-page", "")).strip()
    return homepage or next((url for _label, url in parsed), "")


def _wheel_texts(package: metadata.Distribution) -> tuple[NoticeText, ...]:
    """Alle Lizenz-, NOTICE- und Autorendateien eines Ziel-Wheels."""
    key = licences.normalise(str(package.metadata["Name"]))
    ignored = _IGNORED_WHEEL_TEXTS.get(key, set())
    found: list[NoticeText] = []
    for entry in sorted(package.files or (), key=lambda item: str(item).lower()):
        lowered = entry.name.lower()
        if lowered in ignored or not any(marker in lowered for marker in _NOTICE_NAMES):
            continue
        # Nur Akten aus der Distribution. Eine Bibliothek darf eigene
        # Laufzeitdaten namens LICENSE tragen; genau die gehören ebenfalls dazu.
        path = Path(str(package.locate_file(entry)))
        if not path.is_file():
            continue
        content = _normalised_text(path)
        found.append(NoticeText(str(entry), f"wheel:{entry}", content, _digest(content)))
    return tuple(found)


def _fixed_records(
    record_key: str = "packages",
) -> dict[str, list[tuple[set[str], NoticeText]]]:
    """Prüft Ergänzungen und ordnet sie Paketen oder Laufzeitfamilien zu."""
    with FIXED_MANIFEST.open("rb") as stream:
        document: dict[str, Any] = tomllib.load(stream)
    records: dict[str, list[tuple[set[str], NoticeText]]] = {}
    for entry in document.get("text", []):
        relative = Path(str(entry["path"]))
        path = FIXED_ROOT / relative
        content = _normalised_text(path)
        actual = _digest(content)
        expected = str(entry["sha256"])
        if actual != expected:
            raise RuntimeError(
                f"{relative} hat SHA-256 {actual}, erwartet wird {expected}. "
                "Prüfen Sie Quelle und Manifest gemeinsam."
            )
        notice = NoticeText(relative.name, str(entry["source"]), content, actual)
        versions = {str(value) for value in entry.get("versions", [])}
        for package in entry.get(record_key, []):
            records.setdefault(licences.normalise(str(package)), []).append((versions, notice))
    return records


def _runtime_policies() -> dict[str, RuntimePolicy]:
    """Liest den vollständigen, prüfbaren Katalog nativer Laufzeitfamilien."""
    with FIXED_MANIFEST.open("rb") as stream:
        document: dict[str, Any] = tomllib.load(stream)
    policies: dict[str, RuntimePolicy] = {}
    for entry in document.get("runtime", []):
        identifier = str(entry["id"])
        if identifier in policies:
            raise RuntimeError(f"Doppelte Laufzeitfamilie {identifier} in {FIXED_MANIFEST.name}.")
        policies[identifier] = RuntimePolicy(
            identifier=identifier,
            name=str(entry["name"]),
            source_url=str(entry["source"]),
            notice_package=str(entry.get("notice_package", "")),
            notice_source=str(entry.get("notice_source", "")),
            notice_required=bool(entry.get("notice_required", True)),
            source_delivery=bool(entry.get("source_delivery", False)),
            versions=frozenset(str(value) for value in entry.get("versions", [])),
        )
    return policies


def collect_components() -> tuple[ComponentNotice, ...]:
    """Sammelt die vollständige Lizenzakte der aktuellen Zielumgebung."""
    policy = licences.load_policy()
    violations = licences.check()
    if violations:
        details = "\n".join(f"- {violation}" for violation in violations)
        raise RuntimeError(f"Die Zielumgebung verletzt die Lizenzrichtlinie:\n{details}")
    known = {licences.normalise(key): value for key, value in policy.known.items()}
    fixed = _fixed_records()
    components: list[ComponentNotice] = []
    for package_name in sorted(licences.runtime_packages(strict=True), key=str.lower):
        package = metadata.distribution(package_name)
        name = str(package.metadata["Name"])
        key = licences.normalise(name)
        expression = known.get(key, {}).get("licence", "") or licences.declared_licence(package)
        if not expression:
            raise RuntimeError(f"{name} {package.version} hat keinen geprüften SPDX-Ausdruck.")
        if not licences.licence_allowed(expression, policy):
            raise RuntimeError(f"{name} {package.version}: {expression} ist nicht freigegeben.")
        texts = list(_wheel_texts(package))
        for versions, notice in fixed.get(key, []):
            if versions and package.version not in versions:
                raise RuntimeError(
                    f"{name} {package.version} passt nicht zur festgeschriebenen "
                    f"Lizenztextfassung für {', '.join(sorted(versions))}."
                )
            texts.append(notice)
        if not texts:
            raise RuntimeError(
                f"{name} {package.version} bringt keinen Lizenztext mit und hat keine "
                f"geprüfte Ergänzung in {FIXED_MANIFEST.name}."
            )
        components.append(
            ComponentNotice(
                name=name,
                version=package.version,
                expression=expression,
                source_url=_source_url(package)
                or next((text.source for text in texts if text.source.startswith("https://")), ""),
                texts=tuple(texts),
            )
        )
    return tuple(components)


def _sbom_licence(component: dict[str, Any]) -> str:
    """Liest genau den einen Lizenzwert einer Laufzeitkomponente."""
    choices = component.get("licenses", [])
    if len(choices) != 1:
        raise RuntimeError(f"{component.get('name', '?')} hat keine eindeutige SBOM-Lizenz.")
    choice = choices[0]
    if "expression" in choice:
        return str(choice["expression"])
    return str(choice.get("license", {}).get("name", ""))


def _generic_identifier(component: dict[str, Any]) -> str:
    """Gewinnt die stabile Familien-ID aus einem generischen Package-URL."""
    purl = str(component.get("purl", ""))
    prefix = "pkg:generic/"
    if not purl.startswith(prefix) or "@" not in purl:
        return ""
    return unquote(purl[len(prefix) :].rsplit("@", 1)[0])


def _python_runtime_text() -> NoticeText:
    """Liest die mit dem Build-Interpreter ausgelieferte CPython-Lizenzakte."""
    candidates = (
        Path(sys.base_prefix) / "LICENSE.txt",
        Path(sys.base_prefix) / "LICENSE",
    )
    path = next((entry for entry in candidates if entry.is_file()), None)
    if path is None:
        raise RuntimeError("Die CPython-Lizenzdatei fehlt in der Zielumgebung.")
    content = _normalised_text(path)
    return NoticeText(
        name=path.name,
        source=f"build-runtime:{path.name}",
        content=content,
        sha256=_digest(content),
    )


def _runtime_texts(policy: RuntimePolicy, version: str) -> tuple[NoticeText, ...]:
    """Ordnet einer SBOM-Laufzeitfamilie ihre vollständigen Lizenztexte zu."""
    texts: list[NoticeText] = []
    if policy.notice_source == "python-runtime":
        texts.append(_python_runtime_text())
    if policy.notice_package:
        package = metadata.distribution(policy.notice_package)
        texts.extend(_wheel_texts(package))
        for versions, notice in _fixed_records().get(licences.normalise(policy.notice_package), []):
            if versions and package.version not in versions:
                raise RuntimeError(
                    f"{package.metadata['Name']} {package.version} passt nicht zur "
                    "festgeschriebenen Textfassung."
                )
            texts.append(notice)
    for versions, notice in _fixed_records("runtime").get(
        licences.normalise(policy.identifier), []
    ):
        if versions and version not in versions:
            raise RuntimeError(
                f"{policy.name} {version} passt nicht zur festgeschriebenen Textfassung."
            )
        texts.append(notice)
    unique = {text.sha256: text for text in texts}
    if policy.notice_required and not unique:
        raise RuntimeError(f"Für {policy.name} {version} fehlt der vollständige Lizenztext.")
    return tuple(sorted(unique.values(), key=lambda text: (text.name.casefold(), text.sha256)))


def collect_artifact_components(sbom: dict[str, Any]) -> tuple[ComponentNotice, ...]:
    """Erweitert die Wheel-Akte um jede generische Familie des Endartefakts."""
    policies = _runtime_policies()
    components = list(collect_components())
    seen_names = {licences.normalise(component.name) for component in components}
    for entry in sbom.get("components", []):
        if not isinstance(entry, dict) or entry.get("type") != "library":
            continue
        identifier = _generic_identifier(entry)
        if not identifier:
            continue
        policy = policies.get(identifier)
        if policy is None:
            raise RuntimeError(
                f"Die SBOM-Laufzeitfamilie {identifier} fehlt in {FIXED_MANIFEST.name}."
            )
        name = str(entry.get("name", ""))
        version = str(entry.get("version", ""))
        if name != policy.name or not version:
            raise RuntimeError(f"Unstimmige SBOM-Akte für Laufzeitfamilie {identifier}.")
        if policy.versions and version not in policy.versions:
            raise RuntimeError(f"{policy.name} {version} passt nicht zur geprüften Quellenfassung.")
        version_source = next(
            (
                str(item.get("value", ""))
                for item in entry.get("properties", [])
                if item.get("name") == "solidon:version-source"
            ),
            "",
        )
        if (
            version == "unbekannt"
            or version.startswith("ABI-")
            or version_source.startswith("Compilerangabe")
        ):
            raise RuntimeError(
                f"{policy.name} hat keine exakte Binärversion in der Endartefakt-SBOM."
            )
        if licences.normalise(name) in seen_names:
            raise RuntimeError(f"Doppelte Komponente {name} in Wheel- und Laufzeitakte.")
        components.append(
            ComponentNotice(
                name=name,
                version=version,
                expression=_sbom_licence(entry),
                source_url=policy.source_url,
                texts=_runtime_texts(policy, version),
            )
        )
        seen_names.add(licences.normalise(name))
    return tuple(sorted(components, key=lambda component: component.name.casefold()))


def render_notices(components: tuple[ComponentNotice, ...]) -> str:
    """Schreibt Index und vollständige Texte in stabiler Reihenfolge."""
    lines = [
        "# Drittanbieter-Lizenzen",
        "",
        f"Erzeugt für {APP_NAME} {APP_VERSION} auf `{sysconfig.get_platform()}`.",
        "Quelle sind die Lizenzdateien der tatsächlich installierten Ziel-Wheels",
        "und die im Repository mit SHA-256 festgeschriebenen Ergänzungen.",
        "",
        "| Paket | Version | SPDX-Ausdruck | Quelle |",
        "|---|---:|---|---|",
    ]
    for component in components:
        source = f"[Quelltext]({component.source_url})" if component.source_url else "—"
        lines.append(
            f"| {component.name} | {component.version} | `{component.expression}` | {source} |"
        )
    lines.extend(["", "## Vollständige Hinweise und Lizenztexte", ""])
    for component in components:
        lines.extend(
            [
                f"### {component.name} {component.version}",
                "",
                f"SPDX-Ausdruck: `{component.expression}`",
                "",
            ]
        )
        for notice in component.texts:
            lines.extend(
                [
                    f"#### {notice.name}",
                    "",
                    f"Quelle: {notice.source}",
                    "",
                    f"SHA-256: `{notice.sha256}`",
                    "",
                    "```text",
                    notice.content.rstrip(),
                    "```",
                    "",
                ]
            )
    return "\n".join(lines).rstrip() + "\n"


def render_manifest(components: tuple[ComponentNotice, ...]) -> str:
    """Maschinenlesbare Integrationsschnittstelle für Paket und CRA-Akte."""
    policies = _runtime_policies()
    payload = {
        "schema": 2,
        "product": {"name": APP_NAME, "version": APP_VERSION},
        "target": sysconfig.get_platform(),
        "components": [
            {
                "name": component.name,
                "version": component.version,
                "license_expression": component.expression,
                "source_url": component.source_url,
                "texts": [
                    {"name": text.name, "source": text.source, "sha256": text.sha256}
                    for text in component.texts
                ],
            }
            for component in components
        ],
        "release_gate": {
            "artifact_notice": OUTPUT.name,
            "artifact_sbom": "Solidon3D.cdx.json",
            "runtime_families": sorted(policies),
            "source_delivery": sorted(
                identifier for identifier, policy in policies.items() if policy.source_delivery
            ),
        },
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _file_digest(path: Path) -> str:
    """Hasht ein Release-Artefakt bytegenau und speicherschonend."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _evidence_file(root: Path, value: object) -> Path:
    """Löst ausschließlich relative, innerhalb der Evidenzablage liegende Pfade auf."""
    relative = Path(str(value))
    if relative.is_absolute() or ".." in relative.parts:
        raise RuntimeError(f"Unzulässiger Evidenzpfad: {relative}")
    path = (root / relative).resolve()
    if root.resolve() not in path.parents:
        raise RuntimeError(f"Evidenzpfad verlässt die Ablage: {relative}")
    return path


def _verify_hashed_file(root: Path, entry: dict[str, Any], field: str) -> Path:
    """Prüft Existenz und SHA-256 einer benannten Release-Datei."""
    path = _evidence_file(root, entry[field])
    if not path.is_file():
        raise RuntimeError(f"Evidenzdatei fehlt: {entry[field]}")
    expected = str(entry[f"{field}_sha256"])
    actual = _file_digest(path)
    if actual != expected:
        raise RuntimeError(f"{entry[field]} hat SHA-256 {actual}, erwartet wird {expected}.")
    return path


def _required_package_kinds(target: str) -> set[str]:
    """Nennt die äußersten Kundenpakete, die pro Zielplattform belegt sein müssen."""
    lowered = target.casefold()
    if lowered.startswith("win"):
        return {"windows-installer"}
    if lowered.startswith("linux"):
        return {"appimage", "flatpak"}
    if lowered.startswith(("macos", "darwin")):
        return {"macos-installer"}
    raise RuntimeError(f"Unbekannte Release-Zielplattform: {target}")


def _three_year_anniversary(value: dt.date) -> dt.date:
    """Bildet die Dreijahresfrist auch für einen 29. Februar eindeutig ab."""
    try:
        return value.replace(year=value.year + 3)
    except ValueError:
        return value.replace(year=value.year + 3, day=28)


#: Wie der Quelltext einer LGPL-Familie bereitgestellt wird. ``archive`` legt
#: Quellarchiv und Austauschmaterial bei; ``written-offer`` ist das schriftliche
#: Angebot über mindestens drei Jahre (LGPL 3 §4 d(1), GPL 3 §6 b) — dann liegt
#: kein Archiv bei, und das Relinken läuft über den Austausch der geteilten
#: Bibliothek (LGPL 3 §4 d(1): „a suitable shared library mechanism").
EVIDENCE_METHODS: Final = frozenset({"archive", "written-offer"})
RELINK_METHODS: Final = frozenset({"shared-library-replacement", "archive"})
#: Ein Tag über der Dreijahresfrist, damit die Prüfung auch am Stichtag hält.
OFFER_GRACE_DAYS: Final = 1


def write_release_evidence(
    sbom_path: Path,
    evidence_path: Path,
    packages: dict[str, Path],
    *,
    contact: str = SUPPORT_ADDRESS,
    release_date: dt.date | None = None,
) -> dict[str, Any]:
    """Schreibt die Release-Evidenz aus der Endartefakt-SBOM und den äußeren Paketen.

    **Bis zum 02.09.2026 gab es nur den Prüfer.** ``--release-check`` verlangte
    ``build/release-evidence.json``, und kein Schritt in ``tools/``,
    ``packaging/`` oder ``.github/`` schrieb sie — jeder Releaseakte-Job wäre
    am ersten Aufruf mit ``FileNotFoundError`` gestorben, auf allen drei
    Plattformen. Aufgefallen ist es nicht, weil jeder Tag-Lauf seit dem
    Einbau der Prüfung vorher abgebrochen wurde.

    Was hier entsteht, prüft :func:`_verify_release_evidence` danach am
    selben Ort: die Hashes der äußeren Kundenpakete (je Zielplattform die
    Sorten aus :func:`_required_package_kinds`), und je Laufzeitfamilie mit
    ``source_delivery`` ein schriftliches Quellenangebot von RS Digital —
    Version aus der SBOM, nicht aus einer Liste, damit keyutils aus
    ``dpkg-query`` dieselbe Zahl trägt wie Qt aus dem Wheel. Die Pakete müssen
    in der Ablage der Evidenz liegen: Der Prüfer löst nur relative Pfade darin
    auf, und die CI kopiert sie deshalb vorher nach ``build/``.
    """
    sbom = json.loads(sbom_path.read_text(encoding="utf-8"))
    target = next(
        (
            str(entry.get("value", ""))
            for entry in sbom.get("metadata", {}).get("properties", [])
            if entry.get("name") == "solidon:target-platform"
        ),
        "",
    )
    if not target:
        raise RuntimeError("Die Endartefakt-SBOM nennt keine Zielplattform.")
    released = release_date or dt.date.today()
    root = evidence_path.parent.resolve()
    root.mkdir(parents=True, exist_ok=True)
    if missing_kinds := _required_package_kinds(target) - set(packages):
        raise RuntimeError("Äußere Release-Pakete fehlen: " + ", ".join(sorted(missing_kinds)))
    package_entries: list[dict[str, Any]] = []
    for kind, path in sorted(packages.items()):
        resolved = path.resolve()
        if not resolved.is_file():
            raise RuntimeError(f"Release-Paket fehlt: {path}")
        if root not in resolved.parents:
            raise RuntimeError(f"Release-Paket liegt nicht in der Evidenzablage: {path}")
        package_entries.append(
            {
                "kind": kind,
                "path": resolved.relative_to(root).as_posix(),
                "path_sha256": _file_digest(resolved),
            }
        )
    versions = {
        _generic_identifier(entry): str(entry.get("version", ""))
        for entry in sbom.get("components", [])
        if isinstance(entry, dict) and _generic_identifier(entry)
    }
    available_until = _three_year_anniversary(released) + dt.timedelta(days=OFFER_GRACE_DAYS)
    provisions = [
        {
            "component_id": identifier,
            "version": versions[identifier],
            "issuer": "RS Digital",
            "contact": contact,
            "method": "written-offer",
            "offer_text": (
                f"RS Digital stellt den vollständigen Quelltext von {policy.name} "
                f"{versions[identifier]} in der ausgelieferten Fassung auf Anfrage an "
                f"{contact} bereit — mindestens bis zum {available_until.isoformat()}, "
                f"zu den Kosten des Datenträgers. Quelle: {policy.source_url}"
            ),
            "relink_method": "shared-library-replacement",
            "source_url": policy.source_url,
            "available_until": available_until.isoformat(),
        }
        for identifier, policy in sorted(_runtime_policies().items())
        if policy.source_delivery and identifier in versions
    ]
    evidence: dict[str, Any] = {
        "schema": 1,
        "product_version": APP_VERSION,
        "target": target,
        "release_date": released.isoformat(),
        "packages": package_entries,
        "source_provisions": provisions,
    }
    evidence_path.write_text(
        json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return evidence


def _verify_release_evidence(
    evidence_path: Path,
    sbom: dict[str, Any],
) -> None:
    """Prüft Quellarchive, Austauschmaterial und äußere Plattformpakete."""
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    if evidence.get("schema") != 1 or evidence.get("product_version") != APP_VERSION:
        raise RuntimeError("Release-Evidenzschema oder Produktversion passt nicht.")
    target = str(evidence.get("target", ""))
    sbom_target = next(
        (
            str(entry.get("value", ""))
            for entry in sbom.get("metadata", {}).get("properties", [])
            if entry.get("name") == "solidon:target-platform"
        ),
        "",
    )
    if not sbom_target or target != sbom_target:
        raise RuntimeError("Zielplattform von Release-Evidenz und Endartefakt-SBOM weicht ab.")
    sbom_product = sbom.get("metadata", {}).get("component", {})
    if sbom_product.get("version") != APP_VERSION:
        raise RuntimeError("Produktversion der Endartefakt-SBOM passt nicht.")
    root = evidence_path.parent
    package_entries = evidence.get("packages", [])
    package_kinds: set[str] = set()
    for entry in package_entries:
        if not isinstance(entry, dict):
            raise RuntimeError("Ungültiger Eintrag unter packages.")
        package_kinds.add(str(entry.get("kind", "")))
        _verify_hashed_file(root, entry, "path")
    missing_packages = _required_package_kinds(target) - package_kinds
    if missing_packages:
        raise RuntimeError(
            "Äußere Release-Pakete ohne Hashbeleg: " + ", ".join(sorted(missing_packages))
        )

    try:
        released = dt.date.fromisoformat(str(evidence["release_date"]))
    except (KeyError, ValueError) as exc:
        raise RuntimeError("release_date fehlt oder ist kein ISO-Datum.") from exc
    versions = {
        _generic_identifier(entry): str(entry.get("version", ""))
        for entry in sbom.get("components", [])
        if isinstance(entry, dict) and _generic_identifier(entry)
    }
    if target.casefold().startswith("linux") and "appimage-type2-runtime" not in versions:
        raise RuntimeError(
            "Der eingebettete AppImage type-2 runtime fehlt in der Endartefakt-SBOM."
        )
    required = {
        identifier
        for identifier, policy in _runtime_policies().items()
        if policy.source_delivery and identifier in versions
    }
    provisions: dict[str, dict[str, Any]] = {}
    for entry in evidence.get("source_provisions", []):
        if not isinstance(entry, dict):
            raise RuntimeError("Ungültiger Eintrag unter source_provisions.")
        identifier = str(entry.get("component_id", ""))
        if identifier in provisions:
            raise RuntimeError(f"Doppelter Quellbeleg für {identifier}.")
        provisions[identifier] = entry
    if missing := required - set(provisions):
        raise RuntimeError("Quell-/Austauschbeleg fehlt für: " + ", ".join(sorted(missing)))
    for identifier in sorted(required):
        entry = provisions[identifier]
        if entry.get("version") != versions[identifier]:
            raise RuntimeError(f"Quellarchiv-Version für {identifier} passt nicht zur SBOM.")
        if entry.get("issuer") != "RS Digital" or not str(entry.get("contact", "")).strip():
            raise RuntimeError(f"{identifier}: RS Digital oder Kontakt fehlt im Quellenangebot.")
        method = entry.get("method")
        if method not in EVIDENCE_METHODS:
            raise RuntimeError(f"{identifier}: unbekannte Bereitstellungsmethode.")
        if method == "archive":
            _verify_hashed_file(root, entry, "source_archive")
            _verify_hashed_file(root, entry, "relink_material")
        else:
            # Das schriftliche Angebot: Text, Kontakt und Frist sind der Beleg,
            # das Relinken läuft über die austauschbare Bibliothek. Archive sind
            # dann freiwillig — genannt, werden sie geprüft.
            if not str(entry.get("offer_text", "")).strip():
                raise RuntimeError(f"{identifier}: das schriftliche Angebot hat keinen Text.")
            if entry.get("relink_method") not in RELINK_METHODS:
                raise RuntimeError(f"{identifier}: unbekannter Relink-Weg.")
            for field in ("source_archive", "relink_material"):
                if entry.get(field):
                    _verify_hashed_file(root, entry, field)
        try:
            available_until = dt.date.fromisoformat(str(entry["available_until"]))
        except (KeyError, ValueError) as exc:
            raise RuntimeError(f"{identifier}: available_until ist ungültig.") from exc
        if available_until < _three_year_anniversary(released):
            raise RuntimeError(f"{identifier}: Quellenangebot gilt weniger als drei Jahre.")


def verify_release(
    artifact_root: Path,
    sbom_path: Path,
    evidence_path: Path,
) -> tuple[ComponentNotice, ...]:
    """Prüft Notice, SBOM, native Dateien und Quellbelege am Endartefakt."""
    from tools import make_sbom

    sbom = json.loads(sbom_path.read_text(encoding="utf-8"))
    files = make_sbom.artifact_files(artifact_root)
    unassigned = sorted(entry.path for entry in files if entry.owner == "unassigned-native")
    if unassigned:
        raise RuntimeError("Native Dateien ohne Besitzer: " + ", ".join(unassigned))
    sbom_files = {
        str(entry.get("name"))
        for entry in sbom.get("components", [])
        if isinstance(entry, dict) and entry.get("type") == "file"
    }
    actual_files = {entry.path for entry in files}
    if sbom_files != actual_files:
        raise RuntimeError("Native Dateiliste und Endartefakt-SBOM weichen voneinander ab.")

    components = collect_artifact_components(sbom)
    records = {(licences.normalise(component.name), component.version) for component in components}
    missing = sorted(
        f"{entry.get('name')} {entry.get('version')}"
        for entry in sbom.get("components", [])
        if isinstance(entry, dict)
        and entry.get("type") == "library"
        and (licences.normalise(str(entry.get("name"))), str(entry.get("version"))) not in records
    )
    if missing:
        raise RuntimeError("SBOM-Komponenten ohne Lizenzakte: " + ", ".join(missing))
    notice_files = sorted(artifact_root.rglob(OUTPUT.name))
    if len(notice_files) != 1:
        raise RuntimeError(f"{OUTPUT.name} liegt im Endartefakt {len(notice_files)}-mal vor.")
    if notice_files[0].read_text(encoding="utf-8") != render_notices(components):
        raise RuntimeError("Lizenzbeilage wurde nicht aus der Endartefakt-SBOM erzeugt.")
    _verify_release_evidence(evidence_path, sbom)
    return components


def write_bundle(
    output: Path = OUTPUT,
    manifest: Path = MANIFEST_OUTPUT,
    sbom: Path | None = None,
) -> None:
    """Erzeugt menschen- und maschinenlesbare Akte aus demselben Bestand."""
    components = (
        collect_artifact_components(json.loads(sbom.read_text(encoding="utf-8")))
        if sbom is not None
        else collect_components()
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    manifest.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_notices(components), encoding="utf-8")
    manifest.write_text(render_manifest(components), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--manifest", type=Path, default=MANIFEST_OUTPUT)
    parser.add_argument("--sbom", type=Path)
    parser.add_argument("--artifact-root", type=Path)
    parser.add_argument("--release-evidence", type=Path)
    parser.add_argument("--release-check", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write-evidence", action="store_true")
    parser.add_argument(
        "--package",
        action="append",
        default=[],
        metavar="SORTE=PFAD",
        help="ein äußeres Kundenpaket, z. B. appimage=build/Solidon3D-0.3.0-x86_64.AppImage",
    )
    parser.add_argument("--contact", default=SUPPORT_ADDRESS)
    parser.add_argument("--release-date", type=dt.date.fromisoformat)
    arguments = parser.parse_args()
    if arguments.write_evidence:
        if not arguments.sbom or not arguments.release_evidence:
            parser.error("--write-evidence verlangt --sbom und --release-evidence")
        packages: dict[str, Path] = {}
        for item in arguments.package:
            kind, separator, value = str(item).partition("=")
            if not separator or not kind or not value:
                parser.error(f"--package erwartet SORTE=PFAD, bekam {item!r}")
            packages[kind] = Path(value)
        try:
            evidence = write_release_evidence(
                arguments.sbom,
                arguments.release_evidence,
                packages,
                contact=arguments.contact,
                release_date=arguments.release_date,
            )
        except (OSError, KeyError, ValueError, RuntimeError) as exc:
            print(f"Release-Evidenz nicht geschrieben: {exc}")
            return 1
        print(
            f"Release-Evidenz geschrieben: {len(evidence['packages'])} Pakete, "
            f"{len(evidence['source_provisions'])} Quellenangebote in {arguments.release_evidence}"
        )
        return 0
    if arguments.release_check:
        if not arguments.artifact_root or not arguments.sbom or not arguments.release_evidence:
            parser.error("--release-check verlangt --artifact-root, --sbom und --release-evidence")
        try:
            verified = verify_release(
                arguments.artifact_root,
                arguments.sbom,
                arguments.release_evidence,
            )
        except (OSError, KeyError, ValueError, RuntimeError) as exc:
            print(f"Release-Lizenzprüfung rot: {exc}")
            return 1
        print(f"Release-Lizenzprüfung grün: {len(verified)} Komponenten")
        return 0
    components = (
        collect_artifact_components(json.loads(arguments.sbom.read_text(encoding="utf-8")))
        if arguments.sbom
        else collect_components()
    )
    notices = render_notices(components)
    manifest = render_manifest(components)
    if arguments.check:
        current_notices = (
            arguments.output.read_text(encoding="utf-8") if arguments.output.is_file() else ""
        )
        current_manifest = (
            arguments.manifest.read_text(encoding="utf-8") if arguments.manifest.is_file() else ""
        )
        if current_notices != notices or current_manifest != manifest:
            print("Lizenzbeilage oder Lizenzmanifest passt nicht zur Zielumgebung.")
            return 1
        return 0
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.manifest.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(notices, encoding="utf-8")
    arguments.manifest.write_text(manifest, encoding="utf-8")
    print(f"{arguments.output}: {len(components)} Laufzeitkomponenten")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
