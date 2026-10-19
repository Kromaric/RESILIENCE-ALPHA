# remediation-engine

Moteur de remédiation automatique — port interne **8003**.
Reçoit les alertes d'Alertmanager (`POST /webhook/alert`), exécute les playbooks de `infra/ansible/remediation/`, vérifie la reprise.
Voir CADRAGE §4.6 et §7.
