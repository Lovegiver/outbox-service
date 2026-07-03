# Projects

## Pourquoi cette fonctionnalité existe

Un Project est la racine fonctionnelle d'OB1.

Il isole les données, les utilisateurs, les API Keys, les EventTypes, les Routes, les Events et les métriques d'un domaine métier.

## Vision métier

Un Project représente un espace d'observabilité : application, domaine métier, client, environnement ou flux d'intégration.

## Hiérarchie

```text
Project
  -> Project Members
  -> API Keys
  -> EventTypes
       -> SchemaDefinitions
       -> Routes
       -> Events
            -> EventDeliveries
```

## Invariants métier

- Un EventType appartient à un seul Project.
- Une API Key appartient à un seul Project.
- Un Project doit toujours conserver au moins un OWNER tant qu'il existe.
- La désactivation d'un Project ne supprime pas son historique.
- Les Events historiques restent rattachés à leur Project.

## Comportements validés par BDD

- création d'un Project ;
- affectation automatique du créateur comme OWNER ;
- rejet d'un nom déjà utilisé ;
- listing des Projects visibles ;
- listing global ADMIN ;
- désactivation ;
- rejet d'une désactivation non autorisée ;
- rejet d'une désactivation d'un Project inexistant.
