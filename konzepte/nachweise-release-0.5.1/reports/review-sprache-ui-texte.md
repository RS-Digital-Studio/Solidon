# Sprachprüfung Textpaket und Oberflächenpaket (Release 0.5.1)

Geprüft wurden nur die Texte, den Code prüft ein zweiter Prüfer.

- Textpaket `origin/texte-051`, Basis `aa82afdff`, Endstand `ec0298b15`
- Oberflächenpaket `origin/ui-handbuch-051`, Basis `9f19b44d6`, Endstand `bbc16f9ad`

Vorgehen: Katalogdiffs je Sprache (neu, entfernt, geändert) aus `git show` beider
Stände, dazu ein nachgebauter Merge-Katalog (origin/main `cbef27715` plus beide
Pakete, kein Schlüssel wird von beiden angefasst). Auf diesem Merge-Katalog lief
die Durchsicht über den **ganzen** it-Katalog (Lei- und voi-Formen, „passo“), fr
„Esc“, die Eingabetaste, die Namen von *Trennen* und *Teilen* in jeder Sprache,
Apostrophe, Anführungszeichen, Platzhalter, Zeilenumbrüche und Markdown. Testläufe
waren nicht nötig. Die Auswerteskripte liegen im Scratchpad der Sitzung, nicht im
Baum.

Schwere: **B** blockiert den Merge · **T** vor dem Tag beheben · **N** nach 0.5.1.

## Urteil

| Paket | mergebar | Begründung |
|---|---|---|
| Textpaket | **ja** | Kein Befund macht main schlechter. Offen sind aber rund 33 it-Oberflächentexte in der Lei-Form (T1) und zwei voi-Stellen im it-Changelog (T2). Der Auftrag „Italienisch duzt durchgehend“ ist damit nicht erfüllt, und das gehört vor den Tag. |
| Oberflächenpaket | **ja** | Die deutschen Quellen sind kurz und richtig, alle fünf Übersetzungen stimmen in Platzhaltern, Begriffen und Genus. Einzusetzen beim Merge: gerade Apostrophe in fr/it (U1). Der Rest ist Feinschliff. |

Blockierende Befunde gibt es keine.

## Konflikte zwischen den Paketen

- Kein Katalogschlüssel wird von beiden Paketen geändert (je Sprache: Textpaket
  40 bis 330 Schlüssel, Oberflächenpaket 22, Schnittmenge 0). Beim Merge treffen
  nur benachbarte Zeilen der sortierten JSON-Dateien aufeinander, und die lassen
  sich zusammenführen, ohne dass sich ein Wert ändert.
- `app/ui/labels.py`: Das Textpaket ändert `_CHOICE_NAMES`, `_CHOICE_NOTES` und
  `_INNER_SIDES` (ab Zeile 890), das Oberflächenpaket fügt `limit_sentence` und
  `BoundedSpin` ab Zeile 500 ein. Die Stellen berühren sich nicht, und kein Text
  des einen kommt im anderen vor.
- Die neuen Texte des Oberflächenpakets nutzen die Umbenennungen des Textpakets,
  soweit sie betroffen sind: it „passaggio“ in allen vier Löschsätzen, kein „Esc“,
  keine Nennung von *Trennen* oder *Teilen*, keine Lei- oder voi-Form. Einzige
  Abweichung ist der Apostroph, siehe U1.
- Seit den Basen kamen auf main zwei it-Einträge dazu, die „passo“ für einen
  Schritt im Verlauf sagen. Sie gehören zu keinem der beiden Pakete, sind aber
  beim Merge mitzuziehen, siehe M1.

## Befunde Textpaket

### T1 · it · Lei-Form in 33 Oberflächentexten — T

Die Prüfung `test_italian_says_tu_outside_the_manual` erkennt nur eine kuratierte
Liste von Imperativen am Satzanfang („Faccia clic“, aber nicht „Faccia di nuovo
clic“). Deshalb stehen im gemergten Katalog außerhalb des Handbuchs noch
Lei-Imperative („Incolli“, „Copi … lo apra“, „Allinei“, „Configuri“, „Reinstalli“,
„si rivolga“, „Renda“, „Ridisegni“, „Spunti“, „Raccordi“, „assegni“, „clicchi“,
„Parli … mi scriva“), die Anrede „può“ sowie die Possessiva „sua/suo“ für das
deutsche „Ihr“. Betroffen sind unter anderem die Aktivierung (Kaufschlüssel,
Zahlungslink), Support, Spende und Update-Einstellung. Alle 33 Einträge stehen
unverändert an Basis und Endstand des Textpakets und bleiben auch nach dem Merge
so. Die richtige Fassung ist jeweils der ganze Eintrag, mit
geradem Apostroph:

| Schlüssel (Anfang) | heute | richtig |
|---|---|---|
| Das Muster läuft um einen Zylinder, der breiter … | … Faccia di nuovo clic sulla faccia cilindrica affinché … | Il motivo avvolge un cilindro più largo del corpo: sporge oltre il suo bordo. Fai di nuovo clic sulla faccia cilindrica affinché il diametro torni a corrispondere al corpo. |
| Dieser Baustein benutzt weitere Rezepte, die nicht in Ihrer Bibliothek … | … nella sua libreria. Aggiungale prima … | Questo blocco usa altre ricette che non sono nella tua libreria. Aggiungile prima da un file, poi questo si potrà modificare. |
| Ein Rezept kann höchstens {limit} Maße freigeben … | … Rimuova altre misure dalla selezione. | Una ricetta può offrire al massimo {limit} misure modificabili. Rimuovi altre misure dalla selezione. |
| Fügen Sie den Schlüssel aus der Bestellmail ein. | Incolli la chiave dall’e-mail dell’ordine. | Incolla la chiave dall'e-mail dell'ordine. |
| Kopieren Sie den Zahlungslink und öffnen Sie ihn selbst … | Copi il link di pagamento e lo apra direttamente. Per qualsiasi domanda può rivolgersi a {address}. | Copia il link di pagamento e aprilo direttamente. Per qualsiasi domanda puoi rivolgerti a {address}. |
| Die Gegenfläche muss parallel sein und zur Dichtung zeigen … | … Allinei il corpo contrapposto. | La faccia contrapposta deve essere parallela e rivolta verso la guarnizione. Allinea il corpo contrapposto. |
| {slicer} kennt {printer} nicht — … | … Configuri la stampante nello slicer oppure consegni a uno slicer che la conosca. | {slicer} non conosce {printer}: lì non esiste alcun profilo macchina per questa stampante, né uno da scegliere. Perciò il file non porta dati macchina. Configura la stampante nello slicer oppure passa il file a uno slicer che la conosca. |
| Erzählen Sie anderen von {app}, … | Parli di {app} ad altre persone, oppure mi scriva cosa dovrebbe migliorare. | Parla di {app} ad altre persone, oppure scrivimi cosa dovrebbe migliorare. |
| Eine Programmdatei stimmt nicht mit der Auslieferung überein … | … Reinstalli Solidon; se non aiuta, si rivolga all'assistenza. | Un file del programma non corrisponde alla versione consegnata. Reinstalla Solidon; se non basta, rivolgiti all'assistenza. |
| Der Bereichstest umfasst {count} Kombinationen … | … Renda modificabili meno misure. | Il test dell'intervallo comprende {count} combinazioni; il limite è {limit}. Rendi modificabili meno misure. |
| Diese runde Wand geht ohne Kante in ihre Nachbarn über … | … Ridisegni il contorno. | Questa parete tonda si fonde con le vicine senza spigolo; il suo raggio non può essere modificato da solo. Ridisegna il contorno. |
| Jeder Wert hier wird aus einem anderen gerechnet … | … Spunti quello che deve essere regolabile … | Ogni valore qui è calcolato da un altro. Spunta quello che deve essere regolabile — così perde la sua formula. |
| Ob es inzwischen antwortet, sehen Sie unter {address}. | Può vedere se nel frattempo risponde su {address}. | Puoi vedere se nel frattempo risponde su {address}. |
| An {slicer} übergeben — das Fenster gehört jetzt Ihnen. | … la finestra ora è sua. | Consegnato a {slicer} — la finestra ora è tua. |
| Automatisch zugeordnet. Was hier steht, … Ihre Änderungen … | … Solidon aggiunge sopra solo le sue modifiche … (liest sich als „die Änderungen von Solidon“) | Assegnato automaticamente. Ciò che compare qui viene dallo slicer; Solidon aggiunge sopra solo le tue modifiche e i suggerimenti accettati. |
| Diese Rundung grenzt nicht an zwei ebene Flächen … | … Raccordi invece di nuovo. | Questo raccordo non confina con due facce piane: non si può ricondurre a uno spigolo. Raccorda di nuovo. |
| Diese Rundung lässt sich nicht auf eine Kante zurückführen — … | … raccordi invece di nuovo. | Questo raccordo non si può ricondurre a uno spigolo: raccorda di nuovo. |
| Diesen Wert des Herstellers kann Solidon nicht übersetzen … | … finché non modifica il campo. | Solidon non può tradurre questo valore del produttore. Viene stampato finché non modifichi il campo. |
| Ich bin Robert aus dem Raum Bamberg … | … Se le fa risparmiare lavoro, qui può ricambiare. | Sono Robert, della zona di Bamberga in Germania, e sviluppo {app} da solo, dal programma all'assistenza. Se ti fa risparmiare lavoro, qui puoi ricambiare. |
| Ihr Name oder Kürzel | Il suo nome o pseudonimo | Il tuo nome o pseudonimo |
| Ihr Slicer entscheidet je Teil … | Il suo slicer decide per ogni pezzo. … | Il tuo slicer decide per ogni pezzo. Con PrusaSlicer e Cura vale l'impostazione di Solidon per il materiale. |
| Ihre Einstellung. Zurücksetzen auf {value} aus {source}. | La sua impostazione. … | La tua impostazione. Ripristina {value} da {source}. |
| Wofür das Geld ist und wie Sie freiwillig helfen können. | … e come può aiutare volontariamente. | A cosa servono i soldi e come puoi aiutare volontariamente. |
| Die Toleranzen dieses Materials sind Startwerte … | … si adattano alla sua stampante. | Le tolleranze di questo materiale sono valori di partenza. Con il corpo di prova per le tolleranze si adattano alla tua stampante. |
| Fragt beim Start bei solidon3d.de nach … | … senza la sua conferma. | Chiede a solidon3d.de all'avvio. Nulla viene scaricato o installato senza la tua conferma. |
| Fragt einmal bei solidon3d.de nach … | … senza la sua conferma. | Chiede a solidon3d.de una volta. Nulla viene scaricato o installato senza la tua conferma. |
| Freiwillig und ohne Gegenleistung: … | … Solo il suo clic apre PayPal … | Volontario e senza controprestazione: nessun ordine, nessuno sblocco, nessuna detrazione da un acquisto successivo, nessuna ricevuta di donazione. Solo il tuo clic apre PayPal o GoFundMe nel browser predefinito; in quel momento i dati passano al fornitore scelto. |
| Ob und wie gestützt wird … Profil Ihres Slicers … | … dal profilo del suo slicer. … | Se e come si mettono i supporti. Automatico prende il tipo dal profilo del tuo slicer. L'albero richiede meno materiale e si stacca più facilmente, la griglia regge con più sicurezza gli sbalzi pesanti. |
| Protokoll anhängen — es kann Dateipfade Ihres Rechners enthalten | … del suo computer | Allegare il protocollo — può contenere percorsi di file del tuo computer |
| Stützen an. Welche Art, bestimmt das Profil Ihres Slicers. | … del suo slicer. | Supporti attivi. Il tipo lo decide il profilo del tuo slicer. |
| Der Träger hat ein anderes Material … | … assegni filamenti adatti … | Il corpo di supporto ha un materiale diverso. I colori vengono conservati; assegna filamenti adatti alle zone di colore interessate. |
| Für diese Handlung ist keine Fläche gewählt — … | … ne clicchi una nella vista. | Per questa azione non è scelta alcuna faccia: fai clic su una nella vista. |
| Öffnet die Rückmeldung. Gesendet wird erst nach Ihrer Vorschau. | … prima che lei abbia visto l’anteprima. | Apre il modulo di riscontro. Non viene inviato nulla prima che tu abbia visto l'anteprima. |

Außerdem sollte der Wächter nachgeschärft werden: Lei-Imperative auch mitten im
Satz (nach „oppure“, „e“, „poi“) und mit Pronomen („Faccia di nuovo clic“,
„lo apra“, „si rivolga“), dazu „sua/suo/Suo“, wo die deutsche Quelle „Ihr/Ihre“
sagt, und „può“/„lei“, wo sie „Sie“ sagt. Ohne diese Erweiterung kommen die Formen
mit jedem neuen Eintrag wieder.

### T2 · it · Changelog 0.5.1: zwei voi-Stellen — T

`changelog/it.md` am Endstand `ec0298b15`:

| Zeile | heute | richtig |
|---|---|---|
| 55 | … e le quote che non avete digitato restano esattamente come sono state misurate. | … e le quote che non hai digitato restano esattamente come sono state misurate. |
| 113 | Dove il vostro slicer limita già la velocità … | Dove il tuo slicer limita già la velocità … |

Der Rest des Abschnitts ist sauber: „tu“ durchgehend, «Dividi» für *Teilen*,
«Dividi il modello» und «Tagliare via» wie im Katalog, „passo per passo“ und
„a passo d'uomo“ bleiben zu Recht.

### T3 · fr · *Automatisch teilen* heißt „Découper automatiquement“ und kollidiert mit *Abschneiden* „Découper“ — T

Die neue Regel in `uebersetzung.md` sagt, die Operation *Teilen* folge
*Automatisch teilen*, weil dessen Schritte sie sind. In es/it/pt/en stimmt das
(Dividir/Dividir automáticamente, Dividi/Dividi automaticamente, Split/Split
automatically). In fr heißt *Teilen* jetzt „Diviser“, *Automatisch teilen* aber
weiter „Découper automatiquement“, und *Abschneiden* (verwirft die andere Seite)
heißt „Découper“. Für den Kunden sind damit „Découper“ (wirft weg) und „Découper
automatiquement“ (behält alle Stücke) dasselbe Verb, und der Tourtext sagt „deux
étapes « Diviser » … c'est ainsi que Découper automatiquement a partagé …“.

Richtig: *Automatisch teilen …* → „Diviser automatiquement …“, „Fortschritt:
Automatisch teilen“ → „Progression : division automatique“, dazu alle 18
fr-Einträge mit „Découper automatiquement“/„découpe automatique“. Die neuen
Einträge des Pakets ziehen mit:

| Schlüssel | heute | richtig |
|---|---|---|
| Automatisch teilen trägt ein, in wie viele Stücke es teilt … | Découper automatiquement indique en combien de pièces il découpe. À partir de trois, … | Diviser automatiquement indique en combien de pièces il divise. À partir de trois, elles s'appellent « 1 sur 3 », « 2 sur 3 »… ; zéro signifie : A et B. |
| Seine Nummer in dieser Zählung … | … elle est aussitôt découpée à nouveau. | Son numéro dans ce décompte. Zéro signifie : elle est aussitôt divisée à nouveau. |
| Stücke des Laufs | Pièces du découpage | Pièces de la division |

`website/fr/manual.html` (5 Stellen) und die fr-Handbuchseiten ziehen mit. Die
Kollision bestand schon vorher. Mit der neuen Regel ist sie jetzt aber ein
dokumentierter Widerspruch.

### T4 · pt · englische Anführungszeichen in zwei geänderten Einträgen — T (Kleinigkeit)

Der pt-Bestand setzt «…» (244 Einträge), “…” steht nur in 4. Zwei davon hat das
Paket angefasst:

| Schlüssel | heute | richtig |
|---|---|---|
| Im Verlauf stehen zwei gewöhnliche Schritte „Teilen“: … | No histórico estão dois passos “Dividir” comuns: … | No histórico estão dois passos «Dividir» comuns: foi assim que Dividir automaticamente desmontou a calha. Três peças — numa mesa de 220 não é possível com menos. |
| Öffnen Sie den ersten „Teilen“-Schritt … | Abra o primeiro passo “Dividir” com um duplo clique … | Abra o primeiro passo «Dividir» com um duplo clique e desloque a posição — a junta move-se, e os pinos e ajustes vão com ela. |

### T5 · alle · Übergabeliste „Für das Handbuch“, Punkt 3 unvollständig — T (Handbuch-Sitzung)

Die Seite `window` („Jeder Bereich beantwortet eine eigene Frage.“) nennt *Trennen*
zweimal und *Teilen* einmal. Die Liste in `texte-schluss.md` nennt nur die
Werkzeugreihe. Nachzuziehen sind außerdem en „*Move* and *Split* really change the
model“ → *Cut*, it „*Sposta* e *Dividi* cambiano …“ → *Taglia* und im Satz zu den
Handlungen rechts („with a single one *Drill a bore*, *Hollow out* and *Split*“)
es/pt *Separar* → *Dividir* und fr *Séparer* → *Diviser* (en *Split* und it
bleiben dort richtig).

### T6 · en/it · Cut neben Cut away, Taglia neben Tagliare via — N

en heißt *Trennen* jetzt „Cut“ und *Abschneiden* „Cut away“, it „Taglia“ gegen
„Tagliare via“. Beides lässt sich unterscheiden, und der Wächter vergleicht
Stämme nur bei Einwortnamen. Das Wort „away“ bzw. „via“ trägt die ganze
Unterscheidung. Außerdem steht „Tagliare via“ im Infinitiv, wie sonst nur noch
„Uniformare i triangoli“, „Verificare il percorso di montaggio“ und „Tagliare un
campo di fori“. Die übrigen gut 120 Operationstitel stehen im Imperativ.
Vorschlag für nach 0.5.1: die vier auf den Imperativ ziehen („Taglia via“ …) und
beobachten, ob Kunden die beiden Namen auseinanderhalten.

### T7 · de · „nebeneinander legen“ — N

In „Die zwei Hälften liegen im Modell noch aneinander. Zum Drucken nebeneinander
legen.“ und „Die Teile liegen …“ ist das Verb nach Duden zusammenzuschreiben
(„nebeneinanderlegen“). Das kostet einen neuen Schlüssel in fünf Katalogen,
deshalb erst nach 0.5.1.

### Geprüft und in Ordnung (Textpaket)

- *Trennen* ≠ *Teilen* in allen fünf Katalogen außerhalb des Handbuchs: Jeder
  Oberflächentext, der „Teilen“ oder *Trennen* zitiert, nennt den Knopf so, wie er
  heißt (en Cut/Split, es Separar/Dividir, fr Séparer/Diviser, it Taglia/Dividi,
  pt Separar/Dividir). Die Handbuchseiten sind übergeben (Punkte 1 bis 3, dazu T5).
- Innenwand: alle sechs Seiten × fünf Sprachen mit richtigem Genus (fr „Face
  supérieure intérieure“ gegen „Côté gauche intérieur“, it durchgehend maskulin),
  deckungsgleich mit den Seitennamen.
- fr „Échap“: außerhalb der zwei ausgetragenen Handbuchseiten kein „Esc“ mehr. Die
  Eingabetaste heißt in allen neun Einträgen en/pt Enter, es Intro, fr Entrée, it
  Invio.
- it „passaggio“: im Verlauf durchgehend. „Passo“ bleibt für Steigung, Teilung,
  Rasterweite, Agentenschritte und Tour („Primi passi“, „Passo dopo passo“), wie
  die Regel es will. Ausnahmen aus main siehe M1.
- Die 302 it-Änderungen einzeln als Wortdiff gelesen: Klitika (Selezionala,
  Scaricalo, Toglilo, Inseriscila), der verneinte Imperativ („oppure non
  mantenerli“), Kongruenz und „componente → blocco“ nach Glossar sind richtig.
- RM-271, RM-229, halves_in_place, Prüfstück: Platzhalter vollständig,
  Zeilenumbrüche und Markdown wie in der Quelle, es/fr/pt im Register des
  Bestands (usted, vous, Imperativ mit -a/-e und Infinitiv bei Bedienaktionen),
  Genus stimmt („Colóquelas“, „Mettile una accanto all'altra“, „Pezzi della
  divisione“).
- Deutsche Quellen: kurz und sachlich. Die Aufzählung „Senkung, Stufen und
  Verengung“ zählt die drei Teile auf, die tatsächlich mitgehen, und ist keine
  Stilfigur.

## Befunde Oberflächenpaket

### U1 · fr, it · typografischer Apostroph gegen die neue Regel — T (beim Merge einsetzen)

Das Textpaket legt in `uebersetzung.md` fest, dass fr und it den geraden Apostroph
schreiben. Die neuen Einträge des Oberflächenpakets haben durchgehend „’“. Kein
Test schlägt an, weil kein Eintrag beide Formen mischt. Richtig:

| Sprache | Schlüssel | heute | richtig |
|---|---|---|---|
| fr | Der Testkörper prüft Passungen um genau diesen Durchmesser. | Le corps d’essai … | Le corps d'essai vérifie des ajustements autour de ce diamètre précis. |
| fr | Diese Bohrung ist das Durchgangsloch einer Schraube {size}. | … d’une vis {size}. | Ce perçage est le trou de passage d'une vis {size}. |
| fr | Kein Normgewinde passt in diese Bohrung: Sie ist enger als das Kernloch von {size}. | … l’avant-trou … | Aucun filetage normalisé ne convient à ce perçage : il est plus étroit que l'avant-trou de taraudage de {size}. |
| fr | Keine Einpressbuchse der Normteiltabelle hat ein so weites Loch. | … n’a … | Aucun insert de la table des pièces normalisées n'a un trou aussi large. |
| fr | Keine Mutter der Normteiltabelle hat ein so weites Schraubenloch. | … n’a … | Aucun écrou de la table des pièces normalisées n'a un trou de vis aussi large. |
| fr | Mit dem gewählten Schritt werden auch diese abhängigen Schritte gelöscht: | … avec l’étape sélectionnée : | Ces étapes qui en dépendent seront également supprimées avec l'étape sélectionnée : |
| fr | Mit dem gewählten Schritt wird auch dieser abhängige Schritt gelöscht: | … avec l’étape sélectionnée : | Cette étape qui en dépend sera également supprimée avec l'étape sélectionnée : |
| fr | Passend ist die Einpressbuchse {size}: … | L’insert adapté est {size} : son trou d’insertion … | L'insert adapté est {size} : son trou d'insertion élargit ce perçage. |
| fr | Passend ist die Mutter {size}: … | L’écrou adapté est {size} : … | L'écrou adapté est {size} : son trou de vis englobe ce perçage. |
| it | Passend ist die Einpressbuchse {size}: … | L’inserto adatto è {size}: … | L'inserto adatto è {size}: il suo foro di inserimento allarga questo foro. |

Die zwei „Normteiltabelle“-Zeilen nehmen dabei zugleich das häufigere „table des
pièces normalisées“ statt „tableau“ auf (7 Stellen gegen 3).

### U2 · en · Wortstellung beim Innengewinde — T (Kleinigkeit)

„In diese Bohrung passt ein Innengewinde {size}.“ heute „An internal thread
{size} fits this hole.“, richtig „An {size} internal thread fits this hole.“
(„An M6 internal thread …“ ist auch mit dem Artikel richtig).

### U3 · en, it · „nimmt diese Bohrung auf“ — T (Kleinigkeit)

„Passend ist die Mutter {size}: Ihr Schraubenloch nimmt diese Bohrung auf.“

| Sprache | heute | richtig |
|---|---|---|
| en | The matching nut is {size}: its screw hole takes in this hole. | The matching nut is {size}: its screw hole encloses this hole. |
| it | … il suo foro per la vite comprende questo foro. | Il dado adatto è {size}: il suo foro per la vite ingloba questo foro. |

es „abarca“, fr „englobe“ und pt „abrange“ treffen es.

### U4 · de · „Ihr“ nach dem Doppelpunkt liest sich als Anrede — N (oder beim Merge)

„Passend ist die Einpressbuchse {size}: Ihr Einpressloch weitet diese Bohrung
auf.“ und „Passend ist die Mutter {size}: Ihr Schraubenloch nimmt diese Bohrung
auf.“ In einer Oberfläche, die mit „Sie“ spricht, liest man „Ihr Einpressloch“
zuerst als „Ihres“. Richtig: „Passend ist die Einpressbuchse {size}; ihr
Einpressloch weitet diese Bohrung auf.“ und „Passend ist die Mutter {size}; ihr
Schraubenloch nimmt diese Bohrung auf.“ Die Übersetzungen sagen schon „its / su /
son / il suo / o seu“ und bleiben, nur die Schlüssel ändern sich.

### U5 · es, pt, en · Testkörper-Satz — N

„Der Testkörper prüft Passungen um genau diesen Durchmesser.“

| Sprache | heute | richtig |
|---|---|---|
| es | El cuerpo de prueba comprueba ajustes en torno a exactamente este diámetro. | El cuerpo de prueba comprueba ajustes justo en torno a este diámetro. |
| pt | O corpo de teste verifica ajustes em torno exatamente deste diâmetro. | O corpo de teste verifica ajustes exatamente em torno deste diâmetro. |
| en | The test body checks fits around exactly this diameter. | The fit test body checks fits around exactly this diameter. (Name des Bausteins: „Fit test body“) |

### U6 · fr · Kurzhilfe im Verlauf mit festem Doppelpunkt — N

`panels._changed_parameters` setzt „{label}: {alt} → {neu}“ als f-String
zusammen. In fr fehlt damit das Leerzeichen vor dem Doppelpunkt, das der ganze
Katalog setzt („Largeur : 40,00 mm → 90,00 mm“). Richtig wäre ein übersetzbarer
Rahmen, etwa `tr("{name}: {before} → {after}")`.

### U7 · de · Handbuchsatz des Pakets — N (Handbuch-Sitzung)

Der vorgeschlagene Satz „Liegt eine getippte Zahl außerhalb der Grenzen, übernimmt
Solidon sie nicht: Die Zahl bleibt markiert stehen, darunter steht die Grenze, und
*Parameter ändern …* führt direkt dorthin.“ ist eine Dreierfigur mit
„stehen/steht“. Kürzer: „Liegt eine getippte Zahl außerhalb der Grenzen,
übernimmt Solidon sie nicht und nennt darunter die Grenze; *Parameter ändern …*
führt dorthin.“

### Geprüft und in Ordnung (Oberflächenpaket)

- Löschnachfrage: vier Sätze nach Zahl der gewählten und abhängigen Schritte,
  „· 2 Bohrung setzen“ aus dem Registertitel, „und {count} weitere“ (bestehender
  Schlüssel), Rückweg „Strg+Z stellt beide wieder her.“ bzw. „… alle gemeinsam …“.
  Das entspricht `fenster.md` (Nachfrage nennt abhängige Schritte und Strg+Z). In
  allen fünf Sprachen stimmen Zahl und Genus (fr „toutes“ für étapes, it
  „passaggi … essi“, es „él/ellos“). Die zwei alten Schlüssel sind aus allen fünf
  Katalogen entfernt.
- „Parameter {name}“: Parámetro, Paramètre, Parametro, Parâmetro.
- Gewinde, Einpressbuchse, Mutternfalle, gedruckte Schraube, Toleranz-Testkörper:
  Die Begriffe decken sich mit dem Bestand (Innengewinde, Kernloch → „Tap drill
  hole / Agujero para roscar / Avant-trou de taraudage / Foro per filettatura /
  Furo para roscar“, Durchgangsloch, Normteiltabelle). Die Platzhalter {size},
  {smaller}, {larger} und {measure} sind überall vollständig.
- Ablehnung über der Grenze: „{value} liegt über der Obergrenze {limit}.“ und
  „… unter der Untergrenze …“. Die Übersetzungen nehmen die Wörter der
  Grenzfelder (Upper bound, Límite superior, Borne supérieure, Limite superiore,
  Limite superior). Der Knopf *Parameter ändern …* ist der bestehende Menütext in
  allen Sprachen.
- „Ohne Text gibt es nichts aufzubringen.“ und „Stelle zeigen“ sind bestehende
  Schlüssel. Neue Texte zu *Stelle zeigen* und zur gesperrten Übernahme im
  Operationsdialog gibt es nicht, beide zeigen denselben Grenzsatz.
- Keine geschützten Leerzeichen, fr mit Leerzeichen vor „:“, keine Lei- oder
  voi-Form, kein „Esc“.

## Merge-Nachträge aus main (keinem Paket zuzurechnen)

### M1 · it · „passo“ für einen Schritt im Verlauf — T

| Schlüssel | heute | richtig |
|---|---|---|
| Ein runder Rand wie die Mündung einer Bohrung … wie in Schritten aus älteren Versionen. | … come nei passi delle versioni precedenti. | Un bordo rotondo, come l'imboccatura di un foro, conta come orizzontale, sopra o sotto solo se è orizzontale. In una parete laterale si chiama «Verticale», ma non appartiene a nessun gruppo: sceglilo da solo. Senza spunta, ogni bordo rotondo conta come orizzontale, come nei passaggi delle versioni precedenti. |
| {lip} hält nur auf einer Seite, … prüfen Sie im Schritt die Richtung. | … oppure controlla la direzione nel passo. | {lip} trattiene solo da un lato, perché il blocco è inclinato rispetto alla faccia. Posizionalo perpendicolare alla faccia: fai clic sulla faccia oppure controlla la direzione nel passaggio. |

Die neuen fr- und it-Einträge auf main (Kantengruppen, Schraube und Mutter,
Haltelippe) schreiben ebenfalls „’“. Sie mischen nicht, stehen aber gegen die
Apostroph-Regel des Textpakets, wie U1.

## Nachtrag 8314edf08

Zweig `texte-051-nachtrag`, Commit `8314edf08` über dem Merge-Stand `417b42924`
(main plus beide Pakete). Geprüft wurden der Katalogdiff je Sprache (en/es/pt
je 2 neue, 2 entfernte, 1 bis 3 geänderte Einträge, fr 34, it 39 geänderte),
die Changelogs, `website/fr/features.html`, `fasteners.py` und der Wächter in
`tests/test_translations.py`. Danach liefen dieselben Durchsichten wie oben über
den ganzen Katalog am Stand `8314edf08`.

**Urteil: in Ordnung.** Alle Befunde, die vor dem Tag fällig waren, sind richtig
umgesetzt. Kaputt gegangen ist nichts, und es gibt keine neue Lei- oder
voi-Form. Übrig sind zwei kleine fr-Stellen in der Oberfläche (N1, T) und
Schwächen des Wächters, die erst nach 0.5.1 zählen (N2).

### Umsetzung je Befund

| Befund | Stand |
|---|---|
| T1 it Lei | Alle 33 Einträge stehen in der vorgeschlagenen Fassung. Dazu kommen vier weitere richtig umgestellte Einträge: „— fai di nuovo clic“ am Wickelmuster, „per te?“, „Hai scelto tu stesso“, „hai la {old}“. Meine drei Durchsichten über den ganzen it-Katalog außerhalb des Handbuchs finden keine Lei-Form mehr. Übrig bleiben nur echte Du-Indikative („finché non modifichi“, „se digiti“, „non appena imposti“), Formen der 3. Person („Ha effetto“, „Può richiedere“), das unpersönliche „si potrà“ und „suo“ im Sinn von „sein/ihr“. Die Apostrophe der umgestellten Einträge sind gerade. |
| T2 | it-Changelog Zeilen 55 und 113 richtig. |
| T3 fr | Alle 27 Einträge, die zum automatischen Teilen gehören, sagen „Diviser automatiquement“ bzw. „division“. Kein Eintrag zu *Abschneiden* ist betroffen: „Découper“ und dessen doc-Satz „Découpe un objet selon un plan et conserve un côté“ bleiben, ebenso „découper“ für Tasche, Lochfeld, Ausschnitt und Slicen. Die Changelog-Zeile „La division se fait comme avant.“ und die Funktionsseite sind richtig. Die vier Handbuchstellen und `website/fr/manual.html` hat das Paket in `texte-schluss.md` an die Handbuch-Sitzung übergeben. Zwei Oberflächenstellen fehlen noch, siehe N1. |
| T4 pt | beide Einträge «Dividir» |
| U1 | alle fr-Einträge gerade, „table des pièces normalisées“; it „L'inserto“ |
| U2, U3, U5 | wie vorgeschlagen |
| U4 | neue Schlüssel mit Semikolon und kleinem „ihr“ in allen fünf Katalogen, alte entfernt, Übersetzungen übernommen. Die neuen Abdrücke in `part_ranges.toml` folgen aus dem Dateihash von `fasteners.py`, am Maß ändert sich nichts. |
| M1 | beide Einträge „passaggio“ |

Platzhalter, Zeilenumbrüche, Markdown, Anführungszeichen und Apostrophe
(kein Eintrag mischt) sind in allen geänderten Einträgen sauber.

### N1 · fr · zwei Oberflächentexte zum automatischen Teilen sagen noch „Découper“ — T (Kleinigkeit)

| Schlüssel | Ort | heute | richtig |
|---|---|---|---|
| Ein zu großes Teil zerschneiden, bis jedes Stück auf das Bett passt — mit Passstiften in jeder Schnittfläche. | `main_window.py:4133`, Kurzhilfe des Menüeintrags *Automatisch teilen …* | Découper une pièce trop grande jusqu'à ce que chaque morceau tienne sur le plateau — avec des goupilles dans chaque face de coupe. | Diviser une pièce trop grande jusqu'à ce que chaque morceau tienne sur le plateau — avec des goupilles dans chaque face de coupe. |
| Teile das Teil, damit es auf das Bett passt | `chat.py:95`, Beispielanfrage im Chat | Découpe la pièce pour qu'elle tienne sur le plateau | Divise la pièce pour qu'elle tienne sur le plateau |

Die erste Stelle ist genau der Menüeintrag, um den es bei T3 ging. Die Kurzhilfe
von „Diviser automatiquement …“ beginnt heute mit dem Namen von *Abschneiden*.

### N2 · Wächter `_italian_formal` — N

Er erfüllt seinen Zweck. Am Katalog `417b42924` meldet er 36 Einträge: 32 meiner
33 Funde aus T1 und die vier Nachzügler. Der 33. fehlt, siehe unten. Am neuen
Katalog meldet er keinen, und im heutigen Bestand gibt es keine Fehlmeldung.
Zwei Schwächen bleiben, beide ohne Folgen für 0.5.1:

- **Er mahnt gewöhnliche Wörter an.** `ITALIAN_LEI` enthält Formen, die im
  Italienischen auch Substantive im Plural sind, und läuft mit
  `re.IGNORECASE` nach jedem Satzzeichen. Gegenproben, die alle anschlagen:
  „Selezioni salvate: 3.“, „Disegni e schizzi restano nel passaggio.“,
  „Raccordi e smussi: tutti conservati.“, „Usi tipici: supporti.“ In diesem
  Programm sind „raccordi“, „disegni“ und „selezioni“ häufige Wörter; der erste
  solche Satz macht die Suite rot. Vorschlag: `re.IGNORECASE` weglassen und für
  die mehrdeutigen Formen (Selezioni, Disegni, Raccordi, Spunti, Usi, Copi)
  ein Objekt danach verlangen, etwa `(?=\s+(?:il|lo|la|l'|i|gli|le|un|una|uno|di nuovo|questo|questa|quello|altre|altri)\b)`.
- **Er übersieht Lei-Indikative außer „può“.** Den Satz „finché non modifica
  il campo“ (Quelle „solange Sie das Feld nicht ändern“) hätte er nicht
  gefunden, denn `GERMAN_YOU` kennt weder „solange Sie“ noch „Sie … ändern“,
  und `ITALIAN_FORMAL_VERB` prüft nur „può/lei“. Das Paket nennt die Lücke
  selbst. Dazu kommt eine seltene Fehlmeldung: Wo die Quelle „Ihr Projekt“
  sagt und das Italienische das Possessiv weglässt, zählt ein späteres „il
  suo file“ (sein) als Anrede.

## Changelog 0.5.1 (Zweig `changelog-051`, geprüft ab `b1653cbcc`)

Gelesen wurden alle 38 neuen oder geänderten deutschen Punkte in den fünf
Übersetzungen. Jede Übersetzung eines unveränderten deutschen Punkts ist
gleich geblieben. Die zitierten Namen wurden gegen den Katalog des
Arbeitsbaums geprüft (Sonde `sonden/changelog/cl_zitate.py`). Korrigiert
wurde direkt auf dem Zweig, ein Commit je Datei, Endcommit `a7b046578`.

| Sprache | geänderte Punkte | was |
|---|---|---|
| de | 1 | K3 eindeutig („die passenden … die anderen mit *Stelle zeigen*“) |
| en | 4 | K3; Bahnbreite „bead width“; „Wall rail 2 of 3“ (Objektname im Katalog), „are numbered“; Gewindedialog „names the fitting size at the top“ |
| es | 8 | K3 („cota“); „se sueltan“ (lösen sich) → „siguen siendo desmontables“; „ancho de cordón“; „tramos estrechos“ statt „pasos“; „piezas“, „Listón de pared“; Warnung bei *Solo diámetro del orificio* wieder drin; „retículas“; „al cabo de unos segundos“ |
| fr | 8 | K3 („cote“); „dans les canaux de chaque slicer“ → „dans les canaux, dans tout slicer pris en charge“; „largeur de cordon“; Cura-Punkt wieder mit „comme chez le fabricant“; „Baguette murale“; „aussi profondément“; „Montrer l'endroit“ mit geradem Apostroph (unveränderter deutscher Punkt, aber Knopfname) |
| it | 7 | K3 („quota“); „tratti stretti“ statt „passaggi stretti“ (passaggio ist der Schritt im Verlauf); Übergabe „la consegna“ statt „il passaggio“; „larghezza del cordone“; „Listello da parete“; „alla stessa profondità“; „avvisa se diventa stretta“ |
| pt | 8 | K3 („cota“); „soltam-se“ (lösen sich) → „continuam desmontáveis“; „largura do cordão“; „Calha de parede“; „grelhas“; „pega redonda“ wie im Katalog; „em poucos segundos“; „ao fim de alguns segundos“ |

Alle Punkte haben höchstens 200 Zeichen, keiner beginnt mit `*`, „ oder «. Es gibt
kein Wort der Testfamilie, kein fr-„Esc“ und keinen typografischen Apostroph
mehr. Sonde mit `APP_VERSION = "0.5.1"`: 48 passed, 1 skipped (keine
Presseentwürfe), EXIT 0, Gegenprobe `tests.test_changelog.APP_VERSION = 0.5.1`
(`laeufe/cl-sprache-sonde.txt`). Gebunden: `test_changelog.py` und
`test_translations.py` 203 passed, 1 skipped, EXIT 0 (`laeufe/cl-sprache-tests.txt`).

Bewusst so gelassen:

- es und fr bei *Nur Bohrungsdurchmesser* (Punkt 63): Im Französischen fehlt
  weiter „und warnt, wenn es zu eng wird“. Mit den langen Knopfnamen passt
  der Satz nicht unter 200 Zeichen. Im Spanischen ist er drin, dafür heißt es
  knapp „cambia diámetro y labio“.
- Der fr-Punkt *Kanäle frei halten* hat „elle bloque“ statt „la transmission
  bloque“, der Länge wegen. Gemeint ist dasselbe.
- In it bleibt „il passaggio allo slicer“ in unveränderten Punkten und in der
  Gruppenüberschrift „Stampare e passare allo slicer“. Durch „allo slicer“ ist
  dort klar, was gemeint ist.
- Namen der Qualitätsstufen („Standard“, „Fein“ …) und „0.12mm Fine“ stehen
  nicht im Katalog. Sie sind Namen aus dem Slicerprofil und Teil des
  unveränderten Bestands.
- en „works the edges“ in K3 folgt dem Stil des alten Satzes. Die Kantenwahl
  heißt in allen Sprachen wie in Punkt 74.
