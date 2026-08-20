# Prometheus Docker Integration

## Objectif

Le harness `docker-compose.prometheus-test.yml` prouve qu'un serveur Prometheus
réel peut scraper les `MetricState` produits par OB1. Il valide l'intégration
de BDD-017, pas encore la chaîne fonctionnelle complète du Metrics Observatory.

La stack est réservée aux tests et ne constitue pas une configuration de
production.

## Topologie

```text
postgres
  -> migrate
  -> fixture-loader
       -> worker
       -> targets file-SD
  -> app
app + targets file-SD
  -> prometheus
  -> verifier PromQL
```

L'application FastAPI désactive son worker embarqué dans cette topologie. Le
service `worker` utilise l'entrée officielle `python -m app.worker_runner` et
la même image applicative. Cela évite un double traitement tout en restant
fidèle au déploiement avec worker séparé prévu par OB1.

## Données de test

Le `fixture-loader` réutilise l'`ObjectFactory` de l'infrastructure de test pour
créer deux Projects, trois EventTypes et des `AnalyticalObservation` contrôlées.
Il n'insère aucun `MetricState`. Le vrai worker effectue l'agrégation
incrémentale et crée les checkpoints.

Les identifiants SQL des Projects ne sont jamais supposés. Le loader récupère
les identifiants réellement attribués et génère
`/prometheus-targets/ob1-projects.json`. Prometheus utilise ce fichier par
file-based service discovery pour scraper deux chemins Project distincts sur
la target réseau `app:8000`.

## Vérifications

Le vérificateur emploie des attentes bornées de 90 secondes avec un intervalle
de deux secondes. Il contrôle :

- la disponibilité des documents Prometheus de chaque Project ;
- le Content-Type texte 0.0.4 ;
- les valeurs et labels de plateforme ;
- l'absence de série de l'autre Project ;
- l'absence d'effet de bord du GET sur MetricState et MetricCheckpoint ;
- `/-/ready` ;
- les deux targets dans `/api/v1/targets` avec l'état `UP` ;
- trois séries exactes via `/api/v1/query` ;
- l'isolation des Projects via deux requêtes PromQL négatives.

Les dernières réponses utiles sont écrites dans `.artifacts/`, répertoire
ignoré par Git. GitHub Actions publie ces diagnostics pendant sept jours et
capture `docker compose ps` ainsi que les logs complets en cas d'échec.

## Exécution

```text
docker compose -f docker-compose.prometheus-test.yml config --quiet
docker compose -f docker-compose.prometheus-test.yml build --pull --no-cache app
docker compose -f docker-compose.prometheus-test.yml run --rm --no-deps --entrypoint /bin/promtool prometheus check config /etc/prometheus/prometheus.yml
docker compose -f docker-compose.prometheus-test.yml up --detach --wait --wait-timeout 120 app worker prometheus
docker compose -f docker-compose.prometheus-test.yml run --rm --no-deps verifier
docker compose -f docker-compose.prometheus-test.yml down --volumes --remove-orphans
```

Le workflow CI exécute deux cycles complets séparés par la suppression des
volumes afin de prouver la reproductibilité depuis un environnement propre.

## Limites assumées

- Le scrape reste sans MetricsToken sur un réseau Docker de confiance.
- Le YAML, le Metric Builder, Grafana, le NAS et le déploiement de production
  sont hors périmètre.
- Seuls les counters déjà pris en charge par BDD-017 sont validés.
