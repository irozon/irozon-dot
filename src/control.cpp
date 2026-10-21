#include "control.h"
#include "companion_pairing.h"
#include "control_policy.h"
#include "ui.h"
#include <Arduino.h>
#include <WiFi.h>
#include <esp_http_server.h>
#include <freertos/queue.h>
#include <lwip/sockets.h>

#if __has_include("control_config.h")
#include "control_config.h"
#endif
#ifndef IROZON_CONTROL_TOKEN
#define IROZON_CONTROL_TOKEN ""
#endif
#ifndef IROZON_CONTROL_ALLOWED_IP
#define IROZON_CONTROL_ALLOWED_IP ""
#endif

namespace {
using control_policy::Command;
httpd_handle_t server = nullptr;
StaticQueue_t queueStorage;
uint8_t queueBytes[4 * sizeof(Command)];
QueueHandle_t commands = nullptr;
portMUX_TYPE stateLock = portMUX_INITIALIZER_UNLOCKED;
struct State {
  bool on = true, connected = false;
  ui::Mode mode = ui::Mode::Green;
  usage::Status usage = usage::Status::NoData;
  uint32_t local = 0, mask = 0;
} shared;
bool enabled = false;
uint32_t allowed = 0, lastAttempt = 0;
char token[65] = IROZON_CONTROL_TOKEN;
uint32_t address(IPAddress ip) {
  return uint32_t(ip[0]) << 24 | uint32_t(ip[1]) << 16 | uint32_t(ip[2]) << 8 | ip[3];
}
uint32_t socketAddress(const sockaddr_storage& storage) {
  if (storage.ss_family == AF_INET)
    return ntohl(reinterpret_cast<const sockaddr_in*>(&storage)->sin_addr.s_addr);
#if CONFIG_LWIP_IPV6
  if (storage.ss_family == AF_INET6) {
    const auto& ip = reinterpret_cast<const sockaddr_in6*>(&storage)->sin6_addr;
    return control_policy::mappedIPv4(ip.s6_addr);
  }
#endif
  return 0;  // Native IPv6 is deliberately not a local IPv4 control interface.
}
State state() {
  portENTER_CRITICAL(&stateLock);
  State copy = shared;
  portEXIT_CRITICAL(&stateLock);
  return copy;
}
const char* usageName(usage::Status value) {
  switch (value) {
    case usage::Status::Live: return "live";
    case usage::Status::Partial: return "partial";
    case usage::Status::Stale: return "stale";
    case usage::Status::Offline: return "offline";
    case usage::Status::Setup: return "setup";
    case usage::Status::Test: return "test";
    default: return "no_data";
  }
}
esp_err_t reply(httpd_req_t* request, const char* status, const char* json) {
  httpd_resp_set_status(request, status);
  httpd_resp_set_type(request, "application/json");
  httpd_resp_set_hdr(request, "Cache-Control", "no-store");
  httpd_resp_set_hdr(request, "Connection", "close");
  return httpd_resp_send(request, json, HTTPD_RESP_USE_STRLEN);
}
bool permittedSocket(int socket) {
  const State current = state();
  sockaddr_storage peer{}, local{};
  socklen_t size = sizeof(peer);
  if (!current.connected || getpeername(socket, reinterpret_cast<sockaddr*>(&peer), &size) != 0) return false;
  size = sizeof(local);
  return getsockname(socket, reinterpret_cast<sockaddr*>(&local), &size) == 0 &&
         socketAddress(local) == current.local &&
         control_policy::localPeer(socketAddress(peer), current.local, current.mask, allowed);
}
esp_err_t openSocket(httpd_handle_t, int socket) {
  // Reject AP/foreign-subnet sockets before parsing any HTTP headers.
  return permittedSocket(socket) ? ESP_OK : ESP_FAIL;
}
esp_err_t handle(httpd_req_t* request) {
  const State current = state();
  if (!permittedSocket(httpd_req_to_sockfd(request)))
    return reply(request, "403 Forbidden", "{\"error\":\"local_access_only\"}");
  char authorization[72] = {};
  if (httpd_req_get_hdr_value_len(request, "Authorization") != 71 ||
      httpd_req_get_hdr_value_str(request, "Authorization", authorization, sizeof(authorization)) != ESP_OK ||
      !control_policy::authorized(authorization, token)) {
    httpd_resp_set_hdr(request, "WWW-Authenticate", "Bearer realm=\"Irozon Dot\"");
    return reply(request, "401 Unauthorized", "{\"error\":\"unauthorized\"}");
  }
  const Command command = control_policy::route(request->method == HTTP_GET, request->uri);
  if (command == Command::Invalid)
    return reply(request, "404 Not Found", "{\"error\":\"unknown_endpoint\"}");
  // Fixed paths are the entire command. No body parsing or configuration API.
  if (request->content_len != 0) {
    reply(request, "400 Bad Request", "{\"error\":\"body_not_supported\"}");
    return ESP_FAIL;  // Close without reading an untrusted/unbounded body.
  }
  if (command == Command::State) {
    const char* modes[] = {"green", "blue", "orange", "classic"};
    const char* names[] = {"Green Dashboard", "Blue Minimal", "Orange Numbers", "Classic Rings"};
    const unsigned mode = static_cast<unsigned>(current.mode);
    char json[384];
    snprintf(json, sizeof(json),
        "{\"display_on\":%s,\"mode\":\"%s\",\"mode_name\":\"%s\","
        "\"connection\":\"%s\",\"usage_status\":\"%s\","
        "\"backlight_control\":false,\"power_control\":\"panel_sleep\","
        "\"capabilities\":[\"heading\",\"usb_pairing\"]}",
        current.on ? "true" : "false", modes[mode], names[mode],
        current.connected ? "connected" : "offline", usageName(current.usage));
    return reply(request, "200 OK", json);
  }
  if (xQueueSend(commands, &command, 0) != pdTRUE)
    return reply(request, "503 Service Unavailable", "{\"error\":\"command_queue_full\"}");
  return reply(request, "202 Accepted", "{\"accepted\":true}");
}
}  // namespace

void control::begin() {
  if (companion_pairing::configured())
    strlcpy(token, companion_pairing::controlToken(), sizeof(token));
  commands = xQueueCreateStatic(4, sizeof(Command), queueBytes, &queueStorage);
  enabled = commands && control_policy::validToken(token);
  if (strlen(IROZON_CONTROL_ALLOWED_IP)) {
    IPAddress ip;
    if (!ip.fromString(IROZON_CONTROL_ALLOWED_IP) || (allowed = address(ip)) == 0) enabled = false;
  }
  Serial.println(enabled ? "Authenticated local display control configured (port 8080)" :
                           "Display HTTP control disabled: configure a dedicated token");
}

void control::poll(bool connected, bool provisioning, usage::Status usageStatus) {
  // Only the Arduino loop executes display operations and NVS writes.
  Command command;
  for (int i = 0; commands && i < 4 && xQueueReceive(commands, &command, 0) == pdTRUE; ++i) {
    if (command == Command::On || command == Command::Off) ui::setDisplayOn(command == Command::On);
    else if (command >= Command::Green && command <= Command::Classic)
      ui::selectMode(static_cast<ui::Mode>(static_cast<int>(command) - static_cast<int>(Command::Green)));
  }
  State next;
  next.on = ui::displayOn();
  next.mode = ui::mode();
  next.usage = usageStatus;
  next.connected = connected && !provisioning;
  if (next.connected) {
    next.local = address(WiFi.localIP());
    next.mask = address(WiFi.subnetMask());
  }
  portENTER_CRITICAL(&stateLock);
  shared = next;
  portEXIT_CRITICAL(&stateLock);
  if (!enabled) return;
  // Keep the HTTP task independent through Wi-Fi loss. Sockets are refused by
  // openSocket while offline/provisioning; never wait for httpd_stop in the loop.
  if (!next.connected) return;
  if (server || (lastAttempt && static_cast<uint32_t>(millis() - lastAttempt) < 15000)) return;
  lastAttempt = millis();
  httpd_config_t config = HTTPD_DEFAULT_CONFIG();
  config.server_port = 8080;  // WiFiManager retains exclusive provisioning port 80.
  config.max_open_sockets = 2;
  config.max_uri_handlers = 2;
  config.backlog_conn = 2;
  config.lru_purge_enable = true;
  config.recv_wait_timeout = 1;
  config.send_wait_timeout = 1;
  config.uri_match_fn = httpd_uri_match_wildcard;
  config.open_fn = openSocket;
  if (httpd_start(&server, &config) != ESP_OK) { server = nullptr; return; }
  httpd_uri_t get{};
  get.uri = "/api/*"; get.method = HTTP_GET; get.handler = handle;
  httpd_uri_t post = get; post.method = HTTP_POST;
  if (httpd_register_uri_handler(server, &get) != ESP_OK ||
      httpd_register_uri_handler(server, &post) != ESP_OK) {
    httpd_stop(server); server = nullptr;
  }
}
