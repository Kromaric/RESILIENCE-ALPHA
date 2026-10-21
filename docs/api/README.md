# Documentation des API (Swagger / OpenAPI)

| Fichier | Contenu |
|---|---|
| `index.html` | Swagger UI des services Orbe (choix du service en haut de page) |
| `auth-service.openapi.json` | Spécification OpenAPI 3.1 d'auth-service |
| `payment-service.openapi.json` | Spécification OpenAPI 3.1 de payment-service |
| `bo-api.openapi.json` | Spécification OpenAPI 3.1 de bo-api (back-office du dashboard) |
| `specs.js` | Les mêmes spécifications, chargées par `index.html` |

## Consulter
Ouvrir `index.html` dans un navigateur, directement depuis le disque. Swagger UI est chargé
depuis le CDN jsdelivr : il faut un accès Internet.

Pour envoyer des requêtes depuis Swagger (« Try it out »), choisir le serveur en haut de page :
le démonstrateur (à travers le WAF) ou un service lancé en local.

Chaque service sert aussi son propre Swagger sur `/docs` quand `AUTH_ENABLE_DOCS=true` ou
`PAYMENT_ENABLE_DOCS=true` (désactivé par défaut : à ne pas exposer derrière le WAF).

## Régénérer après une modification d'API
```bash
services/auth-service/.venv/Scripts/python scripts/export_openapi.py auth-service
services/payment-service/.venv/Scripts/python scripts/export_openapi.py payment-service
services/bo-api/.venv/Scripts/python scripts/export_openapi.py bo-api
```
