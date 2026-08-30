"""Der Update-Hinweis (Bauplan §37.2).

Die Prüfung fragt eine Adresse und zeigt eine Zeile an. Das klingt nach wenig
und ist genau deshalb zu prüfen: was von dort kommt, kommt von einem Server
und nicht aus diesem Programm. Jedes Problem hat „keine Antwort" zu heißen —
nie ein Fehlerdialog, nie ein Start, der daran hängt.
"""

from __future__ import annotations

import hashlib
import json
import urllib.error
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest import mock

import pytest

from app.core import updates
from app.core.changes import Group
from app.core.errors import ExternalToolError, OperationCancelled
from tests.release_signing import REAL_PUBLIC_KEY, accept_test_signatures, signed

__all__ = ["accept_test_signatures"]  # die Fixture wirkt durch den Import, nicht durch Aufruf


def answering(payload: dict[str, Any]) -> updates.Transport:
    """Ein Transport, der genau diese Antwort gibt — unterschrieben.

    Die Unterschrift steckt hier und nicht in jedem einzelnen Test: Sie ist
    keine Eigenschaft dessen, was ein Test prüfen will, sondern die Bedingung
    dafür, dass ``check`` die Antwort überhaupt ansieht (§37.2). Wer eine
    unsignierte Antwort braucht, gibt sie über ``raw_answering``.
    """

    def fetch(_url: str, _headers: dict[str, str], _payload: dict[str, Any]) -> dict[str, Any]:
        return signed(payload)

    return fetch


def raw_answering(payload: dict[str, Any]) -> updates.Transport:
    """Ein Transport, der genau diese Antwort gibt — so, wie sie dasteht."""

    def fetch(_url: str, _headers: dict[str, str], _payload: dict[str, Any]) -> dict[str, Any]:
        return payload

    return fetch


def test_the_check_names_the_application_not_the_library() -> None:
    """Die Anfrage sagt, von wem sie kommt — Solidon, nicht Python-urllib.

    Manche CDNs sperren den Bibliotheksnamen, und die Prüfung scheiterte
    still; die Datenschutzerklärung verspricht zudem ein Programm-Kennzeichen.
    ``download()`` machte es seit je richtig, ``check()`` nicht.
    """
    seen: list[dict[str, str]] = []

    def fetch(_url: str, headers: dict[str, str], _payload: dict[str, Any]) -> dict[str, Any]:
        seen.append(dict(headers))
        return signed({"version": "99.0.0", "url": "https://example.org/"})

    updates.check(fetch=fetch)
    assert seen and seen[0].get("User-Agent", "").startswith("Solidon/")


def test_a_newer_version_is_reported() -> None:
    release = updates.check(fetch=answering({"version": "99.0.0", "url": "https://example.org/"}))

    assert release is not None
    assert release.newer_than()
    assert release.url == "https://example.org/"


def test_a_failing_request_is_simply_no_answer() -> None:
    """Ein Update-Hinweis, der den Start unterbricht, wäre schlimmer als
    keiner."""

    def broken(_url: str, _headers: dict[str, str], _payload: dict[str, Any]) -> dict[str, Any]:
        raise OSError("kein Netz")

    assert updates.check(fetch=broken) is None


def test_a_version_without_content_is_no_answer() -> None:
    assert updates.check(fetch=answering({})) is None
    assert updates.check(fetch=answering({"version": "  "})) is None


def test_a_url_that_is_not_https_is_dropped() -> None:
    """Angezeigt wird nur, was auch eine Adresse ist.

    Das Feld landet in der Statusleiste; ein „url", das keine ist, soll dort
    nicht als eine auftreten.
    """
    release = updates.check(fetch=answering({"version": "99.0", "url": "Rufen Sie 0900 an!"}))

    assert release is not None
    assert release.url == ""


def test_the_fields_cannot_flood_the_status_bar() -> None:
    release = updates.check(fetch=answering({"version": "9" * 5000, "notes": "x" * 5000}))

    assert release is not None
    assert len(release.version) <= updates.MAX_FIELD_LENGTH
    assert len(release.notes) <= updates.MAX_FIELD_LENGTH


def test_an_older_version_is_not_announced() -> None:
    """Kein Downgrade-Hinweis, wenn die eigene Version weiter ist."""
    release = updates.check(fetch=answering({"version": "0.0.0"}))

    assert release is not None
    assert not release.newer_than()


# --- Was der Kunde in seiner Sprache liest --------------------------------------
#
# Beides steht im selben Fenster übereinander: der Hinweis als Überschrift, die
# Punkte darunter. Sie aus zwei Sprachen zu setzen wäre schlechter als nur eine.

SPEAKING: dict[str, Any] = {
    "version": "99.0.0",
    "notes": "Der Satz ohne Sprachangabe.",
    "notes_by_language": {"de": "Auf Deutsch.", "en": "In English."},
    "changes": {"de": ["Ein deutscher Punkt."], "en": ["An English point."]},
}


def test_the_points_arrive_in_the_language_of_the_window() -> None:
    release = updates.check(fetch=answering(SPEAKING))

    assert release is not None
    assert release.points("en") == ("An English point.",)
    assert release.points("de") == ("Ein deutscher Punkt.",)


GROUPED: dict[str, Any] = {
    "version": "99.0.0",
    "changes": {"de": ["Vorn.", "Mitte.", "Hinten."]},
    "groups": {
        "de": [
            {"title": "", "points": ["Vorn."]},
            {"title": "Zeichnen", "points": ["Mitte.", "Hinten."]},
        ]
    },
}


def test_the_groups_arrive_with_their_headings() -> None:
    """Was gegliedert geschickt wird, kommt gegliedert an."""
    release = updates.check(fetch=answering(GROUPED))

    assert release is not None
    groups = release.grouped("de")
    assert [group.title for group in groups] == ["", "Zeichnen"]
    assert groups[1].points == ("Mitte.", "Hinten.")


def test_a_file_without_groups_still_shows_its_points() -> None:
    """Der Rückfall, und er ist der Regelfall für jede ältere Versionsdatei.

    Ohne ``groups`` gibt :meth:`Release.grouped` die flache Liste als **eine**
    Gruppe ohne Titel zurück. Das Fenster muss deshalb nur einen Weg kennen —
    und der Kunde sieht, was er immer sah.
    """
    release = updates.check(fetch=answering(SPEAKING))

    assert release is not None
    groups = release.grouped("de")
    assert len(groups) == 1
    assert groups[0].title == ""
    assert groups[0].points == ("Ein deutscher Punkt.",)


def test_the_groups_fall_back_to_the_source_language_like_the_points() -> None:
    """Derselbe Rückfall wie flach — sonst spräche ein Fenster zwei Sprachen."""
    release = updates.check(fetch=answering(GROUPED))

    assert release is not None
    assert [group.title for group in release.grouped("it")] == ["", "Zeichnen"]


def test_a_group_from_the_server_is_trimmed_like_every_other_text() -> None:
    """Der Text kommt von einem Server und landet in einem Fenster.

    Dieselben Grenzen wie für die flache Liste: ein Punkt auf
    ``MAX_TEXT_LENGTH``, ein Titel auf ``MAX_FIELD_LENGTH``. Und die Anzahl
    zählt **über die Gruppen hinweg** — sonst hätte eine Antwort mit fünfzig
    Überschriften à einem Punkt das Fünfzigfache von ``MAX_CHANGES`` im
    Fenster. Die Grenze gilt dem, was der Kunde liest, und das ist die Summe.
    """
    release = updates.check(
        fetch=answering(
            {
                "version": "99.0.0",
                "groups": {
                    "de": [
                        {"title": "T" * 5_000, "points": ["P" * 5_000]},
                        *[{"title": f"Nr {n}", "points": [f"Punkt {n}"]} for n in range(200)],
                    ]
                },
            }
        )
    )

    assert release is not None
    groups = release.grouped("de")
    assert len(groups[0].title) <= updates.MAX_FIELD_LENGTH
    # ``+ 1`` wie beim Hinweistext daneben: ``_text`` kürzt an der Wortgrenze
    # und hängt ein Auslassungszeichen an — wo etwas fehlt, soll es zu sehen sein.
    assert len(groups[0].points[0]) <= updates.MAX_TEXT_LENGTH + 1
    total = sum(len(group.points) for group in groups)
    assert total <= updates.MAX_CHANGES, f"{total} Punkte über alle Gruppen"


def test_a_broken_groups_field_is_ignored_and_not_fatal() -> None:
    """Was keine Liste von Objekten ist, fällt weg — die flache Liste trägt weiter.

    Eine Versionsdatei kommt über das Netz. Ein Feld, das anders aussieht als
    erwartet, darf das Update nicht verhindern; es darf nur nicht gezeigt
    werden.
    """
    release = updates.check(
        fetch=answering(
            {
                "version": "99.0.0",
                "changes": {"de": ["Der flache Punkt."]},
                "groups": {"de": ["kein Objekt", 42, {"points": "keine Liste"}]},
            }
        )
    )

    assert release is not None
    assert release.grouped("de") == (Group(title="", points=("Der flache Punkt.",)),)


def test_a_group_without_points_does_not_become_a_lonely_heading() -> None:
    """Eine Überschrift ohne Punkte darunter ist schlimmer als keine."""
    release = updates.check(
        fetch=answering(
            {
                "version": "99.0.0",
                "groups": {
                    "de": [
                        {"title": "Leer", "points": []},
                        {"title": "Voll", "points": ["Ein Punkt."]},
                    ]
                },
            }
        )
    )

    assert release is not None
    assert [group.title for group in release.grouped("de")] == ["Voll"]


def test_the_note_arrives_in_the_language_of_the_window() -> None:
    release = updates.check(fetch=answering(SPEAKING))

    assert release is not None
    assert release.note("en") == "In English."
    assert release.note("de") == "Auf Deutsch."


def test_an_unwritten_language_falls_back_to_the_source_and_not_to_nothing() -> None:
    """Lieber der deutsche Satz als eine Überschrift ohne Inhalt darunter."""
    release = updates.check(fetch=answering(SPEAKING))

    assert release is not None
    assert release.points("it") == ("Ein deutscher Punkt.",)
    assert release.note("it") == "Auf Deutsch."


def test_a_version_file_without_languages_still_shows_its_note() -> None:
    """Der Rückfall auf ``notes``, und der Grund, aus dem das Feld bleibt.

    Die Versionsdatei wird von **jeder** ausgelieferten Fassung gelesen, auch
    von denen, die ``notes_by_language`` nicht kennen. Wer den alten Schlüssel
    fallen ließe, nähme ihnen den Satz weg.
    """
    release = updates.check(fetch=answering({"version": "99.0.0", "notes": "Nur dieser Satz."}))

    assert release is not None
    assert release.note("en") == "Nur dieser Satz."


def test_a_note_that_is_not_a_string_is_dropped_rather_than_shown() -> None:
    """Was von einem Server kommt, wird geprüft — auch hier.

    Ohne die Prüfung stünde das Abbild eines Wörterbuchs im Fenster, und zwar
    an der Stelle, an der ein Satz erwartet wird.
    """
    release = updates.check(
        fetch=answering(
            {
                "version": "99.0.0",
                "notes": "Der Rückfall.",
                "notes_by_language": {"de": {"verschachtelt": "ja"}, "en": 7, "es": "Bien."},
            }
        )
    )

    assert release is not None
    assert release.note("de") == "Der Rückfall."
    assert release.note("en") == "Der Rückfall."
    assert release.note("es") == "Bien."


def test_a_note_cannot_flood_the_window_in_any_language() -> None:
    release = updates.check(
        fetch=answering(
            {"version": "99.0.0", "notes_by_language": {"de": "x" * 5000, "en": "y" * 5000}}
        )
    )

    assert release is not None
    assert len(release.note("de")) <= updates.MAX_TEXT_LENGTH + 1
    assert len(release.note("en")) <= updates.MAX_TEXT_LENGTH + 1


def test_a_note_of_normal_length_arrives_whole() -> None:
    """Ein Absatz ist kein Feld — er darf nicht auf Statuszeilenlänge fallen.

    Der Hinweis über der Punkteliste ging bis 0.2.1 durch ``MAX_FIELD_LENGTH``
    (200 Zeichen, für die **Statusleiste** gedacht) und wurde dort mitten im
    Wort gekappt. Im Fenster stand „Die Demo bleibt vollständig und oh" — in
    **allen sechs** Sprachen, denn alle sechs Fassungen lagen zwischen 214 und
    237 Zeichen. Ein Satz, der so endet, sieht aus wie ein Programmfehler, und
    er war einer.

    Geprüft wird mit der echten Länge des Falls, nicht mit einer runden Zahl:
    240 Zeichen sind das, was ein Ankündigungsabsatz wirklich braucht.
    """
    satz = (
        "Das bisher größte Update. Neu ist vor allem: Aus Schritten im Verlauf wird "
        "ein eigener Baustein, den Sie wie jeden anderen einsetzen und mit dem Projekt "
        "weitergeben. Die Demo bleibt vollständig und ohne Schlüssel, bis zum 30.10.2026."
    )
    assert len(satz) > updates.MAX_FIELD_LENGTH, "der Fall muss die alte Grenze reißen"

    release = updates.check(
        fetch=answering({"version": "99.0.0", "notes_by_language": {"de": satz}})
    )

    assert release is not None
    assert release.note("de") == satz


def test_a_text_that_is_really_too_long_says_that_it_was_cut() -> None:
    """Wo gekürzt wird, soll es zu sehen sein — und nicht mitten im Wort.

    Die Schranke gegen einen Server, der Romane schickt, bleibt. Sie endet nur
    nicht mehr stumm: Gekürzt wird an einer Wortgrenze, und ein
    Auslassungszeichen sagt, dass etwas fehlt. Ohne das ist eine Schranke von
    einem Fehler nicht zu unterscheiden.
    """
    lang = " ".join(["Wort"] * 4000)
    release = updates.check(
        fetch=answering({"version": "99.0.0", "notes_by_language": {"de": lang}})
    )

    assert release is not None
    note = release.note("de")
    assert len(note) <= updates.MAX_TEXT_LENGTH + 1
    assert note.endswith("…"), note[-40:]
    assert not note.endswith("Wo…"), "an der Wortgrenze getrennt, nicht im Wort"


# --- Die Pakete in der Versionsdatei --------------------------------------------


def with_package(**changes: Any) -> dict[str, Any]:
    """Eine Antwort mit genau einem Paket, an dem sich etwas ändern lässt."""
    entry: dict[str, Any] = {
        "file": "Solidon3D-Setup-9.9.9.exe",
        "url": "https://solidon3d.de/dl/Solidon3D-Setup-9.9.9.exe",
        "size": 4,
        "sha256": "a" * 64,
    }
    entry.update(changes)
    return {"version": "99.0.0", "packages": {updates.PLATFORM_WINDOWS: entry}}


def test_a_package_is_read_with_all_four_fields() -> None:
    release = updates.check(fetch=answering(with_package()))

    assert release is not None
    package = release.package(updates.PLATFORM_WINDOWS)
    assert package is not None
    assert package.file == "Solidon3D-Setup-9.9.9.exe"
    assert package.size == 4
    assert package.sha256 == "a" * 64


def test_a_package_from_another_host_is_dropped() -> None:
    """Die Prüfsumme steht in derselben Datei wie die Adresse.

    Sie schützt darum nicht gegen einen Server, der beide fälscht — was
    schützt, ist die Auflage, dass das Paket von demselben Rechnernamen kommt
    wie die Versionsdatei. Ein Zertifikat für *diesen* Namen ist die Hürde,
    und wer sie nimmt, braucht keine gefälschte Prüfsumme mehr.
    """
    fremd = with_package(url="https://example.org/dl/Solidon3D-Setup-9.9.9.exe")

    release = updates.check(fetch=answering(fremd))

    assert release is not None
    assert release.packages == {}


def test_a_package_over_plain_http_is_dropped() -> None:
    release = updates.check(fetch=answering(with_package(url="http://solidon3d.de/dl/x.exe")))

    assert release is not None
    assert release.packages == {}


def test_a_package_without_a_usable_checksum_is_dropped() -> None:
    """Ohne Prüfsumme gäbe es nichts zu prüfen, und genau das schließt §37.2
    aus."""
    for kaputt in ("", "abc", "z" * 64, 12345):
        release = updates.check(fetch=answering(with_package(sha256=kaputt)))

        assert release is not None
        assert release.packages == {}, kaputt


def test_a_size_that_is_no_size_becomes_zero() -> None:
    for kaputt in ("viel", -5, 0, True, None, 10**13):
        release = updates.check(fetch=answering(with_package(size=kaputt)))

        assert release is not None
        package = release.package(updates.PLATFORM_WINDOWS)
        assert package is not None and package.size == 0, kaputt


def test_packages_that_are_not_a_mapping_are_no_packages() -> None:
    for kaputt in ("alles", [1, 2], 7):
        release = updates.check(fetch=answering({"version": "99.0", "packages": kaputt}))

        assert release is not None
        assert release.packages == {}, kaputt


def test_the_platform_decides_which_package_is_meant(monkeypatch: pytest.MonkeyPatch) -> None:
    """Auf einem Mac unterscheidet der Befehlssatz, sonst das System.

    Ein für arm64 gebautes Programm startet auf einem Intel-Mac nicht — hier
    ist die Architektur keine Feinheit, sondern der Unterschied zwischen
    „läuft" und „lässt sich nicht öffnen".
    """
    monkeypatch.setattr(updates.sys, "platform", "win32")
    assert updates.platform_key() == updates.PLATFORM_WINDOWS

    monkeypatch.setattr(updates.sys, "platform", "linux")
    assert updates.platform_key() == updates.PLATFORM_LINUX

    monkeypatch.setattr(updates.sys, "platform", "darwin")
    monkeypatch.setattr(updates.platform, "machine", lambda: "arm64")
    assert updates.platform_key() == updates.PLATFORM_MACOS_ARM

    monkeypatch.setattr(updates.platform, "machine", lambda: "x86_64")
    assert updates.platform_key() == updates.PLATFORM_MACOS_INTEL


def linux_payload() -> dict[str, Any]:
    """Eine Versionsdatei, die für Linux das Flatpak-Bundle nennt."""
    return {
        "version": "99.0.0",
        "packages": {
            updates.PLATFORM_LINUX: {
                "file": "Solidon3D-9.9.9-x86_64.flatpak",
                "url": "https://solidon3d.de/dl/Solidon3D-9.9.9-x86_64.flatpak",
                "size": 4,
                "sha256": "a" * 64,
            }
        },
    }


def test_a_flatpak_can_be_replaced_from_inside(monkeypatch: pytest.MonkeyPatch) -> None:
    """Von den beiden Linux-Angeboten lässt sich nur das Flatpak einspielen.

    **Hier stand das Gegenteil**, und zwar begründet: „Flatpak und AppImage
    lassen sich nicht von innen ersetzen". Der zweite Halbsatz stimmt weiter,
    der erste war ein Missverständnis — ``flatpak install`` nimmt ein Bundle
    unmittelbar. Als es allein auf der Download-Seite stand, war Linux damit
    die einzige Plattform ohne Update aus der Anwendung heraus. Das AppImage
    kommt ab der nächsten Version hinzu, ersetzt sich aber nicht selbst.
    """
    monkeypatch.setattr(updates, "packaged", lambda: True)
    monkeypatch.setattr(updates, "install_kind", lambda: updates.KIND_FLATPAK)

    release = updates.check(fetch=answering(linux_payload()))

    assert release is not None
    assert release.startable(updates.PLATFORM_LINUX) is not None, "das Flatpak wird eingespielt"


def test_an_appimage_still_only_gets_the_hint(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ein AppImage ersetzt sich nicht selbst — dort bleibt es beim Hinweis.

    Der Unterschied zum Flatpak ist der ganze Grund für
    :func:`updates.install_kind`: Beide tragen denselben Plattformschlüssel
    ``linux``, und nur einer der beiden lässt sich einspielen. Wer nach der
    Plattform fragt, kann die zwei nicht trennen — und bot dem AppImage-Nutzer
    ein ``flatpak install`` an, das scheitern muss.
    """
    monkeypatch.setattr(updates, "packaged", lambda: True)
    monkeypatch.setattr(updates, "install_kind", lambda: updates.KIND_APPIMAGE)

    release = updates.check(fetch=answering(linux_payload()))

    assert release is not None
    assert release.package(updates.PLATFORM_LINUX) is not None, "der Hinweis kennt es"
    assert release.startable(updates.PLATFORM_LINUX) is None, "eingespielt wird es nicht"


def test_running_from_source_offers_no_package(monkeypatch: pytest.MonkeyPatch) -> None:
    """Wer aus den Quellen fährt, hat nichts, was ein Installer ersetzen
    könnte."""
    monkeypatch.setattr(updates, "packaged", lambda: False)

    release = updates.check(fetch=answering(with_package()))

    assert release is not None
    assert release.package(updates.PLATFORM_WINDOWS) is not None
    assert release.startable(updates.PLATFORM_WINDOWS) is None


# --- Die Installationsart (§37.2) -----------------------------------------------


def test_running_from_source_is_no_installation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Aus den Quellen gefahren gibt es nichts, was ein Installer ersetzen könnte."""
    monkeypatch.setattr(updates, "packaged", lambda: False)

    assert updates.install_kind("win32") == updates.KIND_SOURCE
    assert updates.install_kind("linux") == updates.KIND_SOURCE


def test_each_system_names_its_own_way(monkeypatch: pytest.MonkeyPatch) -> None:
    """Die Plattform ist ein Parameter, damit jeder Weg überall messbar ist.

    Genau darum geht es in ``.claude/rules/kern.md``: Ein Zweig hinter
    ``sys.platform`` wird auf der Maschine, auf der entwickelt wird, nie
    ausgeführt — so sind fünf Stellen entstanden, an denen Linux und macOS
    weniger konnten als Windows. Dieser Test läuft auf jeder der drei.
    """
    monkeypatch.setattr(updates, "packaged", lambda: True)
    monkeypatch.setattr(updates.discover, "in_flatpak", lambda: False)
    monkeypatch.delenv("APPIMAGE", raising=False)

    assert updates.install_kind("win32") == updates.KIND_WINDOWS_SETUP
    assert updates.install_kind("darwin") == updates.KIND_MACOS_PACKAGE
    assert updates.install_kind("linux") == updates.KIND_TARBALL


def test_linux_tells_its_three_formats_apart(monkeypatch: pytest.MonkeyPatch) -> None:
    """Drei Arten, ein Plattformschlüssel — und nur eine lässt sich einspielen."""
    monkeypatch.setattr(updates, "packaged", lambda: True)

    monkeypatch.setattr(updates.discover, "in_flatpak", lambda: True)
    assert updates.install_kind("linux") == updates.KIND_FLATPAK

    monkeypatch.setattr(updates.discover, "in_flatpak", lambda: False)
    monkeypatch.setenv("APPIMAGE", "/home/wer/Solidon3D-0.2.1-x86_64.AppImage")
    assert updates.install_kind("linux") == updates.KIND_APPIMAGE

    monkeypatch.delenv("APPIMAGE")
    assert updates.install_kind("linux") == updates.KIND_TARBALL


def test_only_the_two_silent_ways_come_back_by_themselves(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Apples Installer startet nach dem Einspielen nichts — der Satz muss anders sein."""
    monkeypatch.setattr(updates, "install_kind", lambda: updates.KIND_WINDOWS_SETUP)
    assert updates.runs_unattended()

    monkeypatch.setattr(updates, "install_kind", lambda: updates.KIND_FLATPAK)
    assert updates.runs_unattended()

    monkeypatch.setattr(updates, "install_kind", lambda: updates.KIND_MACOS_PACKAGE)
    assert not updates.runs_unattended()


def test_the_setup_runs_without_questions_and_brings_the_window_back() -> None:
    """Still heißt „ohne Fragen", nicht „ohne Zeichen" — und danach ist es wieder da.

    ``/VERYSILENT`` wäre falsch: Ein Paket von rund 180 MB packt sich aus, und
    ohne Balken sähe der Nutzer minutenlang nichts. Und ohne ``/RESTARTAPP=1``
    bliebe er vor einem geschlossenen Programm — der vorhandene
    ``[Run]``-Eintrag im Inno-Skript trägt ``skipifsilent`` und greift bei einem
    stillen Lauf gerade nicht.
    """
    assert "/SILENT" in updates.SETUP_ARGUMENTS
    assert "/VERYSILENT" not in updates.SETUP_ARGUMENTS
    assert "/RESTARTAPP=1" in updates.SETUP_ARGUMENTS


def test_the_restart_switch_is_read_by_the_installer_script() -> None:
    """Der Schalter ist unserer — er wirkt nur, wenn das Inno-Skript ihn liest.

    Ein Anschlusstest (``AGENTS.md``, Testart „Anschluss"): Die Argumentliste
    allein beweist nichts. Wer sie ändert, ohne ``solidon3d.iss`` nachzuziehen,
    baut ein Update, nach dem das Fenster wegbleibt — und das fällt erst dem
    ersten Kunden auf.
    """
    script = (Path(__file__).resolve().parent.parent / "packaging" / "solidon3d.iss").read_text(
        encoding="utf-8"
    )

    assert "Check: WantsRestart" in script, "der zweite [Run]-Eintrag fehlt"
    assert "{param:RESTARTAPP|0}" in script, "der Schalter wird nicht gelesen"


def test_a_flatpak_is_installed_from_the_bundle_and_started_again(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Kein Repo, kein Umweg: das Bundle einspielen und zurückkommen.

    Beides muss auf dem **Rechner** laufen, nicht im Sandkasten — der endet
    gleich darauf. Und es muss eine Kette sein: Der zweite Befehl darf erst
    laufen, wenn der erste durch ist, und dazwischen ist Solidon beendet.
    """
    monkeypatch.setattr(updates, "install_kind", lambda: updates.KIND_FLATPAK)
    monkeypatch.setattr(updates.discover, "in_flatpak", lambda: True)
    monkeypatch.setattr(updates, "_flatpak_is_user", lambda: True)
    monkeypatch.setenv("FLATPAK_ID", "de.rsdigital.solidon3d")

    command = updates._install_command(Path("/home/wer/.cache/Solidon3D/updates/neu.flatpak"))

    assert command[:2] == ["flatpak-spawn", "--host"], "sonst landet es im Sandkasten"
    line = command[-1]
    assert "flatpak install --user --assumeyes" in line
    assert "neu.flatpak" in line
    assert "&& flatpak run" in line, "ohne das bleibt das Fenster weg"


def test_a_system_wide_flatpak_is_not_replaced_by_a_second_one() -> None:
    """``--user`` auf eine systemweite Installation legt eine zweite daneben.

    Der Nutzer hätte danach zwei Fassungen, von denen die alte weiter startet,
    und keinen Hinweis darauf, warum das Update nichts geändert hat. Der Ort
    steht in ``/.flatpak-info`` und wird gelesen, nicht geraten.
    """
    systemweit = """[Instance]
app-path=/var/lib/flatpak/app/x/current"""
    im_profil = """[Instance]
app-path=/home/wer/.local/share/flatpak/app/x/current"""
    ohne_angabe = """[Instance]
branch=stable"""

    assert not updates._flatpak_is_user(systemweit)
    assert updates._flatpak_is_user(im_profil)
    assert updates._flatpak_is_user(ohne_angabe), "ohne Angabe gilt das Profil"


# --- Das Holen ------------------------------------------------------------------


class FakeAnswer:
    """Eine Antwort, die aus einem Puffer liest statt aus dem Netz."""

    def __init__(self, payload: bytes) -> None:
        self._rest = payload

    def __enter__(self) -> FakeAnswer:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self, size: int = -1) -> bytes:
        if size is None or size < 0:
            size = len(self._rest)
        chunk, self._rest = self._rest[:size], self._rest[size:]
        return chunk


def serving(payload: bytes) -> Callable[..., FakeAnswer]:
    def opener(_request: object, **_options: object) -> FakeAnswer:
        return FakeAnswer(payload)

    return opener


def package_for(payload: bytes, **changes: Any) -> updates.Package:
    values: dict[str, Any] = {
        "file": "Solidon3D-Setup-9.9.9.exe",
        "url": "https://solidon3d.de/dl/Solidon3D-Setup-9.9.9.exe",
        "size": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }
    values.update(changes)
    return updates.Package(**values)


def test_a_downloaded_package_is_kept_when_the_checksum_matches() -> None:
    payload = b"ein Installationspaket" * 100

    file = updates.download(package_for(payload), opener=serving(payload))

    assert file.is_file()
    assert file.read_bytes() == payload


def test_the_progress_counts_up_to_the_whole() -> None:
    payload = b"x" * (updates.CHUNK_BYTES * 2 + 17)
    gesehen: list[float] = []

    updates.download(
        package_for(payload),
        progress=lambda share, _text: gesehen.append(share),
        opener=serving(payload),
    )

    assert gesehen, "ohne Fortschritt sieht niemand, dass etwas geschieht"
    assert gesehen == sorted(gesehen)
    assert gesehen[-1] == pytest.approx(1.0)


def test_a_wrong_checksum_leaves_nothing_behind() -> None:
    """Der Fall, für den die Prüfung da ist — und der Beweis, dass danach
    nichts liegen bleibt, das jemand doppelklicken könnte."""
    payload = b"nicht das, was versprochen war"
    package = package_for(payload, sha256="b" * 64)

    with pytest.raises(ExternalToolError) as fehler:
        updates.download(package, opener=serving(payload))

    assert fehler.value.suggestions, "jede Ausnahme trägt einen Handlungsvorschlag"
    assert not list(updates.target_dir().glob("*")), "die halbe Wahrheit bleibt nicht liegen"


def test_a_package_that_is_shorter_than_announced_is_refused() -> None:
    payload = b"abgebrochen"
    package = package_for(payload, size=len(payload) + 500)

    with pytest.raises(ExternalToolError):
        updates.download(package, opener=serving(payload))

    assert not list(updates.target_dir().glob("*"))


def test_a_package_that_is_longer_than_announced_stops_reading() -> None:
    payload = b"y" * 5000
    package = package_for(payload, size=100)

    with pytest.raises(ExternalToolError):
        updates.download(package, opener=serving(payload))

    assert not list(updates.target_dir().glob("*"))


def test_cancelling_removes_the_half_file() -> None:
    payload = b"z" * (updates.CHUNK_BYTES * 3)

    class Sofort:
        @property
        def is_cancelled(self) -> bool:
            return True

        def raise_if_cancelled(self) -> None:
            raise OperationCancelled

    with pytest.raises(OperationCancelled):
        updates.download(package_for(payload), cancelled=Sofort(), opener=serving(payload))

    assert not list(updates.target_dir().glob("*"))


def test_the_file_name_cannot_leave_the_cache() -> None:
    """Der Name kommt von einem Server.

    „../../Autostart/etwas.exe" ist ein gültiger JSON-String; ungeprüft an
    einen Pfad gehängt schreibt er genau dorthin.
    """
    payload = b"harmlos"
    boese = package_for(payload, file="../../" + "hoch/" * 5 + "boese.exe")

    file = updates.download(boese, opener=serving(payload))

    assert file.parent == updates.target_dir()
    assert file.name == "boese.exe"


def test_an_empty_name_still_becomes_a_file() -> None:
    payload = b"namenlos"

    file = updates.download(package_for(payload, file="///"), opener=serving(payload))

    assert file.parent == updates.target_dir()
    assert file.name == "solidon-update"


def test_the_cache_holds_one_package_at_a_time() -> None:
    """Ein Paket wiegt so viel wie die Anwendung. Zwei sind eines zu viel."""
    erst = b"das alte Paket"
    dann = b"das neue Paket, deutlich anders"

    alt = updates.download(package_for(erst, file="alt.exe"), opener=serving(erst))
    neu = updates.download(package_for(dann, file="neu.exe"), opener=serving(dann))

    assert not alt.exists()
    assert neu.is_file()
    assert [p.name for p in updates.target_dir().glob("*")] == ["neu.exe"]


def test_a_server_that_says_no_is_an_error_with_a_way_out() -> None:
    def refusing(_request: object, **_options: object) -> FakeAnswer:
        raise urllib.error.HTTPError("https://solidon3d.de/dl/x", 404, "weg", {}, None)  # type: ignore[arg-type]

    with pytest.raises(ExternalToolError) as fehler:
        updates.download(package_for(b"egal"), opener=refusing)

    assert any(action.id == "open_download_page" for action in fehler.value.suggestions)


def test_starting_a_package_that_is_gone_says_so() -> None:
    fehlt = updates.target_dir() / "nie-dagewesen.exe"

    with pytest.raises(ExternalToolError) as fehler:
        updates.start_installer(fehlt)

    assert fehler.value.suggestions


def test_starting_hands_the_package_to_the_system(monkeypatch: pytest.MonkeyPatch) -> None:
    """Gestartet und nicht abgewartet: Der Installer überlebt Solidon."""
    payload = b"ein Paket"
    file = updates.download(package_for(payload), opener=serving(payload))
    gestartet: list[list[str]] = []

    def note(command: list[str], **_options: object) -> None:
        gestartet.append(command)

    monkeypatch.setattr(updates.subprocess, "Popen", note)

    updates.start_installer(file)

    assert gestartet and str(file) in gestartet[0]


# --- die Unterschrift der Versionsdatei (§37.2) ---------------------------------------


def test_a_tampered_version_file_is_refused() -> None:
    """Der Fall, für den die Unterschrift da ist: jemand hat den Server.

    Er tauscht Paket und Prüfsumme gemeinsam aus — beide stehen in derselben
    Datei, und die Prüfsumme allein widerspricht ihm nicht. Die Unterschrift
    schon: Sie läuft über den ganzen Inhalt, und erzeugen kann er sie nicht.
    """
    echt = signed(
        {
            "version": "9.0.0",
            "url": "https://solidon3d.de/",
            "packages": {
                "windows": {
                    "file": "S.exe",
                    "url": "https://solidon3d.de/S.exe",
                    "size": 1,
                    "sha256": "ab" * 32,
                }
            },
        }
    )
    assert updates.check(fetch=raw_answering(echt)) is not None

    getauscht = json.loads(json.dumps(echt))
    getauscht["packages"]["windows"]["sha256"] = "ff" * 32
    assert updates.check(fetch=raw_answering(getauscht)) is None


def test_a_version_file_without_a_signature_is_refused() -> None:
    """Weglassen darf nicht helfen — sonst wäre die Prüfung eine Bitte."""
    ohne = {"version": "9.0.0", "url": "https://solidon3d.de/"}

    assert updates.check(fetch=raw_answering(ohne)) is None


def test_only_the_content_is_signed_not_its_layout() -> None:
    """Andere Einrückung, dieselbe Aussage: Die Unterschrift trägt weiter.

    Sonst hinge sie daran, wie ein Werkzeug JSON schreibt — und das erste
    Umformatieren nähme allen Kunden den Update-Weg.
    """
    echt = signed({"version": "9.0.0", "url": "https://solidon3d.de/"})

    umgebrochen = json.loads(json.dumps(echt, indent=8, sort_keys=True))

    assert updates.check(fetch=raw_answering(umgebrochen)) is not None


def test_the_published_version_file_is_signed() -> None:
    """**Die Datei, die wir wirklich ausliefern, gegen den echten Schlüssel.**

    Testart „Anschluss": Die Tests darüber prüfen mit dem Schlüssel der Suite
    und belegen damit die Arithmetik, nicht die Auslieferung. Dieser hier
    fängt den Fall, der wirklich passiert — ``make_download.py`` schreibt
    ``version.json`` neu, jemand lädt sie hoch, und niemand hat unterschrieben.
    Der Schaden wäre lautlos: Die Datei liegt richtig da, und trotzdem erfährt
    keine Installation je von dieser Fassung.

    Kein ``monkeypatch``, keine Fixture — hier zählt der echte
    ``RELEASE_PUBLIC_KEY``. Die autouse-Fixture wird dafür ausdrücklich
    zurückgedreht.
    """
    file = Path(__file__).resolve().parent.parent / "website" / "version.json"
    data = json.loads(file.read_text(encoding="utf-8"))
    assert data, "version.json is empty — nothing was checked"

    with mock.patch.object(updates, "RELEASE_PUBLIC_KEY", REAL_PUBLIC_KEY):
        assert updates.signature_ok(data), (
            "website/version.json carries no valid signature — sign it before "
            "uploading: python tools/sign_version.py --private <file>"
        )


# --- Die Datei, die der Client wirklich liest ------------------------------------

PUBLISHED_VERSION_FILE = Path(__file__).resolve().parents[1] / "website" / "version.json"


class _AnswerFromDisk:
    """Ein ``urlopen``-Ersatz, der die eingecheckte Versionsdatei liefert.

    Gemockt wird ``urlopen`` und nicht der ``Transport``: Ein eigener Transport
    ersetzt :func:`updates._get` **samt seiner Größenprüfung** — und genau die
    ist hier der Prüfling. Was der Kunde erlebt hat, entsteht erst zwei Ebenen
    tiefer, beim Lesen der Bytes.
    """

    def __init__(self, raw: bytes) -> None:
        self._raw = raw

    def read(self, count: int | None = None) -> bytes:
        return self._raw if count is None else self._raw[:count]

    def __enter__(self) -> _AnswerFromDisk:
        return self

    def __exit__(self, *_: object) -> bool:
        return False


def test_the_published_version_file_gets_through_the_read_that_bounds_it() -> None:
    """Die ausgelieferte Datei kommt durch :func:`updates._get` — den Weg, auf
    dem sie beim Kunden hängenblieb.

    **Der Anlass ist ein Absturzbericht vom 27.08.2026** (S-20260826-72a4dd).
    Der Kunde meldete einen Absturz; im selben Protokoll steht eine Zeile, die
    harmloser aussieht::

        update check did not answer: version file is too large

    ``website/version.json`` war über die Lesegrenze gewachsen, ``_get`` brach
    ab, und der Hinweis schwieg — richtig nach §37.2, und trotzdem das
    schlechteste Ergebnis: ein Ausfall ohne Fehler, ohne Fenster, ohne Zeile
    beim Kunden. Wer die Prüfung verliert, erfährt von keiner neuen Fassung
    mehr, auch nicht von der, die seinen Absturz behebt.

    **Geprüft hat das nichts.** Die Grenze stand in ``updates.py``, die Datei
    wuchs in ``website/``, und dazwischen gab es keine Zusicherung.
    ``test_the_published_version_file_is_signed`` sieht dieselbe Datei an, aber
    erst *nachdem* sie gelesen wurde — es prüft die Unterschrift, nicht den
    Weg dorthin.

    Gemockt wird deshalb ``urlopen`` und nicht der ``Transport``: Ein eigener
    Transport ersetzt ``_get`` **samt seiner Größenprüfung**, und genau die ist
    hier der Prüfling.
    """
    if not PUBLISHED_VERSION_FILE.exists():
        pytest.skip("die Versionsdatei liegt nur im vollständigen Baum")

    raw = PUBLISHED_VERSION_FILE.read_bytes()

    with mock.patch("urllib.request.urlopen", return_value=_AnswerFromDisk(raw)):
        try:
            payload = updates._get(updates.VERSION_URL, {}, {})
        except Exception as problem:
            # Dieselbe Ausnahme, die beim Kunden im Protokoll landete — nur
            # dort hieß sie „did not answer" und sah nach einem Netzproblem
            # aus. Hier soll sie sagen, was wirklich los ist.
            raise AssertionError(
                f"die ausgelieferte version.json ({len(raw)} Bytes) kommt nicht "
                f"durch den eigenen Lesepfad: {problem}. Die Grenze steht bei "
                f"{updates.MAX_ANSWER_BYTES} Bytes. Beim Kunden heißt das: kein "
                f"Update-Hinweis mehr, ohne jede Meldung."
            ) from problem

    assert payload.get("version"), (
        f"die ausgelieferte version.json ({len(raw)} Bytes) kommt nicht durch "
        f"den eigenen Lesepfad — zu groß für MAX_ANSWER_BYTES "
        f"({updates.MAX_ANSWER_BYTES}) oder kein gültiges JSON. Beim Kunden "
        f"heißt das: kein Update-Hinweis mehr, ohne jede Meldung."
    )


def test_the_read_limit_carries_what_the_format_may_write() -> None:
    """Die Lesegrenze muss über dem liegen, was das eigene Format zulässt.

    Beim Kunden ist sie gerissen: „update check did not answer: version file is
    too large" (Protokoll vom 27.08.2026, Vorgang S-20260826-72a4dd). Der
    Kommentar an der Grenze sagte „Die Datei trägt drei kurze Felder" — richtig,
    als er geschrieben wurde, und mit dem Changelog still falsch geworden:
    ``changes`` ist ein Wörterbuch **je Sprache**, und bei 0.2.1 waren das 49
    Punkte mal sechs, also 37 KB von 64.

    Zwei Grenzen entschieden dieselbe Frage und widersprachen sich —
    ``MAX_CHANGES`` erlaubte hundert Punkte zu schreiben, die 64 KB ließen rund
    neunundachtzig lesen. Dazwischen liegt der Bereich, in dem die Anwendung
    eine Datei erzeugt, die sie selbst nicht mehr liest.

    Das ist die teuerste Stelle für einen stillen Ausfall: Wer die Prüfung
    verliert, erfährt von keiner neuen Fassung — auch nicht von der, die seinen
    Absturz behebt.
    """
    from app.i18n.catalog import available_languages

    languages = len(available_languages())
    assert languages >= 2, f"nur {languages} Sprache(n) gefunden — prüft das etwas?"

    worst_case = updates.MAX_CHANGES * updates.MAX_TEXT_LENGTH * languages
    assert worst_case < updates.MAX_ANSWER_BYTES, (
        f"die Lesegrenze ({updates.MAX_ANSWER_BYTES}) liegt unter dem, was das Format "
        f"schreiben darf ({worst_case}) — bei {languages} Sprachen"
    )


def test_the_shipped_version_file_is_read_without_complaint() -> None:
    """Und die Probe an der Datei, die wirklich ausgeliefert wird.

    Der Test darüber prüft die Rechnung, dieser den Bestand: Was auf dem Server
    liegt, muss die Anwendung lesen können. Beides zusammen, weil eine richtige
    Rechnung an einer Datei scheitern kann, die noch etwas anderes mitbringt —
    die Ableitung deckt den Changelog, nicht ein neues Feld daneben.
    """
    published = Path(__file__).resolve().parent.parent / "website" / "version.json"
    if not published.is_file():  # pragma: no cover — im Klon ohne Website
        pytest.skip("keine ausgelieferte version.json im Baum")

    size = published.stat().st_size
    assert size > 1000, f"{size} Bytes — das ist keine Versionsdatei"
    assert size <= updates.MAX_ANSWER_BYTES, (
        f"die ausgelieferte Datei wiegt {size / 1024:.1f} KB, gelesen werden "
        f"{updates.MAX_ANSWER_BYTES / 1024:.1f} KB"
    )
