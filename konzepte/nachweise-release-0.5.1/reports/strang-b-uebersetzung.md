# Durchsicht Strang B — Übersetzung der 27 gekürzten Erklärseiten

Gegenstand: Zweig `handbuch-texte`, Endstand `a4f6a104c`, Arbeitsbaum
`F:\3D Druck.handbuch-texte` (nur gelesen, `git status` danach leer). Geprüft
wurden die Seiten what, window, looking, features, moving, sketch, ways,
sculpting, history, parameters, tolerances, parts, own-parts, exchange, print,
resin, export, splitting, variants, chat, generating, extras, surfaces, labels,
remote, activation und trouble in en, es, fr, it und pt, jeweils gegen die neue
deutsche Quelle (`laeufe/strang-b-de.txt`, byte-gleich mit dem frischen Druck).

## Vorgehen

Die Seiten aller sechs Sprachen wurden mit `skripte/seiten.py` gedruckt und
absatzweise nebeneinandergelegt; jede Seite hat in jeder Sprache genau so viele
Absätze wie das Deutsche. Jeder Absatz wurde in allen fünf Sprachen gegen den
deutschen gelesen. Maschinell dazu: Bildverweise, Seitenverweise, Code und Zahlen
je Absatz verglichen (alle gleich, abweichend nur übersetzte Tastennamen);
Satzzahl und Länge je Absatz verglichen (kein Rest einer längeren alten Fassung,
alle Abweichungen erklären sich aus Satzzeichen); 1390 hervorgehobene Namen
automatisch gegen den Katalog gehalten, dazu rund 80 Namen und zitierte
Oberflächentexte von Hand nachgeschlagen, auch solche, die im Deutschen nicht
kursiv stehen; Italienisch auf voi- und Lei-Formen durchsucht; Typografie je
Sprache gezählt.

Was unauffällig blieb: Die Treue ist durchweg hoch, nichts fehlt in größerem
Umfang, nichts ist dazugekommen, kein Satz der alten Fassung ist stehen
geblieben. Das Italienische ist auf allen 27 Seiten frei von voi- und Lei-Formen,
auch in Titeln und Kurzfassungen. Französisch folgt dem Bestand (gewöhnliches
Leerzeichen vor : ; ? !, 789 zu 0 im Katalog; « … » mit Leerzeichen innen),
Spanisch setzt jedes ¿, die Anführungszeichen stimmen je Sprache (en “…”, sonst
«…»). Glossarbegriffe und Genus der Bausteinnamen stimmen, wo ich sie
nachgeschlagen habe. Anrede: fr „vous“, es und pt die Höflichkeitsform wie im
Bestand, it „tu“.

## Befunde

Je Befund: Sprache · Seite · Katalogschlüssel (Anfang des deutschen
Seitentextes, bei Titel oder Kurzfassung deren Wortlaut) · Zitat · was falsch
ist · verbesserter Wortlaut.

### Stufe 1 — sachlich falsch oder fehlend

**1. en · parts · „Einen Sechskant so tief in eine Wand zu legen …“**
Absatz „Dazu kommen Schraubenloch, …“: „tongue and groove“. Gemeint ist der
Baustein *Nutfeder für Aluprofil* (Katalog en „T-slot tongue for extrusion“),
ein Nutenstein für Aluprofile; „tongue and groove“ ist eine Holzverbindung aus
Feder und Nut, also etwas anderes.
Besser: „… keyhole, insert ball bearing, screw, printed nut, printed thread,
T-slot tongue, wall mount, …“

**2. es · parts · „Einen Sechskant so tief in eine Wand zu legen …“**
Gleicher Absatz: „la lengüeta y ranura“ — dieselbe Verwechslung (Nut und Feder
statt Nutenstein). Der Katalog sagt „Lengüeta para perfil de aluminio“. Im selben
Satz weicht „el conector de encaje para una junta“ vom Katalog ab („Conector a
presión para una junta“).
Besser: „… la lengüeta para perfil de aluminio, el soporte de pared, la unión de
encaje, el pasador y su taladro, el conector a presión para una junta …“

**3. it · surfaces · „Ein Rändel für den Griff, eine Wabe fürs Aussehen …“**
Letzter Absatz: „In un corpo svuotato da sé lo è.“ „Da sé“ bezieht sich auf den
Körper und heißt „der sich selbst ausgehöhlt hat“; gemeint ist der vom Nutzer
ausgehöhlte Körper.
Besser: „In un corpo che hai svuotato tu lo è.“

**4. it · extras · „**Keines davon ist Pflicht.** …“**
„Importare, modificare, verificare ed esportare funzionano senza tutti e tre.“
„Senza tutti e tre“ liest sich als „nicht mit allen dreien zusammen“, gemeint ist
„ohne jedes der drei“.
Besser: „… funzionano senza nessuno dei tre.“

**5. en · print · „*Datei → Drucken vorbereiten* (Strg+P) …“**
Absatz „Scheitert ein Lauf“: „offers what helps: another slicer, the slicer's
output, checking the machine profile or just exporting.“ Das Verb zu „die Ausgabe
des Slicers ansehen“ fehlt; die Aufzählung angebotener Handlungen kippt in eine
Aufzählung von Dingen.
Besser: „… offers what helps: another slicer, viewing the slicer's output,
checking the machine profile or just exporting.“

**6. fr · activation · „**Diese Version ist eine vollständige, befristete Demo.** …“**
Absatz „Ohne Internet in drei Schritten“: „valider le fichier sur un appareil
connecté à `solidon3d.de/offline-aktivierung.html`“. Das sagt „auf einem Gerät,
das mit dieser Adresse verbunden ist“; gemeint ist ein Gerät mit Internet, auf dem
die Datei unter dieser Adresse eingelöst wird.
Besser: „… valider le fichier à l'adresse `solidon3d.de/offline-aktivierung.html`
sur un appareil connecté à internet, …“

### Stufe 2 — falscher Name

**7. es · history · „Jede Operation steht im Verlauf und bleibt dort änderbar …“**
„**Borrar** está en el menú contextual de la lista y en la barra de debajo“.
Kontextmenü und Leiste zeigen „Eliminar paso …“ (Katalog „Schritt löschen …“;
auch „Löschen“ heißt „Eliminar“). Der Kunde sucht „Borrar“ und findet es nicht.
Besser: „**Eliminar** está en el menú contextual …“ und im selben Absatz „un
paso eliminado“ statt „un paso borrado“.

**8. pt · history · „Jede Operation steht im Verlauf und bleibt dort änderbar …“**
„**Apagar** está no menu de contexto da lista“ — die Oberfläche zeigt „Eliminar
passo …“.
Besser: „**Eliminar** está no menu de contexto …“, dazu „um passo eliminado“
statt „um passo apagado“.

**9. en · tolerances · „Das Stück, das Solidon von einem Slicer unterscheidet …“**
„**The test cut** cuts a cube around one spot …“. Die Operation heißt „Create
test piece“, das erzeugte Objekt „Test piece“.
Besser: „**The test piece** cuts a cube around one spot out of the part …“

**10. es · tolerances · „Das Stück, das Solidon von einem Slicer unterscheidet …“**
„**La probeta** recorta …“. Die Operation heißt „Crear bloque de prueba“, das
erzeugte Objekt „Pieza de prueba“; „probeta“ steht nirgends in der Oberfläche.
Besser: „**La pieza de prueba** recorta de la pieza un cubo …“ (zum Wort „bloque“
in der Operation siehe Nebenbefund d).

**11. it · tolerances · „Das Stück, das Solidon von einem Slicer unterscheidet …“**
„**Il campione** ritaglia dal pezzo un cubo …“ — Operation „Crea pezzo di prova“,
Objekt „Pezzo di prova“.
Besser: „**Il pezzo di prova** ritaglia dal pezzo un cubo …“

**12. pt · tolerances · „Das Stück, das Solidon von einem Slicer unterscheidet …“**
„**O provete** recorta da peça um cubo …“ — Objekt „Peça de ensaio“, Operation
„Criar bloco de ensaio“.
Besser: „**A peça de ensaio** recorta da peça um cubo …“

**13. en · parts · „Einen Sechskant so tief in eine Wand zu legen …“**
Absatz „Kabelclip“: „that is what the grommet is for“, Absatz „Dazu kommen …“:
„cable grommet“. Der Baustein heißt im Katalog „Cable gland with strain relief“.
Besser: „that is what the cable gland is for“ und „… magnet pocket, cable gland,
rib, …“

**14. it · activation · „**Diese Version ist eine vollständige, befristete Demo.** …“**
„**Cambiando computer, prima: disattivare questo computer.**“ Das Deutsche nennt
hier den Knopf *Diesen Rechner deaktivieren*; der heißt italienisch „Disattiva
questo computer“ (en, es, fr, pt treffen ihren Katalogtext).
Besser: „**Se cambi computer, prima: Disattiva questo computer.**“

**15. en · extras · „**Keines davon ist Pflicht.** …“**
Liste unter „Ollama“: „3. **Check the tools.**“ Das Deutsche schreibt den
Knopftext „Werkzeuge prüfen“ (`dialogs.py`), en „Check tools“.
Besser: „3. **Check tools.**“

**16. it · extras · „**Keines davon ist Pflicht.** …“**
Gleiche Liste: „3. **Verificare gli strumenti.**“ — der Knopf heißt „Verifica gli
strumenti“.
Besser: „3. **Verifica gli strumenti.**“, und passend dazu „2. **Recupera un
modello.**“ statt „Recuperare un modello.“ (siehe Befund 17).

### Stufe 3 — Ton

**17. it · parts, sketch, variants, activation, extras — Infinitiv statt „tu“ im Imperativ**
Die Regel verlangt bei Bedienhandlungen den Imperativ der 2. Person, und dieselben
Seiten halten sich meist daran („Apri *Crea → Forme di base → Crea organizer*,
inserisci le misure e scegli …“). Fünf Anleitungssätze stehen aber im Infinitiv,
das liest sich wie zwei Hände:
- parts, „Einen Sechskant so tief …“: „Un blocco lo fa per te: fare clic sulla
  faccia, scegliere il blocco, scegliere la misura.“ → „Un blocco lo fa per te: fai
  clic sulla faccia, scegli il blocco, scegli la misura.“
- parts, Absatz Gegenstücke: „segnare il punto su ciascuno dei due pezzi,
  scegliere la coppia, inserire le misure una volta“ → „segna il punto su ciascuno
  dei due pezzi, scegli la coppia, inserisci le misure una volta“
- sketch, „Für den Umriss …“, Absatz Bemaßen: „digitare lunghezza o diametro,
  Invio“ → „digita lunghezza o diametro e premi Invio“
- variants, „Die Zahl, die über eine Passung entscheidet …“: „Stampare una volta,
  provare e prendere il valore che entra senza gioco.“ → „Stampalo una volta, prova
  e prendi il valore che entra senza gioco.“
- activation, Absatz „Ohne Internet“: „aprire *Attiva offline …* e salvare la
  richiesta, riscattare il file …, caricare la risposta in Solidon“ → „apri *Attiva
  offline …* e salva la richiesta, riscatta il file …, carica la risposta in
  Solidon“
- extras, Ollama-Liste: „**Recuperare un modello.**“, „**Verificare gli
  strumenti.**“ → „**Recupera un modello.**“, „**Verifica gli strumenti.**“

Das Zitat der Meldung in features („Il messaggio indica la via: selezionare la
caratteristica al centro …“) gibt den Wortlaut einer Meldung wieder und darf im
Infinitiv bleiben.

### Stufe 4 — Stil und Sprache

**18. es · window · „Wo was steht, zeigt …“** — „Hay la escena.“ ist falsch
gebildet („hay“ nimmt keinen bestimmten Artikel). Besser: „Solo existe la
escena.“

**19. es · parts · „Einen Sechskant so tief …“** — Absatz Eckwinkel: „está el
nervadura de refuerzo“. Besser: „está la nervadura de refuerzo“.

**20. es · remote · „Ein anderes Programm auf demselben Rechner …“** — „**Está
desactivado hasta que usted lo active**“ bezieht sich auf „la conexión“ aus dem
Satz davor; der Genus stimmt nicht. Besser: „**Está desactivada hasta que usted
la active**“.

**21. es · tolerances · „Das Stück, das Solidon von einem Slicer unterscheidet …“**
— „el plástico contrae“ und im letzten Absatz „contrae de otra forma“: „contraer“
braucht hier das Reflexivpronomen. Besser: „el plástico se contrae“, „se contrae
de otra forma“.

**22. es · extras · „**Keines davon ist Pflicht.** …“** — „La **versión de
escritorio** de comfy.org la encuentra Solidon solo“: „solo“ liest sich als „nur“.
Besser: „… la encuentra Solidon por sí mismo“.

**23. es · parts · „Einen Sechskant so tief …“** — Absatz Einpressbuchse: „se
puede soltar tantas veces como se quiera“; „soltar“ ist für eine Schraubverbindung
schief, fr, it und pt sagen „demontieren“. Besser: „se puede desmontar tantas
veces como se quiera“.

**24. es · chat · „Der Chat ruft dieselben Operationen auf …“** — „**Lleva tres
reglas:**“ klingt nach Übersetzung. Besser: „**Trae tres reglas de serie:**“.

**25. es · own-parts · „Der Halter für die Werkbank …“** — „Quien escribió la
anchura en el prisma“: Die Grundform heißt in der Oberfläche „Caja“. Besser: „…
en la caja …“.

**26. fr · features · „Eine STL-Datei enthält nur Dreiecke …“** — Absatz „Die
Felder stehen auf den gemessenen Werten“: „et laquelle c'est est indiqué
au-dessus“ ist holprig bis ungrammatisch. Besser: „et son nom est indiqué
au-dessus“.

**27. fr · own-parts · „Der Halter für die Werkbank …“** — „et celui qui arrive en
reçoit un propre“: „un propre“ liest sich als „einen sauberen“. Gemeint ist ein
eigener Name (vgl. exchange: „reçoit un nom dérivé“). Besser: „et celui qui
arrive reçoit son propre nom“.

**28. fr · sculpting · „Manche Formen lassen sich nicht bemaßen …“** —
„**Trois étapes** …“ und „**Au sein d'une étape** …“: „étape“ ist im Katalog und
auf derselben Seite („une seule étape de l'historique“) der Verlaufsschritt; drei
Bedeutungen fallen in ein Wort. Besser: „**Trois phases** …“, „**Au sein d'une
phase** …“, „Sans la deuxième phase …“.

**29. fr · ways · Titel „Die vier Wege“** — „Les quatre voies“, Kurzfassung und
Text sagen „quatre chemins“, „Chemin 1“. Besser: „Les quatre chemins“.

**30. fr · exchange · „Bausteine wechseln nur als Datei den Besitzer …“** —
„ni l’auteur“ mit typografischem Apostroph, sonst steht auf der Seite überall der
gerade. Besser: „ni l'auteur“.

**31. fr · own-parts · „Der Halter für die Werkbank …“** — „dans le
parallélépipède“: Die Grundform heißt in der Oberfläche „Pavé“. Besser: „dans le
pavé“.

**32. it · own-parts · „Der Halter für die Werkbank …“** — „**Poi scegli nella
cronologia che cosa viene con sé**“ ist ungrammatisch. Besser: „**Poi scegli nella
cronologia che cosa includere**“.

**33. it · sculpting · „Manche Formen lassen sich nicht bemaßen …“** — „la seconda
si salta volentieri“: Das deutsche „gern“ heißt hier „oft“, „volentieri“ heißt
„mit Vergnügen“. Besser: „la seconda si salta spesso“.

**34. it · what · „Solidon baut und ändert Modelle …“** — „Un foro spostato di due
millimetri viene spostato, non forato di nuovo.“ Zweimal „spostato“. Besser: „Un
foro fuori posto di due millimetri si sposta, non si rifora.“

**35. it · parts und own-parts · Kurzfassungen „Geprüfte Verbindungen aus der
Bibliothek statt selbst konstruierter Geometrie.“ und „Ein selbst gebautes Teil so
ablegen …“** — „geometria progettata da sé“, „un pezzo costruito da sé“: „da sé“
bezieht sich auf das Ding selbst (wie in Befund 3). Besser: „geometria progettata
da te“, „un pezzo costruito da te“.

**36. it · moving · „Zwei Wege ändern das Modell selbst …“** — „le pareti vicine
crescono con lei“: Für eine Sache schriftsprachlich „essa“. Besser: „crescono con
essa“.

**37. it · ways · Titel „Die vier Wege“** — „Le quattro vie“, Kurzfassung und Text
sagen „quattro strade“, „Strada 1“. Besser: „Le quattro strade“.

**38. pt · looking · „Ob ein Modell druckbar ist …“** — „raramente se vê à
primeira“: Es fehlt „vista“, „à primeira“ allein heißt „beim ersten Versuch“.
Besser: „raramente se vê à primeira vista“.

**39. pt · parameters · „Ein Projekt hat benannte Parameter …“** — „o Solidon
reconhece e nomeia em vez de calcular sem fim“: Das Objektpronomen fehlt. Besser:
„o Solidon reconhece-as e nomeia-as em vez de calcular sem fim“.

**40. pt · window · „Wo was steht, zeigt …“** — „Há a cena.“ ist schief. Besser:
„Existe só a cena.“

**41. en · remote · Kurzfassung „Ein anderes Programm bedient Solidon, lokal,
abschaltbar und rücknehmbar.“** — „locally, switchable and undoable“:
„switchable“ heißt „umschaltbar“. Besser: „Another program operates Solidon,
locally, with an off switch, and every step can be undone.“

**42. en · parameters, activation, extras — deutsche Satzstellung** — Drei Sätze
stellen das Objekt nach deutscher Art voran und klingen übersetzt: „**Limits, unit
and expression** you change with a right-click on the parameter“ → „**Limits, unit
and expression** are changed with a right-click on the parameter“; „Which kind a
key is, *Help → About Solidon* shows.“ → „*Help → About Solidon* shows which kind a
key is.“; „whether such a route holds up, the tool test shows.“ → „the tool test
shows whether such a route holds up.“

## Zählung

| Sprache | Stufe 1 | Stufe 2 | Stufe 3 | Stufe 4 | zusammen |
|---|---:|---:|---:|---:|---:|
| en | 2 | 3 | 0 | 2 | 7 |
| es | 1 | 2 | 0 | 8 | 11 |
| fr | 1 | 0 | 0 | 6 | 7 |
| it | 2 | 3 | 1 | 6 | 12 |
| pt | 0 | 2 | 0 | 3 | 5 |
| **alle** | **6** | **10** | **1** | **25** | **42** |

## Urteil

- **en: nein.** „tongue and groove“ nennt einen anderen Gegenstand, drei Namen
  (test piece, cable gland, Check tools) weichen von der Oberfläche ab.
- **es: nein.** Dieselbe Verwechslung bei der Nutfeder, „Borrar“ statt „Eliminar“,
  „La probeta“, dazu zwei echte Grammatikfehler („el nervadura“, „Hay la escena“)
  und ein falscher Genus in remote.
- **fr: ja.** Kein falscher Name, keine sachliche Verfälschung von Gewicht; den
  Satz zur Offline-Aktivierung (Befund 6) und die Stilpunkte würde ich beim
  nächsten Anfassen mitnehmen.
- **it: nein.** Ein Sinnfehler (surfaces), eine missverständliche Kernaussage
  (extras), zwei Knopfnamen falsch, und fünf Anleitungssätze verletzen die
  tu-Imperativ-Regel.
- **pt: nein.** Nur zwei Namen („Apagar“, „O provete“), aber beide sucht der
  Kunde vergeblich.

Keine Sprache braucht eine Neuübersetzung. Alle Befunde der Stufen 1 bis 3 sind
Einzelstellen, zusammen rund 25 Ersetzungen in den Katalogen; danach halte ich
alle fünf für freigabefähig.

## Nebenbefunde außerhalb des Strangs (nicht gezählt)

Die Handbuchseiten zitieren hier die Oberfläche richtig, das Problem sitzt im
Katalog oder in einer Abbildung.

a) **Trennen und Teilen heißen in en, es, fr und pt gleich** (Split, Separar,
Séparer, Separar; it: Dividi und Dividere). Auf `window` und `splitting` stehen
dadurch zwei verschiedene Dinge unter einem Namen: „The shortest way is the
*Split* tool … To type the plane, use *Split* on the right …“.

b) **fr: „{side} innen“ → „{side} intérieur“** ergibt in der Oberfläche „Face
supérieure intérieur“ (Genus); features zitiert es so, wie es angezeigt wird.

c) **Abbildung `sketch-editor`** (`figures.py`, Schlüssel „Bestimmt — jedes Maß
steht fest.“) zeigt es/fr/it/pt „Determinado / Déterminée / Determinato /
Determinado“, die Statuszeile und der Text derselben Seite sagen „Totalmente
definido / Entièrement défini / Completamente definito / Totalmente definido“.
Bild und Text widersprechen sich auf der Seite `sketch`.

d) **es/pt: „Prüfstück erzeugen“ → „Crear bloque de prueba“ / „Criar bloco de
ensaio“.** „Bloque/bloco“ ist laut Glossar der Baustein; das erzeugte Objekt heißt
„Pieza de prueba“ / „Peça de ensaio“. Operation und Objekt sollten ein Wort
teilen, und es sollte nicht „Baustein“ heißen.

e) **Regel gegen Bestand:** `uebersetzung.md` sagt für Französisch „gewöhnliche
Leerzeichen (keine geschützten)“, der Auftrag sprach von geschützten; der Bestand
hat gewöhnliche (789 zu 0), die Seiten folgen ihm. Die Regel „Esc bleibt“ deckt
sich im Französischen nicht mit dem Bestand (15 × „Échap“, 7 × „Esc“); die Seiten
folgen der Mehrheit.
