# PROJECT RESILIENCE-ALPHA — Cadrage technique

> Workshop EPSI BAC+5 — Octobre 2026 — Consortium G\<n\>
> Statut : **v0.4** — modèle Orbe v2 codé : authentification forte (mot de passe + visage), sessions révocables, comptabilité en partie double
> Périmètre : architecture, composants, interfaces, données, observabilité, détection, remédiation, sécurité technique, déploiement.
> La gouvernance (EBIOS RM, PCA/PRA, NIS2/DORA) fait l'objet d'un document séparé.

---

## 1. Critères d'acceptation techniques

| # | Critère | Mesure |
|---|---|---|
| T1 | Un transfert fictif aboutit en nominal | `POST /pay` → `201`, transaction `authorized`, solde du bénéficiaire crédité |
| T2 | Le scénario SC-01, lancé depuis le PC Attaquant, dégrade le service | `probe_transaction_success` passe à 0, latence p95 et 5xx en hausse |
| T3 | L'anomalie est détectée par le modèle ML | `anomaly_score{target="payment-service"}` > seuil |
| T4 | La remédiation s'exécute sans intervention | Incident `verified` dans `remediation-engine`, étapes horodatées |
| T5 | Le service est réellement rétabli | 3 transactions de test consécutives OK + contrôle de cohérence OK |
| T6 | Boucle complète ≤ 40 s | `remediation_duration_seconds` + horodatages incident |
| T7 | Déploiement reproductible | `deploy.yml` sur une machine vierge (Docker Desktop + WSL2) sans étape manuelle non documentée |
| T8 | Aucun secret en clair dans le dépôt | gitleaks vert en CI |

---

## 2. Stack et versions

| Couche | Technologie | Remarque |
|---|---|---|
| Backend | **Python 3.12 / FastAPI**, Uvicorn, SQLAlchemy 2 (async) + `aiomysql` | Tous les services backend |
| Frontend / dashboard | **React + Vite + Tailwind CSS** | Build statique servi par Nginx |
| Base de données | **MariaDB 11.4 LTS** | |
| Conteneurs | **Docker Desktop (WSL2) + Docker Compose v2** | |
| Automatisation | **Ansible** (`ansible-core`, collection `community.docker`) | Exécuté en conteneur (pas de nœud de contrôle natif sous Windows) |
| WAF | **Nginx + ModSecurity v3 + OWASP CRS 4** (`owasp/modsecurity-crs:nginx`) | Point d'entrée unique + répartition de charge |
| Métriques | **Prometheus** + **Alertmanager** + `mysqld_exporter` + cAdvisor | |
| Journaux | **Loki** + **Grafana Alloy** | |
| Visualisation | **Grafana** | |
| Secrets | **HashiCorp Vault** (mode serveur) + **SOPS/age** pour l'amorçage | Pas de mode `-dev` |
| ML | **scikit-learn**, pandas, joblib | |
| Assistant | **Ollama** + **LangChain** + **ChromaDB** | Modèle ≤ 8B |
| Trafic de référence | **Locust** | Baseline ML + profils de charge légitimes |
| CI | **GitHub Actions** | Pas de déploiement depuis la CI (§11) |
| IDS *(optionnel)* | **Snort** → Loki | Faisabilité à tester sous WSL2 |
| Analyse | **Wireshark** | Outil d'équipe, hors chaîne automatique |
| Mots de passe équipe | **KeeWeb** | Ne remplace pas Vault |

**Règle** : toutes les images sont épinglées par tag précis (jamais `:latest`), la liste est tenue dans `docker-compose.yml`.

---

## 3. Architecture

### 3.1 Vue d'ensemble

```
                   Hotspot Windows 192.168.137.0/24
 ┌──────────────┐                │
 │ PC Attaquant │────────────────┤
 └──────────────┘                ▼  :443 (seul port exposé au hotspot)
 ┌───────────────────────── PC Hôte 192.168.137.1 ─────────────────────────┐
 │                                                                          │
 │  net-front   [ waf ] ──► [ frontend ]          [ probe ]──► waf          │
 │                 │                                                        │
 │  net-app        ├──► [ auth-service ]                                    │
 │                 └──► [ payment-service-a ] [ payment-service-b ]         │
 │                                  │                                       │
 │                            [ mariadb ]                                   │
 │                                                                          │
 │  net-obs     [ prometheus ] [ alertmanager ] [ loki ] [ alloy ]          │
 │              [ grafana ] [ cadvisor ] [ mysqld-exporter ]                │
 │                                                                          │
 │  net-ctrl    [ detector-ml ] [ remediation-engine ] [ socket-proxy ]     │
 │              [ vault ] [ dashboard ] [ assistant-rag ]                   │
 └──────────────────────────────────────────────────────────────────────────┘
 ┌────────────────────┐
 │ PC IA (optionnel)  │  [ ollama ]  — joignable uniquement depuis le PC Hôte
 └────────────────────┘
```

### 3.2 Inventaire des conteneurs et budget mémoire

| Conteneur | Image / base | Réseaux | `mem_limit` | `cpus` |
|---|---|---|---|---|
| waf | owasp/modsecurity-crs:nginx | front, app | 256M | 1.0 |
| frontend | nginx (build Vite) | front | 64M | 0.25 |
| probe | python:3.12-slim | front, obs | 128M | 0.25 |
| auth-service | python:3.12-slim | app, ctrl, obs | 256M | 0.5 |
| payment-service-a / -b | python:3.12-slim | app, ctrl, obs | 256M ×2 | 0.5 ×2 |
| mariadb | mariadb:11.4 | app | 512M | 1.0 |
| mysqld-exporter | prom/mysqld-exporter | app, obs | 64M | 0.1 |
| prometheus | prom/prometheus | obs, ctrl | 512M | 0.5 |
| alertmanager | prom/alertmanager | obs, ctrl | 64M | 0.1 |
| loki | grafana/loki | obs, ctrl | 512M | 0.5 |
| alloy | grafana/alloy | obs | 256M | 0.25 |
| grafana | grafana/grafana | obs | 256M | 0.25 |
| cadvisor | gcr.io/cadvisor/cadvisor | obs | 128M | 0.25 |
| detector-ml | python:3.12-slim | ctrl, obs | 512M | 0.5 |
| remediation-engine | python:3.12-slim + ansible-core | ctrl, front, app | 384M | 0.5 |
| socket-proxy | tecnativa/docker-socket-proxy | ctrl (interne) | 32M | 0.1 |
| vault | hashicorp/vault | ctrl, app | 256M | 0.25 |
| dashboard | nginx (build Vite) | ctrl | 64M | 0.25 |
| assistant-rag | python:3.12-slim | ctrl | 512M | 0.5 |
| **Total (plafonds)** | | | **≈ 5,2 Go** | |

Budget PC Hôte 16 Go : Windows ≈ 4 Go + VM WSL2 ≈ 2 Go + conteneurs ≈ 5,2 Go + Ollama 3B ≈ 3 Go → **≈ 14 Go**, serré.
→ Avec 16 Go : modèle 3B sur l'hôte, ou Ollama déporté sur le PC IA. `.wslconfig` : `memory=12GB`, `processors=6` (à ajuster).

### 3.3 Réseaux

| Réseau | `internal` | Membres | Rôle |
|---|---|---|---|
| `net-front` | non | waf, frontend, probe, remediation-engine | Seul réseau avec port publié |
| `net-app` | **oui** | waf, auth, payment-a/b, mariadb, vault, mysqld-exporter, remediation-engine | Trafic métier |
| `net-obs` | **oui** | stack d'observabilité + cibles scrapées | Supervision |
| `net-ctrl` | **oui** | detector-ml, remediation-engine, socket-proxy, vault, dashboard, assistant-rag, prometheus, loki, alertmanager | Plan de contrôle |

### 3.4 Exposition

| Publication | Service |
|---|---|
| `192.168.137.1:443` | waf |
| `127.0.0.1:3000` | grafana |
| `127.0.0.1:8080` | dashboard |
| *aucune* | tout le reste (DB, Vault, Prometheus, Alertmanager, moteur de remédiation, socket-proxy) |

- Docker Desktop publie sur `0.0.0.0` par défaut → **bind IP explicite obligatoire**.
- Le bind sur `192.168.137.1` échoue si le hotspot n'est pas actif → démarrer le hotspot **avant** `compose up` (vérifié par `deploy.yml`).
- Pare-feu Windows : entrant autorisé uniquement sur 443 pour le profil du hotspot.
- TLS : certificat généré au déploiement par une **CA locale (`mkcert`)**, installée sur les appareils de démo (PC, téléphone), le PC Attaquant et la sonde.
- **Nom de domaine `orbe.test`** → `192.168.137.1`, déclaré dans le fichier `hosts` des appareils de démo. Le navigateur n'autorise la caméra (`getUserMedia`) que sur une origine HTTPS : le certificat du WAF couvre `orbe.test`.

---

## 4. Spécification des services

### 4.1 Routage WAF

| Chemin public | Upstream | Remarque |
|---|---|---|
| `/` | frontend | statique |
| `/api/auth/*` | auth-service:8001 | réécriture du préfixe |
| `/api/payments/*` | upstream `payment` (a, b) | `max_fails=2 fail_timeout=10s` |
| `= /api/status` (GET uniquement) | remediation-engine:8003 `/status/public` | État public de la plateforme (§4.6) |
| autres | `404` | |

- Une instance de paiement en échec est **sortie automatiquement** de la répartition (checks passifs Nginx), l'autre continue de servir.
- Limitation de débit de base par IP (`limit_req`) volontairement large ; le **blocage ciblé est une action de remédiation** (§7.4).
- Liste de blocage dynamique : fichier `blocklist.conf` (directive `geo`) sur un volume partagé avec `remediation-engine`, rechargé par signal `HUP`.
- Journaux d'accès et d'audit ModSecurity en **JSON** sur stdout.

### 4.2 auth-service (8001)

> **v2** : double authentification **mot de passe + reconnaissance faciale** (modèle pré-entraîné InsightFace, exécuté par auth-service), sessions révocables et applications clientes. Exigence du coach ; remplace la passkey WebAuthn de la v0.4. auth-service servira aussi d'authentification au back-office. Modèle de données : `docs/mcd.md`.

**Authentification forte (DSP2 : deux facteurs parmi trois)** — le mot de passe est ce que l'on sait, le visage ce que l'on est. Le front capture quelques images à la caméra (`getUserMedia`) ; auth-service calcule les gabarits (embeddings ArcFace, 512 dimensions) et les compare à ceux enregistrés. **Aucune image n'est conservée**, seuls 3 à 5 gabarits chiffrés par client.

```
1. POST /login                         email + mot de passe
   ← 200 { "mfa_required": true, "session_id",
           "face_challenge": { "direction": "left", "frames": 8, "interval_ms": 250 } }
                                       session « en_attente_2fa » (2 min)
2. caméra                              8 images pendant que le client tourne la tête du côté demandé
3. POST /login/face                    { "session_id", "frames": [base64 JPEG…] }
   ← 200 { "access_token", "expires_in": 900, "factors": ["pwd", "face"] }   session « active »
```

| Endpoint | Entrée | Sortie |
|---|---|---|
| `POST /register` | `{ "email", "phone", "display_name", "password" }` | `201 { "client_id", … }` · `409` (`email_taken`, `phone_taken`) · `422` (`weak_password`…) · `429` |
| `POST /login` | `{ "email", "password" }` + en-tête `X-Client-Id` (application) | `200 { "mfa_required", "session_id", "face_challenge", "token", "face_enrollment_required" }` · `401` · `423` · `429` |
| `POST /login/face` | `{ "session_id", "frames" }` | `200 { "access_token", "token_type": "bearer", "expires_in": 900 }` · `401` (`second_factor_failed`, `liveness_failed`) · `422` |
| `POST /face/enroll` | session active, `{ "consent": true, "frames" }` (~16 images, tête qui balaie) | `201 { "enrolled", "templates", "model" }` · `403` · `422` (`consent_required`, `enrollment_failed`) |
| `GET /face` · `DELETE /face` | session active | état de l'enrôlement · droit à l'effacement |
| `POST /logout` | session active | révocation de la session |
| `GET /me` | `Authorization: Bearer` | `200 { "client_id", "email", "phone_masked", "display_name", "factors", "face_enrolled" }` |
| `GET /verify` | en-tête `X-API-Key` | `200 { "partner", "scopes": [] }` · `401` |
| `GET /health/live` · `/health/ready` | — | `200` / `503` |
| `GET /metrics` | — | format Prometheus |

- **Modèle** : InsightFace `buffalo_s` (détection SCRFD + reconnaissance ArcFace MobileFaceNet), CPU via onnxruntime, embarqué dans l'image Docker (aucun téléchargement à l'exécution). Environ 300 Mo de RAM, ~100 ms par image. Licence des modèles : usage non commercial, compatible avec le démonstrateur.
- **Décision 1:1** : similarité cosinus ≥ **0,40** avec un des gabarits du client sur au moins **3 images**. Seuil à mesurer sur l'équipe (taux de faux rejets / fausses acceptations) avant la soutenance.
- **Détection du vivant (défi-réponse)** : le serveur tire au hasard un sens (gauche/droite) ; la rotation de la tête mesurée (lacet) entre le début et la fin de la séquence doit dépasser 8° dans ce sens. Une photo imprimée ou un écran figé échoue (`liveness_failed`). Limite assumée : une vidéo rejouée qui tourne du bon côté passe (une chance sur deux) ; pas d'anti-spoofing par profondeur ou texture.
- **Échecs** : un échec de visage ferme la session en attente (pas de nouvel essai sur le même défi) et compte dans les 5 échecs qui bloquent le compte 10 min.
- **Enrôlement** : consentement explicite obligatoire (horodaté dans `clients.biometric_consent_at`). Un compte sans visage reçoit une session « mot de passe seul » qui ne permet que de consulter et d'enregistrer son visage ; payment-service refuse tout mouvement d'argent (`403 second_factor_required`). Un compte qui a déjà un visage ne le remplace ou ne le supprime que depuis une session confirmée par ce visage.
- **RGPD (art. 9, donnée biométrique)** : images traitées en mémoire puis oubliées, jamais journalisées ; gabarits chiffrés **AES-256-GCM**, liés à leur propriétaire (le client_id sert de donnée authentifiée : un gabarit copié sur un autre compte ne se déchiffre pas) ; clé dans un secret Docker (`face_embedding_key`), Vault Transit possible (`AUTH_FACE_CIPHER=vault`). Effacement à la demande (`DELETE /face`). Démo : comptes fictifs, visages des membres de l'équipe volontaires.
- JWT **RS256**, durée 15 min, claims `sub` (client_id), `email`, `jti` (= identifiant de session), `amr` (`["pwd", "face"]`) ; clé privée lue dans Vault, clé publique distribuée aux services de paiement.
- **Inscription** : email et téléphone normalisés et uniques, mot de passe de 12 caractères minimum refusé s'il est courant ou contient l'email, 5 inscriptions par minute et par IP. `auth_svc` n'a le droit d'insérer que `id, email, phone, display_name, password_hash` : une inscription ne peut pas créer de compte de sonde. Répondre « email déjà utilisé » révèle l'existence d'un compte (compromis assumé, freiné par la limitation de débit). Hors périmètre : vérification de l'email et du téléphone, KYC.
- Mots de passe : `argon2id`. **5 échecs → compte bloqué 10 min** (`failed_logins`, `locked_until`) + limitation par IP. Les tentatives sont tracées dans les journaux (Loki / SOC), pas en base.
- **Ressources** : l'inférence est coûteuse (CPU) ; taille et nombre d'images bornés (12 images de 400 Ko maximum à la connexion), limitation par IP. Scénario « ressource exhaustion » à surveiller : métrique `auth_face_inference_seconds`.
- **Exception de la sonde** : la sonde (CLIENT_API de type `service`, clé d'API dédiée) ouvre ses sessions sans visage et n'agit que sur les comptes `is_probe`. Risque résiduel documenté.
- La maquette annonce une expiration « après 15 min d'inactivité » : avec un JWT fixe, c'est 15 min après la connexion. Libellé à corriger, ou jeton de rafraîchissement à ajouter si le temps le permet.

### 4.3 payment-service (8002) — 2 instances

**Modèle métier (« Stripe local »)** : un client envoie à un autre client le montant de son choix, ou lui **demande** de l'argent. Le payeur paie avec une **carte de test** ; le bénéficiaire est crédité sur son **solde Orbe**, qu'il peut rembourser ou retirer vers son **compte lié** (compte bancaire fictif). Le bénéficiaire se désigne par email, téléphone ou **QR code**. Aucune intégration Stripe : tout est simulé dans le service.

```
Carte de test du payeur ──► payment-service ──► solde du bénéficiaire ──► retrait fictif (payout)
                                                        │
                                                        └──► remboursement vers la carte du payeur
```

**Endpoints** (tous avec `Authorization: Bearer`, sauf santé et métriques)

| Endpoint | Entrée | Sortie |
|---|---|---|
| `POST /pay` | `Idempotency-Key`, `{ "recipient": "<email ou téléphone>"` **ou** `"recipient_qr": "<jeton>", "amount_cents", "currency": "EUR", "description", "card": { "number", "exp_month", "exp_year", "cvc", "holder" } }` | `201 { "reference", "status", "decline_reason", "amount_cents", "card": { "brand", "last4" }, "created_at" }` · `200` (rejeu même clé) · `409` (même clé, corps différent) · `422` · `503` |
| `GET /transactions` | `?status=&direction=sent\|received&limit=20&cursor=` | `200 { "items": [ { "reference", "type", "direction", "counterparty", "description", "card_last4", "amount_cents", "status", "created_at" } ], "next_cursor" }` |
| `GET /transactions/{reference}` | — | `200` · `404` (absente ou étrangère au client) |
| `POST /transactions/{reference}/refund` | `Idempotency-Key` | `201 { "reference" (du remboursement), "status" }` · `403` (pas le bénéficiaire) · `409` (déjà remboursée) · `422` (solde insuffisant) |
| `GET /account` | — | `200 { "balance_cents", "currency", "payout_account": { "label", "iban_last4" } }` |
| `POST /payouts` | `Idempotency-Key`, `{ "amount_cents" }` | `201 { "reference", "status", "amount_cents" }` · `422` (solde insuffisant) |
| `POST /requests` | `Idempotency-Key`, `{ "payer": "<email ou téléphone>", "amount_cents", "description" }` | `201 { "reference": "rq_…", "status", "failure_reason", "expires_at" }` |
| `GET /requests` | `?role=incoming\|outgoing&status=` | `200 { "items": [ { "reference", "role", "counterparty", "amount_cents", "description", "status", "created_at", "expires_at" } ] }` |
| `POST /requests/{reference}/pay` | `Idempotency-Key`, `{ "card": {…} }` (par le payeur demandé) | comme `POST /pay` ; la demande passe à `paid` si le paiement est autorisé |
| `POST /requests/{reference}/decline` | — (par le payeur demandé) | `200` → `declined` |
| `POST /requests/{reference}/cancel` | — (par le demandeur) | `200` → `cancelled` |
| `GET /qr` | — | `200 { "qr_token", "payload": "orbe://pay?to=<jeton>", "display_name" }` |
| `POST /qr/rotate` | — | `200` nouveau jeton (l'ancien QR devient invalide) |
| `GET /health/live` · `/health/ready` | — | `ready` = ping DB + pool disponible |
| `GET /metrics` | — | |

**Désignation du bénéficiaire** — un seul champ, email **ou** téléphone :
- normalisation avant recherche : email en minuscules sans espaces ; téléphone en E.164 (`06 12 34 56 78` → `+33612345678`) ;
- le bénéficiaire doit avoir un compte Orbe ; transfert à soi-même interdit ;
- réponse neutre `decline_reason: "recipient_not_found"` et limitation des essais (anti-énumération) ; **pas** d'endpoint de recherche de bénéficiaire ;
- **QR code** : jeton opaque aléatoire par client (`clients.qr_token`), révocable par `POST /qr/rotate` ; le QR ne contient ni email ni téléphone ;
- les comptes de la sonde (`is_probe`) ne sont joignables que par la sonde.

**Demandes d'argent** (« Demander ») :
- le demandeur désigne le payeur par email ou téléphone ; demande à soi-même interdite ;
- payeur introuvable → `201` avec `status: "failed"`, `failure_reason: "recipient_not_found"` (même réponse neutre que le paiement) ;
- statuts : `pending` → `paid` \| `declined` (par le payeur) \| `cancelled` (par le demandeur) \| `expired` (après 7 jours) ;
- au plus 20 demandes `pending` émises par client ; payer une demande reprend exactement le montant demandé.

**Cartes de test** (aucune carte réelle acceptée)

| Numéro | Résultat |
|---|---|
| `4242 4242 4242 4242` | `authorized` |
| `4000 0000 0000 0002` | `declined` — `card_declined` |
| `4000 0000 0000 0069` | `declined` — `card_expired` |
| `4000 0000 0000 9995` | `declined` — `insufficient_funds` |
| autre numéro, Luhn invalide ou date passée | `422` |

**Données de carte** : seuls `card_brand` et `card_last4` sont stockés. Le numéro complet, le CVC et le titulaire ne sont **jamais** stockés ni journalisés (filtre explicite dans le logger).

**Contrôles serveur** (le montant vient du client)
- `amount_cents` entier, 1 ≤ montant ≤ **50 000 (500 €)** ; devise `EUR` uniquement ; frais nuls ;
- opération acceptée seulement dans une **session active et non révoquée** (v2 : liste de révocation lue avec un cache court, pour ne pas consommer une connexion du pool à chaque paiement) ;
- limite de 10 paiements par minute et par client ;
- remboursement : par le **bénéficiaire** uniquement, total, une seule fois, si son solde le permet ;
- retrait : montant ≤ solde.

**Traitement d'un paiement**
1. Vérification locale du JWT (clé publique) et validation du corps.
2. Résolution du bénéficiaire.
3. Insertion `pending` avec `idempotency_key` unique.
4. Appel simulé au « réseau d'autorisation » fictif selon la carte de test (latence 50–150 ms, **connexion DB conservée** — rend le pool de connexions réaliste comme ressource critique).
5. Si accepté : passage à `authorized` **et** crédit du solde du bénéficiaire dans **la même transaction SQL** (mises à jour atomiques, `UPDATE … SET balance_cents = balance_cents + :montant`). Sinon : `declined` + `decline_reason`.
6. Réponse. Un refus de carte est un `201` avec `status: "declined"` : la transaction existe, elle est refusée.

**Référence publique** : `tx_` + 8 caractères hexadécimaux (ex. `tx_9c01e7aa`), unique ; l'UUID reste interne.

**Comptabilité en partie double** : toute opération autorisée ou effectuée génère **deux écritures** de même montant (débit, crédit), dans la même transaction SQL ; une opération refusée n'en génère aucune.

| Opération | Débit | Crédit |
|---|---|---|
| Paiement autorisé | contrepartie « Encaissements carte » | compte Orbe du bénéficiaire |
| Remboursement | compte Orbe du bénéficiaire | contrepartie « Encaissements carte » |
| Retrait | compte Orbe du client | contrepartie « Retraits » |

**Contrôles de cohérence** (vérifiés après chaque remédiation, §7.5) :
- pour chaque opération, Σ débits = Σ crédits ;
- pour chaque compte, `solde = Σ crédits − Σ débits` ; solde d'un compte client ≥ 0.

**Autres évolutions v2** :
- **Comptes de contrepartie** (« Encaissements carte », « Retraits ») : comptes Orbe sans titulaire qui représentent l'extérieur, pour que chaque écriture ait son vis-à-vis.
- **Plusieurs comptes liés** par client, dont un par défaut : `GET/POST/DELETE /payout-accounts`, `POST /payout-accounts/{id}/default` ; `POST /payouts` accepte un `payout_account_id` facultatif (sinon le compte par défaut).
- **Contacts** : `GET /contacts`, `POST /contacts` (`{ "contact": "<email ou téléphone>", "alias" }`), `DELETE /contacts/{id}` ; seuls des clients Orbe peuvent être ajoutés, réponse neutre si le contact est inconnu (anti-énumération).

**Paramètres** : pool SQLAlchemy `pool_size=10`, `max_overflow=0`, `pool_timeout=2s` ; MariaDB `max_connections=60`.
**Au démarrage** : réconciliation — toute transaction `pending` depuis plus de 30 s passe en `failed` (motif `recovery`).

### 4.4 probe — sonde de transaction synthétique (8006)

- Toutes les 10 s : `login` → `pay` (carte `4242…`, 1 €) → `GET /transactions/{reference}` **à travers le WAF** (vrai chemin utilisateur).
- v2 : la sonde ne peut pas présenter de visage ; elle se connecte avec la clé d'API de son CLIENT_API de type `service` (exception documentée, §4.2).
- Deux comptes de test dédiés (payeur et bénéficiaire de la sonde), marqués `is_probe`, **exclus** des historiques et soldes affichés aux clients ; IP en liste blanche du blocage dynamique.
- Expose `probe_transaction_success` (0/1), `probe_transaction_duration_seconds`, `probe_step_failures_total{step}`.
- Fournit aussi `POST /run` (appelé par le moteur pour la vérification, §7.5).

### 4.5 detector-ml (8004)

| Endpoint | Sortie |
|---|---|
| `GET /score` | `{ "target", "score", "threshold", "features": {…}, "top_deviations": [...] }` |
| `GET /metrics` | `anomaly_score{target}`, `anomaly_detected{target}`, `detector_inference_seconds` |

Détail du modèle en §6.

### 4.6 remediation-engine (8003)

| Endpoint | Accès | Rôle |
|---|---|---|
| `POST /webhook/alert` | Alertmanager uniquement, `Bearer` | Réception des alertes |
| `GET /incidents` · `GET /incidents/{id}` | dashboard (lecture) | Suivi des incidents |
| `GET /status` | dashboard (lecture) | État agrégé des services (via Prometheus `up` + sonde) |
| `GET /status/public` | WAF (`/api/status`), lecture | État minimal pour le frontend : `{ "platform": "operational\|incident\|remediation\|recovered", "payments_enabled", "updated_at", "services": [ { "name", "state" } ], "incident": { "detected_at", "recovered_at", "verified_by" } \| null }` — servi par le moteur pour rester disponible quand `payment-service` tombe ; aucune donnée interne |
| `GET /health` · `GET /metrics` | interne | `remediation_incidents_total{type,status}`, `remediation_duration_seconds` |

Détail en §7.

### 4.7 dashboard

- React/Tailwind, servi par Nginx sur `127.0.0.1:8080`.
- **Back : `bo-api` (8006, FastAPI, lecture seule)**, seul service appelé par le dashboard ; son Nginx relaie `/bo/` vers bo-api, rien d'autre. bo-api lit Prometheus, Loki, Grafana, le moteur de remédiation (`GET /incidents*`, `GET /status`), le détecteur et l'assistant ; lecture de la base avec le compte `bo_ro` (lecture seule ; clients via la vue `bo_clients`, email et téléphone masqués par MariaDB) ; aucun accès au socket Docker, aucune route d'écriture.
- **Données applicatives** (`/bo/data`) : indicateurs, séries et contrôle comptable (rôle `viewer`) ; listes et fiches des opérations, clients et demandes (rôle `operator`, chaque consultation journalisée pour le SOC). Comptes de la sonde exclus.
- **Connexion des opérateurs** : comptes distincts des clients (`operators`), mot de passe seul (pas de reconnaissance faciale pour le back-office), relayée par bo-api vers auth-service (`/operators/*`). JWT d'audience `orbe-bo` (1 h), rôles `viewer` et `operator`. Comptes créés par un administrateur (`scripts/create_operator.py`), jamais par l'API.
- Rafraîchissement 2 s (ou SSE). Panneaux Grafana intégrés (`allow_embedding`, viewer anonyme en lecture seule, port publié sur 127.0.0.1) : tableau versionné `orbe-supervision`, liens fournis par `GET /bo/grafana`.
- Vues : état des services (vert / dégradé / rétabli), frise de l'incident (détecté → contenu → rétabli → vérifié), score d'anomalie, transactions de la sonde.

### 4.8 assistant-rag (8005)

| Endpoint | Entrée | Sortie |
|---|---|---|
| `POST /ask` | `{ "question" }` | `{ "answer", "sources": [ { "doc", "extrait" } ] }` |

- Ingestion de `docs/` (Markdown) : découpage 800 caractères / chevauchement 100, embeddings `nomic-embed-text` via Ollama, ChromaDB persistant.
- Récupération k=4, réponse avec citations obligatoires, refus si rien de pertinent.
- Modèle : Qwen2.5 3B / Llama 3.2 3B sur l'hôte, ou Llama 3.1 8B Q4 sur le PC IA (`OLLAMA_BASE_URL`).
- **Aucun** accès au moteur de remédiation, au socket Docker ni à la base.

### 4.9 Frontend « Orbe » — données par écran et corrections de la maquette

Maquette de référence : `frontend/maquette/orbe-accueil-mobile.html` (application mobile 390 × 844 ; seul l'écran « 2 · Accueil » est fourni, les écrans Envoyer, Recevoir et Activité sont référencés mais pas encore livrés).

| Écran | Appels API |
|---|---|
| Connexion | `POST /api/auth/login` |
| Accueil | `GET /api/auth/me` (prénom), `GET /api/payments/account` (solde, compte lié), `GET /api/payments/transactions?limit=4` (activité récente), `GET /api/status` |
| Demander | `POST /api/payments/requests`, `GET /api/payments/requests` |
| Mon QR / Recevoir | `GET /api/payments/qr`, `POST /api/payments/qr/rotate` |
| Paiement (transfert) | `GET /api/auth/me`, `POST /api/payments/pay`, `GET /api/status` (toutes les 3 s) |
| Historique | `GET /api/payments/transactions`, `POST /api/payments/transactions/{reference}/refund` |
| Solde et retrait | `GET /api/payments/account`, `POST /api/payments/payouts` |
| Paiement pendant l'incident | `GET /api/status` (toutes les 3 s) : bandeau, état des services, bouton « Payer » actif seulement si `payments_enabled` |

**Corrections à apporter à la maquette**

| Élément de la maquette | Correction |
|---|---|
| Commande `CMD-2026-0142` et récapitulatif (Licence Pro, Support…) | Remplacer par un formulaire de **transfert** : bénéficiaire (email ou téléphone), montant, libellé |
| « Carte vérifiée par auth-service » | « Session vérifiée » — auth-service authentifie le client, il ne vérifie pas les cartes |
| Noms `payment-api`, `payments-db` | `payment-service`, `mariadb` |
| Historique : colonnes Référence, Date, Description, Carte, Montant, Statut | Ajouter le **sens** (envoyé / reçu) et le **correspondant** ; bouton « Rembourser » sur les paiements reçus `authorized` ; statuts « Échouée » et « Effectué » |
| « Sessions expirent après 15 min d'inactivité » | « Sessions valables 15 min » (sauf ajout d'un jeton de rafraîchissement) |
| Transaction de vérification `tx_9c01e7aa` visible dans l'historique du client | Les transactions de la sonde sont exclues des vues client ; la référence n'apparaît que dans le bandeau « Service rétabli » |
| Absent | Écran **Solde et retrait** : solde, compte de retrait fictif (`•••• 1234`), bouton « Retirer » |
| Accueil — « Compte lié : l'argent part de ce compte » | L'argent part de la **carte de test** ; le compte lié reçoit les **retraits**. Libellé : « Vos retraits arrivent sur ce compte » |
| Accueil — solde absent | Afficher le **solde Orbe** (`balance_cents`) au-dessus du compte lié |
| Accueil — activité récente (initiales, nom, note, heure, montant signé, Envoyé / Reçu) | Correspond à `counterparty`, `description`, `created_at`, `amount_cents` + `direction` de `GET /transactions` ; les initiales sont calculées par le front |

---

## 5. Modèle de données (MariaDB)

Modèle conceptuel, règles de gestion et MLD : [`docs/mcd.md`](docs/mcd.md). Schéma de référence : `infra/mariadb/init/01-schema.sql` (tables `clients`, `client_apis`, `client_face_templates`, `sessions`, `ledger_accounts`, `ledger_entries`, `payout_accounts`, `contacts`, `transactions`, `payment_requests`).

| `type` | payer | recipient | Statuts possibles |
|---|---|---|---|
| `payment` | client qui paie | client bénéficiaire | `pending` → `authorized` \| `declined` \| `failed` ; `authorized` → `refunded` |
| `refund` | bénéficiaire du paiement | payeur d'origine | `pending` → `completed` \| `failed` |
| `payout` | client qui retire | — | `pending` → `completed` \| `failed` |

**Libellés côté front** : `authorized` = Autorisée · `pending` = En attente · `declined` = Refusée · `failed` = Échouée · `refunded` = Remboursée · `completed` = Effectué.

**Comptes MariaDB (moindre privilège, droits par colonne)** — `infra/mariadb/init/02-users.sh`

| Compte | Droits |
|---|---|
| `auth_svc` | `clients` (lecture, `UPDATE (failed_logins, locked_until, biometric_consent_at)`), `client_apis` (lecture), `client_face_templates` (lecture, insertion, suppression), `sessions` |
| `payment_svc` | `clients` (lecture, `UPDATE (qr_token)`), `sessions` (lecture de `id, client_id, client_api_id, status, factors, expires_at` uniquement), `ledger_accounts` (lecture, création, `UPDATE (balance_cents)`), `ledger_entries` (lecture, insertion), `transactions`, `payment_requests`, `payout_accounts`, `contacts` |
| `remediation_ro` | lecture de `transactions`, `ledger_entries`, `ledger_accounts` (contrôles de cohérence) |
| `exporter` | `PROCESS, REPLICATION CLIENT, SLAVE MONITOR` |

Applications clientes à secret (sonde, partenaires) : `infra/mariadb/init/03-client-apis.sh`, clés lues dans des secrets Docker, seule leur empreinte est stockée.

**Données** : jeu fictif généré par Faker (`scripts/seed.py`) : clients avec email et téléphone fictifs (`+33 6…`, domaine `.test`), comptes de retrait fictifs, historique de transactions couvrant tous les statuts. Cartes : uniquement les cartes de test du §4.3, dont seuls la marque et les 4 derniers chiffres sont stockés.
**Sauvegarde** : `mariadb-dump` toutes les 5 min vers un volume dédié, rétention 24 h.

---

## 6. Observabilité

### 6.1 Prometheus

- `scrape_interval: 5s`, `evaluation_interval: 5s`.
- Cibles : services (`/metrics`), probe, detector-ml, remediation-engine, mysqld-exporter, cadvisor, Alertmanager.

| Métrique | Source |
|---|---|
| `http_requests_total{service,handler,method,status}` | instrumentator FastAPI |
| `http_request_duration_seconds_bucket{service,handler}` | instrumentator FastAPI |
| `http_requests_inprogress{service}` | instrumentator FastAPI |
| `payment_transactions_total{type,status}` | payment-service |
| `payment_declines_total{reason}` | payment-service |
| `payment_db_pool_in_use` · `payment_db_pool_size` | payment-service |
| `auth_login_failures_total` | auth-service |
| `probe_transaction_success` · `probe_transaction_duration_seconds` | probe |
| `mysql_global_status_threads_connected` | mysqld-exporter |
| `container_cpu_usage_seconds_total` · `container_memory_working_set_bytes` | cadvisor |
| `anomaly_score{target}` | detector-ml |
| `remediation_incidents_total{type,status}` · `remediation_duration_seconds` | remediation-engine |

### 6.2 Journaux

- Format JSON unique pour les services Python : `ts`, `level`, `service`, `request_id`, `client_ip`, `method`, `path`, `status`, `duration_ms`, `msg`.
- `request_id` généré par le WAF (`X-Request-ID`) et propagé.
- Alloy : découverte des conteneurs Docker, labels Loki limités à `service`, `level`, `container` (pas d'IP en label → cardinalité).
- Rétention Loki : 72 h.

### 6.3 SOC intégré (Grafana + règles Loki)

| Règle | Requête (principe) |
|---|---|
| Rafale d'échecs d'authentification | `count_over_time({service="auth-service"} \|= "login_failed" [1m])` par IP > seuil |
| Règles CRS déclenchées | `{service="waf"} \| json \| modsec_rule_id != ""` |
| Actions de remédiation | `{service="remediation-engine"} \| json \| event="action"` |
| Alertes IDS *(si Snort)* | `{service="snort"}` |

Tableau de bord « SOC » : événements de sécurité, top IP sources, règles déclenchées, chronologie des actions du moteur.

### 6.4 Alerting

```yaml
# prometheus/rules/anomaly.yml
- alert: PaymentAnomaly
  expr: anomaly_score{target="payment-service"} > 0.7   # seuil calibré (§6.5)
  for: 10s
  labels: { severity: critical, incident_type: resource_exhaustion, target: payment-service }
```

```yaml
# alertmanager.yml (extrait)
route:
  receiver: remediation
  group_by: [alertname, target]
  group_wait: 5s
  group_interval: 30s
  repeat_interval: 5m
receivers:
  - name: remediation
    webhook_configs:
      - url: http://remediation-engine:8003/webhook/alert
        http_config:
          authorization: { credentials_file: /run/secrets/remediation_webhook_token }
```

### 6.5 Détection ML

| Élément | Choix |
|---|---|
| **Approche** | Détection d'anomalies non supervisée, **un modèle par service cible** |
| **Modèle** | `StandardScaler` + `IsolationForest` (pipeline scikit-learn, sérialisé en joblib) |
| **Cadence** | Inférence toutes les 5 s sur une fenêtre glissante de 30 s |
| **Score** | `decision_function` normalisée en [0, 1] (bornes issues du jeu d'entraînement) |

**Variables d'entrée (payment-service)**

| Variable | Requête (principe) |
|---|---|
| débit | `sum(rate(http_requests_total{service="payment"}[30s]))` |
| latence p95 | `histogram_quantile(0.95, sum by (le)(rate(http_request_duration_seconds_bucket{service="payment"}[30s])))` |
| taux 5xx | ratio `status=~"5.."` / total |
| saturation du pool | `max(payment_db_pool_in_use / payment_db_pool_size)` |
| connexions DB | `mysql_global_status_threads_connected` |
| CPU / mémoire conteneur | cadvisor |
| IP sources distinctes | Loki : `count(sum by (client_ip)(count_over_time({service="waf"} \| json [30s])))` |
| concentration du trafic | part de la 1ʳᵉ IP source dans le volume total (Loki) |
| part non authentifiée | ratio `401` / total |

**Pipeline**

| Script | Rôle |
|---|---|
| `ml/collect.py` | Enregistre les vecteurs de variables en CSV pendant le trafic Locust (profils : nominal, pic légitime, heures creuses) |
| `ml/train.py` | Entraîne sur le trafic **normal uniquement**, sauvegarde `model-payment.joblib` + bornes de normalisation |
| `ml/evaluate.py` | Rejoue des épisodes étiquetés (nominal / pic légitime / SC-01) → précision, rappel, faux positifs, **délai de détection** ; produit le seuil retenu |
| `services/detector-ml` | Charge le modèle, interroge Prometheus et Loki, publie le score |

- `top_deviations` (z-scores par variable) sert à l'explicabilité dans le dashboard et à qualifier le type d'incident.
- Un **pic légitime** doit rester sous le seuil : c'est le test qui prouve que le modèle ne confond pas charge et attaque.
- Filet de sécurité optionnel : règle simple sur `probe_transaction_success`, documentée comme complémentaire.

---

## 7. Moteur de remédiation

### 7.1 Architecture interne

- FastAPI + worker asynchrone (file `asyncio`) : le webhook répond `202` immédiatement, l'exécution est découplée.
- Stockage des incidents dans **SQLite** (volume dédié) — volontairement indépendant de MariaDB, qui peut être la ressource dégradée.
- Exécution des playbooks via **`ansible-runner`** (bibliothèque Python), inventaire `localhost`, collection `community.docker`.
- Accès Docker via `DOCKER_HOST=tcp://socket-proxy:2375` uniquement.

### 7.2 Machine à états

```
detected ──► containing ──► recovering ──► verifying ──► verified
                 │               │             │
                 └───────────────┴─────────────┴──► escalated ──► (niveau suivant) ──► failed
```

### 7.3 Politiques (`policies.yml`)

```yaml
resource_exhaustion:
  levels: [pb-contain-and-recover.yml, pb-redeploy-clean.yml]
  cooldown_s: 120          # par cible : pas de nouvelle action pendant ce délai
  max_attempts: 2
compromise:
  levels: [pb-isolate-rotate-redeploy.yml]
  cooldown_s: 300
  max_attempts: 1
```

- Déduplication : une alerte sur une cible déjà en cours de traitement est rattachée à l'incident existant.
- Toute action est journalisée (Loki + SQLite) avec l'acteur `remediation-engine`.

### 7.4 Playbook SC-01 — `pb-contain-and-recover.yml`

| Étape | Action technique | But |
|---|---|---|
| 1 | Requête Loki : IP sources les plus contributrices sur les 30 dernières secondes (hors liste blanche) | Cibler |
| 2 | Écriture de `blocklist.conf` (TTL 15 min) + `docker kill --signal HUP waf` via le proxy | **Contenir** |
| 3 | Identification des instances `payment-*` dont `/health/ready` échoue | Diagnostiquer |
| 4 | Redémarrage des instances dégradées (l'instance saine continue de servir via le WAF) | **Rétablir** |
| 5 | Attente `/health/ready` OK sur les deux instances (timeout 20 s) | Préparer |
| 6 | Vérification (§7.5) | **Prouver** |

Niveau 2 `pb-redeploy-clean.yml` : recréation des conteneurs depuis l'image de référence étiquetée, puis vérification.

### 7.5 Vérification — clôture de l'incident

L'incident passe à `verified` **uniquement si** :

- [ ] `POST probe:8006/run` × 3 → 3 succès consécutifs (login → pay → lecture, via le WAF) ;
- [ ] latence p95 sous la valeur de référence ;
- [ ] `anomaly_score` sous le seuil ;
- [ ] cohérence des données (compte `remediation_ro`) : 0 transaction `pending` de plus de 30 s, 0 doublon d'`idempotency_key`, **invariant des soldes respecté pour chaque client** (§4.3) ;
- [ ] `GET /api/status` repasse à `recovered` puis `operational`, `payments_enabled: true`.

Sinon → niveau suivant, puis `failed`.

### 7.6 Budget temps

| Phase | Cible |
|---|---|
| Effet visible de l'attaque | ~5 s |
| Détection (fenêtre 30 s partiellement remplie + `for: 10s`) | ≤ 15 s |
| Alertmanager → moteur | ≤ 5 s |
| Remédiation | ≤ 15 s |
| Vérification | ≤ 5 s |
| **Total** | **≤ 40 s** |

---

## 8. Scénarios d'incident

### 8.1 SC-01 — Épuisement de ressources du service de paiement (principal)

| Élément | Contenu |
|---|---|
| **Catégorie** | Disponibilité, couche applicative |
| **Ressource visée** | Pool de connexions MariaDB et workers de `payment-service` |
| **Chemin** | PC Attaquant → hotspot → WAF :443 → `POST /api/payments/pay` |
| **Effet attendu** | Pool saturé, `pool_timeout` → `503`, latence p95 en hausse, `probe_transaction_success = 0` |
| **Signaux de détection** | Saturation du pool, p95, taux 5xx, concentration du trafic sur peu d'IP, part non authentifiée |
| **Réponse** | Contenir (blocage ciblé au WAF) → rétablir (redémarrage des instances dégradées) → vérifier |
| **Implémentation** | `redteam/sc01/` : script Python paramétrable (cible, durée, intensité), exécuté **uniquement depuis le PC Attaquant** contre le WAF du consortium |

**Garde-fous techniques**
- Limites `cpus` / `mem_limit` / `pids_limit` sur chaque conteneur : seul `payment-service` est affecté, la supervision et le moteur restent opérationnels.
- Deux instances de paiement + sortie automatique d'une instance en échec au niveau du WAF.
- Idempotence + réconciliation au démarrage : aucune transaction incohérente après la reprise.

### 8.2 SC-02 — Tentative de compromission sur auth-service (bonus)

| Élément | Contenu |
|---|---|
| **Catégorie** | Confidentialité / intégrité |
| **Signaux** | Journaux d'authentification, règles CRS, alertes IDS, modèle `auth-service` |
| **Réponse** `pb-isolate-rotate-redeploy.yml` | Déconnexion du conteneur de `net-app` → export des journaux (preuves) → **révocation des sessions** concernées (v2 : table `sessions`) et, si la clé JWT est en cause, rotation de la clé JWT et des identifiants DB dans Vault → redéploiement depuis l'image de référence → vérification |

À engager seulement si SC-01 est stable.

---

## 9. Sécurité technique

### 9.1 Moteur de remédiation (composant à privilèges)

| Mesure | Détail |
|---|---|
| Pas de socket Docker monté | Accès via `socket-proxy`, sur un réseau interne joignable par le seul moteur |
| Proxy restreint | `CONTAINERS=1`, `POST=1`, `NETWORKS=1` (SC-02) ; tout le reste à 0 (`EXEC`, `IMAGES`, `VOLUMES`, `BUILD`, `SECRETS`, `SWARM`…) — liste minimale à valider en intégration |
| Webhook authentifié | Jeton porteur, comparaison à temps constant, jeton stocké dans Vault |
| Surface réduite | Routes d'écriture inaccessibles depuis le dashboard ; aucun port publié |
| Actions bornées | Seuls les playbooks listés dans `policies.yml` sont exécutables ; cibles limitées par label `resilience.managed=true` |
| Traçabilité | Journal d'audit de chaque action (Loki + SQLite) |

### 9.2 Durcissement des conteneurs (défaut pour tous)

```yaml
user: "10001:10001"
read_only: true            # + tmpfs /tmp si nécessaire
cap_drop: [ALL]
security_opt: [no-new-privileges:true]
pids_limit: 128
restart: unless-stopped
healthcheck: { ... }
```

Exceptions documentées au cas par cas (cadvisor, alloy, mariadb).

### 9.3 Secrets — Vault

| Élément | Choix |
|---|---|
| Mode | Serveur, stockage `file` sur volume, TLS interne |
| Amorçage | `infra/vault/bootstrap.sh` (appelé par Ansible) : init, unseal, montage KV v2, politiques, AppRoles |
| Clés d'unseal / token root | Chiffrés avec **SOPS + age** dans `infra/vault/bootstrap.enc.yaml` ; la clé age reste hors dépôt (KeeWeb) |
| Accès des services | Jeton en lecture seule (secret Docker `oorbe_vault_token`) ou **AppRole** (`role_id` / `secret_id` en secrets Docker), lu au démarrage par `app/vault.py` (auth, payment, bo-api) ; valeurs gardées en mémoire, jamais journalisées ; repli sur `/run/secrets/` si Vault est injoignable ou si une clé manque |
| Chemins | **`secret/data/oorbe/config`** (choix de l'infra, KV v2) : mots de passe MariaDB des comptes de service, clé de chiffrement des gabarits faciaux, clé d'API de la sonde, mot de passe admin Grafana. Les clés JWT restent en secrets Docker. **Risque assumé** : un chemin unique donne à chaque service la lecture de tous les secrets ; cible : un chemin et une politique par service (`secret/oorbe/auth`, `…/payment`, `…/bo`), sans changement de code (`*_VAULT_KV_PATH`) |
| Politiques | Lecture seule, un chemin par service ; seul `remediation-engine` peut écrire sur `kv/auth` et `kv/payment` (rotation SC-02) |

### 9.4 Contrôles en CI

gitleaks (secrets), Trivy (images et dépendances), ruff + bandit (Python), eslint (front), ansible-lint, `docker compose config`.

---

## 10. Assistant opérateur — PC IA (si utilisé)

- Ollama écoute sur l'IP du PC IA, **pare-feu Windows limité à l'IP du PC Hôte**, port 11434 uniquement.
- Le PC IA n'héberge que le modèle et son API.
- `assistant-rag` reste sur le PC Hôte (réseau `net-ctrl`) et appelle `OLLAMA_BASE_URL`.

---

## 11. Déploiement et CI

### 11.1 Ansible (exécuté depuis un conteneur `ansible`)

| Playbook | Rôle |
|---|---|
| `deploy.yml` | Prérequis (hotspot actif, ressources WSL2), génération TLS, `.env`, bootstrap Vault, `compose up`, attente des healthchecks, seed des données |
| `verify.yml` | Tests de fumée : santé de tous les services, transaction de bout en bout, cibles Prometheus `up`, Loki reçoit les journaux |
| `reset.yml` | Retour à l'état nominal entre deux répétitions (vidage de la liste de blocage, incidents archivés, services relancés) |
| `backup.yml` / `restore.yml` | Dump et restauration MariaDB |
| `remediation/*.yml` | Playbooks du moteur (§7) |

Point d'entrée Windows : `scripts/deploy.ps1`, `scripts/verify.ps1`, `scripts/reset.ps1`.

### 11.2 GitHub Actions

| Workflow | Déclencheur | Étapes |
|---|---|---|
| `ci.yml` | PR + push `main` | lint → tests unitaires (pytest, MariaDB en service) → build des images → Trivy → gitleaks → `compose config` → ansible-lint |

Pas de déploiement depuis la CI : les runners GitHub ne joignent pas le PC Hôte, et un runner auto-hébergé exécuterait du code externe sur la machine la plus sensible.

### 11.3 Tests

| Niveau | Contenu |
|---|---|
| Unitaires | Règles de paiement, idempotence, validation JWT, politiques du moteur, machine à états |
| Intégration | `compose up` + `verify.yml` |
| Résilience | Rejeu SC-01 (et SC-02) avec mesure de T2 à T6 ; chaos : arrêt d'une instance de paiement, redémarrage de MariaDB, perte du detector-ml |

---

## 12. Structure du dépôt

```
.
├── README.md
├── CADRAGE.md
├── docker-compose.yml
├── .env.example
├── .github/workflows/ci.yml
├── services/
│   ├── auth-service/
│   ├── payment-service/
│   ├── probe/
│   ├── detector-ml/
│   ├── remediation-engine/
│   └── assistant-rag/
├── frontend/
├── dashboard/
├── infra/
│   ├── ansible/          # deploy, verify, reset, backup, remediation/
│   ├── waf/              # conf Nginx, CRS, blocklist
│   ├── prometheus/  alertmanager/  loki/  alloy/  grafana/
│   ├── mariadb/          # init SQL, comptes
│   └── vault/            # bootstrap, politiques, bootstrap.enc.yaml
├── ml/                   # collect, train, evaluate, locustfile
├── redteam/              # scénarios (PC Attaquant uniquement)
├── scripts/              # *.ps1, seed.py
├── tests/
└── docs/                 # corpus RAG, doc API (OpenAPI exportés)
```

---

## 13. Risques techniques

| Risque | Parade |
|---|---|
| Mémoire insuffisante sur 16 Go | Plafonds par conteneur, `.wslconfig`, LLM 3B ou déporté |
| cAdvisor partiel sous Docker Desktop / WSL2 | Tester lundi ; repli sur les métriques applicatives et `docker stats` via exporter |
| Snort ne voit pas le trafic dans WSL2 | Optionnel, ne bloque pas la chaîne |
| Faux positifs du modèle | Profils de pic légitime dans l'entraînement, `for: 10s`, cooldown du moteur |
| Instabilité du hotspot | Test de reconnexion, vérification dans `deploy.yml` |
| Démo non déterministe | Script SC-01 figé, `reset.yml` entre répétitions, mesures T1–T6 automatisées |

---

## 14. Points techniques ouverts

- [ ] RAM du PC Hôte (16 ou 32 Go) et disponibilité d'un PC IA
- [ ] Modèle LLM définitif
- [ ] Liste minimale validée des droits du `socket-proxy`
- [ ] Faisabilité cAdvisor et Snort sous WSL2
- [ ] Seuil du score d'anomalie (après `ml/evaluate.py`)
- [ ] SC-02 : go / no-go
- [ ] Jeton de rafraîchissement (session « 15 min d'inactivité ») : oui / non
- [ ] Mise à jour de la maquette selon §4.9
- [ ] Appareils de démo avec caméra (téléphone ou PC), éclairage correct ; visages de l'équipe enregistrés à l'avance
- [ ] `orbe.test` + CA `mkcert` installée sur ces appareils : à tester dès le premier jour
- [ ] Résolution de `orbe.test` depuis un téléphone sur le hotspot (DNS du hotspot ou nom de type `sslip.io`) et confiance de la CA `mkcert` sur Android
- [ ] Seuil de reconnaissance faciale mesuré sur l'équipe (§4.2)
