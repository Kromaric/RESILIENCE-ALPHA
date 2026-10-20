// Généré par scripts/export_openapi.py — ne pas modifier à la main.
window.ORBE_SPECS = {
 "auth-service": {
  "openapi": "3.1.0",
  "info": {
   "title": "Orbe — auth-service",
   "description": "Authentification forte des clients Orbe : mot de passe puis passkey WebAuthn (biométrie vérifiée par l'appareil), sessions révocables (JWT RS256 de 15 min), applications clientes et clés d'API partenaires. Exposé par le WAF sous `/api/auth`. Erreurs : `{\"detail\": {\"code\", \"message\"}}`. Voir CADRAGE §4.2.",
   "version": "0.1.0"
  },
  "paths": {
   "/register": {
    "post": {
     "tags": [
      "Authentification"
     ],
     "summary": "Créer un compte",
     "description": "Crée un compte client. Étape suivante : `POST /login`, puis enregistrer une passkey.\n\nHors périmètre du démonstrateur : vérification de l'email et du téléphone, KYC.",
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
   "/login/passkey": {
    "post": {
     "tags": [
      "Authentification"
     ],
     "summary": "Se connecter — étape 2 : passkey (Face ID, Windows Hello)",
     "operationId": "login_passkey_login_passkey_post",
     "requestBody": {
      "content": {
       "application/json": {
        "schema": {
         "$ref": "#/components/schemas/PasskeyLoginRequest"
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
       "description": "Passkey refusée ou session expirée",
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
   "/passkeys/register/options": {
    "post": {
     "tags": [
      "Passkeys"
     ],
     "summary": "Préparer l'enregistrement d'une passkey",
     "description": "Options à passer à `navigator.credentials.create()`.",
     "operationId": "registration_options_passkeys_register_options_post",
     "responses": {
      "200": {
       "description": "Successful Response",
       "content": {
        "application/json": {
         "schema": {
          "additionalProperties": true,
          "type": "object",
          "title": "Response Registration Options Passkeys Register Options Post"
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
       "description": "Session sans passkey alors que le compte en a",
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
   "/passkeys/register": {
    "post": {
     "tags": [
      "Passkeys"
     ],
     "summary": "Enregistrer la passkey de cet appareil",
     "operationId": "register_passkeys_register_post",
     "requestBody": {
      "content": {
       "application/json": {
        "schema": {
         "$ref": "#/components/schemas/PasskeyRegisterRequest"
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
          "$ref": "#/components/schemas/PasskeyOut"
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
       "description": "Session sans passkey alors que le compte en a",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "409": {
       "description": "Aucun enregistrement en cours, ou passkey déjà connue",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "422": {
       "description": "Réponse de l'appareil refusée",
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
   "/passkeys": {
    "get": {
     "tags": [
      "Passkeys"
     ],
     "summary": "Mes appareils",
     "operationId": "list_passkeys_passkeys_get",
     "responses": {
      "200": {
       "description": "Successful Response",
       "content": {
        "application/json": {
         "schema": {
          "items": {
           "$ref": "#/components/schemas/PasskeyOut"
          },
          "type": "array",
          "title": "Response List Passkeys Passkeys Get"
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
       "description": "Session sans passkey alors que le compte en a",
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
   "/passkeys/{passkey_id}": {
    "delete": {
     "tags": [
      "Passkeys"
     ],
     "summary": "Retirer un appareil",
     "operationId": "delete_passkey_passkeys__passkey_id__delete",
     "security": [
      {
       "HTTPBearer": []
      }
     ],
     "parameters": [
      {
       "name": "passkey_id",
       "in": "path",
       "required": true,
       "schema": {
        "type": "string",
        "title": "Passkey Id"
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
       "description": "Session sans passkey alors que le compte en a",
       "content": {
        "application/json": {
         "schema": {
          "$ref": "#/components/schemas/ErrorOut"
         }
        }
       }
      },
      "404": {
       "description": "Passkey inconnue",
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
      "webauthn_options": {
       "anyOf": [
        {
         "additionalProperties": true,
         "type": "object"
        },
        {
         "type": "null"
        }
       ],
       "title": "Webauthn Options"
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
      "passkey_enrollment_required": {
       "type": "boolean",
       "title": "Passkey Enrollment Required",
       "default": false
      }
     },
     "type": "object",
     "required": [
      "mfa_required",
      "session_id"
     ],
     "title": "LoginResponse",
     "description": "Étape 1 de la connexion.\n\n- `mfa_required = true` : valider la passkey avec `webauthn_options`, puis\n  `POST /login/passkey` ;\n- sinon : `token` est fourni. `passkey_enrollment_required = true` signale un compte\n  sans passkey : la session ne permet que de consulter et d'enregistrer une passkey."
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
      "passkey_count": {
       "type": "integer",
       "title": "Passkey Count"
      }
     },
     "type": "object",
     "required": [
      "client_id",
      "email",
      "phone_masked",
      "display_name",
      "factors",
      "passkey_count"
     ],
     "title": "MeResponse"
    },
    "PasskeyLoginRequest": {
     "properties": {
      "session_id": {
       "type": "string",
       "maxLength": 36,
       "minLength": 36,
       "title": "Session Id"
      },
      "credential": {
       "additionalProperties": true,
       "type": "object",
       "title": "Credential",
       "description": "Réponse de navigator.credentials.get()"
      }
     },
     "type": "object",
     "required": [
      "session_id",
      "credential"
     ],
     "title": "PasskeyLoginRequest"
    },
    "PasskeyOut": {
     "properties": {
      "id": {
       "type": "string",
       "title": "Id"
      },
      "device_name": {
       "type": "string",
       "title": "Device Name"
      },
      "created_at": {
       "type": "string",
       "title": "Created At"
      },
      "last_used_at": {
       "anyOf": [
        {
         "type": "string"
        },
        {
         "type": "null"
        }
       ],
       "title": "Last Used At"
      }
     },
     "type": "object",
     "required": [
      "id",
      "device_name",
      "created_at",
      "last_used_at"
     ],
     "title": "PasskeyOut"
    },
    "PasskeyRegisterRequest": {
     "properties": {
      "credential": {
       "additionalProperties": true,
       "type": "object",
       "title": "Credential",
       "description": "Réponse de navigator.credentials.create()"
      },
      "device_name": {
       "type": "string",
       "maxLength": 80,
       "minLength": 1,
       "title": "Device Name",
       "default": "Mon appareil"
      }
     },
     "type": "object",
     "required": [
      "credential"
     ],
     "title": "PasskeyRegisterRequest"
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
       "description": "12 caractères minimum"
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
    "description": "Connexion en deux étapes (mot de passe, puis passkey) et profil"
   },
   {
    "name": "Passkeys",
    "description": "Appareils WebAuthn (Face ID, Windows Hello)"
   },
   {
    "name": "Partenaires",
    "description": "Clés d'API des partenaires"
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
 "payment-service": {
  "openapi": "3.1.0",
  "info": {
   "title": "Orbe — payment-service",
   "description": "Paiements entre clients Orbe : transferts payés par carte de test, demandes d'argent, QR code, remboursements, solde et retraits fictifs. Exposé par le WAF sous `/api/payments`.\n\n- Authentification : `Authorization: Bearer <JWT>` obtenu sur auth-service ; la session ne doit pas être révoquée. Déplacer de l'argent exige une session confirmée par passkey (`403 second_factor_required` sinon).\n- Opérations qui déplacent de l'argent : en-tête `Idempotency-Key` (UUID) obligatoire ; `201` à la création, `200` si la même clé est rejouée.\n- Un refus de carte n'est pas une erreur HTTP : `201` avec `status: declined`.\n- Plafond : 500 € par opération. Chaque opération autorisée passe deux écritures comptables (débit, crédit).\n- Cartes de test : `4242 4242 4242 4242` (acceptée), `4000 0000 0000 0002` (refusée), `…0069` (expirée), `…9995` (fonds insuffisants).\n\nVoir CADRAGE §4.3.",
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
       "description": "Session non confirmée par passkey",
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
       "description": "Session non confirmée par passkey",
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
       "description": "Session non confirmée par passkey",
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
       "description": "Session non confirmée par passkey",
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
       "description": "Session non confirmée par passkey",
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
       "description": "Session non confirmée par passkey",
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
       "description": "Session non confirmée par passkey",
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
       "description": "Session non confirmée par passkey",
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
       "description": "Session non confirmée par passkey",
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
