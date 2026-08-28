"""Ed25519-Signaturprüfung nach RFC 8032, in reinem Python.

Warum ohne Bibliothek: Der Prüfkern wird kompiliert ausgeliefert, damit im
Paket kein Bytecode liegt, den man um ein ``return True`` ergänzt. Eine
Fremdbibliothek käme als eigene Erweiterung daneben und wäre genau die Stelle,
an der ein Angreifer ansetzt — eine mitkompilierte Umsetzung nicht. Dazu
bleibt die Lizenzliste kurz (§36), und das Paket wächst nicht.

Die Anwendung prüft Kaufcodes und Geräte-Zertifikate und signiert ausschließlich
ihre Aktivierungsanforderung mit dem zufälligen privaten Geräteteil aus dem
System-Schlüsselbund. Der Aussteller der Kaufcodes und der Aktivierungsdienst
verwenden getrennte Schlüsselpaare.

Die reine Python-Umsetzung ist nicht als allgemeine Kryptobibliothek gedacht.
Der private Geräteteil schützt die Bindung gegen Kopieren von Dateien; der
private Aussteller- und Serverteil liegt nie in der Anwendung.

Geprüft wird gegen die Testvektoren aus RFC 8032 §7.1
(``tests/test_activation.py``) — eine eigene Krypto-Umsetzung ohne die wäre
unverantwortlich.
"""

from __future__ import annotations

import hashlib
from typing import Final

#: Primzahl des Körpers: 2^255 - 19.
FIELD_PRIME: Final = 2**255 - 19

#: Ordnung der Untergruppe.
GROUP_ORDER: Final = 2**252 + 27742317777372353535851937790883648493

#: Länge eines Punkts und eines Skalars in Bytes.
POINT_BYTES: Final = 32

#: Länge einer Signatur in Bytes.
SIGNATURE_BYTES: Final = 64

#: Ein Punkt in erweiterten Koordinaten (x, y, z, t) — projektiv, damit die
#: Punktaddition ohne Inversion auskommt.
Point = tuple[int, int, int, int]

#: Das neutrale Element der Gruppe.
IDENTITY: Point = (0, 1, 1, 0)


def _inverse(value: int) -> int:
    """Multiplikatives Inverses im Körper, über den kleinen Satz von Fermat."""
    return pow(value, FIELD_PRIME - 2, FIELD_PRIME)


#: Kurvenparameter d = -121665 / 121666.
_CURVE_D: Final = -121665 * _inverse(121666) % FIELD_PRIME

#: Quadratwurzel von -1, für die Rückgewinnung von x aus y.
_SQRT_MINUS_ONE: Final = pow(2, (FIELD_PRIME - 1) // 4, FIELD_PRIME)


def add(first: Point, second: Point) -> Point:
    """Punktaddition auf der verdrehten Edwards-Kurve (RFC 8032, §5.1.4)."""
    a = (first[1] - first[0]) * (second[1] - second[0]) % FIELD_PRIME
    b = (first[1] + first[0]) * (second[1] + second[0]) % FIELD_PRIME
    c = 2 * first[3] * second[3] * _CURVE_D % FIELD_PRIME
    d = 2 * first[2] * second[2] % FIELD_PRIME
    e, f, g, h = b - a, d - c, d + c, b + a
    return (e * f % FIELD_PRIME, g * h % FIELD_PRIME, f * g % FIELD_PRIME, e * h % FIELD_PRIME)


def multiply(scalar: int, point: Point) -> Point:
    """Skalarmultiplikation über Verdoppeln und Addieren.

    Die Laufzeit hängt am Skalar — das ist hier gleichgültig, weil der Skalar
    aus der Signatur kommt und öffentlich ist (siehe Modulkopf).
    """
    result: Point = IDENTITY
    remaining = scalar
    running = point
    while remaining > 0:
        if remaining & 1:
            result = add(result, running)
        running = add(running, running)
        remaining >>= 1
    return result


def _same_point(first: Point, second: Point) -> bool:
    """Gleichheit in projektiven Koordinaten — kreuzweise multipliziert, weil
    derselbe Punkt viele Darstellungen hat."""
    if (first[0] * second[2] - second[0] * first[2]) % FIELD_PRIME != 0:
        return False
    return (first[1] * second[2] - second[1] * first[2]) % FIELD_PRIME == 0


def _recover_x(y: int, sign: int) -> int | None:
    """Gewinnt x aus y und dem Vorzeichenbit zurück. ``None``, wenn es kein
    solches x gibt — dann war der Punkt keiner."""
    if y >= FIELD_PRIME:
        return None
    square = (y * y - 1) * _inverse(_CURVE_D * y * y + 1) % FIELD_PRIME
    if square == 0:
        return None if sign else 0
    x = pow(square, (FIELD_PRIME + 3) // 8, FIELD_PRIME)
    if (x * x - square) % FIELD_PRIME != 0:
        x = x * _SQRT_MINUS_ONE % FIELD_PRIME
    if (x * x - square) % FIELD_PRIME != 0:
        return None
    if (x & 1) != sign:
        x = FIELD_PRIME - x
    return x


def decompress(data: bytes) -> Point | None:
    """Liest einen gepackten Punkt. ``None``, wenn die Bytes keiner sind."""
    if len(data) != POINT_BYTES:
        return None
    packed = int.from_bytes(data, "little")
    sign = packed >> 255
    y = packed & ((1 << 255) - 1)
    x = _recover_x(y, sign)
    if x is None:
        return None
    return (x, y, 1, x * y % FIELD_PRIME)


def compress(point: Point) -> bytes:
    """Packt einen Punkt in 32 Bytes: y, und x nur als Vorzeichenbit."""
    inverse_z = _inverse(point[2])
    x = point[0] * inverse_z % FIELD_PRIME
    y = point[1] * inverse_z % FIELD_PRIME
    return int.to_bytes(y | ((x & 1) << 255), POINT_BYTES, "little")


def base_point() -> Point:
    """Der Basispunkt der Kurve. Aus y = 4/5 zurückgerechnet, wie in RFC 8032."""
    y = 4 * _inverse(5) % FIELD_PRIME
    x = _recover_x(y, 0)
    assert x is not None, "the base point is on the curve by definition"
    return (x, y, 1, x * y % FIELD_PRIME)


def _hash_to_scalar(*parts: bytes) -> int:
    return int.from_bytes(hashlib.sha512(b"".join(parts)).digest(), "little")


def _clamped_scalar(seed: bytes) -> tuple[int, bytes]:
    """Leitet den Ed25519-Skalar und das Präfix aus einem 32-Byte-Startwert ab."""
    if len(seed) != POINT_BYTES:
        raise ValueError("ein Ed25519-Startwert muss 32 Bytes lang sein")
    expanded = bytearray(hashlib.sha512(seed).digest())
    expanded[0] &= 248
    expanded[31] &= 63
    expanded[31] |= 64
    return int.from_bytes(expanded[:32], "little"), bytes(expanded[32:])


def public_key(seed: bytes) -> bytes:
    """Leitet den gepackten öffentlichen Schlüssel aus einem Startwert ab."""
    scalar, _prefix = _clamped_scalar(seed)
    return compress(multiply(scalar, base_point()))


def sign(seed: bytes, message: bytes) -> bytes:
    """Signiert Bytes deterministisch nach RFC 8032."""
    scalar, prefix = _clamped_scalar(seed)
    public = compress(multiply(scalar, base_point()))
    nonce = _hash_to_scalar(prefix, message) % GROUP_ORDER
    packed_r = compress(multiply(nonce, base_point()))
    challenge = _hash_to_scalar(packed_r, public, message) % GROUP_ORDER
    scalar_s = (nonce + challenge * scalar) % GROUP_ORDER
    return packed_r + scalar_s.to_bytes(POINT_BYTES, "little")


def has_small_order(point: Point) -> bool:
    """Ob der Punkt in der Torsionsuntergruppe liegt, also die Ordnung 1, 2, 4
    oder 8 hat.

    Solche Punkte sind gültige Kurvenpunkte, taugen aber nicht als
    öffentlicher Schlüssel: ``[k]A`` nimmt dann nur acht Werte an, und wer
    ``s`` frei wählt, trifft die Prüfgleichung durch bloßes Probieren. Genau
    das passiert mit den zweiunddreißig Nullbytes — sie sind ein Punkt der
    Ordnung 4, kein Nicht-Punkt.

    Drei Verdopplungen, mehr kostet die Prüfung nicht.
    """
    doubled = add(point, point)
    doubled = add(doubled, doubled)
    return _same_point(add(doubled, doubled), IDENTITY)


def verify(public_key: bytes, message: bytes, signature: bytes) -> bool:
    """Ob ``signature`` zu ``message`` und diesem öffentlichen Schlüssel passt.

    Jede Abweichung ist ein ``False``, nie eine Ausnahme: ein
    Lizenzschlüssel, den jemand halb kopiert hat, ist ein ungültiger
    Schlüssel und kein Programmfehler.
    """
    if len(public_key) != POINT_BYTES or len(signature) != SIGNATURE_BYTES:
        return False
    signer = decompress(public_key)
    if signer is None or has_small_order(signer):
        return False
    packed_r = signature[:POINT_BYTES]
    point_r = decompress(packed_r)
    if point_r is None:
        return False
    scalar_s = int.from_bytes(signature[POINT_BYTES:], "little")
    if scalar_s >= GROUP_ORDER:
        return False
    challenge = _hash_to_scalar(packed_r, public_key, message) % GROUP_ORDER
    return _same_point(multiply(scalar_s, base_point()), add(point_r, multiply(challenge, signer)))
