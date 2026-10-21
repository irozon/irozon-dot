#pragma once
#include "button_logic.h"
namespace button {
struct Events { uint8_t taps = 0, powerToggles = 0; bool resetWifi = false; };
void begin();
Events poll();
}  // namespace button
