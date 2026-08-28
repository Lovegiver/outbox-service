# Audit de Couverture BDD OB1

## Date de Verification

2026-08-20

## Resultat Local

Commande executee depuis le repository backend :

```text
.venv/bin/python -m pytest tests/bdd -q
```

Resultat :

```text
240 passed
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
- `features/metric_yaml_versions.feature`

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
- rejet du login pour utilisateur inactif ;
- rejet des formats email invalides et de l'email vide ;
- normalisation des emails a l'inscription et au login ;
- unicite des emails insensible a la casse ;
- validation des bornes et de la complexite des mots de passe ;
- endpoint d'identite authentifie ;
- rejet d'identite sans token ;
- rejet d'identite avec token invalide ;
- rejet d'identite avec token expire ;
- rejet d'identite avec signature incorrecte, claim `sub` absent, utilisateur
  inconnu ou type de token inattendu ;
- rejet d'identite pour utilisateur inactif.

La verification email reste rattachee a la fonctionnalite produit future #22 et
ne fait pas partie du contrat d'authentification actuellement implemente.

### Authorization Transverse

Executable et vert dans une feature transverse dediee.

Couvert indirectement :

- JWT absent sur `/auth/me` ;
- JWT invalide sur `/auth/me` ;
- JWT expire sur `/auth/me` ;
- utilisateur inactif sur `/auth/me` ;
- acces admin global dans Projects et EventTypes ;
- effets des permissions OWNER/DEVELOPER/VIEWER sur Projects, EventTypes, Schemas, Routes, API Keys, Metrics et Dead Letters ;
- cas `403` pour utilisateur non membre ;
- API key absente, invalide ou revoquee sur l'ingestion d'Events.
- matrice complete OWNER/DEVELOPER/VIEWER/non-membre/ADMIN sur les permissions
  Project, EventType, Schema, Route, API Key et Metrics ;
- contrats `401` pour authentification absente ou invalide et `403` pour un
  acteur authentifie sans permission ;
- vocabulaire role-based pour les scenarios metier et permission-based pour
  les controles transverses.
- isolation d'une API key lorsqu'elle tente d'ingerer dans un autre Project.

Aucun manque critique immediat n'a ete identifie pour l'autorisation
transverse.

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

Executable et vert.

Couvert :

- contrat absent retourne `404` ;
- contrat actif retourne `contract_name`, `version` et le schema ;
- schema retourne exactement celui persiste ;
- plusieurs versions ne retournent que la version active ;
- contrat systeme independant du Project utilisateur courant.

La feature `contracts.feature` couvre les cinq scenarios du contrat public.

### Legacy / System Metrics

Executable et vert.

Couvert :

- listing de toutes les metrics systeme persistees ;
- listing de la derniere valeur par metric ;
- reponse coherente sans metric ;
- exposition Prometheus legacy ;
- transformation des `.` en `_` ;
- presence de `# TYPE` et d'une valeur numerique ;
- separation des metrics systeme et du vocabulaire MetricState metier.

La feature `legacy_metrics.feature` couvre les six scenarios du comportement
legacy.

### Runtime Metrics Dashboard

Executable et vert.

Couvert :

- summary vide sur base vide ;
- compteur total d'Events ;
- compteurs d'Events routed, unroutable et failed ;
- compteurs de deliveries par statut ;
- compteur dead-letter ;
- compteur de retries ;
- age du plus ancien Event `RECEIVED` ;
- age de la plus ancienne delivery `PENDING` ;
- PostgreSQL comme source de verite, independamment des evenements WebSocket live ;
- coherence des compteurs apres retry d'une dead letter.

Aucun manque critique immediat n'a ete identifie.

### YAML Metrics Observatory

Le CRUD/listing de base des MetricDefinition et le lot BDD-015A sont
exécutables et verts.

Couvert :

- creer une MetricDefinition ;
- rejet de creation par VIEWER ;
- rejet de creation pour EventType inconnu ;
- rejet de code duplique sur le meme EventType ;
- meme code autorise sur deux EventTypes differents ;
- listing des MetricDefinitions ;
- rejet du listing pour non-membre.
- création d'une version YAML validée contre un schema du même EventType ;
- attribution interne et concurrente d'un numéro de version monotone ;
- conservation exacte du YAML et listing de l'historique immuable ;
- rejet de la syntaxe, des paths et des transforms incompatibles ;
- acceptation et compilation du caractère optionnel d'un champ ;
- validation et preview via les interfaces publiques ;
- contenu fonctionnel et déterministe du plan compilé ;
- absence de persistance après preview valide ou invalide ;
- absence de version partielle après création invalide ;
- permissions, ressources inconnues et isolation entre EventTypes ;
- absence de création de ProcessingChain ou ProcessingPlan pendant le lot 1.

Scenarios pertinents manquants :

- creer une compatibilite YAML/schema ;
- reconstruire une ProcessingChain lors de la compatibilite ;
- desactiver l'ancienne ProcessingChain lors de l'activation d'une nouvelle ;
- rebuild manuel activant une chain ;
- coherence du contenu des ProcessingPlans.

### Metric Builder

La feature executable `metric_builder_schema_contract.feature` couvre
BDD-016A : inspection conservatrice du schema, obligation imbriquee,
nullabilite, six intents Counter, bornes de `sum_value`, politique statique des
labels, chemins bornes, collisions Prometheus, entrees dangereuses inertes et
absence de toute ecriture pendant la preview.

La feature executable `metric_builder_atomic_creation.feature` couvre
BDD-016B : triplet definition/version/compatibilite exact, rejeu idempotent,
conflits de contenu et de nom Prometheus, schema explicite, absence de rebuild,
absence d'activation et preservation d'une chaine ACTIVE. Les tests
PostgreSQL associes prouvent le rollback apres chaque flush et la serialisation
de creations concurrentes. Rebuild et activation restent explicitement dans
BDD-016C.

### Prometheus Metric State

La feature executable `prometheus_metric_state.feature` couvre 17 scenarios :

- endpoint par Project, cas vide et Project inconnu ;
- lecture exclusive du MetricState sans recalcul pendant le scrape ;
- aggregation cumulative, idempotence, checkpoint, atomicite et isolation
  transactionnelle des flux pendant un meme cycle worker ;
- series distinctes par dimensions et isolation entre Projects ;
- exposition de plusieurs EventTypes du meme Project ;
- labels plateforme, collision reservee, tri et echappement ;
- nom Prometheus-safe, ordre deterministe et `# TYPE` unique ;
- contrat `Content-Type` du format texte Prometheus.

## Synchronisation GitHub Effectuee

Les issues BDD GitHub ont ete mises a jour pour refleter l'etat local :

- BDD-001 Authentication : scenarios existants coches, scenarios manquants ajoutes.
- BDD-002 Authorization transverse : scenarios indirectement couverts coches, reste une feature transverse compacte a creer.
- BDD-003 a BDD-009 : scenarios listes coches lorsqu'ils sont couverts et verts.
- BDD-010 Worker / Routing / Deliveries : cycle routing/delivery coche, publication runtime et aggregation MetricState laissees ouvertes.
- BDD-011 Dead Letters : scenarios listes coches, scenarios deja couverts ajoutes.
- BDD-012 à BDD-017 : les lots finalisés sont synchronisés ; BDD-015B,
  BDD-015C et BDD-016 restent ouverts après la finalisation de BDD-015A.

Les issues de clarification produit doivent rester ouvertes : elles necessitent des decisions metier ou d'architecture, pas seulement une synchronisation de tests.

BDD-015 est désormais découpée en trois lots : BDD-015A (#60), BDD-015B
(#61) et BDD-015C (#62). Le lot A est implémenté sur sa branche dédiée ; les
lots B et C restent ouverts et ordonnés avant BDD-016 (#20).
