"""Alle Verweise aller Seiten gegen den Dateibestand halten."""
from __future__ import annotations
import re
from pathlib import Path

WEB = Path("website")
LINK = re.compile(r'(?:src|href)="([^"]+)"')
ID = re.compile(r'id="([^"]+)"')

pages = sorted([*WEB.glob("*.html"), *WEB.glob("*/*.html")])
ids: dict[Path, set[str]] = {p: set(ID.findall(p.read_text(encoding="utf-8"))) for p in pages}

bad: list[str] = []
for page in pages:
    text = page.read_text(encoding="utf-8")
    for ref in LINK.findall(text):
        if ref.startswith(("http://", "https://", "mailto:", "data:", "tel:")):
            continue
        if ref.startswith("#"):
            if ref[1:] and ref[1:] not in ids[page]:
                bad.append(f"{page.relative_to(WEB).as_posix()} -> {ref} (Sprungmarke fehlt)")
            continue
        target, _, anchor = ref.partition("#")
        resolved = (page.parent / target).resolve()
        if not resolved.exists():
            bad.append(f"{page.relative_to(WEB).as_posix()} -> {ref} (Datei fehlt)")
        elif anchor and resolved.suffix == ".html" and anchor not in ids.get(resolved, set()):
            # Datei da, Sprungmarke nicht
            got = set(ID.findall(resolved.read_text(encoding="utf-8")))
            if anchor not in got:
                bad.append(f"{page.relative_to(WEB).as_posix()} -> {ref} (Marke fehlt in Zieldatei)")

print(f"{len(pages)} Seiten geprüft")
for line in bad:
    print(" ", line)
print(f"{len(bad)} kaputte Verweise")
