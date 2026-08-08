---
paths:
  - "app/core/agent/**/*.py"
  - "app/core/backends/**/*.py"
---

# Regeln für die Agentenschicht und die Backends

Der LLM-Agent steuert denselben Operations-API fern, den auch die Menüs
benutzen. Er bekommt keine Sonderwege.

## Eine Transaktion

**Jeder Agentenvorschlag ist genau eine Transaktion** (Regel 16). Ein Undo
nimmt ihn vollständig zurück. Ablauf: Vorschlag → Berechnung in
Entwurfsqualität → Differenzansicht → Übernahme oder Verwerfen. Iterationslimit
und Kostendeckel sind hart.

Nach jeder Op läuft die Prüfung — wasserdicht, Volumen plausibel, keine
unerwarteten Komponenten, keine verwaisten Referenzen, keine verletzten
Passungen — und der Befund geht zurück in den Kontext.

## Die vier Vorrangregeln

**Bausteine vor Primitiven, Op-Liste vor OpenSCAD, Parameter vor Zahlen,
Fragen vor Raten.** Alle vier im Systemprompt verankert und in der Suite
gemessen. Wer eine davon lockert, misst vorher und nachher.

`ask_user` ist Pflicht, keine Höflichkeit: Die Suite enthält absichtlich
mehrdeutige Anfragen und zählt, ob gefragt statt geraten wurde.

**„Fragen vor Raten" trägt nur als Vorbedingung, nicht als Gewohnheit.** Als
vierter Punkt einer Liste war sie anleitend, und das hielt gegen 84 Werkzeuge
nicht: sobald der Systemprompt vollständig ankam, fiel die Quote von 3/3 auf
1/3 — wer genug Angebote hat, findet immer eines, das plausibel aussieht.
Prompt-Version 2 stellt deshalb drei Prüfungen *vor* den ersten
Werkzeugaufruf, jede einzeln hinreichend für eine Rückfrage: Ziel eindeutig,
Maß genannt, Bezug vorhanden. Dazu der Satz, der das Herumprobieren abstellt
(„und sonst nichts") — ein Fall hatte zwanzig Aufrufe hintereinander
abgesetzt.

Wer daran schreibt, formuliert **allgemein** und nicht nach den drei
Testanfragen. Eine Regel, die auf die Suite hin optimiert ist, macht sie als
Maßstab wertlos. Und `PROMPT_VERSION` steigt mit jeder Textänderung, sonst
behauptet eine Projektdatei, unter einem Prompt entstanden zu sein, den es
nicht mehr gibt (§26.4).

## Kontext

Der Agent sieht Steckbrief (mit Projektparametern und **aktueller Auswahl**),
Prüfbericht samt verwendeter Rückfallstufen, Verlauf in Kurzform, die gültigen
Chatbeiträge und die Regelsammlung in ihrer Version. Nicht den rohen Verlauf.

**Jeder Chatbeitrag verweist auf die Transaktion, die er erzeugt hat.** Wird
sie zurückgenommen, gilt der Beitrag als verworfen und geht höchstens als
„wurde verworfen" mit. Ohne diese Kopplung argumentiert der Agent nach jedem
Undo mit einem Zustand, den es nicht mehr gibt.

Jede Transaktion trägt `origin`: Urheber, bei Agenten zusätzlich Modell,
Version des Systemprompts, Version der Regelsammlung, Temperatur.

## Das Kontextfenster ist die Bedingung, nicht die Feineinstellung

**Ollama schneidet den Prompt stillschweigend ab.** Sein Vorgabefenster ist
4096 Token; allein die 84 Werkzeugschemata aus dem Register sind rund 99 000
Zeichen, gemessen 21 162 Token. Was nicht hineinpasst, fällt weg — und mit ihm
der Systemprompt samt der vier Vorrangregeln. Das Modell ist dann nicht
ungehorsam, es hat den Auftrag nie gesehen.

Genau das war der Befund „der Agent greift nicht zu den Bausteinen (0/13)".
Gemessen mit `qwen3:14b` an drei Anfragen, für die ein Baustein die richtige
Antwort ist: 0 von 3 bei 4096, 8192 und 16384 (jedes Mal abgeschnitten), 3 von
3 bei 32768 — und dabei **schneller** (21,2 s gegen 30–36 s je Frage), weil ein
Modell, das den Auftrag kennt, nicht herumrät. `OLLAMA_CONTEXT_TOKENS` in
`backends/llm.py` hält den Wert samt Messreihe.

Wer die Werkzeugmenge ändert, prüft diese Zahl nach: `prompt_eval_count` in
Ollamas Antwort sagt, wie viel wirklich ankam. Liegt es bei etwa der Hälfte des
Fensters, wurde gekürzt.

## Sicherheit (§32)

Projektdateien wandern zwischen Leuten — eine fremde Datei darf nichts
ausführen.

- **Kein `eval`.** Parameterausdrücke über den eigenen Auswerter mit
  beschränkter Grammatik, auch nicht „abgesichert".
- **OpenSCAD-Quelltext wird vor jedem Lauf geprüft**: `import`, `include`,
  `use`, `surface` nur mit relativen Pfaden unterhalb des Arbeitsordners. Gilt
  für Quelltext aus Projektdateien **und aus dem LLM**.
- Fester Arbeitsordner je Lauf, Zeit- und Speicherlimit, kein Netzzugriff.
- Beim Import Dreieckszahl und Dateigröße deckeln — klare Meldung statt
  Speicherüberlauf.

## Backends melden sich ab, sie nörgeln nicht

Ohne Schlüssel sind die Agentenfunktionen ausgegraut und die Anwendung bleibt
voll nutzbar. Ein Hinweis an der Chatleiste, mehr nicht — kein Werbebanner,
kein wiederholtes Nachfragen. Dasselbe gilt für OpenSCAD, den Slicer und die
Mesh-Erzeugung: fehlt das Programm, sagt die betroffene Funktion das in einem
Satz mit Hinweis auf die Einstellung.

Die Mesh-Schnittstelle kennt nur `text_to_mesh` und `image_to_mesh`: kein
Nutzercode, keine Dateipfade, kein Zustand.

## Suite

`tools/run_agent_suite.py` ist **kein Testlauf** — er kostet Geld und braucht
einen Schlüssel oder ein lokales Modell. Sein Ergebnis ist eine Quote, kein
Bestanden. Er läuft auf Ansage, nicht nebenbei.

## Die Schnittstelle nach außen (MCP)

`app/core/agent/remote.py` spricht JSON-RPC und weiß nichts von Netz und
Fenster; `app/ui/remote_server.py` bringt beides dazu. Vier Auflagen, und
`tests/test_remote.py` prüft sie:

- **Standardmäßig aus.** Eine offene Schnittstelle, die niemand eingeschaltet
  hat, ist eine offene Tür.
- **Nur `127.0.0.1`** — dreimal geprüft: an der Bindung, an der Absenderadresse
  jeder Anfrage und an ihrem `Origin`. Eine Bindung allein lässt sich durch
  eine Weiterleitung umgehen. Die Adresse allein hält keinen Browser auf: der
  läuft auf diesem Rechner, gleich welche Seite ihn geschickt hat, und eine
  beliebige Seite kann ihn per `fetch` zu einem POST hierher bewegen. Die
  Antwort verbirgt CORS vor ihr — **ausgeführt** wäre der Aufruf trotzdem.
  `origin_allowed` lässt durch, was keinen `Origin` schickt (ein MCP-Client ist
  kein Browser) und was von `localhost` kommt.
- **Kein ausführbarer Quelltext, kein Dateipfad.** Beides wird abgewiesen,
  **bevor** gerechnet wird. Der Pfad wird am **Wert** erkannt, nicht am Namen
  des Parameters — und eng gefasst, denn eine Sperre, die „Deckel 2"
  verschluckt, macht die Schnittstelle unbrauchbar und sieht dabei sicher aus.
- **Jeder Aufruf eine Transaktion mit Herkunftsvermerk.** Der Aufruf reist als
  Qt-Ereignis in den Hauptthread und geht denselben Weg wie ein Menüklick; der
  Server wartet. Das Dokument gehört dem Fenster, und was nebenher
  hineinschriebe, könnte weder Undo noch Prüfbericht erklären.

Die Werkzeuge kommen aus `tools.py`, abzüglich `DENIED`. Eine zweite Liste gäbe
es nicht — sie wäre am Tag nach der nächsten Operation falsch.
