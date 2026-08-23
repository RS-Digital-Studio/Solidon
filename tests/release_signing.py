"""Unterschriebene Versionsdateien für die Tests (§37.2).

``updates.check`` nimmt seit der Unterschriftsprüfung nur noch an, was von uns
kommt — und der private Schlüssel dafür liegt im Passwortmanager, nicht im
Repository. Ein Test kann also keine echte Unterschrift erzeugen.

Deshalb ein **eigenes Paar für die Suite**: Die Fixture setzt den öffentlichen
Teil an die Stelle von :data:`app.core.updates.RELEASE_PUBLIC_KEY`, und
:func:`signed` unterschreibt eine Antwort mit dem passenden privaten Teil.
Damit prüfen die Tests denselben Weg, den die Anwendung geht — nur mit einem
Schlüssel, den sie kennen dürfen.

**Was das nicht prüft, prüft** ``test_the_published_version_file_is_signed``:
ob die Datei, die wir tatsächlich ausliefern, gegen den **echten** Schlüssel
trägt. Ein Test, der nur seinen eigenen Schlüssel gegen seine eigene Signatur
hält, bestätigt die Arithmetik und nicht die Auslieferung.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

from app.core import updates
from tools.make_licence_keys import public_key, sign

#: Der private Schlüssel der Suite. Er darf hier stehen: Er unterschreibt
#: nichts, was je einen Rechner erreicht, und die Anwendung prüft im Betrieb
#: gegen einen anderen.
TEST_SEED = bytes.fromhex("4a1d9e6c05b83f27ea94c1d0728b6f35a9c47e18d260b3fa815c9d4e70362bc1")

#: Der **echte** öffentliche Schlüssel, festgehalten beim Import.
#:
#: Beim Import und nicht später: Danach hat die Fixture ihn ersetzt, und wer
#: ihn dann läse, bekäme den der Suite. Gebraucht wird er von genau einem Test
#: — dem, der die ausgelieferte ``version.json`` prüft und dafür den Schlüssel
#: braucht, gegen den die Kunden prüfen.
REAL_PUBLIC_KEY = updates.RELEASE_PUBLIC_KEY


def signed(payload: dict[str, Any]) -> dict[str, Any]:
    """Dieselbe Antwort, mit gültiger Unterschrift für die Suite."""
    body = {key: value for key, value in payload.items() if key != updates.SIGNATURE_FIELD}
    return {**body, updates.SIGNATURE_FIELD: sign(TEST_SEED, updates.signed_payload(body)).hex()}


@pytest.fixture(autouse=True)
def accept_test_signatures(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Lässt die Suite ihre eigenen Unterschriften annehmen.

    ``autouse``, damit kein Test sie vergessen kann: Wer sie vergäße, bekäme
    ``None`` zurück und suchte den Fehler in seiner Antwort statt in der
    fehlenden Unterschrift — genau die Verwechslung, die diese Umstellung
    einmal gekostet hat.
    """
    monkeypatch.setattr(updates, "RELEASE_PUBLIC_KEY", public_key(TEST_SEED))
    yield
