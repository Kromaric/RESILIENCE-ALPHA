# Documentation — PROJECT RESILIENCE-ALPHA (Orbe)

Procédures, architecture, alertes et documentation d'API de la plateforme de paiement fictive **Orbe**.
Ce dossier est aussi le **corpus de l'assistant opérateur** (`assistant-rag`) : chaque fichier Markdown
est découpé par titres puis indexé.

Toutes les données sont fictives. Aucune donnée bancaire ou personnelle réelle.

## Sommaire

| Fichier | Contenu | Question type à laquelle il répond |
|---|---|---|
| [`architecture.md`](architecture.md) | Conteneurs, réseaux, ports exposés, flux d'un paiement | « Quels services composent Orbe ? », « Quel port est exposé ? » |
| [`etat-implementation.md`](etat-implementation.md) | Ce qui est livré, ce qui reste à faire, écarts avec le cadrage | « Le WAF est-il ModSecurity ou SafeLine ? » |
| [`services/`](services/) | Une fiche par composant (WAF, auth, paiement, sonde, détection, remédiation, assistant, observabilité, base de données) | « À quoi sert la sonde ? », « Que vérifie `/health/ready` ? » |
| [`alertes/catalogue-alertes.md`](alertes/catalogue-alertes.md) | Une fiche par alerte : signification, action automatique, vérification | « L'alerte PaymentAnomaly s'est déclenchée, ça veut dire quoi ? » |
| [`metriques-et-journaux.md`](metriques-et-journaux.md) | Métriques Prometheus et événements de journal, avec leur sens | « Que mesure `payment_db_pool_in_use` ? » |
| [`runbooks/`](runbooks/) | Procédures : SC-01, SC-02, vérification de reprise, déploiement et remise à zéro, diagnostic | « Qu'a fait l'automate et comment vérifier que le paiement remarche ? » |
| [`securite.md`](securite.md) | Durcissement, moteur de remédiation, Vault, exposition réseau, biométrie | « Pourquoi le moteur n'a-t-il pas le socket Docker ? » |
| [`gouvernance/pca-pra.md`](gouvernance/pca-pra.md) | Services critiques, RTO/RPO, scénarios couverts, responsabilités (brouillon) | « Quel est le RTO du service de paiement ? » |
| [`faq-operateur.md`](faq-operateur.md) | Réponses courtes aux questions fréquentes pendant un incident | Questions rapides |
| [`glossaire.md`](glossaire.md) | Sigles et vocabulaire du projet | « Que veut dire RPO ? » |
| [`mcd.md`](mcd.md) | Modèle conceptuel de données, règles de gestion RG-01 à RG-18 | « Combien d'écritures par paiement ? » |
| [`api/`](api/) | Spécifications OpenAPI exportées (Swagger) | Détail des endpoints |

## Conventions d'écriture (pour le RAG)

- **Un sujet par section**, titre explicite qui répète le nom du service ou de l'alerte
  (« PaymentAnomaly — action automatique » plutôt que « Action »).
- Noms **exacts** tels qu'ils apparaissent dans Grafana, Prometheus et les journaux.
- Phrases autonomes : un extrait de 800 caractères doit rester compréhensible seul.
- Statut explicite quand un élément est prévu mais pas encore livré : *(cible)*.
- Les fichiers d'API (`api/*.json`, `index.html`, `specs.js`) ne sont pas indexés : seul le Markdown l'est.

## Référence

Le document de référence reste [`../CADRAGE.md`](../CADRAGE.md). En cas de contradiction, le cadrage
et le code font foi ; corriger alors le document concerné ici.
