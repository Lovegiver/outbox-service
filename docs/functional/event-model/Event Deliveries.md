# Event Deliveries

## Pourquoi cette fonctionnalité existe

Une EventDelivery représente l'ordre persistant de livrer un Event vers une destination.

Une Route décrit une destination possible. Une EventDelivery matérialise, pour un Event précis, l'intention de livraison vers cette destination.

## Vision métier

Le worker de routage lit les Routes actives d'un EventType et crée une EventDelivery par Route.

Chaque EventDelivery devient une unité de travail autonome pour le worker de livraison.

## Invariants métier

- Une EventDelivery appartient toujours à un seul Event.
- Une EventDelivery cible une seule destination.
- Une EventDelivery est créée à partir d'une Route active.
- Une EventDelivery porte une copie des informations de destination au moment du routage.
- Une EventDelivery nouvellement créée est en `PENDING`.
- Une EventDelivery nouvellement créée a `attempt_count = 0`.
- Une EventDelivery nouvellement créée n'a pas de `last_error`.
- Un Event déjà routé ne doit pas produire de doublons lors d'un nouveau cycle worker.

## Comportements validés par BDD

- une Route active produit une EventDelivery ;
- plusieurs Routes actives produisent plusieurs EventDeliveries ;
- aucune Route rend l'Event `UNROUTABLE` sans créer de Delivery ;
- la Delivery copie la destination ;
- un second cycle ne duplique pas les Deliveries ;
- la Delivery est liée à l'Event routé.
