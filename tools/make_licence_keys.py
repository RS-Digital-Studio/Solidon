"""Erzeugt Schlüsselpaare und Lizenzschlüssel (Konzept §2 B, §8).

Dies ist die einzige Stelle im Repository, die **signiert**. Die Anwendung
prüft nur — sie braucht das Signieren nie und trägt es deshalb nicht mit. Die
Kurvenarithmetik darunter ist dieselbe (``app.core.activation.ed25519``): zwei
Umsetzungen wären der klassische Weg zu einer Signatur, die nur eine Seite
versteht.

Einmalig, um das Paar zu erzeugen:

    python tools/make_licence_keys.py --new-keypair

Der private Schlüssel geht in den Passwortmanager und auf Papier an einen
zweiten Ort — **nie ins Repository**. Der öffentliche tritt in
``app/core/activation/key.py`` an die Stelle von ``PUBLIC_KEY``.

Danach, je Kauf oder für einen Vorrat:

    python tools/make_licence_keys.py --private geheim.key \
        --order A-1234 --holder "vorname@beispiel.de"
    python tools/make_licence_keys.py --private geheim.key --count 50

Mit ``--count`` entstehen unpersonalisierte Schlüssel für einen Vorrat, den der
Zahlungsanbieter ausliefert; die Bestellkennung vergibt dann er, und die
Käuferkennung bleibt leer.
"""

from __future__ import annotations

import argparse
import hashlib
import secrets
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.activation import ed25519
from app.core.activation.key import Licence, current_major, encode, format_key


def _clamped_scalar(seed: bytes) -> tuple[int, bytes]:
    """Der geheime Skalar und das Präfix für den Nonce (RFC 8032, §5.1.5)."""
    digest = hashlib.sha512(seed).digest()
    lower = bytearray(digest[:32])
    lower[0] &= 248
    lower[31] &= 127
    lower[31] |= 64
    return int.from_bytes(lower, "little"), digest[32:]


def public_key(seed: bytes) -> bytes:
    """Der öffentliche Schlüssel zu einem Startwert."""
    scalar, _prefix = _clamped_scalar(seed)
    return ed25519.compress(ed25519.multiply(scalar, ed25519.base_point()))


def sign(seed: bytes, message: bytes) -> bytes:
    """Signiert eine Nachricht (RFC 8032, §5.1.6)."""
    scalar, prefix = _clamped_scalar(seed)
    nonce = int.from_bytes(hashlib.sha512(prefix + message).digest(), "little")
    nonce %= ed25519.GROUP_ORDER
    point_r = ed25519.compress(ed25519.multiply(nonce, ed25519.base_point()))
    challenge = int.from_bytes(
        hashlib.sha512(point_r + public_key(seed) + message).digest(), "little"
    )
    challenge %= ed25519.GROUP_ORDER
    scalar_s = (nonce + challenge * scalar) % ed25519.GROUP_ORDER
    return point_r + scalar_s.to_bytes(32, "little")


def make_key(seed: bytes, licence: Licence) -> str:
    """Der fertige Schlüsseltext zu einer Lizenz."""
    payload = encode(licence)
    return format_key(payload, sign(seed, payload))


def _new_keypair() -> int:
    seed = secrets.token_bytes(32)
    print("Privater Schlüssel — in den Passwortmanager, nie ins Repository:")
    print(f"  {seed.hex()}")
    print()
    print("Öffentlicher Schlüssel — in app/core/activation/key.py als PUBLIC_KEY:")
    print(f'  PUBLIC_KEY: Final = bytes.fromhex(\n      "{public_key(seed).hex()}"\n  )')
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--new-keypair", action="store_true", help="ein neues Schlüsselpaar")
    parser.add_argument("--private", type=Path, help="Datei mit dem privaten Schlüssel als Hex")
    parser.add_argument("--order", default="", help="Bestellkennung")
    parser.add_argument("--holder", default="", help="auf wen der Schlüssel lautet")
    parser.add_argument("--count", type=int, default=1, help="wie viele Schlüssel")
    parser.add_argument("--major", type=int, default=None, help="Hauptversion, Vorgabe: die eigene")
    arguments = parser.parse_args(argv)

    if arguments.new_keypair:
        return _new_keypair()
    if arguments.private is None:
        parser.error("--private oder --new-keypair")
    try:
        seed = bytes.fromhex(arguments.private.read_text(encoding="utf-8").strip())
    except (OSError, ValueError) as problem:
        print(f"Privater Schlüssel nicht lesbar: {problem}")
        return 1
    if len(seed) != 32:
        print(f"Ein privater Schlüssel hat 32 Bytes, dieser {len(seed)}.")
        return 1

    major = current_major() if arguments.major is None else arguments.major
    for number in range(arguments.count):
        order = arguments.order or f"POOL-{number + 1:04d}"
        licence = Licence(
            major=major,
            purchased_on=date.today(),
            order=order,
            holder=arguments.holder,
        )
        print(make_key(seed, licence))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
