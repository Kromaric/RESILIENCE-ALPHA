-- Orbe — données de démonstration (environnement de développement uniquement)
-- Monté par docker-compose.dev.yml, jamais en démonstration jury sans relecture.
-- Données 100 % fictives. Mot de passe de tous les comptes : demo-password

USE orbe;

SET @pwd = '$argon2id$v=19$m=19456,t=2,p=1$th7myHAixH64505QQfPjZg$quTteIYWHvpx+xoqBLxF4OBbONdinapmWSRWvQ4WLXU';

INSERT INTO clients (id, email, phone, display_name, password_hash, is_probe) VALUES
    ('11111111-1111-1111-1111-111111111111', 'camille@orbe.test', '+33612345678', 'Camille Test', @pwd, FALSE),
    ('22222222-2222-2222-2222-222222222222', 'lea@orbe.test',     '+33612345677', 'Léa Martin',   @pwd, FALSE),
    ('33333333-3333-3333-3333-333333333333', 'hugo@orbe.test',    '+33612345676', 'Hugo Bernard', @pwd, FALSE),
    -- comptes de la sonde (transaction de test), invisibles des autres clients
    ('99999999-9999-9999-9999-999999999901', 'probe@orbe.test',           '+33600000001', 'Sonde payeur',       @pwd, TRUE),
    ('99999999-9999-9999-9999-999999999902', 'probe-recipient@orbe.test', '+33600000002', 'Sonde bénéficiaire', @pwd, TRUE);

-- opérateurs du back-office (dashboard), même mot de passe de démo
INSERT INTO operators (id, email, display_name, password_hash, role) VALUES
    ('aaaaaaaa-0000-0000-0000-000000000001', 'ops@orbe.test',    'Opérateur SOC',   @pwd, 'operator'),
    ('aaaaaaaa-0000-0000-0000-000000000002', 'viewer@orbe.test', 'Lecture seule',   @pwd, 'viewer');

INSERT INTO payout_accounts (id, client_id, label, iban_last4, is_default) VALUES
    ('aaaaaaaa-0000-0000-0000-000000000001', '11111111-1111-1111-1111-111111111111', 'Banque Démo', '0142', TRUE),
    ('aaaaaaaa-0000-0000-0000-000000000002', '22222222-2222-2222-2222-222222222222', 'Banque Démo', '0189', TRUE),
    ('aaaaaaaa-0000-0000-0000-000000000003', '33333333-3333-3333-3333-333333333333', 'Néobanque',   '3000', TRUE);
