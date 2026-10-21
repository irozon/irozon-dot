#pragma once
#include <cstdint>
#include <cstdio>
#include "heading_policy.h"

namespace usage {
// Percentage is REMAINING allowance. Countdown is seconds UNTIL reset.
// Unknown is separate from a measured zero; expired readings are never refilled.
struct Window {
  bool available = false;
  float remaining = 0;
  uint32_t resetInSeconds = 0;
};
struct Snapshot {
  Window weekly;
  Window session;
  bool testData = false;
  heading_policy::Heading heading = {};
};
enum class Status { NoData, Live, Partial, Stale, Offline, Setup, Test };
constexpr uint8_t clampPercent(unsigned value) {
  return value > 100 ? 100 : static_cast<uint8_t>(value);
}
constexpr uint32_t countdown(uint32_t initial, uint64_t elapsed) {
  return elapsed >= initial ? 0 : initial - static_cast<uint32_t>(elapsed);
}
constexpr Snapshot simulated(uint64_t elapsedSeconds) {
  // Allowances stay fixed; countdowns stop at zero until the next reboot.
  return {{true, 68, countdown(3 * 86400 + 12 * 3600, elapsedSeconds)},
          {true, 82, countdown(2 * 3600 + 24 * 60, elapsedSeconds)}, true};
}
inline void formatReset(const Window& window, char* out, size_t capacity) {
  const uint32_t seconds = window.resetInSeconds;
  // Round up so a positive sub-minute interval never says zero minutes.
  const uint32_t minutes = seconds / 60 + (seconds % 60 != 0);
  if (!window.available) {
    snprintf(out, capacity, "--");
  } else if (seconds == 0) {
    snprintf(out, capacity, "DUE");
  } else if (minutes >= 1440) {
    snprintf(out, capacity, "%lud %02luh",
             static_cast<unsigned long>(minutes / 1440),
             static_cast<unsigned long>((minutes / 60) % 24));
  } else {
    snprintf(out, capacity, "%luh %02lum",
             static_cast<unsigned long>(minutes / 60),
             static_cast<unsigned long>(minutes % 60));
  }
}
// Compile-time boundary checks run in every firmware build.
static_assert(countdown(60, 0) == 60 && countdown(60, 59) == 1);
static_assert(countdown(60, 60) == 0 && countdown(60, 61) == 0);
static_assert(countdown(60, UINT64_C(0x100000000)) == 0);
static_assert(clampPercent(101) == 100 && clampPercent(0) == 0);
static_assert(simulated(0).weekly.remaining == 68);
static_assert(simulated(864000).session.resetInSeconds == 0);
static_assert(!Snapshot{}.heading.configured && Snapshot{}.heading.text[0] == 'I');
}  // namespace usage
