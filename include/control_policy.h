#pragma once
#include <cstdint>

// Portable request policy; the compile-time checks exercise the same functions
// used by the real HTTP handlers, without opening a listener or using secrets.
namespace control_policy {
enum class Command { Invalid, State, On, Off, Green, Classic, Companion, AnalogClock };
constexpr unsigned length(const char* s) {
  unsigned n = 0;
  while (s[n]) ++n;
  return n;
}
constexpr bool equal(const char* a, const char* b) {
  for (unsigned i = 0;; ++i) {
    if (a[i] != b[i]) return false;
    if (!a[i]) return true;
  }
}
constexpr bool validToken(const char* token) {
  if (length(token) != 64) return false;
  for (unsigned i = 0; i < 64; ++i)
    if (!((token[i] >= '0' && token[i] <= '9') ||
          (token[i] >= 'a' && token[i] <= 'f'))) return false;
  return true;
}
constexpr bool authorized(const char* header, const char* token) {
  if (!validToken(token) || length(header) != 71) return false;
  const char prefix[] = "Bearer ";
  unsigned difference = 0;
  for (unsigned i = 0; i < 7; ++i) difference |= header[i] ^ prefix[i];
  for (unsigned i = 0; i < 64; ++i) difference |= header[i + 7] ^ token[i];
  return difference == 0;
}
constexpr bool localPeer(uint32_t peer, uint32_t local, uint32_t mask, uint32_t allowed) {
  const bool privateLocal = (local >> 24) == 10 || (local >> 20) == 0xac1 || (local >> 16) == 0xc0a8;
  return privateLocal && mask != 0 && peer != 0 && peer != local &&
         (peer & mask) == (local & mask) && (!allowed || peer == allowed);
}
constexpr uint32_t mappedIPv4(const uint8_t* bytes) {
  for (unsigned i = 0; i < 10; ++i) if (bytes[i]) return 0;
  if (bytes[10] != 255 || bytes[11] != 255) return 0;
  return uint32_t(bytes[12]) << 24 | uint32_t(bytes[13]) << 16 |
         uint32_t(bytes[14]) << 8 | bytes[15];
}
constexpr Command route(bool get, const char* path) {
  if (get) return equal(path, "/api/state") ? Command::State : Command::Invalid;
  return equal(path, "/api/display/on") ? Command::On :
         equal(path, "/api/display/off") ? Command::Off :
         equal(path, "/api/display/mode/green") ? Command::Green :
         equal(path, "/api/display/mode/classic") ? Command::Classic :
         equal(path, "/api/display/mode/companion") ? Command::Companion :
         equal(path, "/api/display/mode/analog") ? Command::AnalogClock : Command::Invalid;
}
// Public fixtures only; never production authentication material.
constexpr char testToken[] = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef";
constexpr uint8_t mappedTest[] = {0,0,0,0,0,0,0,0,0,0,255,255,192,168,86,26};
constexpr uint8_t nativeIPv6Test[] = {0x20,1,0xdb,8,0,0,0,0,0,0,0,0,0,0,0,1};
static_assert(mappedIPv4(mappedTest) == 0xc0a8561a && mappedIPv4(nativeIPv6Test) == 0);
static_assert(authorized("Bearer 0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef", testToken));
static_assert(!authorized("", testToken) && !authorized("Bearer short", testToken));
static_assert(!authorized("Bearer 1123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef", testToken));
static_assert(!authorized("bearer 0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef", testToken));
static_assert(!authorized("Bearer 0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef0", testToken));
static_assert(!validToken("") && !validToken("REPLACE_WITH_RANDOM_TOKEN"));
static_assert(localPeer(0xc0a85602, 0xc0a8561a, 0xffffff00, 0));
static_assert(!localPeer(0xc0a85702, 0xc0a8561a, 0xffffff00, 0));
static_assert(!localPeer(0xc0a85602, 0xc0a8561a, 0xffffff00, 0xc0a85603));
static_assert(!localPeer(0xc0a85602, 0xc0a8561a, 0, 0));
static_assert(!localPeer(0x08080801, 0x08080802, 0xffffff00, 0));
static_assert(localPeer(0x0a000002, 0x0a000003, 0xffffff00, 0x0a000002));
static_assert(localPeer(0xac100002, 0xac100003, 0xffffff00, 0));
static_assert(route(true, "/api/state") == Command::State);
static_assert(route(false, "/api/state") == Command::Invalid);
static_assert(route(true, "/api/display/on") == Command::Invalid);
static_assert(route(false, "/api/display/on") == Command::On);
static_assert(route(false, "/api/display/off") == Command::Off);
static_assert(route(false, "/api/display/mode/green") == Command::Green);
static_assert(route(false, "/api/display/mode/blue") == Command::Invalid);
static_assert(route(false, "/api/display/mode/orange") == Command::Invalid);
static_assert(route(false, "/api/display/mode/classic") == Command::Classic);
static_assert(route(false, "/api/display/mode/companion") == Command::Companion);
static_assert(route(false, "/api/display/mode/analog") == Command::AnalogClock);
static_assert(route(false, "/api/display/mode/4") == Command::Invalid);
static_assert(route(false, "/api/display/on?token=secret") == Command::Invalid);
}  // namespace control_policy
