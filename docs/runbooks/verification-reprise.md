# Runbook — vérification de la reprise (clôture d'un incident)

## Pourquoi un redémarrage ne suffit pas

Un conteneur qui redémarre ne prouve pas la reprise : l'API peut rester inaccessible, une opération métier
peut encore échouer, ou des données peuvent être incohérentes. Le moteur de remédiation ne passe un
incident à **`verified`** que si **tous** les contrôles ci-dessous réussissent.

## Les cinq contrôles de vérification

| # | Contrôle | Seuil de réussite |
|---|---|---|
| 1 | `POST probe:8006/run` trois fois de suite (login → pay → lecture, à travers le WAF) | 3 succès consécutifs |
| 2 | Latence p95 de payment-service | Sous la valeur de référence mesurée en nominal |
| 3 | `anomaly_score{target="payment-service"}` | Sous le seuil |
| 4 | Cohérence des données (compte MariaDB `remediation_ro`) | 0 transaction `pending` de plus de 30 s, 0 doublon d'`idempotency_key`, 0 violation de la partie double (voir ci-dessous) |
| 5 | `GET /api/status` | Repasse à `recovered` puis `operational`, avec `payments_enabled: true` |

Si un contrôle échoue : passage au niveau suivant de la politique, puis `failed`.

## Contrôles de cohérence comptable

Repris de `payment-service/app/consistency.py` (`ledger_violations`) :

1. `unbalanced_operation` : une opération dont les débits ne sont pas égaux aux crédits.
2. `entry_count` : une opération réglée sans exactement 2 écritures, ou une opération non réglée avec des écritures.
3. `balance_mismatch` : un compte dont le solde n'est pas égal à crédits − débits.
4. `negative_client_balance` : un compte client en solde négatif.

## Critères d'acceptation correspondants

| Critère | Mesure |
|---|---|
| T4 — remédiation sans intervention | Incident `verified`, étapes horodatées |
| T5 — service réellement rétabli | 3 transactions de test consécutives OK + contrôle de cohérence OK |
| T6 — boucle complète ≤ 40 s | `remediation_duration_seconds` et horodatages de l'incident |

## Vérification visible par le jury

- Dashboard : frise détecté → contenu → rétabli → **vérifié**, et état des services repassé au vert.
- Frontend : bandeau « Service rétabli » avec la référence de la transaction de vérification.
- Paiement réalisé en direct depuis l'application après la reprise.
