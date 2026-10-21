#pragma once
#include <cstdint>

namespace button {
constexpr uint32_t kDebounceMs = 40;
constexpr uint32_t kPowerHoldMs = 2000;
constexpr uint32_t kResetHoldMs = 8000;
enum Action : uint8_t { None = 0, Short = 1, Power = 2, Reset = 4 };

// Classify on debounced release: an 8 s reset never first toggles standby.
// ISR edge timestamps retain physical duration during main-loop HTTP waits.
struct Logic {
  bool raw = false, stable = false, suppressed = false;
  uint32_t changed = 0, pressed = 0;
  constexpr void cancelUntilRelease(uint32_t now, bool down) {
    raw = stable = down;
    changed = pressed = now;
    suppressed = true;
  }
  constexpr uint8_t advance(uint32_t now) {
    if (suppressed) {
      if (!raw && static_cast<uint32_t>(now - changed) >= kDebounceMs) {
        stable = false;
        suppressed = false;
      }
      return None;
    }
    if (raw == stable || static_cast<uint32_t>(now - changed) < kDebounceMs)
      return None;
    stable = raw;
    if (stable) { pressed = changed; return None; }
    const uint32_t duration = changed - pressed;
    return duration >= kResetHoldMs ? Reset : duration >= kPowerHoldMs ? Power : Short;
  }
  constexpr uint8_t edge(uint32_t now, bool down) {
    // The main-loop level sample can race an already queued ISR edge. Ignore
    // the duplicate without advancing the clock backwards to that older edge.
    if (down == raw) return None;
    const auto result = advance(now);
    raw = down;
    changed = now;
    return result;
  }
  // Reconcile the interrupt stream with the pin level during every main-loop
  // poll. ISR timestamps still preserve gesture duration across blocking work.
  constexpr uint8_t sample(uint32_t now, bool down) {
    return down == raw ? advance(now) : edge(now, down);
  }
};
}  // namespace button
