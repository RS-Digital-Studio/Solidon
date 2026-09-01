"""Statische Verträge für die bedienbaren Ziele der Website.

Der Browserlauf misst die wirkliche Seite. Diese Datei hält zusätzlich fest,
welche Komponenten ihren Zielraum ausdrücklich aus dem gemeinsamen Maß
beziehen. So kann eine spätere Verdichtung nicht unbemerkt wieder 29 Pixel
hohe Navigation oder 20 Pixel hohe Fußzeilenlinks erzeugen.
"""

from __future__ import annotations

import re
from pathlib import Path

WEBSITE = Path(__file__).resolve().parent.parent / "website"
CSS = WEBSITE / "style.css"
TARGET_SIZE = "var(--target-min)"


def _rules(css: str) -> dict[str, dict[str, str]]:
    """Liest Blattregeln ohne eine vollständige CSS-Engine zu behaupten.

    Kommentare werden vor dem Zerlegen entfernt. Das Muster sieht nur Blöcke
    ohne weitere geschweifte Klammern und trifft damit auch Regeln innerhalb
    von Medienabfragen, aber keine Medienabfrage selbst.
    """

    without_comments = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    rules: dict[str, dict[str, str]] = {}
    for selector_group, body in re.findall(
        r"([^{}]+)\{([^{}]*)\}", without_comments, flags=re.DOTALL
    ):
        declarations = {
            name.strip(): value.strip()
            for name, value in re.findall(r"([\w-]+)\s*:\s*([^;]+);", body)
        }
        for selector in selector_group.split(","):
            rules.setdefault(selector.strip(), {}).update(declarations)
    return rules


def test_interactive_components_use_shared_target_height() -> None:
    """Alle kompakten Bediengruppen erhalten mindestens 44 CSS-Pixel Höhe."""

    css = CSS.read_text(encoding="utf-8")
    rules = _rules(css)
    assert rules[":root"]["--target-min"] == "2.75rem"

    selectors = (
        ".brand",
        "nav.lang a",
        "nav.lang details.langs summary",
        "nav.lang .menu > summary",
        ".btn",
        ".tab",
        ".download-notes summary",
        ".donate-fine summary",
        ".donate-button",
        ".toc a",
        "footer.site a",
        ".release-picker select",
        ".activation-language select",
        ".activation-file .activation-file-button",
        ".activation-paste summary",
    )
    for selector in selectors:
        assert rules[selector]["min-block-size"] == TARGET_SIZE, selector


def test_compact_header_and_footer_targets_have_minimum_width() -> None:
    """Kurze Kürzel und Symbolgriffe bleiben auch waagerecht 44 Pixel groß."""

    rules = _rules(CSS.read_text(encoding="utf-8"))
    selectors = (
        ".brand",
        "nav.lang a",
        "nav.lang details.langs summary",
        "nav.lang .menu > summary",
        ".tab",
        "footer.site a",
    )
    for selector in selectors:
        assert rules[selector]["min-inline-size"] == TARGET_SIZE, selector


def test_range_uses_a_large_hit_box_without_thickening_its_track() -> None:
    """Der Regler vergrößert den Griffbereich, nicht die sichtbare Spur."""

    rules = _rules(CSS.read_text(encoding="utf-8"))
    range_rule = rules['.dial input[type="range"]']
    assert range_rule["min-block-size"] == TARGET_SIZE
    assert "height" not in range_rule
    assert "block-size" not in range_rule


def test_keyboard_focus_and_reduced_motion_contracts_remain_intact() -> None:
    """Zielgrößen verdrängen weder Fokusmarke noch Bewegungswunsch."""

    css = CSS.read_text(encoding="utf-8")
    rules = _rules(css)
    focus = rules[":focus-visible"]
    assert focus["outline"] == "2px solid var(--accent)"
    assert focus["outline-offset"] == "3px"
    assert rules[":root"]["color-scheme"] == "light dark"
    assert "@media (prefers-color-scheme: dark)" in css
    assert "@media (prefers-reduced-motion: reduce)" in css
    assert rules["html"]["scroll-behavior"] == "auto"
    assert rules["*"]["animation"] == "none !important"
    assert rules["*"]["transition-duration"] == "0.01ms !important"


def test_all_six_start_pages_share_the_accessible_stylesheet() -> None:
    """Die sechs Sprachfassungen tragen denselben Zielgrößenvertrag."""

    pages = (
        ("index.html", "style.css"),
        ("en/index.html", "../style.css"),
        ("es/index.html", "../style.css"),
        ("fr/index.html", "../style.css"),
        ("it/index.html", "../style.css"),
        ("pt/index.html", "../style.css"),
    )
    for relative, href in pages:
        html = (WEBSITE / relative).read_text(encoding="utf-8")
        links = re.findall(r'<link\b[^>]*rel="stylesheet"[^>]*>', html)
        own_styles = [link for link in links if f'href="{href}?v=' in link]
        assert len(own_styles) == 1, relative
