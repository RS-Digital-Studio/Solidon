"""Ed25519-Signaturprüfung nach RFC 8032, in reinem Python.

Warum ohne Bibliothek: Der Prüfkern wird kompiliert ausgeliefert, damit im
Paket kein Bytecode liegt, den man um ein ``return True`` ergänzt. Eine
Fremdbibliothek käme als eigene Erweiterung daneben und wäre genau die Stelle,
an der ein Angreifer ansetzt — eine mitkompilierte Umsetzung nicht. Dazu
bleibt die Lizenzliste kurz (§36), und das Paket wächst nicht.

**Nur Prüfen.** Signiert wird mit ``tools/make_licence_keys.py``; die
Anwendung braucht das nie und trägt es deshalb nicht mit. Die Primitiven
darunter sind gemeinsam — zwei Umsetzungen derselben Kurve wären der
klassische Weg zu einer Signatur, die nur eine Seite versteht.

Seitenkanalfestigkeit ist hier ohne Belang: auf dem Rechner des Nutzers liegt
allein der **öffentliche** Schlüssel. Es gibt nichts zu erlauschen.

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
    result: Point = (0, 1, 1, 0)
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


def verify(public_key: bytes, message: bytes, signature: bytes) -> bool:
    """Ob ``signature`` zu ``message`` und diesem öffentlichen Schlüssel passt.

    Jede Abweichung ist ein ``False``, nie eine Ausnahme: ein
    Lizenzschlüssel, den jemand halb kopiert hat, ist ein ungültiger
    Schlüssel und kein Programmfehler.
    """
    if len(public_key) != POINT_BYTES or len(signature) != SIGNATURE_BYTES:
        return False
    signer = decompress(public_key)
    if signer is None:
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
