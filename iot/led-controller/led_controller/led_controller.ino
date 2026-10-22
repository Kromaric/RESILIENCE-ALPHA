// Orbe — LED d'état de la connexion au back-office (consigne additionnelle 1)
//
// La carte se connecte au hotspot du PC Hôte et interroge toutes les 300 ms la route
// d'auth-service GET /devices/led (via le WAF, en HTTPS), avec sa clé d'appareil :
//   {"state": "green_blink", "seq": 12, "remaining_ms": null, "blinks": null,
//    "blink_period_ms": 500}
// « seq » change à chaque nouvel état : la carte (re)lance alors le motif et le joue
// elle-même, sans bloquer. Une coupure réseau n'empêche pas un motif limité dans le temps
// de se terminer ; un motif sans fin (vert clignotant) s'éteint après 10 s sans réponse.
//
// Au démarrage, les deux LED sont allumées jusqu'à la première réponse valide du serveur :
// elles signalent une carte démarrée mais pas encore connectée.
//
// Test sans serveur : taper le nom d'un motif dans le moniteur série (115200 bauds).
//
// Arduino IDE :
//   - carte : « ESP32 Dev Module » (paquet « esp32 by Espressif Systems »)
//   - bibliothèque : « ArduinoJson » v7 (Benoit Blanchon)
//   - copier arduino_secrets.example.h en arduino_secrets.h, dans ce même dossier

#include <Arduino.h>

#if defined(ESP8266)
#include <ESP8266HTTPClient.h>
#include <ESP8266WiFi.h>
#include <WiFiClientSecureBearSSL.h>
#else
#include <HTTPClient.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#endif

#include <ArduinoJson.h>

#if __has_include("arduino_secrets.h")
#include "arduino_secrets.h"
#else
#error "Copiez arduino_secrets.example.h en arduino_secrets.h (même dossier) et complétez-le"
#endif

// HTTPS par défaut (WAF de la pile de démonstration) ; 0 = HTTP simple, pour le relais
// de la pile dev (docker-compose.dev.led.yml, port 8011)
#ifndef BACKEND_HTTPS
#define BACKEND_HTTPS 1
#endif

// Broches des LED (via une résistance de 220 ohms chacune, voir cablage.svg)
#if defined(ESP8266)
#define PIN_GREEN 5  // D1 sur une NodeMCU
#define PIN_RED 4    // D2
#else
#define PIN_GREEN 25  // P25 sur la carte ESP32 38 broches
#define PIN_RED 26    // P26
#endif

static const char *LED_PATH = "/devices/led";
static const unsigned long POLL_EVERY_MS = 300;
static const unsigned long OFFLINE_AFTER_MS = 10000;   // sans réponse du serveur
static const unsigned long DEFAULT_PERIOD_MS = 500;    // période de clignotement par défaut
static const unsigned long DEFAULT_FIXED_MS = 30000;   // commandes série : vert ou rouge fixe
static const int DEFAULT_RED_BLINKS = 10;
static const unsigned long WIFI_RETRY_MS = 10000;

enum class Pattern { Off, GreenBlink, GreenFixed, RedFixed, RedBlink };

struct LedState {
  Pattern pattern = Pattern::Off;
  unsigned long startedAt = 0;
  unsigned long durationMs = 0;  // 0 = jusqu'au prochain état
  unsigned long halfMs = DEFAULT_PERIOD_MS / 2;
  unsigned long lastToggle = 0;
  bool lit = false;
  int blinksWanted = 0;
  int blinksDone = 0;
};

static LedState led;
static long lastSeq = -1;
static unsigned long lastPoll = 0;
static unsigned long lastOk = 0;
static unsigned long lastWifiAttempt = 0;
static int lastHttpCode = 0;

#if defined(ESP8266)
static BearSSL::WiFiClientSecure tls;
#else
static WiFiClientSecure tls;
#endif
static WiFiClient plain;
static HTTPClient http;

// --- LED -----------------------------------------------------------------------------

static void writeLeds(bool green, bool red) {
  digitalWrite(PIN_GREEN, green ? HIGH : LOW);
  digitalWrite(PIN_RED, red ? HIGH : LOW);
}

static const char *patternName(Pattern p) {
  switch (p) {
    case Pattern::GreenBlink: return "green_blink";
    case Pattern::GreenFixed: return "green_fixed";
    case Pattern::RedFixed: return "red_fixed";
    case Pattern::RedBlink: return "red_blink";
    default: return "off";
  }
}

static bool parsePattern(const char *name, Pattern &out) {
  if (strcmp(name, "off") == 0) out = Pattern::Off;
  else if (strcmp(name, "green_blink") == 0) out = Pattern::GreenBlink;
  else if (strcmp(name, "green_fixed") == 0) out = Pattern::GreenFixed;
  else if (strcmp(name, "red_fixed") == 0) out = Pattern::RedFixed;
  else if (strcmp(name, "red_blink") == 0) out = Pattern::RedBlink;
  else return false;
  return true;
}

static void startPattern(Pattern p, unsigned long durationMs, int blinks, unsigned long periodMs) {
  unsigned long now = millis();
  led.pattern = p;
  led.startedAt = now;
  led.lastToggle = now;
  led.durationMs = durationMs;
  led.halfMs = max(50UL, periodMs / 2);
  led.blinksWanted = blinks;
  led.blinksDone = 0;
  led.lit = (p != Pattern::Off);

  switch (p) {
    case Pattern::GreenBlink:
    case Pattern::GreenFixed: writeLeds(true, false); break;
    case Pattern::RedFixed:
    case Pattern::RedBlink: writeLeds(false, true); break;
    default: writeLeds(false, false); break;
  }
  Serial.printf("[led] %s (durée %lu ms, clignotements %d)\n", patternName(p), durationMs, blinks);
}

// Fait avancer le motif en cours, sans bloquer.
static void tickLed() {
  unsigned long now = millis();
  if (led.pattern == Pattern::Off) return;

  if (led.durationMs > 0 && now - led.startedAt >= led.durationMs) {
    startPattern(Pattern::Off, 0, 0, DEFAULT_PERIOD_MS);
    return;
  }
  if (now - led.lastToggle < led.halfMs) return;

  if (led.pattern == Pattern::GreenBlink) {
    led.lastToggle = now;
    led.lit = !led.lit;
    writeLeds(led.lit, false);
  } else if (led.pattern == Pattern::RedBlink) {
    led.lastToggle = now;
    led.lit = !led.lit;
    if (!led.lit && ++led.blinksDone >= led.blinksWanted) {
      startPattern(Pattern::Off, 0, 0, DEFAULT_PERIOD_MS);
      return;
    }
    writeLeds(false, led.lit);
  }
}

// --- Serveur -------------------------------------------------------------------------

// Applique un nouvel état reçu d'auth-service.
static void applyServerState(Pattern p, long remainingMs, int blinks, unsigned long periodMs) {
  unsigned long duration = remainingMs > 0 ? (unsigned long)remainingMs : 0;
  if (p == Pattern::RedBlink) {
    // Si l'état a été lu en retard, ne jouer que les clignotements restants
    int left = blinks > 0 ? blinks : DEFAULT_RED_BLINKS;
    if (remainingMs > 0) left = min(left, (int)((remainingMs + periodMs - 1) / periodMs));
    startPattern(p, 0, max(left, 1), periodMs);
  } else {
    startPattern(p, duration, 0, periodMs);
  }
}

static void pollServer() {
  http.setTimeout(2000);
  bool started = BACKEND_HTTPS ? http.begin(tls, BACKEND_HOST, BACKEND_PORT, LED_PATH, true)
                               : http.begin(plain, BACKEND_HOST, BACKEND_PORT, LED_PATH, false);
  if (!started) {
    lastHttpCode = -1;
    return;
  }
  http.setReuse(true);  // garde la connexion TLS ouverte entre deux interrogations
  http.setUserAgent("orbe-led/1.0");
  http.addHeader("Accept", "application/json");
  http.addHeader("X-Device-Key", LED_DEVICE_KEY);

  int code = http.GET();
  lastHttpCode = code;
  if (code == 200) {
    JsonDocument doc;
    DeserializationError error = deserializeJson(doc, http.getString());
    Pattern p;
    if (!error && parsePattern(doc["state"] | "", p)) {
      lastOk = millis();
      long seq = doc["seq"] | -1L;
      if (seq != lastSeq) {
        lastSeq = seq;
        long remaining = doc["remaining_ms"].isNull() ? 0L : (doc["remaining_ms"] | 0L);
        unsigned long period = doc["blink_period_ms"] | DEFAULT_PERIOD_MS;
        applyServerState(p, remaining, doc["blinks"] | 0, period ? period : DEFAULT_PERIOD_MS);
      }
    } else {
      Serial.println("[http] réponse illisible");
    }
  } else if (code == 401) {
    Serial.println("[http] clé d'appareil refusée (LED_DEVICE_KEY)");
  } else {
    Serial.printf("[http] échec : %d\n", code);
  }
  http.end();
}

static void ensureWifi() {
  if (WiFi.status() == WL_CONNECTED) return;
  unsigned long now = millis();
  if (lastWifiAttempt != 0 && now - lastWifiAttempt < WIFI_RETRY_MS) return;
  lastWifiAttempt = now;
  Serial.printf("[wifi] connexion à %s…\n", WIFI_SSID);
  WiFi.disconnect();
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
}

// --- Moniteur série (tests sans serveur) ---------------------------------------------

static void readSerial() {
  static String line;
  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c != '\n' && c != '\r') {
      if (line.length() < 32) line += c;
      continue;
    }
    line.trim();
    if (line.length() == 0) continue;
    Pattern p;
    if (parsePattern(line.c_str(), p)) {
      unsigned long fixed =
          (p == Pattern::GreenFixed || p == Pattern::RedFixed) ? DEFAULT_FIXED_MS : 0;
      startPattern(p, fixed, p == Pattern::RedBlink ? DEFAULT_RED_BLINKS : 0, DEFAULT_PERIOD_MS);
    } else if (line == "status") {
      Serial.printf("[status] wifi=%s ip=%s serveur=%s://%s:%d http=%d seq=%ld led=%s\n",
                    WiFi.status() == WL_CONNECTED ? "ok" : "non",
                    WiFi.localIP().toString().c_str(), BACKEND_HTTPS ? "https" : "http",
                    BACKEND_HOST, BACKEND_PORT, lastHttpCode,
                    lastSeq, patternName(led.pattern));
    } else {
      Serial.println("Commandes : off, green_blink, green_fixed, red_fixed, red_blink, status");
    }
    line = "";
  }
}

// --- Programme -----------------------------------------------------------------------

void setup() {
  pinMode(PIN_GREEN, OUTPUT);
  pinMode(PIN_RED, OUTPUT);
  writeLeds(true, true);  // témoin de démarrage, jusqu'à la première réponse du serveur

  Serial.begin(115200);
  delay(200);
  Serial.println("\nOrbe — LED du back-office");

  // Chiffré, sans vérification du certificat (certificat du WAF auto-signé, carte
  // jointe par adresse IP) : limite documentée dans le README.
  tls.setInsecure();
#if !defined(ESP8266)
  WiFi.setHostname("orbe-led");
#endif
  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
}

void loop() {
  ensureWifi();
  unsigned long now = millis();
  if (WiFi.status() == WL_CONNECTED && now - lastPoll >= POLL_EVERY_MS) {
    lastPoll = now;
    pollServer();
  }
  // Serveur muet : ne pas laisser un motif sans fin allumé
  if (led.pattern != Pattern::Off && led.durationMs == 0 && led.pattern != Pattern::RedBlink &&
      lastOk != 0 && millis() - lastOk > OFFLINE_AFTER_MS) {
    Serial.println("[http] serveur injoignable depuis 10 s : LED éteinte");
    startPattern(Pattern::Off, 0, 0, DEFAULT_PERIOD_MS);
    lastSeq = -1;  // réappliquer l'état dès le retour du serveur
  }
  tickLed();
  readSerial();
  delay(5);
}
