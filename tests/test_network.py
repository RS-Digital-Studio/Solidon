"""HTTPS-Vertrauen im gebauten macOS-Paket."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core import network


def test_the_packaged_macos_uses_the_shipped_certificate_bundle(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Der Pfad gehört zum Paket und nicht zur Python-Installation des Bauers."""
    bundle = tmp_path / "cacert.pem"
    bundle.write_text("Testzertifikat", encoding="utf-8")
    monkeypatch.delenv(network.CERTIFICATE_VARIABLE, raising=False)
    monkeypatch.setattr(network.certifi, "where", lambda: str(bundle))

    assert network.configure_certificates(platform="darwin", frozen=True)
    assert network.os.environ[network.CERTIFICATE_VARIABLE] == str(bundle)


def test_an_explicit_certificate_bundle_is_never_overwritten(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Eine Firmen-CA ist eine Vorgabe, kein Fehler, den Solidon korrigiert."""
    own = tmp_path / "company.pem"
    monkeypatch.setenv(network.CERTIFICATE_VARIABLE, str(own))

    assert not network.configure_certificates(platform="darwin", frozen=True)
    assert network.os.environ[network.CERTIFICATE_VARIABLE] == str(own)


def test_development_and_other_platforms_keep_their_system_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(network.CERTIFICATE_VARIABLE, raising=False)

    assert not network.configure_certificates(platform="darwin", frozen=False)
    assert not network.configure_certificates(platform="win32", frozen=True)
    assert network.CERTIFICATE_VARIABLE not in network.os.environ
