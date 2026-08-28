"""Vertrauensanker für HTTPS im gebauten macOS-Paket.

CPythons OpenSSL kennt auf Windows den Systemspeicher und auf Linux die
üblichen Verzeichnisse. Auf macOS zeigen seine Vorgabepfade dagegen in die
Python-Installation des **Bauservers**. Dieser Pfad reist nicht mit dem
PyInstaller-Paket; Update, Rückmeldung und Geräteaktivierung würden deshalb
erst beim Kunden an einem gültigen HTTPS-Zertifikat scheitern.

Das Paket bringt den Mozilla-CA-Satz aus :mod:`certifi` mit. Nur der gebaute
macOS-Prozess bekommt ihn als Vorgabe. Eine ausdrücklich gesetzte
``SSL_CERT_FILE``-Variable bleibt unangetastet — Firmen mit eigener CA dürfen
ihren Vertrauensspeicher weiter vorgeben.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import certifi

CERTIFICATE_VARIABLE = "SSL_CERT_FILE"


def configure_certificates(*, platform: str | None = None, frozen: bool | None = None) -> bool:
    """Richtet den mitgelieferten CA-Satz ein, wenn dieses Paket ihn braucht.

    ``True`` heißt, dass die Variable in diesem Aufruf gesetzt wurde. Auf
    anderen Plattformen, in der Entwicklungsumgebung oder bei einer bereits
    gesetzten Vorgabe bleibt der Prozess unverändert.
    """
    chosen_platform = sys.platform if platform is None else platform
    packaged = bool(getattr(sys, "frozen", False)) if frozen is None else frozen
    if chosen_platform != "darwin" or not packaged or os.environ.get(CERTIFICATE_VARIABLE):
        return False

    bundle = Path(certifi.where())
    if not bundle.is_file():
        return False
    os.environ[CERTIFICATE_VARIABLE] = str(bundle)
    return True
