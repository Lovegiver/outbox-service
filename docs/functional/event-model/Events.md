# Events

## Pourquoi cette fonctionnalité existe

Un Event est l'instance persistée d'un événement métier reçu par OB1.

Il matérialise le fait qu'un système externe a envoyé une information métier à OB1, dans le but que cette information soit validée, conservée, observée, puis éventuellement propagée vers d'autres systèmes.

OB1 est une Outbox : son rôle n'est pas seulement de recevoir des messages, mais de les rendre durables, observables et exploitables par le pipeline runtime.

## Vision métier

Un système émetteur envoie un Event à OB1 via l'API publique `POST /events`.

OB1 répond immédiatement à l'émetteur :

- succès si le message est authentifié et conforme au JSON Schema actif ;
- rejet si l'API key est absente ou invalide ;
- rejet si le payload ne respecte pas le contrat JSON.

Cette validation est volontairement synchrone. L'émetteur attend une réponse HTTP au moment de l'envoi. Si OB1 stockait le message sans le valider, puis découvrait plus tard qu'il est invalide, il serait trop tard pour informer proprement l'émetteur.

## Position dans l'architecture

```text
System A
  -> POST /events
  -> API Key authentication
  -> JSON Schema validation
  -> Event(RECEIVED)
  -> Worker
  -> Metrics / Routes / EventDelivery
```

L'ingestion appartient au pipeline synchrone.

Le worker appartient au pipeline asynchrone.

## Cycle de vie

À l'ingestion, un Event valide est persisté avec le statut `RECEIVED`.

Il n'est pas routé immédiatement. Le routing, les métriques, les deliveries et les retries sont pris en charge plus tard par le worker.

Cette séparation garantit que l'ingestion reste rapide, durable et prévisible.

## Règles métier

- Un Event doit être authentifié par une API key valide.
- Un Event doit cibler un Project.
- Un Event doit cibler un EventType.
- Un Event doit indiquer une version de schéma interne.
- Le payload doit être conforme au JSON Schema actif.
- Un Event accepté est persisté en `RECEIVED`.
- Un `event_uuid` est généré si l'émetteur n'en fournit pas.
- Un `event_uuid` fourni est conservé.
- Un `correlation_id` fourni est conservé.
- Un doublon `event_uuid` est rejeté.
- L'ingestion ne déclenche pas le worker.

## Comportements validés par BDD

- ingestion avec API key valide ;
- refus sans API key ;
- refus avec API key invalide ;
- refus avec API key révoquée ;
- refus payload JSON invalide ;
- refus sans schéma actif ;
- persistance en `RECEIVED` ;
- génération automatique de `event_uuid` ;
- conservation de `event_uuid` et `correlation_id` ;
- rejet des doublons ;
- absence de création d'EventDelivery pendant l'ingestion.

## Ressources de test

Les payloads JSON utilisés par les scénarios sont stockés sous forme de fichiers afin de rester lisibles et réutilisables par Metrics Observatory.

Le payload valide couvre texte, nombres, booléens, objets imbriqués, tableaux simples, tableaux d'objets.

## Évolutions prévues

Les Events seront plus tard corrélés par le modèle Process / Step / Transition.

OB1 restera observateur : il mesurera les transitions et les délais, mais ne prendra pas de décision métier.
