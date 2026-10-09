"""Unterschreibt ``website/version.json`` (Bauplan §37.2).

Warum es diese Datei gibt: Die Prüfsumme eines Pakets steht in derselben Datei
wie seine Adresse. Gegen einen Angreifer im Netz reicht das — er bräuchte ein
Zertifikat für solidon3d.de. Gegen einen, der **den Server selbst** hat, reicht
es nicht: Der tauscht Paket und Prüfsumme gemeinsam aus, und in der
Installation widerspricht nichts.

Dagegen steht eine Unterschrift mit einem Schlüssel, der nicht auf dem Server
liegt. Solidon prüft sie mit den öffentlichen Schlüsseln aus der Installation
(``updates.RELEASE_PUBLIC_KEYS``), bevor es dem Inhalt überhaupt glaubt.

Nach jedem Bau und vor jedem Hochladen::

    python tools/sign_version.py --private geheim.key

Ohne Argument prüft es nur, ob die Datei, die dort liegt, eine gültige
Unterschrift trägt — das ist der Griff, den ``upload_website.py`` benutzt und
den man vor dem Hochladen von Hand tun kann::

    python tools/sign_version.py --check

**Schlüsselwechsel, Schritt für Schritt.** Eine Installation kennt nur die
Schlüssel, mit denen sie ausgeliefert wurde; eine Versionsdatei mit einem
anderen verwirft sie still. Deshalb wird der neue Schlüssel ausgeliefert,
bevor er unterschreibt:

1. Neues Paar erzeugen: ``python tools/sign_version.py --new-keypair``. Der
   private Teil geht in den Passwortmanager und auf Papier an einen zweiten
   Ort — **nie ins Repository und nie auf den Server**. Der öffentliche kommt
   **ans Ende** von ``RELEASE_PUBLIC_KEYS`` in ``app/core/updates.py``; der
   alte bleibt davor stehen.
2. Diese Version bauen und veröffentlichen, ihre Versionsdatei weiter mit dem
   **alten** Schlüssel unterschreiben. Jede ältere Installation sieht das
   Update und bekommt mit ihm den neuen Schlüssel.
3. Erst wenn die Installationen auf dieser Version oder neuer sind (die
   Statistik von ``website/api/count.php`` nennt die fragenden Versionen), mit
   dem neuen unterschreiben: ``--private neu.key --after-switch``. Was davor
   installiert wurde, sieht ab hier kein Update mehr und braucht den Download
   von der Website.
4. In der nächsten Version den alten öffentlichen Schlüssel aus
   ``RELEASE_PUBLIC_KEYS`` entfernen und seinen privaten Teil vernichten. Ist
   der alte verloren oder verraten, folgen Schritt 3 und 4 ohne Wartezeit.

Ohne ``--after-switch`` unterschreibt das Werkzeug nur mit dem ältesten
Schlüssel der Liste: So kann der neue nicht versehentlich schon in Schritt 2
unterschreiben — dann erführe keine ältere Installation je von der Version,
die ihn einführt.

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

from app.core import updates  # noqa: E402  — erst nach sys.path
from tools.make_licence_keys import public_key, sign  # noqa: E402

VERSION_FILE = ROOT / "website" / "version.json"


def new_keypair() -> int:
    """Ein frisches Paar. Läuft einmal je Schlüsselwechsel, und sein Ergebnis
    wird von Hand verteilt — der private Teil in den Passwortmanager, der
    öffentliche in den Quelltext."""
    seed = secrets.token_bytes(32)
    print("Privater Schlüssel (Passwortmanager, NICHT ins Repository):")
    print(f"  {seed.hex()}")
    print()
    print("Öffentlicher Schlüssel (in app/core/updates.py ans Ende von RELEASE_PUBLIC_KEYS):")
    print(f'  "{public_key(seed).hex()}"')
    print()
    print(
        "Der alte Schlüssel unterschreibt weiter, bis eine Version mit dem neuen "
        "draußen ist — Ablauf in tools/sign_version.py, „Schlüsselwechsel“."
    )
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


def _describe(key: bytes) -> str:
    """Welcher Schlüssel der Liste es ist — Stelle und Anfang, nie mehr."""
    keys = updates.RELEASE_PUBLIC_KEYS
    return f"Schlüssel {keys.index(key) + 1} von {len(keys)} ({key.hex()[:16]}…)"


def sign_file(seed: bytes, *, after_switch: bool = False) -> int:
    """Schreibt die Unterschrift in die Versionsdatei.

    Geprüft wird gleich danach mit demselben Weg, den die Anwendung geht: Ein
    Werkzeug, das eine Unterschrift schreibt und sie nicht gegenliest, meldet
    Erfolg auch dann, wenn beide Seiten verschiedene Bytes meinen.
    """
    key = public_key(seed)
    keys = updates.RELEASE_PUBLIC_KEYS
    if key not in keys:
        raise SystemExit(
            "Dieser private Schlüssel gehört zu keinem, gegen den die Anwendung "
            "prüft (updates.RELEASE_PUBLIC_KEYS). Eine damit unterschriebene Datei "
            "würde von jeder Installation verworfen."
        )
    if key != keys[0] and not after_switch:
        raise SystemExit(
            f"Das ist {_describe(key)}, nicht der älteste. Installationen, die ihn "
            "nicht kennen, verwerfen eine damit unterschriebene Datei und sehen "
            "das Update nie.\n"
            "  Solange die Version, die ihn einführt, nicht bei den Installationen "
            "angekommen ist: mit dem ältesten Schlüssel unterschreiben.\n"
            "  Danach (Schritt 3 des Schlüsselwechsels): --after-switch dazunehmen."
        )
    data = json.loads(VERSION_FILE.read_text(encoding="utf-8"))
    data[updates.SIGNATURE_FIELD] = sign(seed, updates.signed_payload(data)).hex()
    # ``newline=""``: der ganze Baum steht auf ``\n``, und hochgeladen wird der
    # Arbeitsbaum — siehe `stamp_assets.stamp_page`.
    VERSION_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline=""
    )
    if updates.signing_key(data) != key:
        raise SystemExit("Die eben geschriebene Unterschrift trägt nicht — nichts hochladen.")
    print(
        f"  {VERSION_FILE.name}: unterschrieben mit {_describe(key)}, Version {data.get('version')}"
    )
    return 0


def check_file() -> int:
    """Ob die Datei, die dort liegt, eine gültige Unterschrift trägt."""
    try:
        data = json.loads(VERSION_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError) as problem:
        print(f"  {VERSION_FILE.name}: nicht lesbar — {problem}")
        return 1
    key = updates.signing_key(data)
    if key is None:
        print(
            f"  {VERSION_FILE.name}: **ohne gültige Unterschrift**. Jede Installation "
            "ab 0.1.4 verwirft sie, und niemand erfährt von dieser Version.\n"
            "  Zu tun: python tools/sign_version.py --private <datei>"
        )
        return 1
    print(
        f"  {VERSION_FILE.name}: Unterschrift trägt mit {_describe(key)}, "
        f"Version {data.get('version')}"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--new-keypair", action="store_true", help="ein neues Schlüsselpaar")
    parser.add_argument("--private", type=Path, help="Datei mit dem privaten Schlüssel als Hex")
    parser.add_argument(
        "--after-switch",
        action="store_true",
        help="mit einem neueren als dem ältesten Schlüssel unterschreiben "
        "(Schritt 3 des Schlüsselwechsels)",
    )
    parser.add_argument(
        "--check", action="store_true", help="nur nachsehen, ob die Unterschrift trägt"
    )
    args = parser.parse_args(argv)

    if args.new_keypair:
        return new_keypair()
    if args.private:
        return sign_file(read_seed(args.private), after_switch=args.after_switch)
    return check_file()


if __name__ == "__main__":
    raise SystemExit(main())
