#pragma once

// Pixel geometry shared with the host preview's bounds checks.
namespace ui_layout {
constexpr int kStackHeadingY = 36;
constexpr int kStackHeadingHeight = 24;
constexpr int kStackWeeklyY = 76;
constexpr int kStackSessionY = 148;
constexpr int kStackWeeklyBarY = 99;
constexpr int kStackSessionBarY = 171;
constexpr int kStackContentLeft = 42;
constexpr int kStackContentRight = 198;
constexpr int kStackRowGap = 16;
constexpr int kStackBarX = kStackContentLeft;
constexpr int kStackBarWidth = kStackContentRight - kStackContentLeft;
constexpr int kStackBarHeight = 8;
constexpr int kStackDividerY = 122;
constexpr int kCompanionFaceX = 50;
constexpr int kCompanionFaceY = 73;
constexpr int kCompanionFaceWidth = 140;
constexpr int kCompanionFaceHeight = 120;
constexpr int kClockCenterX = 120;
constexpr int kClockCenterY = 95;
constexpr int kClockRadius = 72;
constexpr int kClockDateY = 184;
constexpr int kClockYearY = 204;
constexpr int kCountdownWidth = 64;
constexpr int kClassicHeadingHeight = 24;
constexpr int kHeadingSafeRadius = 114;
constexpr int kClassicHeadingSafeRadius = 106;
constexpr int kValueWidth = 80;
constexpr int kValueHeight = 30;
constexpr int kClassicLeftX = 76;
constexpr int kClassicRightX = 164;
constexpr int kClassicGaugeY = 120;
constexpr int kClassicGaugeRadius = 104;
constexpr int kClassicLeftArcStart = 135;
constexpr int kClassicRightArcStart = 315;
constexpr int kClassicArcSweep = 90;
constexpr int kClassicHeadingY = 43;
constexpr int kClassicNoteY = 65;
constexpr int kClassicPercentY = 112;
constexpr int kClassicPercentWidth = 80;
constexpr int kClassicPercentHeight = 32;
constexpr int kClassicLabelY = 140;
constexpr int kClassicLabelWidth = 76;
constexpr int kClassicLabelHeight = 20;
constexpr int kClassicResetY = 164;
constexpr int kClassicResetWidth = 52;
constexpr int kCountdownHeight = 16;
constexpr int kClassicDividerTop = 94;
constexpr int kClassicDividerBottom = 174;
}  // namespace ui_layout
