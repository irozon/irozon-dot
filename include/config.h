#pragma once
#include <cstdint>
#include <driver/gpio.h>
#include "button_logic.h"

namespace config {
// Display wiring; third-party provenance is recorded in THIRD_PARTY_NOTICES.md.
constexpr gpio_num_t kDisplayPinRst = GPIO_NUM_0;
constexpr gpio_num_t kDisplayPinCs = GPIO_NUM_1;
constexpr gpio_num_t kDisplayPinDc = GPIO_NUM_10;
constexpr gpio_num_t kDisplayPinMosi = GPIO_NUM_3;
constexpr gpio_num_t kDisplayPinSclk = GPIO_NUM_4;
constexpr uint32_t kDisplaySpiWriteHz = 40000000;
constexpr bool kDisplayInvert = true;
constexpr bool kDisplayRgbOrder = false;  // This GC9A01 module requires MADCTL's BGR bit.
constexpr gpio_num_t kBootPin = GPIO_NUM_9;
constexpr uint32_t kBootStandbyHoldMs = button::kPowerHoldMs;
constexpr uint32_t kBootResetHoldMs = button::kResetHoldMs;
constexpr char kPortalApName[] = "Irozon-Dot-Setup";
constexpr char kHostname[] = "irozon-dot";
constexpr uint32_t kReconnectMs = 15000;
}  // namespace config
