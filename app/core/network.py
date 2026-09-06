"""Vertrauensanker für HTTPS in den gebauten Paketen.

CPythons OpenSSL kennt auf Windows den Systemspeicher und auf Linux die
üblichen Verzeichnisse. Auf macOS zeigen seine Vorgabepfade dagegen in die
Python-Installation des **Bauservers**. Dieser Pfad reist nicht mit dem
PyInstaller-Paket; Update, Rückmeldung und Geräteaktivierung würden deshalb
erst beim Kunden an einem gültigen HTTPS-Zertifikat scheitern.

Das Paket bringt den Mozilla-CA-Satz aus :mod:`certifi` mit. Eine ausdrücklich
gesetzte ``SSL_CERT_FILE``-Variable bleibt unangetastet — Firmen mit eigener
CA dürfen ihren Vertrauensspeicher weiter vorgeben.

**Und dasselbe trifft das Linux-Paket, nur hat es dort niemand vermutet.**
Im Protokoll des ersten Flatpak-Kunden (Manjaro, 06.09.2026) steht sechsmal
``CERTIFICATE_VERIFY_FAILED: unable to get local issuer certificate`` — bei
jeder Update-Prüfung und bei beiden Versuchen, eine Rückmeldung zu senden.
Der Grund ist derselbe wie auf dem Mac: Das mitgelieferte OpenSSL kennt die
Compile-Time-Pfade des Bauservers, und im Sandkasten der
``org.freedesktop.Platform``-Laufzeit liegen die Zertifikate woanders. Die
Aktivierung geht denselben Weg — ein Kunde hätte kaufen und nicht
freischalten können.

**Gemessen statt geraten**, und die Messung braucht zwei Fragen. Die erste:
Trägt der Vorgabespeicher dieses Prozesses überhaupt einen Anker? Die zweite:
Käme er aus seinen Vorgabepfaden an einen heran? Beide zusammen, weil keine
für sich reicht — OpenSSL lädt ein Zertifikats**verzeichnis** (``capath``)
nicht beim Start, sondern erst beim Prüfen, über den Subjekt-Hash der gesuchten
Kette. Ein System mit ``/etc/ssl/certs`` meldet deshalb null Anker und prüft
trotzdem tadellos; wer nur zählt, tauscht dort einen tragenden Speicher gegen
den mitgelieferten aus und hebelt jede Firmen-CA aus, die darin liegt.

Der mitgelieferte Satz gilt also erst, wenn der Speicher leer ist **und** die
Vorgabepfade nichts hergeben. Das ist die Lage im Sandkasten, und zwar aus zwei
Gründen zugleich: Die kompilierten Pfade zeigen dorthin, wo der Bauserver seine
Zertifikate hatte, und das Verzeichnis, das die Laufzeit stattdessen mitbringt,
trägt die Hash-Namen nicht, über die OpenSSL nachschlägt (siehe
:func:`default_paths_exist`).
"""

from __future__ import annotations

import os
import re
import ssl
import sys
from pathlib import Path

import certifi

CERTIFICATE_VARIABLE = "SSL_CERT_FILE"


def trusted_anchors() -> int:
    """Wie viele Vertrauensanker der Vorgabespeicher dieses Prozesses geladen hat.

    **Die Zahl allein beweist nichts.** Ein ``capath``-Verzeichnis wird erst
    beim Prüfen gelesen; ein tadellos eingerichtetes Linux meldet hier null.
    Zusammen mit :func:`default_paths_exist` wird daraus eine Aussage.
    """
    try:
        return int(ssl.create_default_context().cert_store_stats().get("x509_ca", 0))
    except ssl.SSLError, OSError, ValueError:
        # Ein Speicher, der sich nicht einmal öffnen lässt, ist auch keiner.
        return 0


#: Wie OpenSSL eine Datei in einem ``capath``-Verzeichnis nennen muss, damit es
#: sie findet: acht Hexziffern des Subjekt-Hashes, ein Punkt, eine laufende
#: Nummer. Ein Verzeichnis ohne solche Namen ist für OpenSSL leer, und mag es
#: noch so viele Zertifikate enthalten.
_HASHED_CERTIFICATE = re.compile(r"^[0-9a-f]{8}\.[0-9]+$")


def default_paths_exist() -> bool:
    """Ob OpenSSL aus seinen Vorgabepfaden wirklich etwas holen könnte.

    ``ssl.get_default_verify_paths`` prüft die Existenz bereits: ``cafile`` und
    ``capath`` sind ``None``, wo die Datei oder das Verzeichnis fehlt. Die
    kompilierten Pfade daneben stehen unabhängig davon da und dürfen deshalb
    **nicht** als Rückfall dienen — sie sind die Frage, nicht die Antwort.

    **Ein vorhandenes Verzeichnis genügt trotzdem nicht.** OpenSSL sucht darin
    über den Subjekt-Hash, also nach Namen wie ``4f316efb.0``; die
    ``org.freedesktop.Platform``-Laufzeit legt genau diese Verweise nicht an
    (bekannt seit ``flatpak/freedesktop-sdk-base#3``). Ein Sandkasten hat dort
    also ein Verzeichnis voller Zertifikate, aus dem OpenSSL keines findet —
    und der Kunde bekommt „unable to get local issuer certificate", obwohl
    alles da zu sein scheint. Deshalb zählt hier nicht das Verzeichnis, sondern
    ein Name darin, den OpenSSL auch nachschlagen würde.
    """
    paths = ssl.get_default_verify_paths()
    if paths.cafile:
        return True
    if not paths.capath:
        return False
    try:
        return any(_HASHED_CERTIFICATE.match(entry.name) for entry in Path(paths.capath).iterdir())
    except OSError:
        # Ein Verzeichnis, das sich nicht lesen lässt, trägt nichts bei.
        return False


def configure_certificates(
    *,
    platform: str | None = None,
    frozen: bool | None = None,
    anchors: int | None = None,
    paths: bool | None = None,
) -> bool:
    """Richtet den mitgelieferten CA-Satz ein, wenn dieses Paket ihn braucht.

    ``True`` heißt, dass die Variable in diesem Aufruf gesetzt wurde. In der
    Entwicklungsumgebung, bei einer bereits gesetzten Vorgabe und überall
    dort, wo der Systemspeicher trägt, bleibt der Prozess unverändert.

    Zwei Fälle lösen aus, und der zweite ist der allgemeine: das gebaute
    macOS-Paket, dessen Vorgabepfade nachweislich auf den Bauserver zeigen —
    und **jedes** Paket ohne einen Vertrauensspeicher, der trägt. ``anchors``
    und ``paths`` nehmen die beiden Messungen entgegen; ohne Angabe misst die
    Funktion selbst.
    """
    chosen_platform = sys.platform if platform is None else platform
    packaged = bool(getattr(sys, "frozen", False)) if frozen is None else frozen
    if not packaged or os.environ.get(CERTIFICATE_VARIABLE):
        return False
    if chosen_platform != "darwin":
        counted = trusted_anchors() if anchors is None else anchors
        reachable = default_paths_exist() if paths is None else paths
        if counted > 0 or reachable:
            return False

    bundle = Path(certifi.where())
    if not bundle.is_file():
        return False
    os.environ[CERTIFICATE_VARIABLE] = str(bundle)
    return True
