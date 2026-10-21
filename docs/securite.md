# Sécurité technique d'Orbe

## Exposition réseau

Seul le WAF est publié sur le hotspot (`192.168.137.1:443`). Grafana et le dashboard sont liés à
`127.0.0.1`. La base de données, Vault, Prometheus, Alertmanager, le moteur de remédiation, le socket-proxy
et l'assistant ne sont jamais publiés. Les réseaux `net-app`, `net-obs` et `net-ctrl` sont `internal`.
Le pare-feu Windows n'autorise en entrée que le port 443 sur le profil du hotspot.

## Durcissement des conteneurs

Configuration par défaut de chaque service :

```yaml
user: "10001:10001"          # pas de root
read_only: true              # système de fichiers en lecture seule (+ tmpfs /tmp)
cap_drop: [ALL]              # aucune capacité Linux
security_opt: [no-new-privileges:true]
pids_limit: 128
restart: unless-stopped
healthcheck: { ... }
```

Exceptions documentées au cas par cas : cAdvisor, collecteur de journaux, MariaDB, Vault (`IPC_LOCK`).
Images épinglées par tag précis, jamais `:latest`.

## Sécurité du moteur de remédiation (composant à privilèges)

Le moteur peut arrêter et redémarrer des conteneurs : c'est le composant le plus sensible. Le sujet
demande explicitement qu'il n'introduise pas une interface d'administration accessible à n'importe quel
composant.

| Mesure | Détail |
|---|---|
| Pas de socket Docker monté | Accès via `socket-proxy` (tecnativa), sur un réseau interne joignable par le seul moteur |
| Proxy restreint | `CONTAINERS=1`, `POST=1`, `NETWORKS=1` (pour SC-02) ; `EXEC`, `IMAGES`, `VOLUMES`, `BUILD`, `SECRETS`, `SWARM` à 0 |
| Webhook authentifié | Jeton porteur comparé à temps constant, stocké dans Vault |
| Surface réduite | Aucun port publié ; le dashboard ne relaie que des `GET` en lecture |
| Actions bornées | Seuls les playbooks listés dans `policies.yml`, seulement sur les conteneurs étiquetés `resilience.managed=true` |
| Traçabilité | Chaque action journalisée (Loki + SQLite) |

## Pourquoi l'assistant RAG n'a aucun privilège

L'assistant traite du texte venant en partie de sources non fiables (journaux contenant des charges
d'attaque). Lui donner un accès au moteur ou à Docker transformerait une injection de prompt en action
sur le système. Il est donc en lecture seule sur le corpus `docs/`, sans outil actif, et séparé de
l'automate de remédiation, comme le demande le sujet.

## Gestion des secrets — Vault et SOPS

| Élément | Choix |
|---|---|
| Mode | Serveur (pas `-dev`), stockage `file` sur volume, TLS interne |
| Amorçage | `infra/vault/bootstrap.sh` appelé par Ansible : init, unseal, KV v2, politiques, AppRoles |
| Clés d'unseal et token root | Chiffrés avec **SOPS + age** dans `infra/vault/bootstrap.enc.yaml` ; la clé age reste hors dépôt (KeeWeb) |
| Accès des services | AppRole par service, `role_id` / `secret_id` remis par secrets Docker |
| Chemins | `kv/auth` (clé privée JWT), `kv/payment` (identifiants DB), `kv/remediation` (jeton du webhook, identifiants `remediation_ro`), `kv/probe` (compte de test) |
| Politiques | Lecture seule, un chemin par service ; seul le moteur peut écrire sur `kv/auth` et `kv/payment` (rotation SC-02) |

Aucun secret en clair dans le dépôt : `secrets/` est ignoré par Git, et gitleaks le vérifie en CI.

## Authentification et sessions

- Mots de passe hachés en **argon2id**, 12 caractères minimum, mots de passe courants refusés.
- Double facteur mot de passe + visage (DSP2 : deux facteurs parmi trois).
- JWT RS256 de 15 minutes, sessions révocables, blocage après 5 échecs, limitation par IP.
- Clés d'API des applications clientes stockées sous forme d'empreinte SHA-256.

## Données biométriques (RGPD article 9)

Images traitées en mémoire puis oubliées, jamais journalisées. Seuls 3 à 5 gabarits par client, chiffrés
**AES-256-GCM** et liés à leur propriétaire (un gabarit copié sur un autre compte ne se déchiffre pas).
Consentement explicite horodaté, effacement à la demande (`DELETE /face`). Démo : comptes fictifs, visages
de volontaires de l'équipe.

## Données de paiement

Uniquement des cartes de test. Seuls la marque et les 4 derniers chiffres sont stockés. Numéro complet,
CVC et titulaire ne sont jamais stockés ni journalisés.

## Contrôles en CI

gitleaks (secrets), Trivy (images et dépendances), ruff et bandit (Python), eslint (front), ansible-lint,
`docker compose config`. Pas de déploiement depuis la CI : un runner auto-hébergé exécuterait du code
externe sur la machine la plus sensible.

## Périmètre des actions offensives

Les scénarios d'attaque partent uniquement du PC Attaquant et visent uniquement le WAF de l'équipe.
Réseaux du campus, autres groupes et services Internet sont hors périmètre.
