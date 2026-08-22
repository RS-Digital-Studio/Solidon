# Abgleich: konzept-wettbewerb-2026-08.md

**Geprüft am:** 19.08.2026 · **Dokumentstand:** 11.08.2026, Nachträge 13.08.2026
**Basis:** Arbeitsverzeichnis `C:\Users\rober\Documents\Solidon`, Zweig `main`, Stand `b0415d6`

**Zählung über 22 geprüfte Aussagen:** 9 stimmt · 9 überholt · 3 falsch · 1 unprüfbar

Das Dokument beschreibt einen Stand, der acht Tage alt ist, und acht Tage sind in
diesem Repository rund 200 Commits. Vier seiner eigenen Aussagen widersprechen
einander bereits im Text (2.8 gegen W7, 2.10 gegen W3 und gegen Teil 7 Frage 1);
eine fünfte — die Entscheidung „W9 auslassen" — war schon am Tag der Niederschrift
gegenstandslos, weil das Gebaute im selben Repository lag.

---

## 1. „77 Operationen im Register (16 davon aus der Bausteinbibliothek)"

*Ort:* 2.1 Stand; noch einmal in 2.12 („Fehlbefund")

**Urteil: überholt.**

Beleg:

```
.venv/Scripts/python.exe -c "from app.core.bootstrap import load_operations; \
from app.core.registry import REGISTRY; load_operations(); print(len(REGISTRY.all()))"
→ 85
```

Davon 17 mit Präfix `insert_`. Die Website führt die Zahl mit:
`website/index.html:150` (`<div><b>85</b><span>Operationen im Register</span></div>`),
`website/funktionen.html:408`, `website/index.html:500`. `tests/test_website.py`
prüft sie gegen das Register (159 Fälle grün, Lauf vom 19.08.2026).

Am 11.08.2026 war die Zahl richtig: `git show 345f003:website/index.html` führt
77 und 16. Die Beweisführung des Absatzes 2.12 (jeder Baustein ist zugleich eine
`insert_*`-Operation, `walk_packages` sieht sie nicht) bleibt gültig — nur die
beiden Zahlen darin sind es nicht mehr.

**Stattdessen:** „85 Operationen im Register (17 davon aus der Bausteinbibliothek)."

---

## 2. „16 Bausteine"

*Ort:* 2.7 Stand

**Urteil: überholt.** `app/core/knowledge/parts/registry.py` → `PARTS` enthält 17
Einträge; `website/index.html:151` und `:318` („Siebzehn geprüfte Bausteine")
führen dieselbe Zahl.

**Stattdessen:** „17 Bausteine."

---

## 3. „Normteile in sechs Tabellen (Schrauben, Muttern, Scheiben, Einpressbuchsen, Magnete)"

*Ort:* 2.7 Stand

**Urteil: falsch.** `app/core/knowledge/data/standards.toml` führt **acht**
Tabellen mit zusammen 40 Maßen: `screws` (7), `nuts` (7), `washers` (4),
`inserts` (6), `magnets` (5), `bearings` (4), `profiles` (3), `tubes` (4).
Der Klammerzusatz nennt fünf, der Satz behauptet sechs, im Code sind es acht.

Das galt schon am Tag der Niederschrift:
`git show 345f003:app/core/knowledge/data/standards.toml | grep "^\[\["` liefert
dieselben acht Namen, und `website/index.html` führte damals wie heute
„40 Normteilmaße hinterlegt". Die Tabellen `bearings`, `profiles`, `tubes` stehen
seit `5f9461b` (28.07.2026) darin.

**Stattdessen:** „Normteile in acht Tabellen mit 40 Maßen (Schrauben, Muttern,
Scheiben, Einpressbuchsen, Magnete, Lager, Profile, Rohre)."

---

## 4. „6 Materialien …, 16 Druckerprofile, Selbstkalibrierung über Testkörper"

*Ort:* 2.7 Stand

**Urteil: stimmt.** `materials.toml` → 6 Abschnitte, `printers.toml` → 16.
Die Testkörper liegen in `app/core/knowledge/parts/testbodies.py`.

---

## 5. „Neun Zwangsbedingungen plus `reference`, fünf Elementarten inklusive Spline, Ändern-Gruppe `trim`/`extend`/`offset`/`mirror`/`project`"

*Ort:* 2.2 Stand

**Urteil: stimmt.**

* `app/core/sketch/solver.py:50-59` — `distance`, `coincident`, `horizontal`,
  `vertical`, `parallel`, `perpendicular`, `tangent`, `symmetric`, `fixed` (neun),
  dazu `reference`, in `:65` ausdrücklich als nur messend geführt.
* `app/core/types.py:1048` — `SketchElementKind = Literal["point", "line", "arc",
  "circle", "spline"]`.
* `app/core/sketch/edit.py:141/183/213/267/363` — `trim`, `extend`, `offset`,
  `mirror`, `project`.

---

## 6. „B-Rep-Kern über OpenCASCADE installiert und aktiv, mit `fillet_edges`, `chamfer_edges`, `shell_exact`, `draft_faces`, `thread_exact`, `push_face` und fünf Skizzen-Ops"

*Ort:* 2.2 Stand

**Urteil: stimmt.**

```
.venv/Scripts/python.exe -c "from app.core.brep import kernel; print(kernel.available())"
→ True
```

`app/core/brep/ops.py` registriert `create_brep_box`, `create_brep_cylinder`,
`load_step`, `fillet_edges`, `chamfer_edges`, `shell_exact`, `draft_faces`,
`thread_exact`, `brep_to_mesh`. `push_face` liegt in `app/core/sketch/ops.py:650`
und ruft `app/core/brep/profiles.py:658 push_faces` — die Zuordnung des Konzepts
ist inhaltlich richtig, wenn auch nicht dateigenau. Fünf Skizzen-Ops:
`sketch_extrude`, `sketch_pocket`, `sketch_revolve`, `sketch_sweep`, `sketch_loft`
(`app/core/sketch/ops.py:264/356/458/528/590`).

---

## 7. „Kein gehosteter Backend (P11 offen)"

*Ort:* 2.4 Stand

**Urteil: überholt** — der Sachverhalt stimmt, das Etikett nicht.

`ROADMAP.md:839` führt P11 als `- [–] **Bewusst nicht gebaut.**` mit Begründung
(§27 knüpft die Phase an nachweisbare Nachfrage) und benennt den Auslöser, der sie
wieder öffnen würde. `app/core/backends/` enthält `mesh.py` mit `MeshBackend`
(`text_to_mesh`, `image_to_mesh`) und `scripted.py` als zweite Umsetzung.
„Offen" liest sich als Arbeitsrückstand; es ist eine getroffene Entscheidung.

**Stattdessen:** „Kein gehosteter Backend — P11 ist nach §27 bewusst nicht gebaut,
die Schnittstelle stünde bereit (ROADMAP P11)."

---

## 8. „Agenten-Suite mit 39 Referenzanfragen … 28 von 39 und 98 % der Werkzeugaufrufe, so auf der Website"

*Ort:* 2.5 Stand; Teil 4 Nachmessung W4

**Urteil: stimmt**, mit einer Ortsverschiebung.

```
.venv/Scripts/python.exe -c "from tests.agent_cases import ALL_CASES; print(len(ALL_CASES))"
→ 39
```

Die Quote steht heute nicht mehr auf der Startseite, sondern auf
`website/funktionen.html:105` („28 von 39 gut beantwortet, 98 % der
Werkzeugaufrufe") und `website/en/features.html:104`. Verschoben mit `051fdb6`
(14.08.2026), als rund vierhundert Zeilen von der Startseite auf die neuen
Funktions- und KI-Seiten wanderten. Die Startseite nennt weiterhin die
39 Referenzanfragen (`website/index.html:311`).

**Stattdessen:** ergänzen „… auf der Funktionsseite, nicht mehr auf der Startseite".

---

## 9. „Orientierungssuche über bis zu 2000 Lagen, `SettingAdvice`, getrennt von G-Code-Werten"

*Ort:* 2.6 Stand

**Urteil: stimmt.** `app/core/geom/prepare_ops.py:962-972` — Parameter
`candidates` mit `maximum=2000`, Vorgabe `DEFAULT_CANDIDATES = 200`
(`app/core/slice/orientation.py:41`). `app/core/slice/advise.py` liefert
`SettingAdvice` mit Begründung; die Trennung nach Regel 14 hält
`app/core/slice/gcode.py`.

---

## 10. „Import STL, 3MF (auch als Baugruppe), OBJ, PLY, OFF, GLB, GLTF, STEP, SVG, DXF"

*Ort:* 2.8 Stand

**Urteil: stimmt.** `app/core/geom/mesh.py:30` — `READABLE_SUFFIXES = (".stl",
".obj", ".ply", ".off", ".glb", ".gltf", ".3mf")`; `app/core/ingest/fetch.py:56`
— `EXTRA_SUFFIXES = (".step", ".stp", ".svg", ".dxf")`;
`app/core/ingest/outline.py:38` für SVG/DXF; 3MF als Baugruppe in
`app/core/ingest/ops.py:106-112`.

---

## 11. „Export STL, 3MF, OBJ, PLY, STEP" und „B4: GLB kommt herein und geht nicht hinaus — die Formatliste bestätigt es heute noch"

*Ort:* 2.8 Stand und 2.8 Urteil, dazu die Empfehlung „GLB-Export … sollte einfach passieren"

**Urteil: überholt — und Widerspruch im Dokument.**

`app/core/export/writer.py:54` — `ExportFormat = Literal["stl", "3mf", "obj",
"ply", "glb", "step"]`; `:665 _glb_bytes()` schreibt die Datei mit Namen und
Farben. Teil 4 W7 sagt genau das („erledigt — GLB-Export gebaut", Zeile 340) und
Teil 6 Punkt 3 ebenfalls; 2.8 und seine Empfehlung stehen unverändert dagegen.
Wer nur den Bereichsdurchgang liest, baut etwas nach, das steht.

**Stattdessen:** 2.8 auf „Export STL, 3MF, OBJ, PLY, GLB, STEP" setzen, den
Absatz zu B4 streichen, in der Empfehlung nur den Netzwerkdruck stehen lassen.

---

## 12. „8 Beispielprojekte, sieben Touren"

*Ort:* 2.9 Stand

**Urteil: überholt.** `ls app/examples/*.p3d | wc -l` → 9;
`website/index.html:154` führt „9 Beispielprojekte dabei". Touren:
`app/core/tour.py` → `TOURS` mit 9 Einträgen (neun `Tour(`-Aufrufe ab Zeile 163).

**Stattdessen:** „9 Beispielprojekte, neun Touren."

---

## 13. „103 Modelle durch die laufende Oberfläche geprüft ohne einen Stolperer"

*Ort:* 2.9 Stand

**Urteil: stimmt.** `ROADMAP.md:4322` — „**Ergebnis: 103 Stück, keins
gestolpert.**" Das Werkzeug dazu ist `tools/run_ui_audit.py`.

---

## 14. „Zwei Sprachen. `app/i18n/locales/` enthält genau `en.json`"

*Ort:* 2.10 Stand

**Urteil: überholt — und Widerspruch im Dokument.**

```
ls app/i18n/locales/ → en.json es.json fr.json it.json pt.json
```

Mit Deutsch als Quelle sind es sechs. Angelegt mit `6553566` (13.08.2026,
„Sechs Sprachen, und keine davon fällt mitten im Satz ins Deutsche zurück").
Teil 4 W3 (Zeile 336) und Teil 6 Punkt 2 (Zeile 397) melden das bereits als
erledigt; 2.10 behauptet daneben weiter zwei Sprachen und leitet daraus eine
Empfehlung („Sprachen zuerst, weil billig") ab, die ins Leere zeigt.

**Stattdessen:** 2.10 auf „sechs Sprachen — Deutsch als Quelle, dazu en, es, fr,
it, pt" setzen und die Empfehlung streichen.

---

## 15. „Sechs Sprachen, je 2279 Einträge, `tests/test_translations.py` (104 Fälle), Handbuch- und Website-Tests (460 Fälle)"

*Ort:* Teil 4 W3; Teil 6 Punkt 2

**Urteil: falsch** in allen drei Zahlen (die Zahl der Sprachen stimmt).

* Einträge je Katalog heute: **2647** (alle fünf identisch, gezählt über
  `json.load`). Am 13.08.2026 waren es 2366
  (`git show <letzter Commit vom 13.08.>:app/i18n/locales/es.json`), die ROADMAP
  hielt am 14.08. 2426 fest (`ROADMAP.md:4414`). 2279 findet sich an keinem
  dieser Stände — die Zahl war beim Schreiben schon überholt.
* `pytest tests/test_translations.py -q --collect-only` → **112 Fälle**, nicht 104.
* `pytest tests/test_manual.py -q --collect-only` → 47,
  `tests/test_website.py` → 43, zusammen **90 Fälle**. 460 ist keine Sammelzahl
  dieser beiden Dateien und war es auch am 13.08. nicht (43 Testfunktionen in
  `test_manual.py`, heute 44).

**Stattdessen:** „Sechs Sprachen, je 2647 Einträge, abgenommen von
`tests/test_translations.py` (112 Fälle) und mitgetragen von Handbuch- und
Website-Tests (90 Fälle)." Besser noch: die Zahlen ganz weglassen und auf den
Test verweisen — sie wandern mit jedem Katalogeintrag.

---

## 16. „Kein macOS-Paket … `build.yml`, Job „Paket": `[windows-latest, ubuntu-latest]`"

*Ort:* 2.10 Stand

**Urteil: überholt — und Widerspruch im Dokument.**

`.github/workflows/build.yml:152` —
`os: [windows-latest, ubuntu-latest, macos-13, macos-latest]`. Dazu die Schritte
„Bundle prüfen (macOS)" (`:265`), „Ohne Signatur bauen (macOS)" (`:277`),
„Signieren (macOS)" (`:286`, greift bei gesetztem `APPLE_CERTIFICATE`),
„Archiv packen (macOS)" mit `ditto` (`:306`) und getrennte Artefakte je
Architektur (`:369`). Eingebaut mit `ab6403d` (13.08.2026, „macOS wird
ausgeliefert, und ein Ordner ist dort keine Anwendung").

Teil 7 Frage 1 sagt das bereits; 2.10 nennt es weiter „den härtesten Befund des
Durchgangs". Offen ist nur noch, was `ROADMAP.md:4437-4448` benennt: das
Apple-Zertifikat und die Notarisierung — `xcrun notarytool` und `stapler` kommen
im Auftrag nirgends vor.

**Stattdessen:** 2.10 auf „macOS wird paketiert (Bundle, ICNS, Intel und Apple
Silicon getrennt); offen sind Zertifikat und Notarisierung" setzen.

---

## 17. „`marketing/video/` enthält vier fertige Filme — deutsch und englisch, quer (1080p) und hoch (1080×1920) —, dazu die eingesprochene Tonspur"

*Ort:* 2.9 Nachtrag 13.08.2026; Teil 7 Frage 4

**Urteil: unprüfbar am Repository.**

`/marketing/video/` steht in `.gitignore:25` („Die erzeugten Videos. Sie entstehen
aus `tools/make_video.py` neu"). Auf diesem Rechner existiert der Ordner nicht:
`ls marketing/` liefert nur `drehanleitung-video-1.md` und
`pressemitteilung-demo-2026-08.md`; `git ls-files marketing/` dieselben zwei.

Was belegbar ist: `tools/make_video.py` gibt es, es erzeugt quer (1920×1080) und
hoch (Fenster 1080×1340, Zielformat der Kurzvideos) je Sprache und spricht den
Ton über `speak()` ein (`tools/make_video.py:15-16, 69-78, 519, 602`). Der Satz in
2.9 „Der `marketing/`-Ordner hat bereits **Tonproben** und eine Drehanleitung" ist
dagegen falsch: dort liegt nur die Drehanleitung.

**Stattdessen:** „`tools/make_video.py` erzeugt die vier Filme (deutsch und
englisch, quer und hoch) samt eingesprochener Tonspur; die Dateien selbst liegen
unter `marketing/video/` und sind nicht im Repository (`.gitignore`)."

---

## 18. „Offen: W1 Sichtbarkeit, W2 macOS-Signierung, W5 letzte Meile"

*Ort:* Teil 4 Tabelle; Teil 6 Punkt 5; Teil 7

**Urteil: stimmt.** `ROADMAP.md:31-34` führt alle drei in der Tabelle der
wartenden Punkte, jeweils mit Anlass „Gegen das Wettbewerbsfeld gehalten
(11.08.2026)":

* Sichtbarkeit — „keine Entwicklungsaufgabe — bleibt bewusst stehen" (auch
  `ROADMAP.md:4435`),
* macOS ausliefern — „Apple-Zertifikat und Notarisierung; der Paketierschritt
  steht",
* G-Code an die Maschine senden (B3) — „eine Bauplanentscheidung, nicht auf Code".

---

## 19. „W9 Kein Weg vom Modellkatalog zu uns … **Entschieden: auslassen**; der einzige offene Arbeitspunkt ist, Ziehen und Ablegen sichtbarer zu machen"

*Ort:* Teil 4 Tabelle W9; 2.11 Stand („kein Katalogzugang"); Teil 7 Frage 3

**Urteil: falsch** — der Weg war am Tag der Niederschrift bereits gebaut, und die
Entscheidung vom 13.08. entschied damit über etwas Vorhandenes.

* `app/core/ingest/fetch.py` — angelegt mit `2e99902` vom **11.08.2026** („Der Weg
  von der Modellseite hörte am Ordner auf"). Kopfkommentar: „Der häufigste Weg,
  wie ein Modell in Solidon kommt, beginnt auf einer Modellseite — MakerWorld,
  Printables, Thingiverse. … Dieses Modul deckt den anderen Fall ab: die Adresse
  ist in der Zwischenablage, die Datei noch nirgends." Nur http/https,
  Größengrenze beim Lesen, keine Seitenauswertung.
* `app/ui/main_window.py:103, 402, 2454-2473` — *Datei → Modell aus dem Netz*,
  Herkunft in `SourceOrigin(url=…, retrieved=…)`; `app/ui/start_screen.py:324`.
* `ROADMAP.md:4395-4401` — „`[x]` **Modell aus dem Netz** (§16.3). Verweis aus dem
  Browser ablegen oder *Datei → Modell aus dem Netz* …".
* Die Startseite bewirbt es: `website/index.html:221` — „Datei ablegen — oder den
  Verweis von MakerWorld, Printables oder Thingiverse gleich aus dem Browser ins
  Fenster ziehen, ohne Umweg".

Damit ist auch der Auflagensatz aus Teil 7 Frage 3 („dann muss der Weg
,heruntergeladene Datei ziehen und ablegen' umso sichtbarer sein") eingelöst:
`ROADMAP.md:101-102` führt Startbildschirm mit Ablagefeld und Ziehen-und-Ablegen
auf Fenster, Viewport und Objektbaum als erledigt, die Startseite nennt beides in
der Hauptspalte.

**Stattdessen:** W9 aus der Liste der offenen Punkte streichen. „Der lesende
Zugriff auf eine Adresse ist gebaut (§16.3, `ingest/fetch.py`, *Datei → Modell aus
dem Netz*) und steht auf der Startseite; was fehlt, ist keine Funktion, sondern
Sichtbarkeit — also W1."

---

## 20. „Offen bleibt die Nachaufnahme der Handbuchbilder je Sprache"

*Ort:* Teil 6 Punkt 2

**Urteil: überholt.** `app/images/manual/` führt `de`, `en`, `es`, `fr`, `it`,
`pt` mit je sechs Bildern (`catalog.png`, `main-window.png`, `op-dialog.png`,
`report.png`, `sketch-mode.png`, `start-screen.png`). Angelegt mit `63c71f1`
(13.08.2026, „Vierundzwanzig Bilder, und auf jedem steht jetzt dieselbe Sprache"),
seither zweimal nachgezogen: `8e7b91f` (17.08.) und `bc0323b`/`9e5693d` (18.08.).

**Stattdessen:** Punkt 2 ohne den Zusatz — die Bilder liegen je Sprache vor.

---

## 21. „14 Tage Test, 49 € zur Einführung, später 79 €, Einmalkauf, Betrachterbetrieb; Website führt mit Weg 1; Pressemitteilung durch `tests/test_press_release.py` gehalten"

*Ort:* 2.12 Stand; Teil 4 W4; Teil 7 Frage 4

**Urteil: stimmt.**

* `app/core/activation/store.py:36` — `TRIAL_DAYS: Final = 14`, dazu
  `trial_days_left()` in `:160-187`.
* `website/index.html:382` — „Vollversion folgt zu **49 €** statt 79 € —
  einmalig"; `:404` „Hier sind es 49 € einmal."
* `website/index.html:92` — `<h1>Das heruntergeladene Teil passt nicht. Mach es
  passend.</h1>`, also Weg 1 als Aufmacher.
* `tests/test_press_release.py` — vier Fälle, darunter
  `test_the_press_text_carries_no_path_into_the_project` und
  `test_the_press_text_explains_itself_without_the_code`; grün im Lauf vom
  19.08.2026 (159 Fälle über Übersetzungen, Website und Presse).

---

## 22. „Website deutsch und englisch" (Nebenbefund, nicht in der Arbeitsmappe)

*Ort:* 2.11 Stand

**Urteil: überholt.** `website/` führt neben der deutschen Fassung `en/`, `es/`,
`fr/`, `it/`, `pt/` mit je `index.html`, `features.html`, `ai-models.html` und
`manual.html`. Die Aussage in 2.11 trägt zusätzlich „kein Katalogzugang", was
nach Punkt 19 ebenfalls nicht mehr stimmt.

**Stattdessen:** „Website in sechs Sprachen, Handbuch, Rechtstexte, Paddle als
Abwicklung, Support über eine Adresse. Keine Presse, keine Gemeinschaft."

---

## Was beim Lesen zu einer falschen Entscheidung führt

1. **2.8 lässt GLB-Export als Arbeit stehen** — er ist gebaut. Widerspricht dem
   eigenen W7.
2. **2.10 empfiehlt „Sprachen zuerst"** — sechs Sprachen liegen seit dem
   13.08. vor. Widerspricht dem eigenen W3.
3. **2.10 nennt das fehlende macOS-Paket den härtesten Befund** — es wird seit dem
   13.08. gebaut. Widerspricht Teil 7 Frage 1.
4. **W9 „auslassen"** — der Netzimport war schon am 11.08. im Baum und steht heute
   auf der Startseite. Wer die Entscheidung ernst nähme, baute etwas zurück.
5. **Alle Kennzahlen** (77/16, sechs Normteiltabellen, 8 Beispiele, sieben Touren,
   2279 Einträge, 104/460 Testfälle) sind falsch oder veraltet. Sie stehen in
   diesem Dokument als Marktargumente — auf einer Verkaufsseite wäre jede davon
   ein roter Lauf in `tests/test_website.py`.
