#pragma once
#include "usage.h"
namespace control {
void begin();
// Called on main loop only. HTTP task never touches UI, SPI or Preferences.
void poll(bool connected, bool provisioning, usage::Status usageStatus);
}
