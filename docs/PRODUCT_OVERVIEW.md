# Vue Produit OB1

## Finalite

OB1 est un service de routage et de livraison d'evenements construit autour du pattern Outbox.

Son role est de recevoir des Events metier emis par des systemes externes, les valider, les persister durablement, les observer analytiquement, les router vers des destinations configurees, puis exposer un etat operationnel et runtime pour l'administration.

OB1 n'a pas vocation a devenir une plateforme BI, un outil de construction de dashboards, un moteur de workflow, une base de series temporelles, ni un remplacement de Prometheus ou Grafana. Il produit des donnees operationnelles et analytiques fiables que des outils specialises peuvent ensuite consommer.

## Vision Produit

OB1 fournit aux equipes un plan de controle pour les integrations evenementielles.

Les systemes externes publient des Events via une API publique d'ingestion. Les utilisateurs humains configurent les Projects, EventTypes, JSON Schemas, Routes, API Keys, definitions de metriques et comportements runtime via l'API d'administration et la future IHM OB1.

Le produit doit donner l'impression de piloter un moteur evenementiel vivant : durable, observable, explicite, et exploitable sans surprise en contexte d'exploitation.

## Concepts Principaux

### Project

Un Project est la frontiere principale d'isolation. Il regroupe les membres, API Keys, EventTypes, Routes, Events, deliveries, schemas et metriques.

Les Projects portent le RBAC via les memberships projet. Les utilisateurs OWNER ont le controle complet, les DEVELOPER peuvent configurer et operer la plupart des ressources projet, et les VIEWER peuvent consulter l'etat sans le modifier.

### Authentification et Autorisation

OB1 separe l'authentification humaine et l'authentification machine.

Les utilisateurs humains s'authentifient avec un JWT pour acceder aux endpoints d'administration. Les systemes externes s'authentifient avec des API Keys rattachees a un Project lorsqu'ils publient des Events vers `/events`.

L'autorisation repose sur les roles globaux, les memberships projet et les permissions projet comme `PROJECT_READ`, `EVENT_TYPE_WRITE`, `SCHEMA_WRITE`, `ROUTE_WRITE`, `API_KEY_WRITE` et `METRICS_WRITE`.

### EventType et JSON Schema

Un EventType represente un fait metier observable, par exemple `article.analyzed`, `order.created` ou `payment.failed`.

Chaque EventType appartient a un seul Project. Les JSON Schemas rattaches a un EventType definissent les payloads acceptes par l'API d'ingestion. Les schemas actifs constituent le contrat synchrone utilise pour accepter ou rejeter les Events entrants.

### Ingestion des Events

Les systemes externes soumettent les Events via `POST /events` avec l'en-tete `X-API-Key`.

Les Events acceptes sont valides synchroniquement contre le JSON Schema actif, persistés avec le statut `RECEIVED`, puis retournes a l'emetteur avec leur identite durable. L'ingestion ne lance ni routage ni livraison ; ces responsabilites appartiennent au pipeline worker.

### Routes et EventDeliveries

Les Routes definissent les destinations sortantes d'un EventType. Lorsque le worker route un Event recu, chaque Route active cree une EventDelivery.

Une EventDelivery est une unite durable de travail de livraison. Elle capture les informations de destination au moment du routage et evolue independamment via des statuts comme `PENDING`, `DELIVERED`, `FAILED` et `DEAD_LETTER`.

### Runtime Worker

Le worker execute le pipeline secondaire :

- extraire les observations analytiques des Events recus ;
- router les Events et creer les deliveries ;
- livrer les deliveries pending ou retryable ;
- faire passer les echecs terminaux en Dead Letter ;
- agreger les observations analytiques en MetricState ;
- publier des evenements runtime pour la supervision live.

Le worker est volontairement separe de l'ingestion afin que la publication d'un Event reste rapide et previsible.

### Dead Letters

Une Dead Letter est une EventDelivery ayant atteint un echec terminal de livraison.

Les Dead Letters restent visibles via l'API d'administration. Les utilisateurs autorises peuvent relancer une dead letter ou relancer toutes les dead letters d'un projet. Le retry remet la delivery dans un etat retraitable au lieu de masquer l'echec.

### Metriques et Observabilite

OB1 contient deux familles de metriques.

Les metriques systeme legacy exposent des compteurs operationnels via `/metrics`, `/metrics/latest` et `/metrics/prometheus`.

Les metriques metier sont definies par EventType. Les MetricDefinitions fournissent le nom metier stable. Les versions YAML decrivent comment extraire les observations depuis les payloads d'Events. La compatibilite schema active des ProcessingChains et ProcessingPlans precompiles. Au runtime, les observations sont persistees, agregees en MetricState, puis exposees au format texte Prometheus via `/metrics/event-types/{event_type_id}/prometheus-state`.

### Metric Builder

Le Metric Builder est une interface de plus haut niveau au-dessus des metriques YAML. Il permet a l'utilisateur de partir des champs du JSON Schema et d'une intention metier, de previsualiser le YAML genere et le plan compile, puis de creer une MetricDefinition et une premiere version YAML.

Cette fonctionnalite existe pour rendre la creation de metriques plus sure et plus ergonomique que l'edition YAML manuelle.

### Dashboard Runtime

Le dashboard d'administration doit hydrater ses compteurs durables depuis `GET /api/runtime/metrics/summary`, qui lit PostgreSQL comme source de verite.

Les evenements WebSocket disponibles sur `/runtime/events` servent a l'activite live et a l'animation de l'IHM, pas a produire les compteurs faisant autorite.

## Forme Actuelle du Backend

Le backend est une application FastAPI utilisant PostgreSQL, SQLAlchemy 2, Alembic, l'authentification JWT, les API Keys, le RBAC projet, un worker de fond et une suite de tests orientee BDD.

Le code est organise autour de models, repositories, services, routers, schemas et infrastructure de test. L'ordre d'implementation attendu reste :

```text
Models -> Alembic migration -> Database -> Repository -> Service -> API
```

## Frontieres Produit

OB1 doit rester concentre sur la production de donnees evenementielles et metriques fiables.

Il ne doit pas persister directement les donnees metier finales dans les bases applicatives des consommateurs. Par exemple, BlackHole peut envoyer un Event a OB1 ; OB1 le valide, le route, l'observe et le livre ; BlackHole persiste ensuite son propre etat metier.

Cette frontiere compte pour les futurs travaux sur les transports et les processus. OB1 peut supporter HTTP/webhook en premier puis d'autres transports plus tard, mais il doit conserver une separation claire entre cycle de vie de l'Event, cycle de vie de la Delivery et responsabilite metier downstream.

## Philosophie des Tests BDD

Les tests BDD doivent se comporter comme des clients externes de l'application.

Ils preparent l'etat avec des factories SQL, exercent les APIs publiques ou des points d'entree runtime explicites, puis verifient les resultats observables via des probes SQL independantes.

Les tests BDD ne doivent pas utiliser les modeles ORM applicatifs, les repositories ou les internes de services comme preuve de comportement.

## Etat Actuel des BDD

Le backend local collecte et passe actuellement 107 scenarios BDD.

Les zones couvertes par des BDD executables sont :

- Authentication ;
- Projects ;
- Project Members ;
- API Keys ;
- EventTypes ;
- Schema Definitions ;
- Routes ;
- Event Ingress ;
- EventDeliveries creees par le routage ;
- Delivery Worker ;
- Dead Letters ;
- MetricDefinitions de base.

Il existe aussi un fichier de feature Metric Builder, mais il n'est pas collecte par pytest-bdd car aucun module de test ne le charge. Il ne doit donc pas etre compte comme couverture BDD executable.

Les issues GitHub BDD ouvertes n'etaient pas synchronisees avec le code courant : beaucoup de cases etaient encore decochees alors que les scenarios passent localement, tandis que plusieurs zones listees dans les issues ou pertinentes produit n'ont pas encore de couverture BDD executable.
