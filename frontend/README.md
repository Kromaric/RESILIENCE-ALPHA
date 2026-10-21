# Orbe — Interface Mobile Client

Application mobile React (Vite + Tailwind CSS v3) d'échange d'argent entre particuliers pour la plateforme **Orbe**.

## Fonctionnalités

- **Authentification par code PIN** : Clavier numérique 3x4 sécurisé à 6 chiffres.
- **Double Authentification (2FA) Biométrique** : Reconnaissance faciale par flux webcam avec mire animée et fallback matériel.
- **Accueil & Solde** : Carte compte lié (Banque Démo), actions rapides (`Envoyer`, `Demander`, `Mon QR`) et activité récente.
- **Envoi de fonds** : Recherche de contacts en temps réel et vérification avant envoi.
- **Réception d'argent** : QR code vectoriel net régénéré et formulaire d'émission de demandes.
- **Historique & Activité** : Vue chronologique avec filtres par pilules (`Tout`, `Envoyés`, `Reçus`, `Demandes`) et traçabilité des incidents (`Échec`).
- **Résilience & Mode Dégradé** : Détection automatique des pannes API (5xx/timeout) avec basculement en mode Incident et fallback sur données locales.
- **Contrôleur de Démo** : Widget flottant permettant de forcer manuellement le basculement `Opérationnel <-> Incident`.

## Démarrage rapide

```bash
# Installation des dépendances
npm install

# Lancement en développement (port 5173 avec proxy vers services 8001/8002/8003)
npm run dev

# Vérification du code et build de production
npm run lint
npm run build
```
