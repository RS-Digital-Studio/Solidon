"""Das Update (Bauplan §37.2).

Drei Schritte, und jeder braucht einen Klick: fragen, holen, starten. Hier
stand einmal „ein Hinweis, kein automatisches Update", und der Grund dafür
war gut — ein Programm, das sich selbst ersetzt, kann sich kaputtmachen,
während niemand hinsieht. Er gilt weiter, nur trifft er nicht mehr den Weg,
sondern den **Auslöser**: Es lädt nichts von allein, es ersetzt sich nichts
im Hintergrund, und es startet nichts ohne Zustimmung.

Was die Anwendung jetzt zusätzlich tut, ist das Holen und das Prüfen. Beides
von Hand zu machen hieß: Seite finden, das richtige von vier Paketen
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
import platform
import subprocess
import sys
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final
from urllib.parse import urlsplit

from app.branding import APP_VERSION
from app.core.activation import ed25519
from app.core.backends.llm import Transport
from app.core.errors import (
    OPEN_DOWNLOAD_PAGE,
    RETRY,
    ExternalToolError,
    FileWriteError,
)
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

#: Wie viel von der Antwort überhaupt gelesen wird.
#:
#: Das Zeitlimit deckelt die einzelne Socket-Operation, nicht die Menge: eine
#: Gegenstelle, die zügig und endlos liefert, füllte sonst beim Start den
#: Arbeitsspeicher. Die Datei trägt drei kurze Felder; alles darüber ist keine
#: Versionsdatei mehr.
MAX_ANSWER_BYTES: Final = 64 * 1024

#: Wie lang die einzelnen Felder werden dürfen. Sie landen in der Statusleiste,
#: und was dort steht, kommt von einem Server — nicht aus diesem Programm.
MAX_FIELD_LENGTH: Final = 200

#: Wie lange das Holen des Pakets an einer einzelnen Leseoperation hängen darf.
#: Nicht zu verwechseln mit :data:`TIMEOUT_SECONDS`: Die Abfrage soll den Start
#: nicht aufhalten, ein Download von 180 MB dauert bei jeder Leitung länger als
#: vier Sekunden.
DOWNLOAD_TIMEOUT_SECONDS: Final = 60.0

#: Was ein Paket höchstens wiegen darf. Die Versionsdatei nennt die erwartete
#: Größe, und mehr als das wird nicht gelesen — diese Grenze fängt den Fall,
#: dass sie eine unsinnige Zahl nennt.
MAX_PACKAGE_BYTES: Final = 2 * 1024 * 1024 * 1024

#: In welchen Häppchen gelesen wird. Groß genug, dass der Fortschritt nicht
#: teurer ist als das Lesen; klein genug, dass Abbrechen sich sofort anfühlt.
CHUNK_BYTES: Final = 256 * 1024

#: Wie viele Punkte aus dem Changelog gezeigt werden. Die Datei kommt von einem
#: Server; acht Zeilen sind eine Auswahl, achtzig sind eine Liste, und eine Liste
#: liest niemand vor einem Update.
MAX_CHANGES: Final = 20

#: Wie ein Paketschlüssel in der Versionsdatei heißt. Die Architektur steht nur
#: dort, wo es zwei gibt: Auf einem Mac startet ein für arm64 gebautes Programm
#: auf einem Intel-Gerät nicht.
PLATFORM_WINDOWS: Final = "windows"
PLATFORM_MACOS_ARM: Final = "macos-arm64"
PLATFORM_MACOS_INTEL: Final = "macos-x86_64"
PLATFORM_LINUX: Final = "linux"

#: Wo ein Paket, das gestartet werden kann, überhaupt startbar ist.
#:
#: Linux fehlt mit Absicht. Ein Flatpak ersetzt sich über ``flatpak update``
#: und ein AppImage gar nicht — beides von innen anzustoßen hieße, dem Nutzer
#: ein Paket in einen Ordner zu legen und ihn damit allein zu lassen. Dort
#: bleibt es beim Hinweis und dem Weg zur Download-Seite (§37.2).
STARTABLE: Final = frozenset({PLATFORM_WINDOWS, PLATFORM_MACOS_ARM, PLATFORM_MACOS_INTEL})


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
    packages: Mapping[str, Package] = field(default_factory=dict)
    changes: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    """Was neu ist, in Kundensprache — je Sprache eine Liste."""

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

    def package(self, key: str = "") -> Package | None:
        """Das Paket für diese Plattform, wenn die Versionsdatei eines nennt."""
        return self.packages.get(key or platform_key())

    def startable(self, key: str = "") -> Package | None:
        """Das Paket, **das sich von hier aus auch starten lässt.**

        Drei Gründe, warum es keines gibt, und alle drei sind kein Fehler: Die
        Versionsdatei nennt für diese Plattform keines, es ist eine, die sich
        nicht von innen ersetzen lässt (Linux), oder Solidon läuft gar nicht
        als Paket, sondern aus den Quellen. Dann bleibt der Hinweis, und der
        Weg führt auf die Download-Seite.
        """
        chosen = key or platform_key()
        if chosen not in STARTABLE or not packaged():
            return None
        return self.packages.get(chosen)


def platform_key() -> str:
    """Wie das Paket dieses Rechners in der Versionsdatei heißt."""
    if sys.platform == "win32":
        return PLATFORM_WINDOWS
    if sys.platform == "darwin":
        # ``platform.machine()`` und nicht ``sys.maxsize``: Auf einem Mac sind
        # beide Versionen 64-bittig, unterschieden werden sie am Befehlssatz.
        return PLATFORM_MACOS_ARM if platform.machine() == "arm64" else PLATFORM_MACOS_INTEL
    return PLATFORM_LINUX


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
        packages=_packages(payload.get("packages"), origin=address),
        changes=_changes(payload.get("changes")),
    )


def _changes(raw: object) -> dict[str, tuple[str, ...]]:
    """Der Changelog aus der Antwort, gestutzt auf das, was hineinpasst.

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
            _field(entry)
            for entry in value[:MAX_CHANGES]
            if isinstance(entry, str) and entry.strip()
        )
        if points:
            found[str(key)[:16]] = points
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
            detail=_("Die Prüfsumme des Pakets stimmt nicht — es wurde gelöscht."),
            suggestions=(RETRY, OPEN_DOWNLOAD_PAGE),
            values={"url": package.url, "expected": package.sha256, "got": digest.hexdigest()},
        )

    _log.info("update package verified: %s (%d bytes)", file.name, read)
    return file


def start_installer(file: Path) -> None:
    """Startet das geholte Paket. Danach beendet sich Solidon — nicht hier.

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
    command = [str(file)] if sys.platform == "win32" else ["open", str(file)]
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
