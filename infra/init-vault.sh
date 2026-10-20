#!/bin/sh
set -e

echo "⏳ Attente du démarrage de Vault..."
until nc -z vault 8200; do
  sleep 1
done
echo "🚀 Vault est en ligne, configuration en cours..."

# Export de l'adresse et du token root (configuré par VAULT_DEV_ROOT_TOKEN_ID: "root")
export VAULT_ADDR='http://vault:8200'
export VAULT_TOKEN='root'

# 1. Activer le Database Secrets Engine (s'il ne l'est pas déjà)
vault secrets list | grep -q 'database/' || vault secrets enable -path=database database

# 2. Configurer la connexion avec MariaDB
vault write database/config/mariadb-db \
    plugin_name="mysql-database-plugin" \
    connection_url="{{username}}:{{password}}@tcp(mariadb:3306)/" \
    allowed_roles="oorbe-app-role" \
    username="root" \
    password="admin"

# 3. Créer le rôle pour générer les identifiants dynamiques
vault write database/roles/oorbe-app-role \
    db_name=mariadb-db \
    creation_statements="CREATE USER '{{name}}'@'%' IDENTIFIED BY '{{password}}'; GRANT ALL PRIVILEGES ON oorbe_db.* TO '{{name}}'@'%';" \
    default_time_to_live="1h" \
    max_time_to_live="24h"

echo "✅ Vault est configuré et lié à MariaDB avec succès !"
