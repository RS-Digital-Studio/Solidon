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
- La recherche reconnaît aussi 146 termes courants des trancheurs, dont *perimeters* et *wall loops*.
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
