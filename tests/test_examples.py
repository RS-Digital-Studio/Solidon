"""Die drei Beispielprojekte (Bauplan §37.2, §40 für P8).

„Die drei Beispielprojekte öffnen und rechnen fehlerfrei" — das ist das
Abnahmekriterium, und das hier ist es. Sie sind Dokumentation und Abnahmetest
zugleich, eine Änderung, die eines von ihnen bricht, scheitert also hier statt
vor einem neuen Nutzer.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

import pytest

from app.core import examples
from app.core.knowledge import profiles
from app.core.registry import REGISTRY
from app.core.scene import evaluate
from app.core.scene.project import ProjectSources, load
from app.core.types import Profile
from app.i18n import SOURCE_LANGUAGE, set_language
from app.i18n.catalog import install_language


def test_there_is_one_example_per_way() -> None:
    """§2.2 hat vier Wege, und §37.2 will genau die vier als Beispiele.

    Der vierte kam mit P16 dazu: eine Figur formen. Die weiteren Projekte sind
    keine fünften Wege — sie zeigen, was auf den vieren an Werkzeug
    bereitliegt. Die vier müssen aber da sein und vorn stehen: sie beantworten
    „wie fange ich an", und das ist die erste Frage.
    """
    ways = [entry.way for entry in examples.EXAMPLES if entry.way]

    assert ways == ["1", "2", "3", "4"]
    assert len({entry.id for entry in examples.EXAMPLES}) == len(examples.EXAMPLES)
    for entry in examples.EXAMPLES:
        assert str(entry.title).strip()
        assert str(entry.doc).strip()


def test_the_examples_reach_most_of_the_catalogue() -> None:
    """Drei Beispiele zeigten acht von zweiundsechzig Operationen (§25).

    Das ist genug, um die Wege zu erklären, und zu wenig, um das Werkzeug zu
    zeigen: die Bausteinbibliothek, die Beschriftung und die Kalibrierung waren
    in keinem davon zu sehen. Die Zahl hier ist kein Selbstzweck — sie hält
    fest, dass ein neuer Bereich auch ein Beispiel bekommt.
    """
    used: set[str] = set()
    for entry in examples.EXAMPLES:
        project = load(examples.directory() / entry.filename)
        used.update(operation.op for operation in project.document.ops)

    categories = {REGISTRY.get(name).category for name in used if REGISTRY.has(name)}

    assert len(used) >= 20, f"nur {len(used)} Operationen in allen Beispielen"
    # **``sketch`` steht seit dem 31.08.2026 dabei.** Bis dahin zeigten neun
    # Beispiele keine einzige ``sketch_*``-Operation — ein Kern mit eigenem
    # Löser (§30.1), in den ersten fünf Minuten unsichtbar. Der Test war grün,
    # weil er nicht danach fragte; sein eigener Zweck ist aber genau der, dass
    # ein neuer Bereich auch ein Beispiel bekommt.
    assert {
        "parts",
        "label",
        "prepare",
        "holes",
        "repair",
        "import",
        "sketch",
    } <= categories


def test_all_three_are_installed() -> None:
    found = {path.name for path in examples.paths()}

    assert found == {entry.filename for entry in examples.EXAMPLES}


@pytest.mark.parametrize("example", examples.EXAMPLES, ids=lambda entry: entry.id)
def test_an_example_opens_and_computes(example: examples.Example, profile: Profile) -> None:
    path = examples.directory() / example.filename
    project = load(path)

    result = evaluate(
        project.document,
        profiles.make_profile(
            project.document.printer or "centauri-carbon-2",
            project.document.material or "petg",
        ),
        sources=ProjectSources(project),
    )

    assert result.complete, [str(f.message) for f in result.scene.report.findings]
    assert result.scene.objects
    for entry in result.scene.objects.values():
        assert entry.mesh.volume > 0.0


def test_the_second_way_really_uses_parameters() -> None:
    """§2.2 Weg 2: an einer Zahl drehen, das Modell folgt — es muss also
    Zahlen geben.
    """
    project = load(examples.directory() / "weg2-halter-konstruieren.p3d")

    assert set(project.document.parameters) >= {"breite", "tiefe", "staerke"}
    bound = [
        entry
        for entry in project.document.ops
        if any(str(value).startswith("=@") for value in entry.params.values())
    ]
    assert bound, "the operations are tied to the parameters, not to fixed numbers"

    tile = next(entry for entry in examples.EXAMPLES if entry.id == "weg2-halter-konstruieren")
    description = str(tile.doc)
    for parameter in project.document.parameters.values():
        assert str(parameter.title) in description, (
            f"die Startkachel verschweigt den sichtbaren Parameter {parameter.title}"
        )


def test_the_third_way_tile_describes_the_project_that_opens() -> None:
    """Die Kachel versprach eine Teilung, obwohl der Weg keine enthält."""
    project = load(examples.directory() / "weg3-generiert-aufbereiten.p3d")
    tile = next(entry for entry in examples.EXAMPLES if entry.id == "weg3-generiert-aufbereiten")
    description = str(tile.doc)
    operations = {entry.op for entry in project.document.ops}

    assert "place_on_bed" in operations and "auf das Druckbett" in description
    assert not any(name.startswith("split") for name in operations)
    assert "teilen" not in description.casefold(), "die Kachel verspricht einen fehlenden Schritt"


def test_the_second_way_uses_the_library() -> None:
    """§39: Bausteine vor Primitiven — das Beispiel zeigt es, statt es zu
    sagen.
    """
    project = load(examples.directory() / "weg2-halter-konstruieren.p3d")
    names = [entry.op for entry in project.document.ops]

    assert names.count("insert_screw_hole") == 2
    assert "insert_rib" in names


def test_the_third_way_says_where_its_geometry_came_from() -> None:
    """§16.3: ein erzeugtes Netz ist als erzeugt markiert, nicht als
    gezeichnet.
    """
    project = load(examples.directory() / "weg3-generiert-aufbereiten.p3d")

    kinds = {source.kind for source in project.document.sources.values()}
    assert kinds == {"generated"}


def test_turning_a_parameter_changes_the_second_example(profile: Profile) -> None:
    """Das Versprechen von Weg 2, geprüft am Beispiel, das es vorführt."""
    import dataclasses

    project = load(examples.directory() / "weg2-halter-konstruieren.p3d")
    sources = ProjectSources(project)
    before = evaluate(project.document, profile, sources=sources)

    parameters = project.document.parameters
    parameters["breite"] = dataclasses.replace(parameters["breite"], value=90.0)
    after = evaluate(project.document, profile, sources=sources)

    assert after.complete
    assert (
        after.scene.objects["obj_1"].mesh.bounds.size[0]
        > (before.scene.objects["obj_1"].mesh.bounds.size[0])
    )


def test_the_written_documents_count_the_ways_and_examples_right() -> None:
    """Bauplan und README behaupten Zahlen — hier stehen sie neben der Quelle.

    Beide waren gedriftet: Der Bauplan führte §2.2 als „Drei Hauptwege",
    während der vierte längst gebaut war (P16, `weg4-figur-formen`), und die
    README sprach von drei Wegen und acht Beispielprojekten, als es vier und
    neun waren. Der Test darüber wusste es besser als beide Unterlagen — er
    prüft seit P16 auf vier Wege.

    Gezählt wird gegen ``EXAMPLES``, denn das ist die Quelle: Was dort liegt,
    liegt beim Start bereit.
    """
    wurzel = Path(__file__).resolve().parent.parent
    wege = sum(1 for entry in examples.EXAMPLES if entry.way)
    zahlwort = {3: "drei", 4: "vier", 5: "fünf"}[wege]

    bauplan = (wurzel / "3d-agent-bauplan.md").read_text(encoding="utf-8")
    assert f"### 2.2 {zahlwort.capitalize()} Hauptwege" in bauplan, (
        f"§2.2 nennt nicht {zahlwort} Hauptwege, obwohl {wege} Beispiele einen Weg tragen."
    )

    readme = (wurzel / "README.md").read_text(encoding="utf-8")
    assert f"## Die {zahlwort} Wege" in readme, f"Die README zählt nicht {zahlwort} Wege."

    # Die Unterlagen schreiben Zahlen aus — „neun Beispielprojekte", nicht „9".
    zahlen = {7: "sieben", 8: "acht", 9: "neun", 10: "zehn", 11: "elf", 12: "zwölf"}
    wort = zahlen.get(len(examples.EXAMPLES), str(len(examples.EXAMPLES)))
    assert f"{wort} Beispielprojekte" in readme, (
        f"Die README nennt nicht {wort} ({len(examples.EXAMPLES)}) Beispielprojekte."
    )

    # Und jedes Beispiel steht mit seiner Datei in der Tabelle — eine Zeile,
    # die fehlt, ist ein Projekt, von dem der Leser nichts erfährt.
    fehlen = [entry.id for entry in examples.EXAMPLES if f"{entry.id}.p3d" not in readme]
    assert not fehlen, f"Diese Beispiele fehlen in der README-Tabelle: {fehlen}"


@pytest.mark.parametrize("example", examples.EXAMPLES, ids=lambda entry: entry.id)
def test_no_example_ships_a_printer_of_its_own(example: examples.Example) -> None:
    """Ein Beispiel bringt keinen Drucker mit — sonst nimmt es dem Kunden seinen.

    Der Erstlauf fragt im Dialog „Erste Schritte" nach Drucker und Material.
    Wer danach auf „Weg 1" klickt — den die Anwendung selbst „der häufigste
    Fall" nennt —, hatte beides verloren: Alle neun Beispiele trugen
    ``centauri-carbon-2`` und ``petg``, den Drucker dessen, der sie gebaut
    hat. In der Leiste stand ein fremdes Gerät, in der Statuszeile Gewicht und
    Druckzeit dafür, und die Bohrung im zweiten Tourschritt rechnete mit der
    Toleranz von PETG statt der gewählten (0,25 gegen 0,20 mm).

    Ein **gespeichertes** Projekt soll seinen Drucker mitbringen, das ist
    Reproduzierbarkeit. Ein **mitgeliefertes** Beispiel nicht: Es zeigt einen
    Weg, keine Werkstatt. Bleibt das Feld leer, greift beim Öffnen die Vorgabe
    (``profiles.DEFAULT_PRINTER``), und die ist zugleich das, was der Dialog
    vorschlägt.

    Die Prüfung steht hier und nicht im Erzeuger, weil sie die **ausgelieferte
    Datei** treffen muss: ``tools/make_examples.py`` ist reparierbar, ein
    Beispiel im Paket nicht.
    """
    project = load(examples.directory() / example.filename)
    document = project.document
    assert not document.printer, (
        f"{example.filename} bringt den Drucker {document.printer!r} mit und "
        "überschreibt damit die Wahl des Kunden. Neu erzeugen: "
        "python tools/make_examples.py"
    )
    assert not document.material, (
        f"{example.filename} bringt das Material {document.material!r} mit und "
        "überschreibt damit die Wahl des Kunden. Neu erzeugen: "
        "python tools/make_examples.py"
    )


@pytest.mark.parametrize("example", examples.EXAMPLES, ids=lambda entry: entry.id)
def test_no_example_ships_a_duplicate_operation_id(example: examples.Example) -> None:
    """Zwei Operationen mit derselben Kennung zerstören das Projekt beim Undo.

    Gemessen an ``dose-mit-deckel.p3d``, dem Vorzeigebeispiel, aus dem das
    Handbuchbild stammt: Es trug ``create_lid`` und ``arrange_bed`` beide unter
    der Kennung 6. Ein Strg+Z nahm **beide** zurück, ein Strg+Y brachte nur
    ``arrange_bed`` wieder — der Deckel war weg, die Kette hielt an
    (``complete=False``), und zurück kam er nie. Das ist keine Warnung im
    Bericht, sondern ein zerstörtes Dokument in zwei Tastendrücken.

    Die Ursache im Code ist behoben: ``History._reseed`` richtet die Zähler vor
    jeder Transaktion am Dokument aus, weil mehrere ``History``-Objekte über
    demselben Dokument schreiben (der Deckelablauf legt sich eines an, um die
    Passung nachzutragen). Die **Datei** war älter als der Fix und trug ihn
    nicht — und niemand sah hin. Deshalb steht die Prüfung hier: Der
    Erzeugungsweg ist reparierbar, ein mitgeliefertes Projekt nicht.

    Geprüft werden auch die Verweise der Transaktionen: Eine Transaktion, die
    eine Kennung nennt, die es zweimal gibt, ist genauso wenig eindeutig
    zurücknehmbar.
    """
    project = load(examples.directory() / example.filename)
    ops = project.document.ops

    seen: dict[int, str] = {}
    doubled: list[str] = []
    for operation in ops:
        if operation.id in seen:
            doubled.append(f"{operation.id}: {seen[operation.id]} und {operation.op}")
        seen[operation.id] = operation.op

    assert not doubled, f"{example.filename} trägt doppelte Kennungen — {doubled}"

    known = {operation.id for operation in ops}
    for transaction in project.document.transactions:
        missing = [entry for entry in transaction.ops if entry not in known]
        assert not missing, (
            f"{example.filename}: Transaktion {transaction.id} nennt Operationen, "
            f"die es nicht gibt — {missing}"
        )


@pytest.mark.parametrize("example", examples.EXAMPLES, ids=lambda entry: entry.id)
def test_no_example_shows_a_corpus_filename_as_an_object_name(
    example: examples.Example, profile: Profile
) -> None:
    """Das erste Objekt, das ein Demonutzer sah, hieß „plate_holes".

    Die ``load``-Op nimmt den Dateinamen, wenn ihr keiner gegeben wird — und die
    Datei ist hier ein Netz aus dem Testkorpus. Jedes andere Beispiel benennt
    seine Körper („Halter", „Figur", „Gehäuseboden", „Schild"); ausgerechnet das
    eine, das zuerst geöffnet wird, tat es nicht.

    Geprüft wird die Form, nicht ein einzelner Name: ein Objektname mit
    Unterstrich oder Dateiendung ist keiner, den jemand geschrieben hat.
    """
    project = load(examples.directory() / example.filename)
    result = evaluate(
        project.document,
        profiles.make_profile(
            project.document.printer or "centauri-carbon-2",
            project.document.material or "petg",
        ),
        sources=ProjectSources(project),
    )

    for entry in result.scene.objects.values():
        # **Geprüft wird die angezeigte Fassung**, deshalb ``str``. Seit
        # Format 10 kann ein Objektname ein ``TranslatableText`` sein (§4.1),
        # und der ist keine Zeichenkette: ``"_" in name`` wirft. Gemeint ist
        # hier ohnehin, was der Nutzer liest — ein Dateiname sieht in jeder
        # Sprache wie einer aus.
        name = str(entry.name)
        assert "_" not in name, f"{name} liest sich wie ein Dateiname"
        assert not name.lower().endswith((".stl", ".3mf", ".obj", ".step", ".stp")), (
            f"{name} traegt eine Dateiendung"
        )
        assert name.strip() == name and name, "ein Name ohne Text ist keiner"


def test_no_example_greets_with_a_contradiction(profile: Profile) -> None:
    """Ein Beispiel ist Dokumentation. Was darin warnt, ist eine Aussage über
    die Anwendung — und die erste, die ein neuer Nutzer liest.

    Zwei taten es. „Weg 3" nannte drei Warnungen, davon zwei, die drei Schritte
    später behoben waren: „Es gibt sehr kleine Einzelteile. Gelöscht wurde
    nichts." stand über „Kleinstteile wurden gelöscht.". Und ausgerechnet das
    Beispiel für Passungen zeigte eine verletzte — der Deckelkragen bekam das
    doppelte Spiel, weil ``clearance`` dort radial gerechnet wurde und überall
    sonst diametral.

    Geprüft wird gegen die Befundcodes und nicht gegen die Zahl der Warnungen:
    Eine Warnung, die etwas Wahres sagt („Kleinstteile wurden gelöscht"),
    gehört dorthin.

    **Die Ausnahmen sind dieselben wie beim Nachbarn darunter, nicht eigene.**
    Zwei Listen für dieselbe Frage laufen auseinander, und dann erlaubt die
    eine, was die andere verbietet — das merkt niemand, weil beide Tests grün
    sind, solange kein Beispiel beides auslöst. Was hier verboten ist, steht
    also in ``_ERLAUBTE_BEGRUESSUNG``, und wer eine Ausnahme einträgt,
    begründet sie **einmal**.
    """
    verboten = {"ingest.not_watertight", "ingest.small_components", "fit.violated"}
    for entry in examples.EXAMPLES:
        project = load(examples.directory() / entry.filename)
        result = evaluate(
            project.document,
            profiles.make_profile(
                project.document.printer or "centauri-carbon-2",
                project.document.material or "petg",
            ),
            sources=ProjectSources(project),
        )
        erlaubt = set(_ERLAUBTE_BEGRUESSUNG.get(entry.id, {}))
        found = {
            finding.code
            for finding in result.scene.report.findings
            if finding.code in verboten - erlaubt
        }
        assert not found, f"{entry.id}: {sorted(found)}"


#: Warnungen, mit denen ein Beispiel den Kunden begrüßen **darf** — je Beispiel
#: ein Befundcode mit dem Grund, warum er dasteht.
#:
#: Die Liste ist eine Ausnahmeliste und keine Obergrenze, und der Unterschied
#: entscheidet: „höchstens elf Warnungen" wäre in einer Woche grün mit zwölf,
#: weil jemand die Zahl anpasst. Hier trägt jede Ausnahme ihren eigenen Satz,
#: und eine **neue** Warnung ist sofort rot.
_ERLAUBTE_BEGRUESSUNG: Final[dict[str, dict[str, str]]] = {
    "weg3-generiert-aufbereiten": {
        # Wahr und am Platz: Der erzeugte Körper bringt Kleinstteile mit, das
        # Beispiel räumt sie weg, und der Befund sagt genau das. Eine Warnung,
        # die etwas Wahres über den gezeigten Weg sagt, gehört in ein Beispiel
        # — sie ist Teil dessen, was es vorführt.
        "repair.components_removed": "zeigt, was Weg 3 mit erzeugten Netzen tut",
    },
    "passung-nach-materialwechsel": {
        # **Hier ist die Warnung der Inhalt.** Das Beispiel führt vor, was
        # geschieht, wenn ein Deckel aus weicherem Material kommen soll: Er
        # braucht mehr Spiel, und die Öffnung ist noch die alte. Ohne die
        # Warnung beim Öffnen hätte das Beispiel nichts zu zeigen — sie ist
        # kein Makel, sondern die Ausgangslage, und der Weg daraus ist ein
        # Klick auf die Meldung und eine Zahl.
        "fit.violated": "ist der Inhalt des Beispiels, nicht sein Fehler",
    },
}


def test_no_example_greets_the_customer_with_a_warning(profile: Profile) -> None:
    """Was ein Beispiel beim Öffnen sagt, ist das Erste, was ein Kunde von
    Solidon liest — und es sagt mehr über die Anwendung als jede Zeile im
    Handbuch.

    **Die Lücke, die es gab.** ``test_an_example_opens_and_computes`` fragt, ob
    ein Beispiel öffnet und rechnet; das ist die Frage des Entwicklers. Die
    Frage des Kunden ist „was steht da, wenn ich es aufmache", und die hat
    niemand gestellt: Am 23.08.2026 begrüßten **fünf von neun** Beispielen mit
    zusammen **elf** Warnungen, und keine davon war je an einer Prüfung
    vorbeigekommen — sie waren an gar keiner angekommen. Der Nachbar darüber
    (``…greets_with_a_contradiction``) prüft drei benannte Codes; alles andere
    ging durch.

    **Warum Ausnahmeliste und nicht Verbotsliste.** Eine Verbotsliste kennt nur,
    woran jemand gedacht hat. Zehn der elf Warnungen trugen einen Code, den sie
    nicht enthielt. Umgekehrt gilt: Was hier nicht steht, ist rot — auch ein
    Code, den es heute noch nicht gibt.

    **Und warum sie in beide Richtungen prüft.** Eine Ausnahme, deren Warnung
    verschwunden ist, wird gemeldet: Sonst bleibt die Zeile stehen, wenn der
    Fehler längst behoben ist, und deckt beim nächsten Mal etwas zu, das
    niemand geprüft hat. Wer eine Warnung löst, streicht seine Zeile — der Test
    sagt ihm, dass er darf.
    """
    offen: list[str] = []
    unnoetig: list[str] = []
    for entry in examples.EXAMPLES:
        project = load(examples.directory() / entry.filename)
        result = evaluate(
            project.document,
            profiles.make_profile(
                project.document.printer or "centauri-carbon-2",
                project.document.material or "petg",
            ),
            sources=ProjectSources(project),
        )
        erlaubt = _ERLAUBTE_BEGRUESSUNG.get(entry.id, {})
        gesehen = {
            finding.code
            for finding in result.scene.report.findings
            if finding.severity in ("warning", "error")
        }
        offen.extend(f"{entry.id}: {code}" for code in sorted(gesehen - set(erlaubt)))
        unnoetig.extend(f"{entry.id}: {code}" for code in sorted(set(erlaubt) - gesehen))

    assert not offen, (
        "Beispiele begrüßen den Kunden mit Warnungen, die niemand eingetragen hat:\n"
        + "\n".join(offen)
    )
    assert not unnoetig, (
        "Diese Ausnahmen treffen nicht mehr zu — die Warnung ist weg, die Zeile "
        "darf gestrichen werden:\n" + "\n".join(unnoetig)
    )

    # **Und die dritte Richtung, die beim ersten Bauen fehlte.** Eine Ausnahme
    # für ein Beispiel, das es nicht gibt, wird nie betrachtet:
    # ``get(entry.id)`` findet sie nicht, und sie schweigt für immer.
    # Aufgefallen ist es in der Gegenprobe — dort stand versehentlich
    # ``kalibrieren`` statt ``drucker-kalibrieren``, und der Test blieb grün,
    # obwohl er hätte melden müssen. Ein Eintrag, den niemand liest, ist
    # schlimmer als keiner: Er sieht aus wie eine geprüfte Entscheidung.
    bekannt = {entry.id for entry in examples.EXAMPLES}
    erfunden = sorted(set(_ERLAUBTE_BEGRUESSUNG) - bekannt)
    assert not erfunden, (
        "Ausnahmen für Beispiele, die es nicht gibt — sie werden nie gelesen: "
        + ", ".join(erfunden)
    )


def test_the_split_example_does_not_ask_for_work_it_already_did(profile: Profile) -> None:
    """„Aushöhlen und teilen“ endet fertig angeordnet und ohne Restauftrag."""
    project = load(examples.directory() / "aushoehlen-und-teilen.p3d")
    result = evaluate(project.document, profile, sources=ProjectSources(project))

    codes = {finding.code for finding in result.scene.report.findings}
    assert "prepare.halves_in_place" not in codes, (
        "das Beispiel hat die Hälften bereits angeordnet und darf nicht noch einmal darum bitten"
    )
    from app.core.export.writer import plan_export

    plan = plan_export(
        list(result.scene.objects.values()),
        project_name="aushöhlen-und-teilen",
        profile=profile,
        export_format="3mf",
        sources=dict(project.document.sources),
    )
    export_codes = {finding.code for finding in plan.findings}
    assert "arrange.off_the_plate" not in export_codes, export_codes


def test_every_example_can_still_be_built() -> None:
    """Nicht die eingecheckte Datei prüfen, sondern das Werkzeug, das sie macht.

    Die Tests darüber lesen ``app/examples/*.p3d``. Das sind Artefakte: Sie
    liegen im Repository und bleiben gültig, auch wenn ihr Erzeuger längst
    nicht mehr läuft. ``tools/make_examples.py`` läuft nur im Paketier-Job,
    und der nur bei einem Tag — zwischen zwei Veröffentlichungen fährt es
    also niemand.

    Am 27.08.2026 hat das eine Fassung gekostet. Um 06:59 bekam
    ``blend_union`` ein ``keeps_inputs``, weil die Merkmale des Vorgängers an
    der alten Kennung hängen und ``hole_1`` nach dem Vereinigen sonst auf ein
    anderes Loch zeigt — richtig und nötig. Nur rechnete ``way_four`` danach
    mit einer frischen Kennung weiter und verwies auf ``obj_3``: zwei rein,
    eins heraus, und die Wasserlinie war trotzdem stehengeblieben. Bemerkt
    hat es niemand, bis der Paketbau von 0.2.1 auf allen vier Plattformen an
    derselben Zeile abbrach.

    Der Test kostet ein Hundertstel: Die Bau-Funktionen stellen nur den
    Stapel auf, und ``History.apply`` prüft die Kennungen dabei — gerechnet
    wird erst bei der Auswertung, die hier niemand anstößt.
    """
    from tools import make_examples

    gebaut = {
        "way_one": make_examples.way_one,
        "way_two": make_examples.way_two,
        "way_three": make_examples.way_three,
        "way_four": make_examples.way_four,
        "housing": make_examples.housing,
        "two_colour_sign": make_examples.two_colour_sign,
        "calibration_plate": make_examples.calibration_plate,
        "hollow_and_split": make_examples.hollow_and_split,
        "box_with_lid": make_examples.box_with_lid,
    }

    gescheitert: list[str] = []
    for name, funktion in gebaut.items():
        try:
            funktion()
        except Exception as problem:  # jede Ausnahme ist hier ein Befund
            gescheitert.append(f"{name}: {type(problem).__name__}: {problem}")

    assert not gescheitert, "Beispiele lassen sich nicht mehr bauen:\n" + "\n".join(gescheitert)


@pytest.mark.parametrize("example", examples.EXAMPLES, ids=lambda entry: entry.id)
def test_no_feature_sits_outside_the_body_it_belongs_to(
    example: examples.Example, profile: Profile
) -> None:
    """Ein benanntes Merkmal wandert mit seinem Körper mit (§21.2).

    **Was passiert, wenn nicht.** `create_lid` legt `lid_cavity` mit seinem
    Mittelpunkt an, `arrange_bed` schiebt den Körper danach an seinen Platz auf
    dem Bett — und das Merkmal bleibt, wo es war. Gemessen am elften Beispiel:
    Körper bei x −120…−50, Merkmal bei x 0,3. Der Klick auf eine Warnung fliegt
    die Kamera dann **vom Körper weg ins Leere**, und der Kunde sieht einen
    leeren Viewport, aus dem er sich zurücknavigieren muss. Das ist schlimmer
    als ein folgenloser Klick.

    Der Mechanismus dafür ist gebaut (`moved_features`), greift aber nur, wo
    die Operation **eine** Matrix meldet. `arrange_bed` verschiebt jeden Körper
    einzeln und meldet deshalb keine; für verwaiste Merkmale gab es dazu schon
    eine Sonderbehandlung, für die benannten nicht.

    Geprüft wird gegen den Hüllquader mit einem Zuschlag: Ein Merkmal darf auf
    der Oberfläche sitzen und dort einen halben Millimeter danebenliegen, ohne
    dass etwas falsch wäre.
    """
    project = load(examples.directory() / example.filename)
    result = evaluate(project.document, profile, sources=ProjectSources(project))

    daneben: list[str] = []
    for object_id, entry in result.scene.objects.items():
        bounds = entry.mesh.bounds
        for name, feature in entry.features.items():
            # **Nur die benannten Merkmale**, und die Einschränkung ist keine
            # Bequemlichkeit: Ein *erkanntes* Merkmal wird am aktuellen Netz
            # gemessen und kann gar nicht zurückbleiben; wo es trotzdem
            # danebenliegt (weg4 zeigt einundzwanzig Kugeln), ist das ein
            # anderer Fehler mit einer anderen Ursache und gehört in einen
            # eigenen Test, nicht in eine erweiterte Erwartung hier.
            if feature.provenance != "generated":
                continue
            # Und was der Kunde absichtlich weggeschnitten hat, ist nicht
            # zurückgeblieben, sondern weg: `test_piece` schneidet 22 mm aus
            # einem 70er Gehäuse, und die Merkmale des Originals liegen danach
            # außerhalb. Der Kern sagt dazu an anderer Stelle denselben Satz
            # („was außerhalb des neuen Körpers liegt, wurde weggeschnitten").
            if any(entry.op == "test_piece" for entry in project.document.ops):
                continue
            centre = feature.params.get("centre")
            if not isinstance(centre, list | tuple) or len(centre) != 3:
                continue
            for achse, wert in enumerate(centre):
                unten = bounds.minimum[achse] - 0.5
                oben = bounds.maximum[achse] + 0.5
                if not unten <= float(wert) <= oben:
                    daneben.append(
                        f"{object_id}.{name}: Achse {achse} bei {float(wert):.1f}, "
                        f"Körper von {bounds.minimum[achse]:.1f} bis {bounds.maximum[achse]:.1f}"
                    )
                    break

    assert not daneben, "Merkmale liegen außerhalb ihres Körpers:\n" + "\n".join(daneben)


def test_object_names_follow_a_language_change(profile: Profile) -> None:
    """Ein Objektname wandert mit der Sprache mit, auch bei offenem Projekt.

    **Der Fall, den ein Test ohne Umschalten nicht sieht.** Wer die Sprache
    beim Start setzt und dann öffnet, bekommt „Can" und „Can Lid" — alles
    richtig. Wer auf Deutsch öffnet und danach umschaltet, bekam „Can" und
    **„Dose Deckel"**: Die Dose folgt, weil ihr Name ein übersetzbarer Text
    ist; der Deckel bleibt, weil `create_lid` ihn beim Erzeugen mit
    ``.translate()`` zu einer festen Zeichenkette gemacht hat.

    Es ist dieselbe Familie wie ein Merkmal, das nach dem Anordnen liegen
    bleibt: beim Erzeugen festgeschrieben, von einem späteren Vorgang überholt
    — dort eine Verschiebung, hier ein Sprachwechsel.

    Geprüft wird **ohne** erneute Auswertung, denn genau das tut die Oberfläche
    beim Umschalten auch nicht: Sie zeichnet den Baum neu, sie rechnet die
    Szene nicht nach.
    """
    set_language(SOURCE_LANGUAGE)
    project = load(examples.directory() / "dose-mit-deckel.p3d")
    result = evaluate(project.document, profile, sources=ProjectSources(project))
    objekte = list(result.scene.objects.values())
    assert objekte, "das Beispiel hat Körper"

    install_language("en")
    set_language("en")
    try:
        deutsch = [
            str(entry.name)
            for entry in objekte
            if any(wort in str(entry.name) for wort in ("Dose", "Deckel", "Prüfstück", "Körper"))
        ]
    finally:
        set_language(SOURCE_LANGUAGE)

    assert not deutsch, "diese Namen sind beim Sprachwechsel deutsch geblieben: " + ", ".join(
        deutsch
    )


def test_a_finding_value_that_names_a_body_follows_the_language(profile: Profile) -> None:
    """Ein Körpername in einem Befundwert wandert mit der Sprache mit.

    **Dieselbe Klasse wie der Deckelname, eine Ebene tiefer.** `set_material`
    meldet „Dieser Körper wird in einem eigenen Material gerechnet" und legt den
    Namen als Wert daneben — mit `str()` aufgelöst. Im englischen Fenster stand
    dort weiter „Deckel", während der Körper im Objektbaum daneben „Lid" hieß:
    zwei Namen für dasselbe Teil in einem Blick.

    Der Wert wird beim Speichern aufgelöst, und das ist richtig — `report.json`
    ist die Momentaufnahme des letzten Berichts, und beim Öffnen wird ohnehin
    neu gerechnet. Im Speicher aber bleibt er übersetzbar, und nur darauf sieht
    der Kunde.
    """
    set_language(SOURCE_LANGUAGE)
    project = load(examples.directory() / "passung-nach-materialwechsel.p3d")
    result = evaluate(project.document, profile, sources=ProjectSources(project))
    treffer = [
        finding for finding in result.scene.report.findings if finding.code == "prepare.material"
    ]
    assert treffer, "das Beispiel setzt ein Material und meldet es"
    wert = treffer[0].values["object"]

    install_language("en")
    set_language("en")
    try:
        gezeigt = str(wert)
    finally:
        set_language(SOURCE_LANGUAGE)

    assert "Deckel" not in gezeigt, (
        f"der Befund nennt den Körper im englischen Fenster weiter deutsch: {gezeigt!r}"
    )
