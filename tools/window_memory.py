"""Misst, was ein Fenster- und ein Sprachwechsel im echten Fenster kosten — und lassen.

Warum es das Werkzeug gibt: Der Registerpunkt zum Renderer führte „Speicher
über Fenster- und Sprachwechsel" als offen, weil es keinen Weg gab, ihn zu
messen. ``window_bench.py`` öffnet **ein** Projekt und misst die Wartezeit;
diese Frage ist eine andere — sie hängt am Lebenszyklus, nicht an der Dauer.
Beide teilen dieselben Bausteine (Messprofil, Arbeitssatz, die sichere
Abbaureihenfolge), deshalb liegen sie nebeneinander statt ineinander.

    python tools/window_memory.py                     # 5 Fenster, dann 5 Sprachwechsel
    python tools/window_memory.py --windows 8         # nur die Fensterrunden
    python tools/window_memory.py --languages 0       # ohne Sprachwechsel

**Was gemessen wird, ist die Steigung, nicht der Betrag.** Das erste Fenster
kostet einmalig, was Qt, der Renderer und die Kataloge brauchen; interessant
ist, ob die zweite, dritte und achte Runde etwas draufsetzen. Eine Kurve, die
sättigt, ist gesund; eine, die linear wächst, nennt die Zahl, mit der man
suchen geht. Dieselbe Frage stand am 23.08.2026 schon einmal — damals kostete
das erste Fenster 17 MB und jedes weitere nichts mehr, gemessen unter VTK.

**Ein echtes Fenster, kein Offscreen.** Offscreen baut die Ansicht keinen
Renderer (``viewport._available`` sagt vorher nein), und dann misst man den
Speicher von etwas, das es beim Kunden nicht gibt. Der Lauf braucht also
einen Bildschirm und einen wgpu-Adapter; ohne den sagt er es und hört auf.

Drei Fallen, die dieses Werkzeug schon kennt:

* **Der Speicherbereiniger läuft nicht auf Zuruf.** Zwischen den Runden
  stehen ein ``gc.collect()`` und ein Ereignisdurchlauf; ohne beides misst man
  die Verzögerung des Aufräumens und nicht, was liegen bleibt.
* **Der Arbeitssatz schwankt.** Windows gibt Seiten nicht sofort zurück;
  gemeldet wird deshalb je Runde der Wert **nach** dem Abbau, und die
  Steigung wird über die zweite Hälfte der Runden gerechnet — die erste
  trägt den einmaligen Aufbau.
* **Der Sprachwechsel baut das Fenster neu.** ``app.ui.app.rebuild_for_language``
  ist derselbe Weg, den die Anwendung geht; ein eigener Nachbau hier würde
  etwas anderes messen als das, was der Kunde auslöst.
"""

from __future__ import annotations

import argparse
import gc
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.window_bench import (  # noqa: E402  (der Pfad muss zuerst stehen)
    EVENT_DRAIN_ROUNDS,
    isolate,
    shutdown_window,
    working_set_mb,
)


def drain(application: Any) -> None:
    """Ereignisse abarbeiten und aufräumen, damit die nächste Messung zählt."""
    for _ in range(EVENT_DRAIN_ROUNDS):
        application.processEvents()
    gc.collect()
    for _ in range(EVENT_DRAIN_ROUNDS):
        application.processEvents()


def slope(values: list[float]) -> float:
    """Die mittlere Steigung über die zweite Hälfte der Runden, in MiB je Runde.

    Die erste Hälfte trägt den einmaligen Aufbau; wer sie mitrechnet, findet
    ein Leck, das keines ist.
    """
    tail = values[len(values) // 2 :]
    if len(tail) < 2:
        return 0.0
    return (tail[-1] - tail[0]) / (len(tail) - 1)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--windows", type=int, default=5, help="Fenster nacheinander (0: keine)")
    parser.add_argument("--languages", type=int, default=5, help="Sprachwechsel (0: keine)")
    parser.add_argument(
        "--profile",
        type=Path,
        default=ROOT / "tools" / ".window-bench-profile",
        help="Messprofil für die Nutzerverzeichnisse (bleibt zwischen Läufen)",
    )
    arguments = parser.parse_args()
    isolate(arguments.profile)

    from PySide6.QtWidgets import QApplication

    from app.core import bootstrap

    bootstrap.load_operations()

    from app.ui import viewport as viewport_module
    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    application = QApplication([])

    if not viewport_module._available():
        hint = viewport_module.unavailable_hint()
        print("Hier lässt sich keine 3D-Ansicht bauen, also misst dieser Lauf nichts.")
        if hint:
            print(hint)
        return 2

    print(f"Arbeitsspeicher am Anfang: {working_set_mb():.0f} MiB", flush=True)

    if arguments.windows:
        print(f"\n--- {arguments.windows} Fenster nacheinander")
        after: list[float] = []
        for round_number in range(1, arguments.windows + 1):
            window = MainWindow(Session(), UiSettings())
            window.show()
            drain(application)
            standing = working_set_mb()
            shutdown_window(window, application)
            del window
            drain(application)
            gone = working_set_mb()
            after.append(gone)
            print(
                f"Fenster {round_number}: steht {standing:.0f} MiB, nach dem Abbau {gone:.0f} MiB",
                flush=True,
            )
        print(f"Steigung über die zweite Hälfte: {slope(after):+.1f} MiB je Fenster")

    if arguments.languages:
        from app.i18n import get_language, set_language
        from app.i18n.catalog import available_languages
        from app.ui.app import rebuild_for_language

        sprachen = list(available_languages())
        print(f"\n--- {arguments.languages} Sprachwechsel ({', '.join(sprachen)})")
        session = Session()
        settings = UiSettings()
        window = MainWindow(session, settings)
        window.show()
        drain(application)
        print(f"Fenster steht: {working_set_mb():.0f} MiB", flush=True)
        after = []
        for round_number in range(1, arguments.languages + 1):
            ziel = sprachen[round_number % len(sprachen)]
            set_language(ziel)
            window = rebuild_for_language(application, window, settings)
            window.show()
            drain(application)
            standing = working_set_mb()
            after.append(standing)
            print(
                f"Wechsel {round_number} auf {get_language()}: {standing:.0f} MiB",
                flush=True,
            )
        print(f"Steigung über die zweite Hälfte: {slope(after):+.1f} MiB je Wechsel")
        shutdown_window(window, application)
        drain(application)
        print(f"Nach dem Abbau: {working_set_mb():.0f} MiB")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
