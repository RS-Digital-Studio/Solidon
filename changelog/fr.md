# Nouveautés

Ce fichier est ce qu'affiche la fenêtre de mise à jour, et rien d'autre. Ce
n'est **pas** une liste des modifications : sur 97 commits entre 0.1.1 et
0.1.2, il reste huit lignes, et les choisir est le travail. Un point a sa
place ici si quelqu'un le remarque en utilisant le programme.

Donc : pas de messages de commit, pas de noms de modules, pas de numéros de
paragraphe. « La barre disparaissait alors que l'application calculait encore
pendant quatre secondes » est un bon commit et une mauvaise entrée ; « La
progression reste affichée jusqu'à la fin réelle du calcul » dit la même chose
à celui qui est devant l'écran.

Un fichier par langue dans ce dossier, comme pour les catalogues, et tous
portent les mêmes points dans le même ordre (`tests/test_changelog.py`).
`tools/make_download.py` en tire la section de la version courante et l'écrit
dans `website/version.json`.

## 0.2.0


### Blocs
- Vos propres blocs sans une ligne de code : sélectionnez des étapes dans l'historique et placez-les dans le catalogue comme bloc — avec vos champs, un aperçu et une plage de valeurs vérifiée.
- Un bloc que vous avez créé voyage dans le fichier de projet. Celui qui l'ouvre peut insérer votre pièce sans rien installer.
- Cinq nouveaux blocs au catalogue : crochet pour panneau perforé, équerre, pied, clip de câble et œil de charnière.
- Le crochet tient désormais même si l'on soulève la pièce en retirant quelque chose — une languette élastique s'enclenche derrière le panneau. Désactivable si vous retirez souvent la pièce.
- Support mural, nervure, languette-rainure, ergot, clip d'encliquetage et charnière-film figurent désormais dans le menu d'une face cliquée. Il manquait justement le support mural.
- Qui insère un bloc du catalogue sans choisir un endroit se voit désormais poser la question. Jusqu'ici il se plaçait à l'origine, moitié dans la pièce, moitié sous le plateau.
- Le catalogue de blocs peut être consulté même sans modèle. L'insertion est alors désactivée et en dit la raison, au lieu d'annuler seulement après confirmation.
- Le logement d'écrou et le dégagement de tête du trou de vis n'enlevaient rien : tous deux construisaient au-dessus de la face au lieu d'en dessous.
- Le logement d'aimant retient de nouveau l'aimant : la lèvre de retenue était jusqu'ici ajoutée au logement au lieu d'y être évidée, et disparaissait dedans.
- La fente en trou de serrure pend maintenant à la verticale, si bien que la vis se coince en descendant. Couchée de travers, elle glissait de côté et la tête manquait de place.
- Le logement d'écrou correspond désormais à l'écrou : pour M5, M6 et M8 le tableau indiquait une hauteur trop faible, six dixièmes de trop peu pour le M5.

### Dessin
- En dessinant, la grille montre ce à quoi l'accrochage obéit, le pas se saisit au clavier, les cotes sont près du pointeur, et la barre dit sur quelle face vous dessinez.
- Les raccourcis clavier fonctionnent de nouveau en mode dessin — ligne, cercle, arc, ajuster, décalage, Ctrl+Z — et le clic droit ouvre le menu du dessin au lieu de celui du modèle.
- Ajuster à la vue ramène le dessin dans le cadre, et un clic à cinq millimètres d'un point ne s'y accroche plus.
- Une ligne de construction reste une ligne de construction, même après avoir été ajustée, prolongée, décalée ou reflétée. Jusqu'ici une ligne d'axe devenait une arête de profil et séparait la pièce.
- La boîte de dialogue d'une étape affiche les cotes de votre dessin au lieu des valeurs par défaut, et un cercle apparaît avec son diamètre entier, pas la moitié.
- Une poche issue d'un dessin avec trou conserve le trou. Jusqu'ici elle fraisait aussi l'îlot.
- Un trou dessiné est soustrait quel que soit le sens dans lequel vous l'avez tracé. Selon l'ordre des clics, une pièce plus pleine sortait auparavant.
- Ajuster ne coupe plus qu'à l'intérieur de son propre segment, et Prolonger trouve aussi des cercles et des arcs comme cible — jusqu'ici il ne voyait que des lignes.
- Une transition entre deux dessins conserve leurs trous, et une poche sur une paroi latérale coupe dans la paroi au lieu d'en haut.
- Un contour qui se croise lui-même est désormais signalé sur le dessin, au lieu de produire un corps non étanche qui s'exporte quand même.
- Un dessin avec trou dans un trou conserve tous les niveaux, et Projeter prend le plan sur lequel vous dessinez — jusqu'ici le troisième niveau disparaissait et la coupe venait du dessous.
- La mise à une largeur donnée mesurait aussi une ligne de construction. Cinquante millimètres devenaient cinq.

### Historique et étapes
- Plusieurs étapes de l'historique peuvent être sélectionnées à la fois.
- Les limites d'une cote se modifient après coup — jusqu'ici, ce qui était saisi à la création valait pour toujours.
- Modifier une étape après coup peut désormais être annulé. Jusqu'ici Ctrl+Z retirait la mauvaise action et laissait la valeur modifiée en place.
- Une étape qui vise une face d'un autre corps se recalcule après chaque changement. Jusqu'ici une pièce alignée restait à l'ancien endroit, même après la fermeture.
- Les caractéristiques gardent leur nom quand une pièce est tournée ou déplacée pour l'impression. Les étapes et ajustements qui les visent ne tombent plus dans le vide.
- Si la face jusqu'où l'extrusion va disparaît, l'erreur pointe désormais ce champ et suggère d'en choisir une autre — au lieu du plan de l'esquisse.

### Outils et géométrie
- La fraisure ne fonctionnait que dans un sens par axe. Cliquée du mauvais côté, elle n'enlevait rien et ne disait rien.
- Sur les pièces à gradins, perçage et bouchon travaillaient dans le vide : la direction venait de la boîte englobante et non de la matière à cet endroit.
- Un bouchon traversant ne remplissait que la moitié du perçage — et laissait tout autour l'écart dont le perçage avait été élargi pour la matière.
- Le remplissage en treillis posait des barres à côté de la pièce au lieu de son creux.
- L'évent d'une pièce évidée se termine désormais dans la cavité au lieu de traverser le dessus, et la rainure filetée du couvercle à visser ne perce plus un trou dans son propre dessus.
- Union, soustraction et peinture signalent désormais quand rien ne s'est produit. Jusqu'ici une étape restait dans l'historique au-dessus d'un modèle inchangé.
- Si une pièce se disloque parce qu'un bloc ne touche plus son support, le rapport le signale comme une erreur et recommande une solution. Jusqu'ici le nombre de morceaux n'était qu'une indication.
- Un filetage dans un perçage cliqué ne coupait que sa moitié inférieure. Même chose pour l'insert à chaud.
- Un filetage intérieur est désormais soustrait, comme son intitulé le promet. Jusqu'ici un boulon poussait à la place dans le trou de noyau.

### Impression et slicer
- L'estimation de matière pour les supports était fausse d'un grand facteur : elle calculait la surface sous le porte-à-faux au lieu de la colonne en dessous.
- La largeur de pont mesure désormais la portion vraiment franchie sans appui. Une goulotte à câbles rapportait auparavant la largeur de sa boîte englobante et recevait le mauvais conseil.
- Une pièce plus fine qu'une couche imprimée n'est plus dressée sur chant.
- La division automatique compte le dépassement du tenon dans la limite du plateau et ne laisse aucun ajustement pointant vers des endroits disparus.
- Un assemblage répond désormais aussi à « Poser sur le plateau » : il descend en bloc, les pièces gardant leur position les unes par rapport aux autres. Jusqu'ici rien ne se passait.
- La quantité de filament lue dans un fichier G-code est de nouveau correcte. Une commande en fin de fichier faisait calculer différemment tout ce qui précédait et doublait le total.
- Un changement d'imprimante ou de matériau conserve ce que vous avez réglé. Jusqu'ici tout le jeu était réinitialisé sans un mot.
- Le choix de filament par emplacement de matériau parvient au trancheur. C'était le texte affiché qui était enregistré, pas le profil.

### Vue et utilisation
- Une face sélectionnée compte : perçage, bloc et esquisse vont là où vous avez pointé. Chaque opération sur une face coûtait auparavant deux clics.
- Un clic sur un perçage propose désormais la vis qui y passe vraiment — et indique le diamètre mesuré.
- Après « Décaler la face », les faces de la pièce peuvent de nouveau être cliquées. Jusqu'ici il ne restait rien sur quoi dessiner, percer ou poser un ajustement.
- À l'ouverture d'un projet, un indicateur de chargement apparaît aussitôt. Jusqu'ici le centre de la fenêtre restait noir un moment ou affichait l'écran d'accueil — on aurait dit un plantage.
- Un clic dans la vue ne touche que ce que vous voyez — aucune pièce masquée, aucune d'une autre plaque. Après le mode Déplacer, les arêtes ne transpercent plus toutes les faces.
- Les vues d'axe de Ctrl+0 à Ctrl+6 cadrent de nouveau le modèle, au lieu d'y inclure aussi le plateau et le volume d'impression.
- Qui a beaucoup déplacé une pièce puis la fait pivoter tourne de nouveau autour de la pièce, et non autour d'un point voisin.
- Une cote dans la vue utilise désormais l'unité choisie, un changement de thème recolore le plateau et le volume d'impression, et l'étiquette et la poignée se placent sur la pièce plutôt qu'à côté.
- Ce qu'apporte un bloc inséré figure dans l'arborescence sous son nom, et le nœud propose de modifier précisément cette étape.
- L'ombre sous la pièce montre désormais chaque morceau séparément et se fait plus discrète. Si un corps se disloque, on le voit maintenant à l'ombre.

### Fichiers et export
- Deux fichiers importés portant le même nom ne se perdent plus. Le second écrasait auparavant le premier, et le projet ne pouvait plus être rouvert ensuite.
- Une adresse sans extension de fichier indique désormais qu'une page web s'y trouve et où se situe le bouton de téléchargement, au lieu de « Format non reconnu ».
- À l'export, des pièces de même nom s'écrasaient : un fichier, deux messages de réussite, une pièce perdue.
- L'extension du projet est désormais ajoutée par « Enregistrer sous ». Un projet enregistré sous support.stl était, à l'ouverture, un modèle étranger illisible.
- Un projet modifié n'est plus perdu quand vous glissez un fichier sur l'écran d'accueil — la question est posée avant.

### Vitesse et stabilité
- L'application ne disparaît plus sans un mot quand une cote change, un dessin est lu ou une coupe est calculée. Les mêmes calculs vont maintenant jusqu'à soixante fois plus vite.
- Évider et goupiller peuvent vraiment être annulés. Sur une pièce scannée, le bouton restait immobile pendant des minutes.
- Les gros fichiers d'un trancheur s'ouvrent sans que la fenêtre se fige. Auparavant, le simple comptage des corps chargeait tout le fichier en mémoire.
- Si un calcul en arrière-plan se bloque, l'application le signale désormais. Sinon, la légende, l'analyse des couches et la recherche d'une nouvelle version restaient bloquées pour toujours.
- Annuler abandonne désormais aussi la prochaine exécution déjà mise en file, et la barre de progression ne disparaît plus sur un fichier encore en cours d'écriture.

### Langues
- La langue choisie dans l'installeur s'applique aussitôt, sinon celle du système. Et une langue choisie dans la fenêtre prend effet immédiatement, au lieu d'attendre le prochain démarrage.
- Un changement de langue agit maintenant dans toute la fenêtre. Les réglages d'impression restaient dans la langue de démarrage.
- Les exemples fournis nomment désormais leurs cotes dans votre langue. « Breite, Tiefe, Höhe » y figurait auparavant en allemand, même avec une interface en anglais.
- La ligne de commande parle désormais la langue réglée. Jusqu'ici elle donnait l'aide et les messages d'erreur en allemand, quel que soit le choix.

### Chat et support
- Une proposition du chat qui retire des étapes dit d'avance lesquelles partent avec elle. Et Annuler annule vraiment au lieu de continuer à calculer en arrière-plan.
- Le chat parvient de nouveau à huit étapes par question au lieu de quatre, et la ligne de coût ne surestime plus.
- Ce qui part avec un retour vers l'assistance s'affiche auparavant, mot pour mot — y compris le journal. Et si l'envoi échoue, le message donne la vraie raison.

### OpenSCAD
- Les formes libres ne demandent plus de second programme : ce que faisait OpenSCAD, les outils de dessin et les blocs le font — une installation de moins à gérer.
- Un projet contenant du code OpenSCAD s'ouvre toujours, et tout le reste s'y calcule comme avant. Le Rapport nomme l'étape, et « Afficher les valeurs » en copie le code.

## 0.1.5

- Le dessin se fait désormais dans la vue : la surface de dessin se pose sur le modèle au lieu de le remplacer, et un clic dans la vue place un point sur le plan de l’esquisse.
- La grille de la surface de dessin montre à nouveau ce sur quoi l’accrochage se fait. Elle est restée un temps à un dixième de millimètre, à moitié cachée par la barre.
- Un clic au milieu d’un perçage sélectionne le perçage. Auparavant il touchait la face voisine ou rien, et en vue de dessus il annulait même la sélection.
- Un clic dans une découpe rectangulaire sélectionne la pièce au lieu d’annuler la sélection.
- Le chat trouve maintenant votre modèle local quelle que soit la façon d’écrire l’adresse. Jusqu’ici il fallait l’adresse complète terminée par /api/chat.
- Une clé d’accès refusée par le fournisseur ne bloque plus votre modèle local. Le chat passe de lui-même au modèle disponible suivant au lieu de renvoyer la même clé.
- Les messages d’erreur du chat indiquent de quel modèle il s’agit. Au-dessus d’une erreur de clé, il n’y avait qu’une ligne disant que le modèle n’avait pas répondu.
- Le champ de l’adresse d’un service donne un exemple et précise qu’un dossier n’a rien à y faire. Si vous en saisissez un, il revient avec la raison au-dessus.
- La boîte de dialogue de configuration ne plante plus lorsqu’un champ d’adresse contient un chemin de dossier, ou le champ de clé un texte collé par inadvertance.
- Les menus déroulants affichent de nouveau toutes leurs entrées. Dès qu’un champ avait le focus clavier, il manquait une demi-entrée au menu ouvert.
- Ctrl+Z et Ctrl+Y figurent maintenant sur leur entrée de menu, comme les quatorze autres raccourcis. Ils ont toujours fonctionné ; rien ne les nommait.
- Les messages d’erreur pendant le dessin indiquent quelle limite a été dépassée. Au-dessus de « entre trois et soixante-quatre sommets » il n’y avait que « La saisie n’était pas utilisable ainsi ».
- Les actions regroupées figurent dans le même menu et n’apparaissent qu’une fois dans la recherche de commandes, comme évider et évider avec précision.
- Une entrée de menu « Filetage » indique maintenant où va le filetage — dans un perçage ou sur un boulon.
- L’interface espagnole nomme les caractéristiques de la même manière partout. La même liste contenait auparavant deux mots pour la même chose.
- L’application libère la mémoire à la fermeture d’une fenêtre et s’arrête plus proprement.
- L’image jointe à un retour montre désormais aussi le modèle. Il y avait jusqu’ici une surface noire au milieu — précisément là où se trouve la pièce concernée.


## 0.1.4

- Pendant la démo, Solidon pose une question : après une demi-heure de travail, une carte se pose sur la vue et demande comment cela se passe. Elle n’arrête rien, et rien ne part sans votre clic.
- Cliquez sur une face et insérez un élément : il se place perpendiculairement à cette face au lieu de pointer vers le haut. Sur une paroi latérale, un trou de vis traversait la paroi.
- Un élément posé sur un perçage en reprend la cote. Sur un perçage de 5,19 mm, l'insert à emmancher proposait auparavant M3, qui n'y enlève rien.
- Un clic avec une main un peu tremblante sélectionne de nouveau au lieu de décaler la pièce d'un dixième de millimètre.
- Une pièce sélectionnée se déplace directement à la souris — saisir et tirer, sans passer par « Déplacer ». La poignée reste pour le précis : par axe et par pas de grille.
- Depuis le dessous, on voit désormais à travers le plateau. Qui travaille la face inférieure d'une pièce tourne la vue en dessous et voit la pièce au lieu du plateau.
- Un perçage se sélectionne aussi en cliquant en plein milieu, et non seulement sur sa paroi.
- La recherche de commandes comprend maintenant les mots courants : « copier », « supprimer », « ouvrir » et « colorer » ne menaient nulle part, alors que les quatre existent.
- La recherche trouve aussi pour qui ne connaît pas le terme technique. En tapant « renforcer », « encliqueter » ou « visser », on arrive au nervurage, au crochet et au trou de vis.
- Deux entrées de menu s'appelaient « remailler ». Ce sont maintenant « Affiner les arêtes » et « Uniformiser les triangles » : la première divise les longues arêtes, la seconde égalise leur taille.
- Le programme parle la langue que vous entendez ailleurs : « corps exact » au lieu de « B-Rep », plateau au lieu de surface d’impression, plaque pour la disposition.
- Au démarrage, Solidon vérifie s’il existe une version plus récente et la propose. Elle n’est téléchargée et installée qu’après votre confirmation ; cela se désactive dans les réglages.
- Un modèle de langue local peut désormais calculer dix minutes. Avant, le chat abandonnait au bout de deux et demandait un rapport d’erreur, pour un calcul simplement plus long.
- Un anneau est reconnu comme une seule caractéristique et non plus comme trois bourrelets superposés.
- L’entrée « Épaissir la surface » fait maintenant ce qu’elle promet. Auparavant, elle décalait la surface.
- Le titre de la fenêtre nomme le modèle ouvert, même s’il n’existe pas encore de fichier de projet.
- Pendant le tracé, la cote se trouve à la pointe de la ligne et non au bord de la fenêtre.
- Une entrée de menu désactivée dit maintenant pourquoi elle l’est. La raison était là et restait invisible.
- Le rapport d’erreur emporte l’état de la scène : objets avec cotes, caractéristiques, paramètres et historique. Une erreur se reproduit ainsi au lieu de se deviner.
- Plusieurs plantages à la fermeture de fenêtres et de boîtes de dialogue sont corrigés.

## 0.1.3

- Le noyau exact sait désormais percer : « Percer un trou exact » travaille directement sur le corps exact, sans détour par un maillage.
- Les congés et chanfreins sont reconnus plus sûrement. Un congé était parfois signalé comme un téton — avec un diamètre qui n’existait pas.
- Les exemples fournis n’accueillent plus avec des avertissements qui n’en sont pas.
- L’écran d’accueil tient sur les petits écrans, sans défilement.
- Une caractéristique cliquée se colore elle-même. Auparavant, tout le corps prenait la couleur de sélection et l’on ne voyait pas ce qui était visé.
- L’arborescence des objets indique la cote de chaque caractéristique reconnue.
- Les maillages exportés ne contiennent plus de triangles vides.
- Enregistrer deux fois donne deux fois le même fichier.
- Les cinq traductions ont été relues. Les termes techniques portent maintenant le nom que leur donnent les slicers.
- La barre d’outils est rangée : le champ le plus large était celui dont on se sert le moins.
- Une seconde erreur du programme ne place plus une seconde fenêtre sur la première.

## 0.1.2

- Les nombres décimaux saisis sont lus correctement partout. « 12,5 » reste douze et demi ; auparavant, cela pouvait devenir 125, sans question ni avertissement.
- Chacun des cinquante-six champs des réglages d'impression indique désormais ce qu'il fait quand on le modifie.
- Le temps d'impression et la quantité de matière sont estimés plus finement, surtout pour les pièces évidées.
- Le transfert vers le trancheur atteint le plateau. Avec CuraEngine, les pièces se retrouvaient à côté.
- Lors d'une découpe avec goupilles, les trous correspondants se placent dans la bonne moitié.
- Millimètres et pouces valent maintenant partout où figure un nombre — y compris dans les barres d'outils et lors de la peinture.
- La progression reste affichée jusqu'à la fin réelle du calcul, et la fenêtre demeure utilisable pendant ce temps.
- Tous les raccourcis clavier figurent désormais dans un aperçu unique : dans le menu Aide, sous « Raccourcis clavier », ou en appuyant sur la touche point d’interrogation.
