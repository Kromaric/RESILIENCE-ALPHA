# probe

Sonde de transaction synthétique — port interne **8006**.
Exécute login → pay → lecture à travers le WAF toutes les 10 s et sert à la vérification de reprise (`POST /run`).
Voir CADRAGE §4.4.
