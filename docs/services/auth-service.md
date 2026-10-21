# auth-service — authentification d'Orbe

Port interne **8001**, exposé via le WAF sous `/api/auth/*`. Python 3.12 / FastAPI.

## auth-service — rôle

auth-service gère l'inscription, la connexion à **deux facteurs** (mot de passe + reconnaissance faciale),
les sessions révocables et l'émission des jetons JWT. Il vérifie aussi les clés d'API des applications
clientes (sonde, partenaires). Il servira aussi d'authentification au back-office.

## auth-service — parcours de connexion

1. `POST /login` (email + mot de passe, en-tête `X-Client-Id`) → `200` avec `mfa_required: true`, un `session_id` et un défi `face_challenge` (« tournez la tête à gauche » ou « à droite », 8 images, 250 ms d'intervalle). La session est `en_attente_2fa` pendant 2 minutes.
2. La caméra du navigateur capture 8 images pendant que le client tourne la tête.
3. `POST /login/face` → `200` avec `access_token` (JWT RS256, 15 minutes), session `active`, facteurs `["pwd","face"]`.

## auth-service — reconnaissance faciale et détection du vivant

- Modèle **InsightFace `buffalo_s`** (détection SCRFD + reconnaissance ArcFace), sur CPU, embarqué dans l'image. Environ 300 Mo de RAM, ~100 ms par image.
- Décision : similarité cosinus ≥ **0,40** avec un gabarit du client sur au moins **3 images**.
- Détection du vivant : la rotation de la tête (lacet) doit dépasser **8°** dans le sens demandé. Une photo ou un écran figé échoue (`liveness_failed`).
- Limite assumée : une vidéo rejouée qui tourne du bon côté passe une fois sur deux ; pas d'anti-spoofing par profondeur.
- Aucune image n'est conservée ni journalisée. Seuls 3 à 5 **gabarits chiffrés AES-256-GCM** sont stockés par client.

## auth-service — codes d'erreur de connexion

| Code | Signification | Que faire |
|---|---|---|
| `401` | Mot de passe incorrect | Vérifier l'identifiant ; compte bloqué après 5 échecs |
| `401 second_factor_failed` | Visage non reconnu | Nouvel essai depuis `POST /login` (le défi n'est pas rejouable) ; vérifier l'éclairage |
| `401 liveness_failed` | Rotation de tête insuffisante ou dans le mauvais sens | Recommencer en tournant franchement la tête du côté demandé |
| `423` | Compte bloqué 10 minutes après 5 échecs | Attendre la fin du blocage |
| `429` | Limitation de débit par IP | Ralentir |
| `403 second_factor_required` (renvoyé par payment-service) | Session « mot de passe seul » : le compte n'a pas de visage enregistré | Enregistrer le visage (`POST /face/enroll`) puis se reconnecter |

## auth-service — blocage de compte

Après **5 échecs** (mot de passe ou visage), le compte est bloqué **10 minutes** (`failed_logins`,
`locked_until`). Les tentatives sont tracées dans les journaux (Loki / SOC), pas en base. Une limitation
par IP s'ajoute au blocage par compte.

## auth-service — exception de la sonde

La sonde ne peut pas présenter de visage. Elle s'authentifie avec la clé d'API d'une application cliente
de type `service`, ouvre des sessions sans visage et ne peut agir que sur les comptes marqués `is_probe`.
C'est un risque résiduel documenté.

## auth-service — jetons JWT

JWT **RS256**, durée **15 minutes après la connexion** (pas 15 minutes d'inactivité), claims `sub`
(client_id), `email`, `jti` (identifiant de session), `amr`. La clé privée est détenue par auth-service ;
la clé publique est distribuée à payment-service, qui vérifie les jetons localement. Une session peut
être révoquée avant expiration (`POST /logout`, ou remédiation SC-02).

## auth-service — santé et métriques

- `GET /health/live` : le processus répond.
- `GET /health/ready` : prêt à servir (base joignable).
- `GET /metrics` : métriques Prometheus (voir `metriques-et-journaux.md`), dont `auth_login_failures_total{reason}` et `auth_face_inference_seconds`.

## auth-service — risque d'épuisement CPU

L'inférence faciale est coûteuse. Les entrées sont bornées (12 images de 400 Ko maximum à la connexion)
et limitées par IP. Une hausse anormale de `auth_face_inference_seconds` signale une tentative
d'épuisement des ressources sur auth-service.
