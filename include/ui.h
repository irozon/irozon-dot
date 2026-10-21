#pragma once
#include "usage.h"

namespace ui {
// Append modes to preserve existing Preferences values 0, 1 and 2.
enum class Mode : uint8_t { Green, Blue, Orange, Classic, Count };
static_assert(static_cast<uint8_t>(Mode::Green) == 0 &&
              static_cast<uint8_t>(Mode::Blue) == 1 &&
              static_cast<uint8_t>(Mode::Orange) == 2 &&
              static_cast<uint8_t>(Mode::Classic) == 3,
              "Preserve saved display mode identifiers");
void begin();
void cycleMode();
void selectMode(Mode mode);
Mode mode();
void setDisplayOn(bool enabled);
bool displayOn();
void draw(const usage::Snapshot& data, usage::Status status);
void animate(bool allowStart = true);  // Nonblocking Green face tick.
}  // namespace ui
