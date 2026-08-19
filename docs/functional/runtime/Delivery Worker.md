# Delivery Worker

## Pourquoi cette fonctionnalité existe

Le Delivery Worker exécute les EventDeliveries persistées.

Une EventDelivery exprime l'intention de livrer un Event vers une destination. Le Delivery Worker transforme cette intention en tentative réelle de livraison.

## Vision métier

Le Delivery Worker lit les livraisons éligibles, tente l'envoi, puis met à jour l'état opérationnel de chaque EventDelivery.

Il ne décide pas du routage. Il n'analyse pas le payload. Il exécute uniquement les ordres de livraison déjà créés.

## Cycle de vie

```text
PENDING / FAILED retryable
  -> Delivery Worker
  -> DELIVERED ou FAILED
  -> DEAD_LETTER si le seuil de tentatives est atteint
```

## Invariants métier

- Seules les livraisons `PENDING` ou `FAILED` retryables sont exécutées.
- Une livraison `DELIVERED` n'est pas retraitée.
- Une livraison `DEAD_LETTER` n'est pas retraitée automatiquement.
- Chaque tentative incrémente `attempt_count`.
- Un succès efface `last_error`.
- Un échec renseigne `last_error`.
- Le Delivery Worker travaille sur des EventDeliveries persistées.

## Comportements validés par BDD

- succès webhook -> `DELIVERED` ;
- échec webhook -> `FAILED` ;
- incrément du nombre de tentatives ;
- conservation de l'erreur ;
- absence de retraitement des `DELIVERED` ;
- absence de retraitement des `DEAD_LETTER` ;
- retry d'une livraison `FAILED` encore éligible.

## Évolutions prévues

Les prochaines itérations couvriront plus finement les retries, le passage en Dead Letter et le retry manuel depuis l'administration.
