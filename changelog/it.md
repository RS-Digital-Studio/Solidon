# Novità

Questo file è ciò che compare nella finestra di aggiornamento, e nient'altro.
**Non** è un elenco delle modifiche ma una scelta, e scegliere è il lavoro. Un
punto va qui se qualcuno se ne accorge usando il programma. Quanti siano lo
decide la versione, non un numero.

Quindi: niente messaggi di commit, niente nomi di moduli, niente numeri di
paragrafo. «La barra spariva mentre l'applicazione calcolava ancora per quattro
secondi» è un buon commit e una cattiva voce; «L'avanzamento resta finché il
calcolo è davvero finito» dice la stessa cosa a chi sta davanti allo schermo.

Un file per lingua in questa cartella, come per i cataloghi, e tutti portano
gli stessi punti nello stesso ordine (`tests/test_changelog.py`).
`tools/make_download.py` ne prende la sezione della versione corrente e la
scrive in `website/version.json`.

## 0.4.1

### Forare e posizionare

- Quando posizioni un foro, una casella lo trasforma in asola: indichi lunghezza e direzione, e l'anteprima le mostra entrambe.
- Un foro già presente nel modello si allunga in seguito fino a diventare un'asola: il diametro resta quello misurato.
- L'asola viene allargata della tolleranza del materiale su tutta la sua lunghezza. La corsa che una vite ha al suo interno resta quella indicata.
- Se un'asola sporge dal bordo a un'estremità, Solidon lo dice, anche quando il suo centro sta in pieno materiale.
- Un'asola compare nell'albero degli oggetti come asola, con la sua larghezza e la sua lunghezza, anche in un modello che hai aperto e che ha disegnato qualcun altro.
- Un'asola esistente si allunga in seguito, e la sua direzione resta dov'era.
- Un foro o un'asola selezionati si regolano direttamente nella vista con «Imposta nella vista»: una maniglia per spostare e ruotare, pomelli per allungare, quote a bordi e centri.
- Solo «Applica», a destra, ne fa un passo; Esc annulla. Un'asola allungata mostra la sua lunghezza e mantiene la sua forma quando la spostate con la maniglia.

### Riconoscimento

- Una svasatura sopra un foro viene mantenuta anche su un pezzo con superfici tonde e sinuose: prima andava persa, e foro e svasatura non potevano più essere spostati insieme.
- Una cavità interamente nel materiale, senza via d'uscita, compare nell'albero degli oggetti come sacca d'aria, con il suo volume. Prima compariva come un foro inesistente.

### Scrivere

- Una scritta può usare ora otto caratteri invece di tre, più grassetto e corsivo. Il grassetto porta tratti più spessi a parità di altezza e resta leggibile dove lo stile normale sbava.
- Accanto ai caratteri diritti ci sono ora uno tondo e uno manoscritto, entrambi in un solo stile. Tutti e otto viaggiano con il programma, così un progetto appare uguale ovunque.
- Se un carattere è troppo fine per il tuo ugello, Solidon dice da quale altezza tiene, invece di stamparlo e lasciare che le lettere si impastino.

### Blocchi e accoppiamenti

- Un blocco dal catalogo compare subito nella vista: sulla faccia selezionata o sopra il corpo, con quote e maniglia. Un clic lo posiziona altrove, «Applica» lo inserisce.

### Vista e utilizzo

- Le azioni per un corpo o una caratteristica selezionati stanno a destra, in gruppi richiudibili, con ricerca. I menu Oggetto, Modifica e Prepara sono spariti; le scorciatoie restano.
- Il clic destro su un corpo o una faccia mostra solo ciò che esiste soltanto lì: il passo dietro, lo schizzo sulla faccia, il nascondere. Il pulsante «Blocchi» è in colore d'accento.
- Se la catena si arresta a un passo, le azioni sono bloccate e ne dicono il motivo; chi ci prova vede subito le vie d'uscita del rapporto. Prima il passo finiva in silenzio dietro, mai calcolato.

### Piano di stampa e consegna

- Se un corpo fatto di pezzi singoli — una scritta, per esempio — non entra intero in nessun piano, il rapporto propone di separarlo e orientarlo subito: un clic e i pezzi stanno sui piani.
- «Apri nello slicer» consegna a ElegooSlicer, Orca e Bambu Studio tutti i piani in un unico file: una finestra invece di una per piano.
- Per separazione, scritta e texture il rapporto indica il numero nella frase, dove prima c'era un segnaposto tra parentesi graffe.
- Una scritta a cui avete assegnato un filamento lo conserva quando viene separata in lettere. Prima arrivava nello slicer su un secondo filamento grigio, con quello assegnato accanto inutilizzato.
- Con più piatti, le parti arrivano ora nello slicer dove lui tiene i suoi piatti: nella griglia che dispone da sé. Prima le lettere del terzo e del quarto piatto stavano accanto a tutto.

## 0.4.0

### Costruire e modificare

- Le controparti, come una spina e il suo foro, si posano su entrambi i pezzi in un solo passo. Le misure comuni si indicano una volta e un solo annulla ritira la coppia.
- Il loft fra due contorni accetta ora due disegni distinti: tondo sotto, squadrato sopra. Nasce così l'adattatore da un tubo a un canale.
- Lo sweep lungo un percorso segue un tracciato disegnato con più spigoli e archi, non più un solo arco uniforme. Sugli spigoli vivi Solidon taglia a quartabuono.
- Il raccordo e lo smusso agiscono anche su un singolo spigolo. Lo scegliete in un elenco che indica ogni spigolo con la sua posizione e la sua lunghezza.
- Un blocco raggiunge più punti in un solo passo: quattro fori ricevono insieme le loro boccole e un solo annulla ritira tutti e quattro.
- Novità: *Verificare il percorso di accoppiamento* porta un pezzo nella posizione finale e segnala dove urta per strada, anche quando i due combaciano all'arrivo.
- Ogni blocco può essere scritto come sorgente OpenSCAD, dal catalogo o dalla riga di comando.
- Il nucleo esatto fora anche una faccia inclinata, con svasatura e allargamento; le serie e i montaggi a innesto restano intatti.

### Forare e posizionare

- Quando posate un foro, l'anteprima mostra il contorno dell'imbocco invece di un cilindro semitrasparente. Il punto che conta resta libero.
- L'anteprima segue il mouse in modo fluido: la ricerca della faccia sotto il puntatore non riparte più a ogni movimento.
- I campi delle misure si scostano dal punto in cui nasce il foro, invece di restarci sopra.
- Chi sceglie un'operazione che si posiziona nel modello inizia subito a posizionare; il pulsante precedente sparisce.
- Dopo aver confermato le misure regolate la profondità con il mouse. Il modello diventa traslucido e la vista ruota di lato perché possiate guardare dentro al foro.
- Mentre trascinate, la profondità scatta brevemente nei punti che significano qualcosa: la metà del materiale e la sua faccia posteriore.
- Il parallelepipedo, la sfera e gli altri corpi di base si spostano e si ruotano già nell'anteprima, con la stessa maniglia di un corpo finito.
- I corpi di base hanno un angolo di rotazione: la direzione dice dove punta il corpo, l'angolo dice come è ruotato attorno a essa.
- Forare in un cilindro, una sfera o un toro non produce più a ogni foro l'avviso che sporge oltre il bordo.
- Un foro con svasatura viene rimosso per intero dopo la conferma, invece di lasciare la svasatura senza via di ritorno.

### Caratteristiche e selezione

- Un foro su cui fate clic offre solo le azioni che lì servono a qualcosa; prima comparivano anche la scritta e l'assegnazione del filamento.
- Ogni azione su una caratteristica compare una volta e non due, e sparisce l'intestazione di blocco sopra una sola riga.
- Su una svasatura esistente *Svasare* è di nuovo raggiungibile.
- Nell'albero degli oggetti le caratteristiche dello stesso tipo vengono raggruppate solo se coincide anche la misura. Dieci raccordi di raggio diverso compaiono di nuovo singolarmente.
- Un corpo con filamento assegnato mostra di nuovo la sua selezione nell'immagine, invece di restare grigio come gli altri.
- I campi di una caratteristica portano il loro nome: uno screen reader dice a che cosa appartiene un campo, invece di ripetere sei volte casella numerica, 0,00.

### Blocchi e accoppiamenti

- I vostri blocchi si aprono di nuovo dal catalogo per essere modificati, anche se il progetto da cui provengono non c'è più.
- La scala di tolleranze adotta la misura rilevata del foro su cui la aprite, invece di un valore fisso di 6 mm.
- Ganci e linguette elastiche calcolano con il materiale e la corsa della molla, non con una regola pratica. Solidon segnala un braccio che si rompe al primo scatto.
- I tre corpi di taratura nascono senza corpo ausiliario, e la scala di tolleranze si stampa come due listelli numerati che si innestano fra loro.
- L'avviso della molla misura il braccio reale, la cerniera a film si muove e il pressacavo arriva fino all'anteprima e all'uscita.
- Un blocco depone materiale portante prima di tagliare dove serve; e la loro anteprima si posa bene anche senza supporto.
- Un blocco spiega quale combinazione di misure non è in grado di costruire, invece di tagliarle in silenzio.

### Filamenti e magazzino

- La vostra scorta di filamento ha un posto suo: una tessera nella pagina iniziale e uno scaffale invece di un elenco, con il livello disegnato come avvolgimento sulla bobina.
- Due bobine con lo stesso nome restano distinte. Ognuna porta il proprio residuo, e quella iniziata è quella che interessa.
- Al taglio e alla consegna Solidon chiede se deve scaricare il consumo. Dopo il taglio è la quantità rilevata nel file di stampa, altrimenti una stima.
- Ogni movimento è annullabile, ogni bobina tiene la sua cronologia, e scarica senza chiedere soltanto chi lo imposta espressamente.
- Un filamento assegnato si può togliere di nuovo senza che le facce vicine perdano il loro.
- Una faccia dipinta arriva in Orca e in PrusaSlicer con il suo filamento, non più senza.
- Dopo la rimozione, il profilo del produttore non finisce più sul filamento sbagliato.
- Nello scaffale la ricerca e le azioni principali stanno insieme, e il luogo di deposito e la carica nominale figurano nella finestra della bobina.

### Stampa e preparazione

- Solidon trova quello che ha Cura: stampanti, profili di processo e filamenti che prima restavano invisibili.
- Da PrusaSlicer Solidon riprende i filamenti caricati e l'ultima stampante impostata.
- Se il vostro slicer non conosce affatto la stampante, Solidon lo dice, invece di mandarvi a un elenco in cui non c'è nulla.
- Cambiare livello di qualità richiede secondi e non quasi un minuto, e la finestra resta utilizzabile nel frattempo.
- La consulenza sulle impostazioni di stampa guarda tutti i corpi del piano e non solo la selezione. Ciò che serve a un corpo resta, anche se quello accanto ne fa a meno.
- Calcola in secondo piano, nomina il corpo, mostra il suo avanzamento e si può interrompere.
- Un ponte lungo viene valutato sui suoi appoggi reali, e l'angolo di sporgenza vale per stampante, ugello, altezza di strato e larghezza di linea con cui è stato rilevato.
- Una velocità troppo alta viene limitata sul tipo di percorso interessato, invece di scaldare sempre di più ugello e piano.
- Le proposte deselezionate restano deselezionate, e un cambio di filamento, scena, piano o qualità invalida subito un risultato superato.
- La distanza nella disposizione conta il bordo di adesione e la struttura di supporto: fra due vicini entrambi contano doppio.
- I pezzi vengono disposti al centro del piano, come fanno gli slicer accanto, e non nell'angolo posteriore sinistro.
- Orientare per la stampa ridispone poi i pezzi ruotati. Un corpo che si corica occupa più superficie e prima finiva dentro al vicino.
- La seconda scelta del filamento sotto i profili dello slicer è sparita. Ripeteva il selettore del filamento; recuperare i valori del profilo è ora un pulsante a sé.
- Orientare per la stampa prende ora tutti i corpi della scena, non solo quelli selezionati. Così l'intero piano si sposta al centro invece che un pezzo ruotato schivi verso l'angolo uno rimasto fermo.

### Vista e utilizzo

- Il puntatore del mouse di Solidon vale per l'intera finestra e per ogni finestra di dialogo, non più solo per la vista 3D.
- Cambiare variante in una finestra di operazione non chiude più l'applicazione.
- Una finestra di operazione aperta non sopravvive più in silenzio a un cambio di progetto.
- Le note lunghe non vengono più tagliate mentre accanto resta spazio libero.
- Dalla riga di comando non era possibile richiamare *Assegnare filamento*; ora sì.
- Il primo clic e la prima rotazione non scattano più: ciò che la vista deve preparare per essi avviene ora all'avvio.

### Aggiornamento, installazione e sistema

- In *Novità* compaiono le ultime tre versioni. La cronologia completa di tutte le versioni sta su solidon3d.de e resta consultabile lì.

### Manuale e sito web

- Le immagini di solidon3d.de mostrano il modello per tutta la larghezza, non come una striscia fra i pannelli.
- Manuale e sito web nominano ogni operazione esistente, compresi i nuovi editor delle caratteristiche.

## 0.3.5

### Vista

- La vista 3D disegna con un nuovo livello grafico. Si rivolge alla scheda grafica tramite Direct3D 12, Vulkan o Metal e resta fluida anche con diversi milioni di triangoli.
- Incavi e spigoli risaltano di più: la vista scurisce gli angoli, traccia linee di profondità e coglie il punto che stai indicando.
- Gli spigoli dei corpi stanno come reticolo fine sopra la superficie, e le etichette restano ferme invece di tremare durante la rotazione.
- I nomi delle caratteristiche non si sovrappongono più e i loro segni restano visibili anche nella sezione.
- L'indicatore degli assi in basso a sinistra riempie il suo campo in ogni direzione di vista e le sue lettere si vedono per intero.
- Le viste fisse ruotano la telecamera attorno al punto che stai guardando. L'inquadratura resta invece di tornare all'intera scena; per inquadrare c'è sempre *Adatta alla vista*.
- Puntare attraverso un'apertura sulla faccia dietro di essa seleziona quella faccia e non il bordo dell'apertura.
- I modelli grandi si costruiscono più rapidamente, perché spigoli e normali vengono calcolati una sola volta per corpo.
- Se al computer manca il supporto grafico che la vista richiede, l'applicazione indica i due pacchetti da installare.
- Se inclini la vista vicino a un asse, scatta lì mantenendo la tua rotazione, invece di saltare a una posa fissa.

### Azioni per la selezione

- Il rapporto di verifica e la chat si chiudono a destra con un bordo proprio. Le azioni per la selezione stanno sotto in una scheda propria e tra le due si vede il modello.
- Quali azioni stiano davanti dipende dalla selezione: con più corpi Unisci, Sottrai e Intersezione, con uno solo Pratica un foro, Svuota e Dividere.
- Su un foro selezionato compaiono Svasa e Chiudi un foro; su una faccia, Pratica un foro, Ritaglia tasca e Scosta la faccia.
- Un corpo selezionato mostra lì i suoi filamenti e permette di cambiarli.
- Un campo di ricerca nella stessa scheda trova le altre operazioni; caratteristiche e componenti restano nelle proprie aree.
- La colonna di destra è più larga: le azioni per la selezione ci stanno per intero, invece di stringersi in metà larghezza.

### Costruire e modificare

- Unisci, Sottrai e Taglia prendono tutti i corpi selezionati in una volta, non esattamente due.
- Raccorda non porta più giù l'applicazione quando il raggio supera la parete che deve arrotondare.
- Un corpo del nucleo esatto resta esatto se lo si sposta o lo si ruota soltanto. Raccordi e smussi restano possibili in seguito.
- L'utensile di foratura sporge solo alla bocca del foro e rifiuta diametri che superano il pezzo di parecchie volte.
- Allineare a filo significa a filo entro un angolo, non entro una singola distanza tra punti.
- Ridurre i triangoli si ferma a una risoluzione nominata, e il riempimento a reticolo non inventa più un interno che non c'è.
- L'editor di schizzi coglie gli archi sul cerchio intero, trova i bordi dei cerchi, cancella con Canc l'elemento scelto e non lascia Ripeti in sospeso.
- Il riscontro durante la modellazione non dichiara più senza effetto le piccole modifiche.
- Gli interruttori di un'operazione attivi per impostazione predefinita ora si possono disattivare anche da riga di comando.
- Un errore in un'operazione indica la sua causa: nel registro, nella riga che l'ha fermata e nel rapporto di errore.
- Gli inserimenti rifiutati in posizionamento, deposito delle mesh e ricette arrivano con una proposta di azione invece di un errore nudo.
- I componenti spiegano quali combinazioni di parametri non costruiscono, invece di tagliare le misure in silenzio.
- Un numero inadatto di corpi selezionati viene segnalato prima del calcolo, invece di tralasciare un ingresso senza che si veda.
- Posizionare su una superficie modifica il documento solo alla conferma; un'anteprima scartata non lascia nulla dietro di sé.
- Lettere e cifre restano nel campo di immissione: i tasti di navigazione agiscono solo quando non stai scrivendo lì.
- Separa in pezzi distinti trasforma più corpi staccati di un file in un oggetto ciascuno: ciò che non si tocca non è un pezzo solo.

### Caratteristiche

- Una scansione importata non porta più cupole e coppe inventate; finora nascevano a centinaia da superfici arrotondate in modo uniforme.
- Più filetti su una piastra vengono nominati singolarmente invece di essere riuniti in una sola caratteristica.
- Sfera, toro e cono dichiarano la loro curvatura, i centri dei cilindri coincidono con gli anelli terminali e i passi di filetto seguono l'asse.
- Il pannello delle caratteristiche propone accoppiamenti solo quando è selezionato un secondo corpo e conosce ogni gruppo del nucleo.
- Gli accoppiamenti di taglio automatici non assegnano più due volte lo stesso nome.
- Il riconoscimento delle caratteristiche raggiunge lo stesso risultato più in fretta su reticoli complessi.

### Stampa e preparazione

- La ricerca dell'orientamento giudica in due fasi: duecento posizioni dalle normali, nove delle quali nell'analisi a strati.
- La sua barra di avanzamento arriva alla fine anche quando non c'era nulla da tagliare.
- Lo slicer riceve il mondo della stampante e non quello di Solidon, e un profilo proprio mantiene la sua base del produttore.
- I profili di slicing propri stanno davanti al profilo del produttore con lo stesso nome, e un AppImage ritrova le sue scorte.
- La pulizia dopo l'importazione conserva le assegnazioni dei filamenti.
- La stampante appartiene al progetto e si cambia sia nell'intestazione sia nella finestra di stampa; filamenti assegnati, colori e i tuoi valori di stampa restano.
- Ogni corpo porta il suo filamento nell'albero degli oggetti: un campo colore davanti al nome, un clic per assegnarne un altro.
- Più bobine dello stesso tipo di materiale restano distinguibili per nome e colore.
- Le operazioni relative prendono il nome da ciò che fanno: *Assegna filamento* e *Filamento su una faccia* invece di *Colora il pezzo* e *Colora la faccia*.
- La consegna allo slicer risolve ogni bobina secondo il proprio tipo di materiale; i tuoi valori di stampa mantengono la precedenza.
- Se la mappa dei supporti impiega troppo tempo, il calcolo termina con una spiegazione e propone di ridurre i triangoli.
- La finestra di stampa resta pienamente utilizzabile anche in finestre strette.
- Orienta per la stampa allinea tutti i corpi selezionati, non solo il primo.

### File e progetti

- Un 3MF con molti livelli di duplicazione viene rifiutato prima che da 432 byte nascano mille corpi.
- Un piccolo file di progetto non richiede più gigabyte di memoria.
- Un file GLB in millimetri arriva in millimetri e non come metri.
- Un salvataggio fallito non porta più via l'ultima copia di sicurezza, e annullare annulla davvero l'importazione.
- Un errore tardivo durante la lettura non svuota più la sorgente del progetto successivo.
- Se la cartella della cache non si può creare, il risultato già calcolato resta comunque.
- Un insieme di varianti incompleto non viene più esportato in silenzio.
- Lo schizzo scartato si recupera con Annulla, e un secondo oggetto della cronologia non lascia più un Ripeti scaduto.
- Due rapporti di errore dello stesso secondo non si sovrascrivono più.
- Gli ingressi scelti espressamente sopravvivono al salvataggio e alla riapertura, invece di essere sostituiti da un valore predefinito.
- Annullare termina anche il calcolo che gira ancora dietro una variante.

### Chat e IA

- Uno strumento aggiuntivo con un campo di tipo errato non interrompe più l'intera serie dell'agente.
- Per le varianti di schizzo l'agente indica solo percorsi di menu che esistono.
- Nella generazione di immagini i pesi arrivano interi o non arrivano, e un singolo valore nel campo della struttura non avvia più una generazione non richiesta.
- Un modello locale viene misurato anche quando risponde via HTTPS su una porta propria.
- L'avviso sulla partecipazione dell'IA vale solo con una prova scritta, e un cambio di lingua non termina più il comando a distanza.
- La configurazione di ComfyUI riprende i pesi del modello già completi, invece di scaricarli di nuovo.

### Aggiornamento, installazione e sistema

- La versione minima è ora macOS 13, uguale nel pacchetto, nell'installer e sul sito.
- Tredici librerie sono alle loro ultime versioni stabili, e il nucleo esatto parla OpenCASCADE 8.
- Un pacchetto senza ancora di fiducia nel sistema porta con sé il proprio insieme, su qualunque piattaforma.
- Un download non si interrompe più dopo un tempo totale fisso, e una risposta a goccia rispetta il termine promesso.
- Nel Flatpak l'applicazione trova il gestore di pacchetti del computer.
- Su Linux e macOS un'interruzione non finisce più solo al processo padre.
- La voce di menu su Linux trova l'avviatore anche senza voce nel percorso di ricerca.
- Sul Mac la finestra di aggiornamento dice che Solidon torna da sé dopo l'installer.
- Sul Mac il mouse 3D legge attraverso il driver del produttore invece di attendere accanto a esso.
- La schermata iniziale riconosce il sistema prima della prima immagine, e la tabella dei requisiti non viene più tagliata.
- Un allegato rifiutato non conta più come mancante per il riscontro.
- Il selettore dei filamenti resta sulla bobina giusta dopo un annullamento e mostra anche l'ottava.
- Una mail di assistenza aperta a mano porta oggetto e testo leggibili anche dentro Flatpak; un annullamento lascia il rapporto al suo posto.

### Manuale e sito web

- Manuale e schermate mostrano l'interfaccia rielaborata in tutte e sei le lingue.
- I disegni del manuale mantengono il contrasto del testo anche nelle loro note a margine.
- La finestra del manuale carica solo le proprie figure e nessuna immagine estranea.
- Il sito web dice in un unico punto che cosa lascia il tuo computer.
- L'introduzione non afferma più che un foro sia chiuso quando Annulla ripristina solo il diametro.

## 0.3.4

### Modificare le caratteristiche rilevate

- Un foro e la sua svasatura collegata vengono ora spostati insieme, indipendentemente da quale dei due sia selezionato. Il pannello delle caratteristiche indica il collegamento prima della modifica.
- Quando si modifica un foro, la sua svasatura resta associata sotto di esso nell’albero degli oggetti e può essere adattata direttamente.
- Il pannello delle caratteristiche raggruppa le azioni identiche non disponibili e indica con chiarezza i gruppi di campi interessati.

### Riconoscimento delle caratteristiche

- Le filettature dei modelli importati vengono riconosciute in modo più affidabile; coni, perni e sfere errati al loro interno non appaiono più come caratteristiche separate.
- Le giunzioni strette tra forme unite non generano più numerose caratteristiche errate.
- Il riconoscimento delle caratteristiche è sensibilmente più rapido sui modelli grandi e dettagliati.

### Mappe di analisi

- Le mappe di analisi sono disponibili per un numero maggiore di modelli grandi.
- Se una mappa di analisi è troppo grande per un modello, il messaggio propone direttamente *Riduci triangoli*.
- L’analisi del fabbisogno di supporti è notevolmente più rapida sui modelli grandi.

## 0.3.3

### Vista e selezione

- Il primo clic seleziona il pezzo, il secondo il foro sottostante, un clic accanto annulla la selezione, e il comando impostato resta valido per tutto il tempo.
- Ruotando, l'orizzonte resta orizzontale: dopo un gesto la vista è dritta come prima, in ciascuno dei cinque comandi.
- Il comando e il tema scelti nelle impostazioni sono spuntati anche nel menu *Vista*.
- Più corpi selezionati restano selezionati dopo un nuovo calcolo, e un trascinamento li muove insieme.

### Lavoro sul progetto

- Un progetto si può salvare anche quando a una caratteristica è allegata una nota.
- Passare da una mappa di analisi all'altra sullo stesso corpo mostra subito ciò che è già calcolato.
- Un progetto nuovo comincia senza resti di un'anteprima rimasta aperta al momento del cambio.
- Tramite il comando a distanza, *Annulla* ritira esattamente il passo indicato e non l'ultimo.

## 0.3.2

### Modificare le caratteristiche riconosciute

- Spostando, ruotando o rimuovendo un foro non resta materiale nel punto precedente, nemmeno su pezzi con scanalatura o cavità.
- Il comando *Chiudi un foro* riempie ora esattamente il foro: il tappo non sporge più in una scanalatura né ingrossa il pezzo.
- Una sede sferica viene riconosciuta come superficie sferica e non come svasatura, anche in modelli a mesh fitta, e offre così le azioni che le competono.
- Un foro duplicato riceve un'identità propria e non quella di uno eliminato prima, così un accoppiamento indica ancora la caratteristica che intende.
- Anche ruotando, un foro passante segnala se nella nuova orientazione non passa più.
- Una caratteristica appena creata compare in fondo all'albero degli oggetti e non tra quelle precedenti.
### Visualizzazione e selezione

- L'anteprima scompare appena la modifica è applicata; finora il corpo di confronto con la fascia «non ancora applicato» restava sopra il foro finito.
- La barra spaziatrice torna ad alternare prima e dopo solo dove c'è un'anteprima, e non più ovunque nell'applicazione.
- Un foro non si illumina più nel colore della selezione quando non è selezionato nulla.
- L'arco di rotazione, l'ombra, i segni di trascinamento e l'anello del pennello scompaiono con l'azione a cui appartengono, anche al cambio di strumento o alla chiusura.
- Una misura resta sul suo pezzo, anche se la vista passa a un altro piano di stampa o a tutti.
### Stampa e memoria

- Se non tutto entra su un piano, vengono creati tanti piani quanti servono; finora il resto restava accanto al piano, dove non è stampabile.
- La memoria delle caratteristiche dei modelli grandi resta limitata; finora poteva occupare fino a un gigabyte.
## 0.3.1

### Modificare le caratteristiche riconosciute

- Le caratteristiche riconosciute si possono spostare, ruotare, duplicare e rimuovere: un foro, un perno o una cupola; la cupola senza rotazione, perché non ha orientamento.
- Il ridimensionamento funziona ora anche per un perno o una cupola; finora solo per un foro.
- I valori misurati sono già nei campi: non serve più chiudere e riforare con numeri ricopiati a mano.
- Un foro spostato resta lo stesso foro: ogni accoppiamento che lo indica conserva il suo riferimento.
- Quando un'azione non ha senso per una caratteristica, resta visibile e spiega in una frase perché, invece di mancare in silenzio.
- Un pannello *Caratteristica* si apre a destra appena si seleziona la prima caratteristica e mostra ciò che vi è stato misurato; si può staccare, chiudere e riprendere da *Vista*.
- Ogni numero è modificabile: posizione, diametro, profondità e asse si impostano nel campo, senza finestre intermedie.
- Un numero modificato appare come anteprima nell'immagine prima di essere applicato.
- Una casella *Applica a tutti dello stesso tipo* modifica un'intera fila di fori in una volta, con un solo passo per annullare.
- Due caratteristiche selezionate indicano la loro distanza da centro a centro e per asse.
- Un foro indica la sua misura normalizzata — «misura 5,19 mm, il foro di passaggio per M5» — e dice anche quando nessuna corrisponde.
- Un secondo foro come il primo si ottiene duplicando, invece di ridigitare le misure.
- Il tasto Canc rimuove la caratteristica selezionata e non più l'intero corpo.
- Un doppio clic su una riga dell'elenco degli oggetti apre ciò che la modifica: la finestra adatta per una caratteristica riconosciuta, il passo con le sue misure per una creata.
- Un foro passante che dopo lo spostamento non passa più lo segnala, e una svasatura che chiuderebbe il suo foro non si può spostare.
- Ridurre un foro finché non è più tale dà una spiegazione invece di chiedere una segnalazione di errore.
- Su una faccia, un pulsante porta al catalogo dei blocchi invece di mostrare righe che dicono solo ciò che lì non è possibile.
### Spostare, ruotare e selezionare

- La maniglia di spostamento si trova su ciò che è selezionato: su un foro alla sua apertura, non più al centro del pezzo.
- Si muove ciò che è selezionato: con un foro selezionato, maniglia e barra spostano il foro, non l'intero pezzo.
- Durante il trascinamento, un'anteprima trasparente mostra dove va il foro e un'immagine pallida da dove viene.
- L'ombra segue lo spostamento e mostra così l'altezza sopra il piano.
- Durante la rotazione, un arco mostra di quanto si è ruotato e che l'angolo scatta sui multipli di 45 gradi.
- Le piccole rotazioni arrivano: finora uno scatto angolare invisibile inghiottiva ogni movimento inferiore al suo passo.
- Su una faccia la barra di spostamento offre solo ciò che è possibile e indica il motivo sul pulsante, non in un messaggio dopo il clic.
- Il pulsante *Applica* non c'è più: si applica con Invio nel campo o trascinando la maniglia, ed esattamente una volta, non due.
- Un pezzo spostato non torna più per un istante nella posizione precedente al rilascio.
- Un clic destro nell'elenco degli oggetti colpisce la riga indicata, non le due sopra.
### Vista e albero degli oggetti

- La vista ha un comando proprio, ed è la nuova impostazione predefinita: trascinare con il sinistro sposta, con il destro ruota, la rotellina premuta inclina e ingrandisce.
- Con W, A, S e D si vola nella scena, Q ed E inclinano; il volo attraversa un pezzo, mentre lo zoom si ferma davanti.
- Chi è abituato a un altro comando lo sceglie nelle impostazioni: restano gli schemi per Cura, per Bambu Studio, Orca e PrusaSlicer, per un CAD e per Blender.
- La voce *Adatta alla vista* inquadra il pezzo selezionato; senza selezione, tutta la scena come prima.
- Un pezzo sotto il piano di stampa si vede: ora è il piano a essere trasparente, non il modello.
- I corpi semitrasparenti vengono disegnati nel giusto ordine di profondità, qualunque sia l'ordine di creazione.
- La vista impostata viene mantenuta, invece di tornare indietro al passo successivo.
- Selezione e cambi nella vista 3D avvengono con transizioni morbide invece di salti bruschi.
- Da quattro caratteristiche con lo stesso nome, l'albero degli oggetti mostra una riga espandibile con il loro numero invece di centinaia di righe.
- Viene mostrato solo ciò che una stampante può produrre: le caratteristiche sotto il mezzo millimetro scompaiono; su un supporto per tubo, 296 su 1130.
- I raccordi con raggio zero scompaiono così dall'albero degli oggetti.
- Un clic su un corpo non costa più attesa; su un assieme da 63 MB erano tre quarti di secondo.
- Cambiare la rappresentazione e ricostruire l'immagine di modelli grandi richiede un terzo del tempo precedente.
### Disegno e immissione precisa

- Lunghezza e larghezza di un disegno selezionato sono modificabili; il disegno segue il numero cambiato insieme alle sue quote.
- Una quota sbagliata si può annullare da sola, e non più solo insieme a tutte le altre.
- Dopo aver estruso uno schizzo, la finestra offre di nuovo anche la via per sottrarlo.
- Una quota digitata vale come è stata digitata: 0,1 non diventa più 0,166667.
- La finestra delle unità chiede millimetri e mostra un numero invece di «nan».
- Il campo dello smusso si chiama larghezza, e il relativo messaggio parla di larghezza e non di raggio.
- Un clic nella guida di un cursore lo porta nel punto selezionato, non una pagina più avanti.
- Nella misurazione, il punto di destinazione si aggancia agli spigoli del modello e non a linee assenti dall'immagine.
### Apertura, salvataggio e file di scambio

- Il primo modello di un progetto è centrato sul piano di stampa invece che dove lo mette il suo file; ogni altro mantiene la sua posizione.
- Un file danneggiato viene rifiutato all'apertura, invece di essere accettato e finire nel progetto al salvataggio.
- Il rifiuto indica il motivo — vuoto, troncato, non è un STL, non è un 3MF, senza triangoli, con coordinate inservibili — e offre *Scegli un altro file*.
- Il download interrotto di un file di modello viene riconosciuto come tale.
- I file oltre gli otto megabyte vengono letti con indicatore di caricamento e avanzamento, invece di lasciare la finestra bloccata per quattordici secondi.
- Un nome di file arriva sul disco come è stato digitato, con spazi, accenti, parentesi e segno più.
- Un modello si può salvare come 3MF senza i valori di stampa di Solidon, per arrivare invariato nello slicer.
- Dove STEP non è possibile per una mesh, il rifiuto offre subito *Salva come 3MF*.
- Un modello con mesh troppo fitta riceve *Ridurre i triangoli* come pulsante sul rilievo, non solo come consiglio nel testo.
- Un rilievo che riguarda più corpi si può risolvere per tutti in una volta, scegliendo quali, con un solo Ctrl+Z per l'intera azione.
- Il comando *Auto Split* avvisa quando un taglio lascia una superficie aperta, e un taglio in un corpo modificabile non svuota più la scena.
- Scalare un pezzo sotto il limite della macchina produce un rilievo; finora esisteva solo per troppo grande.
- I blocchi personali riportano la stessa avvertenza di quelli forniti.
### Stampa, slicer e filamento

- La finestra di stampa mostra i profili corrispondenti alla stampante impostata, invece di un magazzino di 1001 voci.
- Con una Elegoo Centauri Carbon sono quattro, e quello giusto è preselezionato.
- Cambiare stampante nel progetto porta con sé volume di stampa, ugello e codice iniziale: un progetto Prusa non riceve più la macchina della Elegoo.
- Lo slicer riceve i dati della macchina e restituisce un file di stampa, invece di interrompersi con «non compatibile con la stampante».
- Se lo slicer è impostato su una stampante diversa dal progetto, Solidon lo dice invece di accettarlo in silenzio.
- L'avviso di profilo mancante indica di quale stampante si tratta.
- L'elenco dei filamenti resta vuoto finché non si sceglie un profilo macchina e ne indica il motivo, invece di offrire 5962 bobine.
- La selezione del filamento si può filtrare per produttore, materiale e valori di un profilo.
- Dove Solidon aggiunge un bordo, indica quale pezzo ne ha bisogno e perché.
- Ciò che la macchina non può fare viene indicato su tutti i campi interessati, non su uno solo.
- Le raccomandazioni del rapporto che lo slicer non accetta non promettono più un effetto.
- Gli oggetti di materiali diversi finiscono su piani separati: la guarnizione in TPU non più sul piano della custodia in PETG.
- L'avviso di stampa dà un consiglio invece di rimandare ai numeri del contratto di licenza.
### Messaggi, pulsanti e informazioni

- I pulsanti bloccati indicano ora sul pulsante ciò che manca: col mouse, da tastiera e per un lettore di schermo.
- Tra questi *Affetta* e *Apri nello slicer* senza slicer configurato, *Inserisci* nel catalogo dei blocchi e *Crea* nella finestra del modello.
- I rifiuti non finiscono con la sola frase, ma con la via d'uscita.
- Un errore inatteso viene spiegato nella lingua impostata, invece di recitare un testo interno in inglese.
- La finestra Informazioni indica chi sta dietro a Solidon e chi risponde ai riscontri.
- Un collegamento a una versione precedente porta a quella attuale invece di una pagina di errore.
- L'installazione su Windows arriva in fondo anche sui computer dove prima si interrompeva con «file danneggiato»; in cambio il file di installazione è 23 megabyte più grande.
### Chat e assistenza dei modelli

- Se un riferimento a una caratteristica è ambiguo, la chat si ferma, evidenzia i candidati nell'immagine e chiede, indicando il corpo di ciascuno.
- Quando la chat dispone oggetti sui piani di stampa, il risultato è poi visibile nell'immagine.
- Un rilievo su un assieme indica il corpo interessato e porta la sua azione; dove non ce n'è, è una semplice indicazione.
- La chat conosce le nuove azioni sulle caratteristiche riconosciute e le esegue su richiesta.
## 0.3.0

### Primi passi e orientamento

- Quattro percorsi guidati spiegano le vie principali dal primo progetto fino al risultato stampabile.
- La schermata iniziale sfrutta interamente anche le finestre piccole o strette, senza schede tagliate o contenuti coperti.
- I progetti usati di recente precedono i tour introduttivi e sono quindi raggiungibili più rapidamente.
- La schermata iniziale non sposta più la selezione senza richiesta e si usa completamente con mouse e tastiera.
- Le voci *Nuovo*, *Apri* ed *Esempi* sono ordinate più chiaramente e descrivono la destinazione già prima dell’apertura.
- Feedback e sostegno volontario sono accessibili dalla schermata iniziale anche con tastiera e tecnologie assistive.
- La chat resta utilizzabile anche con una finestra poco alta: l’inserimento resta fisso in basso e il contenuto scorre.
- La barra degli strumenti superiore resta visibile con progetti aperti e finestre strette, senza uscire dall’area di lavoro.
- Un nuovo esempio di disegno porta direttamente al percorso degli schizzi e completa i progetti di esempio esistenti.
- La schermata iniziale ha un pulsante *Apri modello …*, e l'area di rilascio si può anche cliccare.
### Interfaccia e utilizzo

- I menu hanno titoli ben visibili e colonne di icone allineate in modo uniforme.
- La panoramica dei comandi allinea scorciatoie e spiegazioni, così le voci lunghe si scorrono più rapidamente.
- I dialoghi estesi usano colonne e larghezze di campo uniformi.
- La precedente pagina unica per adesione, retrazione e filamento è divisa in aree di impostazioni più piccole e ben denominate.
- Tutte le 56 impostazioni di stampa si possono cercare tramite le etichette tedesche visibili.
- La ricerca riconosce inoltre 146 termini comuni degli slicer, tra cui *perimeters* e *wall loops*.
- I campi numerici rispondono correttamente a frecce, incremento e arrotondamento, senza più cambiare i valori in modo inatteso.
- I cursori hanno un aspetto uniforme con una maniglia facile da afferrare.
- Il colore in risalto è riservato al pulsante principale; lo strumento attivo si riconosce dal bordo e gli elementi inattivi restano visivamente in secondo piano.
- I calcoli molto brevi evitano indicatori lampeggianti; quelli medi mostrano l’attesa, quelli lunghi anche avanzamento e annullamento.
- I suggerimenti restano su una riga quando c’è spazio e vanno a capo in modo controllato nelle finestre strette.
- Le anteprime nell’albero degli oggetti sono abbastanza grandi da permettere di riconoscere davvero le forme.
- L’elenco dei filamenti scorre separatamente; *Aggiungi filamento* e *Valori di stampa* restano raggiungibili anche con molte bobine.
- Avvisi ed errori sono leggibili senza comunicare il loro significato soltanto tramite il colore del testo.
- I campi di selezione disattivati si distinguono chiaramente da quelli attivi e selezionati.
- Un mouse 3D (SpaceMouse) muove il modello su tutti e sei gli assi appena è collegato; un tasto del dispositivo inquadra tutto.
- Il piano di stampa si nasconde con un clic o con Ctrl+Maiusc+D e resta così finché non serve di nuovo.
### Disegno e immissione precisa

- I cerchi si inseriscono tramite il diametro; un foro M3 può quindi essere creato direttamente con 3,2 mm.
- Un vincolo di diametro resta un’espressione modificabile dopo la risoluzione, il salvataggio e la riapertura.
- Le quote si modificano direttamente con un doppio clic, senza il precedente e lungo percorso di selezione.
- Posizione X, Y e Z, angolo e scala si possono inserire direttamente nella barra di movimento.
- Un’immissione esatta crea lo stesso passaggio annullabile di un movimento con il mouse.
- Durante una rotazione o scalatura esatta, più corpi selezionati usano un centro comune.
- Esc torna indietro di un solo livello nel disegno: linea corrente, strumento corrente e solo dopo l’intero schizzo.
- Ripeti funziona ora anche mentre uno schizzo è aperto.
- Uno schizzo vuoto mostra un suggerimento cliccabile che apre le forme di base pronte.
- Il pulsante delle forme base porta il nome dell’azione eseguita dal clic. Le altre forme si trovano dietro la freccia accanto.
- Lo strumento di taglio si apre nel corpo invece che in una vista vuota fuori dal modello.
- Le viste anteriore, laterale, superiore e opposte si allineano correttamente su tutti e sei gli assi.
- La maniglia di trascinamento resta visibile anche con una telecamera radente o inclinata e mostra una misura utile.
- Lo strumento di misura conclude una misurazione con un riscontro visibile, invece di dare l’impressione di perdere il risultato.
- Durante il sollevamento la quota sta accanto al reticolo, e dopo il rilascio tutti i valori restano modificabili nel dialogo.
- Le quote durante il disegno seguono la griglia, non il puntatore: si vede la misura che si ottiene davvero.
- Le misure dei cerchi si possono commutare tra diametro e raggio direttamente nel campo; la scelta vale in schizzo e dialoghi e viene ricordata.
- Un cerchio con centro fisso e diametro quotato è considerato completamente determinato; la riga di stato non segnala più una quota mancante.
### Vista, cronologia e modifica delle forme

- Più corpi selezionati possono essere spostati insieme.
- Più corpi selezionati ruotano attorno a un centro comune e mantengono le distanze reciproche.
- Dopo una rotazione, i corpi possono tornare correttamente sul piano di stampa nello stesso passaggio.
- I movimenti consecutivi dello stesso corpo sono riuniti in un passaggio comprensibile della cronologia.
- I passaggi collegati compaiono come una voce espandibile, invece di sovraccaricare la cronologia con righe singole.
- Un’azione continua dell’utente si può annullare completamente con un solo comando Annulla.
- Le voci della cronologia mostrano il proprio tipo e un numero di passaggio univoco.
- I modelli scaricati e importati possono essere tagliati immediatamente.
- Un clic su un riscontro porta in modo affidabile al punto, al corpo o al passaggio della cronologia interessato.
- Quando si raggiunge un riscontro, la telecamera inquadra l’obiettivo invece di finire in un primo piano grigio.
- Le facce denominate e le indicazioni si spostano insieme al loro corpo durante disposizione e posizionamento.
- Nella modellazione a pennello viene segnalato se i tratti mancano il modello o non producono modifiche stampabili.
- Un testo su una parete laterale sta orizzontale e diritto invece che a un angolo qualsiasi; sulla faccia superiore e inferiore decide ancora l’angolo impostato.
- Se una scritta finisce dentro il corpo invece che sopra, l’operazione lo dice e indica la strada: fare clic sulla faccia su cui deve stare il testo.
- I corpi svuotati mantengono lo spessore di parete richiesto anche su facce inclinate e curve.
- Un foro allargato di proposito conserva il suo nome e i suoi accoppiamenti invece di risultare perso nel rapporto.
- Le sfere con moltissimi segmenti restano una mesh maneggevole invece di venti milioni di triangoli.

### Blocchi personali e file di scambio

- I blocchi personali si possono salvare come file locale .solidon-part e aggiungere nuovamente al catalogo.
- I file di blocco si possono aprire, trascinare nell’app e importare tramite l’associazione del sistema operativo.
- Il nome e l’estensione rendono subito evidente che il file appartiene a Solidon.
- Importazione, condivisione e libreria locale usano testi completi dell’interfaccia in tutte e sei le lingue.
- Prima del salvataggio, un blocco personale può essere composto da più passaggi e valori modificabili.
- Durante la condivisione si può scegliere tra uso libero, attribuzione o attribuzione con condivisione alle stesse condizioni.
- Per un blocco denominato personalmente, il proprio nome prevale su quello incluso nel file.
- Provenienza e condizioni di condivisione restano rintracciabili durante lo scambio di un blocco.
- Ganci a scatto, occhielli per cerniere, ganci per pannelli forati e piedini hanno transizioni più robuste, senza superfici interne racchiuse.
- Le schede del catalogo mantengono la posizione e la faccia selezionata mentre caricano le anteprime.
- La scala delle tolleranze contrassegna ogni gradino con il proprio numero.
- I file GLB esportati stanno in piedi negli altri programmi invece che di lato.

### Divisione, stampa e filamento

- La divisione automatica privilegia interfacce solide ed evita il precedente possibile punto debole più sottile.
- Per ogni taglio viene scelto separatamente il tipo di collegamento adatto e salvato come forma concreta.
- Le indicazioni sui collegamenti incollati restano associate al taglio scelto.
- La divisione automatica reagisce in modo riproducibile alle indicazioni modificate e si può annullare durante il calcolo.
- La ricerca dell’orientamento prova solo posizioni realmente diverse e rispetta il tempo previsto anche con corpi complessi.
- I file 3MF di grandi dimensioni vengono riconosciuti ed elaborati più rapidamente senza modificare il risultato.
- Materiale, accoppiamento e tolleranze seguono la bobina realmente scelta o la posizione occupata nella stampante.
- L’intestazione mostra il materiale davvero utilizzato e non offre più una seconda selezione del materiale in conflitto.
- Il pulsante disattivato *Salva file di stampa* spiega che il file viene creato solo durante lo slicing.
- Le riparazioni già eseguite nello stesso flusso di lavoro non compaiono più in seguito come consigli ancora aperti.
- I fori per perni si aprono alla divisione con uno smusso d’invito, e il dente di una tasca a scatto sta sulla giunzione.
- Un diametro di perno scelto a mano deve entrare nella giunzione; se per questo si assottiglia, il rapporto lo dice.

### Rapporto, stabilità, piattaforme e lingue
- Su Linux in una sessione Wayland, Solidon si avvia e mostra la vista 3D; se al sistema manca una libreria, l’applicazione si avvia comunque e dice quale manca.

- I riscontri simili sono raggruppati senza perdere il riferimento ai corpi e ai punti interessati.
- Numeri e misure nel rapporto hanno etichette complete invece di singoli valori incomprensibili.
- Se una riparazione non riesce, il corpo originale invariato viene ripristinato completamente.
- Una mesh importata chiusa non viene più aperta dalla rimozione affrettata di un triangolo problematico.
- I pulsanti d’azione del rapporto non mantengono più in memoria, senza farsi notare, una finestra già chiusa.
- I blocchi inclusi e l’attivazione vengono caricati all’avvio senza bloccarsi a vicenda.
- La vista 3D viene chiusa correttamente prima della finestra, rendendo più affidabile la chiusura su Windows, Linux e macOS.
- Su Windows 11 la barra del titolo segue lo schema di colori dell’applicazione; le altre piattaforme restano invariate.
- I pulsanti standard come Apri, Salva e Annulla cambiano lingua immediatamente, senza riavvio.
- I nomi generati di corpi e blocchi cambiano correttamente lingua anche dopo aver già usato contenuti memorizzati nella cache.
- Traduzioni e valori del rapporto sono allo stesso livello in tedesco, inglese, spagnolo, francese, italiano e portoghese.
- Un pezzo senza rilievi offre nel rapporto direttamente il pulsante *Passa allo slicer …*.
- Ogni mappa di analisi spiega al passaggio del mouse cosa mostra, e la domanda sull'unità all'importazione chiama le unità per nome.
- Un pezzo che riempie il piano di stampa viene letto in millimetri senza chiedere.
- Le nervature sottili accanto a piastre spesse sono riconosciute come punto sottile, e i ponti sono misurati alla loro larghezza davvero libera.
- A un pezzo che poggia su sé stesso non vengono consigliati supporti dal piano.
- I consigli di stampa controllano tutte le velocità, calcolano il primo strato con le sue misure e segnalano un piano o una camera troppo freddi per il materiale.
- Le alette sovrapposte conservano ciascuna il proprio foro, e i graffi sottili non contano né come foro né come perno.
### Chat e assistenza dei modelli

- La chat accoglie con il proprio scopo concreto e non si apre più con uno spazio vuoto o termini tecnici relativi ai modelli.
- I contatori tecnici dei token sono stati rimossi dalla normale interfaccia per i clienti.
- Le segnalazioni identiche su dettagli di forma persi raggiungono l’assistente conteggiate invece che una per una.
- La finestra di generazione trasforma testo o immagine in un modello tramite ComfyUI locale e lo inserisce nella stessa scena modificabile.
- Il flusso TripoSG fornito crea un file GLB, poi riparato, ridimensionato e controllato automaticamente per la stampa.
- Ollama locale e ComfyUI locale elaborano uno dopo l’altro, così non occupano contemporaneamente la scheda grafica.
- Dopo una proposta dell’agente o una generazione 3D, Solidon libera i modelli locali e la memoria grafica.
- Durante l’annullamento Solidon rimuove solo il proprio incarico ComfyUI; gli altri incarichi in corso restano intatti.
- Prima del primo uso di un modello cloud, Solidon mostra chiaramente quali contenuti lasciano il computer.
- Il dialogo dei programmi aggiuntivi mostra solo ciò che manca ancora e descrive lo stato di ComfyUI con parole semplici.
## 0.2.2


### Disegno e modellazione

- In modalità schizzo può selezionare e trascinare punti, linee, cerchi e contorni direttamente nella vista. Un segno e una maniglia indicano anche cosa si muoverà.
- Il piano di disegno resta nello spazio passando tra vista dall'alto, frontale e laterale. Così vede la posizione reale invece della stessa immagine tre volte.
- Un rettangolo si completa digitando larghezza e altezza. Le misure restano come vincoli invece di perdersi dopo il disegno.
- Nella vista frontale o laterale trascini un contorno chiuso per dargli altezza. Quota e anteprima a filo crescono insieme; un valore digitato fissa l'altezza esatta.
- Trascini il contorno verso l'esterno per creare un corpo o verso l'interno per creare una tasca visibile. Freccia e croce rendono afferrabili entrambe le direzioni.
- L'anteprima mostra il parallelepipedo, cilindro o corpo dello schizzo mentre inserisce le misure. Prima i nuovi corpi restavano invisibili fino all'applicazione.
- Gli strumenti di disegno dicono cosa farà il clic successivo. I vincoli spiegano effetto e selezione, e i gradi di libertà sono descritti con parole chiare.
- Cubo, cilindro, foro e svuotamento compaiono una sola volta nel menu. La casella «Modifica facce e spigoli in seguito» sostituisce la seconda voce, prima chiamata «esatto».
- Questa casella mantiene disponibili smussi, raccordi, angoli di sformo, facce spostate e l’esportazione STEP. Il dialogo nomina il vantaggio, non il motore di calcolo.
- Durante il disegno, la barra nomina il passo successivo: Solleva, Scava o Fatto. Se manca un contorno chiuso o un corpo selezionato, lo dice anche.
- Un vincolo si toglie con un secondo clic sullo stesso pulsante, e un clic destro sul punto mostra che cosa vi è appeso. Prima ogni clic ne aggiungeva un altro, fino al blocco.
- La barra dei vincoli mostra solo ciò che si adatta alla selezione. Se non è selezionato nulla, lì c’è una frase invece di dieci termini tecnici in grigio.
- I corpi di base nascono «sul piano di stampa» invece che «a Z = 0», e lo strumento di disegno si chiama «curva», come ciò che disegna.

### Fori ed elementi

- Modifichi direttamente il diametro di un foro riconosciuto in un modello importato, senza ridisegnarlo né aprire un programma CAD.
- Il foro modificato conserva posizione e direzione e funziona su mesh e corpi esatti. Anche un foro inclinato resta sul proprio asse originale.
- I segni degli elementi seguono la geometria visibile dopo un nuovo calcolo. Un foro segnato resta aperto e non viene coperto dal proprio segno.
- Gli strumenti frequenti come Foro, Unione e Sottrazione sono un clic più vicini nel menu. I titoli mantengono comunque ben distinti i gruppi.

### Blocchi e componenti standard

- Il catalogo offre viti e dadi stampabili con filettature abbinate. Scelga testa, lunghezza, misura e gioco adatti alla stampa.
- I cuscinetti comuni hanno una sede costruita sulle misure standard. Il cuscinetto può restare estraibile con gioco o essere fissato a pressione.
- Un foro per vite può incassare una testa svasata o la rondella abbinata. La profondità della testa regola quanto entrano nel pezzo.
- Le tabelle comprendono più rondelle, inserti filettati e cuscinetti. Le misure tecniche sono spiegate nella scelta invece di apparire come codici oscuri.
- Tasche per magneti, clip e passacavi accettano anche misure personalizzate. I campi aggiuntivi compaiono solo se la variante scelta li usa davvero.
- I blocchi stanno nel catalogo con immagini di anteprima invece che come elenco nel menu. Un clic destro sul pezzo scelto porta lì.
- Il catalogo avvisa già prima di inserire quando manca il punto sul corpo. La maggior parte dei blocchi ha bisogno di una faccia o di un foro selezionato.

### Stampa e filamento

- Ogni bobina può avere temperature, raffreddamento, ritrazione e valori del materiale propri. Questi valori restano quando cambia il livello di qualità.
- I valori delle singole bobine arrivano al file 3MF e allo slicer nel posto materiale corretto. Un colore non prende più per errore i valori di stampa di un altro.
- Al primo avvio, Solidon importa i filamenti caricati nello slicer con nome, tipo, colore e profilo del produttore. Non deve ricreare le bobine.
- Gli esempi inclusi non sostituiscono più stampante e materiale scelti con le impostazioni usate per creare le loro anteprime.
- Nel Flatpak Linux, Solidon trova e avvia gli slicer del computer, incluse le AppImage. Entrambi i programmi raggiungono la cartella di lavoro condivisa.
- Dividendo si creano spine su una metà e i fori corrispondenti sull’altra. Il messaggio ne indica il numero o avvisa che la faccia di taglio è troppo piccola.
- Dopo la divisione, le metà si allontanano. Spine e fori non spariscono più fra due facce di taglio coincidenti.
- Unendo due corpi, entrambi conservano la loro descrizione del filamento con il nome. Prima la descrizione del secondo colore poteva andare persa.
- Esportando su più piatti, i cambi di colore vengono contati per piatto. Un piatto di un solo materiale non annuncia più cambi che in stampa non avvengono.

- Se lo slicer configurato fallisce, il messaggio offre il passaggio a un altro. Prima restava solo l'esportazione — anche con due slicer funzionanti lì accanto.
- Il file di stampa finito si apre direttamente nella finestra dello slicer, con i suoi profili. Quale consegna usate viene ricordato per progetto.
- Il file di stampa viene verificato contro l'altezza del modello. Un pezzo affondato sotto il piano si nota prima della stampa — non a metà altezza sulla stampante.
- ElegooSlicer accetta di nuovo gli incarichi. E se uno slicer dispone i pezzi da solo, il rapporto lo dice invece di sostituire in silenzio l'occupazione del piano pianificata.
- Il rapporto non accumula più misure vecchie: un nuovo passaggio le sostituisce, lo stesso fatto compare una sola volta, e gli avvisi nominano l'oggetto invece di un numero.
- I profili di slicer ricordati sanno a quale slicer appartengono. Dopo un cambio, nessun profilo estraneo passa nel nuovo programma.
- Un motivo di blocco sotto le impostazioni di stampa sparisce appena non vale più. Prima, «serve un profilo di stampante» restava accanto a un pulsante ormai libero.

### Chat e generazione 3D

- Le impostazioni separano chiaramente modelli cloud e locali. Prima di inserire una chiave cloud spiegano quali dati lasciano il computer.
- Il controllo di un generatore 3D lento non trattiene più la finestra. Mostra cosa viene controllato e come installare i programmi aggiuntivi.
- L'assegnazione degli elementi riconosciuti resta fluida sui modelli grandi. Centinaia di elementi vengono confrontati insieme invece che uno alla volta.
- Le richieste a Ollama e ComfyUI sullo stesso computer evitano il proxy aziendale. Un servizio locale attivo non viene più indicato per errore come irraggiungibile.
- Nel Flatpak Linux, installazione e avvio dei programmi ausiliari avvengono sul computer, non nella sandbox. ComfyUI viene trovato anche nelle posizioni comuni.
- Il pulsante Genera è cliccabile solo se il clic avvia davvero qualcosa. Se manca qualcosa, il dialogo dice cosa — con un pulsante che porta alla soluzione.
- Se la generazione fallisce, la riga di errore di ComfyUI stessa compare nel dialogo, insieme al passo in cui è avvenuta. È esattamente la riga che serve quando si chiede aiuto.
- Se un modello linguistico scrive la chiamata come testo invece di eseguirla, la proposta lo spiega — con la via verso «Verifica gli strumenti». Prima restava JSON grezzo nella conversazione.
- Il manuale ha una pagina nuova, «Quali modelli usa Solidon»: quali sono provati, da dove vengono e quanto impiegano. Per la via dal testo dice quale file va in quale cartella.
- Un corpo generato molto piccolo mostra il suo volume reale invece di «0 mm³» accanto a «chiuso».
- Per i modelli IA della generazione scegliete per compito quale calcola — come per il modello linguistico. «Automatico» resta l'impostazione predefinita e prende ciò che è adatto.

### Vista e comandi

- La barra dei parametri mantiene le misure compatte e visibili. Unità, limiti ed espressione si modificano lì con annullamento, senza nascondere il valore.
- I cursori di Solidon seguono la dimensione di sistema su Windows, macOS e Linux. Il loro punto di clic torna sulla punta disegnata invece che accanto.
- Passaggio del puntatore e selezione sono segnati in modo chiaramente diverso. I colori di analisi e differenza restano prioritari sull'evidenziazione del corpo.
- Menu, indicazioni e manuale usano parole coerenti per chi inizia. I termini specialistici vengono spiegati dove servono per la prima volta.
- La finestra Sostieni spiega prima di aprire PayPal che il pagamento è volontario e non sblocca funzioni. Se il browser non parte, il link può essere copiato.
- Svuota e gli altri strumenti dipendenti mostrano solo i campi usati dalla variante scelta e spiegano in modo uniforme i valori nascosti.
- Gli esempi inclusi si aprono con un tour guidato. A destra indica passo dopo passo cosa fare e riconosce da sé quando un passo è compiuto.
- Le azioni proposte per un errore restano al salvataggio. Riaprendo un progetto prima restava solo l’errore, senza la via d’uscita.
- La ricerca dell’orientamento esamina ogni posizione una sola volta. Le posizioni proposte più volte costavano tempo senza dare un risultato diverso.
- I passi della cronologia si possono cancellare e recuperare con Ctrl+Z. La domanda precedente nomina i passi che si basano su quello cancellato.
- Un doppio clic su un passo raggruppato della cronologia dice dove stanno i singoli passi. Prima non faceva nulla, benché le visite guidate insegnino proprio questo gesto.
- Se un file viene rifiutato durante la lettura, l’indicatore di caricamento sparisce. Prima restava lì come se si calcolasse ancora un file che non era stato accettato.
- Solidon si avvia più in fretta e l’analisi degli strati calcola più spedita. Le grandi librerie di calcolo vengono caricate solo quando c’è davvero da calcolare.

- I messaggi di errore mostrano i dati a cui le loro frasi rimandano. «L'inizio della risposta sta accanto» — ora c'è davvero, insieme a indirizzo e fornitore.
- I consigli «Ridurre i triangoli» e «Aprire la pagina nel browser» ora sono pulsanti che fanno esattamente questo, invece di frasi che lo descrivono.
- Quando un servizio non risponde, il dialogo nomina l'indirizzo da verificare nel browser e raccoglie il tentativo sotto «Dettagli». Gli avvisi rimandano solo a pulsanti esistenti.
- Le liste a discesa delle barre sotto la vista restano aperte finché non scegliete. Prima una lista poteva richiudersi subito, perché scivolava via da sotto il puntatore.
- Il campo di spessore della barra di taglio aspetta la fine della digitazione. Prima tagliava a ogni tasto — prima con 3 mm e poi con 30.
- Dopo l'apertura, il rapporto preseleziona il primo avviso che offre un'azione. «Posare sul piano» sta lì come pulsante da subito, senza dover prima cliccare la riga.
- L'avviso sulle parti staccate molto piccole ora offre il pulsante «Rimuovi le parti piccole». Prima diceva solo che nulla era stato eliminato e lasciava a voi la ricerca della via.
- Le riparazioni già eseguite all'importazione appaiono come nota nel rapporto, non più come avvertenza. Altrimenti il rapporto si apriva in giallo un modello su due, senza nulla da fare.
- L'avviso sulla gestione pacchetti annullata chiama il pulsante col suo nome completo — in tutte e sei le lingue. «Dettagli» da solo era una piccola ricerca in cinque di esse.

### Piattaforme e correzioni

- Per Linux è disponibile un'AppImage oltre al Flatpak. Solidon può quindi avviarsi come singolo file eseguibile senza installare Flatpak.
- Un aggiornamento di Windows avviato da Solidon mostra solo l’avanzamento e poi riapre Solidon. Avviando il programma d’installazione a mano, resta la scelta finale di apertura.
- Il Flatpak Linux può essere aggiornato da Solidon.
- I messaggi al supporto possono essere inviati anche dal pacchetto Linux. Prima mancava l'accesso di rete necessario.
- Su macOS le fessure sottili nella mesh STL di una filettatura vengono ricucite all'esportazione senza accettare una mesh peggiorata.
- La ricerca degli aggiornamenti accetta un changelog multilingue ampio. Le note non finiscono più a metà parola e gli elenchi lunghi non bloccano il controllo.
- La finestra Informazioni del pacchetto mostra di nuovo le note di tutte le librerie incluse.
- I rapporti di errore mostrano versioni reali, sessione e metodo di input. Un trattino non indica più per errore che manca una libreria necessaria.
- Singoli metadati estranei non fanno più fallire la riparazione di una mesh importata.
- Uno svuotamento riuscito indica anche per i corpi esatti lo spessore della parete e il volume rimosso, invece di restare in silenzio dopo il calcolo.

## 0.2.1


### Colori e filamento

- Colori facce e pezzi con due gesti invece che con un pennello: un clic colora una faccia, un clic l'intero pezzo. Se un passo precedente cambia le misure, il colore le segue.
- Un clic sulla faccia superiore colora la faccia superiore: il confine viene dal riconoscimento, senza raggio e senza mirare.
- Il filamento si sceglie per nome e colore — «PETG rosso» invece di un numero. Anche la chat lo capisce.
- Venti bobine sullo scaffale sono venti filamenti nella scelta. Quattro bobine dello stesso materiale in quattro colori sono quattro voci, non una.
- Il colore di un filamento e le sue temperature ora stanno insieme. Prima l'impostazione del rosso poteva finire sul filamento bianco.
- Lo stesso colore riceve lo stesso ugello, anche sul secondo piatto.
- Nella vista compare il colore vero del filamento. Un filamento senza colore proprio è grigio, e la selezione resta riconoscibile.
- Colorare sta ora dove si cerca il colore; prima era sotto «Preparare».
- Il campo «Colore del pezzo» mostrava nel tema chiaro un colore diverso da quello della vista accanto.
- Chi scriveva «PETG» otteneva «Questo profilo di materiale non è noto». Ora il campo è un elenco con i nomi che esistono davvero.
- La preselezione «— nessuno —» veniva rifiutata alla conferma. Ora c'è un valore che la finestra accetta.
- Il selettore di colore mostrava rosso, e dopo la deselezione il pezzo era grigio.

### Blocchi

- Una cerniera a perno che esce dalla stampante già mobile. Niente da montare, niente da inserire: la stampante lascia aperto il gioco.
- Un blocco può riunire più pezzi. Così puoi salvare un modello mobile o assemblato come un'unica voce riutilizzabile del catalogo.
- Mettere il perno nel foro non funzionava, benché entrambi gli elementi ci fossero. Ora sì.

### Stampa e slicer

- Nello slicing scegli quali piatti partono. Chi voleva affettare il piatto 2 riceveva tre file e le bobine del piatto 1.
- Solidon scrive ora anche il profilo di macchina e di processo per lo slicer, invece di rimandare al suo fondo. Sette impostazioni stavano nel file, centotrentasei sono arrivate allo slicer.
- Il codice di avvio viene dal profilo di stampante del produttore invece di essere scritto a mano.
- Ciò che non depone più un cordolo lo dice l'ugello: le pareti troppo sottili stanno nel rapporto come rilievo, non come proposta.
- Il limite inferiore dello spessore di parete viene dal profilo di materiale. Lì stavano due numeri fissi, ed erano sbagliati entrambi: sulla Centauri sono 0,84 mm.
- Il pulsante per affettare invitava al clic benché tre frasi dopo non seguisse nulla.
- Un file G-code con estensione .nc si apriva, ma nella finestra di apertura non si trovava.

### Cosa Solidon vede nel modello

- Nei file importati Solidon riconosce ora fori e tasche anche quando la mesh non è saldata. Prima lì non trovava nulla.
- Il rapporto segnala «più pezzi» solo quando ce ne sono. Una piastra di un pezzo solo contava come 796.
- Lo stesso file non viene più esaminato quindici volte. Questo risparmia i secondi che prima passavano all'apertura.
- Quando la semplificazione non arriva dove richiesto, Solidon lo dice. Finora restavano 992 triangoli dove ne erano voluti 400, senza una parola.
- Lo stesso avviso compare una volta nel rapporto, non di nuovo dopo ogni passo.
- Due corpi nello stesso punto sembravano uno, e nessuno lo diceva.
- Dopo l'unione un elemento puntava a un foro diverso da prima.

### Chat e agente

- Mentre l'agente lavora, la chat mostra quale passo è in corso e con quale strumento. Prima taceva fino a un minuto.
- L'elenco dei modelli locali dice per ciascuno con quanta affidabilità chiama gli strumenti e quanto tempo impiega. Un modello che si limita a scriverne ora si riconosce.
- Se cade il collegamento con il modello linguistico locale, Solidon lo dice — e propone una via invece di annunciare un errore di programma.
- Lo stesso vale se cade il collegamento con il servizio di immagini.
- La chat nomina anche le piccole variazioni di volume. Un foro eseguito si annunciava come «+0,00 cm³» e la proposta sembrava senza effetto.

### Vista e uso

- L'albero degli oggetti nomina perni e filetti, con diametro e passo.
- Un passo che crea due corpi compare nell'albero con due righe; prima ce n'era una.
- Se selezioni più corpi di quanti ne prenda un'operazione, ora vedi quali vengono usati.
- La stampa mostrava lo stesso tempo in due punti in modo diverso: «10 h 5 min» in basso, «605 min» nella finestra.
- Numeri e unità si leggono ovunque uguali: una riga e il suo stesso suggerimento nominavano lo stesso volume in modo diverso, e in pollici per niente.
- Una misura accetta un'espressione in ogni campo numerico; il manuale mostra ora anche il pulsante.
- La griglia dell'editor di schizzi mostrava il passo del momento in cui vi si entrava.
- Due campi di testo si annunciavano come facoltativi e non lo erano mai stati.

### Corretto

- Duplicare dava all'originale un nuovo identificativo, e il corpo spariva dalla vista.
- Un corpo esatto di cui un foro non lasciava nulla restava nell'albero come oggetto vuoto e si poteva salvare.
- La vista delle differenze e le mappe di analisi tacevano sui corpi esatti.
- Un tipo di campo sconosciuto trasformava in silenzio ogni campo in uno di testo.
- Una finestra si lasciava confermare, metteva un passo nella cronologia — e nell'immagine non cambiava nulla.
- Ruotare di zero gradi passava in silenzio invece di dire che non succede nulla.
- La finestra delle novità mostrava settantacinque punti come un muro. Ora sono raggruppati, e l'annuncio arriva nella tua lingua.

## 0.2.0


### Blocchi
- Blocchi propri senza una riga di codice: scegli dei passi nella cronologia e mettili nel catalogo come blocco — con campi propri, anteprima e un intervallo di valori a tua scelta.
- Un blocco costruito da te viaggia dentro il file di progetto. Chi lo apre può inserire il tuo pezzo senza dover installare nulla.
- Cinque nuovi blocchi nel catalogo: gancio per pannello forato, squadretta, piedino, clip per cavi e occhiello di cerniera.
- Il gancio per pannello ora tiene anche se qualcuno solleva il pezzo togliendo qualcosa — una linguetta elastica scatta dietro il pannello. Disattivabile se togli spesso il pezzo.
- Supporto a parete, nervatura, linguetta e scanalatura, dente di scatto, aggancio a scatto e cerniera a film sono ora nel menu di una faccia cliccata. Mancava proprio il supporto a parete.
- Chi inserisce un blocco dal catalogo senza scegliere un punto viene ora interpellato. Finora si posizionava nell'origine, per metà dentro il pezzo e per metà sotto il piatto.
- Il catalogo dei blocchi si può consultare anche senza un modello. L'inserimento è allora disattivato e ne dice il motivo, invece di annullare solo dopo la conferma.
- L'alloggiamento del dado e lo spazio per la testa della vite non toglievano nulla: entrambi costruivano sopra la faccia invece che sotto.
- L'alloggiamento per il magnete tiene di nuovo il magnete: il labbro di ritegno veniva finora aggiunto all'alloggiamento invece di essere scavato al suo interno, e vi spariva dentro.
- L'asola a buco di serratura ora pende in verticale, così la vite si blocca scendendo. Sdraiata di traverso migrava lateralmente e la testa trovava troppo poco spazio.
- L'alloggiamento per il dado ora combacia con il dado: per M5, M6 e M8 la tabella riportava un'altezza troppo bassa, per l'M5 di sei decimi.

### Disegno
- Mentre disegni, la griglia mostra a cosa si aggancia, il passo si può digitare, le quote stanno accanto al puntatore e la barra dice su quale faccia stai disegnando.
- Le scorciatoie da tastiera funzionano di nuovo in modalità disegno — linea, cerchio, arco, taglia, offset, Ctrl+Z — e il clic destro apre il menu del disegno invece di quello del modello.
- Adatta alla vista riporta il disegno nell'inquadratura, e un clic a cinque millimetri da un punto non vi si aggancia più.
- Una linea di costruzione resta tale anche dopo essere tagliata, prolungata, spostata o specchiata. Finora una linea mediana diventava uno spigolo del profilo e divideva il pezzo.
- La finestra di un passo mostra le quote del tuo disegno invece dei valori predefiniti, e un cerchio compare con il suo diametro intero, non con la metà.
- Una tasca da un disegno con foro conserva il foro. Finora fresava via anche l'isola.
- Un foro disegnato viene sottratto in qualunque verso tu lo abbia disegnato. A seconda dell'ordine dei clic prima usciva un pezzo più pieno.
- Taglia ora interviene solo entro il proprio tratto, e Prolunga trova come bersaglio anche cerchi e archi — finora vedeva solo linee.
- Una transizione tra due disegni conserva i loro fori, e una tasca su una parete laterale taglia nella parete invece che dall'alto.
- Un contorno che si autointerseca viene ora segnalato sul disegno, invece di produrre un corpo non stagno che viene comunque esportato.
- Un disegno con foro nel foro conserva tutti i livelli, e Proietta prende il piano su cui stai disegnando — finora il terzo livello andava perso e il taglio arrivava dal basso.
- Scalando a una larghezza data veniva misurata anche una linea di costruzione. Da cinquanta millimetri ne uscivano cinque.

### Cronologia e passi
- Nella cronologia si possono selezionare più passi insieme.
- I limiti di una quota si possono cambiare in seguito — finora valeva per sempre quello che era stato inserito alla creazione.
- Modificare un passo in seguito ora si può annullare. Finora Ctrl+Z rimuoveva l'azione sbagliata e lasciava in piedi il valore modificato.
- Un passo che punta a una faccia di un altro corpo ricalcola dopo ogni modifica. Finora un pezzo allineato restava al vecchio posto, anche dopo la chiusura.
- Le caratteristiche mantengono il loro nome quando un pezzo viene ruotato o spostato per la stampa. I passi e gli accoppiamenti che le indicano non finiscono più nel vuoto.
- Se scompare la faccia fino a cui si estrude, l'errore ora indica quel campo e suggerisce di sceglierne un'altra — invece del piano dello schizzo.

### Strumenti e geometria
- La svasatura funzionava in un solo verso per asse. Cliccata dal lato sbagliato non toglieva nulla e non diceva nulla.
- Su pezzi a gradini, foro e tappo lavoravano nel vuoto: la direzione veniva dal parallelepipedo di ingombro invece che dal materiale in quel punto.
- Un tappo passante riempiva solo metà del foro — e lasciava tutt'intorno la luce di cui il foro era stato allargato per il materiale.
- Il riempimento a reticolo metteva le barre accanto al pezzo invece che nella sua cavità.
- Lo sfiato di un pezzo svuotato termina ora nella cavità invece che attraverso il coperchio, e la scanalatura filettata del coperchio girevole non apre più un foro nella propria sommità.
- Unione, sottrazione e colorazione avvisano ora quando non è successo nulla. Finora un passo restava nella cronologia sopra un modello invariato.
- Se un pezzo si spezza perché un blocco non tocca più il suo supporto, il rapporto ora lo segnala come errore e consiglia un rimedio. Finora il numero di pezzi era solo un'indicazione.
- Una filettatura in un foro cliccato tagliava solo la metà inferiore. Lo stesso valeva per la boccola a caldo.
- Una filettatura interna viene ora sottratta, come dice la sua etichetta. Finora al suo posto cresceva un bullone dentro il foro di nucleo.

### Stampa e slicer
- La stima di materiale per i supporti era sbagliata di molto: calcolava la superficie sotto lo sbalzo invece della colonna sottostante.
- La larghezza del ponte misura ora il tratto realmente sospeso senza appoggio. Una canalina per cavi segnalava prima la larghezza del suo parallelepipedo di ingombro e riceveva il consiglio sbagliato.
- Un pezzo più sottile di uno strato di stampa non viene più messo in piedi.
- La divisione automatica conta la sporgenza della spina nel limite del piatto e non lascia accoppiamenti che puntano a posti scomparsi.
- Anche un assieme risponde ora ad «Appoggia sul piano»: scende nel suo insieme, i pezzi mantengono la loro posizione reciproca. Finora non succedeva nulla, senza un avviso.
- La quantità di filamento letta da un file G-code è di nuovo corretta. Un comando alla fine del file faceva calcolare diversamente tutto ciò che precedeva e raddoppiava il totale.
- Un cambio di stampante o materiale conserva ciò che hai impostato. Finora l'intero insieme veniva azzerato senza dire nulla.
- La scelta del filamento per posto materiale arriva allo slicer. Finora veniva salvato il testo mostrato invece del profilo.

### Vista e comandi
- Una faccia selezionata conta: foro, blocco e schizzo vanno dove hai puntato. Prima ogni operazione su una faccia costava due clic.
- Un clic su un foro propone ora la vite che ci passa davvero — e indica il diametro misurato.
- Dopo «Sposta faccia» le facce del pezzo si possono di nuovo cliccare. Finora non restava nulla su cui disegnare, forare o impostare un accoppiamento.
- Aprendo un progetto compare subito un indicatore di caricamento. Finora il centro della finestra restava nero per alcuni secondi o mostrava la schermata iniziale — sembrava un arresto anomalo.
- Un clic nella vista colpisce solo ciò che si vede — nessun pezzo nascosto, nessuno di un altro piatto. Dopo la modalità Sposta, gli spigoli non trapassano più tutte le facce.
- Le viste d'asse da Ctrl+0 a Ctrl+6 inquadrano di nuovo il modello, invece di includere anche il piatto e il volume di stampa.
- Chi ha spostato molto un pezzo e poi lo ruota, ruota di nuovo attorno al pezzo e non attorno a un punto accanto.
- Una quota nella vista usa ora l'unità impostata, un cambio di tema ricolora anche il piatto e il volume di stampa, e con più piatti l'etichetta e la maniglia stanno sul pezzo invece che accanto.
- Ciò che porta con sé un blocco inserito compare nell'albero degli oggetti sotto il suo nome, e il nodo offre di modificare proprio quel passo.
- L'ombra sotto il pezzo mostra ora ogni frammento a sé e si fa più discreta. Se un corpo si spezza, ora lo si vede dall'ombra.

### File ed esportazione
- Due file importati con lo stesso nome non vanno più persi. Il secondo prima sovrascriveva il primo, e il progetto non si poteva più aprire dopo.
- Un indirizzo senza estensione di file ora dice che lì c'è una pagina web e dove si trova il pulsante di download, invece di «Formato non riconosciuto».
- All'esportazione, pezzi con lo stesso nome si sovrascrivevano: un file, due messaggi di riuscita, un pezzo perso.
- L'estensione del progetto viene ora aggiunta da «Salva con nome». Un progetto salvato come supporto.stl era, all'apertura, un modello estraneo illeggibile.
- Un progetto modificato non va più perso quando trascini un file sulla schermata iniziale — prima viene chiesto.

### Velocità e stabilità
- L'applicazione non sparisce più senza dire nulla quando una quota cambia, un disegno viene letto o si calcola una sezione. Gli stessi calcoli ora vanno fino a sessanta volte più veloci.
- Svuotare e inserire spine si possono davvero annullare. Su un pezzo scansionato il pulsante restava fermo per minuti.
- I file grandi da uno slicer si aprono senza che la finestra si blocchi. Prima il solo conteggio dei corpi leggeva l'intero file in memoria.
- Se un calcolo in sottofondo si blocca, l'applicazione ora lo segnala. Altrimenti la legenda, l'analisi degli strati e la ricerca di una nuova versione restavano ferme per sempre.
- Annulla ora scarta anche la prossima esecuzione già in coda, e la barra di avanzamento non scompare più sopra un file ancora in scrittura.

### Lingue
- La lingua scelta nel programma di installazione si applica subito, altrimenti quella di sistema. E una lingua scelta nella finestra ha effetto immediato, invece che solo al prossimo avvio.
- Un cambio di lingua ha effetto in tutta la finestra. Le impostazioni di stampa restavano nella lingua di avvio.
- Gli esempi inclusi ora indicano le loro quote nella tua lingua. Prima c'era scritto «Breite, Tiefe, Höhe» in tedesco, anche con l'interfaccia in inglese.
- La riga di comando ora parla la lingua impostata. Finora dava aiuto e messaggi di errore in tedesco, qualunque fosse la scelta.

### Chat e supporto
- Una proposta della chat che ritira dei passi dice prima quali se ne vanno con essa. E Annulla annulla davvero, invece di continuare a calcolare in sottofondo.
- La chat torna a gestire otto passi per domanda invece di quattro, e la riga del costo non sovrastima più.
- Ciò che parte con un riscontro al supporto viene mostrato prima, parola per parola — incluso il registro. E se non arriva, il messaggio indica il motivo reale.

### OpenSCAD
- Le forme libere non richiedono più un secondo programma: quello che faceva OpenSCAD lo fanno gli strumenti di disegno e i blocchi — un'installazione in meno di cui occuparsi.
- Un progetto con codice OpenSCAD si apre ancora e tutto il resto viene calcolato come prima. Il Rapporto nomina il passo e «Mostra i valori» ne copia il codice.

## 0.1.5

- Ora si disegna nella vista stessa: la superficie di disegno si posa sul modello invece di sostituirlo, e un clic nella vista colloca un punto sul piano dello schizzo.
- La griglia della superficie di disegno mostra di nuovo ciò a cui si aggancia. Per un periodo è rimasta a un decimo di millimetro e stava metà dietro la barra.
- Un clic al centro di un foro seleziona il foro. Prima colpiva la faccia accanto o nulla, e nella vista dall’alto annullava addirittura la selezione.
- Un clic dentro un intaglio rettangolare seleziona il pezzo invece di annullare la selezione.
- La chat trova ora il tuo modello locale comunque tu scriva l’indirizzo. Finora serviva l’indirizzo completo che termina con /api/chat.
- Una chiave di accesso rifiutata dal fornitore non blocca più il tuo modello locale. La chat passa da sola al modello disponibile successivo invece di inviare di nuovo la stessa chiave.
- I messaggi di errore della chat dicono a quale modello si riferiscono. Sopra un errore di chiave c’era solo che il modello linguistico non aveva risposto.
- Il campo per l’indirizzo di un servizio propone un esempio e avverte che lì non va una cartella. Se ne inserisci una, torna con il motivo sopra.
- La finestra di configurazione non si chiude più con un errore quando un campo indirizzo contiene il percorso di una cartella o il campo chiave un testo incollato per sbaglio.
- I menù a discesa mostrano di nuovo tutte le voci. Appena un campo aveva il fuoco della tastiera, al menù aperto mancava mezza voce.
- Ctrl+Z e Ctrl+Y compaiono ora sulla loro voce di menù, come le altre quattordici scorciatoie. Hanno sempre funzionato; semplicemente nulla le nominava.
- I messaggi di errore durante il disegno dicono quale limite è stato superato. Sopra «tra tre e sessantaquattro vertici» c’era solo «L’immissione non era utilizzabile così».
- Le azioni unificate stanno nello stesso menù e compaiono una volta sola nella ricerca comandi, come svuotare e svuotare con precisione.
- Una voce di menù «Filettatura» dice ora dove va la filettatura — in un foro o su un bullone.
- L’interfaccia spagnola nomina le caratteristiche allo stesso modo ovunque. Nella stessa lista c’erano prima due parole per la stessa cosa.
- L’applicazione libera la memoria quando una finestra si chiude e termina in modo più pulito.
- L’immagine che accompagna una segnalazione mostra ora anche il modello. Prima al centro c’era una superficie nera, proprio dove sta il pezzo di cui si tratta.


## 0.1.4

- Durante la demo Solidon chiede una volta: dopo mezz’ora di lavoro una scheda si posa sulla vista e chiede come sta andando. Non ferma nulla, e senza il suo clic non esce nulla.
- Chi fa clic su una faccia e inserisce un elemento lo ottiene perpendicolare a quella faccia invece che verso l'alto. Su una parete laterale un foro per vite stava prima di traverso.
- Un elemento posato su un foro ne assume la misura. Su un foro da 5,19 mm la boccola a pressione proponeva prima M3, che lì non asporta nulla.
- Un clic con la mano un po' incerta seleziona di nuovo invece di spostare il pezzo di un decimo di millimetro.
- Un pezzo selezionato si sposta direttamente con il mouse: afferrare e trascinare, senza prima richiamare «Sposta». La maniglia resta per il preciso: per assi e a passi di griglia.
- Da sotto si guarda ora attraverso il piano di stampa. Chi lavora la faccia inferiore di un pezzo gira la vista sotto e vede il pezzo invece del piano.
- Un foro si può selezionare anche facendo clic nel mezzo, non solo sulla sua parete.
- La ricerca dei comandi capisce ora anche le parole di tutti i giorni: «copiare», «eliminare», «aprire» e «colorare» prima non portavano da nessuna parte, benché tutte e quattro esistano.
- La ricerca trova anche per chi non conosce il termine tecnico. Digitando «rinforzare», «incastrare» o «avvitare» si arriva alla nervatura, al gancio e al foro per vite.
- Due voci di menu si chiamavano entrambe «rimagliare». Ora sono «Affina gli spigoli» e «Uniforma i triangoli»: la prima divide gli spigoli lunghi, la seconda ne pareggia le dimensioni.
- Il programma parla la lingua che lei sente altrove: «corpo esatto» invece di «B-Rep», piano invece di superficie di stampa, piatto per la disposizione.
- All’avvio Solidon controlla se esiste una versione più recente e la propone. Viene scaricata e installata solo dopo la tua conferma; si può disattivare nelle impostazioni.
- Un modello linguistico locale può ora calcolare dieci minuti. Prima la chat si arrendeva dopo due e chiedeva una segnalazione, per un calcolo che semplicemente durava di più.
- Un anello viene riconosciuto come una sola caratteristica e non più come tre cordoli sovrapposti.
- La voce «Ispessisci superficie» fa ora ciò che promette. Prima spostava la superficie.
- Il titolo della finestra nomina il modello aperto, anche quando non esiste ancora un file di progetto.
- Mentre si disegna, la misura sta sulla punta della linea invece che sul bordo della finestra.
- Una voce di menu bloccata dice ora perché lo è. Il motivo c’era già ed era invisibile.
- La segnalazione porta con sé lo stato della scena: oggetti con misure, caratteristiche, parametri e cronologia. Così un errore si riproduce invece di indovinarlo.
- Sono stati corretti diversi arresti anomali alla chiusura di finestre e finestre di dialogo.

## 0.1.3

- Il nucleo esatto ora sa forare: «Eseguire un foro esatto» lavora direttamente sul corpo esatto, senza passare da una mesh.
- Raccordi e smussi vengono riconosciuti in modo più affidabile. Prima un raccordo veniva talvolta segnalato come un perno, con un diametro che non esisteva.
- Gli esempi inclusi non salutano più con avvisi che non lo sono.
- La schermata iniziale sta negli schermi piccoli, senza scorrere.
- Una caratteristica selezionata si colora da sé. Prima l’intero corpo assumeva il colore di selezione e non si vedeva che cosa fosse inteso.
- L’albero degli oggetti indica la misura di ogni caratteristica riconosciuta.
- Le mesh esportate non contengono più triangoli vuoti.
- Salvare due volte dà due volte lo stesso file.
- Le cinque traduzioni sono state riviste. I termini tecnici si chiamano ora come li chiamano gli slicer.
- La barra degli strumenti è in ordine: il campo più largo era quello che serve meno spesso.
- Un secondo errore del programma non mette più una seconda finestra sopra la prima.

## 0.1.2

- I numeri decimali digitati vengono letti bene ovunque. «12,5» resta dodici e mezzo; prima poteva diventare 125, senza chiedere e senza avvisare.
- Ciascuno dei cinquantasei campi delle impostazioni di stampa dice ora che cosa fa quando lo si muove.
- Tempo di stampa e materiale sono stimati con più precisione, soprattutto per i pezzi svuotati.
- La consegna allo slicer cade sul piatto. Con CuraEngine i pezzi finivano di fianco.
- Dividendo con le spine, i fori corrispondenti finiscono nella metà giusta.
- Millimetri e pollici valgono ora dovunque compaia un numero, anche nelle barre degli strumenti e nella pittura.
- L'avanzamento resta finché il calcolo è davvero finito, e la finestra rimane utilizzabile nel frattempo.
- Tutte le scorciatoie da tastiera sono ora in un unico prospetto: nel menu Aiuto, sotto «Scorciatoie da tastiera», oppure premendo il tasto punto interrogativo.
