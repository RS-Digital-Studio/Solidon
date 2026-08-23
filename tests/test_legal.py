"""Die Rechtstexte (§37.2).

Geprüft wird nicht der Wortlaut — das entscheidet keine Suite —, sondern
dreierlei: dass die erzeugten Seiten zu ihrer Quelle passen, dass die Seite,
die einen Preis nennt, die drei Texte auch verlinkt, und dass kein Platzhalter
ausgeliefert wird, den jemand für eine Anschrift hält.

Der letzte Punkt ist der Grund, warum diese Datei existiert. Ein Impressum
ohne ladungsfähige Anschrift ist bei einem kostenpflichtigen Angebot
abmahnfähig, und ein `[PLZ UND ORT]` fällt beim Durchsehen einer fertigen
Seite nicht auf — es sieht aus wie Text.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

WEBSITE = ROOT / "website"

#: Quelle → erzeugte Seite. Beides gehört ins Repository: die Quelle, weil sie
#: gilt; die Seite, weil sie hochgeladen wird.
DOCUMENTS = {
    "EULA.md": "eula.html",
    "AGB.md": "agb.html",
    "WIDERRUF.md": "widerruf.html",
}

#: Seiten, die ein Verbraucher vor dem Kauf erreichen können muss.
REQUIRED_LINKS = ("agb.html", "widerruf.html", "eula.html", "impressum.html", "datenschutz.html")

#: Was ein Platzhalter ist: Großbuchstaben in eckigen Klammern.
PLACEHOLDER = re.compile(r"\[[A-ZÄÖÜ][A-ZÄÖÜ .\-,]{3,}\]")


@pytest.mark.parametrize("source_name", sorted(DOCUMENTS))
def test_the_source_of_every_legal_text_is_there(source_name: str) -> None:
    source = ROOT / source_name

    assert source.is_file(), f"{source_name} fehlt"
    assert len(source.read_text(encoding="utf-8")) > 1000, f"{source_name} ist zu kurz"


@pytest.mark.parametrize(("source_name", "page_name"), sorted(DOCUMENTS.items()))
def test_the_generated_page_matches_its_source(source_name: str, page_name: str) -> None:
    """Wer die Quelle ändert und das Werkzeug nicht laufen lässt, hat zwei
    Versionen eines Rechtstexts — und die falsche steht im Netz."""
    from make_legal import body_html

    page = WEBSITE / page_name
    assert page.is_file(), f"{page_name} fehlt — tools/make_legal.py läuft nicht?"

    expected = body_html((ROOT / source_name).read_text(encoding="utf-8"))
    assert expected in page.read_text(encoding="utf-8"), (
        f"{page_name} passt nicht mehr zu {source_name}.\n"
        "Neu erzeugen: .venv\\Scripts\\python.exe tools/make_legal.py"
    )


def test_the_installer_shows_the_agreement_and_not_the_copyright_notice() -> None:
    """Der Installer zeigte die Urheberrechtsnotiz — die sagt nicht, was der
    Käufer erwirbt."""
    text = ROOT / "packaging" / "eula.txt"

    assert text.is_file(), "packaging/eula.txt fehlt — tools/make_legal.py läuft nicht?"
    content = text.read_text(encoding="utf-8")
    assert "Endnutzer-Lizenzvertrag" in content
    assert "#" not in content, "Markdown-Zeichen im Text, den Inno Setup roh anzeigt"
    assert "**" not in content


@pytest.mark.parametrize("page_name", ["index.html", "en/index.html"])
def test_the_selling_page_links_every_legal_text(page_name: str) -> None:
    """Eine Seite, die einen Preis nennt, muss zu den Bedingungen führen."""
    html = (WEBSITE / page_name).read_text(encoding="utf-8")

    missing = [name for name in REQUIRED_LINKS if f"/{name}" not in html]
    assert not missing, f"{page_name} verlinkt nicht: {', '.join(missing)}"


def test_a_page_with_a_placeholder_says_that_it_is_a_draft() -> None:
    """Ein Platzhalter darf stehen — aber nicht heimlich.

    Die Anschrift fehlt noch, und sie einzutragen ist ein eigener Schritt.
    Bis dahin muss jede Seite, die einen Platzhalter trägt, sich auch als
    Entwurf ausweisen: `[PLZ UND ORT]` sieht im Fließtext aus wie Text, und
    ein Impressum ohne ladungsfähige Anschrift ist bei einem
    kostenpflichtigen Angebot abmahnfähig.

    Sobald die Angaben stehen, verschwindet der Hinweis von selbst — er wird
    beim Erzeugen gesetzt, nicht von Hand.
    """
    silent: list[str] = []
    for page in sorted(WEBSITE.rglob("*.html")):
        html = page.read_text(encoding="utf-8")
        hits = PLACEHOLDER.findall(html)
        if hits and 'class="draft"' not in html:
            silent.append(f"{page.relative_to(WEBSITE).as_posix()}: {', '.join(sorted(set(hits)))}")

    assert not silent, (
        "Platzhalter ohne Entwurfshinweis — hier hält jemand sie für Angaben:\n" + "\n".join(silent)
    )


def test_an_unreviewed_contract_keeps_its_reservation() -> None:
    """Die fachliche Prüfung hängt an keinem Platzhalter.

    Beides an einem Satz zu führen war zu wenig: mit dem Namen des
    Zahlungsdienstleisters fiel der letzte Platzhalter aus den AGB, und ein
    ungeprüfter Vertrag hätte ohne jeden Vorbehalt dagestanden. Der Hinweis
    fällt erst, wenn jemand `REVIEW_PENDING` umstellt — also wenn die Prüfung
    stattgefunden hat.
    """
    import tools.make_legal as make_legal

    if not make_legal.REVIEW_PENDING:
        pytest.skip("die Texte sind geprüft, der Vorbehalt gehört weg")

    for _source, target, _label in make_legal.DOCUMENTS:
        html = (WEBSITE / target).read_text(encoding="utf-8")
        assert 'class="draft"' in html, f"{target} trägt keinen Vorbehalt"


def test_the_sweep_over_the_pages_finds_something_to_read() -> None:
    """``test_the_selling_page_links_every_legal_text`` sammelt fehlende
    Verweise und sichert zu, dass die Liste leer ist.

    Läuft die Schleife nie, ist sie das auch. Der Glob ist die Grundmenge, und
    ein umbenannter Ordner macht ihn leer, ohne dass jemand etwas merkt.
    """
    pages = sorted(WEBSITE.rglob("*.html"))

    assert len(pages) >= 10, f"nur {len(pages)} Seiten unter {WEBSITE} — falscher Pfad?"


#: Was Anlage 2 zu Art. 246a § 1 Abs. 2 Satz 1 Nr. 1 EGBGB wörtlich vorgibt.
#:
#: Der Gesetzgeber schreibt das Muster-Widerrufsformular im Wortlaut vor; ein
#: Unternehmer darf es sprachlich anpassen, aber nicht entstellen. Die Zeilen
#: hier sind bewusst **kurz gehalten** — geprüft wird, dass die tragenden
#: Bestandteile unverfälscht ankommen, nicht die Zeilenumbrüche.
FORM_LINES: tuple[str, ...] = (
    "Hiermit widerrufe(n) ich/wir (*) den von mir/uns (*) abgeschlossenen Vertrag",
    "Bestellt am (*)",
    "Name des/der Verbraucher(s)",
    "Unzutreffendes streichen",
)


def test_the_withdrawal_form_survives_the_converter() -> None:
    r"""Der vorgeschriebene Wortlaut steht unverfälscht auf der Seite.

    **Gefunden von 3d-druck-58 am 23.08.2026:** Der Markdown-Konverter kannte
    kein ``\*``. Wo die Quelle korrekt ``(\*)`` zweimal je Zeile schreibt, las
    ``_EMPHASIS`` die beiden als Paar — im Formular stand deshalb
    ``ich/wir (\<em>) den von mir/uns (\</em>)``, mitten in dem Text, den das
    Gesetz wörtlich vorgibt.

    **Warum der bestehende Test es nicht fing:**
    ``test_the_generated_page_matches_its_source`` erzeugt seine Erwartung mit
    ``body_html`` — also mit genau der Funktion, die den Fehler gemacht hat. Er
    prüft, ob die Seite **aktuell** ist, nicht ob sie **richtig** ist. Gegen
    einen Konverter, der verfälscht, ist er blind, weil er dieselbe
    Verfälschung erwartet.

    Dieser Test hat deshalb einen **Sollwert von außen**: den Gesetzestext.
    Selbstkonsistenz und Sollwert sehen im Code gleich aus, und der Unterschied
    entscheidet, ob eine Prüfung etwas wert ist.
    """
    page = (WEBSITE / "widerruf.html").read_text(encoding="utf-8")
    plain = re.sub(r"<[^>]+>", "", page).replace("&nbsp;", " ")

    for line in FORM_LINES:
        assert line in plain, (
            f"das Muster-Widerrufsformular ist entstellt — {line!r} steht nicht auf der "
            "Seite. Anlage 2 zu Art. 246a EGBGB gibt den Wortlaut vor."
        )

    assert "\\" not in plain, (
        "im Fließtext des Formulars steht ein Gegenschrägstrich — der Konverter hat "
        "eine geschützte Zeichenfolge nicht durchgereicht"
    )

    # **Die Gegenprobe im Test selbst.** Ein Verbot, das am echten Fehlerbild
    # nicht greift, sieht aus wie eine Absicherung und ist keine — dieselbe
    # Falle, gegen die dieser Test antritt.
    #
    # Die erste Fassung verbot ``<em>``, ``\*``, ``\<`` und ``&lt;em&gt;``.
    # **Keines der vier greift**, gemessen von 3d-druck-58: Die Tags sind zu
    # diesem Zeitpunkt längst weggestrippt, und das Sternchen wurde ja gerade
    # zu einem Tag, steht also nicht mehr da. Übrig bleibt genau der
    # Gegenschrägstrich oben.
    broken = plain.replace(
        "ich/wir (*) den von mir/uns (*)",
        "ich/wir (" + chr(92) + ") den von mir/uns (" + chr(92) + ")",
    )
    assert broken != plain, "das Fehlerbild ließ sich nicht nachstellen"
    assert "\\" in broken, "die Gegenprobe erzeugt kein Fehlerbild, das das Verbot fängt"
