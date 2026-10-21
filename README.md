# PROJECT RESILIENCE-ALPHA — Orbe

Démonstrateur de cyber-résilience (workshop EPSI BAC+5, octobre 2026) : une plateforme de paiement
fictive entre particuliers, **Orbe**, capable de détecter une attaque et de se rétablir seule.

- Cadrage technique : [`CADRAGE.md`](CADRAGE.md)
- Modèle de données : [`docs/mcd.md`](docs/mcd.md)
- Documentation des API (Swagger) : [`docs/api/`](docs/api/)

Toutes les données sont fictives. Aucune donnée bancaire ou personnelle réelle.

## Lancer en local (auth-service + payment-service)

Pré-requis : Docker Desktop (WSL2) et Python 3.12+.

**1. Environnement Python** (sert aux scripts ci-dessous et aux tests) :

```bash
py -3.13 -m venv services/auth-service/.venv
```

```bash
services/auth-service/.venv/Scripts/python -m pip install -e "services/auth-service[dev]"
```

**2. Secrets locaux** : mots de passe MariaDB, clés JWT et clé de la sonde, dans `secrets/` (ignoré par Git).

```bash
services/auth-service/.venv/Scripts/python scripts/init_dev_secrets.py
```

**3. Démarrage** : MariaDB, auth-service, payment-service.

```bash
docker compose -f docker-compose.dev.yml up -d --build
```

| Service | Adresse |
|---|---|
| auth-service (Swagger) | http://localhost:8001/docs |
| payment-service (Swagger) | http://localhost:8002/docs |
| MariaDB (client SQL) | `localhost:3307`, base `orbe` ; mot de passe root dans `secrets/db_root_password` |

Les images sont construites à partir de `dockerfiles/` (contexte : racine du dépôt) :
`Dockerfile-auth`, `Dockerfile-payment` et `Dockerfile-mariadb` (schéma, comptes et configuration
intégrés). Ce sont les mêmes que dans la pile complète `infra/docker-compose.yml`.

### Comptes de démo

Mot de passe commun : `demo-password`.

| Compte | Rôle |
|---|---|
| `camille@orbe.test` · `+33612345678` | client |
| `lea@orbe.test` · `+33612345677` | client |
| `hugo@orbe.test` · `+33612345676` | client |
| `probe@orbe.test` → `probe-recipient@orbe.test` | comptes de la sonde (transaction de test) |

### Créer son propre compte

Dans http://localhost:8001/docs, `POST /register` (exemple pré-rempli), puis :

```bash
services/auth-service/.venv/Scripts/python scripts/dev_token.py nathan@orbe.test --password correct-cheval-batterie
```

Si la base existait avant l'ajout de l'inscription, appliquez le nouveau droit sans perdre vos données :

```bash
docker compose -f docker-compose.dev.yml exec mariadb sh -c 'MYSQL_PWD="$(cat /run/secrets/db_root_password)" mariadb -uroot -e "GRANT INSERT (id, email, phone, display_name, password_hash) ON orbe.clients TO auth_svc"'
```

### Tester dans Swagger

Déplacer de l'argent exige une session confirmée par **reconnaissance faciale**. En local, auth-service
utilise un moteur de visage simulé (`AUTH_FACE_ENGINE=fake`) : ce script enregistre un visage fictif
au premier appel, répond au défi de vivacité et affiche un jeton valable 15 minutes :

```bash
services/auth-service/.venv/Scripts/python scripts/dev_token.py camille@orbe.test
```

Dans Swagger (http://localhost:8002/docs), cliquez sur **Authorize**, collez le jeton, puis
essayez `POST /pay` : l'exemple pré-rempli envoie 12,50 € au téléphone de Léa avec la carte de test
`4242 4242 4242 4242`. L'en-tête `Idempotency-Key` attend un UUID (par exemple généré sur
https://www.uuidgenerator.net ou avec `python -c "import uuid; print(uuid.uuid4())"`).

Autres essais utiles :

- jeton de Léa (`scripts/dev_token.py lea@orbe.test`) → `GET /account` : le solde est crédité ;
- cartes refusées : `4000 0000 0000 0002`, `…0069` (expirée), `…9995` (fonds insuffisants) ;
- une connexion par mot de passe seul (`POST /login` dans http://localhost:8001/docs) donne un jeton
  refusé pour payer (`403 second_factor_required`) ;
- un autre visage est refusé : `scripts/dev_token.py camille@orbe.test --face intrus`
  (`401 second_factor_failed`, compte bloqué après 5 échecs) ;
- jeton de la sonde : `scripts/dev_token.py probe@orbe.test --probe`.

Pour essayer le vrai modèle (InsightFace, déjà dans l'image), passez `AUTH_FACE_ENGINE: insightface`
et `mem_limit: 1g` dans `docker-compose.dev.yml` : il faut alors de vraies photos de la caméra.

### Arrêter, repartir de zéro

```bash
docker compose -f docker-compose.dev.yml down
```

Pour effacer aussi la base (les données de démo sont rechargées au prochain démarrage) :

```bash
docker compose -f docker-compose.dev.yml down -v
```

Après la mise à jour « reconnaissance faciale », un `down -v` est nécessaire (schéma modifié), et
`scripts/init_dev_secrets.py` doit être relancé (nouveau secret `face_embedding_key`).

### Tests automatisés

```bash
services/auth-service/.venv/Scripts/python -m pytest services/auth-service
```

Les tests de payment-service se lancent depuis leur propre environnement (voir
[`services/payment-service/README.md`](services/payment-service/README.md)).
