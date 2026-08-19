# Project Members

## Pourquoi cette fonctionnalité existe

Les Project Members définissent les utilisateurs autorisés à agir sur un Project.

Ils matérialisent le modèle RBAC projet d'OB1.

## Vision métier

Un Project n'est pas seulement un conteneur technique. C'est aussi un périmètre de responsabilité.

Les membres du Project déterminent qui peut lire, configurer, administrer ou intervenir sur le runtime.

## Rôles

- OWNER : contrôle complet du Project.
- DEVELOPER : configuration fonctionnelle et technique, y compris routes, schémas, API keys et métriques.
- VIEWER : consultation des informations et métriques sans modification.

## Invariants métier

- Un Project doit conserver au moins un OWNER.
- Les permissions sont dérivées du rôle projet.
- Un utilisateur hors Project ne peut pas accéder aux ressources projet.
- Les actions sensibles, comme le retry d'une Dead Letter, exigent une permission d'écriture.

## Comportements validés par BDD

- ajout d'un membre ;
- listing des membres ;
- modification de rôle ;
- suppression d'un membre ;
- protection du dernier OWNER ;
- rejet des actions sans permission.

## Lien avec Dead Letters

Le listing des Dead Letters est une opération de lecture runtime.

Le retry manuel est une opération corrective sensible et nécessite donc une permission plus élevée.
