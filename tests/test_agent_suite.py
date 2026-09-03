"""Die Agenten-Suite für Säule C (Bauplan §35, §40 für P4).

Zwei Hälften, und es zählt, klar zu sein, welche welche ist.

**Ohne Modell** — was hier läuft — prüft die Suite, was die *Mechanik*
garantiert, und nur das: dass jede Anfrage das Modell mit dem Kontext erreicht,
den sie braucht, dass jede Operation, die ein Fall erwartet, existiert und als
Werkzeug angeboten wird, dass eine gute Antwort genau eine Transaktion wird,
dass ein mehrdeutiger Fall, der fragt, mit seiner Frage die Oberfläche
erreicht, und dass eine Operation schemageprüft ist, bevor gerechnet wird. Ein
geskriptetes Backend spielt die gute Antwort; das sagt nichts über ein echtes
Modell, und die Suite behauptet das auch nicht.

**Mit Modell** — ``tools/run_agent_suite.py`` — gehen dieselben Fälle an das
konfigurierte Backend, und heraus kommt die Quote, die §40 verlangt: wie oft
wurde gefragt, wo die Anfrage mehrdeutig war, wie oft wurden Hauptmaße zu
Parametern, wie oft war eine Operation ungültig. Dieser Lauf braucht einen
Schlüssel und ist nicht Teil der Testsuite.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.core.agent import apply as agent_apply
from app.core.agent import tools
from app.core.agent.session import AgentSession
from app.core.backends.llm import Reply, ToolCall
from app.core.registry import REGISTRY
from app.core.scene import History, OperationDraft, evaluate
from app.core.scene.project import Project, ProjectSources, new_project
from app.core.types import Profile, Source
from tests.agent_cases import AMBIGUOUS, CASES, Case
from tests.scripted_backend import ScriptedBackend

MESHES = Path(__file__).parent / "data" / "meshes"


@pytest.fixture
def project() -> Project:
    made = new_project("centauri-carbon-2", "petg")
    made.document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/plate_holes.stl", sha256=""
    )
    made.sources["src_1"] = (MESHES / "plate_holes.stl").read_bytes()
    History(made.document).apply(
        "Laden", [OperationDraft(op="load", params={"source": "src_1", "unit": "mm"})]
    )
    return made


def good_answer(case: Case) -> list[Reply]:
    """Was ein Modell, das den Regeln folgt, mit diesem Fall täte."""
    if case.ambiguous:
        return [
            Reply(
                tool_calls=(
                    ToolCall(
                        id="1",
                        name=tools.ASK_USER,
                        arguments={"question": case.request, "options": ["hole_1", "hole_2"]},
                    ),
                )
            ),
            Reply(text="Ich nehme hole_1."),
        ]
    if case.expects_target:
        return [
            Reply(
                tool_calls=(
                    ToolCall(id="1", name=tools.SET_PRINT_TARGET, arguments={"material": "pla"}),
                )
            ),
            Reply(text="Das Projekt druckt jetzt PLA."),
        ]
    if case.expects_reading:
        reading = case.expects_reading[0]
        arguments: dict[str, object] = (
            {"kind": "estimate"}
            if reading == tools.READ_ANALYSIS
            else {"kind": "screw", "size": "M4"}
        )
        closing = "Nachgesehen." + (" Steht im Menü." if case.expects_mention else "")
        return [
            Reply(tool_calls=(ToolCall(id="1", name=reading, arguments=arguments),)),
            Reply(text=closing),
        ]
    if case.expects_mention:
        return [Reply(text="Das steht im Menü Ändern → Bohrung setzen.")]
    if case.expects_parameter:
        return [
            Reply(
                tool_calls=(
                    ToolCall(
                        id="1",
                        name=tools.ADD_PARAMETER,
                        arguments={"name": "breite", "value": 80.0, "unit": "mm"},
                    ),
                )
            ),
            Reply(text="Breite ist jetzt ein Parameter."),
        ]
    if case.expects_answer_only:
        return [Reply(text="Die Platte ist 8 mm dick.")]
    return [
        Reply(
            tool_calls=tuple(_call(index, name) for index, name in enumerate(case.expects_ops, 1))
        ),
        Reply(text="Erledigt."),
    ]


def _call(index: int, name: str) -> ToolCall:
    arguments: dict[str, object] = {"objects": ["obj_1"]}
    if name == "translate_object":
        arguments["dx"] = 10.0
    elif name == "rotate_object":
        arguments.update({"axis": "z", "angle": 90.0})
    elif name == "scale_object":
        arguments["factor"] = 1.2
    elif name == "split_pinned":
        arguments.update({"axis": "z", "position": 0.0})
    elif name == "drill_hole":
        arguments.update({"diameter": 5.0, "x": 0.0, "y": 0.0, "z": 4.0, "axis": "z"})
    elif name == "orient_for_print":
        # Die Suche über hunderte Kandidaten wird in der Leistungs-Suite gemessen;
        # hier machte sie jeden Lauf nur langsamer, ohne mehr zu prüfen.
        arguments["thorough"] = False
    return ToolCall(id=str(index), name=name, arguments=arguments)


def run(case: Case, project: Project, profile: Profile) -> tuple[AgentSession, object]:
    asked: list[str] = []

    def answer(question: str, options: list[str]) -> str:
        asked.append(question)
        return options[0] if options else "hole_1"

    agent = AgentSession(
        backend=ScriptedBackend(answers=good_answer(case)),
        document=project.document,
        profile=profile,
        sources=ProjectSources(project),
        ask=answer,
        selection=case.selection,
    )
    proposal = agent.propose(case.request)
    return agent, proposal


# --- Der Korpus der Anfragen ------------------------------------------------------


def test_the_suite_has_the_size_the_plan_asks_for() -> None:
    """§35: 39 Referenzanfragen — 21 zu Säule C (sechs davon seit der
    Agent-Vertiefung: nachsehen statt raten, Druckziel, Menüort), 18 zu
    Säule A seit den Skizzenfällen aus P13. §40 zu P4: drei mehrdeutig."""
    from tests.agent_cases import ALL_CASES, CASES_A

    assert len(CASES) == 21
    assert len(CASES_A) == 18
    assert len(ALL_CASES) == 39, "§35 nennt 39 Referenzanfragen"
    assert len(AMBIGUOUS) == 3
    assert len({case.id for case in ALL_CASES}) == 39


def test_every_expected_operation_exists() -> None:
    """Ein Fall, der eine Operation erwartet, die niemand deklariert hat,
    ginge aus Versehen durch.
    """
    known = {spec.name for spec in REGISTRY.all()}

    for case in CASES:
        for name in case.expects_ops:
            assert name in known, f"{case.id} expects {name}"


def test_every_expected_operation_is_offered_as_a_tool() -> None:
    offered = set(tools.names())

    for case in CASES:
        for name in case.expects_ops:
            assert name in offered, f"{case.id}: {name} is not a tool"


# --- Was die Mechanik garantiert --------------------------------------------------


@pytest.mark.parametrize("case", CASES, ids=[case.id for case in CASES])
def test_every_request_reaches_the_model_with_its_context(
    case: Case, project: Project, profile: Profile
) -> None:
    """§26.1: Steckbrief, Prüfbericht, Regeln — und die Auswahl, wo es eine
    gibt.
    """
    agent, _proposal = run(case, project, profile)
    backend = agent.backend
    assert isinstance(backend, ScriptedBackend)

    first = backend.seen[0]
    system = " ".join(entry.content for entry in first if entry.role == "system")
    world = first[1].content

    assert "Solidon" in system
    assert "Mindestwandstärke" in system, "the rule set travels along (§39)"
    assert "obj_1" in world
    assert first[-1].content == case.request
    if case.selection is not None:
        assert case.selection[1] in world


@pytest.mark.parametrize("case", CASES, ids=[case.id for case in CASES])
def test_a_good_answer_becomes_one_transaction(
    case: Case, project: Project, profile: Profile
) -> None:
    """AGENTS.md Regel 16: ein Vorschlag, eine Transaktion, ein Undo.

    „Vollständig zurück" heißt: auch die Parameter und Passungen. Solange das
    hier nur Transaktionen zählte, ging ein Vorschlag, der einen Parameter
    anlegte, ohne Transaktion durch — und war damit gar nicht zurückzunehmen.
    """
    _agent, proposal = run(case, project, profile)
    history = History(project.document)
    before = len(project.document.transactions)
    parameters_before = dict(project.document.parameters)
    fits_before = list(project.document.fits)

    transaction = agent_apply.accept(proposal, history)  # type: ignore[arg-type]

    changes_something = bool(
        proposal.drafts  # type: ignore[attr-defined]
        or proposal.parameters  # type: ignore[attr-defined]
        or proposal.fits  # type: ignore[attr-defined]
        or proposal.print_target  # type: ignore[attr-defined]
    )
    if changes_something:
        assert transaction is not None
        assert len(project.document.transactions) == before + 1
        history.undo()
        assert len(project.document.transactions) == before
        assert project.document.parameters == parameters_before
        assert project.document.fits == fits_before
    else:
        assert transaction is None


@pytest.mark.parametrize("case", AMBIGUOUS, ids=[case.id for case in AMBIGUOUS])
def test_an_ambiguous_request_can_ask_and_the_question_arrives(
    case: Case, project: Project, profile: Profile
) -> None:
    """§26.2: die Frage muss die Oberfläche erreichen, nicht im Modell
    bleiben.
    """
    _agent, proposal = run(case, project, profile)

    assert proposal.asked, f"{case.id} is ambiguous and the harness has to carry the question"
    assert proposal.questions[0].answer, "the answer travels back"  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    "case", [entry for entry in CASES if entry.expects_ops], ids=lambda case: case.id
)
def test_the_expected_operations_end_up_in_the_proposal(
    case: Case, project: Project, profile: Profile
) -> None:
    _agent, proposal = run(case, project, profile)

    assert [draft.op for draft in proposal.drafts] == list(case.expects_ops)  # type: ignore[attr-defined]


def test_a_parameter_case_produces_a_parameter(project: Project, profile: Profile) -> None:
    """§39: Hauptmaße werden Parameter, und die Suite misst es."""
    case = next(entry for entry in CASES if entry.expects_parameter)
    _agent, proposal = run(case, project, profile)

    assert proposal.parameters  # type: ignore[attr-defined]


def test_a_question_about_the_model_changes_nothing(project: Project, profile: Profile) -> None:
    case = next(entry for entry in CASES if entry.expects_answer_only)
    _agent, proposal = run(case, project, profile)

    assert proposal.empty  # type: ignore[attr-defined]
    assert proposal.answer  # type: ignore[attr-defined]


def test_an_invalid_operation_never_reaches_the_geometry(
    project: Project, profile: Profile
) -> None:
    """§40 für P4: schemagültig, bevor irgendetwas gerechnet wird."""
    agent = AgentSession(
        backend=ScriptedBackend(
            answers=[
                Reply(
                    tool_calls=(
                        ToolCall(
                            id="1",
                            name="rotate_object",
                            arguments={"objects": ["obj_1"], "axis": "q", "angle": 90.0},
                        ),
                    )
                ),
                Reply(text="Ich korrigiere."),
            ]
        ),
        document=project.document,
        profile=profile,
        sources=ProjectSources(project),
    )

    proposal = agent.propose("Dreh um die Q-Achse")

    assert proposal.drafts == []
    assert len(project.document.ops) == 1, "only the load operation, nothing added"


def test_invalid_calls_are_counted(project: Project, profile: Profile) -> None:
    """§40: „Anteil der Operationen, die im ersten Versuch schemagültig waren"
    ist eine der drei Kennzahlen des Modelllaufs — und sie war nie messbar:
    ``TARGET_VALID`` stand deklariert in ``tools/run_agent_suite.py``, aber
    kein Zähler füllte sie. Der Vorschlag zählt jetzt beides: alle
    Werkzeugaufrufe und die, die die Mechanik ablehnen musste, bevor
    gerechnet wurde.
    """
    agent = AgentSession(
        backend=ScriptedBackend(
            answers=[
                Reply(
                    tool_calls=(
                        # Schemaungültig: die Achse q gibt es nicht.
                        ToolCall(
                            id="1",
                            name="rotate_object",
                            arguments={"objects": ["obj_1"], "axis": "q", "angle": 90.0},
                        ),
                        # Unbekanntes Werkzeug: auch das ist ein ungültiger Aufruf.
                        ToolCall(id="2", name="explode_object", arguments={}),
                    )
                ),
                Reply(
                    tool_calls=(
                        # Der korrigierte Aufruf ist gültig und zählt nicht.
                        ToolCall(
                            id="3",
                            name="rotate_object",
                            arguments={"objects": ["obj_1"], "axis": "z", "angle": 90.0},
                        ),
                    )
                ),
                Reply(text="Korrigiert und gedreht."),
            ]
        ),
        document=project.document,
        profile=profile,
        sources=ProjectSources(project),
    )

    proposal = agent.propose("Dreh das Teil")

    assert proposal.tool_calls == 3
    assert proposal.invalid_calls == 2
    assert [draft.op for draft in proposal.drafts] == ["rotate_object"]


def test_a_refusal_tells_the_model_the_numbers(project: Project, profile: Profile) -> None:
    """Die Fehlertexte des Kerns tragen keine Platzhalter (§33.1).

    „Der Wert liegt über dem zulässigen Höchstwert" ist der ganze Satz; was er
    meint, steht daneben in ``values``. Die Oberfläche setzt beides zusammen,
    die Antwort ans Modell tat es nicht — und damit war der Fehlgriff
    unkorrigierbar: dieselbe Operation kam mit demselben Wert zurück.

    Gemessen an einem echten Lauf, nachdem die Zahlen mitreisen: das Modell
    setzte die Breite auf genau den genannten Mindestwert und schrieb dazu,
    es habe sie „aufgrund der Systemgrenzen" gewählt.
    """
    agent = AgentSession(
        backend=ScriptedBackend(
            answers=[
                Reply(
                    tool_calls=(
                        ToolCall(
                            id="1",
                            name="scale_object",
                            arguments={"objects": ["obj_1"], "factor": 5000.0},
                        ),
                    )
                ),
                Reply(text="Zu groß."),
            ]
        ),
        document=project.document,
        profile=profile,
        sources=ProjectSources(project),
    )

    agent.propose("Mach es fünftausendmal so groß")

    backend = agent.backend
    assert isinstance(backend, ScriptedBackend)
    answer = next(entry for entry in backend.seen[-1] if entry.role == "tool")
    # Die Grenze gehört in die Antwort — den eigenen Wert kennt das Modell,
    # es hat ihn geschickt.
    assert "1000" in answer.content, "die Grenze selbst fehlte, und ohne sie rät der nächste Zug"


def _drill() -> ToolCall:
    return ToolCall(
        id="1",
        name="drill_hole",
        arguments={
            "objects": ["obj_1"],
            "diameter": 6.0,
            "x": 10.0,
            "y": 10.0,
            "z": 4.0,
            "axis": "z",
        },
    )


def test_an_operation_names_the_features_it_created(project: Project, profile: Profile) -> None:
    """Konzept Agent-Vertiefung 3.1: nach ``drill_hole`` muss das Modell die
    ID der neuen Bohrung kennen — sie steht im Werkzeugergebnis, nicht erst
    im nächsten Steckbrief.
    """
    agent = AgentSession(
        backend=ScriptedBackend(answers=[Reply(tool_calls=(_drill(),)), Reply(text="Gebohrt.")]),
        document=project.document,
        profile=profile,
        sources=ProjectSources(project),
    )

    agent.propose("Bohr ein 6er Loch bei 10, 10")

    backend = agent.backend
    assert isinstance(backend, ScriptedBackend)
    answer = next(entry for entry in backend.seen[-1] if entry.role == "tool")
    assert "Neues Merkmal" in answer.content
    assert "hole_" in answer.content and "Ø 6" in answer.content


def test_read_digest_shows_the_state_mid_turn(project: Project, profile: Profile) -> None:
    """Konzept Agent-Vertiefung 3.1: der Steckbrief der Arbeitskopie, nicht
    des Nutzerdokuments — mit dem, was dieser Zug schon getan hat.
    """
    agent = AgentSession(
        backend=ScriptedBackend(
            answers=[
                Reply(tool_calls=(_drill(),)),
                Reply(tool_calls=(ToolCall(id="2", name="read_digest", arguments={}),)),
                Reply(text="Fertig."),
            ]
        ),
        document=project.document,
        profile=profile,
        sources=ProjectSources(project),
    )

    agent.propose("Bohr und sieh nach")

    backend = agent.backend
    assert isinstance(backend, ScriptedBackend)
    drilled = next(entry for entry in backend.seen[1] if entry.role == "tool")
    fresh_hole = next(
        word for word in drilled.content.replace(",", " ").split() if word.startswith("hole_")
    )
    summary = [entry for entry in backend.seen[-1] if entry.role == "tool"][-1]
    assert "Szene" in summary.content
    assert fresh_hole in summary.content, "die neue Bohrung steht im nachgelesenen Steckbrief"


def test_read_standard_answers_from_the_table(project: Project, profile: Profile) -> None:
    """Konzept Agent-Vertiefung 3.4: „welches Kernloch für M4?" ist eine
    Frage an die Tabelle (§24.2), nicht ans Gedächtnis des Modells.
    """
    from app.core.agent.session import standard_text
    from app.core.knowledge import standards

    text = standard_text("screw", "M4")

    wanted = standards.screw("M4")
    assert "M4" in text
    assert f"clearance={wanted.clearance:g} mm" in text
    assert f"tap={wanted.tap:g} mm" in text

    unknown = standard_text("screw", "M99")
    assert "M99" in unknown
    assert "M4" in unknown, "eine unbekannte Größe nennt die bekannten"


def test_read_standard_accepts_the_visible_spelling_of_a_board() -> None:
    """Der Agent darf SKADIS schreiben, obwohl der interne Schlüssel klein ist."""
    from app.core.agent.session import standard_text

    text = standard_text("board", "SKADIS")

    assert "board skadis" in text
    assert "slot_width=" in text


def test_an_unknown_standard_table_counts_as_invalid(project: Project, profile: Profile) -> None:
    """Die Tabelle steht als Enum im Schema — sie zu erfinden ist ein
    Schemaverstoß und zählt für die Kennzahl aus §40.
    """
    agent = AgentSession(
        backend=ScriptedBackend(
            answers=[
                Reply(
                    tool_calls=(
                        ToolCall(
                            id="1",
                            name="read_standard",
                            arguments={"kind": "bolt", "size": "M4"},
                        ),
                    )
                ),
                Reply(text="Verstanden."),
            ]
        ),
        document=project.document,
        profile=profile,
        sources=ProjectSources(project),
    )

    proposal = agent.propose("Was braucht eine M4?")

    assert proposal.invalid_calls == 1


def test_the_turn_reports_its_progress(project: Project, profile: Profile) -> None:
    """Konzept Agent-Vertiefung 4.1: ein Zug dauert zehn bis sechzig Sekunden,
    und „Der Agent denkt nach." war die ganze Auskunft. Die Sitzung meldet
    jetzt je Schritt, was läuft — über einen Rückruf, wie ``ask``, damit der
    Kern nichts vom Fenster weiß.
    """
    seen: list[tuple[int, str]] = []

    agent = AgentSession(
        backend=ScriptedBackend(answers=[Reply(tool_calls=(_drill(),)), Reply(text="Gebohrt.")]),
        document=project.document,
        profile=profile,
        sources=ProjectSources(project),
        progress=lambda step, label: seen.append((step, label)),
    )

    agent.propose("Bohr ein Loch")

    labels = [label for _step, label in seen]
    assert any("Modell" in label for label in labels), "der Modellaufruf meldet sich"
    assert any("Bohrung setzen" in label for label in labels), (
        "das laufende Werkzeug meldet sich mit seinem Titel, nicht seinem Namen"
    )
    assert seen[0][0] == 1, "die Schrittzählung beginnt bei eins"


def test_tool_descriptions_carry_the_menu_place() -> None:
    """§2.6: der Chat ist auch ein Suchfeld. Der Menüort steht in der
    Werkzeugbeschreibung — das Modell hat sonst keine Quelle, um zu sagen,
    wo eine Funktion im Fenster liegt.

    Der Fehler, den dieser Test bewacht, ist eine **abgeschnittene** Angabe:
    Nur Gruppe und Titel zu nennen schickte den Nutzer für 72 von 77 Ops an den
    falschen Ort, weil die Leiste eine Zwischenebene einzieht, die niemand
    erwähnte.

    **Als Liste von vier Zeichenketten hat er das nicht geleistet.** Er stand
    auf HEAD rot, gemessen am 28.08.2026 im eigenen Arbeitsbaum auf 635d1df5,
    und zwar seit Commit 87b00475: Zwei der vier Wege sind kürzer geworden, weil
    die Leiste seither nur noch faltet, was sie falten muss (*Erzeugen* ist
    flach, *Bohrungen* steht direkt in *Ändern*). Ein festgeschriebener Weg ist
    nicht falsch — er dokumentiert einen Stand —, aber er veraltet **still**,
    wenn ihn niemand fährt.

    Deshalb steht die eigentliche Zusage jetzt als Rechnung darunter: Beide
    Tiefen müssen vorkommen. Eine Umsetzung, die grundsätzlich abschneidet,
    lässt die dreistufigen verschwinden; eine, die grundsätzlich eine Ebene
    erfindet, die zweistufigen. Die vier Zeichenketten bleiben als Beispiel und
    als Anlass, hinzusehen, wenn sich ein Weg ändert.
    """
    described = {schema["name"]: schema["description"] for schema in tools.operation_tools()}

    # **Das Paar aus einem Menü ist der Wächter.** Beide liegen in *Ändern*:
    # *Vereinigen* steht direkt darin, *Formgebung* faltet. Eine Umsetzung, die
    # grundsätzlich abschneidet, bricht die zweite; eine, die grundsätzlich eine
    # Ebene erfindet, die erste. Zusammen kann keine Pauschalregel sie erfüllen.
    #
    # **Hier stand ``drill_hole``, und das Paar hat sich selbst aufgelöst.** Mit
    # den vier Merkmalsoperationen (versetzen, drehen, ändern, entfernen) wuchs
    # die Gruppe *Merkmale* von zwei Einträgen auf neun; *Ändern* hätte damit
    # sechzehn Zeilen gehabt und faltet sie stattdessen. Der Weg zur Bohrung ist
    # seither dreistufig — richtig gerechnet, aber als Wächter taugte er nicht
    # mehr, weil beide Hälften des Paares dieselbe Tiefe hatten. Die Booleschen
    # sind zu dritt und wachsen nicht; sie bleiben direkt im Menü.
    assert "Menü: Ändern → Vereinigen." in described["union_objects"]
    assert "Menü: Ändern → Formgebung → Fase anbringen." in described["chamfer_edges"]
    assert "Menü: Ändern → Merkmale → Bohrung setzen." in described["drill_hole"]
    assert "Menü: Erzeugen → Quader anlegen." in described["create_box"]
    assert "Menü: Objekt → Objekt umbenennen." in described["rename_object"]

    # **Ein Baustein der Bibliothek nennt den Katalog, und er nennt ihn als
    # das, was er ist.** Hier stand „Menü: Bausteine → Verbindungen →
    # Schraubenloch" — ein Menü, das es seit dem 29.08.2026 für die Bausteine
    # nicht mehr gibt. Der erste Ersatz schrieb die Pfeilkette einfach weiter
    # („Datei → Bausteinkatalog → Verbindungen → Schraubenloch"), und das war
    # schlechter als der veraltete Weg: Die letzten beiden Glieder sind Gruppe
    # und Kachel **im Katalogfenster**, und wer im Datei-Menü ein Untermenü
    # *Verbindungen* sucht, findet keines. Ein Pfeil zwischen zwei Menüs heißt
    # „dann dort weiter"; zwischen Menü und Dialog heißt er nichts.
    assert (
        "Menü: Datei → Bausteinkatalog …, dort unter Verbindungen: Schraubenloch mit Senkung."
        in described["insert_screw_hole"]
    )
    # **Und die Gegenprobe dazu: nicht jede Operation der Kategorie ``parts``
    # ist ein Katalogeintrag.** ``create_lid`` und ``screw_lid`` bauen einen
    # Deckel, statt einen fertigen einzusetzen — der Katalog zeigt
    # ``PARTS.all()``, und darin stehen sie nicht. Als die Regel noch an der
    # Kategorie hing, verschwanden beide aus der Menüleiste (gemessen: 114
    # Einträge, kein *Deckel erzeugen* darunter) und wurden trotzdem in den
    # Katalog verwiesen. Beide Sätze zusammen sind der Wächter: Wer eine
    # Kachel hat, nennt den Katalog; wer keine hat, nennt sein Menü.
    assert "Menü: Bausteine → Deckel erzeugen." in described["create_lid"]

    places = [
        match.group(1)
        for match in (re.search(r"Menü: (.+?)\.?$", text) for text in described.values())
        if match
    ]
    assert len(places) >= 60, (
        f"nur {len(places)} von {len(described)} Werkzeugen nennen einen Menüort — "
        "dann prüft dieser Test seine eigene Suche und nicht die Beschreibungen"
    )
    levels = {place.count("→") + 1 for place in places}
    assert levels <= {2, 3}, f"unerwartete Menütiefen: {sorted(levels)}"
    assert {2, 3} <= levels, (
        f"nur Wege mit {sorted(levels)} Ebenen — beide Tiefen müssen vorkommen, sonst "
        "entscheidet eine Pauschale statt der Menürechnung"
    )


def test_the_prompt_makes_the_chat_a_search_box() -> None:
    """§2.6, eingelöst in Prompt-Version 3: eine Wie-Frage bekommt neben dem
    Vorschlag den Menüort. Die Version steigt mit dem Text (§26.4).

    **Geprüft wird die Zusage, nicht der Stand.** Hier stand
    ``PROMPT_VERSION == "3"``, und damit sicherte der Test zu, dass der Prompt
    sich nie wieder ändert — Version 4 (der OpenSCAD-Ausbau) machte ihn rot,
    obwohl an §2.6 keine Silbe anders war. Ein Test, der eine Verbesserung
    blockiert, prüft die Gewohnheit und nicht die Zusage. Die Zusage lautet:
    seit Version 3 nennt der Prompt den Menüort, also ab drei aufwärts.
    """
    from app.core.agent.prompt import PROMPT_VERSION, system_prompt

    text = system_prompt()

    assert "Suchfeld" in text
    assert "Menü" in text
    assert int(PROMPT_VERSION) >= 3


def test_views_reach_only_a_backend_that_can_see(project: Project, profile: Profile) -> None:
    """§23 mit Leitprinzip 8: die Ansichten erreichen ein bildfähiges Backend
    neben dem Steckbrief — und entfallen sonst ersatzlos, der Text trägt
    allein.
    """
    png = (("Ansicht von oben", b"\x89PNG\r\n\x1a\nfake"),)

    seeing = ScriptedBackend(answers=[Reply(text="Gesehen.")], images_supported=True)
    AgentSession(
        backend=seeing,
        document=project.document,
        profile=profile,
        sources=ProjectSources(project),
        views=png,
    ).propose("Was siehst du?")
    world = seeing.seen[0][1]
    assert world.images == png, "die Ansichten hängen an der Weltbild-Nachricht"

    blind = ScriptedBackend(answers=[Reply(text="Gelesen.")])
    AgentSession(
        backend=blind,
        document=project.document,
        profile=profile,
        sources=ProjectSources(project),
        views=png,
    ).propose("Was liest du?")
    assert blind.seen[0][1].images == (), "ohne Bildfähigkeit reist kein Bild"


def test_a_lookup_case_reads_instead_of_guessing(project: Project, profile: Profile) -> None:
    """Konzept Agent-Vertiefung 3.3: „Ist das druckbar?" wird nachgesehen,
    nicht gefühlt — der Vorschlag hält fest, welche lesenden Werkzeuge der
    Zug benutzt hat, und die Suite misst daran.
    """
    from tests.agent_cases import by_id

    _agent, proposal = run(by_id("printable"), project, profile)

    assert "read_analysis" in proposal.readings  # type: ignore[attr-defined]
    assert proposal.empty, "nachsehen ändert nichts"  # type: ignore[attr-defined]


def test_a_print_target_refuses_to_mix_with_an_undo(project: Project, profile: Profile) -> None:
    """Regel 16, beide Richtungen derselben Schranke: auch ein gewechseltes
    Druckziel sperrt das Zurücknehmen im selben Vorschlag. Die Schranke
    kannte das Druckziel nicht — der Zug baute einen Vorschlag, den die
    Annahme nur noch mit einer Ausnahme quittieren konnte.
    """
    known = project.document.transactions[0].id
    agent = AgentSession(
        backend=ScriptedBackend(
            answers=[
                Reply(
                    tool_calls=(
                        ToolCall(id="1", name="set_print_target", arguments={"material": "pla"}),
                        ToolCall(id="2", name="undo_transaction", arguments={"transaction": known}),
                    )
                ),
                Reply(text="Verstanden, zwei Vorschläge."),
            ]
        ),
        document=project.document,
        profile=profile,
        sources=ProjectSources(project),
    )

    proposal = agent.propose("Wechsle auf PLA und nimm das Laden zurück")

    assert proposal.undo_of is None, "die Mischung wird abgelehnt, nicht gebaut"
    assert proposal.invalid_calls == 1
    assert agent_apply.accept(proposal, History(project.document)) is not None


def test_an_unknown_object_id_is_an_answer_and_counts(project: Project, profile: Profile) -> None:
    """„obj_9" war nicht von „Objekt ist weg" zu unterscheiden: der
    Steckbrief kam schlicht leer zurück. Jetzt nennt die Antwort die
    falschen IDs samt den vorhandenen, und der Aufruf zählt als ungültig —
    gelesen hat er nichts.
    """
    agent = AgentSession(
        backend=ScriptedBackend(
            answers=[
                Reply(
                    tool_calls=(
                        ToolCall(id="1", name="read_digest", arguments={"objects": ["obj_9"]}),
                    )
                ),
                Reply(text="Dann eben nicht."),
            ]
        ),
        document=project.document,
        profile=profile,
        sources=ProjectSources(project),
    )

    proposal = agent.propose("Zeig mir obj_9")

    assert proposal.invalid_calls == 1
    assert proposal.readings == [], "ein abgelehnter Aufruf hat nichts gelesen"
    backend = agent.backend
    assert isinstance(backend, ScriptedBackend)
    answer = next(entry for entry in backend.seen[-1] if entry.role == "tool")
    assert "obj_9" in answer.content and "obj_1" in answer.content


def test_a_print_target_travels_in_the_transaction_and_back(
    project: Project, profile: Profile
) -> None:
    """Konzept Agent-Vertiefung 5.2: Drucker und Material reisen als
    ``DocumentChange`` in der einen Transaktion des Vorschlags — ein Undo
    stellt beide wieder her (Regel 16, Regel 7 bleibt gewahrt: die
    Toleranzen sind Verweise und rechnen sich mit um).
    """
    from tests.agent_cases import by_id

    material_before = project.document.material
    _agent, proposal = run(by_id("switch_material"), project, profile)

    assert proposal.print_target == (project.document.printer, "pla")  # type: ignore[attr-defined]

    history = History(project.document)
    transaction = agent_apply.accept(proposal, history)  # type: ignore[arg-type]
    assert transaction is not None
    assert project.document.material == "pla"

    history.undo()
    assert project.document.material == material_before


def test_an_invented_object_is_an_invalid_call(project: Project, profile: Profile) -> None:
    """Ein Objekt, das es nicht gibt, hat das Modell erfunden — das zählt.

    Hier stand die umgekehrte Erwartung, unter dem Namen „geometry refusal".
    Die Absicht war richtig und ist es geblieben (siehe den Test darunter):
    ein Aufruf, der an der *Geometrie* scheitert, darf die Quote nicht
    belasten. Nur ist `obj_99` keine Eigenschaft des Netzes, sondern ein
    Fehlgriff des Aufrufers — und weil beide denselben Pfad nahmen, zählte
    gar keiner.

    Was das kostete, zeigte `pocket_plate`: `sketch_pocket` ohne das
    Pflichtfeld ``objects`` lief hier hindurch, und der Läufer meldete „0
    ungültig" zu einem Zug, in dem nichts angewandt wurde.
    """
    agent = AgentSession(
        backend=ScriptedBackend(
            answers=[
                Reply(
                    tool_calls=(
                        # Gültig nach Schema, aber das Objekt gibt es nicht —
                        # das lehnt die Anwendung ab, nicht die Schemaprüfung.
                        ToolCall(
                            id="1",
                            name="rotate_object",
                            arguments={"objects": ["obj_99"], "axis": "z", "angle": 90.0},
                        ),
                    )
                ),
                Reply(text="Das Objekt fehlt."),
            ]
        ),
        document=project.document,
        profile=profile,
        sources=ProjectSources(project),
    )

    proposal = agent.propose("Dreh obj_99")

    assert proposal.tool_calls == 1
    assert proposal.invalid_calls == 1
    assert proposal.drafts == []


def test_a_geometry_refusal_is_not_an_invalid_call(
    project: Project, profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die Kennzahl trennt Bedienfehler von Geometrie (§15.2).

    Ein `GeometryError` ist ein Ergebnis der Rechnung, kein Fehlgriff des
    Aufrufers: dass eine Boolesche Operation an einem Netz scheitert, sagt
    nichts über das Modell. Er darf die Quote deshalb nicht belasten, auch
    wenn er denselben Weg nimmt wie eine abgelehnte Eingabe.
    """
    from app.core.errors import GeometryError
    from app.core.scene.history import History as RealHistory

    def refuse(self: RealHistory, title: object, drafts: object = (), **rest: object) -> None:
        raise GeometryError("Die Körper überschneiden sich nicht.")

    monkeypatch.setattr(RealHistory, "apply", refuse)

    agent = AgentSession(
        backend=ScriptedBackend(
            answers=[
                Reply(
                    tool_calls=(
                        ToolCall(
                            id="1",
                            name="rotate_object",
                            arguments={"objects": ["obj_1"], "axis": "z", "angle": 90.0},
                        ),
                    )
                ),
                Reply(text="Das ging nicht."),
            ]
        ),
        document=project.document,
        profile=profile,
        sources=ProjectSources(project),
    )

    proposal = agent.propose("Dreh das Teil")

    assert proposal.tool_calls == 1
    assert proposal.invalid_calls == 0, "die Geometrie hat abgelehnt, nicht das Modell"
    assert proposal.drafts == []


# --- Säule A (§40 für P6) ---------------------------------------------------------


def test_pillar_a_prefers_parts_over_own_geometry() -> None:
    """§35, §40 zu P6: wird ein Baustein benutzt statt eigener Geometrie?

    Gemessen über den Korpus, nicht über eine Antwort: dreizehn der achtzehn
    Anfragen zu Säule A beantwortet ein Baustein aus der Bibliothek. Die fünf
    ohne sind die, für die es keinen gibt: eine reine Parameterfrage und vier
    Formen, die seit P13 die Skizzen-Ops bauen (§30.1)."""
    from tests.agent_cases import CASES_A

    with_part = [case for case in CASES_A if case.expects_part]
    without = [case for case in CASES_A if not case.expects_part]

    assert len(with_part) == 13
    assert {case.id for case in without} == {
        "parameterise",
        "free_shape",
        "hex_base",
        "pocket_plate",
        "handrail_bend",
    }
    for case in with_part:
        assert any(name.startswith("insert_") for name in case.expects_ops), case.id


def test_pillar_a_turns_main_dimensions_into_parameters() -> None:
    """§39, §35: Hauptmaße werden Parameter, und es ist messbar."""
    from tests.agent_cases import CASES_A

    assert [case.id for case in CASES_A if case.expects_parameter] == [
        "bracket",
        "parameterise",
    ]


def test_every_operation_pillar_a_expects_exists() -> None:
    from tests.agent_cases import CASES_A

    known = {spec.name for spec in REGISTRY.all()}
    for case in CASES_A:
        for name in case.expects_ops:
            assert name in known, f"{case.id} expects {name}"


def test_the_sketch_parameter_stays_locked_but_shapes_pass(
    project: Project, profile: Profile
) -> None:
    """§30.1, beide Ebenen: eine rohe Punktliste wird abgelehnt, auch wenn
    das Modell sie rät — und dieselbe Op läuft über die benannten
    Grundformen. Die Sperre stand seit P13 ohne Test; die Behauptung, der
    Weg über die Formen sei ungewinnbar, stand ungeprüft im Konzept. Beides
    hält dieser Test fest.
    """
    guessed = AgentSession(
        backend=ScriptedBackend(
            answers=[
                Reply(
                    tool_calls=(
                        ToolCall(
                            id="1",
                            name="sketch_extrude",
                            arguments={"sketch": '{"plane": "plane:xy"}', "height": 6.0},
                        ),
                    )
                ),
                Reply(text="Ich versuche es anders."),
            ]
        ),
        document=project.document,
        profile=profile,
        sources=ProjectSources(project),
    )
    proposal = guessed.propose("Zeichne mir etwas")
    assert proposal.drafts == [], "eine geratene Punktliste erreicht die Geometrie nie"
    assert proposal.invalid_calls == 1

    shaped = AgentSession(
        backend=ScriptedBackend(
            answers=[
                Reply(
                    tool_calls=(
                        ToolCall(
                            id="1",
                            name="sketch_extrude",
                            arguments={
                                "shape": "rectangle",
                                "length": 60.0,
                                "width": 40.0,
                                "height": 6.0,
                            },
                        ),
                    )
                ),
                Reply(text="Gebaut."),
            ]
        ),
        document=project.document,
        profile=profile,
        sources=ProjectSources(project),
    )
    proposal = shaped.propose("Bau eine Platte 60 auf 40, 6 stark")
    assert [draft.op for draft in proposal.drafts] == ["sketch_extrude"]
    assert proposal.invalid_calls == 0


def test_the_sketch_cases_are_structurally_winnable() -> None:
    """Die vier Skizzenfälle der Säule A galten als ungewinnbar — zu Unrecht:
    jede erwartete Op bietet dem Agenten die Grundform-Parameter an, und nur
    die rohe Skizze bleibt draußen (§30.1, Leitprinzip 5).
    """
    from tests.agent_cases import by_id

    offered = {schema["name"]: schema for schema in tools.operation_tools()}
    for case_id in ("free_shape", "hex_base", "pocket_plate", "handrail_bend"):
        for name in by_id(case_id).expects_ops:
            fields = offered[name]["input_schema"]["properties"]
            assert "shape" in fields, f"{name} bietet die Grundformen an"
            assert "sketch" not in fields, f"{name} bietet keine rohe Skizze an"


def test_the_free_shape_no_longer_needs_the_fallback() -> None:
    """Der Trichter war der Vorzeigefall des OpenSCAD-Rückfalls (§24.1).

    Seit P13 spannt ``sketch_loft`` ihn im Haus auf (§30.1) — die gute Antwort
    benutzt die eigene Operation. Genau diese Umkehr hält der Fall fest.

    **Und seit dem 26.08.2026 braucht er kein Verbot mehr dafür.** Hier stand
    ``case.forbids_ops == ("create_from_scad",)``; mit dem OpenSCAD-Ausbau ist
    die Operation aus dem Register gefallen, und ein Verbot auf einen Namen,
    den das Register nicht kennt, kann nie greifen — der Bewerter prüft
    ``set(forbids_ops) & set(operations)``, und das bleibt leer, gleich was das
    Modell tut. Es hätte den Fall also **leichter** gemacht statt schärfer.

    Der Test sichert deshalb beides zu: kein Verbot mehr, und der Grund dafür
    ist wirklich der Bestand des Registers und nicht ein vergessener Eintrag.
    """
    from app.core.bootstrap import load_operations
    from app.core.registry import REGISTRY
    from tests.agent_cases import by_id

    load_operations()
    case = by_id("free_shape")

    assert case.expects_ops == ("sketch_loft",)
    assert not case.forbids_ops
    assert not REGISTRY.has("create_from_scad"), (
        "das Verbot ist entfallen, weil es die Operation nicht mehr gibt — "
        "gäbe es sie wieder, gehörte es zurück"
    )
    assert not case.expects_part


def test_the_scene_stays_evaluable_after_every_case(project: Project, profile: Profile) -> None:
    """Ein Vorschlag, der sich nicht rechnen lässt, ist schlechter als keiner —
    also lassen sich alle rechnen.
    """
    for case in CASES:
        made = new_project("centauri-carbon-2", "petg")
        made.document.sources["src_1"] = project.document.sources["src_1"]
        made.sources["src_1"] = project.sources["src_1"]
        History(made.document).apply(
            "Laden", [OperationDraft(op="load", params={"source": "src_1", "unit": "mm"})]
        )
        _agent, proposal = run(case, made, profile)
        agent_apply.accept(proposal, History(made.document))  # type: ignore[arg-type]

        result = evaluate(made.document, profile, sources=ProjectSources(made))
        assert result.complete, f"{case.id} left the stack in a state that stops"
