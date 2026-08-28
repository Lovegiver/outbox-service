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

BDD-016 Metric Builder produit ce même YAML. Son analyse conservatrice guide la
preview, puis le pipeline canonique reste l'unique voie de validation et de
compilation.

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

## Compatibilités YAML/schema

Une `MetricDefinitionVersionSchema` ne signifie pas que deux ressources
existent seulement : elle matérialise une validation et une compilation réussies
de la version YAML persistée contre le `SchemaDefinition` exact. Cette relation
many-to-many est durable et idempotente. Elle ne peut traverser ni Project ni
EventType et sa création ne reconstruit aucune configuration runtime.

```text
POST /api/admin/event-types/{event_type_id}/metric-definitions/
     versions/{metric_definition_version_id}/schemas/{schema_definition_id}
```

Le serveur relit toujours le YAML immutable et réutilise le chemin canonique du
lot 1. Il ne fait pas confiance à une preview fournie par le client.

## Snapshots ProcessingChain

Le rebuild est une opération d'administration explicite :

```text
POST /api/admin/event-types/{event_type_id}/metric-definitions/
     schemas/{schema_definition_id}/processing-chain/rebuild
```

Pour chaque `MetricDefinition` active du scope, OB1 sélectionne la version YAML
active compatible ayant le numéro interne le plus élevé. L'ensemble est trié
par identité de définition, revalidé et recompilé avant toute persistance. Une
chaîne ne contient jamais deux versions d'une même définition.

La chaîne et tous ses plans constituent un snapshot immutable. Tous les
`compiled_plan_json` sont préparés avant la section critique. Une nouvelle
version YAML ou une nouvelle compatibilité ne modifie ni ne reconstruit une
chaîne existante.

Construction et activation sont deux opérations métier distinctes. Un rebuild
modifié persiste une candidate complète `DRAFT` et ses plans dans une même
transaction, sans toucher à la chaîne active. Un rebuild dont la signature est
identique à la chaîne active retourne celle-ci ; s'il correspond à une `DRAFT`
complète existante, il retourne cette candidate. Dans les deux cas, aucun
numéro n'est consommé et aucun plan n'est recréé. Une `INCOMPLETE` n'est jamais
réutilisée comme équivalent d'un snapshot complet : la sélection, les
compatibilités et la compilation doivent être redémontrées pour produire une
nouvelle `DRAFT` activable.

La signature fonctionnelle couvre le scope `EventType + SchemaDefinition`,
l'ensemble normalisé des `MetricDefinitionVersion` et le document compilé
déterministe, qui porte la version du compilateur. Un changement de signature
crée le numéro suivant et conserve tous les anciens snapshots pour l'audit.

Construction, numérotation et activation sont sérialisées par verrouillage du
`SchemaDefinition`, ressource stable du scope. Le service d'orchestration
possède commit et rollback ; les repositories n'en possèdent aucun. La seule
opération qui change le runtime est l'activation explicite. La retraite de
l'ancienne chaîne et l'activation de la candidate appartiennent à la même
transaction. Un index unique partiel PostgreSQL garantit en dernier ressort au
maximum une chaîne `is_active` par scope.

Une chaîne candidate `DRAFT` est techniquement et fonctionnellement complète :
toutes ses versions sont compatibles, tous ses plans sont présents et chaque
`compiled_plan_json` correspond à la compilation canonique du YAML immutable.
Elle reste inactive jusqu'à l'appel explicite :

```text
POST /api/admin/event-types/{event_type_id}/metric-definitions/
     schemas/{schema_definition_id}/processing-chains/{chain_id}/activate
```

Une chaîne `INCOMPLETE` est réservée à la propagation partielle d'un schema.
Elle contient uniquement la partie compatible et chacun de ses plans présents
reste techniquement complet. Elle est fonctionnellement réduite par rapport au
snapshot source et ne peut jamais être activée directement. Corriger, remplacer
ou exclure explicitement les métriques incompatibles impose un nouveau rebuild
canonique vers une `DRAFT` ; un simple changement de statut est interdit.

Une transaction interrompue, un plan absent ou sans document compilé, une
référence cassée ou une erreur technique ne sont jamais représentés par
`INCOMPLETE` : ils provoquent un rollback intégral. Aucun cache de
ProcessingChain n'est actif : la base reste la source de vérité et aucune
invalidation anticipée n'est nécessaire.

Les statuts sont stockés dans la colonne texte existante. Ils ne reposent ni sur
un enum PostgreSQL ni sur une contrainte `CHECK`, donc aucun changement de
schema n'est requis pour `DRAFT` et `INCOMPLETE`. Le service contrôle leurs
transitions, tandis que l'index partiel protège l'unicité active.

| Opération | Construit | Persiste | Modifie la chaîne active |
| --- | --- | --- | --- |
| Compatibilité | Non | Association validée | Non |
| Rebuild | Candidate `DRAFT` éventuelle | Chaîne et plans | Non |
| Propagation | Candidate `DRAFT` ou `INCOMPLETE` éventuelle | Compatibilités, chaîne et plans | Non |
| Activation | Non | Statuts transactionnels | Oui |

## Évolution contrôlée d'un JSON Schema

Le schema source est explicitement fourni, car `json_version_internal` est un
identifiant chaîne et ne définit pas à lui seul un ordre métier fiable :

```text
POST /api/admin/event-types/{event_type_id}/metric-definitions/
     schemas/{target_schema_id}/compatibilities/propagate

{"source_schema_definition_id": 41}
```

OB1 repart exclusivement des versions référencées par la chaîne active du
schema source. Chaque YAML est revalidé séparément contre le nouveau schema.
Les compatibilités démontrées sont ajoutées sans modifier l'historique ; les
incompatibilités restent absentes et sont retournées avec leur raison. Une
erreur technique annule toute persistance, tandis qu'une incompatibilité métier
n'empêche pas l'analyse des autres métriques.

Le rapport contient les nombres évalué, compatible et incompatible, la
composition proposée et l'identité d'une éventuelle candidate. Si une métrique
est incompatible, la candidate réduite porte le statut `INCOMPLETE` et ne peut
pas être activée silencieusement. Si toutes les métriques restent compatibles,
la candidate complète reste inactive jusqu'à l'appel explicite d'activation.
Une propagation répétée ne crée ni association ni candidate en double.

Le passage d'un champ obligatoire à optionnel reste statiquement compatible et
est signalé par un avertissement : le comportement lorsque ce champ manque à
l'exécution est une décision de BDD-015C.

## Exécution runtime BDD-015C

Le runtime sélectionne exclusivement la chaîne `ACTIVE` correspondant au
`schema_definition_id` exact conservé par l'Event. Il matérialise durablement
le snapshot et une exécution par ProcessingPlan avant la fin du routing, puis
exécute chaque plan dans une unité transactionnelle indépendante.

Les seuls transforms activables sont `constant`, `identity`, `count`, `length`
et `to_number`, tous couverts par un exécuteur. Un `value_path` optionnel absent
ne produit aucune observation. Un label optionnel absent est conservé comme
`null` dans l'observation puis dans `MetricState`. Aucune valeur métier n'est
réservée : `"__missing__"` reste une chaîne ordinaire et la chaîne vide reste
distincte de `null` dans PostgreSQL.

Les sorties runtime de ces transforms alimentent exclusivement des Counters.
Chaque valeur est donc validée avant la création d'une
`AnalyticalObservation` : elle doit être numérique, finie et non négative. Une
valeur incompatible provoque l'échec permanent du seul ProcessingPlan
concerné, sans observation ni `MetricState` et sans impact sur routing ou
delivery. Le JSON Schema de l'Event n'est pas réécrit et l'Event reste valide
selon son propre contrat.

Le Builder BDD-016A exploite les contraintes du JSON Schema et refuse
`sum_value` lorsque le champ ciblé ne garantit pas la non-négativité, notamment
lorsqu'aucun `minimum: 0` n'est défini. Le détail du sous-ensemble analysé et
des garde-fous est documenté dans
[Metric Builder Schema Analysis](Metric%20Builder%20Schema%20Analysis.md).

Le Builder BDD-016B persiste la définition, sa première version YAML immutable
et sa compatibilité avec le schema exact dans une seule transaction. Le YAML
stocké est exactement le texte validé et compilé par `MetricYamlService`. Un
rejeu identique retourne les mêmes ressources ; le même code avec un contenu
différent ou un nom Prometheus final en collision retourne un conflit sans
état partiel. Cette création n'effectue aucun rebuild et aucune activation de
ProcessingChain.

La projection Prometheus omet les labels `null` et vides. Plusieurs partitions
internes qui convergent ainsi vers la même identité Prometheus finale sont
additionnées au rendu, sans réécriture en base. Cette règle est limitée aux
Counters actuellement supportés et ne préjuge pas du traitement futur des
Gauges ou Histograms.

Les transforms `unique_count`, `occurrence_count`, `occurrence`, `timestamp`,
`hour_of_day`, `day_of_week`, `sum`, `avg`, `min` et `max` appartiennent aux
évolutions futures ou aux idées historiques de la DSL. Bien qu'une version
antérieure du validateur les ait acceptés, aucun exécuteur runtime stable ne
leur était associé : ils sont désormais rejetés explicitement avant qu'une
nouvelle chaîne puisse être construite ou activée.

La clé durable `Event + ProcessingPlan + observation_key` rend les retries et
rejeux techniques idempotents. Aucun retry métrique ne rejoue une delivery.
Le contrat détaillé est documenté dans
[Metric Runtime Execution](Metric%20Runtime%20Execution.md).
