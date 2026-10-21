#pragma once
#include <cstdint>
namespace pairing_policy {
constexpr bool windowOpen(uint32_t now, uint32_t opened) {
  return static_cast<uint32_t>(now - opened) < 60000;
}
constexpr bool privatePrefix(uint8_t first, uint8_t second) {
  return first == 10 || (first == 172 && second >= 16 && second <= 31) ||
         (first == 192 && second == 168);
}
constexpr bool heading(const char* value) {
  for (unsigned i = 0; i <= 18; ++i) {
    const char c = value[i];
    if (!c) return true;
    if (i == 18 || !((c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') ||
        (c >= '0' && c <= '9') || c == ' ' || c == '.' || c == '_' || c == '-')) return false;
  }
  return false;
}
static_assert(windowOpen(59999, 0) && !windowOpen(60000, 0));
static_assert(windowOpen(100, UINT32_MAX - 100));
static_assert(heading("") && heading("ABCDEFGHIJKLMNOPQR") && !heading("ABCDEFGHIJKLMNOPQRS"));
static_assert(!heading("bad\n") && !heading("<script>") && !heading("\xc3\xa5"));
static_assert(privatePrefix(192, 168) && privatePrefix(172, 16) && privatePrefix(10, 0));
static_assert(!privatePrefix(127, 0) && !privatePrefix(172, 32) && !privatePrefix(8, 8));
}
