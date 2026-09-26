"""Das Werkzeugangebot eines lokalen Modells (``agent/offer.py``, RM-185).

Ein lokales Modell bekommt jede Operation als Werkzeug — aber nur die
gemeinten mit allen Feldern. Geprüft wird hier, was davon eine Zusage ist:
dass keine Operation verschwindet, dass eine Kurzform nichts ausführt und
sich in einem Schritt holen lässt, dass die Anfrage, die gewählte Stelle und
die leere Szene die richtigen Werkzeuge ausführlich machen, und dass das
Angebot den Platz tatsächlich spart, für den es gebaut ist.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

import pytest

from app.core.agent.offer import DETAILED_LIMIT, STUB_MARK, ToolOffer
from app.core.agent.prompt import system_prompt
from app.core.agent.session import AgentSession
from app.core.agent.tools import operation_tools, tool_schemas
from app.core.backends.llm import Message, Reply, ToolCall
from app.core.bootstrap import load_operations
from app.core.registry import REGISTRY, menu_twins
from app.core.registry.search import rank_operations, request_terms
from app.core.scene.project import Project, ProjectSources
from app.core.types import Profile
from tests.helpers import plate_project


@pytest.fixture(autouse=True)
def _registry() -> None:
    load_operations()


def _rendered_length(schemas: Sequence[dict[str, Any]]) -> int:
    """So lang, wie Ollama die Werkzeuge ins Fenster legt — ohne Maskierung."""
    return len(json.dumps(list(schemas), ensure_ascii=False))


# --- was nie verschwindet -------------------------------------------------------------


def test_every_operation_stays_a_tool_in_the_order_of_the_register() -> None:
    """Die Kurzform ist keine Auswahl: dieselben Werkzeuge in derselben
    Reihenfolge wie ``tool_schemas`` (§26.1), nur weniger ausführlich."""
    offered = [entry["name"] for entry in ToolOffer.for_turn(REGISTRY, ["Hallo."]).schemas()]
    assert offered == [entry["name"] for entry in tool_schemas(compact=True)]
    assert len(offered) > 100, "ohne geladenes Register prüft der Vergleich nichts"


def test_a_stub_has_no_fields_and_ends_with_the_mark_the_prompt_explains() -> None:
    offer = ToolOffer.for_turn(REGISTRY, ["Hallo."])
    stubs = [entry for entry in offer.schemas() if offer.is_stub(str(entry["name"]))]
    assert stubs, "zu einer Frage ohne Operation steht jede Operation in Kurzform"
    for entry in stubs:
        assert entry["input_schema"] == {"type": "object", "properties": {}}
        assert str(entry["description"]).endswith(STUB_MARK)
    compact, full = system_prompt(compact=True), system_prompt(compact=False)
    assert f"„{STUB_MARK}“" in compact, "der Prompt sagt, was das Zeichen heißt"
    assert "angekündigt" in compact
    assert "angekündigt" not in full, "ein gehostetes Modell bekommt keine Kurzform"


def test_a_hidden_twin_is_announced_as_the_second_choice() -> None:
    """Zwei Kurzformen „Quader anlegen" wären eine Frage ohne Antwort — die
    versteckte sagt, dass die andere die erste Wahl ist."""
    offer = ToolOffer.for_turn(REGISTRY, ["Hallo."])
    stubs = {str(entry["name"]): str(entry["description"]) for entry in offer.schemas()}
    hidden, shown = next(iter(menu_twins().items()))
    assert stubs[hidden] != stubs[shown]
    assert str(REGISTRY.get(hidden).title) in stubs[hidden]


def test_a_hidden_twin_names_its_first_choice_hosted_and_local() -> None:
    """Der versteckte Zwilling nennt das Werkzeug der ersten Wahl — an beiden Wegen.

    Beide Zwillinge heißen im Menü gleich; „im Menü steht Bohrung setzen" ließ
    offen, welches Werkzeug gemeint war, und qwen3:14b bohrte über den exakten
    Kern. Gehostet stand der Satz bis zum 26.09.2026 im Zweig für fremde
    Rezepte und kam nie an.
    """
    from app.core.agent.tools import second_choice_note

    hidden, shown = next(iter(menu_twins().items()))
    note = second_choice_note(hidden, REGISTRY)
    assert shown in note and str(REGISTRY.get(shown).title) in note
    assert second_choice_note(shown, REGISTRY) == "", "die erste Wahl trägt keinen Satz"

    hosted = {str(entry["name"]): str(entry["description"]) for entry in operation_tools()}
    assert hosted[hidden].endswith(note), "gehostet steht der Satz am versteckten Zwilling"
    assert note not in hosted[shown]

    offer = ToolOffer.for_turn(REGISTRY, ["Hallo."])
    offer.promote([hidden])
    local = {str(entry["name"]): str(entry["description"]) for entry in offer.schemas()}
    assert local[hidden].endswith(note), "lokal ausführlich derselbe Satz"


def test_a_hidden_twin_stays_a_stub_while_its_visible_one_is_meant() -> None:
    """Wer bohren will, bekommt *Bohrung setzen* ausführlich — nicht den Zwilling.

    Standen beide ausführlich da, bohrte qwen3:14b über den exakten Kern, auch
    mit dem Satz, der die erste Wahl nennt. Aufrufbar bleibt der Zwilling: Wer
    ihn anfordert, bekommt ihn.
    """
    hidden = menu_twins()
    offer = ToolOffer.for_turn(
        REGISTRY,
        ["Bohr ein Loch mit 5 mm Durchmesser in die Oberseite, mittig."],
        selected_kind="face",
    )
    assert "drill_hole" in offer.detailed
    assert not offer.detailed & set(hidden), "kein versteckter Zwilling von sich aus ausführlich"
    twin = next(name for name, shown in hidden.items() if shown == "drill_hole")
    assert offer.is_stub(twin)
    offer.introduce(twin)
    assert not offer.is_stub(twin), "angefordert steht er mit Feldern da"


def test_a_detailed_tool_is_the_compact_schema_with_its_place() -> None:
    """Ausführlich heißt: dieselben Felder wie die Kurzfassung für lokale
    Modelle, dazu der Ort im Fenster (§2.6)."""
    offer = ToolOffer.for_turn(REGISTRY, ["Drill a 5 mm hole in the top"])
    assert "drill_hole" in offer.detailed
    sent = next(entry for entry in offer.schemas() if entry["name"] == "drill_hole")
    compact = next(
        entry for entry in operation_tools(compact=True) if entry["name"] == "drill_hole"
    )
    assert sent["input_schema"] == compact["input_schema"]
    assert str(sent["description"]).startswith(str(compact["description"]))
    assert "Ort:" in str(sent["description"])
    assert not str(sent["description"]).endswith(STUB_MARK)


def test_a_detailed_part_keeps_the_fields_of_its_place() -> None:
    """Die zehn Ortsfelder eines Bausteins stehen ausführlich da — ohne Satz.

    Die Kurzfassung für alle 35 Bausteine hatte sie gestrichen (RM-185); ohne
    sie setzte qwen3.5:9b Bausteine ohne Fläche und ohne Position, und die
    Auswertung verwarf sie. Ihre Bedeutung steht im Prompt, deshalb bleiben sie
    ohne eigenen Text.
    """
    from app.core.registry.surfaces import PART_PLACEMENT_PARAMS

    offer = ToolOffer.for_turn(REGISTRY, ["Eine Schlüsselloch-Aufhängung auf der Rückseite."])
    assert "insert_keyhole" in offer.detailed
    sent = next(entry for entry in offer.schemas() if entry["name"] == "insert_keyhole")
    fields = sent["input_schema"]["properties"]
    assert set(PART_PLACEMENT_PARAMS) <= set(fields), "die Stelle steht als Felder da"
    assert not any(fields[name].get("description") for name in ("x", "y", "z", "axis")), (
        "ihr Satz steht einmal im Prompt, nicht an jedem Baustein"
    )
    assert "``at_feature``" in system_prompt(compact=True)


# --- was ausführlich dasteht ----------------------------------------------------------


@pytest.mark.parametrize(
    ("request_text", "wanted"),
    [
        ("Verschieb die Platte 10 mm nach rechts.", "translate_object"),
        ("Skalier das Teil auf 120 Prozent.", "scale_object"),
        ("Eine Schlüsselloch-Aufhängung auf der Rückseite.", "insert_keyhole"),
        ("Drill a 5 mm hole in the top", "drill_hole"),
        ("Rund die Kanten oben ab, 2 mm", "fillet_edges"),
    ],
)
def test_the_request_brings_its_operation_with_its_fields(request_text: str, wanted: str) -> None:
    """Die Wortsuche der Befehlspalette findet die gemeinte Operation — in
    Beugung, als Zusammensetzung und auf Englisch über den Namen."""
    assert wanted in ToolOffer.for_turn(REGISTRY, [request_text]).detailed


def test_a_chosen_hole_brings_the_handlings_its_panel_shows() -> None:
    """„Mach das größer" nennt keinen Titel — an einer gewählten Bohrung
    meint es trotzdem ihre Handlungen."""
    detailed = ToolOffer.for_turn(REGISTRY, ["Mach das größer."], selected_kind="hole").detailed
    assert {"resize_hole", "move_feature", "slot_hole"} <= detailed


def test_an_empty_scene_brings_the_basic_bodies_the_menu_offers() -> None:
    detailed = ToolOffer.for_turn(REGISTRY, ["Hallo."], empty_scene=True).detailed
    shown = set(menu_twins().values())
    bodies = {spec.name for spec in REGISTRY.all() if spec.category == "primitive"}
    assert bodies & shown, "ohne sichtbare Grundkörper prüft der Test nichts"
    assert bodies & shown <= detailed
    assert not detailed & set(menu_twins()), "ein versteckter Zwilling ist keine erste Wahl"


def test_no_request_makes_more_than_the_limit_detailed_by_itself() -> None:
    long_request = " ".join(str(spec.title) for spec in REGISTRY.all())
    assert len(ToolOffer.for_turn(REGISTRY, [long_request]).detailed) <= DETAILED_LIMIT


def test_the_offer_takes_a_fraction_of_the_room_all_tools_took() -> None:
    """Der Grund für das Angebot, als Zahl: Die Kurzfassung aller Werkzeuge
    kostete gemessen 30 461 Token, das Angebot mit vollen zehn ausführlichen
    Werkzeugen soll unter einem Drittel davon bleiben."""
    everything = _rendered_length(tool_schemas(compact=True))
    request = "Bohr ein Loch mit 5 mm Durchmesser in die Oberseite, mittig."
    offer = ToolOffer.for_turn(REGISTRY, [request], selected_kind="face")
    assert len(offer.detailed) == DETAILED_LIMIT
    assert _rendered_length(offer.schemas()) < everything / 3


# --- die Wortsuche --------------------------------------------------------------------


def test_filler_words_decide_nothing() -> None:
    """„das", „auf", „mit" stehen in fast jedem Text und zählen nicht — ohne
    eine Liste von Füllwörtern je Sprache."""
    alone = dict(rank_operations(["Skalieren"], REGISTRY))
    padded = dict(rank_operations(["Skalieren das auf mit die der"], REGISTRY))
    assert alone == padded


def test_the_agent_weighs_its_curated_words_and_not_the_palette_phrases() -> None:
    """Die Kundenwörter der Palette stehen nicht im Angebot des Agenten.

    Gemessen in der Durchsicht 0.5.1 (qwen3:14b, je zweimal): Mit ihnen holte
    „Versteifung" den Eckwinkel neben die Rippe ins ausführliche Angebot, und
    „Versteife die Wand mit einer Rippe" traf 0 von 2 statt 3 von 3 — das
    Modell fragte, statt zu bauen. Die Palette behält sie
    (``rank_entries(customer_words=True)``).
    """
    from app.core.registry.search import rank_entries, registry_fields

    request = "Versteife die Wand mit einer Rippe."
    palette = dict(rank_entries([request], registry_fields(REGISTRY)))
    agent = dict(rank_operations([request], REGISTRY))
    assert palette.get("insert_gusset", 0.0) > agent.get("insert_gusset", 0.0), (
        "die Palette findet den Eckwinkel über „verstärken“, der Agent nicht"
    )
    offer = ToolOffer.for_turn(REGISTRY, [request], empty_scene=True)
    assert "insert_rib" in offer.detailed
    assert "insert_gusset" not in offer.detailed


def test_a_three_letter_word_counts_only_as_a_whole_word() -> None:
    """„pla" meint das Material und nicht „place"."""
    assert "place_on_bed" not in dict(rank_operations(["pla"], REGISTRY))


def test_a_customer_phrase_counts_only_when_all_its_words_are_there() -> None:
    """„leichter machen" meint das Verringern der Dreiecke — „machen" allein
    nicht."""
    assert "decimate_mesh" in dict(rank_operations(["Mach es leichter machen"], REGISTRY))
    assert "decimate_mesh" not in dict(rank_operations(["Mach das Loch größer"], REGISTRY))


def test_request_terms_are_folded_and_counted_once() -> None:
    assert request_terms("Größe größe 12 mm M4 Öse") == ("groesse", "oese")


# --- der Zug ---------------------------------------------------------------------------


@dataclass(slots=True)
class _LocalScripted:
    """Ein lokales Modell aus dem Skript: ``id`` ist ``ollama``, damit die
    Sitzung das Angebot fährt, und es merkt sich die Werkzeuge vollständig."""

    answers: list[Reply]
    tools_seen: list[list[dict[str, Any]]] = field(default_factory=list)
    model: str = "scripted"

    @property
    def id(self) -> str:
        return "ollama"

    @property
    def available(self) -> bool:
        return True

    @property
    def supports_images(self) -> bool:
        return False

    def complete(
        self,
        messages: Sequence[Message],
        tools: Sequence[dict[str, Any]] = (),
        *,
        temperature: float = 0.0,
        max_output_tokens: int | None = None,
    ) -> Reply:
        self.tools_seen.append([dict(entry) for entry in tools])
        if not self.answers:
            return Reply(text="", model=self.model, stop_reason="end_turn")
        return self.answers.pop(0)


def _described(tools: list[dict[str, Any]], name: str) -> bool:
    entry = next(entry for entry in tools if entry["name"] == name)
    return bool(entry["input_schema"].get("properties"))


def _call(name: str, arguments: dict[str, Any], number: int = 1) -> Reply:
    return Reply(tool_calls=(ToolCall(id=f"call_{number}", name=name, arguments=arguments),))


def test_a_stub_call_fetches_the_fields_and_executes_nothing(profile: Profile) -> None:
    project: Project = plate_project()
    backend = _LocalScripted(
        answers=[
            _call("rotate_object", {}),
            _call("rotate_object", {"objects": ["obj_1"], "angle": 90.0}, 2),
            Reply(text="Gedreht."),
        ]
    )
    agent = AgentSession(
        backend=backend,
        document=project.document,
        profile=profile,
        sources=ProjectSources(project),
    )
    proposal = agent.propose("Mach bitte etwas damit.")

    first, second = backend.tools_seen[0], backend.tools_seen[1]
    assert not _described(first, "rotate_object"), "die Anfrage nennt keine Drehung"
    assert _described(second, "rotate_object"), "der Aufruf der Kurzform holt die Felder"
    assert [draft.op for draft in proposal.drafts] == ["rotate_object"], (
        "nur der zweite Aufruf rechnet"
    )
    assert proposal.lookups == 1
    assert proposal.tool_calls == 1, "das Holen der Felder ist kein Werkzeugaufruf"
    assert proposal.invalid_calls == 0


def test_a_found_part_stands_with_its_fields_in_the_next_step(profile: Profile) -> None:
    project: Project = plate_project()
    backend = _LocalScripted(
        answers=[_call("find_part", {"description": "Magnettasche"}), Reply(text="gefunden")]
    )
    agent = AgentSession(
        backend=backend,
        document=project.document,
        profile=profile,
        sources=ProjectSources(project),
    )
    agent.propose("Hallo.")

    assert not _described(backend.tools_seen[0], "insert_magnet_pocket")
    assert _described(backend.tools_seen[1], "insert_magnet_pocket")


def test_a_hosted_model_still_sees_every_tool_in_full(profile: Profile) -> None:
    """Das Angebot gilt dem lokalen Weg; ein gehostetes Modell hat Platz."""
    from tests.scripted_backend import ScriptedBackend

    project: Project = plate_project()
    agent = AgentSession(
        backend=ScriptedBackend(answers=[Reply(text="ok")]),
        document=project.document,
        profile=profile,
        sources=ProjectSources(project),
    )
    agent.propose("Hallo.")
    assert agent.offer is None
