# Nouveautés

Ce fichier est ce qu'affiche la fenêtre de mise à jour, et rien d'autre. Ce
n'est **pas** une liste des modifications mais une sélection, et choisir est le
travail. Un point a sa place ici si quelqu'un le remarque en utilisant le
programme. Combien il y en a, c'est la version qui le décide, pas un nombre.

Donc : pas de messages de commit, pas de noms de modules, pas de numéros de
paragraphe. « La barre disparaissait alors que l'application calculait encore
pendant quatre secondes » est un bon commit et une mauvaise entrée ; « La
progression reste affichée jusqu'à la fin réelle du calcul » dit la même chose
à celui qui est devant l'écran.

Un fichier par langue dans ce dossier, comme pour les catalogues, et tous
portent les mêmes points dans le même ordre (`tests/test_changelog.py`).
`tools/make_download.py` en tire la section de la version courante et l'écrit
dans `website/version.json`.

## 0.5.2

### Nouvelles formes et nouveaux blocs

- Nouvelle forme de base « Ajouter un tube » : diamètre extérieur et hauteur, plus épaisseur de paroi ou diamètre intérieur, en une étape.
- Nouveau bloc « Patte percée » : une patte plate sur n'importe quelle face, trou et cotes adaptés à la vis de M3 à M8.
- Nouveau « Collier de tube » pour les tubes courants de 15 à 40 mm ou toute cote personnelle jusqu'à 110 mm, avec vis de serrage M3 à M6 et le jeu de votre matériau.
- Quatre supports se créent en une étape avec de vraies faces et arêtes : en U, rond, à fourche et à tablette, fixés par trou de serrure, trous de vis, crochet de panneau ou pince.
- Une scène vide montre comment commencer : pavé, cylindre, dessin, blocs ou un fichier que vous y glissez.
- Les nouveaux corps apparaissent sur le plateau ou sur la face plane choisie, plus à l'endroit d'un corps sélectionné avant, et sont ensuite sélectionnés.

### Imprimer et transmettre au slicer

- La préparation de l’export 3MF peut être annulée. Pour plusieurs plateaux, Solidon réutilise les couches et les suggestions déjà calculées.
- Les filaments inutilisés des anciens projets ne sont plus transmis au logiciel de tranchage. Les profils restent associés aux filaments utilisés.
- Les modèles ajoutés trouvent aussi une place après le douzième plateau. Les plateaux importés gardent leur disposition.
- Les modèles ajoutés avec des filaments différents sont placés sur des plateaux séparés si l’imprimante n’a pas assez de buses.
- Lors d’un changement d’imprimante ou de logiciel de tranchage, le plateau précédemment choisi n’est plus repris dans le nouveau profil.
- Les pièces élancées se rapprochent du centre lors du placement. L’espace de la bordure est réglable ; une bordure jointe à la pièce est proposée pour les petites bases.
- Les profils endommagés de PrusaSlicer et SuperSlicer sont signalés. Solidon utilise alors l’ensemble de ses réglages d’impression.
- Les réglages propres à chaque pièce sont mieux transmis au trancheur. Ceux qui s’appliquent à tout le plateau sont expliqués sur la pièce concernée.
- Avec Orca et Prusa, une suggestion de vitesse acceptée pour un ajustement ne ralentit que les pièces concernées.
- Même les petites modifications acceptées dans les réglages d’impression sont conservées à l’export.
- Cura reprend les limites de jerk du profil, avec des valeurs distinctes pour les parois, le remplissage et la première couche.
- Si une autre imprimante est active dans Cura, le transfert nomme les deux et indique où reprendre le choix de Cura.
- Correction d’un plantage d’ElegooSlicer et d’OrcaSlicer lors du tranchage de modèles multicolores avec des supports en grille.
- Après le tranchage, Solidon compare aussi les supports et les couches du modèle par plateau. Le rapport présente l'estimation interne et les valeurs du fichier d'impression.
- La comparaison de matière porte uniquement sur le modèle imprimé. La purge est affichée séparément, avec une indication si sa quantité ne peut pas être lue entièrement.
- L'analyse de l'espace nécessaire aux supports est bien plus rapide sur les modèles creux et préserve les contours fins.
- Pour les pièces qui se chevauchent, l'analyse d'impression ne compte plus l'air enfermé comme de la matière. La détection des surplombs et des supports nécessaires s'améliore aussi.
- Au premier démarrage et dans les réglages, vous choisissez d'abord le slicer, puis l'une de ses imprimantes. La liste a un champ de recherche, volume et buse viennent du profil du slicer.
- Vous choisissez la buse dans les réglages d'impression parmi les tailles que connaît votre imprimante, et le slicer reçoit le profil correspondant.
- Les réglages d'impression demandent dans l'ordre où l'un dépend de l'autre : slicer, imprimante, buse, plateau, filaments et qualité, puis les valeurs.
- Vous pouvez désormais générer le fichier d'impression directement depuis Solidon avec Creality Print 7.2 et 7.3.
- Avec Cura, Solidon reprend à votre demande l'imprimante que Cura utilise, avec sa propre buse. Une imprimante renommée dans Cura est reconnue.
- Cura tranche maintenant avec la buse que vous avez choisie, aussi pour les imprimantes de sa propre liste, et celles dont l'origine est au centre du plateau la gardent.
- Les imprimantes dont l'origine n'est pas dans le coin du plateau, comme delta, BIBO ou Dremel, reçoivent les pièces là où Solidon les pose. Avant, elles étaient au bord ou réorganisées.
- Bambu Studio reçoit la variante de buse et les températures de vos bobines, jusque dans le fichier 3MF.
- Si vous choisissez brim, skirt, raft ou *Automatique* dans les réglages d'impression, seules les cotes que reçoit votre slicer s'affichent, sans champs sans effet.
- Un nombre hors de sa limite reste dans le champ, la limite s'affiche à côté et « Trancher » attend qu'il soit juste. Jusqu'ici, il était tronqué sans rien dire.
- Les pièces hautes et fines sur une petite base reçoivent des parois plus calmes, à 60 mm/s et avec moins d'accélération. Sur la Centauri Carbon 2, ces tiges se détachaient.
- Avec Cura, le rapport de contrôle nomme les pièces qui reçoivent ces valeurs par ricochet, car Cura ne les prend que pour tout le plateau.
- Solidon ne propose « Paroi extérieure d'abord » que pour la pièce qui en a besoin, et jamais pour une pièce avec supports.
- Dans la recherche rapide aussi, « Orienter pour l'impression » vérifie qu'une pièce tient debout en sécurité.
- Avec « Disposer sur le plateau », chaque pièce va sur le premier plateau où elle a de la place. Le jeu de minigolf tient ainsi sur quatre plateaux au lieu de six.
- Si vous faites glisser un corps dans la vue sur un autre plateau, il se retrouve sur ce plateau.
- Quand un autre modèle arrive, depuis un fichier, un téléchargement ou généré, la vue montre le plateau où il se trouve.
- Un autre modèle se place à l'emplacement libre le plus proche du centre du plateau, au lieu du coin arrière gauche.
- Après le premier « Ouvrir dans le slicer … », Solidon ne recalcule plus l'historique.
- La contre-vérification avec SuperSlicer ne signale plus de code de démarrage ignoré là où aucun ne l'a été.
- SuperSlicer ne plante plus sur les pièces rondes : il ne reçoit plus la couture en biseau qu'il ne connaît pas.
- SuperSlicer reçoit des supports en grille avec une explication si des supports arborescents étaient choisis. La couture la plus proche est appliquée sans fausse alerte.
- TPU trouve le profil de filament et ses valeurs de démarrage dans PrusaSlicer et SuperSlicer. Si aucun profil n'est disponible, Solidon indique qu'il utilise son propre tableau de matériaux.
- Cura respecte les limites d'accélération et signale les valeurs choisies réduites. Le remplissage plein garde sa vitesse ; seule la face supérieure utilise la vitesse de surface.
- La température de chambre arrive dans le bon champ du slicer. Les profils sans chauffage de chambre réglable expliquent pourquoi la valeur reste sans effet.
- Le remplissage Lignes arrive dans Bambu Studio et Creality Print sous forme de lignes, sans être remplacé par Grille ou Cubique.
- Après le découpage, Solidon signale les réglages rejetés par PrusaSlicer ou les slicers Orca, ainsi que les changements de bordure, d'ordre des parois et de support.
- La présélection du filament prend Generic ou la marque de votre imprimante au lieu d'un filament spécial tiers, par exemple Generic PETG au lieu de BETA PETG sur la Bambu A1.
- L'export et le tranchage utilisent le calcul fin au lieu de la vue plus rapide de la fenêtre. Les cônes et les pièces fusionnées en douceur arrivent ainsi lisses dans le fichier.
- Sur les surfaces STEP aussi, pour des rotations de près de 180° et sur des faces reconnues en partie, *Orienter pour l'impression*, *Pivoter* et *Déplacer* fonctionnent. Le corps reste exact.
- Un mur extérieur plus lent s'applique aussi aux petits périmètres (trous, tiges) dans PrusaSlicer et la famille Orca.
- PrusaSlicer et la famille Orca respectent la densité des supports choisie. Le champ commence à 1 %. Pour imprimer sans supports, choisissez « Aucun ».
- Pour les impressions multicolores avec OrcaSlicer, ElegooSlicer, Bambu Studio et Creality Print, la tour de purge démarre à une position adaptée à la taille du plateau.
- Les pièces trop grandes sont signalées avant le lancement du slicer. Si leur disposition sur un seul plateau échoue, vous pouvez les répartir sur plusieurs plateaux.
- Les caractères spéciaux dans les noms de projet ou d’utilisateur ne bloquent plus la création du fichier d’impression. Cura lit aussi les modèles aux noms turcs ou chinois.
- Solidon dispose les pièces qui se chevauchent sur le plateau avant le tranchage avec PrusaSlicer ou Cura et vous prévient si aucune disposition adaptée n’est trouvée.
- Si PrusaSlicer ou SuperSlicer signale une première couche vide, Solidon nomme la pièce et propose de la poser sur le plateau ou d'ouvrir les réglages d'impression adaptés.
- Les avertissements de PrusaSlicer et SuperSlicer figurent dans le rapport même si le slicer réussit, une couche vide comme erreur. La distance au radeau se règle à part.

### Perçages, trous oblongs et découpe

- L'angle d'un trou oblong sur un perçage importé pointe dans la direction attendue et la garde quand vous changez la finesse.
- Deux plaques qui se touchent restent un seul corps autour d'un perçage et gardent leur matière, que vous l'étiriez, le modifiiez, le déplaciez ou le fermiez. Une goupille au-dessus reste en place.
- Étirer un perçage qui traverse deux corps ne signale plus que le corps se fragmente quand ce n'est pas le cas.
- Si un perçage coupe le corps en deux, le rapport le dit une seule fois, avec le nombre de pièces à la fin, et se tait dès que le corps est de nouveau d'un seul tenant.
- Les motifs sur les faces cylindriques des modèles importés restent fermés quand vous les modifiez.
- Dans l'historique d'un corps STEP, on peut réordonner les étapes ou en insérer une avant, même si une étape ultérieure vise un perçage. La référence suit le perçage.
- Un perçage déplacé ou dupliqué avec une nouvelle direction reste exact sur un corps STEP.
- Une caractéristique reconnue à plus d'un mètre de l'origine garde sa place quand vous la modifiez. Avant, le champ tronquait le nombre sans rien dire, et le perçage bougeait.
- Si une étape touche une pièce dont la surface se croise elle-même, elle s'arrête et montre l'endroit. Ailleurs, elle continue le calcul et signale que les pièces n'ont pas pu être réunies.
- Même le long de sa couture de symétrie, « Scinder le modèle » coupe une figure proprement, et les goupilles sont en place dès l'aperçu.
- Si une coupe ne fait qu'effleurer une paroi, « Scinder le modèle » indique l'endroit et mène à la position de la coupe au lieu d'échouer sur les goupilles.
- Découper coupe maintenant aussi en biais : en haut, vous choisissez le « Plan » — sur un axe avec inclinaison, parallèle à une face, par une arête ou par trois points cliqués dans la vue.
- Un corps STEP reste un corps STEP quand vous le découpez, avec ses faces, arêtes et noms.
- Un couvercle vissé tout juste créé n'est plus signalé comme trop serré pour son goulot.
- Si un perçage ne peut pas être découpé proprement dans un corps STEP, Solidon le perce dans le modèle en triangles au lieu de transmettre un corps défectueux.
- Si vous avez choisi « Charger maintenant », les pièces de *Scinder le modèle* ne lancent plus non plus des minutes de reconnaissance ; « Reconnaître toutes les caractéristiques » la rattrape.
- Choisir « Scinder le modèle » sur une ligne récapitulative du rapport pour plusieurs corps les scinde l'un après l'autre. Avant, seul le premier l'était.

### Congés et chanfreins

- Arrondir un groupe d'arêtes d'un corps STEP arrondit désormais les arêtes possibles au lieu de tout refuser. *Montrer l'endroit* retrouve chaque arête omise.
- Les arêtes contre une paroi pas plus épaisse que le rayon restent vives, et le rapport indique le rayon qui y tient. Jusqu'ici, tout l'arrondi était refusé.
- Si un corps STEP n'a pas d'arête propre à un endroit choisi, le rapport propose *Terminer la modification des faces et réessayer*. Sur le modèle en triangles, il est aussi arrondi.
- S'il ne reste plus de place pour l'échange avec le processus de calcul, Solidon calcule quand même l'étape et le signale dans le rapport. Avant, il s'arrêtait en conseillant un calcul plus grossier.

### Sculpter, texte et esquisse

- Avec « Sur les deux faces », « Appliquer du texte » pose aussi les lettres au dos, lisibles de l'extérieur. Pratique pour drapeaux, panneaux et étiquettes.
- Les inscriptions sont composées plus précisément : les lettres restent à leur place, et les courbes suivent la police au lieu de perdre jusqu'à 2 % de surface en petite taille.
- La symétrie de « Sculpter » reflète au centre du corps, même loin du centre du plateau. Les anciens projets gardent leur forme.
- Le pinceau de sculpture n'agit que sur la face tournée vers lui. Creuser une plaque mince n'entraîne plus la face inférieure.
- Un trait sur le plan de symétrie agit une fois au lieu de deux, et juste à côté le trait et son reflet se fondent en douceur.
- L'éditeur de squelette montre os et articulation dans la vue, et une articulation se place au milieu du corps au lieu de sa peau, la figure plie donc régulièrement.
- La barre de sculpture nomme maintenant la valeur du pinceau « Intensité » au lieu d'« Épaisseur », qui faisait penser à une paroi.
- Si un trait de sculpture perce la paroi ou la rend trop mince, le rapport et l'export le signalent, avec « Montrer l'endroit » et « Retirer le trait ».
- Dans la fenêtre, « Fusionner en douceur » calcule maintenant finement, tant que le corps n'est pas très grand.
- Si un bloc comme un trou de serrure déborde de sa face, le rapport le signale.
- Une cote tapée comme longueur 40 n'étire l'esquisse que dans cette direction. Le corps obtenu reste fermé et posé sur le plateau.
- Les dessins SVG arrivent correctement : rotations, cisaillements, coins arrondis, ellipses et arcs elliptiques sont justes, et les calques masqués restent dehors.
- La cible d'« Aligner sur une caractéristique » est d'abord vide, et le premier clic dans la vue la remplit. « Appliquer » attend jusque-là au lieu de poser le corps du mauvais côté.
- Un fichier en mètres qui tiendrait aussi sur le plateau lu en pouces n'est plus lu faux sans rien dire. Solidon demande l'unité.
- Un nouveau tracé dans un creux qui vient d'être creusé l'approfondit, même avec un petit pinceau. Jusqu'ici, il restait sans effet et comptait comme manqué.
- Dans « Sculpter », la fenêtre affiche chaque trait aussi vite après de nombreux traits qu'au premier. Jusqu'ici, elle ralentissait à chaque trait.
- Avec « Figer l'état », Solidon enregistre une session de sculpture aussi finement que l'export et l'impression la calculent, et la fenêtre reste utilisable. Avant, il figeait la vue plus grossière.

### Générer avec l'IA

- Annuler pendant « Encore un essai » n'arrête que l'essai en cours. Les essais terminés restent au choix.
- Chaque essai de la liste indique sa phrase ou son image et sa graine. Si votre saisie ne correspond plus à l'essai choisi, la boîte de dialogue dit lequel sera appliqué.
- Le modèle d'image est téléchargé par « Configurer le modèle d'image … » même si les autres poids sont déjà là.
- Si une erreur de génération indique la configuration comme issue, elle apparaît comme bouton dans la boîte de dialogue.
- Pendant la génération d'un modèle, la fenêtre reste utilisable. La boîte de dialogue se met de côté, et la barre d'état montre progression, temps et « Annuler ».
- La boîte de dialogue de génération indique le volume à la taille où la pièce arrive.
- Un modèle généré s'annule d'un seul Ctrl+Z. Il en fallait trois ou quatre.
- Si « Appliquer » est refusé pendant la génération, la boîte de dialogue reste ouverte avec tous les essais et indique l'issue au lieu de jeter le maillage.

### Utilisation et système

- La case « Créer les cotes comme paramètres » est cochée la première fois, puis retient votre dernier choix, même après un redémarrage.
- Les boîtes de dialogue s'ouvrent à la taille de leur contenu, sans espace vide, et une taille que vous avez réglée vous-même est conservée.
- L'export, « Trancher » et « Ouvrir dans le slicer … » reçoivent toujours le calcul fin, pas la vue plus grossière de la fenêtre. Congés et cônes arrivent ainsi en pleine résolution.
- Un export pendant un calcul en cours attend le nouveau résultat. Avant, le fichier pouvait encore porter l'ancienne cote.
- Si vous n'exportez qu'une partie de la scène, la boîte de fichier et la confirmation indiquent l'étendue, par exemple « 1 corps sur 2 ».
- La barre des paramètres refuse une cote hors de sa limite au lieu de laisser la vue vide.
- Dans la barre des paramètres, chaque pas de flèche compte, et le focus reste dans le champ.
- Dans la barre des paramètres, les cotes de deux pavés portent leur numéro, et une cote avec sa propre plage de travail a un curseur.
- Si une étape attend une question, « Appliquer » reste disponible et la question s'affiche.
- Dans la boîte de dialogue d'une opération, les libellés forment une colonne, les champs ont la même largeur et chaque interrupteur précède ce qu'il commande.
- Les coches des listes sont lisibles sur chaque ligne, et les couleurs apparaissent en pastille ronde à côté.
- La palette de commandes explique outils et actions de fichier en une phrase.
- Après un changement de paramètre, « Générer des variantes » commence à la valeur de ce paramètre.
- Si l'enregistrement d'un calibrage échoue, les valeurs précédentes sont conservées.
- Dans le projet d'exemple de la deuxième voie, les trous de vis suivent la largeur et l'épaisseur.
- La fenêtre « Nouveautés » et le site web affichent la mise en valeur en style au lieu d'astérisques.
- L'anglais et l'espagnol emploient un seul mot pour le jeu d'ajustement, et les messages suivent la ponctuation de chaque langue.
- Pendant qu'un dialogue affiche son aperçu, les espaces arrivent dans chaque champ de texte, y compris le questionnaire et le chat, et cases et boutons acceptent la barre d'espace.
- Avec « Mettre à l'échelle », un corps reste posé sur le plateau au lieu de s'enfoncer sous la plaque, et la vue le recadre quand il grandit.
- Certains constats qui visent une étape l'ouvrent pour la modifier, par exemple « Modifier la taille » après « Mettre à la cote ».
- Une ligne récapitulative du rapport comme « Réduire au volume d'impression » est une seule étape d'annulation pour tous les corps.
- L'aide d'une opération mène dans le manuel directement à son entrée, et la référence nomme champs et choix comme dans la boîte de dialogue.
- Quand d'autres programmes occupent l'ordinateur, *Annuler* arrête un long calcul en moins d'une seconde au lieu de demander un redémarrage après plusieurs secondes.
- Un modèle de langage local peut faire douze étapes au lieu de huit par demande dans le chat et résout ainsi plus de demandes en plusieurs parties.
- Le panneau de sélection tient de nouveau dans sa colonne, et la colonne des cotes de l'arbre montre la cote entière, par exemple « Ø5,19 mm » au lieu de « … ».
- Sur un perçage, « Modifier l'élément » ouvre directement « Modifier le trou » avec aperçu, au lieu d'y renvoyer seulement.
- Cliquer sur « Appliquer » pendant un aperçu en cours ne calcule la modification qu'une fois. Avant, Solidon la calculait ensuite une seconde fois.
- La vue des différences hachure l'ajouté et le retiré dans deux directions, de sorte qu'on les distingue aussi sans couleur.
- Quand Solidon demande l'unité d'un fichier à l'ouverture, les cotes s'affichent dans votre unité d'affichage et avec le séparateur décimal de votre langue.
- Si vous déposez un fichier que Solidon n'ouvre pas, par exemple de Blender, il indique comment l'amener en 3MF, STEP ou STL. Le G-Code va à « Contrôler le G-Code ».

## 0.5.1

### Imprimer et transmettre au slicer

- Dans PrusaSlicer, ElegooSlicer, Bambu Studio, Creality Print et OrcaSlicer, le profil du fabricant s'applique. Solidon n'écrit que ce que vous modifiez ou acceptez des suggestions.
- Le niveau « Standard » reprend les vitesses et accélérations du fabricant au lieu de tout brider à 40 mm/s. Sur une Centauri Carbon 2, les grandes pièces prennent 40 à 50 % de temps en moins.
- Les suggestions appliquées ne valent que pour la pièce qui en a besoin : supports, brim et valeurs d'un ajustement, dans chaque slicer pris en charge. Les réglages d'impression nomment les pièces.
- Si une pièce s'imprime debout sans supports, « Orienter pour l'impression » la laisse debout plutôt que sur des supports. Un jeu de minigolf de 16 pièces tient ainsi sur un plateau au lieu de quatre.
- Pour une pièce trop grande dans tous les sens, les réglages d'impression disent avant la découpe de combien elle dépasse et proposent « Scinder le modèle » et « Réduire au volume d'impression ».
- Même si les pièces d'un modèle ne font que se toucher, « Scinder le modèle » réussit, et les connecteurs sont à l'endroit dans leurs trous à chaque jointure. Avant, le rapport y voyait des collisions.
- Solidon prend l'angle de surplomb dans le profil constructeur de votre imprimante : 60 au lieu de 45 degrés chez Elegoo, Bambu et Creality. Chanfreins et pentes douces n'ont plus de supports inutiles.
- Sur les parois extérieures rondes, Solidon propose une « Couture en biseau », dans chaque slicer pris en charge. L'impression dure ainsi 2 à 4 % de plus.
- Si votre slicer calcule lui-même le brim, comme ElegooSlicer, Bambu Studio, Creality Print et OrcaSlicer, Solidon n'en propose pas. Celui du slicer donne plus de bord aux pièces hautes.
- Les niveaux « Fin », « Brouillon » et « Résistant » choisissent désormais le processus correspondant de votre slicer, par exemple « 0.12mm Fine » pour « Fin ».
- Les réglages d'impression montrent ce qui sera imprimé : la base est le profil du fabricant, et vos propres valeurs sont marquées et se rétablissent une par une.
- Vous choisissez le plateau d'impression dans les réglages d'impression, et la température du lit suit. Si le fabricant n'autorise pas ce plateau pour votre filament, Solidon le dit avant.
- Sans « Appliquer les suggestions », aucune pièce ne reçoit plus de brim sans le demander, ni à l'export ni lors de la transmission au slicer.
- Nouvelle suggestion « Garder les canaux libres » : appliquée, elle bloque les supports dans les canaux, dans tout slicer pris en charge. La fenêtre de Cura reçoit ce blocage et les valeurs par pièce.
- Un plafond au-dessus d'un canal d'eau ou d'un tunnel n'attire plus de supports sur le modèle. Si rien d'autre n'en a besoin sur le modèle, Solidon les propose depuis le plateau uniquement.
- Les réglages d'impression affichent leurs suggestions plus vite : sur le support de perceuse, après 4,3 secondes au lieu de 7,6.
- Les projets de 0.5.0 impriment à la vitesse de votre imprimante. Ce que vous y aviez réglé vous-même est conservé.
- La vitesse de la première couche vaut désormais aussi pour son remplissage. Avant, le slicer posait le fond à la vitesse du fabricant, 105 mm/s sur la Centauri Carbon 2.
- Avec PrusaSlicer, l'impression commence désormais comme chez Prusa : avec mesure du plateau, ligne de purge et contrôle de l'imprimante.
- Le PETG part désormais vers PrusaSlicer comme PETG, et non plus comme PLA.
- Dans OrcaSlicer, chaque imprimante reçoit sa propre machine et son processus standard : la Sovol SV06 n'a plus la version High-Speed, ni la Ender-3 V3 « 0.12mm Fine ».
- Nouvelles : les Creality Ender-3 V3 SE et V3 KE. Jusqu'ici, une SE recevait les valeurs de l'Ender-3 V3, bien plus rapide.
- Les copies identiques ne sont calculées qu'une fois par « Orienter pour l'impression », qui termine le même jeu de minigolf en moins d'un tiers du temps.
- Les niveaux de qualité de la boîte de dialogue d'impression s'affichent désormais dans la langue de l'interface.
- La vitesse des déplacements à vide vient aussi de l'imprimante : la Centauri Carbon 2 se déplace à 500 au lieu de 150 mm/s, comme dans le profil d'Elegoo.
- Si vous avez mesuré le surplomb de votre imprimante, le slicer ne pose lui aussi de supports qu'à partir de cet angle, tant que hauteur de couche et largeur de cordon restent celles de la mesure.
- Le rapport calcule lui aussi désormais les surplombs avec l'angle à partir duquel votre profil de slicer ajoute des supports.
- Si un brim, un skirt ou un raft dépasse du plateau, Solidon le signale lors du transfert au slicer et propose « Disposer sur le plateau ».
- Si le slicer refuse une pièce trop haute, Solidon indique les deux hauteurs et propose « Scinder le modèle », « Réduire au volume d'impression » ou une autre imprimante.
- Si le slicer refuse une pièce qui ne tient pas sur son plateau, Solidon en donne la raison et propose « Scinder le modèle », « Réduire au volume d'impression » et « Disposer sur le plateau ».
- Si Bambu Studio reste bloqué après la découpe, Solidon reprend le fichier d'impression terminé au lieu de signaler un échec au bout de cinq minutes.
- Avec Cura, les grands modèles se découpent aussi. Avant, la découpe finissait sans fichier d'impression, par exemple pour la tour Eiffel de 313 000 triangles.
- Si Creality Print ne peut découper un 3MF que dans sa fenêtre, Solidon le dit et mène à « Ouvrir dans le slicer … ».
- Si la première couche a des passages étroits, même quelques longs sur une grande pièce, Solidon propose de la poser à 50 mm/s. Les lignes courtes adhèrent ainsi mieux.
- Solidon ne propose plus un « Temps minimal par couche » plus long que là où votre profil n'en a pas. Avant, la suggestion venait sur presque toute pièce avec un chanfrein ou une pointe.
- Là où votre slicer limite déjà la vitesse selon le débit volumique, Solidon ne propose plus de limite de vitesse propre.
- Si vous reprenez les valeurs d'un profil de filament puis changez de filament, les valeurs du nouveau s'appliquent à nouveau.
- La première couche imprime désormais des lignes aussi larges que le profil de votre imprimante, souvent 0,5 mm avec une buse de 0,4. Avec Cura, la tête ne se traîne plus entre elles.
- Avec Cura, l'impression commence désormais par le code de démarrage de votre imprimante, comme chez le fabricant. Si Cura ignore l'imprimante ou si ce code manque au fichier, Solidon le dit.
- Avec Cura, la première couche utilise désormais l'accélération du profil du fabricant au lieu de l'accélération d'impression complète.
- Les supports de Cura suivent désormais le modèle des profils d'usine : reliés, avec un toit léger et une vitesse modérée.
- Avec Cura, les parois en surplomb s'impriment désormais plus lentement, comme chez le fabricant. Les impressions avec beaucoup de surplombs durent jusqu'à 20 % de plus.
- Avec Cura, le remplissage s'imprime désormais après les parois, et les déplacements évitent les supports et rétractent le filament sur les longs trajets.
- Le profil pour la fenêtre de Cura correspond désormais à l'imprimante configurée dans Cura. Avant, Cura le refusait pour certaines imprimantes ou ne l'affichait pas.
- Les réglages d'impression ne proposent plus le débit volumique pour Cura, car Cura ne le lit pas.
- Les supports en grille arrivent au slicer comme une vraie grille, dont la direction change à chaque couche, au lieu de lignes libres qui se décalent à l'impression.
- Quand une pièce repose sur beaucoup de petits pieds, Solidon propose un brim là où votre slicer n'en calcule pas lui-même, même si les pieds réunis auraient assez de surface.
- Une bande étroite et oblique le long de la paroi extérieure ne compte plus dans le rapport comme un long pont.
- Un lettrage posé comme pièce à part tout contre une paroi ne commence plus dans le vide selon le rapport, et Solidon ne propose plus de supports pour lui.
- Le rapport n'invite plus à calibrer les tolérances de votre matériau que sur les modèles avec ajustements. Solidon ne s'en sert que là.
- La transmission à Cura passe les premières couches sans ventilateur sous forme de montée progressive. L'avertissement ne vient que si le fichier d'impression diffère vraiment.
- Après « Réduire au volume d'impression », la pièce reste posée sur le plateau. Avant, elle se soulevait, et le rapport la disait flottante.
- Si une pièce ne tient sur le plateau qu'avec une marge plus étroite, « Disposer sur le plateau » la met au milieu au lieu de dépasser du bord, et le rapport indique cette marge.
- Sur les grands modèles, « Scinder le modèle » trouve la jointure jusqu'à deux fois plus vite, et sur les modèles multicolores en une fraction du temps. La division se fait comme avant.
- Quand Solidon divise automatiquement un modèle en trois morceaux ou plus, les noms se numérotent et citent les connecteurs, par exemple « Baguette murale 2 sur 3 · Goupilles et trous ».
- Une vis, un écrou ou un joint imprimés du catalogue de blocs ne comptent plus dans le rapport comme un corps fragmenté. C'est une pièce à part, et c'est voulu.
- Les vis et écrous imprimés ont aussi du jeu sous la tête et à l'appui, et restent démontables même imprimés avec la pièce. Les projets plus anciens signalent le changement à l'ouverture.
- Avec une vis à tête fraisée du catalogue de blocs, un corps fait de faces et d'arêtes reste étanche à l'export : la pièce et la vis entrent chacune fermées dans le fichier.

### Modifier les perçages

- Un perçage avec une fraisure d'un côté et un chanfrein de l'autre se laisse incliner, déplacer et dupliquer. Avant, Solidon refusait.
- Un perçage ou une fraisure inclinés n'enlèvent plus ce qui se trouve devant leur entrée, comme une nervure ou le nid d'abeille voisin.
- Un perçage fraisé sur une face bombée se laisse déplacer, y compris par un clic dans la vue. Après déplacement, inclinaison ou suppression, l'ancien emplacement affleure la face.
- Un perçage fraisé à l'entrée arrondie sur une face plane se laisse déplacer, dupliquer et supprimer avec son arrondi. Avant, un creux restait.
- Trous borgnes, trous oblongs et élargissements sur une face inclinée, et perçages borgnes inclinés comme une poche à aimant sans lèvre, restent ouverts à l'entrée. Avant, une fine peau y restait.
- Déplacer et dupliquer avertissent quand la paroi vers le perçage voisin devient trop mince ou se rompt.
- Si un perçage sort sur le côté de la pièce après déplacement, duplication ou inclinaison, Solidon le dit aussi aux endroits en retrait. Une copie non créée est signalée.
- Un perçage déplacé ou dupliqué d'un fichier STL ne signale plus à tort, dans une plaque mince, qu'il ne traverse plus.
- Sur les nervures et dans les nids d'abeille, un perçage incliné ne signale plus à tort qu'il dépasse le bord.
- Après un déplacement, une inclinaison ou une duplication, le panneau des caractéristiques montre les cotes réelles du résultat.
- Percer, déplacer, « Modifier le trou » et l'étirement en trou oblong laissent le modèle tel quel hors du perçage. La reconnaissance qui suit finit bien plus vite sur les grands modèles.
- Si une découpe de perçage échoue en silence sur un corps fait de faces et d'arêtes, issu par exemple d'un STEP, Solidon le remarque et recalcule. Avant, un corps cassé pouvait rester.
- Sur les corps faits de faces et d'arêtes, les étapes de perçage sont prêtes en quelques secondes : sur une plaque perforée issue d'un STEP, « Modifier le trou » prend 2 secondes au lieu d'environ 120.
- Sur les corps faits de faces et d'arêtes, « Découper une poche » ne renvoie plus de corps défectueux.
- Un trou oblong se laisse raccourcir. Étiré à sa propre largeur, il redevient un perçage rond.
- La poignée au bout d'un trou oblong se saisit n'importe où dans l'ouverture, et elle ne saute plus vers le pointeur au premier mouvement.
- Les trous oblongs emportent leurs chanfreins et leur entrée oblique lors d'un déplacement ou d'une duplication. Avant, les chanfreins restaient à l'ancien emplacement.
- Une poche à aimant du catalogue de blocs se laisse déplacer, dupliquer, multiplier et supprimer, avec la lèvre qui retient l'aimant.
- Sur une poche à aimant, « Modifier le trou » avec « Inclure la fraisure, les épaulements et le rétrécissement » change le diamètre avec la lèvre. « Diamètre du trou uniquement » garde l'ouverture.
- Placée en biais par rapport à la face, l'ouverture d'une poche à aimant, d'un trou de vis ou d'un logement de roulement reste dégagée. Avant, un coin de matière la surplombait.
- Si une poche à aimant ou une suspension en trou de serrure est inclinée par rapport à la face, Solidon signale que sa lèvre ne retient que d'un côté et propose « Corriger la saisie ».
- Si un bloc comme une poche à aimant n'enlève rien à l'endroit choisi, Solidon le signale et conseille de cliquer sur la face.
- Sur une poche à aimant avec lèvre, « Étirer en trou oblong » refuse aussi sur les corps faits de faces et d'arêtes, plutôt que de trancher la lèvre.
- Quand vous posez un filetage, un insert à chaud ou un piège à écrou sur un perçage, la boîte de dialogue indique en haut la taille qui convient et présélectionne celle-là.
- Sur une fraisure, « Modifier l'élément » découpe la nouvelle cote comme si elle avait été fraisée ainsi dès le départ. Avant, Solidon refusait ou laissait une fine peau en travers du perçage.
- Quand des pièces d'un modèle s'emboîtent, Solidon les unit avant le calcul, comme elles seront imprimées. Volume et perçages sont alors justes, et le rapport le dit.
- Quand vous agrandissez un perçage, l'aperçu précis montre toute la matière enlevée, même sur les grands modèles, avec une coupe de vue et sur les corps aux canaux fermés.
- Pendant la saisie d'une cote sur une grande figure, l'aperçu grossier apparaît en moins d'une seconde au lieu de dix-neuf au plus, et l'aperçu d'un perçage y réussit.
- Si une étape sur un modèle ouvert ne calcule qu'approximativement et que le volume augmente, le rapport indique l'écart et propose « Réparer d'abord, puis recalculer ».

### Congés et chanfreins

- Le choix d'arêtes « Horizontal », « Haut » ou « Bas » ne prend plus le bord d'un perçage latéral. Pour le traiter, choisissez-le seul ; les anciens projets calculent comme enregistrés.
- Sur un modèle importé, le bord d'un perçage est arrondi ou chanfreiné aussi profondément que sur une pièce construite. Avant, avec de grands rayons, le congé restait jusqu'à un cinquième trop plat.
- Si la cote ne tient pas sur chaque arête d'un choix comme « Tous » ou « Vertical », Solidon traite celles où elle tient et montre les autres avec « Montrer l'endroit », au lieu de refuser.

### Cotes dans la vue

- D'un perçage à l'autre, les cotes dans la vue apparaissent en un tiers du temps. Le premier clic sur une caractéristique ne fige plus la fenêtre, même sur un grand modèle.
- Un clic sur un perçage ne montre plus d'images intermédiaires : le panneau de sélection et la carte des cotes apparaissent directement à leur place, sans sauter.
- Un clic sur les flèches d'un perçage sélectionné ne bloque plus la sélection : le perçage suivant se clique comme d'habitude.
- Échap sur les cotes dans la vue abandonne le brouillon et désélectionne, comme « Annuler ».
- Un clic sur « Appliquer » ne se perd plus en silence, et les cotes que vous n'avez pas saisies restent exactement telles qu'elles ont été mesurées.
- Un perçage commencé ne se perd plus en chemin : un clic dans le rapport, un changement d'outil ou Ctrl+Z demande d'abord de l'appliquer ou de l'annuler.
- Saisir une coordonnée ne fait plus disparaître les champs de cote après le deuxième chiffre.
- Sur les grands modèles, « Mesurer l'épaisseur de paroi » répond environ quatre fois plus vite.
- Un clic au milieu d'un perçage fraisé sélectionne le perçage et non sa fraisure, et les cotes nomment son arête par le côté, comme « Arête extérieure à gauche » au lieu de « Arête extérieure 4 ».
- Quand une arête ou une distance est sélectionnée, le panneau de sélection n'affiche plus « Aucun détail sélectionné … ».

### Reconnaissance

- Les caractéristiques sont reconnues d'elles-mêmes jusqu'à 1,5 million de triangles. Jusqu'à cinq millions, Solidon demande d'abord et indique la mémoire nécessaire et la durée sur votre ordinateur.
- Refusée, la reconnaissance se rattrape par « Reconnaître toutes les caractéristiques » du rapport ou en ligne de commande. Trop longue, « Charger sans reconnaissance des caractéristiques » l'omet.
- Sur les grands modèles, « Détecter les éléments à un endroit » trouve des faces là où il signalait trop de triangles. L'endroit se choisit aussi au clavier.
- Sur les grands modèles, « Détecter les éléments à un endroit » commence tout de suite à chercher. Avant, il recalculait d'abord tout le modèle, 40 secondes par essai sur le dragon du mausolée.
- Grands modèles et treillis sont reconnus bien plus vite : un lit de maison de poupée généré, 1,2 million de triangles, en 27 secondes au lieu de 174. Annuler agit en quelques secondes.
- Copies et pièces tournées ou déplacées reprennent les caractéristiques de leur original sans les rechercher. Un projet avec beaucoup de pièces identiques se calcule en moins de la moitié du temps.
- Après un perçage, la face d'un corps construit indique sa taille actuelle, et un nouveau perçage ne manque plus dans l'arbre quand un autre a été modifié avant.
- Lettrages et entretoises apparaissent dans l'arbre comme des côtés arrondis au lieu de dizaines de congés aux rayons changeants.
- Les contours faits d'arcs et de droites sont reconnus arc par arc avec leur rayon. « Convertir en faces et arêtes » est ainsi bien plus rapide.
- Un tenon épaulé ne passe plus pour un filetage. Les cylindres et les perçages que cette confusion avait avalés sont de retour.
- La lèvre d'une poche à aimant s'appelle rétrécissement dans l'arbre et nomme son ouverture. Aucune action n'en fait plus une fraisure.
- Après « Affiner les arêtes », Solidon reconnaît congés, perçages et lettrages comme sur l'original, même après un autre perçage. Des congés identiques gardent leur nom, même après « Déplacer ».
- Un motif autour d'une poignée ronde, comme un moletage sur un couvercle, garde son centre et sa direction quand vous continuez à modifier.
- Après « Diviser » et « Découper », une face divisée garde son nom sur le plus grand morceau, et les ajustements qui s'y trouvent restent valides.
- Si vous cliquez sur l'arête de bord d'un perçage couché, elle s'appelle « Vertical », comme il se tient réellement.
- Si un modèle a plus de 5 000 caractéristiques, Solidon garde les plus grandes au lieu de n'en afficher aucune. Une mise à l'échelle ne mélange pas leurs noms.
- Un bloc à une seule caractéristique porte le même nom dans l'arbre que dans l'historique, comme « Poche à aimant » au lieu de « Trou borgne 1 ».

### Importer et réparer

- Un grand modèle apparaît dans la vue dès l'import, ses caractéristiques suivent. Avant, il n'apparaissait qu'une fois la reconnaissance terminée.
- Un 3MF à plusieurs plateaux venu de Bambu Studio, OrcaSlicer ou ElegooSlicer place chaque pièce sur son plateau, à sa place. Avant, toutes arrivaient sur un seul, beaucoup hors du plateau.
- Un 3MF à plusieurs plateaux ajouté à un projet garde ses plateaux et les range après ceux qui existent.
- Un modèle supplémentaire va au premier emplacement libre des plateaux, ou sur un nouveau plateau, et y reste. Avant, il gardait les coordonnées de son fichier, souvent hors du plateau.
- Un modèle issu de « Générer un modèle » est lui aussi posé sur le plateau, au premier emplacement libre.
- Un modèle sans couleurs propres garde la couleur du corps après la fermeture de ses trous. Avant, il devenait gris, et « Convertir la texture en filaments » en tirait un filament gris.
- S'il manque à un modèle un morceau de paroi de perçage ou une partie de cône de fraisure, Solidon comble le trou par une paroi, pas par un couvercle en travers.
- Les coutures ouvertes se ferment à l'import et à la réparation sans relier des pièces qui ne font que se toucher. Un modèle intact reste inchangé.
- Les recouvrements sont désormais résolus par « Réparer » lui-même. Quand les pièces d'un modèle importé s'emboîtent, le rapport propose « Résoudre les recouvrements ».
- Une surface sans épaisseur reste ouverte et propose « Donner une épaisseur ». Une grande ouverture se montre avec « Montrer l'endroit », et « Laisser ouvert » ne laisse qu'elle ouverte.
- Après la fermeture d'une ouverture à l'import, « Montrer l'endroit » entoure toute la nouvelle face d'une couleur à part.
- Une pièce retournée à côté d'un corps creux est remise à l'endroit sans perdre la cavité. Une pièce dans la matière d'une autre est signalée au lieu d'être devinée.
- Le rapport après l'import est plus court : les constats que le résultat dément disparaissent, et là où l'on peut agir, un bouton remplace le conseil.
- La carte des défauts de maillage montre les zones saines dans la couleur du corps, pour que chaque défaut ressorte, et porte « Réparer » dans la légende. Elle sélectionne d'office un corps unique.
- La recherche de recouvrements va jusqu'au bout aussi sur les modèles aux éventails de triangles étroits. Carte des défauts et réparation voient alors tout le modèle.
- Un 3MF de PrusaSlicer ne charge plus les modificateurs, bloqueurs et renforts de supports comme matière pleine. Un volume négatif est soustrait de la pièce.
- Avec « Affiner les arêtes », toutes les caractéristiques restent, avec jusqu'à quatre fois moins de triangles : un support de perceuse à 1 mm en cinq secondes au lieu de quatorze minutes.
- Un modèle fermé reste étanche et garde ses couleurs de filament. S'il y a trop de triangles, Solidon indique une longueur d'arête qui marche vraiment.
- L'aperçu de « Affiner les arêtes » et de « Réduire les triangles » est prêt en quelques secondes au lieu de figer la fenêtre, et une longueur trop fine est refusée aussitôt.
- Si un modèle est trop fin pour « Affiner les arêtes », le rapport propose « Réduire les triangles et réessayer » avec un nombre qui fonctionne vraiment.
- Si « Lisser » risque de retourner un corps, Solidon le signale et propose « Affiner les arêtes et réessayer » avec une longueur d'arête qui fonctionne.
- Les grands assemblages s'importent plus vite : la réparation à l'import d'un bateau pirate de 1,2 million de triangles prend environ 30 % de temps en moins.
- À l'ouverture de gros fichiers 3MF, la fenêtre reste utilisable, même pendant la lecture du modèle.
- Si vous importez une copie renommée d'un fichier déjà ouvert, le corps porte le nouveau nom. Avant, il s'appelait comme le premier fichier.
- Sur les grands maillages, « Fermer la surface ouverte » calcule en quelques secondes : 1,8 au lieu de 24 secondes pour 122 752 triangles.

### Manuel et site web

- Quinze guides montrent pas à pas, avec des images de l'application, comment vérifier, imprimer et réparer un modèle, construire et diviser une pièce, y mettre du texte ou imprimer en deux couleurs.
- Le manuel commence par « Par où commencer ? » et mène de là à chaque guide. F1 dans la boîte de dialogue d'une opération ouvre son guide ou son entrée.
- Une image d'ensemble explique la fenêtre : chaque numéro de l'image désigne une zone.
- La recherche du manuel trouve la bonne page même avec des mots courants, l'affiche en premier et l'ouvre à l'endroit où figure le mot.
- La référence indique pour chaque opération où la trouver dans le menu ou dans le panneau de sélection.
- Les pages explicatives sont plus courtes d'un tiers. Quand un guide en images traite leur sujet, un lien vers lui figure en fin de page.
- Sur le site web et dans le PDF, le manuel est organisé comme dans l'application, des premiers pas à la référence. Dans le PDF, des signets mènent à chaque chapitre.

### Utilisation et système

- Les gros calculs comme l'aperçu ou « Affiner les arêtes » tournent dans un processus à part : la fenêtre reste utilisable et « Annuler » agit aussitôt. Un second processus Solidon tourne pour cela.
- Pendant le chargement et les longs calculs, une horloge compte le temps écoulé même si la progression s'arrête, et le temps restant ne saute plus quand une autre partie du calcul commence.
- La sauvegarde automatique tourne en arrière-plan et ne bloque plus la fenêtre, même avec de grands modèles. Si elle ne peut pas s'écrire, Solidon le dit.
- Un modèle sur un disque lent ou qui ne répond pas ne fige plus la fenêtre à l'ouverture.
- Si un fichier de « Ouverts récemment » a été déplacé, Solidon le dit et propose « Choisir un autre fichier ».
- Un fichier illisible n'atterrit plus dans « Ouverts récemment », et le fichier suivant n'annonce plus son nom au chargement.
- Un fichier sans modèle lisible ne reste plus comme première étape, sur laquelle chaque fichier suivant échouait avec « La chaîne s'arrête ».
- Les projets ouverts récemment sur la page d'accueil s'ouvrent en un clic.
- Quand rien n'est sélectionné, le panneau de sélection propose ce qui s'applique à tous les corps : « Orienter pour l'impression », « Disposer sur le plateau » et « Vérifier les chevauchements ».
- Après « Scinder le modèle », toutes les pièces tiennent entièrement dans la vue.
- Chaque étape arrêtée dans le rapport a un bouton : « Corriger la saisie » l'ouvre avec le curseur dans le champ concerné.
- Après « Scinder le modèle », le rapport dit en une phrase que les morceaux sont encore accolés, au lieu de plus de vingt lignes, et les lignes sur l'ancien corps n'ont plus de boutons vides.
- Un dessin tracé librement sans cote ne génère plus d'avertissement dans le rapport.
- Si le rapport ne contient que des remarques, il indique « Prête à imprimer » en haut, et une remarque de configuration n'est plus présélectionnée comme un avertissement.
- Les avertissements du rapport ont un bouton : « Montrer l'élément » sur un ajustement qui ne va pas, « Ouvrir les réglages d'impression » sur plateau, supports, buse et brim.
- Un rapport d'erreur nomme les dossiers sous votre répertoire utilisateur sans votre nom d'utilisateur, même si Solidon lui-même y est installé.
- Dans « Premiers pas », l'imprimante de votre slicer est là dès l'ouverture. Avant, la proposition arrivait après quelques secondes, et « Terminé » prenait jusque-là l'imprimante générique.
- Après l'import, la barre de titre porte le nom du modèle au lieu de « Sans titre », et « Premiers pas » nomme les slicers par leur nom et non par leur nom de fichier.
- Le slicer se choisit dans les réglages d'impression au-dessus des profils, même quand cette section est repliée.
- L'imprimante choisie dans les réglages d'impression vaut aussi pour le prochain nouveau projet. Si votre slicer est réglé sur une autre imprimante, les réglages la proposent en un clic.
- Si vous choisissez une autre imprimante ou un autre slicer, le profil de machine mémorisé du précédent ne s'applique plus.
- Dans la barre des paramètres et dans la boîte de dialogue d'une opération, un nombre saisi hors limites est refusé au lieu d'être tronqué en silence, et Solidon indique la limite.
- La question avant de supprimer une étape nomme les étapes dépendantes qui partent avec elle.
- L'historique nomme un paramètre modifié par son libellé et montre la valeur avant et après.
- La poignée d'une face sélectionnée ne montre plus que la flèche qui sert à la déplacer.
- Sans texte, « Appliquer du texte » dit que le texte manque au lieu de déclarer l'aperçu indisponible.
- Après le dessin, l'onglet d'avant revient à droite, par exemple le rapport. Jusqu'ici, le chat s'y trouvait, et « Transmettre au slicer … » était caché.
- La « Palette de commandes … » trouve les opérations dans chaque langue aussi par des mots courants, comme « copy » ou « calamita ». Jusqu'ici, elle ne les connaissait qu'en allemand.
- À l'enregistrement avec « Enregistrer la sélection comme bloc … », Solidon vérifie l'épaisseur des parois du bloc bien plus vite.
- Dans toutes les traductions, « Séparer » et « Diviser » portent désormais des noms différents, les touches ceux du clavier, et l'interface italienne tutoie partout.

### Assistant avec un modèle local

- Le choix du modèle recommande aussi un modèle plus petit pour les cartes dès 10 Go de mémoire graphique et indique pour chacun la mémoire occupée et sa réussite sur les demandes à plusieurs étapes.
- L'assistant ne reçoit en détail que les actions qui correspondent à la demande. Il reste de la place pour l'historique et la réponse, et les demandes réussissent bien plus souvent.
- Le modèle local reste chargé trois minutes après une réponse, et la question suivante n'attend plus son démarrage.
- Une réponse qui ne trouve pas de fin s'arrête après une longueur fixe et est signalée comme coupée, au lieu d'occuper la carte graphique jusqu'à la limite de dix minutes.

## 0.5.0

### Reconnaissance

- La reconnaissance sur les modèles importés est bien plus rapide : une plaque de 200 000 triangles et ses perçages sont prêts en une seconde, là où une forme libre lisse prenait des minutes.
- Les petites faces comme la pointe d'une came, les perçages coupés et les chanfreins d'entrée sont reconnus de la même façon sur un maillage et sur un corps exact.
- Les cavités fermées et les chambres d'air imbriquées sont reconnues comme un tout. Un perçage qui débouche dans une cavité n'apparaît plus comme un fantôme.
- Les filetages importés sont mesurés : pas, nombre de filets, sens droit ou gauche et diamètre nominal. Les pièces en miroir gardent le bon sens.
- Cônes, sphères et anneaux gardent leurs vraies cotes, et le panneau des caractéristiques dit d'où vient une valeur : mesurée, ajustée ou issue de l'étape.
- Une pièce en miroir, mise à l'échelle ou répétée emporte ses caractéristiques. Les caractéristiques périmées ne restent plus à côté des nouvelles.
- Les fichiers STEP à surfaces de forme libre gardent leurs perçages modifiables, même après enregistrement, réouverture et annulation.
- Après une modification, chaque caractéristique qui existe encore garde son nom. Si deux candidates entrent en jeu, Solidon demande au lieu de deviner.
- Un clic sur un perçage d'un modèle de 360 000 triangles répond en un quart du temps.
- Une fraisure qui touche deux trous oblongs à égalité reste une face conique au lieu de disparaître dans l'un des deux.
- Si un modèle se compose de plusieurs coques et qu'on ne peut pas lire avec certitude si l'une d'elles emprisonne de l'air, le rapport le dit sous forme d'avertissement.
- Un modèle fermé libère sa mémoire ; avant, quelques centaines de mégaoctets par modèle restaient occupés.
- Un modèle avec beaucoup de petites faces, comme un motif en nid d'abeille, garde ses perçages et ses congés. Avant, il n'affichait aucune caractéristique.
- Un champ de 1 400 picots est reconnu en quatre secondes au lieu de douze.

### Motifs

- Un nid d'abeille, un moletage, des nervures, des vagues ou des picots apparaissent dans l'arbre comme un seul motif avec pas, largeur de cellule et profondeur — autour d'une poignée aussi.
- Un motif se supprime d'un clic ou se repose avec un nouveau pas, une nouvelle largeur de cellule et une nouvelle profondeur. Les cellules restent où elles étaient.
- Une texture autour d'un cylindre suit la courbure : les rainures ont partout la même profondeur, et un motif sur toute la circonférence se referme sans couture. Le pas passe à la valeur qui convient.

### Dessin

- Dessiner sur une pièce choisie ne montre plus que cette pièce dans la vue ; les autres restent masquées jusqu'à ce que « Afficher les voisines » les fasse revenir.
- Extruder sur une face choisie rattache désormais le nouveau corps au lieu de s'arrêter — avant, ça ne dépassait jamais l'esquisse.
- Une poche coupe là où vous l'avez dessinée, même quand la face n'est pas centrée sur la pièce.
- Arrondir et chanfreiner un rectangle coté laisse ses cotes inchangées.
- Si vous dessinez avec plusieurs pièces choisies, Solidon demande sur laquelle ; la cible se change à tout moment dans la barre.
- Échap ne jette plus un dessin déjà commencé.
- Une esquisse déjà extrudée se réutilise pour la poche suivante, sans la redessiner.
- Un clic sur une face propose directement « Dessiner ici » et « Dessiner un trou ou une découpe ».

### Modifier sur le modèle exact

- Les corps de base sont toujours créés avec de vraies faces et arêtes. La case « Modifier faces et arêtes plus tard » a disparu ; les anciens projets se calculent sans changement.
- Perçage, trou oblong, lamage, tenon, dôme et tronc de cône restent exacts sur un corps exact quand vous les déplacez, dupliquez, tournez ou supprimez.
- Les bourrelets et les gorges se laissent déplacer, dupliquer, tourner, modifier et supprimer. Un filetage se laisse modifier et fermer.
- Un filetage reçoit sa contrepartie sur l'autre pièce d'un seul clic, à la cote du tableau et comme un seul ajustement.
- Tous les blocs de la bibliothèque se construisent exactement sur un corps exact, du vissage à la rainure d'étanchéité.
- Après un changement de rayon, Solidon arrondit la bonne arête, même quand deux arrondis sont proches.
- Si deux arêtes se trouvent au même endroit, Solidon demande laquelle vous voulez au lieu d'en prendre une.
- Appliquer attend que l'aperçu montre le résultat actuel. Un clic sur une image périmée n'écrit rien de faux.
- Les couleurs de filament restent sur les corps exacts et suivent chaque nouveau maillage.
- Le volume et l'aire d'un corps exact arrivent en millisecondes au lieu de secondes.
- Insérer un filetage prend moins d'une demi-seconde au lieu de treize au plus ; une tige filetée se construit en un tiers de seconde au lieu d'une minute.
- Unir, Soustraire et Poser sur le plateau ne demandent plus s'il faut convertir les corps exacts. Ils restent exacts.
- Quand un perçage est déplacé, aucun triangle superflu ne reste à l'ancien endroit, et une fraisure cachée ne perd rien de son volume.
- Réparer laisse un modèle propre inchangé, aussi sur le corps exact.
- La contrepartie d'un filetage se construit en arrière-plan. La fenêtre reste utilisable pendant ce temps.

### Percer et cotes dans la vue

- Un perçage cliqué montre aussitôt ses cotes dans la vue : distances aux arêtes, centre et diamètre, avec des champs numériques pour saisir.
- Les champs de cote se placent à côté de la pièce plutôt que dessus, et leurs lignes ne se croisent pas.
- La référence d'une cote, arête, centre ou axe, se change par clic droit sur la cote ou par un clic dans le modèle.
- Ce qui figure dans la vue n'est pas répété à droite dans le panneau de sélection.
- Après avoir étiré un perçage en trou oblong, les cotes restent, même si vous tournez la vue. Les boutons pour étirer se trouvent toujours au perçage choisi.
- Choisir un perçage pouvait faire tomber la vue 3D sur certaines cartes graphiques. C'est corrigé.
- Un glissement sur la poignée survit à un rafraîchissement en plein glissement, et un cran de molette au-dessus d'un champ de cote zoome la vue au lieu de modifier la cote.
- Le premier Échap pendant le choix d'une référence ne retire que le choix ; les valeurs saisies restent.
- Avec « Emmener la fraisure et les épaulements », le perçage se déplace aussi par les cotes. Fût et fraisure se déplacent ensemble, en une étape.
- Si Solidon refuse une cote, la raison s’affiche au-dessus de l’aperçu au lieu d’un simple « n’a pas pu être calculé ».
- Les champs de cote restent où ils étaient quand vous changez une valeur. La cote dont vous éditez le champ s’allume dans la vue.
- Les poignées du trou oblong agissent aussi pendant que les cotes du perçage sont dans la vue : Appliquer étire alors le trou oblong — avec un nouveau diamètre, en une étape et à la nouvelle largeur.

### Historique

- Dans l'historique, une nouvelle étape peut désormais s'insérer avant une étape existante, pas seulement s'ajouter à la fin.
- Une étape de l'historique se fait glisser à la souris vers un autre endroit, ou se déplace ligne par ligne.
- Une étape se désactive et se réactive plus tard sans être supprimée ; les étapes qui en dépendent restent en veille avec elle.
- Si une étape ultérieure fait référence à une caractéristique que le remaniement a renommée, Solidon la suit et le signale.
- Si remanier l'historique devait arrêter une étape ultérieure, Solidon refuse et ne change rien.

### Vérifier et imprimer

- Les imprimantes résine sont là : deux appareils génériques par volume d'impression figurent dans la liste, et la vôtre se crée avec taille de pixel et paroi minimale.
- Un projet résine ne reçoit plus de conseils sur la buse, le brim ou les ponts, et la paroi minimale vient du profil de l'imprimante.
- Le fichier s'ouvre dans n'importe quel programme, y compris le slicer d'un fabricant de résine dont Solidon ne connaît pas les réglages.
- Les corps exacts sont maillés aussi finement que les pixels d'une imprimante résine l'exigent ; le rapport indique la valeur.
- Les ajustements vérifient les vrais corps dans leur position de montage. L'export peut être annulé avant.
- L'écart de forme montre quelles faces d'un maillage se trouvent à quelle distance de l'original.
- Quand une épaisseur de paroi s'amincit en coin, Solidon le dit et conseille d'imprimer la paroi extérieure en premier.
- La recherche d'orientation pose une grille à bord étroit sur son bord, et une grille de courtes entretoises n'a pas besoin de supports.
- La fiche pour l'assistant dit du point choisi la même chose que le panneau des caractéristiques.
- L'écart de forme d'une boîte avec couvercle se calcule en un dixième de seconde au lieu de douze.
- Les pièces posées séparément pour l'impression ne reçoivent plus d'avertissement sur leur position de montage. L'ajustement ne signale que ce qu'il a mesuré.
- La recherche d'orientation sur un modèle de plus d'un million de triangles prend cinq secondes au lieu d'une demi-minute.
- Les très petites distances apparaissent dans la carte d'analyse en décimales, pas en puissances de dix.
- L'écart de forme sur les congés et les anneaux est aussi précis que sur les plans et les cylindres, et la carte se calcule plus vite qu'avant.
- Le ventilateur de pièce suit à nouveau la courbe du profil d'imprimante, au lieu de tourner à pleine vitesse à chaque couche.

### Importer

- Un assemblage importé se pose sur le plateau d'un seul clic, comme un tout. Les pièces gardent leur position les unes par rapport aux autres.
- Un glTF sans taille plausible n'est plus cru en mètres. Solidon demande l'unité et montre les cotes pour chaque lecture.
- Un modèle aux zones ouvertes est refermé à la lecture au lieu d'être seulement signalé : trous, faces inversées, arêtes à trois faces. Les grandes ouvertures sont nommées à part dans le rapport.
- Une pièce creuse importée peut être remplie d'une structure en treillis : Solidon détermine le volume intérieur par l'évent et indique qu'il l'a déterminé ainsi.
- Réduire les triangles ne déchire plus les modèles fermés. Là où la forme ne permet rien d'autre, le rapport indique en combien de morceaux le modèle s'est séparé.
- Réduire les triangles atteint désormais sa cible aussi sur les douilles, les anneaux et les boîtiers percés.
- Un assemblage STEP importé arrive comme des corps séparés, chacun avec son nom et ses couleurs de face, au lieu d'un tout fusionné.
- Avant de reprendre un assemblage STEP, vous choisissez les corps dont vous avez besoin ; une pièce en miroir reste un reflet.
- L'export STEP écrit les noms et les couleurs de face dans le fichier ; une pièce relue garde son nom inchangé.

### Utilisation et système

- Chaque action confirme brièvement son résultat là où vous avez cliqué, en plus de la ligne d'état.
- Une erreur du programme laisse un journal local, joint au rapport de support. Rien n'est envoyé de lui-même.
- La configuration de « Modèle à partir d'un texte » télécharge elle-même le modèle d'image manquant au lieu de vous renvoyer vers un dossier.
- Solidon démarre en deux fois moins de temps.
- Avec une caractéristique sélectionnée, l'infobulle reste, et une indication sur la poignée n'efface plus le dernier accusé.
- Si une étape de l'assistant arrête l'évaluation, la proposition la retire entièrement et montre l'état précédent.
- Déplacer ou faire pivoter un modèle de 200 000 triangles répond en une demi-seconde au lieu de huit.
- Annuler répond immédiatement au lieu de deux secondes et demie.
- Pendant que vous tapez un nombre, l'aperçu apparaît en une demi-seconde, chaque suivant en un huitième de ce temps.
- L'évidement calcule un cinquième plus vite.
- Une entrée de menu et une note discrète dans la vue mènent à un soutien volontaire de Solidon via PayPal ou GoFundMe.
- La carte du questionnaire affiche désormais les bonnes couleurs dans le thème clair aussi.

- L’application Windows et son programme d’installation sont signés numériquement. La signature confirme l’identité de l’éditeur et permet de détecter les modifications ultérieures.

## 0.4.4

### Modifier

- La dépouille atteint désormais toutes les faces verticales, même les plus étroites, et fonctionne sur les modèles importés.
- La fusion douce laisse des faces latérales lisses au lieu d’arêtes effilochées.

### Sélectionner et utiliser

- Une bobine du stock de filaments peut avoir jusqu’à quatre couleurs. Bambu Studio, OrcaSlicer et ElegooSlicer reçoivent toutes les couleurs, les autres slicers la première.
- Une arête sélectionnée n’affiche plus que les actions qui agissent sur une arête.
- Sans sélection, le chemin vers les blocs reste visible.
- Le champ de recherche n’apparaît que là où il y a quelque chose à trouver.
- Une cloison de l’organiseur mène à son éditeur de compartiments plutôt qu’aux actions de sa face.
- La boîte de dialogue pour placer un perçage indique que le point se choisit dans la vue.
- Dans la boîte de dialogue « Générer un modèle », le champ de description garde sa hauteur même quand l’avis sur le programme complémentaire manquant apparaît.

### Déplacer et vérifier

- Les suggestions d’impression arrivent bien plus vite : 2,3 millions de triangles en secondes au lieu de minutes, et rouvrir la boîte de dialogue d’impression ne remesure pas.
- Une bobine importée d’un autre type de matériau qu’aucune pièce n’utilisait arrêtait le slicer sans un mot. Désormais chaque bobine d’un plateau reçoit un profil complet.
- Si le slicer n’a pas de profil fabricant pour votre type de matériau, la boîte de dialogue d’impression le dit et prend les valeurs de Solidon, pas un profil d’un autre matériau.
- Deux corps peuvent être poussés l’un dans l’autre pour les réunir ou les fusionner en douceur. Seul ce qui sort du plateau est ramené.
- Si un ajustement renvoie à une entité qui n’existe plus, un bouton mène à l’historique.
- Orienter pour l’impression et Disposer sur le plateau séparent les filaments par plateau, pour qu’une buse ne purge pas sans cesse. Plusieurs buses se déclarent dans la boîte de dialogue d’impression.

### Stock de filament

- Une annulation dans l’historique des consommations peut être annulée à son tour, avec le même bouton.
- Modifier seulement le nom ou l’emplacement d’une bobine ne compte plus comme un nouveau relevé ; ses enregistrements restent annulables.
- Après une annulation, « Enregistrer sans demander » enregistre vraiment une nouvelle impression au lieu de dire seulement « enregistré ».
- Les dates d’achat et d’ouverture ont un calendrier dans votre langue. Une bobine refusée revient dans la boîte de dialogue au lieu de disparaître.
- L’import depuis le slicer crée une nouvelle bobine si le nom est identique mais la couleur différente, au lieu de recolorer la vôtre.
- Si le fichier du stock ne se lit plus, un bouton rappelle le dernier état : Solidon le sauvegarde lui-même à chaque écriture.
- La page de détail indique reste, date d’achat et prix ; l’identifiant à huit caractères n’apparaît que si deux bobines portent le même nom.

## 0.4.3

### Reconnaissance et modification

- Les perçages borgnes peu profonds, les petites faces et les filetages courts sont mieux reconnus. Les fonds des logements pour aimants appartiennent à leurs perçages.
- Modifiez un perçage avec sa fraisure et son entrée en conservant les cotes prévues. Le fond reste associé même après un changement important de diamètre.
- Reconnaissez des éléments à un endroit choisi sur un grand maillage et modifiez-les aussitôt. La reconnaissance et la modification s’annulent ensemble.
- La sélection et l’aperçu montrent le corps complet. Contours et étiquettes identifient la zone choisie ; les lettres inchangées restent sans taches orange.
- Les arêtes se sélectionnent sur n'importe quel corps et s'arrondissent ou se chanfreinent — aussi sur les modèles importés.
- Les perçages, cylindres et arrondis sont construits à partir des mêmes points sur Windows, macOS et Linux. Un projet est reconnu et modifié de la même façon sur chaque machine.

### Construction

- Les organisateurs proposent des cotes liées, des cloisons modifiables séparément et des cases répétées. Bac, bordure, fond et pied enrichissent la bibliothèque.
- Les champs de trous, de lumières et d’hexagones suivent une zone dessinée. Zones réservées, marges et épaisseurs minimales entre ouvertures sont respectées.
- Les colliers de profil comprennent deux coques et deux inserts ajustés. Les profils ronds, ovales ou dessinés sont possibles ; les inserts restent remplaçables.
- Un dessin fermé ou une ouverture choisie crée une rainure et un joint séparé. Matériaux, section et dépassement sont réglables ; les parois restantes sont vérifiées.
- Les motifs de surface atteignent le bord des faces et laissent les perçages libres. Les motifs existants se modifient directement depuis le panneau de sélection.
- Découper garde un côté d’un plan et ferme la face de coupe — pour des parois arrière planes et des parois à la même hauteur. Les congés le long de parois légèrement inclinées se modifient de nouveau.

### Importation et utilisation

- Choisissez visuellement les contours SVG et DXF avant de créer le corps. Les fichiers GLB et GLTF conservent leurs dimensions et leur orientation correctes.
- Les cotes du projet restent actives dans les esquisses de pièces et les aperçus de placement. Le cadrage inclut tous les plateaux d’impression visibles.
- Les filaments peuvent être retirés de l’étagère. Les premiers pas commencent par le slicer ; les retours s’ouvrent vite et préparent les pièces jointes en arrière-plan.
- Suppr sur une face retire le corps et le dit ; Ctrl+Z le ramène. En vue rasante, un corps déplacé suit le pointeur, et la face choisie reste au premier clic de l’esquisse.
- Le chat local reçoit une fenêtre plus grande et ne tronque plus votre demande.
- Le diamètre de la buse se règle sur l'imprimante. Le transfert choisit alors la machine correspondante dans le slicer, même si une autre buse y est sélectionnée.
- La réparation referme les modèles qui se touchent le long d'une arête au lieu de les ouvrir davantage.

## 0.4.2

### Dessin

- Deux clics posent un polygone régulier : d'abord le centre, puis un coin. Le nombre de coins se règle avant — de trois à douze. Un diamètre saisi reste comme cote.
- Un trou oblong naît de deux clics sur les centres de ses extrémités arrondies ; la largeur est à côté dans la barre. Les deux bouts gardent leur taille, les flancs restent droits.
- Quatre nouvelles contraintes : angle en degrés entre deux lignes, même longueur ou taille, point au milieu d'une ligne, concentrique pour deux cercles ou arcs.
- Un point déplacé reste sous le pointeur et ses voisins suivent : un coin du rectangle entraîne ses deux côtés, une ligne étire la forme. Avant, le coin ne suivait qu'en partie.
- Un rectangle tracé au clic est libre : pas de point fixe, pas de cotes tant que vous n'en saisissez pas. Une largeur ou une hauteur saisie reste une cote — comme dans Fusion.
- Les formes du menu se déplacent ; les cotes de l'entrée du menu restent. Pour modifier une cote dans la vue, double-cliquez sur sa carte.
- Congé et chanfrein dans l'éditeur d'esquisse : viser un coin, saisir un rayon ou une cote, cliquer. L'arrondi reste à son coin quand vous déplacez, le chanfrein crée une arête inclinée.
- Quand une contrainte retient un point, la ligne dit laquelle — et qu'un clic droit sur le point la retire. Avant, le point restait muet.
- Fixe veut dire fixe : un point fixé ne suit plus le déplacement. Les lignes exactement horizontales ou verticales le restent, même si vous déplacez un coin ensuite.

### Construire et modifier

- Tourner un trou oblong le tourne, au lieu d’en couper un second en travers. Et modifier un trou oblong que vous avez tiré vous-même change cette étape ; l’historique n’en reçoit pas une seconde.
- Un STL exporté après « Modifier le trou », « Déplacer l'élément » ou « Ajouter un chanfrein » sur un modèle importé arrive fermé dans le slicer. Avant, la couture s'ouvrait à la soudure.
- Si vous ne nommez qu'un axe dans le chat — « perçage à x = 20 » —, le trou ne bouge que là. Avant, il retombait à zéro sur les deux autres axes.
- Congé annonce d'avance qu'un corps exact accepte un rayon plus petit qu'un maillage, et ce qui aide alors : un rayon plus petit ou la suite sur le maillage.
- Ouvrir deux fois le même fichier donne deux noms distincts : « support » et « support 2 ». Avant, les deux corps portaient le même nom, dans l'arbre comme dans le rapport.
- Les messages qui renvoient aux valeurs à droite nomment la fenêtre telle qu'elle s'appelle : Sélection. Avant, ils disaient « panneau des caractéristiques ».
- L’étape « Réduire les triangles » le dit quand une pièce a déjà moins de triangles que le nombre saisi : il n'y a alors rien à réduire. Avant, elle restait telle quelle, sans un mot.
- L’étape « Donner une pose » sans squelette indique que les os se créent dans l'éditeur de squelette — deux clics par os. Avant, l'étape ne déplaçait rien, en silence.
- Un trou que vous déplacez, tournez, dupliquez ou modifiez le signale s’il déborde alors du bord de la pièce — comme au perçage. Avant, seul le résultat apparaissait dans l’image.
- Déplacer et dupliquer un trou avec lamage laissent le volume de la pièce inchangé. Avant, il manquait ensuite jusqu’à un millimètre cube.
- Si une étape casse une pièce en morceaux détachés, le rapport le dit — avec le retour par Ctrl+Z.

### Reconnaissance

- Une paroi courbe — le bout d’une patte, le fond d’une rainure — s’appelle désormais ainsi. Avant, il y avait « Congé » avec une arête qui n’existe pas. Le rayon se modifie.
- Un perçage avec des ergots dans sa paroi, comme la bague d’une fermeture à baïonnette, est un perçage. Avant, c’était un trou oblong aussi long que large, et chaque action aurait ôté les ergots.
- Une rainure au bord chanfreiné est une rainure ; le chanfrein en fait partie. Avant, un cadre affichait 126 lamages isolés dans l’arbre.
- Une encoche ou l’extrémité ronde d’une languette n’est plus un trou, et deux morceaux de la même paroi ronde n’en font plus qu’un dans l’arbre.
- Un morceau de cône sans bord propre s’appelle face conique. On peut l’examiner, mais pas le modifier seul — et chaque ligne le dit.
- La paroi intérieure d’une roue à rayons n’est pas un trou, et un gobelet percé au fond n’est pas un passage. Avant, « Déplacer » y coupait les rayons.
- Les grands modèles sont reconnus jusqu’à trente fois plus vite : une pièce d’horlogerie à 500 arcs prenait deux minutes, maintenant quatre secondes.

### Vue et utilisation

- Une case à cocher bascule maintenant sur toute sa ligne — un clic sur son libellé suffit. Avant, seule la petite case répondait, et « Ouvrir en haut » lors de l'évidage semblait ne pas réagir.
- Quand un aperçu ne peut rien montrer, la vue dit pourquoi — par exemple « Ce plan ne divise pas l'objet ». Si le volume ne change pas, le bandeau le dit ; si le calcul dure, aussi.
- L’étape « Diviser » commence au milieu de la pièce au lieu de sa face inférieure. Le nombre reste modifiable.
- Un outil qui ne peut rien faire sur cette pièce apparaît grisé et dit pourquoi — « Fermer une surface ouverte » sur une pièce fermée, « Séparer en pièces » sur une seule, « Treillis » sans cavité.
- Attribuer un filament montre déjà la couleur dans l'aperçu ; égaliser et subdiviser les triangles montrent le nouveau maillage avec ses arêtes. La barre d'espace ramène l'avant.
- Évider une pièce dont l'enveloppe est trouée dit maintenant que l'enveloppe est le problème et propose « Réparer et réessayer » — au lieu de signaler qu'aucun calcul n'a abouti.
- Sur l'élément choisi, ce qui ne pourrait qu'échouer y apparaît grisé — « Faire pivoter l'élément » sur un perçage fraisé — avec la raison. Et l'aperçu annonce une question à venir à l'application.
- Un champ sans effet pour la forme de base choisie n'apparaît plus grisé dans le dialogue — il apparaît avec la forme qui en a besoin. Un rectangle montre quatre champs devant au lieu de huit.
- À 150 ou 200 pour cent de mise à l'échelle, l'aimantation, les poignées et les repères portent de nouveau comme à 100 pour cent. La poignée est en taille réelle et un clic tremblant reste un clic.
- Sur un grand modèle, l'aperçu arrive en moins d'une seconde au lieu de plusieurs : Solidon le calcule plus grossièrement et écrit « Aperçu grossier ». L'application reste exacte.
- L’étape « Séparer selon une ligne dessinée » commence au milieu de la pièce et non sous elle, comme « Séparer ». Auparavant, l'aperçu montrait seulement que le plan ne sépare rien.
- L’étape « Aligner sur une caractéristique » vous demande maintenant de choisir la deuxième caractéristique au lieu de vous expliquer une notation.
- Le démarrage n'attend plus la carte graphique : elle est recherchée pendant que la fenêtre se construit. Sur les machines qui mettaient longtemps, le programme restait figé plusieurs secondes.
- Ce qui n’est pas possible sur un élément apparaît en gris avec la raison — la phrase même que l’opération aurait dite après le clic. Les phrases sont devenues plus courtes.

### Fichiers et export

- Un 3MF issu du slicer s’ouvre désormais même si ses couleurs ne se lisent pas sans ambiguïté : le modèle arrive en une seule couleur, et le rapport dit pourquoi. Avant, le fichier restait fermé.
- Les faces peintes dans Bambu Studio, Orca et Elegoo arrivent exactement telles qu’elles ont été peintes — même lorsqu’une couleur traverse un triangle. Avant, cela comptait comme « ambigu ».
- Un relief de texte du slicer Elegoo ou de Bambu Studio dans le fichier bloquait l’import. Le fichier s’ouvre maintenant.
- Les modificateurs et bloqueurs de supports du slicer n’apparaissent plus comme des corps, et un évidement (« pièce négative ») est soustrait — comme dans le slicer.

### Blocs et ajustements

- Un bloc destiné à un perçage — insert thermique, logement d’écrou, siège de roulement, filetage, vis — se pose directement dans le perçage choisi, et non au centre de la face.
- Faites glisser un bloc par sa poignée dans la vue et c’est tout le bloc qui bouge, même saisi par un bord du trou de serrure. Avant, seule cette caractéristique se déplaçait.
- Crochets et trous d’un bloc apparaissent à droite comme un nombre, non plus comme « 2,00 mm ». Après « Modifier les cotes », le bloc reste sélectionné, même avec d’autres caractéristiques.

## 0.4.1

### Construire et modifier

- Les congés et les chanfreins fonctionnent maintenant aussi sur un modèle importé : on choisit une arête dans la vue et on indique un rayon ou une largeur. Avant, il fallait un corps dessiné soi-même.
- Décaler la face et la dépouille fonctionnent eux aussi sur un modèle importé, et on peut y modifier ou retirer un arrondi reconnu.
- Décaler la face déplace la face sur laquelle on a cliqué. Sur un escalier, les autres marches restent en place au lieu de bouger toutes ensemble.
- Le cercle de perçage et la grille de trous sont des formes à part entière au dessin, avec leurs cotes : nombre, cercle primitif, diamètre. Avant, c'était six cercles à la main.
- Nouveau : « Ajouter un bourrelet », une baguette ronde le long des arêtes choisies — bourrelet à l'extérieur, cordon d'angle dans un angle rentrant. Un corps exact devient alors un maillage.
- Une arête se choisit maintenant dans la vue : premier clic le corps, puis l'arête. Longueur et boutons Congé et Chanfrein sont à droite. Avant, il fallait la reconnaître dans une liste.
- Sur un tube, le bord intérieur et le bord extérieur se raccordent ou se chanfreinent séparément. Avant, les deux portaient le même nom, et la modification touchait l'un des deux.
- La dépouille laisse la face d'appui en place, même si la pièce ne repose pas à la hauteur zéro. Avant, une pièce surélevée était aussi amincie par le bas.
- Balayer le long d'un chemin commence avec la bonne section et garde les ouvertures du contour — un anneau reste un tube, au lieu de partir déformé et de se remplir à l'intérieur.
- Une paire de contreparties insérée compte comme une modification : elle est enregistrée avec le projet et fait l'objet de la question à la fermeture. Avant, elle pouvait se perdre en silence.
- Le cadenas à côté d'une cote fixée dans l'éditeur d'esquisse est maintenant un symbole dessiné avec une explication. Sur certains ordinateurs, il y avait là un petit carré.

### Percer et placer

- Au moment de placer un perçage, une case en fait un trou oblong : vous saisissez la longueur et la direction, et l'aperçu montre les deux.
- Un perçage déjà présent dans le modèle s'étire après coup en trou oblong — le diamètre reste tel qu'il a été mesuré.
- Le trou oblong est élargi de la tolérance du matériau sur toute sa longueur. La course dont dispose une vis reste celle que vous avez saisie.
- Si un trou oblong dépasse le bord à une extrémité, Solidon le signale, même quand son centre se trouve au cœur de la matière.
- Un trou oblong figure dans l'arbre des objets en tant que tel, avec sa largeur et sa longueur — y compris dans un modèle que vous avez ouvert et que quelqu'un d'autre a dessiné.
- Un trou oblong existant s'étire ensuite en longueur, et sa direction reste là où elle était.
- Un perçage ou un trou oblong sélectionné se règle directement dans la vue avec « Régler dans la vue » : une poignée pour déplacer et tourner, des boutons pour étirer, des cotes aux arêtes et centres.
- Seul « Appliquer », à droite, en fait une étape ; Échap annule. Un trou oblong étiré affiche sa longueur et garde sa forme quand vous le déplacez par la poignée.
- Un champ de coordonnée vide signifie désormais « laisse le trou où il est ». On peut ainsi en placer un au centre de la pièce, le seul endroit qu'il n'atteignait pas.
- Un perçage se déplace avec « Modifier le trou » maintenant aussi sur le corps exact, et sur le maillage il bouge vraiment. S'il passe le bord, Solidon dit qu'il n'est plus un trou.
- La largeur d'un trou oblong se modifie avec « Modifier le trou ». La course dont dispose la vis reste.
- Si un perçage ou un trou oblong traverse la pièce de part en part, si bien qu'elle tombe en morceaux, le rapport le dit — et non seulement que le trou dépasse le bord.

### Reconnaissance

- Un fraisage au-dessus d'un perçage est conservé même sur une pièce aux surfaces rondes et galbées. Auparavant il disparaissait, avec lui le déplacement commun des deux.
- Une cavité entièrement dans la matière, sans issue, figure dans l'arborescence comme poche d'air, avec son volume. Auparavant, elle y figurait comme un perçage qui n'existait pas.
- Sur un modèle très courbé, Solidon dit maintenant ce qui a été mesuré au lieu de parler d'un scan, et quelles formes sont laissées de côté sur une telle surface.
- La reconnaissance des caractéristiques sur de grands modèles de forme organique est environ un quart plus rapide. Elle trouve la même chose qu'avant.
- S'il reste entre un perçage et la paroi autour de lui moins de matière que la vôtre n'en supporte, le rapport le dit, mesuré sur la pièce finie.
- La carte des défauts de maillage marque aussi les faces qui se traversent. Avant, elle ne voyait que les arêtes ouvertes et ramifiées et déclarait un tel modèle sain.
- L'analyse par couches d'une pièce finement moletée prend deux fois moins de temps ; les endroits signalés restent les mêmes.
- Qu'un pont soit jugé trop long dépend maintenant de votre buse : deux lignes d'une buse de 0,4 font 0,84 mm, pas un millimètre rond. Les changements plus petits ne s'affichent plus en « +0,00 cm³ ».
- La reconnaissance des filetages ne demande plus qu'une fraction de la mémoire et peut être interrompue.
- Si un corps ne peut pas être séparé à cause d'un maillage ouvert, la réparation figure comme bouton sur le constat.
- Si une coupe ne peut pas être refermée, Solidon dit que le modèle n'est pas fermé — et comment continuer — au lieu de montrer la coupe.

### Inscrire

- Une inscription dispose désormais de huit polices au lieu de trois, plus gras et italique. Le gras porte des traits plus épais à hauteur égale et reste lisible là où le style normal bave.
- À côté des polices droites, il y a maintenant une ronde et une manuscrite, toutes deux en un seul style. Les huit voyagent avec le programme : un projet a partout la même apparence.
- Si une police est trop fine pour votre buse, Solidon indique à partir de quelle hauteur elle tient, au lieu de l'imprimer et de laisser les lettres se boucher.
- Les côtés arrondis d'une lettre — l'arc du D, le contour du o — figurent maintenant dans l'arbre des objets comme les droits et acceptent leur propre filament. Avant, ils y manquaient.

### Blocs et ajustements

- Un bloc du catalogue apparaît aussitôt dans la vue : sur la face sélectionnée ou sur le dessus du corps, avec cotes et poignée. Un clic le place ailleurs, « Appliquer » l'insère.
- Si vous séparez en pièces distinctes un corps portant un ajustement, Solidon demande quelle pièce l'ajustement vise désormais — au lieu de vous renvoyer à l'annulation des étapes.
- L'insert M2,5 reçoit son trou de montage selon la fiche technique : 4,0 mm au lieu de 3,6. Un projet plus ancien avec cet insert dit à l'ouverture que la cote a changé.
- L'avertissement sur un bras de clip qui casse tient compte du sens d'impression défavorable : un bras qui fléchit en travers des couches porte moins, et cela figure maintenant dans la phrase.
- Le générateur de variantes grave sur chaque pièce sa valeur sur le dessus. Si une pièce est trop petite pour un nombre lisible, le rapport le dit et donne l'ordre sur le plateau.

### Vue et utilisation

- Les actions pour un corps ou une entité sélectionnés sont à droite, en groupes pliables, avec recherche. Les menus Objet, Modifier et Préparer disparaissent ; les raccourcis restent.
- Le clic droit sur un corps ou une face ne montre que ce qui n'existe que là : l'étape derrière, l'esquisse sur la face, le masquage. Le bouton « Blocs » est en couleur d'accent.
- Si la chaîne s'arrête à une étape, les actions sont verrouillées et en donnent la raison ; essayer affiche les issues du rapport. Avant, l'étape restait en silence derrière, jamais calculée.
- Le sélecteur de plateaux de l'en-tête se trouve à côté du nom de l'imprimante, plus par-dessus — même quand les plateaux n'arrivent qu'avec le projet ouvert.
- Le rapport regroupe les messages identiques en une ligne, le nombre entre parenthèses devant. Un clic sélectionne toutes les pièces concernées ; une action demande auxquelles s'appliquer.
- La colonne de droite avec le rapport, le chat et la visite est un peu plus étroite ; la place revient au modèle.
- Pendant la mesure, la vue passe en projection droite et y revient ensuite. En perspective, on vise à côté, d'autant plus que le trait est loin du centre de l'image.
- Qui se contente de regarder un modèle n'est plus interrogé sur l'enregistrement en fermant. En échange, les fichiers importés figurent sous « Ouverts récemment ».
- Si l'on pousse un corps au-delà du bord du plateau avec la poignée, Solidon le ramène à une place libre. Une valeur saisie est exécutée telle quelle.
- Le choix de la langue dans les réglages prend effet aussitôt ; les autres saisies restent, Annuler rétablit la langue. Cela vaut aussi pour la première configuration, qu'un changement ne ferme plus.
- Après un quart d'heure de travail, Solidon demande une fois par version votre retour. On répond ou on ferme : dans cette version, la question ne revient pas.
- Si la souris 3D est bloquée, Solidon indique le chemin pour l'autoriser au lieu de l'ignorer en silence.
- Le chemin vers l'imprimante s'appelle dans le menu « Préparer l'impression … » au lieu de « Réglages d'impression … ». La boîte de dialogue derrière est la même.
- La touche Entrée dans un champ de cote à droite applique l'étape, et la touche Tab parcourt les champs de haut en bas.
- La palette de commandes présélectionne la meilleure correspondance, et non la première exécutable. « Cong » puis Entrée créaient avant un pavé.
- Si vous tirez un corps à la souris, il reste au pointeur même au-dessus du fond vide, au lieu de s'arrêter et de sauter dès que quelque chose se retrouve dessous.
- Après l'ouverture d'un projet aussi, le premier clic dans le modèle ne saccade plus ; la préparation se fait dès que les corps sont en place.
- Les mouvements fins de la molette — pavé tactile, souris haute résolution — zooment maintenant au lieu de se perdre.
- Le vol avec la touche Ctrl enfoncée s'arrête dès que vous relâchez la touche. Avant, la vue continuait de voler.
- À une mise à l'échelle élevée de l'écran, vous atteignez les poignées aussi facilement qu'à 100 %.
- Après un changement de constat, des boutons du rapport apparaissaient un instant comme de petites fenêtres à part. C'est terminé.
- Le contour de couche d'une pièce sur le second plateau se trouve sur cette pièce, pas à côté de la première.
- Sur l'écran d'accueil ne restent que les menus qui y font quelque chose.
- Un second bloc du même type — un second couvercle à vis, par exemple — reçoit un numéro au lieu de porter le nom du premier.

### Fichiers et export

- Avant d'écrire, l'export montre ce que le rapport a trouvé : une paroi mince, un ajustement non respecté. C'est vous qui décidez si le fichier est écrit malgré tout.
- Solidon retient le dossier, le format et le schéma de nom par projet. Si plusieurs fichiers sont écrits, le motif de nom figure dans le champ et se modifie.
- À la lecture d'un modèle, la progression reste affichée jusqu'à ce qu'il soit vraiment là, et l'affichage dit « Lecture du modèle » au lieu de « Chargement du projet ». Annuler reste accessible.
- Une question répondue sur la caractéristique que vise une étape reste répondue — même après la fermeture et la réouverture du projet.
- Si le fichier lié d'un projet n'est pas accessible, le projet s'enregistre et s'ouvre quand même ; le rapport nomme la source. Si les droits manquent, Solidon le dit au lieu de le déclarer endommagé.

### Plateau et transmission

- Si un corps fait de pièces détachées — un lettrage, par exemple — ne tient entier sur aucun plateau, le rapport propose de le séparer et de l'orienter : un clic, et les pièces sont sur les plateaux.
- Ouvrir dans le slicer transmet à ElegooSlicer, Orca et Bambu Studio tous les plateaux dans un seul fichier — une fenêtre au lieu d'une par plateau.
- Pour la séparation, le lettrage et la texture, le rapport donne le nombre dans la phrase, là où un espace réservé entre accolades figurait avant.
- Un lettrage auquel vous avez attribué un filament le garde quand il est séparé en lettres. Avant, il arrivait dans le slicer sur un second filament gris, celui attribué restant inutilisé à côté.
- Avec plusieurs plateaux, les pièces arrivent dans le slicer là où il place ses plateaux : dans la grille qu'il dispose lui-même. Avant, les lettres du troisième et du quatrième restaient à côté.
- S'il reste une bobine inutilisée au découpage, Solidon le dit avec son nom. Avant, le slicer annonçait une réussite et un filament manquait à l'impression.
- Si un slicer se ferme brutalement, Solidon le dit tel quel. Avant, il était dit qu'aucun fichier n'avait été écrit.
- Creality Print est reconnu comme slicer et se choisit dans la boîte d'impression, avec ses imprimantes, ses procédés et ses filaments.
- La boîte d'impression s'ouvre aussitôt avec le slicer choisi en dernier ; la recherche des autres tourne en arrière-plan. Avant, le clic sur Imprimer pouvait ne rien montrer pendant dix secondes.
- Le choix du slicer montre tous les programmes installés — un second Flatpak ou un second AppImage aussi. Avant, le second manquait à chaque emplacement.
- Un filament d'un lot de fabricant PrusaSlicer arrive dans la transmission avec ses propres valeurs, pas avec celles du premier filament du fichier.
- À la transmission en STL — vers Cura, par exemple — Solidon dit que les réglages par pièce ne voyagent pas, et donne la proposition pour tout le plateau, au lieu d'affirmer qu'ils sont appliqués.

### Filaments et stock

- Le stock de filament s'enregistre aussi sur une clé FAT32, un disque exFAT ou un partage réseau. Avant, chaque enregistrement y échouait.
- Si le stock ne peut pas être lu, Solidon le dit aussi dans le sélecteur de filament, avec le bouton « Réessayer » — au lieu d'une liste vide.
- La consommation mesurée dans le fichier d'impression compte aussi la matière poussée sans trajet, et ne compte pas les rétractions deux fois. Si le slicer écrit la quantité, son chiffre vaut.
- Qui choisit « Ne pas enregistrer » au décompte n'est plus interrogé pour cette sortie ; elle reste accessible sous « Non enregistré ».
- Si vous créez une nouvelle bobine au moment de décompter la consommation, les bobines choisies, les quantités saisies et les répartitions restent en place.
- L'arbre des objets ne montre sur un corps et une face que les filaments qui s'y trouvent vraiment — une face avec son propre filament porte le sien, pas la liste de tout le corps.
- Annuler pendant la recherche de profils de filament agit aussitôt.

### Chat et IA

- Avant la première requête à un générateur de modèles, Solidon dit quelles données y partent.
- Si un autre calcul occupe la carte graphique, le chat attend visiblement au lieu de rester figé.

### Mise à jour, installation et système

- Les paquets Mac sont signés et notarisés. Le détour par « Confidentialité et sécurité » → « Ouvrir quand même » disparaît.
- Sous « Soutenir Solidon », GoFundMe est maintenant proposé à côté de PayPal ; seul votre clic ouvre le navigateur, et sans navigateur l'adresse se copie.
- Si votre code d'achat se trouve sur un lecteur dont les droits de fichier ne peuvent pas être définis — FAT, partage réseau —, il reste lisible. Avant, il y passait pour absent.

## 0.4.0

### Construire et modifier

- Les contreparties, comme un goujon et son perçage, se posent sur les deux pièces en une seule étape. Les cotes communes se saisissent une fois et une seule annulation retire la paire.
- Le lissage entre deux contours accepte désormais deux dessins distincts : rond en bas, anguleux en haut. C'est ainsi que naît l'adaptateur d'un tube vers une goulotte.
- Le balayage le long d'un chemin suit un tracé dessiné à plusieurs coins et arcs, et non plus un seul arc régulier. Aux angles vifs, Solidon coupe en onglet.
- Le congé et le chanfrein s'appliquent aussi à une seule arête. Vous la choisissez dans une liste qui donne chaque arête avec sa position et sa longueur.
- Un bloc va à plusieurs endroits en une étape : quatre perçages reçoivent ensemble leurs inserts, et une seule annulation retire les quatre.
- Nouveau : *Vérifier le chemin d'assemblage* amène une pièce à sa position finale et signale où elle bute en route, même si les deux s'emboîtent à l'arrivée.
- Chaque bloc peut être écrit en source OpenSCAD, depuis le catalogue ou depuis la ligne de commande.
- Le noyau exact perce aussi une face inclinée, avec fraisage et lamage ; les motifs et les assemblages emboîtés sont conservés.

### Percer et placer

- Lors de la pose d'un perçage, l'aperçu montre le contour de l'entrée au lieu d'un cylindre semi-transparent. L'endroit qui compte reste dégagé.
- L'aperçu suit la souris avec fluidité : la recherche de la face sous le pointeur ne recommence plus à chaque mouvement.
- Les champs de cote s'écartent de l'endroit où naît le perçage, au lieu de se poser dessus.
- Choisir une opération qui se place dans le modèle lance le placement aussitôt ; le bouton d'avant disparaît.
- Après avoir validé les cotes, vous réglez la profondeur à la souris. Le modèle devient translucide et la vue pivote de côté pour que vous puissiez regarder dans le trou.
- Pendant le glissement, la profondeur s'accroche brièvement aux endroits qui veulent dire quelque chose : le milieu de la matière et sa face arrière.
- Le pavé, la sphère et les autres corps de base se déplacent et tournent déjà dans l'aperçu, avec la même poignée que sur un corps terminé.
- Les corps de base ont reçu un angle de rotation : la direction dit où pointe le corps, l'angle dit comment il est tourné autour d'elle.
- Percer dans un cylindre, une sphère ou un tore ne déclenche plus à chaque perçage l'avertissement qu'il déborde du bord.
- Un perçage avec fraisage est retiré en entier après confirmation, au lieu de laisser le fraisage sans retour possible.

### Caractéristiques et sélection

- Un perçage sur lequel vous cliquez ne propose plus que les actions qui y font quelque chose ; le texte et l'affectation de filament s'y trouvaient aussi.
- Chaque action sur une caractéristique apparaît une fois et non deux, et l'en-tête de bloc au-dessus d'une seule ligne disparaît.
- Sur un fraisage existant, *Fraiser* est de nouveau accessible.
- Dans l'arbre des objets, les caractéristiques de même nature ne sont regroupées que si leur cote concorde aussi. Dix congés de rayons différents figurent de nouveau séparément.
- Un corps avec filament affecté montre de nouveau sa sélection à l'image, au lieu de rester gris comme les autres.
- Les champs d'une caractéristique portent leur nom : un lecteur d'écran dit à quoi appartient un champ, au lieu de répéter six fois champ rotatif, 0,00.

### Blocs et ajustements

- Vos propres blocs s'ouvrent de nouveau depuis le catalogue pour être modifiés, même si le projet dont ils viennent n'existe plus.
- L'échelle de tolérances reprend la cote mesurée du perçage sur lequel vous l'ouvrez, au lieu d'une valeur fixe de 6 mm.
- Les crochets et les languettes élastiques calculent avec la matière et la course du ressort, non avec une règle empirique. Solidon signale un bras qui casse au premier encliquetage.
- Les trois corps d'étalonnage naissent sans corps auxiliaire, et l'échelle de tolérances s'imprime en deux réglettes numérotées qui s'emboîtent.
- L'avertissement du ressort mesure le bras réel, la charnière souple bouge, et le serre-câble va jusque dans l'aperçu et la sortie.
- Un bloc dépose de la matière porteuse avant de couper là où c'est nécessaire ; et leur aperçu se pose correctement même sans support.
- Un bloc explique quelle combinaison de cotes il ne peut pas construire, au lieu de les rogner en silence.

### Filaments et stock

- Votre stock de filament a sa propre place : une tuile sur la page d'accueil et une étagère au lieu d'une liste, avec le niveau dessiné comme un enroulement sur la bobine.
- Deux bobines de même nom restent distinctes. Chacune porte son propre reste, et c'est celle qui est entamée qui compte.
- Au tranchage et à la remise, Solidon demande s'il doit décompter la consommation. Après le tranchage, c'est la quantité mesurée dans le fichier d'impression, sinon une estimation.
- Chaque écriture est annulable, chaque bobine tient son historique, et seul celui qui le règle expressément décompte sans qu'on lui demande.
- Un filament affecté peut être retiré sans que les faces voisines y perdent le leur.
- Une face peinte arrive dans Orca et PrusaSlicer avec son filament, et non plus sans.
- Après un retrait, le profil du fabricant n'atterrit plus sur le mauvais filament.
- Sur l'étagère, la recherche et les actions principales sont réunies, et le lieu de rangement et la charge nominale figurent dans la boîte de dialogue de la bobine.

### Impression et préparation

- Solidon trouve ce que possède Cura : imprimantes, profils de processus et filaments qui restaient invisibles.
- De PrusaSlicer, Solidon reprend les filaments chargés et la dernière imprimante réglée.
- Si votre slicer ne connaît pas du tout l'imprimante, Solidon le dit, au lieu de vous envoyer vers une liste où il n'y a rien.
- Changer de niveau de qualité prend des secondes et non près d'une minute, et la fenêtre reste utilisable pendant ce temps.
- Le conseil sur les réglages d'impression regarde tous les corps du plateau et non la seule sélection. Ce dont un corps a besoin est conservé, même si le voisin s'en passe.
- Il calcule en arrière-plan, nomme le corps, montre sa progression et peut être interrompu.
- Un long pont est jugé sur ses appuis réels, et l'angle de surplomb vaut pour l'imprimante, la buse, la hauteur de couche et la largeur de ligne sous lesquelles il a été mesuré.
- Une vitesse trop élevée est limitée sur le type de trajet concerné, au lieu de chauffer toujours plus la buse et le plateau.
- Les propositions décochées restent décochées, et un changement de filament, de scène, de plateau ou de qualité invalide aussitôt un résultat périmé.
- L'écart lors de la disposition compte la bordure d'adhérence et la structure de support : entre deux voisins, les deux comptent double.
- Les pièces sont disposées au milieu du plateau, comme le font les slicers d'à côté, et non dans le coin arrière gauche.
- Orienter pour l'impression redispose ensuite les pièces tournées. Un corps qui se couche prend plus de surface et finissait avant dans son voisin.
- Le second choix de filament sous les profils du slicer a disparu. Il répétait le sélecteur de filament ; récupérer les valeurs du profil est maintenant un bouton à part.
- Orienter pour l'impression prend tous les corps de la scène, pas seulement les sélectionnés. Le plateau entier se place ensuite au centre, au lieu qu'une pièce tournée en contourne une autre.

### Vue et utilisation

- Le pointeur de souris de Solidon vaut pour toute la fenêtre et pour chaque boîte de dialogue, et non plus seulement pour la vue 3D.
- Changer de variante dans une boîte de dialogue d'opération ne quitte plus l'application.
- Une boîte de dialogue d'opération ouverte ne survit plus sans bruit à un changement de projet.
- Les notes longues ne sont plus coupées alors que la place reste libre à côté.
- Depuis la ligne de commande, *Affecter un filament* ne pouvait pas être appelé ; c'est possible maintenant.
- Le premier clic et la première rotation ne saccadent plus : ce que la vue doit préparer pour eux se fait désormais au démarrage.

### Mise à jour, installation et système

- Sous *Nouveautés* figurent les trois dernières versions. L'historique complet de toutes les versions se trouve sur solidon3d.de et y reste consultable.

### Manuel et site web

- Les images de solidon3d.de montrent le modèle sur toute la largeur, et non comme une bande entre les panneaux.
- Le manuel et le site web nomment toutes les opérations existantes, y compris les nouveaux éditeurs de caractéristiques.

## 0.3.5

### Vue

- La vue 3D dessine avec une nouvelle couche graphique. Elle adresse la carte graphique via Direct3D 12, Vulkan ou Metal et reste fluide même à plusieurs millions de triangles.
- Les creux et les arêtes ressortent davantage : la vue assombrit les coins, trace des lignes de profondeur et atteint le point que vous désignez.
- Les arêtes des corps forment un fin maillage au-dessus de la surface, et les étiquettes restent immobiles au lieu de trembler pendant la rotation.
- Les noms des caractéristiques ne se chevauchent plus, et leurs marques restent visibles même dans la coupe.
- L'indicateur d'axes en bas à gauche remplit son champ dans toutes les directions de vue, et ses lettres sont entièrement visibles.
- Les vues fixes font tourner la caméra autour du point que vous regardez. Votre cadrage est conservé au lieu de revenir à la scène entière ; le cadrage reste l'affaire d'*Ajuster à la vue*.
- Viser à travers une ouverture la face située derrière sélectionne cette face et non le bord de l'ouverture.
- Les grands modèles se construisent plus vite, car arêtes et normales ne sont calculées qu'une fois par corps.
- Si la machine n'a pas le support graphique dont la vue a besoin, l'application nomme les deux paquets à installer.
- Inclinez la vue près d'un axe : elle s'y aligne en conservant votre rotation, au lieu de sauter vers une position figée.

### Actions pour la sélection

- Le rapport de contrôle et le chat se terminent à droite par leur propre bord. Les actions pour la sélection se trouvent en dessous dans une carte distincte, et le modèle apparaît entre les deux.
- Les actions mises en avant dépendent de la sélection : avec plusieurs corps Réunir, Soustraire et Intersection, avec un seul Percer un trou, Évidement et Séparer.
- Sur un perçage sélectionné apparaissent Fraiser et Reboucher un perçage ; sur une face, Percer un trou, Découper une poche et Décaler la face.
- Un corps sélectionné affiche ses filaments sur place et permet de les changer.
- Un champ de recherche dans la même carte trouve les autres opérations ; les caractéristiques et les pièces restent dans leurs propres zones.
- La colonne de droite est plus large : les actions pour la sélection tiennent entièrement, au lieu de se serrer sur une demi-largeur.

### Construire et modifier

- Réunir, Soustraire et Couper prennent tous les corps sélectionnés à la fois, et non exactement deux.
- Le congé n'emporte plus l'application quand le rayon dépasse la paroi qu'il doit arrondir.
- Un corps du noyau exact reste exact si vous ne faites que le déplacer ou le tourner. Congés et chanfreins restent possibles ensuite.
- L'outil de perçage ne dépasse plus qu'à l'entrée du trou et refuse les diamètres qui dépassent la pièce de plusieurs fois.
- Aligner à fleur veut dire à fleur à un angle près, et non à une seule distance de point près.
- Réduire les triangles s'arrête à une résolution nommée, et le remplissage en treillis n'invente plus un intérieur qui n'existe pas.
- L'éditeur d'esquisse atteint les arcs sur le cercle entier, trouve les bords de cercle, supprime l'élément choisi avec Suppr et ne laisse pas Rétablir en attente.
- Le retour pendant le sculptage ne déclare plus les petites modifications sans effet.
- Les interrupteurs d'une opération actifs par défaut peuvent désormais aussi être désactivés en ligne de commande.
- Une erreur dans une opération nomme sa cause : dans le journal, dans la ligne qui l'a arrêtée et dans le rapport d'erreur.
- Les saisies refusées dans le placement, le stockage de maillages et les recettes arrivent avec une proposition d'action au lieu d'une erreur nue.
- Les pièces expliquent quelles combinaisons de paramètres elles ne construisent pas, au lieu de rogner les cotes en silence.
- Un nombre inadapté de corps sélectionnés est signalé avant le calcul, au lieu d'écarter une entrée sans que cela se voie.
- Poser sur une surface ne modifie le document qu'à la validation ; un aperçu abandonné ne laisse rien derrière lui.
- Les lettres et les chiffres restent dans le champ de saisie — les touches de navigation n'agissent que lorsque vous n'y tapez pas.
- Séparer en pièces distinctes fait de plusieurs corps détachés d'un fichier un objet chacun — ce qui ne se touche pas n'est pas une seule pièce.

### Caractéristiques

- Un scan importé ne porte plus de dômes ni de cupules inventés ; jusqu'ici ils naissaient par centaines de surfaces arrondies en douceur.
- Plusieurs filetages sur une plaque sont nommés séparément au lieu d'être réunis en une seule caractéristique.
- Sphère, tore et cône déclarent leur courbure, les centres de cylindre correspondent à leurs anneaux d'extrémité, et les pas de filetage suivent l'axe.
- Le panneau des caractéristiques ne propose des ajustements que lorsqu'un second corps est sélectionné, et il connaît chaque groupe du noyau.
- Les ajustements de coupe automatiques ne distribuent plus deux fois le même nom.
- La détection des caractéristiques atteint le même résultat plus vite sur les maillages complexes.

### Impression et préparation

- La recherche d'orientation juge en deux étapes : deux cents poses issues des normales, dont neuf dans l'analyse par couches.
- Sa barre de progression va jusqu'au bout, même quand il n'y avait rien à couper.
- Le slicer reçoit le monde de l'imprimante et non celui de Solidon, et un profil propre conserve sa base constructeur.
- Les profils de tranchage propres passent avant le profil constructeur du même nom, et un AppImage retrouve son stock.
- Le nettoyage après l'import conserve les affectations de filament.
- L'imprimante appartient au projet et se change aussi bien dans l'en-tête que dans la boîte d'impression ; les filaments attribués, les couleurs et vos propres valeurs d'impression sont conservés.
- Chaque corps porte son filament dans l'arborescence : une pastille de couleur devant le nom, un clic pour en attribuer un autre.
- Plusieurs bobines du même type de matériau restent distinguables par leur nom et leur couleur.
- Les opérations correspondantes portent le nom de ce qu'elles font : *Attribuer un filament* et *Filament sur une face* au lieu de *Colorer la pièce* et *Colorer la face*.
- La remise au slicer résout chaque bobine selon son propre type de matériau ; vos propres valeurs d'impression gardent la priorité.
- Si la carte des supports prend trop de temps, le calcul se termine avec une explication et propose de réduire les triangles.
- La boîte d'impression reste entièrement utilisable même dans des fenêtres étroites.
- Orienter pour l'impression aligne tous les corps sélectionnés, et pas seulement le premier.

### Fichiers et projets

- Un 3MF comportant de nombreux niveaux de duplication est refusé avant que 432 octets ne deviennent mille corps.
- Un petit fichier de projet ne réclame plus des gigaoctets de mémoire.
- Un fichier GLB en millimètres arrive en millimètres et non en mètres.
- Un enregistrement raté n'emporte plus la dernière sauvegarde, et annuler annule vraiment l'import.
- Une erreur tardive à la lecture ne vide plus la source du projet suivant.
- Si le dossier de cache ne peut pas être créé, le résultat déjà calculé reste en place.
- Un jeu de variantes incomplet n'est plus exporté en silence.
- L'esquisse abandonnée revient avec Annuler, et un second objet d'historique ne laisse plus un Rétablir périmé.
- Deux rapports d'erreur de la même seconde ne s'écrasent plus.
- Les saisies choisies expressément survivent à l'enregistrement et à la réouverture, au lieu d'être remplacées par une valeur par défaut.
- Annuler met aussi fin au calcul qui tourne encore derrière une variante.

### Chat et IA

- Un outil supplémentaire dont un champ est mal typé n'interrompt plus toute la série de l'agent.
- Pour les variantes d'esquisse, l'agent ne nomme que des chemins de menu qui existent.
- À la génération d'images, les poids arrivent entiers ou pas du tout, et une seule valeur dans le champ de structure ne déclenche plus de génération non demandée.
- Un modèle local est mesuré même lorsqu'il répond en HTTPS sur un port qui lui est propre.
- La mention de la participation de l'IA ne vaut qu'avec une trace écrite, et un changement de langue ne met plus fin à la télécommande.
- L'installation de ComfyUI reprend les poids de modèle déjà complets, au lieu de les télécharger à nouveau.

### Mise à jour, installation et système

- La version minimale est désormais macOS 13, à l'identique dans le paquet, l'installateur et sur le site.
- Treize bibliothèques sont dans leurs dernières versions stables, et le noyau exact parle OpenCASCADE 8.
- Un paquet sans ancre de confiance dans le système apporte son propre jeu, sur toutes les plateformes.
- Un téléchargement ne s'interrompt plus après une durée totale fixe, et une réponse au compte-gouttes respecte le délai promis.
- Dans le Flatpak, l'application trouve le gestionnaire de paquets de la machine.
- Sous Linux et macOS, une interruption ne s'arrête plus au seul processus parent.
- L'entrée de menu Linux trouve le lanceur même sans entrée dans le chemin de recherche.
- Sur le Mac, la boîte de mise à jour indique que Solidon revient de lui-même après l'installateur.
- Sur le Mac, la souris 3D lit à travers le pilote du fabricant au lieu d'attendre à côté de lui.
- L'écran de démarrage reconnaît le système avant la première image, et le tableau des exigences n'est plus coupé.
- Une pièce jointe refusée ne compte plus comme manquante pour le retour d'information.
- Le sélecteur de filaments reste sur la bonne bobine après une annulation et affiche aussi la huitième.
- Un courriel d'assistance ouvert à la main porte un objet et un texte lisibles également dans Flatpak ; une annulation laisse le rapport en place.

### Manuel et site web

- Le manuel et les captures montrent l'interface remaniée dans les six langues.
- Les dessins du manuel conservent le contraste du texte jusque dans leurs remarques annexes.
- La fenêtre du manuel ne charge que ses propres figures et aucune image étrangère.
- Le site web dit en un seul endroit ce qui quitte votre machine.
- L'introduction n'affirme plus qu'un trou est fermé quand Annuler ne rétablit que le diamètre.

## 0.3.4

### Modifier les caractéristiques détectées

- Un perçage et sa fraisure liée se déplacent désormais ensemble, quel que soit celui des deux que vous sélectionnez. Le panneau Caractéristique indique ce lien avant la modification.
- Lorsque vous modifiez un perçage, sa fraisure reste associée sous lui dans l’arborescence et peut elle aussi être ajustée directement.
- Le panneau Caractéristique regroupe les actions identiques qui ne sont pas disponibles et nomme clairement les groupes de champs concernés.

### Reconnaissance des caractéristiques

- Les filetages des modèles importés sont reconnus de manière plus fiable ; les cônes, tenons et sphères incorrects qui s’y trouvent n’apparaissent plus comme des caractéristiques distinctes.
- Les jointures étroites entre des formes assemblées ne créent plus de nombreuses caractéristiques incorrectes.
- La reconnaissance des caractéristiques est sensiblement plus rapide sur les grands modèles détaillés.

### Cartes d’analyse

- Les cartes d’analyse sont disponibles pour davantage de grands modèles.
- Si une carte d’analyse est trop grande pour un modèle, le message propose directement *Réduire les triangles*.
- L’analyse du besoin en supports est nettement plus rapide sur les grands modèles.

## 0.3.3

### Affichage et sélection

- Le premier clic sélectionne la pièce, le deuxième le perçage en dessous, un clic à côté annule la sélection — et la navigation choisie reste valable tout du long.
- La rotation garde l'horizon à l'horizontale : après un geste, la vue est aussi droite qu'avant, dans chacune des cinq navigations.
- La navigation et le thème choisis dans les réglages sont également cochés dans le menu *Affichage*.
- Plusieurs corps sélectionnés le restent après un nouveau calcul, et un glissement les déplace ensemble.

### Travail sur le projet

- Un projet peut être enregistré même lorsqu'une remarque est attachée à une caractéristique.
- Passer d'une carte d'analyse à l'autre sur le même corps montre aussitôt ce qui est déjà calculé.
- Un nouveau projet démarre sans restes d'un aperçu resté ouvert au moment du changement.
- Par la commande à distance, *Annuler* retire exactement l'étape nommée et non la dernière.

## 0.3.2

### Modifier les caractéristiques reconnues

- Déplacer, tourner ou retirer un perçage ne laisse plus de matière à son ancien emplacement, y compris sur des pièces à rainure ou à cavité.
- La commande *Reboucher un perçage* comble désormais exactement le perçage : le bouchon ne dépasse plus dans une rainure et n'épaissit plus la pièce.
- Une cuvette sphérique est reconnue comme surface sphérique et non comme fraisure, même dans un maillage fin, et porte donc les actions qui lui reviennent.
- Un perçage dupliqué reçoit sa propre identité et non celle d'un perçage supprimé, si bien qu'un ajustement désigne toujours la caractéristique voulue.
- Lors de la rotation aussi, un perçage débouchant signale s'il ne débouche plus dans sa nouvelle orientation.
- Une caractéristique nouvellement créée apparaît à la fin de l'arborescence et non au milieu des anciennes.
### Affichage et sélection

- L'aperçu disparaît dès que la modification est appliquée ; jusqu'ici le corps de comparaison portant « pas encore appliqué » restait au-dessus du perçage terminé.
- La barre d'espace bascule de nouveau entre avant et après uniquement là où un aperçu est affiché, et non plus partout dans l'application.
- Un perçage ne s'illumine plus dans la couleur de sélection lorsque rien n'est sélectionné.
- L'arc de rotation, l'ombre, les repères de glissement et l'anneau du pinceau disparaissent avec l'action à laquelle ils appartiennent, y compris au changement d'outil ou à la fermeture.
- Une mesure reste sur sa pièce, même si la vue passe à un autre plateau d'impression ou à tous.
### Impression et mémoire

- Si tout ne tient pas sur un plateau, autant de plateaux que nécessaire sont créés ; jusqu'ici le reste restait à côté du plateau, où il n'est pas imprimable.
- La mémoire des caractéristiques des grands modèles reste bornée ; jusqu'ici elle pouvait occuper jusqu'à un gigaoctet.
## 0.3.1

### Modifier les caractéristiques reconnues

- Les caractéristiques reconnues peuvent être déplacées, tournées, dupliquées et retirées : un perçage, un tenon ou un dôme ; le dôme sans rotation, faute d'orientation.
- Le redimensionnement fonctionne aussi pour un tenon ou un dôme ; jusqu'ici, seul un perçage le permettait.
- Les valeurs mesurées sont déjà dans les champs : plus besoin de reboucher puis repercer avec des chiffres recopiés à la main.
- Un perçage déplacé reste le même perçage : tout ajustement qui le désigne conserve sa référence.
- Lorsqu'une action n'a pas de sens pour une caractéristique, elle reste visible et explique en une phrase pourquoi, au lieu de manquer en silence.
- Un panneau *Caractéristique* s'ouvre à droite dès le premier clic sur une caractéristique et montre ce qui y a été mesuré ; il se détache, se ferme et revient depuis *Affichage*.
- Chaque valeur y est modifiable : position, diamètre, profondeur et axe se règlent dans le champ, sans boîte de dialogue.
- Une valeur modifiée s'affiche en aperçu dans la vue avant de s'appliquer.
- Une case *Appliquer à tous les semblables* modifie toute une rangée de perçages d'un coup, avec une seule étape pour annuler.
- Deux caractéristiques sélectionnées indiquent leur distance d'axe en axe et par axe.
- Un perçage indique sa taille normalisée — « mesure 5,19 mm, le trou de passage pour M5 » — et signale aussi qu'aucune ne convient.
- Un second perçage identique au premier s'obtient par duplication, au lieu de retaper les cotes.
- La touche Suppr retire la caractéristique sélectionnée et non plus le corps entier.
- Un double clic sur une ligne de la liste des objets ouvre ce qui la modifie : la boîte de dialogue adaptée pour une caractéristique reconnue, l'étape avec ses cotes pour une créée.
- Un perçage débouchant qui ne débouche plus après déplacement le signale, et une fraisure qui refermerait son perçage ne peut pas être déplacée.
- Réduire un perçage jusqu'à ce qu'il n'en soit plus un donne une explication au lieu de demander un rapport d'erreur.
- Sur une face, un bouton mène au catalogue de blocs au lieu d'afficher des lignes qui disent seulement ce qui est impossible.
### Déplacer, tourner et sélectionner

- La poignée de déplacement se place sur ce qui est sélectionné : sur un perçage, à son ouverture, et non au centre de la pièce.
- Ce qui est sélectionné est ce qui bouge : avec un perçage sélectionné, la poignée et la barre déplacent le perçage, non la pièce entière.
- Pendant le glissement, un aperçu transparent montre où va le perçage et une image pâle son point de départ.
- L'ombre suit le déplacement et indique ainsi la hauteur au-dessus du plateau.
- Pendant la rotation, un arc montre l'angle parcouru et l'accrochage aux multiples de 45 degrés.
- Les petites rotations aboutissent : jusqu'ici un accrochage angulaire invisible avalait tout mouvement inférieur à son pas.
- Sur une face, la barre de déplacement ne propose que le possible et donne la raison sur le bouton, non dans un message après le clic.
- Le bouton *Appliquer* disparaît : on applique avec Entrée dans le champ ou en tirant la poignée, et exactement une fois, non deux.
- Une pièce déplacée ne revient plus un instant à son ancienne position au relâchement.
- Un clic droit dans la liste des objets atteint la ligne visée, et non les deux au-dessus.
### Vue et arborescence des objets

- La vue a sa propre commande, et elle est la nouvelle valeur par défaut : glisser à gauche déplace, à droite fait tourner, la molette pressée incline, la molette zoome.
- W, A, S et D permettent de voler dans la scène, Q et E inclinent ; le vol traverse une pièce, tandis que le zoom s'arrête devant.
- Qui préfère une autre commande la choisit dans les réglages : les schémas Cura, Bambu Studio, Orca et PrusaSlicer, CAO et Blender restent en place.
- L'entrée *Ajuster à la vue* cadre la pièce cliquée ; sans sélection, toute la scène comme avant.
- Une pièce sous le plateau d'impression est visible : c'est désormais le plateau qui est transparent, pas le modèle.
- Les corps semi-transparents sont dessinés dans le bon ordre de profondeur, quel que soit leur ordre de création.
- La vue réglée est conservée au lieu de revenir en arrière à l'étape suivante.
- La sélection et les changements dans la vue 3D se font par transitions douces au lieu de sauts brusques.
- À partir de quatre caractéristiques de même nom, l'arborescence affiche une ligne dépliable avec leur nombre au lieu de centaines de lignes.
- Seul ce qu'une imprimante peut fabriquer est affiché : les caractéristiques sous le demi-millimètre disparaissent — sur un support de tuyau, 296 sur 1130.
- Les congés de rayon nul disparaissent donc de l'arborescence des objets.
- Un clic sur un corps ne coûte plus d'attente ; sur un assemblage de 63 Mo, c'était trois quarts de seconde.
- Changer l'affichage et reconstruire l'image des grands modèles prennent un tiers du temps précédent.
### Dessin et saisie précise

- La longueur et la largeur d'un dessin sélectionné sont modifiables ; le dessin suit la valeur modifiée avec ses cotes.
- Une cote mal placée s'annule seule, et non plus uniquement avec toutes les autres.
- Après avoir extrudé une esquisse, la boîte de dialogue propose aussi le chemin pour la soustraire.
- Une cote saisie vaut telle qu'elle a été saisie : 0,1 ne devient plus 0,166667.
- La boîte de dialogue des unités demande des millimètres et affiche un nombre au lieu de « nan ».
- Le champ du chanfrein s'appelle largeur, et son message parle aussi de la largeur, non du rayon.
- Un clic dans la glissière d'un curseur le place à l'endroit cliqué, et non une page plus loin.
- Lors de la mesure, le point cible s'accroche aux arêtes du modèle et non à des lignes absentes de l'image.
### Ouverture, enregistrement et fichiers d'échange

- Le premier modèle d'un projet est centré sur le plateau d'impression au lieu de l'endroit fixé par son fichier ; les suivants gardent leur position.
- Un fichier défectueux est refusé à l'ouverture, au lieu d'être accepté et de finir dans le projet à l'enregistrement.
- Le refus indique la raison — vide, tronqué, pas un STL, pas un 3MF, sans triangles, coordonnées inutilisables — et propose *Choisir un autre fichier*.
- Le téléchargement interrompu d'un fichier de modèle est reconnu comme tel.
- Les fichiers de plus de huit mégaoctets sont lus avec un indicateur de chargement et une progression, au lieu de figer la fenêtre quatorze secondes.
- Un nom de fichier arrive sur le disque tel qu'il a été saisi, avec espaces, accents, parenthèses et signe plus.
- Un modèle peut être enregistré en 3MF sans les valeurs d'impression de Solidon, pour arriver inchangé dans le slicer.
- Lorsque STEP est impossible pour un maillage, le refus propose directement *Enregistrer en 3MF*.
- Un modèle au maillage trop fin reçoit *Réduire les triangles* comme bouton sur le constat, et non seulement comme conseil dans le texte.
- Un constat qui touche plusieurs corps se corrige pour tous d'un coup, avec le choix desquels et un seul Ctrl+Z pour toute l'action.
- La commande *Auto Split* signale quand une coupe laisse une surface ouverte, et une coupe dans un corps modifiable ne vide plus la scène.
- Mettre une pièce à une échelle inférieure à la limite de la machine donne un constat ; jusqu'ici il n'y en avait que pour trop grand.
- Les blocs personnels portent le même avertissement que ceux fournis.
### Impression, slicer et filament

- La boîte de dialogue d'impression affiche les profils correspondant à l'imprimante réglée, au lieu d'un stock de 1001 entrées.
- Pour une Elegoo Centauri Carbon, ce sont quatre profils, le bon étant présélectionné.
- Changer d'imprimante dans le projet entraîne volume d'impression, buse et code de départ : un projet Prusa ne reçoit plus la machine de l'Elegoo.
- Le slicer reçoit les données de la machine et renvoie un fichier d'impression, au lieu d'abandonner avec « incompatible avec l'imprimante ».
- Si le slicer est réglé sur une autre imprimante que le projet, Solidon le signale au lieu de l'accepter en silence.
- L'avis de profil manquant indique de quelle imprimante il s'agit.
- La liste des filaments reste vide tant qu'aucun profil machine n'est choisi et en donne la raison, au lieu de proposer 5962 bobines.
- La sélection de filament se filtre par fabricant, matière et valeurs apportées par un profil.
- Là où Solidon ajoute une bordure, il précise quelle pièce en a besoin et pourquoi.
- Ce que la machine ne peut pas faire est indiqué sur tous les champs concernés, et non sur un seul.
- Les recommandations du rapport que le slicer n'accepte pas ne promettent plus d'effet.
- Les objets de matières différentes vont sur des plateaux séparés : le joint en TPU n'est plus sur le plateau du boîtier en PETG.
- L'avis d'impression donne un conseil au lieu de renvoyer à des numéros du contrat de licence.
### Messages, boutons et informations

- Les boutons verrouillés indiquent désormais sur le bouton ce qui leur manque : à la souris, au clavier et pour un lecteur d'écran.
- Parmi eux : *Trancher* et *Ouvrir dans le slicer* sans slicer configuré, *Insérer* dans le catalogue de blocs et *Créer* dans la boîte de dialogue de modèle.
- Les refus ne s'arrêtent plus à la phrase seule, mais indiquent l'issue.
- Une erreur inattendue est expliquée dans la langue réglée, au lieu de réciter un texte interne en anglais.
- La fenêtre À propos indique qui est derrière Solidon et qui répond aux retours.
- Un lien vers une version antérieure mène à l'actuelle au lieu d'une page d'erreur.
- L'installation Windows aboutit aussi sur les machines où elle échouait avec « fichier corrompu » ; en contrepartie le fichier d'installation est 23 mégaoctets plus gros.
### Discussion et prise en charge des modèles

- Si une référence à une caractéristique est ambiguë, la discussion s'arrête, met les candidats en évidence dans la vue et demande, en nommant le corps de chacun.
- Lorsque la discussion répartit des objets sur des plateaux d'impression, le résultat est ensuite visible dans la vue.
- Un constat sur un assemblage désigne le corps concerné et porte son action ; là où il n'y en a pas, c'est une simple indication.
- La discussion connaît les nouvelles actions sur les caractéristiques reconnues et les exécute sur demande.
## 0.3.0

### Premiers pas et orientation

- Quatre parcours guidés expliquent les principales voies, de la première ébauche au résultat imprimable.
- L’écran d’accueil occupe entièrement les fenêtres petites ou étroites, sans cartes coupées ni contenu masqué.
- Les projets récemment utilisés précèdent les parcours d’introduction et sont ainsi accessibles plus rapidement.
- L’écran d’accueil ne déplace plus la sélection sans demande et se commande entièrement à la souris comme au clavier.
- Les accès *Nouveau*, *Ouvrir* et *Exemples* sont mieux ordonnés et décrivent leur destination avant même l’ouverture.
- Les avis et le soutien facultatif sont directement accessibles depuis l’écran d’accueil, au clavier comme avec les technologies d’assistance.
- La discussion reste utilisable même avec une faible hauteur de fenêtre : la saisie reste fixée en bas et le contenu défile.
- La barre d’outils supérieure reste visible avec un projet ouvert et une fenêtre étroite, sans sortir de l’espace de travail.
- Un nouvel exemple de dessin mène directement au parcours d’esquisse et complète les projets d’exemple existants.
- L'écran d'accueil a un bouton *Ouvrir un modèle …*, et la zone de dépôt se laisse aussi cliquer.
### Interface et utilisation

- Les menus ont des titres bien visibles et des colonnes d’icônes alignées de façon uniforme.
- La liste des commandes aligne proprement raccourcis et explications afin de parcourir plus vite les longues entrées.
- Les grands dialogues emploient des colonnes et des largeurs de champ cohérentes.
- L’ancienne page réunissant adhérence, rétraction et filament est divisée en sections de réglages plus petites et clairement nommées.
- Les 56 réglages d’impression peuvent être recherchés sous leurs libellés allemands visibles.
- La recherche reconnaît aussi 146 termes courants des slicers, dont *perimeters* et *wall loops*.
- Les champs numériques réagissent fidèlement aux flèches, au pas et à l’arrondi, sans plus modifier les valeurs de façon inattendue.
- Les curseurs ont un aspect uniforme avec une poignée facile à saisir.
- La couleur d’accentuation est réservée au bouton principal ; l’outil actif se reconnaît à son bord et les commandes inactives se font visuellement discrètes.
- Les calculs très courts évitent tout affichage clignotant ; les moyens montrent un curseur d’attente, les longs ajoutent progression et annulation.
- Les indications d’outils restent sur une ligne si la largeur suffit et passent proprement à la ligne dans les fenêtres étroites.
- Les aperçus dans l’arborescence des objets sont assez grands pour reconnaître réellement les formes.
- La liste des filaments défile séparément ; *Ajouter un filament* et *Valeurs d’impression* restent accessibles avec de nombreuses bobines.
- Les avertissements et erreurs restent lisibles sans transmettre leur sens uniquement par la couleur du texte.
- Les champs de sélection désactivés se distinguent clairement des champs sélectionnés et actifs.
- Une souris 3D (SpaceMouse) déplace le modèle sur les six axes dès qu'elle est branchée ; un bouton de l'appareil cadre tout.
- Le plateau d'impression se masque d'un clic ou avec Ctrl+Maj+D et le reste jusqu'à ce qu'on en ait de nouveau besoin.
### Dessin et saisie précise

- Les cercles sont saisis par leur diamètre ; un perçage M3 peut ainsi être créé directement à 3,2 mm.
- Une contrainte de diamètre reste une expression modifiable après résolution, enregistrement et réouverture.
- Les cotes se modifient directement par double-clic, sans l’ancien et long détour par la sélection.
- Les positions X, Y et Z, l’angle et l’échelle se saisissent directement dans la barre de déplacement.
- Une saisie exacte crée la même étape annulable qu’un déplacement à la souris.
- Lors d’une rotation ou d’une mise à l’échelle exacte, plusieurs corps sélectionnés utilisent un centre commun.
- Échap recule d’un seul niveau pendant le dessin : ligne actuelle, outil actuel, puis seulement l’esquisse entière.
- Rétablir fonctionne désormais même lorsqu’une esquisse est ouverte.
- Une esquisse vide affiche une indication cliquable qui ouvre les formes de base prêtes à l’emploi.
- Le bouton des formes de base porte le nom de l’action du clic. Les autres formes se trouvent derrière la flèche adjacente.
- L’outil de coupe s’ouvre dans le corps plutôt que dans une vue vide hors du modèle.
- Les vues avant, latérale, supérieure et opposées s’alignent fidèlement sur les six axes.
- La poignée de déplacement reste visible même avec une caméra rasante ou oblique et affiche une cote utile.
- L’outil de mesure termine une mesure par un retour visible, au lieu de donner l’impression de perdre le résultat.
- Pendant l'extrusion, la cote s'affiche sur le fil de fer, et après le relâchement toutes les valeurs restent modifiables dans le dialogue.
- Les cotes pendant le dessin suivent la grille, pas le pointeur : on voit la mesure que l'on obtient vraiment.
- Les cotes de cercle se basculent entre diamètre et rayon directement au champ ; le choix vaut dans l'esquisse et les dialogues et reste mémorisé.
- Un cercle à centre fixe et diamètre coté est considéré comme entièrement déterminé ; la ligne d’état ne signale plus de cote manquante.
### Vue, historique et modification des formes

- Plusieurs corps sélectionnés peuvent être déplacés ensemble.
- Plusieurs corps sélectionnés tournent autour d’un centre commun et conservent leurs distances mutuelles.
- Après une rotation, les corps peuvent être replacés proprement sur le plateau dans la même étape de travail.
- Les déplacements successifs d’un même corps sont regroupés en une étape d’historique compréhensible.
- Les étapes liées apparaissent dans une entrée dépliable au lieu de surcharger l’historique de lignes isolées.
- Une action utilisateur continue s’annule entièrement avec une seule commande Annuler.
- Les entrées d’historique indiquent leur type et un numéro d’étape sans ambiguïté.
- Les modèles téléchargés et importés peuvent être coupés immédiatement.
- Un clic sur un constat du rapport mène fidèlement à l’endroit, au corps ou à l’étape d’historique concernés.
- Lors du saut vers un constat, la caméra cadre la cible au lieu d’aboutir sur un gros plan gris.
- Les faces nommées et les indications suivent leur corps pendant l’agencement et le positionnement.
- Pendant le modelage au pinceau, un message indique si les traits manquent le modèle ou ne produisent aucune modification imprimable.
- Un texte sur une paroi latérale est horizontal et à l’endroit au lieu de suivre un angle quelconque ; sur le dessus et le dessous, c’est toujours l’angle réglé qui donne la direction.
- Si une inscription se retrouve dans le corps au lieu d’être dessus, l’opération le dit et indique la voie : cliquer la face où le texte doit se poser.
- Les corps évidés conservent l’épaisseur de paroi demandée aussi sur les faces inclinées et courbes.
- Un trou agrandi volontairement garde son nom et ses ajustements au lieu de compter comme perdu dans le rapport.
- Les sphères à très nombreux segments restent un maillage maniable au lieu de vingt millions de triangles.

### Blocs personnels et fichiers d’échange

- Les blocs personnels peuvent être enregistrés dans un fichier local .solidon-part puis réintégrés au catalogue.
- Les fichiers de bloc s’ouvrent, se glissent dans l’application et s’importent via l’association de fichiers du système.
- Le nom et l’extension du fichier montrent immédiatement qu’il appartient à Solidon.
- Importation, partage et bibliothèque locale emploient des textes d’interface complets dans les six langues.
- Avant l’enregistrement, un bloc personnel peut être composé de plusieurs étapes et valeurs modifiables.
- Lors du partage, le choix porte sur libre, attribution ou attribution avec partage dans les mêmes conditions.
- Si vous avez nommé votre bloc, votre propre nom reste prioritaire sur un nom fourni avec le fichier.
- La provenance et les conditions de partage restent traçables lors de l’échange d’un bloc.
- Les clips à encliqueter, œillets de charnière, crochets muraux perforés et pieds ont des transitions plus robustes, sans surfaces internes enfermées.
- Les cartes du catalogue conservent leur position et la face sélectionnée pendant le chargement de leurs aperçus.
- L’échelle de tolérances marque chaque marche de son propre numéro.
- Les fichiers GLB exportés se tiennent debout dans d’autres programmes au lieu d’être couchés.

### Séparation, impression et filament

- La séparation automatique privilégie les interfaces solides et évite l’ancien choix possible du point faible le plus fin.
- Le type d’assemblage adapté est choisi séparément pour chaque coupe et enregistré sous forme concrète.
- Les indications concernant les assemblages collés restent liées à la coupe sélectionnée.
- La séparation automatique réagit aux consignes modifiées de façon reproductible et peut être annulée pendant le calcul.
- La recherche d’orientation n’examine que les positions réellement distinctes et respecte le temps prévu, même avec des corps exigeants.
- Les gros fichiers 3MF sont reconnus et traités plus rapidement sans modifier le résultat du fichier.
- Matériau, ajustement et tolérances suivent la bobine réellement choisie ou l’emplacement occupé dans l’imprimante.
- L’en-tête montre le matériau réellement utilisé et ne propose plus une seconde sélection de matériau contradictoire.
- Le bouton désactivé *Enregistrer le fichier d’impression* explique que le fichier n’est créé qu’au tranchage.
- Les réparations déjà effectuées dans le même flux de travail ne sont plus ensuite affichées comme recommandations ouvertes.
- Les perçages de tenons s’ouvrent à la séparation avec un chanfrein d’entrée, et le cran d’une poche à clip se trouve au joint.
- Un diamètre de tenon choisi soi-même doit tenir dans le joint ; s’il s’amincit pour cela, le rapport le dit.

### Rapport, stabilité, plateformes et langues
- Sous Linux dans une session Wayland, Solidon démarre et affiche la vue 3D ; s’il manque une bibliothèque au système, l’application démarre quand même et indique laquelle.

- Les constats semblables sont regroupés sans perdre le lien avec les corps et emplacements concernés.
- Les nombres et mesures du rapport portent des libellés complets plutôt que des valeurs isolées incompréhensibles.
- Si une réparation échoue, le corps d’origine inchangé est entièrement restauré.
- Un maillage importé fermé n’est plus ouvert par la suppression trop hâtive d’un triangle problématique.
- Les boutons d’action du rapport ne retiennent plus discrètement en mémoire une fenêtre déjà fermée.
- Les blocs fournis et l’activation se chargent au démarrage sans se bloquer mutuellement.
- La vue 3D se ferme proprement avant la fenêtre, ce qui fiabilise la fermeture sous Windows, Linux et macOS.
- Sous Windows 11, la barre de titre suit le schéma de couleurs de l’application ; les autres plateformes restent inchangées.
- Les boutons standard comme Ouvrir, Enregistrer et Annuler changent immédiatement de langue, sans redémarrage.
- Les noms de corps et de blocs générés automatiquement changent aussi correctement de langue après l’emploi de contenus mis en cache.
- Les traductions et valeurs de rapport sont au même niveau en allemand, anglais, espagnol, français, italien et portugais.
- Une pièce sans constat propose directement dans le rapport le bouton *Transmettre au slicer …*.
- Chaque carte d'analyse explique au survol ce qu'elle montre, et la question d'unité à l'import nomme les unités en toutes lettres.
- Une pièce qui remplit le plateau est lue en millimètres sans question.
- Les nervures fines à côté de plaques épaisses sont reconnues comme endroit fin, et les ponts sont mesurés à leur largeur réellement libre.
- Une pièce qui repose sur elle-même ne se voit pas recommander de supports depuis le plateau.
- Les recommandations d’impression vérifient toutes les vitesses, calculent la première couche à ses propres dimensions et signalent un plateau ou une enceinte trop froids pour le matériau.
- Les pattes superposées gardent chacune leur perçage, et les fines rayures ne comptent ni comme perçage ni comme tenon.
### Discussion et prise en charge des modèles

- La discussion accueille avec son objectif concret et ne démarre plus sur une zone vide ou des termes techniques liés aux modèles.
- Les compteurs techniques de jetons ont été retirés de l’interface client habituelle.
- Les indications identiques sur des détails de forme perdus parviennent à l’assistant comptées plutôt qu’une par une.
- Le dialogue de génération transforme un texte ou une image en modèle via un ComfyUI local et l’ajoute à la même scène modifiable.
- Le flux TripoSG fourni crée un fichier GLB, ensuite réparé, mis à l’échelle et contrôlé automatiquement pour l’impression.
- Ollama local et ComfyUI local calculent l’un après l’autre afin de ne pas occuper simultanément la carte graphique.
- Après une proposition de l’agent ou une génération 3D, Solidon libère les modèles locaux et la mémoire graphique.
- Lors de l’annulation, Solidon ne retire que sa propre tâche ComfyUI ; les autres tâches en cours y restent intactes.
- Avant la première utilisation d’un modèle cloud, Solidon explique clairement quels contenus quittent l’ordinateur.
- Le dialogue des programmes complémentaires ne montre que ce qui manque encore et décrit l'état de ComfyUI en mots simples.
## 0.2.2


### Dessin et mise en forme

- En mode esquisse, sélectionnez et déplacez points, lignes, cercles et contours directement dans la vue. Un repère et une poignée indiquent aussi ce qui va bouger.
- Le plan de dessin reste dans l'espace quand vous passez entre les vues de dessus, de face et de côté. Vous voyez sa position réelle au lieu de trois images identiques.
- Un rectangle peut être terminé en saisissant sa largeur et sa hauteur. Les cotes restent des contraintes au lieu de disparaître après le dessin.
- Dans la vue de face ou de côté, tirez un contour fermé pour lui donner une hauteur. La cote et l'aperçu filaire grandissent ; une valeur saisie fixe la hauteur exacte.
- Tirez le contour vers l'extérieur pour créer un corps ou vers l'intérieur pour créer une poche visible. Une flèche et une croix rendent les deux directions saisissables.
- L'aperçu affiche le pavé, cylindre ou corps esquissé pendant la saisie de ses cotes. Les nouveaux corps restaient auparavant invisibles jusqu'à l'application.
- Les outils de dessin annoncent l'effet du prochain clic. Les contraintes expliquent leur effet et la sélection, et les degrés de liberté sont décrits simplement.
- Le pavé, le cylindre, le perçage et l’évidement n’apparaissent plus qu’une fois dans le menu. La case « Modifier les faces et les arêtes plus tard » remplace l’entrée « exact ».
- Cette case garde disponibles les chanfreins, les congés, les dépouilles, les faces décalées et l’export STEP. Le dialogue nomme l’intérêt plutôt que le moteur de calcul.
- Pendant le dessin, la barre nomme l’étape suivante : Élever, Creuser ou Terminé. S’il manque un contour fermé ou un corps sélectionné, elle le dit aussi.
- Une contrainte se retire d’un deuxième clic sur le même bouton, et un clic droit sur le point montre ce qui en dépend. Auparavant, chaque clic en ajoutait une autre jusqu’au blocage.
- La barre des contraintes n’affiche que ce qui correspond à la sélection. Si rien n’est sélectionné, une phrase y figure au lieu de dix termes techniques en gris.
- Les corps de base sont posés « sur le plateau d’impression » au lieu de « à Z = 0 », et l’outil de dessin s’appelle « courbe », comme ce qu’il dessine.

### Perçages et éléments

- Modifiez directement le diamètre d'un perçage détecté dans un modèle importé, sans le redessiner ni ouvrir un logiciel de CAO.
- Le perçage modifié garde sa position et sa direction sur les maillages comme sur les corps exacts. Même un perçage incliné reste sur son axe d'origine.
- Les repères d'éléments suivent la géométrie visible après recalcul. Un perçage repéré reste ouvert au lieu d'être masqué par son repère.
- Les outils fréquents comme Perçage, Union et Soustraction sont accessibles avec un clic de moins. Les titres continuent de séparer clairement les groupes.

### Blocs et pièces normalisées

- Le catalogue propose des vis et écrous imprimables avec des filetages assortis. Choisissez tête, longueur, taille et jeu selon l'impression.
- Les roulements courants disposent d'un logement aux dimensions normalisées. Le roulement peut rester démontable avec du jeu ou tenir par ajustement serré.
- Un perçage de vis peut loger une tête fraisée ou sa rondelle. La profondeur de tête règle jusqu'où l'une ou l'autre s'enfonce dans la pièce.
- Les tables contiennent davantage de rondelles, inserts filetés et roulements. Les tailles techniques sont expliquées dans le choix au lieu de rester des codes obscurs.
- Les poches d'aimant, clips et passe-câbles acceptent aussi des dimensions personnalisées. Les champs supplémentaires n'apparaissent que si la variante les utilise.
- Les blocs se trouvent dans le catalogue avec des aperçus au lieu d’une liste dans le menu. Un clic droit sur la pièce choisie y mène.
- Le catalogue prévient avant l’insertion lorsque l’endroit sur le corps manque. La plupart des blocs ont besoin d’une face ou d’un perçage sélectionné.

### Impression et filament

- Chaque bobine peut porter ses propres températures, refroidissement, rétraction et valeurs de matière. Elles restent en place lors d'un changement de qualité.
- Les valeurs de chaque bobine arrivent dans le fichier 3MF et le slicer au bon emplacement de matière. Une couleur ne reprend plus par erreur les valeurs d'une autre.
- Au premier démarrage, Solidon reprend les filaments chargés dans le slicer avec leur nom, type, couleur et profil du fabricant. Les bobines ne sont pas à recréer.
- Les exemples fournis ne remplacent plus l'imprimante et le matériau choisis par les réglages qui ont servi à créer leurs aperçus.
- Dans le Flatpak Linux, Solidon trouve et lance les slicers de l'ordinateur, y compris les AppImages. Les deux programmes accèdent au dossier de travail partagé.
- La séparation pose des goupilles sur une moitié et les trous correspondants sur l’autre. Le message en donne le nombre ou signale que la face de coupe est trop petite.
- Après la séparation, les moitiés s’écartent. Goupilles et trous ne disparaissent plus entre deux faces de coupe confondues.
- Lors de l’union de deux corps, les deux gardent leur description de filament avec son nom. La description de la seconde couleur pouvait auparavant se perdre.
- À l’export sur plusieurs plaques, les changements de couleur sont comptés par plaque. Une plaque d’une seule matière n’annonce plus de changements qui n’ont pas lieu.

- Si le slicer configuré échoue, le message propose d'en choisir un autre. Avant, il ne restait que l'export — même avec deux slicers en état de marche juste à côté.
- Le fichier d'impression terminé s'ouvre directement dans la fenêtre du slicer, avec ses propres profils. Quelle remise vous utilisez est retenu par projet.
- Le fichier d'impression est vérifié contre la hauteur du modèle. Une pièce enfoncée sous le plateau se remarque avant l'impression — pas à mi-hauteur sur l'imprimante.
- ElegooSlicer accepte de nouveau les travaux. Et si un slicer dispose les pièces lui-même, le rapport le dit au lieu de remplacer en silence l'occupation du plateau prévue.
- Le rapport n'empile plus les anciennes mesures : un nouveau passage les remplace, le même fait n'apparaît qu'une fois, et les constats nomment l'objet au lieu d'un numéro.
- Les profils de slicer retenus savent à quel slicer ils appartiennent. Après un changement, aucun profil étranger ne passe dans le nouveau programme.
- Un motif de blocage sous les réglages d'impression disparaît dès qu'il ne vaut plus. Avant, « a besoin d'un profil d'imprimante » restait à côté d'un bouton depuis longtemps libre.

### Chat et génération 3D

- Les réglages séparent clairement les modèles cloud et locaux. Avant la saisie d'une clé cloud, ils expliquent quelles données quittent l'ordinateur.
- La vérification d'un générateur 3D lent ne retient plus la fenêtre. Elle indique ce qui est vérifié et comment installer les programmes supplémentaires.
- L'affectation des éléments détectés reste fluide sur les grands modèles. Des centaines d'éléments sont comparés ensemble au lieu de l'être un par un.
- Les requêtes vers Ollama et ComfyUI sur le même ordinateur évitent le proxy de l'entreprise. Un service local actif n'est plus signalé à tort comme inaccessible.
- Dans le Flatpak Linux, l'installation et le lancement des programmes auxiliaires se font sur l'ordinateur et non dans le bac à sable. ComfyUI est aussi trouvé aux emplacements usuels.
- Le bouton Générer n'est cliquable que si le clic déclenche vraiment quelque chose. S'il manque quelque chose, le dialogue dit quoi — avec un bouton qui mène à la solution.
- Si la génération échoue, la propre ligne d'erreur de ComfyUI s'affiche dans le dialogue, avec l'étape où elle est survenue. C'est exactement la ligne qu'il faut pour demander de l'aide.
- Si un modèle de langage écrit son appel en texte au lieu de l'exécuter, la proposition l'explique — avec le chemin vers « Vérifier les outils ». Avant, du JSON brut restait dans la conversation.
- Le manuel a une nouvelle page, « Quels modèles Solidon utilise » : lesquels sont éprouvés, d'où ils viennent, combien de temps ils prennent — et quel fichier va où pour le texte.
- Un corps généré très petit montre son volume réel au lieu de « 0 mm³ » à côté de « fermé ».
- Pour les modèles d'IA de la génération, vous choisissez par tâche lequel calcule — comme pour le modèle de langage. « Automatique » reste le réglage par défaut et prend ce qui convient.

### Vue et utilisation

- La barre de paramètres garde les cotes compactes et visibles. Unité, limites et expression s'y modifient avec annulation sans masquer la valeur elle-même.
- Les curseurs de Solidon suivent la taille système réglée sous Windows, macOS et Linux. Leur point de clic revient sur la pointe dessinée au lieu d'être à côté.
- Le survol et la sélection sont nettement distingués dans la vue. Les couleurs d'analyse et de différence restent prioritaires sur la surbrillance du corps entier.
- Les menus, indications et le manuel emploient des mots cohérents pour les débutants. Les termes spécialisés sont expliqués lors de leur premier emploi.
- La fenêtre Soutenir explique avant d'ouvrir PayPal que le paiement est volontaire et ne débloque aucune fonction. Si le navigateur échoue, le lien peut être copié.
- Évider et les autres outils dépendants n'affichent que les champs utilisés par la variante choisie et expliquent uniformément les valeurs masquées.
- Les exemples fournis s’ouvrent avec une visite guidée. À droite, elle indique pas à pas quoi faire et reconnaît d’elle-même qu’une étape est faite.
- Les actions proposées pour une erreur sont conservées à l’enregistrement. À la réouverture d’un projet, seule l’erreur subsistait, sans l’issue.
- La recherche d’orientation n’examine plus chaque position qu’une fois. Les positions proposées plusieurs fois coûtaient du temps sans donner un autre résultat.
- Les étapes de l’historique peuvent être supprimées et récupérées avec Ctrl+Z. La question posée avant nomme les étapes qui reposent sur celle qui disparaît.
- Un double clic sur une étape groupée de l’historique indique où se trouvent les étapes individuelles. Auparavant il ne faisait rien, alors que les visites guidées enseignent ce geste.
- Si un fichier est refusé à la lecture, l’indicateur de chargement disparaît. Auparavant il restait comme si l’on calculait encore un fichier qui n’avait pas été accepté.
- Solidon démarre plus vite et l’analyse des couches calcule plus rapidement. Les grandes bibliothèques de calcul ne sont chargées que lorsqu’il y a vraiment à calculer.

- Les messages d'erreur montrent les données auxquelles leurs phrases renvoient. « Le début de la réponse est affiché à côté » — maintenant il l'est vraiment, avec l'adresse et le fournisseur.
- Les conseils « Réduire les triangles » et « Ouvrir la page dans le navigateur » sont désormais des boutons qui font exactement cela, au lieu de phrases qui le décrivent.
- Quand un service ne répond pas, le dialogue nomme l'adresse à vérifier dans le navigateur et garde la tentative sous « Détails ». Ses indications ne renvoient qu'à des boutons existants.
- Les listes déroulantes des barres sous la vue restent ouvertes jusqu'à votre choix. Avant, une liste pouvait se refermer aussitôt parce qu'elle glissait hors du pointeur.
- Le champ d'épaisseur de la barre de coupe attend la fin de la saisie. Avant, il coupait à chaque frappe — d'abord à 3 mm, puis à 30.
- Après l'ouverture, le rapport présélectionne le premier constat qui offre une action. « Poser sur le plateau » est là comme bouton tout de suite, sans devoir cliquer d'abord la ligne.
- L'avis sur les très petites pièces détachées propose désormais le bouton « Supprimer les petites pièces ». Avant, il disait seulement que rien n'avait été supprimé, sans indiquer de chemin.
- Les réparations déjà effectuées à l'import apparaissent comme note dans le rapport, non plus comme avertissement. Sinon il s'ouvrait en jaune un modèle sur deux, sans rien à faire.
- L'avis sur le gestionnaire de paquets annulé nomme le bouton par son nom complet — dans les six langues. « Détails » tout seul était une petite recherche dans cinq d'entre elles.

### Plateformes et corrections

- Linux dispose maintenant d'une AppImage en plus du Flatpak. Solidon peut ainsi démarrer comme un fichier exécutable unique sans installation de Flatpak.
- Une mise à jour Windows lancée depuis Solidon affiche seulement sa progression, puis rouvre Solidon. Lancé manuellement, l’installateur conserve le choix de démarrage sur sa dernière page.
- Le Flatpak Linux peut être mis à jour depuis Solidon.
- Les retours au support peuvent aussi être envoyés depuis le paquet Linux. L'accès réseau nécessaire lui manquait jusqu'ici.
- Sous macOS, les fissures fines du maillage STL d'un filetage sont recousues à l'export sans accepter un maillage devenu moins bon.
- La recherche de mise à jour accepte un changelog multilingue conséquent. Les notes ne finissent plus au milieu d'un mot et les longues listes ne la bloquent plus.
- La fenêtre À propos du paquet affiche de nouveau les mentions de toutes les bibliothèques fournies.
- Les rapports d'erreur donnent les vraies versions, la session et la méthode de saisie. Un tiret ne signifie plus à tort qu'une bibliothèque nécessaire manque.
- Des métadonnées étrangères isolées ne font plus échouer la réparation d'un maillage importé.
- Un évidement réussi indique aussi pour les corps exacts l'épaisseur de paroi et le volume retiré, au lieu de rester silencieux après le calcul.

## 0.2.1


### Couleurs et filament

- Vous colorez faces et pièces avec deux gestes au lieu d'un pinceau : un clic colore une face, un clic la pièce entière. Si une étape antérieure change les cotes, la couleur suit.
- Un clic sur la face du dessus colore la face du dessus — la limite vient de la détection, sans rayon et sans viser.
- Le filament se choisit par nom et couleur — « PETG rouge » au lieu d'un numéro. Le chat le comprend aussi.
- Vingt bobines sur l'étagère font vingt filaments dans le choix. Quatre bobines du même matériau en quatre couleurs font quatre entrées, pas une.
- La couleur d'un filament et ses températures vont maintenant ensemble. Avant, le réglage du rouge pouvait atterrir sur le filament blanc.
- La même couleur reçoit la même buse — sur le deuxième plateau aussi.
- La vue montre la vraie couleur du filament. Un filament sans couleur propre est gris, et la sélection reste reconnaissable.
- Colorer se trouve désormais là où l'on cherche la couleur — avant, c'était rangé sous « Préparer ».
- Le champ « Couleur de la pièce » affichait en thème clair une autre couleur que la vue à côté.
- Taper « PETG » donnait « Ce profil de matériau est inconnu ». Le champ est maintenant une liste des noms qui existent vraiment.
- La présélection « — aucun — » était refusée à la validation. Il y a maintenant une valeur que la boîte de dialogue accepte.
- Le sélecteur de couleur montrait du rouge, et après désélection la pièce était grise.

### Blocs

- Une charnière à axe qui sort de l'imprimante déjà mobile. Rien à assembler, rien à insérer : l'imprimante laisse le jeu ouvert.
- Un bloc peut réunir plusieurs pièces. Vous pouvez ainsi enregistrer un modèle mobile ou assemblé comme une seule entrée réutilisable du catalogue.
- Poser l'axe dans le trou ne marchait pas, bien que les deux éléments soient là. Maintenant si.

### Impression et slicer

- Au tranchage, vous choisissez quels plateaux partent. Qui voulait trancher le plateau 2 recevait trois fichiers et les bobines du plateau 1.
- Solidon écrit maintenant le profil de machine et de processus pour le slicer, au lieu de renvoyer à son fonds. Sept réglages figuraient dans le fichier, cent trente-six sont partis au slicer.
- Le code de démarrage vient du profil d'imprimante du fabricant au lieu d'être écrit à la main.
- Ce qui ne dépose plus de cordon, la buse le dit : les parois trop minces figurent au rapport comme constat, pas comme proposition.
- La limite basse d'épaisseur de paroi vient du profil de matériau. Deux nombres fixes s'y trouvaient, et tous deux étaient faux — sur la Centauri, c'est 0,84 mm.
- Le bouton de tranchage invitait au clic alors que rien ne suivait trois phrases plus loin.
- Un fichier G-code portant l'extension .nc s'ouvrait, mais restait introuvable dans la boîte d'ouverture.

### Ce que Solidon voit dans le modèle

- Dans les fichiers importés, Solidon reconnaît maintenant perçages et poches même quand le maillage n'est pas soudé. Avant, la détection n'y trouvait rien.
- Le rapport signale « plusieurs pièces » seulement quand il y en a. Une plaque d'un seul tenant comptait pour 796.
- Le même fichier n'est plus examiné quinze fois. Cela épargne les secondes qui passaient à l'ouverture.
- Quand la simplification ne va pas aussi loin que demandé, Solidon le dit. Jusqu'ici 992 triangles restaient là où 400 étaient voulus, sans un mot.
- Le même avis figure une fois dans le rapport, pas à nouveau après chaque étape.
- Deux corps au même endroit ressemblaient à un seul, et personne ne le disait.
- Après une union, un élément pointait vers un autre trou qu'avant.

### Chat et agent

- Pendant que l'agent travaille, le chat indique quelle étape tourne et quel outil. Avant, il se taisait jusqu'à une minute.
- La liste des modèles locaux dit pour chacun avec quelle fiabilité il appelle les outils et combien de temps il met. Un modèle qui se contente d'en parler se reconnaît désormais.
- Si la liaison avec le modèle de langue local se rompt, Solidon le dit — et propose une suite au lieu d'annoncer une erreur de programme.
- Il en va de même si la liaison avec le service d'images se rompt.
- Le chat nomme aussi les petites variations de volume. Un perçage posé s'annonçait « +0,00 cm³ », et la proposition semblait sans effet.

### Vue et maniement

- L'arbre des objets nomme tenons et filetages, avec diamètre et pas.
- Une étape qui crée deux corps figure dans l'arbre avec deux lignes — avant il y en avait une.
- Si vous sélectionnez plus de corps qu'une opération n'en prend, vous voyez maintenant lesquels sont utilisés.
- L'impression affichait la même durée différemment à deux endroits : « 10 h 5 min » en bas, « 605 min » dans la boîte de dialogue.
- Nombres et unités se lisent partout pareil : une ligne et sa propre infobulle nommaient le même volume différemment, et en pouces pas du tout.
- Une cote accepte une expression dans chaque champ numérique — le manuel montre maintenant aussi le bouton.
- La grille de l'éditeur d'esquisse montrait l'écart du moment où l'on y entrait.
- Deux champs de texte se déclaraient facultatifs et ne l'étaient jamais.

### Corrigé

- Dupliquer donnait à l'original un nouvel identifiant, et le corps disparaissait de la vue.
- Un corps exact dont un perçage ne laissait rien restait dans l'arbre comme objet vide et pouvait être enregistré.
- La vue des différences et les cartes d'analyse restaient muettes sur les corps exacts.
- Un type de champ inconnu transformait en silence chaque champ en champ de texte.
- Une boîte de dialogue se validait, posait une étape dans l'historique — et rien ne changeait à l'image.
- Tourner de zéro degré passait en silence au lieu de dire que rien ne se produit.
- La fenêtre des nouveautés montrait soixante-quinze points comme un mur. Ils sont groupés maintenant, et l'annonce arrive dans votre langue.

## 0.2.0


### Blocs
- Vos propres blocs sans une ligne de code : sélectionnez des étapes dans l'historique et placez-les dans le catalogue comme bloc — avec vos champs, un aperçu et une plage de valeurs à votre mesure.
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
- Le choix de filament par emplacement de matériau parvient au slicer. C'était le texte affiché qui était enregistré, pas le profil.

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
- Les gros fichiers d'un slicer s'ouvrent sans que la fenêtre se fige. Auparavant, le simple comptage des corps chargeait tout le fichier en mémoire.
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
- Le transfert vers le slicer atteint le plateau. Avec CuraEngine, les pièces se retrouvaient à côté.
- Lors d'une découpe avec goupilles, les trous correspondants se placent dans la bonne moitié.
- Millimètres et pouces valent maintenant partout où figure un nombre — y compris dans les barres d'outils et lors de la peinture.
- La progression reste affichée jusqu'à la fin réelle du calcul, et la fenêtre demeure utilisable pendant ce temps.
- Tous les raccourcis clavier figurent désormais dans un aperçu unique : dans le menu Aide, sous « Raccourcis clavier », ou en appuyant sur la touche point d’interrogation.
