---
description: "Die LLM-Schicht — ein Vorschlag ist eine Transaktion, die drei Vorrangregeln, Kontextfenster, Sicherheitsauflagen nach §32 und die Agenten-Suite"
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
84 Werkzeuge nicht — heute sind es 142 Operationen und elf Zusatzwerkzeuge:
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

**Ob gekürzt wurde, entscheidet die Länge der Anfrage** (`llm.prompt_was_cut`):
`prompt_eval_count` unter dem, was der gesendete Text mindestens an Token hat,
oder genau Ollamas Kürzungszahl (halbes Fenster plus `TRUNCATION_KEEPS`) bei
einer Anfrage, die größer sein kann als das Fenster. Die Werkzeugzahl sagt
seit dem Angebot (unten) nichts mehr über die Größe. Die Messwerkzeuge fragen
dieselbe Funktion — was die Anwendung als gekürzt zurückweist, weist auch die
Messung zurück.
`tools/measure_local_model.py --count-tokens` zählt die Grundlast eines
lokalen Zugs — kompakter Prompt, Angebot zu „Hallo.", keine Operation
ausführlich — und weist Modell, Kontext, Werkzeugzahl und Anfragehash aus.
Dieser funktionale Zählweg misst keine Geschwindigkeit; Kalt-/Warmläufe und
Leistungsprüfungen bleiben dem Release vorbehalten.

### Ein lokales Modell bekommt ein Angebot, nicht das ganze Register

**Jede Operation bleibt ein Werkzeug, das sich aufrufen lässt; nur die
gemeinten stehen mit allen Feldern da** (`agent/offer.py`, Prompt-Version 8).
Das ist keine Auswahl, die aussortiert — eine Operation, die der Agent nicht
mehr sieht, wäre eine Betriebsart mit anderem Namen (§2.6). Die Regeln dazu:

- **Ausführlich** stehen die Treffer von `registry.search.rank_operations`
  über Anfrage und letzte Nutzerbeiträge — **dieselbe** Wortsuche wie die
  Befehlspalette, kein zweites Ranking daneben (`zwillinge.md`), aber **ohne
  die Kundenwörter der Palette** (`CUSTOMER_WORDS`, `customer_words=False`):
  Mit ihnen fiel „Versteife die Wand mit einer Rippe" von 3 von 3 auf 0 von 2
  (qwen3:14b, Durchsicht 0.5.1, `grenzen.md`) —, am gewählten
  Merkmal seine Handlungen aus `ACTION_ORDER`, in leerer Szene die sichtbaren
  Grundkörper, und was das Modell im Zug angefordert oder über `find_part`
  gefunden hat. Von sich aus höchstens `DETAILED_LIMIT`, und nur über
  `MIN_SCORE`.
- **Alle übrigen als Kurzform**: Titel, `STUB_MARK`, keine Felder. Ihr Aufruf
  **führt nichts aus**, holt die Felder für den nächsten Schritt und zählt als
  `Proposal.lookups` — weder als Werkzeugaufruf noch als ungültiger. Die Suite
  weist ihn getrennt aus.
- **Registerreihenfolge**, auch wenn eine Kurzform ausführlich wird: Ein
  unveränderter Anfang der Anfrage bleibt unverändert.
- **Ein gehostetes Modell sieht jedes Werkzeug ausführlich** (`offer is
  None`). Es hat Platz, und das Angebot ist eine Antwort auf das Fenster, nicht
  auf die Werkzeugwahl.
- **Ein versteckter Zwilling (`menu_twins`) steht nie von sich aus
  ausführlich** — gemeint ist sein sichtbarer, der die Körperart selbst fragt.
  Angefordert bekommt das Modell ihn trotzdem. Und an beiden Wegen nennt
  `tools.second_choice_note` das Werkzeug der ersten Wahl, nicht nur ihren
  Titel: Beide Zwillinge heißen im Menü gleich.

Wer an Rangfolge, Grenze oder Kurzform dreht, fährt `tests/test_tool_offer.py`
und danach `tools/check_local_model.py` — acht Fälle, drei davon
Operationen, die ausführlich angeboten werden müssen, einer absichtlich
mehrdeutig — und am Ende die Suite gegen denselben Stand ohne die Änderung.
Gemessen am 25.09.2026 mit qwen3:14b: 30 461 Token für die Kurzfassung aller
153 Werkzeuge gegen **7 258** für die Grundlast des Angebots. **Und die Quote
hält:** Am 26.09.2026 auf freier Karte, derselbe Code mit und ohne Angebot,
qwen3:14b — mit Angebot bei 32 768 24 von 39, ohne 14 (neunmal riss das
Fenster) und mit einem Fenster von 40 960 ebenfalls 24, aber in 149 statt 44
Minuten und zu einem Zehntel auf dem Prozessor. Mit dem Zwilling als Kurzform
22 — im Rauschen: Zwei Läufe desselben Stands kippten bis zu sieben Fälle in
jede Richtung. Gezählt ist mit der Bewertung, die einen Zwilling als dieselbe
Handlung nimmt (`run_agent_suite._acts`).

### Nach dem Zug bleibt das Modell warm — bis ein anderer die Karte braucht

`resource_session` trägt das Modell nach dem Zug mit `resources.keep_warm`
ein, statt es zu entladen (auf dem Prozessor entlädt es sofort);
`local_ai_slot(..., holder=...)` gibt beim Betreten jedes fremde warm
gehaltene Modell frei. **Wer einen neuen lokalen Weg baut, der ein Modell
lädt, trägt es ein und nennt beim Betreten der Spur seinen Halter** — sonst
hält es seine `OLLAMA_KEEP_ALIVE` gegen einen ComfyUI-Lauf, der davon nichts
weiß, und genau diese Lage (zwei Modelle zugleich auf der Karte) ging dem
Absturz vom 01.09.2026 voraus.

**Jede lokale Antwort hat eine Obergrenze** (`OLLAMA_ANSWER_TOKENS` als
`num_predict`). Sie gilt einer Schleife, nicht einer langen Antwort: gemma4:12b
lief bei der Werkzeugprobe in 14 400 Token ohne Ende. Was an der Grenze
abbricht, meldet die Sitzung als abgeschnitten mit Befund.

**Stand 25.09.2026: 142 Operationen, 153 Werkzeuge** — die Zahlen hält
`tests/test_registry_consistency.py` gegen Register und `tool_schemas()`.
Die Grundlast des Angebots wurde mit `qwen3:14b`, `num_ctx=32768` und
`num_predict=1` vollständig mit **7 276 Token** gezählt (22,2 Prozent des
Fensters); ein Zug mit ausführlichen Werkzeugen, Steckbrief und Verlauf kam in
der Suite auf bis zu 14 215. Werkzeugzahl und Tokenzahl in `backends/llm.py`
gehören zu derselben Zählung, und
`test_the_measured_prompt_matches_the_current_tool_count` hält sie zusammen.
Bis zum 23.09.2026 zählte der kompakte Auftrag aller Werkzeuge 27 293 Token
bei 147 Werkzeugen (83,3 Prozent); die Chronik der Zählungen steht bei
`PROMPT_TOKENS`.

Die folgenden früheren Messungen sind historische Vergleiche. Sie ersetzen
die aktuelle vollständige Tokenzählung nicht und belegen keine heutige
Geschwindigkeit. Leistungswerte werden ausschließlich beim Release erneuert.

Bei 85 Operationen nachgemessen, `qwen3:14b` gegen `num_ctx` 32768: 26 601
Token für Systemprompt und alle 96 Werkzeuge, 19 249 für den kompakten Satz,
den der Ollama-Pfad fährt — beide ganz angekommen. Das Fenster trägt also
weiter. Gezählt ist die Luft trotzdem: über dem kompakten Satz bleiben rund
13 500 Token für Steckbrief, Verlauf und Antworten, und größer als 32768 wird
das Fenster nicht ohne Weiteres — bei diesem Wert belegt das Modell 14 GB und
bleibt damit gerade noch auf einer 16-GB-Karte.

**Vom 16.09. bis zum 22.09.2026 stand das Fenster auf 40 960** (Entscheidung
Robert): 143 Werkzeuge kosteten 36 731 Token, der Preis waren 11 statt 41 Token
je Sekunde. **Seit dem 22.09.2026 wieder 32 768** (RM-185): Die Kurzfassung
zählt mit 147 Werkzeugen 27 293 Token statt 37 836. Drei Kürzungen, jede als
Satz im kompakten Prompt (`prompt._COMPACT_FIELDS_HINT`, Prompt-Version 7):

- **Rückseitenfelder** (`placement="advanced"`) behalten nur ihre Bedingung
  (−5 755 Token). Ein Ortsname mit eigener Bedeutung — sein Satz steht nur an
  einem Werkzeug, etwa der Kopfwinkel der Senkung — behält den Satz.
- **Die zehn Ortsfelder** fallen bei den `insert_*`-Bausteinen aus der
  Kurzfassung (−2 905). Angenommen werden sie weiter: Die Sitzung prüft gegen
  das Register, nie gegen die Kurzfassung.
- **Millimeter und Grad** stehen einmal im Prompt statt am Feld (−1 269);
  eine andere Einheit bliebe am Feld (`tools.IMPLIED_UNITS`).

Nicht übernommen, obwohl gemessen: die Zeile „Wann nicht" zu streichen
(−2 123) — sie ist Inhalt. Eine **Bedingung** („Gilt bei …") fällt nie weg,
auch nicht an einem Feld, dessen Satz eine Konvention wiederholt
(`tools._repeats_a_convention`). Wer die Werkzeugmenge ändert, zählt neu
(`tools/measure_local_model.py --count-tokens`); der Test
`test_the_local_window_fits_on_a_sixteen_gigabyte_card_with_room_for_the_scene`
verlangt eine Grundlast unter einem Drittel des Fensters und 16 000 Token
Luft für ausführliche Werkzeuge, Steckbrief und Verlauf. **Eine Ausnahme von
der Kurzfassung:** Im Angebot tragen ausführliche Bausteine ihre zehn
Ortsfelder wieder, ohne Satz (`operation_tools(part_placement=True)`) — ohne
sie setzte qwen3.5:9b Bausteine ohne Stelle.

**Der Steckbrief teilt dasselbe Fenster.** Über `context.CONDENSE_ABOVE_CHARS`
fasst der lokale Weg gleiche Merkmale zusammen, nennt je Körper nur die
zwölf größten Flächen (`digest.FACE_LINES_CONDENSED`) und zählt den Rest;
beide Zeilen nennen den Weg zu allem (`read_digest` mit `objects`, dort
unverdichtet).

**Der Denkblock bleibt an.** `think: false` wurde am 23.09.2026 gemessen und
zurückgenommen: dieselbe Basis mit qwen3:14b ohne Denkblock 14 statt 21 von
39, Baustein 2 statt 7 von 13 — der Zeitgewinn (24 min statt rund 3 h für die
Suite) kostet die Treffer. Wer ihn wieder vorschlägt, misst gegen dieselbe Basis.

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
- **Lesende Rechnungen rechnen im Faden des Servers** (RM-144). Der
  Hauptthread nimmt nur den Schnappschuss und gibt `remote.Deferred` zurück;
  `WindowBridge._compute` rechnet mit Token, das Zeitgrenze und Ausschalten
  erreicht. Keine Transaktion, kein Dokumentzugriff. Eine Zeitüberschreitung
  ist ein Werkzeugfehler mit Satz (`remote.TIMED_OUT`), kein Protokollfehler.

Die Werkzeuge kommen aus `tools.py`, abzüglich `DENIED`. Eine zweite Liste gäbe
es nicht — sie wäre am Tag nach der nächsten Operation falsch.
