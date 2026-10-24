#pragma once
#include "usage.h"

namespace ui {
// Keep saved identifiers stable; removed modes fall back to Green.
enum class Mode : uint8_t { Green = 0, Classic = 3, Companion = 4 };
static_assert(static_cast<uint8_t>(Mode::Green) == 0 &&
              static_cast<uint8_t>(Mode::Classic) == 3 &&
              static_cast<uint8_t>(Mode::Companion) == 4,
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
