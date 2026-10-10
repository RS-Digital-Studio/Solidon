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

## 0.6.0

### Uso e sistema

- Su Mac, Solidon richiede ora macOS 14 o successivo. Ogni Mac dal 2018 in poi può installarlo gratuitamente.
- Solidon ora si avvia sui Mac Intel con macOS 26. La versione 0.5.3 vi si bloccava all'avvio.
- Su Mac, *Annulla* interrompe subito una risposta in corso del modello locale.
- Su Mac, Invio apre la voce selezionata nella schermata iniziale, in *Cerca funzione* e nel rapporto di verifica.
- Su Linux, la scrittura con Fcitx5 e IBus arriva ora nel campo di testo anche nel Flatpak e nell'AppImage.
- La disinstallazione su Windows non lascia nel registro voci dell'associazione dei file.
- Canc funziona anche quando la linguetta *Selezione* ha il focus, e rimuove più corpi contrassegnati in un solo passaggio. Se il tasto non fa nulla, la barra di stato ne dice il motivo.
- Il clic destro sui corpi offre *Rimuovi oggetto* e, con più corpi, *Unisci*. *Svuota* c'è anche su una faccia selezionata, che diventa l'apertura.
- I pannelli a sinistra e a destra si spostano con la maniglia, si agganciano a un bordo o restano sospesi. *Vista → Pannelli al loro posto* li rimette a posto.
- I pannelli si possono disporre anche in basso a sinistra, in basso a destra e lungo il bordo inferiore.
- Le linguette si riordinano e si trascinano in finestre proprie, anche su un secondo schermo. Chiudi la finestra o usa *Torna in Solidon* per riportare il contenuto.
- Solidon ricorda la disposizione. Le finestre restano raggiungibili anche quando uno schermo viene scollegato.
- Durante il ricalcolo, il rapporto di verifica dice *Ricalcolo in corso …* e mostra le righe di prima come stato precedente. Finora i vecchi errori sembravano ancora validi.
- Se il calcolo rapido fallisce in un passaggio, Solidon lo ricalcola a fondo nella stessa esecuzione invece di fermarsi.
- Un rilievo che dice che un passaggio non ha avuto effetto apre quel passaggio sul campo giusto.
- Dopo la rimozione di un corpo, il rapporto non ne parla più, e la cronologia mostra quali passaggi non lasciano più nulla.
- Un foro selezionato non ricade più in silenzio sul suo corpo dopo il ricalcolo. Finora Canc poteva poi rimuovere l'intero corpo.
- Ogni funzione ha lo stesso nome ovunque. Lo strumento *Dividi* offre *Dividi lungo un piano*, *Dividi lungo una linea tracciata* e *Dividi in pezzi distinti*.
- Sul corpo selezionato, *Dividi automaticamente …* si trova ora sotto *Prepara*.
- Nella finestra a riposo solo *Blocchi* risalta a colori. Il rosso resta ai pulsanti che scartano o eliminano, e le domande si aprono con il focus su *Annulla*.
- In modalità disegno la linguetta *Selezione* è nascosta. L'elenco dei vincoli mostra quelli dei punti e delle linee selezionati, più ogni conflitto.
- Nella scheda dei parametri, una misura mostra «Non utilizzato» solo quando è così. Il pulsante dice quanti numeri fissi si possono collegare alle misure.
- La segnalazione di errore allega un registro di arresto anomalo solo dopo un vero arresto anomalo di Solidon.
- La scheda del tour è alta quanto i suoi passi. Un passo si apre con un clic o con la barra spaziatrice, e nessun fumetto copre più la vista.
- Quando un passo del tour indica il rapporto di verifica, il tour resta visibile. La linguetta è incorniciata e il passo dice quale aprire.
- Un clic sulla i accanto a un'azione nella linguetta *Selezione* apre il manuale nel punto in cui è spiegata.
- Ogni quota di un blocco si può legare con fx a una quota del progetto, anche se non contiene ancora un'espressione.
- Dopo aver trascinato la maniglia di un'anteprima, nessun numero resta sopra la vista. Un numero digitato durante il trascinamento sposta l'anteprima, non il corpo scelto.
- Dopo *Ripara e riprova* e percorsi simili, la cronologia non chiama più «eliminato» un passaggio che continua a calcolare. Se la catena si ferma di nuovo, il passaggio è segnato.
- Il pulsante *Filamenti* sta ora nell'intestazione. Elenca i filamenti del progetto e porta al magazzino filamenti.
- Un altro filamento si vede subito, anche su blocchi e corpi STEP, e Solidon non ricalcola nulla per questo. I corpi selezionati mostrano il colore del filamento sotto l'evidenziazione.
- Nella linguetta *Selezione*, il campo del filamento assegna solo con un clic o Invio. Le frecce e la digitazione scorrono soltanto l'elenco, e la rotellina scorre la linguetta.
- Nelle versioni tradotte, *Nuovo filamento* non scorre più di lato quando la finestra è più bassa del suo contenuto.
- I modelli grandi si caricano molto più velocemente e richiedono meno memoria, anche con una cronologia lunga e su computer con 8 GB.
- Anche in una cronologia lunga, un nuovo passaggio richiede appena più tempo del primo.
- Annulla e ripristina sono più veloci, e la memoria non più necessaria si libera subito.
- Risolvere le sovrapposizioni ed esportare in 3MF è molto più veloce.
- L'area di lavoro viene visualizzata più rapidamente quando si aprono file 3MF di grandi dimensioni.
- Un modello aggiunto è poi visibile, anche se finisce accanto a un modello su cui la vista era ingrandita.
- Nel catalogo dei blocchi, *Gestisci blocchi* è aperto finché non esiste ancora un blocco proprio.

### Stampare e passare allo slicer

- Su Linux, Solidon crea ora il file di stampa anche con Cura come Flatpak o AppImage.
- Su Linux, le stampanti di OrcaSlicer, Bambu Studio, ElegooSlicer e Creality Print come AppImage sono subito disponibili, anche se lo slicer non è mai stato aperto.
- La finestra di stampa offre le stampanti dello slicer scelto, come *Primi passi* e *Impostazioni*. Una stampante ripresa così resta legata al suo slicer.
- Nella finestra di stampa lo slicer si cambia come in *Primi passi*, anche con *Scegli programma …* per uno che Solidon non trova da solo.
- Una stampante dell'elenco di Solidon e la stessa dello slicer contano come un solo apparecchio. La finestra sceglie il profilo con l'ugello giusto e il file porta il codice di avvio.
- Senza un profilo dello slicer memorizzato, esportazione e finestra principale usano quanto la finestra di stampa propone per la stampante, con macchina e processo del produttore.
- Vengono offerti solo gli slicer con cui Solidon lavora, più gli slicer per resina come ChituBox e Lychee. Ora vale anche Bambu Studio come AppImage.
- Il codice di avvio e il volume di stampa vengono solo dalla tua stampante, non da un altro modello della stessa serie.
- La finestra di stampa assegna i profili dello slicer molto più in fretta, all'apertura e dopo ogni cambio di slicer.
- Il tempo di stampa stimato è più vicino a quello dello slicer, molto più vicino per i pezzi con supporti.
- Il controllo che supporti e skirt stiano sul piano ora misura solo sotto gli sbalzi. I pezzi vicini al bordo non ricevono più un avviso senza motivo.
- I suggerimenti accettati non lasciano quasi più senza supporto gli sbalzi che ne hanno bisogno. *Tenere liberi i canali* blocca solo lo spazio da cui un supporto non si potrebbe più togliere.
- Dove i supporti sotto piccoli sbalzi poggiano sul modello, Solidon suggerisce supporti ad albero. Lì lasciano meno segni.
- Sulle punte piccole Solidon suggerisce una *Velocità minima di rallentamento* più bassa, così non si ammorbidiscono. L'impostazione arriva a ogni slicer.
- I bordi stretti che si reggono da soli restano liberi con *Bordi senza supporto*. La stampa richiede così molto meno supporto.
- Gli archi a tutto sesto e a sesto acuto si reggono da soli, anche in un muro spesso, e Solidon non chiede più supporti lì. I soffitti piani o poco inclinati mantengono i loro.
- I supporti si staccano più facilmente: lo spazio segue materiale e altezza dello strato di ogni pezzo, anche con più materiali su un piatto. L'interfaccia segue la superficie sopra.
- Se un supporto poggia sul pezzo, Solidon suggerisce anche uno strato di interfaccia sotto, così il suo piede non lascia segni. Con i supporti ad albero solo negli slicer che lo stampano lì.
- Con i supporti ad albero e accanto a una torre di spurgo, Solidon propone lo spazio del supporto in strati interi, come lo stampa lo slicer.
- Per il PLA, Solidon propone più spazio tra le numerose punte sottili e i supporti ad albero sottostanti. In questo modo restano meno residui delle punte dei supporti.
- Per il PETG Solidon suggerisce il raffreddamento pieno sul supporto. Così si stacca più facilmente dal pezzo.
- Nuovo nelle impostazioni di stampa: *Strati di interfaccia inferiori*, *Spazio nell'interfaccia* e *Raffreddamento pieno sul supporto*.
- Il campo *Spazio verso l'alto* ora si chiama *Spazio sopra e sotto* e vale per entrambi i lati del supporto.
- Se lo slicer rifiuta filamenti con temperature troppo diverse su un piatto, Solidon ora indica il motivo e la via d'uscita, invece di dire solo che non è stato creato alcun file.
- Nella finestra di stampa, stampante, filamenti e qualità restano del tutto visibili anche con il testo ingrandito. Le etichette lunghe vanno a capo.
- Il rapporto di verifica calcola più velocemente e richiede meno memoria.
- Su Linux con Flatpak, Solidon ora segnala un arresto anomalo dello slicer come tale, invece di dire solo che non è stato creato alcun file.

### Filettature, fori e componenti normalizzati

- Le filettature accettano ora qualsiasi diametro fino a 1000 mm, con *Filettatura stampabile*, in un foro, con *Crea vite* o *Crea coperchio a vite*.
- Anche i fori normali possono essere creati e richiusi con diametri fino a 1000 mm. I fori grandi e le svasature mantengono la forma rotonda.
- Viti, dadi e rondelle ci sono secondo ISO da M1,6 a M64. Per altre misure, *Misura personalizzata* ricava le dimensioni dalle misure vicine e lo dice.
- Con *Adatto al foro*, *Perno per foro* costruisce la controparte: una testa svasata a filo per una svasatura, una filettatura esterna di pari misura e passo per una interna.
- Su una filettatura interna stampata, la selezione offre direttamente *Perno per foro*.
- Se in un foro c'è un pezzo separato come un perno, le azioni sul foro lo dicono e offrono *Dividi in pezzi distinti*. Finora il perno veniva fuso in silenzio con la piastra.
- Nuovo il *Perno filettato*: una barra filettata o un prigioniero senza testa, smussato a entrambe le estremità, con la stessa filettatura stampabile di vite e dado.
- Anche nei fori dei blocchi come il foro per vite, l'inserto a caldo o la sede per dado, *Perno per foro* crea il perno adatto, e avvisa se il foro non è nel corpo.
- Posizionata a mano su una faccia, la sede per dado scava la sua tasca nel materiale. Finora la tasca restava sopra e veniva forato solo il foro per la vite.
- Il foro per la vite della sede per dado attraversa esattamente il pezzo, anche se spesso. Finora finiva 10 mm sotto la tasca o forava il lato opposto oltre una fessura.
- Inserita da sotto, la sede per dado ha la tasca sotto la faccia e la fessura scende fino a essa. Finora la tasca stava per metà sopra, con la vite nella faccia.
- Se il foro di un blocco non attraversa il pezzo, ora si chiama cieco. Finora si chiamava passante.
- Se la parete è più spessa di quanto indicato per «Passacavo» o «Portagomma», il passaggio lo dice e apre lo spessore di parete. Finora il foro finiva in silenzio nel materiale.
- Se in una svasatura, un'asola, una coppa, una gola o una filettatura c'è un pezzo separato, le azioni lo dicono. Finora veniva tagliato o fuso.

### Blocchi

- I blocchi che sono un pezzo a sé, come clip per cavo, nervature o dadi, nascono senza selezione come corpo a sé in un punto libero del piatto, anche in un progetto vuoto.
- Anche i tuoi blocchi nascono così come corpo a sé e non si attaccano a un corpo già presente nel progetto.
- Con *Salva la selezione come blocco* il corpo selezionato arriva con esattamente i passi che lo costruiscono. Se arrivasse anche un secondo corpo, la finestra lo dice prima.
- Supporti a parete, fascette per tubo, morsetti per profilo e supporti accettano ogni vite da M3 a M64. Se una misura non si accorda con le altre, il blocco dice cosa cambiare.

### Modificare e disegnare

- Con *Sposta caratteristica* il materiale della caratteristica si sposta così com'è e il punto di prima viene riempito in modo pulito. Dove non si può, la selezione lo dice subito.
- Su cordoni e gole, la selezione offre solo ciò che l'operazione sa davvero fare.
- Se accanto a una parete c'è un raccordo, *Applica l'angolo di sformo* dice prima del calcolo che è d'intralcio e indica *Rimuovi caratteristica* come via d'uscita.
- Quando tagli via una parte di un corpo, spariscono anche smussi, filettature e sedi per dadi dei blocchi che vi si trovavano.
- In *Crea coperchio* e *Crea coperchio a vite*, un campo vuoto per l'altezza dell'apertura significa «Bordo superiore», e 0 è l'altezza del piano. I progetti più vecchi mantengono la loro apertura.
- Un vincolo d'angolo in uno schizzo piccolo non ribalta più le linee.
- Un corpo si tira su con tre clic: *Disegna* nella barra in alto (Ctrl+Maiusc+E), poi angolo, angolo opposto, altezza. Verso l'esterno si unisce, verso l'interno ritaglia.
- Mentre si tira su, le misure si possono digitare. Un doppio clic sul passaggio apre le sue misure, e alla voce *Tipo* diventa un solido di rivoluzione o un campo di fori.
- Dall'editor di schizzi, *Fatto* riporta nella vista e il clic successivo mette l'altezza. Esc mette da parte il contorno, Ctrl+Z lo riporta.
- Se un nuovo passaggio non si può calcolare, la bozza resta nella vista e *Ripara e riprova* lo calcola senza un altro clic.
- Per modellare ci sono quattro strumenti, ognuno con il suo pulsante e la sua scorciatoia. L'intensità è un livello da 1 a 10, e ripassare lo stesso punto non accumula più materiale.
- Il pennello si adatta alle dimensioni del corpo. Se la mesh è troppo grossolana, *Modella* uniforma i triangoli al primo tratto, e un Ctrl+Z annulla entrambe le cose.
- Nello specchiare il piano sta dove il corpo corrisponde a sé stesso, anche quando una parte sporge molto di lato.
- Modellare segue il mouse in modo fluido, e anche un passaggio con centinaia di tratti di pennello si calcola in fretta.
- In *Scheletro* ogni clic dopo il primo crea un osso, Invio chiude la catena, trascinare un'articolazione la piega e *Fatto* salva tutto senza dialogo.
- Uno scheletro piega solo ciò che è legato alle sue ossa, il resto del corpo resta fermo. I progetti precedenti si calcolano come salvati.
- Con Ctrl o Maiusc selezioni più spigoli e li raccordi o smussi in un solo passaggio. Un clic su un angolo seleziona tutti gli spigoli che vi si incontrano.
- Su un corpo esatto l'evidenziazione di uno spigolo mostra anche gli spigoli tangenti adiacenti che *Raccorda* e *Applica uno smusso* includono.
- Ciò che la selezione offre su una caratteristica, l'operazione lo esegue con esattamente quei valori. Ciò che è in grigio lo dice con la stessa frase, anche via chat e riga di comando.
- Come posto della copia, *Duplica caratteristica* propone una larghezza e mezza accanto all'originale, con una parete in mezzo e mai lungo il suo asse.
- Su una svasatura, *Ruota caratteristica* propone l'angolo più grande con cui resta tale, e avvisa quando una rotazione rimette la caratteristica solo su sé stessa.
- Se un'azione colpisse un pezzo separato accanto alla caratteristica, o una caratteristica posizionata toccasse altro materiale solo lungo una linea, Solidon lo dice invece di danneggiare il corpo.

### Generare con l'IA

- La finestra di generazione calcola in locale con TRELLIS.2 e FLUX.2 [klein] invece di TripoSG e SDXL. Da un testo nasce prima un'immagine, e dall'immagine il modello.
- Prima del download, la configurazione indica licenze e dimensioni dei modelli. Rimuove la vecchia configurazione TripoSG di Solidon e dice prima quali cartelle sono e quanto occupano.
- Le pareti sottili, per esempio di un vaso, arrivano chiuse e con uno spessore.
- L'assistente risponde nella lingua in cui scrivi.
- Con un modello locale l'assistente ha tanto spazio quanto con uno ospitato e porta a termine compiti fino a dodici passaggi.
- I modelli generati arrivano chiusi più spesso. Dove le facce si toccano soltanto, Solidon le separa e leviga le piccole pieghe della superficie invece di segnalare un'autointersezione.
- Se un tentativo si è già sfaldato durante la generazione, la finestra lo dice prima di accettarlo e offre *Un altro tentativo*.
- Se un modello generato è solo una pelle sottile attorno a una cavità, lo dice la finestra prima di accettarlo e il rapporto di verifica dopo, con la via a un nuovo tentativo.
- Prima del download, *Configura la chat* e *Configura ComfyUI* dicono quanta memoria grafica e quanto spazio servono a un modello e se questo computer li ha.
- Su un Mac, *Configura la chat* propone un modello locale che sta nella memoria condivisa e dice quando conviene una chiave per un modello ospitato.

## 0.5.3

### Uso e sistema

- A destra c'è una scheda con le linguette *Selezione*, *Rapporto di verifica* e *Chat*. I nuovi avvisi non portano più il rapporto in primo piano; la sua linguetta li mostra con un simbolo e un numero.
- In alto nella finestra trovi ogni funzione con *Cerca funzione* (Ctrl+Maiusc+P). La mappa delle funzioni segue l'ordine della barra dei menu.
- Nella selezione, su una caratteristica è aperta una sola azione alla volta. Le altre restano chiuse e mostrano i loro valori.
- Le finestre delle operazioni mostrano davanti al massimo quattro campi e una frase. I valori cambiati di rado stanno in *Altre impostazioni*, i limiti in *Quando evitarla?*.
- Uno zero con un significato dice nel campo cosa fa, per esempio «automatico», «senza» o «dal materiale».
- Tutte le finestre di dialogo hanno la stessa forma, con sezioni piatte e un bordo comune per le etichette, anche impostazioni, finestra dell'IA e sblocco.
- Il rapporto di verifica mostra prima i rilievi, con sopra una riga di stato e contatori. *Esporta …* sta accanto a *Passa allo slicer …*.
- Rilievi, passi del tour e suggerimenti sono più brevi. Dove un pulsante offre l'azione, la frase non la ripete più.
- L'azione *Ricostruisci modello* si trova sul corpo selezionato.
- La schermata iniziale mostra in grande, in alto, i quattro modi per cominciare. *Primi passi* chiede lingua, slicer e stampante e chiude il resto.
- Il catalogo dei blocchi mostra immagine e titolo in ogni riquadro. Su un foro, *Blocchi adatti …* mostra solo ciò che va in un foro.
- La finestra *Salva la selezione come blocco* mostra una riga per misura, con valore predefinito e limiti.
- Su Windows il puntatore del mouse di Solidon torna a cliccare esattamente sulla punta. Prima il clic cadeva qualche pixel più in là.
- La ricerca nel manuale non si interrompe più con un errore quando un carattere in più non trova risultati.
- Se annulli o elimini un passo mentre *Modifica questo passaggio* è aperto, la finestra si chiude e te lo dice.
- Un raro blocco dell'applicazione durante la verifica di stampa è stato risolto.
- Sul Mac le frasi che nominano una scorciatoia usano i tasti del Mac, cioè ⌘, ⇧ e ⌥.
- Sul Mac il tasto di cancellazione elimina corpi, caratteristiche, passi della cronologia e linee di un disegno.
- Su Linux anche la scorciatoia per ripetere indicata da tour e suggerimenti ripristina un passo.

### Stampare e passare allo slicer

- Novità: Anycubic Slicer Next con tutte le 39 stampanti Anycubic, su Windows, macOS e Linux.
- Su Linux Solidon trova OrcaSlicer, Bambu Studio e PrusaSlicer installati come Flatpak, con le tue stampanti e i tuoi profili, anche dal Flatpak di Solidon.
- Su Linux anche gli slicer in AppImage offrono le stampanti dei produttori che vi hai configurato.
- Su Mac Solidon ora crea il file di stampa anche con Cura. Prima trovava solo la finestra di Cura.
- Creality Print 7 porta con sé le sue stampanti e l'ultima che hai scelto.
- Gli elenchi delle stampanti nominano ogni stampante una sola volta, senza varianti di ugello. L'ugello lo scegli nelle impostazioni di stampa.
- Un ugello scelto nelle impostazioni di stampa resta anche se poi salvi le impostazioni del programma.
- Se cambi ugello per PrusaSlicer o SuperSlicer, lo slicer riceve anche il profilo di stampante adatto.
- Solidon offre più stampanti, anche quelle il cui profilo non indica piano o ugello, come la Creality CR-20 e la Anycubic i3 Mega in PrusaSlicer.
- Le impostazioni di stampa mostrano davanti slicer, stampante, ugello, filamenti, qualità, densità di riempimento e supporti; il resto sta in *Altre impostazioni*.
- Ogni motivo di un suggerimento nelle impostazioni di stampa sta in una riga. *Salva file di stampa* compare appena c'è un file di stampa.
- I pezzi più larghi in alto che alla base non ricevono più un avviso sul bordo se brim e skirt restano sul piano.
- I supporti accettati arrivano anche sotto i ponti con strati sottili. Finora *Tenere liberi i canali* poteva toglierli lì del tutto.
- Se i supporti sono attivi e nello slicer non ne arriva nessuno, Solidon lo dice dopo lo slicing e indica la via d'uscita.
- OrcaSlicer ed ElegooSlicer creano il file di stampa anche quando un profilo del produttore contiene valori che loro stessi rifiutano. Solidon nomina ogni valore sostituito.
- Se un profilo indica una punta del supporto ad albero più stretta della linea di supporto, Solidon la allarga perché lo slicer calcoli con i supporti.
- Se uno slicer applica un'impostazione in modo diverso, l'avviso nomina il campo e i due valori e porta alle impostazioni di stampa.
- Su Linux Solidon offre anche PrusaSlicer e OrcaSlicer del gestore di pacchetti insieme alle loro stampanti del produttore.
- Su un Mac il cui file system distingue maiuscole e minuscole, Solidon trova le stampanti del produttore nel pacchetto dello slicer.

### Fori, asole e divisione

- Una filettatura o un inserto a caldo in un foro selezionato non si ferma più con «fuori dalla superficie». Se il foro è troppo largo, Solidon indica le misure adatte.
- Su un foro selezionato la vista mostra solo diametro, profondità e due quote dai bordi. I riferimenti prendono il nome dal loro lato, per esempio «Bordo esterno a sinistra».
- In pollici, la frase sopra un foro ne indica la misura in pollici.
- La fascia dell'anteprima dice in una riga cosa cambia, con le lunghezze nella tua unità di visualizzazione.

### Modellare, testo e schizzo

- Per supporti e piastre con fori, svasature e scritte, *Ricostruisci modello* ora crea un contorno con le sedi sottratte. Se non trova una struttura, lo dice.
- Se in uno schizzo riprendi la sezione di un corpo convertito, i suoi cerchi e archi arrivano come cerchi e archi.
- Se un pezzo non si può convertire in facce e spigoli, Solidon indica il motivo e una via d'uscita invece di finire con un errore imprevisto.

### Generare con l'IA

- L'avviso sull'IA dice in due frasi, per ogni destinazione, cosa viene inviato. Dato che il testo è cambiato, lo confermi ancora una volta.
- Le descrizioni dei modelli locali consigliati sono più brevi.

## 0.5.2

### Nuove forme e nuovi blocchi

- Nuova è la forma di base «Crea un tubo»: diametro esterno e altezza, più spessore di parete o diametro interno, in un solo passo.
- Nuovo è il blocco «Aletta con foro»: un'aletta piatta su qualsiasi faccia, con foro e misure adatti alla vite da M3 a M8.
- Nuova è la «Fascetta per tubo» per i tubi comuni da 15 a 40 mm o qualsiasi misura tua fino a 110 mm, con vite di serraggio da M3 a M6 e il gioco del tuo materiale.
- Nuovo assistente «Contenitore con coperchio»: tondo o rettangolare, coperchio a vite, a incastro o a cerniera e, se vuoi, scomparti, inserto e fori spargitori. Le misure principali sono parametri.
- Quattro supporti nascono in un passo con facce e spigoli veri: a U, rotondo, a forcella e a mensola, fissati con buco di serratura, fori per viti, gancio per pannello o morsetto.
- Nuovi sono «Chiusura a baionetta» e «Disco girevole a scatti», ciascuno come coppia abbinata, e «Manicotto a innesto e raccordo per aste» da due a quattro aste.
- Nuovi anche «Portagomma», il cui passaggio attraversa la parete, «Giunto di canale» per le canaline, e «Pavimento della stanza», «Parete della stanza» e «Vetro della finestra» per stanze a incastro.
- Una scena vuota mostra come iniziare: parallelepipedo, cilindro, disegno, blocchi o un file che trascini dentro.
- I nuovi corpi nascono sul piano invece che su un corpo selezionato, e restano selezionati. Su una faccia scelta si appoggiano nel punto cliccato o al centro e, se vuoi, si uniscono subito al pezzo.
- Blocchi come una tasca per magnete o un foro per vite stanno dove fai clic sulla faccia. La loro distanza da due spigoli resta quando il pezzo cambia in seguito.
- La «Linguetta per profilato di alluminio» va su Motedis 20 × 20 tipo B cava 6 e 30 × 30 tipo B cava 8, con la testa sagomata sulla cava. Le tre misure precedenti restano come misure vecchie.
- Nel rapporto, «Ricostruisci modello» ricrea un pezzo importato, anche squadre, gole e svasature, lo confronta con l'originale entro il limite scelto e lo applica in un solo passaggio.
- Il «Morsetto con inserti» parte con il materiale del progetto in entrambi i campi del materiale. Finora erano vuoti.
- La ricerca dei blocchi trova la «Linguetta per profilato di alluminio» anche come dado a T, e la sua descrizione dice in cosa si distingue da un dado a T filettato.
- Un coperchio da «Crea coperchio» può avere una cerniera, stampata in posizione o con un perno da «Perno per foro», e il suo collare è accorciato per aprirsi liberamente.
- Con «Ricava controforma», un inserto riceve sedi per utensili che ne escono di nuovo dritti.

### Stampare e passare allo slicer

- La preparazione dell’esportazione 3MF può essere annullata. Con più piatti, Solidon riutilizza gli strati e i suggerimenti già calcolati.
- I filamenti inutilizzati dei vecchi progetti non vengono più inviati allo slicer. I profili restano associati ai filamenti in uso.
- I modelli aggiunti trovano spazio anche oltre il dodicesimo piatto. I piatti importati mantengono la loro disposizione.
- I modelli aggiunti con filamenti diversi vengono collocati su piatti separati se la stampante non ha abbastanza ugelli.
- Quando cambi stampante o slicer, il piatto di stampa scelto in precedenza non viene più trasferito al nuovo profilo.
- Le parti slanciate vengono disposte più vicine al centro. La distanza del brim è regolabile; per le basi piccole viene suggerito un brim a contatto con la parte.
- I profili danneggiati di PrusaSlicer e SuperSlicer vengono segnalati. Solidon utilizza quindi tutte le proprie impostazioni di stampa.
- Le impostazioni delle singole parti arrivano allo slicer in modo più affidabile. Quelle valide per tutto il piatto sono spiegate sulla parte interessata.
- Se accetti un brim solo per un pezzo snello, gli altri pezzi mantengono la tua scelta di adesione, e il campo indica i pezzi a cui vale il brim.
- Con Orca e Prusa, un suggerimento di velocità accettato per un accoppiamento rallenta solo le parti interessate.
- Anche le piccole modifiche accettate nelle impostazioni di stampa vengono mantenute nell’esportazione.
- Cura usa i limiti di jerk del profilo, con valori distinti per pareti, riempimento e primo strato.
- Se in Cura è attiva un’altra stampante, il trasferimento indica entrambe e mostra dove adottare la scelta di Cura.
- Risolto un arresto anomalo di ElegooSlicer e OrcaSlicer durante lo slicing di modelli multicolore con supporti a griglia.
- Dopo lo slicing, Solidon confronta anche il materiale dei supporti e gli strati del modello per piatto. Il rapporto mostra la stima interna e i valori del file di stampa.
- Il confronto del materiale considera solo il modello stampato. Lo spurgo è mostrato separatamente, segnalando se la quantità non può essere letta completamente.
- Il confronto del tempo di stampa conta dal primo strato con le velocità della tua stampante, anche con i supporti, e non segnala più una forte differenza quasi a ogni stampa.
- L'analisi degli strati è diverse volte più rapida sui modelli cavi e su quelli con molti soffitti, e mantiene i contorni fini. La vista degli strati riusa ciò che il rapporto ha già calcolato.
- Nelle parti sovrapposte, l'analisi di stampa non conta più l'aria racchiusa come materiale. Migliora anche il rilevamento degli sbalzi e dei supporti necessari.
- Al primo avvio e nelle impostazioni scegli prima lo slicer e poi una delle sue stampanti. L'elenco ha un campo di ricerca, volume e ugello arrivano dal profilo dello slicer.
- Se al primo avvio fai clic su «Salva e avvia» mentre Solidon cerca ancora le stampanti dello slicer, l'applicazione non si blocca più.
- Scegli l'ugello nelle impostazioni di stampa tra le misure che la tua stampante conosce, e lo slicer riceve il profilo corrispondente.
- Le impostazioni di stampa chiedono nell'ordine in cui una cosa dipende dall'altra: slicer, stampante, ugello, piatto, filamenti e qualità, poi i valori.
- Ora puoi generare i file di stampa direttamente da Solidon con Creality Print 7.2 e 7.3.
- Con Cura, Solidon riprende su richiesta la stampante che Cura sta usando, con il suo ugello. Una stampante rinominata in Cura viene riconosciuta.
- Cura esegue ora lo slicing con l'ugello che hai scelto, anche per le stampanti del suo elenco, e le stampanti con l'origine al centro del piano la mantengono.
- Le stampanti con l'origine fuori dall'angolo del piano, come delta, BIBO o Dremel, ricevono i pezzi dove Solidon li mette. Prima finivano sul bordo o lo slicer li ridisponeva.
- Bambu Studio riceve la variante dell'ugello e le temperature delle tue bobine, fino al file 3MF.
- Se scegli brim, skirt, raft o «Automatico» nelle impostazioni di stampa, compaiono solo le misure che riceve il tuo slicer, senza campi che non avrebbero effetto.
- Un numero fuori dal suo limite resta nel campo, il limite compare accanto e «Esegui slicing» aspetta che sia giusto. Finora veniva tagliato senza avviso.
- I pezzi alti e sottili su una base piccola ricevono pareti più tranquille, a 60 mm/s e con meno accelerazione. Sulla Centauri Carbon 2 queste aste si staccavano.
- Con Cura il rapporto di verifica nomina i pezzi che ricevono questi valori solo di riflesso, perché Cura li accetta solo per l'intero piatto.
- Solidon propone «Prima la parete esterna» solo per il pezzo che ne ha bisogno, e mai per uno con supporti.
- La ricerca rapida di «Orienta per la stampa» controlla anche che un pezzo stia in piedi in modo sicuro. Se uno non sta in piedi da nessuna parte, orienta comunque gli altri e lo indica nel rapporto.
- Con «Disponi sul piano» ogni pezzo va sul primo piatto dove c'è posto. Il set di minigolf ora ne occupa quattro invece di sei.
- Se trascini un corpo nella vista su un altro piano, finisce sul piatto di quel piano.
- Quando arriva un altro modello, da un file, da un download o generato, la vista mostra il piatto su cui si trova.
- Un altro modello va nel posto libero più vicino al centro del piatto, invece che nell'angolo posteriore sinistro.
- Dopo il primo «Apri nello slicer …», Solidon non ricalcola più la cronologia.
- La controverifica con SuperSlicer non segnala più un codice di avvio saltato dove non ne è stato saltato nessuno.
- SuperSlicer non si blocca più con i pezzi rotondi: non riceve più la cucitura a sciarpa che non conosce.
- SuperSlicer riceve supporti a griglia con un avviso se erano stati scelti supporti ad albero. La cucitura più vicina viene applicata senza falsi avvisi.
- TPU trova il profilo filamento e i valori di avvio in PrusaSlicer e SuperSlicer. Se manca un profilo, Solidon indica che usa la propria tabella dei materiali.
- Cura rispetta i limiti di accelerazione e segnala i valori scelti ridotti. Il riempimento pieno usa la velocità di riempimento; solo la faccia superiore usa quella di superficie.
- Cura prende la velocità minima della ventola e la soglia del tempo di strato dal profilo della tua stampante. Finora la ventola partiva già al primo strato, dove doveva restare ferma.
- La temperatura della camera arriva nel campo corretto dello slicer. I profili senza riscaldamento regolabile della camera spiegano perché il valore non ha effetto.
- Il riempimento Linee arriva in Bambu Studio e Creality Print come linee, senza essere sostituito da Griglia o Cubico.
- Dopo il taglio, Solidon segnala le impostazioni scartate da PrusaSlicer o dagli slicer Orca, oltre alle modifiche a bordo, ordine delle pareti e tipo di supporto.
- La preselezione del filamento prende Generic o la marca della tua stampante invece di un filamento speciale di terzi, ad esempio Generic PETG invece di BETA PETG sulla Bambu A1.
- Ora «Orienta per la stampa», «Ruota» e «Sposta» funzionano anche con modelli di superfici STEP, con rotazioni di quasi 180° e su facce riconosciute in parte. Il corpo resta esatto.
- Una parete esterna più lenta vale ora anche per i perimetri piccoli come fori e steli in PrusaSlicer e nella famiglia Orca.
- PrusaSlicer e la famiglia Orca rispettano la densità dei supporti scelta. Il campo parte dall'1 %. Per stampare senza supporti, scegli «Nessuno».
- Nelle stampe multicolore con OrcaSlicer, ElegooSlicer, Bambu Studio e Creality Print, la torre di spurgo parte da una posizione adatta alle dimensioni del piatto.
- I pezzi troppo grandi vengono segnalati prima di avviare lo slicer. Se non si trova spazio per tutti su un piatto, puoi distribuirli su più piatti.
- I caratteri speciali nei nomi di progetto o utente non impediscono più di creare il file di stampa. Cura legge anche i modelli con nomi turchi o cinesi.
- Solidon dispone sul piatto le parti sovrapposte prima dello slicing con PrusaSlicer o Cura e avvisa se non trova una disposizione adatta.
- Se PrusaSlicer o SuperSlicer segnala un primo strato vuoto, Solidon indica il pezzo e permette di posizionarlo sul piatto o aprire le impostazioni di stampa pertinenti.
- Gli avvisi di PrusaSlicer e SuperSlicer compaiono nel rapporto anche se lo slicer riesce, uno strato vuoto come errore. La distanza dal raft si imposta a parte.
- Se lo slicer divide un piatto in più file di stampa, Solidon lo segnala e propone di disporre o esportare. Prima ne prendeva in silenzio uno solo.
- In cima al rapporto vedi se il trasferimento è pronto, richiede una decisione o è sconsigliato, e cosa resta da verificare. Senza rilievi un pezzo non vale più da solo come pronto per la stampa.
- Un rilievo selezionato indica la sua conseguenza per la stampa, e ogni azione proposta dice cos'altro cambia.
- Dopo l'esportazione o «Apri nello slicer …» Solidon rilegge il file. Il resoconto nel rapporto indica file, destinazione di stampa, materiale, impostazioni e se il file corrisponde alla richiesta.
- Esportato in 3MF dalla riga di comando, un corpo di un solo colore mantiene il suo filamento quando lo riapri.
- Per le impostazioni dei singoli pezzi, la riga di comando indica quali pezzi sono e quale valore ricevono.
- Se accetti i supporti per un ponte lungo sopra il pezzo stesso, ora arrivano anche lì. Prima si aggiungeva «Solo dal piano», e diversi slicer stampavano il ponte senza supporto.
- I pezzi piccoli distesi, come le viti, non ricevono più supporti proposti dove un bordo di taglio mostrava per errore un punto sospeso.
- Se un pezzo termina in alto in uno spigolo che lo slicer non stampa, dopo lo slicing Solidon non segnala più un modello tagliato.
- Se il primo strato di un pezzo è più stretto di una linea, il messaggio dopo lo slicing propone le linee di parete e il raft come via d'uscita.
- SuperSlicer mantiene la disposizione di Solidon e non spinge più i pezzi fino al bordo del piano; lo skirt resta sul piano.
- Se un pezzo entra nel piano solo ruotato, arriva ruotato a OrcaSlicer, Bambu Studio ed ElegooSlicer; se a Creality Print non basta il margine, Solidon lo dice prima.
- Solidon propone un brim solo largo quanto il piano lo consente.
- Se il bordo attorno a un pezzo entra in una zona esclusa del piano, il controllo prima dell'esportazione lo segnala.
- Se nello slicer si incrociano i percorsi di due pezzi, o di un pezzo e della torre di spurgo, il messaggio lo dice e propone vie d'uscita.
- Se il brim è su automatico, Solidon avvisa prima dell'esportazione quando può uscire dal piano o entrare in una zona esclusa, e propone una larghezza fissa.
- I supporti e lo skirt al bordo del piano contano nel controllo prima dell'esportazione, con l'allargamento del primo strato di supporto indicato dal profilo dello slicer.
- I file STL esportati da pezzi STEP non contengono triangoli senza area.

### Fori, asole e divisione

- L'angolo di un'asola su un foro importato punta nella direzione attesa e la mantiene quando cambi la finezza.
- Un'asola in una parete laterale rivolta a sinistra o a destra si può accorciare, restringere e ruotare. I progetti delle versioni precedenti mantengono le loro asole finché non cambi il passaggio.
- Sui corpi STEP un'asola in una faccia inclinata non risulta più sporgente di lato, e un secondo trascinamento su un'asola che finisce in un gradino non riempie più il corpo.
- Un'asola attraverso una piastra inclinata o smussata mostra tutta la sua profondità sui corpi STEP, e la sua copia oltre il bordo dà lo stesso messaggio su pezzi STL e STEP.
- Su un corpo con facce e spigoli veri, un blocco inserito dopo un foro resta sulla faccia scelta, e «Crea coperchio a vite» riesce anche sul bordo di una scatola svuotata.
- Due piastre che si toccano restano un solo corpo attorno a un foro e conservano il materiale, che tu lo allunghi, lo modifichi, lo sposti o lo chiuda. Una spina sopra resta al suo posto.
- Allungare un foro che attraversa due corpi non segnala più che il corpo si spezza quando non succede.
- Se un foro taglia il corpo in due, il rapporto lo dice una volta sola, con il numero di pezzi alla fine, e tace appena il corpo torna a essere un pezzo unico.
- I motivi sulle facce cilindriche dei modelli importati restano chiusi quando li modifichi.
- Nella cronologia di un corpo STEP puoi riordinare i passi o inserirne uno prima, anche se un passo successivo riguarda un foro. Il riferimento segue il foro.
- Un foro semplice o un'asola spostati o duplicati con una nuova direzione restano esatti su un corpo STEP.
- Una caratteristica riconosciuta a più di un metro dall'origine mantiene il suo posto quando la modifichi. Prima il campo tagliava il numero in silenzio e il foro si spostava.
- Se un passaggio colpisce un pezzo la cui superficie interseca se stessa, si ferma e mostra il punto. Altrove continua a calcolare e avvisa che i pezzi non si sono potuti unire.
- Ora «Dividi il modello» taglia una figura anche lungo la sua cucitura di simmetria senza lasciarla aperta, e le spine sono già al loro posto nell'anteprima.
- Se un taglio sfiora soltanto una parete, «Dividi il modello» indica il punto e porta alla posizione del taglio invece di fallire sulle spine.
- Tronca ora taglia anche in obliquo: in alto scegli il «Piano»: su un asse con inclinazione, parallelo a una faccia, per uno spigolo o per tre punti cliccati nella vista.
- Un corpo STEP resta un corpo STEP quando lo tronchi, con facce, spigoli e nomi.
- Un coperchio a vite appena creato non risulta più troppo stretto per il suo collo.
- Se un foro non si riesce a tagliare in modo pulito in un corpo STEP, Solidon lo esegue sul modello a triangoli invece di passare avanti un corpo difettoso.
- Se hai scelto «Carica subito», anche i pezzi di «Dividi il modello» non avviano più minuti di riconoscimento; «Riconosci tutte le caratteristiche» lo recupera.
- Scegliendo «Dividi il modello» su una riga riassuntiva del rapporto per più corpi, Solidon li divide uno dopo l'altro. Prima veniva diviso solo il primo.
- Se con «Unisci» un corpo copre un foro del tutto o in parte, il rapporto lo segnala con il punto e la cavità che resta.
- I motivi circolari e «Specchia» prendono il loro «Centro di rotazione» da un corpo, una caratteristica, un punto o l'origine. Il centro resta fisso anche se il corpo si sposta in seguito.
- Un trascinamento nell'apertura di un foro svasato selezionato lascia fermo il corpo, e la riga di stato indica la via per l'asola. Finora spostava tutto il corpo.
- Quando la scheda delle quote di un foro diventa alta, le altre quote restano accanto al corpo, e la maniglia per spostare sta all'imboccatura invece che dentro il pezzo.
- Se selezioni un foro fatto in Solidon, il suo diametro compare solo nella scheda delle quote nella vista. Finora compariva una seconda volta a destra.
- Una direzione che inserisci a destra per un'asola passa anche alla scheda delle quote nella vista, e «Applica» resta disponibile. Finora lì tornava a 0°.
- Solidon riconosce coni, anche piatti e corti, raccordi e facce strette allo stesso modo su più modelli, che il modello sia spostato, ruotato o scalato.
- Un lato superiore bombato si chiama anche sui corpi STEP «Faccia curva» invece di «Raccordo», e i pezzi STL arrotondati ovunque mostrano ogni raccordo, come lo stesso pezzo da STEP.
- Lettere e contorni curvi dei modelli importati non mostrano più falsi raccordi.
- Solidon riconosce ogni campo di nervature, nido d'ape o bugne di un file importato come un solo motivo, e «Riconosci caratteristiche qui» raggruppa le celle di un campo.
- Un campo piccolo che Solidon legge solo come caratteristiche singole diventa un motivo con «Raggruppa come motivo». I motivi nei file STEP vengono riconosciuti direttamente.
- Anche nei progetti di versioni precedenti i pezzi di una divisione automatica vengono numerati, e un taglio eliminato o disattivato non conta più.
- Un foro duplicato, spostato o ripetuto lungo una faccia inclinata resta lo stesso foro su pezzi STL e STEP, con le stesse misure e gli stessi messaggi.
- Dopo «Ripeti caratteristica», una copia su un pezzo STEP non fora più fino alla faccia superiore, e un foro STL a sfaccettature grossolane resta passante.
- Una filettatura si allarga o si stringe con «Cambia caratteristica» senza sfondare la parete, e la filettatura opposta di un accoppiamento filettato cambia con essa.
- Una coppia di filettature stampate supera la verifica dell'accoppiamento: entrambe indicano la misura con cui sono costruite, e la verifica si aspetta il gioco di entrambe le metà.
- Con «Verifica il percorso di montaggio», i pezzi possono anche ruotare, oppure essere inseriti e poi ruotati come una baionetta.
- Un pezzo da «Crea pezzo di prova» ritaglia la stessa finestra da entrambe le parti di un accoppiamento e indica il gioco.
- Un foro svasato che dopo la duplicazione, lo spostamento o la ripetizione finisce tutto nel materiale non segnala più di sporgere oltre il bordo.
- Se la svasatura di una copia supera un lato, Solidon ritrova la copia allo stesso modo su pezzi STL e STEP.
- Se duplichi un foro lungo il suo asse nel vuoto, l'originale mantiene il suo nome sui pezzi STL, e la copia risulta persa come sui pezzi STEP.
- Una gola o un cordone diviso in due archi da un'apertura compare nei pezzi STEP come un unico anello nell'albero, come nei pezzi STL e 3MF.
- Le caratteristiche uguali nei pezzi STEP, come due parti di una superficie conica, mantengono il loro nome quando fori, duplichi, cambi un foro o inserisci un componente altrove.
- Le caratteristiche che vanno insieme compaiono come gruppo nell'albero degli oggetti, e camere e chiusure cambiano in blocco: misura interna, profondità, gioco e corsa di rotazione.

### Raccordi e smussi

- Arrotondare un gruppo di spigoli su un corpo STEP arrotonda ora gli spigoli possibili invece di rifiutare tutto. «Mostra il punto» trova ogni spigolo escluso.
- Gli spigoli accanto a una parete non più spessa del raggio restano vivi, e il report indica il raggio che lì entra. Finora veniva rifiutato l'intero raccordo.
- Se un corpo STEP non ha uno spigolo proprio in un punto scelto, il report offre «Termina la modifica delle facce e riprova». Sul modello a triangoli viene arrotondato anche lì.
- Se manca spazio per lo scambio con il processo di calcolo, Solidon calcola comunque il passaggio e lo segnala nel report. Prima si fermava consigliando un calcolo più grossolano.

### Modellare, testo e schizzo

- Con «Su entrambe le facce», «Applica testo» mette le lettere anche sul retro, leggibili da fuori. Va bene per bandierine, cartelli e targhette.
- Le scritte vengono composte con più precisione: le lettere stanno al loro posto e le curve seguono il carattere, invece di perdere fino al 2 per cento di superficie nelle misure piccole.
- La simmetria in «Modella» specchia al centro del corpo, anche lontano dal centro del piano. I progetti più vecchi mantengono la loro forma.
- Il pennello di modellazione agisce solo sulla faccia rivolta verso di lui. Scavare una piastra sottile non spinge più anche la faccia inferiore.
- Un tratto sul piano di simmetria agisce una volta invece di due, e subito accanto il tratto e il suo riflesso si fondono con continuità.
- L'editor dello scheletro mostra ossa e giunto nella vista, e un giunto sta al centro del corpo invece che sulla pelle, così la figura si piega in modo uniforme.
- La barra di modellazione chiama ora «Intensità» il valore del pennello invece di «Spessore», che faceva pensare a una parete.
- Se un tratto di modellazione buca la parete o la rende troppo sottile, il rapporto e l'esportazione lo segnalano, con «Mostra il punto» e «Annulla il tratto».
- Ora «Fondi dolcemente» calcola fine anche nella finestra, finché il corpo non è molto grande.
- Se un blocco come un buco di serratura sporge oltre il bordo della sua faccia, anche solo con la svasatura o lo smusso, o entra in una parete dietro, il rapporto lo segnala.
- Una misura digitata come lunghezza 40 allunga lo schizzo solo in quella direzione. Il corpo che ne nasce resta chiuso e appoggiato sul piano.
- I disegni SVG arrivano corretti: rotazioni, inclinazioni, angoli arrotondati, ellissi e archi ellittici sono giusti, e i livelli nascosti restano fuori.
- La destinazione di «Allinea alla caratteristica» parte vuota, e il primo clic nella vista la riempie. «Applica» aspetta fino ad allora invece di mettere il corpo dal lato sbagliato.
- Un file in metri che starebbe sul piano anche letto in pollici non viene più letto in modo sbagliato senza avviso. Solidon chiede l'unità.
- Un altro tratto in una cavità appena scavata la rende più profonda, anche con un pennello piccolo. Finora restava senza effetto e contava come mancato.
- In «Modella», la finestra mostra ogni tratto con la stessa rapidità anche dopo molti tratti, e le sessioni grandi calcolano l'anteprima in background. Finora rallentava a ogni tratto.
- Con «Fissa lo stato», Solidon salva una sessione di modellazione fine come la calcolano esportazione e stampa, e la finestra resta utilizzabile. Finora salvava la vista più grossolana.
- Un doppio clic su «Modella» nella cronologia riapre la sessione con i suoi tratti. Ctrl+Z annulla un tratto intero, e «Fatto» cambia lo stesso passaggio.
- La voce «Crea da uno schizzo …» inizia subito a disegnare, il piano di disegno mostra la sua origine, e un doppio clic nella cronologia riapre un disegno in modalità disegno.
- In «Modella» e nell'editor dello scheletro, la barra mostra spessore di parete o sbalzo come mappa con legenda e segnala un tratto oltre il volume di stampa. Dopo la piegatura dice come si stampa.
- Una texture applicata si seleziona per intero. Il pannello di selezione offre allora «Cambia texture» e «Rimuovi texture».
- Il testo segue un arco o avvolge una superficie arrotondata, e «Intarsia testo» lo inserisce a filo nel suo colore.

### Generare con l'IA

- Annullare durante «Un altro tentativo» ferma solo il tentativo in corso. Quelli finiti restano da scegliere.
- Ogni tentativo nell'elenco indica la sua frase o immagine e il seme. Se il tuo input non corrisponde più al tentativo scelto, la finestra dice quale verrà applicato.
- Ora «Configura modello immagine …» scarica il modello di immagine anche se gli altri pesi ci sono già.
- Se un errore durante la generazione indica la configurazione come via d'uscita, compare come pulsante nella finestra.
- Mentre si genera un modello, la finestra resta utilizzabile. La finestra di dialogo si sposta di lato, e la barra di stato mostra avanzamento, tempo e «Annulla».
- La finestra di generazione indica il volume alla misura con cui arriva il pezzo.
- Un modello generato si annulla con un solo Ctrl+Z. Prima ne servivano tre o quattro.
- Se «Applica» viene rifiutato durante la generazione, la finestra resta aperta con tutti i tentativi e indica la via d'uscita invece di scartare la mesh.

### Uso e sistema

- Su Mac, Solidon non si chiude più poco dopo l'avvio. Nella versione 0.5.1 succedeva su ogni Mac, anche senza un mouse 3D collegato.
- La spunta «Creare le misure come parametri» è attiva la prima volta e poi ricorda la tua ultima scelta, anche dopo un riavvio.
- Le finestre di dialogo si aprono alla misura del loro contenuto, senza spazio vuoto, e una misura che hai trascinato tu resta.
- Esportazione, «Esegui slicing» e «Apri nello slicer …» ricevono sempre il calcolo fine, non la vista più grossolana della finestra. Raccordi e coni arrivano nel file a piena risoluzione.
- Un'esportazione durante un calcolo in corso aspetta il nuovo risultato. Prima il file poteva avere ancora la misura vecchia.
- Se esporti solo una parte della scena, la finestra del file e la conferma indicano quanto contiene, ad esempio «1 di 2 corpi».
- La barra dei parametri rifiuta una misura oltre il suo limite invece di lasciare la vista vuota.
- Nella barra dei parametri conta ogni passo di freccia, e il focus resta nel campo.
- Nella barra dei parametri le misure di due parallelepipedi portano il loro numero, e una misura con un proprio campo di lavoro ha un cursore.
- Se un passo attende una domanda, «Applica» resta disponibile e la domanda compare.
- Nella finestra di un'operazione le etichette stanno in una colonna, i campi hanno la stessa larghezza e ogni interruttore sta prima di ciò che comanda.
- Le spunte negli elenchi si leggono in ogni riga, e i colori compaiono come un pallino rotondo accanto.
- La tavolozza dei comandi spiega strumenti e azioni sui file in una frase.
- Dopo un cambio di parametro, «Genera varianti» parte dal valore di quel parametro.
- Se il salvataggio di una calibrazione non riesce, restano i valori precedenti.
- Nel progetto di esempio della seconda via, i fori per le viti seguono larghezza e spessore.
- La finestra «Novità» e il sito mostrano le evidenziazioni come testo marcato invece che con asterischi.
- Tutte le traduzioni usano le stesse parole per caratteristiche, pulsanti e termini di stampa, e i messaggi seguono la punteggiatura di ogni lingua.
- Il pulsante che scala il consumo dal magazzino filamenti ora si chiama «Detrai», e i suggerimenti nominano le azioni come la finestra, per esempio «Uniforma i triangoli».
- Il modo di rivolgersi è coerente: spagnolo, portoghese e francese usano la forma di cortesia, l'italiano il tu. Tre messaggi in spagnolo e portoghese che dicevano il contrario sono corretti.
- Mentre una finestra mostra l'anteprima, gli spazi arrivano in ogni campo di testo, anche nel questionario e nella chat, e caselle e pulsanti accettano la barra spaziatrice.
- Con «Scala» un corpo resta appoggiato sul piano invece di affondare sotto la piastra, e la vista lo reinquadra quando cresce.
- Alcuni rilievi che riguardano un passo lo aprono per modificarlo, per esempio «Cambia dimensione» dopo «Porta a misura».
- Una riga riassuntiva del rapporto come «Riduci al volume di stampa» è un solo passo di annullamento per tutti i corpi.
- L'aiuto di un'operazione salta nel manuale direttamente alla sua voce, e il riferimento chiama campi e scelte come nella finestra di dialogo.
- Quando altri programmi tengono occupato il computer, «Annulla» ferma un calcolo lungo in meno di un secondo invece di chiedere un riavvio dopo alcuni secondi.
- Un modello linguistico locale può fare dodici passi invece di otto per richiesta nella chat e risolve così più richieste composte da più parti.
- Il pannello di selezione torna a stare nella sua colonna, e la colonna delle misure nell'albero mostra la misura intera, per esempio «Ø5,19 mm» invece di «…».
- Su un foro, «Cambia caratteristica» apre direttamente «Cambia foro» con anteprima, invece di limitarsi a rimandarvi.
- Premendo «Applica» durante un'anteprima in corso, Solidon calcola la modifica una sola volta. Prima la calcolava poi una seconda volta.
- La vista delle differenze tratteggia ciò che si aggiunge e ciò che si toglie in due direzioni, così si distinguono anche senza colore.
- Quando Solidon chiede l'unità di un file all'apertura, le misure compaiono nella tua unità di visualizzazione e con il separatore decimale della tua lingua.
- Se trascini un file che Solidon non apre, ad esempio da Blender, ti dice come portarlo come 3MF, STEP o STL. Il G-Code va a «Controlla il G-Code».
- Puoi aprire più file in un solo passaggio. Mantengono la loro posizione reciproca, un Ctrl+Z li annulla tutti, e gli avvisi di importazione uguali compaiono raggruppati nel rapporto.
- Sopra la cronologia, «Prima/dopo» mostra con un cursore ogni stato precedente. «Continua qui» inserisce lì nuovi passaggi, e i nomi dei tuoi passaggi restano.
- Con «a», «Sposta» porta il centro, il centro della base, un angolo o una caratteristica in una posizione fissa, e «Ruota» porta il corpo ad angoli fissi, anche con più corpi.
- Se copi il link della pagina di un modello, compare già nel campo di «Modello dalla rete», e Solidon mostra la via attraverso il browser.
- Se una finestra di dialogo non può applicare, il motivo compare anche sotto i suoi campi, non solo nella fascia sopra la vista.
- Dopo Ctrl+Y, la riga di stato indica il passaggio ripristinato, come dopo Ctrl+Z.
- Le anteprime di esempi e blocchi mostrano l'altezza verso l'alto. Finora i pezzi alti vi puntavano verso il basso.
- Gli esempi inclusi si aprono con la tua stampante e il tuo materiale. Finora venivano calcolati per la stampante generica.
- Se Solidon non riesce a salvare la scelta «Includi i valori», l'avviso compare direttamente accanto all'interruttore.
- Se altri programmi occupano tutti i core su Windows, un calcolo su un modello grande non resta più fermo per minuti.
- Le lunghezze nei messaggi usano il separatore decimale della tua lingua.
- Dopo il caricamento di un modello grande, l'indicatore di caricamento resta finché la vista mostra il modello.
- Un clic su una riga del rapporto di verifica seleziona i suoi corpi anche se l'elenco si sposta durante il clic.
- I numeri fissi si collegano con un clic a una misura del progetto, e il selettore dei piani nomina i corpi di ogni piano e mostra intero quello scelto.

## 0.5.1

### Stampare e passare allo slicer

- In PrusaSlicer, ElegooSlicer, Bambu Studio, Creality Print e OrcaSlicer vale il profilo del produttore. Solidon scrive solo ciò che modifichi o accetti dai suggerimenti.
- Il livello «Standard» stampa con velocità e accelerazioni del profilo del produttore invece di frenare tutto a 40 mm/s. Su una Centauri Carbon 2 i pezzi grandi richiedono il 40-50 % di tempo in meno.
- I suggerimenti applicati valgono solo per il pezzo che ne ha bisogno: supporti, brim e valori di un accoppiamento, in ogni slicer supportato. Le impostazioni di stampa nominano i pezzi.
- Se un pezzo si stampa in piedi senza supporti, «Orienta per la stampa» lo lascia in piedi invece di adagiarlo su supporti. Un set da minigolf di 16 pezzi sta così su un piatto invece che su quattro.
- Se un pezzo non entra sul piano in nessuna posizione, le impostazioni di stampa dicono prima dello slicing di quanto è troppo grande e propongono «Dividi il modello» e «Riduci al volume di stampa».
- Anche dove le parti di un modello si toccano soltanto, «Dividi il modello» riesce, e i connettori stanno nel verso giusto nei loro fori a ogni giunzione. Prima il rapporto segnalava collisioni.
- Solidon prende l'angolo di sbalzo dal profilo del produttore della stampante: 60 invece di 45 gradi per Elegoo, Bambu e Creality. Smussi e pendenze lievi non ricevono più supporti inutili.
- Sulle pareti esterne tonde Solidon propone una «Cucitura a sciarpa», in ogni slicer supportato. La stampa dura così dal 2 al 4 % in più.
- Se il tuo slicer calcola da sé il brim, come ElegooSlicer, Bambu Studio, Creality Print e OrcaSlicer, Solidon non ne propone uno suo. Quello dello slicer dà più bordo ai pezzi alti.
- I livelli «Fine», «Bozza» e «Resistente» scelgono ora il processo corrispondente del tuo slicer, ad esempio «0.12mm Fine» per «Fine».
- Le impostazioni di stampa mostrano ciò che viene stampato: la base è il profilo del produttore, i tuoi valori sono evidenziati e si ripristinano uno per uno.
- Il piatto di stampa si sceglie nelle impostazioni di stampa e la temperatura del piano lo segue. Se il produttore non ammette il piatto per il tuo filamento, Solidon lo dice prima.
- Senza «Applica i suggerimenti» nessun pezzo riceve più un brim senza chiederlo, né all'esportazione né nel passaggio allo slicer.
- Nuovo suggerimento «Tenere liberi i canali»: applicato, la consegna blocca i supporti nei canali in ogni slicer supportato. Anche la finestra di Cura riceve il blocco e i valori per pezzo.
- Un soffitto sopra un canale d'acqua o un tunnel non richiama più supporti sul modello. Se nient'altro li richiede sul modello, Solidon li propone solo dal piano.
- Le impostazioni di stampa mostrano i suggerimenti più in fretta: sul supporto per trapano dopo 4,3 secondi invece di 7,6.
- I progetti della 0.5.0 stampano alla velocità della tua stampante. Ciò che avevi impostato tu resta.
- La velocità del primo strato vale ora anche per il suo riempimento. Prima lo slicer stendeva il fondo alla velocità del produttore, 105 mm/s sulla Centauri Carbon 2.
- Con PrusaSlicer la stampa inizia ora come con Prusa stessa: con livellamento del piano, linea di spurgo e controllo della stampante.
- Il PETG arriva ora a PrusaSlicer come PETG, non più come PLA.
- In OrcaSlicer ogni stampante riceve preselezionata la propria macchina con il suo processo standard: la Sovol SV06 non riceve più la versione High-Speed, né la Ender-3 V3 «0.12mm Fine».
- Nuove: le Creality Ender-3 V3 SE e V3 KE. Finora una SE riceveva i valori della molto più veloce Ender-3 V3.
- Le copie uguali vengono calcolate una sola volta da «Orienta per la stampa», che finisce lo stesso set da minigolf in meno di un terzo del tempo.
- I livelli di qualità nella finestra di stampa appaiono ora nella lingua dell'interfaccia.
- Anche la velocità degli spostamenti a vuoto viene dalla stampante: la Centauri Carbon 2 si sposta a 500 invece di 150 mm/s, come nel profilo di Elegoo.
- Se hai misurato lo sbalzo della tua stampante, anche lo slicer mette i supporti solo da quell'angolo, finché valgono l'altezza dello strato e la larghezza del cordone della misura.
- Anche il rapporto calcola ora gli sbalzi con l'angolo a partire dal quale il tuo profilo dello slicer mette i supporti.
- Se un brim, uno skirt o un raft sporge oltre il piano, Solidon lo segnala nel passaggio allo slicer e propone «Disponi sul piano».
- Se lo slicer rifiuta un pezzo troppo alto, Solidon indica entrambe le altezze e propone «Dividi il modello», «Riduci al volume di stampa» o un'altra stampante.
- Se lo slicer rifiuta un pezzo che non entra nel suo piatto, Solidon indica il motivo e propone «Dividi il modello», «Riduci al volume di stampa» e «Disponi sul piano».
- Se Bambu Studio resta bloccato dopo lo slicing, Solidon prende il file di stampa finito invece di segnalare un errore dopo cinque minuti.
- Con Cura si può fare lo slicing anche di modelli grandi. Prima lo slicing finiva senza file di stampa, per esempio con la torre Eiffel da 313 000 triangoli.
- Se Creality Print può calcolare un 3MF solo nella sua finestra, Solidon lo dice e porta ad «Apri nello slicer …».
- Se il primo strato ha tratti stretti, anche pochi e lunghi su un pezzo grande, Solidon propone di stenderlo a 50 mm/s. Così le linee corte aderiscono meglio.
- Solidon propone un «Tempo minimo per strato» più lungo solo dove il tuo profilo non ne ha uno. Prima il suggerimento arrivava su quasi ogni pezzo con uno smusso o una punta.
- Dove il tuo slicer limita già la velocità in base al flusso volumetrico, Solidon non propone più un proprio limite di velocità.
- Se adotti i valori di un profilo di filamento e poi cambi filamento, tornano a valere i valori del nuovo.
- Il primo strato stampa ora linee larghe quanto il profilo della tua stampante, di solito 0,5 mm con ugello da 0,4. Con Cura la testina non va più a passo d'uomo tra una e l'altra.
- Con Cura la stampa inizia ora con il codice di avvio della tua stampante, come dal produttore. Se Cura non conosce la stampante o il codice manca nel file di stampa, Solidon te lo dice.
- Con Cura il primo strato usa ora l'accelerazione del profilo del produttore invece dell'accelerazione di stampa piena.
- I supporti di Cura seguono ora lo schema dei profili di fabbrica: collegati, con un tetto leggero e velocità moderata.
- Con Cura le pareti a sbalzo si stampano ora più lentamente, come dal produttore. Le stampe con molti sbalzi durano fino a circa il 20 % in più.
- Con Cura il riempimento si stampa ora dopo le pareti, e gli spostamenti evitano i supporti e ritraggono il filamento sui percorsi lunghi.
- Il profilo per la finestra di Cura corrisponde ora alla stampante configurata in Cura. Prima Cura lo rifiutava con alcune stampanti o non lo mostrava.
- Le impostazioni di stampa non offrono più il flusso volumetrico per Cura, perché Cura non lo legge.
- I supporti a griglia arrivano allo slicer come vera griglia, con la direzione che cambia a ogni strato, invece che come linee sciolte che si spostano in stampa.
- Se un pezzo poggia su molti piedini, Solidon propone un brim dove il tuo slicer non ne calcola uno da sé, anche se i piedini insieme avrebbero superficie sufficiente.
- Una striscia stretta e inclinata lungo la parete esterna non conta più nel rapporto come un lungo ponte.
- Una scritta che è un pezzo a sé accostato a una parete non inizia più a mezz'aria nel rapporto, e Solidon non propone più supporti per essa.
- Il rapporto mostra l'avviso di calibrare le tolleranze del tuo materiale solo sui modelli con accoppiamenti. Solo lì Solidon le usa.
- Il passaggio a Cura trasmette i primi strati senza ventola come avvio graduale. L'avviso arriva solo se il file di stampa finito si discosta davvero.
- Dopo «Riduci al volume di stampa» il pezzo resta appoggiato sul piano. Prima si sollevava, e il rapporto lo segnalava come sospeso.
- Se un pezzo entra sul piano solo con un margine più stretto, «Disponi sul piano» lo mette al centro invece di farlo sporgere dal bordo, e il rapporto indica quel margine.
- Sui modelli grandi, «Dividi il modello» trova la giunzione fino a due volte più in fretta, e su quelli multicolore in una frazione del tempo. La divisione avviene come prima.
- Se Solidon divide automaticamente un modello in tre o più pezzi, i nomi vengono numerati e indicano i connettori, per esempio «Listello da parete 2 di 3 · Spine e fori».
- Una vite, un dado o una guarnizione stampati dal catalogo dei blocchi non contano più nel rapporto come un corpo frammentato. È un pezzo a sé, ed è voluto.
- Viti e dadi stampati hanno gioco anche sotto la testa e sull'appoggio, e restano svitabili anche se stampati insieme al pezzo. I progetti più vecchi segnalano la modifica all'apertura.
- Con una vite a testa svasata dal catalogo dei blocchi, un corpo fatto di facce e spigoli resta stagno all'esportazione: pezzo e vite entrano nel file ciascuno chiuso.

### Modificare i fori

- Un foro con svasatura da un lato e smusso dall'altro si può inclinare, spostare e duplicare. Prima Solidon rifiutava.
- Un foro o una svasatura inclinati non tagliano più ciò che sta davanti alla loro imboccatura, come una nervatura o il nido d'ape accanto.
- Un foro svasato su una faccia bombata si può spostare, anche con un clic nella vista. Dopo lo spostamento, l'inclinazione o la rimozione, il vecchio punto torna a filo con la faccia.
- Un foro svasato con il bordo dell'imboccatura arrotondato su una faccia piana si può spostare, duplicare e rimuovere insieme all'arrotondamento. Prima restava un avvallamento.
- Fori ciechi, asole e allargamenti in una faccia inclinata, e fori ciechi inclinati come una tasca per magnete senza labbro, restano del tutto aperti all'imboccatura. Prima vi restava una pellicola.
- Spostare e duplicare avvisano quando la parete verso il foro vicino diventa troppo sottile o si rompe.
- Se un foro esce dal fianco del pezzo dopo uno spostamento, una duplicazione o un'inclinazione, Solidon lo dice anche nei punti a gradino. Una copia non creata viene notata.
- Un foro spostato o duplicato da un file STL non segnala più per errore, nelle piastre sottili, di non essere più passante.
- Su nervature e nidi d'ape, un foro inclinato non segnala più per errore di sporgere oltre il bordo.
- Dopo spostamento, inclinazione o duplicazione, il pannello delle caratteristiche mostra le quote che il risultato ha davvero.
- Forare, spostare, «Modifica foro» e l'allungamento in asola lasciano il modello com'era lontano dal foro. Il riconoscimento successivo finisce molto più in fretta sui modelli grandi.
- Se su un corpo fatto di facce e spigoli, per esempio da un file STEP, un taglio di foro fallisce senza che si noti, Solidon se ne accorge e ricalcola. Prima poteva restare un corpo rotto.
- Sui corpi fatti di facce e spigoli, i passaggi di foratura sono pronti in pochi secondi: su una piastra forata proveniente da un file STEP, «Modifica foro» richiede 2 secondi invece di circa 120.
- Sui corpi fatti di facce e spigoli, «Ritaglia tasca» non restituisce più un corpo difettoso.
- Un'asola si può accorciare. Tirata alla sua stessa larghezza, torna a essere un foro rotondo.
- La maniglia all'estremità di un'asola si afferra in qualsiasi punto dell'apertura, e al primo trascinamento non salta più verso il puntatore.
- Le asole portano con sé gli smussi e l'imboccatura obliqua quando vengono spostate o duplicate. Prima gli smussi restavano nel punto vecchio.
- Una tasca per magnete del catalogo dei blocchi si può spostare, duplicare, moltiplicare e rimuovere, insieme al labbro che trattiene il magnete.
- Su una tasca per magnete, «Modifica foro» con «Includi svasatura, gradini e restringimento» cambia il diametro con il labbro. «Solo diametro del foro» mantiene l'apertura e avvisa se diventa stretta.
- Posizionata obliquamente rispetto alla faccia, l'apertura di una tasca per magnete, di un foro per vite o di una sede per cuscinetto resta libera. Prima un cuneo di materiale la copriva.
- Se una tasca per magnete o un attacco a buco di serratura sta inclinato rispetto alla faccia, Solidon avvisa che il labbro tiene solo da un lato e propone «Correggi l'inserimento».
- Se un blocco come una tasca per magnete non asporta nulla nel punto scelto, Solidon lo segnala e consiglia di fare clic sulla faccia.
- Su una tasca per magnete con labbro, «Allunga in asola» rifiuta ora anche sui corpi fatti di facce e spigoli, invece di tagliare il labbro.
- Se metti una filettatura, un inserto a caldo o una sede per dado su un foro, la finestra indica in alto la misura adatta e preseleziona proprio quella.
- Su una svasatura, «Modifica elemento» taglia la nuova misura come se fosse stata svasata così fin dall'inizio. Prima Solidon rifiutava oppure lasciava una pellicola sottile di traverso sul foro.
- Se parti di un modello sono infilate l'una nell'altra, Solidon le unisce prima del calcolo, come verranno stampate. Volume e fori tornano, e il rapporto lo dice.
- Quando allarghi un foro, l'anteprima precisa mostra tutto il materiale asportato, anche sui modelli grandi, con una sezione della vista e sui corpi con canali chiusi.
- Mentre digiti una quota su una figura grande, l'anteprima grossolana compare in meno di un secondo invece che fino a diciannove, e l'anteprima di un foro riesce.
- Se un passaggio su un modello aperto calcola solo in modo approssimato e il volume cresce, il rapporto indica lo scostamento e propone «Prima ripara, poi ricalcola».

### Raccordi e smussi

- La scelta di spigoli «Orizzontale», «Alto» o «Basso» non prende più il bordo di un foro laterale. Se lo vuoi, sceglilo da solo; i progetti più vecchi calcolano come salvati.
- Su un modello importato il bordo di un foro viene raccordato o smussato alla stessa profondità di un pezzo costruito. Prima, con raggi grandi, il raccordo veniva fino a un quinto troppo piatto.
- Se la quota non sta su ogni spigolo di una scelta come «Tutti» o «Verticale», Solidon lavora quelli in cui sta e mostra gli altri con «Mostra il punto», invece di rifiutare.

### Quote nella vista

- Da un foro all'altro le quote nella vista compaiono in un terzo del tempo. Il primo clic su una caratteristica non blocca più la finestra, nemmeno sui modelli grandi.
- Un clic su un foro non mostra più immagini intermedie: pannello di selezione e scheda delle quote compaiono subito al loro posto, senza saltare.
- Un clic sulle frecce di un foro selezionato non blocca più la selezione: il foro successivo si può cliccare come sempre.
- Esc sulle quote nella vista scarta la bozza e toglie la selezione, come «Annulla».
- Un clic su «Applica» non va più perso in silenzio, e le quote che non hai digitato restano esattamente come sono state misurate.
- Un foro iniziato non va più perso per strada: un clic nel rapporto, un cambio di strumento o Ctrl+Z chiedono prima di applicarlo o annullarlo.
- Digitando una coordinata, i campi quota non spariscono più dopo la seconda cifra.
- Sui modelli grandi, «Misura lo spessore di parete» risponde circa quattro volte più in fretta.
- Un clic al centro di un foro svasato seleziona il foro e non la svasatura, e le quote indicano il bordo per lato, come «Bordo esterno a sinistra» invece di «Bordo esterno 4».
- Con uno spigolo o una distanza selezionati, il pannello di selezione non dice più «Nessun elemento selezionato …».

### Riconoscimento

- Le caratteristiche vengono riconosciute da sole fino a 1,5 milioni di triangoli. Fino a cinque milioni Solidon chiede prima e indica la memoria necessaria e la durata sul tuo computer.
- Rifiutato il riconoscimento completo, lo recuperi con «Riconosci tutte le caratteristiche» nel rapporto o da riga di comando. Se è lento, «Carica senza riconoscimento delle caratteristiche» lo salta.
- Sui modelli grandi «Riconosci elementi in un punto» trova facce dove prima segnalava troppi triangoli. Il punto si sceglie anche da tastiera.
- Sui modelli grandi «Riconosci elementi in un punto» inizia subito a cercare. Prima ricalcolava tutto il modello, 40 secondi a tentativo sul drago del mausoleo.
- Modelli grandi e reticoli vengono riconosciuti molto più in fretta: un letto da casa delle bambole generato, 1,2 milioni di triangoli, in 27 secondi invece di 174. Annulla agisce in pochi secondi.
- Le copie e i pezzi ruotati o spostati prendono le caratteristiche del loro originale invece di cercarle di nuovo. Un progetto con molti pezzi uguali viene calcolato così in meno della metà del tempo.
- Dopo un foro, la faccia di un corpo costruito indica la sua misura attuale, e un foro nuovo non manca più nell'albero se prima ne è stato modificato un altro.
- Scritte e montanti compaiono nell'albero come lati arrotondati invece che come decine di raccordi dai raggi variabili.
- I contorni fatti di archi e rette vengono riconosciuti arco per arco con il loro raggio. «Converti in facce e spigoli» diventa così molto più rapido.
- Un perno a gradino non conta più come filettatura. Tornano i cilindri e i fori che questo scambio aveva inghiottito.
- Il labbro di una tasca per magnete si chiama restringimento nell'albero e indica la sua apertura. Nessuna azione lo trasforma più in svasatura.
- Dopo «Affina gli spigoli», Solidon riconosce raccordi, fori e scritte come nell'originale, anche dopo un altro foro. Raccordi uguali mantengono il nome, anche dopo «Sposta».
- Un motivo attorno a un'impugnatura tonda, come una zigrinatura su un coperchio, mantiene centro e direzione mentre continui a modificare.
- Dopo «Dividi» e «Tagliare via», una faccia divisa mantiene il suo nome sul pezzo più grande, e gli accoppiamenti su di essa restano validi.
- Se fai clic sullo spigolo di bordo di un foro sdraiato, si chiama «Verticale», come sta davvero.
- Se un modello ha più di 5 000 caratteristiche, Solidon tiene le più grandi invece di restare senza nessuna. Scalare non rimescola i loro nomi.
- Un blocco con una sola caratteristica si chiama nell'albero come nella cronologia, per esempio «Tasca per magnete» invece di «Foro cieco 1».

### Importare e riparare

- Un modello grande compare nella vista subito dopo l'importazione, e le sue caratteristiche seguono. Prima compariva solo a riconoscimento finito.
- Un 3MF con più piatti da Bambu Studio, OrcaSlicer o ElegooSlicer mette ogni pezzo sul suo piatto, al suo posto. Prima finivano tutti su uno, molti fuori dal piano.
- Un 3MF con più piatti aggiunto a un progetto mantiene i suoi piatti e li mette dopo quelli esistenti.
- Un altro modello va al primo posto libero dei piatti, oppure su un piatto nuovo, e resta lì. Prima manteneva le coordinate del suo file, quasi sempre fuori dal piano.
- Anche un modello da «Genera modello» viene appoggiato sul piano, al primo posto libero dei piatti.
- Un modello senza colori propri resta nel colore del corpo dopo la chiusura dei fori. Prima diventava grigio, e «Converti la texture in filamenti» ne ricavava un filamento grigio.
- Se a un modello manca un pezzo di parete di un foro o parte di un cono di svasatura, Solidon chiude il vuoto come parete, non come coperchio di traverso al foro.
- Le cuciture aperte si chiudono all'importazione e alla riparazione senza unire parti che si toccano soltanto. Un modello integro resta invariato.
- Le sovrapposizioni le risolve ora «Ripara» da solo. Se le parti di un modello importato sono infilate l'una nell'altra, il rapporto propone «Risolvi le sovrapposizioni».
- Una superficie senza spessore resta aperta e propone «Dai spessore». Un'apertura grande indica il suo punto con «Mostra il punto», e «Lascia aperto» lascia aperta solo lei.
- Dopo la chiusura di un'apertura all'importazione, «Mostra il punto» contorna tutta la nuova faccia con un colore proprio.
- Una parte rovesciata accanto a un corpo cavo viene raddrizzata senza perdere la cavità. Una parte dentro il materiale di un'altra viene segnalata invece che indovinata.
- Il rapporto dopo l'importazione è più corto: i rilievi smentiti dal risultato spariscono, e dove si può fare qualcosa c'è un pulsante invece di un consiglio.
- La mappa dei difetti della mesh mostra le zone sane nel colore del corpo, così ogni difetto risalta, e porta «Ripara» nella legenda. Se il corpo è uno solo, lo seleziona da sé.
- La ricerca delle sovrapposizioni arriva ora fino in fondo anche sui modelli con ventagli di triangoli stretti. Mappa dei difetti e riparazione vedono tutto il modello.
- Un 3MF di PrusaSlicer non carica più modificatori, blocchi e rinforzi dei supporti come materiale pieno. Un volume negativo viene sottratto dal pezzo.
- Con «Affina gli spigoli» restano tutte le caratteristiche e i triangoli sono fino a quattro volte meno: un supporto per trapano con spigoli di 1 mm in cinque secondi invece di quattordici minuti.
- Un modello chiuso resta stagno e conserva i colori del filamento. Con troppi triangoli, Solidon indica una lunghezza di spigolo che funziona davvero.
- L'anteprima di «Affina gli spigoli» e «Ridurre i triangoli» è pronta in pochi secondi invece di bloccare la finestra, e una lunghezza troppo fine viene rifiutata subito.
- Se un modello è troppo fine per «Affina gli spigoli», il rapporto propone «Riduci i triangoli e riprova» con un numero che funziona davvero.
- Se «Leviga» rischiasse di rovesciare un corpo, Solidon lo segnala e propone «Affina gli spigoli e riprova» con una lunghezza di spigolo che funziona.
- I grandi assiemi si importano più in fretta: la riparazione all'importazione di una nave pirata da 1,2 milioni di triangoli richiede circa il 30 % di tempo in meno.
- All'apertura di file 3MF grandi la finestra resta utilizzabile, anche mentre il modello viene letto.
- Se importi una copia rinominata di un file già aperto, il corpo porta il nuovo nome. Prima si chiamava come il primo file.
- Sulle mesh grandi «Chiudi la superficie aperta» calcola in pochi secondi: 1,8 invece di 24 secondi con 122 752 triangoli.

### Manuale e sito web

- Quindici guide mostrano passo per passo, con immagini dell'applicazione, come verificare, stampare e riparare un modello, costruire e dividere un pezzo, scriverci sopra o stampare a due colori.
- Il manuale inizia da «Da dove comincio?» e porta da lì a ogni guida. F1 nella finestra di dialogo di un'operazione apre la sua guida o la sua voce.
- Un'immagine d'insieme spiega la finestra: ogni numero nell'immagine indica un'area.
- La ricerca nel manuale trova la pagina giusta anche con parole di tutti i giorni, la mostra per prima e la apre dove compare la parola.
- Il riferimento indica per ogni operazione dove trovarla nel menu o nel pannello di selezione.
- Le pagine esplicative sono più brevi di un terzo. Se una guida per immagini tratta il loro argomento, il collegamento si trova in fondo alla pagina.
- Sul sito web e nel PDF il manuale è organizzato come nell'applicazione, dai primi passi alla consultazione. Nel PDF i segnalibri portano a ogni capitolo.

### Uso e sistema

- I calcoli grandi come l'anteprima o «Affina gli spigoli» girano in un processo a parte: la finestra resta utilizzabile e «Annulla» agisce subito. Per questo gira un secondo processo di Solidon.
- Durante il caricamento e i calcoli lunghi un orologio conta il tempo trascorso anche se l'avanzamento si ferma, e il tempo restante non salta più quando inizia una nuova parte del calcolo.
- Il salvataggio automatico gira in secondo piano e non blocca più la finestra, anche con modelli grandi. Se non si può scrivere, Solidon lo dice.
- Un modello su un'unità lenta o che non risponde non blocca più la finestra all'apertura.
- Se un file in «Aperti di recente» è stato spostato, Solidon lo dice e propone «Scegli un altro file».
- Un file che non si è potuto leggere non finisce più in «Aperti di recente», e il file successivo non ne annuncia più il nome durante il caricamento.
- Un file senza un modello leggibile non resta più come primo passaggio, su cui ogni file successivo falliva con «La catena si arresta».
- I progetti aperti di recente nella pagina iniziale si aprono con un clic.
- Senza selezione, il pannello di selezione offre ciò che vale per tutti i corpi: «Orienta per la stampa», «Disponi sul piano» e «Controlla sovrapposizioni».
- Dopo «Dividi il modello», tutti i pezzi stanno interamente nella vista.
- Ogni passaggio interrotto nel rapporto ha un pulsante: «Correggi l'inserimento» lo apre con il cursore nel campo interessato.
- Dopo «Dividi il modello», il rapporto dice in una frase che i pezzi sono ancora a contatto, invece che in oltre venti righe, e le righe sul corpo vecchio non hanno più pulsanti vuoti.
- Un disegno tracciato liberamente senza quota non genera più un avviso nel rapporto.
- Se nel rapporto ci sono solo note, in alto dice «Pronto per la stampa», e una nota sulla configurazione non è più preselezionata come un avviso.
- Gli avvisi del rapporto hanno un pulsante: «Mostra l'elemento» su un accoppiamento che non va, «Apri le impostazioni di stampa» su piano, supporti, ugello e brim.
- Un rapporto di errore indica le cartelle nella tua directory utente senza il tuo nome utente, anche se Solidon stesso è installato lì.
- In «Primi passi» la stampante del tuo slicer c'è appena si apre. Prima il suggerimento arrivava dopo alcuni secondi, e «Fatto» prendeva fino ad allora la stampante generica.
- Dopo l'importazione la barra del titolo porta il nome del modello invece di «Senza titolo», e «Primi passi» chiama gli slicer per nome invece che col nome del file.
- Lo slicer si sceglie nelle impostazioni di stampa sopra i profili, anche quando quella sezione è chiusa.
- La stampante scelta nelle impostazioni di stampa vale anche per il prossimo progetto nuovo. Se il tuo slicer è impostato su un'altra stampante, le impostazioni te la propongono con un clic.
- Se scegli un'altra stampante o un altro slicer, il profilo macchina memorizzato del precedente non vale più.
- Nella barra dei parametri e nella finestra di un'operazione, un numero digitato fuori dai limiti viene rifiutato invece di essere troncato in silenzio, e Solidon indica il limite.
- La domanda prima di eliminare un passaggio nomina i passaggi dipendenti che vengono eliminati insieme.
- La cronologia indica un parametro modificato con la sua etichetta e mostra il valore prima e dopo.
- La maniglia di una faccia selezionata mostra solo la freccia con cui la sposti.
- Senza testo, «Applica testo» dice che manca il testo invece di dichiarare l'anteprima non disponibile.
- Dopo il disegno torna a destra la scheda di prima, per esempio il rapporto. Finora c'era la chat, e «Passa allo slicer …» restava nascosto.
- La «Palette dei comandi …» trova le operazioni in ogni lingua anche con parole di tutti i giorni, come «copy» o «calamita». Finora conosceva queste parole solo in tedesco.
- Quando salvi con «Salva la selezione come blocco …», Solidon controlla lo spessore delle pareti del blocco molte volte più in fretta.
- In tutte le traduzioni «Taglia» e «Dividi» hanno ora nomi diversi, i tasti quelli della tastiera, e l'interfaccia italiana dà del tu ovunque.

### Assistente con modello locale

- La scelta del modello consiglia anche un modello più piccolo per schede da 10 GB di memoria grafica e indica per ciascuno la memoria che occupa e quanto bene gestisce richieste in più parti.
- L'assistente riceve in dettaglio solo le azioni adatte alla richiesta. Resta così spazio per cronologia e risposta, e le richieste riescono molto più spesso.
- Il modello locale resta caricato tre minuti dopo una risposta, e la domanda successiva non aspetta più il suo avvio.
- Una risposta che non trova una fine si interrompe dopo una lunghezza fissa e viene segnalata come troncata, invece di occupare la scheda grafica fino al limite di dieci minuti.

## 0.5.0

### Riconoscimento

- Il riconoscimento sui modelli importati è molte volte più veloce: una piastra da 200 000 triangoli con i suoi fori è pronta in un secondo, dove una forma libera liscia richiedeva minuti.
- Le facce piccole come la punta di una camma, i fori tagliati e gli smussi d'imbocco sono riconosciuti allo stesso modo su una mesh e su un corpo esatto.
- Le cavità chiuse e le camere d'aria annidate sono riconosciute come un tutto. Un foro che sbocca in una cavità non compare più come fantasma.
- Le filettature importate vengono misurate: passo, numero di principi, verso destro o sinistro e diametro nominale. Le parti specchiate mantengono il verso corretto.
- Coni, sfere e anelli mantengono le loro misure reali, e il pannello delle caratteristiche dice da dove viene un valore: misurato, adattato o dal passaggio.
- Una parte specchiata, scalata o ripetuta porta con sé le sue caratteristiche. Le caratteristiche superate non restano più accanto a quelle nuove.
- I file STEP con superfici di forma libera mantengono i fori modificabili, anche dopo salvataggio, riapertura e annullamento.
- Dopo una modifica, ogni caratteristica che esiste ancora mantiene il suo nome. Se entrano in gioco due candidate, Solidon chiede invece di indovinare.
- Un clic su un foro di un modello con 360 000 triangoli risponde in un quarto del tempo.
- Una svasatura che tocca due asole in modo uguale resta una faccia conica invece di sparire in una delle due.
- Se un modello è fatto di più gusci e non si può leggere con certezza se uno di essi intrappola aria, il rapporto lo dice come avviso.
- Un modello chiuso libera la sua memoria; prima restavano occupati alcune centinaia di megabyte per modello.
- Un modello con molte facce piccole, come un motivo a nido d'ape, conserva i suoi fori e raccordi. Prima non mostrava nemmeno una caratteristica.
- Un campo di 1400 bottoni viene riconosciuto in quattro secondi invece che in dodici.

### Motivi

- Un nido d'ape, una zigrinatura, nervature, onde o bugne compaiono nell'albero come un motivo con passo, larghezza di cella e profondità, anche intorno a un'impugnatura. Prima erano centinaia di facce.
- Un motivo si rimuove con un clic o si rimette con nuovo passo, larghezza di cella e profondità. Le celle restano dov'erano.
- Una texture intorno a un cilindro segue la curvatura: le scanalature sono ugualmente profonde, e un motivo lungo tutta la circonferenza si chiude senza giunzione. Il passo va al valore che torna.

### Disegno

- Disegnare su una parte scelta mostra solo quella parte nella vista; le altre restano nascoste finché «Mostra vicine» non le fa tornare.
- Estrudere su una faccia scelta ora unisce il nuovo corpo invece di fermarsi — prima non andava mai oltre lo schizzo.
- Una tasca taglia dove l'avete disegnata, anche quando la faccia non è centrata sulla parte.
- Raccordare e smussare un rettangolo quotato lascia le sue quote invariate.
- Se disegnate con più parti scelte, Solidon chiede su quale; la destinazione si cambia in qualsiasi momento nella barra.
- Esc non butta più via uno schizzo già iniziato.
- Uno schizzo già estruso si può riutilizzare per la tasca successiva, senza ridisegnarlo.
- Un clic su una faccia offre direttamente «Disegna qui» e «Disegna foro o incavo».

### Modificare sul modello esatto

- I corpi base nascono sempre con facce e spigoli reali. La casella «Modificare facce e spigoli più tardi» è sparita; i progetti vecchi si calcolano senza cambiamenti.
- Foro, asola, lamatura, perno, cupola e tronco di cono restano esatti su un corpo esatto quando li spostate, duplicate, ruotate o rimuovete.
- Cordoni e gole si possono spostare, duplicare, ruotare, modificare e rimuovere. Una filettatura si può modificare e chiudere.
- Una filettatura riceve la sua controparte sull'altra parte con un solo tasto, nella misura di tabella e come un unico accoppiamento.
- Tutti i blocchi della libreria si costruiscono esattamente su un corpo esatto, dall'avvitamento alla scanalatura di tenuta.
- Dopo un cambio di raggio, Solidon raccorda lo spigolo giusto, anche quando due raccordi sono vicini.
- Se due spigoli si trovano nello stesso punto, Solidon chiede quale intendete invece di prenderne uno.
- Applica attende finché l'anteprima mostra il risultato attuale. Un clic su un'immagine superata non scrive nulla di sbagliato.
- I colori del filamento restano sui corpi esatti e seguono ogni nuova mesh.
- Volume e area di un corpo esatto arrivano in millisecondi invece che in secondi.
- Inserire una filettatura ha richiesto da 0,38 a 0,41 secondi durante la misurazione, rispetto a 8–13 secondi. L'operazione completa ha creato una barra filettata M6 × 1 lunga 12 mm in 0,55 secondi.
- Unisci, Sottrai e Posa sul piatto non chiedono più se convertire i corpi esatti. Restano esatti.
- Quando un foro viene spostato, nel vecchio punto non restano triangoli in più, e una svasatura nascosta non perde nulla del suo volume.
- Ripara lascia invariato un modello pulito, anche sul corpo esatto.
- La controparte di una filettatura nasce in secondo piano. Nel frattempo la finestra resta utilizzabile.

### Forare e quote nella vista

- Un foro cliccato mostra subito le sue quote nella vista: distanze dagli spigoli, centro e diametro, con campi numerici per digitare.
- I campi delle quote stanno accanto alla parte invece che sopra, e le loro linee non si incrociano.
- Il riferimento di una quota, spigolo, centro o asse, si cambia con clic destro sulla quota o con un clic nel modello.
- Ciò che sta nella vista non è ripetuto a destra nel pannello di selezione.
- Dopo aver tirato un foro in asola, le quote restano, anche se ruotate la vista. I pulsanti per tirare stanno sempre sul foro scelto.
- Scegliendo un foro, la vista 3D poteva cadere su alcune schede grafiche. È risolto.
- Un trascinamento sulla maniglia sopravvive a un ridisegno a metà trascinamento, e uno scatto della rotella sopra un campo di quota ingrandisce la vista invece di cambiare la quota.
- Il primo Esc durante la scelta di un riferimento ritira solo la scelta; i valori digitati restano.
- Con «Porta con sé svasatura e gradini» il foro si sposta anche tramite le quote. Gambo e svasatura si muovono insieme, in un solo passaggio.
- Se Solidon rifiuta una quota, il motivo compare sopra l’anteprima invece del solo «non è stato possibile calcolare».
- I campi quota restano dove erano quando cambiate un valore. La quota nel cui campo scrivete si illumina nella vista.
- Le manopole per l’asola funzionano anche mentre le quote del foro stanno nella vista: Applica trasforma allora il foro in asola — con un nuovo diametro accanto in un solo passo, nella nuova larghezza.

### Cronologia

- Nella cronologia si può ora inserire un nuovo passaggio prima di uno esistente, non solo aggiungerlo in fondo.
- Un passaggio della cronologia si trascina con il mouse in un altro punto, oppure si sposta riga per riga.
- Un passaggio si può disattivare e riattivare più tardi senza eliminarlo; i passaggi dipendenti restano in sospeso con lui.
- Se un passaggio successivo fa riferimento a una caratteristica che la riorganizzazione ha rinominato, Solidon la segue e lo segnala.
- Se riorganizzare la cronologia fermasse un passaggio successivo, Solidon rifiuta e non cambia nulla.

### Verificare e stampare

- Le stampanti a resina sono arrivate: due apparecchi generici per volume di stampa stanno nell'elenco, e una propria si crea con dimensione del pixel e parete minima.
- Un progetto a resina non riceve più consigli su ugello, brim o ponti, e la parete minima viene dal profilo della stampante.
- Il file si apre in qualsiasi programma, anche nello slicer di un produttore di resina di cui Solidon non conosce le impostazioni.
- I corpi esatti vengono maglati tanto fini quanto i pixel di una stampante a resina richiedono; il rapporto indica la misura.
- Gli accoppiamenti verificano i corpi reali nella loro posizione di montaggio. L'esportazione si può annullare prima.
- Lo scostamento di forma mostra quali facce di una mesh si trovano a quale distanza dall'originale.
- Se uno spessore di parete si assottiglia a cuneo, Solidon lo dice e consiglia di stampare prima la parete esterna.
- La ricerca dell'orientamento appoggia una griglia dal bordo stretto sul suo bordo, e una griglia di traversi corti non ha bisogno di supporti.
- La scheda per l'assistente dice del punto scelto la stessa cosa del pannello delle caratteristiche.
- Lo scostamento di forma di una scatola con coperchio si calcola in un decimo di secondo invece che in dodici.
- Le parti separate per la stampa non ricevono più un avviso sulla posizione di montaggio. L'accoppiamento segnala solo ciò che ha misurato.
- La ricerca dell'orientamento su un modello con oltre un milione di triangoli richiede cinque secondi invece di mezzo minuto.
- Le distanze molto piccole compaiono nella mappa di analisi come decimali, non come potenze di dieci.
- Lo scostamento di forma su raccordi e anelli è preciso come su piani e cilindri, e la mappa si calcola più rapidamente di prima.
- La ventola del pezzo segue di nuovo la curva del profilo della stampante, invece di girare a piena velocità a ogni strato.

### Importare

- Un assieme importato si può appoggiare sul piano come un tutto con un clic. Le parti mantengono la loro posizione reciproca.
- Un glTF senza una dimensione plausibile non viene più creduto in metri. Solidon chiede l'unità e mostra le misure per ogni lettura.
- Un modello con zone aperte viene chiuso durante la lettura invece di essere solo segnalato: buchi, facce invertite, spigoli con tre facce. Le aperture grandi sono indicate a parte nel rapporto.
- Un pezzo cavo importato si può riempire con un reticolo: Solidon determina il vano interno attraverso lo sfiato e dice di averlo determinato così.
- Ridurre i triangoli non lacera più i modelli chiusi. Dove la forma non consente altro, il rapporto indica in quante parti il modello si è diviso.
- Ridurre i triangoli raggiunge ora il suo obiettivo anche su boccole, anelli e scatole con aperture.
- Un assieme STEP importato arriva come corpi separati, ciascuno con il proprio nome e i propri colori di faccia, invece di un tutto fuso insieme.
- Prima di acquisire un assieme STEP, scegliete quali corpi vi servono; una parte specchiata resta uno specchio.
- L'esportazione STEP scrive nomi e colori di faccia nel file; una parte riletta conserva il suo nome invariato.

### Uso e sistema

- Ogni azione conferma brevemente il suo risultato dove avete cliccato, oltre che nella riga di stato.
- Un errore del programma lascia un registro locale, allegato alla segnalazione al supporto. Nulla viene inviato da solo.
- La configurazione di «Modello dal testo» scarica da sola il modello d'immagine mancante invece di rimandarvi a una cartella.
- Solidon si avvia nella metà del tempo.
- Con una caratteristica selezionata il suggerimento resta, e un'indicazione sulla maniglia non cancella più l'ultima conferma.
- Se un passaggio dell'assistente ferma la valutazione, la proposta lo ritira del tutto e mostra lo stato precedente.
- Spostare o ruotare un modello da 200 000 triangoli risponde in mezzo secondo invece che in otto.
- Annulla risponde subito invece che dopo due secondi e mezzo.
- Modificando il diametro del foro nella piastra forata, durante la misurazione la prima anteprima è comparsa dopo 0,57 secondi e ogni successiva dopo 0,13 secondi.
- Lo svuotamento è stato dal 7 al 25 per cento più rapido sui tre modelli misurati.
- Una voce di menu e un avviso discreto nella vista portano al sostegno volontario di Solidon tramite PayPal o GoFundMe.
- La scheda del sondaggio mostra ora i colori giusti anche nel tema chiaro.

- L’applicazione Windows e il programma di installazione sono firmati digitalmente. La firma conferma l’identità dell’autore e permette di rilevare modifiche successive.

## 0.4.4

### Modificare

- Lo sformo raggiunge ora tutte le facce verticali, anche quelle strette, e funziona sui modelli importati.
- La fusione morbida lascia facce laterali lisce invece di bordi sfilacciati.

### Selezionare e usare

- Una bobina nel magazzino filamenti può avere fino a quattro colori. Bambu Studio, OrcaSlicer ed ElegooSlicer ricevono tutti i colori, gli altri slicer il primo.
- Uno spigolo selezionato mostra solo le azioni che agiscono su uno spigolo.
- Senza selezione resta visibile la via verso i blocchi.
- Il campo di ricerca compare solo dove ci sia qualcosa da trovare.
- Un divisorio dell’organizer porta al suo editor degli scomparti invece che alle azioni della sua faccia.
- La finestra per collocare un foro dice che il punto si sceglie nella vista.
- Nella finestra «Genera modello» il campo della descrizione mantiene la sua altezza anche quando compare l’avviso sul programma aggiuntivo mancante.

### Spostare e verificare

- I suggerimenti di stampa arrivano molto più in fretta: una figura da 2,3 milioni di triangoli in secondi invece di minuti, e una seconda apertura della finestra di stampa non misura di nuovo.
- Una bobina importata di un altro tipo di materiale che nessun pezzo usava chiudeva lo slicer senza una parola. Ora ogni bobina di un piano riceve un profilo completo.
- Se lo slicer non ha un profilo del produttore per il tuo tipo di materiale, la finestra di stampa lo dice e usa i valori di Solidon, non un profilo di un altro materiale.
- Due corpi si possono spingere uno dentro l’altro per unirli o fonderli dolcemente. Viene riportato indietro solo ciò che finisce fuori dal piano.
- Se un accoppiamento rimanda a una caratteristica che non esiste più, un pulsante porta alla cronologia.
- Orienta per la stampa e Disponi sul piano mettono i pezzi di filamenti diversi su piani propri, così un ugello non spurga di continuo. Più ugelli si indicano nella finestra di stampa.

### Magazzino filamenti

- Un annullamento nella cronologia dei movimenti si può ripristinare, con lo stesso pulsante.
- Cambiare solo nome o posizione di una bobina non conta più come nuovo conteggio; le sue registrazioni restano annullabili.
- Dopo un annullamento, «Registra senza chiedere» registra davvero una nuova stampa invece di dire solo «registrato».
- Le date di acquisto e apertura hanno un calendario nella tua lingua. Una bobina rifiutata torna nella finestra invece di sparire.
- L’importazione dallo slicer crea una bobina nuova se il nome è uguale e il colore diverso, invece di ricolorare la tua.
- Se il file del magazzino non si legge, un pulsante recupera l’ultimo stato: Solidon lo salva da solo a ogni scrittura.
- La pagina di dettaglio mostra resto, data di acquisto e prezzo; il codice a otto caratteri compare solo se due bobine hanno lo stesso nome.

## 0.4.3

### Riconoscimento e modifica

- Fori ciechi poco profondi, piccole superfici funzionali e filettature corte vengono riconosciuti meglio. I fondi delle sedi per magneti appartengono ai rispettivi fori.
- Modifichi i fori insieme a svasature e imbocchi mantenendo le misure previste. Il fondo resta associato anche dopo variazioni importanti del diametro.
- Riconosca gli elementi in un punto scelto di una mesh grande e li modifichi subito. Riconoscimento e modifica si annullano insieme.
- Selezione e anteprima mostrano il corpo completo. Contorni ed etichette identificano la zona scelta; le scritte invariate restano prive di macchie arancioni.
- Gli spigoli si possono selezionare su qualsiasi corpo e raccordare o smussare, anche sui modelli importati.
- Fori, cilindri e raccordi nascono dagli stessi punti su Windows, macOS e Linux. Un progetto viene riconosciuto e modificato allo stesso modo su ogni computer.

### Costruzione

- Gli organizer offrono misure collegate, divisori modificabili singolarmente e celle ripetute. Vaschetta, bordo, fondo e piedino ampliano la libreria.
- I campi di fori, asole ed esagoni seguono una regione disegnata. Rispettano le zone riservate, i margini e i ponti minimi.
- I morsetti per profili comprendono due gusci e due inserti su misura. Sono ammessi profili rotondi, ovali e disegnati; gli inserti possono essere sostituiti in seguito.
- Un disegno chiuso o un’apertura scelta crea una scanalatura e una guarnizione separata. Materiali, sezione e sporgenza sono regolabili; le pareti residue vengono verificate.
- I motivi superficiali raggiungono il bordo delle facce e lasciano liberi i fori. I motivi esistenti si modificano direttamente dal pannello di selezione.
- Tagliare via conserva un lato di un piano e chiude la faccia di taglio: per pareti posteriori lisce e pareti alla stessa altezza. I raccordi accanto a pareti un po’ inclinate tornano modificabili.

### Importazione e uso

- Scelga visivamente i contorni SVG e DXF prima di creare il corpo. I file GLB e GLTF conservano dimensioni e orientamento corretti.
- Le misure del progetto restano attive negli schizzi dei componenti e nelle anteprime di posizionamento. L’inquadratura comprende tutti i piatti di stampa visibili.
- I filamenti possono essere rimossi dallo scaffale. I primi passi iniziano dallo slicer; i commenti si aprono rapidamente e preparano gli allegati in background.
- Canc su una faccia rimuove il corpo e lo dice; Ctrl+Z lo riporta. In vista radente un corpo trascinato segue il puntatore, e la faccia scelta resta al primo clic dello schizzo.
- La chat locale riceve una finestra più grande e non accorcia più la richiesta.
- Il diametro dell'ugello si imposta sulla stampante. Il trasferimento sceglie poi la macchina giusta nello slicer, anche se lì è selezionato un altro ugello.
- La riparazione chiude i modelli che si toccano lungo uno spigolo invece di aprirli ulteriormente.

## 0.4.2

### Disegno

- Due clic creano un poligono regolare: prima il centro, poi un angolo. Il numero di angoli si imposta prima: da tre a dodici. Un diametro digitato resta come quota.
- Un'asola nasce da due clic sui centri delle sue estremità arrotondate; la larghezza sta accanto nella barra. Le due estremità restano uguali e i fianchi diritti.
- Quattro nuovi vincoli: angolo in gradi fra due linee, stessa lunghezza o dimensione, punto a metà di una linea, concentrico per due cerchi o archi.
- Un punto trascinato resta sotto il puntatore e i vicini lo seguono: un angolo del rettangolo porta con sé i due lati, una linea allunga la forma. Prima l'angolo arrivava solo a metà strada.
- Un rettangolo fatto con i clic è libero: nessun punto fisso, nessuna quota finché non la digiti. Una larghezza o altezza digitata resta come quota, come in Fusion.
- Le forme del menu si possono spostare; le quote della voce di menu restano. Per cambiare una quota nella vista, fai doppio clic sulla sua scheda.
- Raccordo e smusso nell'editor di schizzi: indica un angolo, digita il raggio o la quota, fai clic. Il raccordo resta al suo angolo quando trascini, lo smusso crea uno spigolo inclinato.
- Se un vincolo trattiene un punto, la riga dice quale — e che un clic destro sul punto lo rimuove. Prima il punto restava fermo senza spiegazione.
- Fisso vuol dire fisso: un punto fissato non segue più il trascinamento. Le linee esattamente orizzontali o verticali restano tali, anche se dopo trascini un angolo.

### Costruire e modificare

- Ruotare un’asola la ruota, invece di tagliarne una seconda di traverso. E modificare un’asola che avete tirato voi stessi cambia quel passo; la cronologia non ne riceve un secondo.
- Un STL esportato dopo «Modifica foro», «Sposta elemento» o «Applica uno smusso» su un modello importato arriva chiuso nello slicer. Prima la giunzione si apriva quando lo slicer la saldava.
- Se nella chat indichi un solo asse — « foro a x = 20 » —, il foro si sposta solo lì. Prima negli altri due assi saltava a zero.
- Raccordo avvisa prima che un corpo esatto ammette un raggio minore di una mesh, e cosa aiuta allora: un raggio minore oppure proseguire sulla mesh.
- Aprire due volte lo stesso file dà due nomi distinguibili: « supporto » e « supporto 2 ». Prima i due corpi si chiamavano uguali, nell'albero e nel rapporto.
- I messaggi che rimandano ai valori a destra chiamano la finestra come si chiama: Selezione. Prima dicevano « pannello delle caratteristiche ».
- Il passo « Ridurre i triangoli » lo dice quando un pezzo ha già meno triangoli del numero indicato: allora non c'è nulla da ridurre. Prima restava com'era, senza una parola.
- Il passo « Dai una posa » senza scheletro segnala che le ossa nascono nell'editor dello scheletro: due clic per osso. Prima il passo non muoveva nulla, in silenzio.
- Un foro che sposta, ruota, duplica o modifica lo segnala se così sporge oltre il bordo del pezzo — come nella foratura. Prima si vedeva solo il risultato nell’immagine.
- Spostare e duplicare un foro con svasatura lasciano invariato il volume del pezzo. Prima mancava poi fino a un millimetro cubo.
- Se un passaggio spezza un pezzo in parti staccate, il rapporto lo dice — con la via del ritorno tramite Ctrl+Z.

### Riconoscimento

- Una parete curva — l’estremità di una linguetta, il fondo di una scanalatura — ora si chiama così. Prima c’era «Raccordo» con uno spigolo che non esiste. Il raggio si può cambiare.
- Un foro con nasi nella parete, come l’anello di una chiusura a baionetta, è un foro. Prima compariva come un’asola lunga quanto larga, e ogni azione avrebbe tolto i nasi.
- Un’asola con il bordo smussato è un’asola; lo smusso ne fa parte. Prima un telaio mostrava 126 svasature separate nell’albero.
- Una tacca o l’estremità arrotondata di una linguetta non è più un foro, e due pezzi della stessa parete rotonda compaiono come uno solo nell’albero.
- Un pezzo di cono senza un bordo proprio si chiama faccia conica. Si può esaminare, ma non modificare da solo — e ogni riga lo dice.
- La parete interna di una ruota a raggi non è un foro, e un bicchiere con un buco sul fondo non è un passaggio. Prima «Sposta» tagliava lì i raggi.
- I modelli grandi vengono riconosciuti fino a trenta volte più in fretta: un pezzo di orologeria con 500 archi richiedeva due minuti, ora quattro secondi.

### Vista e utilizzo

- Una casella in una finestra ora commuta su tutta la riga — anche cliccando sulla sua etichetta. Prima rispondeva solo il piccolo riquadro, e «Apri in alto» nello svuotamento sembrava non reagire.
- Quando un'anteprima non può mostrare nulla, la vista dice perché — per esempio «Questo piano non divide l'oggetto». Se il volume non cambia, la barra lo dice; se il calcolo dura di più, anche.
- Il passo «Dividi» inizia al centro del pezzo invece che sulla sua faccia inferiore. Il numero resta modificabile.
- Uno strumento che su questo pezzo non può fare nulla appare grigio e dice perché — «Chiudi superficie aperta» su un pezzo chiuso, «Dividi in parti» su un pezzo solo, «Reticolo» senza cavità.
- Assegnare un filamento mostra il colore già nell'anteprima; uniformare e suddividere i triangoli mostrano la nuova mesh con i suoi spigoli. La barra spaziatrice riporta il prima.
- Svuotare un pezzo con buchi nel guscio dice ora che il guscio è il problema e offre «Ripara e riprova» — invece di segnalare che nessun calcolo ha funzionato.
- Sull'elemento scelto appare in grigio ciò che lì potrebbe solo fallire — «Ruota elemento» su un foro svasato, per esempio — con il motivo. E l'anteprima dice se all'applicazione arriverà una domanda.
- Un campo che non fa nulla con la forma base scelta non appare più grigio nella finestra — appare con la forma che ne ha bisogno. Un rettangolo mostra davanti quattro campi invece di otto.
- Con lo schermo al 150 o 200 per cento, aggancio, maniglie e segni arrivano di nuovo lontano come al 100 per cento. La maniglia è a grandezza piena e un clic tremolante resta un clic.
- Su un modello grande l'anteprima arriva in meno di un secondo invece che in diversi: Solidon la calcola più grossolanamente e scrive «Anteprima grossolana». Applicare resta esatto.
- Il passo «Separare lungo una linea disegnata» parte dal centro del pezzo e non dalla sua faccia inferiore, come «Dividere». Prima l'anteprima mostrava soltanto che il piano non separa nulla.
- Il passo «Allineare a una caratteristica» ti chiede ora di scegliere la seconda caratteristica invece di spiegarti una notazione.
- L'avvio non aspetta più la scheda grafica: viene cercata mentre la finestra si costruisce. Su macchine che ci mettevano molto, il programma restava fermo per secondi.
- Ciò che non è possibile su una caratteristica compare in grigio con il motivo — la stessa frase che l’operazione avrebbe detto dopo il clic. Le frasi sono diventate più brevi.

### File ed esportazione

- Un 3MF dallo slicer ora si apre anche quando i colori non si leggono senza ambiguità: il modello arriva in un solo colore e il rapporto dice perché. Prima il file restava chiuso.
- Le facce dipinte in Bambu Studio, Orca ed Elegoo arrivano esattamente come dipinte, anche dove un colore attraversa un triangolo. Prima contava come «ambiguo».
- Un rilievo di testo dello slicer Elegoo o di Bambu Studio nel file fermava l’importazione. Ora il file si apre.
- Modificatori e blocchi supporti dello slicer non compaiono più come corpi, e un incavo («parte negativa») viene sottratto, come nello slicer.

### Blocchi e accoppiamenti

- Un blocco per fori — inserto a caldo, sede per dado, sede per cuscinetto, filettatura, vite — si posa subito nel foro scelto, invece che al centro della faccia.
- Trascinando un blocco con la maniglia nella vista si sposta l’intero blocco, anche afferrandolo a un bordo del foro a serratura. Prima si spostava solo quella caratteristica.
- Ganci e fori di un blocco compaiono a destra come numero, non più come «2,00 mm». E dopo «Modifica misure» il blocco resta selezionato, anche con altre caratteristiche.

## 0.4.1

### Costruire e modificare

- Raccordare e smussare funzionano ora anche su un modello importato: si sceglie uno spigolo nella vista e si indica raggio o larghezza. Prima servivano solo su un corpo disegnato da sé.
- Anche scostare la faccia e l'angolo di sformo funzionano su un modello importato, e lì si può pure modificare o togliere un raccordo riconosciuto.
- Scostare la faccia muove la faccia su cui si è fatto clic. Su una scala gli altri gradini restano dove sono, invece di spostarsi tutti insieme.
- Cerchio fori e griglia di fori sono forme a sé nel disegno, con le loro quote: numero, cerchio primitivo, diametro. Prima erano sei cerchi fatti a mano.
- Novità: «Aggiungi cordone», un listello tondo lungo gli spigoli scelti — all'esterno come cordone, in un angolo interno come cordone d'angolo. Un corpo esatto diventa così una mesh.
- Uno spigolo si sceglie ora nella vista: primo clic il corpo, poi lo spigolo. Lunghezza e i pulsanti Raccorda e Smusso stanno a destra. Prima bisognava riconoscerlo in un elenco.
- Su un tubo, bordo interno e bordo esterno si raccordano o si smussano separatamente. Prima si chiamavano allo stesso modo, e la modifica colpiva uno dei due.
- L'angolo di sformo lascia intatta la base d'appoggio, anche se il pezzo non sta a quota zero. Prima un pezzo sollevato veniva assottigliato anche in basso.
- Sweep lungo un percorso parte con la sezione giusta e mantiene le aperture nel contorno: un anello resta un tubo, invece di partire deformato e riempirsi all'interno.
- Una coppia di controparti inserita conta come modifica: viene salvata con il progetto e alla chiusura si chiede se salvarla. Prima poteva andare persa in silenzio.
- Il lucchetto accanto a una quota fissata nell'editor di schizzi è ora un simbolo disegnato con spiegazione. Su qualche computer compariva lì un quadratino.

### Forare e posizionare

- Quando posizioni un foro, una casella lo trasforma in asola: indichi lunghezza e direzione, e l'anteprima le mostra entrambe.
- Un foro già presente nel modello si allunga in seguito fino a diventare un'asola: il diametro resta quello misurato.
- L'asola viene allargata della tolleranza del materiale su tutta la sua lunghezza. La corsa che una vite ha al suo interno resta quella indicata.
- Se un'asola sporge dal bordo a un'estremità, Solidon lo dice, anche quando il suo centro sta in pieno materiale.
- Un'asola compare nell'albero degli oggetti come asola, con la sua larghezza e la sua lunghezza, anche in un modello che hai aperto e che ha disegnato qualcun altro.
- Un'asola esistente si allunga in seguito, e la sua direzione resta dov'era.
- Un foro o un'asola selezionati si regolano direttamente nella vista con «Imposta nella vista»: una maniglia per spostare e ruotare, pomelli per allungare, quote a bordi e centri.
- Solo «Applica», a destra, ne fa un passo; Esc annulla. Un'asola allungata mostra la sua lunghezza e mantiene la sua forma quando la spostate con la maniglia.
- Un campo di coordinata vuoto significa ora «lascia il foro dov'è». Così se ne può mettere uno al centro del pezzo, l'unico punto che prima non raggiungeva.
- Un foro si sposta con «Modifica foro» ora anche sul corpo esatto — e sulla mesh si muove davvero. Se esce oltre il bordo, Solidon dice che non è più un foro.
- La larghezza di un'asola si cambia con «Modifica foro». La corsa che una vite ha al suo interno resta.
- Se un foro o un'asola attraversa il pezzo da parte a parte, tanto che si spezza in più pezzi, il rapporto lo dice — invece di dire solo che il foro sporge oltre il bordo.

### Riconoscimento

- Una svasatura sopra un foro viene mantenuta anche su un pezzo con superfici tonde e sinuose: prima andava persa, e foro e svasatura non potevano più essere spostati insieme.
- Una cavità interamente nel materiale, senza via d'uscita, compare nell'albero degli oggetti come sacca d'aria, con il suo volume. Prima compariva come un foro inesistente.
- Su un modello molto curvo Solidon dice ora che cosa è stato misurato invece di chiamarlo una scansione, e quali forme su una superficie simile restano fuori.
- Il riconoscimento delle caratteristiche su modelli grandi di forma organica è circa un quarto più rapido. Trova le stesse cose di prima.
- Se tra un foro e la parete attorno resta meno materiale di quanto il vostro ne regga, il rapporto lo dice, misurato sul pezzo finito.
- La mappa dei difetti della mesh segna ora anche le facce che si attraversano. Prima vedeva solo spigoli aperti e ramificati e dava un modello simile per sano.
- L'analisi a strati di un pezzo finemente zigrinato richiede ora la metà del tempo; i punti segnalati restano gli stessi.
- Se un ponte conta come troppo lungo dipende ora dal vostro ugello: due linee di un ugello da 0,4 sono 0,84 mm, non un millimetro tondo. Modifiche più piccole la chat non le segnala più.
- Il riconoscimento delle filettature richiede solo una frazione della memoria e si può interrompere.
- Se un corpo non si può dividere a causa di una mesh aperta, la riparazione sta come pulsante sul rilievo.
- Se un taglio non si può richiudere, Solidon dice che il modello non è chiuso — e come proseguire — invece di indicare il taglio.

### Scrivere

- Una scritta può usare ora otto caratteri invece di tre, più grassetto e corsivo. Il grassetto porta tratti più spessi a parità di altezza e resta leggibile dove lo stile normale sbava.
- Accanto ai caratteri diritti ci sono ora uno tondo e uno manoscritto, entrambi in un solo stile. Tutti e otto viaggiano con il programma, così un progetto appare uguale ovunque.
- Se un carattere è troppo fine per il tuo ugello, Solidon dice da quale altezza tiene, invece di stamparlo e lasciare che le lettere si impastino.
- I lati curvi di una lettera — l'arco della D, il contorno della o — compaiono ora nell'albero degli oggetti come quelli dritti e accettano un filamento proprio. Prima mancavano del tutto.

### Blocchi e accoppiamenti

- Un blocco dal catalogo compare subito nella vista: sulla faccia selezionata o sopra il corpo, con quote e maniglia. Un clic lo posiziona altrove, «Applica» lo inserisce.
- Se separate in pezzi distinti un corpo con un accoppiamento, Solidon chiede a quale pezzo si riferisca ora l'accoppiamento — invece di rimandarvi ad annullare i passi.
- La boccola a inserimento M2,5 riceve il suo foro di montaggio secondo la scheda tecnica: 4,0 mm invece di 3,6. Un progetto più vecchio con questa boccola dice all'apertura che la misura è cambiata.
- L'avviso su un braccio a scatto che si rompe tiene conto della direzione di stampa sfavorevole: un braccio che flette di traverso agli strati regge meno, e ora lo dice la frase.
- Il generatore di varianti incide su ogni pezzo il suo valore sulla faccia superiore. Se un pezzo è troppo piccolo per un numero leggibile, il rapporto lo dice e indica l'ordine sul piatto.

### Vista e utilizzo

- Le azioni per un corpo o una caratteristica selezionati stanno a destra, in gruppi richiudibili, con ricerca. I menu Oggetto, Modifica e Prepara sono spariti; le scorciatoie restano.
- Il clic destro su un corpo o una faccia mostra solo ciò che esiste soltanto lì: il passo dietro, lo schizzo sulla faccia, il nascondere. Il pulsante «Blocchi» è in colore d'accento.
- Se la catena si arresta a un passo, le azioni sono bloccate e ne dicono il motivo; chi ci prova vede subito le vie d'uscita del rapporto. Prima il passo finiva in silenzio dietro, mai calcolato.
- Il selettore dei piatti nell'intestazione sta accanto al nome della stampante, non più sopra — anche quando i piatti arrivano solo con il progetto aperto.
- Il rapporto raggruppa i messaggi uguali in una riga, con il numero tra parentesi davanti. Un clic seleziona tutte le parti interessate; un'azione chiede a quali applicarsi.
- La colonna destra con rapporto, chat e tour è un po' più stretta; lo spazio va al modello.
- Durante la misura la vista passa alla proiezione diritta e poi torna indietro. In prospettiva si mira accanto, tanto più quanto il tratto è lontano dal centro.
- Chi guarda soltanto un modello non riceve più la domanda sul salvataggio alla chiusura. In compenso i file importati stanno ora sotto «Aperti di recente».
- Se si spinge un corpo oltre il bordo del piano con la maniglia, Solidon lo riporta in un posto libero. Un valore digitato viene eseguito così come è stato immesso.
- La scelta della lingua nelle impostazioni ha effetto subito; le altre immissioni restano, Annulla ripristina la lingua. Vale anche nella prima configurazione, che un cambio non chiude più.
- Dopo un quarto d'ora di lavoro Solidon chiede una volta per versione un riscontro. Si risponde o si chiude: in questa versione la domanda non torna.
- Se il mouse 3D è bloccato, Solidon indica la via per abilitarlo invece di passarci sopra in silenzio.
- La via verso la stampante nel menu si chiama «Preparare la stampa …» invece di «Impostazioni di stampa …». La finestra dietro è la stessa.
- Il tasto Invio in un campo di misura a destra applica il passo, e il tasto Tab percorre i campi dall'alto in basso.
- La palette dei comandi preseleziona la corrispondenza migliore, non la prima eseguibile. «Racc» e Invio prima creavano un parallelepipedo.
- Se trascinate un corpo con il mouse, resta al puntatore anche sopra lo sfondo vuoto, invece di fermarsi e saltare non appena sotto torna a esserci qualcosa.
- Anche dopo l'apertura di un progetto il primo clic nel modello non scatta più; la preparazione avviene appena i corpi sono al loro posto.
- I movimenti fini della rotella — touchpad, mouse ad alta risoluzione — ora fanno zoom invece di andare persi.
- Il volo con il tasto Ctrl premuto si ferma appena rilasciate il tasto. Prima la vista continuava a volare.
- Con una scala dello schermo elevata centrate le maniglie con la stessa facilità che al 100 %.
- Dopo un cambio di rilievo, i pulsanti del rapporto comparivano per un attimo come piccole finestre a sé. È finita.
- Il contorno di strato di un pezzo sul secondo piatto sta su quel pezzo, non accanto al primo.
- Nella schermata iniziale restano solo i menu che lì fanno qualcosa.
- Un secondo blocco dello stesso tipo — un secondo coperchio a vite, per esempio — riceve un numero invece di chiamarsi come il primo.

### File ed esportazione

- Prima di scrivere, l'esportazione mostra che cosa ha trovato il rapporto: una parete sottile, un accoppiamento violato. Decidete voi se il file nasce lo stesso.
- Solidon ricorda cartella, formato e schema dei nomi per ogni progetto. Se nascono più file, il modello del nome sta nel campo e si può cambiare.
- Durante la lettura di un modello l'avanzamento resta finché il modello c'è davvero, e l'indicazione dice «Lettura del modello» invece di «Caricamento del progetto». Annulla resta raggiungibile.
- Una domanda già risposta su quale caratteristica intenda un passo resta risposta — anche dopo aver chiuso e riaperto il progetto.
- Se il file collegato di un progetto non è raggiungibile, il progetto si salva e si apre lo stesso; il rapporto nomina l'origine. Se mancano i permessi, Solidon lo dice invece di dirlo danneggiato.

### Piano di stampa e consegna

- Se un corpo fatto di pezzi singoli — una scritta, per esempio — non entra intero in nessun piano, il rapporto propone di separarlo e orientarlo subito: un clic e i pezzi stanno sui piani.
- Apri nello slicer consegna a ElegooSlicer, Orca e Bambu Studio tutti i piani in un unico file: una finestra invece di una per piano.
- Per separazione, scritta e texture il rapporto indica il numero nella frase, dove prima c'era un segnaposto tra parentesi graffe.
- Una scritta a cui avete assegnato un filamento lo conserva quando viene separata in lettere. Prima arrivava nello slicer su un secondo filamento grigio, con quello assegnato accanto inutilizzato.
- Con più piatti, le parti arrivano ora nello slicer dove lui tiene i suoi piatti: nella griglia che dispone da sé. Prima le lettere del terzo e del quarto piatto stavano accanto a tutto.
- Se durante lo slicing resta una bobina inutilizzata, Solidon lo dice con il suo nome. Prima lo slicer segnalava successo e nella stampa mancava un filamento.
- Se uno slicer si chiude di colpo, Solidon lo dice così. Prima si leggeva che non aveva scritto alcun file di stampa.
- Creality Print viene riconosciuto come slicer ed è selezionabile nella finestra di stampa, con le sue stampanti, i processi e i filamenti.
- La finestra di stampa si apre subito con lo slicer scelto l'ultima volta; la ricerca degli altri corre in secondo piano. Prima il clic su Stampa poteva non mostrare nulla per dieci secondi.
- La scelta dello slicer mostra tutti i programmi installati — anche un secondo Flatpak o un secondo AppImage. Prima mancava il secondo di ogni posizione.
- Un filamento da un pacchetto di produttore di PrusaSlicer arriva nella consegna con i propri valori, non con quelli del primo filamento del file.
- Nella consegna come STL — a Cura, per esempio — Solidon dice che le impostazioni per pezzo non viaggiano, e nomina la proposta per l'intero piatto, invece di affermare che sono impostate.

### Filamenti e magazzino

- Il magazzino filamenti si può salvare anche su una chiavetta FAT32, un disco exFAT o una condivisione di rete. Prima lì ogni salvataggio falliva.
- Se il magazzino non si può leggere, Solidon lo dice anche nel selettore del filamento, con il pulsante «Prova di nuovo» — invece di un elenco vuoto.
- Il consumo rilevato dal file di stampa conta anche il materiale spinto senza percorso, e non conta due volte le ritrazioni. Se lo slicer scrive da sé la quantità nel file, vale ancora la sua cifra.
- Chi allo scarico del consumo sceglie «Non registrare» non viene più interpellato per quell'uscita; resta raggiungibile sotto «Non registrato».
- Se create una nuova bobina mentre scaricate il consumo, le bobine scelte, le quantità inserite e le ripartizioni restano.
- L'albero degli oggetti mostra su corpo e faccia solo i filamenti che vi stanno davvero — una faccia con filamento proprio porta il suo, non l'elenco dell'intero corpo.
- Annulla durante la ricerca dei profili di filamento agisce subito.

### Chat e IA

- Prima della prima richiesta a un generatore di modelli, Solidon dice quali dati vi arrivano.
- Se un altro processo occupa la scheda grafica, la chat aspetta in modo visibile invece di restare ferma.

### Aggiornamento, installazione e sistema

- I pacchetti per Mac sono firmati e notarizzati. Il giro per «Privacy e sicurezza» → «Apri comunque» non serve più.
- Sotto «Sostieni Solidon», accanto a PayPal si può ora scegliere GoFundMe; solo il vostro clic apre il browser, e senza browser l'indirizzo si può copiare.
- Se il vostro codice d'acquisto sta su un'unità i cui permessi sui file non si possono impostare — FAT, condivisione di rete —, resta leggibile. Prima lì risultava assente.

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
