"""Den Drehpunkt am echten Fenster fahren — offscreen gibt es keinen Picker.

``_aim_rotation`` fragt seit dem 04.09.2026 zuerst, was in der Bildmitte
steht (``centre_hit`` → ``_world_at`` → ``vtkCellPicker``). Diese Kette prüft
die Suite an keiner Stelle: Offscreen bleibt ``Viewport.plotter`` auf ``None``,
und die Tests in ``tests/test_viewport_decisions.py`` setzen an ihre Stelle
eine Attrappe. Ob der Renderer im echten Fenster eine brauchbare Größe meldet
und ob der Picker in ihrer Mitte wirklich den Körper trifft, sagt keiner von
ihnen — das ist die Lücke, die dieser Prüfstand schließt.

Gemessen wird die Zusage selbst und nicht ihre Vorarbeit: **Was in der
Bildmitte lag, liegt nach dem Drehen noch dort.** Dazu die Gegenprobe mit dem
alten Weg (Drehpunkt aus der Mitte aller Körper), damit die Zahl einen
Vergleich hat.

    .venv\\Scripts\\python.exe -u .claude\\.state\\drehpunkt-2026-09-04\\fahre_drehpunkt.py

Exit 0 heißt: Der Drehpunkt sitzt dort, wo man hinsieht.

**Echtes Fenster, nicht offscreen** — und ein eigener Nutzerordner, wie
``tests/conftest.py`` ihn setzt (§38), damit der Lauf nicht in Roberts
Einstellungen schreibt. Beides wie im Prüfstand ``steuerung-2026-09-03``.
"""

from __future__ import annotations

import os
import tempfile

_EIGEN = tempfile.mkdtemp(prefix="drehpunkt-")
for _name in ("APPDATA", "LOCALAPPDATA", "HOME", "XDG_DATA_HOME", "XDG_CONFIG_HOME"):
    os.environ[_name] = _EIGEN
os.environ.pop("QT_QPA_PLATFORM", None)

from pathlib import Path  # noqa: E402

from PySide6.QtWidgets import QApplication  # noqa: E402

MESHES = Path(__file__).resolve().parents[3] / "tests" / "data" / "meshes"

#: Wie weit der Punkt in der Bildmitte nach einer Drehung höchstens wandern
#: darf (Millimeter). Die Platte ist 80 mm lang; ein Punkt, der um weniger als
#: zwei Millimeter rutscht, steht für den Betrachter still.
HAELT = 2.0


def bericht(name: str, gemessen: str, gut: bool, erwartet: str = "") -> bool:
    print(f"{'ok  ' if gut else 'ROT '}{name:<44} {gemessen}")
    if not gut and erwartet:
        print(f"    erwartet: {erwartet}")
    return gut


def main() -> int:
    from app.core.bootstrap import load_operations
    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    QApplication.instance() or QApplication([])
    load_operations()
    gut = True

    window = MainWindow(Session(), UiSettings())
    window.resize(1100, 750)
    window.show()
    QApplication.processEvents()
    viewport = window.viewport
    if viewport.plotter is None:
        print("ROT  kein Plotter — VTK ist nicht hochgekommen")
        return 1

    window.open_path(MESHES / "plate_holes.stl")
    window.session.wait_for_idle()
    QApplication.processEvents()
    viewport.show_scene(window.session.last_result)
    QApplication.processEvents()

    renderer = viewport.plotter.renderer
    breite, hoehe = renderer.GetSize()
    links, unten = renderer.GetOrigin()
    mitte = (links + breite // 2, unten + hoehe // 2)
    gut &= bericht(
        "der Renderer hat eine Bildmitte",
        f"{breite}x{hoehe} ab ({links},{unten}) -> Mitte {mitte}",
        breite > 1 and hoehe > 1,
        "eine Größe über null — sonst fragt centre_hit den Picker nie",
    )

    def in_der_mitte() -> tuple[float, float, float] | None:
        return viewport._world_at(*mitte)

    # Nah heran, schräg auf die Platte: die Bildmitte trifft ihre Oberfläche,
    # die Mitte aller Körper liegt eine halbe Plattenlänge dahinter. Genau die
    # Lage, in der die beiden Drehpunkte auseinanderlaufen.
    def von_vorn() -> None:
        viewport.set_camera_pose((60.0, -60.0, 45.0), (10.0, 8.0, 2.0), (0.0, 0.0, 1.0))
        QApplication.processEvents()

    von_vorn()
    treffer = viewport.centre_hit()
    gesehen = in_der_mitte()
    gut &= bericht(
        "centre_hit trifft den Koerper in der Mitte",
        f"{treffer}",
        treffer is not None and gesehen is not None,
        "einen Punkt auf der Platte — der Picker muss in der Bildmitte antworten",
    )

    # Der eigentliche Beweis: rechts ziehen, und der Punkt in der Bildmitte
    # bleibt stehen. Gefahren über VTKs eigene Ereignisse, damit der
    # Drehbeginn wirklich durch den Interaktionsstil läuft.
    def ziehen(taste: str, dx: int, dy: int) -> tuple[float, ...] | None:
        vorher = in_der_mitte()
        if vorher is None:
            return None
        iren = viewport.plotter.iren.interactor
        drueck = {
            "right": iren.RightButtonPressEvent,
            "middle": iren.MiddleButtonPressEvent,
        }[taste]
        los = {
            "right": iren.RightButtonReleaseEvent,
            "middle": iren.MiddleButtonReleaseEvent,
        }[taste]
        iren.SetEventPosition(*mitte)
        drueck()
        # In Schritten, nicht in einem Sprung: Das Kippen rechnet die Strecke
        # zwischen zwei Ereignissen, ein einziger Sprung wäre ein anderer Fall.
        for schritt in range(1, 6):
            iren.SetEventPosition(mitte[0] + dx * schritt // 5, mitte[1] + dy * schritt // 5)
            iren.MouseMoveEvent()
        los()
        QApplication.processEvents()
        nachher = in_der_mitte()
        if nachher is None:
            return None
        return tuple(abs(a - b) for a, b in zip(vorher, nachher, strict=True))

    von_vorn()
    neu = ziehen("right", 100, 0)
    weg_neu = max(neu) if neu else float("inf")
    gut &= bericht(
        "die Bildmitte haelt beim Drehen",
        f"{weg_neu:.2f} mm gewandert",
        weg_neu <= HAELT,
        f"höchstens {HAELT:.1f} mm — gedreht wird um das, was dort steht",
    )

    # Dasselbe für das gedrückte Rad: ``camera_step`` kippt um den Blickpunkt,
    # also gilt dort derselbe Drehpunkt. Ohne den Ruf im ``tilt``-Zweig des
    # Interaktionsstils wäre diese Zeile die einzige, die es merkt.
    von_vorn()
    gekippt = ziehen("middle", 0, 90)
    weg_kipp = max(gekippt) if gekippt else float("inf")
    gut &= bericht(
        "die Bildmitte haelt beim Kippen",
        f"{weg_kipp:.2f} mm gewandert",
        weg_kipp <= HAELT,
        f"höchstens {HAELT:.1f} mm — das gedrueckte Rad dreht dieselbe Ansicht",
    )

    # Gegenprobe: derselbe Zug mit dem alten Weg, also ohne die Bildmitte als
    # Quelle. Die Zahl daneben ist der ganze Unterschied dieser Änderung.
    von_vorn()
    frueher = viewport.centre_hit
    viewport.centre_hit = lambda: None  # type: ignore[method-assign]
    try:
        alt = ziehen("right", 100, 0)
    finally:
        viewport.centre_hit = frueher  # type: ignore[method-assign]
    weg_alt = max(alt) if alt else float("inf")
    print(f"    zum Vergleich, nur ueber rotation_centre: {weg_alt:.2f} mm")

    # Und über leerem Hintergrund gibt es nichts zu treffen — dort muss der
    # alte Weg übernehmen, statt dass gar kein Drehpunkt gesetzt wird. Senkrecht
    # nach oben geblickt: Die erste Fassung dieser Probe zielte schräg am Teil
    # vorbei und traf es über die Pickertoleranz doch (25,-25,0) — eine Probe,
    # die knapp danebenzielt, prüft die Toleranz und nicht den Hintergrund.
    viewport.set_camera_pose((0.0, -120.0, 40.0), (0.0, -120.0, 200.0), (0.0, 1.0, 0.0))
    QApplication.processEvents()
    gut &= bericht(
        "ueber dem Hintergrund faellt es zurueck",
        f"centre_hit = {viewport.centre_hit()}, rotation_centre = {viewport.rotation_centre()}",
        viewport.centre_hit() is None and viewport.rotation_centre() is not None,
        "kein Treffer, aber eine Koerpermitte",
    )

    # Die Kulissenfrage, und sie ist der Grund für die PickList in _world_at:
    # Senkrecht auf das Bett, weit neben dem Teil. Träfe der Picker dort die
    # Druckplatte, wäre der Drehpunkt wieder das, was 2026-08 als „gedreht
    # wurde um die Kulisse" behoben wurde.
    viewport.set_camera_pose((200.0, 100.0, 120.0), (200.0, 100.0, 0.0), (0.0, 1.0, 0.0))
    QApplication.processEvents()
    auf_dem_bett = viewport.centre_hit()
    gut &= bericht(
        "die Druckplatte zieht den Drehpunkt nicht",
        f"centre_hit = {auf_dem_bett}",
        auf_dem_bett is None,
        "kein Treffer — gepickt wird nur unter den Koerperaktoren",
    )

    window.wait_for_workers()
    return 0 if gut else 1


if __name__ == "__main__":
    raise SystemExit(main())
