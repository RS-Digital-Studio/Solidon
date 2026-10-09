---
description: "Die Sprachkataloge — eine Sprache ist eine Datei, was nie übersetzt wird, verbindliche Glossare je Sprache und der Genus, der durch den Satz zieht, neu übersetzen statt flicken, neue Schlüssel ziehen überall nach"
paths:
  - "app/i18n/**"
  - "changelog/*.md"
---

# Regeln für die Sprachkataloge

Eine Sprache ist **eine Datei** in `app/i18n/locales/` und sonst nichts
(`AGENTS.md`, Sprachregelung): `available_languages()` liest das Verzeichnis,
Sprachauswahl, Einsammler, Handbuch, Abbildungen und Prüfung finden sie dort —
eine zweite Stelle zum Nachziehen gibt es nicht. Derzeit sechs: Deutsch als
Quelle, dazu `en`, `es`, `fr`, `it`, `pt`.

**Unvollständig wird keine eingecheckt.** `tests/test_translations.py` prüft
jede gefundene Datei auf Vollständigkeit, verwaiste Schlüssel und Rückfall ins
Deutsche mitten im Satz — eine halb übersetzte Datei ist ein roter Lauf, kein
Zwischenstand.

Wie ein Text für den Kunden klingt (kurz, nicht nach einem Sprachmodell,
„Version“): `oberflaeche.md` unter „Texte, die der Kunde liest“. Warum:
`konzepte/begruendungen/regel-uebersetzung.md`.

## Was nie übersetzt wird

- **Markdown bleibt unverändert** (`**fett**`, `*kursiv*`, Listen,
  Überschriften), Zeilenumbrüche bleiben als `\n`-Escape.
- **`![](figure:xyz)` byte-gleich übernehmen** — der Schlüssel ist eine
  Adresse, kein Text.
- **Seitenverweise `[Text](manual:schlüssel)`:** den Text übersetzen, das Ziel
  byte-gleich übernehmen und keinen Verweis auslassen — `test_manual` hält
  die Ziele je Seite gegen das Deutsche.
- **Platzhalter in `{}` / `{name}`** unverändert samt Inhalt.
- **Produktnamen:** Solidon, OrcaSlicer, PrusaSlicer, Bambu Studio, Cura,
  ElegooSlicer, ComfyUI, Ollama, OpenSCAD, Claude, Hunyuan3D, Inno Setup,
  Paddle.
- **Formatnamen:** STL, 3MF, STEP, GLB, OBJ, PLY, OFF, SVG, DXF, G-Code.
- **Normbezeichnungen** (M4, DIN 912) und selbstbenennende Werte (mm, 6x3,
  DejaVu Sans, gyroid).
- **Tastennamen:** aus „Strg" wird „Ctrl" wie im Englischen; F1, Esc und Tab
  bleiben. Französisch schreibt „Échap“, weil französische Tastaturen die
  Taste so beschriften. Die Eingabetaste heißt, wie der Bestand sie nennt:
  en/pt Enter, es Intro, fr Entrée, it Invio.
- **Ein Kürzel im Satz steht in der Schreibweise von Windows** („Strg+Z“,
  „Ctrl+Z“, Umschalt/Shift, Alt, dahinter genau eine Taste): Auf dem Mac
  schreibt `tr` es als ⌘Z, ⇧⌘P, ⌥7 und *Wiederholen* als ⇧⌘Z
  (`app/i18n/keys.py`, eingestellt beim Start über `sys.platform`). Eine
  andere Form („Strg-Z“, „Strg + Z“) erkennt es nicht; Handbuch, Website und
  Changelog-Seiten bleiben in dieser Schreibweise (`test_native_keys.py`).
- **Entf und Pos1 haben je Sprache einen Namen**, im Katalog unter dem Kontext
  „Taste“ (en Del/Home, es Supr/Inicio, fr Suppr/Origine, it Canc/Home, pt
  Del/Home), und jeder Satz nennt die Taste genau so: Auf dem Mac schreibt
  `tr` daraus ⌫ und ↖ (`key_names`; `test_native_keys.py` zählt je Satz
  nach). Pos1 gilt nur in `…`, in Klammern oder vor „(*Handlung*)“, denn
  „Home“ ist auch die Startseite. Einfg hat dort kein Gegenstück und bleibt.

## Ein Schlüssel, eine Bedeutung, eine Schreibweise

Heißt dasselbe deutsche Wort zwei Dinge („Startwert“: Seed der Erzeugung und
Kalibrierstand eines Materials) oder steht es einmal als Beschriftung und
einmal als Wort im Satz („Dreiecke“: Feld *Triangles*, Anzahl *440842
triangles*), trennt ein `context` die Schlüssel (`tr("Startwert",
context="Kalibrierstand")`, `context="Anzahl"`). Eine Übersetzung für beide
passt an keiner Stelle — „starting point“ steht dann klein als Feldbeschriftung.

## Glossare je Sprache — verbindlich

Wer einen neuen Schlüssel nachträgt, nimmt diese Wörter. Sie sind über den
ganzen Bestand durchgehalten; ein abweichendes Synonym lässt die Oberfläche
auseinanderlaufen, ohne dass ein Test es merkt.

**Ausnahme zu Maß → cota/quota:** Wo die Oberfläche „medidas“/„misure“ sagt
— am Haken „Maße als Parameter anlegen“ und in so beschrifteten Dialogen —,
folgen Anleitungen der Oberfläche, denn der Kunde sucht das Wort im Fenster.

**Apostroph:** Französisch und Italienisch schreiben ihn gerade (`'`) wie die
Mehrheit des Bestands, und kein Eintrag mischt beide Formen — ein Menüeintrag
mit „’“ neben einem Satz, der ihn mit „'“ zitiert, ist für den Kunden derselbe
Knopf, für die Zitatprüfung ein anderer. Alle französischen und italienischen
Katalogwerte schreiben ihn gerade, einschließlich Handbuch und Anleitungen
(`test_french_and_italian_use_straight_apostrophes_everywhere`). Der zusätzliche
Wächter `test_no_entry_mixes_two_apostrophes` prüft das Mischen im selben Text.

**Vorher lesen: Der Genus zieht durch den Satz.** `bloque`, `bloc` und `bloco`
sind maskulin, `pieza`, `pièce` und `peça` feminin. Wer beim Baustein nur das
Substantiv tauscht, hinterlässt einen Satz, der wie eine geprüfte Übersetzung
aussieht und in sich nicht stimmt — schlechter als der Fehler davor. Artikel,
Partizipien und Pronomen ziehen mit („Esta pieza … la rechazaría“ → „Este
bloque … lo rechazaría“, „partagée telle quelle“ → „partagé tel quel“, „la
suya“ → „el suyo“). Das Italienische bleibt maskulin (`componente`, `blocco`)
und verführt so zum Schluss, ein Wörtertausch genüge. Ersetzt wird nur, wo die
Quelle „Baustein“ sagt: `pieza`/`pièce`/`peça` für das Werkstück (Teil) und
`componenti normalizzati` für Normteile bleiben. Geprüft wird je Sprache über die Schlüssel
mit „Baustein“ — dort steht kein anderer Begriff mehr; die Website zitiert
Dialogtitel wörtlich, `website/{es,fr,it,pt}/index.html` und `features.html`
ziehen nach.

**Spanisch:** Operation→operación · Transaktion→transacción · Baustein→bloque ·
Teil→pieza · Passung→ajuste · Spiel→holgura · Presspassung→ajuste a presión ·
Prüfbericht→informe de comprobación · Steckbrief→ficha ·
Regelsammlung→colección de reglas · Auswertung→evaluación · Verlauf→historial ·
Rückgängig→deshacer · Skizze→boceto · Zwangsbedingung→restricción ·
Bemaßung→acotación · Maß→cota · Netz→malla · wasserdicht→estanco ·
Druckplatte→placa de impresión · Bauraum→volumen de impresión ·
Schichtanalyse→análisis de capas · Schichthöhe→altura de capa · Düse→boquilla ·
Überhang→voladizo · Insel→isla · Brücke→puente · Stützen→soportes · Baumstützen→soportes en árbol ·
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
Stützen→supports · Baumstützen→supports arborescents · Gewinde→filetage · Senkung→fraisure · Aushöhlen→évidement ·
Passstift→goupille · Trennebene→plan de coupe · Startwert→graine ·
Baugruppe→assemblage · Merkmal→caractéristique · Werkzeug→outil ·
Ansicht→vue · Drucker→imprimante · Materialprofil→profil de matériau.
Ton: Anrede „vous", Infinitiv bei Bedienaktionen, gewöhnliche Leerzeichen
(keine geschützten). Vor : ; ? ! steht eines, auch wo der Code einen Satz
zusammensetzt: Das Satzzeichen zwischen zwei übersetzten Teilen gehört in den
Katalogeintrag mit Platzhaltern (`_("Gilt für: {kinds}", kinds=…)`), nicht fest
in den Code — sonst steht an jeder Operation der Referenz „Objets: 0 → 1“
(`test_french_sets_a_space_before_colon_semicolon_and_question_mark`).

**Italienisch:** Operation→operazione · Transaktion→transazione ·
Baustein→blocco · Teil→pezzo · Passung→accoppiamento · Spiel→gioco ·
Presspassung→accoppiamento forzato · Prüfbericht→rapporto di verifica ·
Steckbrief→scheda · Regelsammlung→raccolta di regole · Auswertung→valutazione ·
Verlauf→cronologia · Rückgängig→annulla · Skizze→schizzo ·
Zwangsbedingung→vincolo · Bemaßung→quotatura · Maß→quota · Netz→mesh ·
wasserdicht→a tenuta stagna · Druckplatte→piatto di stampa · Bauraum→volume di
stampa · Schichtanalyse→analisi degli strati · Schichthöhe→altezza dello
strato · Düse→ugello · Überhang→sbalzo · Insel→isola · Brücke→ponte ·
Stützen→supporti · Baumstützen→supporti ad albero · Gewinde→filettatura · Senkung→svasatura ·
Aushöhlen→svuotamento · Passstift→spina · Trennebene→piano di taglio ·
Startwert→seme · Baugruppe→assieme · Merkmal→caratteristica ·
Werkzeug→strumento · Ansicht→vista · Drucker→stampante ·
Materialprofil→profilo del materiale · Op-Stapel→pila ·
Schritt (im Verlauf)→passaggio. „Passo“ ist schon Steigung und Schrittweite;
Tour- und Anleitungsschritte und „passo dopo passo“ bleiben „passo“.
Ton: Imperativ 2. Person bei Bedienaktionen („tu“, nicht „voi“ oder „Lei“),
volle Akzente, Anführungszeichen «…» (so steht es im ganzen Bestand).

**Eine italienische Kollision ist vorentschieden:** „Bearbeiten“ (Edit) heißt
im Bestand **Modifica**, zwei Menüs dürfen nicht gleich heißen — also **Ändern →
Cambia**, auch in Handbuchstellen mit *Ändern → …*. In den anderen drei
Sprachen tritt sie nicht auf (editar/modificar, édition/modifier,
editar/modificar).

**Portugiesisch:** Operation→operação · Transaktion→transação ·
Baustein→bloco · Teil→peça · Passung→ajuste · Spiel→folga ·
Presspassung→ajuste por interferência · Prüfbericht→relatório de verificação ·
Steckbrief→ficha · Regelsammlung→coleção de regras · Auswertung→avaliação ·
Verlauf→histórico · Rückgängig→desfazer · Skizze→esboço ·
Zwangsbedingung→restrição · Bemaßung→cotagem · Maß→cota · Netz→malha ·
wasserdicht→estanque · Druckplatte→placa de impressão · Bauraum→volume de
impressão · Schichtanalyse→análise de camadas · Schichthöhe→altura de camada ·
Düse→bico · Überhang→saliência · Insel→ilha · Brücke→ponte ·
Stützen→suportes · Baumstützen→suportes em árvore · Gewinde→rosca ·
Senkung→escareamento ·
Aushöhlen→esvaziamento · Passstift→pino de posicionamento · Trennebene→plano de
corte · Startwert→semente · Baugruppe→conjunto · Merkmal→característica ·
Werkzeug→ferramenta · Ansicht→vista · Drucker→impressora ·
Materialprofil→perfil de material.
Ton: Orthographie nach Acordo Ortográfico 1990, europäisch geprägt aber in
Brasilien lesbar, Infinitiv bei Bedienaktionen, volle Diakritika.

**Englisch:** Passung→fit · Spiel→clearance, als Feld „Clearance“. „play“
bleibt nur, wo *Spiel* die Lose meint (Langloch für Schrauben, die sich
verschieben lassen) — im 3D-Druck meint „play“ Wackeln, und ein Feld „Play“
neben einem Satz über „clearance“ sind für den Kunden zwei Dinge.

**Jeder Weg, ein Teil zu teilen, sagt „teilen“, und keine zwei heißen gleich**
(RM-507, Entscheidung Robert 06.10.2026): das Werkzeug *Teilen* (en Split, es Dividir, fr Diviser, it Dividi,
pt Dividir), die Operationen *An Ebene teilen*, *An gezeichneter Linie teilen*
und *In Einzelteile aufteilen*, der Ablauf *Automatisch teilen*. Drei Verben für
eine Sache ließen den Kunden suchen, ein gemeinsamer Name schickte ihn an den
falschen Ort (`test_every_way_to_split_says_teilen`,
`test_no_tool_or_operation_shares_its_name_with_another`). Auch ein Satz, der
das Teilen beschreibt, sagt „teilen“ oder „aufteilen“, nie „zerlegen“; die
Übersetzungen folgen dem Namen der Operation.

## Übersetzen heißt neu schreiben, nicht flicken

**Neu übersetzen, wenn es sauberer ist** (Entscheidung Robert). Ein
Katalogschlüssel ist oft der ganze Text — ein Handbuchkapitel unter einem
Schlüssel —, und ein Zusatz erzeugt einen neuen. Anhängen nur, wenn der Zusatz
ein eigenständiger Absatz am Ende ist und die alte Übersetzung trägt (Absatzzahl
und Ton verglichen; der neue Absatz wird frisch übersetzt). Neu übersetzen,
sobald der Zusatz in den Text greift oder seine Aussage verschiebt — ein
geflickter Text liest sich wie zwei Handschriften —, und immer, wenn die alte
Übersetzung schwächer ist als das Deutsche: Der Kunde liest das Ganze, nicht den
Diff. Der alte Schlüssel muss hinaus (`test_every_text_is_translated`).

**Ein mehrsprachiges Bildschirmvideo übersetzt auch, was der Film selbst
anlegt:** Objekt- und Parameternamen samt den `@`-Verweisen in allen
Operationen sind Benutzereingaben, und die übersetzt die Anwendung nicht.
Einblendungen, sichtbare Dialoge und Formeln werden gemeinsam geprüft; nur den
Text über einer deutschen Aufnahme zu ersetzen reicht nicht.

**Ein Name im Satz einer Bildanleitung ist der Name am Bildschirm.** Was ein
Schritt hervorhebt (*Aushöhlen*, *Oben öffnen*, *Erzeugen → Bausteine →
Deckel erzeugen*), steht in der Übersetzung genau so, wie der Katalog Knopf,
Feld oder Menüeintrag übersetzt — kein Synonym, keine Kurzform, denn der Kunde
sucht das Wort im Fenster. `tests/test_guides.py` prüft es in jeder Sprache.

## Neue Schlüssel nachtragen

Die neuen Texte in jede Katalogdatei eintragen — `test_translations.py` sagt,
welche fehlen; ein eigenes Verfahren braucht es nicht. Wer eine ganze Sprache
am Stück übersetzt, arbeitet gegen eine eingefrorene Basis: Der lebende Katalog
wächst mitten im Lauf und verschiebt jede Indexangabe. Wo Werkzeuge und Ablauf
dafür liegen: `konzepte/begruendungen/regel-uebersetzung.md`.

Handbuchbilder und -seiten je Sprache erzeugen `tools/make_figures.py` und
`tools/make_manual.py` — **nicht** offscreen, ein eigener Schritt (`/erzeugen`).
