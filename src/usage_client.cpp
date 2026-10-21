#include "usage_client.h"
#include "companion_pairing.h"
#include "pairing_policy.h"
#include <Arduino.h>
#include <HTTPClient.h>
#include <WiFi.h>
#include <ArduinoJson.h>
#include <esp_system.h>
#include <esp_timer.h>
#include <mbedtls/md.h>
#include <cmath>
#include <cstring>

#if __has_include("companion_config.h")
#include "companion_config.h"
#endif
#ifndef IROZON_COMPANION_HOST
#define IROZON_COMPANION_HOST ""
#endif
#ifndef IROZON_PAIRING_KEY
#define IROZON_PAIRING_KEY ""
#endif

namespace {
const char* pairedHost() {
  return companion_pairing::configured() ? companion_pairing::host() : IROZON_COMPANION_HOST;
}
const char* pairedKey() {
  return companion_pairing::configured() ? companion_pairing::key() : IROZON_PAIRING_KEY;
}
usage::Snapshot saved;
uint64_t receivedAt = 0;
uint32_t sourceAge = 0;
bool haveSample = false, latestLive = false, lastFetchOk = false;
uint64_t secondsNow() { return esp_timer_get_time() / 1000000; }
int hex(char c) {
  if (c >= '0' && c <= '9') return c - '0';
  if (c >= 'a' && c <= 'f') return c - 'a' + 10;
  return -1;
}
bool decodeHex(const char* input, uint8_t* output, size_t count) {
  if (strlen(input) != count * 2) return false;
  for (size_t i = 0; i < count; ++i) {
    int a = hex(input[i * 2]), b = hex(input[i * 2 + 1]);
    if (a < 0 || b < 0) return false;
    output[i] = (a << 4) | b;
  }
  return true;
}
bool authenticate(const String& body, const String& signature) {
  uint8_t key[32], expected[32], actual[32];
  if (!decodeHex(pairedKey(), key, 32) ||
      !decodeHex(signature.c_str(), actual, 32)) return false;
  const auto* md = mbedtls_md_info_from_type(MBEDTLS_MD_SHA256);
  if (mbedtls_md_hmac(md, key, sizeof(key),
      reinterpret_cast<const uint8_t*>(body.c_str()), body.length(), expected) != 0) return false;
  uint8_t difference = 0;
  for (size_t i = 0; i < 32; ++i) difference |= expected[i] ^ actual[i];
  return difference == 0;
}
bool parseWindow(JsonVariantConst value, uint32_t serverTime, usage::Window& window) {
  if (value.isNull()) return true;
  if (!value.is<JsonObjectConst>() || !value["remaining"].is<float>() ||
      !value["reset_at"].is<uint32_t>()) return false;
  const float remaining = value["remaining"].as<float>();
  const uint32_t reset = value["reset_at"].as<uint32_t>();
  if (!std::isfinite(remaining) || remaining < 0 || remaining > 100 ||
      reset <= serverTime || reset - serverTime > 604800 + 300) return false;
  window = {true, remaining, reset - serverTime};
  return true;
}
}  // namespace

bool usage_client::configured() {
  uint8_t key[32];
  return strlen(pairedHost()) != 0 && decodeHex(pairedKey(), key, 32);
}

void usage_client::fetch() {
  lastFetchOk = false;
  if (!configured() || WiFi.status() != WL_CONNECTED) return;
  char nonce[33];
  uint8_t random[16];
  esp_fill_random(random, sizeof(random));
  for (int i = 0; i < 16; ++i) snprintf(nonce + i * 2, 3, "%02x", random[i]);
  WiFiClient socket;
  HTTPClient http;
  http.setConnectTimeout(2000);
  http.setTimeout(2000);
  http.setFollowRedirects(HTTPC_DISABLE_FOLLOW_REDIRECTS);
  String url = String("http://") + pairedHost() + ":8787/usage?nonce=" + nonce;
  if (!http.begin(socket, url)) return;
  const char* headers[] = {"X-Irozon-Signature"};
  http.collectHeaders(headers, 1);
  if (http.GET() != HTTP_CODE_OK || http.getSize() <= 0 || http.getSize() > 1536) {
    http.end();
    return;
  }
  const int expectedSize = http.getSize();
  const String signature = http.header(headers[0]);
  const String body = http.getString();
  http.end();
  if (body.length() != static_cast<unsigned>(expectedSize) || !authenticate(body, signature)) return;
  JsonDocument doc;
  if (deserializeJson(doc, body)) return;
  if (doc["version"] != 1 || doc["source"] != "codex" ||
      !doc["test_data"].is<bool>() || doc["test_data"].as<bool>() ||
      doc["nonce"] != nonce || !doc["server_time"].is<uint32_t>() ||
      !doc["sampled_at"].is<uint32_t>() || doc["weekly"].isUnbound() ||
      doc["session"].isUnbound()) return;
  const uint32_t serverTime = doc["server_time"];
  const uint32_t sampledAt = doc["sampled_at"];
  if (serverTime < 1700000000 || sampledAt > serverTime) return;
  const char* state = doc["status"] | "";
  if (strcmp(state, "live") && strcmp(state, "stale") && strcmp(state, "unavailable")) return;
  usage::Snapshot next;
  if (!doc["heading"].isNull()) {
    if (!doc["heading"].is<const char*>()) return;
    if (!next.heading.assign(doc["heading"].as<const char*>())) return;
  }
  if (!parseWindow(doc["weekly"], serverTime, next.weekly) ||
      !parseWindow(doc["session"], serverTime, next.session)) return;
  saved = next;
  receivedAt = secondsNow();
  sourceAge = serverTime - sampledAt;
  haveSample = true;
  latestLive = strcmp(state, "live") == 0 && sourceAge <= 150;
  lastFetchOk = true;
}

usage::Snapshot usage_client::snapshot() {
  auto result = saved;
  const uint64_t elapsed = secondsNow() - receivedAt;
  for (auto* window : {&result.weekly, &result.session}) {
    window->resetInSeconds = usage::countdown(window->resetInSeconds, elapsed);
    if (haveSample && window->resetInSeconds == 0) window->available = false;
  }
  return result;
}

usage::Status usage_client::status() {
  if (!haveSample || (!saved.weekly.available && !saved.session.available)) return usage::Status::NoData;
  if (!lastFetchOk || !latestLive || sourceAge + secondsNow() - receivedAt > 150)
    return usage::Status::Stale;
  const auto data = snapshot();
  if (!data.weekly.available && !data.session.available) return usage::Status::NoData;
  return data.weekly.available && data.session.available ? usage::Status::Live : usage::Status::Partial;
}
