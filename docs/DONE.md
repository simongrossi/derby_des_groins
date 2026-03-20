# DONE - Derby des Groins

Liste des fonctionnalités et idées déjà implémentées dans le projet.

## Gestion des Courses
- **Gestion des courses vides / sous-peuplées** : Mise en place d'une règle configurable (`min_real_participants`) pour remplir automatiquement les courses avec des bots ou les annuler.
- **Remboursement automatique** : Les paris sur les courses annulées sont désormais automatiquement remboursés aux utilisateurs.
- **Scaling des Bots** : Les bots ajoutés aux courses s'adaptent désormais au niveau moyen des participants réels (90% à 110% de la puissance moyenne).

## Poids et Stratégie
- **Système de poids tactique** : Le poids influence désormais dynamiquement les statistiques de Force et d'Agilité.
    - **Surnourri** : Gain de Force (effet bulldozer) mais perte massive d'Agilité.
    - **Sous-poids** : Gain d'Agilité (très vif) mais perte de Force (manque d'impact).
- **Indicateurs visuels** : Affichage explicite des modificateurs de stats sur le tableau de bord et la page du cochon.

## Reproduction et Héritage
- **Système de reproduction** : Deux cochons actifs peuvent lancer une portée pour générer un porcelet.
- **Hérédité** : Les porcelets héritent partiellement des statistiques, de la rareté et de l'origine de leurs parents.
- **Retraite d'honneur & Héritage permanent** : Les cochons légendaires ou victorieux peuvent être mis à la retraite pour booster l'héritage de la porcherie et renforcer leur lignée.
- **Pression de nourrissage** : Le coût des céréales augmente avec le nombre de cochons dans la porcherie (+20% par cochon supplémentaire) pour équilibrer la progression.

## Bourse aux Grains (Marche dynamique)
- **Grille de cotation 5x5** : un curseur partage entre tous les joueurs determine le prix (axe X) et la qualite (axe Y) de la nourriture.
- **Points de mouvement** : chaque joueur accumule des points en achetant (1 pt / 10 achats) et peut deplacer le curseur pour influencer les prix.
- **Vitrine anti-spam** : le dernier grain achete est bloque pour tous jusqu'a ce qu'un autre grain soit achete, forcant la variete.
- **Prix dynamiques** : le cout final combine le modificateur Bourse, la pression de porcherie et le cout de base.
- **Qualite variable** : les bonus de faim, energie et stats sont multiplies par le modificateur de qualite de la grille.
- **Interface dediee** (`/bourse`) : grille visuelle, controles directionnels, selecteur de cochon, cartes de cereales avec prix ajustes.
- **Modele GrainMarket** : singleton en base pour stocker l'etat partage du marche.

## Classement enrichi
- **5 onglets** : General, Abattoir & Cimetiere, Paris & Fortune, Elevage & Ecole, Mur de la Honte.
- **Palmares complet** : 18+ awards automatiques (Roi du Derby, Boucher en Chef, Kamikaze Supreme, Le Pigeon, etc.).
- **Charts supplementaires** : morts empilees par cause, donut des causes de deces, profit/perte paris, taux de reussite, courses disputees, win rate.
- **Mur de la Honte** : classements des pires performances (looser, boucher, pigeon, negligent, flambeur, rat fauche, gaveur).

## Infrastructure et Admin
- **Configuration Admin** : Ajout de réglages dans le panneau d'administration pour les seuils de participants et les modes de gestion des courses vides.
- **Historique étendu** : Les courses annulées apparaissent désormais dans l'historique pour une meilleure transparence.
