# PCA / PRA d'Orbe — brouillon technique

> **Brouillon à valider par le responsable gouvernance.** Les valeurs techniques viennent du cadrage ;
> les responsabilités et l'analyse EBIOS RM complète restent à produire dans le dossier de gouvernance.

## Services critiques d'Orbe

| Service | Criticité | Justification |
|---|---|---|
| Paiement (payment-service + MariaDB) | **Critique** | Fonction métier principale ; chaque minute d'arrêt bloque les transferts entre clients |
| Authentification (auth-service) | **Critique** | Sans connexion, aucun nouveau paiement ; porte aussi les données biométriques |
| WAF | **Critique** | Point d'entrée unique ; sa perte coupe tout le service |
| Frontend | Important | Les paiements restent possibles par l'API, mais pas pour un client ordinaire |
| Supervision, détection, remédiation | Important | Leur perte n'arrête pas le paiement mais supprime la reprise automatique |
| Assistant RAG | Secondaire | Aide à l'analyse, sans effet sur le service |

## Objectifs de reprise (RTO / RPO)

| Service | RTO cible (démonstrateur) | RPO | Fondement |
|---|---|---|---|
| Paiement | **40 s** de bout en bout pour SC-01 (critère T6) | 0 pour les transactions validées ; 5 min en cas de restauration | Transaction SQL atomique, idempotence, réconciliation ; dump toutes les 5 min |
| Authentification | 40 s (SC-01) ; quelques minutes pour SC-02 (isolement + rotation) | 5 min (sessions recréables) | Sessions révocables, rotation Vault |
| Données | — | **5 min** | `mariadb-dump` toutes les 5 min, rétention 24 h |

Un RTO de 40 s n'est réaliste que pour le périmètre du démonstrateur. En contexte industriel, il faudrait
le recalculer à partir de l'impact métier (volume de transactions par minute, pénalités contractuelles).

## Scénarios couverts

| Scénario | Réponse | Automatique | Fichier |
|---|---|---|---|
| SC-01 — épuisement de ressources du paiement | Contenir au WAF → redémarrer → vérifier ; niveau 2 : recréation depuis l'image de référence | Oui | `runbooks/sc01-epuisement-ressources.md` |
| SC-02 — compromission d'auth-service *(bonus)* | Isoler → preuves → révoquer les sessions → rotation des secrets → redéployer → vérifier | Oui, une tentative | `runbooks/sc02-compromission-auth.md` |
| Arrêt d'une instance de paiement (chaos) | Sortie automatique au WAF, l'autre instance sert | Oui (WAF + `restart`) | — |
| Redémarrage de MariaDB (chaos) | Réconnexion du pool, réconciliation des `pending` | Oui | — |
| Perte de detector-ml (chaos) | Alerte de secours sur la sonde | Partiel | `alertes/catalogue-alertes.md` |
| Perte du PC Hôte | Redéploiement complet (`deploy.yml`) sur une autre machine + restauration | **Non** | `runbooks/deploiement-et-reset.md` |

## Choix de restauration

- **Disponibilité** (SC-01) : redémarrer suffit, car les données ne sont pas touchées. On ne restaure pas la base.
- **Compromission** (SC-02) : on repart de l'**image de référence étiquetée** plutôt que du conteneur existant, et on renouvelle les secrets.
- **Corruption de données** : restauration du dernier dump (`restore.yml`), avec une perte de 5 min au plus. Non automatisé.

## Responsabilités *(à compléter avec les noms de l'équipe)*

| Rôle | Responsabilité pendant un incident |
|---|---|
| Moteur de remédiation | Détecter, contenir, rétablir, vérifier ; escalader si échec |
| Opérateur d'astreinte | Surveiller le dashboard, consulter l'assistant, intervenir seulement si l'incident est `failed` |
| Responsable sécurité | Analyser les preuves (SC-02), décider des notifications |
| Responsable gouvernance | Mise à jour du PRA, retour d'expérience |

## Risques résiduels après la reprise

- L'attaquant peut revenir avec une autre IP après le TTL de 15 minutes, ou depuis plusieurs IP (attaque distribuée non couverte par le blocage par IP).
- Le modèle peut produire des faux négatifs sur une attaque lente qui reste proche du trafic normal.
- La sonde s'authentifie sans visage : sa clé d'API est un secret sensible.
- Une vidéo rejouée peut tromper la détection du vivant une fois sur deux.
- Point unique de défaillance : le PC Hôte (une seule machine, un seul MariaDB).
- Le moteur de remédiation reste un composant à privilèges ; sa compromission permettrait d'arrêter des conteneurs.

## NIS2 / DORA — éléments démontrables par le prototype

| Exigence | Démontré par |
|---|---|
| Détection des incidents | Modèle ML + alertes + SOC Grafana |
| Réponse et reprise documentées et testées | Playbooks, vérification, rejeu de SC-01, tests de chaos |
| Journalisation et traçabilité | Loki, journal d'audit du moteur, `request_id` |
| Gestion des secrets et des accès | Vault, moindre privilège MariaDB, socket-proxy |
| Tests de résilience | Rejeux mesurés T2 à T6 |

Non démontrable en quatre jours : notification des incidents aux autorités dans les délais réglementaires,
gestion des risques liés aux prestataires tiers, tests de pénétration fondés sur la menace (TLPT),
gouvernance au niveau de la direction, continuité multisite.
