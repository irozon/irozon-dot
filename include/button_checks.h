#pragma once
#include <initializer_list>
#include "button_logic.h"

// Compile the production state machine checks in both firmware variants.
namespace button::checks {
constexpr uint8_t released(uint32_t start, uint32_t duration) {
  Logic logic;
  if (logic.edge(start, true) != None) return 255;
  if (logic.edge(start + duration, false) != None) return 255;
  if (logic.advance(start + duration + kDebounceMs - 1) != None) return 255;
  const auto action = logic.advance(start + duration + kDebounceMs);
  if (logic.advance(start + duration + 1000) != None) return 255;
  return action;
}
constexpr bool boundaries() {
  // Every millisecond around both thresholds, and every shorter tap/noise pulse.
  for (uint32_t duration = 0; duration <= 8100; ++duration) {
    const auto expected = duration < kDebounceMs ? None :
        duration < kPowerHoldMs ? Short : duration < kResetHoldMs ? Power : Reset;
    if (released(100, duration) != expected) return false;
  }
  return true;
}
constexpr bool heldAndRearmed() {
  Logic logic;
  logic.edge(100, true);
  for (uint32_t elapsed : {40U, 1999U, 2000U, 7999U, 8000U, 20000U})
    if (logic.advance(100 + elapsed) != None) return false;
  if (logic.edge(20100, false) != None || logic.advance(20140) != Reset) return false;
  if (logic.advance(22000) != None) return false;
  logic.edge(23000, true); logic.edge(23100, false);
  return logic.advance(23140) == Short;
}
constexpr bool bounce() {
  Logic logic;
  logic.edge(0, true); logic.edge(10, false); logic.edge(20, true);
  logic.edge(100, false); logic.edge(110, true); logic.edge(120, false);
  if (logic.advance(159) != None || logic.advance(160) != Short) return false;
  Logic hold;
  hold.edge(0, true); hold.edge(10, false); hold.edge(20, true);
  hold.edge(2010, false); hold.edge(2020, true); hold.edge(2030, false);
  return hold.advance(2070) == Power && hold.advance(3000) == None;
}
constexpr bool cancellation() {
  // Same suppression path at startup and on lost/noisy ISR edges.
  Logic logic;
  logic.cancelUntilRelease(100, true);
  if (logic.advance(20000) != None || logic.edge(21000, false) != None ||
      logic.advance(21040) != None) return false;
  logic.edge(22000, true); logic.edge(24000, false);
  if (logic.advance(24040) != Power) return false;
  logic.edge(25000, true);
  logic.cancelUntilRelease(32000, true);
  if (logic.edge(40000, false) != None || logic.advance(40040) != None) return false;
  logic.edge(41000, true); logic.edge(41100, false);
  return logic.advance(41140) == Short;
}
static_assert(boundaries(), "BOOT timing, mutually exclusive gestures and single release event");
static_assert(heldAndRearmed(), "No action while held; reset only after release; re-arm");
static_assert(bounce(), "BOOT press/release bounce must not invent a tap or Wi-Fi reset");
static_assert(cancellation(), "Startup-held and overflowed gestures must be discarded");
static_assert(released(UINT32_MAX - 1000, 120) == Short);
static_assert(released(UINT32_MAX - 1000, 2000) == Power);
static_assert(released(UINT32_MAX - 1000, 7999) == Power);
static_assert(released(UINT32_MAX - 1000, 8000) == Reset);
}  // namespace button::checks
