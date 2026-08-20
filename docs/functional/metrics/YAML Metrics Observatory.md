# YAML Metrics Observatory

## Rôle

Le YAML Metrics Observatory est le contrat déclaratif versionné qui relie un
JSON Schema d'EventType à de futures observations métier. Il est interprété,
validé et compilé pendant la configuration. Le runtime ne doit jamais relire ou
recompiler ce YAML.

La chaîne complète suivie par BDD-015 est découpée en trois lots :

1. BDD-015A : versions YAML, validation et preview ;
2. BDD-015B : compatibilité et activation de snapshots ProcessingChain ;
3. BDD-015C : exécution des ProcessingPlans persistés vers
   AnalyticalObservation.

BDD-016 Metric Builder viendra ensuite produire ce même YAML. Il ne constituera
pas une seconde voie de validation ou de compilation.

## Contrat YAML 1.0

Le document doit être un objet YAML non vide utilisant la version chaîne
`"1.0"`. `observations` est une liste non vide d'objets.

Exemple de compteur :

```yaml
version: "1.0"
observations:
  - code: products_sold_total
    transform: constant
    labels:
      country: $.country
```

Exemple de valeur numérique :

```yaml
version: "1.0"
observations:
  - code: revenue_total
    transform: identity
    value_path: $.amount
    labels:
      country: $.country
```

`constant` interdit `value_path` et produit la valeur `1`. Les autres
transformations exigent un chemin non vide et compatible avec le type déclaré
par le JSON Schema. Un champ optionnel est compatible ; son caractère optionnel
est conservé dans le plan compilé.

Les chemins et itérations sont résolus contre le JSON Schema ciblé. Les labels
doivent être des noms Prometheus valides et le préfixe de plateforme `ob1_*`
leur est interdit. `$index` nécessite une itération de tableau, et les chemins
itérés d'une même observation doivent rester alignés.

## Parsing sûr

OB1 utilise exclusivement le chargeur YAML sûr. Les documents vides, les
racines non objets, les syntaxes invalides et les constructeurs YAML non sûrs
sont rejetés avec des erreurs déterministes. Le contenu YAML original n'est pas
normalisé avant persistance : une version conserve exactement le document
soumis pour l'audit.

## Interfaces publiques du lot 1

Les opérations nécessitent les permissions Metrics déjà définies sur
l'EventType.

```text
POST /api/admin/event-types/{event_type_id}/metric-definitions/yaml/validate
POST /api/admin/event-types/{event_type_id}/metric-definitions/yaml/preview
POST /api/admin/event-types/{event_type_id}/metric-definitions/{metric_definition_id}/versions
GET  /api/admin/event-types/{event_type_id}/metric-definitions/{metric_definition_id}/versions
```

Validation et preview reçoivent :

```json
{
  "schema_definition_id": 42,
  "yaml_content": "version: \"1.0\"\nobservations: ..."
}
```

La création reçoit le même schema et YAML, plus un
`yaml_version_label` optionnel. Le client ne fournit pas le numéro interne.
OB1 verrouille la MetricDefinition, calcule le prochain numéro strictement
croissant et persiste la nouvelle version dans la même transaction.

La preview retourne le `compiled_plan_json` déterministe mais ne persiste ni
MetricDefinitionVersion, ni compatibilité, ni ProcessingChain, ni
ProcessingPlan. La création et la preview utilisent exactement le même chemin
parser → validateur → compilateur.

## Erreurs et isolation

- `404` : MetricDefinition ou SchemaDefinition inconnue ;
- `403` : ressource connue appartenant à un autre EventType, ou permission
  insuffisante ;
- `422` : création refusée pour YAML syntaxiquement, structurellement ou
  sémantiquement invalide ;
- `409` : conflit persistant de version.

Les endpoints de validation et preview conservent leur contrat de retour
`valid=false` et une liste d'erreurs pour les erreurs YAML. Une ressource
inconnue ou hors scope reste une erreur HTTP.

Une preview valide ou invalide ne produit aucune écriture. Une création invalide
est rejetée avant l'ajout d'une version ; une erreur de persistance annule la
transaction. L'historique est uniquement étendu : une ancienne version n'est
jamais modifiée lors de la création d'une nouvelle version.

## Lots futurs

BDD-015A ne crée aucune compatibilité ou configuration runtime.

BDD-015B décidera notamment le comportement d'un rebuild identique,
l'invalidation des compatibilités après changement de schema et le renforcement
en base de l'unicité de la chaîne active.

BDD-015C décidera le contrat des transformations actuellement déclarées mais
pas encore toutes exécutables, le comportement exact des champs optionnels
absents, l'idempotence des AnalyticalObservation et la trace d'une erreur
métrique isolée du routing/delivery.
