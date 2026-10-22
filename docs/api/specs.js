// Généré par scripts/export_openapi.py — ne pas modifier à la main.
window.ORBE_SPECS = {
 "auth-service": {
  "openapi": "3.1.0",
  "info": {
   "title": "Orbe — auth-service",
   "description": "Authentification forte des clients Orbe : mot de passe puis **reconnaissance faciale** (modèle InsightFace, test du vivant par rotation de la tête dans un sens tiré au hasard), sessions révocables (JWT RS256 de 15 min), applications clientes et clés d'API partenaires. Exposé par le WAF sous `/api/auth`. Erreurs : `{\"detail\": {\"code\", \"message\"}}`. Voir CADRAGE §4.2.",
   "version": "0.1.0"
  },
  "paths": {
   "/register": {
    "post": {
     "tags": [
      "Authentification"
     ],
     "summary": "Créer un compte",
     "description": "Crée un compte client. Ensuite : `POST /login`, puis `POST /face/enroll` (visage).\n\nHors périmètre du démonstrateur : vérification de l'email et du téléphone, KYC.",
     "operationId": "register_register_post",
     "requestBody": {
      "content": {
       "application/json": {
        "schema": {
         "$ref": "#/components/schemas/RegisterRequest"
        }
       }
      },
      "required": true
     },
     "responses": {
      "201": {
       "description": "Successful Response",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/RegisterResponse"
         }
        }
       }
      },
      "409": {
       "description": "Email ou téléphone déjà utilisé",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "422": {
       "description": "Email, téléphone ou mot de passe invalide",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "429": {
       "description": "Trop d'inscriptions depuis cette IP",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      }
     }
    }
   },
   "/login": {
    "post": {
     "tags": [
      "Authentification"
     ],
     "summary": "Se connecter — étape 1 : mot de passe",
     "operationId": "login_login_post",
     "parameters": [
      {
       "name": "X-Client-Id",
       "in": "header",
       "required": false,
       "schema": {
        "anyOf": [
         {
          "type": "string"
         },
         {
          "type": "null"
         }
        ],
        "title": "X-Client-Id"
       }
      },
      {
       "name": "X-API-Key",
       "in": "header",
       "required": false,
       "schema": {
        "anyOf": [
         {
          "type": "string"
         },
         {
          "type": "null"
         }
        ],
        "title": "X-Api-Key"
       }
      }
     ],
     "requestBody": {
      "required": true,
      "content": {
       "application/json": {
        "schema": {
         "$ref": "#/components/schemas/LoginRequest"
        }
       }
      }
     },
     "responses": {
      "200": {
       "description": "Successful Response",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/LoginResponse"
         }
        }
       }
      },
      "401": {
       "description": "Identifiants ou application cliente invalides",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "403": {
       "description": "Application non autorisée pour ce compte",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "423": {
       "description": "Compte bloqué (en-tête Retry-After)",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "429": {
       "description": "Trop de tentatives depuis cette IP",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "422": {
       "description": "Validation Error",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/HTTPValidationError"
         }
        }
       }
      }
     }
    }
   },
   "/login/face": {
    "post": {
     "tags": [
      "Authentification"
     ],
     "summary": "Se connecter — étape 2 : reconnaissance faciale",
     "description": "Images filmées pendant que la tête tourne dans le sens indiqué par `face_challenge`.\n\nUn échec clôt la tentative (il faut recommencer `POST /login`, avec une nouvelle consigne)\net compte dans le blocage du compte, comme un mauvais mot de passe.",
     "operationId": "login_face_login_face_post",
     "requestBody": {
      "content": {
       "application/json": {
        "schema": {
         "$ref": "#/components/schemas/FaceLoginRequest"
        }
       }
      },
      "required": true
     },
     "responses": {
      "200": {
       "description": "Successful Response",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/TokenResponse"
         }
        }
       }
      },
      "401": {
       "description": "Visage non reconnu, test du vivant échoué ou session expirée",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "422": {
       "description": "Images invalides",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "429": {
       "description": "Trop de tentatives depuis cette IP",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "503": {
       "description": "Reconnaissance faciale indisponible",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      }
     }
    }
   },
   "/logout": {
    "post": {
     "tags": [
      "Authentification"
     ],
     "summary": "Se déconnecter (révoque la session)",
     "operationId": "logout_logout_post",
     "responses": {
      "204": {
       "description": "Successful Response"
      },
      "401": {
       "description": "Session invalide ou expirée",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      }
     },
     "security": [
      {
       "HTTPBearer": []
      }
     ]
    }
   },
   "/me": {
    "get": {
     "tags": [
      "Authentification"
     ],
     "summary": "Mon profil",
     "operationId": "me_me_get",
     "responses": {
      "200": {
       "description": "Successful Response",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/MeResponse"
         }
        }
       }
      },
      "401": {
       "description": "Jeton absent, invalide ou expiré",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      }
     },
     "security": [
      {
       "HTTPBearer": []
      }
     ]
    }
   },
   "/verify": {
    "get": {
     "tags": [
      "Partenaires"
     ],
     "summary": "Vérifier une clé d'API partenaire",
     "operationId": "verify_api_key_verify_get",
     "parameters": [
      {
       "name": "X-API-Key",
       "in": "header",
       "required": false,
       "schema": {
        "anyOf": [
         {
          "type": "string"
         },
         {
          "type": "null"
         }
        ],
        "title": "X-Api-Key"
       }
      }
     ],
     "responses": {
      "200": {
       "description": "Successful Response",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/VerifyResponse"
         }
        }
       }
      },
      "401": {
       "description": "Clé absente, inconnue ou désactivée",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "422": {
       "description": "Validation Error",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/HTTPValidationError"
         }
        }
       }
      }
     }
    }
   },
   "/face": {
    "get": {
     "tags": [
      "Visage"
     ],
     "summary": "Mon visage enregistré",
     "operationId": "face_status_face_get",
     "responses": {
      "200": {
       "description": "Successful Response",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/FaceStatus"
         }
        }
       }
      },
      "401": {
       "description": "Session invalide ou expirée",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "403": {
       "description": "Session sans visage alors que le compte en a un",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      }
     },
     "security": [
      {
       "HTTPBearer": []
      }
     ]
    },
    "delete": {
     "tags": [
      "Visage"
     ],
     "summary": "Supprimer mon visage (droit à l'effacement)",
     "description": "Efface définitivement les gabarits et le consentement. La connexion repassera par\nl'enrôlement du visage.",
     "operationId": "erase_face_delete",
     "responses": {
      "204": {
       "description": "Successful Response"
      },
      "401": {
       "description": "Session invalide ou expirée",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "403": {
       "description": "Session sans visage alors que le compte en a un",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      }
     },
     "security": [
      {
       "HTTPBearer": []
      }
     ]
    }
   },
   "/face/challenge": {
    "get": {
     "tags": [
      "Visage"
     ],
     "summary": "Obtenir une consigne de test du vivant pour vérification biométrique",
     "description": "Consigne tirée par le serveur et mémorisée dans la session : `POST /face/verify` ne\nl'accepte qu'une fois. Un client ne peut donc pas choisir le sens de rotation.",
     "operationId": "get_face_challenge_face_challenge_get",
     "responses": {
      "200": {
       "description": "Successful Response",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/FaceChallenge"
         }
        }
       }
      },
      "401": {
       "description": "Session invalide ou expirée",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "403": {
       "description": "Session sans visage alors que le compte en a un",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      }
     },
     "security": [
      {
       "HTTPBearer": []
      }
     ]
    }
   },
   "/face/verify": {
    "post": {
     "tags": [
      "Visage"
     ],
     "summary": "Vérifier le visage et élever la session en authentification forte (2FA)",
     "operationId": "verify_face_face_verify_post",
     "requestBody": {
      "content": {
       "application/json": {
        "schema": {
         "$ref": "#/components/schemas/FaceVerifyRequest"
        }
       }
      },
      "required": true
     },
     "responses": {
      "200": {
       "description": "Successful Response",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/FaceVerifyResponse"
         }
        }
       }
      },
      "401": {
       "description": "Visage non reconnu ou test du vivant échoué",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "403": {
       "description": "Session sans visage alors que le compte en a un",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "422": {
       "description": "Images invalides ou visage non détecté",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "503": {
       "description": "Reconnaissance faciale indisponible",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      }
     },
     "security": [
      {
       "HTTPBearer": []
      }
     ]
    }
   },
   "/face/enroll": {
    "post": {
     "tags": [
      "Visage"
     ],
     "summary": "Enregistrer (ou remplacer) mon visage",
     "description": "Environ 16 images en tournant lentement la tête de gauche à droite. Seuls 3 à 5\ngabarits (embeddings) sont conservés, chiffrés ; aucune image n'est stockée.",
     "operationId": "enroll_face_enroll_post",
     "requestBody": {
      "content": {
       "application/json": {
        "schema": {
         "$ref": "#/components/schemas/FaceEnrollRequest"
        }
       }
      },
      "required": true
     },
     "responses": {
      "201": {
       "description": "Successful Response",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/FaceStatus"
         }
        }
       }
      },
      "401": {
       "description": "Session invalide ou expirée",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "403": {
       "description": "Session sans visage alors que le compte en a un",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "422": {
       "description": "Consentement absent, visage non détecté ou plusieurs personnes",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "503": {
       "description": "Reconnaissance faciale indisponible",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      }
     },
     "security": [
      {
       "HTTPBearer": []
      }
     ]
    }
   },
   "/operators/login/identify": {
    "post": {
     "tags": [
      "Back-office"
     ],
     "summary": "Connexion — 1. identifiant",
     "description": "Démarre la connexion et renvoie la consigne de la caméra (tourner la tête). Bloqué\n30 s après un visage non reconnu (`429 identification_locked`, en-tête Retry-After).",
     "operationId": "identify_operators_login_identify_post",
     "requestBody": {
      "content": {
       "application/json": {
        "schema": {
         "$ref": "#/components/schemas/OperatorIdentifyRequest"
        }
       }
      },
      "required": true
     },
     "responses": {
      "200": {
       "description": "Successful Response",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/OperatorLoginStep"
         }
        }
       }
      },
      "423": {
       "description": "Compte bloqué (en-tête Retry-After)",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "429": {
       "description": "Identification bloquée ou trop de tentatives",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "422": {
       "description": "Validation Error",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/HTTPValidationError"
         }
        }
       }
      }
     }
    }
   },
   "/operators/login/face": {
    "post": {
     "tags": [
      "Back-office"
     ],
     "summary": "Connexion — 2. reconnaissance faciale (caméra USB)",
     "description": "Reconnu : LED verte clignotante jusqu'au mot de passe. Non reconnu : LED rouge fixe\n30 s, identification bloquée 30 s, la caméra peut être éteinte.",
     "operationId": "login_face_operators_login_face_post",
     "requestBody": {
      "content": {
       "application/json": {
        "schema": {
         "$ref": "#/components/schemas/OperatorFaceRequest"
        }
       }
      },
      "required": true
     },
     "responses": {
      "200": {
       "description": "Successful Response",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/OperatorLoginStep"
         }
        }
       }
      },
      "401": {
       "description": "Visage non reconnu ou étape expirée",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "422": {
       "description": "Images invalides",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "503": {
       "description": "Reconnaissance faciale indisponible",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      }
     }
    }
   },
   "/operators/login/password": {
    "post": {
     "tags": [
      "Back-office"
     ],
     "summary": "Connexion — 3. mot de passe",
     "description": "Correct : LED verte fixe 30 s et jeton du back-office. Faux : LED rouge clignotante\n10 fois, la connexion recommence à l'identifiant.",
     "operationId": "login_password_operators_login_password_post",
     "requestBody": {
      "content": {
       "application/json": {
        "schema": {
         "$ref": "#/components/schemas/OperatorPasswordRequest"
        }
       }
      },
      "required": true
     },
     "responses": {
      "200": {
       "description": "Successful Response",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/OperatorTokenResponse"
         }
        }
       }
      },
      "401": {
       "description": "Mot de passe faux ou étape expirée",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "422": {
       "description": "Validation Error",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/HTTPValidationError"
         }
        }
       }
      }
     }
    }
   },
   "/operators/me/face": {
    "post": {
     "tags": [
      "Back-office"
     ],
     "summary": "Première connexion : enregistrer mon visage",
     "description": "Réservé au jeton de première connexion (`face_enrollment_required`), au démarrage\nseulement. La session est ensuite fermée : l'opérateur se reconnecte avec son visage.",
     "operationId": "enroll_me_operators_me_face_post",
     "requestBody": {
      "content": {
       "application/json": {
        "schema": {
         "$ref": "#/components/schemas/FaceEnrollRequest"
        }
       }
      },
      "required": true
     },
     "responses": {
      "201": {
       "description": "Successful Response",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/FaceStatus"
         }
        }
       }
      },
      "401": {
       "description": "Jeton d'enrôlement absent ou expiré",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "422": {
       "description": "Consentement absent ou visage non détecté",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      }
     },
     "security": [
      {
       "HTTPBearer": []
      }
     ]
    }
   },
   "/operators/logout": {
    "post": {
     "tags": [
      "Back-office"
     ],
     "summary": "Déconnexion d'un opérateur (révoque la session)",
     "operationId": "logout_operators_logout_post",
     "responses": {
      "204": {
       "description": "Successful Response"
      },
      "401": {
       "description": "Session invalide ou expirée",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      }
     },
     "security": [
      {
       "HTTPBearer": []
      }
     ]
    }
   },
   "/operators/me": {
    "get": {
     "tags": [
      "Back-office"
     ],
     "summary": "Opérateur connecté (sert aussi à bo-api pour vérifier la session)",
     "operationId": "me_operators_me_get",
     "responses": {
      "200": {
       "description": "Successful Response",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/OperatorMe"
         }
        }
       }
      },
      "401": {
       "description": "Jeton absent, invalide ou révoqué",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      }
     },
     "security": [
      {
       "HTTPBearer": []
      }
     ]
    }
   },
   "/operators/accounts": {
    "get": {
     "tags": [
      "Back-office — habilitations"
     ],
     "summary": "Opérateurs",
     "operationId": "list_accounts_operators_accounts_get",
     "responses": {
      "200": {
       "description": "Successful Response",
       "content": {
        "application/json": {
         "schema": {
          "items": {
           "$ref": "#/components/schemas/OperatorAccount"
          },
          "type": "array",
          "title": "Response List Accounts Operators Accounts Get"
         }
        }
       }
      },
      "401": {
       "description": "Session invalide ou expirée",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "403": {
       "description": "Réservé au rôle « admin »",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      }
     },
     "security": [
      {
       "HTTPBearer": []
      }
     ]
    },
    "post": {
     "tags": [
      "Back-office — habilitations"
     ],
     "summary": "Créer un opérateur",
     "description": "Le visage s'enregistre ensuite, la personne devant la caméra (`POST …/{id}/face`).",
     "operationId": "create_account_operators_accounts_post",
     "requestBody": {
      "content": {
       "application/json": {
        "schema": {
         "$ref": "#/components/schemas/OperatorCreate"
        }
       }
      },
      "required": true
     },
     "responses": {
      "201": {
       "description": "Successful Response",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/OperatorAccount"
         }
        }
       }
      },
      "401": {
       "description": "Session invalide ou expirée",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "403": {
       "description": "Réservé au rôle « admin »",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "409": {
       "description": "Email déjà utilisé",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "422": {
       "description": "Email ou mot de passe invalide",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      }
     },
     "security": [
      {
       "HTTPBearer": []
      }
     ]
    }
   },
   "/operators/accounts/{operator_id}": {
    "patch": {
     "tags": [
      "Back-office — habilitations"
     ],
     "summary": "Modifier le nom, le rôle ou l'activation",
     "description": "Désactiver un compte révoque ses sessions ; un changement de rôle s'applique dès la\nrequête suivante (bo-api relit le rôle auprès d'auth-service).",
     "operationId": "update_account_operators_accounts__operator_id__patch",
     "security": [
      {
       "HTTPBearer": []
      }
     ],
     "parameters": [
      {
       "name": "operator_id",
       "in": "path",
       "required": true,
       "schema": {
        "type": "string",
        "title": "Operator Id"
       }
      }
     ],
     "requestBody": {
      "required": true,
      "content": {
       "application/json": {
        "schema": {
         "$ref": "#/components/schemas/OperatorUpdate"
        }
       }
      }
     },
     "responses": {
      "200": {
       "description": "Successful Response",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/OperatorAccount"
         }
        }
       }
      },
      "401": {
       "description": "Session invalide ou expirée",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "403": {
       "description": "Réservé au rôle « admin »",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "404": {
       "description": "Opérateur inconnu",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "409": {
       "description": "Dernier admin",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "422": {
       "description": "Validation Error",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/HTTPValidationError"
         }
        }
       }
      }
     }
    }
   },
   "/operators/accounts/{operator_id}/password": {
    "post": {
     "tags": [
      "Back-office — habilitations"
     ],
     "summary": "Définir un nouveau mot de passe",
     "description": "Révoque les sessions de l'opérateur et lève un éventuel blocage.",
     "operationId": "reset_password_operators_accounts__operator_id__password_post",
     "security": [
      {
       "HTTPBearer": []
      }
     ],
     "parameters": [
      {
       "name": "operator_id",
       "in": "path",
       "required": true,
       "schema": {
        "type": "string",
        "title": "Operator Id"
       }
      }
     ],
     "requestBody": {
      "required": true,
      "content": {
       "application/json": {
        "schema": {
         "$ref": "#/components/schemas/OperatorPasswordReset"
        }
       }
      }
     },
     "responses": {
      "204": {
       "description": "Successful Response"
      },
      "401": {
       "description": "Session invalide ou expirée",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "403": {
       "description": "Réservé au rôle « admin »",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "404": {
       "description": "Opérateur inconnu",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "422": {
       "description": "Trop faible",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      }
     }
    }
   },
   "/operators/accounts/{operator_id}/unlock": {
    "post": {
     "tags": [
      "Back-office — habilitations"
     ],
     "summary": "Débloquer un compte (après 5 échecs)",
     "operationId": "unlock_operators_accounts__operator_id__unlock_post",
     "security": [
      {
       "HTTPBearer": []
      }
     ],
     "parameters": [
      {
       "name": "operator_id",
       "in": "path",
       "required": true,
       "schema": {
        "type": "string",
        "title": "Operator Id"
       }
      }
     ],
     "responses": {
      "200": {
       "description": "Successful Response",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/OperatorAccount"
         }
        }
       }
      },
      "401": {
       "description": "Session invalide ou expirée",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "403": {
       "description": "Réservé au rôle « admin »",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "404": {
       "description": "Opérateur inconnu",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "422": {
       "description": "Validation Error",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/HTTPValidationError"
         }
        }
       }
      }
     }
    }
   },
   "/operators/accounts/{operator_id}/sessions": {
    "delete": {
     "tags": [
      "Back-office — habilitations"
     ],
     "summary": "Révoquer toutes les sessions d'un opérateur",
     "operationId": "revoke_sessions_operators_accounts__operator_id__sessions_delete",
     "security": [
      {
       "HTTPBearer": []
      }
     ],
     "parameters": [
      {
       "name": "operator_id",
       "in": "path",
       "required": true,
       "schema": {
        "type": "string",
        "title": "Operator Id"
       }
      }
     ],
     "responses": {
      "204": {
       "description": "Successful Response"
      },
      "401": {
       "description": "Session invalide ou expirée",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "403": {
       "description": "Réservé au rôle « admin »",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "404": {
       "description": "Opérateur inconnu",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "422": {
       "description": "Validation Error",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/HTTPValidationError"
         }
        }
       }
      }
     }
    }
   },
   "/operators/accounts/{operator_id}/face": {
    "post": {
     "tags": [
      "Back-office — habilitations"
     ],
     "summary": "Enregistrer (ou remplacer) le visage d'un opérateur",
     "description": "L'opérateur est devant la caméra USB du poste et a donné son consentement explicite\n(case à cocher). ~16 images, tête qui balaie lentement de gauche à droite.",
     "operationId": "enroll_face_operators_accounts__operator_id__face_post",
     "security": [
      {
       "HTTPBearer": []
      }
     ],
     "parameters": [
      {
       "name": "operator_id",
       "in": "path",
       "required": true,
       "schema": {
        "type": "string",
        "title": "Operator Id"
       }
      }
     ],
     "requestBody": {
      "required": true,
      "content": {
       "application/json": {
        "schema": {
         "$ref": "#/components/schemas/FaceEnrollRequest"
        }
       }
      }
     },
     "responses": {
      "201": {
       "description": "Successful Response",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/OperatorAccount"
         }
        }
       }
      },
      "401": {
       "description": "Session invalide ou expirée",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "403": {
       "description": "Réservé au rôle « admin »",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "404": {
       "description": "Opérateur inconnu",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "422": {
       "description": "Consentement absent ou visage non détecté",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      }
     }
    },
    "delete": {
     "tags": [
      "Back-office — habilitations"
     ],
     "summary": "Effacer le visage d'un opérateur (droit à l'effacement)",
     "description": "Sans visage, l'opérateur ne peut plus se connecter : ses sessions sont révoquées.",
     "operationId": "erase_face_operators_accounts__operator_id__face_delete",
     "security": [
      {
       "HTTPBearer": []
      }
     ],
     "parameters": [
      {
       "name": "operator_id",
       "in": "path",
       "required": true,
       "schema": {
        "type": "string",
        "title": "Operator Id"
       }
      }
     ],
     "responses": {
      "200": {
       "description": "Successful Response",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/OperatorAccount"
         }
        }
       }
      },
      "401": {
       "description": "Session invalide ou expirée",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "403": {
       "description": "Réservé au rôle « admin »",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "404": {
       "description": "Opérateur inconnu",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "422": {
       "description": "Validation Error",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/HTTPValidationError"
         }
        }
       }
      }
     }
    }
   },
   "/devices/led": {
    "get": {
     "tags": [
      "Objet connecté"
     ],
     "summary": "État de la LED du poste back-office (ESP8266)",
     "description": "À interroger toutes les 300 ms environ. Motifs : `off`, `green_fixed`, `red_fixed`,\n`green_blink` (période `blink_period_ms`), `red_blink` (`blinks` clignotements, puis éteinte).\n`remaining_ms` : durée restante de l'état, `null` s'il dure jusqu'au prochain changement.",
     "operationId": "led_devices_led_get",
     "parameters": [
      {
       "name": "X-Device-Key",
       "in": "header",
       "required": false,
       "schema": {
        "anyOf": [
         {
          "type": "string"
         },
         {
          "type": "null"
         }
        ],
        "title": "X-Device-Key"
       }
      }
     ],
     "responses": {
      "200": {
       "description": "Successful Response",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/LedOut"
         }
        }
       }
      },
      "401": {
       "description": "Clé d'appareil absente ou invalide",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "422": {
       "description": "Validation Error",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/HTTPValidationError"
         }
        }
       }
      }
     }
    }
   }
  },
  "components": {
   "schemas": {
    "ErrorDetail": {
     "properties": {
      "code": {
       "type": "string",
       "title": "Code",
       "examples": [
        "invalid_credentials"
       ]
      },
      "message": {
       "type": "string",
       "title": "Message",
       "examples": [
        "Email ou mot de passe incorrect."
       ]
      }
     },
     "type": "object",
     "required": [
      "code",
      "message"
     ],
     "title": "ErrorDetail"
    },
    "ErrorOut": {
     "properties": {
      "detail": {
       "$ref": "#/components/schemas/ErrorDetail"
      }
     },
     "type": "object",
     "required": [
      "detail"
     ],
     "title": "ErrorOut"
    },
    "FaceChallenge": {
     "properties": {
      "direction": {
       "type": "string",
       "enum": [
        "left",
        "right"
       ],
       "title": "Direction"
      },
      "frames": {
       "type": "integer",
       "title": "Frames",
       "description": "Nombre d'images à envoyer"
      },
      "interval_ms": {
       "type": "integer",
       "title": "Interval Ms",
       "description": "Intervalle conseillé entre deux images",
       "default": 250
      }
     },
     "type": "object",
     "required": [
      "direction",
      "frames"
     ],
     "title": "FaceChallenge",
     "description": "Consigne du test du vivant : filmer le visage pendant que la tête tourne dans ce sens."
    },
    "FaceEnrollRequest": {
     "properties": {
      "consent": {
       "type": "boolean",
       "title": "Consent",
       "description": "Consentement explicite au traitement des données biométriques (RGPD art. 9)"
      },
      "frames": {
       "items": {
        "type": "string"
       },
       "type": "array",
       "maxItems": 30,
       "minItems": 1,
       "title": "Frames",
       "description": "Images JPEG encodées en base64, capturées par la caméra du navigateur"
      }
     },
     "type": "object",
     "required": [
      "consent",
      "frames"
     ],
     "title": "FaceEnrollRequest"
    },
    "FaceLoginRequest": {
     "properties": {
      "session_id": {
       "type": "string",
       "maxLength": 36,
       "minLength": 36,
       "title": "Session Id"
      },
      "frames": {
       "items": {
        "type": "string"
       },
       "type": "array",
       "maxItems": 20,
       "minItems": 1,
       "title": "Frames",
       "description": "Images JPEG encodées en base64, capturées par la caméra du navigateur"
      }
     },
     "type": "object",
     "required": [
      "session_id",
      "frames"
     ],
     "title": "FaceLoginRequest"
    },
    "FaceStatus": {
     "properties": {
      "enrolled": {
       "type": "boolean",
       "title": "Enrolled"
      },
      "templates": {
       "type": "integer",
       "title": "Templates"
      },
      "model": {
       "anyOf": [
        {
         "type": "string"
        },
        {
         "type": "null"
        }
       ],
       "title": "Model"
      },
      "consent_at": {
       "anyOf": [
        {
         "type": "string"
        },
        {
         "type": "null"
        }
       ],
       "title": "Consent At"
      },
      "token": {
       "anyOf": [
        {
         "$ref": "#/components/schemas/TokenResponse"
        },
        {
         "type": "null"
        }
       ]
      }
     },
     "type": "object",
     "required": [
      "enrolled",
      "templates",
      "model",
      "consent_at"
     ],
     "title": "FaceStatus"
    },
    "FaceVerifyRequest": {
     "properties": {
      "frames": {
       "items": {
        "type": "string"
       },
       "type": "array",
       "maxItems": 20,
       "minItems": 1,
       "title": "Frames",
       "description": "Images JPEG encodées en base64, capturées par la caméra du navigateur"
      },
      "direction": {
       "anyOf": [
        {
         "type": "string",
         "enum": [
          "left",
          "right"
         ]
        },
        {
         "type": "null"
        }
       ],
       "title": "Direction"
      }
     },
     "type": "object",
     "required": [
      "frames"
     ],
     "title": "FaceVerifyRequest"
    },
    "FaceVerifyResponse": {
     "properties": {
      "verified": {
       "type": "boolean",
       "title": "Verified"
      },
      "confidence": {
       "type": "number",
       "title": "Confidence"
      },
      "token": {
       "$ref": "#/components/schemas/TokenResponse"
      }
     },
     "type": "object",
     "required": [
      "verified",
      "confidence",
      "token"
     ],
     "title": "FaceVerifyResponse"
    },
    "HTTPValidationError": {
     "properties": {
      "detail": {
       "items": {
        "$ref": "#/components/schemas/ValidationError"
       },
       "type": "array",
       "title": "Detail"
      }
     },
     "type": "object",
     "title": "HTTPValidationError"
    },
    "LedOut": {
     "properties": {
      "state": {
       "type": "string",
       "enum": [
        "off",
        "green_blink",
        "green_fixed",
        "red_blink",
        "red_fixed"
       ],
       "title": "State"
      },
      "seq": {
       "type": "integer",
       "title": "Seq"
      },
      "remaining_ms": {
       "anyOf": [
        {
         "type": "integer"
        },
        {
         "type": "null"
        }
       ],
       "title": "Remaining Ms"
      },
      "blinks": {
       "anyOf": [
        {
         "type": "integer"
        },
        {
         "type": "null"
        }
       ],
       "title": "Blinks"
      },
      "blink_period_ms": {
       "type": "integer",
       "title": "Blink Period Ms"
      }
     },
     "type": "object",
     "required": [
      "state",
      "seq",
      "remaining_ms",
      "blinks",
      "blink_period_ms"
     ],
     "title": "LedOut"
    },
    "LoginRequest": {
     "properties": {
      "email": {
       "type": "string",
       "maxLength": 254,
       "minLength": 3,
       "title": "Email"
      },
      "password": {
       "type": "string",
       "maxLength": 128,
       "minLength": 1,
       "title": "Password"
      }
     },
     "type": "object",
     "required": [
      "email",
      "password"
     ],
     "title": "LoginRequest",
     "examples": [
      {
       "email": "client@boutique-demo.test",
       "password": "demo-password"
      }
     ]
    },
    "LoginResponse": {
     "properties": {
      "mfa_required": {
       "type": "boolean",
       "title": "Mfa Required"
      },
      "session_id": {
       "type": "string",
       "title": "Session Id"
      },
      "face_challenge": {
       "anyOf": [
        {
         "$ref": "#/components/schemas/FaceChallenge"
        },
        {
         "type": "null"
        }
       ]
      },
      "token": {
       "anyOf": [
        {
         "$ref": "#/components/schemas/TokenResponse"
        },
        {
         "type": "null"
        }
       ]
      },
      "face_enrollment_required": {
       "type": "boolean",
       "title": "Face Enrollment Required",
       "default": false
      }
     },
     "type": "object",
     "required": [
      "mfa_required",
      "session_id"
     ],
     "title": "LoginResponse",
     "description": "Étape 1 de la connexion.\n\n- `mfa_required = true` : filmer le visage selon `face_challenge`, puis `POST /login/face` ;\n- sinon : `token` est fourni. `face_enrollment_required = true` signale un compte sans\n  visage enregistré : la session ne permet que de consulter et d'enrôler son visage."
    },
    "MeResponse": {
     "properties": {
      "client_id": {
       "type": "string",
       "title": "Client Id"
      },
      "email": {
       "type": "string",
       "title": "Email"
      },
      "phone_masked": {
       "type": "string",
       "title": "Phone Masked"
      },
      "display_name": {
       "type": "string",
       "title": "Display Name"
      },
      "factors": {
       "items": {
        "type": "string"
       },
       "type": "array",
       "title": "Factors"
      },
      "face_enrolled": {
       "type": "boolean",
       "title": "Face Enrolled"
      }
     },
     "type": "object",
     "required": [
      "client_id",
      "email",
      "phone_masked",
      "display_name",
      "factors",
      "face_enrolled"
     ],
     "title": "MeResponse"
    },
    "OperatorAccount": {
     "properties": {
      "operator_id": {
       "type": "string",
       "title": "Operator Id"
      },
      "email": {
       "type": "string",
       "title": "Email"
      },
      "display_name": {
       "type": "string",
       "title": "Display Name"
      },
      "role": {
       "type": "string",
       "enum": [
        "viewer",
        "operator",
        "admin"
       ],
       "title": "Role"
      },
      "active": {
       "type": "boolean",
       "title": "Active"
      },
      "locked": {
       "type": "boolean",
       "title": "Locked"
      },
      "face_enrolled": {
       "type": "boolean",
       "title": "Face Enrolled"
      },
      "face_templates": {
       "type": "integer",
       "title": "Face Templates"
      },
      "biometric_consent_at": {
       "anyOf": [
        {
         "type": "string"
        },
        {
         "type": "null"
        }
       ],
       "title": "Biometric Consent At"
      },
      "last_login_at": {
       "anyOf": [
        {
         "type": "string"
        },
        {
         "type": "null"
        }
       ],
       "title": "Last Login At"
      },
      "created_at": {
       "type": "string",
       "title": "Created At"
      },
      "active_sessions": {
       "type": "integer",
       "title": "Active Sessions"
      }
     },
     "type": "object",
     "required": [
      "operator_id",
      "email",
      "display_name",
      "role",
      "active",
      "locked",
      "face_enrolled",
      "face_templates",
      "biometric_consent_at",
      "last_login_at",
      "created_at",
      "active_sessions"
     ],
     "title": "OperatorAccount"
    },
    "OperatorCreate": {
     "properties": {
      "email": {
       "type": "string",
       "maxLength": 254,
       "minLength": 3,
       "title": "Email"
      },
      "display_name": {
       "type": "string",
       "maxLength": 80,
       "minLength": 2,
       "title": "Display Name"
      },
      "role": {
       "type": "string",
       "enum": [
        "viewer",
        "operator",
        "admin"
       ],
       "title": "Role",
       "default": "viewer"
      },
      "password": {
       "type": "string",
       "maxLength": 128,
       "minLength": 1,
       "title": "Password",
       "description": "12 caractères minimum"
      }
     },
     "type": "object",
     "required": [
      "email",
      "display_name",
      "password"
     ],
     "title": "OperatorCreate",
     "examples": [
      {
       "display_name": "Léa (SOC)",
       "email": "lea.soc@orbe.test",
       "password": "un-mot-de-passe-solide",
       "role": "operator"
      }
     ]
    },
    "OperatorFaceRequest": {
     "properties": {
      "session_id": {
       "type": "string",
       "maxLength": 36,
       "minLength": 36,
       "title": "Session Id"
      },
      "frames": {
       "items": {
        "type": "string"
       },
       "type": "array",
       "maxItems": 20,
       "minItems": 1,
       "title": "Frames",
       "description": "Images JPEG encodées en base64, capturées par la caméra du navigateur"
      }
     },
     "type": "object",
     "required": [
      "session_id",
      "frames"
     ],
     "title": "OperatorFaceRequest"
    },
    "OperatorIdentifyRequest": {
     "properties": {
      "email": {
       "type": "string",
       "maxLength": 254,
       "minLength": 3,
       "title": "Email"
      }
     },
     "type": "object",
     "required": [
      "email"
     ],
     "title": "OperatorIdentifyRequest",
     "examples": [
      {
       "email": "ops@orbe.test"
      }
     ]
    },
    "OperatorLoginStep": {
     "properties": {
      "session_id": {
       "type": "string",
       "title": "Session Id"
      },
      "step": {
       "type": "string",
       "enum": [
        "face",
        "password"
       ],
       "title": "Step"
      },
      "face_challenge": {
       "anyOf": [
        {
         "$ref": "#/components/schemas/FaceChallenge"
        },
        {
         "type": "null"
        }
       ]
      },
      "face_enrollment_required": {
       "type": "boolean",
       "title": "Face Enrollment Required",
       "default": false
      },
      "expires_in": {
       "type": "integer",
       "title": "Expires In"
      }
     },
     "type": "object",
     "required": [
      "session_id",
      "step",
      "expires_in"
     ],
     "title": "OperatorLoginStep",
     "description": "Étape suivante de la connexion au back-office."
    },
    "OperatorMe": {
     "properties": {
      "operator_id": {
       "type": "string",
       "title": "Operator Id"
      },
      "email": {
       "type": "string",
       "title": "Email"
      },
      "display_name": {
       "type": "string",
       "title": "Display Name"
      },
      "role": {
       "type": "string",
       "enum": [
        "viewer",
        "operator",
        "admin"
       ],
       "title": "Role"
      },
      "session_id": {
       "type": "string",
       "title": "Session Id"
      },
      "expires_at": {
       "type": "string",
       "title": "Expires At"
      },
      "factors": {
       "items": {
        "type": "string"
       },
       "type": "array",
       "title": "Factors"
      }
     },
     "type": "object",
     "required": [
      "operator_id",
      "email",
      "display_name",
      "role",
      "session_id",
      "expires_at",
      "factors"
     ],
     "title": "OperatorMe"
    },
    "OperatorPasswordRequest": {
     "properties": {
      "session_id": {
       "type": "string",
       "maxLength": 36,
       "minLength": 36,
       "title": "Session Id"
      },
      "password": {
       "type": "string",
       "maxLength": 128,
       "minLength": 1,
       "title": "Password"
      }
     },
     "type": "object",
     "required": [
      "session_id",
      "password"
     ],
     "title": "OperatorPasswordRequest"
    },
    "OperatorPasswordReset": {
     "properties": {
      "password": {
       "type": "string",
       "maxLength": 128,
       "minLength": 1,
       "title": "Password",
       "description": "12 caractères minimum"
      }
     },
     "type": "object",
     "required": [
      "password"
     ],
     "title": "OperatorPasswordReset"
    },
    "OperatorTokenResponse": {
     "properties": {
      "access_token": {
       "type": "string",
       "title": "Access Token"
      },
      "token_type": {
       "type": "string",
       "const": "bearer",
       "title": "Token Type",
       "default": "bearer"
      },
      "expires_in": {
       "type": "integer",
       "title": "Expires In"
      },
      "role": {
       "type": "string",
       "enum": [
        "viewer",
        "operator",
        "admin"
       ],
       "title": "Role"
      },
      "face_enrollment_required": {
       "type": "boolean",
       "title": "Face Enrollment Required",
       "default": false
      }
     },
     "type": "object",
     "required": [
      "access_token",
      "expires_in",
      "role"
     ],
     "title": "OperatorTokenResponse"
    },
    "OperatorUpdate": {
     "properties": {
      "display_name": {
       "anyOf": [
        {
         "type": "string",
         "maxLength": 80,
         "minLength": 2
        },
        {
         "type": "null"
        }
       ],
       "title": "Display Name"
      },
      "role": {
       "anyOf": [
        {
         "type": "string",
         "enum": [
          "viewer",
          "operator",
          "admin"
         ]
        },
        {
         "type": "null"
        }
       ],
       "title": "Role"
      },
      "active": {
       "anyOf": [
        {
         "type": "boolean"
        },
        {
         "type": "null"
        }
       ],
       "title": "Active"
      }
     },
     "type": "object",
     "title": "OperatorUpdate"
    },
    "RegisterRequest": {
     "properties": {
      "email": {
       "type": "string",
       "maxLength": 254,
       "minLength": 3,
       "title": "Email"
      },
      "phone": {
       "type": "string",
       "maxLength": 24,
       "minLength": 8,
       "title": "Phone",
       "description": "Format français ou international"
      },
      "display_name": {
       "type": "string",
       "maxLength": 80,
       "minLength": 2,
       "title": "Display Name"
      },
      "password": {
       "type": "string",
       "maxLength": 128,
       "minLength": 1,
       "title": "Password",
       "description": "8 caractères minimum"
      }
     },
     "type": "object",
     "required": [
      "email",
      "phone",
      "display_name",
      "password"
     ],
     "title": "RegisterRequest",
     "examples": [
      {
       "display_name": "Nathan Moreau",
       "email": "nathan@orbe.test",
       "password": "correct-cheval-batterie",
       "phone": "06 12 34 56 75"
      }
     ]
    },
    "RegisterResponse": {
     "properties": {
      "client_id": {
       "type": "string",
       "title": "Client Id"
      },
      "email": {
       "type": "string",
       "title": "Email"
      },
      "phone_masked": {
       "type": "string",
       "title": "Phone Masked"
      },
      "display_name": {
       "type": "string",
       "title": "Display Name"
      }
     },
     "type": "object",
     "required": [
      "client_id",
      "email",
      "phone_masked",
      "display_name"
     ],
     "title": "RegisterResponse"
    },
    "TokenResponse": {
     "properties": {
      "access_token": {
       "type": "string",
       "title": "Access Token"
      },
      "token_type": {
       "type": "string",
       "const": "bearer",
       "title": "Token Type",
       "default": "bearer"
      },
      "expires_in": {
       "type": "integer",
       "title": "Expires In"
      },
      "factors": {
       "items": {
        "type": "string"
       },
       "type": "array",
       "title": "Factors"
      }
     },
     "type": "object",
     "required": [
      "access_token",
      "expires_in",
      "factors"
     ],
     "title": "TokenResponse"
    },
    "ValidationError": {
     "properties": {
      "loc": {
       "items": {
        "anyOf": [
         {
          "type": "string"
         },
         {
          "type": "integer"
         }
        ]
       },
       "type": "array",
       "title": "Location"
      },
      "msg": {
       "type": "string",
       "title": "Message"
      },
      "type": {
       "type": "string",
       "title": "Error Type"
      },
      "input": {
       "title": "Input"
      },
      "ctx": {
       "type": "object",
       "title": "Context"
      }
     },
     "type": "object",
     "required": [
      "loc",
      "msg",
      "type"
     ],
     "title": "ValidationError"
    },
    "VerifyResponse": {
     "properties": {
      "partner": {
       "type": "string",
       "title": "Partner"
      },
      "scopes": {
       "items": {
        "type": "string"
       },
       "type": "array",
       "title": "Scopes"
      }
     },
     "type": "object",
     "required": [
      "partner",
      "scopes"
     ],
     "title": "VerifyResponse"
    }
   },
   "securitySchemes": {
    "HTTPBearer": {
     "type": "http",
     "scheme": "bearer"
    }
   }
  },
  "tags": [
   {
    "name": "Authentification",
    "description": "Connexion en deux étapes (mot de passe, puis visage) et profil"
   },
   {
    "name": "Visage",
    "description": "Enrôlement et effacement du visage (consentement, RGPD art. 9)"
   },
   {
    "name": "Partenaires",
    "description": "Clés d'API des partenaires"
   },
   {
    "name": "Back-office",
    "description": "Connexion des opérateurs du dashboard (mot de passe seul)"
   }
  ],
  "servers": [
   {
    "url": "https://192.168.137.1/api/auth",
    "description": "Démonstrateur, à travers le WAF"
   },
   {
    "url": "http://localhost:8001",
    "description": "Service lancé en local"
   }
  ]
 },
 "bo-api": {
  "openapi": "3.1.0",
  "info": {
   "title": "Orbe — bo-api",
   "description": "API du back-office : alimente le dashboard de supervision (état des services, indicateurs, incidents, journaux, Grafana, assistant). **Lecture seule** : aucune route ne modifie la plateforme, sauf la gestion des habilitations (rôle admin).\n\n- Connexion : identifiant (`POST /bo/auth/identify`), visage par la caméra USB (`POST /bo/auth/face`), mot de passe (`POST /bo/auth/password`), puis `Authorization: Bearer <jeton>` sur toutes les autres routes.\n- Rôles : `admin` (habilitations), `viewer` (indicateurs agrégés) et `operator` (en plus : listes et fiches clients, opérations, demandes ; chaque consultation est journalisée).\n- Erreurs : `{\"detail\": {\"code\", \"message\"}}` ; un service interrogé indisponible renvoie `503 <service>_unavailable`.\n\nVoir CADRAGE §4.7.",
   "version": "0.1.0"
  },
  "paths": {
   "/bo/auth/identify": {
    "post": {
     "tags": [
      "Connexion"
     ],
     "summary": "Connexion — 1. identifiant",
     "description": "Renvoie la consigne de la caméra (`face_challenge`) : allumer la caméra USB, puis\n`POST /bo/auth/face`. `429 identification_locked` : attendre `Retry-After` secondes\n(visage non reconnu juste avant, LED rouge fixe).",
     "operationId": "identify_bo_auth_identify_post",
     "requestBody": {
      "content": {
       "application/json": {
        "schema": {
         "$ref": "#/components/schemas/IdentifyRequest"
        }
       }
      },
      "required": true
     },
     "responses": {
      "200": {
       "description": "Successful Response",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/LoginStep"
         }
        }
       }
      },
      "401": {
       "description": "Étape échouée ou expirée : recommencer l'identifiant",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "429": {
       "description": "Identification bloquée 30 s (en-tête Retry-After)",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "503": {
       "description": "auth-service ou reconnaissance faciale indisponible",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "423": {
       "description": "Compte bloqué",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "422": {
       "description": "Validation Error",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/HTTPValidationError"
         }
        }
       }
      }
     }
    }
   },
   "/bo/auth/face": {
    "post": {
     "tags": [
      "Connexion"
     ],
     "summary": "Connexion — 2. reconnaissance faciale",
     "description": "`frames` : `face_challenge.frames` images toutes les `interval_ms`. Reconnu : étape\n`password` (LED verte clignotante). Non reconnu : `401`, éteindre la caméra, vider\nl'identifiant ; nouvel essai après 30 s (LED rouge fixe).",
     "operationId": "face_bo_auth_face_post",
     "requestBody": {
      "content": {
       "application/json": {
        "schema": {
         "$ref": "#/components/schemas/FaceRequest"
        }
       }
      },
      "required": true
     },
     "responses": {
      "200": {
       "description": "Successful Response",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/LoginStep"
         }
        }
       }
      },
      "401": {
       "description": "Étape échouée ou expirée : recommencer l'identifiant",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "429": {
       "description": "Identification bloquée 30 s (en-tête Retry-After)",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "503": {
       "description": "auth-service ou reconnaissance faciale indisponible",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "422": {
       "description": "Validation Error",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/HTTPValidationError"
         }
        }
       }
      }
     }
    }
   },
   "/bo/auth/password": {
    "post": {
     "tags": [
      "Connexion"
     ],
     "summary": "Connexion — 3. mot de passe",
     "description": "Correct : jeton (1 h), LED verte fixe 30 s, le back-office est disponible. Faux :\n`401`, LED rouge clignotante 10 fois, tout recommence à l'identifiant.",
     "operationId": "password_bo_auth_password_post",
     "requestBody": {
      "content": {
       "application/json": {
        "schema": {
         "$ref": "#/components/schemas/PasswordRequest"
        }
       }
      },
      "required": true
     },
     "responses": {
      "200": {
       "description": "Successful Response",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/TokenResponse"
         }
        }
       }
      },
      "401": {
       "description": "Étape échouée ou expirée : recommencer l'identifiant",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "429": {
       "description": "Identification bloquée 30 s (en-tête Retry-After)",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "503": {
       "description": "auth-service ou reconnaissance faciale indisponible",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "422": {
       "description": "Validation Error",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/HTTPValidationError"
         }
        }
       }
      }
     }
    }
   },
   "/bo/auth/enroll-face": {
    "post": {
     "tags": [
      "Connexion"
     ],
     "summary": "Démarrage : le premier administrateur enregistre son visage",
     "description": "Seulement avec le jeton reçu quand `face_enrollment_required` vaut `true` (aucun\nopérateur n'a encore de visage). Ensuite, se reconnecter avec le visage.",
     "operationId": "enroll_face_bo_auth_enroll_face_post",
     "requestBody": {
      "content": {
       "application/json": {
        "schema": {
         "$ref": "#/components/schemas/EnrollRequest"
        }
       }
      },
      "required": true
     },
     "responses": {
      "201": {
       "description": "Successful Response",
       "content": {
        "application/json": {
         "schema": {}
        }
       }
      },
      "401": {
       "description": "Jeton d'enrôlement absent ou expiré",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "422": {
       "description": "Validation Error",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/HTTPValidationError"
         }
        }
       }
      }
     },
     "security": [
      {
       "HTTPBearer": []
      }
     ]
    }
   },
   "/bo/auth/logout": {
    "post": {
     "tags": [
      "Connexion"
     ],
     "summary": "Se déconnecter (révoque la session)",
     "operationId": "logout_bo_auth_logout_post",
     "responses": {
      "204": {
       "description": "Successful Response"
      },
      "401": {
       "description": "Session invalide ou expirée",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      }
     },
     "security": [
      {
       "HTTPBearer": []
      }
     ]
    }
   },
   "/bo/auth/me": {
    "get": {
     "tags": [
      "Connexion"
     ],
     "summary": "Opérateur connecté",
     "operationId": "me_bo_auth_me_get",
     "responses": {
      "200": {
       "description": "Successful Response",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/MeResponse"
         }
        }
       }
      },
      "401": {
       "description": "Jeton absent, invalide ou révoqué",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      }
     },
     "security": [
      {
       "HTTPBearer": []
      }
     ]
    }
   },
   "/bo/admin/operators": {
    "get": {
     "tags": [
      "Habilitations"
     ],
     "summary": "Opérateurs",
     "operationId": "list_operators_bo_admin_operators_get",
     "responses": {
      "200": {
       "description": "Successful Response",
       "content": {
        "application/json": {
         "schema": {
          "items": {
           "$ref": "#/components/schemas/Account"
          },
          "type": "array",
          "title": "Response List Operators Bo Admin Operators Get"
         }
        }
       }
      },
      "401": {
       "description": "Jeton absent, invalide ou révoqué",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "403": {
       "description": "Réservé au rôle « admin »",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "404": {
       "description": "Opérateur inconnu",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      }
     },
     "security": [
      {
       "HTTPBearer": []
      }
     ]
    },
    "post": {
     "tags": [
      "Habilitations"
     ],
     "summary": "Créer",
     "operationId": "create_operator_bo_admin_operators_post",
     "requestBody": {
      "content": {
       "application/json": {
        "schema": {
         "$ref": "#/components/schemas/AccountCreate"
        }
       }
      },
      "required": true
     },
     "responses": {
      "201": {
       "description": "Successful Response",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/Account"
         }
        }
       }
      },
      "401": {
       "description": "Jeton absent, invalide ou révoqué",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "403": {
       "description": "Réservé au rôle « admin »",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "404": {
       "description": "Opérateur inconnu",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "422": {
       "description": "Validation Error",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/HTTPValidationError"
         }
        }
       }
      }
     },
     "security": [
      {
       "HTTPBearer": []
      }
     ]
    }
   },
   "/bo/admin/operators/{operator_id}": {
    "patch": {
     "tags": [
      "Habilitations"
     ],
     "summary": "Nom, rôle, activation",
     "operationId": "update_operator_bo_admin_operators__operator_id__patch",
     "security": [
      {
       "HTTPBearer": []
      }
     ],
     "parameters": [
      {
       "name": "operator_id",
       "in": "path",
       "required": true,
       "schema": {
        "type": "string",
        "pattern": "^[0-9a-f-]{36}$",
        "title": "Operator Id"
       }
      }
     ],
     "requestBody": {
      "required": true,
      "content": {
       "application/json": {
        "schema": {
         "$ref": "#/components/schemas/AccountUpdate"
        }
       }
      }
     },
     "responses": {
      "200": {
       "description": "Successful Response",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/Account"
         }
        }
       }
      },
      "401": {
       "description": "Jeton absent, invalide ou révoqué",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "403": {
       "description": "Réservé au rôle « admin »",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "404": {
       "description": "Opérateur inconnu",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "422": {
       "description": "Validation Error",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/HTTPValidationError"
         }
        }
       }
      }
     }
    }
   },
   "/bo/admin/operators/{operator_id}/password": {
    "post": {
     "tags": [
      "Habilitations"
     ],
     "summary": "Nouveau mot de passe",
     "operationId": "reset_password_bo_admin_operators__operator_id__password_post",
     "security": [
      {
       "HTTPBearer": []
      }
     ],
     "parameters": [
      {
       "name": "operator_id",
       "in": "path",
       "required": true,
       "schema": {
        "type": "string",
        "pattern": "^[0-9a-f-]{36}$",
        "title": "Operator Id"
       }
      }
     ],
     "requestBody": {
      "required": true,
      "content": {
       "application/json": {
        "schema": {
         "$ref": "#/components/schemas/PasswordReset"
        }
       }
      }
     },
     "responses": {
      "204": {
       "description": "Successful Response"
      },
      "401": {
       "description": "Jeton absent, invalide ou révoqué",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "403": {
       "description": "Réservé au rôle « admin »",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "404": {
       "description": "Opérateur inconnu",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "422": {
       "description": "Validation Error",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/HTTPValidationError"
         }
        }
       }
      }
     }
    }
   },
   "/bo/admin/operators/{operator_id}/unlock": {
    "post": {
     "tags": [
      "Habilitations"
     ],
     "summary": "Débloquer",
     "operationId": "unlock_bo_admin_operators__operator_id__unlock_post",
     "security": [
      {
       "HTTPBearer": []
      }
     ],
     "parameters": [
      {
       "name": "operator_id",
       "in": "path",
       "required": true,
       "schema": {
        "type": "string",
        "pattern": "^[0-9a-f-]{36}$",
        "title": "Operator Id"
       }
      }
     ],
     "responses": {
      "200": {
       "description": "Successful Response",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/Account"
         }
        }
       }
      },
      "401": {
       "description": "Jeton absent, invalide ou révoqué",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "403": {
       "description": "Réservé au rôle « admin »",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "404": {
       "description": "Opérateur inconnu",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "422": {
       "description": "Validation Error",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/HTTPValidationError"
         }
        }
       }
      }
     }
    }
   },
   "/bo/admin/operators/{operator_id}/sessions": {
    "delete": {
     "tags": [
      "Habilitations"
     ],
     "summary": "Révoquer ses sessions",
     "operationId": "revoke_sessions_bo_admin_operators__operator_id__sessions_delete",
     "security": [
      {
       "HTTPBearer": []
      }
     ],
     "parameters": [
      {
       "name": "operator_id",
       "in": "path",
       "required": true,
       "schema": {
        "type": "string",
        "pattern": "^[0-9a-f-]{36}$",
        "title": "Operator Id"
       }
      }
     ],
     "responses": {
      "204": {
       "description": "Successful Response"
      },
      "401": {
       "description": "Jeton absent, invalide ou révoqué",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "403": {
       "description": "Réservé au rôle « admin »",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "404": {
       "description": "Opérateur inconnu",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "422": {
       "description": "Validation Error",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/HTTPValidationError"
         }
        }
       }
      }
     }
    }
   },
   "/bo/admin/operators/{operator_id}/face": {
    "post": {
     "tags": [
      "Habilitations"
     ],
     "summary": "Enregistrer le visage (opérateur devant la caméra, consentement)",
     "description": "~16 images pendant que l'opérateur tourne lentement la tête de gauche à droite.",
     "operationId": "enroll_face_bo_admin_operators__operator_id__face_post",
     "security": [
      {
       "HTTPBearer": []
      }
     ],
     "parameters": [
      {
       "name": "operator_id",
       "in": "path",
       "required": true,
       "schema": {
        "type": "string",
        "pattern": "^[0-9a-f-]{36}$",
        "title": "Operator Id"
       }
      }
     ],
     "requestBody": {
      "required": true,
      "content": {
       "application/json": {
        "schema": {
         "$ref": "#/components/schemas/EnrollRequest"
        }
       }
      }
     },
     "responses": {
      "201": {
       "description": "Successful Response",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/Account"
         }
        }
       }
      },
      "401": {
       "description": "Jeton absent, invalide ou révoqué",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "403": {
       "description": "Réservé au rôle « admin »",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "404": {
       "description": "Opérateur inconnu",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "422": {
       "description": "Validation Error",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/HTTPValidationError"
         }
        }
       }
      }
     }
    },
    "delete": {
     "tags": [
      "Habilitations"
     ],
     "summary": "Effacer le visage",
     "operationId": "erase_face_bo_admin_operators__operator_id__face_delete",
     "security": [
      {
       "HTTPBearer": []
      }
     ],
     "parameters": [
      {
       "name": "operator_id",
       "in": "path",
       "required": true,
       "schema": {
        "type": "string",
        "pattern": "^[0-9a-f-]{36}$",
        "title": "Operator Id"
       }
      }
     ],
     "responses": {
      "200": {
       "description": "Successful Response",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/Account"
         }
        }
       }
      },
      "401": {
       "description": "Jeton absent, invalide ou révoqué",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "403": {
       "description": "Réservé au rôle « admin »",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "404": {
       "description": "Opérateur inconnu",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "422": {
       "description": "Validation Error",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/HTTPValidationError"
         }
        }
       }
      }
     }
    }
   },
   "/bo/supervision/overview": {
    "get": {
     "tags": [
      "Supervision"
     ],
     "summary": "État général et indicateurs",
     "description": "Badge d'état, bannière et les 6 indicateurs de la page Supervision.",
     "operationId": "overview_bo_supervision_overview_get",
     "responses": {
      "200": {
       "description": "Successful Response",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/Overview"
         }
        }
       }
      },
      "401": {
       "description": "Jeton absent, invalide ou révoqué",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      }
     },
     "security": [
      {
       "HTTPBearer": []
      }
     ]
    }
   },
   "/bo/supervision/services": {
    "get": {
     "tags": [
      "Supervision"
     ],
     "summary": "État des services",
     "description": "Une carte par service : `ok`, `warn`, `down`, `restored` (rétabli par la remédiation)\nou `unknown` (pas de mesure).",
     "operationId": "services_bo_supervision_services_get",
     "responses": {
      "200": {
       "description": "Successful Response",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ServicesOut"
         }
        }
       }
      },
      "401": {
       "description": "Jeton absent, invalide ou révoqué",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      }
     },
     "security": [
      {
       "HTTPBearer": []
      }
     ]
    }
   },
   "/bo/supervision/series": {
    "get": {
     "tags": [
      "Supervision"
     ],
     "summary": "Courbes : latence, score d'anomalie, transactions",
     "description": "Une mesure par minute. `incident` marque les minutes de l'incident en cours ou du\ndernier incident (bornes x1 / x2 pour la zone grisée des graphiques).",
     "operationId": "series_bo_supervision_series_get",
     "security": [
      {
       "HTTPBearer": []
      }
     ],
     "parameters": [
      {
       "name": "minutes",
       "in": "query",
       "required": false,
       "schema": {
        "type": "integer",
        "maximum": 360,
        "minimum": 5,
        "description": "fenêtre, une mesure par minute",
        "default": 30,
        "title": "Minutes"
       },
       "description": "fenêtre, une mesure par minute"
      }
     ],
     "responses": {
      "200": {
       "description": "Successful Response",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/SupervisionSeries"
         }
        }
       }
      },
      "401": {
       "description": "Jeton absent, invalide ou révoqué",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "422": {
       "description": "Validation Error",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/HTTPValidationError"
         }
        }
       }
      }
     }
    }
   },
   "/bo/supervision/resources": {
    "get": {
     "tags": [
      "Supervision"
     ],
     "summary": "Ressources du PC Hôte",
     "description": "CPU, mémoire, disque et réseau entrant (node-exporter).",
     "operationId": "resources_bo_supervision_resources_get",
     "responses": {
      "200": {
       "description": "Successful Response",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ResourcesOut"
         }
        }
       }
      },
      "401": {
       "description": "Jeton absent, invalide ou révoqué",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      }
     },
     "security": [
      {
       "HTTPBearer": []
      }
     ]
    }
   },
   "/bo/supervision/logs": {
    "get": {
     "tags": [
      "Supervision"
     ],
     "summary": "Derniers journaux",
     "description": "Journaux des services (Loki), plus récents d'abord. Les identifiants, adresses IP et\nemails sont retirés : seuls l'événement et quelques champs techniques sont affichés.",
     "operationId": "logs_bo_supervision_logs_get",
     "security": [
      {
       "HTTPBearer": []
      }
     ],
     "parameters": [
      {
       "name": "level",
       "in": "query",
       "required": false,
       "schema": {
        "enum": [
         "all",
         "warn",
         "error"
        ],
        "type": "string",
        "default": "all",
        "title": "Level"
       }
      },
      {
       "name": "source",
       "in": "query",
       "required": false,
       "schema": {
        "anyOf": [
         {
          "type": "string",
          "maxLength": 40,
          "pattern": "^[a-z0-9-]+$"
         },
         {
          "type": "null"
         }
        ],
        "title": "Source"
       }
      },
      {
       "name": "minutes",
       "in": "query",
       "required": false,
       "schema": {
        "type": "integer",
        "maximum": 60,
        "minimum": 1,
        "default": 15,
        "title": "Minutes"
       }
      },
      {
       "name": "limit",
       "in": "query",
       "required": false,
       "schema": {
        "type": "integer",
        "maximum": 200,
        "minimum": 1,
        "default": 100,
        "title": "Limit"
       }
      },
      {
       "name": "hide_requests",
       "in": "query",
       "required": false,
       "schema": {
        "type": "boolean",
        "description": "masquer les journaux d'accès HTTP",
        "default": true,
        "title": "Hide Requests"
       },
       "description": "masquer les journaux d'accès HTTP"
      }
     ],
     "responses": {
      "200": {
       "description": "Successful Response",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/LogsOut"
         }
        }
       }
      },
      "401": {
       "description": "Jeton absent, invalide ou révoqué",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "422": {
       "description": "Validation Error",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/HTTPValidationError"
         }
        }
       }
      }
     }
    }
   },
   "/bo/data/summary": {
    "get": {
     "tags": [
      "Données applicatives"
     ],
     "summary": "Indicateurs de l'application",
     "description": "Clients, opérations des dernières 24 h et 7 jours, demandes d'argent, soldes.\nHors comptes de la sonde.",
     "operationId": "summary_bo_data_summary_get",
     "responses": {
      "200": {
       "description": "Successful Response",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/Summary"
         }
        }
       }
      },
      "401": {
       "description": "Jeton absent, invalide ou révoqué",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "503": {
       "description": "Base de données indisponible",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      }
     },
     "security": [
      {
       "HTTPBearer": []
      }
     ]
    }
   },
   "/bo/data/series": {
    "get": {
     "tags": [
      "Données applicatives"
     ],
     "summary": "Évolution dans le temps",
     "description": "`hour` : 24 dernières heures ; `day` : 30 derniers jours. `amount` = montants des\npaiements autorisés (centimes) ; `declines` = paiements refusés ; `transactions` = toutes\nles opérations ; `registrations` = inscriptions. Hors comptes de la sonde.",
     "operationId": "series_bo_data_series_get",
     "security": [
      {
       "HTTPBearer": []
      }
     ],
     "parameters": [
      {
       "name": "metric",
       "in": "query",
       "required": false,
       "schema": {
        "enum": [
         "transactions",
         "amount",
         "declines",
         "registrations"
        ],
        "type": "string",
        "default": "transactions",
        "title": "Metric"
       }
      },
      {
       "name": "interval",
       "in": "query",
       "required": false,
       "schema": {
        "enum": [
         "hour",
         "day"
        ],
        "type": "string",
        "default": "hour",
        "title": "Interval"
       }
      }
     ],
     "responses": {
      "200": {
       "description": "Successful Response",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/Series"
         }
        }
       }
      },
      "401": {
       "description": "Jeton absent, invalide ou révoqué",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "503": {
       "description": "Base de données indisponible",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "422": {
       "description": "Validation Error",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/HTTPValidationError"
         }
        }
       }
      }
     }
    }
   },
   "/bo/data/ledger/check": {
    "get": {
     "tags": [
      "Données applicatives"
     ],
     "summary": "Contrôle de cohérence comptable",
     "description": "Partie double : chaque opération a autant de débits que de crédits, chaque solde est\nla somme de ses écritures, aucun client n'est à découvert, une opération autorisée a\nexactement 2 écritures et une opération refusée aucune. Porte sur toute la base.",
     "operationId": "ledger_check_bo_data_ledger_check_get",
     "responses": {
      "200": {
       "description": "Successful Response",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/LedgerCheck"
         }
        }
       }
      },
      "401": {
       "description": "Jeton absent, invalide ou révoqué",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "503": {
       "description": "Base de données indisponible",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      }
     },
     "security": [
      {
       "HTTPBearer": []
      }
     ]
    }
   },
   "/bo/data/transactions": {
    "get": {
     "tags": [
      "Données applicatives"
     ],
     "summary": "Opérations",
     "description": "Plus récentes d'abord. Hors comptes de la sonde.",
     "operationId": "list_transactions_bo_data_transactions_get",
     "security": [
      {
       "HTTPBearer": []
      }
     ],
     "parameters": [
      {
       "name": "type",
       "in": "query",
       "required": false,
       "schema": {
        "anyOf": [
         {
          "enum": [
           "payment",
           "refund",
           "payout"
          ],
          "type": "string"
         },
         {
          "type": "null"
         }
        ],
        "title": "Type"
       }
      },
      {
       "name": "status",
       "in": "query",
       "required": false,
       "schema": {
        "anyOf": [
         {
          "type": "string",
          "maxLength": 16
         },
         {
          "type": "null"
         }
        ],
        "title": "Status"
       }
      },
      {
       "name": "client_id",
       "in": "query",
       "required": false,
       "schema": {
        "anyOf": [
         {
          "type": "string",
          "maxLength": 36
         },
         {
          "type": "null"
         }
        ],
        "description": "payeur ou bénéficiaire",
        "title": "Client Id"
       },
       "description": "payeur ou bénéficiaire"
      },
      {
       "name": "reference",
       "in": "query",
       "required": false,
       "schema": {
        "anyOf": [
         {
          "type": "string",
          "maxLength": 11
         },
         {
          "type": "null"
         }
        ],
        "title": "Reference"
       }
      },
      {
       "name": "date_from",
       "in": "query",
       "required": false,
       "schema": {
        "anyOf": [
         {
          "type": "string",
          "format": "date-time"
         },
         {
          "type": "null"
         }
        ],
        "description": "UTC, inclus",
        "title": "Date From"
       },
       "description": "UTC, inclus"
      },
      {
       "name": "date_to",
       "in": "query",
       "required": false,
       "schema": {
        "anyOf": [
         {
          "type": "string",
          "format": "date-time"
         },
         {
          "type": "null"
         }
        ],
        "description": "UTC, exclu",
        "title": "Date To"
       },
       "description": "UTC, exclu"
      },
      {
       "name": "page",
       "in": "query",
       "required": false,
       "schema": {
        "type": "integer",
        "minimum": 1,
        "default": 1,
        "title": "Page"
       }
      },
      {
       "name": "size",
       "in": "query",
       "required": false,
       "schema": {
        "type": "integer",
        "minimum": 1,
        "default": 25,
        "title": "Size"
       }
      }
     ],
     "responses": {
      "200": {
       "description": "Successful Response",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/TransactionPage"
         }
        }
       }
      },
      "401": {
       "description": "Jeton absent, invalide ou révoqué",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "403": {
       "description": "Réservé au rôle « operator »",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "503": {
       "description": "Base de données indisponible",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "422": {
       "description": "Validation Error",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/HTTPValidationError"
         }
        }
       }
      }
     }
    }
   },
   "/bo/data/transactions/{reference}": {
    "get": {
     "tags": [
      "Données applicatives"
     ],
     "summary": "Détail d'une opération",
     "description": "Avec ses écritures comptables, le paiement d'origine ou le remboursement, la demande\nd'argent réglée et le compte lié d'un retrait.",
     "operationId": "transaction_detail_bo_data_transactions__reference__get",
     "security": [
      {
       "HTTPBearer": []
      }
     ],
     "parameters": [
      {
       "name": "reference",
       "in": "path",
       "required": true,
       "schema": {
        "type": "string",
        "title": "Reference"
       }
      }
     ],
     "responses": {
      "200": {
       "description": "Successful Response",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/TransactionDetail"
         }
        }
       }
      },
      "401": {
       "description": "Jeton absent, invalide ou révoqué",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "403": {
       "description": "Réservé au rôle « operator »",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "503": {
       "description": "Base de données indisponible",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "404": {
       "description": "Opération inconnue",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "422": {
       "description": "Validation Error",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/HTTPValidationError"
         }
        }
       }
      }
     }
    }
   },
   "/bo/data/clients": {
    "get": {
     "tags": [
      "Données applicatives"
     ],
     "summary": "Clients",
     "description": "Email et téléphone toujours masqués. Recherche par nom seulement (pas par email ni\ntéléphone : on ne pourrait pas s'en servir pour retrouver une valeur masquée). Plus récents\nd'abord, hors comptes de la sonde.",
     "operationId": "list_clients_bo_data_clients_get",
     "security": [
      {
       "HTTPBearer": []
      }
     ],
     "parameters": [
      {
       "name": "q",
       "in": "query",
       "required": false,
       "schema": {
        "anyOf": [
         {
          "type": "string",
          "maxLength": 80
         },
         {
          "type": "null"
         }
        ],
        "description": "nom affiché (contient)",
        "title": "Q"
       },
       "description": "nom affiché (contient)"
      },
      {
       "name": "locked",
       "in": "query",
       "required": false,
       "schema": {
        "anyOf": [
         {
          "type": "boolean"
         },
         {
          "type": "null"
         }
        ],
        "title": "Locked"
       }
      },
      {
       "name": "face_enrolled",
       "in": "query",
       "required": false,
       "schema": {
        "anyOf": [
         {
          "type": "boolean"
         },
         {
          "type": "null"
         }
        ],
        "title": "Face Enrolled"
       }
      },
      {
       "name": "page",
       "in": "query",
       "required": false,
       "schema": {
        "type": "integer",
        "minimum": 1,
        "default": 1,
        "title": "Page"
       }
      },
      {
       "name": "size",
       "in": "query",
       "required": false,
       "schema": {
        "type": "integer",
        "minimum": 1,
        "default": 25,
        "title": "Size"
       }
      }
     ],
     "responses": {
      "200": {
       "description": "Successful Response",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ClientPage"
         }
        }
       }
      },
      "401": {
       "description": "Jeton absent, invalide ou révoqué",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "403": {
       "description": "Réservé au rôle « operator »",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "503": {
       "description": "Base de données indisponible",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "422": {
       "description": "Validation Error",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/HTTPValidationError"
         }
        }
       }
      }
     }
    }
   },
   "/bo/data/clients/{client_id}": {
    "get": {
     "tags": [
      "Données applicatives"
     ],
     "summary": "Fiche client",
     "description": "Comptes liés (4 derniers caractères de l'IBAN), sessions actives, demandes en attente\net 20 dernières opérations.",
     "operationId": "client_detail_bo_data_clients__client_id__get",
     "security": [
      {
       "HTTPBearer": []
      }
     ],
     "parameters": [
      {
       "name": "client_id",
       "in": "path",
       "required": true,
       "schema": {
        "type": "string",
        "title": "Client Id"
       }
      }
     ],
     "responses": {
      "200": {
       "description": "Successful Response",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ClientDetail"
         }
        }
       }
      },
      "401": {
       "description": "Jeton absent, invalide ou révoqué",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "403": {
       "description": "Réservé au rôle « operator »",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "503": {
       "description": "Base de données indisponible",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "404": {
       "description": "Client inconnu",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "422": {
       "description": "Validation Error",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/HTTPValidationError"
         }
        }
       }
      }
     }
    }
   },
   "/bo/data/requests": {
    "get": {
     "tags": [
      "Données applicatives"
     ],
     "summary": "Demandes d'argent",
     "description": "Plus récentes d'abord, hors comptes de la sonde.",
     "operationId": "list_requests_bo_data_requests_get",
     "security": [
      {
       "HTTPBearer": []
      }
     ],
     "parameters": [
      {
       "name": "status",
       "in": "query",
       "required": false,
       "schema": {
        "anyOf": [
         {
          "enum": [
           "pending",
           "paid",
           "declined",
           "cancelled",
           "expired",
           "failed"
          ],
          "type": "string"
         },
         {
          "type": "null"
         }
        ],
        "title": "Status"
       }
      },
      {
       "name": "client_id",
       "in": "query",
       "required": false,
       "schema": {
        "anyOf": [
         {
          "type": "string",
          "maxLength": 36
         },
         {
          "type": "null"
         }
        ],
        "description": "demandeur ou payeur",
        "title": "Client Id"
       },
       "description": "demandeur ou payeur"
      },
      {
       "name": "page",
       "in": "query",
       "required": false,
       "schema": {
        "type": "integer",
        "minimum": 1,
        "default": 1,
        "title": "Page"
       }
      },
      {
       "name": "size",
       "in": "query",
       "required": false,
       "schema": {
        "type": "integer",
        "minimum": 1,
        "default": 25,
        "title": "Size"
       }
      }
     ],
     "responses": {
      "200": {
       "description": "Successful Response",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/RequestPage"
         }
        }
       }
      },
      "401": {
       "description": "Jeton absent, invalide ou révoqué",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "403": {
       "description": "Réservé au rôle « operator »",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "503": {
       "description": "Base de données indisponible",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "422": {
       "description": "Validation Error",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/HTTPValidationError"
         }
        }
       }
      }
     }
    }
   },
   "/bo/incidents": {
    "get": {
     "tags": [
      "Incidents, assistant et Grafana"
     ],
     "summary": "Incidents (moteur de remédiation)",
     "description": "Liste du moteur de remédiation, relayée telle quelle (format défini par le moteur).",
     "operationId": "incidents_bo_incidents_get",
     "security": [
      {
       "HTTPBearer": []
      }
     ],
     "parameters": [
      {
       "name": "limit",
       "in": "query",
       "required": false,
       "schema": {
        "type": "integer",
        "maximum": 100,
        "minimum": 1,
        "default": 20,
        "title": "Limit"
       }
      }
     ],
     "responses": {
      "200": {
       "description": "Successful Response",
       "content": {
        "application/json": {
         "schema": {
          "title": "Response Incidents Bo Incidents Get"
         }
        }
       }
      },
      "401": {
       "description": "Jeton absent, invalide ou révoqué",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "503": {
       "description": "Service interrogé indisponible",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "422": {
       "description": "Validation Error",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/HTTPValidationError"
         }
        }
       }
      }
     }
    }
   },
   "/bo/incidents/{incident_id}": {
    "get": {
     "tags": [
      "Incidents, assistant et Grafana"
     ],
     "summary": "Détail d'un incident : étapes, actions, vérification",
     "operationId": "incident_bo_incidents__incident_id__get",
     "security": [
      {
       "HTTPBearer": []
      }
     ],
     "parameters": [
      {
       "name": "incident_id",
       "in": "path",
       "required": true,
       "schema": {
        "type": "string",
        "maxLength": 40,
        "pattern": "^[A-Za-z0-9_-]+$",
        "title": "Incident Id"
       }
      }
     ],
     "responses": {
      "200": {
       "description": "Successful Response",
       "content": {
        "application/json": {
         "schema": {
          "title": "Response Incident Bo Incidents  Incident Id  Get"
         }
        }
       }
      },
      "401": {
       "description": "Jeton absent, invalide ou révoqué",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "503": {
       "description": "Service interrogé indisponible",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "404": {
       "description": "Incident inconnu",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "422": {
       "description": "Validation Error",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/HTTPValidationError"
         }
        }
       }
      }
     }
    }
   },
   "/bo/assistant/ask": {
    "post": {
     "tags": [
      "Incidents, assistant et Grafana"
     ],
     "summary": "Poser une question à l'assistant opérateur",
     "description": "Relayée à assistant-rag (`POST /ask`), qui répond à partir de la documentation et\ncite ses sources. Peut prendre plusieurs secondes (modèle local).",
     "operationId": "ask_bo_assistant_ask_post",
     "requestBody": {
      "content": {
       "application/json": {
        "schema": {
         "$ref": "#/components/schemas/AskRequest"
        }
       }
      },
      "required": true
     },
     "responses": {
      "200": {
       "description": "Successful Response",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/AskResponse"
         }
        }
       }
      },
      "401": {
       "description": "Jeton absent, invalide ou révoqué",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "503": {
       "description": "Service interrogé indisponible",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "403": {
       "description": "Réservé au rôle « operator »",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "429": {
       "description": "Trop de questions (en-tête Retry-After)",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "422": {
       "description": "Validation Error",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/HTTPValidationError"
         }
        }
       }
      }
     },
     "security": [
      {
       "HTTPBearer": []
      }
     ]
    }
   },
   "/bo/grafana": {
    "get": {
     "tags": [
      "Incidents, assistant et Grafana"
     ],
     "summary": "Liens Grafana et panneaux à intégrer",
     "description": "`panels[].embed_url` se place dans une `<iframe>` (Grafana autorise l'intégration et\nl'accès anonyme en lecture seule). `tools` remplace les liens codés en dur de la barre\nlatérale.",
     "operationId": "grafana_bo_grafana_get",
     "responses": {
      "200": {
       "description": "Successful Response",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/GrafanaOut"
         }
        }
       }
      },
      "401": {
       "description": "Jeton absent, invalide ou révoqué",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      }
     },
     "security": [
      {
       "HTTPBearer": []
      }
     ]
    }
   }
  },
  "components": {
   "schemas": {
    "Account": {
     "properties": {
      "operator_id": {
       "type": "string",
       "title": "Operator Id"
      },
      "email": {
       "type": "string",
       "title": "Email"
      },
      "display_name": {
       "type": "string",
       "title": "Display Name"
      },
      "role": {
       "type": "string",
       "enum": [
        "viewer",
        "operator",
        "admin"
       ],
       "title": "Role"
      },
      "active": {
       "type": "boolean",
       "title": "Active"
      },
      "locked": {
       "type": "boolean",
       "title": "Locked"
      },
      "face_enrolled": {
       "type": "boolean",
       "title": "Face Enrolled"
      },
      "face_templates": {
       "type": "integer",
       "title": "Face Templates"
      },
      "biometric_consent_at": {
       "anyOf": [
        {
         "type": "string"
        },
        {
         "type": "null"
        }
       ],
       "title": "Biometric Consent At"
      },
      "last_login_at": {
       "anyOf": [
        {
         "type": "string"
        },
        {
         "type": "null"
        }
       ],
       "title": "Last Login At"
      },
      "created_at": {
       "type": "string",
       "title": "Created At"
      },
      "active_sessions": {
       "type": "integer",
       "title": "Active Sessions"
      }
     },
     "type": "object",
     "required": [
      "operator_id",
      "email",
      "display_name",
      "role",
      "active",
      "locked",
      "face_enrolled",
      "face_templates",
      "biometric_consent_at",
      "last_login_at",
      "created_at",
      "active_sessions"
     ],
     "title": "Account"
    },
    "AccountCreate": {
     "properties": {
      "email": {
       "type": "string",
       "maxLength": 254,
       "minLength": 3,
       "title": "Email"
      },
      "display_name": {
       "type": "string",
       "maxLength": 80,
       "minLength": 2,
       "title": "Display Name"
      },
      "role": {
       "type": "string",
       "enum": [
        "viewer",
        "operator",
        "admin"
       ],
       "title": "Role",
       "default": "viewer"
      },
      "password": {
       "type": "string",
       "maxLength": 128,
       "minLength": 1,
       "title": "Password",
       "description": "12 caractères minimum"
      }
     },
     "type": "object",
     "required": [
      "email",
      "display_name",
      "password"
     ],
     "title": "AccountCreate"
    },
    "AccountMismatch": {
     "properties": {
      "account_id": {
       "type": "string",
       "title": "Account Id"
      },
      "label": {
       "type": "string",
       "title": "Label"
      },
      "balance_cents": {
       "type": "integer",
       "title": "Balance Cents"
      },
      "computed_cents": {
       "type": "integer",
       "title": "Computed Cents"
      }
     },
     "type": "object",
     "required": [
      "account_id",
      "label",
      "balance_cents",
      "computed_cents"
     ],
     "title": "AccountMismatch"
    },
    "AccountUpdate": {
     "properties": {
      "display_name": {
       "anyOf": [
        {
         "type": "string",
         "maxLength": 80,
         "minLength": 2
        },
        {
         "type": "null"
        }
       ],
       "title": "Display Name"
      },
      "role": {
       "anyOf": [
        {
         "type": "string",
         "enum": [
          "viewer",
          "operator",
          "admin"
         ]
        },
        {
         "type": "null"
        }
       ],
       "title": "Role"
      },
      "active": {
       "anyOf": [
        {
         "type": "boolean"
        },
        {
         "type": "null"
        }
       ],
       "title": "Active"
      }
     },
     "type": "object",
     "title": "AccountUpdate"
    },
    "AskRequest": {
     "properties": {
      "question": {
       "type": "string",
       "maxLength": 2000,
       "minLength": 3,
       "title": "Question"
      }
     },
     "type": "object",
     "required": [
      "question"
     ],
     "title": "AskRequest"
    },
    "AskResponse": {
     "properties": {
      "answer": {
       "type": "string",
       "title": "Answer"
      },
      "sources": {
       "items": {
        "$ref": "#/components/schemas/AskSource"
       },
       "type": "array",
       "title": "Sources"
      }
     },
     "type": "object",
     "required": [
      "answer",
      "sources"
     ],
     "title": "AskResponse"
    },
    "AskSource": {
     "properties": {
      "doc": {
       "type": "string",
       "title": "Doc"
      },
      "extrait": {
       "type": "string",
       "title": "Extrait"
      }
     },
     "type": "object",
     "required": [
      "doc",
      "extrait"
     ],
     "title": "AskSource"
    },
    "BalancesSummary": {
     "properties": {
      "clients_total_cents": {
       "type": "integer",
       "title": "Clients Total Cents"
      },
      "counterparts_cents": {
       "additionalProperties": {
        "type": "integer"
       },
       "type": "object",
       "title": "Counterparts Cents"
      }
     },
     "type": "object",
     "required": [
      "clients_total_cents",
      "counterparts_cents"
     ],
     "title": "BalancesSummary"
    },
    "Banner": {
     "properties": {
      "tone": {
       "type": "string",
       "enum": [
        "ok",
        "warn",
        "danger",
        "unknown"
       ],
       "title": "Tone"
      },
      "text": {
       "type": "string",
       "title": "Text"
      },
      "meta": {
       "type": "string",
       "title": "Meta"
      }
     },
     "type": "object",
     "required": [
      "tone",
      "text",
      "meta"
     ],
     "title": "Banner"
    },
    "Card": {
     "properties": {
      "brand": {
       "anyOf": [
        {
         "type": "string"
        },
        {
         "type": "null"
        }
       ],
       "title": "Brand"
      },
      "last4": {
       "type": "string",
       "title": "Last4"
      }
     },
     "type": "object",
     "required": [
      "brand",
      "last4"
     ],
     "title": "Card"
    },
    "ClientDetail": {
     "properties": {
      "client_id": {
       "type": "string",
       "title": "Client Id"
      },
      "display_name": {
       "type": "string",
       "title": "Display Name"
      },
      "email_masked": {
       "type": "string",
       "title": "Email Masked"
      },
      "phone_masked": {
       "type": "string",
       "title": "Phone Masked"
      },
      "created_at": {
       "type": "string",
       "title": "Created At"
      },
      "face_enrolled": {
       "type": "boolean",
       "title": "Face Enrolled"
      },
      "locked": {
       "type": "boolean",
       "title": "Locked"
      },
      "balance_cents": {
       "type": "integer",
       "title": "Balance Cents"
      },
      "operations_count": {
       "type": "integer",
       "title": "Operations Count"
      },
      "failed_logins": {
       "type": "integer",
       "title": "Failed Logins"
      },
      "active_sessions": {
       "type": "integer",
       "title": "Active Sessions"
      },
      "pending_requests": {
       "type": "integer",
       "title": "Pending Requests"
      },
      "payout_accounts": {
       "items": {
        "$ref": "#/components/schemas/PayoutAccount"
       },
       "type": "array",
       "title": "Payout Accounts"
      },
      "recent_transactions": {
       "items": {
        "$ref": "#/components/schemas/TransactionItem"
       },
       "type": "array",
       "title": "Recent Transactions"
      }
     },
     "type": "object",
     "required": [
      "client_id",
      "display_name",
      "email_masked",
      "phone_masked",
      "created_at",
      "face_enrolled",
      "locked",
      "balance_cents",
      "operations_count",
      "failed_logins",
      "active_sessions",
      "pending_requests",
      "payout_accounts",
      "recent_transactions"
     ],
     "title": "ClientDetail"
    },
    "ClientItem": {
     "properties": {
      "client_id": {
       "type": "string",
       "title": "Client Id"
      },
      "display_name": {
       "type": "string",
       "title": "Display Name"
      },
      "email_masked": {
       "type": "string",
       "title": "Email Masked"
      },
      "phone_masked": {
       "type": "string",
       "title": "Phone Masked"
      },
      "created_at": {
       "type": "string",
       "title": "Created At"
      },
      "face_enrolled": {
       "type": "boolean",
       "title": "Face Enrolled"
      },
      "locked": {
       "type": "boolean",
       "title": "Locked"
      },
      "balance_cents": {
       "type": "integer",
       "title": "Balance Cents"
      },
      "operations_count": {
       "type": "integer",
       "title": "Operations Count"
      }
     },
     "type": "object",
     "required": [
      "client_id",
      "display_name",
      "email_masked",
      "phone_masked",
      "created_at",
      "face_enrolled",
      "locked",
      "balance_cents",
      "operations_count"
     ],
     "title": "ClientItem"
    },
    "ClientPage": {
     "properties": {
      "items": {
       "items": {
        "$ref": "#/components/schemas/ClientItem"
       },
       "type": "array",
       "title": "Items"
      },
      "page": {
       "type": "integer",
       "title": "Page"
      },
      "size": {
       "type": "integer",
       "title": "Size"
      },
      "total": {
       "type": "integer",
       "title": "Total"
      }
     },
     "type": "object",
     "required": [
      "items",
      "page",
      "size",
      "total"
     ],
     "title": "ClientPage"
    },
    "ClientsSummary": {
     "properties": {
      "total": {
       "type": "integer",
       "title": "Total"
      },
      "new_7d": {
       "type": "integer",
       "title": "New 7D"
      },
      "face_enrolled": {
       "type": "integer",
       "title": "Face Enrolled"
      },
      "locked": {
       "type": "integer",
       "title": "Locked"
      }
     },
     "type": "object",
     "required": [
      "total",
      "new_7d",
      "face_enrolled",
      "locked"
     ],
     "title": "ClientsSummary"
    },
    "Count": {
     "properties": {
      "key": {
       "type": "string",
       "title": "Key"
      },
      "count": {
       "type": "integer",
       "title": "Count"
      }
     },
     "type": "object",
     "required": [
      "key",
      "count"
     ],
     "title": "Count"
    },
    "EnrollRequest": {
     "properties": {
      "consent": {
       "type": "boolean",
       "title": "Consent",
       "description": "Consentement explicite (RGPD art. 9)"
      },
      "frames": {
       "items": {
        "type": "string"
       },
       "type": "array",
       "maxItems": 30,
       "minItems": 1,
       "title": "Frames",
       "description": "Images JPEG en base64 de la caméra USB, prises pendant la rotation de la tête"
      }
     },
     "type": "object",
     "required": [
      "consent",
      "frames"
     ],
     "title": "EnrollRequest"
    },
    "EntriesAnomaly": {
     "properties": {
      "reference": {
       "type": "string",
       "title": "Reference"
      },
      "status": {
       "type": "string",
       "title": "Status"
      },
      "entries": {
       "type": "integer",
       "title": "Entries"
      }
     },
     "type": "object",
     "required": [
      "reference",
      "status",
      "entries"
     ],
     "title": "EntriesAnomaly"
    },
    "ErrorDetail": {
     "properties": {
      "code": {
       "type": "string",
       "title": "Code",
       "examples": [
        "invalid_token"
       ]
      },
      "message": {
       "type": "string",
       "title": "Message",
       "examples": [
        "Session invalide ou expirée."
       ]
      }
     },
     "type": "object",
     "required": [
      "code",
      "message"
     ],
     "title": "ErrorDetail"
    },
    "ErrorOut": {
     "properties": {
      "detail": {
       "$ref": "#/components/schemas/ErrorDetail"
      }
     },
     "type": "object",
     "required": [
      "detail"
     ],
     "title": "ErrorOut"
    },
    "FaceChallenge": {
     "properties": {
      "direction": {
       "type": "string",
       "enum": [
        "left",
        "right"
       ],
       "title": "Direction"
      },
      "frames": {
       "type": "integer",
       "title": "Frames"
      },
      "interval_ms": {
       "type": "integer",
       "title": "Interval Ms"
      }
     },
     "type": "object",
     "required": [
      "direction",
      "frames",
      "interval_ms"
     ],
     "title": "FaceChallenge"
    },
    "FaceRequest": {
     "properties": {
      "session_id": {
       "type": "string",
       "maxLength": 36,
       "minLength": 36,
       "title": "Session Id"
      },
      "frames": {
       "items": {
        "type": "string"
       },
       "type": "array",
       "maxItems": 20,
       "minItems": 1,
       "title": "Frames",
       "description": "Images JPEG en base64 de la caméra USB, prises pendant la rotation de la tête"
      }
     },
     "type": "object",
     "required": [
      "session_id",
      "frames"
     ],
     "title": "FaceRequest"
    },
    "GrafanaLink": {
     "properties": {
      "title": {
       "type": "string",
       "title": "Title"
      },
      "url": {
       "type": "string",
       "title": "Url"
      }
     },
     "type": "object",
     "required": [
      "title",
      "url"
     ],
     "title": "GrafanaLink"
    },
    "GrafanaOut": {
     "properties": {
      "base_url": {
       "type": "string",
       "title": "Base Url"
      },
      "dashboards": {
       "items": {
        "$ref": "#/components/schemas/GrafanaLink"
       },
       "type": "array",
       "title": "Dashboards"
      },
      "panels": {
       "items": {
        "$ref": "#/components/schemas/GrafanaPanel"
       },
       "type": "array",
       "title": "Panels"
      },
      "tools": {
       "items": {
        "$ref": "#/components/schemas/GrafanaLink"
       },
       "type": "array",
       "title": "Tools"
      }
     },
     "type": "object",
     "required": [
      "base_url",
      "dashboards",
      "panels",
      "tools"
     ],
     "title": "GrafanaOut"
    },
    "GrafanaPanel": {
     "properties": {
      "key": {
       "type": "string",
       "title": "Key"
      },
      "title": {
       "type": "string",
       "title": "Title"
      },
      "embed_url": {
       "type": "string",
       "title": "Embed Url"
      }
     },
     "type": "object",
     "required": [
      "key",
      "title",
      "embed_url"
     ],
     "title": "GrafanaPanel"
    },
    "HTTPValidationError": {
     "properties": {
      "detail": {
       "items": {
        "$ref": "#/components/schemas/ValidationError"
       },
       "type": "array",
       "title": "Detail"
      }
     },
     "type": "object",
     "title": "HTTPValidationError"
    },
    "IdentifyRequest": {
     "properties": {
      "email": {
       "type": "string",
       "maxLength": 254,
       "minLength": 3,
       "title": "Email"
      }
     },
     "type": "object",
     "required": [
      "email"
     ],
     "title": "IdentifyRequest",
     "examples": [
      {
       "email": "ops@orbe.test"
      }
     ]
    },
    "IncidentWindow": {
     "properties": {
      "x1": {
       "type": "string",
       "title": "X1"
      },
      "x2": {
       "type": "string",
       "title": "X2"
      }
     },
     "type": "object",
     "required": [
      "x1",
      "x2"
     ],
     "title": "IncidentWindow"
    },
    "Kpi": {
     "properties": {
      "key": {
       "type": "string",
       "title": "Key"
      },
      "label": {
       "type": "string",
       "title": "Label"
      },
      "value": {
       "type": "string",
       "title": "Value"
      },
      "raw": {
       "anyOf": [
        {
         "type": "number"
        },
        {
         "type": "null"
        }
       ],
       "title": "Raw"
      },
      "sub": {
       "type": "string",
       "title": "Sub"
      },
      "tone": {
       "anyOf": [
        {
         "type": "string",
         "enum": [
          "ok",
          "warn",
          "danger",
          "unknown"
         ]
        },
        {
         "type": "null"
        }
       ],
       "title": "Tone"
      }
     },
     "type": "object",
     "required": [
      "key",
      "label",
      "value",
      "raw",
      "sub"
     ],
     "title": "Kpi"
    },
    "LedgerCheck": {
     "properties": {
      "ok": {
       "type": "boolean",
       "title": "Ok"
      },
      "checked_at": {
       "type": "string",
       "title": "Checked At"
      },
      "transactions_checked": {
       "type": "integer",
       "title": "Transactions Checked"
      },
      "accounts_checked": {
       "type": "integer",
       "title": "Accounts Checked"
      },
      "unbalanced_transactions": {
       "items": {
        "type": "string"
       },
       "type": "array",
       "title": "Unbalanced Transactions"
      },
      "account_mismatches": {
       "items": {
        "$ref": "#/components/schemas/AccountMismatch"
       },
       "type": "array",
       "title": "Account Mismatches"
      },
      "negative_client_balances": {
       "type": "integer",
       "title": "Negative Client Balances"
      },
      "entries_anomalies": {
       "items": {
        "$ref": "#/components/schemas/EntriesAnomaly"
       },
       "type": "array",
       "title": "Entries Anomalies"
      }
     },
     "type": "object",
     "required": [
      "ok",
      "checked_at",
      "transactions_checked",
      "accounts_checked",
      "unbalanced_transactions",
      "account_mismatches",
      "negative_client_balances",
      "entries_anomalies"
     ],
     "title": "LedgerCheck"
    },
    "LedgerLine": {
     "properties": {
      "direction": {
       "type": "string",
       "enum": [
        "debit",
        "credit"
       ],
       "title": "Direction"
      },
      "amount_cents": {
       "type": "integer",
       "title": "Amount Cents"
      },
      "account_type": {
       "type": "string",
       "enum": [
        "client",
        "counterpart"
       ],
       "title": "Account Type"
      },
      "account_label": {
       "type": "string",
       "title": "Account Label"
      }
     },
     "type": "object",
     "required": [
      "direction",
      "amount_cents",
      "account_type",
      "account_label"
     ],
     "title": "LedgerLine"
    },
    "LogLine": {
     "properties": {
      "time": {
       "type": "string",
       "title": "Time"
      },
      "ts": {
       "type": "string",
       "title": "Ts"
      },
      "level": {
       "type": "string",
       "enum": [
        "DEBUG",
        "INFO",
        "WARN",
        "ERROR",
        "ALERT",
        "ACTION"
       ],
       "title": "Level"
      },
      "source": {
       "type": "string",
       "title": "Source"
      },
      "msg": {
       "type": "string",
       "title": "Msg"
      }
     },
     "type": "object",
     "required": [
      "time",
      "ts",
      "level",
      "source",
      "msg"
     ],
     "title": "LogLine"
    },
    "LoginStep": {
     "properties": {
      "session_id": {
       "type": "string",
       "title": "Session Id"
      },
      "step": {
       "type": "string",
       "enum": [
        "face",
        "password"
       ],
       "title": "Step"
      },
      "face_challenge": {
       "anyOf": [
        {
         "$ref": "#/components/schemas/FaceChallenge"
        },
        {
         "type": "null"
        }
       ]
      },
      "face_enrollment_required": {
       "type": "boolean",
       "title": "Face Enrollment Required",
       "default": false
      },
      "expires_in": {
       "type": "integer",
       "title": "Expires In"
      }
     },
     "type": "object",
     "required": [
      "session_id",
      "step",
      "expires_in"
     ],
     "title": "LoginStep"
    },
    "LogsOut": {
     "properties": {
      "logs": {
       "items": {
        "$ref": "#/components/schemas/LogLine"
       },
       "type": "array",
       "title": "Logs"
      }
     },
     "type": "object",
     "required": [
      "logs"
     ],
     "title": "LogsOut"
    },
    "MeResponse": {
     "properties": {
      "operator_id": {
       "type": "string",
       "title": "Operator Id"
      },
      "email": {
       "type": "string",
       "title": "Email"
      },
      "display_name": {
       "type": "string",
       "title": "Display Name"
      },
      "role": {
       "type": "string",
       "enum": [
        "viewer",
        "operator",
        "admin"
       ],
       "title": "Role"
      }
     },
     "type": "object",
     "required": [
      "operator_id",
      "email",
      "display_name",
      "role"
     ],
     "title": "MeResponse"
    },
    "OperationsWindow": {
     "properties": {
      "count": {
       "type": "integer",
       "title": "Count"
      },
      "by_type": {
       "additionalProperties": {
        "type": "integer"
       },
       "type": "object",
       "title": "By Type"
      },
      "by_status": {
       "additionalProperties": {
        "type": "integer"
       },
       "type": "object",
       "title": "By Status"
      },
      "payments_authorized_cents": {
       "type": "integer",
       "title": "Payments Authorized Cents"
      },
      "refunds_cents": {
       "type": "integer",
       "title": "Refunds Cents"
      },
      "payouts_cents": {
       "type": "integer",
       "title": "Payouts Cents"
      },
      "decline_rate": {
       "type": "number",
       "title": "Decline Rate"
      },
      "decline_reasons": {
       "items": {
        "$ref": "#/components/schemas/Count"
       },
       "type": "array",
       "title": "Decline Reasons"
      }
     },
     "type": "object",
     "required": [
      "count",
      "by_type",
      "by_status",
      "payments_authorized_cents",
      "refunds_cents",
      "payouts_cents",
      "decline_rate",
      "decline_reasons"
     ],
     "title": "OperationsWindow"
    },
    "Overview": {
     "properties": {
      "updated_at": {
       "type": "string",
       "title": "Updated At"
      },
      "status": {
       "$ref": "#/components/schemas/StatusBadge"
      },
      "banner": {
       "$ref": "#/components/schemas/Banner"
      },
      "kpis": {
       "items": {
        "$ref": "#/components/schemas/Kpi"
       },
       "type": "array",
       "title": "Kpis"
      },
      "sources": {
       "additionalProperties": {
        "type": "string",
        "enum": [
         "up",
         "down"
        ]
       },
       "type": "object",
       "title": "Sources"
      }
     },
     "type": "object",
     "required": [
      "updated_at",
      "status",
      "banner",
      "kpis",
      "sources"
     ],
     "title": "Overview"
    },
    "Party": {
     "properties": {
      "client_id": {
       "type": "string",
       "title": "Client Id"
      },
      "display_name": {
       "type": "string",
       "title": "Display Name"
      }
     },
     "type": "object",
     "required": [
      "client_id",
      "display_name"
     ],
     "title": "Party"
    },
    "PasswordRequest": {
     "properties": {
      "session_id": {
       "type": "string",
       "maxLength": 36,
       "minLength": 36,
       "title": "Session Id"
      },
      "password": {
       "type": "string",
       "maxLength": 128,
       "minLength": 1,
       "title": "Password"
      }
     },
     "type": "object",
     "required": [
      "session_id",
      "password"
     ],
     "title": "PasswordRequest"
    },
    "PasswordReset": {
     "properties": {
      "password": {
       "type": "string",
       "maxLength": 128,
       "minLength": 1,
       "title": "Password"
      }
     },
     "type": "object",
     "required": [
      "password"
     ],
     "title": "PasswordReset"
    },
    "PayoutAccount": {
     "properties": {
      "label": {
       "type": "string",
       "title": "Label"
      },
      "iban_last4": {
       "type": "string",
       "title": "Iban Last4"
      },
      "is_default": {
       "type": "boolean",
       "title": "Is Default"
      }
     },
     "type": "object",
     "required": [
      "label",
      "iban_last4",
      "is_default"
     ],
     "title": "PayoutAccount"
    },
    "RequestItem": {
     "properties": {
      "reference": {
       "type": "string",
       "title": "Reference"
      },
      "amount_cents": {
       "type": "integer",
       "title": "Amount Cents"
      },
      "currency": {
       "type": "string",
       "title": "Currency"
      },
      "status": {
       "type": "string",
       "title": "Status"
      },
      "failure_reason": {
       "anyOf": [
        {
         "type": "string"
        },
        {
         "type": "null"
        }
       ],
       "title": "Failure Reason"
      },
      "requester": {
       "$ref": "#/components/schemas/Party"
      },
      "payer": {
       "anyOf": [
        {
         "$ref": "#/components/schemas/Party"
        },
        {
         "type": "null"
        }
       ]
      },
      "transaction_reference": {
       "anyOf": [
        {
         "type": "string"
        },
        {
         "type": "null"
        }
       ],
       "title": "Transaction Reference"
      },
      "description": {
       "anyOf": [
        {
         "type": "string"
        },
        {
         "type": "null"
        }
       ],
       "title": "Description"
      },
      "created_at": {
       "type": "string",
       "title": "Created At"
      },
      "expires_at": {
       "type": "string",
       "title": "Expires At"
      }
     },
     "type": "object",
     "required": [
      "reference",
      "amount_cents",
      "currency",
      "status",
      "failure_reason",
      "requester",
      "payer",
      "transaction_reference",
      "description",
      "created_at",
      "expires_at"
     ],
     "title": "RequestItem"
    },
    "RequestPage": {
     "properties": {
      "items": {
       "items": {
        "$ref": "#/components/schemas/RequestItem"
       },
       "type": "array",
       "title": "Items"
      },
      "page": {
       "type": "integer",
       "title": "Page"
      },
      "size": {
       "type": "integer",
       "title": "Size"
      },
      "total": {
       "type": "integer",
       "title": "Total"
      }
     },
     "type": "object",
     "required": [
      "items",
      "page",
      "size",
      "total"
     ],
     "title": "RequestPage"
    },
    "RequestsSummary": {
     "properties": {
      "pending": {
       "type": "integer",
       "title": "Pending"
      },
      "paid_7d": {
       "type": "integer",
       "title": "Paid 7D"
      }
     },
     "type": "object",
     "required": [
      "pending",
      "paid_7d"
     ],
     "title": "RequestsSummary"
    },
    "Resource": {
     "properties": {
      "label": {
       "type": "string",
       "title": "Label"
      },
      "value": {
       "type": "string",
       "title": "Value"
      },
      "percent": {
       "anyOf": [
        {
         "type": "number"
        },
        {
         "type": "null"
        }
       ],
       "title": "Percent"
      }
     },
     "type": "object",
     "required": [
      "label",
      "value",
      "percent"
     ],
     "title": "Resource"
    },
    "ResourcesOut": {
     "properties": {
      "resources": {
       "items": {
        "$ref": "#/components/schemas/Resource"
       },
       "type": "array",
       "title": "Resources"
      }
     },
     "type": "object",
     "required": [
      "resources"
     ],
     "title": "ResourcesOut"
    },
    "Series": {
     "properties": {
      "metric": {
       "type": "string",
       "enum": [
        "transactions",
        "amount",
        "declines",
        "registrations"
       ],
       "title": "Metric"
      },
      "interval": {
       "type": "string",
       "enum": [
        "hour",
        "day"
       ],
       "title": "Interval"
      },
      "points": {
       "items": {
        "$ref": "#/components/schemas/SeriesPoint"
       },
       "type": "array",
       "title": "Points"
      }
     },
     "type": "object",
     "required": [
      "metric",
      "interval",
      "points"
     ],
     "title": "Series"
    },
    "SeriesMinute": {
     "properties": {
      "time": {
       "type": "string",
       "title": "Time"
      },
      "ts": {
       "type": "string",
       "title": "Ts"
      },
      "incident": {
       "type": "boolean",
       "title": "Incident"
      },
      "latency": {
       "anyOf": [
        {
         "type": "number"
        },
        {
         "type": "null"
        }
       ],
       "title": "Latency"
      },
      "anomaly": {
       "anyOf": [
        {
         "type": "number"
        },
        {
         "type": "null"
        }
       ],
       "title": "Anomaly"
      },
      "tx": {
       "anyOf": [
        {
         "type": "number"
        },
        {
         "type": "null"
        }
       ],
       "title": "Tx"
      }
     },
     "type": "object",
     "required": [
      "time",
      "ts",
      "incident",
      "latency",
      "anomaly",
      "tx"
     ],
     "title": "SeriesMinute"
    },
    "SeriesPoint": {
     "properties": {
      "time": {
       "type": "string",
       "title": "Time"
      },
      "value": {
       "type": "integer",
       "title": "Value"
      }
     },
     "type": "object",
     "required": [
      "time",
      "value"
     ],
     "title": "SeriesPoint"
    },
    "ServiceCard": {
     "properties": {
      "name": {
       "type": "string",
       "title": "Name"
      },
      "desc": {
       "type": "string",
       "title": "Desc"
      },
      "status": {
       "type": "string",
       "enum": [
        "ok",
        "warn",
        "down",
        "restored",
        "unknown"
       ],
       "title": "Status"
      },
      "metric": {
       "type": "string",
       "title": "Metric"
      }
     },
     "type": "object",
     "required": [
      "name",
      "desc",
      "status",
      "metric"
     ],
     "title": "ServiceCard"
    },
    "ServicesOut": {
     "properties": {
      "updated_at": {
       "type": "string",
       "title": "Updated At"
      },
      "services": {
       "items": {
        "$ref": "#/components/schemas/ServiceCard"
       },
       "type": "array",
       "title": "Services"
      }
     },
     "type": "object",
     "required": [
      "updated_at",
      "services"
     ],
     "title": "ServicesOut"
    },
    "StatusBadge": {
     "properties": {
      "label": {
       "type": "string",
       "title": "Label"
      },
      "tone": {
       "type": "string",
       "enum": [
        "ok",
        "warn",
        "danger",
        "unknown"
       ],
       "title": "Tone"
      }
     },
     "type": "object",
     "required": [
      "label",
      "tone"
     ],
     "title": "StatusBadge"
    },
    "Summary": {
     "properties": {
      "generated_at": {
       "type": "string",
       "title": "Generated At"
      },
      "clients": {
       "$ref": "#/components/schemas/ClientsSummary"
      },
      "operations_24h": {
       "$ref": "#/components/schemas/OperationsWindow"
      },
      "operations_7d": {
       "$ref": "#/components/schemas/OperationsWindow"
      },
      "requests": {
       "$ref": "#/components/schemas/RequestsSummary"
      },
      "balances": {
       "$ref": "#/components/schemas/BalancesSummary"
      }
     },
     "type": "object",
     "required": [
      "generated_at",
      "clients",
      "operations_24h",
      "operations_7d",
      "requests",
      "balances"
     ],
     "title": "Summary"
    },
    "SupervisionSeries": {
     "properties": {
      "points": {
       "items": {
        "$ref": "#/components/schemas/SeriesMinute"
       },
       "type": "array",
       "title": "Points"
      },
      "incident": {
       "anyOf": [
        {
         "$ref": "#/components/schemas/IncidentWindow"
        },
        {
         "type": "null"
        }
       ]
      }
     },
     "type": "object",
     "required": [
      "points",
      "incident"
     ],
     "title": "SupervisionSeries"
    },
    "TokenResponse": {
     "properties": {
      "access_token": {
       "type": "string",
       "title": "Access Token"
      },
      "token_type": {
       "type": "string",
       "const": "bearer",
       "title": "Token Type",
       "default": "bearer"
      },
      "expires_in": {
       "type": "integer",
       "title": "Expires In"
      },
      "role": {
       "type": "string",
       "enum": [
        "viewer",
        "operator",
        "admin"
       ],
       "title": "Role"
      },
      "face_enrollment_required": {
       "type": "boolean",
       "title": "Face Enrollment Required",
       "default": false
      }
     },
     "type": "object",
     "required": [
      "access_token",
      "expires_in",
      "role"
     ],
     "title": "TokenResponse"
    },
    "TransactionDetail": {
     "properties": {
      "reference": {
       "type": "string",
       "title": "Reference"
      },
      "type": {
       "type": "string",
       "enum": [
        "payment",
        "refund",
        "payout"
       ],
       "title": "Type"
      },
      "amount_cents": {
       "type": "integer",
       "title": "Amount Cents"
      },
      "currency": {
       "type": "string",
       "title": "Currency"
      },
      "status": {
       "type": "string",
       "title": "Status"
      },
      "decline_reason": {
       "anyOf": [
        {
         "type": "string"
        },
        {
         "type": "null"
        }
       ],
       "title": "Decline Reason"
      },
      "card": {
       "anyOf": [
        {
         "$ref": "#/components/schemas/Card"
        },
        {
         "type": "null"
        }
       ]
      },
      "payer": {
       "$ref": "#/components/schemas/Party"
      },
      "recipient": {
       "anyOf": [
        {
         "$ref": "#/components/schemas/Party"
        },
        {
         "type": "null"
        }
       ]
      },
      "description": {
       "anyOf": [
        {
         "type": "string"
        },
        {
         "type": "null"
        }
       ],
       "title": "Description"
      },
      "created_at": {
       "type": "string",
       "title": "Created At"
      },
      "updated_at": {
       "type": "string",
       "title": "Updated At"
      },
      "parent_reference": {
       "anyOf": [
        {
         "type": "string"
        },
        {
         "type": "null"
        }
       ],
       "title": "Parent Reference"
      },
      "refund_reference": {
       "anyOf": [
        {
         "type": "string"
        },
        {
         "type": "null"
        }
       ],
       "title": "Refund Reference"
      },
      "request_reference": {
       "anyOf": [
        {
         "type": "string"
        },
        {
         "type": "null"
        }
       ],
       "title": "Request Reference"
      },
      "payout_account": {
       "anyOf": [
        {
         "$ref": "#/components/schemas/PayoutAccount"
        },
        {
         "type": "null"
        }
       ]
      },
      "entries": {
       "items": {
        "$ref": "#/components/schemas/LedgerLine"
       },
       "type": "array",
       "title": "Entries"
      }
     },
     "type": "object",
     "required": [
      "reference",
      "type",
      "amount_cents",
      "currency",
      "status",
      "decline_reason",
      "card",
      "payer",
      "recipient",
      "description",
      "created_at",
      "updated_at",
      "parent_reference",
      "refund_reference",
      "request_reference",
      "payout_account",
      "entries"
     ],
     "title": "TransactionDetail"
    },
    "TransactionItem": {
     "properties": {
      "reference": {
       "type": "string",
       "title": "Reference"
      },
      "type": {
       "type": "string",
       "enum": [
        "payment",
        "refund",
        "payout"
       ],
       "title": "Type"
      },
      "amount_cents": {
       "type": "integer",
       "title": "Amount Cents"
      },
      "currency": {
       "type": "string",
       "title": "Currency"
      },
      "status": {
       "type": "string",
       "title": "Status"
      },
      "decline_reason": {
       "anyOf": [
        {
         "type": "string"
        },
        {
         "type": "null"
        }
       ],
       "title": "Decline Reason"
      },
      "card": {
       "anyOf": [
        {
         "$ref": "#/components/schemas/Card"
        },
        {
         "type": "null"
        }
       ]
      },
      "payer": {
       "$ref": "#/components/schemas/Party"
      },
      "recipient": {
       "anyOf": [
        {
         "$ref": "#/components/schemas/Party"
        },
        {
         "type": "null"
        }
       ]
      },
      "description": {
       "anyOf": [
        {
         "type": "string"
        },
        {
         "type": "null"
        }
       ],
       "title": "Description"
      },
      "created_at": {
       "type": "string",
       "title": "Created At"
      }
     },
     "type": "object",
     "required": [
      "reference",
      "type",
      "amount_cents",
      "currency",
      "status",
      "decline_reason",
      "card",
      "payer",
      "recipient",
      "description",
      "created_at"
     ],
     "title": "TransactionItem"
    },
    "TransactionPage": {
     "properties": {
      "items": {
       "items": {
        "$ref": "#/components/schemas/TransactionItem"
       },
       "type": "array",
       "title": "Items"
      },
      "page": {
       "type": "integer",
       "title": "Page"
      },
      "size": {
       "type": "integer",
       "title": "Size"
      },
      "total": {
       "type": "integer",
       "title": "Total"
      }
     },
     "type": "object",
     "required": [
      "items",
      "page",
      "size",
      "total"
     ],
     "title": "TransactionPage"
    },
    "ValidationError": {
     "properties": {
      "loc": {
       "items": {
        "anyOf": [
         {
          "type": "string"
         },
         {
          "type": "integer"
         }
        ]
       },
       "type": "array",
       "title": "Location"
      },
      "msg": {
       "type": "string",
       "title": "Message"
      },
      "type": {
       "type": "string",
       "title": "Error Type"
      },
      "input": {
       "title": "Input"
      },
      "ctx": {
       "type": "object",
       "title": "Context"
      }
     },
     "type": "object",
     "required": [
      "loc",
      "msg",
      "type"
     ],
     "title": "ValidationError"
    }
   },
   "securitySchemes": {
    "HTTPBearer": {
     "type": "http",
     "scheme": "bearer"
    }
   }
  },
  "tags": [
   {
    "name": "Connexion",
    "description": "Identifiant → visage (caméra USB) → mot de passe ; pilote la LED"
   },
   {
    "name": "Habilitations",
    "description": "Comptes, rôles et visages (rôle admin)"
   },
   {
    "name": "Supervision",
    "description": "État des services, indicateurs, courbes, ressources, journaux"
   },
   {
    "name": "Données applicatives",
    "description": "Clients, opérations, demandes et comptabilité (lecture seule, email et téléphone masqués)"
   }
  ],
  "servers": [
   {
    "url": "http://127.0.0.1:8080",
    "description": "Démonstrateur, à travers le Nginx du dashboard"
   },
   {
    "url": "http://localhost:8006",
    "description": "Service lancé en local"
   }
  ]
 },
 "payment-service": {
  "openapi": "3.1.0",
  "info": {
   "title": "Orbe — payment-service",
   "description": "Paiements entre clients Orbe : transferts payés par carte de test, demandes d'argent, QR code, remboursements, solde et retraits fictifs. Exposé par le WAF sous `/api/payments`.\n\n- Authentification : `Authorization: Bearer <JWT>` obtenu sur auth-service ; la session ne doit pas être révoquée. Déplacer de l'argent exige une session confirmée par reconnaissance faciale (`403 second_factor_required` sinon).\n- Opérations qui déplacent de l'argent : en-tête `Idempotency-Key` (UUID) obligatoire ; `201` à la création, `200` si la même clé est rejouée.\n- Un refus de carte n'est pas une erreur HTTP : `201` avec `status: declined`.\n- Plafond : 500 € par opération. Chaque opération autorisée passe deux écritures comptables (débit, crédit).\n- Cartes de test : `4242 4242 4242 4242` (acceptée), `4000 0000 0000 0002` (refusée), `…0069` (expirée), `…9995` (fonds insuffisants).\n\nVoir CADRAGE §4.3.",
   "version": "0.1.0"
  },
  "paths": {
   "/pay": {
    "post": {
     "tags": [
      "Paiements"
     ],
     "summary": "Envoyer de l'argent",
     "operationId": "pay_pay_post",
     "security": [
      {
       "HTTPBearer": []
      }
     ],
     "parameters": [
      {
       "name": "Idempotency-Key",
       "in": "header",
       "required": false,
       "schema": {
        "anyOf": [
         {
          "type": "string"
         },
         {
          "type": "null"
         }
        ],
        "title": "Idempotency-Key"
       }
      }
     ],
     "requestBody": {
      "required": true,
      "content": {
       "application/json": {
        "schema": {
         "$ref": "#/components/schemas/PayIn"
        }
       }
      }
     },
     "responses": {
      "201": {
       "description": "Successful Response",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/PaymentOut"
         }
        }
       }
      },
      "401": {
       "description": "Jeton absent, invalide, expiré ou session révoquée",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "403": {
       "description": "Session non confirmée par reconnaissance faciale",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "400": {
       "description": "Idempotency-Key absente ou invalide",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "409": {
       "description": "Idempotency-Key déjà utilisée pour une autre requête",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "422": {
       "description": "Données invalides, carte non acceptée, solde insuffisant…",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "429": {
       "description": "Trop d'opérations par minute",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "503": {
       "description": "Service saturé ou base indisponible (réessayer)",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      }
     }
    }
   },
   "/transactions": {
    "get": {
     "tags": [
      "Historique"
     ],
     "summary": "Lister mes opérations",
     "operationId": "list_transactions_transactions_get",
     "security": [
      {
       "HTTPBearer": []
      }
     ],
     "parameters": [
      {
       "name": "status",
       "in": "query",
       "required": false,
       "schema": {
        "anyOf": [
         {
          "enum": [
           "pending",
           "authorized",
           "declined",
           "failed",
           "refunded",
           "completed"
          ],
          "type": "string"
         },
         {
          "type": "null"
         }
        ],
        "title": "Status"
       }
      },
      {
       "name": "direction",
       "in": "query",
       "required": false,
       "schema": {
        "anyOf": [
         {
          "enum": [
           "sent",
           "received"
          ],
          "type": "string"
         },
         {
          "type": "null"
         }
        ],
        "title": "Direction"
       }
      },
      {
       "name": "limit",
       "in": "query",
       "required": false,
       "schema": {
        "type": "integer",
        "maximum": 100,
        "minimum": 1,
        "default": 20,
        "title": "Limit"
       }
      },
      {
       "name": "cursor",
       "in": "query",
       "required": false,
       "schema": {
        "anyOf": [
         {
          "type": "string"
         },
         {
          "type": "null"
         }
        ],
        "title": "Cursor"
       }
      }
     ],
     "responses": {
      "200": {
       "description": "Successful Response",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/TransactionList"
         }
        }
       }
      },
      "401": {
       "description": "Jeton absent, invalide, expiré ou session révoquée",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "422": {
       "description": "Validation Error",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/HTTPValidationError"
         }
        }
       }
      }
     }
    }
   },
   "/transactions/{reference}": {
    "get": {
     "tags": [
      "Historique"
     ],
     "summary": "Détail d'une opération",
     "operationId": "get_transaction_transactions__reference__get",
     "security": [
      {
       "HTTPBearer": []
      }
     ],
     "parameters": [
      {
       "name": "reference",
       "in": "path",
       "required": true,
       "schema": {
        "type": "string",
        "title": "Reference"
       }
      }
     ],
     "responses": {
      "200": {
       "description": "Successful Response",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/TransactionItem"
         }
        }
       }
      },
      "401": {
       "description": "Jeton absent, invalide, expiré ou session révoquée",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "404": {
       "description": "Introuvable pour ce client",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "422": {
       "description": "Validation Error",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/HTTPValidationError"
         }
        }
       }
      }
     }
    }
   },
   "/transactions/{reference}/refund": {
    "post": {
     "tags": [
      "Paiements"
     ],
     "summary": "Rembourser un paiement reçu",
     "operationId": "refund_transactions__reference__refund_post",
     "security": [
      {
       "HTTPBearer": []
      }
     ],
     "parameters": [
      {
       "name": "reference",
       "in": "path",
       "required": true,
       "schema": {
        "type": "string",
        "title": "Reference"
       }
      },
      {
       "name": "Idempotency-Key",
       "in": "header",
       "required": false,
       "schema": {
        "anyOf": [
         {
          "type": "string"
         },
         {
          "type": "null"
         }
        ],
        "title": "Idempotency-Key"
       }
      }
     ],
     "responses": {
      "201": {
       "description": "Successful Response",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/RefundOut"
         }
        }
       }
      },
      "401": {
       "description": "Jeton absent, invalide, expiré ou session révoquée",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "403": {
       "description": "Session non confirmée par reconnaissance faciale",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "400": {
       "description": "Idempotency-Key absente ou invalide",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "409": {
       "description": "Idempotency-Key déjà utilisée pour une autre requête",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "422": {
       "description": "Données invalides, carte non acceptée, solde insuffisant…",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "429": {
       "description": "Trop d'opérations par minute",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "503": {
       "description": "Service saturé ou base indisponible (réessayer)",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "404": {
       "description": "Introuvable pour ce client",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      }
     }
    }
   },
   "/account": {
    "get": {
     "tags": [
      "Compte"
     ],
     "summary": "Solde et compte lié",
     "operationId": "account_account_get",
     "responses": {
      "200": {
       "description": "Successful Response",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/AccountOut"
         }
        }
       }
      },
      "401": {
       "description": "Jeton absent, invalide, expiré ou session révoquée",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      }
     },
     "security": [
      {
       "HTTPBearer": []
      }
     ]
    }
   },
   "/payouts": {
    "post": {
     "tags": [
      "Compte"
     ],
     "summary": "Retirer vers le compte lié",
     "operationId": "payout_payouts_post",
     "security": [
      {
       "HTTPBearer": []
      }
     ],
     "parameters": [
      {
       "name": "Idempotency-Key",
       "in": "header",
       "required": false,
       "schema": {
        "anyOf": [
         {
          "type": "string"
         },
         {
          "type": "null"
         }
        ],
        "title": "Idempotency-Key"
       }
      }
     ],
     "requestBody": {
      "required": true,
      "content": {
       "application/json": {
        "schema": {
         "$ref": "#/components/schemas/PayoutIn"
        }
       }
      }
     },
     "responses": {
      "201": {
       "description": "Successful Response",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/PayoutOut"
         }
        }
       }
      },
      "401": {
       "description": "Jeton absent, invalide, expiré ou session révoquée",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "403": {
       "description": "Session non confirmée par reconnaissance faciale",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "400": {
       "description": "Idempotency-Key absente ou invalide",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "409": {
       "description": "Idempotency-Key déjà utilisée pour une autre requête",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "422": {
       "description": "Données invalides, carte non acceptée, solde insuffisant…",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "429": {
       "description": "Trop d'opérations par minute",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "503": {
       "description": "Service saturé ou base indisponible (réessayer)",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      }
     }
    }
   },
   "/requests": {
    "post": {
     "tags": [
      "Demandes d'argent"
     ],
     "summary": "Demander de l'argent",
     "operationId": "create_request_requests_post",
     "security": [
      {
       "HTTPBearer": []
      }
     ],
     "parameters": [
      {
       "name": "Idempotency-Key",
       "in": "header",
       "required": false,
       "schema": {
        "anyOf": [
         {
          "type": "string"
         },
         {
          "type": "null"
         }
        ],
        "title": "Idempotency-Key"
       }
      }
     ],
     "requestBody": {
      "required": true,
      "content": {
       "application/json": {
        "schema": {
         "$ref": "#/components/schemas/RequestIn"
        }
       }
      }
     },
     "responses": {
      "201": {
       "description": "Successful Response",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/RequestOut"
         }
        }
       }
      },
      "401": {
       "description": "Jeton absent, invalide, expiré ou session révoquée",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "403": {
       "description": "Session non confirmée par reconnaissance faciale",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "400": {
       "description": "Idempotency-Key absente ou invalide",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "409": {
       "description": "Idempotency-Key déjà utilisée pour une autre requête",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "422": {
       "description": "Données invalides, carte non acceptée, solde insuffisant…",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "429": {
       "description": "Trop d'opérations par minute",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "503": {
       "description": "Service saturé ou base indisponible (réessayer)",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      }
     }
    },
    "get": {
     "tags": [
      "Demandes d'argent"
     ],
     "summary": "Lister mes demandes",
     "operationId": "list_requests_requests_get",
     "security": [
      {
       "HTTPBearer": []
      }
     ],
     "parameters": [
      {
       "name": "role",
       "in": "query",
       "required": false,
       "schema": {
        "anyOf": [
         {
          "enum": [
           "incoming",
           "outgoing"
          ],
          "type": "string"
         },
         {
          "type": "null"
         }
        ],
        "title": "Role"
       }
      },
      {
       "name": "status",
       "in": "query",
       "required": false,
       "schema": {
        "anyOf": [
         {
          "enum": [
           "pending",
           "paid",
           "declined",
           "cancelled",
           "expired",
           "failed"
          ],
          "type": "string"
         },
         {
          "type": "null"
         }
        ],
        "title": "Status"
       }
      }
     ],
     "responses": {
      "200": {
       "description": "Successful Response",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/RequestList"
         }
        }
       }
      },
      "401": {
       "description": "Jeton absent, invalide, expiré ou session révoquée",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "422": {
       "description": "Validation Error",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/HTTPValidationError"
         }
        }
       }
      }
     }
    }
   },
   "/requests/{reference}/pay": {
    "post": {
     "tags": [
      "Demandes d'argent"
     ],
     "summary": "Payer une demande reçue",
     "operationId": "pay_request_requests__reference__pay_post",
     "security": [
      {
       "HTTPBearer": []
      }
     ],
     "parameters": [
      {
       "name": "reference",
       "in": "path",
       "required": true,
       "schema": {
        "type": "string",
        "title": "Reference"
       }
      },
      {
       "name": "Idempotency-Key",
       "in": "header",
       "required": false,
       "schema": {
        "anyOf": [
         {
          "type": "string"
         },
         {
          "type": "null"
         }
        ],
        "title": "Idempotency-Key"
       }
      }
     ],
     "requestBody": {
      "required": true,
      "content": {
       "application/json": {
        "schema": {
         "$ref": "#/components/schemas/RequestPayIn"
        }
       }
      }
     },
     "responses": {
      "201": {
       "description": "Successful Response",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/PaymentOut"
         }
        }
       }
      },
      "401": {
       "description": "Jeton absent, invalide, expiré ou session révoquée",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "403": {
       "description": "Session non confirmée par reconnaissance faciale",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "400": {
       "description": "Idempotency-Key absente ou invalide",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "409": {
       "description": "Idempotency-Key déjà utilisée pour une autre requête",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "422": {
       "description": "Données invalides, carte non acceptée, solde insuffisant…",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "429": {
       "description": "Trop d'opérations par minute",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "503": {
       "description": "Service saturé ou base indisponible (réessayer)",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "404": {
       "description": "Introuvable pour ce client",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      }
     }
    }
   },
   "/requests/{reference}/decline": {
    "post": {
     "tags": [
      "Demandes d'argent"
     ],
     "summary": "Refuser une demande reçue",
     "operationId": "decline_request_requests__reference__decline_post",
     "security": [
      {
       "HTTPBearer": []
      }
     ],
     "parameters": [
      {
       "name": "reference",
       "in": "path",
       "required": true,
       "schema": {
        "type": "string",
        "title": "Reference"
       }
      }
     ],
     "responses": {
      "200": {
       "description": "Successful Response",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/RequestOut"
         }
        }
       }
      },
      "401": {
       "description": "Jeton absent, invalide, expiré ou session révoquée",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "404": {
       "description": "Introuvable pour ce client",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "422": {
       "description": "Validation Error",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/HTTPValidationError"
         }
        }
       }
      }
     }
    }
   },
   "/requests/{reference}/cancel": {
    "post": {
     "tags": [
      "Demandes d'argent"
     ],
     "summary": "Annuler une demande émise",
     "operationId": "cancel_request_requests__reference__cancel_post",
     "security": [
      {
       "HTTPBearer": []
      }
     ],
     "parameters": [
      {
       "name": "reference",
       "in": "path",
       "required": true,
       "schema": {
        "type": "string",
        "title": "Reference"
       }
      }
     ],
     "responses": {
      "200": {
       "description": "Successful Response",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/RequestOut"
         }
        }
       }
      },
      "401": {
       "description": "Jeton absent, invalide, expiré ou session révoquée",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "404": {
       "description": "Introuvable pour ce client",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "422": {
       "description": "Validation Error",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/HTTPValidationError"
         }
        }
       }
      }
     }
    }
   },
   "/qr": {
    "get": {
     "tags": [
      "QR code"
     ],
     "summary": "Mon QR « Recevoir »",
     "operationId": "get_qr_qr_get",
     "responses": {
      "200": {
       "description": "Successful Response",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/QrOut"
         }
        }
       }
      },
      "401": {
       "description": "Jeton absent, invalide, expiré ou session révoquée",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      }
     },
     "security": [
      {
       "HTTPBearer": []
      }
     ]
    }
   },
   "/qr/rotate": {
    "post": {
     "tags": [
      "QR code"
     ],
     "summary": "Renouveler mon QR",
     "operationId": "rotate_qr_qr_rotate_post",
     "responses": {
      "200": {
       "description": "Successful Response",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/QrOut"
         }
        }
       }
      },
      "401": {
       "description": "Jeton absent, invalide, expiré ou session révoquée",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      }
     },
     "security": [
      {
       "HTTPBearer": []
      }
     ]
    }
   },
   "/payout-accounts": {
    "get": {
     "tags": [
      "Compte"
     ],
     "summary": "Mes comptes liés",
     "operationId": "list_payout_accounts_payout_accounts_get",
     "responses": {
      "200": {
       "description": "Successful Response",
       "content": {
        "application/json": {
         "schema": {
          "items": {
           "$ref": "#/components/schemas/PayoutAccountOut"
          },
          "type": "array",
          "title": "Response List Payout Accounts Payout Accounts Get"
         }
        }
       }
      },
      "401": {
       "description": "Jeton absent, invalide, expiré ou session révoquée",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      }
     },
     "security": [
      {
       "HTTPBearer": []
      }
     ]
    },
    "post": {
     "tags": [
      "Compte"
     ],
     "summary": "Ajouter un compte lié",
     "operationId": "add_payout_account_payout_accounts_post",
     "requestBody": {
      "content": {
       "application/json": {
        "schema": {
         "$ref": "#/components/schemas/PayoutAccountIn"
        }
       }
      },
      "required": true
     },
     "responses": {
      "201": {
       "description": "Successful Response",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/PayoutAccountOut"
         }
        }
       }
      },
      "401": {
       "description": "Jeton absent, invalide, expiré ou session révoquée",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "403": {
       "description": "Session non confirmée par reconnaissance faciale",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "422": {
       "description": "IBAN invalide ou trop de comptes",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      }
     },
     "security": [
      {
       "HTTPBearer": []
      }
     ]
    }
   },
   "/payout-accounts/{account_id}/default": {
    "post": {
     "tags": [
      "Compte"
     ],
     "summary": "Choisir le compte lié par défaut",
     "operationId": "default_payout_account_payout_accounts__account_id__default_post",
     "security": [
      {
       "HTTPBearer": []
      }
     ],
     "parameters": [
      {
       "name": "account_id",
       "in": "path",
       "required": true,
       "schema": {
        "type": "string",
        "title": "Account Id"
       }
      }
     ],
     "responses": {
      "200": {
       "description": "Successful Response",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/PayoutAccountOut"
         }
        }
       }
      },
      "401": {
       "description": "Jeton absent, invalide, expiré ou session révoquée",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "403": {
       "description": "Session non confirmée par reconnaissance faciale",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "404": {
       "description": "Compte lié introuvable",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "422": {
       "description": "Validation Error",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/HTTPValidationError"
         }
        }
       }
      }
     }
    }
   },
   "/payout-accounts/{account_id}": {
    "delete": {
     "tags": [
      "Compte"
     ],
     "summary": "Retirer un compte lié",
     "operationId": "delete_payout_account_payout_accounts__account_id__delete",
     "security": [
      {
       "HTTPBearer": []
      }
     ],
     "parameters": [
      {
       "name": "account_id",
       "in": "path",
       "required": true,
       "schema": {
        "type": "string",
        "title": "Account Id"
       }
      }
     ],
     "responses": {
      "204": {
       "description": "Successful Response"
      },
      "401": {
       "description": "Jeton absent, invalide, expiré ou session révoquée",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "403": {
       "description": "Session non confirmée par reconnaissance faciale",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "404": {
       "description": "Compte lié introuvable",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "422": {
       "description": "Validation Error",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/HTTPValidationError"
         }
        }
       }
      }
     }
    }
   },
   "/contacts": {
    "get": {
     "tags": [
      "Contacts"
     ],
     "summary": "Mes contacts",
     "operationId": "list_contacts_contacts_get",
     "responses": {
      "200": {
       "description": "Successful Response",
       "content": {
        "application/json": {
         "schema": {
          "items": {
           "$ref": "#/components/schemas/ContactOut"
          },
          "type": "array",
          "title": "Response List Contacts Contacts Get"
         }
        }
       }
      },
      "401": {
       "description": "Jeton absent, invalide, expiré ou session révoquée",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      }
     },
     "security": [
      {
       "HTTPBearer": []
      }
     ]
    },
    "post": {
     "tags": [
      "Contacts"
     ],
     "summary": "Ajouter un contact (client Orbe)",
     "operationId": "add_contact_contacts_post",
     "requestBody": {
      "content": {
       "application/json": {
        "schema": {
         "$ref": "#/components/schemas/ContactIn"
        }
       }
      },
      "required": true
     },
     "responses": {
      "201": {
       "description": "Successful Response",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ContactOut"
         }
        }
       }
      },
      "401": {
       "description": "Jeton absent, invalide, expiré ou session révoquée",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "403": {
       "description": "Session non confirmée par reconnaissance faciale",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "404": {
       "description": "Aucun compte Orbe pour ce contact",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "409": {
       "description": "Contact déjà présent",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "429": {
       "description": "Trop de recherches par minute",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "422": {
       "description": "Validation Error",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/HTTPValidationError"
         }
        }
       }
      }
     },
     "security": [
      {
       "HTTPBearer": []
      }
     ]
    }
   },
   "/contacts/{contact_id}": {
    "delete": {
     "tags": [
      "Contacts"
     ],
     "summary": "Retirer un contact",
     "operationId": "remove_contact_contacts__contact_id__delete",
     "security": [
      {
       "HTTPBearer": []
      }
     ],
     "parameters": [
      {
       "name": "contact_id",
       "in": "path",
       "required": true,
       "schema": {
        "type": "string",
        "title": "Contact Id"
       }
      }
     ],
     "responses": {
      "204": {
       "description": "Successful Response"
      },
      "401": {
       "description": "Jeton absent, invalide, expiré ou session révoquée",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "404": {
       "description": "Contact introuvable",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "422": {
       "description": "Validation Error",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/HTTPValidationError"
         }
        }
       }
      }
     }
    }
   }
  },
  "components": {
   "schemas": {
    "AccountOut": {
     "properties": {
      "balance_cents": {
       "type": "integer",
       "title": "Balance Cents"
      },
      "currency": {
       "type": "string",
       "title": "Currency",
       "default": "EUR"
      },
      "payout_accounts": {
       "items": {
        "$ref": "#/components/schemas/PayoutAccountOut"
       },
       "type": "array",
       "title": "Payout Accounts"
      }
     },
     "type": "object",
     "required": [
      "balance_cents",
      "payout_accounts"
     ],
     "title": "AccountOut"
    },
    "CardIn": {
     "properties": {
      "number": {
       "type": "string",
       "format": "password",
       "title": "Number",
       "writeOnly": true
      },
      "exp_month": {
       "type": "integer",
       "maximum": 12.0,
       "minimum": 1.0,
       "title": "Exp Month"
      },
      "exp_year": {
       "type": "integer",
       "maximum": 2100.0,
       "minimum": 2000.0,
       "title": "Exp Year"
      },
      "cvc": {
       "type": "string",
       "format": "password",
       "title": "Cvc",
       "writeOnly": true
      },
      "holder": {
       "type": "string",
       "maxLength": 80,
       "minLength": 1,
       "title": "Holder"
      }
     },
     "type": "object",
     "required": [
      "number",
      "exp_month",
      "exp_year",
      "cvc",
      "holder"
     ],
     "title": "CardIn"
    },
    "CardOut": {
     "properties": {
      "brand": {
       "type": "string",
       "title": "Brand"
      },
      "last4": {
       "type": "string",
       "title": "Last4"
      }
     },
     "type": "object",
     "required": [
      "brand",
      "last4"
     ],
     "title": "CardOut"
    },
    "ContactIn": {
     "properties": {
      "contact": {
       "type": "string",
       "maxLength": 254,
       "minLength": 3,
       "title": "Contact",
       "description": "Email ou téléphone"
      },
      "alias": {
       "anyOf": [
        {
         "type": "string",
         "maxLength": 80
        },
        {
         "type": "null"
        }
       ],
       "title": "Alias"
      }
     },
     "type": "object",
     "required": [
      "contact"
     ],
     "title": "ContactIn"
    },
    "ContactOut": {
     "properties": {
      "contact_id": {
       "type": "string",
       "title": "Contact Id"
      },
      "display_name": {
       "type": "string",
       "title": "Display Name"
      },
      "alias": {
       "anyOf": [
        {
         "type": "string"
        },
        {
         "type": "null"
        }
       ],
       "title": "Alias"
      },
      "added_at": {
       "type": "string",
       "title": "Added At"
      }
     },
     "type": "object",
     "required": [
      "contact_id",
      "display_name",
      "alias",
      "added_at"
     ],
     "title": "ContactOut"
    },
    "ErrorDetail": {
     "properties": {
      "code": {
       "type": "string",
       "title": "Code",
       "examples": [
        "insufficient_balance"
       ]
      },
      "message": {
       "type": "string",
       "title": "Message",
       "examples": [
        "Solde insuffisant."
       ]
      }
     },
     "type": "object",
     "required": [
      "code",
      "message"
     ],
     "title": "ErrorDetail"
    },
    "ErrorOut": {
     "properties": {
      "detail": {
       "$ref": "#/components/schemas/ErrorDetail"
      }
     },
     "type": "object",
     "required": [
      "detail"
     ],
     "title": "ErrorOut"
    },
    "HTTPValidationError": {
     "properties": {
      "detail": {
       "items": {
        "$ref": "#/components/schemas/ValidationError"
       },
       "type": "array",
       "title": "Detail"
      }
     },
     "type": "object",
     "title": "HTTPValidationError"
    },
    "PayIn": {
     "properties": {
      "recipient": {
       "anyOf": [
        {
         "type": "string",
         "maxLength": 254,
         "minLength": 3
        },
        {
         "type": "null"
        }
       ],
       "title": "Recipient"
      },
      "recipient_qr": {
       "anyOf": [
        {
         "type": "string",
         "maxLength": 64,
         "minLength": 16
        },
        {
         "type": "null"
        }
       ],
       "title": "Recipient Qr"
      },
      "recipient_contact": {
       "anyOf": [
        {
         "type": "string",
         "maxLength": 36,
         "minLength": 36
        },
        {
         "type": "null"
        }
       ],
       "title": "Recipient Contact",
       "description": "client_id d'un de mes contacts"
      },
      "amount_cents": {
       "type": "integer",
       "minimum": 1.0,
       "title": "Amount Cents"
      },
      "currency": {
       "type": "string",
       "const": "EUR",
       "title": "Currency",
       "default": "EUR"
      },
      "description": {
       "anyOf": [
        {
         "type": "string",
         "maxLength": 140
        },
        {
         "type": "null"
        }
       ],
       "title": "Description"
      },
      "card": {
       "$ref": "#/components/schemas/CardIn"
      }
     },
     "type": "object",
     "required": [
      "amount_cents",
      "card"
     ],
     "title": "PayIn",
     "examples": [
      {
       "amount_cents": 1250,
       "card": {
        "cvc": "123",
        "exp_month": 12,
        "exp_year": 2030,
        "holder": "Camille Test",
        "number": "4242 4242 4242 4242"
       },
       "currency": "EUR",
       "description": "Ciné",
       "recipient": "06 12 34 56 77"
      }
     ]
    },
    "PaymentOut": {
     "properties": {
      "reference": {
       "type": "string",
       "title": "Reference"
      },
      "status": {
       "type": "string",
       "title": "Status"
      },
      "decline_reason": {
       "anyOf": [
        {
         "type": "string"
        },
        {
         "type": "null"
        }
       ],
       "title": "Decline Reason"
      },
      "amount_cents": {
       "type": "integer",
       "title": "Amount Cents"
      },
      "currency": {
       "type": "string",
       "title": "Currency"
      },
      "card": {
       "anyOf": [
        {
         "$ref": "#/components/schemas/CardOut"
        },
        {
         "type": "null"
        }
       ]
      },
      "created_at": {
       "type": "string",
       "title": "Created At"
      }
     },
     "type": "object",
     "required": [
      "reference",
      "status",
      "decline_reason",
      "amount_cents",
      "currency",
      "card",
      "created_at"
     ],
     "title": "PaymentOut"
    },
    "PayoutAccountIn": {
     "properties": {
      "label": {
       "type": "string",
       "maxLength": 80,
       "minLength": 1,
       "title": "Label"
      },
      "iban": {
       "type": "string",
       "maxLength": 42,
       "minLength": 15,
       "title": "Iban",
       "description": "Fictif ; seuls les 4 derniers caractères sont conservés"
      },
      "make_default": {
       "type": "boolean",
       "title": "Make Default",
       "default": false
      }
     },
     "type": "object",
     "required": [
      "label",
      "iban"
     ],
     "title": "PayoutAccountIn",
     "examples": [
      {
       "iban": "FR76 3000 6000 0112 3456 7890 189",
       "label": "Banque Démo"
      }
     ]
    },
    "PayoutAccountOut": {
     "properties": {
      "id": {
       "type": "string",
       "title": "Id"
      },
      "label": {
       "type": "string",
       "title": "Label"
      },
      "iban_last4": {
       "type": "string",
       "title": "Iban Last4"
      },
      "is_default": {
       "type": "boolean",
       "title": "Is Default"
      }
     },
     "type": "object",
     "required": [
      "id",
      "label",
      "iban_last4",
      "is_default"
     ],
     "title": "PayoutAccountOut"
    },
    "PayoutIn": {
     "properties": {
      "amount_cents": {
       "type": "integer",
       "minimum": 1.0,
       "title": "Amount Cents"
      },
      "payout_account_id": {
       "anyOf": [
        {
         "type": "string"
        },
        {
         "type": "null"
        }
       ],
       "title": "Payout Account Id",
       "description": "Compte lié destinataire ; compte par défaut si absent"
      }
     },
     "type": "object",
     "required": [
      "amount_cents"
     ],
     "title": "PayoutIn"
    },
    "PayoutOut": {
     "properties": {
      "reference": {
       "type": "string",
       "title": "Reference"
      },
      "status": {
       "type": "string",
       "title": "Status"
      },
      "amount_cents": {
       "type": "integer",
       "title": "Amount Cents"
      },
      "payout_account_id": {
       "anyOf": [
        {
         "type": "string"
        },
        {
         "type": "null"
        }
       ],
       "title": "Payout Account Id"
      },
      "created_at": {
       "type": "string",
       "title": "Created At"
      }
     },
     "type": "object",
     "required": [
      "reference",
      "status",
      "amount_cents",
      "payout_account_id",
      "created_at"
     ],
     "title": "PayoutOut"
    },
    "QrOut": {
     "properties": {
      "qr_token": {
       "type": "string",
       "title": "Qr Token"
      },
      "payload": {
       "type": "string",
       "title": "Payload"
      },
      "display_name": {
       "type": "string",
       "title": "Display Name"
      }
     },
     "type": "object",
     "required": [
      "qr_token",
      "payload",
      "display_name"
     ],
     "title": "QrOut"
    },
    "RefundOut": {
     "properties": {
      "reference": {
       "type": "string",
       "title": "Reference"
      },
      "status": {
       "type": "string",
       "title": "Status"
      },
      "amount_cents": {
       "type": "integer",
       "title": "Amount Cents"
      },
      "refunded": {
       "type": "string",
       "title": "Refunded"
      }
     },
     "type": "object",
     "required": [
      "reference",
      "status",
      "amount_cents",
      "refunded"
     ],
     "title": "RefundOut"
    },
    "RequestIn": {
     "properties": {
      "payer": {
       "type": "string",
       "maxLength": 254,
       "minLength": 3,
       "title": "Payer"
      },
      "amount_cents": {
       "type": "integer",
       "minimum": 1.0,
       "title": "Amount Cents"
      },
      "description": {
       "anyOf": [
        {
         "type": "string",
         "maxLength": 140
        },
        {
         "type": "null"
        }
       ],
       "title": "Description"
      }
     },
     "type": "object",
     "required": [
      "payer",
      "amount_cents"
     ],
     "title": "RequestIn",
     "examples": [
      {
       "amount_cents": 800,
       "description": "Covoiturage",
       "payer": "camille@orbe.test"
      }
     ]
    },
    "RequestList": {
     "properties": {
      "items": {
       "items": {
        "$ref": "#/components/schemas/RequestOut"
       },
       "type": "array",
       "title": "Items"
      }
     },
     "type": "object",
     "required": [
      "items"
     ],
     "title": "RequestList"
    },
    "RequestOut": {
     "properties": {
      "reference": {
       "type": "string",
       "title": "Reference"
      },
      "role": {
       "type": "string",
       "enum": [
        "incoming",
        "outgoing"
       ],
       "title": "Role"
      },
      "counterparty": {
       "type": "string",
       "title": "Counterparty"
      },
      "amount_cents": {
       "type": "integer",
       "title": "Amount Cents"
      },
      "currency": {
       "type": "string",
       "title": "Currency"
      },
      "description": {
       "anyOf": [
        {
         "type": "string"
        },
        {
         "type": "null"
        }
       ],
       "title": "Description"
      },
      "status": {
       "type": "string",
       "title": "Status"
      },
      "failure_reason": {
       "anyOf": [
        {
         "type": "string"
        },
        {
         "type": "null"
        }
       ],
       "title": "Failure Reason"
      },
      "created_at": {
       "type": "string",
       "title": "Created At"
      },
      "expires_at": {
       "type": "string",
       "title": "Expires At"
      }
     },
     "type": "object",
     "required": [
      "reference",
      "role",
      "counterparty",
      "amount_cents",
      "currency",
      "description",
      "status",
      "failure_reason",
      "created_at",
      "expires_at"
     ],
     "title": "RequestOut"
    },
    "RequestPayIn": {
     "properties": {
      "card": {
       "$ref": "#/components/schemas/CardIn"
      }
     },
     "type": "object",
     "required": [
      "card"
     ],
     "title": "RequestPayIn"
    },
    "TransactionItem": {
     "properties": {
      "reference": {
       "type": "string",
       "title": "Reference"
      },
      "type": {
       "type": "string",
       "title": "Type"
      },
      "direction": {
       "type": "string",
       "enum": [
        "sent",
        "received"
       ],
       "title": "Direction"
      },
      "counterparty": {
       "type": "string",
       "title": "Counterparty"
      },
      "description": {
       "anyOf": [
        {
         "type": "string"
        },
        {
         "type": "null"
        }
       ],
       "title": "Description"
      },
      "card_last4": {
       "anyOf": [
        {
         "type": "string"
        },
        {
         "type": "null"
        }
       ],
       "title": "Card Last4"
      },
      "amount_cents": {
       "type": "integer",
       "title": "Amount Cents"
      },
      "currency": {
       "type": "string",
       "title": "Currency"
      },
      "status": {
       "type": "string",
       "title": "Status"
      },
      "created_at": {
       "type": "string",
       "title": "Created At"
      }
     },
     "type": "object",
     "required": [
      "reference",
      "type",
      "direction",
      "counterparty",
      "description",
      "card_last4",
      "amount_cents",
      "currency",
      "status",
      "created_at"
     ],
     "title": "TransactionItem"
    },
    "TransactionList": {
     "properties": {
      "items": {
       "items": {
        "$ref": "#/components/schemas/TransactionItem"
       },
       "type": "array",
       "title": "Items"
      },
      "next_cursor": {
       "anyOf": [
        {
         "type": "string"
        },
        {
         "type": "null"
        }
       ],
       "title": "Next Cursor"
      }
     },
     "type": "object",
     "required": [
      "items",
      "next_cursor"
     ],
     "title": "TransactionList"
    },
    "ValidationError": {
     "properties": {
      "loc": {
       "items": {
        "anyOf": [
         {
          "type": "string"
         },
         {
          "type": "integer"
         }
        ]
       },
       "type": "array",
       "title": "Location"
      },
      "msg": {
       "type": "string",
       "title": "Message"
      },
      "type": {
       "type": "string",
       "title": "Error Type"
      },
      "input": {
       "title": "Input"
      },
      "ctx": {
       "type": "object",
       "title": "Context"
      }
     },
     "type": "object",
     "required": [
      "loc",
      "msg",
      "type"
     ],
     "title": "ValidationError"
    }
   },
   "securitySchemes": {
    "HTTPBearer": {
     "type": "http",
     "scheme": "bearer"
    }
   }
  },
  "tags": [
   {
    "name": "Paiements",
    "description": "Envoyer et rembourser"
   },
   {
    "name": "Historique",
    "description": "Opérations envoyées et reçues"
   },
   {
    "name": "Compte",
    "description": "Solde, comptes liés et retraits"
   },
   {
    "name": "Demandes d'argent",
    "description": "Demander, payer, refuser, annuler"
   },
   {
    "name": "QR code",
    "description": "Recevoir de l'argent par QR code"
   },
   {
    "name": "Contacts",
    "description": "Carnet de contacts (clients Orbe)"
   }
  ],
  "servers": [
   {
    "url": "https://192.168.137.1/api/payments",
    "description": "Démonstrateur, à travers le WAF"
   },
   {
    "url": "http://localhost:8002",
    "description": "Service lancé en local"
   }
  ]
 }
};
