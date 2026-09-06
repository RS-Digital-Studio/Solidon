"""HTTPS-Vertrauen in den gebauten Paketen."""

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


def test_development_and_a_working_system_store_keep_their_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Wer einen tragenden Speicher hat, behält ihn — auch im Paket.

    ``anchors`` und ``paths`` stehen ausdrücklich da: Ohne sie fragte der Test
    den Zertifikatsspeicher der Maschine, auf der er läuft, und antwortete auf
    einem Rechner ohne CAs anders als auf Roberts.

    **Die dritte Zeile ist die wichtige.** Ein eingerichtetes Linux hält seine
    Zertifikate in einem Verzeichnis, und OpenSSL liest daraus erst beim
    Prüfen — der Zähler steht dort auf null, obwohl jede Verbindung trägt. Wer
    nur zählte, tauschte diesen Speicher gegen den mitgelieferten aus und
    hebelte jede Firmen-CA darin aus.
    """
    monkeypatch.delenv(network.CERTIFICATE_VARIABLE, raising=False)

    assert not network.configure_certificates(
        platform="darwin", frozen=False, anchors=0, paths=False
    )
    assert not network.configure_certificates(
        platform="win32", frozen=True, anchors=85, paths=False
    )
    assert not network.configure_certificates(platform="linux", frozen=True, anchors=0, paths=True)
    assert network.CERTIFICATE_VARIABLE not in network.os.environ


def test_a_package_without_any_trust_anchor_gets_the_shipped_bundle(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Der Fall des ersten Flatpak-Kunden (Manjaro, 06.09.2026).

    Sein Protokoll trägt sechsmal ``CERTIFICATE_VERIFY_FAILED: unable to get
    local issuer certificate`` — bei jeder Update-Prüfung und bei beiden
    Versuchen, eine Rückmeldung zu senden. Dieselbe Kette trägt die
    Geräteaktivierung; ohne diesen Satz hätte er kaufen und nicht
    freischalten können.
    """
    bundle = tmp_path / "cacert.pem"
    bundle.write_text("Testzertifikat", encoding="utf-8")
    monkeypatch.delenv(network.CERTIFICATE_VARIABLE, raising=False)
    monkeypatch.setattr(network.certifi, "where", lambda: str(bundle))

    assert network.configure_certificates(platform="linux", frozen=True, anchors=0, paths=False)
    assert network.os.environ[network.CERTIFICATE_VARIABLE] == str(bundle)


def test_the_anchor_count_answers_even_when_the_store_refuses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ein Speicher, der sich nicht öffnen lässt, ist keiner — und wirft nicht."""

    def refuse() -> object:
        raise OSError("kein Speicher")

    monkeypatch.setattr(network.ssl, "create_default_context", refuse)
    assert network.trusted_anchors() == 0


def test_only_a_directory_openssl_can_look_things_up_in_counts_as_a_store(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Ein ``capath`` trägt erst mit den Namen, über die OpenSSL nachschlägt.

    **Der Fall, der den Kunden getroffen hätte.** Die
    ``org.freedesktop.Platform``-Laufzeit legt unter ``/etc/ssl/certs`` die
    Zertifikate ab, aber nicht die Verweise ``<hash>.<n>``, über die OpenSSL
    sie findet (``flatpak/freedesktop-sdk-base#3``). Wer nur fragt, ob es das
    Verzeichnis gibt, hält diesen Sandkasten für versorgt — und der Kunde
    bekommt weiter „unable to get local issuer certificate".
    """
    folder = tmp_path / "certs"
    folder.mkdir()

    def paths() -> object:
        return network.ssl.DefaultVerifyPaths(
            None,
            str(folder),
            "SSL_CERT_FILE",
            str(tmp_path / "fehlt.pem"),
            "SSL_CERT_DIR",
            str(folder),
        )

    monkeypatch.setattr(network.ssl, "get_default_verify_paths", paths)

    (folder / "ca-certificates.crt").write_text("Zertifikate ohne Verweise", encoding="utf-8")
    assert not network.default_paths_exist(), "ohne Hash-Namen findet OpenSSL hier nichts"

    (folder / "4f316efb.0").write_text("Verweis", encoding="utf-8")
    assert network.default_paths_exist()


def test_a_missing_directory_is_no_store(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Fehlt beides, bleibt nur der mitgelieferte Satz.

    ``ssl.get_default_verify_paths`` setzt ``cafile`` und ``capath`` selbst auf
    ``None``, wo nichts liegt; die kompilierten Pfade daneben stehen trotzdem
    da. Sie als Rückfall zu lesen hieße, die Frage für die Antwort zu halten.
    """

    def paths() -> object:
        return network.ssl.DefaultVerifyPaths(
            None,
            None,
            "SSL_CERT_FILE",
            "/usr/lib/ssl/cert.pem",
            "SSL_CERT_DIR",
            "/usr/lib/ssl/certs",
        )

    monkeypatch.setattr(network.ssl, "get_default_verify_paths", paths)
    assert not network.default_paths_exist()


def test_the_running_process_reports_its_own_anchors() -> None:
    """Die Zahl kommt aus dem Prozess und nicht aus einer Annahme."""
    assert network.trusted_anchors() >= 0
