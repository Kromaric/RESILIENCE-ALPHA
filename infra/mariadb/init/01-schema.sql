-- Orbe — schéma de la base (source de vérité, voir CADRAGE §5)
-- Exécuté une seule fois par l'image officielle MariaDB, au premier démarrage.
-- Toutes les dates sont en UTC.

CREATE DATABASE IF NOT EXISTS orbe CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE orbe;

CREATE TABLE clients (
    id             CHAR(36)     NOT NULL,
    email          VARCHAR(254) NOT NULL,
    phone          VARCHAR(16)  NOT NULL,              -- format E.164 (+33612345678)
    display_name   VARCHAR(80)  NOT NULL,
    password_hash  VARCHAR(255) NOT NULL,              -- argon2id
    balance_cents  BIGINT       NOT NULL DEFAULT 0,
    failed_logins  INT          NOT NULL DEFAULT 0,
    locked_until   DATETIME     NULL,
    qr_token       CHAR(22)     NULL,                  -- jeton opaque du QR « Recevoir »
    is_probe       BOOLEAN      NOT NULL DEFAULT FALSE, -- comptes de la sonde, exclus des vues client
    created_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    CONSTRAINT uq_clients_email UNIQUE (email),
    CONSTRAINT uq_clients_phone UNIQUE (phone),
    CONSTRAINT uq_clients_qr_token UNIQUE (qr_token),
    CONSTRAINT ck_clients_balance CHECK (balance_cents >= 0)
) ENGINE = InnoDB;

CREATE TABLE payout_accounts (
    id          BIGINT      NOT NULL AUTO_INCREMENT,
    client_id   CHAR(36)    NOT NULL,
    label       VARCHAR(80) NOT NULL,
    iban_last4  CHAR(4)     NOT NULL,                  -- IBAN fictif, jamais stocké en entier
    PRIMARY KEY (id),
    CONSTRAINT uq_payout_accounts_client UNIQUE (client_id),
    CONSTRAINT fk_payout_accounts_client FOREIGN KEY (client_id) REFERENCES clients (id)
) ENGINE = InnoDB;

CREATE TABLE api_keys (
    id            BIGINT      NOT NULL AUTO_INCREMENT,
    partner_name  VARCHAR(80) NOT NULL,
    key_hash      CHAR(64)    NOT NULL,                -- SHA-256 hexadécimal de la clé
    scopes        JSON        NOT NULL,
    active        BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at    DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    CONSTRAINT uq_api_keys_hash UNIQUE (key_hash)
) ENGINE = InnoDB;

CREATE TABLE transactions (
    id               CHAR(36)     NOT NULL,
    reference        CHAR(11)     NOT NULL,            -- tx_ + 8 caractères hexadécimaux
    type             ENUM ('payment', 'refund', 'payout') NOT NULL,
    payer_id         CHAR(36)     NULL,
    recipient_id     CHAR(36)     NULL,
    parent_id        CHAR(36)     NULL,                -- remboursement → paiement d'origine
    amount_cents     INT          NOT NULL,
    currency         CHAR(3)      NOT NULL DEFAULT 'EUR',
    description      VARCHAR(140) NULL,
    card_brand       VARCHAR(16)  NULL,
    card_last4       CHAR(4)      NULL,
    status           ENUM ('pending', 'authorized', 'declined', 'failed', 'refunded', 'completed') NOT NULL,
    decline_reason   VARCHAR(32)  NULL,
    idempotency_key  CHAR(36)     NOT NULL,
    request_hash     CHAR(64)     NOT NULL,
    created_at       DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    updated_at       DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
    PRIMARY KEY (id),
    CONSTRAINT uq_transactions_reference UNIQUE (reference),
    CONSTRAINT uq_transactions_idempotency UNIQUE (payer_id, idempotency_key),
    CONSTRAINT uq_transactions_parent UNIQUE (parent_id),  -- un seul remboursement par paiement
    CONSTRAINT ck_transactions_amount CHECK (amount_cents > 0),
    CONSTRAINT fk_transactions_payer FOREIGN KEY (payer_id) REFERENCES clients (id),
    CONSTRAINT fk_transactions_recipient FOREIGN KEY (recipient_id) REFERENCES clients (id),
    CONSTRAINT fk_transactions_parent FOREIGN KEY (parent_id) REFERENCES transactions (id),
    INDEX ix_transactions_payer (payer_id, created_at),
    INDEX ix_transactions_recipient (recipient_id, created_at),
    INDEX ix_transactions_status (status, created_at)
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
