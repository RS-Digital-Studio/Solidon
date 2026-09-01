"""Abhängigkeiten gegen die Freigabeliste (Bauplan §36, AGENTS.md Regel 22)."""

from __future__ import annotations

from dataclasses import replace
from email.message import Message
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
    assert "GPL-3.0-only" in policy.forbidden
    assert "LGPL-3.0-only" in policy.allowed


def test_the_banned_packages_are_not_installed() -> None:
    installed = {licences.normalise(name) for name in licences.runtime_packages()}
    for banned in licences.load_policy().banned_packages:
        assert licences.normalise(banned) not in installed, f"{banned} must not be installed"


def test_a_gpl_package_would_be_caught() -> None:
    """Ein Wächter für die Prüfung selbst — sonst bewiese ein grüner Lauf
    nichts.
    """
    assert not licences.licence_allowed("GPL-3.0-or-later")


@pytest.mark.parametrize(
    ("expression", "allowed"),
    [
        ("LGPL-3.0-only OR GPL-3.0-only", True),
        ("LGPL-3.0-only AND GPL-3.0-only", False),
        ("LGPL-3.0-only AND AGPL-3.0-only", False),
        ("MIT OR (Apache-2.0 AND BSD-3-Clause)", True),
        ("mit AND apache-2.0", True),
        ("MIT AND LicenseRef-Proprietary", False),
        ("GPL-3.0-or-later WITH GCC-exception-3.1", True),
        ("GPL-3.0-or-later WITH Classpath-exception-2.0", False),
    ],
)
def test_spdx_operators_are_evaluated_instead_of_searched(expression: str, allowed: bool) -> None:
    assert licences.licence_allowed(expression) is allowed


@pytest.mark.parametrize(
    "expression",
    [
        "MIT-ish",
        "permit",
        "BSD",
        "LGPL-3.0-only OR",
        "(MIT AND Apache-2.0",
        "MIT WITH",
    ],
)
def test_unknown_or_malformed_licence_text_is_not_a_substring_match(expression: str) -> None:
    try:
        allowed = licences.licence_allowed(expression)
    except ValueError:
        allowed = False
    assert not allowed


class FakeDistribution:
    """Paketmetadaten für die Randfälle des Lizenzfelds."""

    def __init__(self, *, licence: str = "", expression: str = "") -> None:
        self.metadata = Message()
        if licence:
            self.metadata["License"] = licence
        if expression:
            self.metadata["License-Expression"] = expression


def test_a_long_free_text_licence_is_not_mistaken_for_an_spdx_expression() -> None:
    package = FakeDistribution(licence="Copyright und Bedingungen\n" * 40)
    assert licences.declared_licence(package) == ""


def test_a_machine_readable_expression_wins_even_beside_a_long_licence_text() -> None:
    package = FakeDistribution(
        licence="Copyright und Bedingungen\n" * 40,
        expression="MIT AND Apache-2.0",
    )
    assert licences.declared_licence(package) == "MIT AND Apache-2.0"


def test_an_unrecorded_direct_mit_dependency_is_a_violation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Eine zulässige Lizenz ersetzt nicht die ausdrückliche Vorabfreigabe."""
    policy = licences.load_policy()
    known = {
        name: record
        for name, record in policy.known.items()
        if licences.normalise(name) != "certifi"
    }
    monkeypatch.setattr(licences, "load_policy", lambda: replace(policy, known=known))

    violations = licences.check()

    assert any(
        licences.normalise(entry.package) == "certifi"
        and "direkte Abhängigkeit ohne Eintrag" in entry.reason
        for entry in violations
    )


def test_an_unrecorded_transitive_mit_dependency_is_checked_semantically(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Transitive Pakete brauchen keinen vorgetäuschten Direkteintrag."""
    policy = licences.load_policy()
    known = {
        name: record for name, record in policy.known.items() if licences.normalise(name) != "attrs"
    }
    monkeypatch.setattr(licences, "load_policy", lambda: replace(policy, known=known))

    violations = licences.check()

    assert not any(licences.normalise(entry.package) == "attrs" for entry in violations)


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
        + "\n\nNeu erzeugen: python tools/make_licence_notices.py"
    )


def test_every_known_platform_package_has_an_exact_policy_record() -> None:
    """Andere Zielsysteme sind freigegeben, ohne Wheel-Texte vorzutäuschen.

    Die vollständige Beilage wird auf jedem Zielsystem aus dessen echten
    Wheels erzeugt. Eine Windows-Beilage darf deshalb keine Linux-Wheel-Akte
    behaupten; deren Ausdrücke müssen aber vor dem jeweiligen Baulauf bereits
    exakt geprüft und freigegeben sein.
    """
    policy = licences.load_policy()
    known = {licences.normalise(name): record for name, record in policy.known.items()}
    for name in licences.PLATFORM_PACKAGES:
        expression = known[licences.normalise(name)]["licence"]
        assert licences.licence_allowed(expression, policy), name


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

    policy = licences.load_policy()
    known = {licences.normalise(name): record for name, record in policy.known.items()}
    for entry in comfy_setup.PACKAGES:
        name = licences.normalise(entry.split("==")[0])
        assert name in known, f"{name} fehlt als direkte externe Freigabe"
        assert licences.licence_allowed(known[name]["licence"], policy), name


def test_the_shipped_workflows_name_no_gpl_node() -> None:
    """Mitgelieferte Abläufe dürfen keinen ausgeschlossenen Knoten verlangen."""
    import json

    from app.core.backends import mesh

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
    assert text.startswith("| Paket | Version | SPDX-Ausdruck | Quelle |"), text[:80]
    assert all(line.startswith("|") for line in text.splitlines()), (
        "die Erklärung aus dem Kopf der Beilage gehört nicht in den Dialog"
    )
    assert "contrib.rocks" not in text, "eine Tabelle aus einem Lizenzvolltext lief mit ein"


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
