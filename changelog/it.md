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

- I riscontri simili sono raggruppati senza perdere il riferimento ai corpi e ai punti interessati.
- Numeri e misure nel rapporto hanno etichette complete invece di singoli valori incomprensibili.
- Se una riparazione non riesce, il corpo originale invariato viene ripristinato completamente.
- Una mesh importata chiusa non viene più aperta dalla rimozione affrettata di un triangolo problematico.
- I pulsanti d’azione del rapporto non mantengono più in memoria, senza farsi notare, una finestra già chiusa.
- I blocchi inclusi e l’attivazione vengono caricati all’avvio senza bloccarsi a vicenda.
- La vista 3D viene chiusa correttamente prima della finestra, rendendo più affidabile la chiusura su Windows, Linux e macOS.
- Su Windows 11 la barra del titolo segue lo schema di colori dell’applicazione; le altre piattaforme restano invariate.
- Su Linux in una sessione Wayland, Solidon si avvia e mostra la vista 3D; se al sistema manca una libreria, l’applicazione si avvia comunque e dice quale manca.
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
