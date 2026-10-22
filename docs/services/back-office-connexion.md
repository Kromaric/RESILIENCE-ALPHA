# Back-office — connexion par reconnaissance faciale et LED ESP8266

Connexion des opérateurs au dashboard de supervision, sur le poste du PC Hôte (caméra USB),
et LED bicolore d'un ESP8266 qui suit chaque étape. Gérée par auth-service, relayée par bo-api.

## Back-office — parcours de connexion

L'ordre est imposé : **identifiant → visage → mot de passe**.

1. `POST /bo/auth/identify` `{ "email" }` → `{ session_id, step: "face", face_challenge }`. Le front
   allume la caméra USB et affiche la consigne (« tournez la tête vers la gauche »).
2. `POST /bo/auth/face` `{ session_id, frames }` : `face_challenge.frames` images (12) prises toutes les
   `interval_ms` (300 ms) pendant la rotation de la tête.
   - Reconnu → `{ step: "password" }`, LED **verte clignotante** jusqu'au mot de passe.
   - Non reconnu → `401 face_not_recognized` (ou `liveness_failed`), LED **rouge fixe 30 s** ; le front
     éteint la caméra et vide l'identifiant ; tout nouvel identifiant est refusé pendant 30 s
     (`429 identification_locked`, en-tête `Retry-After`).
3. `POST /bo/auth/password` `{ session_id, password }` :
   - Correct → jeton du back-office (1 h), LED **verte fixe 30 s** puis éteinte ; le dashboard s'ouvre.
   - Faux → `401 invalid_credentials`, LED **rouge clignotante 10 fois** puis éteinte ; retour à
     l'identifiant (identifiant vidé, caméra éteinte).

Chaque étape doit être franchie dans les 2 minutes (`401 login_step_expired` sinon). Un identifiant
inconnu reçoit lui aussi une consigne de visage : l'échec arrive au visage, sans révéler si le compte
existe. Après 5 échecs (visage ou mot de passe), le compte est bloqué 10 minutes (`423`).

## Back-office — LED de l'ESP8266

| Étape | LED (`state`) |
|---|---|
| Au repos | `off` |
| Identifiant saisi et visage reconnu | `green_blink` jusqu'au mot de passe |
| Mot de passe correct | `green_fixed` 30 s, puis `off` |
| Mot de passe faux | `red_blink` 10 fois, puis `off` |
| Visage non reconnu | `red_fixed` 30 s, puis `off` |

L'ESP8266, connecté en WiFi au point d'accès de la solution, interroge auth-service toutes les 300 ms
environ :

```
GET http://<auth-service>:8001/devices/led
X-Device-Key: <contenu du secret led_device_key>

200 { "state": "red_blink", "seq": 42, "remaining_ms": 4800, "blinks": 10, "blink_period_ms": 500 }
401 { "detail": { "code": "invalid_device", … } }      clé absente ou fausse
```

- `state` : motif à afficher. `green_blink` et `red_blink` clignotent avec une période de
  `blink_period_ms` (500 ms : 250 ms allumée, 250 ms éteinte) ; `red_blink` s'arrête après `blinks`
  clignotements.
- `seq` change à chaque nouvel état : le firmware recommence le motif quand `seq` change, même si
  `state` est identique (deux mots de passe faux de suite).
- `remaining_ms` : durée restante de l'état ; `null` s'il dure jusqu'au prochain changement.
- En cas de perte du WiFi ou d'erreur, la LED doit s'éteindre (état sûr).
- Un redémarrage d'auth-service remet la LED à `off` (l'état est tenu en mémoire : une seule LED, pour
  le seul poste du back-office).

Firmware : projet PlatformIO dans JetBrains CLion (obligatoire), cible ESP8266, LED bicolore sur deux
broches (rouge, verte). La clé `led_device_key` est générée par `scripts/init_dev_secrets.py` (ou lue
dans Vault) et recopiée dans la configuration du firmware, jamais dans le dépôt.

## Back-office — démarrage et habilitations

- **Démarrage** : tant qu'aucun opérateur n'a de visage, le premier qui se connecte (identifiant, puis
  mot de passe) reçoit `face_enrollment_required: true` et un jeton limité à `POST /bo/auth/enroll-face`.
  Il enregistre son visage, puis se reconnecte normalement. Créer ce premier administrateur :
  `scripts/create_operator.py admin@… --name "…" --role admin`.
- **Ensuite**, seul un administrateur enregistre le visage d'un opérateur, la personne devant la caméra
  et après son consentement explicite : un mot de passe connu ne permet jamais de poser son propre visage.
- **Rôles** : `viewer` (indicateurs), `operator` (en plus : données personnelles, assistant), `admin`
  (en plus : habilitations).
- **Habilitations** (`/bo/admin/operators`, rôle `admin`) : lister, créer, renommer, changer le rôle,
  désactiver (sessions révoquées), nouveau mot de passe, débloquer, révoquer les sessions, enregistrer
  ou effacer le visage. Il reste toujours au moins un administrateur actif (`409 last_admin`). Chaque
  action est journalisée (`operator_admin_action` : administrateur, action, opérateur visé).

## Back-office — dépannage

| Symptôme | Cause probable | Que faire |
|---|---|---|
| `429 identification_locked` | Visage non reconnu il y a moins de 30 s | Attendre `Retry-After` secondes |
| `401 liveness_failed` | Tête pas assez tournée ou du mauvais côté | Tourner nettement la tête pendant la capture |
| `401 face_not_recognized` à chaque essai | Visage non enregistré ou mauvais éclairage | Demander à un administrateur d'enregistrer (à nouveau) le visage |
| `423 account_locked` | 5 échecs | Attendre 10 minutes ou demander un déblocage à un administrateur |
| LED toujours éteinte | Mauvaise clé d'appareil (`401`), WiFi, ou auth-service redémarré | Vérifier la clé et la connexion de l'ESP8266 |
