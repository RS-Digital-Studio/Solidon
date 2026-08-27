"""Das signierte Manifest über die eigene Auslieferung (Konzept §2 I, H4).

Die vier Grenzstellen aus §2 C liegen in gewöhnlichen Python-Dateien. Wer eine
davon im ausgelieferten Paket um ihr ``require`` kürzt, hat die Grenze
entfernt — dagegen steht dieses Modul: beim ersten Zustandsabruf werden genau
diese vier Dateien gegen ein Manifest geprüft, das beim Bau erzeugt und
signiert wurde. Ein Patch an einer von ihnen fällt auf, und der Zustand ist
dann gesperrt, nicht abgestürzt.

**In der Entwicklung prüft das Modul nichts**: :data:`MANIFEST_PUBLIC_KEY` ist
``None``, und ohne erwartetes Manifest gibt es nichts zu vergleichen — sonst
sperrte jeder Arbeitsstand die eigene Suite. Der Wert wird beim Bau gesetzt,
bevor das Prüfmodul kompiliert wird (V4c); erst dann ist ein fehlendes oder
verändertes Manifest ein Bruch. Der zugehörige private Schlüssel ist je Bau
frisch und wird nach dem Signieren verworfen — er ist nicht der
Lizenzschlüssel aus §8, der den Passwortmanager nie verlässt.

Die Nutzlast der Signatur baut :func:`manifest_payload` — dieselbe Funktion
benutzt das Bauwerkzeug. Zwei Umsetzungen wären der Weg zu einem Manifest, das
nur eine Seite versteht.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Final

import app
from app.core.activation import ed25519
from app.core.log import get_logger

_log = get_logger(__name__)

#: Der öffentliche Schlüssel, gegen den das Manifest geprüft wird.
#:
#: ``None`` heißt: dieser Lauf erwartet kein Manifest (Entwicklung, Suite).
#: Beim Bau tritt der öffentliche Teil eines je Bau erzeugten Paars an diese
#: Stelle — im kompilierten Prüfmodul, nicht in einer Datei daneben.
MANIFEST_PUBLIC_KEY: bytes | None = None

#: Dateiname des Manifests, neben dem ``app``-Paket.
MANIFEST_FILE: Final = "licence.manifest"

#: Die vier Grenzdateien aus §2 C, relativ zum ``app``-Paket. Das Manifest
#: muss mindestens sie decken — was es darüber hinaus deckt, wird mitgeprüft.
BOUNDARY_FILES: Final = (
    "core/scene/history.py",
    "core/export/writer.py",
    "core/export/handover.py",
    "core/agent/session.py",
)


def app_root() -> Path:
    """Wo das ``app``-Paket liegt — in der Entwicklung wie im Paket."""
    return Path(app.__file__).parent


def manifest_path() -> Path:
    return app_root().parent / MANIFEST_FILE


def boundary_hashes() -> dict[str, str]:
    """SHA-256 der vier Grenzdateien, wie sie jetzt auf der Platte liegen.

    Eine fehlende Datei wird eine leere Prüfsumme, kein Fehler: gegen das
    Manifest gehalten ist „weg" dieselbe Aussage wie „verändert".
    """
    root = app_root()
    hashes: dict[str, str] = {}
    for name in BOUNDARY_FILES:
        try:
            hashes[name] = hashlib.sha256((root / name).read_bytes()).hexdigest()
        except OSError:
            hashes[name] = ""
    return hashes


def manifest_payload(files: dict[str, str]) -> bytes:
    """Die Bytes, über die die Signatur läuft — kanonisch, damit Bauwerkzeug
    und Prüfung dasselbe signieren und prüfen."""
    return json.dumps(files, sort_keys=True, separators=(",", ":")).encode("utf-8")


def intact() -> bool:
    """Ob die Auslieferung ist, was der Bau signiert hat.

    Drei Arten zu scheitern, alle gleichwertig: das Manifest fehlt oder ist
    unlesbar, seine Signatur passt nicht, oder eine Grenzdatei weicht ab.
    Protokolliert wird der Grund; nach außen zählt nur, dass die schreibende
    Seite zu bleibt.
    """
    if MANIFEST_PUBLIC_KEY is None:
        return True
    try:
        data = json.loads(manifest_path().read_text(encoding="utf-8"))
        files = {str(name): str(digest) for name, digest in data["files"].items()}
        signature = bytes.fromhex(str(data["signature"]))
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        _log.warning("licence manifest missing or unreadable")
        return False
    if not ed25519.verify(MANIFEST_PUBLIC_KEY, manifest_payload(files), signature):
        _log.warning("licence manifest signature does not match")
        return False
    if any(name not in files for name in BOUNDARY_FILES):
        _log.warning("licence manifest does not cover the boundary files")
        return False
    # Alles, was das Manifest deckt, wird geprüft — der Satz an
    # ``BOUNDARY_FILES`` versprach das schon, gehalten hat ihn erst diese
    # Schleife: Vorher liefen genau vier Vergleiche, und eine fünfte gedeckte
    # Datei durfte beliebig abweichen (Gesamtreview L-7). Die Pfade sind
    # vertrauenswürdig, denn die Signatur ist zu diesem Zeitpunkt geprüft.
    root = app_root()
    for name, expected in files.items():
        try:
            actual = hashlib.sha256((root / name).read_bytes()).hexdigest()
        except OSError:
            actual = ""
        if expected != actual:
            _log.warning("licence boundary file does not match the manifest: %s", name)
            return False
    return True
