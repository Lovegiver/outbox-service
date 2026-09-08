# OB1 — Outbox Service

OB1 est un service autonome de réception, validation, persistance, observation,
routage et livraison d'événements métier.

Son architecture d'exécution suit le flux :

```text
Ingress API → PostgreSQL → Worker → Runtime Events → Dashboard
```

L'ingress FastAPI accepte rapidement un événement valide et le persiste avec
le statut `RECEIVED`. Le worker exécute ensuite le traitement secondaire :
matérialisation des métriques, routage, livraison, retries, dead letters et
agrégation de l'état exposable à Prometheus.

OB1 produit des données opérationnelles et analytiques. Il ne remplace ni un
moteur de workflow, ni Prometheus, ni Grafana.

## Stack

- Python 3.11 ou supérieur et gestionnaire de paquets `uv` ;
- FastAPI et Uvicorn ;
- PostgreSQL ;
- SQLAlchemy 2 et Alembic ;
- APScheduler pour le worker ;
- pytest et pytest-bdd.

## Démarrage local

Une base PostgreSQL compatible avec la configuration DEV est nécessaire.

```bash
cp .env.example .env
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

Le profil actif est sélectionné par `OUTBOX_ENV` et charge
`config/app.<environnement>.yaml`. Les secrets doivent être fournis hors Git.
Le worker intégré est actif par défaut ; définir
`OB1_ENABLE_EMBEDDED_WORKER=false` permet de démarrer uniquement l'API.

Points de contrôle :

- santé : `GET /health` ;
- documentation OpenAPI : `/docs` ;
- ingestion machine : `POST /events` avec `X-API-Key` ;
- administration humaine : JWT et RBAC par Project ;
- activité live : `/runtime/events` ;
- métriques Prometheus par Project :
  `/metrics/projects/{project_id}/prometheus-state`.

## Vérifications

```bash
uv run pytest
```

Les changements de schéma passent exclusivement par les migrations Alembic
sous `migrations/`. Aucune correction directe de la base ne doit remplacer
une évolution du modèle et sa migration.

## Documentation

- [Vue produit](docs/PRODUCT_OVERVIEW.md)
- [Décisions produit et contrats runtime](docs/PRODUCT_DECISIONS.md)
- [Audit de couverture BDD](docs/BDD_COVERAGE_AUDIT.md)
- [Documentation fonctionnelle](docs/functional/)
- [Instructions pour les agents](AGENT.md)

L'interface d'administration est maintenue séparément dans
[Lovegiver/ob1-admin](https://github.com/Lovegiver/ob1-admin).
