"""Unterschreibt ``website/version.json`` (Bauplan §37.2).

Warum es diese Datei gibt: Die Prüfsumme eines Pakets steht in derselben Datei
wie seine Adresse. Gegen einen Angreifer im Netz reicht das — er bräuchte ein
Zertifikat für solidon3d.de. Gegen einen, der **den Server selbst** hat, reicht
es nicht: Der tauscht Paket und Prüfsumme gemeinsam aus, und in der
Installation widerspricht nichts.

Dagegen steht eine Unterschrift mit einem Schlüssel, der nicht auf dem Server
liegt. Solidon prüft sie mit dem öffentlichen Teil aus der Installation
(``updates.RELEASE_PUBLIC_KEY``), bevor es dem Inhalt überhaupt glaubt.

Einmalig, um das Paar zu erzeugen::

    python tools/sign_version.py --new-keypair

Der private Teil geht in den Passwortmanager und auf Papier an einen zweiten
Ort — **nie ins Repository und nie auf den Server**. Der öffentliche tritt in
``app/core/updates.py`` an die Stelle von ``RELEASE_PUBLIC_KEY``.

Danach, nach jedem Bau und vor jedem Hochladen::

    python tools/sign_version.py --private geheim.key

Ohne Argument prüft es nur, ob die Datei, die dort liegt, eine gültige
Unterschrift trägt — das ist der Griff, den ``upload_website.py`` benutzt und
den man vor dem Hochladen von Hand tun kann::

    python tools/sign_version.py --check

**Das Signieren steht hier und nicht in der Anwendung.** Sie prüft nur; sie
braucht das Signieren nie und trüge damit den Weg mit sich, den ein Angreifer
sucht. Dieselbe Aufteilung wie beim Lizenzschlüssel (``make_licence_keys.py``),
und die Kurvenarithmetik darunter ist dieselbe.
"""

from __future__ import annotations

import argparse
import json
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.core.updates import (  # noqa: E402  — erst nach sys.path
    RELEASE_PUBLIC_KEY,
    SIGNATURE_FIELD,
    signature_ok,
    signed_payload,
)
from tools.make_licence_keys import public_key, sign  # noqa: E402

VERSION_FILE = ROOT / "website" / "version.json"


def new_keypair() -> int:
    """Ein frisches Paar. Läuft einmal, und sein Ergebnis wird von Hand
    verteilt — der private Teil in den Passwortmanager, der öffentliche in den
    Quelltext."""
    seed = secrets.token_bytes(32)
    print("Privater Schlüssel (Passwortmanager, NICHT ins Repository):")
    print(f"  {seed.hex()}")
    print()
    print("Öffentlicher Schlüssel (nach app/core/updates.py, RELEASE_PUBLIC_KEY):")
    print(f'  "{public_key(seed).hex()}"')
    return 0


def read_seed(path: Path) -> bytes:
    """Der private Schlüssel aus einer Datei, als Hex."""
    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError as problem:
        raise SystemExit(f"Der private Schlüssel ließ sich nicht lesen: {problem}") from problem
    try:
        seed = bytes.fromhex(text)
    except ValueError as problem:
        raise SystemExit(
            f"{path.name} enthält keinen Schlüssel als Hex. Erwartet werden "
            "64 Hex-Zeichen, sonst nichts."
        ) from problem
    if len(seed) != 32:
        raise SystemExit(f"Ein Schlüssel hat 32 Bytes, dieser hat {len(seed)}.")
    return seed


def sign_file(seed: bytes) -> int:
    """Schreibt die Unterschrift in die Versionsdatei.

    Geprüft wird gleich danach mit demselben Weg, den die Anwendung geht: Ein
    Werkzeug, das eine Unterschrift schreibt und sie nicht gegenliest, meldet
    Erfolg auch dann, wenn beide Seiten verschiedene Bytes meinen.
    """
    if public_key(seed) != RELEASE_PUBLIC_KEY:
        raise SystemExit(
            "Dieser private Schlüssel gehört nicht zu dem, gegen den die Anwendung "
            "prüft (updates.RELEASE_PUBLIC_KEY). Eine damit unterschriebene Datei "
            "würde von jeder Installation verworfen."
        )
    data = json.loads(VERSION_FILE.read_text(encoding="utf-8"))
    data[SIGNATURE_FIELD] = sign(seed, signed_payload(data)).hex()
    VERSION_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not signature_ok(data):
        raise SystemExit("Die eben geschriebene Unterschrift trägt nicht — nichts hochladen.")
    print(f"  {VERSION_FILE.name}: unterschrieben, Version {data.get('version')}")
    return 0


def check_file() -> int:
    """Ob die Datei, die dort liegt, eine gültige Unterschrift trägt."""
    try:
        data = json.loads(VERSION_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError) as problem:
        print(f"  {VERSION_FILE.name}: nicht lesbar — {problem}")
        return 1
    if not signature_ok(data):
        print(
            f"  {VERSION_FILE.name}: **ohne gültige Unterschrift**. Jede Installation "
            "ab 0.1.4 verwirft sie, und niemand erfährt von dieser Version.\n"
            "  Zu tun: python tools/sign_version.py --private <datei>"
        )
        return 1
    print(f"  {VERSION_FILE.name}: Unterschrift trägt, Version {data.get('version')}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--new-keypair", action="store_true", help="ein neues Schlüsselpaar")
    parser.add_argument("--private", type=Path, help="Datei mit dem privaten Schlüssel als Hex")
    parser.add_argument(
        "--check", action="store_true", help="nur nachsehen, ob die Unterschrift trägt"
    )
    args = parser.parse_args()

    if args.new_keypair:
        return new_keypair()
    if args.private:
        return sign_file(read_seed(args.private))
    return check_file()


if __name__ == "__main__":
    raise SystemExit(main())
