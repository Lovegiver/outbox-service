# API Keys

## Pourquoi cette fonctionnalité existe

Les API Keys authentifient les systèmes qui publient des Events dans OB1.

Elles représentent une identité technique, distincte des utilisateurs humains authentifiés par JWT.

## Vision métier

Un système externe ne doit pas utiliser un compte utilisateur pour envoyer des Events.

Il reçoit une API Key rattachée à un Project. Cette clé lui donne la capacité de publier dans le périmètre de ce Project.

## Règles métier

- Une API Key appartient à un Project.
- Le secret complet n'est affiché qu'à la création ou rotation.
- Le listing ne révèle jamais le secret complet.
- Une API Key peut être révoquée.
- Une API Key révoquée ne permet plus l'ingestion.
- Une API Key peut être remplacée par rotation.
- L'ancienne clé ne fonctionne plus après rotation.

## Position dans l'architecture

```text
External System
  -> X-API-Key
  -> POST /events
  -> Project
  -> EventType
  -> Event
```

## Comportements validés par BDD

- création par utilisateur autorisé ;
- secret visible uniquement à la création ;
- listing sans secret complet ;
- rejet création sans permission ;
- révocation ;
- rejet révocation inexistante ;
- rotation ;
- rejet de l'ancienne clé ;
- acceptation de la nouvelle clé ;
- rejet d'une clé révoquée sur l'ingestion.

## Décision d'architecture

JWT et API Key ne sont pas interchangeables.

Le JWT identifie un utilisateur humain. L'API Key identifie une capacité machine-à-machine accordée à un Project.
