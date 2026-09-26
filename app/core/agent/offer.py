"""Das Werkzeugangebot eines lokalen Modells (§26.2, RM-185).

Ein gehostetes Modell bekommt jede Operation mit allen Feldern: Es hat Platz,
und sein Anbieter hält den gleichbleibenden Anfang der Anfrage vor. Ein
lokales Modell bezahlt jedes Feld mit Kontextfenster, Grafikspeicher und
Wartezeit. Gemessen am 25.09.2026 mit qwen3:14b: 153 Werkzeuge in Kurzfassung
kosteten 30 461 von 32 768 Token — für Steckbrief, Verlauf und Antwort blieben
rund 2 300.

**Jede Operation bleibt ein Werkzeug, das sich aufrufen lässt.** Was sich
ändert, ist nur, wie ausführlich sie dasteht:

* **Mit allen Feldern** stehen die Operationen, die die Anfrage meint
  (``registry.search.rank_operations``, dieselbe Wortsuche wie die
  Befehlspalette), die zur gewählten Stelle passen, und alles, was das Modell
  in diesem Zug schon angefordert oder über ``find_part`` gefunden hat.
* **In Kurzform** — Name und Titel, keine Felder — stehen alle übrigen. Ruft
  das Modell eine davon auf, wird nichts ausgeführt: Die Antwort sagt, dass
  sie jetzt mit ihren Feldern dasteht, und der nächste Schritt trägt sie so.

Das ist keine Auswahl, die Operationen aussortiert — das wäre eine
Betriebsart mit anderem Namen (§2.6), und der Agent käme an sie nicht mehr
heran, ohne dass ihm jemand sagt, dass es sie gibt. Hier sagt es ihm jeder
Zug: Die Kurzform nennt jede Operation beim Namen, und ihr Aufruf ist der Weg
zu den Feldern. Die Reihenfolge ist die des Registers (§26.1), damit ein
unveränderter Anfang der Anfrage unverändert bleibt.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any, Final

from app.core.agent.tools import (
    extra_tools,
    framed_if_foreign,
    operation_tools,
    second_choice_note,
)
from app.core.registry import Registry, menu_path, menu_twins
from app.core.registry.search import rank_operations
from app.i18n import tr

#: Wie viele Operationen ein Schritt höchstens von sich aus ausführlich zeigt.
#:
#: Dazu kommt, was das Modell im Zug anfordert. Zehn reichen für eine Anfrage
#: mit zwei Absichten („Platte mit zwei Senkbohrungen") und kosten rund 2 000
#: Token; ein Treffer auf Platz elf ist ein Aufruf mehr, keine verlorene
#: Fähigkeit.
DETAILED_LIMIT: Final = 10

#: Unter dieser Wertung ist ein Treffer Zufall: ein häufiges Wort im
#: ``doc``-Satz, das nichts entscheidet. Ein Titeltreffer eines Worts, das in
#: einem Dutzend Operationen steht, liegt bei rund sechs.
MIN_SCORE: Final = 4.0

#: Das Zeichen am Ende einer Kurzform. Eine Operation ohne Felder gibt es
#: auch ausführlich (sie nimmt nur ihre Objekte); woran das Modell die Kurzform
#: erkennt, muss deshalb an der Beschreibung stehen, nicht am Schema.
STUB_MARK: Final = "…"


def _stub(name: str, title: str, *, second_choice: bool) -> dict[str, Any]:
    """Eine Operation in Kurzform: Name, Titel, keine Felder."""
    text = str(tr("{title}, zweite Wahl").format(title=title)) if second_choice else title
    return {
        "name": name,
        "description": f"{text} {STUB_MARK}",
        "input_schema": {"type": "object", "properties": {}},
    }


@dataclass(slots=True)
class ToolOffer:
    """Was das lokale Modell in einem Zug sieht — und was es nachfordern kann."""

    detailed: set[str]
    """Die Operationen, die gerade mit allen Feldern dastehen."""
    _order: tuple[str, ...]
    _full: dict[str, dict[str, Any]]
    _stubs: dict[str, dict[str, Any]]
    _extras: tuple[dict[str, Any], ...]
    requested: list[str] = field(default_factory=list)
    """Welche Kurzformen das Modell in diesem Zug aufgerufen hat — für die
    Messung, nicht für die Entscheidung."""

    @classmethod
    def for_request(
        cls,
        registry: Registry,
        texts: Iterable[str],
        *,
        favoured: Iterable[str] = (),
        pinned: Iterable[str] = (),
    ) -> ToolOffer:
        """Das Angebot für eine Anfrage — ``texts`` ist sie samt den letzten
        Nutzerbeiträgen, ``favoured`` rückt in der Rangfolge nach vorn, was zur
        Lage passt, ``pinned`` steht in jedem Fall ausführlich da."""
        # **Mit den Ortsfeldern der Bausteine** (``part_placement``): Ohne sie
        # setzte qwen3.5:9b am 25.09.2026 in zwölf von dreizehn Bausteinfällen
        # einen Baustein ohne Fläche und ohne Position, und die Auswertung
        # verwarf ihn. Die Kurzfassung hatte sie gestrichen, weil 35 Bausteine
        # sie je Zug 2 905 Token kosteten; ausführlich stehen hier höchstens
        # zehn Werkzeuge da.
        schemas = operation_tools(registry, compact=True, part_placement=True)
        twins = menu_twins()
        full: dict[str, dict[str, Any]] = {}
        stubs: dict[str, dict[str, Any]] = {}
        for schema in schemas:
            name = str(schema["name"])
            spec = registry.get(name)
            # **Der Ort gehört zur ausführlichen Fassung** (§2.6, der Chat ist
            # auch ein Suchfeld). Bis zum 25.09.2026 fehlte er dem lokalen Weg
            # ganz, weil er je Werkzeug zu teuer war; an zehn Werkzeugen kostet
            # er rund 150 Token, und „Wo finde ich das Aushöhlen?" bekommt eine
            # Antwort, die stimmt.
            #
            # **Titel und Menüweg eines fremden Rezepts sind Fremdtext** (§32):
            # Beide enden mit dessen Titel, und ``operation_tools`` rahmt ihn
            # nur in dem, was es selbst schreibt. Was hier dazukommt, rahmt
            # dieselbe Funktion.
            description = (
                f"{schema['description']} {tr('Ort')}: "
                f"{framed_if_foreign(name, menu_path(spec, registry))}."
            )
            # Der versteckte Zwilling ist zweite Wahl — in beiden Fassungen,
            # sonst verlöre er den Satz, sobald er ausführlich wird.
            note = second_choice_note(name, registry)
            if note:
                description += f" {note}"
            full[name] = {**schema, "description": description}
            stubs[name] = _stub(
                name, framed_if_foreign(name, spec.title), second_choice=name in twins
            )
        wanted = set(favoured)
        # **Ein versteckter Zwilling ist nicht gemeint, wenn es sein sichtbarer
        # ist** (P2.8): *Bohrung setzen* fragt die Körperart selbst, der exakte
        # Zwilling bleibt für alte Projekte registriert. Standen beide
        # ausführlich da, bohrte qwen3:14b am 26.09.2026 über ``mesh_to_exact``
        # und ``drill_brep_hole`` — auch mit dem Satz, der die erste Wahl
        # nennt. Er bleibt deshalb Kurzform; wer ihn aufruft, bekommt ihn.
        detailed = {name for name in pinned if name in full and name not in twins}
        for name, score in rank_operations(texts, registry, favoured=wanted):
            if len(detailed) >= DETAILED_LIMIT:
                break
            if name in twins:
                continue
            if score >= MIN_SCORE or name in wanted:
                detailed.add(name)
        return cls(
            detailed=detailed,
            _order=tuple(str(schema["name"]) for schema in schemas),
            _full=full,
            _stubs=stubs,
            _extras=extra_tools(),
        )

    @classmethod
    def for_turn(
        cls,
        registry: Registry,
        texts: Iterable[str],
        *,
        selected_kind: str | None = None,
        empty_scene: bool = False,
    ) -> ToolOffer:
        """Das Angebot für einen Zug — was die Sätze meinen, und was die Lage
        nahelegt.

        Ist ein Merkmal gewählt, rücken die Operationen nach vorn, die es
        annehmen (``applies_to``), und die Handlungen, die das Merkmalfenster
        an ihm als Felder zeigt (``perceive.actions.ACTION_ORDER``), stehen
        in jedem Fall ausführlich da: „Mach das größer" an einer gewählten
        Bohrung meint *Bohrung ändern*, auch wenn kein Wort des Satzes im
        Titel steht. In einer leeren Szene stehen die Grundkörper ausführlich
        da, die das Menü anbietet: Dort gibt es nichts, woran eine andere
        Operation wirken könnte, und ein erster Körper ist fast immer der
        erste Schritt.
        """
        favoured: tuple[str, ...] = ()
        pinned: tuple[str, ...] = ()
        if selected_kind is not None:
            from app.core.perceive.actions import ACTION_ORDER

            favoured = tuple(spec.name for spec in registry.for_feature(selected_kind))
            pinned = tuple(name for row in ACTION_ORDER for name in row if name in favoured)
        elif empty_scene:
            hidden = menu_twins()
            favoured = tuple(
                spec.name
                for spec in registry.all()
                if spec.category == "primitive" and spec.name not in hidden
            )
            pinned = tuple(name for name in favoured if name in set(hidden.values()))
        return cls.for_request(registry, texts, favoured=favoured, pinned=pinned)

    def schemas(self) -> list[dict[str, Any]]:
        """Die Werkzeugliste dieses Schritts: Operationen in Registerreihenfolge,
        dahinter die Zusatzwerkzeuge — dieselbe Ordnung wie ``tool_schemas``."""
        return [
            *(
                self._full[name] if name in self.detailed else self._stubs[name]
                for name in self._order
            ),
            *self._extras,
        ]

    def is_stub(self, name: str) -> bool:
        """Ob diese Operation gerade nur in Kurzform dasteht."""
        return name in self._stubs and name not in self.detailed

    def promote(self, names: Iterable[str]) -> None:
        """Diese Operationen ab dem nächsten Schritt ausführlich zeigen."""
        self.detailed.update(name for name in names if name in self._full)

    def introduce(self, name: str) -> str:
        """Eine aufgerufene Kurzform ausführlich machen — und es dem Modell sagen.

        Die Antwort ist die Werkzeugantwort auf den Aufruf. Sie sagt, dass
        nichts geschehen ist und was jetzt zu tun ist; die Felder selbst stehen
        ab dem nächsten Schritt im Schema und nicht noch einmal hier.
        """
        self.requested.append(name)
        self.promote([name])
        return str(
            tr(
                "Noch nicht ausgeführt: {name} steht jetzt mit seinen Feldern in der "
                "Werkzeugliste. Rufe es mit Werten auf."
            ).format(name=name)
        )
