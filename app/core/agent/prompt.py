"""Der Systemprompt (Bauplan §26.1, §39).

Versioniert, denn jede Transaktion hält fest, welcher Prompt sie erzeugt hat
(§26.4). Text ändern heißt Version erhöhen — sonst behauptet eine
Projektdatei, unter einem Prompt entstanden zu sein, den es nicht mehr gibt.

Die Sätze am Ende sind die, die §26.5 hier verankert und in der Suite gemessen
haben will: Bausteine vor Primitiven, Parameter vor Zahlen, Fragen vor Raten.

**Es waren vier, und die zweite hieß „Op-Liste vor OpenSCAD".** Sie ist am
26.08.2026 mit dem OpenSCAD-Ausbau entfallen — nicht gelockert, sondern
gegenstandslos geworden: Der Quelltextweg, vor dem sie warnte, existiert nicht
mehr. Was sie inhaltlich schützte, sagt Regel 1 ohnehin. Eine Regel, die ein
Modell vor etwas warnt, das es gar nicht tun kann, kostet Platz im Auftrag und
lehrt eine Unterscheidung ohne Gegenstand.
"""

from __future__ import annotations

from app.core.knowledge import rules

#: Wird erhöht, sobald sich der Text darunter ändert (§26.4).
#:
#: Version 2 macht aus „Fragen vor Raten" eine Vorbedingung mit drei Prüfungen.
#: Als Gewohnheit unter vier anderen trug sie nicht: sobald der Systemprompt
#: vollständig ankam (siehe ``OLLAMA_CONTEXT_TOKENS``) und das Modell alle
#: vierundachtzig Werkzeuge sah, fiel die Quote bei mehrdeutigen Anfragen von
#: 3/3 auf 1/3 — wer genug Angebote hat, findet immer eines, das plausibel
#: aussieht. Die 3/3 davor waren kein Gehorsam, sondern Mangel an Alternativen.
#:
#: Version 3 löst §2.6 ein: der Chat ist auch ein Suchfeld. Eine Wie-Frage
#: bekommt neben dem Vorschlag den Menüort der Funktion — der steht seither
#: in jeder Werkzeugbeschreibung, das Modell muss ihn nur nennen.
#:
#: Version 4 streicht „Op-Liste vor OpenSCAD": Der Weg, vor dem sie warnte,
#: ist mit dem OpenSCAD-Ausbau verschwunden (26.08.2026). Aus vier
#: Gewohnheiten werden drei. Die Version steigt, obwohl der Prompt nur
#: *kürzer* wird — eine Transaktion soll auch dann wissen, unter welchem Text
#: sie entstand, wenn der Text etwas weniger sagt als vorher.
PROMPT_VERSION = "4"

_ROLE = """
Du bist der Konstruktionsassistent von Solidon, einer Anwendung für druckbare
3D-Modelle. Du arbeitest mit denselben Operationen, die auch der Nutzer hat:
jede Änderung entsteht als Operation auf dem Stapel, nie als freie Geometrie.

Du bekommst zu jeder Anfrage einen Steckbrief der Szene, den Prüfbericht und
den Verlauf in Kurzform. Objekte und Merkmale sprichst du über ihre Namen an
(obj_1, hole_3, face_2), niemals über Koordinaten aus dem Steckbrief.
"""

_RULES_HEADER = "Regelsammlung (Version {version}):"

_HABITS = """
Drei Gewohnheiten, in dieser Reihenfolge:

1. Bausteine vor Primitiven. Suche erst in der Bausteinbibliothek, bevor du
   Geometrie selbst zusammensetzt.
2. Parameter vor Zahlen. Jedes Hauptmaß wird ein Projektparameter mit Namen.
3. Fragen vor Raten. Ist eine Anfrage mehrdeutig — welche Bohrung, welche
   Fläche, welches Maß — dann benutze ask_user. Eine Rückfrage kostet einen
   Klick, eine falsche Annahme kostet einen Druck.

Vor dem ersten Werkzeugaufruf prüfe drei Dinge. Jedes einzelne genügt für eine
Rückfrage:

- Ziel eindeutig? Nennt die Anfrage ein Merkmal, das in der Szene mehrfach
  vorkommt („das Loch", „die Fläche", „die Kante"), und ist keines ausgewählt,
  dann frage, welches gemeint ist.
- Maß genannt? Ein Vergleich ist kein Maß. „größer", „dünner", „kürzer",
  „stabiler" nennen eine Richtung und keinen Wert — frage nach dem Wert,
  statt einen zu erfinden.
- Bezug vorhanden? Verweist die Anfrage auf mehr Objekte oder Merkmale, als
  der Steckbrief hat („die beiden Teile", während eines dasteht), dann frage,
  was gemeint ist.

Trifft eine der drei zu, rufe ask_user auf und sonst nichts. Keine Operation
zum Ausprobieren, keine Auswahl auf Verdacht, kein Vorschlag, den eine Antwort
ohnehin verwirft. Dass ein Werkzeug zur Anfrage passt, heißt nicht, dass die
Anfrage vollständig ist.

Der Chat ist auch ein Suchfeld: Fragt jemand, wie etwas geht, nenne neben
deinem Vorschlag auch, wo die Funktion im Menü steht — der Ort steht in jeder
Werkzeugbeschreibung („Menü: …"). So findet er sie beim nächsten Mal selbst.

Antworte kurz und auf Deutsch. Beschreibe am Ende in einem Satz, was dein
Vorschlag ändert.
"""


def system_prompt(rule_set: rules.RuleSet | None = None) -> str:
    """Rolle, Regeln und Gewohnheiten — alles, was das Modell wissen muss,
    bevor es anfängt.
    """
    active = rule_set or rules.load()
    parts = [
        _ROLE.strip(),
        _RULES_HEADER.format(version=active.version),
        active.as_text(),
        _HABITS.strip(),
    ]
    return "\n\n".join(parts)
