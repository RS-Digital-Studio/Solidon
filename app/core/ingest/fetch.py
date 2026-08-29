"""Eine Modelldatei aus dem Netz holen (Bauplan §16.3, §17.1, §32).

Der häufigste Weg, wie ein Modell in Solidon kommt, beginnt auf einer
Modellseite — MakerWorld, Printables, Thingiverse. Bis hierher hieß das:
herunterladen, im Ordner suchen, hereinziehen. Das geht weiterhin, und für
eine Datei, die schon auf der Platte liegt, ist es der kürzere Weg. Dieses
Modul deckt den anderen Fall ab: die Adresse ist in der Zwischenablage, die
Datei noch nirgends.

**Was hier ausdrücklich nicht passiert.** Es wird nichts durchsucht, nichts
angemeldet, nichts im Hintergrund geholt und keine Seite ausgewertet. Eine
Adresse zeigt auf eine Datei oder eben nicht — im zweiten Fall sagt die
Meldung genau das und schlägt den Weg über den Herunterladen-Knopf der Seite
vor (Regel 17). Solidon liest keine Modellseiten aus; was deren Betreiber
erlauben, steht in ihren Bedingungen und nicht in unserem Quelltext.

Die Grenzen sind dieselben wie beim Import von der Platte
(:func:`app.core.ingest.loader.check_limits`), plus die drei, die nur im Netz
gelten: nur ``http`` und ``https``, ein Zeitlimit, und ein Abbruch, sobald
mehr Daten kommen als erlaubt — geprüft **während** des Lesens, nicht danach.
Ein Server, der endlos sendet, füllt sonst den Speicher, und ein Kopf mit
``Content-Length: 12`` ist ein Versprechen, kein Beweis.
"""

from __future__ import annotations

import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import PurePosixPath
from typing import Final
from urllib.parse import unquote, urlsplit

from app.core.errors import Action, ExternalToolError, ValidationError
from app.core.ingest.loader import MAX_FILE_BYTES
from app.core.ingest.plan import MODEL_SUFFIXES
from app.core.log import get_logger
from app.core.types import ProgressFn
from app.i18n import _

_log = get_logger(__name__)

#: Wie lange auf den Server gewartet wird, ehe der Versuch als gescheitert
#: gilt. Großzügig genug für ein 200-MB-Modell an einer müden Leitung, kurz
#: genug, dass niemand glaubt, die Anwendung hänge.
TIMEOUT_SECONDS: Final = 60.0

#: Wie viel am Stück gelesen wird. Klein genug, dass Fortschritt und Abbruch
#: sich flüssig anfühlen, groß genug, dass es nicht bremst.
#:
#: **Gilt für jeden Netzstrom des Kerns, nicht nur für diesen.**
#: ``updates.py`` führte dieselbe Zahl mit derselben Begründung noch einmal
#: und verwies daneben im Kommentar auf diese Datei — ein Verweis ist keine
#: geteilte Sache, er wandert beim nächsten Anfassen nicht mit. Sie wohnt
#: hier, weil diese Datei das Holen im Namen trägt (27.08.2026).
CHUNK_BYTES: Final = 256 * 1024

#: Dieselbe Liste wie auf der Platte. Der Netzweg ändert nur die Herkunft,
#: nicht die Formate, die Solidon verspricht (§16.3).
ALLOWED_SUFFIXES: Final = MODEL_SUFFIXES

#: Dateiname aus ``Content-Disposition``. Absichtlich schlicht: was in
#: Anführungszeichen hinter ``filename=`` steht, mehr wird nicht geraten.
_DISPOSITION = re.compile(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?', re.IGNORECASE)

#: Ein Kennwort, das sagt, wer da anfragt. Ohne eines antworten manche Server
#: mit 403 — und die Wahrheit ist die freundlichste Angabe.
USER_AGENT: Final = "Solidon3D"


@dataclass(frozen=True, slots=True)
class FetchedModel:
    """Was von der Adresse zurückkam: die Datei und woher sie stammt."""

    name: str
    payload: bytes
    url: str
    retrieved: str
    """Zeitpunkt in ISO-Schreibweise — er wandert in die Provenienz (§16.3)."""


def check_url(url: str) -> str:
    """Prüft eine Adresse, bevor irgendetwas geöffnet wird.

    Erst das Schema, dann der Rechnername. ``file:``-Adressen sind der
    eigentliche Grund für diese Prüfung: sie würden über denselben Aufruf die
    Festplatte auslesen, und eine Adresse aus der Zwischenablage ist kein Ort,
    an dem man das zulässt (§32).
    """
    parts = urlsplit(url.strip())
    if parts.scheme.lower() not in ("http", "https"):
        raise ValidationError(
            field="url",
            detail=_("Es gehen nur Adressen, die mit http:// oder https:// beginnen."),
            constraint="scheme",
            values={"url": url, "scheme": parts.scheme},
        )
    if not parts.netloc:
        raise ValidationError(
            field="url",
            detail=_("In der Adresse fehlt der Rechnername."),
            constraint="host",
            values={"url": url},
        )
    return url.strip()


def suffix_of(name: str) -> str:
    """Die Endung eines Namens in Kleinbuchstaben, oder eine leere
    Zeichenkette."""
    return PurePosixPath(name).suffix.lower()


def fetch_model(
    url: str,
    *,
    progress: ProgressFn | None = None,
    opener: object | None = None,
) -> FetchedModel:
    """Holt eine Modelldatei und gibt sie mit ihrer Herkunft zurück.

    ``opener`` ist der Einstieg für die Suite: sie fährt diesen Weg gegen
    einen eigenen Server, statt ins Netz zu greifen.
    """
    address = check_url(url)
    request = urllib.request.Request(address, headers={"User-Agent": USER_AGENT})
    open_url = opener if callable(opener) else urllib.request.urlopen

    try:
        answer = open_url(request, timeout=TIMEOUT_SECONDS)
    except urllib.error.HTTPError as error:
        # Ein HTTPError ist selbst eine offene Antwort. Wer ihn nur auswertet,
        # lässt einen Socket zurück — im Testlauf eine ResourceWarning, in
        # einer langen Sitzung ein Handle nach jedem Fehlversuch.
        error.close()
        raise ExternalToolError(
            tool="download",
            # Kein Platzhalter im Text: eine Message-ID kennt keine, und der
            # Kern setzt sie nicht ein — die Zahl reist in ``values`` mit und
            # steht in der Meldung der Oberfläche.
            detail=_("Der Server hat die Datei nicht herausgegeben."),
            values={"url": address, "status": error.code},
        ) from error
    except (urllib.error.URLError, OSError) as error:
        raise ExternalToolError(
            tool="download",
            detail=_("Die Adresse war nicht erreichbar."),
            values={"url": address, "reason": str(error)},
        ) from error

    with answer:
        # Noch einmal dieselbe Prüfung, jetzt am *erreichten* Ort. Die Prüfung
        # oben gilt der eingetippten Adresse; dazwischen liegt der
        # Weiterleitungs-Handler von urllib, und der folgt auch nach `ftp:` —
        # ein http-Server, der mit `Location: ftp://…` antwortet, käme so an
        # der Schemaprüfung vorbei (§32). Gelesen wird erst danach.
        address = check_url(str(getattr(answer, "url", address) or address))
        # Erst die Herkunft, dann der Name: Eine Modellseite trägt keine Endung
        # (der Normalfall beim Kopieren aus dem Browser), und ``_name_from``
        # warf dafür „Format nicht erkannt", bevor der hilfreiche Satz „hier
        # steht eine Webseite, lade die Datei dort" überhaupt drankam. Den Namen
        # braucht diese Meldung nicht; sie führt ihn nur zur Ansicht mit.
        _reject_web_page(answer, "", address)
        name = _name_from(answer, address)
        payload = _read_limited(answer, progress)

    _log.info("fetched %d bytes from %s", len(payload), urlsplit(address).netloc)
    return FetchedModel(
        name=name,
        payload=payload,
        url=address,
        retrieved=datetime.now(UTC).isoformat(timespec="seconds"),
    )


def _read_limited(answer: object, progress: ProgressFn | None) -> bytes:
    """Liest mit Fortschritt und bricht ab, sobald die Grenze überschritten
    ist.

    Die Grenze wird an den gelesenen Daten geprüft und nicht an
    ``Content-Length``: die Angabe im Kopf ist das, was der Server behauptet.
    """
    announced = _announced_length(answer)
    chunks: list[bytes] = []
    seen = 0
    while True:
        chunk = answer.read(CHUNK_BYTES)  # type: ignore[attr-defined]
        if not chunk:
            break
        seen += len(chunk)
        if seen > MAX_FILE_BYTES:
            raise ValidationError(
                field="file",
                detail=_("Die Datei ist größer, als diese Anwendung verarbeitet."),
                constraint="file_too_large",
                values={"size": seen, "limit": MAX_FILE_BYTES},
            )
        chunks.append(chunk)
        if progress is not None:
            share = min(seen / announced, 1.0) if announced else 0.0
            progress(share, str(_("Modell herunterladen")))
    return b"".join(chunks)


def _announced_length(answer: object) -> int:
    """Was der Server als Länge angibt — für den Fortschritt, für sonst
    nichts."""
    raw = _header(answer, "Content-Length")
    try:
        return max(int(raw or 0), 0)
    except ValueError:
        return 0


def _header(answer: object, name: str) -> str:
    headers = getattr(answer, "headers", None)
    if headers is None:
        return ""
    return str(headers.get(name, "") or "")


def _name_from(answer: object, url: str) -> str:
    """Der Dateiname: erst was der Server sagt, sonst was in der Adresse
    steht.

    Ein Name ohne brauchbare Endung wird nicht erfunden — ohne Endung weiß
    niemand, welches Format da ankommt, und geraten wird hier nicht (Regel 21).
    """
    disposition = _DISPOSITION.search(_header(answer, "Content-Disposition"))
    if disposition:
        candidate = unquote(disposition.group(1)).strip()
        if suffix_of(candidate) in ALLOWED_SUFFIXES:
            return PurePosixPath(candidate).name
    from_path = unquote(PurePosixPath(urlsplit(url).path).name)
    if suffix_of(from_path) in ALLOWED_SUFFIXES:
        return from_path
    raise ValidationError(
        field="url",
        detail=_("Aus der Adresse geht nicht hervor, welches Format die Datei hat."),
        constraint="unknown_format",
        values={
            "url": url,
            "name": from_path,
            "formats": ", ".join(entry.lstrip(".").upper() for entry in ALLOWED_SUFFIXES),
        },
        suggestions=[_DOWNLOAD_YOURSELF],
    )


def _reject_web_page(answer: object, name: str, url: str) -> None:
    """Eine Modellseite ist keine Modelldatei — und sagt das auch so.

    Der Fall ist nicht selten, sondern der Normalfall: wer eine Adresse aus
    dem Browser kopiert, kopiert die Seite, nicht die Datei dahinter. Ohne
    diese Prüfung landete das HTML in der Eingangsstufe und käme als „Das
    Format wird nicht erkannt" zurück — richtig und trotzdem unbrauchbar.
    """
    kind = _header(answer, "Content-Type").split(";")[0].strip().lower()
    if kind in ("text/html", "application/xhtml+xml"):
        raise ValidationError(
            field="url",
            detail=_(
                "Unter dieser Adresse steht eine Webseite, keine Modelldatei. "
                "Auf der Seite gibt es einen Knopf zum Herunterladen — die Datei "
                "danach hier ablegen."
            ),
            constraint="web_page",
            values={"url": url, "name": name, "type": kind},
            suggestions=[_DOWNLOAD_YOURSELF],
        )


#: Der Ausweg, der bei beiden Adressfehlern gilt: die Seite im Browser
#: öffnen und dort herunterladen.
_DOWNLOAD_YOURSELF: Final = Action(
    id="open_in_browser",
    label=_("Seite im Browser öffnen"),
)
