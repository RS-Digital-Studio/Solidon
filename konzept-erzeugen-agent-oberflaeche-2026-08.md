# Konzept — Erzeugen, Agent, Oberfläche (Stand 12.08.2026, Zahlen nachgezogen am 18.08.2026, nachrecherchiert am 19.08.2026)

Aus vier Fragen: Wie steht die Oberfläche gegen die anderen? Klappt Bild zu 3D,
und lässt sich das Ergebnis danach über den Agenten anpassen? Was geht mit dem
lokalen Modell? Und halten wir gegen Meshy und Hyper3D mit?

Alles unten ist **gemessen oder gerendert**, nicht abgeleitet: ComfyUI wurde
gestartet, ein Bild durch den Erzeugen-Dialog geschickt, das Ergebnis in der
Szene ausgelesen, das lokale Modell gegen die Werkzeuge gefahren. Wo eine
erste Einschätzung falsch war, steht die Korrektur dabei.

Verhältnis zu den anderen Papieren: `konzept-wettbewerb-2026-08.md` zieht das
Feld auf und bewertet alle Bereiche; dieses geht in die drei Bereiche hinein,
die dort nur eine Zeile bekommen haben, und trägt die Messwerte nach.

> **Das Papier ist abgearbeitet, und es hat sieben Tage lang nicht davon
> erzählt.** Sechs der sieben Punkte aus Teil 9 wurden am 12.08.2026 umgesetzt
> — `ROADMAP.md:4663`, „Das Erzeugen-und-Agent-Konzept abgearbeitet". Zwei
> fielen dabei anders aus als hier vorgeschlagen (A1, L1), einer war von
> Anfang an keiner (der Viewport-Befund war ein Messartefakt), und **einer ist
> offen geblieben: B1**, das zweite Netz-Backend — der einzige Punkt, den
> keine Liste führt. Am 18.08. wurden in Teil 5 die Zählwerte nachgezogen,
> die Vorschläge zwei Absätze darunter blieben stehen, als wären sie offen.
> Die Vermerke unten lösen das auf; geprüft am 19.08.2026 gegen `main`
> (b0415d6).

---

## Teil 1 — Der Befund, der alles andere überholt

**Nach dem Laden blieb der Viewport leer.** Im Bild standen nur die
Orientierungsmarker; der Körper blitzte beim Zoomen kurz auf und war danach
wieder weg. Gesehen hat es Robert am Bildschirm — ich hatte dasselbe Bild
zweimal in der Hand (`plotter.screenshot` und `QWidget.grab`) und beide Male
als Aufnahme-Artefakt abgetan. Das war der teuerste Fehler dieser Sitzung: ein
Fehlbild zweimal gesehen und wegerklärt.

Der Szenengraph war in Ordnung — sieben Akteure, alle sichtbar, Kamera auf dem
Körper, Clipping passend, zwei Renderer sauber auf Layer 0 und 1, das
Orientierungs-Widget in seiner Ecke. Falsch war, **wie** gezeichnet wird:
`plotter.render()` ist unter pyvistaqt kein Zeichnen, sondern ein
Repaint-Wunsch an Qt. Fällt der Wunsch mit dem Aufbau der Szene zusammen,
bleibt der Puffer leer, bis eine Interaktion VTK direkt rendern lässt.

`show_scene` bittet jetzt das Renderfenster direkt (`_render_now`). **Der
Nachweis ist unvollständig**, und das gehört zum Befund: der Fehler tritt
sporadisch auf. In vier Läufen nach der Änderung stand das Bild, davor in
mehreren nicht. Kommt er wieder, ist die nächste Spur der Qt-Malpfad über dem
nativen OpenGL-Fenster: `WA_NoSystemBackground` steht auf `False`, und der
`OverlayHost` darüber trägt ein Stylesheet — beides zusammen lässt Qt den
Bereich übermalen, in den VTK gezeichnet hat.

> **Erledigt — und der Befund war keiner: das Messgerät hat ihn erzeugt.** Die
> Prüfskripte fuhren `processEvents()` statt `app.exec()`; ein natives
> OpenGL-Fenster zeichnet so nur, solange etwas passiert. Dazu kommt, dass
> beide Aufnahmewege lügen: `plotter.screenshot` rendert neu und repariert
> damit genau den Zustand, den es zeigen soll, `QWidget.grab()` lässt den
> OpenGL-Bereich schwarz. In der normal gestarteten Anwendung stand das Bild —
> auch auf dem Stand vom 08.08., gegen den die Gegenprobe lief. Die Lehre steht
> in `ROADMAP.md:4697–4706`: *„Ein Messgerät, das seinen Gegenstand verändert,
> misst nichts."*
>
> Beide Änderungen sind trotzdem drin und richtig: `_render_now()` in
> `app/ui/viewport.py:1621`, aus `show_scene` gerufen, und die „nächste Spur"
> ist abgearbeitet — `app/ui/viewport.py:1196` setzt `WA_NoSystemBackground`
> heute auf `True`, mit dem Kommentarblock ab `:1188`, der genau die Begründung
> dieses Absatzes trägt. Was hier als sporadischer Fehler beschrieben ist, war
> die Sporadik der Prüfumgebung, nicht die der Anwendung. (Nachgeprüft am
> 19.08.2026.)

---

## Teil 2 — Bild zu 3D: es klappt, und dann hört es auf

### 2.1 Gemessen, durch den Dialog gefahren

Nicht gegen den Kern, sondern über *Datei → Modell erzeugen*, mit einem Bild
aus dem Druckordner. ComfyUI lief lokal auf einer RTX 4080 (16 GB). **Gemessen
am 12.08.2026**; nachfahren ließ sich der Lauf am 19.08. nicht, weil hier kein
ComfyUI läuft — die Zahlen bleiben als Messwerte jenes Tages stehen.

| | |
|---|---|
| Hinweis im Dialog vorher | „Bereit. Das kann einige Minuten dauern." |
| Dauer | **42,5 s** |
| Ergebnis | **1.588.016 Dreiecke**, wasserdicht, zwei Komponenten |
| Transaktionen danach | *Modell erzeugen* → *Auf Arbeitsgröße bringen* → *Reparaturkette* |
| Merkmale am Objekt | **0** |
| Prüfbericht | dreimal „Für die Merkmalserkennung ist dieses Modell zu groß", dazu „sehr fein vernetzt" |

Ein zweiter Lauf über denselben Backend, andere Bilddatei: 44,9 s, 1.088.166
Dreiecke, roh wasserdicht — **nach** der Eingangsstufe nicht mehr.

### 2.2 Was daraus folgt

**Die Kette funktioniert und endet in einer Sackgasse.** Ein Netz mit anderthalb
Millionen Dreiecken hat keine erkannten Merkmale, und ohne Merkmale hat der
Agent nichts, worauf er zeigen kann: Leitprinzip 5 verbietet ihm, Koordinaten
zu erfinden, also kann er an diesem Körper genau nichts tun, was mit „setz da
eine Bohrung hin" anfängt.

Der Ausweg steht im Prüfbericht — „Netz → Dezimieren" — und **niemand geht ihn**.
Die Reparaturkette läuft automatisch, das Dezimieren nicht. Das ist die
kleinste sinnvolle Änderung dieses Papiers: Wer ein Modell erzeugen lässt, will
danach damit arbeiten, nicht erst eine Operation suchen, die im Bericht als
Nebensatz steht.

**Vorschlag D1 — Dezimieren gehört in die Erzeugen-Kette.** Nach *Auf
Arbeitsgröße bringen* eine vierte Transaktion, die auf ein Ziel unterhalb der
Merkmalsgrenze bringt, sichtbar im Stapel und mit einem Klick rücknehmbar. Der
Wert kommt nicht aus dem Bauch: die Grenze, an der `perceive` abwinkt, steht im
Code und ist die Zahl, gegen die dezimiert wird.

> **Erledigt.** Die Kette hat die vierte Transaktion: *Modell erzeugen* → *Auf
> Arbeitsgröße bringen* → *Reparaturkette* → *Auf Arbeitsauflösung bringen*
> (`op="decimate_mesh"`, `app/core/generate.py:234–248`). Sie läuft, sobald das
> Netz `GENERATED_TRIANGLE_LIMIT` = 500 000 Dreiecke übersteigt, und bringt auf
> `GENERATED_TRIANGLE_TARGET` = 200 000 (`app/core/generate.py:68` und `:73`) —
> genau die Zahl, an der `FEATURE_LIMIT_TRIANGLES` steht
> (`app/core/scene/evaluate.py:72`, Prüfung `:394`). Als eigene Transaktion und
> nicht als stiller Teil der Reparatur, damit ein Undo sie zurücknimmt.
> Abgesichert durch `tests/test_way_three.py:265`
> `test_a_generated_mesh_arrives_workable` („Laden, Reparieren, Dezimieren").
> Commit `da6e821`, 12.08.2026 — „Erzeugt, repariert — und dann konnte niemand
> etwas damit anfangen"; `ROADMAP.md:4678`.

### 2.3 Anspruchsvolle Figuren

Was aus Hunyuan3D herauskommt, ist keine Kiste — die Netze tragen Falten,
Rundungen und Hinterschnitte. Was fehlt, ist nicht die Ausgabequalität, sondern
alles danach: Ohne Dezimieren keine Merkmale, ohne Merkmale keine Bohrung, kein
Baustein, keine Passung. Die Figur kommt an, sie ist nur nicht bearbeitbar.

> **Erledigt — die Sackgasse ist zu.** Seit dem 12.08.2026 dezimiert die Kette
> selbst auf 200 000 Dreiecke, und darunter greift die Merkmalserkennung: die
> Prüfung in `app/core/scene/evaluate.py:394` ist ein `>`, 200 000 liegt also
> nicht mehr darüber. Nachgerechnet am 19.08.2026 gegen eine Icosphäre mit
> 1 310 720 Dreiecken: `decimate(…, GENERATED_TRIANGLE_TARGET)` liefert exakt
> 200 000. Das Ziel ist bewusst deutlich unter der Grenze gewählt, damit eine
> spätere Boolesche Operation nicht sofort wieder darüber landet — und immer
> noch fein genug, dass die Figur ihre Falten behält
> (`app/core/generate.py:70–73`).

---

## Teil 3 — Der Blocker unter dem Erzeugen: die Lizenzen

Aus einer eigenen Recherche zu den Modellen, die hinter dem Erzeugen stehen.
**Zwei Funde betreffen den ausgelieferten Zustand unmittelbar.**

### 3.1 Hunyuan3D ist in der EU nicht lizenziert

Die Lizenz beider Fassungen trägt als Kopfzeile: *„THIS LICENSE AGREEMENT DOES
NOT APPLY IN THE EUROPEAN UNION, UNITED KINGDOM AND SOUTH KOREA"*, und
`Territory` ist ausdrücklich als „worldwide territory, **excluding** the
territory of the European Union …" definiert. Das ist keine Nutzerzahl-Grenze,
an der ein kleiner Anbieter vorbeikäme — für einen deutschen Anbieter gibt es
schlicht keine Rechtseinräumung. Eine Bitte, die EU aufzunehmen, liegt seit
Monaten unbeantwortet als Issue im Projekt.

Solidon liefert die Gewichte nicht mit, und der Nutzer installiert ComfyUI
selbst. Aber **der mitgelieferte Graph nennt das Modell**, und die Anleitung im
Handbuch nennt es auch.

### 3.2 RMBG-2.0 im Graphen ist nicht-kommerziell

`app/core/backends/data/image_to_mesh.json` setzt `"model": "RMBG-2.0"` — das
Freistellmodell steht unter **CC BY-NC 4.0**. Der zahlende Nutzer landet ohne
Zutun im nicht-kommerziellen Modell.

### 3.3 Was stattdessen geht

| Modell | Lizenz | Kommerziell | EU |
|---|---|---|---|
| **Step1X-3D** | Apache-2.0 | ja | ja |
| **TripoSG** | MIT | ja | ja |
| **TripoSR** | MIT | ja | ja |
| TRELLIS | MIT — **aber** Pipeline zieht `nvdiffrast` und `diffoctreerast`, beide ausdrücklich nicht-kommerziell | nein | — |
| Hunyuan3D 2.0/2.1/Omni | Tencent Community | — | **nein** |
| RMBG-2.0 | CC BY-NC 4.0 | **nein** | — |
| BiRefNet / InSPyReNet (Freistellen) | MIT | ja | ja |

**Vorschlag L1 — zwei Zeichenketten tauschen.** Im Graphen `RMBG-2.0` durch
`BiRefNet` oder `INSPYRENET` ersetzen und die Erzeugerrolle auf **Step1X-3D**
oder **TripoSG** umstellen. Genau dafür ist `MODEL_ROLES` in `backends/mesh.py`
gebaut: der Graph nennt die Rolle, nicht die Datei. Kein Python, keine neue
Abhängigkeit, keine Paketvergrößerung — aber ein neuer Knotensatz muss die
Rolle bedienen, und die `Hy3D*`-Knotennamen im Graphen ändern sich mit.

---

## Teil 4 — Brauchen wir ComfyUI?

**Nein, zwingend nicht — aber die Alternative ist schlechter, als sie klingt.**

| Weg | Was er kostet |
|---|---|
| **ComfyUI über HTTP** (heute) | nichts im eigenen Paket; der Nutzer installiert |
| Modell direkt in Python (`hy3dgen`, Step1X-3D, TripoSG) | PyTorch + CUDA in der Auslieferung: aus 40 MB werden Gigabyte, CUDA wird Installationsbedingung, Gewichte 10–29 GB |
| TripoSR als ONNX | der einzige wirklich schlanke Läufer, dafür das schwächste Ergebnis |
| Gehostete API (fal.ai) | 0,16 $ je Lauf ohne Textur, Nutzerschlüssel wie beim Sprachmodell |

Der externe Aufruf ist hier nicht die faule Lösung, sondern dieselbe
Entscheidung wie bei OpenSCAD und den Slicern (§36): ein GPL-Programm wird
aufgerufen, nicht mitgeliefert. **Was falsch ist, ist nicht die Architektur,
sondern die Modellwahl darin** (Teil 3).

**Vorschlag B1 — eine Rückfallebene für Rechner ohne Grafikkarte.** Ein zweiter
Backend gegen fal.ai passt ohne Umbau in das `MeshBackend`-Protokoll — zwei
Aufrufe, kein Zustand, Schlüssel im Schlüsselbund. Das ist P11 aus dem Bauplan,
nur mit einem fremden Betreiber statt einem eigenen Server.

> **Entschieden: nein** (Robert, 20.08.2026). Der Vorschlag war der letzte
> offene Punkt dieses Papiers und ist damit keiner mehr — er wird nicht
> gebaut, und zwar nicht „später", sondern gar nicht.
>
> **Was daraus folgt, gehört ausgesprochen:** Weg 3 bleibt an eine Maschine
> mit Grafikkarte gebunden. Wer keine hat, hat drei von vier Wegen. Das ist
> ab jetzt eine Grenze und keine Lücke — und Grenzen gehören auf die
> Download-Seite, wie „kein Netzwerkdruck" und „kein Apple-Zertifikat" auch.
> Die Kostentabelle darüber bleibt stehen: Sie hat die Entscheidung getragen,
> und wer sie später umdrehen will, findet dort die Zahlen.

---

## Teil 5 — Der lokale Agent: gemessen, nicht vermutet

Der Chat spricht mit Anthropic über einen eigenen Schlüssel **oder** mit Ollama
lokal. Der Agent sieht **96 Werkzeuge** (85 Operationen + 11 eigene:
`ask_user`, `undo_transaction`, `add_parameter`, `set_parameter`, `add_fit`,
`read_report`, `find_part`, `read_digest`, `read_standard`, `read_analysis`,
`set_print_target`), das Schema ist **110 KB** groß, ein Zug endet nach
höchstens acht Schritten. Gemessen wurde weiter unten bei 88 Werkzeugen und
104 KB — seither ist das Register gewachsen, die Enge also auch.

Auf dieser Maschine liegen fünf Modelle. Gemessen wurde die Stufe, ohne die
keine Antwort etwas nützt — **kommt ein strukturierter Werkzeugaufruf zurück
oder Prosa?**

| Modell | strukturiert | richtig | auffällig |
|---|---|---|---|
| `qwen3:14b` | 4/5 | **3/5** | `read_report` 121 s, `add_parameter` Zeitüberschreitung, `undo_transaction` → rief `ask_user` |

Das Urteil des Läufers: **„Brauchbar: keines."**

Das ist die ehrliche Antwort auf „was geht lokal": Die Schicht ist gebaut, die
Werkzeuge stehen, die Absicherung greift — aber kein installiertes lokales
Modell bedient die 88 Werkzeuge mit 104 KB Schema zuverlässig, die es zur
Messung waren. Zwei Minuten für einen einzigen Werkzeugaufruf sind keine
Bedienung.

**Vorschlag A1 — dem lokalen Modell weniger zumuten.** Nicht alle 96 Werkzeuge
mitschicken, sondern die zur Auswahl passenden (`applies_to` sortiert das
Kontextmenü bereits) plus die elf eigenen. Das ist kein neues Konzept, sondern
dieselbe Sortierung, die die Oberfläche schon benutzt — angewandt auf das, was
ins Modell geht.

> **Umgesetzt, aber ausdrücklich nicht so — und das ist wichtig, weil der
> Vorschlag oben in seiner Form gegen §2.6 verstößt.** Wer nach `applies_to`
> filtert, gibt dem Agenten je nach Auswahl einen anderen Werkzeugkasten:
> eine Betriebsart mit anderem Namen. Gebaut wurde deshalb das Kürzen statt
> des Weglassens — `compact=True` für Ollama
> (`app/core/agent/session.py:194`), und der Kommentar dort sagt es wörtlich:
> „``compact`` kürzt die Beschreibungen, **ohne ein Werkzeug wegzulassen**"
> (`app/core/agent/tools.py:75–82`). Wirkung heute nachgemessen: **110,2 KB →
> 86,9 KB, alle 96 Werkzeuge bleiben.** Der größte Posten waren nicht die
> Operationstexte, sondern die Parametertexte. `ROADMAP.md:4681`, Commit
> `6a3b5ad`.

**Vorschlag A2 — sagen, was Sache ist.** Wer Ollama einträgt, soll im Chat
lesen, was gemessen wurde: welches Modell hier wie oft trifft. `check_local_model`
liefert die Zahlen, sie stehen nur nirgends, wo jemand sie sieht.

> **Erledigt.** `local_model_expectation()`
> (`app/core/backends/llm.py:605`) liefert die gemessenen Zahlen, der Satz
> steht an der Chatleiste (`app/ui/main_window.py:3032`). `ROADMAP.md:4685`.

---

## Teil 6 — Meshy und Hyper3D: halten wir mit?

### 6.1 Was sie kosten und können

| | Meshy | Hyper3D / Rodin |
|---|---|---|
| Einstieg | 0 $ (100 Credits/Monat, CC BY 4.0) | 7-Tage-Test |
| Pro | 20 $/Monat (1000 Credits) | Creator 30 $ / Business 120 $ |
| Bild→3D | 20 Credits ohne, 30 mit Textur, 35 bei 8K | ~4–5 s je Modell, bis 10 Mio. Polygone |
| Dazu | Remesh 5, Rigging 5, Animation 3, 3D-Print-Reparatur 10, **Analyse gratis** | PBR, UVs, ControlNet, Teilbearbeitung, Plugins für Blender/Unity/Unreal/Maya |
| Formate | GLB/FBX/OBJ/STL/USDZ | dieselben |
| API | ab Pro | ab Business |

### 6.2 Das Urteil

**Beim Erzeugen halten wir nicht mit, und das sollten wir auch nicht wollen.**
Deren Geschäft ist das Modell: Texturen, Rigging, Animation, Teilbearbeitung,
Sekundenzeiten auf fremder Hardware. Unser Erzeugen ist ein Zulieferer für
Weg 3, kein Wettbewerber — der Bauplan sagt selbst, dass erzeugte Netze maßlich
unpräzise sind (§42).

**Wo wir stehen, wo sie nicht sind:** Meshy hat seit kurzem 3D-Print-Funktionen
(Analyse gratis, Reparatur 10 Credits, Mehrfarbe 10) — das ist genau unser
Feld, und es ist ein Warnsignal. Aber es ist ein Knopf in einem Webdienst, kein
Prüfbericht, der Inseln, Brückenweiten und Stützvolumen vor dem Slicen gegen
ein Druckerprofil rechnet, und kein Materialprofil, aus dem eine Passung ihr
Spiel zieht.

**Vorschlag M1 — anschlussfähig statt konkurrierend.** Wer mit Meshy, Tripo
oder Rodin erzeugt, lädt ein GLB herunter. Solidon liest GLB seit jeher und
schreibt es seit heute. Der Satz, der auf die Website gehört, ist nicht „wir
erzeugen auch", sondern: *bring, was du erzeugt hast — hier wird es druckbar.*

---

## Teil 7 — Oberfläche und Design gegen die anderen

Beurteilt an dem, was im Bild steht: Startbildschirm, Hauptfenster mit
geladenem Modell, Operationsdialog, Musterauswahl.

**Was trägt.** Der Startbildschirm ist kein leeres Fenster: Ablagefeld, acht
Beispiele als Kacheln mit gerendertem Vorschaubild und einem Satz, „Zuletzt
geöffnet", und der Weg ins Handbuch steht neben den Knöpfen, zu denen er
gehört. Das Hauptfenster hält die drei Zonen aus §2.5 ein und wächst nicht:
neun Menüs, sechs Werkzeuge in der Zeile unter dem Modell, links drei
einklappbare Abschnitte, rechts Bericht oder Chat.

> **Zwei Zahlen nachgezählt am 19.08.2026, eine davon war schon am 12.08.
> falsch.** Es sind **neun** Beispielkacheln (`weg4-figur-formen` kam am
> 14.08. dazu, `5a9418c`) und **acht** Werkzeuge in der Zeile — nicht sechs:
> `section · measure · transform · analysis · layers · explode · split ·
> paint`. Am Dokumentstand waren es sieben, `split` kam am 14.08. dazu; sechs
> waren es nie. Die neun Menüs und die drei einklappbaren Abschnitte stimmen.
> *Nebenbei:* Der Docstring `app/ui/start_screen.py:474` sagt weiterhin „acht
> Beispiele" und ist damit selbst veraltet. Der Operationsdialog zeigt
die gestufte Tiefe wörtlich — vorn sechs Werte, hinten „Weitere Einstellungen",
und an jedem Zahlenfeld ein `fx` für den Projektparameter.

**Was ihn von Fusion und Shapr3D unterscheidet**, im Guten: keine Betriebsarten,
keine Multifunktionsleiste mit fünfzig Symbolen, keine Anmeldung. Im weniger
Guten: kein Bewegungsgefühl. Fusion und Plasticity leben davon, dass eine
Änderung sich *anfühlt* — Vorschau am Zeiger, Werte am Objekt statt im Dialog.
Wir zeigen die Änderung nach dem Übernehmen.

**Zwei Befunde aus den Bildern:**

* **Auf sehr breiten Bildschirmen zerfällt das Verhältnis.** Bei 3413 px steht
  die linke Spalte in 160 px gedrängt — die Maßspalte im Objektbaum bricht ab
  („100 × 99,98 × 89,79 …") — während in der Mitte ein 20-mm-Würfel in einer
  leeren Fläche von zwei Metern Breite steht. Die Spalten sind für 1920 gebaut
  und wachsen nicht mit.

  > **Erledigt am selben Tag** (`f48a7e3`, 12.08.2026): Die Karten wachsen
  > anteilig mit dem Fenster, mit Deckel bei 420 und 460 px; unter etwa
  > 2000 px ändert sich nichts. Dazu startet die Anwendung seit `7fd9303`
  > (15.08.) bildschirmfüllend statt auf 1280 × 820.
* **Der Musterdialog war zweisprachig, ohne es zu wollen.** „Art: raised",
  „Auflegen: flat" — behoben, samt der 24 weiteren Auswahlwerte im Register,
  siehe `konzept-wettbewerb-2026-08.md`.

---

## Teil 8 — Handbuch gegen Meshys Doku

Meshys API-Doku hat vier Bereiche, **17 Endpunkte**, dazu Fehlercodes,
Ratengrenzen, Webhooks und eine Preisseite mit Credit-Kosten je Aufruf.

Unser Handbuch hat **35 Seiten und 19.578 Wörter**: zwanzig geschriebene über
die ersten fünfzehn Minuten, das Fenster, Zeichnen, Verlauf, Parameter,
Toleranzen, Bausteine, Chat, Fernsteuerung und ein Wörterbuch — dazu je eine
**erzeugte** Seite pro Registerkategorie, mit jeder Operation, jedem Wert,
jedem Bereich und jeder Vorgabe. Die erzeugte Hälfte kann nicht veralten.

> **Nachgezählt am 19.08.2026: 40 Seiten, 21 geschriebene und 19 erzeugte,
> rund 24.900 Wörter.** Die harte Zahl ist die Seitenzahl (`manual.pages()`);
> die Wortzahl hängt an der Zählweise.

**Der Vergleich fällt zu unseren Gunsten aus — mit einer Lücke.** Was bei Meshy
„API-Referenz" heißt, ist bei uns über zwei Orte verteilt: die
Fernsteuerungsseite erklärt MCP in fünf Absätzen, und die Werkzeuge, die
dahinter stehen, stehen in der Operationsreferenz — ohne dass ein Satz die
beiden verbindet. Wer Solidon fernsteuern will, findet nirgends „diese 88
Werkzeuge gibt es, mit diesen Parametern".

**Vorschlag H1.** Ein Absatz auf der Fernsteuerungsseite, der auf die
Registerreferenz zeigt und sagt, dass jede dort beschriebene Operation ein
Werkzeug ist. Zwei Sätze, kein neues Kapitel.

> **Erledigt, und mehr als vorgeschlagen.** Der Absatz steht
> (`app/core/manual.py:921–927`): „Jede Operation der folgenden Kapitel ist
> eines … Eine eigene Schnittstellenliste gibt es deshalb nicht." Dazu kam
> eine **erzeugte** Seite *Die Werkzeuge der Fernsteuerung*
> (`app/core/manual.py:1383`, gebaut aus `remote_tools()`) — heute **94
> Einträge**: die 96 Werkzeuge minus `create_from_scad` und `ask_user`, die
> absichtlich nicht durch die Leitung gehen (`DENIED` in
> `app/core/agent/remote.py`). Der Satz oben, man finde nirgends „diese 88
> Werkzeuge gibt es", ist damit überholt.

---

## Teil 9 — Was daraus zu tun ist

> **Abgearbeitet — der Stand am 19.08.2026, Punkt für Punkt.**
>
> | Punkt | Stand |
> |---|---|
> | 1. Viewport-Befund | hinfällig: das Messgerät hat ihn erzeugt (`ROADMAP.md:4697`) |
> | 2. L1 Zeichenketten | halb erledigt, halb bewusst verworfen (`:4671`, `:4674`) |
> | 3. D1 Dezimieren | erledigt (`app/core/generate.py:234`) |
> | 4. A1/A2 | erledigt, A1 anders: kompakt statt gefiltert (`:4681`, `:4685`) |
> | 5. M1 und H1 | erledigt, beide weiter als vorgeschlagen (`:4688`) |
> | 6. Linke Spalte | erledigt (`f48a7e3`) |
>
> **Offen ist einer, und er steht in keiner Liste:** B1 — die Frage, ob ein
> gehosteter Erzeugungsdienst als zweiter Weg neben ComfyUI treten soll.

Nach Wirkung, nicht nach Aufwand:

1. **Den Viewport-Befund verfolgen** (Teil 1). Ein Programm, dessen Bild leer
   bleibt, hat kein anderes Problem. Der Fix steht, der Nachweis fehlt.
2. **L1 — die zwei Zeichenketten im Graphen tauschen** (Teil 3). Das ist eine
   Rechtsfrage, keine Geschmacksfrage, und sie betrifft den ausgelieferten
   Stand.
3. **D1 — Dezimieren in die Erzeugen-Kette** (Teil 2). Ohne das ist Weg 3 eine
   Einbahnstraße.
4. **A1/A2 — dem lokalen Modell weniger zumuten und die Messwerte zeigen**
   (Teil 5).
5. **M1 und H1** — zwei Sätze Vermarktung, zwei Sätze Handbuch.
6. **Die linke Spalte auf breiten Bildschirmen** (Teil 7).

Was hier **nicht** steht: ein eigener Generator, ein Wettlauf um Texturen und
Rigging, ein Abo. Alles drei würde uns von dem wegführen, worin wir vorn sind.

---

*Beschlossenes wandert nach `ROADMAP.md`; der Bauplan ändert sich nur mit
Ansage.*

---

## Nachrecherchiert am 19.08.2026

Fünfzehn Aussagen dieses Dokuments über den eigenen Code nachgeprüft:
**vier stimmen, acht sind überholt, eine war falsch, zwei sind nicht
prüfbar.** Das Papier ist abgearbeitet — `ROADMAP.md:4663` führt sechs
seiner sieben Punkte mit Haken — und hat sieben Tage lang nicht davon
gewusst.

**Der gefährlichste Satz war Vorschlag A1.** In seiner ursprünglichen Form
ist er eine Anleitung zu einem Regelverstoss: Nach `applies_to` zu filtern
hätte dem Agenten je nach Auswahl einen anderen Werkzeugkasten gegeben —
eine Betriebsart mit anderem Namen, die §2.6 verbietet. Gebaut wurde
stattdessen das Kürzen der Beschreibungen: 110,2 KB auf 86,9 KB, kein
Werkzeug fällt weg. Die Begründung dagegen stand bis heute nur im Code und
in der ROADMAP.

**Was anders ausfiel als vorgeschlagen:** L1 zur Hälfte — das Freistellmodell
ist getauscht (`RMBG-2.0` unter CC BY-NC ist raus, `INSPYRENET` unter MIT ist
drin, abgesichert durch `test_the_shipped_graphs_name_no_non_commercial_model`),
der Formkern nicht: Hunyuan3D bleibt, weil ein Wechsel eine andere
ComfyUI-Knotensammlung verlangt. Stattdessen sagen Modulkopf, Handbuch und
Website, dass die Lizenz für die EU nicht gilt und welche Modelle frei sind.

**Was der Zähler überholt hat:** acht Beispielkacheln → neun · sechs
Werkzeuge in der Zeile → acht (sechs waren es nie) · 35 Handbuchseiten → 40 ·
19.578 Wörter → rund 24.900 · „88 Werkzeuge, die nirgends stehen" → 94, die
auf einer eigenen erzeugten Handbuchseite stehen.

**Offen ist genau einer:** B1, der gehostete Erzeugungsdienst als zweiter Weg.
Er steht in keiner Arbeitsliste — weder hier noch in der ROADMAP.

**Nicht prüfbar und deshalb offen gelassen:** die ComfyUI-Messung (der Dienst
läuft auf dieser Maschine nicht) und der Ollama-Lauf (die Gegenstelle
antwortet nicht). Beide Messwerte bleiben als datierte Angaben stehen.
