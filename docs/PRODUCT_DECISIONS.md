# Décisions produit et contrats runtime OB1

Ce document centralise les décisions prises pour stabiliser le comportement
produit, les contrats publics et les futurs scénarios BDD. Il distingue les
invariants métier, qui doivent rester identiques dans tous les environnements,
des paramètres d'exploitation configurables.

## Authentification

### Emails

- Les emails sont nettoyés des espaces en début et fin de chaîne.
- Ils sont normalisés et persistés en minuscules.
- L'unicité est insensible à la casse.
- Le login applique la même normalisation que l'inscription.
- Le format est validé avec `EmailStr`, sans espace, avec une longueur maximale
  de 254 caractères.

### Mots de passe

- Longueur comprise entre 8 et 32 caractères.
- Présence obligatoire d'une lettre majuscule, d'une lettre, d'un chiffre et
  d'un caractère spécial.
- Les erreurs d'inscription sont explicites.
- Le login retourne toujours l'erreur générique `Invalid credentials` afin de
  ne pas révéler l'existence d'un compte.

### JWT

- Un access token porte obligatoirement le claim `typ: access`.
- Les claims `sub`, `iat`, `exp` et `jti` sont obligatoires.
- Un token d'invitation, de vérification d'email ou de réinitialisation de mot
  de passe ne peut pas être utilisé comme access token.
- Le secret, l'algorithme et la durée de vie sont des paramètres runtime.

## Projects

- Le nom contient entre 1 et 20 caractères.
- Seuls les lettres, chiffres, tirets et underscores sont autorisés.
- Aucun espace n'est accepté.
- Le nom est normalisé en minuscules et son unicité est insensible à la casse.
- La description contient au maximum 128 caractères.
- La désactivation est idempotente. Une nouvelle demande retourne le Project
  toujours inactif et signale qu'il était déjà désactivé.
- Un Project inactif reste lisible.
- Aucun membre, API Key, EventType, Schema ou Route ne peut y être ajouté.
- Sa désactivation révoque transactionnellement toutes ses API Keys.

## Membres et invitations

- Un utilisateur peut appartenir à plusieurs Projects.
- L'association `(project_id, user_id)` est unique.
- Les rôles admis sont `OWNER`, `DEVELOPER` et `VIEWER`.
- Les permissions découlent exclusivement du rôle. Tout membre possède au
  minimum le rôle `VIEWER` et la permission `PROJECT_READ`.
- Les scénarios fonctionnels parlent prioritairement de rôles.
- Une ressource appartenant à un autre Project est refusée avec `403`. Une
  association inexistante dans un Project accessible retourne `404`.
- Un OWNER peut inviter un email sans compte existant.
- Une invitation est distincte d'un membership, expire après 7 jours et peut
  être annulée par un OWNER avant son acceptation.
- Le rôle par défaut à l'acceptation est `VIEWER` s'il n'a pas été précisé.
- Le dernier OWNER ne peut être supprimé ou rétrogradé. Il doit transférer la
  propriété ou désactiver le Project avant de quitter.

### Vocabulaire et matrice d'autorisation

Les scénarios métier expriment le rôle de l'acteur (`OWNER`, `DEVELOPER`,
`VIEWER`). Les scénarios transverses d'infrastructure peuvent nommer la
permission précise contrôlée. Un membre sans `PROJECT_READ` n'existe pas dans
le modèle actuel : cette absence de permission représente un non-membre.

| Famille | OWNER | DEVELOPER | VIEWER |
| --- | --- | --- | --- |
| Project | lecture, écriture | lecture | lecture |
| EventType | lecture, écriture | lecture, écriture | lecture |
| Schema | lecture, écriture | lecture, écriture | lecture |
| Route | lecture, écriture | lecture, écriture | lecture |
| API Key | lecture, écriture | lecture, écriture | lecture |
| Metrics | lecture, écriture | lecture, écriture | lecture |

Un `ADMIN` global contourne les contrôles de membership. Un utilisateur
authentifié sans permission reçoit `403`; une authentification absente,
invalide ou expirée reçoit `401`.

La suppression RGPD d'un compte doit faire l'objet d'une conception dédiée.
La piste retenue est l'effacement des données personnelles et l'anonymisation
irréversible lorsque la conservation technique d'une ligne est nécessaire,
après traitement des responsabilités de dernier OWNER.

## API Keys

- Le nom est obligatoire, contient entre 1 et 64 caractères et est unique sans
  tenir compte de la casse à l'intérieur d'un Project.
- Le même nom est autorisé dans plusieurs Projects.
- La rotation d'une clé active révoque l'ancienne et crée la nouvelle.
- Une clé déjà révoquée ne peut pas être tournée.
- La révocation est idempotente.
- `last_used_at` est mis à jour lorsqu'une clé valide a authentifié une requête,
  même si l'Event est ensuite refusé pour une raison métier.
- Une clé absente, invalide ou révoquée ne met pas `last_used_at` à jour.
- La désactivation du Project révoque toutes ses clés.

## EventTypes et Schema Definitions

### EventType

- Le code respecte `^[a-z][a-z0-9._-]{0,63}$`.
- Son unicité porte sur `(project_id, code)`.
- Un même code peut donc exister dans plusieurs Projects.
- Les EventTypes inactifs restent lisibles.

### Versions de schema

Le client fournit un JSON Schema et une version utilisateur au format `x.y.z`.
Cette version est une étiquette destinée à l'audit et au diagnostic ; OB1 ne
l'interprète pas pour sélectionner le contrat d'ingress.

Pour chaque EventType, OB1 attribue à chaque nouveau schema une version interne
strictement incrémentale : `1`, `2`, `3`, etc. La correspondance affichée est
par exemple :

```text
version utilisateur 2.4.1 ↔ version interne 3
```

- La création et l'activation sont deux opérations distinctes.
- Un schema nouvellement créé est inactif par défaut.
- L'activation désactive atomiquement le précédent schema actif.
- Un seul schema peut être actif pour un EventType.
- L'ingress sélectionne exclusivement ce schema actif.
- Le producteur ne fournit aucune version de schema lors de l'ingestion.
- L'Event conserve `schema_definition_id` afin d'identifier exactement le
  contrat utilisé. OB1 peut exposer les deux versions pour l'audit.
- Le listing retourne tout l'historique avec versions et statut actif/inactif.
- Un schema vide est refusé.

## Event Ingress

- Le comportement des propriétés supplémentaires est exactement celui du JSON
  Schema : `additionalProperties: false` les refuse ; `true` ou l'absence de la
  propriété les autorise.
- Les champs non déclarés explicitement sous `properties` ne sont jamais
  proposés au Metric Builder et ne peuvent participer à une métrique.
- Un champ déclaré mais optionnel ne produit aucune observation lorsqu'il est
  absent.
- `correlation_id` utilise le format UUID.
- Un `event_uuid` déjà associé à un contenu identique retourne l'Event existant
  sans créer de doublon.
- Le même UUID avec un contenu différent retourne `409 EVENT_UUID_CONFLICT`.
- Deux ingestions concurrentes identiques produisent un seul Event durable.

Codes HTTP retenus :

- `422` pour une entrée syntaxiquement invalide ;
- `400` pour un payload incompatible avec le JSON Schema ;
- `403` pour une ressource appartenant à un autre Project ;
- `404` pour une ressource inconnue ;
- `409` pour une ressource inactive ou un conflit d'UUID.

Une erreur de schema expose un code stable, un message et le chemin JSON.

## Process, Route et Transport

- `Process` et `Task` décrivent le parcours métier.
- Une `Route` décide vers quelle destination poursuivre.
- Un `Transport` décrit comment effectuer la livraison.
- Une fin de parcours est une transition terminale explicite, par exemple
  `COMPLETED`, et non une Route HTTP sans URL.
- `routing_key` n'est pas considérée comme un concept métier stable tant que le
  modèle Process/Task n'est pas finalisé.
- Une Route HTTP exige une URL absolue `http` ou `https`, avec un hôte et sans
  identifiants intégrés.
- Un doublon exact `(event_type, destination, transport, endpoint)` est refusé.
- Les premiers modes d'authentification sont `NONE`, `API_KEY_HEADER` et
  `BEARER_TOKEN`.
- `auth_config` décrit le mécanisme mais ne contient jamais le secret.
- `secret_ref` permet au transport de résoudre le secret au moment de livrer.

## Livraison et idempotence

### Contrat d'ingress et corps sortant

Le contrat OB1 est le format que le système producteur A doit utiliser pour
publier un Event auprès d'OB1. Il contient les informations nécessaires à
l'ingress, dont le `payload` métier.

Le JSON Schema associé à l'EventType décrit exclusivement ce `payload`. Il
représente donc le contrat de données attendu par le système consommateur B,
et non une enveloppe sortante propre à OB1.

Lors de la livraison, le worker envoie comme corps HTTP exactement le payload
persisté et validé :

```json
{
  "duration_seconds": 12.3
}
```

OB1 n'ajoute pas son enveloppe dans le corps, car celle-ci pourrait rendre la
requête incompatible avec le schema imposé par B. Les métadonnées techniques
utiles au transport sont portées par des headers :

```http
Idempotency-Key: <event_uuid>
X-Outbox-Event-Id: <event_uuid>
X-Outbox-Correlation-Id: <correlation_id>
X-Outbox-Event-Type: <event_type_code>
X-Outbox-Schema-Version: <version utilisateur>
```

Les headers de corrélation, type et version peuvent être omis si la destination
ne les autorise pas ou si sa configuration de transport ne les demande pas.
`Idempotency-Key` reste le mécanisme recommandé pour identifier un rejeu.

### Rejeu et clé d'idempotence

HTTP et PostgreSQL ne partagent pas une transaction. Si le consommateur traite
un webhook puis qu'OB1 échoue avant d'enregistrer `DELIVERED`, OB1 doit rejouer
la livraison.

La clé d'idempotence métier retenue est `event_uuid`. Elle reste identique à
chaque tentative et suffit lorsque chaque consommateur doit traiter un Event au
plus une fois. Il n'est pas nécessaire d'exposer l'identifiant SQL de la
delivery. OB1 garantit la réémission d'une delivery retryable ; le système
cible est responsable de la déduplication et de l'absence de double effet
métier.

```http
Idempotency-Key: <event_uuid>
X-Outbox-Event-Id: <event_uuid>
```

Le consommateur implémente un pattern Inbox ou une contrainte unique sur
`event_uuid`. La première réception effectue le traitement ; les suivantes
retournent un succès sans reproduire l'effet métier. Ce contrat est nécessaire
pour obtenir un traitement effectif unique sur un transport garantissant au
moins une livraison.

### Transactions et concurrence

- Le routing d'un Event, son statut et ses deliveries sont atomiques.
- Chaque tentative de delivery possède sa propre transaction.
- Les workers utilisent `FOR UPDATE SKIP LOCKED` pour ne pas réclamer la même
  delivery simultanément.
- Un Event absent est une incohérence terminale : la delivery passe directement
  en `DEAD_LETTER` avec `EVENT_NOT_FOUND`.
- Une erreur d'extraction de métrique métier est tracée et publiée mais ne
  bloque pas le routing ni la livraison.

### Politique HTTP

- Toute réponse `2xx` est un succès.
- Timeout et erreur réseau sont retryables.
- `408`, `425` et `429` sont retryables.
- Les autres `4xx` sont terminaux.
- Les `5xx` sont retryables.
- Le backoff est exponentiel, plafonné et assorti d'un jitter.

## Dead Letters et métriques runtime

- Le listing est trié par `updated_at DESC, id DESC`.
- La pagination utilise un curseur.
- Aucun secret n'est exposé.
- Retry-all sur un Project inexistant retourne `404`.
- Une absence d'âge est sérialisée en `null` et affichée `N/A` par le frontend.
- `retry_count` est la somme de `max(attempt_count - 1, 0)`.
- Après retry d'une dead letter, `dead_letter_count` diminue et `pending_count`
  augmente sans perdre l'historique global des tentatives.

## Prometheus et MetricState

- Le scrape lit uniquement MetricState et ne déclenche aucun recalcul.
- Le contrat métier est exposé par Project via
  `GET /metrics/projects/{project_id}/prometheus-state` et inclut tous ses
  EventTypes.
- `ob1_project` contient le nom fonctionnel du Project et `ob1_event_type` le
  code fonctionnel de l'EventType. Ces labels sont ajoutés uniquement lors de
  l'exposition et ne participent jamais à `labels_hash`.
- Le préfixe `ob1_` est réservé aux noms de labels de plateforme ; tout label
  métier `ob1_*` est rejeté explicitement.
- Les noms respectent `[a-zA-Z_:][a-zA-Z0-9_:]*` ; les caractères invalides
  sont remplacés par `_`, puis le préfixe de métrique `ob1_` est appliqué une
  seule fois. Un `metric_code` déjà préfixé par `ob1_` reste accepté et n'est
  pas préfixé une seconde fois.
- Deux codes métier qui convergent vers le même nom après normalisation sont
  une incohérence explicite et ne sont pas fusionnés silencieusement.
- Les labels sont triés alphabétiquement.
- Les antislashs, guillemets et retours à la ligne sont échappés.
- Une réponse sans MetricState est vide.
- `# TYPE` est émis une seule fois par nom de métrique.
- La première version expose uniquement des counters finis et non négatifs.

## YAML Metrics Observatory

- Le YAML version `"1.0"` est le contrat déclaratif commun à l'administration
  et au futur Metric Builder.
- Le parsing utilise exclusivement un chargeur sûr et exige un objet YAML non
  vide.
- La validation cible explicitement une SchemaDefinition appartenant au même
  EventType que l'opération administrative.
- OB1 attribue le numéro interne de MetricDefinitionVersion ; le client peut
  fournir uniquement un label d'affichage optionnel.
- Une version persiste exactement le YAML soumis et n'est jamais modifiée
  rétroactivement.
- Preview et création partagent le même parser, validateur et compilateur.
- Une preview ne persiste ni version, ni compatibilité, ni chaîne, ni plan.
- Une création invalide est rejetée avant toute écriture ; une erreur de
  persistance annule la transaction.
- La preview compile un plan déterministe, mais seule une future ProcessingChain
  explicitement construite et activée pourra rendre ce plan exécutable.
- Le runtime ne relit et ne recompile jamais le YAML.
- Le format HTTP est `text/plain; version=0.0.4; charset=utf-8`.
- Une cardinalité jugée forte par le Metric Builder provoque un rejet, pas un
  simple warning.

### Metric Builder BDD-016A

- Le JSON Schema exact est l'unique source de vérité du type, de l'obligation
  et de la nullabilité. Un chemin imbriqué n'est obligatoire que si tous ses
  ancêtres le sont.
- Une construction non maîtrisée est `UNSUPPORTED` et n'est jamais présumée
  compatible.
- `sum_value` exige une borne inférieure démontrable supérieure ou égale à
  zéro. Une absence de borne est `UNSAFE` et bloque la preview.
- Une donnée optionnelle absente ou une valeur `null` autorisée ne produit ni
  observation, ni incrément, ni zéro artificiel. Une vraie valeur produisant
  zéro reste une contribution valide.
- Les labels du premier périmètre sont les booléens et enums scalaires bornés.
  Les valeurs libres, identifiants et vecteurs statiques de forte cardinalité
  sont refusés. La limite par défaut de l'enum est configurable et vaut 20.
- Le nom Prometheus final est calculé par OB1 et exposé en lecture seule. Une
  collision déterminable après normalisation bloque la preview.
- Le plan compilé `1.1` transporte la nullabilité. Le runtime continue à lire
  les plans historiques `1.0`, sans relire le schema ou le YAML.

### Metric Builder BDD-016B

- `create` revalide la requête contre le `SchemaDefinition` exact et transmet
  le texte YAML généré sans divergence à `MetricYamlService` avant toute
  écriture.
- `MetricDefinition`, sa première `MetricDefinitionVersion` et la compatibilité
  exacte sont persistées dans une transaction unique. Le service
  d'orchestration possède le commit et le rollback ; les repositories utilisent
  `flush()` sans commit intermédiaire.
- La clé naturelle initiale est `EventType + code métrique`. Un rejeu
  fonctionnellement identique retourne les mêmes identifiants sans nouvelle
  version ; un contenu différent retourne un conflit et ne modifie pas
  l'existant.
- Les créations sont sérialisées par verrou de l'EventType, puis du schema
  exact. Le contrôle du nom Prometheus est refait sous ce verrou dans le scope
  EventType ; les contraintes PostgreSQL existantes restent les derniers
  garde-fous d'unicité.
- Une création ne reconstruit ni n'active aucune ProcessingChain. Le rebuild et
  l'activation restent des actions explicites et séparées.

### Metric Builder BDD-016C

- Preview, création atomique, rebuild et activation restent quatre frontières
  explicites. Seul le rebuild crée une `DRAFT`; seule l'activation modifie la
  chaîne `ACTIVE`; aucun Event historique n'est traité par ces opérations.
- Le rebuild refuse un snapshot dont deux codes métier distincts convergent
  vers le même nom Prometheus. L'activation refait la même validation canonique
  sous le verrou du `SchemaDefinition` exact avant de retirer l'ancienne chaîne.
  Un échec conserve donc intégralement l'ancienne `ACTIVE`.
- Deux EventTypes restent isolés par leurs identités persistées, même si leurs
  JSON Schemas sont structurellement identiques. Le nom Prometheus n'est pas un
  conflit global : les labels plateforme distinguent les séries.
- L'acquisition métrique verrouille avec `SKIP LOCKED` le plan et son exécution
  parent. Deux workers peuvent ainsi prendre des Events distincts sans exécuter
  simultanément deux plans du même snapshot Event ni attendre sur son parent.
- La baseline initiale utilise PostgreSQL réel, 100 Events d'environ 1 KiB,
  cinq plans Counter, quatre producteurs et un worker métrique. Elle bloque sur
  l'exactitude et les timeouts fonctionnels, jamais sur un percentile. Elle est
  comparative et ne constitue ni SLA ni capacité produit absolue.

## Paramètres runtime et invariants

### Exécution des métriques compilées

- L'Event utilise uniquement son `schema_definition_id` exact et la chaîne
  `ACTIVE` de ce scope ; aucun fallback n'est permis.
- Le premier traitement matérialise durablement le snapshot Event/chaîne et
  une exécution unique par Event/ProcessingPlan avant la fin du routing.
- Les plans sont exécutés séparément du routing et de la delivery, avec une
  transaction par plan et acquisition PostgreSQL `SKIP LOCKED` du plan et de
  son parent Event/snapshot.
- Les observations, la réussite du plan et leurs références sont atomiques.
- Un retry métrique conserve le snapshot initial et ne rejoue aucune delivery.
- L'identité d'une observation runtime est
  `Event + ProcessingPlan + observation_key` et est protégée par PostgreSQL.
- Le runtime ne lit, ne valide et ne compile jamais le YAML.
- Les transforms exécutables sont `constant`, `identity`, `count`, `length` et
  `to_number`. Une opération sans exécuteur est refusée avant activation.
- Les métriques utilisateur sont actuellement des Counters. Chaque incrément
  est validé avant la création d'une `AnalyticalObservation` : il doit être
  numérique, fini et supérieur ou égal à zéro. `-0` est normalisé à zéro.
  Une valeur incompatible place uniquement son `MetricPlanExecution` en
  `FAILED_PERMANENT`, sans `AnalyticalObservation`, sans `MetricState` et sans
  interrompre routing ou delivery. L'agrégateur et le renderer conservent une
  défense contre les données historiques ou corrompues.
- Un `value_path` optionnel absent ne produit aucune observation.
- Un label optionnel absent reste un `null` structurel dans
  `AnalyticalObservation` et `MetricState`. Aucune valeur métier n'est réservée :
  `"__missing__"` et la chaîne vide restent des données ordinaires distinctes en
  base.
- À l'exposition Prometheus, les labels `null` ou vides sont omis. Les
  partitions internes convergeant vers la même identité Prometheus sont
  additionnées sans modifier les `MetricState`. Cette coalescence repose
  exclusivement sur la sémantique additive des Counters actuellement pris en
  charge ; Gauge et Histogram devront définir leur propre projection.
- `RUNNING` n'est jamais committé seul : verrou, tentative, observations et
  résultat appartiennent à la même transaction de plan. Une interruption avant
  commit restaure donc `PENDING` ou `RETRYABLE` et libère le verrou PostgreSQL.
- Une incohérence active est enregistrée durablement ; elle n'est jamais
  réparée par fallback, recompilation ou rebuild implicite.

Les paramètres de batch, nombre maximal de tentatives et backoff des métriques
appartiennent à `metrics.execution` dans les profils runtime.

BDD-016A analyse les contraintes du JSON Schema et refuse un intent Counter
lorsqu'une valeur ne garantit pas sa non-négativité, notamment en l'absence de
`minimum: 0`.

Les fichiers existants `config/app.dev.yaml`, `config/app.test.yaml` et
`config/app.prod.yaml` sont le bon emplacement pour les paramètres variant par
environnement :

- secret, algorithme et durée de vie JWT ;
- timeout et nombre maximal de tentatives de livraison ;
- base, plafond et jitter du backoff ;
- taille des pages de dead letters ;
- exigence de HTTPS selon l'environnement ;
- fournisseur et emplacement des secrets de destination.

Les règles suivantes sont des invariants et ne doivent pas être modifiables par
environnement : normalisation des emails, formats et longueurs métier,
unicité, rôles, codes HTTP, activation unique du schema, idempotence,
`additionalProperties`, contrat d'ingress et livraison du payload sans
enveloppe supplémentaire.

Le `ConfigService` constitue le point d'accès aux settings. Avant leur usage en
production, `OUTBOX_JWT_SECRET_KEY` remplace obligatoirement le placeholder du
YAML. `JwtService` consomme les settings via `ConfigService`. Les secrets de
destination référencés par les Routes sont résolus depuis l'environnement au
moment de la livraison et ne sont jamais persistés dans leur configuration.
