# Transparence Joueur

Ce document explique comment la transparence des regles est exposee dans l'interface web.

## Principe

Objectif:
- aucun mecanisme critique ne doit reposer sur une regle "cachee";
- un joueur doit pouvoir comprendre sans lire le code:
  - comment faire progresser un cochon;
  - pourquoi il ne peut plus lancer une action;
  - comment l'economie BitGroins circule;
  - pourquoi un cochon se blesse, meurt, ou prend sa retraite.

## Etat avant la mise a plat de mars 2026

Les aides existaient deja mais elles etaient fragmentees:
- `Mon Cochon` expliquait plusieurs jauges et seuils;
- `Bourse` embarquait une aide locale;
- `Paris` expliquait surtout les tickets et la mise;
- la documentation depot et certaines anciennes notes d'equilibrage n'etaient plus entierement alignees.

Le resultat:
- difficultes a comprendre l'algo de progression;
- incomprehension sur la logique blessures / veto / mort;
- confusion entre regles permanentes et simples choix de balancing temporaires.

## Etat cible maintenant en place

### 1. Un hub unique public

La page `/regles` est la reference joueur dans l'interface.

Elle regroupe:
- demarrage;
- stats et niveau;
- energie, satiete, humeur, fraicheur, poids;
- courses et recompenses;
- blessures, veto, mort et retraite;
- paris et tickets;
- economie d'elevage;
- Bourse aux Grains;
- marche, galerie et mini-jeux.

### 2. Des liens contextuels depuis les pages critiques

Ajouts dans l'interface:
- `Mon Cochon` pointe vers les sections progression et jauges;
- `Paris` pointe vers les regles de tickets et de formats de paris;
- `Bourse` pointe vers les regles du marche et leur impact economique;
- le menu principal contient maintenant une entree `Regles`.

### 3. Une doc depot alignee

Les fichiers a conserver a jour:
- `docs/regles_du_jeu.md` pour la regle metier documentee;
- `docs/transparence_joueur.md` pour la strategie d'exposition dans l'UI;
- `README.md` pour l'orientation globale et les liens de docs.

## Ce qui doit toujours etre visible pour un joueur

Liste minimale de transparence:
- seuils bloquants de course: energie et satiete;
- cooldown ecole / typing;
- quota de courses par semaine;
- nombre de Tickets Bacon;
- mise mini / maxi;
- fermeture des paris 30 secondes avant le depart;
- existence d'un cap payout si actif;
- fenetre veterinaire;
- regle d'acces au marche;
- pression de nourrissage par cochon supplementaire;
- conditions de retraite d'honneur;
- table claire des actions qui montent les stats.

## Ce qui peut rester "ambiance" sans nuire a la transparence

On n'a pas besoin d'exposer au joueur:
- tous les details internes du moteur tour par tour;
- les structures SQL;
- les details techniques de cache, scheduler ou verrouillage en base.

En revanche, les effets visibles doivent rester explicites:
- ce qui modifie la perf;
- ce qui modifie le risque;
- ce qui modifie l'economie.

## Regle de maintenance

A chaque gros reequilibrage:
1. mettre a jour la logique de jeu;
2. mettre a jour `/regles`;
3. mettre a jour `docs/regles_du_jeu.md`;
4. verifier les liens contextuels sur `Mon Cochon`, `Paris`, `Bourse`.

Sans cette chaine complete, la transparence se degrade tres vite.
