#include "ui.h"
#include "ui_layout.h"
#include "ui_animation.h"
#include "hardware/lgfx_config.hpp"
#include <cmath>
#include <Preferences.h>

namespace {
using namespace ui_layout;
static_assert(kMouthBufferOriginY - kMouthDepth - ui_animation::kMovementPixels >= 0);
static_assert(kMouthBufferOriginY + kMouthDepth + ui_animation::kMovementPixels + 1 < kValueHeight);
static_assert(2 * (kMouthHalfWidth + ui_animation::kMovementPixels) + 1 <= kValueWidth);
static_assert(120 - kLeftX + kRadius + 1 < kRimRadius);
static_assert(kRightX - 120 + kRadius + 1 < kRimRadius);
LGFX tft;
LGFX_Sprite line(&tft);
bool buffered = false;
constexpr uint16_t rgb(uint32_t hex) {
  return ((hex >> 8) & 0xf800) | ((hex >> 5) & 0x07e0) | ((hex >> 3) & 0x001f);
}
constexpr uint16_t bg = rgb(0x071A21);
constexpr uint16_t green = rgb(0x02C685);
constexpr uint16_t lime = rgb(0x9BE15D);
constexpr uint16_t track = rgb(0x17343D);
constexpr uint16_t white = rgb(0xE8F2EE);
constexpr uint16_t muted = rgb(0xA3BABD);
constexpr uint16_t amber = rgb(0xE8AF56);
constexpr uint16_t red = rgb(0xE87878);
constexpr uint16_t rim = rgb(0x102C34);
constexpr uint16_t blueBg = rgb(0x071322);
constexpr uint16_t blue = rgb(0x50B8FF);
constexpr uint16_t cyan = rgb(0x59E2E7);
constexpr uint16_t orangeBg = rgb(0x180F0A);
constexpr uint16_t orange = rgb(0xFF9A3C);
constexpr uint16_t gold = rgb(0xFFC66D);
uint16_t canvas = bg, primary = lime, secondary = green;
ui::Mode selectedMode = ui::Mode::Green;
uint8_t paintedMode = 255;
int lastWeek = -2, lastSession = -2;
usage::Status lastStatus = usage::Status::NoData;
bool displayEnabled = true;
bool panelRecovering = false;
uint32_t panelReadyAt = 0;
bool panelSleeping = false;
ui_animation::Face faceClock;
int currentBend = 0, paintedMouthDepth = 100;
bool currentReliable = false, currentFaceReliable = false;
int paintedBlink = 0;
uint32_t lastFaceFrame = 0;
heading_policy::Heading displayHeading;

// H is remaining allowance, including fractional precision at the boundaries.
// Unavailable/expired readings must never retain a reassuring expression.
constexpr int mouthBend(float remaining, bool reliable) {
  return !reliable ? 0 : remaining > 55 ? 1 : remaining < 45 ? -1 : 0;
}
static_assert(mouthBend(55.01f, true) == 1 && mouthBend(55, true) == 0);
static_assert(mouthBend(45, true) == 0 && mouthBend(44.99f, true) == -1);
static_assert(mouthBend(100, false) == 0 && mouthBend(0, false) == 0);

void mouth(int bend, bool reliable, int offset = 0) {
  offset = reliable ? offset : 0;
  const int half = kMouthHalfWidth + offset;
  // Reuse the percentage sprite; one small transfer prevents erase/draw flicker.
  lgfx::LGFXBase& target = buffered ? static_cast<lgfx::LGFXBase&>(line) : tft;
  const int originX = buffered ? kValueWidth / 2 : 120;
  const int originY = buffered ? kMouthBufferOriginY : kMouthY;
  if (buffered) line.fillSprite(canvas);
  else tft.fillRect(120 - kValueWidth / 2, kMouthY - kMouthBufferOriginY,
                    kValueWidth, kValueHeight, canvas);
  const uint16_t color = !reliable ? track : bend < 0 ? amber : green;
  const int depth = ui_animation::curvature(kMouthDepth, bend, offset);
  auto y = [=](int x) {
    return originY + depth * (half * half - x * x) / (half * half);
  };
  // A small two-pixel parabola; no framebuffer or new graphics dependency.
  for (int x = -half; x < half; ++x) {
    target.drawLine(originX + x, y(x), originX + x + 1, y(x + 1), color);
    target.drawLine(originX + x, y(x) + 1, originX + x + 1, y(x + 1) + 1, color);
  }
  if (buffered) line.pushSprite(120 - kValueWidth / 2, kMouthY - kMouthBufferOriginY);
  paintedMouthDepth = depth;
}

void heading(const char* value, bool classic, bool changedMode) {
  static int oldWidth = 0, oldHeight = 0;
  const int y = classic ? kClassicHeadingY : kHeadingY;
  if (!changedMode && oldWidth) tft.fillRect(120 - oldWidth / 2, y - oldHeight / 2,
                                            oldWidth, oldHeight, canvas);
  oldWidth = oldHeight = 0;
  if (!value[0]) return;  // Explicit empty clears the old heading, with no fallback.
  const int radius = classic ? kClassicHeadingSafeRadius : kHeadingSafeRadius;
  const lgfx::IFont* candidates[] = {&fonts::FreeSansBold12pt7b,
      &fonts::FreeSansBold9pt7b, &fonts::Font2, &fonts::Font0};
  const int maxHeight = classic ? kClassicHeadingHeight : kHeadingHeight;
  for (int height = maxHeight; height >= 8; --height) {
    // Safe chord at the furthest edge of this centered text rectangle.
    const int dy = 120 - y + (height + 1) / 2 + 1;
    const int width = 2 * static_cast<int>(sqrtf(radius * radius - dy * dy));
    for (int i = 0; i < 4; ++i) {
      tft.setFont(candidates[i]);
      tft.setTextSize(1);
      const float scale = static_cast<float>(height) / tft.fontHeight();
      if (scale < (i < 2 ? 0.75f : 1.0f)) continue;
      tft.setTextSize(scale);
      const int measured = tft.textWidth(value) + 4;  // Ink/rounding guard.
      if (measured > width) continue;
      oldWidth = measured;
      oldHeight = height + 2;
      tft.setTextColor(white);
      tft.setTextDatum(lgfx::middle_center);
      tft.drawString(value, 120, y);
      tft.setTextSize(1);  // Never scale percentages/countdowns by accident.
      return;
    }
  }
  tft.setTextSize(1);  // 18 printable ASCII characters always fit Font0.
}

// Full circles start at 12 o'clock and fill clockwise. LovyanGFX's arc
// convention starts at 3 o'clock, so split at 360 instead of wrapping.
float ellipseAngle(float angle, float scale) {
  if (scale == 1 || angle == 360) return angle;
  const float rad = angle * 0.01745329252f;
  float result = atan2f(sinf(rad) * scale, cosf(rad)) * 57.29577951f;
  return result < 0 ? result + 360 : result;
}

void ringOn(lgfx::LGFXBase& target, int cx, int cy, uint8_t remaining,
            uint16_t color, int radius, int verticalRadius) {
  const float end = 270.0f + 3.6f * usage::clampPercent(remaining);
  const float scale = static_cast<float>(verticalRadius) / radius;
  const int inner = radius - kThickness;
  const int innerY = (inner * verticalRadius + radius / 2) / radius;
  target.fillEllipseArc(cx, cy, radius, inner, verticalRadius, innerY, 0, 360, track);
  if (remaining == 0) return;
  // Ellipse arcs use physical polar angles; map the unchanged progress angle
  // through the vertical scale so its endpoint follows the same ring fraction.
  target.fillEllipseArc(cx, cy, radius, inner, verticalRadius, innerY, 270,
                        end < 360 ? ellipseAngle(end, scale) : 360, color);
  if (end > 360) {
    target.fillEllipseArc(cx, cy, radius, inner, verticalRadius, innerY, 0,
                          ellipseAngle(end - 360, scale), color);
  }
  // Soft rounded ends without a framebuffer.
  const float rad = end * 0.01745329252f;
  const float mid = radius - kThickness * 0.5f;
  if (verticalRadius == radius) {
    target.fillCircle(cx, lroundf(cy - mid), 2, color);
    target.fillCircle(lroundf(cx + cosf(rad) * mid), lroundf(cy + sinf(rad) * mid), 2, color);
  } else {
    const int capY = scale < 0.75f ? 1 : 2;
    target.fillEllipse(cx, lroundf(cy - mid * scale), 2, capY, color);
    target.fillEllipse(lroundf(cx + cosf(rad) * mid), lroundf(cy + sinf(rad) * mid * scale),
                       2, capY, color);
  }
}

void ring(int cx, uint8_t remaining, uint16_t color, int radius = kRadius) {
  ringOn(tft, cx, kGaugeY, remaining, color, radius, radius);
}

void blinkingEye(int cx, int remaining, uint16_t color, int compression) {
  // Composite ring + background before each transfer. Transparent rectangles
  // preserve the existing text pixels without reading the panel or redrawing text.
  constexpr uint16_t transparent = 0xF81F;  // Not used by any display palette.
  constexpr int diameter = 2 * kRadius + 1;
  for (int row = 0; row < diameter; row += kValueHeight) {
    for (int col = 0; col < diameter; col += kValueWidth) {
      const int x = cx - kRadius + col, y = kGaugeY - kRadius + row;
      line.fillSprite(canvas);
      ringOn(line, cx - x, kGaugeY - y, remaining < 0 ? 0 : remaining,
             color, kRadius, kRadius - compression);
      line.fillRect(cx - 12 - x, kLabelY - 11 - y, 24, 22, transparent);
      line.fillRect(cx - kValueWidth / 2 - x, kPercentY - kValueHeight / 2 - y,
                    kValueWidth, kValueHeight, transparent);
      line.fillRect(cx - kCountdownWidth / 2 - x, kCountdownY - kCountdownHeight / 2 - y,
                    kCountdownWidth, kCountdownHeight, transparent);
      if (col + kValueWidth > diameter)
        line.fillRect(diameter - col, 0, kValueWidth, kValueHeight, transparent);
      if (row + kValueHeight > diameter)
        line.fillRect(0, diameter - row, kValueWidth, kValueHeight, transparent);
      // The square's corners can touch the outer rim. Preserve everything
      // outside the original circle's raster envelope, including its edge pixels.
      for (int sy = 0; sy < kValueHeight; ++sy) {
        const int dy = y + sy - kGaugeY;
        if (dy < -kRadius || dy > kRadius) {
          line.fillRect(0, sy, kValueWidth, 1, transparent);
          continue;
        }
        const int extent = static_cast<int>(sqrtf(kRadius * (kRadius + 1) - dy * dy));
        const int left = cx - extent - x, right = cx + extent - x + 1;
        if (left > 0) line.fillRect(0, sy, left, 1, transparent);
        if (right < kValueWidth)
          line.fillRect(right < 0 ? 0 : right, sy, kValueWidth, 1, transparent);
      }
      line.pushSprite(x, y, transparent);
    }
  }
}

void blinkingEyes(int compression, int week, int session, bool stale) {
  blinkingEye(kLeftX, week, stale ? muted : lime, compression);
  blinkingEye(kRightX, session, stale ? muted : green, compression);
  paintedBlink = compression;
}

// Reuse one 80 x 30 RGB565 strip (4,800 bytes) for the large percentages.
// Every cleared rectangle stays strictly inside its own gauge's inner edge.
void percentage(const usage::Window& window, char* value, size_t size) {
  if (window.available) snprintf(value, size, "%.0f%%", floorf(window.remaining));
  else snprintf(value, size, "--");
}

// All modes share the verified snapshot and formatters; only geometry changes.
void text(const char* value, int cx, int y, int width, int height,
          const lgfx::IFont* font, uint16_t color) {
  tft.fillRect(cx - width / 2, y - height / 2, width, height, canvas);
  tft.setFont(font);
  tft.setTextColor(color);
  tft.setTextDatum(lgfx::middle_center);
  tft.drawString(value, cx, y);
}

void resetText(const usage::Window& window, int cx, int y) {
  char value[16];
  usage::formatReset(window, value, sizeof(value));
  text(value, cx, y, kCountdownWidth, kCountdownHeight, &fonts::Font2, muted);
}

void gaugeText(int cx, const char* label, const usage::Window& window, uint16_t color) {
  char value[16];
  percentage(window, value, sizeof(value));
  if (buffered) {
    line.fillSprite(canvas);
    line.setFont(&fonts::FreeSansBold12pt7b);
    line.setTextColor(color);
    line.setTextDatum(lgfx::middle_center);
    line.drawString(value, kValueWidth / 2, kValueHeight / 2);
    line.pushSprite(cx - kValueWidth / 2, kPercentY - kValueHeight / 2);
  } else {
    tft.fillRect(cx - kValueWidth / 2, kPercentY - kValueHeight / 2,
                 kValueWidth, kValueHeight, canvas);
    tft.setFont(&fonts::FreeSansBold12pt7b);
    tft.setTextColor(color);
    tft.setTextDatum(lgfx::middle_center);
    tft.drawString(value, cx, kPercentY);
  }
  text(label, cx, kLabelY, 24, 22, &fonts::FreeSansBold9pt7b, color);
  resetText(window, cx, kCountdownY);
}
}  // namespace

void ui::begin() {
  tft.init();
  tft.setRotation(0);
  tft.setBrightness(255);
  tft.setTextWrap(false);
  line.setColorDepth(16);
  buffered = line.createSprite(kValueWidth, kValueHeight) != nullptr;
  line.setTextWrap(false);
  Preferences prefs;
  if (prefs.begin("irozon-ui", false)) {
    const uint8_t saved = prefs.getUChar("mode", 0);
    selectedMode = saved < static_cast<uint8_t>(Mode::Count) ? static_cast<Mode>(saved) : Mode::Green;
    displayEnabled = prefs.getBool("power", true);
    if (prefs.isKey("heading")) displayHeading.assign(prefs.getString("heading", "").c_str());
    prefs.end();
  }
  if (!displayEnabled) {
    tft.fillScreen(0);
    tft.sleep();  // Panel sleep only: the hardware has no controlled backlight.
    panelSleeping = true;
    panelReadyAt = millis() + 120;
    panelRecovering = true;
  }
}

ui::Mode ui::mode() { return selectedMode; }

void ui::cycleMode() {
  selectMode(static_cast<Mode>((static_cast<uint8_t>(selectedMode) + 1) %
                               static_cast<uint8_t>(Mode::Count)));
}

void ui::selectMode(Mode next) {
  if (next >= Mode::Count || next == selectedMode) return;
  selectedMode = next;
  faceClock.reset();
  Preferences prefs;
  if (prefs.begin("irozon-ui", false)) {
    if (prefs.putUChar("mode", static_cast<uint8_t>(selectedMode)) != 1)
      Serial.println("Display mode could not be saved");
    prefs.end();
  }
}

bool ui::displayOn() { return displayEnabled; }

void ui::setDisplayOn(bool enabled) {
  if (enabled == displayEnabled) return;
  displayEnabled = enabled;
  faceClock.reset();
  Preferences prefs;
  if (prefs.begin("irozon-ui", false)) {
    if (prefs.putBool("power", enabled) != 1) Serial.println("Display power state could not be saved");
    prefs.end();
  }
  if (enabled) paintedMode = 255;  // Redraw latest usage completely after waking.
}

void ui::draw(const usage::Snapshot& data, usage::Status status) {
  // Missing fields retain the last heading. An explicit empty string is a value,
  // persisted even in standby, before any panel work or early return.
  if (data.heading.configured && (!displayHeading.configured ||
      strcmp(displayHeading.text, data.heading.text) != 0)) {
    displayHeading = data.heading;
    Preferences prefs;
    bool persisted = false;
    if (prefs.begin("irozon-ui", false)) {
      prefs.putString("heading", displayHeading.text);
      persisted = prefs.isKey("heading") && prefs.getString("heading", "?") == displayHeading.text;
      prefs.end();
    }
    if (!persisted) Serial.println("Display heading could not be saved");
  }
  // Serialize rapid ON/OFF requests with both panel recovery intervals. The
  // regular draw tick advances this state without delaying Wi-Fi or HTTP work.
  if (panelRecovering && static_cast<int32_t>(millis() - panelReadyAt) < 0) return;
  panelRecovering = false;
  if (!displayEnabled) {
    if (!panelSleeping) {
      tft.fillScreen(0);
      tft.sleep();
      panelSleeping = true;
      panelReadyAt = millis() + 120;
      panelRecovering = true;
    }
    return;
  }
  if (panelSleeping) {
    tft.wakeup();
    panelSleeping = false;
    panelReadyAt = millis() + 120;
    panelRecovering = true;
    return;
  }
  // The local clock ticks each second; redraw only when visible minutes,
  // integer percentages, availability, provenance or status actually change.
  const bool changedMode = paintedMode != static_cast<uint8_t>(selectedMode);
  const bool classic = selectedMode == Mode::Classic;
  const bool reliableH = data.session.available && std::isfinite(data.session.remaining) &&
      (status == usage::Status::Live || status == usage::Status::Partial ||
       status == usage::Status::Test);
  const int bend = mouthBend(data.session.remaining, reliableH);
  currentBend = bend;
  currentReliable = reliableH;
  currentFaceReliable = reliableH && data.weekly.available && std::isfinite(data.weekly.remaining);
  const uint32_t now = millis();
  const int mouthOffset = faceClock.tick(now, selectedMode == Mode::Green && currentFaceReliable, false);
  const int blink = buffered ? faceClock.blink(now) : 0;
  char screenKey[128];
  static char previousKey[128] = "";
  snprintf(screenKey, sizeof(screenKey), "%d:%d:%u:%d:%d:%u:%d:%d:%d:%s",
           data.weekly.available, static_cast<int>(floorf(data.weekly.remaining)),
           data.weekly.resetInSeconds / 60 + (data.weekly.resetInSeconds % 60 != 0),
           data.session.available, static_cast<int>(floorf(data.session.remaining)),
           data.session.resetInSeconds / 60 + (data.session.resetInSeconds % 60 != 0),
           data.testData, static_cast<int>(status), selectedMode == Mode::Green ? bend : 0, displayHeading.text);
  if (!changedMode && strcmp(screenKey, previousKey) == 0) return;
  snprintf(previousKey, sizeof(previousKey), "%s", screenKey);
  tft.startWrite();
  if (changedMode) {
    canvas = selectedMode == Mode::Blue ? blueBg : selectedMode == Mode::Orange ? orangeBg : bg;
    primary = selectedMode == Mode::Blue ? blue : selectedMode == Mode::Orange ? orange : lime;
    secondary = selectedMode == Mode::Blue ? cyan : selectedMode == Mode::Orange ? gold : green;
    tft.fillScreen(canvas);
    lastWeek = lastSession = -2;
    paintedBlink = 0;
    if (selectedMode == Mode::Green) tft.drawCircle(120, 120, kRimRadius, rim);
    paintedMode = static_cast<uint8_t>(selectedMode);
  }
  heading(displayHeading.text, classic, changedMode);
  const int week = data.weekly.available ? static_cast<int>(floorf(data.weekly.remaining)) : -1;
  const int session = data.session.available ? static_cast<int>(floorf(data.session.remaining)) : -1;
  const bool stale = status == usage::Status::Stale || status == usage::Status::Offline;
  if (selectedMode == Mode::Green &&
      (lastWeek != week || lastSession != session || status != lastStatus || paintedBlink != blink)) {
    if (buffered && (paintedBlink || blink)) blinkingEyes(blink, week, session, stale);
    else {
      ring(kLeftX, week < 0 ? 0 : week, stale ? muted : lime);
      ring(kRightX, session < 0 ? 0 : session, stale ? muted : green);
    }
    lastWeek = week;
    lastSession = session;
  }
  if (classic && (lastWeek != week || status != lastStatus)) {
    ring(classic ? 120 : kLeftX, week < 0 ? 0 : week, stale ? muted : lime,
         classic ? kClassicOuterRadius : kRadius);
    lastWeek = week;
  }
  if (classic && (lastSession != session || status != lastStatus)) {
    ring(classic ? 120 : kRightX, session < 0 ? 0 : session, stale ? muted : green,
         classic ? kClassicInnerRadius : kRadius);
    lastSession = session;
  }
  const uint16_t first = stale ? muted : primary, second = stale ? muted : secondary;
  if (selectedMode == Mode::Green) {
    gaugeText(kLeftX, "W", data.weekly, first);
    gaugeText(kRightX, "H", data.session, second);
  } else if (selectedMode == Mode::Blue) {
    char value[16], hour[24];
    text("W", 120, kBlueLabelY, 24, 16, &fonts::Font2, first);
    percentage(data.weekly, value, sizeof(value));
    text(value, 120, kBlueValueY, kBlueWidth, kBlueHeight, &fonts::FreeSansBold24pt7b, first);
    resetText(data.weekly, 120, kBlueResetY);
    percentage(data.session, value, sizeof(value));
    snprintf(hour, sizeof(hour), "H %s", value);
    text(hour, 120, kBlueHourY, 128, 30, &fonts::FreeSansBold12pt7b, second);
    resetText(data.session, 120, kBlueHourResetY);
  } else if (classic) {
    for (int i = 0; i < 2; ++i) {
      const auto& window = i == 0 ? data.weekly : data.session;
      char value[16], label[24];
      percentage(window, value, sizeof(value));
      snprintf(label, sizeof(label), "%s %s", i == 0 ? "W" : "H", value);
      text(label, 120, i == 0 ? kClassicWeekY : kClassicHourY,
           kClassicValueWidth, kClassicValueHeight, &fonts::FreeSansBold12pt7b,
           i == 0 ? first : second);
      resetText(window, 120, i == 0 ? kClassicWeekResetY : kClassicHourResetY);
    }
  } else {
    for (int i = 0; i < 2; ++i) {
      const int cx = i == 0 ? kLeftX : kRightX;
      const auto& window = i == 0 ? data.weekly : data.session;
      const uint16_t color = i == 0 ? first : second;
      char value[16];
      text(i == 0 ? "W" : "H", cx, kOrangeLabelY, 24, 22, &fonts::FreeSansBold9pt7b, color);
      percentage(window, value, sizeof(value));
      text(value, cx, kOrangeValueY, kOrangeWidth, kOrangeHeight, &fonts::FreeSansBold18pt7b, color);
      resetText(window, cx, kOrangeResetY);
    }
  }
  const char* note = data.testData ? "TEST DATA" :
      status == usage::Status::Stale ? "STALE" :
      status == usage::Status::Offline ? "OFFLINE" :
      status == usage::Status::Setup ? "WIFI SETUP" :
      status == usage::Status::NoData ? "NO DATA" :
      status == usage::Status::Partial ? "PARTIAL" : "";
  const int noteY = classic ? kClassicNoteY : kNoteY;
  tft.fillRect(76, noteY - 5, 88, 10, canvas);
  tft.setFont(&fonts::Font0);
  tft.setTextColor(data.testData ? white : amber);
  tft.setTextDatum(lgfx::middle_center);
  tft.drawString(note, 120, noteY);
  if (selectedMode == Mode::Green) {
    mouth(bend, reliableH, mouthOffset);
  }
  lastStatus = status;
  tft.endWrite();
}

void ui::animate(bool allowStart) {
  const bool eligible = displayEnabled && !panelSleeping && !panelRecovering &&
      selectedMode == Mode::Green && paintedMode == static_cast<uint8_t>(Mode::Green) && currentFaceReliable;
  const uint32_t now = millis();
  const int offset = faceClock.tick(now, eligible, allowStart);
  const int blink = buffered ? faceClock.blink(now) : 0;
  if (!displayEnabled || panelSleeping || panelRecovering || selectedMode != Mode::Green ||
      paintedMode != static_cast<uint8_t>(Mode::Green)) return;
  const bool eyesChanged = paintedBlink != blink;
  const bool mouthChanged = paintedMouthDepth != ui_animation::curvature(kMouthDepth, currentBend, offset);
  if (!eyesChanged && !mouthChanged) return;
  // Cancellation/restoration is immediate; cosmetic intermediate frames are capped.
  if (eligible && (blink || offset) && static_cast<uint32_t>(now - lastFaceFrame) < ui_animation::kFrameMs)
    return;
  tft.startWrite();
  if (eyesChanged) blinkingEyes(blink, lastWeek, lastSession,
                               lastStatus == usage::Status::Stale || lastStatus == usage::Status::Offline);
  if (mouthChanged) mouth(currentBend, currentReliable, offset);
  tft.endWrite();
  lastFaceFrame = now;
}
