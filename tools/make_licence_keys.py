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
        --archive D:\\Geheim\\solidon-licences.jsonl \
        --order A-1234 --holder "vorname@beispiel.de"
    python tools/make_licence_keys.py --private geheim.key --count 50 \
        --purchased-on 2026-11-01 \
        --archive D:\\Geheim\\solidon-licences.jsonl

Mit ``--count`` entstehen unpersonalisierte Schlüssel für einen Vorrat, den der
Zahlungsanbieter ausliefert; die Bestellkennung vergibt dann er, und die
Käuferkennung bleibt leer.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import secrets
import sys
import tempfile
from datetime import UTC, date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.activation import DEVICE_ACTIVATION_FROM, ed25519
from app.core.activation import key as licence_key
from app.core.activation.key import Licence, current_major, encode, format_key
from tools.licence_archive import archive_lock

ROOT = Path(__file__).resolve().parent.parent
ARCHIVE_FORMAT = 1


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


def _archive_target(parser: argparse.ArgumentParser, target: Path) -> Path:
    """Hält vollständige Kundenschlüssel und Käuferangaben aus dem Repository."""
    resolved = target.expanduser().resolve()
    try:
        resolved.relative_to(ROOT)
    except ValueError:
        return resolved
    parser.error(
        f"{resolved} liegt im Repository. Das private Schlüsselarchiv muss außerhalb davon liegen"
    )


def _existing_archive(path: Path, signer_public: bytes) -> list[dict[str, object]]:
    """Liest das private JSONL-Archiv streng; eine beschädigte Zeile hält an."""
    if not path.exists():
        return []
    records: list[dict[str, object]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as problem:
        raise ValueError(f"Schlüsselarchiv nicht lesbar: {problem}") from problem
    for number, line in enumerate(lines, start=1):
        try:
            record = json.loads(line)
        except (TypeError, ValueError) as problem:
            raise ValueError(f"Schlüsselarchiv, Zeile {number}, ist kein JSON") from problem
        if not isinstance(record, dict) or record.get("format") != ARCHIVE_FORMAT:
            raise ValueError(f"Schlüsselarchiv, Zeile {number}, hat das falsche Format")
        try:
            licence_text = record["key"]
            digest = record["digest"]
            major = record["major"]
            purchased_on = record["purchased_on"]
            order = record["order"]
            holder = record["holder"]
            transaction = record.get("transaction", "")
            archived_at = record["archived_at"]
            if (
                not isinstance(licence_text, str)
                or not isinstance(digest, str)
                or not isinstance(major, int)
                or isinstance(major, bool)
                or not isinstance(purchased_on, str)
                or not isinstance(order, str)
                or not isinstance(holder, str)
                or not isinstance(transaction, str)
                or not isinstance(archived_at, str)
                or not archived_at
            ):
                raise ValueError("metadata")
            licence = licence_key.parse(
                licence_text,
                public_key=signer_public,
                major=major,
            )
            expected_digest = hashlib.sha256(encode(licence)).hexdigest()
            if (
                digest != expected_digest
                or purchased_on != licence.purchased_on.isoformat()
                or order != licence.order
                or holder != licence.holder
                or transaction != " ".join(transaction.split()).strip()
                or len(transaction) > 128
            ):
                raise ValueError("mapping")
        except (KeyError, TypeError, ValueError, licence_key.LicenceKeyError) as problem:
            raise ValueError(f"Schlüsselarchiv, Zeile {number}, ist beschädigt") from problem
        records.append(record)
    digests = [str(record["digest"]) for record in records]
    if len(digests) != len(set(digests)):
        raise ValueError("Schlüsselarchiv enthält dieselbe Lizenz mehrfach")
    return records


def _archive_records(
    path: Path,
    generated: list[tuple[Licence, str]],
    signer_public: bytes,
) -> None:
    """Ergänzt das Archiv atomar, bevor auch nur ein Schlüssel ausgegeben wird."""
    with archive_lock(path):
        existing = _existing_archive(path, signer_public)
        known = {str(record["digest"]) for record in existing}
        now = datetime.now(UTC).isoformat()
        additions: list[dict[str, object]] = []
        for licence, licence_text in generated:
            digest = hashlib.sha256(encode(licence)).hexdigest()
            if digest in known:
                raise ValueError(f"Lizenz {digest[:12]} steht bereits im Schlüsselarchiv")
            known.add(digest)
            additions.append(
                {
                    "format": ARCHIVE_FORMAT,
                    "digest": digest,
                    "key": licence_text,
                    "major": licence.major,
                    "purchased_on": licence.purchased_on.isoformat(),
                    "order": licence.order,
                    "holder": licence.holder,
                    "transaction": "",
                    "archived_at": now,
                }
            )
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = "".join(
            json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"
            for record in (*existing, *additions)
        )
        temporary_name = ""
        try:
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                dir=path.parent,
                prefix=f".{path.name}.",
                suffix=".tmp",
                delete=False,
            ) as temporary:
                temporary.write(payload)
                temporary.flush()
                os.fsync(temporary.fileno())
                temporary_name = temporary.name
            Path(temporary_name).replace(path)
        finally:
            if temporary_name:
                Path(temporary_name).unlink(missing_ok=True)
    with contextlib.suppress(OSError):
        path.chmod(0o600)


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
    parser.add_argument(
        "--archive",
        type=Path,
        help="privates JSONL-Schlüsselarchiv außerhalb des Repositorys",
    )
    parser.add_argument("--order", default="", help="Bestellkennung")
    parser.add_argument("--holder", default="", help="auf wen der Schlüssel lautet")
    parser.add_argument("--count", type=int, default=1, help="wie viele Schlüssel")
    parser.add_argument("--major", type=int, default=None, help="Hauptversion, Vorgabe: die eigene")
    parser.add_argument(
        "--purchased-on",
        type=date.fromisoformat,
        default=date.today(),
        metavar="JJJJ-MM-TT",
        help="im Schlüssel gespeicherter Ausstelltag, Vorgabe: heute",
    )
    parser.add_argument(
        "--legacy",
        action="store_true",
        help="bewusster einzelner Bestandsschlüssel ohne Geräteaktivierung",
    )
    parser.add_argument(
        "--start",
        type=int,
        default=None,
        help="erste Nummer der Vorratskennung — ohne Angabe wird sie zufällig gewürfelt",
    )
    arguments = parser.parse_args(argv)

    if arguments.new_keypair:
        return _new_keypair()
    if arguments.private is None:
        parser.error("--private oder --new-keypair")
    if arguments.purchased_on < DEVICE_ACTIVATION_FROM and not arguments.legacy:
        parser.error(
            f"{arguments.purchased_on} liegt vor der Geräteaktivierung ab "
            f"{DEVICE_ACTIVATION_FROM}. Für den Verkaufsvorrat --purchased-on "
            f"{DEVICE_ACTIVATION_FROM} angeben; einen bewussten Einzelfall mit --legacy"
        )
    if arguments.legacy and arguments.purchased_on >= DEVICE_ACTIVATION_FROM:
        parser.error(
            "--legacy braucht --purchased-on vor "
            f"{DEVICE_ACTIVATION_FROM}; ab diesem Tag ist Geräteaktivierung verbindlich"
        )
    if arguments.legacy and (arguments.count != 1 or not arguments.order):
        parser.error("--legacy ist nur für einen ausdrücklich benannten Einzelfall mit --order")
    if arguments.archive is None:
        parser.error("--archive ist Pflicht, damit jeder ausgegebene Schlüssel auffindbar bleibt")
    archive = _archive_target(parser, arguments.archive)
    try:
        seed = bytes.fromhex(arguments.private.read_text(encoding="utf-8").strip())
    except (OSError, ValueError) as problem:
        print(f"Privater Schlüssel nicht lesbar: {problem}")
        return 1
    if len(seed) != 32:
        print(f"Ein privater Schlüssel hat 32 Bytes, dieser {len(seed)}.")
        return 1

    major = current_major() if arguments.major is None else arguments.major
    # Die Nutzlast war vollständig determiniert: Zähler ab eins plus heutiges
    # Datum — zwei Vorratsläufe am selben Tag erzeugten Byte für Byte
    # dieselben Schlüssel, und zwei Käufer bekamen denselben. Ohne --start
    # würfelt jeder Lauf seinen eigenen Namensraum.
    first = arguments.start if arguments.start is not None else None
    prefix = f"POOL-{secrets.token_hex(3).upper()}" if first is None else "POOL"
    made: set[str] = set()
    generated: list[tuple[Licence, str]] = []
    for number in range(arguments.count):
        if arguments.order:
            order = arguments.order
        elif first is not None:
            order = f"POOL-{first + number:04d}"
        else:
            order = f"{prefix}-{number + 1:04d}"
        licence = Licence(
            major=major,
            purchased_on=arguments.purchased_on,
            order=order,
            holder=arguments.holder,
        )
        licence_text = make_key(seed, licence)
        if licence_text in made:
            print(f"Doppelter Schlüssel für {order} — Abbruch, nichts davon ausgeben.")
            return 1
        made.add(licence_text)
        generated.append((licence, licence_text))
    try:
        _archive_records(archive, generated, public_key(seed))
    except (OSError, ValueError) as problem:
        print(f"Privates Schlüsselarchiv nicht geschrieben: {problem}")
        return 1
    for _licence, licence_text in generated:
        print(licence_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
