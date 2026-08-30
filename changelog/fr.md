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

## 0.2.3


### Partager des blocs

- Un bloc que vous avez construit se transmet sous forme de recette, et ceux des autres se reprennent de même. Une recette est la liste de vos étapes avec leurs valeurs.
- Qui reprend une recette ne reçoit pas une forme finie, mais vos étapes — et peut en changer chaque chiffre.
- En le transmettant, vous choisissez ce que les autres peuvent en faire : l'utiliser librement, vous citer, ou vous citer et partager aux mêmes conditions.
- Un bloc repris reste signalé comme celui d'un autre. Si l'un des vôtres porte le même nom, le vôtre l'emporte.

### Historique et annulation

- Qui pousse une pièce trois fois de suite obtient une étape dans l'historique, pas trois. Une seule annulation retire tout le mouvement.
- Les étapes qui vont ensemble forment une entrée et se replient. L'historique reste lisible même quand il en contient beaucoup.
- Après une rotation, la pièce se repose sur le plateau. Les deux ensemble font une étape, et une annulation retire les deux.

### Dessin et cotes

- Un cercle demande son diamètre et non son rayon. Ce que vous tapez est le chiffre que vous mesurerez sur la pièce finie.
- Échap retire ce que vous êtes en train de faire : d'abord la ligne commencée, puis l'outil, puis l'esquisse.
- Le bouton des formes de base porte le nom de ce qu'un clic dessus fait. Les autres formes restent derrière la flèche à côté.
- L'indication de l'esquisse nomme les deux voies : dessiner un contour ou insérer une forme toute faite.
- Un nouveau projet d'exemple montre le dessin avec cotes et contraintes. Qui parcourt les exemples le rencontre dès le début.

### Quand quelque chose ne tiendra pas, il le dit maintenant

- Un crochet de panneau perforé dont l'ergot ne pointe pas vers le haut le dit à la pose. Avant, vous obteniez une pièce qui semblait juste et ne tenait pas.
- Une charnière film posée de chant dans la pièce est signalée au lieu d'être imprimée. Imprimée ainsi, elle casse à la première ouverture.
- Un motif de surface qui manque le corps le dit. Avant, des morceaux détachés restaient à côté sans que rien ne le signale.

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
- Les valeurs de chaque bobine arrivent dans le fichier 3MF et le trancheur au bon emplacement de matière. Une couleur ne reprend plus par erreur les valeurs d'une autre.
- Au premier démarrage, Solidon reprend les filaments chargés dans le trancheur avec leur nom, type, couleur et profil du fabricant. Les bobines ne sont pas à recréer.
- Les exemples fournis ne remplacent plus l'imprimante et le matériau choisis par les réglages qui ont servi à créer leurs aperçus.
- Dans le Flatpak Linux, Solidon trouve et lance les trancheurs de l'ordinateur, y compris les AppImages. Les deux programmes accèdent au dossier de travail partagé.
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

### Impression et trancheur

- Au tranchage, vous choisissez quels plateaux partent. Qui voulait trancher le plateau 2 recevait trois fichiers et les bobines du plateau 1.
- Solidon écrit maintenant le profil de machine et de processus pour le trancheur, au lieu de renvoyer à son fonds. Sept réglages figuraient dans le fichier, cent trente-six sont partis au trancheur.
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
