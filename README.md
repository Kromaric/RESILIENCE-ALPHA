# PROJECT RESILIENCE-ALPHA — Orbe

Démonstrateur de cyber-résilience (workshop EPSI BAC+5, octobre 2026) : une plateforme de paiement fictive entre particuliers, **Orbe**, capable de détecter automatiquement une cyberattaque (déni de service, saturation de ressources) et de s'auto-remédier en moins de 40 secondes sans intervention humaine.

- **Cadrage technique et d'architecture** : [`CADRAGE.md`](CADRAGE.md)
- **Modèle de données relationnel** : [`docs/mcd.md`](docs/mcd.md)
- **Documentation des API (OpenAPI / Swagger)** : [`docs/api/`](docs/api/)
- **Runbooks d'exploitation** : [`docs/runbooks/`](docs/runbooks/)

> [!NOTE]
> Toutes les données sont fictives. Aucune donnée bancaire ou personnelle réelle n'est utilisée.

---

## Sommaire

1. [Architecture générale](#architecture-générale)
2. [Prérequis](#prérequis)
3. [Configuration initiale (Secrets & DNS)](#configuration-initiale-secrets--dns)
4. [Options de déploiement](#options-de-déploiement)
   - [Option A : Pile complète de démonstration (Recommandé)](#option-a--pile-complète-de-démonstration-recommandé)
   - [Option B : Pile de test local de cyber-résilience](#option-b--pile-de-test-local-de-cyber-résilience)
   - [Option C : Pile de développement minimal](#option-c--pile-de-développement-minimal)
5. [Comptes de démonstration & Identifiants](#comptes-de-démonstration--identifiants)
6. [Cartographie des accès et services](#cartographie-des-accès-et-services)
7. [Guide de vérification du système](#guide-de-vérification-du-système)
   - [1. Vérification de l'état des conteneurs](#1-vérification-de-létat-des-conteneurs)
   - [2. Vérification fonctionnelle de bout en bout](#2-vérification-fonctionnelle-de-bout-en-bout)
   - [3. Vérification de la cyber-résilience (Scénario d'attaque et auto-remédiation)](#3-vérification-de-la-cyber-résilience-scénario-dattaque-et-auto-remédiation)
   - [4. Vérification de la supervision et des journaux](#4-vérification-de-la-supervision-et-des-journaux)
   - [5. Exécution des tests automatisés](#5-exécution-des-tests-automatisés)
8. [Arrêt et réinitialisation](#arrêt-et-réinitialisation)

---

## Architecture générale

Le système Orbe est découpé en quatre couches étanches :

```
                                 ┌────────────────────────────────────────────────────────┐
                                 │                   Clients & Opérateurs                 │
                                 └───────────┬────────────────────────────────┬───────────┘
                                             │ https://payment.oorbe.fr       │ https://dashboard.oorbe.fr
                                             ▼                                ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ EDGE / PROXY : WAF OWASP ModSecurity CRS (Nginx TLS 8443)                                              │
│ - Filtrage applicatif et liste de blocage dynamique (infra/waf/blocklist/blocklist.conf)               │
└────────────┬───────────────────────────────┬────────────────────────────────┬───────────────────────────┘
             │                               │                                │
             ▼                               ▼                                ▼
┌──────────────────────────┐    ┌──────────────────────────┐    ┌──────────────────────────┐
│ oorbe-interface (8081)   │    │ oorbe-auth-service (8001)│    │ oorbe-dashboard (8083)   │
│ WebApp mobile P2P React  │    │ JWT RSA 3072, 2FA visage │    │ Dashboard SOC React      │
└──────────────────────────┘    └────────────┬─────────────┘    └─────────────┬────────────┘
                                             │                                │
                                             ▼                                ▼
                                ┌──────────────────────────┐    ┌──────────────────────────┐
                                │ oorbe-payment-service    │    │ oorbe-bo-api (8006)      │
                                │ (8002) - Double partie   │    │ API supervision (RO)     │
                                └────────────┬─────────────┘    └─────────────┬────────────┘
                                             │                                │
                                             ▼                                ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ PERSISTANCE & SÉCURITÉ : MariaDB (Schéma strict, moindres privilèges) · HashiCorp Vault                │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────┘
                                             ▲
                                             │ Métriques & Alertes
┌────────────────────────────────────────────┴────────────────────────────────────────────────────────────┐
│ PLAN DE CONTRÔLE & RÉSILIENCE AUTONOME                                                                  │
│ - detector-ml (8004) : Détection d'anomalies (IsolationForest) sur métriques temps réel                 │
│ - Prometheus (9090) & Alertmanager (9093) : Déclenchement d'alertes saturations / dégradations          │
│ - remediation-engine (8003) : Moteur d'auto-remédiation (blocage WAF IP, redémarrage conteneurs,       │
│   vérification comptable et reprise automatique)                                                        │
│ - assistant-rag (8005) : Assistant opérateur IA connecté à Ollama                                       │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Prérequis

- **Docker Desktop** avec le moteur Docker Compose v2 (sous Linux, macOS ou Windows avec WSL2).
  - Allocation recommandée : 4 vCPU, 8 à 12 Go de RAM disponibles.
- **Python 3.12+** pour exécuter les scripts d'initialisation, de tokens et les tests.
- **Droits d'administration locaux** pour renseigner le fichier `hosts` de votre machine hôte.

---

## Configuration initiale (Secrets & DNS)

### 1. Résolution des noms de domaine locaux

Le WAF sécurise les échanges via HTTPS et route les requêtes selon le nom de domaine. Ajoutez les entrées suivantes dans votre fichier `hosts` :

- **Linux / macOS** : `/etc/hosts`
- **Windows** : `C:\Windows\System32\drivers\etc\hosts`

```text
127.0.0.1  payment.oorbe.fr payments.oorbe.fr dashboard.oorbe.fr
```

*(Un certificat TLS couvrant ces domaines est déjà provisionné dans [`infra/waf/certs/oorbe.crt`](infra/waf/certs/oorbe.crt)).*

### 2. Environnement virtuel Python et dépendances

Créez un environnement virtuel à la racine du projet :

```bash
# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
pip install cryptography requests

# Windows (PowerShell)
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
pip install cryptography requests
```

### 3. Génération des secrets locaux

Générez les mots de passe de base de données, la clé symétrique AES-256 pour les gabarits biométriques et le bi-clé RSA 3072 JWT dans le dossier `secrets/` (ignoré par Git) :

```bash
# Depuis la racine du projet
python scripts/init_dev_secrets.py
```

> [!TIP]
> Le script ne remplace jamais un secret existant. Pour forcer la régénération d'un secret, supprimez le fichier concerné dans `secrets/` puis relancez le script.

---

## Options de déploiement

Le projet dispose de trois configurations Compose adaptées aux différents besoins.

### Option A : Pile complète de démonstration (Recommandé)

Déploie l'ensemble de l'infrastructure de cyber-résilience : WAF ModSecurity, frontends React, microservices, moteur de remédiation, détecteur ML, pile d'observabilité complète (Prometheus, Loki, Promtail, Grafana, Alertmanager, cAdvisor) et assistant RAG.

```bash
docker compose -f infra/docker-compose.yml up -d --build
```

*(Ou alternativement : `cd infra && docker compose up -d --build`)*

Pour suivre l'état de l'initialisation :
```bash
docker compose -f infra/docker-compose.yml ps
```

### Option B : Pile de test local de cyber-résilience

Déploie une pile intermédiaire comprenant MariaDB, Auth, Payment, BO API, WAF, Prometheus, Alertmanager, Détecteur ML et Moteur de remédiation. Idéal pour tester la boucle d'attaque et de défense en local avec une empreinte mémoire réduite.

```bash
docker compose -f docker-compose.local-test.yml up -d --build
```

### Option C : Pile de développement minimal

Déploie uniquement le cœur applicatif : MariaDB, `auth-service`, `payment-service` et `bo-api`.

```bash
# Microservices seuls
docker compose -f docker-compose.dev.yml up -d --build

# Avec la supervision (Prometheus, Loki, Grafana)
docker compose -f docker-compose.dev.yml --profile obs up -d --build
```

---

## Comptes de démonstration & Identifiants

Les comptes suivants sont pré-chargés en base par les scripts de seed MariaDB :

| Compte | Type | Rôle / Description | Mot de passe |
|---|---|---|---|
| `camille@orbe.test` | Client | Client émetteur (solde crédité, compte lié) | `demo-password` |
| `lea@orbe.test` | Client | Client bénéficiaire (tél: `+33612345677`) | `demo-password` |
| `hugo@orbe.test` | Client | Client de test | `demo-password` |
| `probe@orbe.test` | Sonde | Compte d'émission des transactions de test | `demo-password` |
| `ops@orbe.test` | Opérateur SOC | Accès au Dashboard SOC (`operator`) | `demo-password` |
| `admin@orbe.test` | Administrateur | Administration des habilitations (`admin`) | `demo-password` |
| `viewer@orbe.test` | Opérateur | Consultation en lecture seule (`viewer`) | `demo-password` |

### Créer un nouvel opérateur de supervision

Pour ajouter un nouvel opérateur SOC avec un mot de passe sécurisé :

```bash
python scripts/create_operator.py mon-ops@orbe.test --name "Opérateur Analyse" --role operator
```

---

## Cartographie des accès et services

Une fois la pile déployée, les interfaces et points d'entrée suivants sont accessibles :

### Interfaces Utilisateurs & SOC

| Interface | URL d'accès | Identifiants |
|---|---|---|
| **Interface Client Mobile (P2P)** | [https://payment.oorbe.fr](https://payment.oorbe.fr) ou [https://payments.oorbe.fr](https://payments.oorbe.fr) | Code PIN démo ou login `camille@orbe.test` |
| **Dashboard Opérateur SOC** | [https://dashboard.oorbe.fr](https://dashboard.oorbe.fr) | `ops@orbe.test` / `demo-password` |
| **Grafana** | [http://localhost:3000](http://localhost:3000) | `admin` / mot de passe dans `secrets/grafana_admin_password` |
| **Prometheus UI** | [http://localhost:9090](http://localhost:9090) | Accès direct |
| **Alertmanager UI** | [http://localhost:9093](http://localhost:9093) | Accès direct |

### APIs et Documentations Interactives (Swagger)

| Service | Port local | Documentation Swagger |
|---|---|---|
| `auth-service` | 8001 | [http://localhost:8001/docs](http://localhost:8001/docs) |
| `payment-service` | 8002 | [http://localhost:8002/docs](http://localhost:8002/docs) |
| `bo-api` (Back-Office) | 8006 | [http://localhost:8006/docs](http://localhost:8006/docs) |
| `remediation-engine` | 8003 | [http://localhost:8003/incidents](http://localhost:8003/incidents) |
| `detector-ml` | 8004 | [http://localhost:8004/score](http://localhost:8004/score) |
| `assistant-rag` | 8005 | [http://localhost:8005/health/ready](http://localhost:8005/health/ready) |

---

## Guide de vérification du système

Suivez ces 5 étapes pour vérifier le bon fonctionnement de bout en bout du système, valider l'intégrité des services et éprouver la boucle de cyber-résilience.

### 1. Vérification de l'état des conteneurs

Vérifiez que tous les services sont démarrés et que les sondes d'état répondent :

```bash
# Vérifier l'état global
docker compose -f infra/docker-compose.yml ps
```

Interrogez les points de contrôle de santé :
```bash
# Statut de la plateforme via le WAF
curl -k https://payment.oorbe.fr/api/status

# Santé interne des services
curl http://localhost:8001/health/ready     # Auth
curl http://localhost:8002/health/ready     # Payment
curl http://localhost:8003/status           # Moteur de remédiation
curl http://localhost:8004/health/live      # Détecteur ML
```

### 2. Vérification fonctionnelle de bout en bout

Pour tester le paiement nominal, générez un jeton d'authentification valide pour Camille (avec simulation de 2FA biométrique) :

```bash
python scripts/dev_token.py camille@orbe.test
```

Le script affiche un JWT d'accès valable 15 minutes. Vous pouvez ensuite exécuter un virement de test vers Léa :

```bash
# Remplacer <VOTRE_JWT> par le jeton obtenu
curl -k -X POST https://payment.oorbe.fr/api/payments/pay \
  -H "Authorization: Bearer <VOTRE_JWT>" \
  -H "Idempotency-Key: $(uuidgen)" \
  -H "Content-Type: application/json" \
  -d '{
    "amount": 12.50,
    "recipient": "+33612345677",
    "card_token": "4242 4242 4242 4242"
  }'
```

Puis vérifiez le solde crédité sur le compte de Léa :
```bash
TOKEN_LEA=$(python scripts/dev_token.py lea@orbe.test --quiet)
curl -k https://payment.oorbe.fr/api/payments/account -H "Authorization: Bearer $TOKEN_LEA"
```

### 3. Vérification de la cyber-résilience (Scénario d'attaque et auto-remédiation)

Le projet intègre un outil de Red Team (`redteam/attack.py`) permettant de simuler l'attaque **SC-01 (Épuisement de ressources & saturation de requêtes)**.

#### Étape 3.1 : Lancement de l'attaque
Lancez une attaque par saturation de calcul et de bande passante :

```bash
# Attaque par saturation de requêtes (40 threads simultanés)
python redteam/attack.py --mode resource --threads 40
```

#### Étape 3.2 : Observation de la boucle de remédiation autonome (< 40 secondes)
Observez en direct sur le Dashboard SOC ([https://dashboard.oorbe.fr](https://dashboard.oorbe.fr)) et dans les journaux :

1. **Détection** :
   - Le pic de requêtes / saturation CPU fait grimper le score d'anomalie du `detector-ml` (`GET http://localhost:8004/score`).
   - Prometheus déclenche l'alerte `PaymentServiceHighCpu` ou `PaymentAnomaly` ([http://localhost:9090/alerts](http://localhost:9090/alerts)).
2. **Confinement immédiat** :
   - Alertmanager notifie `remediation-engine` via webhook.
   - Le moteur de remédiation isole l'attaquant en injectant son IP dans la liste de blocage Nginx/WAF ([`infra/waf/blocklist/blocklist.conf`](infra/waf/blocklist/blocklist.conf)) et recharge la configuration WAF.
   - Les requêtes de l'attaquant sont instantanément rejetées avec un statut HTTP `403 Forbidden` (`Blocked by Orbe Remediation Engine`).
3. **Rétablissement & Vérification de reprise** :
   - Le moteur redémarre le conteneur dégradé si nécessaire.
   - Le moteur exécute les **5 contrôles de validation de reprise** (voir [`docs/runbooks/verification-reprise.md`](docs/runbooks/verification-reprise.md)) :
     - 3 transactions de bout en bout exécutées avec succès par la sonde (`probe`).
     - Vérification de l'absence d'incohérence comptable (respect de la partie double).
     - Rétablissement de la latence p95 sous le seuil nominal.
   - Le statut passe à `recovered`, puis `operational`.
   - La frise d'incident sur le dashboard passe à l'état **Vérifié**.

#### Étape 3.3 : Remise à zéro post-attaque
Pour purger la blocklist WAF et réinitialiser les compteurs d'incidents :

```bash
python redteam/attack.py --reset
```

### 4. Vérification de la supervision et des journaux

- **Tableaux de bord Grafana** ([http://localhost:3000](http://localhost:3000)) :
  Consultez les tableaux de bord pré-provisionnés (*Dashboard Orbe*, *Métriques Système*, *Trafic WAF*).
- **Journaux centralisés Loki** :
  Recherchez les logs des services via le panneau Explore de Grafana ou via LogQL :
  `{container="oorbe-payment-service"}` ou `{container="remediation-engine"}`.

### 5. Exécution des tests automatisés

Chaque composant dispose de sa propre suite de tests unitaires et d'intégration :

```bash
# Tests du service d'authentification
python -m pytest services/auth-service

# Tests du service de paiement
python -m pytest services/payment-service

# Tests de l'API back-office
python -m pytest services/bo-api

# Tests du détecteur ML
python -m pytest services/detector-ml

# Tests du moteur de remédiation
python -m pytest services/remediation-engine
```

---

## Arrêt et réinitialisation

### Arrêter les services en conservant les données

```bash
# Pile complète
docker compose -f infra/docker-compose.yml down

# Ou pile de dev
docker compose -f docker-compose.dev.yml down
```

### Réinitialiser entièrement l'environnement (Repartir de zéro)

Pour supprimer également les volumes persistants (base MariaDB, index RAG, métriques Prometheus) et recharger les données de démo initiales au prochain démarrage :

```bash
docker compose -f infra/docker-compose.yml down -v
```
