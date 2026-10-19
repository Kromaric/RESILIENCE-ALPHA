#!/bin/bash
# Orbe — comptes MariaDB à moindre privilège (voir CADRAGE §5).
# Ce script est « sourcé » par l'entrypoint de l'image officielle MariaDB au premier
# démarrage : la fonction docker_process_sql est donc disponible.
# Les mots de passe viennent de l'environnement du conteneur (jamais du dépôt).

: "${MARIADB_AUTH_SVC_PASSWORD:?MARIADB_AUTH_SVC_PASSWORD manquant}"
: "${MARIADB_PAYMENT_SVC_PASSWORD:?MARIADB_PAYMENT_SVC_PASSWORD manquant}"
: "${MARIADB_REMEDIATION_RO_PASSWORD:?MARIADB_REMEDIATION_RO_PASSWORD manquant}"
: "${MARIADB_EXPORTER_PASSWORD:?MARIADB_EXPORTER_PASSWORD manquant}"

docker_process_sql <<-EOSQL
	CREATE USER IF NOT EXISTS 'auth_svc'@'%' IDENTIFIED BY '${MARIADB_AUTH_SVC_PASSWORD}';
	GRANT SELECT ON orbe.clients TO 'auth_svc'@'%';
	GRANT UPDATE (failed_logins, locked_until) ON orbe.clients TO 'auth_svc'@'%';
	GRANT SELECT ON orbe.api_keys TO 'auth_svc'@'%';

	CREATE USER IF NOT EXISTS 'payment_svc'@'%' IDENTIFIED BY '${MARIADB_PAYMENT_SVC_PASSWORD}';
	GRANT SELECT ON orbe.clients TO 'payment_svc'@'%';
	GRANT UPDATE (balance_cents) ON orbe.clients TO 'payment_svc'@'%';
	GRANT SELECT ON orbe.payout_accounts TO 'payment_svc'@'%';
	GRANT SELECT, INSERT, UPDATE ON orbe.transactions TO 'payment_svc'@'%';

	CREATE USER IF NOT EXISTS 'remediation_ro'@'%' IDENTIFIED BY '${MARIADB_REMEDIATION_RO_PASSWORD}';
	GRANT SELECT ON orbe.transactions TO 'remediation_ro'@'%';
	GRANT SELECT (id, balance_cents, is_probe) ON orbe.clients TO 'remediation_ro'@'%';

	CREATE USER IF NOT EXISTS 'exporter'@'%' IDENTIFIED BY '${MARIADB_EXPORTER_PASSWORD}' WITH MAX_USER_CONNECTIONS 3;
	GRANT PROCESS, REPLICATION CLIENT, SLAVE MONITOR ON *.* TO 'exporter'@'%';

	FLUSH PRIVILEGES;
EOSQL
