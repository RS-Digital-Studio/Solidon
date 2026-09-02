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

## Die drei Vorrangregeln

**Bausteine vor Primitiven, Parameter vor Zahlen, Fragen vor Raten.** Alle
drei im Systemprompt verankert und in der Suite gemessen. Wer eine davon
lockert, misst vorher und nachher.

**Es waren vier, und die zweite hieß „Op-Liste vor OpenSCAD".** Sie ist am
26.08.2026 mit dem OpenSCAD-Ausbau entfallen — nicht gelockert, sondern
gegenstandslos: Der Quelltextweg, vor dem sie warnte, existiert nicht mehr.
Was sie inhaltlich schützte, sagt „Bausteine vor Primitiven" ohnehin. Eine
Regel, die ein Modell vor etwas warnt, das es gar nicht tun kann, kostet Platz
im Auftrag und lehrt eine Unterscheidung ohne Gegenstand
(`PROMPT_VERSION = "4"`, Regelsammlung Version 3).

`ask_user` ist Pflicht, keine Höflichkeit: Die Suite enthält absichtlich
mehrdeutige Anfragen und zählt, ob gefragt statt geraten wurde.

**„Fragen vor Raten" trägt nur als Vorbedingung, nicht als Gewohnheit.** Als
vierter Punkt einer Liste war sie anleitend, und das hielt gegen die damals
84 Werkzeuge nicht — heute sind es 95 Operationen und elf Zusatzwerkzeuge:
sobald der Systemprompt vollständig ankam, fiel die Quote von 3/3 auf
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

Der Agent sieht Steckbrief (mit Projektparametern, **aktueller Auswahl**,
Passungen samt Verletzt-Zustand, Druckeinstellungszeile, Quellen und dem
Verlauf mit den gesetzten Werten), Prüfbericht samt verwendeter
Rückfallstufen, die gültigen Chatbeiträge und die Regelsammlung in ihrer
Version. Nicht den rohen Verlauf; ein gedeckelter sagt, wie viele ältere
Beiträge fehlen. Jedes Op-Ergebnis nennt die **neuen Merkmale mit IDs**;
`read_digest` liest den Steckbrief der Arbeitskopie mitten im Zug neu, und
`read_standard` schlägt die Normteiltabelle nach (§26.2 führt die
abschließende Werkzeugliste). Die Werkzeugbeschreibungen tragen den Menüort
(„Menü: …") — daran hängt §2.6, der Chat als Suchfeld (Prompt-Version 3).

Die Sitzung meldet Fortschritt je Schritt über einen Rückruf (`progress`,
wie `ask` — kein Qt im Kern); Vorschläge zeigen Schritte, Token und
Rückfragen in der Entscheidungszeile, eine erreichte Grenze ausgeschrieben.

`read_analysis` (`agent/analysis.py`) macht Schichtanalyse, Schätzung,
Einstellungsrat und Orientierungssuche lesbar — jede Antwort beginnt mit
ihrer Herkunft (Regel 14), ein harter Dreiecksdeckel ersetzt Zeitgewalt.
Druckeinstellungen werden **nie gesetzt**: sie reisen nicht in Transaktionen
(§15.5), der Agent nennt die `advise`-Vorschläge samt Grund. Drucker und
Material wechselt `set_print_target` — als `DocumentChange`, Undo nimmt
beide zurück. Die gerenderten Ansichten (§23) liefert die Oberfläche
(`app/ui/snapshots.py`) als beschriftete PNG; nur ein Backend mit
`supports_images` bekommt sie. Skizzen entstehen über die
Grundform-Parameter der Skizzen-Ops (§30.1) — die rohe Punktliste bleibt
zweifach gesperrt und zählt als ungültiger Aufruf.

**Eindeutig umkehrbare Vorschläge laufen automatisch** (§26.5, Regel 19):
vier Bedingungen in `agent_apply.auto_acceptable`, die Leiste wird zur
Übernommen-Leiste mit Rückgängig-Knopf, `auto_accept_reversible` (Vorgabe:
an) schaltet es ab. Die Suite misst über `proposal.readings`, ob eine Frage
nachgesehen oder geraten wurde — 39 Referenzanfragen seit der
Agent-Vertiefung.

**Jeder Chatbeitrag verweist auf die Transaktion, die er erzeugt hat.** Wird
sie zurückgenommen, gilt der Beitrag als verworfen und geht höchstens als
„wurde verworfen" mit. Ohne diese Kopplung argumentiert der Agent nach jedem
Undo mit einem Zustand, den es nicht mehr gibt.

Jede Transaktion trägt `origin`: Urheber, bei Agenten zusätzlich Modell,
Version des Systemprompts, Version der Regelsammlung, Temperatur.

## Das Kontextfenster ist die Bedingung, nicht die Feineinstellung

**Ollama schneidet den Prompt stillschweigend ab.** Sein Vorgabefenster ist
4096 Token; allein die 85 Werkzeugschemata aus dem Register sind rund 109 000
Zeichen, gemessen 24 474 Token. Was nicht hineinpasst, fällt weg — und mit ihm
der Systemprompt samt der Vorrangregeln. Das Modell ist dann nicht
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

**Stand 02.09.2026: 95 Operationen, 106 Werkzeuge** — die Zahlen hält
`tests/test_registry_consistency.py` gegen Register und `tool_schemas()`.
Systemprompt und Werkzeugsatz zusammen waren am 26.08.2026 (90 Operationen,
nach dem OpenSCAD-Ausbau eines weniger) 149 061 Zeichen im vollen und 110 027
im kompakten Satz; seither sind fünf Operationen dazugekommen, und die
Zeichenzahl ist nicht neu gemessen.

Die Tokenmessung darunter ist **älter als diese Zahlen** und steht trotzdem
hier, weil sie in die sichere Richtung altert: Der Ausbau hat den Auftrag an
drei Stellen *kürzer* gemacht — ein Werkzeug weniger, eine Gewohnheit weniger
im Prompt, zwei Regeln weniger in der Sammlung. Was bei mehr Werkzeugen
hineinpasste, passt bei weniger erst recht. Wer die Zahl scharf braucht, misst
sie neu; `prompt_eval_count` ist der einzige ehrliche Weg dorthin.

Bei 85 Operationen nachgemessen, `qwen3:14b` gegen `num_ctx` 32768: 26 601
Token für Systemprompt und alle 96 Werkzeuge, 19 249 für den kompakten Satz,
den der Ollama-Pfad fährt — beide ganz angekommen. Das Fenster trägt also
weiter. Gezählt ist die Luft trotzdem: über dem kompakten Satz bleiben rund
13 500 Token für Steckbrief, Verlauf und Antworten, und größer als 32768 wird
das Fenster nicht ohne Weiteres — bei diesem Wert belegt das Modell 14 GB und
bleibt damit gerade noch auf einer 16-GB-Karte.

## Eine Ablehnung muss sagen, was zu ändern ist

Das Modell korrigiert nur, was es erfährt. Zwei Stellen haben das lange
verschluckt, und beide sahen aus wie Fehlerbehandlung:

- **Die Kette hält an, und der Grund bleibt im Bericht.** `checks.check`
  meldete „Die Auswertung hält bei dieser Operation an" — der Satz, der
  weiterhilft („Der gewählte Körper ist ein Netz"), stand daneben und ging
  nicht mit. Gemessen an `pocket_plate`: viermal dieselbe Operation mit
  anderen Zahlen, statt einmal den Körpertyp zu wechseln. Die Befunde der
  anhaltenden Operation reisen jetzt mit.
- **Die Fehlertexte des Kerns tragen keine Platzhalter** (§33.1). „Der Wert
  liegt unter dem zulässigen Mindestwert" ist der ganze Satz; die Zahlen
  stehen in `values`. Die Oberfläche setzt beides zusammen, die Antwort ans
  Modell tat es nicht. **Der Feldname gehört ausdrücklich dazu** — ohne ihn
  korrigierte das Modell dreimal die Tiefe, während `corners` die Grenze riss.

Wer eine neue Meldung ans Modell schreibt, prüft sie an derselben Frage: Steht
darin, *welcher* Wert *welche* Grenze reißt? Ein Satz ohne diese zwei Angaben
erzeugt einen zweiten Versuch, keinen besseren.

## Sicherheit (§32)

Projektdateien wandern zwischen Leuten — eine fremde Datei darf nichts
ausführen.

- **Kein `eval`.** Parameterausdrücke über den eigenen Auswerter mit
  beschränkter Grammatik, auch nicht „abgesichert".
- **Kein fremder Quelltext wird ausgeführt.** Hier stand die Prüfung, die
  OpenSCAD-Quelltext vor jedem Lauf durchsah (`import`, `include`, `use`,
  `surface` nur relativ). Sie ist seit dem 26.08.2026 gegenstandslos: Der
  einzige Weg, der fremden Code ausführte, ist ausgebaut. Damit wird aus einer
  Prüfung eine **Zusage** — eine Projektdatei kann nichts starten. Wer je
  wieder eine Operation baut, die Quelltext entgegennimmt, baut die Prüfung
  mit (Regel 11) und trägt sie in `foreign.SCRIPTED_OPS` ein; die Maschinerie
  dafür steht und wird an einer Attrappe geprüft.
- Fester Arbeitsordner je Lauf für **jedes** externe Programm, Zeit- und
  Speicherlimit, kein Netzzugriff.
- Beim Import Dreieckszahl und Dateigröße deckeln — klare Meldung statt
  Speicherüberlauf.

## Backends melden sich ab, sie nörgeln nicht

Ohne Schlüssel sind die Agentenfunktionen ausgegraut und die Anwendung bleibt
voll nutzbar. Ein Hinweis an der Chatleiste, mehr nicht — kein Werbebanner,
kein wiederholtes Nachfragen. Dasselbe gilt für den Slicer und die
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
