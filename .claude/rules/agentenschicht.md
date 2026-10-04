---
description: "Die LLM-Schicht — ein Vorschlag ist eine Transaktion, die drei Vorrangregeln, Kontext und Kontextfenster, das Angebot für lokale Modelle, Sicherheitsauflagen nach §32, MCP und die Agenten-Suite"
paths:
  - "app/core/agent/**/*.py"
  - "app/core/backends/**/*.py"
---

# Regeln für die Agentenschicht und die Backends

Der LLM-Agent steuert denselben Operations-API fern wie die Menüs — er bekommt
keine Sonderwege. Das Warum steht unter denselben Überschriften in
`konzepte/begruendungen/regel-agentenschicht.md`.

## Eine Transaktion

**Jeder Agentenvorschlag ist genau eine Transaktion** (Regel 16): Vorschlag →
Berechnung in Entwurfsqualität → Differenzansicht → Übernahme oder Verwerfen;
Iterationslimit und Kostendeckel sind hart. Nach jeder Op läuft die Prüfung —
wasserdicht, Volumen plausibel, keine unerwarteten Komponenten, keine
verwaisten Referenzen, keine verletzten Passungen —, und der Befund geht
zurück in den Kontext.

## Die drei Vorrangregeln

**Bausteine vor Primitiven, Parameter vor Zahlen, Fragen vor Raten** — im
Systemprompt verankert, in der Suite gemessen; wer eine lockert, misst vorher
und nachher. `ask_user` ist Pflicht, keine Höflichkeit: Die Suite enthält
absichtlich mehrdeutige Anfragen und zählt, ob gefragt statt geraten wurde.

- **„Fragen vor Raten" steht als Vorbedingung vor dem ersten
  Werkzeugaufruf, nicht als Gewohnheit in einer Liste**: drei Prüfungen, jede
  einzeln hinreichend für eine Rückfrage — Ziel eindeutig, Maß genannt, Bezug
  vorhanden —, dazu der Satz, der das Herumprobieren abstellt („und sonst
  nichts"). Anleitend in einer Liste hielt sie nicht; heute sind es 172
  Operationen und elf Zusatzwerkzeuge, und wer genug Angebote hat, findet
  immer eines, das plausibel aussieht.
- **Allgemein formulieren, nicht nach den Testanfragen** — eine auf die Suite
  hin optimierte Regel macht sie als Maßstab wertlos.
- **Keine Regel, die vor etwas warnt, das das Modell gar nicht tun kann**: Sie
  kostet Platz im Auftrag und lehrt eine Unterscheidung ohne Gegenstand.
- **`PROMPT_VERSION` steigt mit jeder Textänderung** — sonst behauptet eine
  Projektdatei einen Prompt, den es nicht mehr gibt (§26.4).

## Kontext

Der Agent sieht den Steckbrief (Projektparameter, **aktuelle Auswahl**,
Passungen samt Verletzt-Zustand, Druckeinstellungszeile, Quellen, Verlauf mit
den gesetzten Werten), den Prüfbericht samt verwendeter Rückfallstufen, die
gültigen Chatbeiträge und die Regelsammlung in ihrer Version — nicht den rohen
Verlauf; ein gedeckelter sagt, wie viele ältere Beiträge fehlen. Jedes
Op-Ergebnis nennt die **neuen Merkmale mit IDs**; `read_digest` liest den
Steckbrief der Arbeitskopie mitten im Zug neu, `read_standard` schlägt die
Normteiltabelle nach (§26.2 führt die abschließende Werkzeugliste). Die
Werkzeugbeschreibungen tragen den Menüort („Menü: …"); daran hängt §2.6, der
Chat als Suchfeld.

- Die Sitzung meldet Fortschritt je Schritt über einen Rückruf (`progress`,
  wie `ask` — kein Qt im Kern); Vorschläge zeigen Schritte, Token und
  Rückfragen in der Entscheidungszeile, eine erreichte Grenze ausgeschrieben.
- `read_analysis` (`agent/analysis.py`) macht Schichtanalyse, Schätzung,
  Einstellungsrat und Orientierungssuche lesbar: Jede Antwort beginnt mit ihrer
  Herkunft (Regel 14), ein harter Dreiecksdeckel ersetzt Zeitgewalt.
- **Druckeinstellungen setzt der Agent nie** — sie reisen nicht in
  Transaktionen (§15.5); er nennt die `advise`-Vorschläge samt Grund. Drucker
  und Material wechselt `set_print_target` als `DocumentChange`, Undo nimmt
  beide zurück.
- Gerenderte Ansichten (§23) liefert die Oberfläche (`app/ui/snapshots.py`) als
  beschriftete PNG, nur an ein Backend mit `supports_images`. Skizzen entstehen
  über die Grundform-Parameter der Skizzen-Ops (§30.1); die rohe Punktliste
  bleibt zweifach gesperrt und zählt als ungültiger Aufruf.
- **Eindeutig umkehrbare Vorschläge laufen automatisch** (§26.5, Regel 19):
  vier Bedingungen in `agent_apply.auto_acceptable`, die Leiste wird zur
  Übernommen-Leiste mit Rückgängig-Knopf, `auto_accept_reversible` (Vorgabe:
  an) schaltet es ab. Die Suite misst über `proposal.readings`, ob eine Frage
  nachgesehen oder geraten wurde — 39 Referenzanfragen.
- **Jeder Chatbeitrag verweist auf die Transaktion, die er erzeugt hat.** Wird
  sie zurückgenommen, gilt der Beitrag als verworfen und geht höchstens als
  „wurde verworfen" mit — sonst argumentiert der Agent nach jedem Undo mit
  einem Zustand, den es nicht mehr gibt.
- Jede Transaktion trägt `origin`: Urheber, bei Agenten zusätzlich Modell,
  Version des Systemprompts, Version der Regelsammlung, Temperatur.

## Das Kontextfenster ist die Bedingung, nicht die Feineinstellung

**Ollama schneidet den Prompt stillschweigend ab** (Vorgabefenster 4096
Token): Was nicht hineinpasst, fällt weg, mit ihm Systemprompt und
Vorrangregeln — das Modell ist dann nicht ungehorsam, es hat den Auftrag nie
gesehen. `OLLAMA_CONTEXT_TOKENS` in `backends/llm.py` hält den Wert (32 768)
samt Messreihe.

- **Ob gekürzt wurde, entscheidet die Länge der Anfrage**
  (`llm.prompt_was_cut`): `prompt_eval_count` unter dem, was der gesendete
  Text mindestens an Token hat, oder genau Ollamas Kürzungszahl (halbes
  Fenster plus `TRUNCATION_KEEPS`) bei einer Anfrage, die größer sein kann als
  das Fenster. Die Werkzeugzahl sagt nichts über die Größe. Die Messwerkzeuge
  fragen dieselbe Funktion.
- **172 Operationen, 183 Werkzeuge** — die Zahlen hält
  `tests/test_registry_consistency.py` gegen Register und `tool_schemas()`.
  Werkzeug- und Tokenzahl in `backends/llm.py` gehören zur selben Zählung
  (`test_the_measured_prompt_matches_the_current_tool_count`; die Chronik
  steht bei `PROMPT_TOKENS`). Wer die Werkzeugmenge ändert, zählt neu:
  `tools/measure_local_model.py --count-tokens` zählt die Grundlast eines
  lokalen Zugs (kompakter Prompt, Angebot zu „Hallo.", keine Operation
  ausführlich) und weist Modell, Kontext, Werkzeugzahl und Anfragehash aus;
  Geschwindigkeit misst er nicht — Kalt-/Warmläufe und Leistungsprüfungen nur
  beim Release. `test_the_local_window_fits_on_a_sixteen_gigabyte_card_with_room_for_the_scene`
  verlangt eine Grundlast unter einem Drittel des Fensters und 16 000 Token
  Luft für ausführliche Werkzeuge, Steckbrief und Verlauf.
- **Die Kurzfassung der Werkzeuge** (`prompt._COMPACT_FIELDS_HINT`):
  Rückseitenfelder (`placement="advanced"`) behalten nur ihre Bedingung — ein
  Ortsname mit eigener Bedeutung, dessen Satz nur an einem Werkzeug steht
  (etwa der Kopfwinkel der Senkung), behält den Satz; die zehn Ortsfelder
  fallen bei den `insert_*`-Bausteinen aus der Kurzfassung und werden weiter
  angenommen (die Sitzung prüft gegen das Register, nie gegen die
  Kurzfassung); Millimeter und Grad stehen einmal im Prompt statt am Feld
  (eine andere Einheit bleibt am Feld, `tools.IMPLIED_UNITS`). **Eine
  Bedingung („Gilt bei …") fällt nie weg**, auch nicht an einem Feld, dessen
  Satz eine Konvention wiederholt (`tools._repeats_a_convention`); die Zeile
  „Wann nicht" ist Inhalt und bleibt. Im Angebot tragen ausführliche
  Bausteine ihre zehn Ortsfelder wieder, ohne Satz
  (`operation_tools(part_placement=True)`) — ohne sie setzte ein lokales
  Modell Bausteine ohne Stelle.
- **Der Steckbrief teilt dasselbe Fenster**: Über
  `context.CONDENSE_ABOVE_CHARS` fasst der lokale Weg gleiche Merkmale
  zusammen, nennt je Körper nur die zwölf größten Flächen
  (`digest.FACE_LINES_CONDENSED`) und zählt den Rest; beide Zeilen nennen den
  Weg zu allem (`read_digest` mit `objects`, dort unverdichtet).
- **Der Denkblock bleibt an** — ohne ihn fallen die Treffer; wer `think: false`
  wieder vorschlägt, misst gegen dieselbe Basis.

### Ein lokales Modell bekommt ein Angebot, nicht das ganze Register

**Jede Operation bleibt ein Werkzeug, das sich aufrufen lässt; nur die
gemeinten stehen mit allen Feldern da** (`agent/offer.py`). Das ist keine
Auswahl, die aussortiert — eine Operation, die der Agent nicht mehr sieht,
wäre eine Betriebsart mit anderem Namen (§2.6).

- **Ausführlich** stehen die Treffer von `registry.search.rank_operations`
  über Anfrage und letzte Nutzerbeiträge — **dieselbe** Wortsuche wie die
  Befehlspalette, kein zweites Ranking (`zwillinge.md`), aber **ohne die
  Kundenwörter der Palette** (`CUSTOMER_WORDS`, `customer_words=False`,
  `grenzen.md`) —, am gewählten Merkmal seine Handlungen aus `ACTION_ORDER`, in
  leerer Szene die sichtbaren Grundkörper, und was das Modell im Zug
  angefordert oder über `find_part` gefunden hat. Von sich aus höchstens
  `DETAILED_LIMIT`, und nur über `MIN_SCORE`.
- **Alle übrigen als Kurzform**: Titel, `STUB_MARK`, keine Felder. Ihr Aufruf
  **führt nichts aus**, holt die Felder für den nächsten Schritt und zählt als
  `Proposal.lookups` — weder als Werkzeugaufruf noch als ungültiger; die Suite
  weist ihn getrennt aus.
- **Registerreihenfolge**, auch wenn eine Kurzform ausführlich wird: Ein
  unveränderter Anfang der Anfrage bleibt unverändert.
- **Ein gehostetes Modell sieht jedes Werkzeug ausführlich**
  (`offer is None`) — das Angebot antwortet auf das Fenster, nicht auf die
  Werkzeugwahl.
- **Ein versteckter Zwilling (`menu_twins`) steht nie von sich aus
  ausführlich** — gemeint ist sein sichtbarer, der die Körperart selbst fragt;
  angefordert bekommt das Modell ihn trotzdem. An beiden Wegen nennt
  `tools.second_choice_note` das Werkzeug der ersten Wahl, nicht nur ihren
  Titel: Beide Zwillinge heißen im Menü gleich.

Wer an Rangfolge, Grenze oder Kurzform dreht, fährt `tests/test_tool_offer.py`,
danach `tools/check_local_model.py` — acht Fälle, drei davon Operationen, die
ausführlich angeboten werden müssen, einer absichtlich mehrdeutig — und am
Ende die Suite gegen denselben Stand ohne die Änderung, gezählt mit der
Bewertung, die einen Zwilling als dieselbe Handlung nimmt
(`run_agent_suite._acts`). Zwei Läufe desselben Stands kippen bis zu sieben
Fälle in jede Richtung; ein Unterschied darunter ist Rauschen.

### Nach dem Zug bleibt das Modell warm — bis ein anderer die Karte braucht

`resource_session` trägt das Modell nach dem Zug mit `resources.keep_warm`
ein, statt es zu entladen (auf dem Prozessor entlädt es sofort);
`local_ai_slot(..., holder=...)` gibt beim Betreten jedes fremde warm
gehaltene Modell frei. **Wer einen neuen lokalen Weg baut, der ein Modell
lädt, trägt es ein und nennt beim Betreten der Spur seinen Halter** — sonst
hält es seine `OLLAMA_KEEP_ALIVE` gegen einen ComfyUI-Lauf, der davon nichts
weiß, und zwei Modelle zugleich auf der Karte gingen schon einem Absturz
voraus.

**Jede lokale Antwort hat eine Obergrenze** (`OLLAMA_ANSWER_TOKENS` als
`num_predict`); sie gilt einer Schleife, nicht einer langen Antwort. Was an der
Grenze abbricht, meldet die Sitzung als abgeschnitten mit Befund.

## Eine Ablehnung muss sagen, was zu ändern ist

Das Modell korrigiert nur, was es erfährt:

- **Hält die Kette an, reist der Grund mit**: Die Befunde der anhaltenden
  Operation gehen mit ans Modell (`checks.check`), nicht nur „Die Auswertung
  hält bei dieser Operation an".
- **Die Fehlertexte des Kerns tragen keine Platzhalter** (§33.1); die Zahlen
  stehen in `values`. Die Antwort ans Modell setzt beides zusammen wie die
  Oberfläche — **mit dem Feldnamen**.

Wer eine neue Meldung ans Modell schreibt, prüft sie: Steht darin, *welcher*
Wert *welche* Grenze reißt? Ein Satz ohne diese zwei Angaben erzeugt einen
zweiten Versuch, keinen besseren.

## Sicherheit (§32)

Projektdateien wandern zwischen Leuten — eine fremde Datei darf nichts
ausführen.

- **Kein `eval`** (Regel 10): Parameterausdrücke über den eigenen Auswerter
  mit beschränkter Grammatik, auch nicht „abgesichert".
- **Kein fremder Quelltext wird ausgeführt** (Regel 11) — eine Projektdatei
  kann nichts starten. Wer je wieder eine Operation baut, die Quelltext
  entgegennimmt, baut die Prüfung mit und trägt sie in `foreign.SCRIPTED_OPS`
  ein; die Maschinerie dafür steht und wird an einer Attrappe geprüft.
- Fester Arbeitsordner je Lauf für **jedes** externe Programm, Zeit- und
  Speicherlimit, kein Netzzugriff.
- Beim Import Dreieckszahl und Dateigröße deckeln — klare Meldung statt
  Speicherüberlauf (`dateiformat.md`).

## Backends melden sich ab, sie nörgeln nicht

Ohne Schlüssel sind die Agentenfunktionen ausgegraut, und die Anwendung bleibt
voll nutzbar: ein Hinweis an der Chatleiste, kein Werbebanner, kein
wiederholtes Nachfragen. Dasselbe für Slicer und Mesh-Erzeugung — fehlt das
Programm, sagt die betroffene Funktion das in einem Satz mit Hinweis auf die
Einstellung. Die Mesh-Schnittstelle kennt nur `text_to_mesh` und
`image_to_mesh`: kein Nutzercode, keine Dateipfade, kein Zustand.

## Suite

`tools/run_agent_suite.py` ist **kein Testlauf** — er kostet Geld und braucht
einen Schlüssel oder ein lokales Modell. Sein Ergebnis ist eine Quote, kein
Bestanden. Er läuft auf Ansage, nicht nebenbei.

## Die Schnittstelle nach außen (MCP)

`app/core/agent/remote.py` spricht JSON-RPC und weiß nichts von Netz und
Fenster; `app/ui/remote_server.py` bringt beides dazu. `tests/test_remote.py`
prüft die Auflagen:

- **Standardmäßig aus.** Eine offene Schnittstelle, die niemand eingeschaltet
  hat, ist eine offene Tür.
- **Nur `127.0.0.1`** — dreimal geprüft: an der Bindung, an der Absenderadresse
  jeder Anfrage und an ihrem `Origin`. Eine Bindung allein lässt sich durch
  eine Weiterleitung umgehen; die Adresse allein hält keinen Browser auf — eine
  beliebige Seite kann ihn per `fetch` zu einem POST hierher bewegen, CORS
  verbirgt nur die Antwort, **ausgeführt** wäre der Aufruf trotzdem.
  `origin_allowed` lässt durch, was keinen `Origin` schickt (ein MCP-Client ist
  kein Browser) und was von `localhost` kommt.
- **Kein ausführbarer Quelltext, kein Dateipfad** — beides wird abgewiesen,
  **bevor** gerechnet wird. Der Pfad wird am **Wert** erkannt, nicht am Namen
  des Parameters, und eng gefasst: Eine Sperre, die „Deckel 2" verschluckt,
  macht die Schnittstelle unbrauchbar und sieht dabei sicher aus.
- **Jeder Aufruf eine Transaktion mit Herkunftsvermerk**: Er reist als
  Qt-Ereignis in den Hauptthread und geht denselben Weg wie ein Menüklick; der
  Server wartet. Das Dokument gehört dem Fenster.
- **Lesende Rechnungen rechnen im Faden des Servers**: Der Hauptthread nimmt
  nur den Schnappschuss und gibt `remote.Deferred` zurück;
  `WindowBridge._compute` rechnet mit Token, das Zeitgrenze und Ausschalten
  erreicht. Keine Transaktion, kein Dokumentzugriff; eine Zeitüberschreitung
  ist ein Werkzeugfehler mit Satz (`remote.TIMED_OUT`), kein Protokollfehler.

Die Werkzeuge kommen aus `tools.py`, abzüglich `DENIED` — eine zweite Liste
wäre am Tag nach der nächsten Operation falsch.
