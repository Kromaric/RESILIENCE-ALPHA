# remediation-engine — moteur de remédiation automatique *(cible)*

Port interne **8003**, aucun port publié. FastAPI + worker asynchrone + `ansible-runner`.

## remediation-engine — rôle

Le moteur reçoit les alertes d'Alertmanager, choisit une politique, exécute les playbooks Ansible
correspondants, puis **vérifie** que le service est réellement rétabli avant de clore l'incident.
C'est le seul composant qui agit sur les conteneurs. L'assistant RAG, lui, n'agit jamais.

## remediation-engine — états d'un incident

```
detected ──► containing ──► recovering ──► verifying ──► verified
                 │               │             │
                 └───────────────┴─────────────┴──► escalated ──► (niveau suivant) ──► failed
```

| État | Signification |
|---|---|
| `detected` | Alerte reçue, incident créé |
| `containing` | Confinement en cours (blocage des IP au WAF) |
| `recovering` | Redémarrage ou recréation des instances dégradées |
| `verifying` | Contrôles de reprise en cours (sonde ×3, latence, score, cohérence) |
| `verified` | Service rétabli **et prouvé** : l'incident est clos |
| `escalated` | Un contrôle a échoué : passage au niveau de playbook suivant |
| `failed` | Tous les niveaux ont échoué : intervention humaine nécessaire |

## remediation-engine — politiques (`policies.yml`)

| Type d'incident | Playbooks (par niveau) | Délai entre deux actions sur une cible | Tentatives |
|---|---|---|---|
| `resource_exhaustion` | 1. `pb-contain-and-recover.yml` · 2. `pb-redeploy-clean.yml` | 120 s | 2 |
| `compromise` | `pb-isolate-rotate-redeploy.yml` | 300 s | 1 |

- **Déduplication** : une alerte sur une cible déjà en cours de traitement est rattachée à l'incident existant.
- **Cooldown** : pas de nouvelle action sur une cible pendant le délai, pour éviter les boucles de redémarrage.
- Seuls les playbooks listés sont exécutables, et seulement sur les conteneurs étiquetés `resilience.managed=true`.

## remediation-engine — endpoints

| Endpoint | Appelant | Rôle |
|---|---|---|
| `POST /webhook/alert` | Alertmanager uniquement (jeton `Bearer`) | Réception des alertes ; répond `202` immédiatement |
| `GET /incidents`, `GET /incidents/{id}` | dashboard, lecture | Liste et détail horodaté des incidents |
| `GET /status` | dashboard, lecture | État agrégé des services |
| `GET /status/public` | WAF (`/api/status`) | État minimal pour le frontend : `operational`, `incident`, `remediation`, `recovered` et `payments_enabled` |
| `GET /health`, `GET /metrics` | interne | `remediation_incidents_total{type,status}`, `remediation_duration_seconds` |

## remediation-engine — stockage et traçabilité

- Incidents stockés dans **SQLite** sur un volume dédié, volontairement indépendant de MariaDB, qui peut être la ressource dégradée.
- Chaque action est journalisée dans Loki (`event="action"`, acteur `remediation-engine`) et dans SQLite, avec horodatage.

## remediation-engine — budget temps de la boucle complète

| Phase | Cible |
|---|---|
| Effet visible de l'attaque | ~5 s |
| Détection (fenêtre de 30 s partiellement remplie + `for: 10s`) | ≤ 15 s |
| Alertmanager → moteur | ≤ 5 s |
| Remédiation | ≤ 15 s |
| Vérification | ≤ 5 s |
| **Total** | **≤ 40 s** (critère T6) |

## remediation-engine — sécurité du moteur

Le moteur a des droits élevés sur les conteneurs. Il n'a **pas** le socket Docker monté : il passe par
`socket-proxy` (`DOCKER_HOST=tcp://socket-proxy:2375`), qui n'autorise que les opérations sur les
conteneurs (et les réseaux pour SC-02). Exécution de commandes, images, volumes et secrets sont refusés.
Détails : `securite.md`.
