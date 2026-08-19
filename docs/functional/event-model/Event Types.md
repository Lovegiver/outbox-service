# Event Types

## Pourquoi cette fonctionnalité existe

Un EventType décrit une catégorie métier d'Events.

Il constitue le point d'ancrage principal du modèle OB1 : schémas JSON, routes, métriques, events et futures étapes de processus y sont rattachés.

## Vision métier

Un EventType correspond à un fait métier observable : `article.analyzed`, `order.created`, `payment.failed`, etc.

## Invariants métier

- Un EventType appartient à un seul Project.
- Son `code` identifie le type métier.
- Les SchemaDefinitions d'un EventType définissent les payloads acceptés.
- Les Routes d'un EventType définissent les destinations.
- Les MetricDefinitions d'un EventType définissent ce qui sera observé.
- Les Events reçus référencent l'EventType qui les qualifie.
