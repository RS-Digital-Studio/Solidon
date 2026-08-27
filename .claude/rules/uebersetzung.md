---
paths:
  - "app/i18n/**"
---

# Regeln für die Sprachkataloge

Eine Sprache ist **eine Datei** in `app/i18n/locales/` und sonst nichts.
`available_languages()` liest das Verzeichnis; Sprachauswahl, Einsammler,
Handbuch, Abbildungen und Prüfung finden sie von dort. Wer eine Sprache
hinzufügt, legt eine Datei ab — es gibt keine zweite Stelle, die nachgezogen
werden müsste.

Derzeit sechs: Deutsch als Quelle, dazu `en`, `es`, `fr`, `it`, `pt`.

**Unvollständig wird keine eingecheckt.** `tests/test_translations.py` prüft
jede gefundene Datei — Vollständigkeit, verwaiste Schlüssel, und dass keine
Sprache mitten im Satz auf Deutsch zurückfällt. Eine halb übersetzte Datei ist
ein roter Lauf, kein Zwischenstand.

## Was nie übersetzt wird

- **Markdown bleibt unverändert** (`**fett**`, `*kursiv*`, Listen,
  Überschriften), Zeilenumbrüche bleiben als `\n`-Escape.
- **`![](figure:xyz)` byte-gleich übernehmen** — der Schlüssel ist eine
  Adresse, kein Text.
- **Platzhalter in `{}` / `{name}`** unverändert samt Inhalt.
- **Produktnamen:** Solidon, OrcaSlicer, PrusaSlicer, Bambu Studio, Cura,
  ElegooSlicer, ComfyUI, Ollama, OpenSCAD, Claude, Hunyuan3D, Inno Setup,
  Paddle.
- **Formatnamen:** STL, 3MF, STEP, GLB, OBJ, PLY, OFF, SVG, DXF, G-Code.
- **Normbezeichnungen** (M4, DIN 912) und selbstbenennende Werte (mm, 6x3,
  DejaVu Sans, gyroid).
- **Tastennamen:** aus „Strg" wird „Ctrl" wie im Englischen; F1, Esc, Tab,
  Enter bleiben.

## Glossare je Sprache — verbindlich

Wer einen neuen Schlüssel nachträgt, nimmt diese Wörter. Sie sind über den
gesamten Bestand durchgehalten; ein abweichendes Synonym lässt die Oberfläche
in sich auseinanderlaufen, ohne dass ein Test es merkt.

**Spanisch:** Operation→operación · Transaktion→transacción · Baustein→bloque ·
Teil→pieza · Passung→ajuste · Spiel→holgura · Presspassung→ajuste a presión ·
Prüfbericht→informe de comprobación · Steckbrief→ficha ·
Regelsammlung→colección de reglas · Auswertung→evaluación · Verlauf→historial ·
Rückgängig→deshacer · Skizze→boceto · Zwangsbedingung→restricción ·
Bemaßung→acotación · Maß→cota · Netz→malla · wasserdicht→estanco ·
Druckplatte→placa de impresión · Bauraum→volumen de impresión ·
Schichtanalyse→análisis de capas · Schichthöhe→altura de capa · Düse→boquilla ·
Überhang→voladizo · Insel→isla · Brücke→puente · Stützen→soportes ·
Gewinde→rosca · Senkung→avellanado · Aushöhlen→vaciado · Passstift→pasador ·
Trennebene→plano de corte · Startwert→semilla · Baugruppe→ensamblaje ·
Merkmal→característica · Werkzeug→herramienta · Ansicht→vista ·
Drucker→impresora · Materialprofil→perfil de material.
Ton: gepflegtes, neutrales Spanisch (Spanien wie Lateinamerika), Infinitiv bei
Bedienaktionen, volle Akzente inkl. ¿…?/¡…!.

**Französisch:** Operation→opération · Transaktion→transaction ·
Baustein→bloc · Teil→pièce · Passung→ajustement · Spiel→jeu ·
Presspassung→ajustement serré · Prüfbericht→rapport de contrôle ·
Steckbrief→fiche · Regelsammlung→recueil de règles · Auswertung→évaluation ·
Verlauf→historique · Rückgängig→annuler · Skizze→esquisse ·
Zwangsbedingung→contrainte · Bemaßung→cotation · Maß→cote · Netz→maillage ·
wasserdicht→étanche · Druckplatte→plateau d'impression · Bauraum→volume
d'impression · Schichtanalyse→analyse des couches · Schichthöhe→hauteur de
couche · Düse→buse · Überhang→surplomb · Insel→îlot · Brücke→pont ·
Stützen→supports · Gewinde→filetage · Senkung→fraisure · Aushöhlen→évidement ·
Passstift→goupille · Trennebene→plan de coupe · Startwert→graine ·
Baugruppe→assemblage · Merkmal→caractéristique · Werkzeug→outil ·
Ansicht→vue · Drucker→imprimante · Materialprofil→profil de matériau.
Ton: Anrede „vous", Infinitiv bei Bedienaktionen, gewöhnliche Leerzeichen
(keine geschützten).

**Italienisch:** Operation→operazione · Transaktion→transazione ·
Baustein→blocco · Teil→pezzo · Passung→accoppiamento · Spiel→gioco ·
Presspassung→accoppiamento forzato · Prüfbericht→rapporto di verifica ·
Steckbrief→scheda · Regelsammlung→raccolta di regole · Auswertung→valutazione ·
Verlauf→cronologia · Rückgängig→annulla · Skizze→schizzo ·
Zwangsbedingung→vincolo · Bemaßung→quotatura · Maß→quota · Netz→mesh ·
wasserdicht→a tenuta stagna · Druckplatte→piatto di stampa · Bauraum→volume di
stampa · Schichtanalyse→analisi degli strati · Schichthöhe→altezza dello
strato · Düse→ugello · Überhang→sbalzo · Insel→isola · Brücke→ponte ·
Stützen→supporti · Gewinde→filettatura · Senkung→svasatura ·
Aushöhlen→svuotamento · Passstift→spina · Trennebene→piano di taglio ·
Startwert→seme · Baugruppe→assieme · Merkmal→caratteristica ·
Werkzeug→strumento · Ansicht→vista · Drucker→stampante ·
Materialprofil→profilo del materiale · Op-Stapel→pila.
Ton: Imperativ 2. Person bei Bedienaktionen, volle Akzente,
Anführungszeichen «…» (so steht es im ganzen Bestand).

**Eine italienische Kollision, die vorentschieden ist.** „Bearbeiten" (Edit)
steht im Bestand als **Modifica**. Damit ist das naheliegende Wort für
„Ändern" (Modify) verbraucht — zwei Menüs dürfen nicht gleich heißen.
Festgelegt: **Ändern → Cambia**. Wer den Menütext oder eine Handbuchstelle mit
*Ändern → …* übersetzt, nimmt Cambia. In den anderen drei Sprachen tritt die
Kollision nicht auf (editar/modificar, édition/modifier, editar/modificar).

**Portugiesisch:** Operation→operação · Transaktion→transação ·
Baustein→bloco · Teil→peça · Passung→ajuste · Spiel→folga ·
Presspassung→ajuste por interferência · Prüfbericht→relatório de verificação ·
Steckbrief→ficha · Regelsammlung→coleção de regras · Auswertung→avaliação ·
Verlauf→histórico · Rückgängig→desfazer · Skizze→esboço ·
Zwangsbedingung→restrição · Bemaßung→cotagem · Maß→cota · Netz→malha ·
wasserdicht→estanque · Druckplatte→placa de impressão · Bauraum→volume de
impressão · Schichtanalyse→análise de camadas · Schichthöhe→altura de camada ·
Düse→bico · Überhang→saliência · Insel→ilha · Brücke→ponte ·
Stützen→suportes · Gewinde→rosca · Senkung→escareamento ·
Aushöhlen→esvaziamento · Passstift→pino de posicionamento · Trennebene→plano de
corte · Startwert→semente · Baugruppe→conjunto · Merkmal→característica ·
Werkzeug→ferramenta · Ansicht→vista · Drucker→impressora ·
Materialprofil→perfil de material.
Ton: Orthographie nach Acordo Ortográfico 1990, europäisch geprägt aber in
Brasilien lesbar, Infinitiv bei Bedienaktionen, volle Diakritika.

## Neue Schlüssel nachtragen

Der Normalfall: die Oberfläche bekommt einen Text, `en.json` wächst, die
anderen fünf müssen nach. Dafür braucht es kein Verfahren — die neuen Texte in
jede Katalogdatei eintragen, `test_translations.py` sagt, welche fehlen.

Die vier Kataloge `es`, `fr`, `it` und `pt` sind am 13.08.2026 in einem Zug
entstanden: acht Hintergrund-Agenten, je zwei pro Sprache, gegen eine
eingefrorene Basis, weil der lebende Katalog mitten im Lauf um fünfzehn
Schlüssel wuchs und jede Indexangabe darüber verschob. Wer so etwas noch
einmal braucht — eine siebte Sprache am Stück —, findet Werkzeuge und
Ablaufbeschreibung in der Historie unter `.claude/i18n-wip/`, bis
Commit `93f0989`. Für alles Kleinere ist der Ordner nicht nötig, und deshalb
liegt er nicht mehr im Baum.

Was danach noch aussteht, ist kein Katalogthema: `tools/make_figures.py` und
`tools/make_manual.py` erzeugen Handbuchbilder und -seiten je Sprache neu. Das
läuft **nicht** offscreen (siehe `CLAUDE.md`) und ist ein eigener Schritt.
