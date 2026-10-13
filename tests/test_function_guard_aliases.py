"""Gebundene und dynamisch gelesene Methoden bleiben Bedienumwege (NC-M1)."""

import pytest

from tools.function_guard import forbidden_calls


@pytest.mark.parametrize(
    "source",
    [
        "apply = self.window.session.apply\napply('x', [])",
        "getattr(self.window.session, 'apply')('x', [])",
        "def run(button, name):\n    action = getattr(button, name)\n    action()",
        "s = self.window.session\nt = s\nt.apply('x', [])",
        "s = self.window.session\nt = s\ngetattr(t, 'apply')('x', [])",
        "s = self.window.session\nQMetaObject.invokeMethod(s, 'apply')",
        "def run(button, name):\n    first = getattr(button, name)\n"
        "    second = first\n    second()",
        "def outer():\n    s = self.window.session\n    def inner():\n        s.apply('x', [])",
        "def outer(button, name):\n    action = getattr(button, name)\n"
        "    def inner():\n        action()",
    ],
)
def test_method_and_session_aliases_cannot_hide_an_action(source: str) -> None:
    """Jeder Umweg steht allein; kein Treffer am Nachbarn kann ihn verdecken."""
    assert forbidden_calls(source), source


@pytest.mark.parametrize(
    "source",
    [
        "phase = getattr(self, f'phase_{name}')\nphase()",
        "value = getattr(button, name)",
        "getattr(self.history, 'apply')('x', [])",
        "def first():\n    s = self.window.session\ndef second(s):\n    s.apply('x', [])",
        "def first(button, name):\n    action = getattr(button, name)\n"
        "def second(action):\n    action()",
        "def first():\n    name = 'click'\ndef second(button):\n"
        "    name = 'text'\n    getattr(button, name)()",
        "s = self.window.session\ns = self.history\ns.apply('x', [])",
        "action = getattr(button, name)\naction = allowed\naction()",
    ],
)
def test_alias_information_stays_in_its_lexical_scope(source: str) -> None:
    """Eigene Phasen, reines Lesen und gleichnamige lokale Bindungen bleiben erlaubt."""
    assert forbidden_calls(source) == [], source
