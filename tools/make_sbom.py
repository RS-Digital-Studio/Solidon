r"""Erzeugt die CycloneDX-Stückliste des ausgelieferten Laufzeitbaums (§37.3).

Die Entwicklungsumgebung ist absichtlich **nicht** die Quelle. Die
PyInstaller-Spec übergibt nach ihrer Analyse die tatsächlich aufgenommenen
Importpakete. Nur Distributionen, die zugleich zu Solidons Laufzeitbaum
gehören und im Analyseergebnis vorkommen, erscheinen im Kundenartefakt.

Aufruf::

    .venv\Scripts\python.exe tools/make_sbom.py

Ohne PyInstaller-Analyse erzeugt der Aufruf eine konservative Vorschau der
deklarierten Laufzeitmenge. Sie ist ausdrücklich kein Kundenartefakt.
"""

from __future__ import annotations

import argparse
import json
import platform
import re
import shutil
import ssl
import subprocess
import sys
import sysconfig
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path
from typing import Any, Final, cast
from urllib.parse import quote

from packaging.markers import default_environment
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

from app.branding import APP_NAME, APP_VERSION, DISTRIBUTION_NAME
from app.core.knowledge import licences

ROOT: Final = Path(__file__).resolve().parent.parent
OUTPUT: Final = ROOT / "build" / "Solidon3D.cdx.json"
RUNTIME_EXTRAS: Final = licences.RUNTIME_EXTRAS
SPDX_ALIASES: Final = {"LGPL-3.0": "LGPL-3.0-only"}
NON_SPDX_LICENCES: Final = {
    "PSF-based",
    "Microsoft Visual Studio Runtime license",
}
# CPython-Tags: PCbuild/python.props setzt in jedem dieser Windows-Bauten 3.4.4.
WINDOWS_LIBFFI_VERSIONS: Final = {"3.13.14": "3.4.4", "3.13.15": "3.4.4", "3.14.7": "3.4.4"}
#: Die Microsoft-Laufzeit im Windows-Paket: C++-Laufzeit, UCRT und ihre
#: Weiterleitungs-DLLs. ``api-ms-win-core-*`` fehlte hier — 29 Dateien ohne
#: Besitzer im Windows-Artefakt, gemessen am 31.08.2026.
MSVC_RUNTIME_PREFIXES: Final = (
    "msvcp",
    "vcruntime",
    "ucrtbase",
    "api-ms-win-crt",
    "api-ms-win-core",
)
#: Systembibliotheken, die das Linux-Paket bewusst mitnimmt, als Familien mit
#: ihren Sonamen-Präfixen (kleingeschrieben). Reihenfolge zählt: Die
#: xcb-util-Bibliotheken heißen alle ``libxcb-…`` und stehen deshalb vor
#: ``libxcb`` selbst. Was das Paket dem Rechner überlässt, steht in
#: ``make_linux_packages.HOST_PROVIDED_LIBRARIES``.
LINUX_LIBRARY_FAMILIES: Final = (
    ("xcb-util-cursor", ("libxcb-cursor.",)),
    ("xcb-util-image", ("libxcb-image.",)),
    ("xcb-util-keysyms", ("libxcb-keysyms.",)),
    ("xcb-util-renderutil", ("libxcb-render-util.",)),
    ("xcb-util-wm", ("libxcb-icccm.", "libxcb-ewmh.")),
    ("xcb-util", ("libxcb-util.",)),
    ("libxcb", ("libxcb-", "libxcb.")),
    ("libxkbcommon", ("libxkbcommon",)),
    ("krb5", ("libgssapi_krb5.", "libkrb5.", "libk5crypto.", "libkrb5support.")),
    ("e2fsprogs", ("libcom_err.",)),
    ("keyutils", ("libkeyutils.",)),
    # Kleingeschrieben, weil ``_runtime_owner`` den Dateinamen faltet — ein
    # Präfix mit großem X träfe nie, und die Datei fiele als besitzerlos auf.
    ("libx11", ("libx11.", "libx11-xcb.")),
    ("expat", ("libexpat.",)),
    ("fontconfig", ("libfontconfig.",)),
    ("freetype", ("libfreetype.",)),
    (
        "glib",
        ("libglib-2.0.", "libgio-2.0.", "libgobject-2.0.", "libgmodule-2.0.", "libgthread-2.0."),
    ),
    ("pcre2", ("libpcre2-",)),
    ("dbus", ("libdbus-1.",)),
    ("systemd", ("libsystemd.",)),
    ("libgcrypt", ("libgcrypt.",)),
    ("libgpg-error", ("libgpg-error.",)),
    ("libcap", ("libcap.",)),
    ("lz4", ("liblz4.",)),
    ("xz", ("liblzma.",)),
    ("zstd", ("libzstd.",)),
    ("brotli", ("libbrotli",)),
    ("bzip2", ("libbz2.",)),
    ("util-linux", ("libmount.", "libblkid.")),
    ("libuuid", ("libuuid.",)),
    ("libselinux", ("libselinux.",)),
    ("libpng", ("libpng",)),
    ("zlib", ("libz.",)),
)
#: Name, Lizenz und Herkunft je Familie — der Name muss dem ``[[runtime]]``-
#: Eintrag in ``third_party_licenses.toml`` gleichen, die Notices prüfen das.
LINUX_FAMILY_COMPONENTS: Final = {
    "libxcb": ("libxcb", "MIT", "https://gitlab.freedesktop.org/xorg/lib/libxcb"),
    "xcb-util": ("xcb-util", "MIT", "https://gitlab.freedesktop.org/xorg/lib/libxcb-util"),
    "xcb-util-image": (
        "xcb-util-image",
        "MIT",
        "https://gitlab.freedesktop.org/xorg/lib/libxcb-image",
    ),
    "xcb-util-keysyms": (
        "xcb-util-keysyms",
        "MIT",
        "https://gitlab.freedesktop.org/xorg/lib/libxcb-keysyms",
    ),
    "xcb-util-renderutil": (
        "xcb-util-renderutil",
        "MIT",
        "https://gitlab.freedesktop.org/xorg/lib/libxcb-render-util",
    ),
    "xcb-util-wm": ("xcb-util-wm", "MIT", "https://gitlab.freedesktop.org/xorg/lib/libxcb-wm"),
    "xcb-util-cursor": (
        "xcb-util-cursor",
        "MIT",
        "https://gitlab.freedesktop.org/xorg/lib/libxcb-cursor",
    ),
    "libxkbcommon": ("libxkbcommon", "MIT", "https://github.com/xkbcommon/libxkbcommon"),
    "krb5": ("MIT Kerberos", "MIT", "https://github.com/krb5/krb5"),
    "e2fsprogs": (
        "e2fsprogs com_err",
        "MIT",
        "https://git.kernel.org/pub/scm/fs/ext2/e2fsprogs.git",
    ),
    "keyutils": (
        "keyutils",
        "LGPL-2.1-or-later",
        "https://git.kernel.org/pub/scm/linux/kernel/git/dhowells/keyutils.git",
    ),
    "libx11": ("libX11", "MIT", "https://gitlab.freedesktop.org/xorg/lib/libx11"),
    "expat": ("Expat", "MIT", "https://github.com/libexpat/libexpat"),
    "fontconfig": (
        "fontconfig",
        "HPND",
        "https://gitlab.freedesktop.org/fontconfig/fontconfig",
    ),
    # FreeType ist FTL ODER GPL-2.0; die GPL scheidet nach Regel 15 aus, also
    # ist die Wahl vorgegeben. Dasselbe bei D-Bus (AFL-2.1 statt GPL-2.0+),
    # libcap (BSD-3 statt GPL-2.0) und Zstandard (BSD-3 statt GPL-2.0).
    "freetype": ("FreeType", "FTL", "https://gitlab.freedesktop.org/freetype/freetype"),
    "glib": ("GLib", "LGPL-2.1-or-later", "https://gitlab.gnome.org/GNOME/glib"),
    "pcre2": ("PCRE2", "BSD-3-Clause", "https://github.com/PCRE2Project/pcre2"),
    "dbus": ("D-Bus", "AFL-2.1", "https://gitlab.freedesktop.org/dbus/dbus"),
    "systemd": ("systemd", "LGPL-2.1-or-later", "https://github.com/systemd/systemd"),
    "libgcrypt": ("Libgcrypt", "LGPL-2.1-or-later", "https://gnupg.org/software/libgcrypt/"),
    "libgpg-error": (
        "libgpg-error",
        "LGPL-2.1-or-later",
        "https://gnupg.org/software/libgpg-error/",
    ),
    "libcap": (
        "libcap",
        "BSD-3-Clause",
        "https://git.kernel.org/pub/scm/libs/libcap/libcap.git",
    ),
    "lz4": ("LZ4", "BSD-2-Clause", "https://github.com/lz4/lz4"),
    "xz": ("XZ Utils", "0BSD", "https://github.com/tukaani-project/xz"),
    "zstd": ("Zstandard", "BSD-3-Clause", "https://github.com/facebook/zstd"),
    "brotli": ("Brotli", "MIT", "https://github.com/google/brotli"),
    "bzip2": ("bzip2", "bzip2-1.0.6", "https://sourceware.org/bzip2/"),
    "util-linux": (
        "util-linux",
        "LGPL-2.1-or-later",
        "https://github.com/util-linux/util-linux",
    ),
    "libuuid": ("libuuid", "BSD-3-Clause", "https://github.com/util-linux/util-linux"),
    "libselinux": (
        "libselinux",
        "LicenseRef-libselinux-public-domain",
        "https://github.com/SELinuxProject/selinux",
    ),
    "libpng": ("libpng", "libpng-2.0", "https://github.com/pnggroup/libpng"),
    "zlib": ("zlib", "Zlib", "https://github.com/madler/zlib"),
}

DistributionLookup = Callable[[str], metadata.Distribution]


@dataclass(frozen=True, slots=True)
class RuntimeGraph:
    """Aufgelöste Laufzeitpakete und ihre direkten Abhängigkeiten."""

    distributions: dict[str, metadata.Distribution]
    edges: dict[str, set[str]]


@dataclass(frozen=True, slots=True)
class NativeComponent:
    """Eine native Hauptbibliothek, die eine Python-Distribution mitbringt."""

    owner: str
    name: str
    slug: str
    licence: str
    website: str


@dataclass(frozen=True, slots=True)
class ArtifactFile:
    """Eine tatsächlich im fertigen Kundenartefakt liegende native Datei."""

    path: str
    owner: str
    version: str
    binary_version: str = "unbekannt"


NATIVE_COMPONENTS: Final = (
    NativeComponent(
        "pyside6-essentials",
        "Qt",
        "qt",
        "LGPL-3.0-only",
        "https://doc.qt.io/qt-6/licensing.html",
    ),
    NativeComponent(
        "cadquery-ocp-novtk",
        "Open CASCADE Technology",
        "opencascade-technology",
        "LGPL-2.1-only WITH OCCT-exception-1.0",
        "https://dev.opencascade.org/doc/overview/html/occt_public_license.html",
    ),
    NativeComponent(
        "shapely",
        "GEOS",
        "geos",
        "LGPL-2.1-or-later",
        "https://libgeos.org/",
    ),
    NativeComponent(
        "vtk",
        "VTK native libraries",
        "vtk-native",
        "BSD-3-Clause",
        "https://docs.vtk.org/en/latest/about.html",
    ),
    NativeComponent(
        "wgpu", "wgpu-native", "wgpu-native", "MIT", "https://github.com/gfx-rs/wgpu-native"
    ),
    NativeComponent(
        "freetype-py",
        "FreeType (freetype-py)",
        "freetype-py-native",
        "FTL",
        "https://freetype.org/",
    ),
    NativeComponent(
        "uharfbuzz",
        "HarfBuzz (uharfbuzz)",
        "uharfbuzz-native",
        "LicenseRef-HarfBuzz-Old-MIT",
        "https://github.com/harfbuzz/harfbuzz",
    ),
)

NATIVE_MAGIC: Final = {
    b"MZ\x90\x00",
    b"\x7fELF",
    b"\xfe\xed\xfa\xce",
    b"\xce\xfa\xed\xfe",
    b"\xfe\xed\xfa\xcf",
    b"\xcf\xfa\xed\xfe",
    b"\xca\xfe\xba\xbe",
    b"\xbe\xba\xfe\xca",
    b"\xca\xfe\xba\xbf",
    b"\xbf\xba\xfe\xca",
}


def _applies(
    requirement: Requirement,
    *,
    environment: Mapping[str, str],
    active_extras: Iterable[str],
) -> bool:
    """Ob eine Anforderung für Zielplattform und gewählte Extras gilt."""
    if requirement.marker is None:
        return True
    candidates = {"", *active_extras}
    return any(
        requirement.marker.evaluate({**environment, "extra": extra}) for extra in sorted(candidates)
    )


def runtime_graph(
    *,
    distribution: DistributionLookup = metadata.distribution,
    extras: Iterable[str] = RUNTIME_EXTRAS,
    environment: Mapping[str, str] | None = None,
) -> RuntimeGraph:
    """Löst die transitive Laufzeitmenge für genau eine Build-Umgebung auf.

    Fehlt ein Paket, wird nicht mit einer unvollständigen Stückliste
    weitergebaut. Die Meldung nennt den Weg zurück zur vollständigen Umgebung.
    """
    target = dict(cast(Mapping[str, str], default_environment()))
    if environment is not None:
        target.update(environment)
    root = canonicalize_name(DISTRIBUTION_NAME)
    requested_extras: dict[str, set[str]] = {root: set(extras)}
    requirements: dict[str, dict[str, Requirement]] = {root: {}}
    processed: dict[str, tuple[frozenset[str], frozenset[str]]] = {}
    found: dict[str, metadata.Distribution] = {}
    edges: dict[str, set[str]] = {}
    pending = [root]

    while pending:
        name = pending.pop(0)
        active = frozenset(requested_extras.get(name, set()))
        declared = frozenset(requirements.get(name, {}))
        state = (active, declared)
        if processed.get(name) == state:
            continue
        try:
            package = distribution(name)
        except (metadata.PackageNotFoundError, KeyError) as problem:
            raise RuntimeError(
                f"Laufzeitpaket {name!r} fehlt. Installieren Sie "
                '".[geom,ui,agent,brep]" gegen constraints.txt und erzeugen '
                "Sie die Stückliste erneut."
            ) from problem

        for requirement in requirements.get(name, {}).values():
            if requirement.specifier and not requirement.specifier.contains(
                package.version, prereleases=True
            ):
                raise RuntimeError(
                    f"Laufzeitpaket {name!r} ist als {package.version} installiert, "
                    f"erwartet wird {requirement.specifier}. Stellen Sie die Umgebung "
                    "mit constraints.txt wieder her und erzeugen Sie die Stückliste erneut."
                )

        processed[name] = state
        edges.setdefault(name, set())
        if name != root:
            found[name] = package

        for raw in package.requires or ():
            requirement = Requirement(raw)
            if not _applies(requirement, environment=target, active_extras=active):
                continue
            child = canonicalize_name(requirement.name)
            edges[name].add(child)
            before = frozenset(requested_extras.get(child, set()))
            requested_extras.setdefault(child, set()).update(requirement.extras)
            child_requirements = requirements.setdefault(child, {})
            requirement_key = str(requirement)
            new_requirement = requirement_key not in child_requirements
            child_requirements[requirement_key] = requirement
            after = frozenset(requested_extras[child])
            if child not in processed or before != after or new_requirement:
                pending.append(child)

    return RuntimeGraph(found, edges)


def distributions_for_analysis(
    entries: Iterable[tuple[object, ...]],
    *,
    package_map: Mapping[str, Iterable[str]] | None = None,
) -> set[str]:
    """Ordnet PyInstallers tatsächlich aufgenommene Einträge Distributionen zu.

    Der erste Teil eines PYMODULE-/BINARY-/DATA-Zielnamens ist der importierte
    Paketstamm. ``packages_distributions()`` ist dafür die installierte
    Rückwärtszuordnung; damit werden auch Fälle wie ``PIL`` → ``Pillow`` und
    ``OCP`` → ``cadquery-ocp-novtk`` richtig erfasst.
    """
    owners = package_map or metadata.packages_distributions()
    normalised = {name.casefold(): tuple(values) for name, values in owners.items()}
    found: set[str] = set()
    for entry in entries:
        if not entry:
            continue
        target = str(entry[0]).replace("\\", "/")
        root = target.split("/", 1)[0].split(".", 1)[0]
        for package in normalised.get(root.casefold(), ()):
            found.add(canonicalize_name(package))
    return found


def _artifact_relative(path: Path, root: Path) -> str:
    """Stabiler Vorwärtsschrägstrich-Pfad innerhalb des Kundenartefakts."""
    return path.relative_to(root).as_posix()


def _is_native_binary(path: Path) -> bool:
    """Erkennt PE, ELF und Mach-O am Inhalt statt an Plattform-Endungen."""
    try:
        with path.open("rb") as stream:
            magic = stream.read(4)
    except OSError:
        return False
    return magic[:2] == b"MZ" or magic in NATIVE_MAGIC


def _package_root(relative: str) -> str:
    """Importwurzel hinter PyInstallers plattformspezifischem Paketrahmen."""
    parts = relative.split("/")
    if parts and parts[0] == "_internal":
        parts = parts[1:]
    elif len(parts) >= 3 and tuple(parts[:2]) in {
        ("Contents", "Frameworks"),
        ("Contents", "MacOS"),
    }:
        parts = parts[2:]
    if not parts:
        return ""
    root = parts[0]
    if root.casefold().endswith(".libs"):
        root = root[:-5]
    return root.split(".", 1)[0]


def _runtime_owner(relative: str) -> str:
    """Besitzer für Laufzeitdateien außerhalb eines Importpakets."""
    name = Path(relative).name.casefold()
    if name.casefold() in {APP_NAME.casefold(), f"{APP_NAME.casefold()}.exe"}:
        return "pyinstaller-bootloader"
    # CPython auf Linux und macOS baut vierzig Module als eigene Dateien, die
    # Windows in die DLL einbaut — ``_bisect``, ``_json``, ``math`` …; die
    # Präfixliste unten kennt nur die Windows-Sorte. Der Ordner sagt es sicherer
    # als jeder Name.
    if "/lib-dynload/" in f"/{relative}":
        return "cpython"
    if "python.framework/" in relative.casefold():
        return "cpython"
    if any(
        part.casefold().startswith("qt") and part.casefold().endswith(".framework")
        for part in relative.split("/")
    ):
        return "pyside6-essentials"
    if name.startswith(
        ("python3", "libpython3", "_asyncio", "_bz2", "_ctypes", "_decimal", "_wmi")
    ):
        return "cpython"
    if name.startswith(
        (
            "_elementtree",
            "_hashlib",
            "_lzma",
            "_multiprocessing",
            "_overlapped",
            "_queue",
            "_socket",
            "_ssl",
            "_uuid",
            "pyexpat",
            "select.",
            "unicodedata",
        )
    ):
        return "cpython"
    if name.startswith(("libssl", "libcrypto")):
        return "openssl"
    if name.startswith("libffi"):
        return "libffi"
    if "openblas" in name:
        return "openblas"
    if name.startswith(("libgcc", "libgfortran", "libquadmath", "libstdc++")):
        return "gcc-runtime"
    if name.startswith(MSVC_RUNTIME_PREFIXES):
        return "msvc-runtime"
    for family, prefixes in LINUX_LIBRARY_FAMILIES:
        if name.startswith(prefixes):
            return family
    return "unassigned-native"


def _vendored_owner(relative: str, package_root: str) -> tuple[str, ...]:
    """Die Distribution hinter einem ``<name>.libs``-Ordner eines reparierten
    Wheels — ``pillow.libs`` gehört Pillow, obwohl kein Importpaket so heißt.

    ``auditwheel`` und ``delocate`` legen die mitgebrachten Bibliotheken neben
    das Importpaket, benannt nach der Distribution. Die Rückwärtszuordnung über
    Importnamen kennt diesen Ordner nicht: 18 Dateien ohne Besitzer im
    Linux-Paket, gemessen an der 0.2.1.
    """
    parts = relative.replace("\\", "/").split("/")
    if parts and parts[0] == "_internal":
        parts = parts[1:]
    elif len(parts) >= 3 and tuple(parts[:2]) in {
        ("Contents", "Frameworks"),
        ("Contents", "MacOS"),
    }:
        parts = parts[2:]
    if len(parts) < 2 or not parts[0].casefold().endswith(".libs"):
        return ()
    try:
        return (metadata.distribution(package_root).metadata["Name"],)
    except metadata.PackageNotFoundError:
        return ()


def _pe_file_version(path: Path) -> str:
    """Liest die feste vierteilige Dateiversion direkt aus einer PE-Datei."""
    try:
        import pefile  # type: ignore[import-untyped]
    except ImportError:
        return "unbekannt"

    image: Any = None
    try:
        image = pefile.PE(str(path), fast_load=True)
        image.parse_data_directories(
            directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_RESOURCE"]]
        )
        records = getattr(image, "VS_FIXEDFILEINFO", None) or ()
        if not records:
            return "unbekannt"
        record = records[0]
        parts = (
            int(record.FileVersionMS) >> 16,
            int(record.FileVersionMS) & 0xFFFF,
            int(record.FileVersionLS) >> 16,
            int(record.FileVersionLS) & 0xFFFF,
        )
        return ".".join(str(part) for part in parts)
    except OSError, ValueError, pefile.PEFormatError:
        return "unbekannt"
    finally:
        if image is not None:
            image.close()


def artifact_files(
    root: Path,
    *,
    package_map: Mapping[str, Iterable[str]] | None = None,
) -> list[ArtifactFile]:
    """Inventarisiert jede native Datei aus dem fertigen Paket.

    Der Eigentümer ist eine Python-Distribution, wo die Rückwärtszuordnung
    das belegt. Wurzeldateien gehören zu CPython, PyInstallers Bootloader oder
    einer namentlich erkannten nativen Laufzeitfamilie. Unbekanntes bleibt
    sichtbar und wird nicht unter einer geratenen Lizenz versteckt.
    """
    owners = package_map or metadata.packages_distributions()
    normalised = {name.casefold(): tuple(values) for name, values in owners.items()}
    found: list[ArtifactFile] = []
    for path in sorted(entry for entry in root.rglob("*") if entry.is_file()):
        # PyInstaller legt für den Lader Verweise auf die Bibliotheken der
        # Pakete an — 335 im Linux-Paket, die Qt-Frameworks auf macOS ebenso.
        # Ein Verweis ist keine zweite native Datei, und sein bloßer Name kennt
        # den Besitzer nicht, den das Ziel längst hat.
        if path.is_symlink():
            continue
        if not _is_native_binary(path):
            continue
        relative = _artifact_relative(path, root)
        package_root = _package_root(relative)
        distributions = normalised.get(package_root.casefold(), ()) or _vendored_owner(
            relative, package_root
        )
        owner: str
        if package_root.casefold() == "app":
            owner = str(canonicalize_name(DISTRIBUTION_NAME))
            version = APP_VERSION
        elif distributions:
            owner = str(canonicalize_name(min(distributions, key=str.casefold)))
            try:
                version = metadata.version(owner)
            except metadata.PackageNotFoundError:
                version = "unbekannt"
        else:
            owner = _runtime_owner(relative)
            version = "unbekannt"
        found.append(ArtifactFile(relative, owner, version, _pe_file_version(path)))
    return found


def _generic_purl(slug: str, version: str) -> str:
    return f"pkg:generic/{quote(slug, safe='.-_')}@{quote(version, safe='.-_+')}"


def _runtime_component(
    slug: str,
    name: str,
    version: str,
    licence: str,
    website: str,
    version_source: str,
) -> dict[str, Any]:
    """Eine Laufzeitfamilie außerhalb des Python-Distributionsgraphen."""
    reference = _generic_purl(slug, version)
    licence_entry: dict[str, object]
    if licence in NON_SPDX_LICENCES or "PyInstaller Bootloader Exception" in licence:
        licence_entry = {"license": {"name": licence}}
    else:
        licence_entry = {"expression": licence}
    return {
        "type": "library",
        "bom-ref": reference,
        "name": name,
        "version": version,
        "purl": reference,
        "licenses": [licence_entry],
        "externalReferences": [{"type": "website", "url": website}],
        "properties": [
            {"name": "solidon:version-source", "value": version_source},
            {
                "name": "solidon:licence-source",
                "value": "geprüfte Lizenzbeilage im Kundenartefakt",
            },
        ],
    }


def _openssl_version() -> str:
    match = re.search(r"\d+\.\d+\.\d+[a-z]*", ssl.OPENSSL_VERSION)
    return match.group(0) if match else ssl.OPENSSL_VERSION


def _openblas_version(owner: str) -> str:
    """Liest die im Wheel dokumentierte BLAS-Version, nicht den Dateinamen."""
    try:
        package = __import__(owner)
        config = package.__config__.CONFIG
        value = config["Build Dependencies"]["blas"]["version"]
        return str(value)
    except AttributeError, KeyError, TypeError:
        return "unbekannt"


def _libffi_version(
    *,
    target_platform: str | None = None,
    python_version: str | None = None,
) -> tuple[str, str]:
    """Belegt die Quellversion hinter einer gebündelten libffi-Binärdatei."""
    selected_platform = target_platform or sys.platform
    selected_python = python_version or platform.python_version()
    if selected_platform == "win32":
        version = WINDOWS_LIBFFI_VERSIONS.get(selected_python, "unbekannt")
        return version, f"CPython {selected_python} PCbuild/python.props"

    compiler_config = shutil.which("pkg-config")
    if compiler_config is None:
        return "unbekannt", "pkg-config für libffi fehlt"
    try:
        completed = subprocess.run(
            [compiler_config, "--modversion", "libffi"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5.0,
        )
    except OSError, subprocess.TimeoutExpired:
        return "unbekannt", "pkg-config für libffi war nicht ausführbar"
    version = completed.stdout.strip()
    if completed.returncode != 0 or not re.fullmatch(
        r"\d+(?:\.\d+){1,3}(?:[-+][0-9A-Za-z.-]+)?", version
    ):
        return "unbekannt", "pkg-config meldete keine exakte libffi-Version"
    return version, "pkg-config --modversion libffi"


def _msvc_runtime_version(entries: Iterable[ArtifactFile]) -> str:
    """Bindet die Laufzeitfamilie an alle tatsächlich mitgereisten PE-Versionen."""
    selected = tuple(
        entry
        for entry in entries
        if Path(entry.path).name.casefold().startswith(MSVC_RUNTIME_PREFIXES)
    )
    if not selected or any(entry.binary_version == "unbekannt" for entry in selected):
        return "unbekannt"
    return ",".join(sorted({entry.binary_version for entry in selected}))


def _dpkg_version(soname: str) -> tuple[str, str]:
    """Belegt die Quellversion einer gebündelten Systembibliothek über das
    Paket des Bauservers — ``dpkg-query -S`` nennt das Paket, ``-W`` seine
    Fassung, und vor dem ersten Bindestrich steht die des Projekts.

    Dasselbe Muster wie :func:`_libffi_version`: Die Fassung wandert mit dem
    Runner, also wird sie gelesen und nicht eingetragen. Ohne dpkg — Windows,
    macOS, ein fremdes Linux — bleibt sie ``unbekannt``, und die Releaseakte
    lässt das auf Linux nicht durch.
    """
    tool = shutil.which("dpkg-query")
    if tool is None:
        return "unbekannt", "dpkg-query fehlt"
    try:
        search = subprocess.run(
            [tool, "-S", soname], capture_output=True, text=True, check=False, timeout=30
        )
    except OSError, subprocess.SubprocessError:
        return "unbekannt", "dpkg-query -S war nicht ausführbar"
    package = ""
    for line in search.stdout.splitlines():
        owner, _, location = line.partition(": ")
        if Path(location.strip()).name == soname:
            package = owner.split(":", 1)[0].strip()
            break
    if not package:
        return "unbekannt", f"dpkg-query -S kennt {soname} nicht"
    try:
        shown = subprocess.run(
            [tool, "-W", "-f=${Version}", package],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except OSError, subprocess.SubprocessError:
        return "unbekannt", "dpkg-query -W war nicht ausführbar"
    full = shown.stdout.strip()
    if not full:
        return "unbekannt", f"dpkg-query -W meldete keine Fassung für {package}"
    upstream = full.split(":", 1)[-1].split("-", 1)[0]
    return upstream, f"dpkg-query -W {package} ({full})"


def runtime_components(
    files: Iterable[ArtifactFile], *, python_version: str | None = None
) -> list[dict[str, Any]]:
    """Logische Komponenten für die im Artefakt erkannten Laufzeitfamilien.

    ``python_version`` nennt die Laufzeit des Artefakts; ohne Angabe die des
    laufenden Interpreters.
    """
    entries = tuple(files)
    owners = {entry.owner for entry in entries}
    paths = {entry.path.casefold() for entry in entries}
    components: list[dict[str, Any]] = []

    if "cpython" in owners:
        components.append(
            _runtime_component(
                "cpython",
                "CPython runtime",
                python_version or platform.python_version(),
                "PSF-2.0",
                "https://www.python.org/psf/license/",
                "laufender Build-Interpreter",
            )
        )
    if "pyinstaller-bootloader" in owners:
        components.append(
            _runtime_component(
                "pyinstaller-bootloader",
                "PyInstaller bootloader",
                metadata.version("pyinstaller"),
                "GPL-2.0-or-later WITH PyInstaller Bootloader Exception",
                "https://pyinstaller.org/en/stable/license.html",
                "installierte Build-Distribution",
            )
        )
    if "openssl" in owners or any("/libssl" in f"/{path}" for path in paths):
        components.append(
            _runtime_component(
                "openssl",
                "OpenSSL",
                _openssl_version(),
                "Apache-2.0",
                "https://www.openssl.org/source/license.html",
                "ssl.OPENSSL_VERSION",
            )
        )
    if "libffi" in owners:
        version, version_source = _libffi_version(python_version=python_version)
        components.append(
            _runtime_component(
                "libffi",
                "libffi",
                version,
                "MIT",
                "https://github.com/libffi/libffi",
                version_source,
            )
        )
    for owner in ("numpy", "scipy"):
        if any(entry.owner == owner and "openblas" in entry.path.casefold() for entry in entries):
            components.append(
                _runtime_component(
                    f"openblas-{owner}",
                    f"OpenBLAS ({owner})",
                    _openblas_version(owner),
                    "BSD-3-Clause",
                    "https://www.openblas.net/",
                    f"{owner}.__config__",
                )
            )
    if "gcc-runtime" in owners or any(
        Path(path).name.startswith(("libgcc", "libgfortran", "libquadmath", "libstdc++"))
        for path in paths
    ):
        # **Die Fassung kommt aus dem Paket des Bauservers, nicht aus dem
        # Interpreter** (03.09.2026). `platform.python_compiler()` nennt den
        # Compiler, mit dem CPython gebaut wurde — nicht die Bibliothek, die
        # mitreist, und die Releaseakte verwirft eine solche Angabe seit
        # 05ca4bd7 ausdrücklich („Compilerangabe"). MSVC und libffi lesen
        # ihre Fassung längst aus der Datei beziehungsweise dem Paket; GCC
        # blieb als einzige Familie zurück und ließ den Linux-Paketjob
        # scheitern. Derselbe Weg wie bei den übrigen Linux-Familien darunter:
        # `dpkg-query` sagt, aus welchem Paket die Datei stammt und in welcher
        # Fassung. Wo es kein dpkg gibt — macOS —, bleibt es bei der alten
        # Angabe; dort greift die Prüfung nicht.
        gcc_files = [
            entry for entry in entries if Path(entry.path).name.startswith(("libgcc", "libstdc++"))
        ]
        if gcc_files and shutil.which("dpkg-query") is not None:
            gcc_version, gcc_source = _dpkg_version(Path(gcc_files[0].path).name)
        else:
            gcc_version = platform.python_compiler()
            gcc_source = "Compilerangabe des Zielinterpreters"
        components.append(
            _runtime_component(
                "gcc-runtime",
                "GCC Runtime Libraries",
                gcc_version,
                "GPL-3.0-or-later WITH GCC-exception-3.1",
                "https://gcc.gnu.org/onlinedocs/libstdc++/manual/license.html",
                gcc_source,
            )
        )
    if "msvc-runtime" in owners or any(
        Path(path).name.startswith(("msvcp", "vcruntime", "ucrtbase")) for path in paths
    ):
        components.append(
            _runtime_component(
                "microsoft-visual-cpp-runtime",
                "Microsoft Visual C++ Runtime",
                _msvc_runtime_version(entries),
                "Microsoft Visual Studio Runtime license",
                "https://visualstudio.microsoft.com/license-terms/",
                "PE FileVersion der gebündelten Laufzeitdateien",
            )
        )
    for family, _prefixes in LINUX_LIBRARY_FAMILIES:
        members = [entry for entry in entries if entry.owner == family]
        if not members:
            continue
        name, licence, website = LINUX_FAMILY_COMPONENTS[family]
        version, version_source = _dpkg_version(Path(members[0].path).name)
        components.append(
            _runtime_component(family, name, version, licence, website, version_source)
        )
    return components


def artifact_root(
    dist: Path,
    *,
    platform: str = sys.platform,
    app_name: str = APP_NAME,
) -> Path:
    """Das echte Kundenartefakt, ohne macOS-COLLECT-Zwischenordner."""
    return dist / (f"{app_name}.app" if platform == "darwin" else app_name)


def locate_artifact_sbom(
    dist: Path,
    *,
    platform: str = sys.platform,
    app_name: str = APP_NAME,
) -> Path:
    """Findet genau eine Stückliste im Zielartefakt der aktuellen Plattform."""
    root = artifact_root(dist, platform=platform, app_name=app_name)
    files = sorted(root.rglob("Solidon3D.cdx.json")) if root.is_dir() else []
    if len(files) != 1:
        raise RuntimeError(
            f"Im Kundenartefakt {root} wurde {len(files)}-mal "
            "Solidon3D.cdx.json gefunden; erwartet ist genau eine Datei. "
            "Bauen Sie das Zielpaket neu und prüfen Sie die PyInstaller-Datenliste."
        )
    return files[0]


def _visible_dependencies(
    graph: RuntimeGraph,
    source: str,
    included: set[str],
) -> set[str]:
    """Überbrückt nicht paketierte Zwischenknoten im deklarierten Graphen."""
    visible: set[str] = set()
    pending = list(graph.edges.get(source, set()))
    seen: set[str] = set()
    while pending:
        child = pending.pop()
        if child in seen:
            continue
        seen.add(child)
        if child in included:
            visible.add(child)
        else:
            pending.extend(graph.edges.get(child, set()))
    return visible


def _native_version(component: NativeComponent, package: metadata.Distribution) -> str:
    """Nutzt die native Version, soweit sie ohne Dateiraten feststellbar ist."""
    if component.slug == "wgpu-native":
        # Den registrierenden Backend-Import vermeiden: seine feste Zielversion
        # steht als Literal im installierten Wrapper, kein Grafikadapter wird angefragt.
        source = Path(package.locate_file("wgpu/backends/wgpu_native/__init__.py"))
        try:
            match = re.search(
                r'^__version__ = "([0-9.]+)"$', source.read_text(encoding="utf-8"), re.MULTILINE
            )
        except OSError:
            return "unbekannt"
        return match.group(1) if match else "unbekannt"
    if component.slug == "freetype-py-native":
        import freetype

        return ".".join(str(part) for part in freetype.version())
    if component.slug == "uharfbuzz-native":
        import uharfbuzz

        return str(uharfbuzz.version_string())
    if component.slug == "geos":
        try:
            import shapely

            return str(shapely.geos_version_string)
        except AttributeError, ImportError:
            return package.version
    if component.slug == "opencascade-technology":
        match = re.match(r"\d+\.\d+\.\d+", package.version)
        if match:
            return match.group(0)
    return package.version


def _purl(name: str, version: str) -> str:
    package = quote(canonicalize_name(name), safe=".-_")
    release = quote(version, safe=".-_+")
    return f"pkg:pypi/{package}@{release}"


def _licence(package: metadata.Distribution) -> list[dict[str, object]]:
    """Die geprüfte Rechtsgrundlage, erst danach rohe Paketmetadaten."""
    name = str(package.metadata.get("Name", ""))
    known = {canonicalize_name(key): value for key, value in licences.load_policy().known.items()}
    selected = known.get(canonicalize_name(name), {}).get("licence")
    if selected:
        text = str(selected)
        if text in NON_SPDX_LICENCES:
            return [{"license": {"name": text}}]
        return [{"expression": SPDX_ALIASES.get(text, text)}]

    expression = package.metadata.get("License-Expression")
    if expression:
        return [{"expression": str(expression)}]

    text = licences.declared_licence(package)
    if not text:
        text = known.get(canonicalize_name(name), {}).get("licence", "NOASSERTION")
    return [{"license": {"name": text}}]


def _native_component(
    definition: NativeComponent,
    owner: metadata.Distribution,
) -> dict[str, Any]:
    """Maschinenlesbarer Eintrag für eine mitgebrachte native Hauptbibliothek."""
    version = _native_version(definition, owner)
    reference = f"pkg:generic/{quote(definition.slug, safe='.-_')}@{quote(version, safe='.-_+')}"
    return {
        "type": "library",
        "bom-ref": reference,
        "name": definition.name,
        "version": version,
        "purl": reference,
        "licenses": [{"expression": definition.licence}],
        "externalReferences": [{"type": "website", "url": definition.website}],
        "properties": [
            {
                "name": "solidon:bundled-by",
                "value": str(owner.metadata.get("Name", definition.owner)),
            },
            {
                "name": "solidon:version-source",
                "value": ("native runtime" if definition.slug == "geos" else "owning distribution"),
            },
            {
                "name": "solidon:licence-source",
                "value": "app/core/knowledge/data/licences.toml and upstream project",
            },
        ],
    }


def _artifact_file_component(entry: ArtifactFile) -> dict[str, Any]:
    """Dateiebene für das lückenlose native Inventar des Zielpakets."""
    reference = f"urn:solidon:native-file:{quote(entry.path, safe='.-_/')}"
    return {
        "type": "file",
        "bom-ref": reference,
        "name": entry.path,
        "version": entry.version,
        "properties": [
            {"name": "solidon:artifact-path", "value": entry.path},
            {"name": "solidon:bundled-by", "value": entry.owner},
            {
                "name": "solidon:licence-source",
                "value": "Lizenzbeilage der Besitzerkomponente; unbekannt bleibt offen",
            },
        ],
    }


def build_bom(
    *,
    distribution: DistributionLookup = metadata.distribution,
    extras: Iterable[str] = RUNTIME_EXTRAS,
    environment: Mapping[str, str] | None = None,
    version: str = APP_VERSION,
    platform: str | None = None,
    included_distributions: Iterable[str] | None = None,
    customer_artifact: Path | None = None,
    python_version: str | None = None,
) -> dict[str, Any]:
    """Baut eine deterministische CycloneDX-1.6-Stückliste.

    ``python_version`` ist die Laufzeit des Artefakts — ohne Angabe die des
    laufenden Interpreters. Ein Test auf einer Entwicklermaschine mit 3.14
    beschreibt damit trotzdem das Paket, das die CI mit 3.13 baut.
    """
    selected_extras = tuple(extras)
    graph = runtime_graph(
        distribution=distribution,
        extras=selected_extras,
        environment=environment,
    )
    target = platform or sysconfig.get_platform()
    python_version = python_version or (
        f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    )
    product_ref = _purl(DISTRIBUTION_NAME, version)
    included: set[str]
    if included_distributions is None:
        included = set(graph.distributions)
    else:
        included = {
            str(canonicalize_name(name))
            for name in included_distributions
            if canonicalize_name(name) in graph.distributions
        }
    refs = {
        name: _purl(str(package.metadata.get("Name", name)), package.version)
        for name, package in graph.distributions.items()
        if name in included
    }

    components = []
    for name in sorted(included):
        package = graph.distributions[name]
        shown = str(package.metadata.get("Name", name))
        reference = refs[name]
        components.append(
            {
                "type": "library",
                "bom-ref": reference,
                "name": shown,
                "version": package.version,
                "purl": reference,
                "licenses": _licence(package),
            }
        )

    native_refs: dict[str, str] = {}
    for definition in NATIVE_COMPONENTS:
        if definition.owner not in included:
            continue
        native = _native_component(definition, graph.distributions[definition.owner])
        components.append(native)
        native_refs[definition.owner] = str(native["bom-ref"])

    packaged_files = artifact_files(customer_artifact) if customer_artifact is not None else []
    file_refs: dict[str, list[str]] = {}
    for entry in packaged_files:
        component = _artifact_file_component(entry)
        components.append(component)
        file_refs.setdefault(entry.owner, []).append(str(component["bom-ref"]))

    packaged_runtime = runtime_components(packaged_files, python_version=python_version)
    components.extend(packaged_runtime)
    runtime_refs = {str(component["bom-ref"]) for component in packaged_runtime}
    components.sort(key=lambda component: (str(component["name"]).casefold(), component["version"]))

    root = canonicalize_name(DISTRIBUTION_NAME)
    dependencies = [
        {
            "ref": product_ref,
            "dependsOn": sorted(
                [
                    *(refs[name] for name in _visible_dependencies(graph, root, included)),
                    *runtime_refs,
                    *(
                        reference
                        for owner, references in file_refs.items()
                        if owner not in refs
                        for reference in references
                    ),
                ]
            ),
        }
    ]
    dependencies.extend(
        {
            "ref": refs[name],
            "dependsOn": sorted(
                [
                    *(refs[child] for child in _visible_dependencies(graph, name, included)),
                    *([native_refs[name]] if name in native_refs else []),
                    *file_refs.get(name, []),
                ]
            ),
        }
        for name in sorted(included)
    )
    dependencies.extend(
        {"ref": reference, "dependsOn": []} for reference in sorted(native_refs.values())
    )
    dependencies.extend({"ref": reference, "dependsOn": []} for reference in sorted(runtime_refs))
    dependencies.extend(
        {"ref": reference, "dependsOn": []}
        for reference in sorted(
            reference for references in file_refs.values() for reference in references
        )
    )

    boundary = (
        "Declared Python runtime dependency closure with bundled native components"
        if included_distributions is None
        else "PyInstaller-analyzed customer artifact with bundled native components and files"
    )

    return {
        "$schema": "https://cyclonedx.org/schema/bom-1.6.schema.json",
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "version": 1,
        "metadata": {
            "component": {
                "type": "application",
                "bom-ref": product_ref,
                "name": APP_NAME,
                "version": version,
                "supplier": {"name": "RS Digital"},
                "purl": product_ref,
            },
            "properties": [
                {"name": "solidon:target-platform", "value": target},
                {
                    "name": "solidon:python-version",
                    "value": python_version,
                },
                {
                    "name": "solidon:runtime-extras",
                    "value": ",".join(sorted(selected_extras)),
                },
                {
                    "name": "solidon:component-boundary",
                    "value": boundary,
                },
            ],
        },
        "components": components,
        "dependencies": dependencies,
    }


def render_bom(bom: Mapping[str, Any]) -> str:
    """Stabile Bytes: keine Uhrzeit, keine Zufallskennung, feste Sortierung."""
    return json.dumps(bom, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def write_bom(
    output: Path = OUTPUT,
    *,
    included_distributions: Iterable[str] | None = None,
    customer_artifact: Path | None = None,
) -> dict[str, Any]:
    """Erzeugt und schreibt die Stückliste; Rückgabe dient dem Bauprotokoll."""
    bom = build_bom(
        included_distributions=included_distributions,
        customer_artifact=customer_artifact,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_bom(bom), encoding="utf-8")
    return bom


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT, help="Zieldatei")
    parser.add_argument(
        "--check",
        action="store_true",
        help="nur prüfen, ob die Zieldatei zur aktuellen Build-Umgebung passt",
    )
    parser.add_argument(
        "--locate-artifact",
        type=Path,
        metavar="DIST",
        help="genau eine Stückliste im echten Kundenartefakt finden",
    )
    arguments = parser.parse_args()

    if arguments.locate_artifact is not None:
        try:
            print(locate_artifact_sbom(arguments.locate_artifact))
        except RuntimeError as problem:
            print(problem, file=sys.stderr)
            return 2
        return 0

    try:
        bom = build_bom()
        rendered = render_bom(bom)
    except RuntimeError as problem:
        print(problem, file=sys.stderr)
        return 2

    if arguments.check:
        try:
            current = arguments.output.read_text(encoding="utf-8")
        except OSError:
            current = ""
        if current != rendered:
            print(
                f"{arguments.output} passt nicht zur Laufzeitumgebung. "
                "Erzeugen Sie die Datei ohne --check neu.",
                file=sys.stderr,
            )
            return 1
        print(f"{arguments.output} passt zur Laufzeitumgebung.")
        return 0

    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(rendered, encoding="utf-8")
    count = len(bom["components"])
    print(f"{arguments.output} geschrieben: {count} Laufzeitpakete für {sysconfig.get_platform()}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
