# Sprachprüfung Changelog 0.5.1, zweiter Durchgang

Zweig `changelog-051b`, geprüft ab `e87f48af7` (Basis `6eacc1a63`), **Endcommit
`32758db1f`**, gepusht, nicht gemergt. Der Zweig war in `wt-changelog2` ausgecheckt;
gearbeitet wurde deshalb in einem abgekoppelten Arbeitsbaum `wt-clsprache`, gepusht mit
`HEAD:changelog-051b`, danach `wt-changelog2` per Fast-Forward nachgezogen. Der
Arbeitsbaum `wt-clsprache` ist entfernt.

## Umfang

Geprüft wurden alle 40 Punkte, deren deutscher Satz gegenüber `6eacc1a63` neu oder
geändert ist (36 Funde des Agenten und die vier Sätze der Gesamtprüfung; die 33 aus dem
Auftrag zählen die ersetzten Punkte anders), jeweils in en, es, fr, it und pt:
Aussage, Zahlen, Knopfnamen gegen `app/i18n/locales/<sprache>.json`, Hausregeln, Länge,
Gliederung.

**Knopfnamen:** Jeder zitierte Knopf und jede zitierte Anzeige („Druckbereit“,
„Unbenannt“, „Die Kette hält an“, „Kein Merkmal gewählt …“, „{reference} links“,
„Sackbohrung“, „Magnettasche“) steht wie im Katalog der Sprache. Einzige Abweichung ist
der Apostroph in „Montrer l'élément“/„Mostra l'elemento“, siehe unten.
**Zahlen:** in allen Sprachen gleich (4,3/7,6 s, 313 000, 122 752, 1,8/24 s, 16 Teile,
40 s, 2 bis 4 Prozent). **Anrede:** it duzt in allen neuen Punkten (allarghi, importi,
salvi), es/pt/fr siezen durchgehend. **fr-Typografie:** Leerzeichen vor „:“ und in
« … » wie im übrigen Abschnitt 0.5.1, dort gewöhnliche Leerzeichen (ein geschütztes
Paar steht nur in einem älteren Abschnitt).

## Berichtigungen: 42 (en 6, es 10, fr 7, it 10, pt 9)

Angegeben ist die Stelle als laufende Nummer im Abschnitt (1-basiert) und der
geänderte Satzteil.

### en (6)

| Nr. | alt | neu | Grund |
|---|---|---|---|
| 66 | A moved or duplicated bore from an STL file in a thin plate no longer wrongly reports that it no longer goes through. | In thin plates, a moved or duplicated bore from an STL file no longer wrongly reports that it has stopped going through. | doppeltes „no longer“, Ortsangabe hing am falschen Glied |
| 106 | … take over the features of their original … A project with many identical parts computes in less than half the time. | … inherit the features of their original … A project with many identical parts is then computed in less than half the time. | „take over“ heißt an sich reißen; ein Projekt rechnet nicht selbst; „so“ fehlte |
| 119 | … at its place there. Before, all came onto one, many beside the bed. | … in its position there. Before, they all landed on one plate, many of them beside the bed. | ungrammatisch verkürzt |
| 129 | A single body is selected by the map itself. | If there is only one body, the map selects it on its own. | Passiv verdrehte die Aussage „einen einzigen Körper wählt sie selbst“ |
| 150 | The automatic backup runs alongside the window and no longer stalls it, … | The automatic backup runs in the background and no longer stalls the window, … | „alongside the window“ ist wörtlich übertragen, gemeint ist Hintergrund |
| 174 | After drawing, the tab from before is back on the right, such as the report. Until now the chat stood there, … | After drawing, the previous tab, such as the report, is back on the right. Until now the chat was shown there, … | Beispiel hing am falschen Glied; „stood“ ist Deutsch |

### es (10)

| Nr. | alt | neu | Grund |
|---|---|---|---|
| 5 | dicen antes de laminar cuánto sobra | dicen ya antes de laminar en cuánto es demasiado grande | „cuánto sobra“ liest sich als „wie viel Platz übrig ist“; „schon“ fehlte |
| 6 | los conectores quedan del derecho … Antes el informe mostraba colisiones. | los conectores quedan bien orientados … Antes el informe mostraba ahí colisiones. | „del derecho“ sagt man von Kleidung; „dort“ fehlte |
| 21 | la Sovol SV06 ya no la versión High-Speed, la Ender-3 V3 ya no «0.12mm Fine». | la Sovol SV06 ya no recibe la versión High-Speed ni la Ender-3 V3 «0.12mm Fine». | verblose Aufzählung, holpert |
| 53 | y el informe indica el margen. | y el informe indica ese margen. | „den schmaleren Rand“ fehlte |
| 85 | con un corte de vista | con la vista en sección | Katalog nennt den Ansichtsschnitt „Sección“ |
| 99 | Un clic … elige el taladro | Un clic … selecciona el taladro | Auswahl im Fenster; Katalog und Abschnitt sagen „seleccionar“ |
| 100 | Con una arista o una distancia elegida | Con una arista o una distancia seleccionada | wie 99, passt zum zitierten «Ningún elemento seleccionado …» |
| 106 | Un proyecto … calcula así | Un proyecto … se calcula así | ein Projekt rechnet nicht selbst |
| 129 | Si hay un solo cuerpo, lo elige él. | Si hay un solo cuerpo, lo selecciona solo. | wie 99; „él“ war mehrdeutig |
| 150 | La copia de seguridad automática corre junto a la ventana y ya no la detiene | … funciona en segundo plano y ya no detiene la ventana | wie en 150; Katalog sagt „en segundo plano“ |

### fr (7)

| Nr. | alt | neu | Grund |
|---|---|---|---|
| 6 | Même quand des pièces ne font que se toucher | Même si les pièces d'un modèle ne font que se toucher | „eines Modells“ fehlte |
| 21 | la Sovol SV06 n'a plus la version High-Speed, la Ender-3 V3 plus « 0.12mm Fine ». | … n'a plus la version High-Speed, ni la Ender-3 V3 « 0.12mm Fine ». | elliptisch, holpert |
| 99 | Un clic … choisit le perçage | Un clic … sélectionne le perçage | Auswahl im Fenster, wie im übrigen Abschnitt |
| 100 | Quand une arête ou une distance est choisie | … est sélectionnée | wie 99, passt zu « Aucun détail sélectionné … » |
| 106 | Un projet … calcule en moins de la moitié du temps. | Un projet … se calcule en moins de la moitié du temps. | ein Projekt rechnet nicht selbst |
| 129 | Un corps unique, elle le choisit seule. | Elle sélectionne d'office un corps unique. | Satzbau umgangssprachlich; „choisir“ statt Auswahl |
| 150 | La sauvegarde automatique tourne à côté de la fenêtre et ne la bloque plus | … tourne en arrière-plan et ne bloque plus la fenêtre | wie en 150; Katalog sagt „en arrière-plan“ |

Geprüft und belassen, weil die bessere Fassung über 200 Zeichen käme: Nr. 4 „la laisse
debout plutôt que sur des supports“ (das Hinlegen fehlt, die Aussage bleibt) und Nr. 5
„Pour une pièce trop grande dans tous les sens“ (statt „in keiner Lage“; sachlich
dasselbe). Nr. 162 „sur plateau, supports, buse et brim“ lässt „Befunde zu“ aus,
ebenso it; im Zusammenhang eindeutig.

### it (10)

| Nr. | alt | neu | Grund |
|---|---|---|---|
| 21 | la Sovol SV06 non più la versione High-Speed, la Ender-3 V3 non più «0.12mm Fine». | … non riceve più la versione High-Speed, né la Ender-3 V3 «0.12mm Fine». | verblose Aufzählung |
| 32 | Con Cura si possono affettare anche modelli grandi. | Con Cura si può fare lo slicing anche di modelli grandi. | „affettare“ neben „slicing“ im selben Abschnitt (Nr. 5, 32); im Italienischen sagt man „slicing“ |
| 33 | Se Creality Print può affettare un 3MF … | Se Creality Print può calcolare un 3MF … | wie 32; das Deutsche sagt „rechnen“ |
| 53 | e il rapporto indica il margine. | e il rapporto indica quel margine. | „den schmaleren Rand“ fehlte |
| 99 | Un clic … sceglie il foro | Un clic … seleziona il foro | Auswahl im Fenster, wie im übrigen Abschnitt |
| 100 | Con uno spigolo o una distanza scelti | … selezionati | wie 99, passt zu «Nessun elemento selezionato …» |
| 102 | Se è lungo, «Carica senza … | Se è lento, «Carica senza … | „se è lungo“ sagt man von einem Vorgang nicht; „Se dura troppo“ hätte 203 Zeichen |
| 106 | Un progetto … calcola così | Un progetto … viene calcolato così | ein Projekt rechnet nicht selbst |
| 129 | Se il corpo è uno solo, lo sceglie da sé. | … lo seleziona da sé. | wie 99 |
| 150 | Il salvataggio automatico gira accanto alla finestra e non la blocca più | … gira in secondo piano e non blocca più la finestra | wie en 150; Katalog sagt „in secondo piano“ |

### pt (9)

| Nr. | alt | neu | Grund |
|---|---|---|---|
| 5 | dizem antes de fatiar quanto é grande demais | dizem já antes de fatiar em quanto é demasiado grande | „grande demais“ ist brasilianisch und ungrammatisch nach „quanto“; der Abschnitt ist pt-PT („demasiado fino“); „schon“ fehlte |
| 6 | os conectores ficam do lado certo | os conectores ficam bem orientados | „do lado certo“ heißt „auf der richtigen Seite“ |
| 21 | a Sovol SV06 já não a versão High-Speed, a Ender-3 V3 já não «0.12mm Fine». | … já não recebe a versão High-Speed, nem a Ender-3 V3 «0.12mm Fine». | verblose Aufzählung |
| 53 | em vez de sair da borda | em vez de ultrapassar a borda | „sair da borda“ heißt „vom Rand weggehen“ |
| 99 | Um clique … escolhe o furo | Um clique … seleciona o furo | Auswahl im Fenster, wie im übrigen Abschnitt |
| 100 | Com uma aresta ou uma distância escolhida | … selecionada | wie 99, passt zu «Nenhum detalhe selecionado …» |
| 106 | Um projeto … calcula assim | Um projeto … é calculado assim | ein Projekt rechnet nicht selbst |
| 129 | Se houver um só corpo, escolhe-o sozinho. | … seleciona-o sozinho. | wie 99 |
| 150 | A cópia de segurança automática corre ao lado da janela e já não a bloqueia | … corre em segundo plano e já não bloqueia a janela | wie en 150; Katalog sagt „em segundo plano“ |

## Offene Katalogfragen (nicht im Changelog zu lösen)

- **Typografischer Apostroph im Katalog:** `Merkmal zeigen` steht in fr als
  „Montrer l’élément“, in it als „Mostra l’elemento“. Der Changelog führt nach der
  Entscheidung aus dem Textpaket den geraden Apostroph (Nr. 162); der Katalog sollte
  nachziehen, sonst bleibt der Unterschied an jeder zitierten Stelle.
- **it „Ridurre i triangoli“:** Der Knopf `Dreiecke verringern` steht im Infinitiv,
  seine Geschwister im Imperativ („Riduci i triangoli e riprova“, „Affina gli spigoli“).
  Der Changelog zitiert wie der Katalog (Nr. 134); der Katalog sollte „Riduci i
  triangoli“ heißen, dann der Changelog mit.
- **it „Fare clic su …“** im Leersatz „Kein Merkmal gewählt. …“ ist Infinitiv statt Du
  („Fai clic“). Im Changelog steht nur der erste Teil, deshalb dort ohne Folgen.

## Prüfläufe

- `laeufe\clsprache-1.txt` (gebunden, Art `kern`, weil cmd die Anführungszeichen
  zerlegt): test_changelog und test_wording, 64 passed, 1 skipped, 7 deselected,
  EXIT kern=0.
- `laeufe\clsprache-2.txt` (`sonden\changelog\pruefe051.py`, Gegenprobe
  `APP_VERSION = 0.5.1`): 48 passed, 1 skipped, pytest-Exit 0; je Sprache 181 Punkte,
  längster de 200, en 197, es 200, fr 200, it 199, pt 199; Gruppenformen gleich
  [58, 29, 3, 10, 17, 23, 7, 30, 4]; Verstöße gesamt 0; EXIT python=0.
