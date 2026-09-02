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
import importlib
import json
import os
import platform
import shlex
import stat
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from time import monotonic, sleep
from typing import Any, BinaryIO, Final, cast
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
from app.core.http import (
    READ_CHUNK_BYTES,
    HttpBoundaryError,
    RejectRedirects,
    ResponseDeadlineError,
    ResponseTooLargeError,
    deadline_after,
    iter_limited,
    read_limited,
    response_url,
    same_origin,
    validate_http_url,
)
from app.core.install import packaged
from app.core.json_boundary import StrictJsonError
from app.core.json_boundary import loads as load_json
from app.core.log import get_logger, redact_external, redact_url
from app.core.paths import user_cache_dir
from app.core.process import detached_process_options
from app.core.types import CancelToken, ProgressFn
from app.i18n import SOURCE_LANGUAGE, _, get_language

_windows_ctypes: Any = None
_windows_msvcrt: Any = None
if os.name == "nt":
    import ctypes as _native_ctypes
    import msvcrt as _native_msvcrt

    _windows_ctypes = _native_ctypes
    _windows_msvcrt = _native_msvcrt

_log = get_logger(__name__)
CHUNK_BYTES: Final = READ_CHUNK_BYTES
_UPDATE_OPENER = urllib.request.build_opener(RejectRedirects())


def _open_update(request: urllib.request.Request, *, timeout: float) -> Any:
    """Öffnet eine feste Update-Adresse ohne Weiterleitung."""
    return _UPDATE_OPENER.open(request, timeout=timeout)


_DEFAULT_OPEN_UPDATE = _open_update

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
MAX_CHANGES: Final = 120


def _room_for_the_version_file() -> int:
    """Was die Versionsdatei im schlimmsten erlaubten Fall wiegen darf.

    Hundertzwanzig Punkte à achthundert Zeichen — mehr lässt das eigene Format nicht
    zu — in **jeder** eingecheckten Sprache, und das **zweimal**: ``changes``
    trägt die flache Liste, ``groups`` dieselben Punkte gegliedert. Beide
    stehen nebeneinander in der Datei, weil jede ausgelieferte Fassung sie
    liest und der Leser bis 0.2.2 nur die flache kennt. Dazu noch einmal so
    viel Luft für Überschriften, Kopffelder, Paketliste, Unterschrift und die
    Anführungszeichen des Formats.

    **Der Faktor stand bis zum 02.09.2026 auf 2 und kannte nur ``changes``.**
    Damit rechnete die Ableitung die Hälfte dessen, was das eigene Format
    schreiben darf — derselbe Widerspruch, der sie überhaupt erst nötig
    gemacht hat: eine Datei, die die Anwendung erzeugen kann und selbst nicht
    mehr liest.

    Die Sprachzahl kommt aus dem Verzeichnis, weil eine weitere Sprache eine
    Datei ist und sonst nichts (``AGENTS.md``): Wer eine hinzufügt, soll nicht
    auch noch hier nachrechnen müssen. Der Import steht in der Funktion, damit
    das Modul ohne Katalogverzeichnis ladbar bleibt.
    """
    from app.i18n.catalog import available_languages

    return 3 * MAX_CHANGES * MAX_TEXT_LENGTH * max(len(available_languages()), 1)


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
#: nicht selbst. macOS bleibt ebenfalls beim Download-Hinweis: ``open`` reicht
#: ein Dokument über LaunchServices an die Installer-App weiter. Diese erbt
#: Solidons geprüften Dateideskriptor nicht; ``/dev/fd/N`` würde dort deshalb
#: einen anderen oder gar keinen Deskriptor bezeichnen. Ein erneutes Öffnen des
#: Cachepfads wäre dagegen derselbe Austauschspalt, den die Startprüfung
#: schließen soll. Erkannt werden alle Arten trotzdem — sonst bekäme ein
#: AppImage-Nutzer ein ``flatpak install``, das scheitern muss, und die
#: Auskunft „geht hier nicht" wäre eine Vermutung statt einer Feststellung.
REPLACEABLE: Final = frozenset({KIND_WINDOWS_SETUP, KIND_FLATPAK})

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

    ``file`` steht in der Meldung, ``url`` wird geholt, ``size`` deckelt das
    Lesen und ``sha256`` entscheidet, ob das Geholte je gestartet wird. Die
    drei letzten Felder halten zusätzlich genau die signierte Freigabe fest,
    die unmittelbar vor dem Start noch einmal geprüft wird.
    """

    file: str
    url: str
    size: int = 0
    sha256: str = ""
    release_key: str = ""
    signed_release: bytes = b""
    release_signature: bytes = b""


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


#: Wie viele Zahlen eine Fassung vergleichbar machen. Drei sind es im Haus,
#: die vierte ist Luft für eine Nachlieferung wie ``0.3.0.1``.
_VERSION_SEGMENTS: Final = 4

#: Was vor der endgültigen Fassung kommt, und in welcher Reihenfolge.
#:
#: Die Zahl daneben ist kleiner als die der endgültigen Fassung — ``0.3.0rc1``
#: liegt damit **vor** ``0.3.0`` und nicht dahinter.
_PRERELEASE_RANK: Final[dict[str, int]] = {"a": 0, "alpha": 0, "b": 1, "beta": 1, "rc": 2, "c": 2}
_FINAL_RANK: Final = 3


def _as_tuple(version: str) -> tuple[int, ...]:
    """Eine Fassung als vergleichbare Zahlenfolge.

    **Zwei Fälle standen bis zum 02.09.2026 falsch**, und beide fielen nur
    deshalb nicht auf, weil bisher keine Vorabfassung veröffentlicht wurde:

    * Je Abschnitt wurden schlicht die Ziffern eingesammelt. ``0.3.0rc1``
      wurde damit zu ``(0, 3, 1)`` und galt als **neuer** als ``0.3.0`` — der
      Kunde bekäme ein Update auf etwas angeboten, das vor seiner eigenen
      Fassung liegt.
    * Fehlende Abschnitte fehlten auch im Ergebnis: ``0.3`` ergab ``(0, 3)``
      und war damit kleiner als ``(0, 3, 0)``, obwohl beides dieselbe Fassung
      meint.

    Aufgefüllt wird deshalb auf :data:`_VERSION_SEGMENTS` Stellen, und hinten
    stehen zwei weitere Zahlen: der Rang der Vorabfassung und ihre Nummer. Für
    eine endgültige Fassung sind das ``(3, 0)`` — größer als jedes ``rc``.
    """
    numbers: list[int] = []
    rank = _FINAL_RANK
    counter = 0
    for piece in version.strip().split("."):
        digits = ""
        index = 0
        while index < len(piece) and piece[index].isdigit():
            digits += piece[index]
            index += 1
        numbers.append(int(digits) if digits else 0)
        rest = piece[index:].strip().lower()
        if rest and rank == _FINAL_RANK:
            marker = "".join(character for character in rest if not character.isdigit())
            trailing = "".join(character for character in rest if character.isdigit())
            if marker in _PRERELEASE_RANK:
                rank = _PRERELEASE_RANK[marker]
                counter = int(trailing) if trailing else 0
    numbers = numbers[:_VERSION_SEGMENTS]
    numbers.extend([0] * (_VERSION_SEGMENTS - len(numbers)))
    return (*numbers, rank, counter)


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
        packages=_packages(payload.get("packages"), origin=address, release=payload),
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


def _packages(
    raw: object,
    *,
    origin: str,
    release: Mapping[str, Any] | None = None,
) -> dict[str, Package]:
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

    **Ohne brauchbare Größe gilt dasselbe, und zwar seit dem 02.09.2026.**
    ``_as_size`` gibt für eine fehlende oder unsinnige Angabe 0 zurück, und
    damit lief das Paket in eine Sackgasse: :func:`download` prüft die Länge
    nur, *wenn* eine angekündigt war, und ließ es durch — :func:`_verified_package`
    prüft sie beim Start unbedingt und wies dieselbe Datei mit „Das
    Update-Paket wurde nach dem Herunterladen verändert" ab. Ein Paket, das
    sich laden, aber nie starten lässt, ist schlechter als keines: Der Kunde
    hat gewartet, hat einen Verdacht auf Manipulation gelesen und steht
    danach dort, wo die Download-Seite ihn gleich hingeführt hätte.
    """
    if not isinstance(raw, dict):
        return {}
    try:
        checked_origin = validate_http_url(
            origin,
            allow_http=False,
            allow_query=False,
            allow_fragment=False,
        )
    except ValueError:
        return {}
    host = urlsplit(checked_origin).hostname or ""
    signed_release = signed_payload(release) if release is not None else b""
    raw_signature = release.get(SIGNATURE_FIELD) if release is not None else None
    try:
        release_signature = bytes.fromhex(raw_signature) if isinstance(raw_signature, str) else b""
    except ValueError:
        release_signature = b""
    found: dict[str, Package] = {}
    for key, value in raw.items():
        if not isinstance(value, dict):
            continue
        address = _field(value.get("url"))
        digest = _field(value.get("sha256")).lower()
        try:
            checked_address = validate_http_url(
                address,
                allow_http=False,
                allow_query=False,
                allow_fragment=False,
            )
        except ValueError:
            checked_address = ""
        if not checked_address or not same_origin(checked_origin, checked_address):
            _log.info("update package %s ignored: %s is not on %s", key, address, host)
            continue
        if len(digest) != 64 or not all(character in "0123456789abcdef" for character in digest):
            _log.info("update package %s ignored: no usable checksum", key)
            continue
        size = _as_size(value.get("size"))
        if not size:
            _log.info("update package %s ignored: no usable size", key)
            continue
        found[str(key)[:MAX_FIELD_LENGTH]] = Package(
            file=_field(value.get("file")),
            url=checked_address,
            size=size,
            sha256=digest,
            release_key=str(key)[:MAX_FIELD_LENGTH],
            signed_release=signed_release,
            release_signature=release_signature,
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
    address = validate_http_url(
        url,
        allow_http=False,
        allow_query=False,
        allow_fragment=False,
    )
    deadline = deadline_after(TIMEOUT_SECONDS)
    request = urllib.request.Request(address, headers=headers)
    with _open_update(request, timeout=TIMEOUT_SECONDS) as answer:
        final = validate_http_url(response_url(answer, address), allow_http=False)
        if not same_origin(address, final):
            raise ValueError("version endpoint redirected")
        raw = read_limited(
            answer,
            limit=MAX_ANSWER_BYTES,
            deadline=deadline,
            require_timeout=_open_update is _DEFAULT_OPEN_UPDATE,
        )
    return dict(load_json(raw, max_bytes=MAX_ANSWER_BYTES))


# --- Das Paket holen ------------------------------------------------------------


def target_dir() -> Path:
    """Wohin das Paket geladen wird.

    In den Zwischenspeicher und nicht neben die Anwendung: Dort darf gelöscht
    werden, und genau das passiert vor jedem Lauf. Ein Paket, das einmal
    gestartet wurde, hat seine Aufgabe erfüllt — liegen bleiben soll es nicht,
    es wiegt so viel wie die Anwendung selbst.
    """
    folder = user_cache_dir() / "updates"
    junction = getattr(folder, "is_junction", None)
    if folder.is_symlink() or (callable(junction) and junction()):
        raise FileWriteError(detail=_("Der Update-Zwischenspeicher ist eine Verknüpfung."))
    try:
        folder.mkdir(mode=0o700, parents=True, exist_ok=True)
        root = folder.parent.resolve(strict=True)
        resolved = folder.resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, ValueError) as problem:
        raise FileWriteError(
            detail=_("Der Update-Zwischenspeicher liegt außerhalb des Nutzerordners."),
            values={"path": str(folder)},
        ) from problem
    # Verglichen wird mit dem aufgelösten Elternpfad plus dem eigenen Namen,
    # nicht mit ``folder`` selbst: Ein 8.3-Kurzname im Nutzerordner
    # (``ROSCHN~1``) löst sich zum langen Namen auf, ohne eine Verknüpfung zu
    # sein — und sperrte so jedes Update auf einer Maschine, deren
    # ``%LOCALAPPDATA%`` den Kurznamen trägt (gemessen 02.09.2026).
    if resolved != root / folder.name:
        raise FileWriteError(detail=_("Der Update-Zwischenspeicher ist eine Verknüpfung."))
    if os.name != "nt":
        metadata = resolved.stat()
        getuid = cast(Callable[[], int], vars(os)["getuid"])
        if metadata.st_uid != getuid():
            raise FileWriteError(
                detail=_("Der Update-Zwischenspeicher gehört einem anderen Nutzer.")
            )
        try:
            resolved.chmod(0o700)
        except OSError as problem:
            raise FileWriteError(
                detail=_("Der Update-Zwischenspeicher ließ sich nicht privat absichern.")
            ) from problem
    return resolved


def _descriptor_path(descriptor: int) -> Path | None:
    """Der kanonische Pfad eines offenen Handles, soweit die Plattform ihn anbietet."""
    if os.name == "nt":
        kernel32 = _windows_ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.GetFinalPathNameByHandleW.argtypes = (
            _windows_ctypes.c_void_p,
            _windows_ctypes.c_wchar_p,
            _windows_ctypes.c_uint32,
            _windows_ctypes.c_uint32,
        )
        kernel32.GetFinalPathNameByHandleW.restype = _windows_ctypes.c_uint32
        handle = _windows_ctypes.c_void_p(_windows_msvcrt.get_osfhandle(descriptor))
        length = kernel32.GetFinalPathNameByHandleW(handle, None, 0, 0)
        if not length:
            return None
        buffer = _windows_ctypes.create_unicode_buffer(length + 1)
        if not kernel32.GetFinalPathNameByHandleW(handle, buffer, len(buffer), 0):
            return None
        name = buffer.value
        if name.startswith("\\\\?\\UNC\\"):
            name = "\\\\" + name[8:]
        elif name.startswith("\\\\?\\"):
            name = name[4:]
        return Path(name).resolve(strict=True)
    descriptor_path = Path("/proc/self/fd") / str(descriptor)
    return descriptor_path.resolve(strict=True) if descriptor_path.exists() else None


def _posix_lock(descriptor: int, *, exclusive: bool) -> None:
    """Sperrt eine Datei über das erst auf POSIX geladene Systemmodul."""
    module = importlib.import_module("fcntl")
    flock = cast(Callable[[int, int], None], vars(module)["flock"])
    if exclusive:
        operation = int(vars(module)["LOCK_EX"]) | int(vars(module)["LOCK_NB"])
    else:
        operation = int(vars(module)["LOCK_UN"])
    flock(descriptor, operation)


@contextmanager
def _cache_lock(folder: Path) -> Any:
    """Sperrt Bereinigung, Download und atomaren Wechsel pro Nutzerprofil."""
    lock_path = folder.parent / ".solidon-updates.lock"
    flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(lock_path, flags, 0o600)
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise FileWriteError(detail=_("Die Update-Sperre ist keine gewöhnliche Datei."))
        opened = _descriptor_path(descriptor)
        expected_lock = folder.parent.resolve(strict=True) / lock_path.name
        if opened is not None and opened != expected_lock:
            raise FileWriteError(detail=_("Die Update-Sperre ist eine Verknüpfung."))
        if os.name != "nt":
            os.fchmod(descriptor, 0o600)
        deadline = monotonic() + 10.0
        while True:
            try:
                if os.name == "nt":
                    _windows_msvcrt.locking(descriptor, _windows_msvcrt.LK_NBLCK, 1)
                else:
                    _posix_lock(descriptor, exclusive=True)
                break
            except OSError as problem:
                if monotonic() >= deadline:
                    raise FileWriteError(
                        detail=_("Ein anderer Update-Vorgang benutzt den Zwischenspeicher.")
                    ) from problem
                sleep(0.05)
        try:
            yield
        finally:
            if os.name == "nt":
                _windows_msvcrt.locking(descriptor, _windows_msvcrt.LK_UNLCK, 1)
            else:
                _posix_lock(descriptor, exclusive=False)
    finally:
        os.close(descriptor)


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
    file = folder / _safe_name(package.file, "solidon-update")
    open_url = opener if callable(opener) else _open_update
    strict_timeout = opener is None
    address = validate_http_url(
        package.url,
        allow_http=False,
        allow_query=False,
        allow_fragment=False,
    )
    deadline = deadline_after(DOWNLOAD_TIMEOUT_SECONDS)
    request = urllib.request.Request(address, headers={"User-Agent": f"Solidon/{APP_VERSION}"})

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
            values={"url": redact_url(address), "status": error.code},
        ) from error
    except (urllib.error.URLError, OSError) as error:
        raise ExternalToolError(
            tool="update",
            detail=_("Die Adresse war nicht erreichbar."),
            suggestions=(RETRY, OPEN_DOWNLOAD_PAGE),
            values={"url": redact_url(address), "reason": redact_external(error)},
        ) from error

    with _cache_lock(folder):
        return _store_download(
            answer,
            package,
            file,
            address=address,
            deadline=deadline,
            strict_timeout=strict_timeout,
            progress=progress,
            cancelled=cancelled,
        )


_VERIFIED_PACKAGES: dict[Path, Package] = {}


def _store_download(
    answer: Any,
    package: Package,
    file: Path,
    *,
    address: str,
    deadline: float,
    strict_timeout: bool,
    progress: ProgressFn | None,
    cancelled: CancelToken | None,
) -> Path:
    """Schreibt einen Download exklusiv, prüft ihn und wechselt ihn atomar ein."""
    _clear(file.parent)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{file.name}.",
        suffix=".part",
        dir=file.parent,
    )
    temporary = Path(temporary_name)
    expected = package.size or MAX_PACKAGE_BYTES
    digest = hashlib.sha256()
    read = 0
    try:
        with os.fdopen(descriptor, "wb") as sink, answer:
            opened_temporary = _descriptor_path(sink.fileno())
            if opened_temporary is not None and opened_temporary != temporary.resolve(strict=True):
                raise FileWriteError(
                    detail=_("Der Update-Zwischenspeicher wechselte während des Downloads.")
                )
            final = validate_http_url(response_url(answer, address), allow_http=False)
            if not same_origin(address, final):
                raise ExternalToolError(
                    tool="update",
                    detail=_("Der Server hat das Paket nicht herausgegeben."),
                    suggestions=(RETRY, OPEN_DOWNLOAD_PAGE),
                    values={"url": redact_url(address)},
                )
            for chunk in iter_limited(
                answer,
                limit=expected,
                deadline=deadline,
                require_timeout=strict_timeout,
                chunk_size=CHUNK_BYTES,
            ):
                if cancelled is not None:
                    cancelled.raise_if_cancelled()
                read += len(chunk)
                try:
                    sink.write(chunk)
                except OSError as problem:
                    raise FileWriteError(
                        detail=str(problem), values={"path": str(file)}
                    ) from problem
                digest.update(chunk)
                if progress is not None:
                    progress(read / expected, _megabytes(read, package.size))
            sink.flush()
            os.fsync(sink.fileno())
    except ResponseTooLargeError as error:
        _remove(temporary)
        raise ExternalToolError(
            tool="update",
            detail=_("Das Paket ist größer als angekündigt."),
            suggestions=(OPEN_DOWNLOAD_PAGE,),
            values={"url": redact_url(address), "expected": expected, "read": error.received},
        ) from error
    except (ResponseDeadlineError, OSError, HttpBoundaryError) as error:
        _remove(temporary)
        raise ExternalToolError(
            tool="update",
            detail=_("Die Adresse war nicht erreichbar."),
            suggestions=(RETRY, OPEN_DOWNLOAD_PAGE),
            values={"url": redact_url(address), "reason": redact_external(error)},
        ) from error
    except BaseException:
        # Abbruch, zu großes Paket, was auch immer: eine halbe Datei bleibt
        # nicht liegen. Sie sähe aus wie eine ganze — der Name stimmt, die
        # Endung stimmt —, und der nächste Lauf fände sie vor.
        _remove(temporary)
        raise

    if package.size and read != package.size:
        _remove(temporary)
        raise ExternalToolError(
            tool="update",
            detail=_("Das Paket ist unvollständig angekommen."),
            suggestions=(RETRY, OPEN_DOWNLOAD_PAGE),
            values={"url": redact_url(address), "expected": package.size, "read": read},
        )
    if digest.hexdigest() != package.sha256:
        _remove(temporary)
        raise ExternalToolError(
            tool="update",
            detail=_("Das geladene Paket ist beschädigt und wurde gelöscht."),
            suggestions=(RETRY, OPEN_DOWNLOAD_PAGE),
            values={
                "url": redact_url(address),
                "expected": package.sha256,
                "got": digest.hexdigest(),
            },
        )

    try:
        temporary.replace(file)
        if os.name != "nt":
            folder_descriptor = os.open(file.parent, os.O_RDONLY)
            try:
                os.fsync(folder_descriptor)
            finally:
                os.close(folder_descriptor)
    except OSError as problem:
        _remove(file)
        raise FileWriteError(detail=str(problem), values={"path": str(file)}) from problem
    finally:
        _remove(temporary)
    _VERIFIED_PACKAGES[file.resolve(strict=True)] = package
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


def _flatpak_command(file: Path, *, forwarded_descriptor: int | None = None) -> list[str]:
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

    Beim echten Start reist kein erneut aufzulösender Cachepfad nach draußen,
    sondern der bereits geprüfte Deskriptor über ``--forward-fd``. Der dafür
    gebildete ``/proc/self/fd``-Pfad wird trotzdem gequotet; auch ein intern
    gebauter Wert rechtfertigt keine ungequotete Shell-Zeile.
    """
    scope = "--user" if _flatpak_is_user() else "--system"
    identifier = os.environ.get("FLATPAK_ID") or APP_ID
    line = (
        f"flatpak install {scope} --assumeyes {shlex.quote(str(file))}"
        f" && flatpak run {shlex.quote(identifier)}"
    )
    command = ["sh", "-c", line]
    if discover.in_flatpak():
        prefix = ["flatpak-spawn", "--host"]
        if forwarded_descriptor is not None:
            prefix.append(f"--forward-fd={forwarded_descriptor}")
        return [*prefix, *command]
    return command


def _install_command(file: Path, *, forwarded_descriptor: int | None = None) -> list[str]:
    """Der Befehl, der dieses Paket einspielt — je Installationsart ein anderer.

    Hier stand eine Zeile mit einer Verzweigung darin: Windows startete die
    Datei, alles andere gab sie an ``open``. Das war für macOS richtig und für
    Linux nie erreichbar, weil dort gar kein Paket angeboten wurde.

    Zwei sichere Wege, und jeder ist der, den sein Format vorsieht: Die
    Setup-Datei nimmt Schalter (:data:`SETUP_ARGUMENTS`), das Flatpak-Bundle
    geht über seinen vererbten Deskriptor an ``flatpak install``. macOS bleibt
    beim Download-Hinweis, weil LaunchServices diesen Deskriptor verliert.
    """
    kind = install_kind()
    if kind == KIND_WINDOWS_SETUP:
        return [str(file), *SETUP_ARGUMENTS]
    if kind == KIND_FLATPAK:
        return _flatpak_command(file, forwarded_descriptor=forwarded_descriptor)
    if kind == KIND_MACOS_PACKAGE:
        raise ExternalToolError(
            tool="update",
            detail=_("Das macOS-Paket lässt sich aus Solidon nicht sicher öffnen."),
            suggestions=(OPEN_DOWNLOAD_PAGE,),
        )
    raise ExternalToolError(
        tool="update",
        detail=_("Diese Installationsart lässt sich nicht aus Solidon aktualisieren."),
        suggestions=(OPEN_DOWNLOAD_PAGE,),
    )


def _package_authorized(package: Package) -> bool:
    """Prüft die signierte Paketangabe unmittelbar vor dem Start erneut."""
    if not package.signed_release or not package.release_signature or not package.release_key:
        return False
    if not ed25519.verify(
        RELEASE_PUBLIC_KEY,
        package.signed_release,
        package.release_signature,
    ):
        return False
    try:
        release = load_json(package.signed_release, max_bytes=MAX_ANSWER_BYTES)
        entry = release["packages"][package.release_key]
    except (KeyError, TypeError, StrictJsonError):
        return False
    if not isinstance(entry, dict):
        return False
    return (
        _field(entry.get("file")) == package.file
        and _field(entry.get("url")) == package.url
        and _as_size(entry.get("size")) == package.size
        and _field(entry.get("sha256")).lower() == package.sha256
    )


def _open_start_locked(file: Path) -> BinaryIO:
    """Öffnet ein Paket so, dass Windows es bis zum Prozessstart nicht austauscht."""
    if os.name != "nt":
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        return os.fdopen(os.open(file, flags), "rb")

    kernel32 = _windows_ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateFileW.argtypes = (
        _windows_ctypes.c_wchar_p,
        _windows_ctypes.c_uint32,
        _windows_ctypes.c_uint32,
        _windows_ctypes.c_void_p,
        _windows_ctypes.c_uint32,
        _windows_ctypes.c_uint32,
        _windows_ctypes.c_void_p,
    )
    kernel32.CreateFileW.restype = _windows_ctypes.c_void_p
    kernel32.CloseHandle.argtypes = (_windows_ctypes.c_void_p,)
    kernel32.CloseHandle.restype = _windows_ctypes.c_int
    handle = kernel32.CreateFileW(
        str(file),
        0x80000000,  # GENERIC_READ
        0x00000001,  # FILE_SHARE_READ, ausdrücklich kein Schreiben oder Löschen
        None,
        3,  # OPEN_EXISTING
        0x08000080,  # FILE_FLAG_SEQUENTIAL_SCAN | FILE_ATTRIBUTE_NORMAL
        None,
    )
    if handle in (None, _windows_ctypes.c_void_p(-1).value):
        raise OSError(
            _windows_ctypes.get_last_error(),
            "Update-Paket ließ sich nicht sperren",
        )
    try:
        descriptor = _windows_msvcrt.open_osfhandle(
            int(handle),
            os.O_RDONLY | getattr(os, "O_BINARY", 0),
        )
    except BaseException:
        kernel32.CloseHandle(_windows_ctypes.c_void_p(handle))
        raise
    return os.fdopen(descriptor, "rb")


def _inherited_descriptor_path(descriptor: int) -> Path:
    """Nennt denselben offenen POSIX-Deskriptor im gestarteten Prozess.

    Ein offener Handle allein sperrt auf POSIX keinen Namenswechsel. Der
    Installer bekommt deshalb nicht den erneut aufzulösenden Cachepfad,
    sondern genau den Deskriptor, dessen Inhalt soeben geprüft wurde.
    """
    for folder in (Path("/proc/self/fd"), Path("/dev/fd")):
        if folder.is_dir():
            return folder / str(descriptor)
    raise ExternalToolError(
        tool="update",
        detail=_("Dieses System kann das geprüfte Update-Paket nicht sicher übergeben."),
        suggestions=(OPEN_DOWNLOAD_PAGE,),
    )


@contextmanager
def _verified_package(file: Path) -> Iterator[tuple[Path, Package, BinaryIO]]:
    """Hält den identitätsgebunden geprüften Inhalt bis zum Prozessstart offen."""
    folder = target_dir()
    junction = getattr(file, "is_junction", None)
    if file.is_symlink() or (callable(junction) and junction()):
        raise ExternalToolError(
            tool="update",
            detail=_("Das Update-Paket ist keine gewöhnliche Datei."),
            suggestions=(RETRY, OPEN_DOWNLOAD_PAGE),
        )
    try:
        resolved = file.resolve(strict=True)
        resolved.relative_to(folder)
    except (OSError, ValueError) as problem:
        raise ExternalToolError(
            tool="update",
            detail=_("Das Paket liegt nicht mehr da, wo es geladen wurde."),
            suggestions=(RETRY, OPEN_DOWNLOAD_PAGE),
            values={"path": str(file)},
        ) from problem
    package = _VERIFIED_PACKAGES.get(resolved)
    if package is None or not _package_authorized(package):
        raise ExternalToolError(
            tool="update",
            detail=_("Die Freigabe des Update-Pakets ist nicht mehr gültig."),
            suggestions=(RETRY, OPEN_DOWNLOAD_PAGE),
        )
    digest = hashlib.sha256()
    read = 0
    source: BinaryIO | None = None
    try:
        source = _open_start_locked(resolved)
        opened = _descriptor_path(source.fileno())
        if opened is not None and opened != resolved:
            raise OSError("Paketpfad wechselte beim Öffnen")
        before = os.fstat(source.fileno())
        if not stat.S_ISREG(before.st_mode):
            raise OSError("Paket ist keine gewöhnliche Datei")
        while chunk := source.read(CHUNK_BYTES):
            read += len(chunk)
            if read > MAX_PACKAGE_BYTES:
                raise OSError("Paket überschreitet die Größenobergrenze")
            digest.update(chunk)
        after = os.fstat(source.fileno())
        path_state = resolved.stat()
    except OSError as problem:
        if source is not None:
            source.close()
        raise ExternalToolError(
            tool="update",
            detail=_("Das Update-Paket ließ sich nicht erneut prüfen."),
            suggestions=(RETRY, OPEN_DOWNLOAD_PAGE),
        ) from problem
    except BaseException:
        if source is not None:
            source.close()
        raise

    assert source is not None

    def identity(state: os.stat_result) -> tuple[int, int, int, int]:
        return state.st_dev, state.st_ino, state.st_size, state.st_mtime_ns

    if (
        identity(before) != identity(after)
        or identity(after) != identity(path_state)
        or read != package.size
        or digest.hexdigest() != package.sha256
    ):
        source.close()
        raise ExternalToolError(
            tool="update",
            detail=_("Das Update-Paket wurde nach dem Herunterladen verändert."),
            suggestions=(RETRY, OPEN_DOWNLOAD_PAGE),
        )
    source.seek(0)
    try:
        yield resolved, package, source
    finally:
        source.close()


def start_installer(file: Path) -> None:
    """Spielt das geholte Paket ein. Danach beendet sich Solidon — nicht hier.

    Getrennt mit Absicht: Was mit dem offenen Dokument geschieht, entscheidet
    das Fenster und nicht der Kern. Diese Funktion startet ein Programm und
    kehrt zurück.
    """
    with (
        _cache_lock(target_dir()),
        _verified_package(file) as (
            verified_file,
            _package,
            source,
        ),
    ):
        options = detached_process_options(graphical=True)
        if os.name == "nt":
            command = _install_command(verified_file)
        else:
            descriptor = source.fileno()
            inherited_path = _inherited_descriptor_path(descriptor)
            command = _install_command(
                inherited_path,
                forwarded_descriptor=descriptor,
            )
            options["pass_fds"] = (descriptor,)
        try:
            # Windows hält den Namen bis zu CreateProcess gegen Austausch
            # gesperrt. POSIX startet ausdrücklich vom vererbten Deskriptor;
            # dort wäre der weiter offene Cachepfad allein keine Sperre.
            subprocess.Popen(command, **options)
        except OSError as error:
            raise ExternalToolError(
                tool="update",
                detail=_("Das Installationsprogramm ließ sich nicht starten."),
                suggestions=(OPEN_DOWNLOAD_PAGE,),
                values={"path": str(verified_file), "reason": str(error)},
            ) from error


def _megabytes(done: int, total: int) -> str:
    """Der Fortschrittstext. Megabyte, weil ein Anteil allein nichts über die
    Leitung sagt."""
    if total:
        return f"{done / 1048576:.0f} / {total / 1048576:.0f} MB"
    return f"{done / 1048576:.0f} MB"


def _clear(folder: Path) -> None:
    """Räumt den Zwischenspeicher, bevor etwas Neues hineinkommt."""
    _VERIFIED_PACKAGES.clear()
    for old in folder.glob("*"):
        junction = getattr(old, "is_junction", None)
        if old.is_symlink() or old.is_file():
            _remove(old)
        elif old.is_dir() or (callable(junction) and junction()):
            raise FileWriteError(
                detail=_("Im Update-Zwischenspeicher liegt ein unerwarteter Ordner."),
                values={"path": str(old)},
            )


def _remove(file: Path) -> None:
    """Löscht, und schweigt, wenn es nicht geht — es ist der Zwischenspeicher."""
    try:
        file.unlink(missing_ok=True)
    except OSError as problem:
        _log.info("could not remove %s: %s", file, problem)
