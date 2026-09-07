# Konzept — Doppelte Stellen und Zwillinge: finden, halten, vermeiden

Stand 07.09.2026. **Konzept und Umsetzung: P1.1, P1.2, P2.1, P2.2, P3.1 und
Entscheidung E sind am selben Tag gebaut** (Robert: „mach das beste“). Offen
bleiben die Testhilfen (P3.3, Entscheidung H), der Satz in `AGENTS.md`
(Entscheidung I, geht an Robert) und der Fund der Nachbarsitzung über die
Zwillingsregel der Oberfläche. Gemessen gegen den Arbeitsstand `d9999d1b`; die
Rohfunde und das erste Messskript liegen unter
`.claude/.state/zwillinge-2026-09-07/`, das eingecheckte Werkzeug ist
`tools/twin_scan.py`.

Anlass: Robert, 07.09.2026 — „wir wollen doppelte Stellen und Zwillinge
vermeiden, Kontrolle, Analyse und Konzept sauber und gründlich."

Bezug: Bauplan §3 („Konsistenz vor Vollständigkeit"; „Verbote sind Prüfungen,
keine Absichten"), §9 (Verträge), §10 (Konsistenztest des Registers), §16.2
(Formatversion und Migrationen), §35 (Testbarkeit); AGENTS.md Regel 7 und 8
(keine Zahlenkonstante für Toleranzen, keine Streuzahl), Arbeitsweise
„Konsistenz vor Vollständigkeit" und „Bestehende Struktur nutzen". „§" meint
hier immer den Bauplan. Der Bauplan kennt das Wort „Zwilling" nicht; die
Sache ist eine Frage der Arbeitsweise, nicht des Produkts — deshalb liegt
hier ein Konzept und keine Bauplanänderung.

Was hier steht, ist Begründung und Vorschlag. **Offene Arbeit steht im
Register von `ROADMAP.md`** unter „Doppelte Stellen und Zwillinge, gemessen
(07.09.2026)" und nirgends sonst.

---

## §0 Ist-Zustand

Jede Aussage in diesem Abschnitt ist am Code belegt oder mit dem Skript
gemessen. Wo eine Zahl steht, steht ihre Messvorschrift daneben.

### §0.1 Was „Zwilling" in diesem Projekt heißt

Der Begriff stammt aus der Durchsicht vom 27.08.2026 (ROADMAP: „Was die
Zwillingsdurchsicht in der Oberfläche liegen ließ"): **eine Auskunft, die an
mehr als einer Stelle hergeleitet wird.** Nicht jede Wiederholung von Code ist
damit gemeint, sondern jede Stelle, an der eine zweite Herleitung derselben
Sache steht — eine Zahl, eine Regel, ein Satz, eine Rechnung —, so dass ein
Nachbessern an einer Stelle die andere nicht erreicht.

Derselbe Begriff bezeichnet im Bestand auch die **gewollten** Paare: „Quader
anlegen" im Netz- und im exakten Kern (`MENU_TWINS`, `registry.py:133`), mit
dem Kriterium aus `konzepte/entscheidungen-2026-08-22.md`: *Ein Zwilling
entsteht dort, wo der Zweig ohne ihn endet — nicht dort, wo er möglich wäre.*
Beide Bedeutungen behalten das Wort; §1 trennt sie in Klassen.

### §0.2 Was schon getan wurde — und was davon liegen blieb

| Datum | Durchgang | Ergebnis | Werkzeug |
|---|---|---|---|
| 24.08.2026 | „Fünf Doppelungen, und eine hatte schon Folgen" über `app/core` (159 Dateien) | fünf zusammengelegt, davon eine mit Kundenschaden (`require_positive`) | Duplikat-Sucher, nicht eingecheckt |
| 24.08.2026 | „Was niemand las, und was zweimal dastand" | Konstanten, Texte, Sicherheitsliste `INCLUDING` als Zusicherung | Suchmuster, nicht eingecheckt |
| 27.08.2026 | Konstanten-Zwillinge (`57200cb9`), Oberflächen-Zwillinge, 26 Slicer-Namensvergleiche | `tests/test_shared_constants.py`; sieben Auskünfte zusammengelegt; ein Prädikat statt Namensvergleich | 20-Zeilen-AST-Skript, nicht eingecheckt |
| 02.09.2026 | Pfad eines offenen Handles zweimal (`_opened_file_path`, `_descriptor_path`) | im Register offen: „nicht in die Nacht vor ein Paket" | — |
| 03.09.2026 | `_too_small_to_make` nur bei drei von sechs Erkennern | Quelltext-Wächter `test_every_fitted_kind_asks_the_same_question` | — |
| 07.09.2026 | diese Messung über `app/`, `tools/`, `tests/` | siehe §0.3 | `twin_scan.py`, abgelegt unter `.claude/.state/` |

Drei Durchgänge, drei Werkzeuge, keines im Repository — die ROADMAP vom 27.08.
sagt es selbst: „Das Messskript steht in der Sitzung … und ist in zwanzig
Zeilen wieder gebaut." Es wurde wieder gebaut, am 07.09. zum dritten Mal.

### §0.3 Die Messung vom 07.09.2026

Sieben Fragen, je Baum eine Spalte. Gemessen mit `ast`, ohne Ausführung.

| Frage | `app/` | `tools/` | `tests/` |
|---|---|---|---|
| Dateien / Zeilen | 260 / 190 223 | 55 / 28 805 | 249 / 194 921 |
| Funktionen und Methoden | 5 956 | — | — |
| Konstanten auf Modulebene (Großname, fester Wert) | 958 in 931 Namen | 115 in 109 | 63 in 62 |
| 1a gleicher Name, gleicher Wert, andere Datei | **4** | 3 | 0 |
| 1b gleicher Name, **anderer** Wert | **15** | 3 | 1 |
| 1c gleicher nicht-trivialer Wert, anderer Name | 81 Werte | 7 | 0 |
| 2 wortgleiche Körper, mind. 2 Anweisungen | **12** Gruppen | 0 | — |
| 2 wortgleiche Körper, mind. 4 Anweisungen | **0** | 0 | — |
| 2 wortgleiche Körper, Zeilenmaß (4 Anw. oder 8 Zeilen samt Docstring) | 11 | 0 | 21 |
| 3 strukturgleich (Namen und Zahlen normalisiert), zusätzlich | 8 | 1 | 16 |
| 4 nahe Zwillinge (Jaccard über 6-Gramme ≥ 0,55; ab 15 Zeilen) | 10 Paare | 26 | 18 |
| 5 Zeichenketten, gegen die an ≥ 3 Stellen in ≥ 2 Dateien verglichen wird | 82 | 7 | 291 |
| 6 Kommentare, die Kopie oder Gegenstück nennen | 593 Zeilen | 31 | 310 |
| 7 gleichnamige Funktionen ≥ 8 Zeilen in mehreren Dateien | 193 Namen | 13 | 46 |

**Zwei Messfallen, an denen dieser Lauf selbst hing:**

* **Das Zeilenmaß zählt Docstrings.** Elf „wortgleiche Körper ab acht Zeilen"
  waren zur Hälfte Einzeiler unter langen Docstrings — `wants_bed_coordinates`
  und `PrintDisclosureResult.may_continue` sind beide `return True` und haben
  nichts miteinander zu tun. Gezählt werden **Anweisungen des Körpers**, und
  dann bleiben ab vier Anweisungen null Gruppen.
* **Ein Skript, das nichts findet, sieht aus wie eines, das nichts zu finden
  hat.** Ein Lauf mit Git-Bash-Pfad (`/c/Users/…`) fand unter Windows null
  Dateien und meldete null Zwillinge. Die Mindestzählung (Zeile „Funktionen:
  5 956") ist deshalb Teil des Ergebnisses, nicht Beiwerk — dieselbe
  Zusicherung, die `test_shared_constants.FLOOR` und `suite-getrennt.sh`
  tragen.
* **Ein Filter, der sich selbst ausschließt, findet nichts.**
  `tests/test_directory_docs.maps()` überspringt Pfade mit dem Segment
  `worktrees`, um fremde Arbeitsbäume auszulassen — und prüfte den absoluten
  Pfad. In einem Arbeitsbaum unter `.claude/worktrees/<name>/` schließt das
  jeden Pfad aus, auch den eigenen: null Karten (gemeldet von solidon-74,
  07.09.2026, nachgestellt mit 32 Karten, behoben). Dieselbe Familie wie die
  zwei Fallen darüber, und die unauffälligste von dreien — ein Ausschluss ist
  richtig formuliert und trifft zu viel.
* **Ein bereits aufgelöster Zwilling meldet sich weiter, und das ist die
  Kalibrierung des Verfahrens.** `viewport.sketch_view_near` und
  `axis_view_near` rufen beide `_nearest_view` mit je einer eigenen
  Richtungstabelle (`viewport.py:695` und `:710`) — die gemeinsame Rechnung
  ist dort längst herausgezogen, übrig sind zwei benannte Eingänge. Genau die
  richtige Bauart also, und das Ähnlichkeitsmaß über Namen und Rumpf zeigt
  trotzdem darauf. Wer nach Zwillingen sucht, prüft jeden Treffer daraufhin,
  ob er den **Zwilling** oder dessen **Auflösung** gefunden hat (Hinweis der
  Sitzung, die `viewport.py` hält, 07.09.2026).

### §0.4 Bewertung am Code

Zahlen sind Verdacht. Was zählt, steht hier: jeder Kandidat mit Stelle, Klasse
(§1) und dem Beleg, der die Klasse trägt.

| Fund | Stellen | Klasse | Beleg |
|---|---|---|---|
| Hohlraum oder Materie? — **zusammengelegt 07.09.2026 (P1.1)** | `geom/prepare_ops._feature_is_a_cavity:422` ↔ `perceive/relations.is_a_cavity:182` | **gehalten ohne Wächter, Begründung widerlegt** | Der Docstring in `relations.py:187` sagt, `tests/test_features.py` halte beide zusammen — **kein Test in `tests/` nennt eine der beiden Funktionen.** Er begründet die Kopie damit, die Wahrnehmung dürfe die Geometrie nicht importieren — `relations.py:36` importiert `geom.mesh`, und `prepare_ops` importiert `relations` lokal an vier Stellen (649, 947, 1066, 1392). Sieben Aufrufer in `prepare_ops`. |
| UTC-Zeitstempel — **zusammengelegt 07.09.2026 (P1.2)** | `ui/ai_disclosure._is_utc_timestamp:284` ↔ `ui/print_disclosure._is_utc_timestamp:96` | **ungewollt, bereits gedriftet** | Die eine prüft `T` im Wert und einen Versatz von null; die andere nur das `Z` am Ende. Zwei Geschwistermodule, zwei Wahrheiten darüber, was ein UTC-Zeitpunkt ist. Beim Zusammenlegen kam die zweite Hälfte dazu: Der Zeitpunkt wurde auch **geschrieben** mit wortgleicher Zeile. Gemessen ist die Drift schmaler als vermutet — nur `2026-09-03 06:00:00Z` ging durch die laxe Fassung, ein blankes Datum mit `Z` fiel bei beiden durch. |
| Pfad eines offenen Handles | `scene/project._opened_file_path:365` ↔ `updates._descriptor_path:967` | **ungewollt, bereits gedriftet** — im Register offen (02.09.) | `project.py` fragt `/proc/self/fd` **und** `/dev/fd`, `updates.py` nur `/proc/self/fd`; die eine wirft `OSError`, die andere gibt `None`. Der Kommentar in `updates.py:991` nennt die andere Stelle als „Zwillingsstelle" — und hat den Unterschied nicht bemerkt. |
| TOML- und SCAD-Literal | `knowledge/calibration._literal:165` ↔ `knowledge/parts/scad._literal:61` | ungewollt, klein | Wortgleich; zwei Kommentare mit zwei Anlässen für dieselbe `json.dumps`-Zeile. |
| Verdeckung und Kontaktschatten | `ui/viewport.ambient_occlusion:4323` ↔ `contact_shadows:4467` | ungewollt, klein — **aber nur die Bedingung** | Beide `return self._map is None`; der zweite Docstring sagt „Dieselbe Ausnahme wie bei der Umgebungsverdeckung". Die Regel „aus, solange eine Karte läuft" hat keinen Namen; ein `_a_map_is_showing` gibt ihr einen. **Die zwei Eigenschaften bleiben zwei** (Einwand der Sitzung, die `viewport.py` hält, 07.09.2026): „soll die Verdeckung gelten" und „soll ein Kontaktschatten liegen" sind verschiedene Fragen, die heute dieselbe Antwort haben und morgen auseinandergehen können. Wer nur die Bedingung benennt, löst den Zwilling; wer die Eigenschaften zusammenlegt, erfindet einen. |
| Themenfarben zweier Karten | `ui/survey.SurveyNotice.set_theme:319` ↔ `ui/viewport.PreviewBanner.set_theme:2610` | naher Zwilling (0,89), **Ort steht schon fest** | Beide bauen ihr Stylesheet nach demselben Muster aus `THEMES`; die Unterschiede sind Regel-18-Aussagen und keine Zufälle — gestrichelt heißt vorläufig, durchgezogen ist eine Fläche, und `muted` gegen `disabled` ist ein gemessener Kontrastwert. **Keine gemeinsame Basisklasse:** Die Farbzuweisung der Karten steht in `overlay.card_stylesheet`, und deren Docstring trägt den Umzug schon vor — „Wo das hingehört: nach ``style.py``, zu den übrigen Formregeln" (`overlay.py:234`). Das ist der Sammelpunkt, wenn jemand ihn baut (Hinweis der Sitzung, die `viewport.py` hält, 07.09.2026). |
| Zwillingsregel der Oberfläche | `ui/panels.py:1665` (bedingt) ↔ `ui/panels.py:1626` und `ui/selection_operations.py:55` (unbedingt) | **ungewollt, zwei Regeln statt zweier Schreibweisen** | Der Kern gibt die Rohmenge und verweist die Zusammenlegung an die Oberfläche (`surfaces.context_menu`); dort steht sie dreimal, zweimal in derselben Datei. Die bedingte Fassung trägt im Docstring die Begründung, warum die unbedingte spurlos verschwinden lässt. Gemessen halten heute alle drei (78 von 80 in der Körpermenge, kein Unterschied), weil bei allen vier Paaren beide Seiten dieselbe `consumes`-Klasse haben. Gemeldet von der Sitzung, die den Code hält, 07.09.2026; hier nachgemessen. |
| Ladeanimation | `ui/loading.py` `EASING`, `FRAME_MS` ↔ `ui/splash.py` | **ungewollt** (Oberfläche) | Gleiche Werte 0,18 und 16; `loading.py` sagt im Docstring „Zwei Wartezeiten, eine Sprache" und teilt die Sprache trotzdem nicht. |
| HiDPI-Überabtastung | `ui/icons.OVERSAMPLING:44` ↔ `ui/manual_window.OVERSAMPLING:432` | ungewollt (Oberfläche) | Gleicher Wert, gleicher Grund in beiden Kommentaren („franst auf HiDPI aus" / „Matsch auf HiDPI"). |
| Wartefrist beim Schließen | `ui/generate_dialog.WAIT_MILLISECONDS:73` ↔ `ui/support_dialog.WAIT_MILLISECONDS:81` | ungewollt (Oberfläche) | Wortgleicher Kommentar über beiden. |
| Farbe „verworfen" | `ui/chat.DISCARDED_COLOUR:53` ↔ `ui/panels.UNDONE_COLOUR:627` | ungewollt (Oberfläche) | Der Kommentar bekennt: „dieselbe wie für einen verworfenen Chatbeitrag, und aus demselben Grund" — genau der Verweis, den `test_shared_constants.py` im Docstring als „keine geteilte Sache" benennt. |
| Slicer-Familie als Name | `export/handover.py:1218, 1894, 2364`; `ui/print_settings_dialog.py:4343, 4354` | **Namensvergleich statt Prädikat** — Rest der Serie vom 27.08. | Alle fünf meinen „nimmt ein Maschinen- und ein Prozessprofil"; `slicer_keys.takes_a_machine_profile:910` steht dafür bereit. `handover.py:564` ist ein Verteiler-Wörterbuch und bleibt. Der Registerpunkt vom 27.08. ist abgehakt. |
| `MAX_PROJECT_PARAMETERS` | `knowledge/parts/shared.py:56` = 128 ↔ `scene/project.py:112` = 10 000 | **Namenszwilling**, beide öffentlich, beide `Final` | Zwei Sachen (Parameter eines Rezepts, Parameter einer Projektdatei), ein Name; `from … import MAX_PROJECT_PARAMETERS` sagt nicht, welche. |
| `TIMEOUT_SECONDS` ×8, `FORMAT_VERSION` ×3, `MAX_WORKERS`, `FALLOFF`, `_FLAT_ENOUGH` … | 15 Namen | Namenszwillinge, je Modul eine eigene Sache | `_FLAT_ENOUGH` ist 0,866 (Filmscharnier, `parts/ops.py:431`) und 0,966 (Wortwahl eines Hinweises, `sketch_editor.py:199`) — verschieden und beide richtig. Modulprivat und damit nicht importierbar. |
| Mesh/B-Rep-Paare | `MENU_TWINS`, drei Paare | **gewollt**, mit Kriterium und Tests | `test_brep.py:829` prüft `DrillParams` mit `is`; `:1198` prüft, dass jedes Paar dieselbe Frage gleich beantwortet. |
| Migrationen 5→6 bis 19→20 | `scene/migrations.py`, zehn Funktionen `return data` | **gewollt** (§16.2, Checkliste „Dateiformat ändern": Migrationen werden nie zusammengefasst) | Jeder Schritt trägt im Docstring, warum er strukturell nichts ändert. |
| Slicer-Prädikate | `export/slicer_keys.py:878–980`, fünf Funktionen `return flavour == "orca"` | **gewollt**: eine Eigenschaft je Funktion | Entscheidung 27.08.: heute geben alle dieselbe Antwort; der Preis fällt an, wenn ein Fork in einer Eigenschaft abweicht — dann ändert sich eine Zeile statt elf. |
| Protokollmethoden | `LLMBackend.complete`, `MeshBackend.text_to_mesh`, `Renderer.add_surface` … | gewollt (`...`) | Verträge nach §9. |
| Neu / Beispiele | `ui/main_window.action_new:4256` ↔ `action_examples:4270` | gewollt, begründet | Zwei Menüorte, eine Handlung, beide Docstrings sagen warum. |
| Dialogmuster | `FirstRunDialog`/`InstallDialog` `_survey_done`, `wait_for_survey`; drei `set_room`; `ExampleTile`/`StartActionCard` `enterEvent`, `leaveEvent`, `focusInEvent` | Musterwiederholung, zwei bis drei Anweisungen | Nur mit Mixin oder Basisklasse auflösbar; ein Mixin für drei Zeilen kostet mehr, als es spart. |
| Zufall | `wants_bed_coordinates` ↔ `may_continue` | keiner | Beide `return True` — siehe Messfalle Zeilenmaß. |
| Gleiche Rechnung, zwei Formen | `sketch/edit.arc_through:542` ↔ `sketch/profile.arc_through:575` | **fachlicher Zwilling**, maschinell unsichtbar | Beide bestimmen den Umkreis durch drei Punkte; Ähnlichkeit 0,05 bei gleicher Mathematik, verschiedene Rückgaben (Mittelpunkt und Endpunkte gegen Mittelpunkt, Radius und Bogen). |
| Schlüsselpaar | `tools/make_licence_keys._new_keypair:221` ↔ `tools/sign_version.new_keypair:59` | ungewollt, klein, sicherheitsnah | Strukturgleich; zwei Zielorte (`activation/key.py`, `updates.py`), ein Erzeuger würde reichen. |
| Testhilfen | `_freeform_patch` 45 Zeilen in `test_cone_fit_quality.py:15` und `test_torus_fit_quality.py:15`; `on_the_bore_wall` 20 Zeilen ×2; `run` 15 Zeilen ×4; `_opened_by`, `_placed`, `with_a_body`, `window` … | Testhilfen-Zwillinge, 21 Gruppen | Geteilte Module gibt es (`tests/render_fakes.py`, `tests/scripted_backend.py`); die Kopien entstehen je Datei. Ein Fix am Prüfstand erreicht eine Kopie — der Fall `size_for_thread` vom 24.08. war genau das. |
| Plattform als Literal | `'darwin'` 18×, `'win32'` 15×, `'nt'` 17× | **gewollt** | mypy liest `sys.platform == "darwin"` und prüft den Zweig je Plattform (`--platform darwin`); ein Prädikat davor machte den Rest dort zu totem Code — `project.py:397–404` begründet es. |
| Merkmalsart als Literal | `'face'` 34× in 15 Dateien, `'hole'` 20× in 10, `'thread'` 17× in 6 | Muster, kein Zwilling je Stelle | Wo hinter dem Vergleich eine **Frage** steht (Hohlraum? rund? durchgehend?), gehört ein Prädikat hin — `is_a_cavity` ist eines. Wo eine Verteilung steht, bleibt das Literal. |
| Befundcode als Literal | `'perceive.orphaned'` 9× (`panels.py` 7, `agent/checks.py` 2) | Muster | Eine Konstante würde neun Stellen an einen Namen binden. |

**Und die Grenze des Verfahrens, an einem Fund gemessen, den es nicht gefunden hat.**
Die Zwillingsregel der Oberfläche steht in zwei Formulierungen — eine bedingte und
eine unbedingte —, und keine der sieben Fragen zeigt darauf: Zwei verschieden
geschriebene Fassungen derselben Regel haben weder Wortgleichheit noch
Strukturgleichheit, und ihre Konstante steht bei beiden. Gefunden hat sie jemand,
der den Code geschrieben hat. **Ein Skript findet Kopien; eine Regel in zwei
Fassungen findet nur, wer die Sache kennt** — deshalb bleibt die Durchsicht durch
einen Menschen oder eine Sitzung mit Gebietskenntnis der Hauptweg, und das
Werkzeug ist ihr Zubringer und nicht ihr Ersatz.

**Der Befund vorweg, weil er das Konzept trägt:** In `app/` gibt es heute
**keinen** wortgleichen Funktionskörper ab vier Anweisungen. Die Durchgänge
vom 24. und 27.08. haben den großen Funktionszwilling beseitigt. Was blieb,
ist von zwei Sorten: **klein und strukturell** (Dialogmuster, Einzeiler) oder
**bereits auseinandergelaufen** — und die zweite Sorte findet eine Suche nach
Wortgleichheit nicht mehr. Die zwei gefährlichsten Zwillinge dieses Laufs
(Zeitstempel, Pfad) sind beide gedriftet und beide für einen
Wortgleichheits-Wächter unsichtbar.

### §0.5 Die Kontrolle heute

| Prüfung | Was sie hält | Was sie nicht sieht |
|---|---|---|
| `tests/test_shared_constants.py` | Konstanten in `app/core`: gleicher Name, gleicher Wert; `FLOOR = 300` (gemessen 412 am 27.08.); `DELIBERATE` leer | **nur `app/core`** — die vier Oberflächenfälle aus §0.4; **gleicher Name, anderer Wert** — der Fall, der den Test am 27.08. veranlasst hat (`BOOLEAN_OVERLAP` 0,05 gegen 0,01), ist bis heute nicht abgedeckt; gleicher Wert unter anderem Namen bewusst nicht (81 Werte, fast alle verschiedene Sachen) |
| `test_features.test_every_fitted_kind_asks_the_same_question` | eine Konstante wird an einer Stelle verglichen | Einzelfall |
| `test_brep.test_the_exact_bore_and_its_twin_read_the_same_parameters` | ein Schema, geprüft mit `is` | Einzelfall |
| `test_brep.test_every_twin_pair_answers_the_same_question_the_same_way` | die gewollten Paare verhalten sich gleich | — |
| `test_mesh_backend.test_the_sizes_in_the_progress_text_match_the_constants` | Zahl im Text gegen Konstante | Einzelfall |
| `test_interface_limits` (Thema und Navigation) | Menü und Einstellungsdialog lesen dieselben Listen | Einzelfall |
| `test_translations` | jeder Text hat in fünf Katalogen einen Eintrag — Textdrift wird ein unübersetzter Schlüssel | fängt Texte, nicht Logik |
| `test_registry_consistency`, `test_lazy_exports`, `test_install` („und nirgends sonst") | Kürzel-Dubletten, drei Listen je Lazy-Paket, Kennungen je Verwaltung | Einzelfälle |
| Funktionskörper | **keine Prüfung** | — |
| Ein Kommentar, der einen Wächter behauptet | **keine Prüfung** | der Phantom-Wächter aus §0.4 |
| Werkzeug für die Durchsicht | **keines eingecheckt** | jede Durchsicht baut neu |

Zusammengefasst: Die Kontrolle besteht aus einem allgemeinen Wächter mit zwei
Lücken und einem Dutzend Einzelwächtern, die je einen Vorfall festhalten. Das
ist die richtige Bauart für Vorfälle (Bauplan §3: Verbote sind Prüfungen) —
aber niemand prüft die **Klasse** der Fälle, nur ihre Vertreter.

### §0.6 Warum Zwillinge hier entstehen

Aus den Fällen in §0.4 und der ROADMAP, je mit dem Fall, der es belegt:

1. **Eine Grenze als Vorwand, die keine ist.** „Die Wahrnehmung darf die
   Geometrie nicht importieren" — sie tut es längst. Wer eine Schichtregel
   vermutet, statt sie nachzulesen, kopiert. (`is_a_cavity`)
2. **Zwei Anlässe, zwei Sitzungen, ein Problem.** Die Pfadfunktion entstand
   einmal für die Projektdatei und einmal für das Update; `_too_small_to_make`
   entstand am Vormittag und fehlte am Nachmittag bei drei Erkennern. Wer
   parallel arbeitet, findet die Nachbarstelle nicht, weil sie noch nicht
   committet ist — oder weil er nicht danach sucht.
3. **Der Kommentar fühlt sich wie Teilen an.** „Dieselbe wie … aus demselben
   Grund" ist ehrlich und wirkungslos: Er wandert beim nächsten Anfassen nicht
   mit. Vier Oberflächenkonstanten tragen ihn.
4. **Der Name statt der Eigenschaft.** `== "orca"` meint jedes Mal etwas
   anderes und sieht jedes Mal gleich aus; 26 Stellen am 27.08., fünf heute.
5. **Das Geschwistermodul entsteht aus dem ersten durch Kopieren.**
   `print_disclosure` aus `ai_disclosure`, `splash` und `loading`,
   `InstallDialog` und `FirstRunDialog` — das zweite Modul nimmt die
   Hilfsfunktion mit statt sie herauszuziehen.
6. **Jede Testdatei bringt ihre Fixture mit**, weil sie allein lauffähig sein
   soll. 21 wortgleiche Gruppen in `tests/`.

---

## §1 Vier Klassen, und jede hat eine Pflicht

Das Wort bleibt, die Klasse entscheidet, was zu tun ist.

| Klasse | Definition | Pflicht | Beispiel |
|---|---|---|---|
| **gewollter Zwilling** | dieselbe Handlung in zwei Rechenkernen oder zwei bewusst getrennten Fassungen | ein **Kriterium**, das sagt, wann er entsteht, und ein **Test**, der beide auf dieselbe Frage gleich antworten lässt | `MENU_TWINS`; Migrationen; Slicer-Prädikate |
| **gehaltener Zwilling** | eine Kopie, die aus einem am Code belegten Grund nicht zusammengelegt werden kann | Eintrag in einer **kuratierten Liste** mit dem Grund; ein Wächter prüft, dass beide Stellen **wortgleich** bleiben; der Grund muss am Code stimmen | heute: keiner — `is_a_cavity` scheidet aus, weil sein Grund nicht stimmt |
| **ungewollter Zwilling** | dieselbe Auskunft zweimal hergeleitet, ohne Kriterium und ohne Grund | **zusammenlegen**; bis dahin ein Registerpunkt | Zeitstempel, Pfad, vier Oberflächenkonstanten |
| **Namenszwilling** | ein Name, zwei Sachen | **umbenennen**, wenn beide öffentlich sind; sonst erlaubt | `MAX_PROJECT_PARAMETERS` umbenennen; `_FLAT_ENOUGH` bleibt |

Dazu zwei Nachbarn, die keine Zwillinge sind und trotzdem gefunden werden:
**Musterwiederholung** (drei Zeilen, die drei Dialoge gleich tun — auflösen nur,
wenn eine Abstraktion ohnehin entsteht) und **fachlicher Zwilling** (dieselbe
Rechnung in zwei Formen — nur von Hand zu finden, und nur beim Anfassen der
Stelle zusammenzulegen).

---

## §2 Entscheidungen

**A — Die Klasse steht am Fund, nicht am Gefühl.** Jeder gemeldete Zwilling
bekommt eine der vier Klassen aus §1 mit Beleg, bevor jemand ihn anfasst. Ein
gewollter Zwilling ohne Test und ein gehaltener ohne Listeneintrag sind
ungewollte.

**B — Ein Kommentar ist kein Wächter.** „`tests/test_x.py` hält beide
zusammen" gilt nur, wenn dieser Test existiert und beide Stellen beim Namen
nennt — sonst ist der Satz zu streichen und die Kopie ein ungewollter
Zwilling. Für gehaltene Zwillinge steht die Zusicherung nicht im Kommentar,
sondern in einer **Liste im Test** (`HELD_TWINS`, Paare qualifizierter Namen
mit Grund), und der Test prüft die Wortgleichheit der Körper. Vorbild ist die
Entscheidung vom 24.08. zu `INCLUDING`: „Die Liste ist jetzt die Zusicherung."
Die Liste entsteht **mit dem ersten Eintrag**, nicht auf Vorrat — ein Test über
eine leere Menge hält nichts (`.claude/rules/tests.md`).

**C — Der Konstanten-Wächter wächst über den Kern hinaus und bekommt eine
zweite Zusicherung.** `test_shared_constants.py` liest künftig `app/` statt
`app/core` (die vier Oberflächenfälle sind dann rot, bis sie zusammengelegt
sind) und meldet zusätzlich **öffentliche** Namen, die in mehreren Dateien mit
**verschiedenem** Wert stehen — der Fall vom 27.08., gegen den er gebaut wurde.
Modulprivate Namen (`_X`) mit verschiedenem Wert bleiben erlaubt: Sie sind
nicht importierbar, also nicht verwechselbar. `FLOOR` wird an der neuen
Grundmenge gemessen (958 gefunden → `FLOOR = 700`), `DELIBERATE` bleibt
kuratiert mit Grund je Eintrag.

**D — Kein Tor-Wächter für wortgleiche Funktionskörper.** Gemessen: null
Gruppen ab vier Anweisungen, zwölf Kleinstfälle darunter, und die zwei
gefährlichen Zwillinge dieses Laufs sind gedriftet und für Wortgleichheit
unsichtbar. Ein Wächter, der zwölf Dreizeiler meldet und die zwei echten
Fälle übersieht, kostet jede Sitzung Zeit und hält niemanden. Funktionszwillinge
werden mit dem **Werkzeug** (E) gesucht, je Durchsicht und vor einem Release,
nicht je Commit.

**E — Das Werkzeug wird eingecheckt, mit Mindestzählung und Selbsttest.**
Dreimal neu gebaut ist zweimal zu oft. `twin_scan.py` wandert nach `tools/`
als Durchsicht-Werkzeug (Karte `tools/CLAUDE.md`, Familie „Messen und
Prüfen"), mit den beiden Zusicherungen aus `ROADMAP-ARCHIV.md` (24.08.):
*Zähle zuerst, wie viel du gefunden hast, und lass den Lauf scheitern, wenn es
zu wenig ist* — und *gib dem Werkzeug einen Fall, dessen Ausgang du kennst*.
Der Selbsttest (`tests/test_twin_scan.py`) fährt es über einen kleinen
Baum mit einem gepflanzten Zwilling und einer gepflanzten Konstante und
verlangt beide Funde. Bis Robert entschieden hat, liegt das Skript unter
`.claude/.state/zwillinge-2026-09-07/` — wie die Messskripte der anderen
Durchsichten, und mit derselben Warnung: Es belegt seine Zahl nur unverändert.

**F — Der Name weicht dem Prädikat, wo eine Eigenschaft gemeint ist.**
`== "orca"` wird `takes_a_machine_profile(flavour)`, wie am 27.08. begonnen.
**Nicht** bei Plattformen — `sys.platform == "darwin"` ist die Form, die mypy
je Plattform prüfen kann, und ein Prädikat davor macht den Zweig auf der
anderen Plattform zu totem Code (`project.py:397–404`). **Nicht** bei
Verteilern (ein Wörterbuch oder ein Dreiwege-`if`, dessen Zweige verschiedene
Dinge tun). Bei Merkmalsarten gilt: ein Prädikat je **Frage** (`is_a_cavity`),
nicht je Art.

**G — Beim Geschwistermodul wird zuerst geteilt, dann kopiert.** Wer ein
zweites Modul nach dem Muster eines ersten anlegt (zweite Hinweisseite, zweite
Wartezeitanzeige, zweiter Dialog mit Arbeiter), zieht vorher heraus, was beide
brauchen — an einen Ort, den es schon gibt: `app/ui/motion.py` für
Bewegungskonstanten, `app/ui/labels.py` für Texte, auf die sich mehrere Teile
einigen müssen, `app/ui/leash.py` für das Warten auf Arbeiter. Keine neue
Regeldatei, ein Satz in `.claude/rules/oberflaeche.md` beim Abschnitt über
geteilte Auskünfte.

**H — Testhilfen ab zehn Körperzeilen in zwei Dateien wandern in ein geteiltes
Modul** — `tests/render_fakes.py` und `tests/scripted_backend.py` zeigen den
Ort. Kein Tor-Wächter (Robert, 02.09.2026: „Tests das Nötigste"), sondern eine
Frage im Durchsicht-Werkzeug (Abschnitt 2 über `tests/`), je Release.

**I — Suchen vor Schreiben, und nach der Sache, nicht nach dem Namen.** Wer
eine Hilfsfunktion oder Konstante neu anlegt, sucht zuerst nach dem, was sie
tut — nach den Wörtern, die ihr Kommentar tragen würde („HiDPI", „Wartefrist",
„Deskriptor") — und nicht nach dem Namen, den er ihr geben will. Die Lehre steht
schon in der ROADMAP (25.08.: „Eine Lücke im Katalog ist erst eine, wenn man
nach der Sache gesucht hat und nicht nach dem Namen"); sie fehlt in der
Arbeitsweise von `AGENTS.md`. **Das ändert die Hausordnung und geht an
Robert.**

---

## §3 Kontrolle: was ins Tor gehört und was in die Durchsicht

| Frage | Ort | Warum dort |
|---|---|---|
| Konstante mit gleichem Namen und Wert in zwei Dateien (`app/`) | **Tor** (`test_shared_constants.py`) | eindeutig, billig, null Rauschen — vier Funde heute, alle echt |
| Öffentliche Konstante mit gleichem Namen und verschiedenem Wert | **Tor** (dito, zweite Zusicherung) | der Fall vom 27.08.; `DELIBERATE` trägt die begründeten Ausnahmen |
| Gehaltene Zwillinge bleiben wortgleich | **Tor** (`HELD_TWINS`, sobald es einen gibt) | die Liste ist die Zusicherung |
| Wortgleiche und strukturgleiche Funktionskörper | **Durchsicht** (`twin_scan.py`, Abschnitte 2 und 3) | heute null echte Fälle ab vier Anweisungen; die Klasse muss am Code entschieden werden |
| Nahe Zwillinge, gedriftete Paare | **Durchsicht** (Abschnitt 4 und 7: gleichnamige Funktionen in verschiedenen Dateien) | beide echten Fälle dieses Laufs kamen aus Abschnitt 7, nicht aus 2 |
| Literale, gegen die oft verglichen wird | **Durchsicht** (Abschnitt 5) | Plattform-Literale sind gewollt; die Klasse steht am Fund |
| Kommentare, die eine Kopie bekennen | **Durchsicht** (Abschnitt 6) | 593 Zeilen, die meisten erklären Nachbarschaft, nicht Kopie — ein Lesefilter, kein Test |
| Testhilfen doppelt | **Durchsicht** über `tests/` je Release | Entscheidung H |

Der Grundsatz dahinter, aus `.claude/rules/tests.md`: Eine Zeile, deren
Entfernen nichts rot macht, prüft nichts — und ein Test, der zwölf Dreizeiler
meldet, wird in vier Wochen mit `DELIBERATE`-Einträgen stillgestellt und
prüft dann auch nichts mehr.

---

## §4 Umsetzungsplan — commit-fähige Pakete

Jedes Paket endet mit grünem Lauf der betroffenen Tests
(`tools/affected_tests.py <dateien> --run`), ein Commit je Paket, das Tor vor
dem Commit. Umfang S = eine Datei und ihr Test, L = mehrere Dateien oder ein
neuer Test, XL = Plattformcode oder CI.

| Paket | Inhalt | Umfang | Verifikation | Stand |
|---|---|---|---|---|
| **P1.1** ✔ | Hohlraum-Zwilling: `prepare_ops` ruft `relations.is_a_cavity` (lokaler Import wie an vier Nachbarstellen), sieben Aufrufer, `_feature_is_a_cavity` fällt; der Docstring in `relations.py` verliert den Satz über den Test, den es nicht gibt | S | `affected_tests.py app/core/geom/prepare_ops.py app/core/perceive/relations.py --run`; danach null Treffer für `_feature_is_a_cavity` | **gebaut 07.09.2026** |
| **P1.2** ✔ | Zeitstempel: eine `_is_utc_timestamp`, die **strengere** (`T` und Versatz null); Ort: das Modul, das das andere schon importiert — sonst `app/ui/labels.py` nicht, sondern ein kleines gemeinsames `disclosure`-Hilfsmodul; beide Tests fahren gegen dieselbe Funktion | S | `test_ai_disclosure.py`, `test_print_disclosure.py`; ein Test mit `2026-09-07T10:00:00Z` und mit `2026-09-07 10:00:00Z` (das zweite muss in beiden Modulen dasselbe ergeben) | **gebaut 07.09.2026**, in `app/ui/settings.py`; die Erzeugung war derselbe Zwilling und ist mit umgezogen |
| **P1.3** | Pfadfunktion: eine Funktion in `app/core/paths.py` (dort stehen die Plattformzweige schon), `project` und `updates` rufen sie; die beiden Fehlerformen (werfen gegen `None`) werden **eine** mit Begründung; `/dev/fd` in beiden | XL | `test_project.py`, `test_updates.py`, `test_hard_rules.py`; der Mac-Fall aus dem Tag-Lauf 0.3.0 als Test; **ein Tag-Lauf in der CI** auf allen drei Plattformen | offen (Registerpunkt vom 02.09.) |
| **P2.1** ✔ | Konstanten-Wächter auf `app/`; die vier Oberflächenfälle zusammenlegen: `EASING`/`FRAME_MS` nach `ui/motion.py`, `OVERSAMPLING` bleibt in `ui/icons.py` und `manual_window` importiert, `WAIT_MILLISECONDS` an den Ort des Wartens (`ui/leash.py`), `UNDONE_COLOUR`/`DISCARDED_COLOUR` als **ein** Name im Thema | L | `test_shared_constants.py` grün **ohne** neuen `DELIBERATE`-Eintrag; `FLOOR` neu gemessen; Fensterdateien `test_ui.py`, `test_chat_ui.py` einzeln | **gebaut 07.09.2026**, ohne neuen `DELIBERATE`-Eintrag |
| **P2.2** ✔ | Zweite Zusicherung (gleicher Name, anderer Wert, öffentlich); `MAX_PROJECT_PARAMETERS` in `parts/shared.py` wird `MAX_RECIPE_PROJECT_PARAMETERS` oder Ähnliches; für `TIMEOUT_SECONDS` ×8 und `FORMAT_VERSION` ×3 die Entscheidung: umbenennen (`LLM_TIMEOUT_SECONDS` …) oder `DELIBERATE` mit Grund „je Modul eine eigene Frist" | L | `test_shared_constants.py`; Gegenprobe: Test rot mit dem alten Stand von `BOOLEAN_OVERLAP` (0,05 und 0,01 gepflanzt) | **gebaut 07.09.2026**; `MAX_PROJECT_PARAMETERS` heißt in `parts/shared.py` jetzt `MAX_DOCUMENT_PARAMETERS`, zwölf Namen stehen mit Grund in `DIFFERENT_ON_PURPOSE` |
| **P3.1** ✔ | Slicer-Rest: fünf `== "orca"` auf `takes_a_machine_profile` und Nachbarn; `handover.py:564` bleibt als Verteiler | S | `test_handover.py`, `test_print_settings_ui.py`; danach `grep '== "orca"'` nur noch in `slicer_keys.py` | **gebaut 07.09.2026** — drei Stellen gestellt, zwei bleiben mit Begründung: es sind drei Eigenschaften und nicht eine |
| **P3.2** ✔ | Werkzeug `tools/twin_scan.py`: Anweisungszählung statt Zeilen, Windows-Pfad-Falle als Mindestzählung, `--baum app|tools|tests`; Selbsttest mit gepflanztem Fall; Karte `tools/CLAUDE.md`; Erwähnung in `/roadmap` oder `/pruefen`? — **nein**, in keinem Skill: je Durchsicht von Hand | L | `tests/test_twin_scan.py` (gepflanzter Zwilling gefunden; leerer Baum ist ein Fehler, kein Ergebnis) | **gebaut 07.09.2026** — und der Selbsttest hat die Mindestgröße von vier auf drei korrigiert, sonst hätte das Werkzeug seinen eigenen Anlassfall verpasst |
| **P3.3** | Testhilfen: `_freeform_patch`, `_placed` (Kegel/Torus), `on_the_bore_wall`, `run` ×4, `_opened_by` in geteilte Module | L | die betroffenen Testdateien, Testzahl vorher und nachher gleich | wartet auf H |
| **P3.4** | Kleinstfälle beim Anfassen der Datei mitnehmen, kein eigener Commit: `_literal` ×2, `ambient_occlusion`/`contact_shadows` (ein `_a_map_is_showing`), `_new_keypair` ×2 | S | die Tests der jeweiligen Datei | beim nächsten Anfassen |
| **P4** | Ein Satz in `AGENTS.md` Arbeitsweise (Entscheidung I) und einer in `.claude/rules/oberflaeche.md` (Entscheidung G) | S | `test_directory_docs.py` | **Robert** |

Reihenfolge: P1.1 und P1.2 zuerst (beide S, beide beheben einen Fund, der
heute schon falsch ist oder es morgen sein kann), dann P2.1 (schließt die
Lücke, durch die die vier Oberflächenfälle kamen), dann P2.2 und P3.1. P1.3 nur
mit CI-Lauf, nicht vor einem Paket (Entscheidung 02.09. bleibt).

### §4.1 Leitplanken

* **Koexistenz:** Kein Paket ändert Verhalten, das der Kunde sieht. Der
  Nachweis dafür ist der vom 24.08.: Register, Schemata und Texte vor und
  nach dem Umbau zeichengleich (`load_operations()` und Kataloge), Testzahl
  je Gruppe erklärt.
* **Erwartete Inkonsistenz:** Zwischen P2.1 (Wächter auf `app/`) und dem
  Zusammenlegen ist der Wächter rot — beides gehört in **einen** Commit.
* **Nicht-Ziele:** keine Massenumbenennung der 15 Namenszwillinge, die
  modulprivat sind; kein Mixin für die Dialogmuster; kein Prädikat für
  Plattformen; keine Änderung an `MENU_TWINS` oder den Migrationen; kein
  Umbau der 82 Literalvergleiche außer dort, wo eine Frage dahintersteht.
* **Rückfall:** P1.3 kann jederzeit auf zwei Funktionen zurück, solange der
  CI-Lauf fehlt; P2.1 auf `CORE` zurück mit den vier Fällen als
  Registerpunkten — nicht als `DELIBERATE`-Einträgen, denn die wären der
  Kommentar, der sich wie Teilen anfühlt.

---

## §5 Was Robert entscheidet

**Wie viele es sind, sagt das Register und nicht dieser Abschnitt.** Hier
standen vier Punkte, die Kopfzeile im Index sprach von drei, und das Register
führte eine — drei Zahlen für dieselbe Sache, alle drei am 07.09.2026
geschrieben. Das ist der Fehler dieses Konzepts in seiner eigenen Währung.
Die Liste unten bleibt als **Inhalt** der Fragen; ob eine noch offen ist,
steht im Register von `ROADMAP.md`.

1. **E — das Werkzeug:** `tools/twin_scan.py` mit Selbsttest, oder Wegwerf-
   Skript unter `.claude/.state/` wie bisher. Empfehlung: `tools/`, weil drei
   Durchsichten es neu gebaut haben und die vierte es wieder täte.
2. **H — Testhilfen:** eine Durchsicht der 21 Gruppen je Release, oder gar
   nicht. Empfehlung: einmal jetzt für die fünf großen (ab 15 Körperzeilen),
   danach nur beim Anfassen.
3. **I — der Satz in `AGENTS.md`:** „Suchen vor Schreiben, nach der Sache."
   Empfehlung: ja, ein Satz unter Arbeitsweise neben „Bestehende Struktur
   nutzen".
4. **P2.2 — `TIMEOUT_SECONDS` ×8:** umbenennen oder als Ausnahme mit Grund
   führen. Empfehlung: Ausnahme mit Grund — acht Fristen sind acht Sachen, und
   der Name sagt im Modul, was er meint.

Alles andere fällt unter die Vollmacht für Bedienung und Qualität und kann
ohne Rückfrage gebaut werden.

---

## §6 Abnahme

* `tests/test_shared_constants.py` liest `app/`, meldet gleiche Namen mit
  verschiedenem Wert bei öffentlichen Konstanten, und ist grün ohne neue
  `DELIBERATE`-Einträge für die vier Oberflächenfälle.
* `grep -rn "_feature_is_a_cavity" app/` liefert nichts; `relations.py`
  behauptet keinen Test mehr, den es nicht gibt.
* `_is_utc_timestamp` steht einmal in `app/ui/`.
* `grep -rn '== "orca"' app/` trifft nur `slicer_keys.py`.
* Das Werkzeug (falls E ja) findet seinen gepflanzten Fall und meldet einen
  leeren Baum als Fehler.
* Die Registerpunkte unter „Doppelte Stellen und Zwillinge, gemessen
  (07.09.2026)" sind abgehakt oder mit Entscheidung und Datum stehen
  geblieben. **Zwei sind es am 07.09.2026:** der Hohlraum-Zwilling und die
  Zeitstempelprüfung. Die dritte Zeile der Abnahme (`grep` auf
  `_feature_is_a_cavity`) ist damit erfüllt — der Name steht nur noch als
  Geschichte im Docstring von `is_a_cavity`.

---

## §7 Übergabenotizen

* Das Messskript zählt in seiner abgelegten Fassung **Zeilen samt Docstring**
  (Abschnitte 2 und 3). Wer es wieder fährt, liest die Zahl „ab vier
  Anweisungen" aus dem Nachlauf im Kopf der Rohdatei oder baut die Zählung
  auf `stmts` um (P3.2). Die Tabellen in §0.3 nennen beide Maße.
* Unter Windows nimmt das Skript einen **Windows-Pfad** (`C:/…/app`), keinen
  Git-Bash-Pfad — sonst findet `rglob` nichts und meldet null Zwillinge.
* Der Pfad-Zwilling ist im Register unter „Die CI kam zum ersten Mal bis zum
  Ende (02.09.2026)" geführt; der Drift-Beleg (nur eine Fassung fragt
  `/dev/fd`) steht hier in §0.4 und im neuen ROADMAP-Abschnitt, der alte
  Punkt ist unverändert.
* **Der Richtungswächter des Kerns trägt den Umbau.** Im Baum liegt
  unverfolgt `tests/test_core_package_direction.py` (fremde Arbeit, von keiner
  Sitzung beansprucht) — eine Wache über die Importkanten zwischen den
  dreizehn Kernpaketen, mit dem Ist-Zustand als erster Zeile. Die Kante
  `geom → perceive` steht dort bereits als **träge**; P1.1 zieht also keine
  neue Abhängigkeit, sondern nutzt eine vorhandene an einer fünften Stelle.
  Gefahren am 07.09.2026 gegen den gebauten Stand: 4 passed, Exit 0.

* Die Nachbarsitzungen sind am 07.09.2026 informiert und haben gegengeprüft;
  drei Funde liegen in fremdem Gebiet und sind dort gemeldet:
  `viewport.ambient_occlusion`/`contact_shadows`, `SurveyNotice.set_theme`
  gegen `PreviewBanner.set_theme` und die drei wortgleichen `set_room`.

* **Zwei gemeldete Funde sind nach Prüfung keine, und das steht hier, damit
  die nächste Messung nicht wieder darauf zeigt.** Ein verworfener Fund, dessen
  Verwerfung niemand aufschreibt, wird dreimal gemeldet und dreimal richtig
  verworfen.

  `sketch_editor._needs_phrase`, `_does_phrase` und `_constraint_label` sind
  strukturgleich, weil drei Wörterbücher über dieselben zwölf Bedingungsarten
  dieselbe Form haben — und tragen drei verschiedene Auskünfte:
  `.claude/rules/zeichenflaeche.md` verlangt sie ausdrücklich als je **eine**
  Quelle, gelesen an mehreren Stellen (Zeile 244 für den fehlenden Hinweis,
  Zeile 459 bis 464 für die Wirkung an vier Stellen). Das ist das Gegenteil
  eines Zwillings; es ist die Bauform, die dieses Konzept empfiehlt.

  `viewport.sketch_view_near` und `axis_view_near` sind Gegenstücke mit
  verschiedenen Richtungstabellen — drei Zeichenebenen gegen sechs
  Achsenblicke. Der Docstring nennt den Grund: von hinten zuzusehen ist so gut
  wie von vorn, eine rückseitige Zeichenebene läge gespiegelt zu ihrem Namen.

* **Ein Kandidat wartet auf einen Commit, nicht auf eine Entscheidung.** Die
  Nachbarsitzung meldet am 07.09.2026, dass `panels.operations_for_feature`
  (committet, `panels.py:1645` aus `8db1cbdb`) und ein neues
  `selection_operations.feature_operations` beide über `applies_to` filtern —
  mit verschiedenem Zweck: Das Kontextmenü legt Zwillinge zusammen, das Panel
  wirft zusätzlich den Bausteinkatalog heraus. Ihre Frage ist, ob eine
  gemeinsame Funktion in `registry/surfaces.py` beide bedienen kann.

  Kein Registerpunkt, solange die zweite Hälfte nicht committet ist: Ein Fund
  über Code, den es in `main` nicht gibt, beschreibt einen Zustand, der sich
  bis zum Commit ändert. Nach der Klassenlehre aus §1 ist es
  **Musterwiederholung mit verschiedenem Zweck** und kein Zwilling — eine
  gemeinsame Funktion trägt nur, wenn der Unterschied ein *Parameter* wird und
  nicht ein `if` im Kern; sonst entsteht die halbe Vereinheitlichung, die
  schlechter ist als keine (§0.2, Fall vom 03.09.).

* **Zwillinge entstehen weiter, und zwar heute.** Am 07.09.2026 haben zwei
  Sitzungen unabhängig voneinander je einen zusammengelegt — diese hier die
  Hohlraumfrage und die Zeitstempelprüfung, die Nachbarsitzung eine doppelt
  gerechnete Kameradrehung in ihrem eigenen Umbau. Das ist das Argument für
  Entscheidung E: Ein Werkzeug, das jede Sitzung neu baut, findet nur, was die
  Sitzung ohnehin gerade ansieht.
