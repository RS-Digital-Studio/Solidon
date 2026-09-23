"""Schreibt ``kopiervorlage.html`` aus den Texten dieses Ordners.

    .venv\\Scripts\\python.exe marketing/gofundme/make_kopiervorlage.py

GoFundMes Editor übernimmt Fettdruck, wenn er als formatierter Text ankommt;
aus einer Markdown-Datei kopiert, landen dort Sternchen. Die Kopiervorlage
zeigt deshalb dieselben Texte formatiert im Browser: markieren, kopieren,
einfügen. Die Quelle bleibt die Markdown-Datei; übernommen wird genau der Teil
zwischen ``<!-- einsetzen:anfang -->`` und ``<!-- einsetzen:ende -->``.

Die Blöcke sind im Browser bearbeitbar, damit Robert die **[prüfen]**-Stellen
(gelb) vor dem Kopieren anpassen kann, ohne die Markdown-Datei zu öffnen.
Gespeichert wird dabei nichts.
"""

from __future__ import annotations

import html
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGET = HERE / "kopiervorlage.html"
START = "<!-- einsetzen:anfang -->"
END = "<!-- einsetzen:ende -->"


def block(name: str) -> str:
    """Der einzusetzende Teil einer Markdown-Datei."""
    text = (HERE / name).read_text(encoding="utf-8")
    if START not in text or END not in text:
        raise SystemExit(f"{name}: Marken {START} und {END} fehlen. Sie begrenzen den Text.")
    return text.split(START, 1)[1].split(END, 1)[0].strip()


def recommended_title(name: str) -> str:
    """Der als empfohlen markierte Titel aus der Tabelle der Datei."""
    text = (HERE / name).read_text(encoding="utf-8")
    found = re.search(r"\|\s*\*\*empfohlen\*\*\s*\|\s*\*\*(.+?)\*\*\s*\|", text)
    if found is None:
        raise SystemExit(f"{name}: keine Zeile „**empfohlen**“ in der Titeltabelle gefunden.")
    return found.group(1)


def inline(line: str) -> str:
    """Fett und Prüfmarken einer Zeile als HTML."""
    escaped = html.escape(line, quote=False)
    escaped = escaped.replace("**[prüfen]**", "<mark>[prüfen]</mark>")
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escaped)


def to_html(markdown: str) -> str:
    """Absätze mit Leerzeile dazwischen, Zeilen im Absatz mit Umbruch.

    Genau so legt GoFundMes Editor den Text selbst ab (gemessen an der
    Kampagnenseite am 23.09.2026: ``<div>`` je Zeile, ``<div><br></div>``
    als Leerzeile).
    """
    paragraphs = [part.strip() for part in markdown.split("\n\n") if part.strip()]
    rendered = []
    for paragraph in paragraphs:
        lines = [inline(line) for line in paragraph.split("\n")]
        rendered.append(f"<p>{'<br>'.join(lines)}</p>")
    return "\n".join(rendered)


def section(title: str, hint: str, content: str, key: str) -> str:
    """Ein Abschnitt mit Knopf zum Markieren und Kopieren."""
    return f"""
<section>
  <h2>{html.escape(title)}</h2>
  <p class="hint">{html.escape(hint)}</p>
  <button type="button" data-copy="{key}">Markieren und kopieren</button>
  <div class="block" id="{key}" contenteditable="true" spellcheck="true">
{content}
  </div>
</section>"""


def page() -> str:
    """Die ganze Seite."""
    title_de = recommended_title("kampagne-de.md")
    story = to_html(block("kampagne-de.md")) + "\n<p><br></p>\n" + to_html(block("kampagne-en.md"))
    update = to_html(block("update-1-de.md")) + "\n<p><br></p>\n" + to_html(block("update-1-en.md"))
    sections = [
        section(
            "Titel",
            "In GoFundMe: Bearbeiten → Details → Titel. Höchstens 60 Zeichen.",
            f"<p>{html.escape(title_de)}</p>",
            "titel",
        ),
        section(
            "Geschichte (Deutsch, darunter Englisch)",
            "Vor dem Kopieren lesen; hier lässt sich der Text noch ändern. In GoFundMe: "
            "Bearbeiten → Details → Geschichte, alten Text markieren, Strg+V.",
            story,
            "geschichte",
        ),
        section(
            "Historisches Update 1 (Deutsch, darunter Englisch)",
            "Nur die falsche Signaturzusage im bestehenden Bericht korrigieren. "
            "Keinen neuen Updatepost anlegen und keine Benachrichtigungen auslösen. "
            "Die vier damaligen Versionen und der Ausblick bleiben historisch erhalten.",
            update,
            "update",
        ),
    ]
    return f"""<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>GoFundMe-Kopiervorlage</title>
<style>
  :root {{ color-scheme: light dark; --bg: #f7f6f3; --fg: #1c1b1a; --muted: #5f5b55;
    --line: #e0ddd7; --accent: #a4551e; }}
  @media (prefers-color-scheme: dark) {{
    :root {{ --bg: #171614; --fg: #ece9e4; --muted: #a39e96; --line: #35322d;
      --accent: #e08b4e; }}
  }}
  body {{ margin: 0; background: var(--bg); color: var(--fg);
    font: 17px/1.55 "Segoe UI", system-ui, sans-serif; }}
  main {{ max-width: 760px; margin: 0 auto; padding: 32px 16px 64px; }}
  h1 {{ font-size: 1.6rem; margin: 0 0 .4rem; }}
  h2 {{ font-size: 1.2rem; margin: 2.2rem 0 .3rem; }}
  .hint, .lead {{ color: var(--muted); margin: .2rem 0 .8rem; }}
  /* Der Block ist immer schwarz auf weiß, auch im dunklen Schema: Beim Kopieren
     reisen Farben mit, und hellgraue Schrift wäre auf GoFundMes weißer Seite
     kaum zu lesen. */
  .block {{ background: #fff; color: #000; border: 1px solid var(--line);
    border-radius: 10px; padding: 18px 20px; outline: none; }}
  .block:focus {{ border-color: var(--accent); }}
  .block p {{ margin: 0 0 1em; }}
  mark {{ background: #ffe58a; color: #000; padding: 0 3px; border-radius: 3px; }}
  button {{ font: inherit; font-weight: 600; padding: 8px 16px; margin: 0 0 10px;
    border-radius: 8px; border: 1px solid var(--accent); background: var(--accent);
    color: #fff; cursor: pointer; min-height: 44px; }}
  .done {{ color: var(--muted); margin-left: 10px; }}
</style>
</head>
<body>
<main>
  <h1>GoFundMe-Kopiervorlage</h1>
  <p class="lead">Erzeugt aus den Markdown-Dateien in diesem Ordner. Änderungen hier
  werden nicht gespeichert. Anleitung: anleitung-einstellen.md, Schritt 4.</p>
  <p class="lead"><b>Lokale Freigabeschranke für 0.5.0:</b> Noch nicht veröffentlicht.
  Die neue Geschichte erst einsetzen, wenn das endgültige Windows-Paket mit geprüfter
  Anwendungs- und Installer-Signatur öffentlich verfügbar ist und die Website die
  genannten Preise zeigt. Bis dahin bleibt die öffentliche Kampagne beim Stand 0.4.4.</p>
  {"".join(sections)}
</main>
<script>
  for (const button of document.querySelectorAll("[data-copy]")) {{
    button.addEventListener("click", () => {{
      const target = document.getElementById(button.dataset.copy);
      const range = document.createRange();
      range.selectNodeContents(target);
      const selection = window.getSelection();
      selection.removeAllRanges();
      selection.addRange(range);
      let copied = false;
      try {{ copied = document.execCommand("copy"); }} catch (error) {{ copied = false; }}
      let note = button.nextElementSibling;
      if (!note || !note.classList.contains("done")) {{
        note = document.createElement("span");
        note.className = "done";
        button.after(note);
      }}
      note.textContent = copied ? "Kopiert. In GoFundMe mit Strg+V einfügen."
                                : "Markiert. Jetzt Strg+C drücken.";
    }});
  }}
</script>
</body>
</html>
"""


def main() -> int:
    """Schreibt die Kopiervorlage."""
    TARGET.write_text(page(), encoding="utf-8", newline="\n")
    print(f"geschrieben: {TARGET.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
