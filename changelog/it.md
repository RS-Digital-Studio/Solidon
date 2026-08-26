# Novità

Questo file è ciò che compare nella finestra di aggiornamento, e nient'altro.
**Non** è un elenco delle modifiche: di 97 commit fra 0.1.1 e 0.1.2 restano
otto righe, e sceglierle è il lavoro. Un punto va qui se qualcuno se ne accorge
usando il programma.

Quindi: niente messaggi di commit, niente nomi di moduli, niente numeri di
paragrafo. «La barra spariva mentre l'applicazione calcolava ancora per quattro
secondi» è un buon commit e una cattiva voce; «L'avanzamento resta finché il
calcolo è davvero finito» dice la stessa cosa a chi sta davanti allo schermo.

Un file per lingua in questa cartella, come per i cataloghi, e tutti portano
gli stessi punti nello stesso ordine (`tests/test_changelog.py`).
`tools/make_download.py` ne prende la sezione della versione corrente e la
scrive in `website/version.json`.

## 0.2.0


### Blocchi
- Blocchi propri senza una riga di codice: scegli dei passi nella cronologia e mettili nel catalogo come blocco — con campi propri, anteprima e intervallo di valori verificato.
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
