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
Unterschrift trägt, und zwar mit einem Schlüssel, den die zuletzt
veröffentlichte Version schon kannte — das ist der Griff, den
``upload_website.py`` benutzt und den man vor dem Hochladen von Hand tun kann::

    python tools/sign_version.py --check

**Schlüsselwechsel.** Eine Installation kennt nur die Schlüssel, mit denen sie
ausgeliefert wurde; eine Versionsdatei mit einem anderen verwirft sie still.
Der Ablauf in vier Schritten steht an einer Stelle: ``Signierung/README.md``,
„Versionsdatei — der Release-Schlüssel und sein Wechsel“.

**Was das Werkzeug davon erzwingt.** Unterschrieben wird nur mit einem
Schlüssel, den schon die vorige veröffentlichte Version in ihrer Liste trug —
gelesen aus ihrem Git-Tag, nicht aus dem Arbeitsbaum. Schritt 2 mit dem neuen
lehnt es deshalb ab, gleich mit welchem Schalter und an welcher Stelle der
Liste er steht. Wechselt der Schlüssel gegenüber der zuletzt veröffentlichten
Versionsdatei (``HEAD:website/version.json``), verlangt es ``--after-switch``
als Bestätigung, dass die Wartezeit aus Schritt 3 um ist.

**Das Signieren steht hier und nicht in der Anwendung.** Sie prüft nur; sie
braucht das Signieren nie und trüge damit den Weg mit sich, den ein Angreifer
sucht. Dieselbe Aufteilung wie beim Lizenzschlüssel (``make_licence_keys.py``),
und die Kurvenarithmetik darunter ist dieselbe.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import secrets
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.core import updates  # noqa: E402  — erst nach sys.path
from tools.make_licence_keys import public_key, sign  # noqa: E402

VERSION_FILE = ROOT / "website" / "version.json"

#: Worüber die Besitzprobe eines neuen Schlüssels läuft — dahinter steht der
#: öffentliche Schlüssel selbst. Nur wer den privaten Teil hat, kann sie
#: erzeugen, und ein falsch eingetragener öffentlicher Teil besteht sie nicht.
PROOF_PREFIX = b"Solidon release key "

Version = tuple[int, int, int]


def proof_message(key: bytes) -> bytes:
    """Die Bytes, die die Besitzprobe für ``key`` unterschreibt."""
    return PROOF_PREFIX + key


def new_keypair() -> int:
    """Ein frisches Paar. Läuft einmal je Schlüsselwechsel, und sein Ergebnis
    wird von Hand verteilt — der private Teil in den Passwortmanager, der
    öffentliche in den Quelltext."""
    seed = secrets.token_bytes(32)
    key = public_key(seed)
    print("Privater Schlüssel (Passwortmanager, NICHT ins Repository):")
    print(f"  {seed.hex()}")
    print()
    print("Öffentlicher Schlüssel (in app/core/updates.py ans Ende von RELEASE_PUBLIC_KEYS):")
    print(f'  bytes.fromhex("{key.hex()}"),')
    print()
    print("Besitzprobe (in tests/release_signing.py nach KEY_PROOFS):")
    print(f'  "{key.hex()}": "{sign(seed, proof_message(key)).hex()}",')
    print()
    print(
        "Der alte Schlüssel unterschreibt weiter, bis eine Version mit dem neuen "
        "draußen ist — Ablauf in Signierung/README.md, „Schlüsselwechsel“."
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


def keys_in_source(source: str) -> tuple[bytes, ...]:
    """Die Release-Schlüssel, die ein Stand von ``app/core/updates.py`` trägt.

    Gelesen über ``ast``, nicht ausgeführt (Regel 11). Beide Formen zählen:
    ``RELEASE_PUBLIC_KEY`` bis 0.5.3 und die Liste ``RELEASE_PUBLIC_KEYS``.
    """
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign):
            targets, value = node.targets, node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets, value = [node.target], node.value
        else:
            continue
        names = {target.id for target in targets if isinstance(target, ast.Name)}
        if not names & {"RELEASE_PUBLIC_KEY", "RELEASE_PUBLIC_KEYS"}:
            continue
        return tuple(
            bytes.fromhex(call.args[0].value)
            for call in ast.walk(value)
            if isinstance(call, ast.Call)
            and isinstance(call.func, ast.Attribute)
            and call.func.attr == "fromhex"
            and call.args
            and isinstance(call.args[0], ast.Constant)
            and isinstance(call.args[0].value, str)
        )
    return ()


def _git(*arguments: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(ROOT), *arguments],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
    except OSError:
        return None
    return result.stdout if result.returncode == 0 else None


def as_version(text: object) -> Version | None:
    """``0.6.0`` als Zahlentripel; ``None``, wenn es keine Versionsnummer ist."""
    match = re.match(r"v?(\d+)\.(\d+)\.(\d+)", str(text))
    return None if match is None else (int(match[1]), int(match[2]), int(match[3]))


def published_key_lists() -> dict[Version, tuple[bytes, ...]]:
    """Die Release-Schlüssel jeder veröffentlichten Version, aus ihrem Git-Tag.

    Versionen ohne Schlüssel (vor der Unterschriftsprüfung) fehlen. Ohne Git
    oder ohne Tags ist das Ergebnis leer — die Prüfungen darüber halten dann an.
    """
    found: dict[Version, tuple[bytes, ...]] = {}
    for tag in (_git("tag", "--list", "v*") or "").split():
        version = as_version(tag)
        source = _git("show", f"{tag}:app/core/updates.py")
        if version is None or source is None:
            continue
        keys = keys_in_source(source)
        if keys:
            found[version] = keys
    return found


def previous_signer() -> bytes | None:
    """Welcher Schlüssel die zuletzt veröffentlichte Versionsdatei unterschrieb.

    Gelesen aus ``HEAD:website/version.json`` — der Arbeitsbaum trägt nach
    ``make_download.py`` schon die neue, noch unterschriebene oder nicht.
    """
    text = _git("show", "HEAD:website/version.json")
    if text is None:
        return None
    try:
        return updates.signing_key(json.loads(text))
    except ValueError:
        return None


def _short(key: bytes) -> str:
    return f"{key.hex()[:16]}…"


def key_problem(
    key: bytes, version: object, published: Mapping[Version, tuple[bytes, ...]]
) -> str | None:
    """Warum ``key`` die Versionsdatei dieser Version nicht unterschreiben darf.

    Er muss schon in der Liste der vorigen veröffentlichten Version stehen:
    Deren Installationen und alle davor fragen nach dieser Version, und nur
    was sie kennen, nehmen sie an. ``None``, wenn nichts dagegen spricht.
    """
    target = as_version(version)
    if target is None:
        return (
            f"version.json nennt keine Versionsnummer ({version!r}).\n"
            "  Zu tun: python tools/make_download.py neu fahren."
        )
    older = {number: keys for number, keys in published.items() if number < target}
    if not older:
        return (
            "Keine veröffentlichte Version vor dieser gefunden, deren Git-Tag "
            "einen Release-Schlüssel trägt — ob ihre Installationen den Schlüssel "
            "kennen, lässt sich so nicht prüfen.\n"
            "  Zu tun: git fetch --tags und erneut versuchen."
        )
    previous = max(older)
    known = older[previous]
    if key in known:
        return None
    name = ".".join(map(str, previous))
    return (
        f"Version {name}, die zuletzt veröffentlichte, kennt den Schlüssel "
        f"{_short(key)} nicht. Jede Installation bis {name} verwürfe diese "
        "Versionsdatei still und sähe das Update nie.\n"
        f"  Zu tun: mit dem Schlüssel unterschreiben, den {name} kennt "
        f"({', '.join(_short(k) for k in known)}). Ein neuer unterschreibt erst, "
        "wenn eine veröffentlichte Version ihn trägt (Schlüsselwechsel, Schritt 2)."
    )


def sign_file(
    seed: bytes,
    *,
    after_switch: bool = False,
    published: Mapping[Version, tuple[bytes, ...]] | None = None,
    previous: bytes | None = None,
) -> int:
    """Schreibt die Unterschrift in die Versionsdatei.

    Geprüft wird gleich danach mit demselben Weg, den die Anwendung geht: Ein
    Werkzeug, das eine Unterschrift schreibt und sie nicht gegenliest, meldet
    Erfolg auch dann, wenn beide Seiten verschiedene Bytes meinen.
    ``published`` und ``previous`` liest es sonst aus Git.
    """
    key = public_key(seed)
    if key not in updates.RELEASE_PUBLIC_KEYS:
        raise SystemExit(
            f"Der Schlüssel {_short(key)} steht nicht in updates.RELEASE_PUBLIC_KEYS. "
            "Eine damit unterschriebene Datei würde von jeder Installation verworfen.\n"
            "  Zu tun: den privaten Schlüssel aus dem Passwortmanager nehmen, der zu "
            "RELEASE_PUBLIC_KEYS gehört. Ein neuer kommt erst ans Ende der Liste und "
            "mit einer Version hinaus (Schlüsselwechsel, Schritt 1 und 2)."
        )
    data = json.loads(VERSION_FILE.read_text(encoding="utf-8"))
    problem = key_problem(
        key, data.get("version"), published_key_lists() if published is None else published
    )
    if problem is not None:
        raise SystemExit(problem)
    signer = previous_signer() if previous is None else previous
    if signer != key and not after_switch:
        raise SystemExit(
            f"Die zuletzt veröffentlichte Versionsdatei unterschrieb ein anderer "
            f"Schlüssel als {_short(key)}. Ab dieser Version sehen Installationen, die "
            "den neuen nicht kennen, kein Update mehr.\n"
            "  Zu tun: mit dem bisherigen Schlüssel unterschreiben. Ist die Wartezeit "
            "aus Schritt 3 des Schlüsselwechsels um: --after-switch dazunehmen."
        )
    data[updates.SIGNATURE_FIELD] = sign(seed, updates.signed_payload(data)).hex()
    # ``newline=""``: der ganze Baum steht auf ``\n``, und hochgeladen wird der
    # Arbeitsbaum — siehe `stamp_assets.stamp_page`.
    VERSION_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline=""
    )
    if updates.signing_key(data) != key:
        raise SystemExit("Die eben geschriebene Unterschrift trägt nicht — nichts hochladen.")
    print(f"  {VERSION_FILE.name}: unterschrieben mit {_short(key)}, Version {data.get('version')}")
    return 0


def version_file_problem(
    data: Mapping[str, Any], published: Mapping[Version, tuple[bytes, ...]] | None = None
) -> str | None:
    """Warum diese Versionsdatei nicht hinausgehen darf — ``None``, wenn sie darf.

    Dieselbe Prüfung für ``--check`` und die Uploadsperre: eine Unterschrift,
    die trägt, mit einem Schlüssel, den die vorige Version schon kannte.
    """
    key = updates.signing_key(data)
    if key is None:
        return (
            "ohne gültige Unterschrift. Jede Installation ab 0.1.4 verwirft sie, "
            "und niemand erfährt von dieser Version.\n"
            "  Zu tun: python tools/sign_version.py --private <datei>"
        )
    return key_problem(
        key, data.get("version"), published_key_lists() if published is None else published
    )


def check_file() -> int:
    """Ob die Datei, die dort liegt, hinausgehen darf."""
    try:
        data = json.loads(VERSION_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError) as problem:
        print(f"  {VERSION_FILE.name}: nicht lesbar — {problem}")
        return 1
    problem = version_file_problem(data)
    key = updates.signing_key(data)
    if problem is not None or key is None:
        print(f"  {VERSION_FILE.name}: {problem}")
        return 1
    print(
        f"  {VERSION_FILE.name}: Unterschrift trägt mit {_short(key)}, "
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
        help="bestätigt die Wartezeit, bevor der neue Schlüssel den alten ablöst "
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
