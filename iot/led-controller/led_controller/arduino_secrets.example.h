// Copier ce fichier en arduino_secrets.h (même dossier que le .ino) et le compléter.
// arduino_secrets.h est ignoré par Git : aucun mot de passe dans le dépôt.
#pragma once

// Point d'accès mobile Windows du PC Hôte (2,4 GHz obligatoire pour l'ESP)
#define WIFI_SSID "RESILIENCE-G1"
#define WIFI_PASSWORD "mot-de-passe-du-hotspot"

// WAF du PC Hôte (HTTPS), qui transmet GET /devices/led à auth-service
#define BACKEND_HOST "192.168.137.1"
#define BACKEND_PORT 443
#define BACKEND_HTTPS 1
// Pile dev (docker-compose.dev.led.yml) : IP du PC, port 8011, BACKEND_HTTPS 0

// Clé d'appareil : contenu de secrets/led_device_key (créé par scripts/init_dev_secrets.py)
#define LED_DEVICE_KEY "orbe_led_..."
