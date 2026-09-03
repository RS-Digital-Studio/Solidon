"""Die neue Steuerung am echten Fenster fahren — nicht am Wächter.

Die vier Wächter aus ``8550cac3`` prüfen die Tabelle und die reine Funktion.
Was keiner von ihnen prüft: ob VTK die Bewegung, die die Tabelle nennt, auch
ausführt. Deshalb geht dieser Prüfstand den Weg des Kunden — er löst VTKs
eigene Ereignisse aus, dieselben, an denen die Beobachter des Stils hängen —
und misst danach die Kamerastellung.

**Echtes Fenster, nicht offscreen.** Offscreen vergibt Qt keinen Fokus, und
ohne Fokus kommt kein Tastendruck an; die Flugtasten wären ungeprüft.

**Und ein eigener Nutzerordner**, wie ``tests/conftest.py`` ihn setzt (§38).
Sonst schriebe der Lauf die Vorgabe in Roberts echte Einstellungen.
"""

from __future__ import annotations

import os
import tempfile

_EIGEN = tempfile.mkdtemp(prefix="steuerung-")
for _name in ("APPDATA", "LOCALAPPDATA", "HOME", "XDG_DATA_HOME", "XDG_CONFIG_HOME"):
    os.environ[_name] = _EIGEN
os.environ.pop("QT_QPA_PLATFORM", None)

from PySide6.QtCore import QEvent, Qt  # noqa: E402
from PySide6.QtGui import QKeyEvent  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

#: Der Abstand, aus dem gemessen wird (Millimeter). **Fest gesetzt, nicht
#: übernommen:** Jede Bewegung dieser Steuerung skaliert mit der Entfernung
#: zum Blickpunkt, damit sie am Bildschirm gleich schnell wirkt. In einer
#: leeren Szene steht die Kamera anderthalb Millimeter vom Blickpunkt, und
#: dann ist ein voller Flugschritt 0,2 mm — was wie ein Befund aussieht und
#: keiner ist (gemessen am 03.09.2026, erste Fassung dieses Prüfstands).
ABSTAND = 300.0
#: Ab wann eine Bewegung zählt: ein Promille der Entfernung. Relativ, aus
#: demselben Grund.
MERKLICH = ABSTAND / 1000.0


def abstand(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    return max(abs(x - y) for x, y in zip(a, b, strict=True))


def anteil(vorher: tuple[float, ...], nachher: tuple[float, ...]) -> str:
    """Wie weit sich etwas bewegt hat, als Anteil der Entfernung.

    In Anteilen und nicht in Millimetern: Jede Bewegung dieser Steuerung
    skaliert mit dem Abstand zum Blickpunkt, eine Millimeterzahl sagt also nur
    zusammen mit ihm etwas.
    """
    return f"{abstand(vorher, nachher) / ABSTAND * 100:5.1f}%"


def bericht(name: str, erwartet: str, gemessen: str, gut: bool) -> bool:
    zeichen = "ok  " if gut else "ROT "
    print(f"{zeichen}{name:<34} {gemessen}")
    if not gut:
        print(f"    erwartet: {erwartet}")
    return gut


def zug(viewport, taste: str, dx: int, dy: int, start: tuple[int, int] = (400, 300)) -> None:
    """Eine Taste drücken, ziehen, loslassen — über VTKs eigene Ereignisse.

    Nicht über ``QTest.mousePress``: Qt reicht den Klick an das Widget, und
    erst dessen Übersetzung erzeugt das VTK-Ereignis. Wer hier ansetzt, misst
    die Übersetzung mit; wer bei VTK ansetzt, misst die Beobachter des Stils,
    und die sind der Gegenstand.
    """
    iren = viewport.plotter.iren.interactor
    drueck = {
        "left": iren.LeftButtonPressEvent,
        "middle": iren.MiddleButtonPressEvent,
        "right": iren.RightButtonPressEvent,
    }[taste]
    los = {
        "left": iren.LeftButtonReleaseEvent,
        "middle": iren.MiddleButtonReleaseEvent,
        "right": iren.RightButtonReleaseEvent,
    }[taste]
    iren.SetEventPosition(*start)
    drueck()
    # In Schritten, nicht in einem Sprung: Das Kippen rechnet die Strecke
    # zwischen zwei Ereignissen, ein einziger Sprung wäre ein anderer Fall.
    for schritt in range(1, 6):
        iren.SetEventPosition(start[0] + dx * schritt // 5, start[1] + dy * schritt // 5)
        iren.MouseMoveEvent()
    los()
    QApplication.processEvents()


#: Wie lange eine Taste für die Messung liegt (Millisekunden).
#: Bei ``FLIGHT_RATE`` = 1 sind 150 ms rund 15 % der Entfernung.
HALTEN_MS = 150


def taste(viewport, buchstabe: str) -> None:
    """Eine Taste drücken, kurz halten, loslassen — den Weg, den Qt geht.

    **Halten, nicht antippen.** Seit dem 03.09.2026 schaltet der Anschlag den
    Flug nur ein; gefahren wird in einem eigenen Takt, solange die Taste liegt.
    Ein Prüfstand, der nur drückt und sofort misst, sähe null Bewegung und
    hielte das für einen Befund.
    """
    from PySide6.QtTest import QTest

    schluessel = getattr(Qt.Key, f"Key_{buchstabe.upper()}")
    mod = Qt.KeyboardModifier.NoModifier
    QApplication.sendEvent(viewport, QKeyEvent(QEvent.Type.KeyPress, schluessel, mod, buchstabe))
    QTest.qWait(HALTEN_MS)
    QApplication.sendEvent(viewport, QKeyEvent(QEvent.Type.KeyRelease, schluessel, mod, buchstabe))
    QApplication.processEvents()


def main() -> int:
    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings, load_settings

    QApplication.instance() or QApplication([])
    # Ohne diesen Aufruf ist das Register leer, und schon die Menüs werfen.
    from app.core.bootstrap import load_operations

    load_operations()
    gut = True

    # 1. Die Vorgabe — frischer Nutzerordner, also der Zustand eines neuen Kunden.
    frisch = load_settings()
    gut &= bericht(
        "Vorgabe ist das eigene Schema",
        "solidon",
        f"navigation = {frisch.navigation!r}",
        frisch.navigation == "solidon",
    )

    window = MainWindow(Session(), UiSettings())
    window.resize(1100, 750)
    window.show()
    QApplication.processEvents()
    viewport = window.viewport
    if viewport.plotter is None:
        print("ROT  kein Plotter — VTK ist nicht hochgekommen")
        return 1

    # **Kein Körper.** Ein ``session.apply`` blockiert hier: Es wartet auf
    # seinen Arbeiter, und dieser Prüfstand hält den Hauptthread — dieselbe
    # Falle wie beim vermeintlichen NaN-Hänger vom 03.09.2026. Für die
    # Kamerabewegungen ist er auch nicht nötig: Bett und Bauraum stehen
    # ohnehin in der Szene, und die Steuerung bewegt die Kamera, nicht ein
    # Teil. Was einen Körper bräuchte — die Auswahl unter dem Zeiger — prüft
    # ``test_viewport_decisions`` ohne Fenster.
    viewport.set_navigation("solidon")
    QApplication.processEvents()

    def stellung() -> tuple[tuple[float, ...], tuple[float, ...]]:
        pose = viewport.camera_pose()
        return tuple(pose[0]), tuple(pose[1])

    def von_vorn() -> tuple[tuple[float, ...], tuple[float, ...]]:
        """Dieselbe Ausgangslage vor jeder Messung."""
        viewport.set_camera_pose((0.0, -ABSTAND, 0.0), (0.0, 0.0, 0.0), (0.0, 0.0, 1.0))
        QApplication.processEvents()
        return stellung()

    # 2. Links ziehen verschiebt: Standort und Blickpunkt wandern gemeinsam.
    vorher_p, vorher_f = von_vorn()
    zug(viewport, "left", 120, 0)
    nachher_p, nachher_f = stellung()
    gut &= bericht(
        "links ziehen verschiebt",
        "Standort und Blickpunkt wandern gemeinsam",
        f"Standort {anteil(vorher_p, nachher_p)} der Entfernung, "
        f"Blickpunkt {anteil(vorher_f, nachher_f)}",
        abstand(vorher_p, nachher_p) > MERKLICH and abstand(vorher_f, nachher_f) > MERKLICH,
    )

    # 3. Rechts ziehen dreht: der Blickpunkt bleibt, wo er ist.
    vorher_p, vorher_f = von_vorn()
    zug(viewport, "right", 100, 0)
    nachher_p, nachher_f = stellung()
    gut &= bericht(
        "rechts ziehen dreht",
        "Standort wandert, Blickpunkt steht",
        f"Standort {anteil(vorher_p, nachher_p)} der Entfernung, "
        f"Blickpunkt {anteil(vorher_f, nachher_f)}",
        abstand(vorher_p, nachher_p) > MERKLICH and abstand(vorher_f, nachher_f) < MERKLICH,
    )

    # 4. Das gedrückte Rad kippt — senkrecht, und nur senkrecht.
    vorher_p, vorher_f = von_vorn()
    zug(viewport, "middle", 0, 90)
    nachher_p, nachher_f = stellung()
    gut &= bericht(
        "gedruecktes Rad kippt",
        "Standort wandert, Blickpunkt steht",
        f"Standort {anteil(vorher_p, nachher_p)} der Entfernung, "
        f"Blickpunkt {anteil(vorher_f, nachher_f)}",
        abstand(vorher_p, nachher_p) > MERKLICH and abstand(vorher_f, nachher_f) < MERKLICH,
    )

    # 5. Und waagerecht tut das Rad nichts — sonst wäre es ein zweites Drehen.
    vorher_p, vorher_f = von_vorn()
    zug(viewport, "middle", 90, 0)
    nachher_p, nachher_f = stellung()
    gut &= bericht(
        "Rad waagerecht bewegt nichts",
        "keine Bewegung",
        f"Standort {anteil(vorher_p, nachher_p)} der Entfernung",
        abstand(vorher_p, nachher_p) < MERKLICH,
    )

    # 6. W fliegt — und nimmt den Blickpunkt mit.
    viewport.setFocus()
    QApplication.processEvents()
    vorher_p, vorher_f = von_vorn()
    taste(viewport, "w")
    nachher_p, nachher_f = stellung()
    gut &= bericht(
        "W fliegt vorwaerts",
        "Standort und Blickpunkt wandern",
        f"Standort {anteil(vorher_p, nachher_p)} der Entfernung, "
        f"Blickpunkt {anteil(vorher_f, nachher_f)}",
        abstand(vorher_p, nachher_p) > MERKLICH and abstand(vorher_f, nachher_f) > MERKLICH,
    )

    # 7. A und D seitwaerts, Q und E kippen.
    for buchstabe, was in (
        ("a", "A seitwaerts"),
        ("d", "D seitwaerts"),
        ("q", "Q kippt"),
        ("e", "E kippt"),
    ):
        vorher_p, _ = von_vorn()
        taste(viewport, buchstabe)
        nachher_p, _ = stellung()
        gut &= bericht(
            was,
            "die Kamera bewegt sich",
            f"Standort {anteil(vorher_p, nachher_p)} der Entfernung",
            abstand(vorher_p, nachher_p) > MERKLICH,
        )

    # 8. Eine Taste, die nicht belegt ist, bewegt nichts.
    vorher_p, _ = von_vorn()
    taste(viewport, "z")
    nachher_p, _ = stellung()
    gut &= bericht(
        "Z bewegt nichts",
        "keine Bewegung",
        f"Standort {anteil(vorher_p, nachher_p)} der Entfernung",
        abstand(vorher_p, nachher_p) < MERKLICH,
    )

    # 9. Und in einem fremden Schema fliegt gar nichts.
    viewport.set_navigation("slicer")
    QApplication.processEvents()
    vorher_p, _ = von_vorn()
    taste(viewport, "w")
    nachher_p, _ = stellung()
    gut &= bericht(
        "W in 'slicer' bewegt nichts",
        "keine Bewegung",
        f"Standort {anteil(vorher_p, nachher_p)} der Entfernung",
        abstand(vorher_p, nachher_p) < MERKLICH,
    )

    window.close()
    print()
    print("ALLES GRUEN" if gut else "MINDESTENS EINE ROT")
    return 0 if gut else 1


if __name__ == "__main__":
    raise SystemExit(main())
