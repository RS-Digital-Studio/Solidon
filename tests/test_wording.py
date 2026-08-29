"""Die Außendarstellung sagt dasselbe wie die Anwendung.

**Zwei Löcher im Tor, beide am 29.08.2026 aufgefallen, beide mit derselben
Wurzel** — ein Versprechen an einer Stelle, das an einer anderen niemand
nachgezogen hat:

* **„B-Rep" stand dreißigmal auf der Website und null-mal in der Anwendung.**
  Ein Changelog-Punkt aus 0.1.x kündigt ausdrücklich an, die Anwendung sage
  „exakter Körper" statt „B-Rep"; sie hat Wort gehalten, die Website nicht.
  Dasselbe mit „Spline", nachdem das Werkzeug „Kurve" hieß. Kein Lauf hat es
  gesehen.
* **Eine Änderung am Handbuch macht die erzeugte Seite veraltet, und
  ``test_website`` bleibt grün.** Beim Changelog ist das anders: Dort wird der
  Test rot, sobald die Quelle von der Seite abweicht, und genau das hat am
  selben Tag den Erzeugungslauf erzwungen. Für den Handbuchtext fehlte diese
  Klammer.

Beides steht hier. Die erste Hälfte ist **kuratiert** und nicht abgeleitet —
dieselbe Erfahrung wie bei ``GERMAN_STEMS`` in ``test_language_rules``: Der
automatische Weg ertrinkt in Fehlalarmen, weil Fach- und Alltagssprache sich
überlappen. Wer ein Wort ablegt, trägt es unten ein.
"""

from __future__ import annotations

import html
import re
from pathlib import Path

import pytest

from app.core import manual
from app.i18n import install_catalog, set_language
from app.i18n.catalog import available_languages

WEBSITE = Path(__file__).resolve().parent.parent / "website"

#: Die Seiten, die von Hand gepflegt werden und für den Kunden werben.
WORBEN = ("index.html", "funktionen.html", "ki-modelle.html")

#: Wort, Sprachen, und warum es abgelegt ist.
#:
#: ``None`` als Sprachliste heißt: in **jeder** Sprache abgelegt. Sonst gilt
#: der Eintrag nur dort — „contraintes" ist im Französischen das Wort der
#: Anwendung und bleibt, während das deutsche „Zwänge" gegangen ist.
ABGELEGT: tuple[tuple[str, tuple[str, ...] | None, str], ...] = (
    (
        "B-Rep",
        None,
        "Die Anwendung nennt den Nutzen („Flächen und Kanten später "
        "bearbeiten“), nie den Rechenkern.",
    ),
    (
        "Spline",
        None,
        "Das Zeichenwerkzeug heißt Kurve — so, wie sein Ergebnis im Objektbaum immer schon hieß.",
    ),
    (
        "Skizzen mit Zwängen",
        ("de",),
        "Die Anwendung sagt Bedingungen. In den anderen fünf Sprachen ist "
        "constraint und seine Geschwister das Wort der Anwendung.",
    ),
)


def _seiten_einer_sprache(language: str) -> tuple[Path, ...]:
    """Die geworbenen Seiten — deutsch im Wurzelverzeichnis, sonst je Ordner."""
    if language == "de":
        return tuple(WEBSITE / name for name in WORBEN)
    ordner = WEBSITE / language
    # Die Sprachfassungen tragen englische Dateinamen.
    namen = ("index.html", "features.html", "ai-models.html")
    return tuple(ordner / name for name in namen if (ordner / name).exists())


def _sichtbar(pfad: Path) -> str:
    """Was ein Leser sieht — ohne Skript, Stil und Auszeichnung.

    Auch die Attribute fallen weg: Ein abgelegtes Wort in einem ``alt``-Text
    steht ebenso vor dem Kunden wie eines im Fließtext, aber ein Ankername wie
    ``#skizzen-mit-zwaengen`` ist eine Adresse und kein Text — deshalb wird
    erst entauszeichnet und dann gesucht.
    """
    roh = pfad.read_text(encoding="utf-8")
    ohne_kopf = re.sub(r"<(script|style)\b.*?</\1>", " ", roh, flags=re.DOTALL | re.IGNORECASE)
    return html.unescape(re.sub(r"<[^>]+>", " ", ohne_kopf))


def _vergleichbar(text: str) -> str:
    """Beide Seiten auf dieselbe Schreibweise bringen.

    **Ein Tag wird zu einem Leerzeichen, und das steht dann vor dem Komma.**
    ``<strong>a peça inteira</strong>, o segundo`` ergibt „a peça inteira , o
    segundo", die Quelle sagt „a peça inteira, o segundo" — und der Vergleich
    meldete sechzehn Absätze als fehlend, die alle dastanden. Der Fehler lag im
    Werkzeug, nicht auf der Seite; deshalb wird hier **beides** gleich
    behandelt, statt die Seite nachzubessern.
    """
    zusammen = " ".join(text.split())
    ohne_lücke_davor = re.sub(r"\s+([,.;:!?…»)])", r"\1", zusammen)
    # Und dieselbe Lücke auf der anderen Seite: ``(<em>Wandstärkenleiter</em>)``
    # ergibt „( Wandstärkenleiter)". Zwei Regeln statt einer, weil eine
    # Zeichenklasse für beide Richtungen auch Bindestriche und Gedankenstriche
    # träfe — und die trennen hier wirklich.
    ohne_lücke_dahinter = re.sub(r"([(«])\s+", r"\1", ohne_lücke_davor)
    # Der dritte Fall kommt aus den romanischen Sprachen: Ein Apostroph, dem
    # unmittelbar ein fett gesetztes Wort folgt, bekommt beim Entfernen des
    # Tags ein Leerzeichen dahinter — aus dem französischen Artikel vor
    # „édition" wird eine Lücke, die es in der Quelle nicht gibt. Ersetzt wird
    # nur vor einem Wortzeichen, damit ein Apostroph am Satzende sein
    # Leerzeichen behält.
    return re.sub(r"([‘’'])\s+(?=\w)", r"\1", ohne_lücke_dahinter)


@pytest.mark.parametrize("language", sorted(available_languages()))
def test_no_page_keeps_a_word_the_application_has_dropped(language: str) -> None:
    """Was die Anwendung abgelegt hat, wirbt nicht weiter auf der Website."""
    seiten = _seiten_einer_sprache(language)
    assert seiten, f"{language}: keine Seiten gefunden — der Test prüfte nichts"

    for pfad in seiten:
        text = _sichtbar(pfad)
        assert text.strip(), f"{pfad.name}: kein sichtbarer Text"
        for wort, sprachen, grund in ABGELEGT:
            if sprachen is not None and language not in sprachen:
                continue
            # Ohne Rücksicht auf Groß- und Kleinschreibung: Im Englischen und
            # Italienischen stand „B-rep" mit kleinem r, und die erste Suche
            # meldete beide Sprachen als sauber.
            assert not re.search(re.escape(wort), text, re.IGNORECASE), (
                f"{pfad.relative_to(WEBSITE)}: „{wort}“ steht noch da. {grund}"
            )


def test_the_dropped_words_are_really_gone_from_the_application() -> None:
    """Die Gegenrichtung: Ein Wort steht hier erst, wenn die Anwendung es ablegt.

    Ohne sie wäre die Liste oben eine Wunschliste. Sie hält außerdem den Fall
    fest, dass jemand ein Wort zurückholt — dann wird dieser Test rot und
    nicht der obere, und die Meldung zeigt auf die richtige Stelle.
    """
    from app.core.bootstrap import load_operations
    from app.core.registry import REGISTRY

    load_operations()
    sichtbar = " ".join(str(teil) for spec in REGISTRY.all() for teil in (spec.title, spec.doc))
    assert len(sichtbar) > 1000, "das Register kam leer — der Test prüfte nichts"

    for wort, sprachen, _grund in ABGELEGT:
        if sprachen is not None and "de" not in sprachen:
            continue
        assert wort.lower() not in sichtbar.lower(), (
            f"„{wort}“ steht wieder im Register — dann gehört es nicht in ABGELEGT"
        )


@pytest.mark.parametrize("language", sorted(available_languages()))
def test_every_manual_paragraph_reaches_the_generated_page(language: str) -> None:
    """Der Handbuchtext und die erzeugte Seite sagen dasselbe.

    Die Klammer, die der Changelog seit je hat und das Handbuch nicht: Wer
    ``app/core/manual.py`` ändert und ``tools/make_manual.py`` vergisst, bekam
    einen grünen Lauf und eine veraltete Website. Am 29.08.2026 genau so
    passiert — neun neue Wörterbucheinträge, und ``test_website`` blieb bei
    266 grün.

    **Der Nachbar prüft die Kapitelüberschriften**
    (``test_manual.test_the_website_page_carries_every_chapter``), und seine
    Begründung — eine Datei Zeichen für Zeichen zu vergleichen hieße, sie im
    Test noch einmal zu erzeugen — gilt unverändert. Sie trifft diesen Test
    aber nicht: Geprüft wird nicht, ob die Seite **gleich** ist, sondern ob
    jeder Absatz der Quelle darin **vorkommt**. Genau dazwischen lag der Fall
    vom 29.08.2026: Neun neue Wörterbucheinträge, und weil der Titel
    „Wörterbuch" unverändert blieb, sah der Kapiteltest nichts.

    Verglichen wird der **Text**, nicht das Markup: Die Seite entsteht über
    ``markup.py`` aus Markdown, und ein Vergleich der Auszeichnung prüfte den
    Wandler statt der Aktualität.
    """
    from app.i18n.catalog import read_catalog

    pfad = WEBSITE / ("handbuch.html" if language == "de" else f"{language}/manual.html")
    assert pfad.exists(), f"{pfad} fehlt — tools/make_manual.py läuft nicht?"
    seite = _vergleichbar(_sichtbar(pfad))

    install_catalog(language, read_catalog(language))
    set_language(language)
    try:
        seiten = manual.pages()
        assert len(seiten) > 20, "das Handbuch kam leer — der Test prüfte nichts"
        fehlend = [
            f"{eintrag.key}: {absatz[:70]} …"
            for eintrag in seiten
            for absatz in _absaetze(str(eintrag.body))
            if absatz not in seite
        ]
    finally:
        set_language("de")

    assert not fehlend, (
        f"{language}: {len(fehlend)} Absätze stehen nicht auf der Seite — "
        f"tools/make_manual.py laufen lassen. Erster: {fehlend[0]}"
    )


def _absaetze(körper: str) -> list[str]:
    """Die Fließtextabsätze eines Handbuchtexts, ohne Markup und Bilder.

    Genommen werden nur Absätze ab einer Länge, die zufällige Treffer
    ausschließt: Ein Halbsatz wie „Und danach?" stünde in jeder Seite.
    """
    absätze: list[str] = []
    for roh in körper.split("\n\n"):
        if roh.lstrip().startswith(("![", "*", "-", "|", "#")):
            continue
        ohne_markup = re.sub(r"[*`]", "", roh)
        text = _vergleichbar(ohne_markup)
        if len(text) >= 60:
            absätze.append(text)
    return absätze
