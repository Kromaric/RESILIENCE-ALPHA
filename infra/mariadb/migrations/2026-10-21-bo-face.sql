-- Migration d'une base existante : connexion au back-office par reconnaissance faciale.
-- Une base neuve n'en a pas besoin (01-schema.sql et 02-users.sh sont déjà à jour).
-- À lancer avec le compte root, par exemple :
--   docker compose -f docker-compose.dev.yml exec -T mariadb sh -c \
--     'MYSQL_PWD="$(cat /run/secrets/db_root_password)" mariadb -uroot orbe' \
--     < infra/mariadb/migrations/2026-10-21-bo-face.sql

USE orbe;

ALTER TABLE operators
    MODIFY role ENUM ('viewer', 'operator', 'admin') NOT NULL DEFAULT 'viewer',
    ADD COLUMN IF NOT EXISTS biometric_consent_at DATETIME NULL AFTER last_login_at;

CREATE TABLE IF NOT EXISTS operator_face_templates (
    id             CHAR(36)      NOT NULL,
    operator_id    CHAR(36)      NOT NULL,
    embedding_ct   VARCHAR(4096) CHARACTER SET ascii NOT NULL,
    embedding_dim  SMALLINT      NOT NULL DEFAULT 512,
    model          VARCHAR(40)   NOT NULL,
    quality_score  DECIMAL(4, 3) NOT NULL,
    captured_at    DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    CONSTRAINT ck_operator_face_templates_ct CHECK (
        embedding_ct LIKE 'local:v%:%' OR embedding_ct LIKE 'vault:v%:%'
    ),
    CONSTRAINT fk_operator_face_templates_operator FOREIGN KEY (operator_id) REFERENCES operators (id) ON DELETE CASCADE,
    INDEX ix_operator_face_templates_operator (operator_id)
) ENGINE = InnoDB;

ALTER TABLE operator_sessions
    MODIFY operator_id CHAR(36) NULL,
    MODIFY status ENUM ('pending_face', 'pending_password', 'enrollment', 'active', 'revoked', 'expired') NOT NULL,
    ADD COLUMN IF NOT EXISTS factors VARCHAR(40) NOT NULL DEFAULT '' AFTER status,
    ADD COLUMN IF NOT EXISTS challenge VARCHAR(16) NULL AFTER factors,
    ADD COLUMN IF NOT EXISTS face_template_id CHAR(36) NULL AFTER challenge,
    ADD COLUMN IF NOT EXISTS face_score DECIMAL(4, 3) NULL AFTER face_template_id,
    ADD CONSTRAINT fk_operator_sessions_face_template FOREIGN KEY IF NOT EXISTS (face_template_id)
        REFERENCES operator_face_templates (id) ON DELETE SET NULL;

-- Sessions ouvertes avec le mot de passe seul (ancienne connexion) : fermées
UPDATE operator_sessions SET status = 'revoked', revoked_at = UTC_TIMESTAMP(3),
    revocation_reason = 'migration_face_required'
WHERE status = 'active';

GRANT INSERT (id, email, display_name, password_hash, role) ON orbe.operators TO 'auth_svc'@'%';
GRANT UPDATE (failed_logins, locked_until, last_login_at, biometric_consent_at, display_name, role, active, password_hash) ON orbe.operators TO 'auth_svc'@'%';
GRANT SELECT, INSERT, DELETE ON orbe.operator_face_templates TO 'auth_svc'@'%';

-- Administrateur de démonstration (base de développement seulement, mot de passe demo-password)
INSERT IGNORE INTO operators (id, email, display_name, password_hash, role)
SELECT 'aaaaaaaa-0000-0000-0000-000000000003', 'admin@orbe.test', 'Administrateur', password_hash, 'admin'
FROM operators WHERE email = 'ops@orbe.test';

FLUSH PRIVILEGES;
