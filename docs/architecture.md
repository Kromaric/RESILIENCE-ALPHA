# Architecture de la plateforme Orbe

> Source : CADRAGE §3 et §4. Écarts avec l'état actuel du dépôt : voir `etat-implementation.md`.

## Vue d'ensemble de l'architecture Orbe

Orbe est une plateforme de paiement fictive entre particuliers, conteneurisée avec Docker Compose sur le
**PC Hôte** (Windows, Docker Desktop + WSL2). Elle doit détecter une attaque et se rétablir seule.

Trois machines sont impliquées :

| Machine | Adresse | Rôle |
|---|---|---|
| PC Hôte | `192.168.137.1` (point d'accès mobile Windows `RESILIENCE-G<n>`) | Exécute toute la plateforme |
| PC Attaquant | `192.168.137.x` | Lance les scénarios d'attaque (SC-01, SC-02) contre le WAF uniquement |
| PC IA *(facultatif)* | `192.168.137.x` | Héberge uniquement Ollama, joignable seulement depuis le PC Hôte |

```
                   Hotspot Windows 192.168.137.0/24
 ┌──────────────┐                │
 │ PC Attaquant │────────────────┤
 └──────────────┘                ▼  :443 (seul port exposé au hotspot)
 ┌───────────────────────── PC Hôte 192.168.137.1 ─────────────────────────┐
 │  net-front   [ waf ] ──► [ frontend ]          [ probe ]──► waf          │
 │  net-app        ├──► [ auth-service ]                                    │
 │                 └──► [ payment-service-a ] [ payment-service-b ]         │
 │                                  │                                       │
 │                            [ mariadb ]                                   │
 │  net-obs     [ prometheus ] [ alertmanager ] [ loki ] [ alloy ]          │
 │              [ grafana ] [ cadvisor ] [ mysqld-exporter ]                │
 │  net-ctrl    [ detector-ml ] [ remediation-engine ] [ socket-proxy ]     │
 │              [ vault ] [ dashboard ] [ assistant-rag ]                   │
 └──────────────────────────────────────────────────────────────────────────┘
 ┌────────────────────┐
 │ PC IA (optionnel)  │  [ ollama ]  — joignable uniquement depuis le PC Hôte
 └────────────────────┘
```

## Rôle de chaque conteneur Orbe

| Conteneur | Port interne | Rôle |
|---|---|---|
| `waf` | 443 | Point d'entrée unique, filtrage applicatif, répartition entre les deux instances de paiement, liste de blocage dynamique |
| `frontend` | — | Application client « Orbe » (React + Vite + Tailwind), servie en statique |
| `auth-service` | 8001 | Inscription, connexion mot de passe + visage, sessions, émission des JWT |
| `payment-service-a` / `-b` | 8002 | Paiements, remboursements, retraits, demandes d'argent, QR ; deux instances identiques |
| `mariadb` | 3306 | Base `orbe` partagée, un compte à moindre privilège par service |
| `probe` | 8006 | Sonde : une transaction réelle toutes les 10 s à travers le WAF |
| `prometheus` | 9090 | Collecte des métriques (scrape toutes les 5 s) |
| `alertmanager` | 9093 | Route les alertes vers le moteur de remédiation |
| `loki` + `alloy` | 3100 | Centralisation des journaux des conteneurs |
| `grafana` | 3000 | Tableaux de bord, SOC intégré |
| `cadvisor`, `mysqld-exporter` | — | Métriques des conteneurs et de MariaDB |
| `detector-ml` | 8004 | Modèle IsolationForest, publie `anomaly_score` |
| `remediation-engine` | 8003 | Reçoit les alertes, exécute les playbooks Ansible, vérifie la reprise |
| `socket-proxy` | 2375 | Seul accès à l'API Docker, filtré, réservé au moteur |
| `vault` | 8200 | Secrets (clé privée JWT, identifiants DB, jeton du webhook) |
| `dashboard` | 8080 | Supervision React pour le jury, lecture seule |
| `assistant-rag` | 8005 | Assistant opérateur (Ollama + LangChain), lecture seule |

## Réseaux Docker d'Orbe

| Réseau | Interne | Membres | Rôle |
|---|---|---|---|
| `net-front` | non | waf, frontend, probe, remediation-engine | Seul réseau avec un port publié |
| `net-app` | oui | waf, auth, payment-a/b, mariadb, vault, mysqld-exporter, remediation-engine | Trafic métier |
| `net-obs` | oui | Stack d'observabilité et cibles scrapées | Supervision |
| `net-ctrl` | oui | detector-ml, remediation-engine, socket-proxy, vault, dashboard, assistant-rag, prometheus, loki, alertmanager | Plan de contrôle |

Un réseau `internal` n'a pas d'accès à l'extérieur : MariaDB, Vault et le moteur ne sont jamais
joignables depuis le hotspot.

## Ports exposés par Orbe

| Publication | Service | Qui y accède |
|---|---|---|
| `192.168.137.1:443` | waf | Clients, téléphone de démo, PC Attaquant, sonde |
| `127.0.0.1:3000` | grafana | Opérateurs sur le PC Hôte |
| `127.0.0.1:8080` | dashboard | Jury, sur le PC Hôte |
| aucune | base de données, Vault, Prometheus, Alertmanager, moteur de remédiation, socket-proxy, assistant | — |

- Docker Desktop publie sur `0.0.0.0` par défaut : l'IP de publication est **toujours explicite**.
- Le bind sur `192.168.137.1` échoue si le hotspot n'est pas actif : démarrer le hotspot **avant** `docker compose up`.
- Pare-feu Windows : entrant autorisé uniquement sur 443 pour le profil du hotspot.
- Nom de domaine de démo : `orbe.test` → `192.168.137.1` (fichier `hosts`), certificat TLS émis par une CA locale `mkcert`. HTTPS est obligatoire pour que le navigateur autorise la caméra.

## Routage du WAF Orbe

| Chemin public | Destination | Remarque |
|---|---|---|
| `/` | frontend | statique |
| `/api/auth/*` | auth-service:8001 | préfixe réécrit |
| `/api/payments/*` | upstream `payment` (instances a et b) | `max_fails=2 fail_timeout=10s` |
| `= /api/status` (GET) | remediation-engine:8003 `/status/public` | état public de la plateforme |
| autre | `404` | |

## Flux d'un paiement Orbe de bout en bout

1. Le client se connecte : `POST /api/auth/login` (email + mot de passe), puis `POST /api/auth/login/face` (images de la caméra). auth-service renvoie un **JWT RS256** valable 15 minutes, avec `amr: ["pwd","face"]`.
2. Le client paie : `POST /api/payments/pay` avec un en-tête `Idempotency-Key`, le bénéficiaire (email, téléphone ou QR), le montant et une carte de test.
3. Le WAF transmet à l'une des deux instances de payment-service.
4. payment-service vérifie le JWT localement (clé publique), la session (non révoquée) et le corps.
5. La transaction est insérée `pending`, puis le « réseau d'autorisation » fictif répond en 50–150 ms **en gardant la connexion DB ouverte**.
6. Si la carte est acceptée : statut `authorized` et crédit du solde du bénéficiaire **dans la même transaction SQL**, avec deux écritures comptables (débit, crédit).
7. Réponse `201` avec la référence publique `tx_xxxxxxxx`.

Ce maintien de connexion fait du **pool de connexions** (10 par instance) la ressource critique visée par le scénario SC-01.

## Chaîne de détection et de remédiation Orbe

```
attaque ─► waf ─► payment-service (pool saturé, 503)
                       │ métriques            │ journaux
                       ▼                      ▼
                  Prometheus ◄────────────── Loki
                       │  variables (fenêtre 30 s)
                       ▼
                  detector-ml ─► anomaly_score
                       │
                  Prometheus (règle PaymentAnomaly, for: 10s)
                       ▼
                  Alertmanager ─► POST /webhook/alert ─► remediation-engine
                                                              │ ansible-runner
                                                              ▼
                                           contenir (WAF) → rétablir (restart) → vérifier (sonde ×3)
```

L'assistant RAG ne fait **pas** partie de cette chaîne : il ne reçoit pas les alertes et ne peut
déclencher aucune action.

## Budget mémoire du PC Hôte

Les plafonds de tous les conteneurs totalisent environ **5,2 Go**. Sur un PC de 16 Go : Windows ≈ 4 Go,
VM WSL2 ≈ 2 Go, conteneurs ≈ 5,2 Go, Ollama avec un modèle 3B ≈ 3 Go, soit ≈ 14 Go : c'est serré.
Avec 16 Go, utiliser un modèle 3B sur l'hôte ou déporter Ollama sur le PC IA. Fichier `.wslconfig`
conseillé : `memory=12GB`, `processors=6`.
