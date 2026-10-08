"""Die Backend-Suche des System-Schlüsselbunds, einmal je Prozess.

Zwei Kernpakete lesen den Schlüsselbund: ``backends.keys`` für den eigenen
Schlüssel des Nutzers (§27) und ``activation.device`` für die Gerätekennung.
Die Suche liegt hier, damit keines der beiden das andere importiert.
"""

from __future__ import annotations

from typing import Any

#: Ob ``keyring`` sein Backend schon gesucht hat (:func:`find_backend_once`).
_backend_found = False


def find_backend_once(keyring: Any) -> None:
    """``keyring`` sein Backend suchen lassen — einmal, in einem eigenen Faden.

    **Die erste Backend-Suche hält ihre Rahmen fest** (gemessen unter Linux
    und macOS: ``get_all_keyring`` → ``_detect_backend`` → ``get_keyring`` →
    ``get_password``) und mit ihnen über ``f_back`` jeden Aufrufer darüber.
    Fand sie im Aufbau des Chat-Dialogs statt, lebte dieser Dialog bis zum
    Prozessende weiter (``test_widget_lifetime``, „1 von 10 KeyDialog“). Im
    eigenen Faden endet die Kette an dessen Anfang; gewartet wird trotzdem,
    damit der Aufrufer ein fertiges Backend bekommt.

    **Ein Fehler der Suche gehört dem Aufrufer.** ``keyring`` wirft etwa
    ``RuntimeError``, wenn das eingestellte Backend hier nicht nutzbar ist.
    Im Faden ungefangen ginge er an ``threading.excepthook`` und damit als
    Absturzbericht hinaus (``log._unhandled_thread``); so fliegt derselbe
    Fehler nach dem Warten beim Aufrufer, der ihn behandelt wie zuvor
    (``keys.read`` warnt, ``device._read_seed`` nennt Auswege). Als gefunden
    gilt das Backend erst nach einer erfolgreichen Suche.
    """
    global _backend_found
    if _backend_found:
        return
    import threading

    failures: list[Exception] = []

    def search() -> None:
        try:
            keyring.get_keyring()
        except Exception as error:  # geht an den Aufrufer, siehe oben
            failures.append(error)

    searching = threading.Thread(target=search, name="keyring-backend")
    searching.start()
    searching.join()
    if failures:
        raise failures.pop()
    _backend_found = True
