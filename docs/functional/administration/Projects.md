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
- consultation individuelle, y compris lorsque le Project est désactivé ;
- modification partielle du nom et de la description ;
- distinction entre champ PATCH absent, `description: null` et valeur vide ;
- désactivation ;
- réactivation idempotente sans recréer les membres ou ressources liées ;
- rejet d'une désactivation non autorisée ;
- rejet d'une désactivation d'un Project inexistant.

## Contrat d'administration

```text
GET   /api/admin/projects/{project_id}
PATCH /api/admin/projects/{project_id}
PATCH /api/admin/projects/{project_id}/disable
PATCH /api/admin/projects/{project_id}/enable
```

La lecture requiert `project:read`. Les mutations lifecycle et le PATCH
requièrent `project:write`. Les OWNER conservent ces permissions sur leur
Project désactivé ; un ADMIN global suit le contournement de membership déjà
défini. Un utilisateur authentifié extérieur au Project reçoit `403`.

Le PATCH est fermé et ne permet de modifier que :

- `name`, normalisé en minuscules et validé selon la grammaire Project ;
- `description`, nullable et bornée.

Un champ absent est inchangé. Une description explicitement nulle ou vide est
effacée. Un nom nul, vide ou invalide est refusé. Un payload sans champ
modifiable retourne `PROJECT_UPDATE_EMPTY`; une collision de nom retourne
`PROJECT_NAME_CONFLICT`. Les erreurs publiques restent structurées et
n'exposent ni SQL ni contrainte PostgreSQL.

Le service possède le commit et le rollback. Les repositories se limitent aux
lectures, verrous, mutations et `flush`. La contrainte d'unicité PostgreSQL
reste l'arbitre final des renommages concurrents.

La désactivation et la réactivation ne suppriment rien et ne recréent aucun
membre, EventType, Schema, Route, credential ou objet métrique. La suppression
physique et le workflow d'invitation sont des décisions séparées ; les
invitations restent suivies par #31 et #22.
