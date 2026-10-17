"""Für welche Plattform es neuere Versionen gibt, welches Paket sie meint und ob es hier startet.

Eigene Datei, weil ``test_updates.py`` an der Sperrklinke steht (Konzept Codestruktur 3.4).
Verstellt wird nie ``sys.platform`` des Prozesses (RM-531), sondern ``updates.sys`` allein,
``updates.platform_key`` oder die Systemversion.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.core import install, updates
from tests.release_signing import accept_test_signatures, signed

__all__ = ["accept_test_signatures"]  # die Fixture wirkt durch den Import, nicht durch Aufruf


def test_only_a_mac_with_an_intel_processor_gets_no_newer_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """0.6.1 ist auf dem Intel-Mac die letzte Version und läuft dort als Demo bis zum 30.11.
    (Entscheidungen Robert, 17.10.2026): Ein Hinweis dort sagte eine Version an, die auf dem
    Gerät nicht startet. Jede andere Plattform fragt weiter — gefragt wird am Schlüssel und,
    ohne ihn, an diesem Rechner."""
    assert not updates.newer_versions_run_here(updates.PLATFORM_MACOS_INTEL)
    for key in (updates.PLATFORM_WINDOWS, updates.PLATFORM_LINUX, updates.PLATFORM_MACOS_ARM):
        assert updates.newer_versions_run_here(key), key

    monkeypatch.setattr(updates, "platform_key", lambda: updates.PLATFORM_MACOS_INTEL)
    assert not updates.newer_versions_run_here()
    monkeypatch.setattr(updates, "platform_key", lambda: updates.PLATFORM_MACOS_ARM)
    assert updates.newer_versions_run_here()


@pytest.mark.parametrize(("apple_chip", "key"), [(True, "macos-arm64"), (False, "macos-x86_64")])
def test_a_mac_is_named_by_its_chip_also_under_rosetta(
    monkeypatch: pytest.MonkeyPatch, apple_chip: bool, key: str
) -> None:
    """Unter Rosetta sagt ``platform.machine()`` „x86_64“: Ein Mac mit Apple-Chip, der das
    Intel-Paket trägt, hieße sonst Intel-Mac — fragte nie mehr nach und bekäme nie das Paket,
    das für ihn gebaut ist (Review L1). Gefragt wird ``machine.is_apple_silicon``."""
    monkeypatch.setattr(updates, "sys", SimpleNamespace(platform="darwin"))
    monkeypatch.setattr(updates.machine, "is_apple_silicon", lambda: apple_chip)

    assert updates.platform_key() == key


@pytest.mark.parametrize(
    ("system", "chip", "translated", "answer", "apple_chip"),
    [
        ("darwin", "arm64", 0, -1, True),
        ("darwin", "x86_64", 1, 0, True),
        ("darwin", "x86_64", 0, 0, False),
        ("darwin", "x86_64", 1, -1, False),
        ("darwin", "x86_64", 1, None, False),
        ("win32", "arm64", 1, 0, False),
    ],
)
def test_rosetta_is_told_apart_by_asking_the_system(
    monkeypatch: pytest.MonkeyPatch,
    system: str,
    chip: str,
    translated: int,
    answer: int | None,
    apple_chip: bool,
) -> None:
    """``machine.is_apple_silicon`` fragt unter ``x86_64`` ``sysctl.proc_translated``: 1 heißt
    Rosetta auf einem Apple-Chip, 0 oder ein Fehler ein Intel-Mac, der den Schlüssel nicht
    kennt; ohne ladbare Systembibliothek (``None``) gilt Intel (Nachprüfung L-5). Gefragt
    wird über Attrappen von ``platform`` und ``ctypes`` im Modul, nie über den Prozess."""
    import ctypes

    from app.core.backends import machine

    asked: list[bytes] = []

    def sysctlbyname(name: bytes, value: Any, _size: Any, _new: None, _new_size: int) -> int:
        asked.append(name)
        value._obj.value = translated
        assert answer is not None
        return answer

    def library(_name: None) -> SimpleNamespace:
        if answer is None:
            raise OSError("keine Systembibliothek")
        return SimpleNamespace(sysctlbyname=sysctlbyname)

    monkeypatch.setattr(machine, "sys", SimpleNamespace(platform=system))
    monkeypatch.setattr(machine, "platform", SimpleNamespace(machine=lambda: chip))
    monkeypatch.setattr(
        machine,
        "ctypes",
        SimpleNamespace(
            CDLL=library,
            c_int=ctypes.c_int,
            c_size_t=ctypes.c_size_t,
            sizeof=ctypes.sizeof,
            byref=ctypes.byref,
        ),
    )

    assert machine.is_apple_silicon() is apple_chip
    asks = system == "darwin" and chip == "x86_64" and answer is not None
    assert asked == ([b"sysctl.proc_translated"] if asks else [])


@pytest.mark.parametrize(
    ("minimum", "found", "missing"),
    [
        ("15.0", (14, 6, 1), "Windows 15.0"),
        ("15.0", (15, 0), ""),
        ("15.0", (15,), ""),
        ("15", (15, 0, 0), ""),
        ("15.0", (26, 0, 1), ""),
        ("10.0.19045", (10, 0, 17763), "Windows 10.0.19045"),
        ("10.0.19045", (10, 0, 22631), ""),
        ("", (10, 0, 17763), ""),
        ("15.0", (), ""),
    ],
)
def test_a_package_names_the_system_it_needs(
    minimum: str, found: tuple[int, ...], missing: str
) -> None:
    """``Package.minimum_system`` aus der Versionsdatei gegen die Version des Rechners: Fehlt
    sie, nennt ``needs_newer_system`` das System; ohne Grenze oder ohne lesbare Version nichts.
    Eine kürzere Folge zählt mit Nullen aufgefüllt — sonst läge „15“ vor „15.0“ (Review L1)."""
    package = updates.Package(file="x", url="https://solidon3d.de/x", minimum_system=minimum)
    release = updates.Release(version="99.0.0", packages={updates.PLATFORM_WINDOWS: package})

    assert release.needs_newer_system(updates.PLATFORM_WINDOWS, found) == missing
    assert release.needs_newer_system(updates.PLATFORM_LINUX, found) == "", "ohne Paket"


@pytest.mark.parametrize(
    ("text", "parts"),
    [
        ("15.0", (15, 0)),
        ("10.0.19045", (10, 0, 19045)),
        (" 14.6.1 ", (14, 6, 1)),
        ("", ()),
        ("15.a", ()),
        ("15.", ()),
        ("1" * 12, ()),
        ("1.2.3.4.5", ()),
        ("١٥.٠", ()),
        ("15².0", ()),
    ],
)
def test_only_a_version_number_counts_as_a_minimum(text: str, parts: tuple[int, ...]) -> None:
    """Was aus der Versionsdatei kommt, ist fremde Eingabe: nur ASCII-Ziffern und Punkte.
    ``str.isdigit`` nähme arabische Ziffern und „²“ an — an „²“ scheitert ``int``."""
    assert updates._as_version_parts(text) == parts


def _version_file(minimum: str, name: str) -> dict[str, object]:
    """Eine Versionsdatei mit Windows-Setup und Mindestsystem, wie ``make_download`` sie
    ab 0.6.2 schreibt (RM-815)."""
    return {
        "version": "99.0.0",
        "packages": {
            updates.PLATFORM_WINDOWS: {
                "file": "Solidon3D-99.0.0-windows-setup.exe",
                "url": "https://solidon3d.de/dl/Solidon3D-99.0.0-windows-setup.exe",
                "size": 4,
                "sha256": "a" * 64,
                "minimum_system": minimum,
                "minimum_system_name": name,
            }
        },
    }


@pytest.mark.parametrize(
    ("minimum", "name", "said"),
    [
        ("10.0.19045", "Windows 10 22H2", "Windows 10 22H2"),
        ("10.0.19045", "", "Windows 10.0.19045"),
        ("10.0.19045", "<b>Windows</b>", "Windows 10.0.19045"),
        ("10.0.19045", "W" * 41, "Windows 10.0.19045"),
        ("10.0.19045; rm", "Windows 10 22H2", ""),
        ("١٠.٠", "Windows 10 22H2", ""),
    ],
)
def test_the_version_file_carries_the_minimum_and_its_name(
    monkeypatch: pytest.MonkeyPatch, minimum: str, name: str, said: str
) -> None:
    """Über den echten Leseweg (``updates.check`` mit unterschriebener Antwort, Review L1):
    Grenze und Name kommen aus der Versionsdatei, und was dort keine Versionsnummer oder kein
    schlichter Name ist, gilt nicht — der Name fällt auf System und Zahl zurück, eine
    unlesbare Grenze auf keine. Das gilt auch, wo sich das Paket nicht von innen einspielen
    lässt (``startable`` leer): Dort führt der Hinweis zur Download-Seite, und deren Paket
    startete ebenso wenig (Nachprüfung L-6)."""
    monkeypatch.setattr(install, "packaged", lambda: True)
    payload = signed(_version_file(minimum, name))

    for kind, replaceable in ((updates.KIND_WINDOWS_SETUP, True), (updates.KIND_SOURCE, False)):
        monkeypatch.setattr(updates, "install_kind", lambda kind=kind: kind)

        release = updates.check(fetch=lambda _url, _headers, _payload: payload)

        assert release is not None, "die unterschriebene Antwort wird gelesen"
        assert (release.startable(updates.PLATFORM_WINDOWS) is not None) is replaceable, kind
        assert release.needs_newer_system(updates.PLATFORM_WINDOWS, (10, 0, 17763)) == said
        assert release.needs_newer_system(updates.PLATFORM_WINDOWS, (10, 0, 26100)) == ""


def test_the_system_version_comes_from_the_platform(monkeypatch: pytest.MonkeyPatch) -> None:
    """macOS über ``mac_ver``, Windows über ``version`` samt Build, Linux ohne Grenze."""
    monkeypatch.setattr(updates.platform, "mac_ver", lambda: ("14.6.1", ("", "", ""), ""))
    monkeypatch.setattr(updates.platform, "version", lambda: "10.0.19045")

    assert updates.system_version("darwin") == (14, 6, 1)
    assert updates.system_version("win32") == (10, 0, 19045)
    assert updates.system_version("linux") == ()
