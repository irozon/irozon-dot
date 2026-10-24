#include "ui.h"
#include "ui_layout.h"
#include "hardware/lgfx_config.hpp"
#include <cmath>
#include <ctime>
#include <Preferences.h>

namespace {
using namespace ui_layout;
LGFX tft;
LGFX_Sprite line(&tft);
LGFX_Sprite companionFace(&tft);
bool buffered = false;
bool companionFaceBuffered = false;
constexpr uint16_t rgb(uint32_t hex) {
  return ((hex >> 8) & 0xf800) | ((hex >> 5) & 0x07e0) | ((hex >> 3) & 0x001f);
}
constexpr uint16_t classicBackground = rgb(0x000000);
constexpr uint16_t classicTrack = rgb(0x202020);
constexpr uint16_t white = rgb(0xE8F2EE);
constexpr uint16_t muted = rgb(0xA3BABD);
constexpr uint16_t amber = rgb(0xE8AF56);
constexpr uint16_t stackWeekly = rgb(0x22D3EE);
constexpr uint16_t stackSession = rgb(0x8B5CF6);
constexpr uint16_t stackWeeklyTrack = rgb(0x08343C);
constexpr uint16_t stackSessionTrack = rgb(0x261744);
constexpr uint16_t faceLime = rgb(0x9BE15D);
constexpr uint16_t clockCyan = rgb(0x22D3EE);
constexpr uint16_t clockTrack = rgb(0x07313A);
constexpr uint16_t classicOrange = rgb(0xFF9F1C);
constexpr uint16_t classicRed = rgb(0xFF453A);
constexpr uint16_t classicOrangeTrack = rgb(0x4D3008);
constexpr uint16_t classicRedTrack = rgb(0x4D1511);
constexpr int kClassicThickness = 8;
constexpr uint32_t kGaugeDurationMs = 2000;
constexpr uint32_t kAnimationFrameMs = 40;
constexpr uint32_t kCompanionFrameMs = 50;
constexpr uint32_t kCompanionTransitionMs = 400;
uint16_t canvas = classicBackground;
ui::Mode selectedMode = ui::Mode::Green;
uint8_t paintedMode = 255;
int lastWeek = -2, lastSession = -2;
usage::Status lastStatus = usage::Status::NoData;
bool displayEnabled = true;
bool panelRecovering = false;
uint32_t panelReadyAt = 0;
bool panelSleeping = false;
uint32_t usageRevision = 0, gaugeStarted = 0, lastGaugeFrame = 0;
bool gaugeAnimating = false, startupGaugeAnimationPlayed = false;
float gaugeWeekTarget = 0, gaugeSessionTarget = 0;
bool gaugeWeekAvailable = false, gaugeSessionAvailable = false;
bool classicAnimating = false, classicStartupPlayed = false;
bool classicWeekAvailable = false, classicSessionAvailable = false;
float classicWeekTarget = 0, classicSessionTarget = 0;
uint32_t classicStarted = 0, lastClassicFrame = 0;
enum class CompanionMood : uint8_t { Uninitialized, Active, Tired, Sleeping, Waking };
enum class CompanionAction : uint8_t { None, Blink, DoubleBlink, Glance, Happy, Surprise, Pause, Sad };
CompanionMood companionMood = CompanionMood::Uninitialized;
CompanionAction companionAction = CompanionAction::None;
uint32_t companionRandomState = 0x9E3779B9;
uint32_t companionMoodStarted = 0, companionActiveDuration = 0;
uint32_t companionTiredDuration = 0, companionSleepingDuration = 0, companionActionStarted = 0;
uint32_t companionActionDuration = 0, companionNextAction = 0, lastCompanionFrame = 0;
uint32_t lastCompanionRender = 0;
struct CompanionPose {
  float leftOpen = 100, rightOpen = 100;
  float gazeX = 0, gazeY = 0, bounce = 0, smile = 7, mouthOpen = 0;
  float closedStyle = 0;
  float leftBrowLength = 0, leftBrowY0 = -26, leftBrowY1 = -26;
  float rightBrowLength = 0, rightBrowY0 = -26, rightBrowY1 = -26;
};
CompanionPose lastCompanionPose{};
CompanionPose companionTransitionFrom{};
bool companionPoseValid = false;
bool companionTransitioning = false;
int companionExpressionKey = -1;
uint32_t companionTransitionStarted = 0;
bool clockFaceDrawn = false, clockWaitingDrawn = false, clockTimeDrawn = false, clockHandsDrawn = false;
int clockLastSecond = -1, clockLastMinute = -1, clockLastDate = -1;
int clockHourX = kClockCenterX, clockHourY = kClockCenterY;
int clockMinuteX = kClockCenterX, clockMinuteY = kClockCenterY;
int clockSecondX = kClockCenterX, clockSecondY = kClockCenterY;
uint32_t lastClockPoll = 0;
heading_policy::Heading displayHeading;

void text(const char* value, int cx, int y, int width, int height,
          const lgfx::IFont* font, uint16_t color);

uint32_t companionRandom() {
  uint32_t x = companionRandomState;
  x ^= x << 13;
  x ^= x >> 17;
  x ^= x << 5;
  companionRandomState = x ? x : 0x9E3779B9;
  return companionRandomState;
}

uint32_t companionBetween(uint32_t minimum, uint32_t maximum) {
  return minimum + companionRandom() % (maximum - minimum + 1);
}

void startCompanion(uint32_t now) {
  companionRandomState ^= now + micros() + 0x85EBCA6B;
  if (!companionRandomState) companionRandomState = 0x9E3779B9;
  companionMood = CompanionMood::Active;
  companionMoodStarted = now;
  companionActiveDuration = companionBetween(45000, 85000);
  companionAction = CompanionAction::None;
  companionNextAction = now + companionBetween(1200, 3600);
  lastCompanionFrame = now;
  lastCompanionRender = 0;
  companionPoseValid = false;
  companionTransitioning = false;
  companionExpressionKey = -1;
}

void startCompanionAction(uint32_t now) {
  const uint32_t pick = companionRandom() % 16;
  if (pick == 0) {
    companionAction = CompanionAction::Surprise;
    companionActionDuration = 900;
  } else if (pick == 1) {
    companionAction = CompanionAction::Sad;
    companionActionDuration = 1100;
  } else {
    switch (companionRandom() % 5) {
      case 0: companionAction = CompanionAction::Blink; companionActionDuration = 460; break;
      case 1: companionAction = CompanionAction::DoubleBlink; companionActionDuration = 900; break;
      case 2: companionAction = CompanionAction::Glance; companionActionDuration = 1700; break;
      case 3: companionAction = CompanionAction::Happy; companionActionDuration = 1000; break;
      default: companionAction = CompanionAction::Pause; companionActionDuration = 1800; break;
    }
  }
  companionActionStarted = now;
}

void tickCompanion(uint32_t now) {
  const uint32_t elapsed = now - companionMoodStarted;
  if (companionMood == CompanionMood::Active) {
    if (elapsed >= companionActiveDuration) {
      companionMood = CompanionMood::Tired;
      companionMoodStarted = now;
      companionTiredDuration = companionBetween(5000, 8500);
      companionAction = CompanionAction::None;
    } else if (companionAction != CompanionAction::None &&
               now - companionActionStarted >= companionActionDuration) {
      companionAction = CompanionAction::None;
      companionNextAction = now + companionBetween(1200, 3600);
    } else if (companionAction == CompanionAction::None &&
               static_cast<int32_t>(now - companionNextAction) >= 0) {
      startCompanionAction(now);
    }
  } else if (companionMood == CompanionMood::Tired && elapsed >= companionTiredDuration) {
    companionMood = CompanionMood::Sleeping;
    companionMoodStarted = now;
    companionSleepingDuration = companionBetween(14000, 26000);
  } else if (companionMood == CompanionMood::Sleeping && elapsed >= companionSleepingDuration) {
    companionMood = CompanionMood::Waking;
    companionMoodStarted = now;
  } else if (companionMood == CompanionMood::Waking && elapsed >= 1200) {
    companionMood = CompanionMood::Active;
    companionMoodStarted = now;
    companionActiveDuration = companionBetween(45000, 85000);
    companionAction = CompanionAction::None;
    companionNextAction = now + companionBetween(900, 2500);
  }
}

float ease(float t) { return t * t * (3.0f - 2.0f * t); }

float blinkAt(uint32_t elapsed, uint32_t start) {
  const uint32_t t = elapsed - start;
  if (t >= 360) return 0;
  if (t < 130) return ease(static_cast<float>(t) / 130.0f);
  if (t < 170) return 1;
  return 1.0f - ease(static_cast<float>(t - 170) / 190.0f);
}

bool samePose(const CompanionPose& a, const CompanionPose& b) {
  return a.leftOpen == b.leftOpen && a.rightOpen == b.rightOpen &&
      a.gazeX == b.gazeX && a.gazeY == b.gazeY && a.bounce == b.bounce &&
      a.smile == b.smile && a.mouthOpen == b.mouthOpen && a.closedStyle == b.closedStyle &&
      a.leftBrowLength == b.leftBrowLength && a.leftBrowY0 == b.leftBrowY0 &&
      a.leftBrowY1 == b.leftBrowY1 && a.rightBrowLength == b.rightBrowLength &&
      a.rightBrowY0 == b.rightBrowY0 && a.rightBrowY1 == b.rightBrowY1;
}

float mix(float from, float to, float amount) { return from + (to - from) * amount; }

CompanionPose interpolatePose(const CompanionPose& from, const CompanionPose& to, float amount) {
  CompanionPose result;
  result.leftOpen = mix(from.leftOpen, to.leftOpen, amount);
  result.rightOpen = mix(from.rightOpen, to.rightOpen, amount);
  result.gazeX = mix(from.gazeX, to.gazeX, amount);
  result.gazeY = mix(from.gazeY, to.gazeY, amount);
  result.bounce = mix(from.bounce, to.bounce, amount);
  result.smile = mix(from.smile, to.smile, amount);
  result.mouthOpen = mix(from.mouthOpen, to.mouthOpen, amount);
  result.closedStyle = mix(from.closedStyle, to.closedStyle, amount);
  result.leftBrowLength = mix(from.leftBrowLength, to.leftBrowLength, amount);
  result.leftBrowY0 = mix(from.leftBrowY0, to.leftBrowY0, amount);
  result.leftBrowY1 = mix(from.leftBrowY1, to.leftBrowY1, amount);
  result.rightBrowLength = mix(from.rightBrowLength, to.rightBrowLength, amount);
  result.rightBrowY0 = mix(from.rightBrowY0, to.rightBrowY0, amount);
  result.rightBrowY1 = mix(from.rightBrowY1, to.rightBrowY1, amount);
  return result;
}

uint16_t faceTint(float amount) {
  const uint8_t red = static_cast<uint8_t>(0x9B * amount / 100.0f);
  const uint8_t green = static_cast<uint8_t>(0xE1 * amount / 100.0f);
  const uint8_t blue = static_cast<uint8_t>(0x5D * amount / 100.0f);
  return rgb((static_cast<uint32_t>(red) << 16) | (static_cast<uint32_t>(green) << 8) | blue);
}

void drawFaceEye(lgfx::LGFXBase& target, int cx, int cy, float openness,
                 float gazeX, float gazeY, float closedStyle) {
  if (openness <= 8.0f) {
    const float blinkAmount = 1.0f - closedStyle / 100.0f;
    const int outerY = lroundf(3.0f * blinkAmount);
    const int middleY = -lroundf(5.0f * blinkAmount);
    target.drawWideLine(cx - 16, cy + outerY, cx, cy + middleY, 3.0f, faceLime);
    target.drawWideLine(cx, cy + middleY, cx + 16, cy + outerY, 3.0f, faceLime);
    return;
  }
  const int eyeHeight = fmaxf(4.0f, lroundf(42.0f * openness / 100.0f));
  const int px = cx + lroundf(gazeX);
  const int py = cy + lroundf(gazeY);
  const int top = cy - eyeHeight / 2;
  const int corner = fminf(12.0f, eyeHeight * 0.5f);
  target.drawRoundRect(cx - 21, top, 42, eyeHeight, corner, faceLime);
  if (eyeHeight > 5)
    target.drawRoundRect(cx - 20, top + 1, 40, eyeHeight - 2,
                         fmaxf(1.0f, corner - 1.0f), faceLime);
  if (eyeHeight > 7)
    target.drawRoundRect(cx - 19, top + 2, 38, eyeHeight - 4,
                         fmaxf(1.0f, corner - 2.0f), faceLime);
  const int pupilRadius = fminf(4.0f, eyeHeight / 2.0f - 4.0f);
  if (pupilRadius > 0) target.fillCircle(px, py, pupilRadius, faceLime);
}

void drawFaceBrow(lgfx::LGFXBase& target, int cx, int cy, float length, float y0, float y1) {
  if (length < 1.0f) return;
  const int half = lroundf(length * 0.5f);
  target.drawWideLine(cx - half, cy + lroundf(y0), cx + half, cy + lroundf(y1),
                      2.5f, faceLime);
}

void drawFaceMouth(lgfx::LGFXBase& target, int ox, int oy, const CompanionPose& pose) {
  const int cx = ox + kCompanionFaceWidth / 2;
  const int cy = oy + 104 + lroundf(pose.bounce);
  const uint16_t lineColor = faceTint(100.0f - pose.mouthOpen);
  for (int x = -18; x < 18; ++x) {
    // Screen y grows downwards: negative curve depth raises the smile corners.
    const int y1 = lroundf(-pose.smile * x * x / 324.0f);
    const int y2 = lroundf(-pose.smile * (x + 1) * (x + 1) / 324.0f);
    target.drawWideLine(cx + x, cy + y1, cx + x + 1, cy + y2, 3.0f, lineColor);
  }
  if (pose.mouthOpen > 0.0f) {
    const int radius = fmaxf(1.0f, 5.0f * pose.mouthOpen / 100.0f);
    const uint16_t mouthColor = faceTint(pose.mouthOpen);
    target.fillCircle(cx, cy, radius, mouthColor);
    if (radius > 2) target.fillCircle(cx, cy, radius - 2, classicBackground);
  }
}

void drawFaceExpression(const CompanionPose& pose) {
  const int ox = companionFaceBuffered ? 0 : kCompanionFaceX;
  const int oy = companionFaceBuffered ? 0 : kCompanionFaceY;
  lgfx::LGFXBase& target = companionFaceBuffered ?
      static_cast<lgfx::LGFXBase&>(companionFace) : static_cast<lgfx::LGFXBase&>(tft);
  if (companionFaceBuffered) companionFace.fillSprite(classicBackground);
  else tft.fillRect(kCompanionFaceX, kCompanionFaceY,
                    kCompanionFaceWidth, kCompanionFaceHeight, classicBackground);
  const int leftX = ox + 30, rightX = ox + 110;
  const int leftY = oy + 30 + lroundf(pose.bounce);
  const int rightY = leftY;
  drawFaceBrow(target, leftX, leftY, pose.leftBrowLength, pose.leftBrowY0, pose.leftBrowY1);
  drawFaceBrow(target, rightX, rightY, pose.rightBrowLength, pose.rightBrowY0, pose.rightBrowY1);
  drawFaceEye(target, leftX, leftY, pose.leftOpen, pose.gazeX, pose.gazeY, pose.closedStyle);
  drawFaceEye(target, rightX, rightY, pose.rightOpen, pose.gazeX, pose.gazeY, pose.closedStyle);
  drawFaceMouth(target, ox, oy, pose);
  if (companionFaceBuffered) companionFace.pushSprite(kCompanionFaceX, kCompanionFaceY);
}

void drawCompanion(uint32_t now) {
  if (companionMood == CompanionMood::Uninitialized) startCompanion(now);
  tickCompanion(now);
  const uint32_t elapsed = now - companionActionStarted;
  float openness = 1.0f, rightOpenness = 1.0f, gazeX = 0.0f, gazeY = 0.0f;
  float smile = 7.0f, mouthOpen = 0.0f, bounce = 0.0f;
  float leftBrowLength = 0, leftBrowY0 = 0, leftBrowY1 = 0;
  float rightBrowLength = 0, rightBrowY0 = 0, rightBrowY1 = 0;
  const bool tired = companionMood == CompanionMood::Tired;
  const bool sleeping = companionMood == CompanionMood::Sleeping;
  const bool waking = companionMood == CompanionMood::Waking;
  if (tired) {
    openness = rightOpenness = 0.52f;
    smile = 0;
  } else if (sleeping) {
    openness = rightOpenness = 0.0f;
    smile = 2.0f;
  } else if (waking) {
    const float t = fminf(1.0f, static_cast<float>(now - companionMoodStarted) / 1200.0f);
    openness = rightOpenness = 0.08f + 1.07f * ease(t);
    bounce = lroundf(-4.0f * sinf(t * 3.14159265f));
    smile = 7.0f * ease(t);
    leftBrowLength = rightBrowLength = 24.0f;
    leftBrowY0 = leftBrowY1 = rightBrowY0 = rightBrowY1 = -26.0f;
  } else if (companionAction != CompanionAction::None) {
    const float t = fminf(1.0f, static_cast<float>(elapsed) / companionActionDuration);
    if (companionAction == CompanionAction::Blink) {
      openness = rightOpenness = 1.0f - blinkAt(elapsed, 0);
    } else if (companionAction == CompanionAction::DoubleBlink) {
      openness = rightOpenness = 1.0f - fmaxf(blinkAt(elapsed, 0), blinkAt(elapsed, 440));
    } else if (companionAction == CompanionAction::Glance) {
      if (t < 0.25f) gazeX = -ease(t / 0.25f);
      else if (t < 0.50f) gazeX = -1.0f + 2.0f * ease((t - 0.25f) / 0.25f);
      else if (t < 0.75f) { gazeX = 1.0f - ease((t - 0.50f) / 0.25f); gazeY = -ease((t - 0.50f) / 0.25f); }
      else { gazeX = 0; gazeY = -1.0f + ease((t - 0.75f) / 0.25f); }
    } else if (companionAction == CompanionAction::Happy) {
      bounce = lroundf(-3.0f * sinf(t * 3.14159265f));
      smile = 7.0f + 2.0f * sinf(t * 3.14159265f);
    } else if (companionAction == CompanionAction::Surprise) {
      openness = rightOpenness = 1.12f;
      mouthOpen = 100.0f;
      smile = 0;
      leftBrowLength = rightBrowLength = 24.0f;
      leftBrowY0 = leftBrowY1 = rightBrowY0 = rightBrowY1 = -26.0f;
    } else if (companionAction == CompanionAction::Sad) {
      openness = rightOpenness = 0.7f;
      smile = -4.0f;
      leftBrowLength = rightBrowLength = 22.0f;
      leftBrowY0 = -22.0f; leftBrowY1 = -28.0f;
      rightBrowY0 = -28.0f; rightBrowY1 = -22.0f;
    } else if (companionAction == CompanionAction::Pause) {
      gazeX = 0.3f;
      rightOpenness = 1.08f;
      smile = 3.0f;
      rightBrowLength = 21.0f;
      rightBrowY0 = -24.0f; rightBrowY1 = -28.0f;
    }
  }
  CompanionPose target;
  target.leftOpen = fmaxf(0.0f, fminf(115.0f, openness * 100.0f));
  target.rightOpen = fmaxf(0.0f, fminf(115.0f, rightOpenness * 100.0f));
  target.gazeX = gazeX * 7.0f;
  target.gazeY = gazeY * 5.0f;
  target.bounce = bounce;
  target.smile = smile;
  target.mouthOpen = mouthOpen;
  target.closedStyle = sleeping ? 100.0f : 0.0f;
  target.leftBrowLength = leftBrowLength;
  target.leftBrowY0 = leftBrowY0;
  target.leftBrowY1 = leftBrowY1;
  target.rightBrowLength = rightBrowLength;
  target.rightBrowY0 = rightBrowY0;
  target.rightBrowY1 = rightBrowY1;

  int expressionKey = 0;  // Blink, glance and bounce have continuous action curves.
  if (companionMood == CompanionMood::Tired) expressionKey = 4;
  else if (companionMood == CompanionMood::Sleeping) expressionKey = 5;
  else if (companionMood == CompanionMood::Waking) expressionKey = 6;
  else if (companionAction == CompanionAction::Surprise) expressionKey = 1;
  else if (companionAction == CompanionAction::Sad) expressionKey = 2;
  else if (companionAction == CompanionAction::Pause) expressionKey = 3;

  CompanionPose pose = target;
  if (!companionPoseValid) {
    companionExpressionKey = expressionKey;
    companionTransitioning = false;
  } else {
    if (expressionKey != companionExpressionKey) {
      companionTransitionFrom = lastCompanionPose;
      companionExpressionKey = expressionKey;
      companionTransitionStarted = now;
      companionTransitioning = true;
    }
    if (companionTransitioning) {
      const uint32_t duration = now - companionTransitionStarted;
      if (duration >= kCompanionTransitionMs) {
        companionTransitioning = false;
      } else {
        pose = interpolatePose(companionTransitionFrom, target,
            static_cast<float>(duration) / kCompanionTransitionMs);
      }
    }
    if (samePose(pose, lastCompanionPose)) return;
    if (static_cast<uint32_t>(now - lastCompanionRender) < kCompanionFrameMs) return;
  }
  drawFaceExpression(pose);
  lastCompanionPose = pose;
  companionPoseValid = true;
  lastCompanionRender = now;
}

void drawClockFace() {
  for (int hour = 0; hour < 12; ++hour) {
    const float angle = (hour * 30.0f - 90.0f) * 0.01745329252f;
    const int outer = kClockRadius;
    const int inner = outer - (hour % 3 == 0 ? 8 : 4);
    const uint16_t color = hour % 3 == 0 ? clockCyan : clockTrack;
    tft.drawWideLine(lroundf(kClockCenterX + cosf(angle) * inner),
                     lroundf(kClockCenterY + sinf(angle) * inner),
                     lroundf(kClockCenterX + cosf(angle) * outer),
                     lroundf(kClockCenterY + sinf(angle) * outer),
                     hour % 3 == 0 ? 2.5f : 1.5f, color);
  }
}

void clockPoint(float angle, int length, int& x, int& y) {
  const float radians = (angle - 90.0f) * 0.01745329252f;
  x = lroundf(kClockCenterX + cosf(radians) * length);
  y = lroundf(kClockCenterY + sinf(radians) * length);
}

void clockHand(int x, int y, float width, uint16_t color) {
  tft.drawWideLine(kClockCenterX, kClockCenterY, x, y, width, color);
}

void drawAnalogClock(time_t timestamp) {
  if (!clockFaceDrawn) {
    drawClockFace();
    clockFaceDrawn = true;
  }
  if (timestamp < 1704067200) {
    if (!clockWaitingDrawn) {
      text("WAITING FOR TIME", kClockCenterX, kClockCenterY + 38, 160, 18,
           &fonts::Font2, white);
      clockWaitingDrawn = true;
    }
    return;
  }

  struct tm current{};
  if (!localtime_r(&timestamp, &current)) return;
  if (clockWaitingDrawn) {
    text("", kClockCenterX, kClockCenterY + 38, 160, 18, &fonts::Font2, white);
    clockWaitingDrawn = false;
    clockLastSecond = -1;
    clockLastMinute = -1;
    clockLastDate = -1;
    clockHandsDrawn = false;
    clockTimeDrawn = false;
  }
  static const char* const weekdays[] = {"Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"};
  static const char* const months[] = {"Jan", "Feb", "Mar", "Apr", "May", "Jun",
      "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"};
  char date[20], year[8];
  snprintf(date, sizeof(date), "%s, %d %s", weekdays[current.tm_wday], current.tm_mday,
           months[current.tm_mon]);
  snprintf(year, sizeof(year), "%04d", current.tm_year + 1900);
  const bool minuteChanged = current.tm_min != clockLastMinute || !clockHandsDrawn;
  const bool secondChanged = current.tm_sec != clockLastSecond || !clockHandsDrawn;
  if (current.tm_yday != clockLastDate || !clockTimeDrawn) {
    tft.setTextSize(1);
    text(date, kClockCenterX, kClockDateY, 150, 18, &fonts::FreeSans9pt7b, white);
    text(year, kClockCenterX, kClockYearY, 64, 18, &fonts::FreeSans9pt7b, clockCyan);
    clockLastDate = current.tm_yday;
    clockTimeDrawn = true;
  }
  if (minuteChanged || secondChanged) {
    if (clockHandsDrawn) {
      if (minuteChanged) {
        clockHand(clockHourX, clockHourY, 5.0f, classicBackground);
        clockHand(clockMinuteX, clockMinuteY, 3.0f, classicBackground);
      }
      if (secondChanged) clockHand(clockSecondX, clockSecondY, 1.5f, classicBackground);
    }
    const float hourAngle = (current.tm_hour % 12) * 30.0f + current.tm_min * 0.5f;
    const float minuteAngle = current.tm_min * 6.0f;
    const float secondAngle = current.tm_sec * 6.0f;
    if (minuteChanged) {
      clockPoint(hourAngle, 39, clockHourX, clockHourY);
      clockPoint(minuteAngle, 56, clockMinuteX, clockMinuteY);
      clockHand(clockHourX, clockHourY, 5.0f, white);
      clockHand(clockMinuteX, clockMinuteY, 3.0f, white);
      clockLastMinute = current.tm_min;
    }
    if (secondChanged) {
      clockPoint(secondAngle, 64, clockSecondX, clockSecondY);
      clockHand(clockSecondX, clockSecondY, 1.5f, clockCyan);
      clockLastSecond = current.tm_sec;
    }
    tft.fillCircle(kClockCenterX, kClockCenterY, 4, clockCyan);
    clockHandsDrawn = true;
  }
}

void heading(const char* value, bool classic, bool changedMode) {
  static int oldWidth = 0, oldHeight = 0;
  const int y = classic ? kClassicHeadingY : kStackHeadingY;
  if (!changedMode && oldWidth) tft.fillRect(120 - oldWidth / 2, y - oldHeight / 2,
                                            oldWidth, oldHeight, canvas);
  oldWidth = oldHeight = 0;
  if (!value[0]) return;  // Explicit empty clears the old heading, with no fallback.
  const int radius = classic ? kClassicHeadingSafeRadius : kHeadingSafeRadius;
  const lgfx::IFont* candidates[] = {&fonts::FreeSansBold12pt7b,
      &fonts::FreeSansBold9pt7b, &fonts::Font2, &fonts::Font0};
  const int maxHeight = classic ? kClassicHeadingHeight : kStackHeadingHeight;
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

void classicSideArc(bool weekly, float remaining, bool drawTrack = true) {
  const int radius = kClassicGaugeRadius;
  const int inner = radius - kClassicThickness;
  const float mid = radius - kClassicThickness * 0.5f;
  const float start = weekly ? kClassicLeftArcStart : kClassicRightArcStart;
  const float finish = start + kClassicArcSweep;
  auto arc = [&](float from, float to, uint16_t color, int padding = 0) {
    // LovyanGFX wraps the right side's 315..405 degrees through zero.
    tft.fillEllipseArc(120, kClassicGaugeY, radius + padding, inner - padding,
                      radius + padding, inner - padding, from, to, color);
    for (float angle : {from, to}) {
      const float rad = angle * 0.01745329252f;
      tft.fillCircle(lroundf(120 + cosf(rad) * mid),
                     lroundf(kClassicGaugeY + sinf(rad) * mid), kClassicThickness / 2 + padding, color);
    }
  };
  if (drawTrack) {
    arc(start, finish, classicBackground, 1);  // Clear fractional cap rounding at the edges.
    arc(start, finish, weekly ? classicOrangeTrack : classicRedTrack);
  }
  if (remaining <= 0) return;
  const float sweep = kClassicArcSweep * fminf(remaining, 100.0f) / 100.0f;
  // Consumed usage stays faded at the top; remaining usage fills from the bottom.
  if (weekly) arc(start, start + sweep, classicOrange);
  else arc(finish - sweep, finish, classicRed);
}

float classicStartupFraction(uint32_t now) {
  const uint32_t elapsed = now - classicStarted;
  const float t = elapsed >= kGaugeDurationMs ? 1.0f :
      static_cast<float>(elapsed) / kGaugeDurationMs;
  const float inverse = 1.0f - t;
  return 1.0f - inverse * inverse * inverse;
}

float startupFraction(uint32_t now) {
  const uint32_t elapsed = now - gaugeStarted;
  const float t = elapsed >= kGaugeDurationMs ? 1.0f :
      static_cast<float>(elapsed) / kGaugeDurationMs;
  const float inverse = 1.0f - t;
  return 1.0f - inverse * inverse * inverse;
}

void text(const char* value, int cx, int y, int width, int height,
          const lgfx::IFont* font, uint16_t color) {
  tft.fillRect(cx - width / 2, y - height / 2, width, height, canvas);
  tft.setFont(font);
  tft.setTextColor(color);
  tft.setTextDatum(lgfx::middle_center);
  tft.drawString(value, cx, y);
}

void classicPercentage(int cx, float remaining, bool available, uint16_t color) {
  char value[16];
  if (available) snprintf(value, sizeof(value), "%.0f%%", floorf(remaining));
  else snprintf(value, sizeof(value), "--");
  tft.setTextSize(0.85f);
  text(value, cx, kClassicPercentY, kClassicPercentWidth, kClassicPercentHeight,
       &fonts::FreeSansBold18pt7b, color);
  tft.setTextSize(1);
}

void resetText(const usage::Window& window, int cx, int y) {
  char value[16];
  usage::formatReset(window, value, sizeof(value));
  text(value, cx, y, kCountdownWidth, kCountdownHeight, &fonts::Font2, muted);
}

void stackBar(int y, float remaining, uint16_t color, uint16_t trackColor) {
  const float clamped = fmaxf(0.0f, fminf(100.0f, remaining));
  const int filled = static_cast<int>(lroundf(kStackBarWidth * clamped / 100.0f));
  tft.fillRoundRect(kStackBarX, y - kStackBarHeight / 2, kStackBarWidth,
                    kStackBarHeight, kStackBarHeight / 2, trackColor);
  if (filled > 0)
    tft.fillRoundRect(kStackBarX, y - kStackBarHeight / 2, filled,
                      kStackBarHeight, kStackBarHeight / 2, color);
}

void stackSection(bool weekly, float remaining, bool available) {
  const int y = weekly ? kStackWeeklyY : kStackSessionY;
  const int barY = weekly ? kStackWeeklyBarY : kStackSessionBarY;
  const uint16_t color = weekly ? stackWeekly : stackSession;
  const uint16_t trackColor = weekly ? stackWeeklyTrack : stackSessionTrack;
  char value[8];
  if (available) snprintf(value, sizeof(value), "%.0f%%", floorf(remaining));
  else snprintf(value, sizeof(value), "--");
  const char* label = weekly ? "W" : "H";
  tft.setFont(&fonts::FreeSansBold12pt7b);
  tft.setTextSize(1);
  const int labelRight = kStackContentLeft + tft.textWidth(label) + 4;
  const int percentLeft = kStackContentRight - kValueWidth;
  int scale = 80;
  if (buffered) {
    line.fillSprite(canvas);
    line.setFont(&fonts::FreeSansBold18pt7b);
    line.setTextSize(static_cast<float>(scale) / 100.0f);
    int percentWidth = line.textWidth(value);
    while ((percentWidth + 8 > kValueWidth ||
            kStackContentRight - 4 - percentWidth < labelRight + kStackRowGap) && scale > 60) {
      scale -= 5;
      line.setTextSize(static_cast<float>(scale) / 100.0f);
      percentWidth = line.textWidth(value);
    }
    line.setTextColor(color);
    line.setTextDatum(lgfx::middle_right);
    line.drawString(value, kValueWidth - 4, kValueHeight / 2);
    line.pushSprite(percentLeft, y - kValueHeight / 2);
    line.setTextSize(1);
  } else {
    tft.setFont(&fonts::FreeSansBold18pt7b);
    tft.setTextSize(static_cast<float>(scale) / 100.0f);
    int percentWidth = tft.textWidth(value);
    while ((percentWidth + 8 > kValueWidth ||
            kStackContentRight - 4 - percentWidth < labelRight + kStackRowGap) && scale > 60) {
      scale -= 5;
      tft.setTextSize(static_cast<float>(scale) / 100.0f);
      percentWidth = tft.textWidth(value);
    }
    tft.fillRect(percentLeft, y - kValueHeight / 2, kValueWidth, kValueHeight, canvas);
    tft.setTextColor(color);
    tft.setTextDatum(lgfx::middle_right);
    tft.drawString(value, kStackContentRight - 4, y);
    tft.setTextSize(1);
  }
  stackBar(barY, available ? remaining : 0, color, trackColor);
}

void stackLabel(bool weekly) {
  const char* value = weekly ? "W" : "H";
  tft.setFont(&fonts::FreeSansBold12pt7b);
  tft.setTextSize(1);
  const int measured = tft.textWidth(value) + 4;
  const int center = kStackContentLeft + measured / 2;
  text(value, center, weekly ? kStackWeeklyY : kStackSessionY, measured, 28,
       &fonts::FreeSansBold12pt7b, white);
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
  companionFace.setColorDepth(16);
  companionFaceBuffered = companionFace.createSprite(kCompanionFaceWidth,
                                                       kCompanionFaceHeight) != nullptr;
  Preferences prefs;
  if (prefs.begin("irozon-ui", false)) {
    const uint8_t saved = prefs.getUChar("mode", 0);
    selectedMode = saved == static_cast<uint8_t>(Mode::Classic) ? Mode::Classic :
        saved == static_cast<uint8_t>(Mode::Companion) ? Mode::Companion :
        saved == static_cast<uint8_t>(Mode::AnalogClock) ? Mode::AnalogClock : Mode::Green;
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
  selectMode(selectedMode == Mode::Green ? Mode::Classic :
              selectedMode == Mode::Classic ? Mode::Companion :
              selectedMode == Mode::Companion ? Mode::AnalogClock : Mode::Green);
}

void ui::selectMode(Mode next) {
  if ((next != Mode::Green && next != Mode::Classic && next != Mode::Companion &&
       next != Mode::AnalogClock) ||
      next == selectedMode) return;
  selectedMode = next;
  gaugeAnimating = false;
  classicAnimating = false;
  if (selectedMode == Mode::Companion) startCompanion(millis());
  clockFaceDrawn = clockWaitingDrawn = clockTimeDrawn = clockHandsDrawn = false;
  clockLastDate = -1;
  clockLastSecond = clockLastMinute = -1;
  lastClockPoll = 0;
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
  if (!enabled) {
    gaugeAnimating = false;
    classicAnimating = false;
  }
  Preferences prefs;
  if (prefs.begin("irozon-ui", false)) {
    if (prefs.putBool("power", enabled) != 1) Serial.println("Display power state could not be saved");
    prefs.end();
  }
  if (enabled) {
    paintedMode = 255;  // Redraw latest usage completely after waking.
    if (selectedMode == Mode::AnalogClock) {
      clockFaceDrawn = clockWaitingDrawn = clockTimeDrawn = clockHandsDrawn = false;
      clockLastDate = -1;
      clockLastSecond = clockLastMinute = -1;
      lastClockPoll = 0;
    }
  }
}

void ui::draw(const usage::Snapshot& data, usage::Status status, uint32_t sampleRevision) {
  // Missing fields retain the last heading. An explicit empty string is a value,
  // persisted even in standby, before any panel work or early return.
  bool headingChanged = false;
  if (data.heading.configured && (!displayHeading.configured ||
      strcmp(displayHeading.text, data.heading.text) != 0)) {
    displayHeading = data.heading;
    headingChanged = true;
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
  const bool freshUsage = sampleRevision != usageRevision;
  const bool validUsage = (data.weekly.available && std::isfinite(data.weekly.remaining)) ||
      (data.session.available && std::isfinite(data.session.remaining));
  if (freshUsage) {
    usageRevision = sampleRevision;
    if (startupGaugeAnimationPlayed) gaugeAnimating = false;
    if (classicStartupPlayed) classicAnimating = false;
  }
  if (!startupGaugeAnimationPlayed && sampleRevision != 0 && validUsage &&
      selectedMode == Mode::Green) {
    startupGaugeAnimationPlayed = true;
    gaugeAnimating = true;
    gaugeWeekAvailable = data.weekly.available;
    gaugeSessionAvailable = data.session.available;
    gaugeWeekTarget = gaugeWeekAvailable ? data.weekly.remaining : 0;
    gaugeSessionTarget = gaugeSessionAvailable ? data.session.remaining : 0;
    gaugeStarted = millis();
    lastGaugeFrame = gaugeStarted;
  }
  bool startClassic = false;
  if (!classicStartupPlayed && sampleRevision != 0 && validUsage &&
      selectedMode == Mode::Classic) {
    classicStartupPlayed = classicAnimating = startClassic = true;
    classicWeekAvailable = data.weekly.available;
    classicSessionAvailable = data.session.available;
    classicWeekTarget = classicWeekAvailable ? data.weekly.remaining : 0;
    classicSessionTarget = classicSessionAvailable ? data.session.remaining : 0;
    classicStarted = millis();
    lastClassicFrame = classicStarted;
  }
  const bool classicAvailabilityChanged = classicAnimating &&
      (data.weekly.available != classicWeekAvailable || data.session.available != classicSessionAvailable);
  if (classicAvailabilityChanged) classicAnimating = false;
  const bool classic = selectedMode == Mode::Classic;
  const bool companion = selectedMode == Mode::Companion;
  const bool analogClock = selectedMode == Mode::AnalogClock;
  char screenKey[128];
  static char previousKey[128] = "";
  snprintf(screenKey, sizeof(screenKey), "%d:%d:%u:%d:%d:%u:%d:%d:%s",
           data.weekly.available, static_cast<int>(floorf(data.weekly.remaining)),
           data.weekly.resetInSeconds / 60 + (data.weekly.resetInSeconds % 60 != 0),
           data.session.available, static_cast<int>(floorf(data.session.remaining)),
           data.session.resetInSeconds / 60 + (data.session.resetInSeconds % 60 != 0),
           data.testData, static_cast<int>(status), companion ? displayHeading.text : "");
  if (!changedMode && (!freshUsage || companion || analogClock) &&
      strcmp(screenKey, previousKey) == 0) return;
  snprintf(previousKey, sizeof(previousKey), "%s", screenKey);
  tft.startWrite();
  if (changedMode) {
    canvas = classicBackground;
    tft.fillScreen(canvas);
    lastWeek = lastSession = -2;
    paintedMode = static_cast<uint8_t>(selectedMode);
    if (selectedMode == Mode::Companion) {
      companionPoseValid = false;
    }
  }
  if ((changedMode || headingChanged) && !analogClock && !companion)
    heading("Codex", classic, changedMode);
  const int week = data.weekly.available ? static_cast<int>(floorf(data.weekly.remaining)) : -1;
  const int session = data.session.available ? static_cast<int>(floorf(data.session.remaining)) : -1;
  if (selectedMode == Mode::Green &&
      (lastWeek != week || lastSession != session || status != lastStatus || freshUsage)) {
    stackLabel(true);
    stackLabel(false);
    stackSection(true, gaugeAnimating ? 0 : data.weekly.remaining,
                 data.weekly.available);
    stackSection(false, gaugeAnimating ? 0 : data.session.remaining,
                 data.session.available);
    lastWeek = week;
    lastSession = session;
  }
  if (companion) drawCompanion(millis());
  if (analogClock) drawAnalogClock(time(nullptr));
  if (classic && (!classicAnimating || startClassic) &&
      (lastWeek != week || status != lastStatus || freshUsage || classicAvailabilityChanged)) {
    classicSideArc(true, classicAnimating ? 0 : data.weekly.available ? data.weekly.remaining : 0);
    lastWeek = week;
  }
  if (classic && (!classicAnimating || startClassic) &&
      (lastSession != session || status != lastStatus || freshUsage || classicAvailabilityChanged)) {
    classicSideArc(false, classicAnimating ? 0 : data.session.available ? data.session.remaining : 0);
    lastSession = session;
  }
  if (selectedMode == Mode::Green) {
    tft.drawFastHLine(42, kStackDividerY, 156, classicTrack);
  } else if (classic) {
    tft.drawLine(120, kClassicDividerTop, 120, kClassicDividerBottom, classicTrack);
    if (!classicAnimating || startClassic) {
      classicPercentage(kClassicLeftX, classicAnimating ? 0 : data.weekly.remaining,
                        data.weekly.available, classicOrange);
      classicPercentage(kClassicRightX, classicAnimating ? 0 : data.session.remaining,
                        data.session.available, classicRed);
    }
    text("W", kClassicLeftX, kClassicLabelY, kClassicLabelWidth,
         kClassicLabelHeight, &fonts::FreeSansBold9pt7b, white);
    text("S", kClassicRightX, kClassicLabelY, kClassicLabelWidth,
         kClassicLabelHeight, &fonts::FreeSansBold9pt7b, white);
    for (int i = 0; i < 2; ++i) {
      char value[16];
      usage::formatReset(i == 0 ? data.weekly : data.session, value, sizeof(value));
      text(value, i == 0 ? kClassicLeftX : kClassicRightX, kClassicResetY,
           kClassicResetWidth, kCountdownHeight, &fonts::Font2, muted);
    }
    const char* note = data.testData ? "TEST DATA" :
        status == usage::Status::Stale ? "STALE" :
        status == usage::Status::Offline ? "OFFLINE" :
        status == usage::Status::Setup ? "WIFI SETUP" :
        status == usage::Status::NoData ? "NO DATA" :
        status == usage::Status::Partial ? "PARTIAL" : "";
    tft.fillRect(76, kClassicNoteY - 5, 88, 10, canvas);
    tft.setFont(&fonts::Font0);
    tft.setTextColor(data.testData ? white : amber);
    tft.setTextDatum(lgfx::middle_center);
    tft.drawString(note, 120, kClassicNoteY);
  }
  lastStatus = status;
  tft.endWrite();
}

void ui::animate() {
  if (selectedMode == Mode::AnalogClock) {
    if (!displayEnabled || panelSleeping || panelRecovering ||
        paintedMode != static_cast<uint8_t>(Mode::AnalogClock)) return;
    const uint32_t now = millis();
    if (static_cast<uint32_t>(now - lastClockPoll) < 1000) return;
    lastClockPoll = now;
    tft.startWrite();
    drawAnalogClock(time(nullptr));
    tft.endWrite();
    return;
  }
  if (selectedMode == Mode::Companion) {
    if (!displayEnabled || panelSleeping || panelRecovering ||
        paintedMode != static_cast<uint8_t>(Mode::Companion)) return;
    const uint32_t now = millis();
    if (static_cast<uint32_t>(now - lastCompanionFrame) < kCompanionFrameMs) return;
    lastCompanionFrame = now;
    tft.startWrite();
    drawCompanion(now);
    tft.endWrite();
    return;
  }
  if (selectedMode == Mode::Classic) {
    if (!displayEnabled || panelSleeping || panelRecovering || !classicAnimating ||
        paintedMode != static_cast<uint8_t>(Mode::Classic)) return;
    const uint32_t now = millis();
    if (static_cast<uint32_t>(now - lastClassicFrame) < kAnimationFrameMs) return;
    const bool finished = static_cast<uint32_t>(now - classicStarted) >= kGaugeDurationMs;
    const float eased = classicStartupFraction(now);
    const float week = classicWeekTarget * eased, session = classicSessionTarget * eased;
    tft.startWrite();
    // Grow over existing tracks; restore the final raster to remove cap rounding remnants.
    classicSideArc(true, week, finished);
    classicSideArc(false, session, finished);
    classicPercentage(kClassicLeftX, week, classicWeekAvailable, classicOrange);
    classicPercentage(kClassicRightX, session, classicSessionAvailable, classicRed);
    tft.endWrite();
    lastClassicFrame = now;
    if (finished) classicAnimating = false;
    return;
  }
  const uint32_t now = millis();
  if (!displayEnabled || panelSleeping || panelRecovering || selectedMode != Mode::Green ||
      paintedMode != static_cast<uint8_t>(Mode::Green) || !gaugeAnimating ||
      static_cast<uint32_t>(now - lastGaugeFrame) < kAnimationFrameMs) return;
  const uint32_t elapsed = now - gaugeStarted;
  const bool finished = elapsed >= kGaugeDurationMs;
  const float eased = finished ? 1.0f : startupFraction(now);
  tft.startWrite();
  stackSection(true, gaugeWeekTarget * eased, gaugeWeekAvailable);
  stackSection(false, gaugeSessionTarget * eased, gaugeSessionAvailable);
  tft.endWrite();
  lastGaugeFrame = now;
  if (finished) gaugeAnimating = false;
}
