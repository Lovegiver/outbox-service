# Prometheus Metric State

## Contrat HTTP

OB1 expose les compteurs métier matérialisés d'un Project avec :

```text
GET /metrics/projects/{project_id}/prometheus-state
```

Le endpoint suit la convention actuelle des endpoints de scrape OB1 et
n'introduit pas de nouveau mécanisme d'authentification. Un Project inconnu
retourne `404`. Un Project existant sans `MetricState` retourne `200` avec un
corps vide.

Une réponse non vide utilise :

```text
Content-Type: text/plain; version=0.0.4; charset=utf-8
```

Exemple :

```text
# TYPE ob1_products_sold_total counter
ob1_products_sold_total{country="BE",ob1_event_type="product.sold",ob1_project="shop"} 4
ob1_products_sold_total{country="FR",ob1_event_type="product.sold",ob1_project="shop"} 12
```

## Source de vérité

Le GET lit uniquement `MetricState`. Il ne lit ni `Event` ni
`AnalyticalObservation`, ne charge aucun `ProcessingPlan` et ne déclenche
aucune agrégation. Le worker agrège séparément les observations après le
checkpoint de chaque flux Project/EventType. Les états et le checkpoint sont
mis à jour dans la même transaction.

## Noms et labels

Les caractères d'un `metric_code` hors `[a-zA-Z0-9_:]` sont remplacés par
`_`. Le préfixe `ob1_` est ensuite ajouté une seule fois ; il garantit aussi
un premier caractère valide. Si deux codes distincts convergent vers le même
nom après normalisation, l'exposition échoue explicitement au lieu de fusionner
des familles sans intention métier.

Chaque série reçoit à l'exposition :

- `ob1_project`, alimenté par le nom fonctionnel du Project ;
- `ob1_event_type`, alimenté par le code fonctionnel de l'EventType.

Ces labels ne sont pas persistés dans `labels_json` et ne participent pas à
`labels_hash`. Tout label métier dont le nom commence par `ob1_` est rejeté.
Les noms de labels métier doivent respecter
`[a-zA-Z_][a-zA-Z0-9_]*`.

Les familles, séries et labels sont triés. Les antislashs, guillemets doubles
et retours à la ligne des valeurs de labels sont échappés selon le format
texte Prometheus 0.0.4. Cette première version n'expose que des counters finis
et non négatifs.
