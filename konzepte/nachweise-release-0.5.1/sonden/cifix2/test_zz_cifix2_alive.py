from pathlib import Path

import pytest

import tests.test_ci_runner as runner


@pytest.mark.parametrize("error", [ProcessLookupError, FileNotFoundError])
def test_ende_zwischen_kill_und_lesen(monkeypatch, error):
    monkeypatch.setattr(runner.sys, "platform", "linux")
    monkeypatch.setattr(runner.os, "kill", lambda pid, sig: None)
    monkeypatch.setattr(Path, "is_dir", lambda self: True)

    def gone(self, *a, **k):
        raise error(3, "No such process")

    monkeypatch.setattr(Path, "read_text", gone)
    assert runner._process_alive(12345) is False


def test_lebend_und_zombie(monkeypatch):
    monkeypatch.setattr(runner.sys, "platform", "linux")
    monkeypatch.setattr(runner.os, "kill", lambda pid, sig: None)
    monkeypatch.setattr(Path, "is_dir", lambda self: True)
    monkeypatch.setattr(Path, "read_text", lambda self, *a, **k: "1 (py) S 0")
    assert runner._process_alive(1) is True
    monkeypatch.setattr(Path, "read_text", lambda self, *a, **k: "1 (py) Z 0")
    assert runner._process_alive(1) is False
