# Glossaire d'Orbe et de RESILIENCE-ALPHA

| Terme | Définition |
|---|---|
| **AIOps** | IA appliquée à l'exploitation : ici, détection d'anomalies par ML et déclenchement automatique de la remédiation |
| **Alertmanager** | Composant Prometheus qui regroupe les alertes et les envoie au moteur de remédiation |
| **anomaly_score** | Score de 0 à 1 publié par detector-ml ; plus il est haut, plus le comportement est inhabituel |
| **Cooldown** | Délai pendant lequel le moteur n'agit plus sur une même cible (120 s pour SC-01) |
| **DORA** | Règlement européen sur la résilience opérationnelle numérique du secteur financier |
| **EBIOS RM** | Méthode de l'ANSSI d'appréciation des risques cyber |
| **Idempotency-Key** | En-tête unique par opération : la rejouer ne crée pas de deuxième paiement |
| **IsolationForest** | Algorithme non supervisé de détection d'anomalies (scikit-learn) |
| **JWT** | Jeton signé (RS256) émis par auth-service, valable 15 minutes |
| **Liveness / détection du vivant** | Vérification qu'un vrai visage est présent (rotation de la tête demandée) |
| **Loki** | Base de journaux de Grafana, interrogée en LogQL |
| **NIS2** | Directive européenne sur la sécurité des réseaux et systèmes d'information |
| **Orbe** | Nom de la plateforme de paiement fictive du démonstrateur |
| **Partie double** | Chaque opération crée un débit et un crédit de même montant |
| **PCA / PRA** | Plan de continuité / de reprise d'activité |
| **Playbook** | Fichier Ansible décrivant une suite d'actions de remédiation |
| **Pool de connexions** | 10 connexions à la base réservées par instance de payment-service ; ressource visée par SC-01 |
| **Probe / sonde** | Service qui fait une vraie transaction toutes les 10 s pour prouver que le paiement fonctionne |
| **RAG** | Génération augmentée par recherche : le modèle répond à partir d'extraits retrouvés dans la documentation |
| **Réconciliation** | Passage en `failed` des paiements restés `pending` plus de 30 s |
| **RPO** | Perte de données maximale admissible (5 min pour Orbe) |
| **RTO** | Durée maximale admissible d'interruption (40 s pour SC-01 sur le démonstrateur) |
| **SC-01** | Scénario principal : épuisement de ressources de payment-service |
| **SC-02** | Scénario bonus : tentative de compromission d'auth-service |
| **SIEM / SOC** | Collecte et corrélation des événements de sécurité ; ici, tableau de bord SOC dans Grafana |
| **socket-proxy** | Intermédiaire qui filtre les appels du moteur à l'API Docker |
| **SOPS / age** | Outils de chiffrement de fichiers de configuration (clés d'amorçage de Vault) |
| **top_deviations** | Variables qui expliquent un score d'anomalie élevé |
| **Vault** | Coffre à secrets HashiCorp |
| **WAF** | Pare-feu applicatif web, point d'entrée unique d'Orbe |
| **Zero-Touch Recovery** | Reprise automatique sans intervention humaine |
