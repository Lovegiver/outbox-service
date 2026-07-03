# Authentication

## Pourquoi cette fonctionnalité existe

OB1 expose deux types d'interfaces :

- des interfaces humaines d'administration ;
- une API publique d'ingestion utilisée par des systèmes techniques.

Ces usages nécessitent deux mécanismes d'authentification distincts.

## Vision métier

Un utilisateur humain s'authentifie avec un compte et reçoit un JWT.

Un système externe s'authentifie avec une API Key lorsqu'il envoie des Events.

Cette séparation évite de mélanger les identités humaines et les identités machine.

## Modèle d'authentification

### Utilisateurs

Les utilisateurs utilisent JWT pour accéder aux endpoints d'administration.

Leur niveau d'accès est ensuite contrôlé par leur rôle global, leur appartenance à un Project et leurs permissions projet.

### Systèmes

Les systèmes utilisent `X-API-Key` pour appeler `POST /events`.

Une API key est rattachée à un Project et peut être révoquée ou remplacée.

## Position dans l'architecture

```text
Human user -> JWT -> Admin API
System      -> X-API-Key -> POST /events
```

## Règles métier

- un token JWT invalide est rejeté ;
- un token expiré est rejeté ;
- un utilisateur inactif est rejeté ;
- une API key absente est rejetée ;
- une API key invalide est rejetée ;
- une API key révoquée est rejetée.

## Comportements validés par BDD

Les campagnes BDD Authentication et API Keys valident le login, les rejets d'identifiants invalides, l'accès protégé par JWT, la création des API keys, le secret visible uniquement à la création, la révocation, la rotation et le rejet des clés révoquées sur `POST /events`.

## Décision d'architecture

JWT et API Keys ne sont pas interchangeables.

Le JWT représente une identité humaine.

L'API Key représente une capacité technique accordée à un système.
