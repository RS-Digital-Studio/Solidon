"""Bewegung im 3D-Fenster — was `motion.mix` und `motion.tween` zusagen.

Die übrigen Funktionen in `app/ui/motion.py` bewegen **Widgets**, und ihre
Tests stehen bei den anderen Fensterprüfungen in `test_ui.py`. Diese zwei tun
etwas anderes: Sie rechnen nur und überlassen dem Aufrufer, was mit dem Wert
geschieht — für einen VTK-Aktor gibt es kein `QGraphicsOpacityEffect`, und die
Farbe eines Körpers ist kein Qt-Property.

Weil sie ohne Fenster auskommen, sind sie auch ohne Fenster prüfbar. Das ist
kein Zufall, sondern der Grund für den Schnitt: Wo eine Blende auf ein Bild
wartet, wartet hier niemand.
"""

from __future__ import annotations

import pytest


def test_mixing_two_colours_hits_both_ends_and_the_middle() -> None:
    """0 ist die eine Farbe, 1 die andere, 0,5 liegt genau dazwischen.

    Die Mitte ist der Teil, der wirklich etwas prüft: Beide Enden bekäme auch
    eine Funktion, die den Bruchteil rundet und deshalb nie mischt.
    """
    from app.ui.motion import mix

    grau = (0.5, 0.5, 0.5)
    blau = (0.1, 0.4, 0.9)

    assert mix(grau, blau, 0.0) == pytest.approx(grau)
    assert mix(grau, blau, 1.0) == pytest.approx(blau)
    assert mix(grau, blau, 0.5) == pytest.approx((0.3, 0.45, 0.7))


def test_mixing_stays_inside_the_two_colours() -> None:
    """Über 1 und unter 0 wird beschnitten — eine Kurve schießt übers Ziel.

    `QEasingCurve.OutBack` und `OutElastic` geben Werte über 1 heraus; ohne
    Beschneidung käme dabei eine Farbkomponente über 1 zurück, und die ist
    keine Farbe mehr. VTK nimmt sie trotzdem an und zeigt etwas Helles — ein
    Fehler, der nicht auffällt, sondern nur falsch aussieht.
    """
    from app.ui.motion import mix

    schwarz = (0.0, 0.0, 0.0)
    weiss = (1.0, 1.0, 1.0)

    assert mix(schwarz, weiss, 1.4) == pytest.approx(weiss)
    assert mix(schwarz, weiss, -0.3) == pytest.approx(schwarz)


def test_mixing_refuses_two_colours_of_different_length() -> None:
    """RGB gegen RGBA ist ein Fehler und kein stiller Abschnitt.

    `zip` ohne `strict` hörte beim kürzeren auf: Aus einem RGBA-Ton würde
    stillschweigend RGB, die Deckkraft fiele weg, und niemand erführe davon.
    """
    from app.ui.motion import mix

    with pytest.raises(ValueError):
        mix((0.0, 0.0, 0.0), (1.0, 1.0, 1.0, 0.5), 0.5)


def test_a_tween_without_motion_still_sets_the_end(qt_app: object) -> None:
    """Ist Bewegung aus, kommt der Endzustand trotzdem — genau einmal.

    Das ist die Zusage, auf der jeder Aufrufer steht: Wer die Zielfarbe *nur*
    über `tween` setzt, ist offscreen, unter `SOLIDON3D_MOTION=aus` und auf
    einem Rechner ohne Bewegung genauso richtig wie mit. Ohne sie bliebe die
    Auswahl in der ganzen Suite auf der Ausgangsfarbe stehen, und jeder
    Farbtest darüber prüfte einen Zustand, den der Kunde nie sieht.

    „Genau einmal" gehört dazu: Ein Aufrufer, der je Schritt neu zeichnet,
    zeichnete sonst zweimal für nichts.
    """
    from PySide6.QtCore import QObject

    from app.ui.motion import animations_enabled, tween

    assert not animations_enabled(), "die Suite läuft offscreen — sonst misst dieser Test nichts"

    schritte: list[float] = []
    fertig: list[bool] = []
    laeuft = tween(QObject(), on_step=schritte.append, on_done=lambda: fertig.append(True))

    assert schritte == [1.0]
    assert fertig == [True]
    assert laeuft is None, "ohne Bewegung gibt es keine Animation zum Anhalten"


def test_a_running_tween_reports_the_end_exactly_once(qt_app: object, monkeypatch) -> None:
    """Mit Bewegung endet sie auf 1,0 — und meldet die 1,0 **genau einmal**.

    Der erste Entwurf setzte den Endwert zur Sicherheit noch einmal aus
    `finished` und begründete das damit, Qt bleibe bei kurzen Dauern auf 0,97
    stehen. **Das stimmt nicht.** Zwölf Läufe von 1 bis 220 ms, `OutCubic` und
    `OutBack`, endeten alle zwölf auf 1,0; die Gegenprobe zum Zusatz blieb
    grün, weil er nichts tat, was die Kurve nicht schon tut.

    Übrig bleibt die Zusage in ihrer scharfen Form, und die ist die nützliche:
    Ein Aufrufer, der je Schritt neu zeichnet, zeichnet den Endzustand
    **einmal**. Ein doppelter Aufruf wäre kein zweiter Gurt, sondern ein
    Neuzeichnen für einen Wert, der schon steht.

    Umgebogen wird nur die **Auskunft** von `animations_enabled`, nicht die
    Plattform: Die Anwendung läuft weiter offscreen, und `QVariantAnimation`
    braucht kein Bild. Gemessen wird damit die Sache und nicht die Lage.
    """
    from PySide6.QtCore import QEventLoop, QObject, QTimer

    from app.ui.motion import animations_enabled, tween

    monkeypatch.setenv("QT_QPA_PLATFORM", "xcb")
    assert animations_enabled(), "sonst prüft der Test denselben Zweig wie der davor"

    schritte: list[float] = []
    schleife = QEventLoop()
    QTimer.singleShot(2000, schleife.quit)  # Deckel, falls `finished` ausbleibt
    # Der Halter steht in einer Variablen, und das ist keine Förmlichkeit: Ein
    # `tween(QObject(), ...)` meldete beim ersten Lauf **null** Schritte —
    # Python räumt das namenlose Objekt sofort weg, und die Animation daran
    # stirbt mit. Genau dafür nimmt `tween` einen Halter entgegen.
    halter = QObject()
    tween(halter, on_step=schritte.append, on_done=schleife.quit, duration=60)
    schleife.exec()

    assert schritte, "die Animation hat keinen einzigen Schritt gemeldet"
    assert schritte[-1] == 1.0
    assert schritte.count(1.0) == 1, f"der Endwert kam mehrfach: {schritte}"
    assert len(schritte) > 1, "eine Animation, die nur den Endwert meldet, bewegt nichts"
