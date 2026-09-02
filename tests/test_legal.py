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
    "DATENSCHUTZ.md": "datenschutz.html",
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

    contract = source_name != "DATENSCHUTZ.md"
    expected = body_html((ROOT / source_name).read_text(encoding="utf-8"), contract)
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


def test_a_demo_support_payment_does_not_turn_into_a_licence_order() -> None:
    """Der PayPal-Weg widerspricht weder AGB noch Widerrufsbelehrung.

    Beide Texte sagten vorher pauschal, während der Demo gebe es keinen
    Zahlungsdienstleister. Seit dem Unterstützungsweg ist das falsch, obwohl es
    weiterhin keinen Kauf gibt. Die Grenze ist die Gegenleistung und muss in
    Quelle und erzeugter Seite dieselbe bleiben.
    """
    agb = (ROOT / "AGB.md").read_text(encoding="utf-8")
    withdrawal = (ROOT / "WIDERRUF.md").read_text(encoding="utf-8")
    agb_words = " ".join(agb.split())

    assert "unentgeltliche Zuwendung ohne Gegenleistung" in agb_words
    assert "keine Bestellung einer Lizenz" in agb_words
    assert "keine steuerliche Zuwendungsbestätigung" in agb_words
    assert "Profileinstellungen" in withdrawal
    assert "PayPal-Unterstützungsweg" in (WEBSITE / "agb.html").read_text(encoding="utf-8")
    assert "Profileinstellungen" in (WEBSITE / "widerruf.html").read_text(encoding="utf-8")


def test_paypal_support_is_local_first_and_never_suggests_tax_deductibility() -> None:
    """Vor PayPal steht ein lokaler Hinweis; die Zahlung kauft nichts."""
    privacy = (ROOT / "DATENSCHUTZ.md").read_text(encoding="utf-8")
    privacy_words = " ".join(privacy.split())

    for required in (
        "Freiwillige Unterstützung über PayPal",
        "öffnet die Aktion *Solidon unterstützen …* zunächst nur einen lokalen Dialog",
        "*PayPal im Browser öffnen*",
        "Unterstützungsbereich ebenfalls zuerst einen lokal verarbeiteten Hinweis",
        "*Mit PayPal unterstützen* führt zu PayPal",
        "keine Gegenleistung",
        "keine steuerliche Bestätigung",
    ):
        assert required in privacy_words
    assert "PayPal-Spendenknopf" not in privacy_words
    assert "PayPal bietet einmalige, monatliche und jährliche Spenden an" not in privacy_words
    assert "Zuwendung" not in privacy_words


@pytest.mark.parametrize(
    ("page_name", "forbidden"),
    [
        ("index.html", ("spende", "spenden")),
        ("en/index.html", ("donation", "donations")),
        ("es/index.html", ("donación", "donaciones", "donativo", "donativos")),
        ("fr/index.html", ("don volontaire", "dons")),
        ("it/index.html", ("donazione", "donazioni")),
        ("pt/index.html", ("doação", "doações", "donativo", "donativos")),
    ],
)
def test_public_support_uses_no_tax_privileged_donation_wording(
    page_name: str, forbidden: tuple[str, ...]
) -> None:
    """Der PayPal-Weg wird in jeder Sprache als Unterstützung bezeichnet."""

    html = (WEBSITE / page_name).read_text(encoding="utf-8").casefold()
    for term in forbidden:
        assert re.search(rf"\b{re.escape(term)}\b", html) is None, (page_name, term)


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


def test_public_legal_pages_do_not_carry_an_internal_review_disclaimer() -> None:
    """Die interne Qualitätssicherung ist keine Kundeninformation.

    Der Satz stand pauschal über jeder fertigen Seite und blieb auch nach der
    Prüfung sichtbar. Echte Platzhalter werden weiterhin gesondert markiert.
    """
    sentence = "Sorgfältiger Entwurf, aber keine Rechtsberatung"
    for page in sorted(WEBSITE.rglob("*.html")):
        html = page.read_text(encoding="utf-8")
        assert sentence not in html, (
            f"{page.relative_to(WEBSITE)} trägt noch den internen Vorbehalt"
        )


def test_current_digital_content_withdrawal_paragraph_is_named() -> None:
    """Seit der Neufassung steht das Erlöschen für digitale Inhalte in Absatz 6."""
    agb = (ROOT / "AGB.md").read_text(encoding="utf-8")

    assert "§ 356 Abs. 6 BGB" in agb
    assert "§ 356 Abs. 5 BGB" not in agb


def test_third_party_rights_take_precedence_over_proprietary_terms() -> None:
    """LGPL- und andere Fremdrechte dürfen nicht vom Mantelvertrag verschwinden."""
    eula = (ROOT / "EULA.md").read_text(encoding="utf-8")
    notice = (ROOT / "LICENSE").read_text(encoding="utf-8")

    assert "gehen deren Lizenzbedingungen diesen Bestimmungen vor" in eula
    assert "geht dessen Lizenz diesen Bestimmungen vor" in notice
    assert "LGPL-Bibliotheken austauschen" in eula


def test_eula_keeps_local_part_exchange_and_printability_limits_clear() -> None:
    """Lokaler Austausch darf nicht wieder zum RS-Dienst werden; „druckbar“
    ist keine unbemerkte Sicherheitsfreigabe."""
    eula = (ROOT / "EULA.md").read_text(encoding="utf-8")
    words = " ".join(eula.split())

    assert "lokal übernommenen Bausteindatei" in words
    assert "Herkunft, Autor und Lizenz" in words
    assert "Tauschbörse" not in words
    for required in (
        "geometrischen und drucktechnischen Kriterien",
        "Tragfähigkeit",
        "Lebensmittelechtheit",
        "persönliche Schutzausrüstung",
        "sonstige Schutzvorrichtungen",
        "Gas- oder Druckanwendungen",
        "elektrische Sicherheit",
        "tragende Konstruktionen",
        "nicht automatisch zum Hersteller jedes späteren Ausdrucks",
        "mitgelieferte digitale Konstruktionsunterlagen",
        "Fehlt eine Lizenzangabe",
        "keine Weitergabe- oder Nutzungsrechte",
    ):
        assert required in words


def test_root_license_keeps_mandatory_liability_exceptions() -> None:
    """Der Manteltext darf die differenzierte Haftungsregel nicht aushebeln."""
    notice = (ROOT / "LICENSE").read_text(encoding="utf-8")
    words = " ".join(notice.split())

    for required in (
        "Endnutzer-Lizenzvertrag, insbesondere dessen Nummer 11",
        "Vorsatz oder grobe Fahrlässigkeit",
        "Verletzung von Leben, Körper oder Gesundheit",
        "zwingende Haftung nach dem Produkthaftungsgesetz",
    ):
        assert required in words
    assert "RS Digital haftet nicht für Schäden, die aus der Nutzung entstehen" not in words
    assert "OpenSCAD" not in words


def test_eula_preserves_user_rights_without_releasing_bundled_templates() -> None:
    """Eigene Inhalte und mitgelieferte Vorlagen brauchen getrennte Rechte."""
    eula = " ".join((ROOT / "EULA.md").read_text(encoding="utf-8").split())

    assert "erwirbt RS Digital keine zusätzlichen Rechte" in eula
    assert "Rechte Dritter und die nachfolgenden Regeln" in eula
    assert "in Nummer 3 ausdrücklich erlaubte Nutzung separat lizenzierter" in eula
    assert "Was Sie mit Solidon3D erzeugen, gehört Ihnen" not in eula
    assert "RS Digital beansprucht keine Rechte an dem, was Sie mit Solidon3D erzeugen" not in eula


def test_contracts_do_not_promise_a_fixed_first_sale_or_local_remote_ollama() -> None:
    """Weitere 0.x-Demos bleiben möglich; entferntes Ollama bleibt entfernt."""

    eula = (ROOT / "EULA.md").read_text(encoding="utf-8")
    agb = (ROOT / "AGB.md").read_text(encoding="utf-8")
    eula_words = " ".join(eula.split())
    agb_words = " ".join(agb.split())

    assert "am 1. November 2026 startende Vollversion" not in eula_words
    assert "Zum Verkaufsstart am 1. November 2026" not in agb_words
    assert "Eine spätere 0.x-Demo kann einen eigenen Stichtag nennen" in eula_words
    assert "weitere kostenlose 0.x-Demo" in agb_words
    assert "entfernten Ollama-Adresse" in eula_words
    assert "Mit einem lokalen Modell verlässt nichts den Rechner" not in eula_words


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


def test_a_date_at_a_line_break_does_not_become_a_numbered_list() -> None:
    """„nennt den\n30. Oktober 2026." stand im Vertrag als „1. Oktober 2026".

    Der Umbruch vor dem Datum ließ die Zahl am Zeilenanfang stehen, und der
    Erzeuger las sie als Aufzählung — der Browser zählt eine ``<ol>`` ab eins.
    Eine Zahl mit Punkt beginnt eine Liste nur, wenn eine läuft, sie mit 1
    beginnt oder kein Absatz offen ist (so hält es auch CommonMark).
    """
    from make_legal import body_html

    broken = "Die Demo nennt den\n30. Oktober 2026. Danach nicht mehr.\n"
    html = body_html(broken, True)
    assert "<ol>" not in html
    assert "30. Oktober 2026" in html

    real_list = "Es gilt:\n\n1. erstens\n2. zweitens\n"
    assert body_html(real_list, True).count("<li>") == 2
