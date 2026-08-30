"""Das Update (Bauplan §37.2).

Drei Schritte, und jeder braucht einen Klick: fragen, holen, starten. Hier
stand einmal „ein Hinweis, kein automatisches Update", und der Grund dafür
war gut — ein Programm, das sich selbst ersetzt, kann sich kaputtmachen,
während niemand hinsieht. Er gilt weiter, nur trifft er nicht mehr den Weg,
sondern den **Auslöser**: Es lädt nichts von allein, es ersetzt sich nichts
im Hintergrund, und es startet nichts ohne Zustimmung.

Was die Anwendung jetzt zusätzlich tut, ist das Holen und das Prüfen. Beides
von Hand zu machen hieß: Seite finden, das richtige von fünf Paketen
erkennen, die Prüfsumme irgendwo abgleichen. Der letzte Schritt fiel dabei
immer aus.

**Woran die Sicherheit hängt.** Die Prüfsumme steht in derselben Datei wie
die Adresse — gegen einen Server, der beides fälscht, hilft sie nicht. Was
hilft, ist HTTPS und die Auflage, dass das Paket von *demselben Rechnernamen*
kommt wie die Versionsdatei: Wer die Antwort umbiegen will, braucht ein
Zertifikat für diesen Namen. Die Prüfsumme fängt, was danach kommt — den
abgebrochenen Download, den halb geschriebenen Puffer, die Datei aus einem
Zwischenspeicher.

Die Prüfung beim Start ist an — seit dem 23.08.2026, und die
Datenschutzerklärung auf der Website sagt es so. Sie bleibt eine Anfrage, die
den Rechner verlässt, und damit eine Entscheidung: abschaltbar in den
Einstellungen, und ältere Einstellungsdateien werden beim ersten Lesen einmal
angehoben (``update_default_lifted`` in ``app/ui/settings.py``).
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shlex
import subprocess
import sys
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final
from urllib.parse import urlsplit

from app.branding import APP_ID, APP_VERSION
from app.core import discover
from app.core.activation import ed25519
from app.core.backends.llm import Transport
from app.core.changes import Group
from app.core.errors import (
    OPEN_DOWNLOAD_PAGE,
    RETRY,
    ExternalToolError,
    FileWriteError,
)
from app.core.ingest.fetch import CHUNK_BYTES
from app.core.install import packaged
from app.core.log import get_logger
from app.core.paths import ensure_dir, user_cache_dir
from app.core.types import CancelToken, ProgressFn
from app.i18n import SOURCE_LANGUAGE, _, get_language

_log = get_logger(__name__)

#: Wo die Versionsdatei liegt. Eine Adresse, ein JSON-Objekt.
VERSION_URL: Final = "https://solidon3d.de/version.json"

#: Der öffentliche Schlüssel, gegen den die Versionsdatei geprüft wird (§37.2).
#:
#: **Warum ein eigenes Paar und nicht das aus §8.** Der Lizenzschlüssel und die
#: Versionsdatei haben verschiedene Aufgaben und verschiedene Lebensdauern. Ein
#: gemeinsames Paar hieße: Wer den einen Teil verliert, verliert beide Zwecke
#: auf einmal — und der Lizenzschlüssel wird bei jedem Kauf benutzt, die
#: Versionsdatei bei jedem Bau.
#:
#: Der private Teil liegt **nicht im Repository und nicht auf dem Server**. Das
#: ist der ganze Punkt: Gegen einen Angreifer, der den Webserver hat, hilft die
#: Prüfsumme nicht — sie steht in derselben Datei wie die Adresse, und er
#: tauscht beide zusammen aus. Gegen ihn hilft nur eine Unterschrift, die er
#: dort nicht erzeugen kann.
RELEASE_PUBLIC_KEY: Final = bytes.fromhex(
    "603ec2d86e9f1b5232ccec58153b863f00c1f91cbc647a8696ecf6dfd4bbee79"
)

#: Wie das Feld heißt, in dem die Unterschrift steht.
SIGNATURE_FIELD: Final = "signature"

#: Wie lange die Prüfung dauern darf. Sie läuft beim Start; niemand wartet
#: auf sie.
TIMEOUT_SECONDS: Final = 4.0


#: Wie lang die einzelnen Felder werden dürfen. Sie landen in der Statusleiste,
#: und was dort steht, kommt von einem Server — nicht aus diesem Programm.
MAX_FIELD_LENGTH: Final = 200

#: Wie lang ein **Fließtext** werden darf: der Hinweis über der Punkteliste und
#: die Punkte selbst.
#:
#: **Nicht** :data:`MAX_FIELD_LENGTH`. Deren 200 Zeichen sind für eine
#: Statuszeile gedacht, und der Hinweis ist ein Absatz in einem Dialog mit
#: Rollbereich. Bei 0.2.1 riss ihn **jede der sechs Sprachfassungen** — 214 bis
#: 237 Zeichen —, und gekappt wurde mitten im Wort: „Die Demo bleibt
#: vollständig und oh". Ein Satz, der so endet, sieht aus wie ein Fehler des
#: Programms, und er ist einer.
#:
#: 800 ist keine runde Zahl aus Bequemlichkeit: Es ist die Länge, ab der ein
#: Absatz in einem Rollbereich lang genug ist, ohne dass ein Server ihn als
#: Textwüste missbrauchen kann.
#:
#: **Hier stand einmal eine Rechnung, und sie war falsch:** „Selbst 100 Punkte
#: à 800 Zeichen bleiben unter den 64 KB, die überhaupt gelesen werden."
#: Nachgerechnet sind hundert mal achthundert schon 78 KB — für **eine**
#: Sprache, und ``changes`` trägt jede. Der Satz bestätigte die Grenze, die er
#: prüfen
#: sollte, und beim Kunden riss sie (siehe :data:`MAX_ANSWER_BYTES`). Die
#: Lesegrenze wird deshalb aus diesen Werten **abgeleitet**, nicht an ihnen
#: gemessen — die Abhängigkeit läuft in eine Richtung.
MAX_TEXT_LENGTH: Final = 800

#: Wie lange das Holen des Pakets an einer einzelnen Leseoperation hängen darf.
#: Nicht zu verwechseln mit :data:`TIMEOUT_SECONDS`: Die Abfrage soll den Start
#: nicht aufhalten, ein Download von 180 MB dauert bei jeder Leitung länger als
#: vier Sekunden.
DOWNLOAD_TIMEOUT_SECONDS: Final = 60.0

#: Was ein Paket höchstens wiegen darf. Die Versionsdatei nennt die erwartete
#: Größe, und mehr als das wird nicht gelesen — diese Grenze fängt den Fall,
#: dass sie eine unsinnige Zahl nennt.
MAX_PACKAGE_BYTES: Final = 2 * 1024 * 1024 * 1024

#: Wie viele Punkte aus dem Changelog gezeigt werden. Die Datei kommt von einem
#: Server, und diese Zahl fängt den, der achthundert Zeilen schickt — das
#: Fenster rollt für den Rest.
#:
#: **Sie begrenzt nicht, wie viel eine Fassung zu sagen hat.** Die Zahl stand
#: auf zwanzig, stieg zu 0.2.0 auf hundert, und im Kopf von
#: ``changelog/de.md`` stand daneben eine zweite — „acht Zeilen" —, die als
#: Sollwert gelesen wurde: 0.2.0 galt als Ausnahme mit 75 Punkten, und der
#: nächste Abschnitt begann wieder bei acht. Diese zweite Zahl ist am
#: 27.08.2026 gestrichen worden (Entscheidung Robert). Wie viele Punkte ein
#: Abschnitt trägt, entscheidet die Fassung: Ein halbes Jahr Arbeit und ein
#: Wartungsschritt haben nicht gleich viel zu sagen, und gestrichen wird, was
#: der Kunde nicht merkt — nicht, was über einer Grenze steht.
#:
#: Wer **diese** Grenze anfasst, prüft dagegen weiterhin, ob das Fenster den
#: Zuwachs verträgt; sie gehört der Anzeige und nicht der Auswahl.
MAX_CHANGES: Final = 100


def _room_for_the_version_file() -> int:
    """Was die Versionsdatei im schlimmsten erlaubten Fall wiegen darf.

    Hundert Punkte à achthundert Zeichen — mehr lässt das eigene Format nicht
    zu — in **jeder** eingecheckten Sprache, dazu noch einmal so viel Luft für
    Kopffelder, Paketliste, Unterschrift und die Anführungszeichen des Formats.

    Die Sprachzahl kommt aus dem Verzeichnis, weil eine weitere Sprache eine
    Datei ist und sonst nichts (``AGENTS.md``): Wer eine hinzufügt, soll nicht
    auch noch hier nachrechnen müssen. Der Import steht in der Funktion, damit
    das Modul ohne Katalogverzeichnis ladbar bleibt.
    """
    from app.i18n.catalog import available_languages

    return 2 * MAX_CHANGES * MAX_TEXT_LENGTH * max(len(available_languages()), 1)


#: Wie viel von der Antwort überhaupt gelesen wird.
#:
#: Das Zeitlimit deckelt die einzelne Socket-Operation, nicht die Menge: eine
#: Gegenstelle, die zügig und endlos liefert, füllte sonst beim Start den
#: Arbeitsspeicher.
#:
#: **Hier stand „Die Datei trägt drei kurze Felder" und 64 KB daneben.** Der
#: Satz war richtig, als er geschrieben wurde, und ist mit dem Changelog still
#: falsch geworden: ``changes`` ist ein Wörterbuch **je Sprache**, und das sind
#: bei 0.2.1 schon 49 Punkte mal sechs — 37 KB, also 58 Prozent der alten
#: Grenze, und 88 Prozent davon allein für den Changelog.
#:
#: Beim Kunden ist sie gerissen: „update check did not answer: version file is
#: too large" (Protokoll vom 27.08.2026, Vorgang S-20260826-72a4dd). Das ist
#: die teuerste Stelle für einen Ausfall — wer die Prüfung verliert, erfährt
#: von keiner neuen Fassung mehr, auch nicht von der, die seinen Absturz
#: behebt.
#:
#: **Zwei Grenzen entschieden dieselbe Frage und widersprachen sich:**
#: :data:`MAX_CHANGES` erlaubt hundert Punkte zu schreiben, die 64 KB ließen
#: rund neunundachtzig lesen. Dazwischen liegt der Bereich, in dem das Programm
#: eine Datei erzeugt, die es selbst nicht mehr liest. Die Rechnung im
#: Kommentar an :data:`MAX_TEXT_LENGTH` bestätigte das Gegenteil — sie zählte
#: eine Sprache statt sechs, und selbst für die eine kam sie auf 78 KB.
#:
#: Abgeleitet statt geraten. Die Schranke gegen eine endlos liefernde
#: Gegenstelle bleibt, sie sitzt nur nicht mehr unterhalb der eigenen Zusagen.
MAX_ANSWER_BYTES: Final = _room_for_the_version_file()

#: Wie ein Paketschlüssel in der Versionsdatei heißt. Die Architektur steht nur
#: dort, wo es zwei gibt: Auf einem Mac startet ein für arm64 gebautes Programm
#: auf einem Intel-Gerät nicht.
PLATFORM_WINDOWS: Final = "windows"
PLATFORM_MACOS_ARM: Final = "macos-arm64"
PLATFORM_MACOS_INTEL: Final = "macos-x86_64"
PLATFORM_LINUX: Final = "linux"

#: Wie diese Installation eingespielt worden ist — und damit, **wie** ein
#: Update sie ersetzt.
#:
#: Nicht zu verwechseln mit dem Plattformschlüssel darüber: Der sagt, *welches*
#: Paket gemeint ist. Unter Linux tragen drei Arten denselben Schlüssel
#: ``linux`` und brauchen drei verschiedene Wege — dort ist die Plattform als
#: Auskunft zu grob.
KIND_WINDOWS_SETUP: Final = "windows-setup"
KIND_MACOS_PACKAGE: Final = "macos-package"
KIND_FLATPAK: Final = "flatpak"
KIND_APPIMAGE: Final = "appimage"
KIND_TARBALL: Final = "tarball"
KIND_SOURCE: Final = "source"

#: Welche Arten sich von innen ersetzen lassen.
#:
#: **Hier stand einmal eine Menge von Plattformen, und Linux fehlte darin** —
#: mit der Begründung, ein Flatpak wolle ``flatpak update`` und ein AppImage
#: ersetze sich gar nicht. Der zweite Halbsatz stimmt weiterhin. Der erste war
#: der Grund für eine Lücke, die keiner der drei Plattformen anzusehen war:
#: Ausgeliefert wurde für Linux **nur** das Flatpak-Bundle, und damit war Linux
#: die einzige Plattform ohne Update aus der Anwendung heraus. Wer dort
#: arbeitete, sah einen Hinweis und durfte 276 MB von Hand holen — während
#: Windows und macOS es angeboten bekamen. Ab der nächsten Version stehen
#: Flatpak und AppImage nebeneinander; einspielen lässt sich weiterhin nur das
#: Flatpak-Bundle.
#:
#: **Ein Repo braucht es dafür nicht.** ``flatpak install`` nimmt eine
#: Bundle-Datei unmittelbar und aktualisiert damit eine vorhandene
#: Installation; der Weg nach draußen steht mit ``flatpak-spawn --host``
#: ohnehin schon (:func:`app.core.discover.on_host`, Berechtigung
#: ``--talk-name=org.freedesktop.Flatpak`` im Manifest).
#:
#: AppImage und Archiv bleiben außen: Das Archiv ist nur ein Bauartefakt, das
#: AppImage wird ab der nächsten Version zwar ausgeliefert, ersetzt sich aber
#: nicht selbst. Erkannt werden beide trotzdem — sonst bekäme ein
#: AppImage-Nutzer ein ``flatpak install``, das scheitern muss, und die
#: Auskunft „geht hier nicht" wäre eine Vermutung statt einer Feststellung.
REPLACEABLE: Final = frozenset({KIND_WINDOWS_SETUP, KIND_MACOS_PACKAGE, KIND_FLATPAK})

#: Womit die Setup-Datei beim Update aufgerufen wird.
#:
#: ``/SILENT`` und **nicht** ``/VERYSILENT``: Der Fortschrittsbalken bleibt.
#: Ein Paket von rund 180 MB packt sich aus, und das dauert — ohne jede Anzeige
#: sähe der Nutzer nach dem Beenden minutenlang nichts und hielte es für einen
#: Absturz. Still heißt hier „ohne Fragen", nicht „ohne Zeichen".
#:
#: ``/NORESTART``, damit der Installer den Rechner nicht neu startet. Das ist
#: seine Entscheidung nicht, und ein Update, das den Rechner mitnimmt, verliert
#: alles andere, was offen war.
#:
#: ``/RESTARTAPP=1`` ist kein Schalter von Inno Setup, sondern unserer:
#: ``packaging/solidon3d.iss`` liest ihn in einem eigenen ``[Run]``-Eintrag und
#: startet Solidon danach wieder. Der vorhandene Eintrag dort trägt
#: ``skipifsilent`` und greift bei einem stillen Lauf gerade **nicht** — ohne
#: den zweiten bliebe der Nutzer nach dem Update vor einem geschlossenen
#: Programm und müsste selbst darauf kommen, es zu starten.
SETUP_ARGUMENTS: Final = ("/SILENT", "/NORESTART", "/RESTARTAPP=1")


@dataclass(frozen=True, slots=True)
class Package:
    """Ein Installationspaket, wie die Versionsdatei es beschreibt.

    Vier Angaben, und jede hat eine Aufgabe: ``file`` steht in der Meldung,
    ``url`` wird geholt, ``size`` deckelt das Lesen und ``sha256`` entscheidet,
    ob das Geholte je gestartet wird.
    """

    file: str
    url: str
    size: int = 0
    sha256: str = ""


@dataclass(frozen=True, slots=True)
class Release:
    """Was die Versionsdatei sagt."""

    version: str
    url: str = ""
    notes: str = ""
    """Der Hinweistext ohne Sprachangabe — der Rückfall, wenn :attr:`notes_by_language`
    für die Sprache des Fensters nichts hat."""

    notes_by_language: Mapping[str, str] = field(default_factory=dict)
    """Derselbe Hinweis je Sprache.

    Ein eigenes Feld und nicht ``notes`` als Wörterbuch, weil die Versionsdatei
    von **jeder** ausgelieferten Fassung gelesen wird: Bis 0.1.5 nimmt der
    Leser ``notes`` unbesehen als Zeichenkette, und ein Wörterbuch stünde dort
    als Python-Abbild im Fenster. Der alte Schlüssel bleibt deshalb, was er
    war; die Sprachen kommen daneben.
    """

    packages: Mapping[str, Package] = field(default_factory=dict)
    changes: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    """Was neu ist, in Kundensprache — je Sprache eine Liste."""

    groups: Mapping[str, tuple[Group, ...]] = field(default_factory=dict)
    """Dasselbe, gegliedert — je Sprache die Abschnitte mit ihren Überschriften.

    **Ein zweites Feld neben ``changes`` und kein Ersatz.** Die Versionsdatei
    wird von jeder ausgelieferten Fassung gelesen, und bis 0.2.2 kennt der
    Leser nur die flache Liste; sie bleibt deshalb, was sie war. Ein Server,
    der noch keine Gruppen schickt, ist kein Fehler — :meth:`grouped` fällt
    dann auf ``changes`` zurück.

    Wiederverwendet wird :class:`app.core.changes.Group`, nicht eine zweite
    Klasse derselben Form: Was hier über das Netz kommt und was
    ``changes.history`` aus der eingebauten Datei liest, ist für den Leser
    dasselbe — eine Überschrift und ihre Punkte. Zwei Typen hätten zwei
    Darstellungen im Fenster nach sich gezogen.
    """

    def newer_than(self, current: str = APP_VERSION) -> bool:
        return _as_tuple(self.version) > _as_tuple(current)

    def points(self, language: str = "") -> tuple[str, ...]:
        """Die Punkte in der Sprache des Fensters, sonst in der Quellsprache.

        Ein Rückfall und keine Lücke: Wer auf Italienisch arbeitet und für
        dessen Sprache noch nichts geschrieben wurde, liest lieber den
        deutschen Satz als eine Überschrift ohne Inhalt darunter.
        """
        chosen = language or get_language()
        return self.changes.get(chosen) or self.changes.get(SOURCE_LANGUAGE) or ()

    def grouped(self, language: str = "") -> tuple[Group, ...]:
        """Die Punkte gegliedert — und wo nichts gegliedert ist, als ein Block.

        Derselbe Sprachrückfall wie bei :meth:`points`. Fehlt das Feld ganz
        (eine Versionsdatei, die vor dieser Fassung geschrieben wurde), kommt
        die flache Liste als **eine** Gruppe ohne Titel zurück: Der Aufrufer
        muss dann nicht zwei Wege kennen, und der Kunde sieht dieselbe Liste
        wie bisher.
        """
        chosen = language or get_language()
        found = self.groups.get(chosen) or self.groups.get(SOURCE_LANGUAGE)
        if found:
            return found
        points = self.points(language)
        return (Group(title="", points=points),) if points else ()

    def note(self, language: str = "") -> str:
        """Der Hinweistext in der Sprache des Fensters, sonst in der Quellsprache.

        Derselbe Rückfall wie bei :meth:`points`, und aus demselben Grund: Der
        Satz steht als Überschrift über der Punkteliste, und die ist übersetzt.
        Ein deutscher Satz über einer englischen Liste sagt dem Leser vor allem,
        dass hier jemand die Hälfte vergessen hat.
        """
        chosen = language or get_language()
        return (
            self.notes_by_language.get(chosen)
            or self.notes_by_language.get(SOURCE_LANGUAGE)
            or self.notes
        )

    def package(self, key: str = "") -> Package | None:
        """Das Paket für diese Plattform, wenn die Versionsdatei eines nennt."""
        return self.packages.get(key or platform_key())

    def startable(self, key: str = "") -> Package | None:
        """Das Paket, **das sich von hier aus auch einspielen lässt.**

        Drei Gründe, warum es keines gibt, und alle drei sind kein Fehler: Die
        Versionsdatei nennt für diese Plattform keines, diese Installation
        lässt sich nicht von innen ersetzen (AppImage, ausgepacktes Archiv),
        oder Solidon läuft gar nicht als Paket, sondern aus den Quellen. Dann
        bleibt der Hinweis, und der Weg führt auf die Download-Seite.

        **Gefragt wird nach der Installationsart, nicht nach der Plattform.**
        Vorher stand hier eine Menge von Plattformschlüsseln, und ``linux``
        fehlte darin — womit die Antwort für ein Flatpak und für ein AppImage
        dieselbe war, obwohl nur das zweite sich wirklich nicht ersetzen lässt.
        Der übergebene Schlüssel wählt jetzt nur noch **welches** Paket
        zurückkommt; ob es eingespielt werden kann, entscheidet
        :func:`install_kind`.
        """
        if install_kind() not in REPLACEABLE:
            return None
        return self.packages.get(key or platform_key())


def platform_key() -> str:
    """Wie das Paket dieses Rechners in der Versionsdatei heißt."""
    if sys.platform == "win32":
        return PLATFORM_WINDOWS
    if sys.platform == "darwin":
        # ``platform.machine()`` und nicht ``sys.maxsize``: Auf einem Mac sind
        # beide Versionen 64-bittig, unterschieden werden sie am Befehlssatz.
        return PLATFORM_MACOS_ARM if platform.machine() == "arm64" else PLATFORM_MACOS_INTEL
    return PLATFORM_LINUX


def install_kind(system: str = "") -> str:
    """Wie diese Installation eingespielt worden ist.

    Aus den Quellen gefahren ist keine Installation — dann gibt es nichts, was
    ein Installer ersetzen könnte. Alles übrige entscheidet sich am System und
    unter Linux am **Format**: Ein Flatpak sagt es selbst (``/.flatpak-info``
    oder ``FLATPAK_ID``), ein AppImage über ``$APPIMAGE``, und was beides nicht
    ist, ist der ausgepackte Ordner aus dem Archiv.

    **Das System ist ein Parameter und keine Abfrage im Rumpf**, und das ist
    hier keine Stilfrage (``.claude/rules/kern.md``): Ein Zweig hinter
    ``sys.platform`` wird auf der Maschine, auf der entwickelt wird, nie
    ausgeführt und nie geprüft — genau so sind fünf Stellen entstanden, an
    denen Linux und macOS weniger konnten als Windows. So lässt sich jeder der
    drei Wege überall messen, und ``mypy --platform`` sieht alle drei.
    """
    chosen = system or sys.platform
    if not packaged():
        return KIND_SOURCE
    if chosen == "win32":
        return KIND_WINDOWS_SETUP
    if chosen == "darwin":
        return KIND_MACOS_PACKAGE
    if discover.in_flatpak():
        return KIND_FLATPAK
    # ``$APPIMAGE`` setzt der Bootloader des AppImage selbst; er nennt den Pfad
    # der Datei, die der Nutzer gestartet hat. Im ausgepackten Archiv steht er
    # nicht.
    if os.environ.get("APPIMAGE"):
        return KIND_APPIMAGE
    return KIND_TARBALL


def _as_tuple(version: str) -> tuple[int, ...]:
    parts = []
    for piece in version.split("."):
        digits = "".join(character for character in piece if character.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


def signed_payload(data: Mapping[str, Any]) -> bytes:
    """Die Bytes, über die die Unterschrift läuft — alles außer ihr selbst.

    Kanonisch, damit Bauwerkzeug und Prüfung dasselbe signieren und prüfen:
    Schlüssel sortiert, keine Leerzeichen, ASCII. Dieselbe Form wie beim
    Manifest (``activation.integrity.manifest_payload``) und aus demselben
    Grund — zwei Umsetzungen wären der Weg zu einer Unterschrift, die nur eine
    Seite versteht.

    Damit trägt sie **den ganzen Inhalt**: Version, Adresse, Hinweistext, jede
    Paketangabe und jeden Changelog-Punkt. Wer eine Prüfsumme austauscht,
    bricht sie; wer nur die Einrückung ändert, nicht.
    """
    rest = {key: value for key, value in data.items() if key != SIGNATURE_FIELD}
    return json.dumps(rest, sort_keys=True, separators=(",", ":")).encode("utf-8")


def signature_ok(data: Mapping[str, Any]) -> bool:
    """Ob die Versionsdatei von uns kommt.

    Ein fehlendes Feld ist kein Sonderfall, sondern derselbe Fall wie eine
    falsche Unterschrift: Sonst genügte es, sie wegzulassen.
    """
    raw = data.get(SIGNATURE_FIELD)
    if not isinstance(raw, str):
        return False
    try:
        signature = bytes.fromhex(raw)
    except ValueError:
        return False
    return ed25519.verify(RELEASE_PUBLIC_KEY, signed_payload(data), signature)


def check(url: str = VERSION_URL, fetch: Transport | None = None) -> Release | None:
    """Fragt einmal. Jedes Problem heißt „keine Antwort", nie ein Fehlerdialog.

    Ein Update-Hinweis, der den Start unterbricht, weil ein Server nicht
    erreichbar war, wäre schlimmer als gar keiner.
    """
    address = url
    try:
        # Derselbe Absender wie beim Paketholen weiter unten: Ohne ihn ging
        # die Anfrage als ``Python-urllib/3.13`` hinaus — manche CDNs sperren
        # das, die Prüfung scheiterte still, und der Datenschutztext
        # verspricht ein Programm-Kennzeichen statt eines Bibliotheksnamens
        # (Gesamtreview L-6).
        payload = (fetch or _get)(url, {"User-Agent": f"Solidon/{APP_VERSION}"}, {})
    except Exception as problem:  # ein Netz scheitert auf viele Arten, keine davon ist unsere
        _log.info("update check did not answer: %s", problem)
        return None

    if not signature_ok(payload):
        # Wie ein Server, der nicht antwortet: kein Fenster, kein Fehler, ein
        # Satz im Protokoll. Eine Versionsdatei, deren Unterschrift nicht
        # trägt, ist keine Versionsdatei — und wovor wir hier schützen, ist
        # genau der Fall, in dem sie überzeugend aussieht.
        _log.warning("version file is not signed by us, ignoring it")
        return None

    version = _field(payload.get("version"))
    if not version:
        return None
    url = _field(payload.get("url"))
    return Release(
        version=version,
        # Angezeigt wird nur, was auch anklickbar wäre. Ein „url", das keine
        # ist, war entweder nie eine oder soll etwas anderes sein als eine
        # Adresse — beides gehört nicht in die Statusleiste.
        url=url if url.startswith("https://") else "",
        notes=_field(payload.get("notes")),
        notes_by_language=_notes(payload.get("notes_by_language")),
        packages=_packages(payload.get("packages"), origin=address),
        changes=_changes(payload.get("changes")),
        groups=_groups(payload.get("groups")),
    )


def _notes(raw: object) -> dict[str, str]:
    """Der Hinweistext je Sprache, gestutzt auf :data:`MAX_TEXT_LENGTH`.

    Dieselbe Vorsicht wie bei :func:`_changes`: Was keine Zeichenkette ist,
    fällt weg; was zu lang ist, wird gekürzt. Eine Obergrenze für die Zahl der
    Sprachen braucht es nicht — gezeigt wird ohnehin genau eine.
    """
    if not isinstance(raw, dict):
        return {}
    found: dict[str, str] = {}
    for key, value in raw.items():
        if isinstance(value, str) and value.strip():
            found[str(key)[:16]] = _text(value)
    return found


def _changes(raw: object) -> dict[str, tuple[str, ...]]:
    """Der Changelog aus der Antwort, gestutzt auf :data:`MAX_TEXT_LENGTH`.

    Dieselbe Vorsicht wie bei jedem anderen Feld: Der Text kommt von einem
    Server und landet in einem Fenster. Was keine Liste von Zeichenketten ist,
    fällt weg; was zu lang ist, wird gekürzt; was zu viel ist, hört nach
    :data:`MAX_CHANGES` auf.
    """
    if not isinstance(raw, dict):
        return {}
    found: dict[str, tuple[str, ...]] = {}
    for key, value in raw.items():
        if not isinstance(value, list):
            continue
        points = tuple(
            _text(entry)
            for entry in value[:MAX_CHANGES]
            if isinstance(entry, str) and entry.strip()
        )
        if points:
            found[str(key)[:16]] = points
    return found


def _groups(raw: object) -> dict[str, tuple[Group, ...]]:
    """Die gegliederten Punkte aus der Antwort, mit denselben Grenzen wie flach.

    Dieselbe Vorsicht wie überall hier: Der Text kommt von einem Server und
    landet in einem Fenster. Was keine Liste von Objekten ist, fällt weg; ein
    Titel wird auf :data:`MAX_FIELD_LENGTH` gestutzt, ein Punkt auf
    :data:`MAX_TEXT_LENGTH`.

    **Gezählt wird über die Gruppen hinweg**, nicht je Gruppe: Sonst hätte
    eine Antwort mit fünfzig Überschriften à einem Punkt das Fünfzigfache von
    :data:`MAX_CHANGES` im Fenster — die Grenze gilt dem, was der Kunde liest,
    und das ist die Summe.
    """
    if not isinstance(raw, dict):
        return {}
    found: dict[str, tuple[Group, ...]] = {}
    for key, value in raw.items():
        if not isinstance(value, list):
            continue
        blocks: list[Group] = []
        left = MAX_CHANGES
        for block in value:
            if left <= 0 or not isinstance(block, dict):
                continue
            raw_points = block.get("points")
            if not isinstance(raw_points, list):
                continue
            points = tuple(
                _text(entry)
                for entry in raw_points[:left]
                if isinstance(entry, str) and entry.strip()
            )
            if not points:
                continue
            left -= len(points)
            title = block.get("title")
            blocks.append(
                Group(
                    title=str(title)[:MAX_FIELD_LENGTH] if isinstance(title, str) else "",
                    points=points,
                )
            )
        if blocks:
            found[str(key)[:16]] = tuple(blocks)
    return found


def _packages(raw: object, *, origin: str) -> dict[str, Package]:
    """Die Pakete aus der Antwort — verworfen wird alles, was nicht passt.

    **Der Rechnername muss derselbe sein wie der der Versionsdatei.** Das ist
    die eine Auflage, die trägt: Die Prüfsumme steht in derselben Datei wie
    die Adresse und schützt darum nicht gegen einen Server, der beide fälscht.
    Ein Zertifikat für diesen Namen zu haben ist die höhere Hürde, und HTTPS
    verlangt sie — solange die Adresse nirgendwo anders hinzeigt.

    Ein Paket ohne Prüfsumme ist keines. Es würde geladen und gestartet, ohne
    dass irgendetwas es geprüft hätte; das ist genau der Weg, den §37.2
    ausschließt. Es fehlt dann in der Liste, und die Anwendung zeigt auf die
    Download-Seite, statt etwas anzubieten.
    """
    if not isinstance(raw, dict):
        return {}
    host = urlsplit(origin).netloc.lower()
    found: dict[str, Package] = {}
    for key, value in raw.items():
        if not isinstance(value, dict):
            continue
        address = _field(value.get("url"))
        digest = _field(value.get("sha256")).lower()
        parts = urlsplit(address)
        if parts.scheme != "https" or parts.netloc.lower() != host:
            _log.info("update package %s ignored: %s is not on %s", key, address, host)
            continue
        if len(digest) != 64 or not all(character in "0123456789abcdef" for character in digest):
            _log.info("update package %s ignored: no usable checksum", key)
            continue
        found[str(key)[:MAX_FIELD_LENGTH]] = Package(
            file=_field(value.get("file")),
            url=address,
            size=_as_size(value.get("size")),
            sha256=digest,
        )
    return found


def _as_size(value: object) -> int:
    """Die Größenangabe als Zahl, oder 0 für „steht nicht da"."""
    if not isinstance(value, int | str) or isinstance(value, bool):
        return 0
    try:
        size = int(value)
    except ValueError:
        return 0
    return size if 0 < size <= MAX_PACKAGE_BYTES else 0


def _field(value: object) -> str:
    """Ein Feld aus der Antwort, gestutzt auf das, was hineinpasst."""
    return str(value if value is not None else "").strip()[:MAX_FIELD_LENGTH]


def _text(value: object) -> str:
    """Ein Fließtext aus der Antwort — großzügiger gestutzt, und sichtbar.

    Zwei Unterschiede zu :func:`_field`, beide aus demselben Fall gelernt:

    * Die Grenze ist :data:`MAX_TEXT_LENGTH`, nicht die der Statuszeile.
    * **Gekürzt wird an einer Wortgrenze und mit einem Auslassungszeichen.**
      Wo etwas fehlt, soll es zu sehen sein; ein Satz, der lautlos mitten im
      Wort endet, sieht aus wie ein Programmfehler statt wie eine Schranke.
    """
    text = str(value if value is not None else "").strip()
    if len(text) <= MAX_TEXT_LENGTH:
        return text
    gestutzt = text[:MAX_TEXT_LENGTH]
    # Bis zum letzten Leerzeichen zurück, aber nicht beliebig weit: Ein Text
    # ohne jedes Leerzeichen bekommt sonst gar nichts zu sehen.
    luecke = gestutzt.rfind(" ")
    if luecke > MAX_TEXT_LENGTH // 2:
        gestutzt = gestutzt[:luecke]
    return gestutzt.rstrip(" ,;:.") + "…"


def _get(url: str, headers: dict[str, str], _payload: dict[str, Any]) -> dict[str, Any]:
    import urllib.request

    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as answer:
        # Ein Byte mehr als erlaubt wird noch gelesen, damit „zu lang" von
        # „gerade noch" unterscheidbar bleibt.
        raw = answer.read(MAX_ANSWER_BYTES + 1)
    if len(raw) > MAX_ANSWER_BYTES:
        raise ValueError("version file is too large")
    return dict(json.loads(raw.decode("utf-8")))


# --- Das Paket holen ------------------------------------------------------------


def target_dir() -> Path:
    """Wohin das Paket geladen wird.

    In den Zwischenspeicher und nicht neben die Anwendung: Dort darf gelöscht
    werden, und genau das passiert vor jedem Lauf. Ein Paket, das einmal
    gestartet wurde, hat seine Aufgabe erfüllt — liegen bleiben soll es nicht,
    es wiegt so viel wie die Anwendung selbst.
    """
    return ensure_dir(user_cache_dir() / "updates")


def _safe_name(name: str, fallback: str) -> str:
    """Aus dem Namen der Versionsdatei einen Dateinamen, dem man trauen kann.

    Er kommt von einem Server. Ein Name mit ``..`` und Trennzeichen darin ist
    ein gültiger JSON-String, und wer ihn ungeprüft an einen Pfad hängt,
    schreibt genau dorthin. Übrig bleibt der letzte Namensteil, und von dem nur
    Zeichen, die in einem Paketnamen vorkommen.
    """
    tail = name.replace("\\", "/").rsplit("/", 1)[-1]
    cleaned = "".join(
        character for character in tail if character.isalnum() or character in "._-+"
    ).lstrip(".")
    return cleaned[:120] or fallback


def download(
    package: Package,
    *,
    progress: ProgressFn | None = None,
    cancelled: CancelToken | None = None,
    opener: Callable[..., Any] | None = None,
) -> Path:
    """Holt das Paket und gibt es erst zurück, wenn die Prüfsumme stimmt.

    Gelesen wird in Häppchen, weil zweierlei daran hängt: der Fortschritt, den
    jemand sieht, und das Abbrechen, das sofort greifen soll. Gerechnet wird
    die Prüfsumme im selben Durchgang — ein zweiter Lauf über 180 MB wäre eine
    Minute, die niemand geschenkt bekommt.

    Was hier nicht passiert: starten. Diese Funktion holt und prüft, nichts
    weiter. Wer sie ruft, hat danach eine Datei und immer noch die Wahl.
    """
    folder = target_dir()
    _clear(folder)
    file = folder / _safe_name(package.file, "solidon-update")
    open_url = opener if callable(opener) else urllib.request.urlopen
    request = urllib.request.Request(package.url, headers={"User-Agent": f"Solidon/{APP_VERSION}"})

    try:
        answer = open_url(request, timeout=DOWNLOAD_TIMEOUT_SECONDS)
    except urllib.error.HTTPError as error:
        # Ein HTTPError ist selbst eine offene Antwort; wer ihn nur auswertet,
        # lässt einen Socket zurück (derselbe Fund wie in ingest/fetch.py).
        error.close()
        raise ExternalToolError(
            tool="update",
            detail=_("Der Server hat das Paket nicht herausgegeben."),
            suggestions=(RETRY, OPEN_DOWNLOAD_PAGE),
            values={"url": package.url, "status": error.code},
        ) from error
    except (urllib.error.URLError, OSError) as error:
        raise ExternalToolError(
            tool="update",
            detail=_("Die Adresse war nicht erreichbar."),
            suggestions=(RETRY, OPEN_DOWNLOAD_PAGE),
            values={"url": package.url, "reason": str(error)},
        ) from error

    expected = package.size or MAX_PACKAGE_BYTES
    digest = hashlib.sha256()
    read = 0
    try:
        with answer, file.open("wb") as sink:
            while True:
                if cancelled is not None:
                    cancelled.raise_if_cancelled()
                chunk = answer.read(CHUNK_BYTES)
                if not chunk:
                    break
                read += len(chunk)
                if read > expected:
                    raise ExternalToolError(
                        tool="update",
                        detail=_("Das Paket ist größer als angekündigt."),
                        suggestions=(OPEN_DOWNLOAD_PAGE,),
                        values={"url": package.url, "expected": expected, "read": read},
                    )
                sink.write(chunk)
                digest.update(chunk)
                if progress is not None:
                    progress(read / expected, _megabytes(read, package.size))
    except OSError as error:
        _remove(file)
        raise FileWriteError(detail=str(error), values={"path": str(file)}) from error
    except BaseException:
        # Abbruch, zu großes Paket, was auch immer: eine halbe Datei bleibt
        # nicht liegen. Sie sähe aus wie eine ganze — der Name stimmt, die
        # Endung stimmt —, und der nächste Lauf fände sie vor.
        _remove(file)
        raise

    if package.size and read != package.size:
        _remove(file)
        raise ExternalToolError(
            tool="update",
            detail=_("Das Paket ist unvollständig angekommen."),
            suggestions=(RETRY, OPEN_DOWNLOAD_PAGE),
            values={"url": package.url, "expected": package.size, "read": read},
        )
    if digest.hexdigest() != package.sha256:
        _remove(file)
        raise ExternalToolError(
            tool="update",
            detail=_("Das geladene Paket ist beschädigt und wurde gelöscht."),
            suggestions=(RETRY, OPEN_DOWNLOAD_PAGE),
            values={"url": package.url, "expected": package.sha256, "got": digest.hexdigest()},
        )

    _log.info("update package verified: %s (%d bytes)", file.name, read)
    return file


def runs_unattended() -> bool:
    """Läuft das Einspielen ohne Fragen durch — und startet Solidon danach wieder?

    Zwei der drei Wege tun das: Die Setup-Datei bekommt ``/SILENT`` und den
    eigenen Neustart-Eintrag, das Flatpak-Bundle wird eingespielt und mit
    ``flatpak run`` zurückgeholt. Der dritte ist Apples Installer — er zeigt
    den Lizenzvertrag, lässt den Ort wählen und startet danach nichts
    (Entscheidung Robert, 28.08.2026: der ``.pkg``-Weg bleibt).

    Der Dialog braucht die Auskunft für **einen Satz**, und der Satz ist keine
    Kosmetik: Wer „dann startet das Installationsprogramm" liest und
    stattdessen nichts sieht, hält das Update für gescheitert und klickt ein
    zweites Mal.
    """
    return install_kind() in (KIND_WINDOWS_SETUP, KIND_FLATPAK)


def _flatpak_is_user(info: str | None = None) -> bool:
    """Liegt diese Flatpak-Installation im Nutzerprofil?

    **Der Geltungsbereich wird gelesen, nicht geraten**, und daran hängt mehr
    als eine Kleinigkeit: ``--user`` auf eine systemweite Installation legt
    eine **zweite** daneben, statt die vorhandene zu ersetzen. Der Nutzer hätte
    danach zwei Fassungen, von denen die alte weiter startet, und keinen
    Hinweis darauf, warum das Update nichts geändert hat.

    ``/.flatpak-info`` nennt unter ``app-path`` den Ort des eingehängten
    Anwendungsordners. Eine systemweite Installation liegt unter
    ``/var/lib/flatpak``, eine im Profil unter dem Heimatverzeichnis.

    Ist die Datei nicht lesbar, gilt das Profil: Es ist die Wahl, die ohne
    Rechte auskommt. Sie kann im schlimmsten Fall eine zweite Installation
    anlegen — die andere Richtung scheitert an einer Rechteabfrage, die
    niemand sieht, weil Solidon zu diesem Zeitpunkt beendet ist.

    Der Inhalt ist ein Parameter, damit beide Lagen ohne Flatpak messbar sind.
    """
    raw = info
    if raw is None:
        try:
            raw = Path("/.flatpak-info").read_text(encoding="utf-8")
        except OSError as problem:
            _log.info("cannot read /.flatpak-info: %s", problem)
            return True
    for line in raw.splitlines():
        name, found, value = line.partition("=")
        if found and name.strip() == "app-path":
            return not value.strip().startswith("/var/lib/flatpak")
    return True


def _flatpak_command(file: Path) -> list[str]:
    """Das Bundle einspielen und Solidon danach wieder starten.

    Beides in **einer** Kette auf dem Rechner, und beides muss dort laufen:
    ``flatpak-spawn --host`` überlebt den Sandkasten, der gleich danach endet.
    Zwei getrennte Aufrufe gingen nicht — der zweite darf erst laufen, wenn der
    erste durch ist, und dazwischen ist Solidon längst beendet.

    ``flatpak run`` am Ende ist dasselbe Versprechen wie ``/RESTARTAPP=1`` unter
    Windows: Wer ein Update anstößt, will danach weiterarbeiten und nicht vor
    einem geschlossenen Programm sitzen.

    **Ein Repo braucht das nicht.** ``flatpak install`` nimmt die Bundle-Datei
    unmittelbar und aktualisiert damit die vorhandene Installation — genau das
    Paket, das die Download-Seite ohnehin anbietet.

    Und der Pfad stimmt auf beiden Seiten: Der Zwischenspeicher liegt unter
    ``$XDG_CACHE_HOME``, und das ist im Flatpak ``~/.var/app/<kennung>/cache``
    — derselbe Pfad, den der Rechner sieht. Er wird trotzdem gequotet: Er
    trägt den Dateinamen aus der Versionsdatei, und der kommt von einem Server
    (``_safe_name`` hat ihn entschärft, aber eine Shell-Zeile baut man nicht
    auf ein Vertrauen, das eine andere Funktion herstellt).
    """
    scope = "--user" if _flatpak_is_user() else "--system"
    identifier = os.environ.get("FLATPAK_ID") or APP_ID
    line = (
        f"flatpak install {scope} --assumeyes {shlex.quote(str(file))}"
        f" && flatpak run {shlex.quote(identifier)}"
    )
    return discover.on_host(["sh", "-c", line])


def _install_command(file: Path) -> list[str]:
    """Der Befehl, der dieses Paket einspielt — je Installationsart ein anderer.

    Hier stand eine Zeile mit einer Verzweigung darin: Windows startete die
    Datei, alles andere gab sie an ``open``. Das war für macOS richtig und für
    Linux nie erreichbar, weil dort gar kein Paket angeboten wurde.

    Drei Wege, und jeder ist der, den sein Format vorsieht: Die Setup-Datei
    nimmt Schalter (:data:`SETUP_ARGUMENTS`), das ``.pkg`` geht an ``open`` und
    zeigt Apples Installer, das Flatpak-Bundle geht an ``flatpak install``.
    """
    kind = install_kind()
    if kind == KIND_WINDOWS_SETUP:
        return [str(file), *SETUP_ARGUMENTS]
    if kind == KIND_FLATPAK:
        return _flatpak_command(file)
    # macOS: ``open`` übergibt das Paket dem Installer des Systems, der den
    # Lizenzvertrag zeigt und den Ort wählen lässt (Entscheidung Robert,
    # 28.08.2026 — der Weg bleibt, wie er ist).
    return ["open", str(file)]


def start_installer(file: Path) -> None:
    """Spielt das geholte Paket ein. Danach beendet sich Solidon — nicht hier.

    Getrennt mit Absicht: Was mit dem offenen Dokument geschieht, entscheidet
    das Fenster und nicht der Kern. Diese Funktion startet ein Programm und
    kehrt zurück.
    """
    if not file.is_file():
        raise ExternalToolError(
            tool="update",
            detail=_("Das Paket liegt nicht mehr da, wo es geladen wurde."),
            suggestions=(RETRY, OPEN_DOWNLOAD_PAGE),
            values={"path": str(file)},
        )
    command = _install_command(file)
    try:
        # Kein Warten auf das Ende: Der Installer läuft weiter, wenn Solidon
        # nicht mehr da ist — darauf zu warten hieße, auf das eigene Ende zu
        # warten.
        subprocess.Popen(command)
    except OSError as error:
        raise ExternalToolError(
            tool="update",
            detail=_("Das Installationsprogramm ließ sich nicht starten."),
            suggestions=(OPEN_DOWNLOAD_PAGE,),
            values={"path": str(file), "reason": str(error)},
        ) from error


def _megabytes(done: int, total: int) -> str:
    """Der Fortschrittstext. Megabyte, weil ein Anteil allein nichts über die
    Leitung sagt."""
    if total:
        return f"{done / 1048576:.0f} / {total / 1048576:.0f} MB"
    return f"{done / 1048576:.0f} MB"


def _clear(folder: Path) -> None:
    """Räumt den Zwischenspeicher, bevor etwas Neues hineinkommt."""
    for old in folder.glob("*"):
        if old.is_file():
            _remove(old)


def _remove(file: Path) -> None:
    """Löscht, und schweigt, wenn es nicht geht — es ist der Zwischenspeicher."""
    try:
        file.unlink(missing_ok=True)
    except OSError as problem:
        _log.info("could not remove %s: %s", file, problem)
