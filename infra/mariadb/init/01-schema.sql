-- Orbe — schéma de la base, v2 (source de vérité, voir docs/mcd.md et CADRAGE §5)
-- Exécuté une seule fois par l'image officielle MariaDB, au premier démarrage.
-- Toutes les dates sont en UTC. Base partagée par auth-service et payment-service.

CREATE DATABASE IF NOT EXISTS orbe CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE orbe;

-- --- Domaine commun ---------------------------------------------------------------

CREATE TABLE clients (
    id             CHAR(36)     NOT NULL,
    email          VARCHAR(254) NOT NULL,
    phone          VARCHAR(16)  NOT NULL,              -- format E.164 (+33612345678)
    display_name   VARCHAR(80)  NOT NULL,
    password_hash  VARCHAR(255) NOT NULL,              -- argon2id
    failed_logins  INT          NOT NULL DEFAULT 0,
    locked_until   DATETIME     NULL,
    qr_token       CHAR(22)     NULL,                  -- jeton opaque du QR « Recevoir »
    is_probe       BOOLEAN      NOT NULL DEFAULT FALSE, -- comptes de la sonde, exclus des vues client
    created_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    CONSTRAINT uq_clients_email UNIQUE (email),
    CONSTRAINT uq_clients_phone UNIQUE (phone),
    CONSTRAINT uq_clients_qr_token UNIQUE (qr_token)
) ENGINE = InnoDB;

-- --- Authentification (auth-service) ------------------------------------------------

CREATE TABLE client_apis (
    id          VARCHAR(40)  NOT NULL,                 -- ex. orbe-web, orbe-probe, demo-merchant-02
    name        VARCHAR(80)  NOT NULL,
    type        ENUM ('application', 'partner', 'service') NOT NULL,
    key_hash    CHAR(64)     NULL,                     -- SHA-256 de la clé ; NULL pour l'appli web publique
    scopes      JSON         NOT NULL,
    active      BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    CONSTRAINT uq_client_apis_key UNIQUE (key_hash)
) ENGINE = InnoDB;

CREATE TABLE passkeys (
    id             CHAR(36)     NOT NULL,
    client_id      CHAR(36)     NOT NULL,
    credential_id  VARCHAR(512) NOT NULL,              -- base64url, fourni par l'appareil
    public_key     TEXT         NOT NULL,              -- clé publique COSE, base64url
    sign_count     BIGINT       NOT NULL DEFAULT 0,
    device_name    VARCHAR(80)  NOT NULL,
    created_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_used_at   DATETIME     NULL,
    PRIMARY KEY (id),
    CONSTRAINT uq_passkeys_credential UNIQUE (credential_id),
    CONSTRAINT fk_passkeys_client FOREIGN KEY (client_id) REFERENCES clients (id),
    INDEX ix_passkeys_client (client_id)
) ENGINE = InnoDB;

CREATE TABLE sessions (
    id                 CHAR(36)     NOT NULL,          -- = jti du JWT
    client_id          CHAR(36)     NOT NULL,
    client_api_id      VARCHAR(40)  NOT NULL,
    passkey_id         CHAR(36)     NULL,              -- passkey qui a confirmé la session
    status             ENUM ('pending_2fa', 'active', 'revoked', 'expired') NOT NULL,
    factors            VARCHAR(40)  NOT NULL,          -- « pwd » ou « pwd,passkey »
    webauthn_challenge VARCHAR(128) NULL,              -- défi en cours (connexion ou enregistrement)
    challenge_purpose  ENUM ('login', 'register') NULL,
    ip_address         VARCHAR(45)  NULL,
    opened_at          DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    expires_at         DATETIME(3)  NOT NULL,
    revoked_at         DATETIME(3)  NULL,
    revocation_reason  VARCHAR(64)  NULL,
    PRIMARY KEY (id),
    CONSTRAINT fk_sessions_client FOREIGN KEY (client_id) REFERENCES clients (id),
    CONSTRAINT fk_sessions_client_api FOREIGN KEY (client_api_id) REFERENCES client_apis (id),
    CONSTRAINT fk_sessions_passkey FOREIGN KEY (passkey_id) REFERENCES passkeys (id) ON DELETE SET NULL,
    INDEX ix_sessions_client (client_id, status)
) ENGINE = InnoDB;

-- --- Paiements (payment-service) ----------------------------------------------------

CREATE TABLE ledger_accounts (
    id             CHAR(36)     NOT NULL,
    type           ENUM ('client', 'counterpart') NOT NULL,
    code           VARCHAR(32)  NULL,                  -- comptes de contrepartie : card_settlement, payouts
    label          VARCHAR(80)  NOT NULL,
    balance_cents  BIGINT       NOT NULL DEFAULT 0,    -- dérivé : Σ crédits − Σ débits
    client_id      CHAR(36)     NULL,
    created_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    CONSTRAINT uq_ledger_accounts_code UNIQUE (code),
    CONSTRAINT uq_ledger_accounts_client UNIQUE (client_id),
    CONSTRAINT fk_ledger_accounts_client FOREIGN KEY (client_id) REFERENCES clients (id),
    CONSTRAINT ck_ledger_accounts_owner CHECK (
        (type = 'client' AND client_id IS NOT NULL AND balance_cents >= 0)
        OR (type = 'counterpart' AND client_id IS NULL AND code IS NOT NULL)
    )
) ENGINE = InnoDB;

CREATE TABLE payout_accounts (
    id          CHAR(36)    NOT NULL,
    client_id   CHAR(36)    NOT NULL,
    label       VARCHAR(80) NOT NULL,
    iban_last4  CHAR(4)     NOT NULL,                  -- IBAN fictif, jamais stocké en entier
    is_default  BOOLEAN     NOT NULL DEFAULT FALSE,
    created_at  DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    CONSTRAINT fk_payout_accounts_client FOREIGN KEY (client_id) REFERENCES clients (id),
    INDEX ix_payout_accounts_client (client_id)
) ENGINE = InnoDB;

CREATE TABLE contacts (
    owner_id    CHAR(36)    NOT NULL,
    contact_id  CHAR(36)    NOT NULL,
    alias       VARCHAR(80) NULL,
    added_at    DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (owner_id, contact_id),
    CONSTRAINT ck_contacts_not_self CHECK (owner_id <> contact_id),
    CONSTRAINT fk_contacts_owner FOREIGN KEY (owner_id) REFERENCES clients (id),
    CONSTRAINT fk_contacts_contact FOREIGN KEY (contact_id) REFERENCES clients (id)
) ENGINE = InnoDB;

CREATE TABLE transactions (
    id                 CHAR(36)     NOT NULL,
    reference          CHAR(11)     NOT NULL,          -- tx_ + 8 caractères hexadécimaux
    type               ENUM ('payment', 'refund', 'payout') NOT NULL,
    session_id         CHAR(36)     NOT NULL,          -- session qui a initié l'opération
    payer_id           CHAR(36)     NOT NULL,          -- émetteur
    recipient_id       CHAR(36)     NULL,              -- bénéficiaire (aucun pour un retrait)
    parent_id          CHAR(36)     NULL,              -- remboursement → paiement d'origine
    payout_account_id  CHAR(36)     NULL,              -- retrait → compte lié destinataire
    amount_cents       INT          NOT NULL,
    currency           CHAR(3)      NOT NULL DEFAULT 'EUR',
    description        VARCHAR(140) NULL,
    card_brand         VARCHAR(16)  NULL,
    card_last4         CHAR(4)      NULL,
    status             ENUM ('pending', 'authorized', 'declined', 'failed', 'refunded', 'completed') NOT NULL,
    decline_reason     VARCHAR(32)  NULL,
    idempotency_key    CHAR(36)     NOT NULL,
    request_hash       CHAR(64)     NOT NULL,
    created_at         DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    updated_at         DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
    PRIMARY KEY (id),
    CONSTRAINT uq_transactions_reference UNIQUE (reference),
    CONSTRAINT uq_transactions_idempotency UNIQUE (payer_id, idempotency_key),
    CONSTRAINT uq_transactions_parent UNIQUE (parent_id),  -- un seul remboursement par paiement
    CONSTRAINT ck_transactions_amount CHECK (amount_cents > 0),
    CONSTRAINT fk_transactions_session FOREIGN KEY (session_id) REFERENCES sessions (id),
    CONSTRAINT fk_transactions_payer FOREIGN KEY (payer_id) REFERENCES clients (id),
    CONSTRAINT fk_transactions_recipient FOREIGN KEY (recipient_id) REFERENCES clients (id),
    CONSTRAINT fk_transactions_parent FOREIGN KEY (parent_id) REFERENCES transactions (id),
    CONSTRAINT fk_transactions_payout_account FOREIGN KEY (payout_account_id) REFERENCES payout_accounts (id) ON DELETE SET NULL,
    INDEX ix_transactions_payer (payer_id, created_at),
    INDEX ix_transactions_recipient (recipient_id, created_at),
    INDEX ix_transactions_status (status, created_at)
) ENGINE = InnoDB;

CREATE TABLE ledger_entries (
    id              BIGINT      NOT NULL AUTO_INCREMENT,
    transaction_id  CHAR(36)    NOT NULL,
    account_id      CHAR(36)    NOT NULL,
    direction       ENUM ('debit', 'credit') NOT NULL,
    amount_cents    INT         NOT NULL,
    created_at      DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    PRIMARY KEY (id),
    CONSTRAINT ck_ledger_entries_amount CHECK (amount_cents > 0),
    CONSTRAINT fk_ledger_entries_transaction FOREIGN KEY (transaction_id) REFERENCES transactions (id),
    CONSTRAINT fk_ledger_entries_account FOREIGN KEY (account_id) REFERENCES ledger_accounts (id),
    INDEX ix_ledger_entries_transaction (transaction_id),
    INDEX ix_ledger_entries_account (account_id)
) ENGINE = InnoDB;

CREATE TABLE payment_requests (
    id               CHAR(36)     NOT NULL,
    reference        CHAR(11)     NOT NULL,            -- rq_ + 8 caractères hexadécimaux
    requester_id     CHAR(36)     NOT NULL,            -- client qui demande l'argent
    payer_id         CHAR(36)     NULL,                -- NULL si le payeur désigné est introuvable
    transaction_id   CHAR(36)     NULL,                -- paiement qui a réglé la demande
    amount_cents     INT          NOT NULL,
    currency         CHAR(3)      NOT NULL DEFAULT 'EUR',
    description      VARCHAR(140) NULL,
    status           ENUM ('pending', 'paid', 'declined', 'cancelled', 'expired', 'failed') NOT NULL,
    failure_reason   VARCHAR(32)  NULL,
    idempotency_key  CHAR(36)     NOT NULL,
    request_hash     CHAR(64)     NOT NULL,
    created_at       DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    expires_at       DATETIME(3)  NOT NULL,
    updated_at       DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
    PRIMARY KEY (id),
    CONSTRAINT uq_payment_requests_reference UNIQUE (reference),
    CONSTRAINT uq_payment_requests_idempotency UNIQUE (requester_id, idempotency_key),
    CONSTRAINT uq_payment_requests_transaction UNIQUE (transaction_id),
    CONSTRAINT ck_payment_requests_amount CHECK (amount_cents > 0),
    CONSTRAINT fk_payment_requests_requester FOREIGN KEY (requester_id) REFERENCES clients (id),
    CONSTRAINT fk_payment_requests_payer FOREIGN KEY (payer_id) REFERENCES clients (id),
    CONSTRAINT fk_payment_requests_transaction FOREIGN KEY (transaction_id) REFERENCES transactions (id),
    INDEX ix_payment_requests_requester (requester_id, status, created_at),
    INDEX ix_payment_requests_payer (payer_id, status, created_at)
) ENGINE = InnoDB;

-- --- Données de référence -------------------------------------------------------------

-- Comptes de contrepartie : l'extérieur d'Orbe (réseau carte, banques)
INSERT INTO ledger_accounts (id, type, code, label) VALUES
    ('00000000-0000-0000-0000-00000000c001', 'counterpart', 'card_settlement', 'Encaissements carte'),
    ('00000000-0000-0000-0000-00000000c002', 'counterpart', 'payouts', 'Retraits');

-- Application web publique (pas de secret possible dans un navigateur)
INSERT INTO client_apis (id, name, type, key_hash, scopes) VALUES
    ('orbe-web', 'Application Orbe (web)', 'application', NULL, JSON_ARRAY('payments'));
