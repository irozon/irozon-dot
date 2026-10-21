#include <Arduino.h>
#include <WiFi.h>
#include <WiFiManager.h>
#include <esp_timer.h>
#include "config.h"
#include "ui.h"
#include "usage_client.h"
#include "button.h"
#include "control.h"
#include "companion_pairing.h"

namespace {
WiFiManager wifi;
uint64_t startedUs;
uint32_t lastDrawSecond = UINT32_MAX;
uint32_t lastFetch = 0;
bool fetched = false;
uint32_t lastRetry = 0;
int lastState = -1;

}  // namespace

void setup() {
  Serial.begin(115200);  // Never wait for a serial monitor to be attached.
  companion_pairing::begin();
  button::begin();
  startedUs = esp_timer_get_time();
  ui::begin();
  control::begin();
#ifdef IROZON_DEMO
  ui::draw(usage::simulated(0), usage::Status::Test);
  Serial.println("Irozon Dot - TEST DATA simulation build");
#else
  ui::draw({}, usage::Status::NoData);
  Serial.println("Irozon Dot - live mode; no simulated fallback");
  if (!usage_client::configured()) Serial.println("Companion pairing is not configured");
#endif
  WiFi.mode(WIFI_STA);
  WiFi.setHostname(config::kHostname);
  wifi.setDebugOutput(false);
  wifi.setConfigPortalBlocking(false);
  wifi.setConnectTimeout(10);  // Only initial saved-network attempt may wait.
  wifi.setConfigPortalTimeout(0);
  wifi.autoConnect(config::kPortalApName);
  WiFi.setAutoReconnect(true);
  if (wifi.getConfigPortalActive()) {
    Serial.println("Wi-Fi setup: join Irozon-Dot-Setup, open http://192.168.4.1");
  }
}

void loop() {
  const uint32_t now = millis();
  companion_pairing::poll();
  wifi.process();
  const bool connected = WiFi.status() == WL_CONNECTED;
  if (connected && wifi.getConfigPortalActive()) {
    wifi.stopConfigPortal();
  }
  if (!connected && !wifi.getConfigPortalActive() &&
      static_cast<uint32_t>(now - lastRetry) >= config::kReconnectMs) {
    lastRetry = now;
    WiFi.reconnect();
  }

  // On release: tap cycles mode, 2 s toggles standby, 8 s clears Wi-Fi.
  // Holding BOOT while resetting instead invokes the chip's ROM downloader.
  const auto gesture = button::poll();
  if (gesture.resetWifi) {
    wifi.resetSettings();
    ESP.restart();
    return;
  }
  if (gesture.powerToggles & 1) {
    // Same state, persistence and panel-sleep path as HA's HTTP commands.
    ui::setDisplayOn(!ui::displayOn());
    lastDrawSecond = UINT32_MAX;
  }
  if (gesture.taps) {
    for (uint8_t i = 0; i < gesture.taps; ++i) ui::cycleMode();
    lastDrawSecond = UINT32_MAX;
  }

  const int state = connected ? 1 : (wifi.getConfigPortalActive() ? 2 : 0);
#ifdef IROZON_DEMO
  control::poll(connected, wifi.getConfigPortalActive(), usage::Status::Test);
#else
  control::poll(connected, wifi.getConfigPortalActive(), state == 2 ? usage::Status::Setup :
                !connected ? usage::Status::Offline : usage_client::status());
#endif
#ifndef IROZON_DEMO
  if (connected && (!fetched || state != lastState ||
      static_cast<uint32_t>(now - lastFetch) >= 30000)) {
    lastFetch = now;
    fetched = true;
    usage_client::fetch();
  }
#endif
  const uint64_t elapsed = (esp_timer_get_time() - startedUs) / 1000000;
  if (elapsed != lastDrawSecond || state != lastState) {
#ifdef IROZON_DEMO
    ui::draw(usage::simulated(elapsed), usage::Status::Test);
#else
    ui::draw(usage_client::snapshot(), state == 2 ? usage::Status::Setup :
             !connected ? usage::Status::Offline : usage_client::status());
#endif
    if (state != lastState && connected) {
      Serial.printf("Wi-Fi connected. IP: %s\n", WiFi.localIP().toString().c_str());
    }
    lastDrawSecond = elapsed;
    lastState = state;
  }
#ifdef IROZON_DEMO
  ui::animate();
#else
  // Defer the cosmetic movement if a synchronous usage fetch is imminent.
  // Never postpone the existing fetch schedule to complete an animation.
  ui::animate(connected && fetched && static_cast<uint32_t>(millis() - lastFetch) < 28000);
#endif
  delay(10);
}
