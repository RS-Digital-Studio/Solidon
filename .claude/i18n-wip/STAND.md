# Stand der Mehrsprachigkeit (W3) — 13.08.2026

**Das hier ist keine Ablage für immer.** Dieser Ordner ist eine
Zwischenstation für vier Katalogdateien, die noch nicht vollständig sind.
Sobald `app/i18n/locales/es.json`, `fr.json`, `it.json` und `pt.json`
jeweils vollständig und von `tests/test_translations.py` grün abgenommen
sind, wird dieser ganze Ordner gelöscht — er gehört nicht zur Anwendung.

## Warum er trotzdem im Repository liegt

Acht Hintergrund-Agenten haben parallel übersetzt (zwei je Sprache, je
eine Hälfte von 2264 Katalogeinträgen). Der Claude-Code-Prozess ist mitten
im Lauf neu gestartet worden — ein Modellwechsel über `/model` beendet den
Prozess, und Hintergrund-Agenten sterben mit. Ihr Zwischenstand lag nur im
session-eigenen Scratchpad-Verzeichnis, das laut Systemvorgabe
session-spezifisch ist und nicht garantiert überlebt. Er ist deshalb hier
gesichert, damit ein zweiter Abbruch nichts mehr kostet.

## Ist-Stand, exakt nachgezählt (13.08.2026, 2264 Einträge gesamt)

| Sprache | fertige Einträge | fehlend | fehlende Bereiche (Index, 0-basiert) |
|---|---|---|---|
| Italienisch (`it`) | 1720 (76 %) | 544 | 680–1131, 2172–2263 |
| Spanisch (`es`) | 960 (42 %) | 1304 | 480–1131, 1612–2263 |
| Französisch (`fr`) | 760 (34 %) | 1504 | 440–1131, 1452–2263 |
| Portugiesisch (`pt`) | 680 (30 %) | 1584 | 360–1131, 1452–2263 |

Die Zahlen sind gemessen, nicht fortgeschrieben: `make_locale.py` meldet die
fehlenden Bereiche, wenn es nicht schreiben kann. Wer die Tabelle ändert, hat
sie vorher laufen lassen.

Jede Sprache hatte zwei Agenten (Hälfte A: Index 0–1131, Hälfte B: Index
1132–2263) — beide Hälften brechen mitten im jeweiligen jeweiligen
Arbeitsblock ab, keine Sprache ist in nur einer Hälfte fertig.

Die vorhandenen Teile liegen unter `es/`, `fr/`, `it/`, `pt/`, je Datei
`part-NNNN.json` = ein JSON-Array `[{"i": <Index>, "t": "<Übersetzung>"}, …]`
für die 40 Einträge ab Index `NNNN`. Geprüft (Parsebarkeit, keine
doppelten/leeren Werte) — siehe „Wie weiter" unten.

## Wie weiter

1. **Fehlende Bereiche übersetzen.** Für jede Sprache mit den obigen
   Lücken neue Blöcke erzeugen:
   ```
   .venv\Scripts\python.exe .claude\i18n-wip\dump_chunk.py <START> <ENDE>
   ```
   (Beide Skripte fanden ihre Wurzel anfangs über einen absoluten Pfad des
   Rechners, auf dem sie entstanden sind — auf einem zweiten Rechner liefen
   sie damit gar nicht. Sie leiten sie jetzt aus der eigenen Lage ab.)
   gibt die fehlenden Einträge als JSONL aus (`{"i", "de", "en"}` je
   Zeile; `de` ist die Quelle, `en` die englische Referenz für Ton und
   Begriffswahl). Übersetzung als `part-NNNN.json` in den passenden
   Sprachordner schreiben (Format s. o.), am besten in Blöcken von ~40.
2. **Zusammenfügen und prüfen:**
   ```
   .venv\Scripts\python.exe .claude\i18n-wip\make_locale.py <lang> .claude\i18n-wip\<lang>
   ```
   schreibt `app/i18n/locales/<lang>.json` im Format des Einsammlers,
   aber nur wenn **alle** 2264 Indizes abgedeckt sind — sonst meldet es
   die fehlenden Bereiche und schreibt nichts.
3. **Suite:** `pytest tests/test_translations.py -k <lang>` (bzw. ohne
   `-k` für alle) — prüft Vollständigkeit, verwaiste Schlüssel und dass
   keine Sprache mitten im Satz auf Deutsch zurückfällt.

   Vorher, und ohne dass ein vollständiger Katalog nötig wäre:
   ```
   .venv\Scripts\python.exe .claude\i18n-wip\check_parts.py [lang …]
   ```
   prüft die Teile gegen die Invarianten weiter unten — Platzhalter,
   Abbildungsmarken, Absatzzahl, unübersetzt Übernommenes. Das fängt
   genau die Fehler, die sonst erst beim Einsammeln auffallen, und es
   läuft auf halbfertigem Bestand.
4. **Erst wenn alle vier Sprachen grün sind**, diesen Ordner
   (`.claude/i18n-wip/`) löschen und in einem eigenen Commit die vier
   `app/i18n/locales/*.json` einchecken. Nicht sprachweise einzeln
   committen, solange `test_every_text_is_translated` nur vollständige
   Kataloge zulässt (Regel: keine halb übersetzte Datei einchecken,
   AGENTS.md Sprachregelung).
5. Wenn ein Agent für eine Sprache **neu** angesetzt wird (statt hier
   fortzusetzen): das Glossar unten unverändert mitgeben, sonst laufen
   Fachbegriffe zwischen altem und neuem Teil auseinander.

## Format-Invarianten, die für jeden Block galten

- Markdown unverändert (**fett**, *kursiv*, Listen, Überschriften).
- Zeilenumbrüche bleiben als `\n`-Escape.
- `![](figure:xyz)` byte-gleich übernehmen, den Schlüssel nie übersetzen.
- Platzhalter in `{}`/`{name}` unverändert samt Inhalt.
- Nicht übersetzt: Produktnamen (Solidon, OrcaSlicer, PrusaSlicer, Bambu
  Studio, Cura, ElegooSlicer, ComfyUI, Ollama, OpenSCAD, Claude, Hunyuan3D,
  Inno Setup, Paddle), Formatnamen (STL, 3MF, STEP, GLB, OBJ, PLY, OFF,
  SVG, DXF, G-Code), Normbezeichnungen (M4, DIN 912), selbstbenennende
  Werte (mm, 6x3, DejaVu Sans, gyroid).
- Tastennamen: aus „Strg" wird „Ctrl" (wie im Englischen); F1, Esc, Tab,
  Enter bleiben.

## Glossare je Sprache (verbindlich, für Fortsetzung wie für Neustart)

**Spanisch:** Operation→operación · Transaktion→transacción ·
Baustein→bloque · Teil→pieza · Passung→ajuste · Spiel→holgura ·
Presspassung→ajuste a presión · Prüfbericht→informe de comprobación ·
Steckbrief→ficha · Regelsammlung→colección de reglas ·
Auswertung→evaluación · Verlauf→historial · Rückgängig→deshacer ·
Skizze→boceto · Zwangsbedingung→restricción · Bemaßung→acotación ·
Maß→cota · Netz→malla · wasserdicht→estanco · Druckplatte→placa de
impresión · Bauraum→volumen de impresión · Schichtanalyse→análisis de
capas · Schichthöhe→altura de capa · Düse→boquilla · Überhang→voladizo ·
Insel→isla · Brücke→puente · Stützen→soportes · Gewinde→rosca ·
Senkung→avellanado · Aushöhlen→vaciado · Passstift→pasador ·
Trennebene→plano de corte · Startwert→semilla · Baugruppe→ensamblaje ·
Merkmal→característica · Werkzeug→herramienta · Ansicht→vista ·
Drucker→impresora · Materialprofil→perfil de material. Ton: gepflegtes,
neutrales Spanisch (Spanien wie Lateinamerika), Infinitiv bei
Bedienaktionen, volle Akzente inkl. ¿…?/¡…!.

**Französisch:** Operation→opération · Transaktion→transaction ·
Baustein→bloc · Teil→pièce · Passung→ajustement · Spiel→jeu ·
Presspassung→ajustement serré · Prüfbericht→rapport de contrôle ·
Steckbrief→fiche · Regelsammlung→recueil de règles ·
Auswertung→évaluation · Verlauf→historique · Rückgängig→annuler ·
Skizze→esquisse · Zwangsbedingung→contrainte · Bemaßung→cotation ·
Maß→cote · Netz→maillage · wasserdicht→étanche · Druckplatte→plateau
d'impression · Bauraum→volume d'impression · Schichtanalyse→analyse des
couches · Schichthöhe→hauteur de couche · Düse→buse · Überhang→surplomb ·
Insel→îlot · Brücke→pont · Stützen→supports · Gewinde→filetage ·
Senkung→fraisure · Aushöhlen→évidement · Passstift→goupille ·
Trennebene→plan de coupe · Startwert→graine · Baugruppe→assemblage ·
Merkmal→caractéristique · Werkzeug→outil · Ansicht→vue ·
Drucker→imprimante · Materialprofil→profil de matériau. Ton: Anrede
„vous", Infinitiv bei Bedienaktionen, gewöhnliche Leerzeichen (keine
geschützten Leerzeichen).

**Italienisch:** Operation→operazione · Transaktion→transazione ·
Baustein→blocco · Teil→pezzo · Passung→accoppiamento · Spiel→gioco ·
Presspassung→accoppiamento forzato · Prüfbericht→rapporto di verifica ·
Steckbrief→scheda · Regelsammlung→raccolta di regole ·
Auswertung→valutazione · Verlauf→cronologia · Rückgängig→annulla ·
Skizze→schizzo · Zwangsbedingung→vincolo · Bemaßung→quotatura ·
Maß→quota · Netz→mesh · wasserdicht→a tenuta stagna · Druckplatte→piatto
di stampa · Bauraum→volume di stampa · Schichtanalyse→analisi degli
strati · Schichthöhe→altezza dello strato · Düse→ugello ·
Überhang→sbalzo · Insel→isola · Brücke→ponte · Stützen→supporti ·
Gewinde→filettatura · Senkung→svasatura · Aushöhlen→svuotamento ·
Passstift→spina · Trennebene→piano di taglio · Startwert→seme ·
Baugruppe→assieme · Merkmal→caratteristica · Werkzeug→strumento ·
Ansicht→vista · Drucker→stampante · Materialprofil→profilo del
materiale. Ton: Imperativ 2. Person bei Bedienaktionen, volle Akzente.
Anführungszeichen «…» (so steht es im ganzen Bestand), Op-Stapel→pila.

**Menünamen, Italienisch — eine Kollision, die vorentschieden ist.**
„Bearbeiten" (Edit) steht im Bestand als **Modifica** (Index 167). Damit ist
das naheliegende Wort für „Ändern" (Modify) verbraucht: zwei Menüs dürfen
nicht gleich heißen. Festgelegt: **Ändern → Cambia** (Index 2230). Wer den
Menütext oder die Handbuchstellen mit *Ändern → …* übersetzt, nimmt Cambia.
In den anderen drei Sprachen tritt die Kollision nicht auf (editar/modificar,
édition/modifier, editar/modificar).

**Portugiesisch:** Operation→operação · Transaktion→transação ·
Baustein→bloco · Teil→peça · Passung→ajuste · Spiel→folga ·
Presspassung→ajuste por interferência · Prüfbericht→relatório de
verificação · Steckbrief→ficha · Regelsammlung→coleção de regras ·
Auswertung→avaliação · Verlauf→histórico · Rückgängig→desfazer ·
Skizze→esboço · Zwangsbedingung→restrição · Bemaßung→cotagem ·
Maß→cota · Netz→malha · wasserdicht→estanque · Druckplatte→placa de
impressão · Bauraum→volume de impressão · Schichtanalyse→análise de
camadas · Schichthöhe→altura de camada · Düse→bico · Überhang→saliência ·
Insel→ilha · Brücke→ponte · Stützen→suportes · Gewinde→rosca ·
Senkung→escareamento · Aushöhlen→esvaziamento · Passstift→pino de
posicionamento · Trennebene→plano de corte · Startwert→semente ·
Baugruppe→conjunto · Merkmal→característica · Werkzeug→ferramenta ·
Ansicht→vista · Drucker→impressora · Materialprofil→perfil de material.
Ton: Orthographie nach Acordo Ortográfico 1990, europäisch geprägt aber
in Brasilien lesbar, Infinitiv bei Bedienaktionen, volle Diakritika.

## Was danach noch offen bleibt (aus `konzept-wettbewerb-2026-08.md` W3)

Mit den vier Katalogen ist das **Gerüst** vollständig ausgenutzt, aber
noch nichts an Bildern gemacht: `tools/make_figures.py` und
`tools/make_manual.py` erzeugen Handbuchbilder und -seiten je Sprache neu
(`available_languages()` liest das Verzeichnis automatisch) — das läuft
nicht offscreen (siehe `CLAUDE.md`) und ist ein eigener, separater
Schritt nach den Katalogen, keiner hier.
