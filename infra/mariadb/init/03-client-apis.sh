#!/bin/bash
# Orbe — applications clientes à secret (sonde, partenaires de démo), CADRAGE §4.2.
# Comme 02-users.sh : fonctionne « sourcé » ou exécuté. Les clés viennent de secrets
# Docker (ORBE_<NOM>_API_KEY_FILE) ; seule leur empreinte SHA-256 est enregistrée.
# Une clé absente est simplement ignorée (l'application correspondante n'est pas créée).

run_sql() {
	if declare -F docker_process_sql > /dev/null; then
		docker_process_sql "$@"
	else
		MYSQL_PWD="${MARIADB_ROOT_PASSWORD:?MARIADB_ROOT_PASSWORD manquant}" \
			mariadb --protocol=socket -uroot "$@"
	fi
}

key_hash() {
	local file_var="${1}_FILE"
	if [ -n "${!file_var:-}" ]; then
		tr -d '\r\n' < "${!file_var}" | sha256sum | cut -d' ' -f1
	elif [ -n "${!1:-}" ]; then
		printf '%s' "${!1}" | sha256sum | cut -d' ' -f1
	fi
}

PROBE_HASH="$(key_hash ORBE_PROBE_API_KEY)"
if [ -n "$PROBE_HASH" ]; then
	run_sql <<-EOSQL
		INSERT INTO orbe.client_apis (id, name, type, key_hash, scopes)
		VALUES ('orbe-probe', 'Sonde de transaction', 'service', '${PROBE_HASH}', JSON_ARRAY('payments', 'probe'));
	EOSQL
fi

MERCHANT_HASH="$(key_hash ORBE_DEMO_MERCHANT_API_KEY)"
if [ -n "$MERCHANT_HASH" ]; then
	run_sql <<-EOSQL
		INSERT INTO orbe.client_apis (id, name, type, key_hash, scopes)
		VALUES ('demo-merchant-02', 'Boutique Démo', 'partner', '${MERCHANT_HASH}', JSON_ARRAY('payments:read'));
	EOSQL
fi
