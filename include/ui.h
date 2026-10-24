#pragma once
#include "usage.h"

namespace ui {
// Keep saved identifiers stable; removed modes 1 and 2 fall back to Green.
enum class Mode : uint8_t { Green = 0, Classic = 3, Companion = 4, AnalogClock = 5 };
static_assert(static_cast<uint8_t>(Mode::Green) == 0 &&
              static_cast<uint8_t>(Mode::Classic) == 3 &&
              static_cast<uint8_t>(Mode::Companion) == 4 &&
              static_cast<uint8_t>(Mode::AnalogClock) == 5,
              "Preserve saved display mode identifiers");
void begin();
void cycleMode();
void selectMode(Mode mode);
Mode mode();
void setDisplayOn(bool enabled);
bool displayOn();
void draw(const usage::Snapshot& data, usage::Status status, uint32_t sampleRevision = 0);
void animate();  // Nonblocking progress animation tick.
}  // namespace ui
