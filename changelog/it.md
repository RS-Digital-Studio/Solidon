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
