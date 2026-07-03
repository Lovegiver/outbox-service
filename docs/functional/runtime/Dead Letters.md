# Dead Letters

## Pourquoi cette fonctionnalité existe

Une Dead Letter représente une EventDelivery arrivée dans un état d'échec terminal.

Elle conserve la trace des livraisons qui n'ont pas pu être exécutées malgré les tentatives autorisées, tout en empêchant leur retraitement automatique infini.

## Vision métier

Une livraison qui échoue trop souvent sort du flux normal. Elle reste visible dans l'administration afin qu'un humain puisse diagnostiquer le problème, corriger la cause externe éventuelle, puis relancer manuellement la livraison.

## Position dans l'architecture

```text
EventDelivery(FAILED)
  -> seuil de tentatives atteint
  -> DEAD_LETTER
  -> diagnostic admin
  -> retry manuel
  -> PENDING
```

## Invariants métier

- Une Dead Letter est une EventDelivery avec statut `DEAD_LETTER`.
- Une Dead Letter n'est pas retraitée automatiquement.
- Une Dead Letter reste rattachée à son Event et à son Project.
- Le listing est filtré par Project.
- Le retry manuel nécessite une permission d'écriture.
- Le retry manuel remet la livraison en `PENDING`.
- Le retry manuel remet `attempt_count` à `0`.
- Le retry manuel efface `last_error`.

## Comportements validés par BDD

- listing des dead letters d'un Project ;
- filtrage par Project ;
- rejet du listing sans permission ;
- exposition des informations utiles : destination, attempts, last_error, event_uuid ;
- retry manuel autorisé ;
- retry manuel interdit à un viewer ;
- retry d'une dead letter inexistante ;
- rejet du retry d'une livraison non `DEAD_LETTER` ;
- retry-all limité au Project demandé.

## Évolutions prévues

Les prochaines itérations pourront enrichir l'historique des tentatives afin de conserver la mémoire complète des échecs avant retry.
