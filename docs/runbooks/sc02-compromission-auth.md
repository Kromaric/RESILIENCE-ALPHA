# Runbook SC-02 — tentative de compromission sur auth-service *(bonus, go/no-go à décider)*

> À engager seulement si SC-01 est stable. Ce scénario touche à la **confidentialité et à l'intégrité** :
> rétablir la disponibilité ne suffit pas, il faut aussi invalider ce que l'attaquant a pu obtenir.

## SC-02 — description

| Élément | Contenu |
|---|---|
| Catégorie | Confidentialité / intégrité |
| Exemples d'attaque | Force brute ou credential stuffing sur `/api/auth/login`, tentatives d'injection, rejeu de jeton |
| Signaux | Journaux d'authentification (`login_failed`, `account_locked`, `second_factor_failed`), règles WAF déclenchées, alertes IDS, modèle de détection d'auth-service |

## SC-02 — différence avec SC-01

SC-01 est un problème de **disponibilité** : on bloque, on redémarre, on vérifie. SC-02 est un problème de
**compromission** : un redémarrage ne révoque pas un jeton volé et ne change pas un secret exposé. La
réponse doit donc isoler, conserver les preuves et renouveler les secrets.

## SC-02 — actions automatiques (`pb-isolate-rotate-redeploy.yml`)

| Étape | Action | But |
|---|---|---|
| 1 | Déconnexion du conteneur auth-service du réseau `net-app` | **Isoler** |
| 2 | Export des journaux de la période (Loki) | **Conserver les preuves** |
| 3 | Révocation des sessions concernées (table `sessions`) | Invalider les jetons potentiellement volés |
| 4 | Si la clé JWT est en cause : rotation de la clé JWT et des identifiants DB dans Vault | **Renouveler les secrets** |
| 5 | Redéploiement depuis l'image de référence étiquetée | Repartir d'un état sain |
| 6 | Vérification (connexion, paiement de la sonde, cohérence) | **Prouver** |

Politique : `compromise`, une seule tentative, cooldown de 300 s.

## SC-02 — conséquences pour les utilisateurs

- Les clients dont la session a été révoquée doivent se reconnecter (mot de passe + visage).
- Après une rotation de la clé JWT, **tous** les jetons existants deviennent invalides.
- Pendant l'isolement, la connexion est impossible ; les paiements des sessions encore valides continuent, car payment-service vérifie les JWT localement.

## SC-02 — ce qui reste à faire par des humains

Une remédiation automatique ne clôt pas une compromission. Restent à traiter hors démonstration :
l'analyse des journaux exportés, la recherche d'une éventuelle exfiltration, la notification si des données
personnelles étaient concernées (RGPD, NIS2/DORA pour une activité financière réelle), et la correction de
la faille exploitée.
