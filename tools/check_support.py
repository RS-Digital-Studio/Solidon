"""Prüft, ob die Rückmeldung wirklich ankommt.

Der Weg aus der Anwendung heraus hat ein Stück, das keine Suite prüfen kann:
den Server. `website/api/support.php` muss unter `httpdocs/api/` liegen, PHP
muss Post verschicken dürfen, und der Absender muss durch die eigene
SPF-Prüfung kommen. Läuft eines davon nicht, merkt es sonst der erste Kunde.

    .venv\\Scripts\\python.exe tools/check_support.py
    .venv\\Scripts\\python.exe tools/check_support.py --url http://localhost/api/support.php

Es geht eine **echte** Sendung mit einem kleinen Anhang hinaus; sie landet im
Support-Postfach und ist als Prüfung erkennbar. Wer das nicht will, lässt es.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.core import support  # noqa: E402
from app.core.errors import AppError  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=support.SUPPORT_URL, help="Adresse des Endpunkts")
    parser.add_argument("--contact", default="", help="Rückadresse für die Testsendung")
    arguments = parser.parse_args()

    ticket = support.Ticket(
        kind=support.KIND_QUESTION,
        message=(
            "Testsendung aus tools/check_support.py. Wenn diese Nachricht im Postfach "
            "liegt, steht der Weg aus der Anwendung zum Support."
        ),
        contact=arguments.contact,
        attachments=[
            support.Attachment("pruefung.txt", b"Ein Anhang, damit auch der Weg dafuer zaehlt.")
        ],
    )

    print(f"An: {arguments.url}")
    print(f"Größe: {ticket.total_bytes} Bytes, {len(ticket.attachments)} Anhang")
    try:
        receipt = support.send(ticket, arguments.url)
    except AppError as problem:
        print(f"\nNicht angekommen: {problem.title}")
        if problem.detail:
            print(f"  {problem.detail}")
        if problem.values.get("reason"):
            print(f"  {problem.values['reason']}")
        print("\nWas jetzt zu prüfen ist:")
        print("  - liegt website/api/support.php unter httpdocs/api/ ?")
        print("  - darf PHP dort mail() benutzen?")
        print("  - gibt es den Absender noreply@solidon3d.de, oder lässt SPF ihn zu?")
        return 1

    print(f"\nAngekommen. Vorgang: {receipt.reference or '(keine Nummer vergeben)'}")
    print("Jetzt im Support-Postfach nachsehen — angenommen ist nicht zugestellt.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
