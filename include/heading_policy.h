#pragma once
#include "pairing_policy.h"

namespace heading_policy {
constexpr bool space(char c) { return c == ' ' || c == '\t' || c == '\r' || c == '\n'; }
struct Heading {
  char text[19] = "IROZON DOT";
  bool configured = false;
  constexpr bool assign(const char* value) {
    if (!value) return false;
    unsigned first = 0, end = 0;
    while (value[end]) ++end;
    while (first < end && space(value[first])) ++first;
    while (end > first && space(value[end - 1])) --end;
    if (end - first > 18) return false;
    char candidate[19] = {};
    for (unsigned i = first; i < end; ++i) candidate[i - first] = value[i];
    if (!pairing_policy::heading(candidate)) return false;
    for (unsigned i = 0; i < 19; ++i) text[i] = candidate[i];
    configured = true;
    return true;
  }
};
constexpr bool checks() {
  Heading h;
  if (h.configured || h.text[0] != 'I') return false;
  if (!h.assign("") || !h.configured || h.text[0]) return false;
  if (!h.assign(" \t\r\n ") || h.text[0]) return false;
  if (!h.assign("  Dot \t") || h.text[0] != 'D' || h.text[3]) return false;
  if (!h.assign("ABCDEFGHIJKLMNOPQR") || h.assign("ABCDEFGHIJKLMNOPQRS")) return false;
  return !h.assign("<script>") && !h.assign("a\nb") && h.text[17] == 'R';
}
static_assert(checks(), "Heading absence, explicit empty, trimming, bounds and atomic validation");
}  // namespace heading_policy
