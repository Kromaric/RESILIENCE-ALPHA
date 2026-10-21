# Runbook — déploiement, vérification et remise à zéro d'Orbe

## Prérequis du PC Hôte

- Windows 10 ou 11, droits d'administration, virtualisation activée.
- Docker Desktop avec WSL2. Minimum : 4 cœurs, 16 Go de RAM, 50 Go libres sur SSD (32 Go conseillés).
- `.wslconfig` : `memory=12GB`, `processors=6` (à ajuster).
- **Point d'accès mobile Windows actif** (`RESILIENCE-G<n>`, PC Hôte en `192.168.137.1`) **avant** tout démarrage : le WAF se lie à cette adresse.
- CA `mkcert` installée sur les appareils de démo ; `orbe.test` → `192.168.137.1` dans leur fichier `hosts`.

## Déploiement complet *(cible)*

Point d'entrée Windows : `scripts/deploy.ps1`, qui lance le playbook Ansible `deploy.yml` dans un conteneur :

1. vérification des prérequis (hotspot actif, ressources WSL2) ;
2. génération du certificat TLS ;
3. génération du `.env` ;
4. amorçage de Vault (`infra/vault/bootstrap.sh` : init, unseal, KV v2, politiques, AppRoles) ;
5. `docker compose up` ;
6. attente des healthchecks ;
7. chargement des données de démo.

## Démarrage en développement (état actuel)

```bash
services/auth-service/.venv/Scripts/python scripts/init_dev_secrets.py
docker compose -f docker-compose.dev.yml up -d --build
```

auth-service : `http://localhost:8001/docs` · payment-service : `http://localhost:8002/docs`.
Jeton de test : `scripts/dev_token.py camille@orbe.test` (moteur de visage simulé en local).
Repartir de zéro : `docker compose -f docker-compose.dev.yml down -v`.

## Tests de fumée — `verify.yml`

`scripts/verify.ps1` vérifie : santé de tous les services, une transaction de bout en bout, toutes les
cibles Prometheus à `up`, et la réception des journaux par Loki. À lancer après chaque déploiement et avant
chaque répétition.

## Remise à zéro entre deux répétitions — `reset.yml`

`scripts/reset.ps1` :

- vide la liste de blocage du WAF (sinon l'IP du PC Attaquant reste bloquée 15 minutes) ;
- archive les incidents du moteur (le cooldown de 120 s ne bloque plus une nouvelle action) ;
- relance les services pour revenir à l'état nominal.

## Sauvegarde et restauration — `backup.yml` / `restore.yml`

Dump MariaDB toutes les 5 minutes vers un volume dédié, rétention 24 h. `restore.yml` recharge un dump.
Non nécessaire pour SC-01.

## Avant le passage devant le jury

1. Hotspot actif, PC Attaquant et téléphone connectés, `orbe.test` résolu sur chaque appareil.
2. `deploy.ps1` puis `verify.ps1` au vert.
3. Modèle Ollama préchargé (`keep_alive` + une question de chauffe) pour éviter 20 à 30 s d'attente au premier appel.
4. Visages de l'équipe enregistrés, éclairage correct.
5. `reset.ps1` juste avant le passage.
6. Dashboard (`127.0.0.1:8080`) et Grafana (`127.0.0.1:3000`) ouverts.
7. Script SC-01 prêt sur le PC Attaquant, paramètres figés.
