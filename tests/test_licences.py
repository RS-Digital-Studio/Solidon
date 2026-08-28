"""Abhängigkeiten gegen die Freigabeliste (Bauplan §36, AGENTS.md Regel 22)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.branding import DISTRIBUTION_NAME
from app.core.knowledge import licences

NOTICE_FILE = Path(__file__).parent.parent / "THIRD-PARTY-NOTICES.md"


def test_no_dependency_violates_the_policy() -> None:
    violations = licences.check()
    assert not violations, "licence violations:\n" + "\n".join(str(entry) for entry in violations)


def test_the_runtime_tree_is_actually_walked() -> None:
    packages = {name.lower() for name in licences.runtime_packages()}
    for expected in ("trimesh", "manifold3d", "numpy", "scipy", "pyside6", "pyvista"):
        assert expected in packages, f"{expected} is missing from the checked tree"


def test_gpl_is_refused_and_lgpl_is_not() -> None:
    policy = licences.load_policy()
    assert any("GPL-3" in entry for entry in policy.forbidden)
    assert "LGPL" in policy.allowed, "PySide6 is LGPL and is allowed when linked dynamically"


def test_the_banned_packages_are_not_installed() -> None:
    installed = {licences.normalise(name) for name in licences.runtime_packages()}
    for banned in licences.load_policy().banned_packages:
        assert licences.normalise(banned) not in installed, f"{banned} must not be installed"


def test_a_gpl_package_would_be_caught() -> None:
    """Ein Wächter für die Prüfung selbst — sonst bewiese ein grüner Lauf
    nichts.
    """
    policy = licences.load_policy()
    text = "GPL-3.0-or-later".lower()
    assert any(entry.lower() in text for entry in policy.forbidden)
    assert "lgpl" not in text


def test_notices_list_every_package() -> None:
    text = licences.notices()
    assert text.startswith("| Paket | Lizenz |")
    for name in licences.runtime_packages():
        assert name in text


def test_the_notice_file_names_every_runtime_package() -> None:
    """Die eingecheckte Datei, nicht die erzeugte Liste (§36).

    ``notices()`` gegen sich selbst zu prüfen beweist nichts: die Liste ist
    per Bauart vollständig. Was mit dem Paket ausgeliefert wird, ist
    ``THIRD-PARTY-NOTICES.md`` — sie steht in ``packaging/solidon3d.spec`` und
    ist der Hinweis, den BSD und MIT bei einer Binärverteilung verlangen. Sie
    war elf Pakete hinterher, weil niemand sie mit dem Baum verglichen hat.

    Geprüft wird nur der **Name**. Die Lizenzangabe eines Pakets ändert
    zwischen zwei Versionen schon mal ihre Schreibweise („BSD License" gegen
    „BSD-3-Clause"), und daran soll kein Lauf scheitern — ein fehlendes Paket
    ist der Fehler, den es zu fangen gilt.
    """
    text = NOTICE_FILE.read_text(encoding="utf-8")
    missing = sorted(name for name in licences.runtime_packages() if name not in text)
    assert not missing, (
        "THIRD-PARTY-NOTICES.md nennt diese Laufzeitpakete nicht:\n"
        + "\n".join(missing)
        + "\n\nNeu erzeugen: python -m app.core.knowledge.licences"
    )


def test_the_notice_file_names_every_platform_package() -> None:
    """Auch die Pakete der **anderen** Plattformen (§36).

    Der Test darüber prüft, was hier installiert ist. Genau das ist seine
    Lücke: ``PLATFORM_PACKAGES`` sind die Pakete, die je nach Betriebssystem
    dazukommen, und ``runtime_packages()`` sieht auf dieser Maschine nur die
    eigenen. Gemessen auf Windows ist von den sechs Einträgen genau einer
    dabei — ``pywin32-ctypes``; die fünf für Linux fehlen dem Baum. Ein
    verschwundenes ``SecretStorage`` bliebe damit unbemerkt, und die
    Hinweisdatei reist trotzdem zu einem Linux-Kunden.

    Deshalb hier gegen die Tabelle statt gegen die Umgebung. Geprüft wird der
    **Name**, aus demselben Grund wie oben: An einer geänderten Schreibweise
    der Lizenz soll kein Lauf scheitern.
    """
    text = NOTICE_FILE.read_text(encoding="utf-8")
    missing = sorted(name for name in licences.PLATFORM_PACKAGES if name not in text)
    assert not missing, (
        "THIRD-PARTY-NOTICES.md nennt diese Plattformpakete nicht:\n"
        + "\n".join(missing)
        + "\n\nNeu erzeugen: python -m app.core.knowledge.licences"
    )


@pytest.mark.parametrize("package", ["pymeshlab", "PyQt5", "PyQt6"])
def test_the_plan_names_these_as_forbidden(package: str) -> None:
    assert package in licences.load_policy().banned_packages


def test_every_package_solidon_installs_elsewhere_is_on_record() -> None:
    """**Was Solidon in eine fremde Umgebung installiert, gehört in die Akten.**

    Die Einrichtung von Weg 3 zieht Pakete in ComfyUIs eigenes Python nach.
    Sie sind keine Abhängigkeit dieser Anwendung — nichts davon wird hier
    importiert, und :func:`licences.check` sieht sie nicht —, aber Solidon legt
    sie auf den Rechner eines Kunden.

    Der Kommentar an ``comfy_setup.PACKAGES`` behauptete, alle Lizenzen seien
    geprüft, und genau so eine Behauptung war der GPL-Knoten ``RMBG``: wahr
    gemeint, von keinem Test gehalten, und im Ablauf stand er trotzdem. Diese
    Prüfung ist der Unterschied zwischen einer Behauptung und einer Aktenlage.

    Geprüft wird die Vollständigkeit und nicht die Lizenz selbst: Welche Lizenz
    ein fremdes Paket führt, kann diese Suite nicht nachsehen — es ist hier
    nicht installiert. Dass jedes davon **benannt** ist, kann sie.
    """
    from app.core.backends import comfy_setup

    text = licences._DATA_FILE.read_text(encoding="utf-8")
    for entry in comfy_setup.PACKAGES:
        name = entry.split("==")[0]
        assert name in text, (
            f"{name} is in comfy_setup.PACKAGES but not in {licences._DATA_FILE.name} "
            "- rule 22 wants the record first"
        )


def test_the_shipped_workflows_name_no_gpl_node() -> None:
    """**Regel 15 hing an einer Datendatei, und keine Prüfung sah dorthin.**

    Beide mitgelieferten ComfyUI-Abläufe sprachen ``RMBG`` an — den Knoten aus
    ``ComfyUI-RMBG``, GPL-3.0. Damit verlangte Solidon vom Kunden eine
    GPL-Installation, damit Weg 3 läuft, und ``licences.check()`` konnte es
    nicht sehen: Es liest die eigene Laufzeit, und ein ComfyUI-Knoten steht
    dort nicht.

    Geprüft werden deshalb die Namen in den Ablaufdateien. Die Liste ist bewusst
    kurz und nennt, was bekannt ist — sie ersetzt keine Lizenzrecherche für
    einen neuen Knoten, aber sie fängt die Rückkehr eines bekannten.
    """
    import json

    from app.core.backends import mesh

    #: Knotensammlungen, deren Lizenz Regel 15 ausschließt.
    refused = {"RMBG": "ComfyUI-RMBG is GPL-3.0"}

    for name in ("image_to_mesh", "text_to_mesh"):
        graph = json.loads((mesh.WORKFLOW_DIR / f"{name}.json").read_text(encoding="utf-8"))
        kinds = {str(entry.get("class_type")) for entry in graph.values()}
        for kind, why in refused.items():
            assert kind not in kinds, f"{name}.json uses {kind} - {why}"


def test_the_notices_survive_a_build_without_own_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Im gebauten Paket ist Solidon keine installierte Distribution.

    ``runtime_packages`` fragt ``importlib.metadata`` nach der **eigenen**
    Distribution, und die gibt es in keinem PyInstaller-Bau — die Ausnahme riss
    durch ``notices()`` bis in den Über-Dialog, der stattdessen einen
    Ersatzsatz zeigte. Damit stand die Liste der Fremdbestandteile in der
    Entwicklung **immer** und im ausgelieferten Paket **nie** da; PySide6 steht
    unter LGPL, und §36 verlangt sie.

    Geprüft wird die Bedingung, die im Bau herrscht: nur die eigenen Metadaten
    fehlen, alles andere ist da.
    """
    echt = licences.metadata.distribution

    def ohne_eigene(name: str) -> object:
        if licences.normalise(name) == licences.normalise(DISTRIBUTION_NAME):
            raise licences.metadata.PackageNotFoundError(name)
        return echt(name)

    monkeypatch.setattr(licences.metadata, "distribution", ohne_eigene)
    text = licences.notices()

    assert "PySide6" in text, "die LGPL-Zusage fehlt im Paket"
    assert text.startswith("| Paket | Lizenz |"), text[:60]
    assert all(line.startswith("|") for line in text.splitlines()), (
        "die Erklärung aus dem Kopf der Beilage gehört nicht in den Dialog"
    )


def test_the_notice_file_travels_where_the_fallback_looks_for_it() -> None:
    """Und sie liegt da, wo der Rückfall sie sucht — in beiden Lagen.

    ``NOTICE_FILE`` rechnet vom Modul aus nach oben. In der Entwicklung ist
    das der Projektstamm, im Bau ``<_MEIPASS>``, wohin die Spec sie legt
    (Ziel ``"."``). Beide Male derselbe Ausdruck, und das ist der Grund, warum
    er hier prüfbar ist: Ein Pfad, der nur im gebauten Paket stimmt, wird
    nirgends geprüft.
    """
    assert licences.NOTICE_FILE.is_file(), licences.NOTICE_FILE
    assert licences.NOTICE_FILE.name == "THIRD-PARTY-NOTICES.md"
    assert licences.NOTICE_FILE == NOTICE_FILE, "zwei Wege zu derselben Datei"

    spec = (Path(__file__).parent.parent / "packaging" / "solidon3d.spec").read_text(
        encoding="utf-8"
    )
    assert '"THIRD-PARTY-NOTICES.md"), "."' in spec, "die Spec legt sie woandershin"
