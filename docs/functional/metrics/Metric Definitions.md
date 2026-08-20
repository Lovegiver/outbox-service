# Metric Definitions

## Pourquoi cette fonctionnalité existe

Une MetricDefinition déclare une métrique métier attachée à un EventType.

Elle répond à la question : quelle information observable veut-on produire à partir des Events de ce type ?

## Vision métier

L'utilisateur ne manipule pas directement Prometheus, SQL ou les tables analytiques. Il commence par nommer une métrique métier : compteur d'analyses, durée de traitement, nombre d'erreurs, volume par source, etc.

La MetricDefinition est ce point d'ancrage stable. Les versions YAML viendront ensuite décrire comment produire concrètement cette métrique.

## Invariants métier

- Une MetricDefinition appartient à un seul EventType.
- Son `code` est unique dans le périmètre de cet EventType.
- Le même `code` peut exister sur deux EventTypes différents.
- Une MetricDefinition nouvellement créée est active.
- La création nécessite `METRICS_WRITE`.
- La lecture nécessite `METRICS_READ`.
- Une version YAML est immuable et conserve exactement le document soumis.
- Son numéro interne est attribué par OB1 et augmente strictement dans le
  périmètre de la MetricDefinition.
- La version est validée contre une SchemaDefinition du même EventType avant
  toute persistance.
- La preview compile le même contrat mais ne persiste aucune configuration.

## Comportements validés par BDD

- création par un DEVELOPER ;
- rejet de création par un VIEWER ;
- rejet sur EventType inexistant ;
- rejet du doublon de code sur le même EventType ;
- acceptation du même code sur deux EventTypes différents ;
- listing des MetricDefinitions d'un EventType ;
- rejet du listing par un utilisateur hors Project.

Le contrat détaillé des versions, de la validation et de la preview est décrit
dans [YAML Metrics Observatory](YAML%20Metrics%20Observatory.md).
