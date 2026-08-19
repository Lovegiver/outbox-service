# Audit de Couverture BDD OB1

## Date de Verification

2026-08-17

## Resultat Local

Commande executee depuis le repository backend :

```text
.venv/bin/python -m pytest tests/bdd -q
```

Resultat :

```text
107 passed
```

Warnings observes :

- Passlib importe `crypt`, deprecie et cible pour suppression dans Python 3.13.
- Le secret JWT de test est plus court que la longueur recommandee pour HMAC SHA-256.
- Deux warnings SQLAlchemy indiquent une transaction deja dissociee de la connexion au moment du rollback.

## Etat de Collecte

Features BDD executables collectees :

- `features/authentication.feature`
- `features/projects.feature`
- `features/project_members.feature`
- `features/api_keys.feature`
- `features/event_types.feature`
- `features/schema_definitions.feature`
- `features/routes.feature`
- `features/events.feature`
- `features/event_deliveries.feature`
- `features/delivery_worker.feature`
- `features/dead_letters.feature`
- `features/metric_definitions.feature`

Fichier de feature present mais non collecte :

- `metrics/metric_builder.feature`

Le scenario Metric Builder est redige en Gherkin, mais aucun module pytest n'appelle `scenarios("metrics/metric_builder.feature")`. Il ne constitue donc pas encore une couverture BDD executable.

## Couverture Par Domaine Fonctionnel

### Authentication

Executable et vert.

Couvert :

- inscription utilisateur ;
- rejet d'email deja utilise ;
- login valide ;
- rejet de mot de passe invalide ;
- rejet d'utilisateur inconnu ;
- endpoint d'identite authentifie ;
- rejet d'identite sans token ;
- rejet d'identite avec token invalide ;
- rejet d'identite avec token expire ;
- rejet d'identite pour utilisateur inactif.

Scenarios pertinents manquants :

- rejet du login pour utilisateur inactif ;
- format email invalide ;
- limites de politique de mot de passe une fois la politique produit definie ;
- verification email une fois la fonctionnalite implementee.

### Authorization Transverse

Partiellement couvert par les autres fichiers de feature, mais il n'existe pas encore de feature transverse dediee a l'autorisation.

Couvert indirectement :

- JWT absent sur `/auth/me` ;
- JWT invalide sur `/auth/me` ;
- JWT expire sur `/auth/me` ;
- utilisateur inactif sur `/auth/me` ;
- acces admin global dans Projects et EventTypes ;
- effets des permissions OWNER/DEVELOPER/VIEWER sur Projects, EventTypes, Schemas, Routes, API Keys, Metrics et Dead Letters ;
- cas `403` pour utilisateur non membre ;
- API key absente, invalide ou revoquee sur l'ingestion d'Events.

Scenarios pertinents manquants :

- une feature BDD transverse compacte qui prouve la matrice de permissions sans dupliquer chaque feature metier ;
- documentation explicite du vocabulaire BDD role-based vs permission-based.

### Projects

Executable et vert.

Couvert :

- creation de Project par utilisateur authentifie ;
- membership OWNER automatique pour le createur ;
- rejet du nom de Project duplique ;
- listing limite aux Projects visibles par l'utilisateur ;
- listing global par admin ;
- desactivation de Project par utilisateur autorise ;
- rejet de desactivation sans `PROJECT_WRITE` ;
- rejet de desactivation d'un Project inexistant.

Aucun manque critique immediat n'a ete identifie.

### Project Members

Executable et vert.

Couvert :

- listing des membres par membre autorise ;
- rejet du listing sans membership ou permission de lecture ;
- ajout d'un utilisateur existant ;
- rejet d'ajout d'un utilisateur inconnu ;
- rejet de membership duplique dans le meme Project ;
- modification de role ;
- rejet de modification sans `PROJECT_WRITE` ;
- suppression de membre ;
- rejet de suppression d'un non-membre ;
- protection contre la suppression du dernier OWNER ;
- protection contre la retrogradation du dernier OWNER.

Scenarios pertinents manquants :

- un utilisateur peut etre membre de plusieurs Projects ;
- le scenario de membership duplique devrait etre renomme pour expliciter "dans le meme Project" ;
- workflow d'invitation pour utilisateurs inconnus une fois la decision produit prise.

### API Keys

Executable et vert.

Couvert :

- creation par utilisateur autorise ;
- secret complet visible uniquement a la creation ;
- listing sans secrets complets ;
- rejet de creation sans `API_KEY_WRITE` ;
- revocation ;
- rejet de revocation d'une cle inconnue ;
- cle revoquee rejetee sur ingestion ;
- rotation ;
- ancienne cle rejetee apres rotation ;
- nouvelle cle acceptee apres rotation.

Aucun manque critique immediat n'a ete identifie.

### Event Types

Executable et vert.

Couvert :

- creation dans un Project actif ;
- rejet de creation sans `EVENT_TYPE_WRITE` ;
- rejet de creation pour Project inconnu ;
- rejet de creation dans Project inactif ;
- rejet de code duplique dans le Project ;
- listing des EventTypes d'un Project ;
- lecture autorisee ;
- rejet de lecture non autorisee ;
- lecture par admin global.

Aucun manque critique immediat n'a ete identifie.

### Schema Definitions

Executable et vert.

Couvert :

- creation de JSON Schema pour un EventType ;
- nouveau schema devenant actif ;
- listing retournant le schema actif ;
- listing vide lorsqu'aucun schema actif n'existe ;
- rejet de creation sans `SCHEMA_WRITE` ;
- rejet de listing sans `SCHEMA_READ` ;
- rejet de creation pour EventType inconnu.

Scenarios pertinents manquants :

- desactivation du schema precedent lorsqu'un nouveau schema devient actif, si c'est bien l'invariant attendu ;
- rejet d'un JSON Schema invalide, si ce n'est pas couvert ailleurs.

### Routes

Executable et vert.

Couvert :

- creation de route ;
- listing de routes ;
- modification de route ;
- rejet de creation sans `ROUTE_WRITE` ;
- rejet de listing sans `ROUTE_READ` ;
- rejet de creation pour EventType inconnu ;
- rejet de modification de route inconnue ;
- route creee influencant les deliveries generees ;
- route modifiee influencant les deliveries ulterieures.

Scenarios pertinents manquants :

- URL de destination manquante rejetee au moment de la configuration de route si le modele de transport exige des endpoints HTTP ;
- scenarios de modele de transport une fois la frontiere RouteDefinition / ProcessStep / ProcessTransition clarifiee.

### Event Ingress

Executable et vert.

Couvert :

- ingestion avec API key valide ;
- rejet sans API key ;
- rejet avec API key invalide ;
- rejet avec API key revoquee ;
- rejet de payload avec champ requis manquant ;
- rejet de payload avec type JSON invalide ;
- rejet lorsqu'aucun schema actif n'existe ;
- generation automatique de l'Event UUID ;
- conservation de l'Event UUID fourni et du correlation ID ;
- rejet d'Event UUID duplique ;
- ingestion ne declenchant pas le worker.

Aucun manque critique immediat n'a ete identifie.

### Event Deliveries

Executable et vert.

Couvert :

- une Route active cree une delivery pending ;
- plusieurs Routes actives creent plusieurs deliveries ;
- aucune Route active rend l'Event `UNROUTABLE` sans delivery ;
- rerouter un Event deja route ne duplique pas les deliveries ;
- la delivery appartient toujours a l'Event route ;
- la delivery capture le type de destination, l'URL, le statut initial, le nombre de tentatives et l'absence de derniere erreur.

Scenarios pertinents manquants :

- publication d'evenements runtime pendant le routage non verifiee.

### Delivery Worker

Executable et vert.

Couvert :

- succes d'une delivery webhook pending ;
- persistence d'un echec webhook ;
- delivery deja `DELIVERED` non retraitee ;
- delivery `DEAD_LETTER` non retraitee ;
- delivery `FAILED` retryable retraitee ;
- type de destination non supporte faisant echouer la delivery ;
- URL de destination manquante faisant echouer la delivery ;
- dernier echec faisant passer la delivery en dead letter ;
- delivery `FAILED` non retryable non retraitee ;
- plusieurs deliveries pending traitees dans un meme passage ;
- succes webhook envoyant le payload d'Event vers l'URL de destination ;
- identifiant de delivery inexistant ignore proprement.

Scenarios pertinents manquants :

- evenements runtime `DELIVERY_STARTED`, `DELIVERY_SUCCEEDED`, `DELIVERY_FAILED` et `DELIVERY_DEAD_LETTERED` non verifies.

### Dead Letters

Executable et vert.

Couvert :

- viewer projet pouvant lister les dead letters du Project ;
- listing limite au Project demande ;
- non-membre ne pouvant pas lister les dead letters ;
- developer pouvant relancer une dead letter ;
- viewer ne pouvant pas relancer une dead letter ;
- retry d'une dead letter inconnue retournant not found ;
- retry d'une delivery non dead-letter rejete ;
- retry-all requeue uniquement les dead letters du Project.

Aucun manque critique immediat n'a ete identifie.

### Contracts

Aucune feature BDD executable trouvee.

Scenarios pertinents :

- le dernier contrat Outbox Event retourne le contrat actif `OUTBOX_EVENT` ;
- absence de contrat actif retournant `404` ;
- reponse contenant `contract_name` ;
- reponse contenant `version` ;
- reponse contenant `schema` ;
- schema retourne correspondant au JSON Schema actif persiste.

### Legacy / System Metrics

Aucune feature BDD executable trouvee.

Scenarios pertinents :

- lister toutes les system metrics persistees ;
- lister les dernieres metrics ;
- exposition texte Prometheus legacy ;
- normalisation des noms de metriques avec remplacement des points par underscores ;
- sortie `# TYPE` ;
- valeur numerique exposee ;
- comportement a vide.

### Runtime Metrics Dashboard

Aucune feature BDD executable trouvee.

Scenarios pertinents :

- summary vide sur base vide ;
- compteur total d'Events ;
- compteurs d'Events routed, unroutable et failed ;
- compteurs de deliveries par statut ;
- compteur dead-letter ;
- compteur de retries ;
- age du plus ancien Event `RECEIVED` ;
- age de la plus ancienne delivery `PENDING` ;
- PostgreSQL comme source de verite, independamment des evenements WebSocket live.

### YAML Metrics Observatory

Seul le CRUD/listing de base des MetricDefinition est executable et vert.

Couvert :

- creer une MetricDefinition ;
- rejet de creation par VIEWER ;
- rejet de creation pour EventType inconnu ;
- rejet de code duplique sur le meme EventType ;
- meme code autorise sur deux EventTypes differents ;
- listing des MetricDefinitions ;
- rejet du listing pour non-membre.

Scenarios pertinents manquants :

- creer une version YAML ;
- valider un YAML valide ;
- retourner `valid=false` pour YAML invalide ;
- rejeter un path inexistant ;
- rejeter un transform incompatible ;
- accepter un champ optionnel compatible ;
- previsualiser le plan compile ;
- retourner des erreurs lors d'une preview invalide ;
- creer une compatibilite YAML/schema ;
- reconstruire une ProcessingChain lors de la compatibilite ;
- desactiver l'ancienne ProcessingChain lors de l'activation d'une nouvelle ;
- rebuild manuel activant une chain ;
- coherence du contenu des ProcessingPlans.

### Metric Builder

Le Gherkin existe mais n'est pas executable.

Scenarios pertinents :

- lister les champs depuis le JSON Schema actif ;
- lister les champs pour un schema id explicite ;
- rejeter un schema inconnu ;
- exposer path, type JSON, required, label_allowed, value_intents, cardinality_risk et warnings ;
- preview `count_event` ;
- preview `count_by_label` ;
- warning sur labels a forte cardinalite ;
- rejet d'intention incompatible avec le champ ;
- creation de MetricDefinition et premiere version YAML ;
- retour des warnings a la creation ;
- rejet d'une requete builder invalide.

### Prometheus Metric State

Aucune feature BDD executable trouvee.

Scenarios pertinents :

- exposer uniquement le MetricState materialise ;
- ne pas recalculer depuis les Events au moment du scrape ;
- rendre le format counter ;
- trier les labels ;
- echapper les guillemets dans les labels ;
- retourner une reponse vide sans state ;
- exposer plusieurs series pour un meme metric_code avec labels differents ;
- emettre `# TYPE` une seule fois par nom de metrique Prometheus.

## Synchronisation GitHub Effectuee

Les issues BDD GitHub ont ete mises a jour pour refleter l'etat local :

- BDD-001 Authentication : scenarios existants coches, scenarios manquants ajoutes.
- BDD-002 Authorization transverse : scenarios indirectement couverts coches, reste une feature transverse compacte a creer.
- BDD-003 a BDD-009 : scenarios listes coches lorsqu'ils sont couverts et verts.
- BDD-010 Worker / Routing / Deliveries : cycle routing/delivery coche, publication runtime et aggregation MetricState laissees ouvertes.
- BDD-011 Dead Letters : scenarios listes coches, scenarios deja couverts ajoutes.
- BDD-012 a BDD-017 : zones majoritairement non couvertes laissees ouvertes, sauf la partie MetricDefinition de base qui recoupe BDD-015.

Les issues de clarification produit doivent rester ouvertes : elles necessitent des decisions metier ou d'architecture, pas seulement une synchronisation de tests.
