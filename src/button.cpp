#include "button.h"
#include "button_checks.h"
#include "config.h"
#include <Arduino.h>

namespace {
static_assert(config::kBootStandbyHoldMs == 2000 && config::kBootResetHoldMs == 8000);
struct Edge { uint32_t at; bool down; };
constexpr uint8_t capacity = 16;
volatile Edge edges[capacity];
volatile uint8_t readIndex = 0, writeIndex = 0;
volatile bool overflow = false;
portMUX_TYPE mux = portMUX_INITIALIZER_UNLOCKED;
button::Logic logic;
void IRAM_ATTR changed() {
  const uint32_t now = millis();
  const bool down = digitalRead(config::kBootPin) == LOW;
  portENTER_CRITICAL_ISR(&mux);
  const uint8_t next = (writeIndex + 1) % capacity;
  if (next == readIndex) overflow = true;
  else {
    edges[writeIndex].at = now;
    edges[writeIndex].down = down;
    writeIndex = next;
  }
  portEXIT_CRITICAL_ISR(&mux);
}
}  // namespace

void button::begin() {
  // Reuses the verified BOOT GPIO; never drive a boot-strapping pin as output.
  pinMode(config::kBootPin, INPUT_PULLUP);
  // A key held at firmware entry is not a gesture; wait for release.
  logic.cancelUntilRelease(millis(), digitalRead(config::kBootPin) == LOW);
  attachInterrupt(digitalPinToInterrupt(config::kBootPin), changed, CHANGE);
}

button::Events button::poll() {
  Events result;
  const auto collect = [&result](uint8_t action) {
    if (action & Short) ++result.taps;
    if (action & Power) ++result.powerToggles;
    if (action & Reset) result.resetWifi = true;
  };
  while (true) {
    Edge event{};
    bool available, lost;
    portENTER_CRITICAL(&mux);
    lost = overflow;
    if (lost) { readIndex = writeIndex; overflow = false; }
    available = !lost && readIndex != writeIndex;
    if (available) {
      event.at = edges[readIndex].at;
      event.down = edges[readIndex].down;
      readIndex = (readIndex + 1) % capacity;
    }
    portEXIT_CRITICAL(&mux);
    if (lost) {
      // Discard noisy/overflowed gestures rather than invent a tap or reset.
      logic.cancelUntilRelease(millis(), digitalRead(config::kBootPin) == LOW);
      return {};
    }
    if (!available) break;
    collect(logic.edge(event.at, event.down));
  }
  // GPIO9 is sampled even when the LCD panel is asleep. This also recovers a
  // missed interrupt edge; ordinary ISR events retain their precise timestamps.
  collect(logic.sample(millis(), digitalRead(config::kBootPin) == LOW));
  return result;
}
