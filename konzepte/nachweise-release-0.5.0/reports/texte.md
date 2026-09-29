# Paket „texte" — Durchsicht vor Solidon 0.5.0

Arbeitsbaum `F:\3D Druck.review-050\wt-texte`, Basis `29dcefa4` (detached).
Dieser Bericht ist fortlaufend geschrieben, in zwei Blöcken: dem ersten
(Preise, Generator, README-Version, Rechtstexte) und einem zweiten, größeren
Block auf ausdrücklichen Auftrag „gesamten Rest vollständig abarbeiten".

## Gelesener Umfang

- `AGENTS.md`, `CLAUDE.md` (Root), `website/CLAUDE.md`,
  `.claude/rules/oberflaeche.md` (Abschnitt Texte).
- Memory: `nicht-nach-ki-klingen.md`, `kurze-texte-in-der-app.md`,
  `kundentexte-sagen-version.md`, `aus-kundensicht-perfekt.md`,
  `verkaufsphase-preise-und-demo-zahlen.md` (Stand 20.09., durch Roberts
  Ansage vom 23.09.2026 überholt).
- `reports/dienste.md`, `reports/sollliste*.md` vollständig für die
  angeforderten Fundstellen.
- `app/branding.py`, `app/ui/main_window.py` (`_build_menus`, Hilfe-Menü,
  Export-Tooltip), `app/ui/survey.py`, `app/core/feedback.py`
  (`MAX_INVITATIONS`), `website/api/activation_common.php` (Lizenzarten),
  `website/ki-modelle.html` (Referenztext TripoSG/SDXL), `changelog/de.md`,
  `app/core/perceive/actions.py` (`fillet_blocked`), `app/ui/labels.py`
  (Kuppel/Kehle/Hohlkehle-Namen), `app/core/knowledge/parts/testbodies.py`
  (Toleranz-Testkörper), `app/core/export/writer.py` (Exportformate),
  `app/core/header.py`-Kommentar (Filament nicht mehr in der Kopfzeile),
  `app/core/geom/colour_ops.py` (`slots_from_texture`), SECURITY.md,
  SECURITY-INCIDENT.md, `website/security.html` und alle fünf
  Sprachfassungen, `app/core/manual.py` (Seite „Zeichnen" und Glossar),
  `ROADMAP.md` (RM-084, RM-088).

## Geändert je Datei — Block 1 (Preise, Generator, Version, Recht)

**Preise (RM-182, Entscheidung Robert 23.09.2026):**
- `marketing/presse-0.5.0/05-t3n.eml`, `22-computerbase.eml`, `VERSAND.html`
  (synchron nachgezogen): „Einmalkauf in drei Stufen" → zwei Lizenzarten mit
  den neuen Zahlen (privat 69 €/99 €, gewerblich 199 €/249 €, Umstellung
  Februar).
- Website nennt aktuell keinen Preis („wird vor dem Angebot veröffentlicht")
  — kein Widerspruch, keine Änderung nötig.

**Generator RM-003 (Startseite an KI-Seite angleichen):**
- `website/index.html` und alle fünf Sprachfassungen: Weg-3-Filmkarte,
  Abschnitt „Wenn das Modell aus einem Generator kommt", Systemvoraussetzungen
  — von „lädt kein bestimmtes Modell" auf „richtet TripoSG/SDXL auf Wunsch
  ein, lädt nichts ungefragt, Lizenzkette wird geprüft".
- `README.md`: „MIT-Lizenz — Quelltext wie Gewichte" → „Lizenz- und
  Herkunftskette der Gewichte wird derzeit geprüft".

**README — Version:**
- Absatz „nach Veröffentlichung von 0.4.2" war doppelt falsch (Website bei
  0.4.4, genannte Funktionen bereits in 0.4.3 draußen) → auf 0.4.4/0.5.0 und
  echte 0.5.0-Neuerungen umgestellt.

**Rechtstexte (Freigabe bei Robert, siehe unten):**
- `DATENSCHUTZ.md`, `EULA.md`: Menüpfad „Hilfe → Installation" → „Hilfe →
  Zusätzliche Programme …"; Fragebogen „bis zu dreimal" → „einmal je
  Version"; EULA §9 um zwei fehlende Netzwege ergänzt (Modell-Direktdownload,
  Einrichtung von Zusatzprogrammen/KI-Modellen) und den Update-Download
  ergänzt.

## Geändert je Datei — Block 2 (vollständiger Rest)

**1. Sicherheit (RM-091/RM-165) — geprüft, keine Textänderung nötig.**
`SECURITY.md`, `SECURITY-INCIDENT.md`, `website/security.html` und alle fünf
Sprachfassungen bereits konform: Meldeweg ausschließlich über
`support@solidon3d.de`, Antwortfrist zwei Arbeitstage klar benannt, keine
Belohnung/Bug-Bounty erwähnt, kein PGP behauptet. `SECURITY-INCIDENT.md`
benennt die offenen Punkte (EU-Login, Vertretung, Probelauf) bereits ehrlich
als unerledigte Checkliste mit Datum — nichts erfunden, nichts beschönigt.
Keine Änderung vorgenommen.

**2. Agentenquote (Website, alle sechs Sprachfassungen):**
`website/funktionen.html`, `website/{en,es,fr,it,pt}/features.html`:
„Stand 08.08.2026 … 28 von 39" → „Stand 22.09.2026 … 24 von 39" (Zahl von der
Koordination vorgegeben, Messung 22.09.).

**3. Übertrag v0.4.1:**
- **Flächennamen im Handbuch:** `app/core/manual.py` Zeile ~483 nennt
  „Oberseite", „Vorderseite", „Rechte Seite" — deckt sich mit
  `app/core/scene/placement.py SIDE_NAMES`. Kein Fund, keine Änderung nötig.
- **Slicer-Begriff es/fr/pt vereinheitlicht auf „slicer"** (Mehrheit,
  123–135 gegen 27–29 Stellen; auch der Slicer selbst heißt so): ersetzt in
  `app/i18n/locales/{es,fr,pt}.json` (29/29/27 Stellen), `changelog/{es,fr,pt}.md`
  (inkl. Pluralformen und einem dritten Fremdbegriff „laminador" in der
  portugiesischen Fassung), `website/{es,fr,pt}/index.html` und
  `features.html`.
- **Italienisch Du/Lei:** Bestand gezählt (50 „tu"-Marker, 0 „Lei"-Marker in
  Katalog und Website) — bereits vollständig einheitlich, keine Änderung.
- **Portugiesische Anführungszeichen:** 52 Paare „…" (Kurvzeichen) auf «…»
  vereinheitlicht (198 Paare Mehrheit) in `app/i18n/locales/pt.json`.
  **Nebenwirkung:** Eine dieser 52 Stellen ist ein Label innerhalb der
  code-gezeichneten Abbildung „texture" (`app/core/figures.py:_texture`,
  Satz „Der Schalter „Auflegen“ …"); die dadurch veraltete SVG-Referenzdatei
  unter `website/handbuch/pt/` ist **nicht** neu erzeugt worden (Vorgabe:
  Handbuchseiten erst beim Release über `tools/make_manual.py`) — ein
  einzelner Testfall bleibt deshalb bewusst rot, siehe „Läufe".

**4. Sollliste-Punkte (Einzelheiten in `reports/sollliste*.md`):**
- **B13/B12** (`website/funktionen.html`): „Im Kontextmenü einer Fläche
  stehen …" → „Der Katalog rechts kennt …" (Kontextmenü trägt seit 11.09.
  keine Operationen mehr, `panels.py:2375-2403`).
- **B11c**: Formelbeispiel `schraube_m4 + spiel` (von `expressions.py`
  abgewiesen, Namen brauchen `@`) → `=@schraube_m4 + @spiel`; „vorn zwei bis
  drei Werte" (60 von 136 Ops haben 4–8 Felder) entschärft zu „die Werte, die
  man wirklich ändert"; „Menü, Kontextmenü, Kommandozeile und Chat" →
  „Menü, Kommandozeile und Chat" (Kontextmenü trägt keine Ops mehr).
- **B32**: „Zwölf Schritte" Elektronikgehäuse → „13 Schritte" (Schritt 13
  seit `05645f54`) in `website/index.html` und allen fünf Sprachfassungen.
- **B23**: „offene Fläche verdicken" → „mit „Offene Fläche schließen" eine
  Fläche zum Körper machen" (echter Op-Titel, `mesh_ops.py:1500`).
- **B16**: „fragt Solidon3D nach" → „setzt … zur Vorschau auf die größte nach
  oben zeigende Fläche" (`placement_flow.py:2289-2295`, kein Dialog).
- **B3**: „kein Vieleck" um den Zusatz „am exakten Körper oder Modell"
  ergänzt (gilt so nicht für STL/3MF, die facettiert bleiben).
- **B34** (`README.md`): „Teil wählen → rechts Prüfstück erzeugen" →
  „Bohrung, Zapfen oder Fläche wählen → rechts Prüfstück erzeugen"
  (`applies_to=["hole","pin","face"]`, `prepare_ops.py:11222`).
- **B26/B27**: nach Prüfung **nicht geändert** — „ein Schritt" (Formsitzung)
  und „Fett/Kursiv nur 6 von 8 Schriften" sind eng genug gefasst bzw. an
  anderer Stelle nicht als Blankoversprechen zu lesen; als Grenzfall im
  Register belassen, siehe „Offen".
- **README-Namen**: „Hilfe → Solidon3D unterstützen …" stimmt bereits mit
  `APP_NAME`/Menü überein — keine Änderung nötig.
- **Presse A16**: **nicht bearbeitet** — 25 Presse-Entwürfe behaupten „aus
  dem Netz wird ein exakter Körper", was es nicht gibt (keine
  Netz→exakt-Umwandlung, STEP-Export nur am exakten Körper). Zu groß und zu
  heikel für eine mechanische Textkorrektur in diesem Schritt; Versand ist
  ohnehin durch `marketing/presse-0.5.0/README.md` gesperrt, solange RM-188
  offen ist. Bleibt offen, siehe unten.
- **Kehle/Kuppe**: `website/funktionen.html`, `website/index.html` und alle
  fünf Sprachfassungen — „Kehlen und fließende Übergänge bleiben davon
  ausgenommen" war zu pauschal (`fillet_blocked` erlaubt Kehlen/Verrundungen,
  die erkennbar eine Kante ersetzen; nur tangentiale Übergänge sind sicher
  gesperrt) → präzisiert. `changelog/de.md:71` „Kuppe" → „Kuppel" (einzige
  Stelle im Deutschen, die vom sonst durchgängigen App-Begriff „Kuppel"
  abwich; andere Sprachfassungen waren schon konsistent).
- **Leistungszahlen (A23)**: **nicht bearbeitet** — die Liste in
  `sollliste-A-merkmale.md` nennt zehn einzelne Zahlenbelege, die alle gegen
  eigene Messläufe verifiziert werden müssten; außerhalb des Zeitrahmens
  dieses Schritts. Bleibt offen.
- **C2**: Bildunterschrift/Alt-Text zu `report.png` in `website/funktionen.html`
  und allen fünf `features.html` beschrieben ein anderes Bild (falsche
  Fehler-/Warnungszahlen, erfundene Zitate) — per Bildsichtung korrigiert auf
  den tatsächlichen Screenshot (Dose mit Deckel, 0 Fehler/1 Warnung/4
  Hinweise, echte Sätze).
- **C9** (Analogon „Widerspruch 9"): „die Kopfzeile nennt, was die Szene
  trägt" — Kopfzeile zeigt seit einer bewussten Entscheidung (Kommentar in
  `app/ui/header.py`) kein Filament mehr → in `website/funktionen.html` und
  allen fünf `features.html` auf „der Filamentbereich links zählt, welcher
  Körper welche Spule trägt" umgestellt.
- **C12-Namen (Teil)**: „Toleranzleiter" → „Toleranz-Testkörper" (echter
  Bausteinname, `testbodies.py:195`) in `website/funktionen.html`,
  `website/en/features.html` und `README.md`. GLB fehlte in der
  Export-Aufzählung — ergänzt in `app/ui/main_window.py` (Exportieren-Tooltip,
  alle fünf Kataloge nachgezogen) und in `website/index.html` plus allen fünf
  Sprachfassungen (Feature-Liste „Deine Projekte bleiben lesbar").
  **Nicht bearbeitet:** Auto-Split/Automatisch-teilen-Benennung,
  Materialart/Typ, exakter Menüname „Drucken vorbereiten", „Überhangwinkel je
  Schicht" — niedrige Priorität, siehe „Offen".
- **Widerspruch #10** (Weg 3 „teilt oder verstiftet bei Bedarf",
  „Farben … Zahl, die wirklich in der Maschine steckt"): geprüft, **keine
  Änderung** — das Verstiften selbst passiert (`split_pinned` erzeugt
  Passstifte), nur die separate `Fit`-Verknüpfung fehlt (das ist C8, ein
  Code-, kein Textbefund); die Filamentzahl ist ein einstellbarer Parameter
  „so viele, wie eingelegt sind" und damit korrekt als Gegensatz zu einer
  festen Höchstzahl beschrieben.

**5. RM-088/RM-084 (`ROADMAP.md`):** Fortschrittsnotizen ergänzt, **beide
Punkte bleiben unangehakt** — siehe „Offen" unten für die Begründung.

**6. Git-log-Suche v0.4.0..HEAD nach falschen Abwesenheitsversprechen:**
Stichprobenartig durchgeführt (gezielte Grep-Muster auf `website/`,
`README.md`, keine erschöpfende Commit-für-Commit-Analyse). Die dabei
gefundenen echten Treffer sind alle oben unter Punkt 4 aufgeführt (B13/B12
Kontextmenü, C9 Kopfzeile/Filament, Kehle/Verrundung). Kein weiterer Fund.

**7. Ollama-Zahlen:** `reports/dienste.md` trägt bis zum Ende dieser Sitzung
**keine** Zeile „Ollama-Messwerte" (Paket „dienste" lief parallel, letzter
Stand: Endlauf `suite_final.txt` „läuft", Ergebnis nicht eingetragen). Die
Website-Zahlen „16 GB, 17 s" sind gegen den letzten *abgeschlossenen*
Messwert in `dienste.md` (Median 17 s, RTX 4080 16 GB) geprüft und **nicht**
veraltet — keine Änderung. Die Agentenquote (Punkt 2 oben) wurde separat von
der Koordination vorgegeben (24/39, 22.09.) und ist unabhängig von der
Ollama-Messwerte-Zeile übernommen worden.

## Handbuchquelle `app/core/manual.py` — Seite „Zeichnen" und Glossar

Auf Anweisung des Pakets „skizze" (`reports/skizze.md`, „Für andere Gebiete")
vollständig als **ein** Katalogschlüssel neu übersetzt (Regel „Übersetzung
neu statt flicken"), alter Schlüssel entfernt, neuer in allen fünf Katalogen:

1. Nach der Ebenenwahl neuer Absatz „**Eine eigene Ebene.**" (*Neue Ebene …*
   im Ebenenfeld: parallel versetzt, gekippt, durch drei Punkte; Abstand als
   Projektparameter).
2. Veraltetes Zitat „Vier Freiheitsgrade sind noch frei" → „Noch 4 Maße
   fehlen, dann wackelt nichts mehr" (deckt sich mit der tatsächlichen
   Statuszeile `sketch_editor.py:1818`), an **beiden** Stellen (Seite
   „Zeichnen" und Glossareintrag „Freiheitsgrad").
3. *Projizieren*-Satz ergänzt um *Flächenkontur* (neuer Knopf, RM-188 P3.4:
   Rand der Fläche unter der Zeichnung, außen und um jedes Loch, als Kreis an
   einer erkannten Bohrung; fest und als Hilfslinie, Kopie ohne Mitlauf bei
   späteren Körperänderungen).

Terminologie für *Flächenkontur*/*Neue Ebene …* aus dem Patch des Pakets
„skizze" übernommen (`reports/skizze.final.patch`: EN „Face outline"/„New
plane …", ES „Contorno de cara"/„Nuevo plano …", FR „Contour de
face"/„Nouveau plan …", IT „Contorno della faccia"/„Nuovo piano …", PT
„Contorno da face"/„Novo plano …") — sobald das Paket „skizze" nach `main`
zieht, sind Wortlaute deckungsgleich.

Zusatzauftrag „gleich groß (Längen und Radien)": `website/funktionen.html`
(~Z. 255) und `website/index.html` (~Z. 656) samt allen fünf
Sprachfassungen (`features.html`/`index.html`) — „gleiche Länge(n)" ersetzt,
App bleibt bei „Gleich groß" (Bedingung gilt Längen **und** Radien; Robert-
Entscheidung im skizze-Bericht).

## Rechtsstellen für Roberts Freigabe

1. `DATENSCHUTZ.md` — Menüpfad „Hilfe → Zusätzliche Programme …" statt
   „Hilfe → Installation".
2. `DATENSCHUTZ.md` — Fragebogenhäufigkeit „einmal je Version" statt
   „bis zu dreimal".
3. `EULA.md` §9 — dieselbe Häufigkeitskorrektur.
4. `EULA.md` §9 — zwei neue Aufzählungspunkte (Modell-Direktdownload,
   Einrichtung von Zusatzprogrammen/KI-Modellen) und eine Ergänzung beim
   Update-Punkt (nennt jetzt auch den Programm-Download).

## Läufe

- `tests/test_website.py`, `tests/test_translations.py -m "not windowed"`,
  `tests/test_language_rules.py`, `tests/test_manual.py -m "not windowed and
  not rendered"`, `tests/test_changelog.py`, `tests/test_directory_docs.py`,
  `tests/test_plan_references.py` zusammen: **1858 passed, 1 failed, 80
  deselected** (`reports/_run_block5.txt`, Exit 1).
  Der eine Fehlschlag ist bekannt und dokumentiert:
  `test_the_drawn_figures_are_the_ones_the_code_draws[pt]` — durch die
  portugiesische Anführungszeichen-Vereinheitlichung (Punkt 3 oben) ist die
  eingecheckte `website/handbuch/pt/texture(-dark).svg` und
  `sketch-uses(-dark).svg` gegenüber dem Code veraltet. Gegenprobe: am
  unveränderten Stand (`git stash`) läuft derselbe Test grün
  (`reports/_check_pt_baseline.txt`). Neu erzeugen ist Aufgabe von
  `/erzeugen` beim Release (`tools/make_manual.py`), nicht dieses Pakets.
- `ruff check .`: All checks passed — Exit 0 (`reports/_run_ruff2.txt`).
- `ruff format --check .`: 1205 files already formatted — Exit 0
  (`reports/_run_ruffformat2.txt`).
- `mypy app/ui/main_window.py app/core/manual.py`: Success — Exit 0
  (`reports/_run_mypy.txt`) — die beiden einzigen mit echtem Code
  geänderten Dateien (Export-Tooltip-Text, Handbuchseite).
- Frühere Einzelläufe (Block 1 und Zwischenstände) in
  `reports/_run_website.txt`, `_run_translations.txt`,
  `_run_language_rules.txt`, `_run_manual.txt`, `_run_changelog.txt`,
  `_run_docs_plan.txt`, `_run_ruff.txt`, `_run_ruffformat.txt`,
  `_run_block3.txt`, `_run_block4.txt`, `_run_manual_after.txt` — alle
  Exit 0.

## Offen

- **RM-084**: nicht abgehakt. Diese Sitzung deckt die in `sollliste*.md`
  benannten Einzelstellen, Preise, Generatoraussage, Sicherheit, Agentenquote
  und die Sprachkonsistenz-Punkte ab — das ist kein erschöpfender
  Zeile-für-Zeile-Durchgang durch jeden Anwendungs- und Websitetext, wie die
  Abnahme „systematisch … verbleibende Stellen" verlangt. Fortschritt in
  `ROADMAP.md` vermerkt.
- **RM-088**: nicht abgehakt — die Abnahme verlangt „freigegebene
  Formulierung" der Verständlichkeitsregel selbst; das ist Roberts
  Regelentscheidung, keine Textkorrektur. Vermerkt, dass die Slicer-Ausnahme
  in der Praxis (Punkt 3) bereits gesetzt ist.
- **Presse A16** (Kernversprechen „Netz → exakter Körper" in 25 Entwürfen):
  nicht bearbeitet, siehe oben — Versand ohnehin gesperrt (RM-188 offen).
- **Leistungszahlen (A23)**: zehn Einzelbelege im Changelog/in der Presse
  nicht gegen eigene Messläufe verifiziert.
- **C12 restliche Namen**: Auto-Split/Automatisch teilen, Materialart/Typ,
  exakter Menüname „Drucken vorbereiten", „Überhangwinkel je Schicht" —
  niedrige Priorität, nicht geprüft.
- **B26/B27**: als Grenzfälle geprüft, aber nicht geändert (siehe oben);
  bei Bedarf erneut ansehen.
- **C8** (`split_pinned` legt keine Fit-Beziehung an): echter Softwarebefund,
  kein Textproblem — gehört einem Code-Paket, nicht „texte".
- Kein neuer Katalogschlüssel blieb ohne Übersetzung: `test_translations.py`
  lief nach jedem Block grün.
