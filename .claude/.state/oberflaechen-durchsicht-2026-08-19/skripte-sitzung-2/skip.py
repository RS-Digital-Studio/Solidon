"""Jeder von Hand gepflegten Seite den Sprung an den Inhalt geben.

Eingesetzt wird direkt hinter ``<body>``, und ``<main>`` bekommt sein Ziel.
Die erzeugten Handbuchseiten stehen nicht dabei — die baut
``tools/make_manual.py``.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

WEB = Path(sys.argv[1] if len(sys.argv) > 1 else "website")

LABEL = {
    "de": "Zum Inhalt springen",
    "en": "Skip to content",
    "es": "Saltar al contenido",
    "fr": "Aller au contenu",
    "it": "Vai al contenuto",
    "pt": "Ir para o conteúdo",
}

GENERATED = {"handbuch.html", "manual.html"}

for page in sorted([*WEB.glob("*.html"), *WEB.glob("*/*.html")]):
    if page.name in GENERATED:
        continue
    text = page.read_text(encoding="utf-8")
    language = page.parent.name if page.parent != WEB else "de"
    label = LABEL[language]
    if 'class="skip"' in text:
        print(f"  schon da: {page.relative_to(WEB).as_posix()}")
        continue
    link = f'<a class="skip" href="#content">{label}</a>'
    changed, count = re.subn(r"<body>\n", f"<body>\n{link}\n", text, count=1)
    if count != 1:
        raise SystemExit(f"{page}: kein <body> gefunden")
    changed, count = re.subn(r"<main(\s|>)", r'<main id="content"\1', changed, count=1)
    if count != 1:
        raise SystemExit(f"{page}: kein <main> gefunden")
    page.write_text(changed, encoding="utf-8")
    print(f"  {page.relative_to(WEB).as_posix()} ({language})")
