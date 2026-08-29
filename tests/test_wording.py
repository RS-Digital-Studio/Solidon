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
import json
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
    (
        "Hilfsgeometrie",
        ("de",),
        "Der Knopf heißt Hilfslinie — das Wort, das jemand kennt, der nie ein "
        "CAD benutzt hat. In den Docstrings des Kerns bleibt der Fachbegriff.",
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


# --- Die dritte Klammer: genannte Menüwege ---------------------------------

#: Was legitim vor einem Pfeil steht, ohne ein Menü der Leiste zu sein.
#: Kuratiert wie ``ABGELEGT`` darüber: Wer eine Geste beschreibt, trägt ihr
#: Wort hier ein — alles andere muss ein Menü sein, sonst schickt der Satz
#: den Kunden an eine Stelle, die es nicht gibt.
KEIN_MENUE = ("Rechtsklick",)

#: Ein Menüweg im Fließtext: Großbuchstabe, dann mindestens ein „ → ".
#: Das Muster nimmt den Satz mit, in dem der Weg steht — welcher Teil davon
#: der Weg ist, entscheidet erst der Abgleich mit der Leiste.
WEG_MUSTER = re.compile(r"[A-ZÄÖÜ][\w \-äöüß]{1,28}(?: → [A-ZÄÖÜ][\w \-äöüß.]{1,32})+")

#: Wo Menüwege in Kundentexten stehen.
WEG_QUELLEN = ("app/core/manual.py", "app/core/tour.py")


def _ohne_zierat(text: str) -> str:
    """Ein Menütext, wie ihn ein Satz schreibt: ohne Mnemonic und Auslassung."""
    return text.replace("&", "").replace("…", "").replace("...", "").strip(" .")


def _menue_der_anwendung(window: object) -> tuple[set[str], set[str]]:
    """Alle Menüwege des gebauten Fensters, dazu die Namen der Leiste.

    Gefragt wird das Fenster und nicht ``menu_path``: Die Hälfte der Wege in
    Handbuch und Tour führt zu Einträgen, die keine Operation sind — *Datei →
    Exportieren*, *Hilfe → Handbuch*. Ein Test gegen das Register sähe genau
    die nicht.
    """
    from PySide6.QtWidgets import QMenu

    wege: set[str] = set()
    leiste: set[str] = set()

    def sammeln(menu: QMenu, vorne: str) -> None:
        for eintrag in menu.actions():
            if eintrag.isSeparator():
                continue
            name = _ohne_zierat(eintrag.text())
            if not name:
                continue
            weg = f"{vorne} → {name}" if vorne else name
            wege.add(weg)
            untermenü = eintrag.menu()
            if untermenü is not None:
                sammeln(untermenü, weg)

    for eintrag in window.menuBar().actions():  # type: ignore[attr-defined]
        untermenü = eintrag.menu()
        if untermenü is not None:
            kopf = _ohne_zierat(eintrag.text())
            leiste.add(kopf)
            sammeln(untermenü, kopf)

    return wege, leiste


def _weg_urteil(satz: str, wege: set[str], leiste: set[str]) -> str | None:
    """Warum ein genannter Weg nirgends hinführt — oder ``None``, wenn doch.

    Das Muster hat den umgebenden Satz mitgenommen, also wird an beiden Enden
    zurückgeschnitten: vorn bis zu einem Namen der Leiste, hinten wortweise,
    bis ein echter Weg dasteht. Trifft kein Ausschnitt, ist der Weg falsch.
    """
    glieder = [_ohne_zierat(teil) for teil in satz.split("→")]
    erste, letzte = glieder[0].split(), glieder[-1].split()

    for von in range(len(erste)):
        kopf = " ".join(erste[von:])
        if kopf in KEIN_MENUE:
            return None
        if kopf not in leiste:
            continue
        for bis in range(len(letzte), 0, -1):
            fuß = _ohne_zierat(" ".join(letzte[:bis]))
            if " → ".join([kopf, *glieder[1:-1], fuß]) in wege:
                return None
        return f"das Menue {kopf} gibt es, aber den Eintrag darunter nicht"

    return "beginnt mit keinem Menü der Leiste"


def test_every_menu_path_in_the_texts_exists_in_the_menu_bar(
    qt_app: object, tmp_path: Path
) -> None:
    """Ein Weg, den Handbuch oder Tour nennt, muss in der Leiste stehen.

    Am 29.08.2026 zweimal gebrochen, beide Male in derselben Stunde: Das
    Handbuch schickte zum *Toleranz-Testkörper* über „Bausteine → Kalibrierung",
    die Tour an zwei Stellen ins selbe Menü — und das Menü *Bausteine* gab es
    seit dem Umbau auf den Katalog nicht mehr. Gefunden hat beides ein Mensch
    beim Lesen; ``test_manual``, ``test_tour`` und ``test_website`` standen mit
    380 grünen Zeilen daneben. Ein Verweis ins Leere liest sich so glatt wie
    ein gültiger.

    Die Tour wiegt dabei schwerer als das Handbuch: Ihre Schritte haben
    Bedingungen und rücken nicht weiter, wenn der Kunde den Eintrag nicht
    findet.
    """
    from app.core import bootstrap
    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    bootstrap.load_operations()
    window = MainWindow(Session(), UiSettings())
    wege, leiste = _menue_der_anwendung(window)
    assert leiste, "die Menüleiste ist leer — dann prüft der Test nichts"

    funde = []
    geprüft = 0
    for name in WEG_QUELLEN:
        text = Path(name).read_text(encoding="utf-8")
        # Eine über mehrere Zeilen umbrochene Zeichenkette ist ein Satz.
        text = re.sub(r'"\s*\n\s*"', "", text)
        for satz in sorted(set(WEG_MUSTER.findall(text))):
            geprüft += 1
            grund = _weg_urteil(satz.strip(), wege, leiste)
            if grund:
                funde.append(f"{name}: {satz.strip()} — {grund}")

    assert geprüft >= 20, f"nur {geprüft} Wege gefunden — das Muster greift nicht mehr"
    assert not funde, f"{len(funde)} Menüwege führen nirgends hin:\n" + "\n".join(funde)


# --- Die vierte Klammer: genannte Bedienelemente ----------------------------

#: Ein kursiv ausgezeichneter Name in Handbuch und Tour: *Trimmen*, *Fertig*,
#: *Auf das Bett setzen*. So werden dort Bedienelemente ausgezeichnet, und
#: nur so — fett steht für Sammelbegriffe und Zwischenüberschriften.
NAME_MUSTER = re.compile(r"(?<![*\w])\*([A-ZÄÖÜ][^*\n]{2,34})\*(?!\*)")

#: Was hinter einem Namen stehen darf, wenn die Anwendung ihn als Anfang
#: eines längeren Textes zeigt: „Bestimmt — alle Freiheitsgrade sind vergeben."
TRENNER = (" — ", " – ", ": ", " …", "…", " (")


def _kennt_die_anwendung(name: str, texte: set[str]) -> bool:
    """Sagt die Anwendung diesen Namen — allein oder als Anfang eines Satzes?"""
    if name in texte:
        return True
    return any(text.startswith(name + trenner) for text in texte for trenner in TRENNER)


def test_every_control_the_texts_name_is_one_the_application_says() -> None:
    """Ein Name im Handbuch muss einer sein, den der Kunde auch sieht.

    Drei standen am 29.08.2026 falsch da, und alle drei hätte ein Kunde
    gesucht: *Grenzen ändern …* heißt in Wahrheit *Ändern …*, *Laden* heißt
    *Modell laden*, und *Färben* gibt es gar nicht — die Menüeinträge heißen
    *Teil färben* und *Fläche färben*. Der dritte war eine falsche
    Auszeichnung: Kursiv ist ein Bedienelement, fett ein Sammelbegriff, und
    dreißig Zeilen später stand dasselbe Wort richtig als **Färben**.

    Verglichen wird gegen die Katalogschlüssel, also gegen jeden Text, den
    ``tr()`` je gesehen hat — die vollständigste Liste dessen, was die
    Anwendung sagt. Menüwege trägt
    :func:`test_every_menu_path_in_the_texts_exists_in_the_menu_bar`; sie
    stehen hier nicht noch einmal.
    """
    texte = set(json.loads(Path("app/i18n/locales/en.json").read_text(encoding="utf-8")))
    assert len(texte) > 500, f"nur {len(texte)} Katalogschlüssel — dann prüft das nichts"

    genannt: dict[str, set[str]] = {}
    for name in WEG_QUELLEN:
        text = re.sub(r'"\s*\n\s*"', "", Path(name).read_text(encoding="utf-8"))
        for treffer in NAME_MUSTER.findall(text):
            genannt.setdefault(treffer.strip(), set()).add(Path(name).name)

    assert len(genannt) >= 80, f"nur {len(genannt)} Namen gefunden — das Muster greift nicht mehr"

    funde = [
        f"{', '.join(sorted(quellen))}: {name}"
        for name, quellen in sorted(genannt.items())
        if "→" not in name and not _kennt_die_anwendung(name, texte)
    ]
    assert not funde, f"{len(funde)} Namen sagt die Anwendung nicht:\n" + "\n".join(funde)
