#include "companion_pairing.h"
#include "control_policy.h"
#include "pairing_policy.h"
#include <Arduino.h>
#include <ArduinoJson.h>
#include <Preferences.h>
#include <WiFi.h>
#include <esp_system.h>

namespace {
char hostValue[16]{}, keyValue[65]{}, controlValue[65]{};
char input[384]{}, nonce[33]{};
size_t used = 0;
bool valid = false, discarded = false, restartPending = false;
uint32_t opened = 0, restartAt = 0;
bool privateHost(const char* value) {
  IPAddress ip;
  return value && ip.fromString(value) &&
    pairing_policy::privatePrefix(ip[0], ip[1]);
}
bool validLink(JsonDocument& doc) {
  return doc["host"].is<const char*>() && privateHost(doc["host"]) &&
    doc["pairing_key"].is<const char*>() && control_policy::validToken(doc["pairing_key"]) &&
    doc["control_token"].is<const char*>() && control_policy::validToken(doc["control_token"]);
}
void handleLine() {
  JsonDocument doc;
  if (deserializeJson(doc, input)) return;
  if (doc["irozon_probe"] == 1) {
    uint8_t random[16];
    esp_fill_random(random, sizeof(random));
    for (unsigned i = 0; i < sizeof(random); ++i) snprintf(nonce + i * 2, 3, "%02x", random[i]);
    Serial.printf("{\"irozon_probe\":1,\"nonce\":\"%s\"}\n", nonce);
    return;
  }
  if (doc["irozon_pair"] != 1 || !nonce[0] || !doc["nonce"].is<const char*>() ||
      !control_policy::equal(doc["nonce"], nonce) || !validLink(doc)) return;
  nonce[0] = 0;
  doc.remove("nonce"); doc.remove("irozon_pair");
  char encoded[256];
  const size_t length = serializeJson(doc, encoded, sizeof(encoded));
  if (length >= sizeof(encoded) - 1) return;
  Preferences prefs;
  const bool saved = prefs.begin("irozon-link", false) && prefs.putString("link", encoded) == length;
  prefs.end();
  memset(encoded, 0, sizeof(encoded));
  if (!saved) { Serial.println("{\"irozon_pair\":1,\"accepted\":false}"); return; }
  Serial.println("{\"irozon_pair\":1,\"accepted\":true}");
  restartAt = millis() + 300;
  restartPending = true;
}
}
void companion_pairing::begin() {
  opened = millis();
  Preferences prefs;
  if (!prefs.begin("irozon-link", true)) return;
  String encoded = prefs.getString("link", "");
  prefs.end();
  if (encoded.length() > 255) return;
  JsonDocument doc;
  if (deserializeJson(doc, encoded) || !validLink(doc)) return;
  strlcpy(hostValue, doc["host"], sizeof(hostValue));
  strlcpy(keyValue, doc["pairing_key"], sizeof(keyValue));
  strlcpy(controlValue, doc["control_token"], sizeof(controlValue));
  valid = true;
}
void companion_pairing::poll() {
  if (restartPending) {
    if (static_cast<int32_t>(millis() - restartAt) >= 0) ESP.restart();
    return;
  }
  // Physical USB during the first minute only; no HTTP provisioning route.
  if (!pairing_policy::windowOpen(millis(), opened)) return;
  for (unsigned budget = 0; budget < 128 && Serial.available(); ++budget) {
    const char c = Serial.read();
    if (c == '\n') {
      if (!discarded) { input[used] = 0; handleLine(); }
      memset(input, 0, sizeof(input)); used = 0; discarded = false;
    } else if (!discarded && c != '\r') {
      if (used + 1 < sizeof(input)) input[used++] = c;
      else discarded = true;
    }
  }
}
bool companion_pairing::configured() { return valid; }
const char* companion_pairing::host() { return hostValue; }
const char* companion_pairing::key() { return keyValue; }
const char* companion_pairing::controlToken() { return controlValue; }
