#pragma once
#include <stdint.h>

// Presentation clock only: unsigned elapsed arithmetic also handles millis wrap.
namespace ui_animation {
constexpr uint32_t kIntervalMs = 10000;
constexpr uint32_t kDurationMs = 1000;
constexpr int kMovementPixels = 7;
constexpr int kBlinkCompression = 35;  // Radius 51 -> 16, with text kept at full size.
constexpr uint32_t kFrameMs = 40;      // At most 25 face updates per second.
constexpr int blinkAt(uint32_t elapsed) {
  if (elapsed <= 200 || elapsed >= 800) return 0;
  const uint64_t t = ((elapsed <= 500 ? elapsed - 200 : 800 - elapsed) * 1000) / 300;
  return (kBlinkCompression * t * t * (3000 - 2 * t) + 500000000) / 1000000000;
}
constexpr int offsetAt(uint32_t elapsed) {
  if (elapsed >= kDurationMs) return 0;
  const uint64_t t = (elapsed <= 500 ? elapsed : 1000 - elapsed) * 2;
  // Smoothstep out and back, rounded only at the final pixel boundary.
  return (kMovementPixels * t * t * (3000 - 2 * t) + 500000000) / 1000000000;
}
constexpr int curvature(int base, int bend, int offset) {
  return base * bend + (bend < 0 ? -offset : offset);
}
struct Face {
  bool armed = false;
  bool active = false;
  uint32_t started = 0;
  constexpr void reset() { armed = active = false; }
  constexpr int blink(uint32_t now) const { return active ? blinkAt(now - started) : 0; }
  constexpr int tick(uint32_t now, bool eligible, bool allowStart = true) {
    if (!eligible) { reset(); return 0; }
    if (!armed) { armed = true; started = now; return 0; }
    const uint32_t elapsed = now - started;
    if (elapsed >= kIntervalMs) {
      if (!allowStart) { active = false; return 0; }
      started = now; active = true; return 0;
    }
    if (active && elapsed >= kDurationMs) active = false;
    return active ? offsetAt(elapsed) : 0;
  }
};
constexpr bool checks() {
  Face clock;
  if (clock.tick(100, true) || clock.tick(10099, true) || clock.active) return false;
  clock.tick(10100, true);
  if (!clock.active || clock.tick(10225, true) != 1 || clock.tick(10600, true) != 7 ||
      clock.tick(11099, true) != 0 || !clock.active || clock.tick(11100, true) || clock.active) return false;
  clock.tick(20100, true);
  if (!clock.active || clock.tick(20600, true) != 7 || clock.blink(20600) != 35) return false;
  if (clock.tick(20601, false) || clock.active || clock.armed || clock.blink(20601)) return false;
  clock.tick(200000, true);
  if (clock.tick(209999, true) || clock.active) return false;
  clock.reset();
  clock.tick(0, true);
  clock.tick(10000, true, false);
  if (clock.active || clock.tick(11000, true) || !clock.active || clock.tick(11500, true) != 7)
    return false;
  clock.reset();
  clock.tick(UINT32_MAX - 5000, true);
  clock.tick(4999, true);
  return clock.active && clock.tick(5499, true) == 7;
}
static_assert(checks(), "Face cadence, duration, cancellation, resume and rollover");
constexpr bool easingChecks() {
  for (unsigned t = 0; t <= 500; ++t) {
    if (offsetAt(t) != offsetAt(1000 - t) || offsetAt(t) < 0 || offsetAt(t) > 7) return false;
    if (blinkAt(t) != blinkAt(1000 - t) || blinkAt(t) < 0 || blinkAt(t) > 35) return false;
    if (t && blinkAt(t) < blinkAt(t - 1)) return false;
    if (t && offsetAt(t) < offsetAt(t - 1)) return false;
  }
  return blinkAt(0) == 0 && blinkAt(200) == 0 && blinkAt(500) == 35 && blinkAt(800) == 0 &&
      offsetAt(0) == 0 && offsetAt(1000) == 0 && offsetAt(500) == 7 &&
      curvature(7, 1, 7) == 14 && curvature(7, 0, 7) == 7 && curvature(7, -1, 7) == -14;
}
static_assert(easingChecks(), "Symmetric eased movement deepens happy and sad expressions");
}  // namespace ui_animation
