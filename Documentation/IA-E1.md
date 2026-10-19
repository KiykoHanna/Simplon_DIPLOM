## Ressource open data

[https://data.europa.eu/en](https://data.europa.eu/en)  
[https://www.data.gouv.fr/fr/](https://www.data.gouv.fr/fr/)

https://api.gouv.fr/rechercher-api

## Résumé des actions à mener pour la mise en place d'un service numérique basé sur l'utilisation de données :

1. ### Collecte des données

   * Automatiser l'extraction depuis diverses sources (web, fichiers, bases de données, big data) en utilisant des scripts adaptés.  
   * Développer des requêtes SQL pour extraire les données des bases de données relationnelles et des systèmes big data.  
   * Agréger les données issues de différentes sources, supprimer les entrées corrompues et homogénéiser les formats.

2. ### Mise à disposition des données

   * Créer une base de données conforme au RGPD en modélisant la structure des données et en important les données préparées.  
   * Développer une API REST pour permettre l'exploitation du jeu de données par d'autres composants du projet.

## Descriptif des compétences à valider et critères d'évaluation :

### A1. Programmer la collecte de données

* #### **C1. Automatisation de l'extraction**

  * Compétences :  
    * Identifier les contraintes techniques des sources de données.  
    * Rédiger des spécifications techniques.  
    * Construire des requêtes HTTP.  
    * Lire des fichiers de données.  
    * Effectuer du web scraping.  
    * Se connecter à des bases de données et des systèmes big data.  
    * Filtrer et parser les données.  
    * Exécuter des requêtes SQL.  
  * Critères d'évaluation :  
    * Script fonctionnel récupérant toutes les données visées.  
    * Script structuré avec point de lancement, initialisation, traitement, gestion des erreurs et sauvegarde.  
    * Script versionné et accessible sur un dépôt Git.  
    * Extraction depuis plusieurs types de sources.

* #### **C2. Développement de requêtes SQL**

  * Compétences :  
    * Écrire des requêtes SQL pour extraire des données de bases de données et de systèmes big data.  
    * Documenter les requêtes.  
  * Critères d'évaluation :  
    * Requêtes fonctionnelles extrayant les données visées.  
    * Documentation expliquant les choix et les optimisations.

* #### **C3. Agrégation et nettoyage des données**

  * Compétences :  
    * Rédiger des spécifications techniques.  
    * Programmer l'agrégation, l'identification et la suppression des entrées corrompues, et l'homogénéisation des formats.  
    * Versionner et documenter les scripts.  
  * Critères d'évaluation :  
    * Script fonctionnel produisant un jeu de données unique, nettoyé et normalisé.  
    * Script versionné et accessible sur un dépôt Git.  
    * Documentation complète du script.

### A2. Développer la mise à disposition technique des données

* #### **C4. Création de la base de données**

  * Compétences :  
    * Rédiger des spécifications techniques.  
    * Modéliser la structure des données avec Merise.  
    * Choisir un système de gestion de base de données.  
    * Créer la base de données.  
    * Documenter l'installation et le script d'import.  
    * Mettre en conformité avec le RGPD (registre des traitements, procédures de tri).  
  * Critères d'évaluation :  
    * Modélisation conforme à Merise.  
    * Modèle physique fonctionnel.  
    * Choix de la base de données adapté.  
    * Procédures d'installation reproductibles.  
    * Script d'import fonctionnel et documenté.  
    * Conformité au RGPD assurée.

* #### **C5. Développement de l'API**

  * Compétences :  
    * Rédiger des spécifications techniques.  
    * Configurer les accès aux données.  
    * Développer la réception, la validation des requêtes, les requêtes à la base de données et les réponses de l'API.  
    * Gérer les autorisations et sécuriser l'API.  
    * Documenter l'API et l'accès à la base de données.  
  * Critères d'évaluation :  
    * Documentation technique complète de l'API.  
    * API fonctionnelle pour l'accès et la mise à disposition des données.  
    * Respect des spécifications et des règles d'autorisation.

## E1. Mise en situation (C1, C2, C3, C4, C5) 

L’évaluation doit se faire dans un contexte de réalisation d’un service numérique réel ou fictif basé sur l’usage de données, à partir du cadrage pour la réalisation d’un service numérique (spécifications fonctionnelles et techniques par exemple). Le projet évalué a pour but d’optimiser, d’automatiser, de pérenniser et de mettre à disposition les flux de données et les données, utiles et nécessaires à la réalisation du service numérique, par les équipes techniques (par exemple en analyse statistique, en business intelligence, en machine learning ou encore en intelligence artificielle).  
Livrable : rapport professionnel individuel  
Évaluation :  
\- Correction du rapport professionnel  
\- Soutenance orale individuelle

## A1 : Programmer la collecte de données depuis plusieurs sources pour un projet en intelligence artificielle

### C1. Automatiser l’extraction de données depuis un service web, une page web (scraping\*), un fichier de données, une base de données et un système big data\* en programmant le script\* adapté afin de pérenniser la collecte des données nécessaires au projet.

#### **Référentiel:** 

\- Identification des contraintes techniques propres aux sources de données (consulter la documentation, les règles de confidentialité, etc.).  
\- Rédaction des spécifications techniques pour l’extraction des données.  
\- Construction les requêtes HTTP pour la récupération des données depuis un service web (REST\*).  
\- Lecture d’un fichier de données dans un script (Python, R, etc.).  
\- Téléchargement de l’HTML d’une ou plusieurs pages web visées par une action de scraping.  
\- Connexion programmatique (Python, R, etc.) à un système de gestion de base de données et à un système big data (Hive, Apache Impala, etc.).  
\- Programmation des filtrages/parsing des données utiles dans les résultats obtenus depuis :  
\- une API,  
\- depuis la lecture d’un ou de plusieurs fichiers de données,  
\- et depuis l’HTML collecté d’un site web (scraping).  
\- Exécution programmatique des requêtes d’extraction de type SQL\*.  
\- Exécution programmatique des requêtes d’extraction depuis un système big data.

#### **Critères**

\- La présentation du projet et de son contexte est complète : acteurs, objectifs fonctionnels et techniques, environnements et contraintes techniques, budget, organisation du travail et planification.  
\- Les spécifications techniques précisent : les technologies et outils, les services externes, les exigences de programmation (langages), l’accessibilité (disponibilité, accès).  
\- Le périmètre des spécifications techniques est complet : il couvre l’ensemble des moyens techniques à mettre en œuvre pour l’extraction et l'agrégation des données en un jeu de données brutes final.  
\- Le script d’extraction des données est fonctionnel : toutes les données visées sont effectivement récupérées à l’issue de l’exécution du script.  
\- Le script comprend un point de lancement, l’initialisation des dépendances et des connexions externes, les règles logiques de traitement, la gestion des erreurs et des exceptions, la fin du traitement et la sauvegarde des résultats.  
\- Le script d’extraction des données est versionné\* et accessible depuis un dépôt Git\*.  
\- L’extraction des données est faite depuis un mix entre au moins les sources suivantes : un service web (API REST), un fichier de données, un scraping, une base de données et un système big data.

### C2. Développer des requêtes de type SQL d’extraction des données depuis un système de gestion de base de données et un système big data en appliquant le langage de requête propre au système afin de préparer la collecte des données nécessaires au projet.

#### **Référentiel:**

\- Ecriture des requêtes d’extraction de type SQL de récupération de données stockées en base de données et depuis un système big data (Hive, Spark, etc).  
\- Documentation des requêtes d’extraction

#### **Critères:**

\- Les requêtes de type SQL pour la collecte de données sont fonctionnelles : les données visées sont effectivement extraites suites à l'exécution des requêtes.  
\- La documentation des requêtes met en lumière choix de sélections, filtrages, conditions, jointures, etc., en fonction des objectifs de collecte.  
\- La documentation explicite les optimisations appliquées aux requêtes 

### C3. Développer des règles d'agrégation de données issues de différentes sources en programmant, sous forme de script, la suppression des entrées corrompues et en programmant l’homogénéisation des formats des données afin de préparer le stockage du jeu de données final.

#### **Référentiel:**

\- Rédaction des spécifications techniques pour l'agrégation des données.  
\- Programmation des règles d’agrégation des données collectées depuis chaque source en un jeu de données brutes unique.  
\- Programmation de l’identification des entrées corrompues dans le jeu de données (par exemple, données partielles et/ou manquantes).  
\- Programmation de la suppression des entrées corrompues.  
\- Programmation de l’identification des entrées au format non normalisé.  
\- Programmation de la l’homogénéisation des formats de données (par exemple, format des dates, des unités, etc.).  
\- Versionnement\* des scripts avec Git et un dépôt Git en ligne.  
\- Documentation des scripts.

#### **Critères:**

\- Le script d’agrégation des données est fonctionnel : les données sont effectivement agrégées, nettoyées et normalisées en un seul jeu de données à l’issue de l’exécution du script.  
\- Le script d’agrégation des données est versionné et accessible depuis un dépôt Git.  
\- La documentation du script d’agrégation est complète : dépendances, commandes, les enchaînements logiques de l’algorithme, les choix de nettoyage et d’homogénéisation des formats données.

## 

## A2 : Développer la mise à disposition technique des données collectées pour un projet d’intelligence artificielle

### C4. Créer une base de données dans le respect du RGPD en élaborant les modèles conceptuels et physiques des données à partir des données préparées et en programmant leur import afin de stocker le jeu de données du projet.

#### **Référentiel:**

\- Rédaction des spécifications techniques pour le stockage des données.  
\- Modélisation de la structure des données de la base de données selon la méthode Merise\*.  
\- Choix du système de gestion de base de données.  
\- Création de la base de données dans le système de gestion de base de données.  
\- Documentation de la procédure d’installation du système de gestion de base de données.  
\- Rédaction ou mise à jour du registre des traitements de données personnelles en vue de la mise en conformité de la base de données avec le RGPD.  
\- Rédaction des procédures de tri des données personnelles stockées dans la base de données pour la mise en conformité avec le RGPD (par exemple : détection et suppression des données personnelles inutiles, trop anciennes, etc.).  
\- Programmation du script d’import des données en base de données.  
\- Documentation du script d’import

#### **Critères:**

\- Les modélisations des données respectent la méthode et le formalisme Merise.  
\- Le modèle physique des données est fonctionnel : il est intégré avec succès lors de la création de la base de données, sans erreur.  
\- La base de données est choisie au regard de la modélisation des données et des contraintes du projet.  
\- La reproduction des procédures d’installation décrites (base de données et API) a pour résultat un système conforme aux objets techniques attendus..  
\- Le script d’import fourni est fonctionnel : il permet l’insertion des données dans le système mis en place.  
\- La documentation technique du script d’import est versionné à la racine du même dépôt Git que celui utilisé pour le script d’import.  
\- Les documentations techniques des script couvrent les parties suivantes :  
\- les dépendances nécessaires pour la réutilisation des scripts (langages, dépendances externes, etc)  
\- les commandes pour l’exécution des scripts.  
\- Le registre des traitements de données personnelles intègre l’ensemble des traitements de données personnelles impliqués dans la base de données.  
\- Les procédures de tri des données personnelles pour la mise en conformité de la base de données avec le RGPD sont rédigées.  
\- Les procédures de tri détaillent les traitements de conformité (automatisés ou non) à appliquer ainsi que leur fréquence d’exécution.

### C5. Développer une API mettant à disposition le jeu de données en utilisant l’architecture REST afin de permettre l’exploitation du jeu de données par les autres composants du projet

#### **Référentiel** 

\- Rédaction des spécifications techniques des moyens de mise à disposition et d’accès aux données du projet : API (REST) et accès direct à la base de données.  
\- Configuration des accès au jeu de données depuis le serveur de l’API.  
\- Développement de la réception et de la validation des requêtes client (web, mobile…)  
\- Développement des requêtes à la base de données en fonction de la mise à disposition des données prévues par les spécifications.  
\- Développement des réponses de l’API au client.  
\- Développement des règles d'autorisation et d’accès aux points de terminaison de l’API REST.  
\- Sécurisation de l’API : Top 10 OWASP API1 par exemple.  
\- Rédaction de la documentation technique de l’API REST.  
\- Rédaction de la documentation technique d’accès à la base de données adaptée aux environnements techniques du projet.

#### **Critères**

\- La documentation technique de l’API (REST) couvre tous les points de terminaisons.  
\- La documentation technique couvre les règles d’authentification et/ou d’autorisation de l’API.  
\- La documentation technique respecte les standards du modèle choisi (par exemple OpenAPI\*).

\- L’API REST est fonctionnelle pour l’accès aux données du projet : elle restreint par une autorisation (ou authentification) l'accès aux données,  
\- L’API REST est fonctionnelle pour la mise à disposition : elle permet la récupération de l’ensemble des données nécessaires au projet, comme prévu selon les spécifications données.  
