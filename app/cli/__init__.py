"""Kommandozeilen-Einstieg oben auf dem Kern (§10, ROADMAP P0)."""


def launch(argv: list[str] | None = None) -> int:
    """Erfasst auch Fehler beim Laden der eigentlichen Kommandozeile."""
    from app.core.log import install_crash_logging

    install_crash_logging()
    from app.cli.main import main

    return main(argv)
