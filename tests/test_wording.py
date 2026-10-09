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

import ast
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
        "Die Anwendung nennt den Nutzen („Mit echten Flächen und Kanten "
        "rechnen“), nie den Rechenkern.",
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


@pytest.mark.rendered
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
        # Ein Verweis steht auf der Seite als sein Text, und eine nummerierte
        # Legende als Liste, deren Ziffern das Markup zeichnet und nicht der
        # Text: Seit dem Handbuchumbau (0.5.1) meldete der Vergleich sieben
        # Absätze als fehlend, die alle dastanden.
        ohne_verweis = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", roh)
        ohne_ziffern = re.sub(r"(?m)^\s*\d+\.\s+", "", ohne_verweis)
        ohne_markup = re.sub(r"[*`]", "", ohne_ziffern)
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


def _kundentexte(name: str) -> str:
    """Die Zeichenketten einer Quelle — der Code dazwischen ist kein Kundentext.

    Bis zum 13.09.2026 liefen die Muster über den rohen Quelltext, und
    ``return (*INTRODUCTION, _spacemouse_page(), *knowledge_pages(), …)`` las
    sich als kursiv ausgezeichnetes Bedienelement „INTRODUCTION,
    _spacemouse_page(),“ (Fund des Reviews). Der Syntaxbaum kennt die
    Zeichenketten, und umbrochene Literale fügt er selbst zusammen.
    """
    source = Path(name).read_text(encoding="utf-8")
    if not name.endswith(".py"):
        return re.sub(r'"\s*\n\s*"', "", source)
    return "\n".join(
        node.value
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    )


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
        text = _kundentexte(name)
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
#: eines längeren Textes zeigt: „Bestimmt — jedes Maß steht fest."
TRENNER = (" — ", " – ", ": ", " …", "…", " (")


def _kennt_die_anwendung(name: str, texte: set[str]) -> bool:
    """Sagt die Anwendung diesen Namen — allein oder als Anfang eines Satzes?"""
    if name in texte:
        return True
    return any(text.startswith(name + trenner) for text in texte for trenner in TRENNER)


#: Ein Name, den die Anwendung abgelegt hat und den eine Handbuchseite noch
#: nennt — die Seite gehört der Handbuch-Sitzung und zieht nach. Der neue Name
#: steht daneben; nennt keine Seite den alten mehr, fliegt der Eintrag heraus.
NAME_WARTET_AUF_HANDBUCH: dict[str, str] = {}


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
        text = _kundentexte(name)
        for treffer in NAME_MUSTER.findall(text):
            genannt.setdefault(treffer.strip(), set()).add(Path(name).name)

    assert len(genannt) >= 80, f"nur {len(genannt)} Namen gefunden — das Muster greift nicht mehr"

    funde = [
        f"{', '.join(sorted(quellen))}: {name}"
        for name, quellen in sorted(genannt.items())
        if "→" not in name
        and not _kennt_die_anwendung(name, texte)
        and not (name in NAME_WARTET_AUF_HANDBUCH and NAME_WARTET_AUF_HANDBUCH[name] in texte)
    ]
    assert not funde, f"{len(funde)} Namen sagt die Anwendung nicht:\n" + "\n".join(funde)
    erledigt = sorted(set(NAME_WARTET_AUF_HANDBUCH) - set(genannt))
    assert not erledigt, f"nachgezogen — aus NAME_WARTET_AUF_HANDBUCH austragen: {erledigt}"


#: Ein Fenstername aus einem Kundentext, den kein Fenster trägt — und der
#: Name, unter dem der Kunde es wirklich findet.
#:
#: Kuratiert wie :data:`ABGELEGT`: Es gibt keinen Weg, aus einem deutschen
#: Wort abzuleiten, ob ein Fenster so heißt. Wer einen Namen ablegt, trägt
#: ihn hier ein.
FENSTER_HEISST_ANDERS: tuple[tuple[str, str, str], ...] = (
    (
        "Merkmalfenster",
        "unter Auswahl",
        "Das Dock heißt seit dem 07.09.2026 „Auswahl“ (ein Ort für die "
        "Auswahl). Fünf Sätze schickten den Kunden bis zum 14.09.2026 an ein "
        "Fenster, dessen Name nirgends im Fenster steht.",
    ),
    (
        "Auswahlfenster",
        "unter Auswahl",
        "Seit RM-511 (05.10.2026) ist die Auswahl ein Reiter der rechten Karte "
        "und kein Fenster mehr; ein Satz schickt den Kunden „rechts unter Auswahl“.",
    ),
)


def test_no_customer_text_names_a_window_the_application_does_not_have() -> None:
    """Ein Satz, der einen Ort nennt, nennt ihn so, wie er dort steht.

    Geprüft wird über die **Katalogschlüssel**, also über jeden Text, den
    ``tr()`` je gesehen hat: Meldungen des Fensters, Befunde des Kerns und das
    Handbuch stehen darin gleichermaßen. Ein Docstring darf den alten Begriff
    behalten — er beschreibt den Code und schickt niemanden irgendwohin.
    """
    quelle = set(json.loads(Path("app/i18n/locales/en.json").read_text(encoding="utf-8")))
    assert len(quelle) > 500, f"nur {len(quelle)} Katalogschlüssel — dann prüft das nichts"

    for falsch, richtig, grund in FENSTER_HEISST_ANDERS:
        treffer = sorted(key for key in quelle if falsch in key)
        assert not treffer, f"{len(treffer)} Texte sagen „{falsch}“. {grund}\n" + "\n".join(treffer)
        # Und die Gegenrichtung: Der richtige Name muss einer sein, den die
        # Anwendung selbst sagt — sonst tauscht dieser Test einen falschen
        # Ort gegen einen zweiten falschen.
        assert any(richtig in key for key in quelle), (
            f"„{richtig}“ steht in keinem Kundentext — dann ist es kein Ort, sondern eine Idee"
        )


# --- Konstrukteurswörter (RM-088) -------------------------------------------

#: Wörter, die ein Konstrukteur kennt und ein Slicer-Nutzer nicht. Maßstab ist
#: der Slicer (Cura, PrusaSlicer, Orca): „Brim“, „Stützen“, „Infill“, „Netz“
#: stehen dort, „Normale“, „Facette“ oder „verschweißen“ nicht. Kuratiert wie
#: ``ABGELEGT`` oben — „verschweißt“ bleibt erlaubt, denn eine Stütze, die am
#: Teil verschweißt, beschreibt den Druck und nicht das Netz.
KONSTRUKTEURSWORT = re.compile(
    r"(?<![A-Za-zÄÖÜäöüß])(Flächennormalen?|Normalen\w*|Normale\b(?! Wandstärke)"
    r"|[Mm]anifold|B-Rep|Tessell\w*|Facette\w*|Vertex|Vertices|Voxel\w*"
    r"|[Ww]asserdicht\w*|[Bb]oolesch\w*|[Dd]eterministisch\w*|[Ee]ntartet\w*"
    r"|[Dd]ezimier\w*|[Uu]ngeschweißt\w*|[Vv]erschweißen|Freiheitsgrad\w*)"
)

#: Dieselbe Frage an der englischen Übersetzung — dort stehen die Wörter auch
#: dann, wenn die deutsche Quelle sie meidet („Eckpunkt“ wurde „vertex“).
DESIGNER_WORD = re.compile(
    r"\b(normals?|manifold|tessellat\w*|facets?|vertex|vertices|voxels?|watertight|welding|welded"
    r"|decimat\w*|degrees? of freedom)\b",
    re.IGNORECASE,
)

#: Schlüsselanfang → warum das Wort dort stehen darf.
DARF_KONSTRUKTEURSWORT: dict[str, str] = {
    "Die Wörter, die in Solidon, in Slicern und in Druckforen vorkommen": (
        "Das Glossar des Handbuchs erklärt genau diese Wörter."
    ),
    "Normale": (
        "Nur im Steckbrief für das Sprachmodell (perceive/digest.py) — der Kunde liest ihn nicht."
    ),
}
DARF_DESIGNER_WORD: dict[str, str] = {
    "Einen Parameterwert setzen": "Kommandozeile: „Boolean“ ist dort der Datentyp.",
    "Für Wahrheitswerte verwenden Sie": "Kommandozeile: „Boolean“ ist dort der Datentyp.",
    "Wie breit eine Bahn gelegt wird.": "„is normal“ heißt dort „ist üblich“.",
    "Normale": (
        "Nur im Steckbrief für das Sprachmodell (perceive/digest.py) — der Kunde liest ihn nicht."
    ),
    "Die Wörter, die in Solidon, in Slicern und in Druckforen vorkommen": (
        "Das Glossar des Handbuchs erklärt genau diese Wörter."
    ),
}


def test_no_customer_text_uses_a_designer_word() -> None:
    """Was ein Kunde ohne CAD-Kenntnisse liest, nennt er so, wie sein Slicer es nennt.

    Gemessen in der Durchsicht 0.5.1: 32 deutsche Quelltexte mit einem
    Konstrukteurswort („entlang ihrer Normalen“, „Facettenkorrektur“,
    „Punkte verschweißen“, „nicht wasserdicht“, „Normale X“) und zwölf, in denen
    erst die englische Übersetzung eines trug („snaps to a vertex“). Die Regel
    steht in ``.claude/rules/oberflaeche.md``; dieser Test hält sie.

    Geprüft werden die Katalogschlüssel, also jeder Text, den ``tr()`` je gesehen
    hat — Meldungen, Befunde, Feldhilfen und das Handbuch. Kommentare und
    Docstrings dürfen die Wörter behalten: Sie beschreiben den Code.
    """
    englisch = json.loads(Path("app/i18n/locales/en.json").read_text(encoding="utf-8"))
    assert len(englisch) > 500, f"nur {len(englisch)} Katalogschlüssel — dann prüft das nichts"

    def erlaubt(schluessel: str, ausnahmen: dict[str, str]) -> bool:
        return any(schluessel.startswith(anfang) for anfang in ausnahmen)

    deutsch = sorted(
        f"{KONSTRUKTEURSWORT.findall(key)}: {key[:100]}"
        for key in englisch
        if KONSTRUKTEURSWORT.search(key) and not erlaubt(key, DARF_KONSTRUKTEURSWORT)
    )
    assert not deutsch, "Konstrukteurswort im deutschen Text:\n" + "\n".join(deutsch)

    uebersetzt = sorted(
        f"{DESIGNER_WORD.findall(text)}: {key[:60]} -> {text[:80]}"
        for key, text in englisch.items()
        if DESIGNER_WORD.search(text) and not erlaubt(key, DARF_DESIGNER_WORD)
    )
    assert not uebersetzt, "Konstrukteurswort in der englischen Übersetzung:\n" + "\n".join(
        uebersetzt
    )

    # Und jede Ausnahme muss noch gebraucht werden — sonst hält sie still eine
    # Tür offen, durch die das nächste Wort unbemerkt hereinkommt.
    for ausnahmen in (DARF_KONSTRUKTEURSWORT, DARF_DESIGNER_WORD):
        for anfang in ausnahmen:
            assert any(key.startswith(anfang) for key in englisch), (
                f"Ausnahme „{anfang}“ trifft keinen Text mehr — austragen"
            )


# --- Knopfnamen in Zitaten (RM-084) ------------------------------------------

#: (Anfang des Schlüssels, Zitat) → warum die Übersetzung dort nicht wörtlich
#: den Knopf nennt.
ZITAT_DARF_ABWEICHEN: dict[tuple[str, str], str] = {
    ("Alle Maße in Millimetern.", "Spiel"): "Begriff im Satz, nicht der Feldname; klein im Satz.",
    (
        "Alle Maße in Millimetern.",
        "Presssitz",
    ): "Begriff im Satz, nicht der Feldname; klein im Satz.",
}

#: (Anfang des Schlüssels, Zitat) → Übersetzungskontext des zitierten Knopfs.
#: Ein deutsches Wort für zwei Knöpfe trennt ein Kontext (*Abziehen* als
#: Boolesche Operation und als Buchung im Filamentlager); ohne Eintrag hier
#: meint ein Zitat den Schlüssel ohne Kontext.
ZITAT_KONTEXT: dict[tuple[str, str], str] = {
    ("Vorschlag: {spool}.", "Abziehen"): "Lagerbestand",
}


def test_a_quoted_control_is_named_as_the_control_says() -> None:
    """Ein Satz, der „Werkzeuge prüfen“ zitiert, zitiert in jeder Sprache den Knopf.

    Gemessen in der Durchsicht 0.5.1: 51 Zitate in 25 Sätzen nannten einen Knopf
    anders, als er im Fenster heißt — „Plug hole“ neben dem Knopf „Fill a bore“,
    «Comprobar herramientas» neben «Comprobar las herramientas». Der Kunde sucht
    dann einen Knopf, den es nicht gibt.
    """
    languages = [language for language in available_languages() if language != "de"]
    catalogs = {
        language: json.loads(
            (Path("app/i18n/locales") / f"{language}.json").read_text(encoding="utf-8")
        )
        for language in languages
    }
    source = catalogs[languages[0]]
    assert len(source) > 500, "keine Katalogschlüssel gelesen — dann prüft das nichts"
    contexts_used: set[tuple[str, str]] = set()

    def control(sentence: str, name: str) -> str | None:
        entry = next(
            (
                entry
                for entry in ZITAT_KONTEXT
                if sentence.startswith(entry[0]) and name == entry[1]
            ),
            None,
        )
        if entry is not None:
            contexts_used.add(entry)
            key = f"{ZITAT_KONTEXT[entry]}\x04{name}"
            assert key in source, f"Kontextschlüssel {key!r} fehlt im Katalog"
            return key
        if name in source:
            return name
        return next((key for key in source if key.rstrip(" …") == name), None)

    checked = 0
    wrong: list[str] = []
    used: set[tuple[str, str]] = set()
    for key in source:
        for quote in re.findall(r"„([^“]+)“", key):
            parts = [part.strip() for part in quote.split("→")]
            keys = [control(key, part) for part in parts]
            if any(entry is None for entry in keys):
                continue  # kein Knopf, sondern ein Beispielsatz oder ein Begriff
            exempt = next(
                (
                    entry
                    for entry in ZITAT_DARF_ABWEICHEN
                    if key.startswith(entry[0]) and quote == entry[1]
                ),
                None,
            )
            for language in languages:
                checked += 1
                for part, entry in zip(parts, keys, strict=True):
                    wanted = catalogs[language][entry]
                    wanted = wanted if part.endswith("…") else wanted.rstrip(" …")
                    if wanted in catalogs[language][key]:
                        continue
                    if exempt is not None:
                        used.add(exempt)
                        continue
                    wrong.append(f"[{language}] „{part}“ = {wanted!r} fehlt in {key[:60]!r}")
    assert sorted(set(ZITAT_KONTEXT) - contexts_used) == [], "Kontextangabe ohne Zitat"
    assert checked > 100, f"nur {checked} Zitate geprüft — dann prüft das nichts"
    assert not wrong, "Knopf anders zitiert, als er heißt:\n" + "\n".join(wrong)
    unused = sorted(set(ZITAT_DARF_ABWEICHEN) - used)
    assert not unused, f"Ausnahmen ohne Treffer — austragen: {unused}"


@pytest.mark.parametrize("language", [entry for entry in available_languages() if entry != "de"])
def test_the_sketch_figure_says_the_word_of_the_status_line(language: str) -> None:
    """Das Bild des Skizzeneditors zeigt dasselbe Wort wie seine Statuszeile.

    Durchsicht 0.5.1: Die Abbildung ``sketch-editor`` sagte es/fr/it/pt
    „Determinado“, „Déterminée“, „Determinato“, die Statuszeile und das
    Handbuch „Totalmente definido“, „Entièrement défini“, „Completamente
    definito“. Wer das Wort aus dem Bild in der Anwendung sucht, findet es
    nicht.
    """
    catalog = json.loads(
        (Path("app/i18n/locales") / f"{language}.json").read_text(encoding="utf-8")
    )
    figure = catalog["Bestimmt — jedes Maß steht fest."]
    status = catalog["{state} · Bestimmt — jedes Maß steht fest, nichts wackelt mehr. {advice}"]
    word = status.removeprefix("{state} · ").split(" — ")[0]
    assert figure.split(" — ")[0] == word, f"Bild {figure!r}, Statuszeile {word!r}"


# --- Fachwörter und Satzmuster (RM-509) --------------------------------------

#: Wörter aus der Datenhaltung, die ein Kunde nicht sucht (Durchsicht 0.5.2,
#: D13). Einige sind heute Feldnamen („Startwert“, „Materialtoleranz
#: berücksichtigen“) — der Bestand ist eingefroren, ein neues Vorkommen nicht.
FACHWORT = re.compile(
    r"Mindestbahnbreite|im Rahmen des Rasters|Maßherkunft|Bereichstest|Startwert\w*"
    r"|Materialtoleranz|exakte[nr]? Körper|Rezept\w*"
)

#: Satzmuster, die nach Sprachmodell klingen (D14): das Semikolon und die
#: Formel „Nur …:“ / „Nicht …:“ am Anfang.
SATZMUSTER: dict[str, re.Pattern[str]] = {
    "Fachwort": FACHWORT,
    "Semikolon": re.compile(r";"),
    "Nur-Formel": re.compile(r"^(Nur|Nicht)\b[^:.]{0,80}:"),
}

#: Wie viele Kundentexte je Muster heute noch treffen. Die Zahl sinkt mit jeder
#: Überarbeitung; sie zu erhöhen ist eine Entscheidung, kein Nachtrag. Mit
#: Review P2 N5 stieg sie einmal, weil der Wächter seitdem jeden Katalogtext
#: liest und nicht nur die nach Aufrufort eingeordneten.
MUSTER_BESTAND: dict[str, int] = {"Fachwort": 119, "Semikolon": 381, "Nur-Formel": 11}

MUSTER_DATEI = Path(__file__).resolve().parent / "data" / "text_patterns.json"

#: Je Sprache, wie viele Übersetzungen ein Semikolon tragen, das ihre deutsche
#: Quelle nicht hat. Die Zahl darf nur sinken (Review P2 N5).
UEBERSETZT_BESTAND: dict[str, int] = {"en": 89, "es": 192, "fr": 97, "it": 61, "pt": 113}

UEBERSETZT_DATEI = Path(__file__).resolve().parent / "data" / "translated_semicolons.json"


def kundentexte() -> set[str]:
    """Jeder deutsche Kundentext — die Schlüssel der Sprachkataloge.

    Bis Review P2 N5 las der Musterwächter nur, was ``test_text_length`` nach
    Aufrufort einordnet. Ein ``return _(…)`` außerhalb einer ``*empty*``-Funktion
    und jeder Handbuchabsatz fielen dabei durch, und neue Semikolons standen
    unbemerkt im Kundentext. Jeder Text über ``_()`` steht in jedem Katalog
    (``test_translations``), die Schlüssel sind also die vollständige Menge.
    """
    from app.i18n.catalog import read_catalog

    found: set[str] = set()
    for language in available_languages():
        if language != "de":
            found |= set(read_catalog(language))
    return found


def uebersetzte_semikolons() -> dict[str, list[str]]:
    """Je Sprache die Quelltexte ohne Semikolon, deren Übersetzung eines trägt, sortiert."""
    from app.i18n.catalog import read_catalog

    return {
        language: sorted(
            source
            for source, text in read_catalog(language).items()
            if ";" in text and ";" not in source
        )
        for language in available_languages()
        if language != "de"
    }


def muster_funde(texte: set[str]) -> dict[str, list[str]]:
    """Je Muster die Kundentexte, die es treffen, sortiert."""
    return {
        name: sorted(text for text in texte if muster.search(text))
        for name, muster in SATZMUSTER.items()
    }


def muster_probleme(
    funde: dict[str, list[str]], bestand: dict[str, list[str]], zahlen: dict[str, int]
) -> list[str]:
    """Was den Musterwächter rot macht — leer, wenn alles stimmt."""
    probleme: list[str] = []
    for name in funde:
        erlaubt = set(bestand.get(name, []))
        probleme += [f"{name} neu: {text}" for text in funde[name] if text not in erlaubt]
        probleme += [
            f"{name}: aus dem Bestand streichen: {text}"
            for text in bestand.get(name, [])
            if text not in funde[name]
        ]
        if len(bestand.get(name, [])) != zahlen.get(name, 0):
            probleme.append(
                f"{name}: {len(bestand.get(name, []))} eingefroren, MUSTER_BESTAND sagt "
                f"{zahlen.get(name, 0)} — der Bestand darf nur schrumpfen"
            )
    return probleme


def test_no_new_customer_text_uses_jargon_or_a_machine_pattern() -> None:
    """Kein neuer Kundentext mit Fachwort, Semikolon oder „Nur …:“ (RM-509, D13/D14).

    Geprüft wird jeder Katalogtext (:func:`kundentexte`), auch Handbuch und
    Sätze ohne eingeordneten Aufrufort. Was heute trifft, steht in
    ``tests/data/text_patterns.json``.
    """
    from tests.test_text_length import application_sources, customer_texts

    texte = kundentexte()
    eingeordnet = {entry.text for entry in customer_texts(application_sources())}
    assert eingeordnet and eingeordnet <= texte, "der Katalog fasst die eingeordneten Texte"
    bestand = json.loads(MUSTER_DATEI.read_text(encoding="utf-8"))
    probleme = muster_probleme(muster_funde(texte), bestand, MUSTER_BESTAND)
    assert not probleme, "\n".join(probleme[:30])


def test_the_pattern_guard_reads_the_manual_and_unplaced_returns() -> None:
    """Handbuchabsätze und ein ``return _(…)`` ohne Art sind im Wächter (Review P2 N5).

    Beide ordnet ``test_text_length`` keiner Art zu; ohne sie sah der Wächter
    das Semikolon im Normteil-Absatz des Handbuchs und in „Zu weit für …“ nicht.
    """
    from tests.test_text_length import application_sources, customer_texts

    eingeordnet = {entry.text for entry in customer_texts(application_sources())}
    texte = kundentexte()
    handbuch = next(text for text in texte if text.startswith("Woher die Maße kommen"))
    zu_weit = next(text for text in texte if text.startswith("Für {size} zu weit, der Gang"))
    assert handbuch not in eingeordnet and zu_weit not in eingeordnet, "sonst prüft das nichts"


def test_no_translation_adds_a_semicolon_its_source_does_not_have() -> None:
    """Eine Übersetzung trägt kein Semikolon, wo die deutsche Quelle keines hat (Review P2 N5).

    Der Senkkopfsatz verlor sein Semikolon in allen sechs Sprachen und bekam es
    in fünf Übersetzungen zurück, ohne dass ein Test rot wurde. Was heute
    trifft, steht je Sprache in ``tests/data/translated_semicolons.json``.
    """
    funde = uebersetzte_semikolons()
    assert set(funde) == set(UEBERSETZT_BESTAND), "jede Übersetzung hat einen Bestand"
    bestand = json.loads(UEBERSETZT_DATEI.read_text(encoding="utf-8"))
    probleme = muster_probleme(funde, bestand, UEBERSETZT_BESTAND)
    assert not probleme, "\n".join(probleme[:30])


def test_the_pattern_guard_sees_a_new_semicolon() -> None:
    """Gegenprobe: ein neues Semikolon ist rot, ein gestrichenes Vorkommen auch."""
    funde = muster_funde({"Kurz und klar.", "Erst dies; dann das.", "Nur hier: so."})
    assert funde["Semikolon"] == ["Erst dies; dann das."]
    assert funde["Nur-Formel"] == ["Nur hier: so."]
    probleme = muster_probleme(funde, {"Nur-Formel": ["Nur hier: so."]}, {"Nur-Formel": 1})
    assert probleme == ["Semikolon neu: Erst dies; dann das."]
    veraltet = muster_probleme(
        muster_funde({"Kurz."}), {"Semikolon": ["Erst dies; dann das."]}, {"Semikolon": 1}
    )
    assert veraltet == ["Semikolon: aus dem Bestand streichen: Erst dies; dann das."]
