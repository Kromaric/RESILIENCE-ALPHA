#!/bin/bash
# Orbe — comptes MariaDB à moindre privilège (voir CADRAGE §5).
# Exécuté par l'entrypoint de l'image officielle MariaDB au premier démarrage, soit
# « sourcé » (fichier non exécutable), soit lancé comme script (fichier exécutable,
# cas d'un montage depuis Windows) : les deux cas sont gérés.
#
# Mots de passe : variable MARIADB_<COMPTE>_PASSWORD_FILE (secret Docker, recommandé)
# ou, à défaut, MARIADB_<COMPTE>_PASSWORD. Jamais dans le dépôt.

secret() {
	local file_var="${1}_FILE"
	if [ -n "${!file_var:-}" ]; then
		cat "${!file_var}"
	else
		printf '%s' "${!1:?$1 ou $file_var manquant}"
	fi
}

run_sql() {
	if declare -F docker_process_sql > /dev/null; then
		docker_process_sql "$@"
	else
		MYSQL_PWD="${MARIADB_ROOT_PASSWORD:?MARIADB_ROOT_PASSWORD manquant}" \
			mariadb --protocol=socket -uroot "$@"
	fi
}

AUTH_SVC_PASSWORD="$(secret MARIADB_AUTH_SVC_PASSWORD)" || exit 1
PAYMENT_SVC_PASSWORD="$(secret MARIADB_PAYMENT_SVC_PASSWORD)" || exit 1
REMEDIATION_RO_PASSWORD="$(secret MARIADB_REMEDIATION_RO_PASSWORD)" || exit 1
EXPORTER_PASSWORD="$(secret MARIADB_EXPORTER_PASSWORD)" || exit 1
BO_RO_PASSWORD="$(secret MARIADB_BO_RO_PASSWORD)" || exit 1

run_sql <<-EOSQL
	CREATE USER IF NOT EXISTS 'auth_svc'@'%' IDENTIFIED BY '${AUTH_SVC_PASSWORD}';
	GRANT SELECT ON orbe.clients TO 'auth_svc'@'%';
	GRANT UPDATE (failed_logins, locked_until, biometric_consent_at) ON orbe.clients TO 'auth_svc'@'%';
	-- inscription : is_probe n'en fait pas partie (une inscription ne crée jamais de compte de sonde)
	GRANT INSERT (id, email, phone, display_name, password_hash) ON orbe.clients TO 'auth_svc'@'%';
	GRANT SELECT ON orbe.client_apis TO 'auth_svc'@'%';
	GRANT SELECT, INSERT, DELETE ON orbe.client_face_templates TO 'auth_svc'@'%';
	GRANT SELECT, INSERT, UPDATE ON orbe.sessions TO 'auth_svc'@'%';
	-- opérateurs du back-office : gestion des habilitations par les administrateurs (rôle admin,
	-- session confirmée par le visage) ; pas de suppression de compte (désactivation seulement)
	GRANT SELECT ON orbe.operators TO 'auth_svc'@'%';
	GRANT INSERT (id, email, display_name, password_hash, role) ON orbe.operators TO 'auth_svc'@'%';
	GRANT UPDATE (failed_logins, locked_until, last_login_at, biometric_consent_at, display_name, role, active, password_hash) ON orbe.operators TO 'auth_svc'@'%';
	GRANT SELECT, INSERT, DELETE ON orbe.operator_face_templates TO 'auth_svc'@'%';
	GRANT SELECT, INSERT, UPDATE ON orbe.operator_sessions TO 'auth_svc'@'%';

	CREATE USER IF NOT EXISTS 'payment_svc'@'%' IDENTIFIED BY '${PAYMENT_SVC_PASSWORD}';
	GRANT SELECT ON orbe.clients TO 'payment_svc'@'%';
	GRANT UPDATE (qr_token) ON orbe.clients TO 'payment_svc'@'%';
	GRANT SELECT (id, client_id, client_api_id, status, factors, expires_at) ON orbe.sessions TO 'payment_svc'@'%';
	GRANT SELECT, INSERT ON orbe.ledger_accounts TO 'payment_svc'@'%';
	GRANT UPDATE (balance_cents) ON orbe.ledger_accounts TO 'payment_svc'@'%';
	GRANT SELECT, INSERT ON orbe.ledger_entries TO 'payment_svc'@'%';
	GRANT SELECT, INSERT, UPDATE ON orbe.transactions TO 'payment_svc'@'%';
	GRANT SELECT, INSERT, UPDATE ON orbe.payment_requests TO 'payment_svc'@'%';
	GRANT SELECT, INSERT, UPDATE, DELETE ON orbe.payout_accounts TO 'payment_svc'@'%';
	GRANT SELECT, INSERT, UPDATE, DELETE ON orbe.contacts TO 'payment_svc'@'%';

	CREATE USER IF NOT EXISTS 'remediation_ro'@'%' IDENTIFIED BY '${REMEDIATION_RO_PASSWORD}';
	GRANT SELECT ON orbe.transactions TO 'remediation_ro'@'%';
	GRANT SELECT ON orbe.ledger_entries TO 'remediation_ro'@'%';
	GRANT SELECT ON orbe.ledger_accounts TO 'remediation_ro'@'%';

	-- bo-api (back-office) : lecture seule, colonnes utiles uniquement. Clients via la vue
	-- masquée bo_clients ; jamais de hachage, de clé d'idempotence ni d'empreinte de requête.
	CREATE USER IF NOT EXISTS 'bo_ro'@'%' IDENTIFIED BY '${BO_RO_PASSWORD}' WITH MAX_USER_CONNECTIONS 5;
	GRANT SELECT ON orbe.bo_clients TO 'bo_ro'@'%';
	GRANT SELECT (id, reference, type, payer_id, recipient_id, parent_id, payout_account_id, amount_cents, currency, description, card_brand, card_last4, status, decline_reason, created_at, updated_at) ON orbe.transactions TO 'bo_ro'@'%';
	GRANT SELECT ON orbe.ledger_entries TO 'bo_ro'@'%';
	GRANT SELECT ON orbe.ledger_accounts TO 'bo_ro'@'%';
	GRANT SELECT (id, reference, requester_id, payer_id, transaction_id, amount_cents, currency, description, status, failure_reason, created_at, expires_at, updated_at) ON orbe.payment_requests TO 'bo_ro'@'%';
	GRANT SELECT (id, client_id, label, iban_last4, is_default, created_at) ON orbe.payout_accounts TO 'bo_ro'@'%';
	GRANT SELECT (id, client_id, status, opened_at, expires_at) ON orbe.sessions TO 'bo_ro'@'%';

	CREATE USER IF NOT EXISTS 'exporter'@'%' IDENTIFIED BY '${EXPORTER_PASSWORD}' WITH MAX_USER_CONNECTIONS 3;
	GRANT PROCESS, REPLICATION CLIENT, SLAVE MONITOR ON *.* TO 'exporter'@'%';

	FLUSH PRIVILEGES;
EOSQL
