---
description: "Die Sprachkataloge — eine Sprache ist eine Datei, was nie übersetzt wird, verbindliche Glossare je Sprache und der Genus, der durch den Satz zieht, neu übersetzen statt flicken, neue Schlüssel ziehen überall nach"
paths:
  - "app/i18n/**"
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
ganzen Bestand durchgehalten; ein abweichendes Synonym lässt die Oberfläche
auseinanderlaufen, ohne dass ein Test es merkt.

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
Stützen→suportes · Gewinde→rosca · Senkung→escareamento ·
Aushöhlen→esvaziamento · Passstift→pino de posicionamento · Trennebene→plano de
corte · Startwert→semente · Baugruppe→conjunto · Merkmal→característica ·
Werkzeug→ferramenta · Ansicht→vista · Drucker→impressora ·
Materialprofil→perfil de material.
Ton: Orthographie nach Acordo Ortográfico 1990, europäisch geprägt aber in
Brasilien lesbar, Infinitiv bei Bedienaktionen, volle Diakritika.

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
wächst mitten im Lauf und verschiebt jede Indexangabe. Werkzeuge und Ablauf dafür
stehen in der Historie unter `.claude/i18n-wip/` (bis Commit `93f0989`).

Handbuchbilder und -seiten je Sprache erzeugen `tools/make_figures.py` und
`tools/make_manual.py` — **nicht** offscreen, ein eigener Schritt (`/erzeugen`).
