/**
 * =================================================================================================
 * @file    LanguageSelector.cpp
 * @ingroup position_reader
 * @brief   Debounced four-position language selector implementation.
 * @date    2026-05-27
 * =================================================================================================
 */

#include "LanguageSelector.h"

namespace {
const char *const LANGUAGE_LABELS[LanguageSelector::NUM_LANGUAGES] = {
  "EN", "FR", "DE", "IT"
};
}

// =================================================================================================
// Construction and setup
// =================================================================================================

LanguageSelector::LanguageSelector(
  const uint8_t (&pins)[NUM_LANGUAGES],
  unsigned long debounceMs
) : pins_(pins),
    debounceMs_(debounceMs) {}

// -------------------------------------------------------------------------------------------------

void LanguageSelector::begin() {
  for (uint8_t i = 0; i < NUM_LANGUAGES; i++) {
    pinMode(pins_[i], INPUT_PULLUP);
  }
  delay(5);

  const uint8_t initial = readRaw();
  if (initial != INVALID) {
    current_ = initial;
  }
}

// =================================================================================================
// Debounced language updates
// =================================================================================================

bool LanguageSelector::update(unsigned long now) {
  const uint8_t raw = readRaw();
  if (raw == INVALID) {
    // Rotation can momentarily ground no pins or several pins. Treat that as a transient and keep
    // the already accepted language.
    pending_ = INVALID;
    return false;
  }
  if (raw == current_) {
    pending_ = INVALID;
    return false;
  }
  if (raw != pending_) {
    // First sighting of a different valid language: start the debounce timer, but do not accept it
    // until the same value survives for the full debounce interval.
    pending_ = raw;
    pendingSinceMs_ = now;
    return false;
  }
  if ((unsigned long)(now - pendingSinceMs_) < debounceMs_) {
    return false;
  }

  current_ = raw;
  pending_ = INVALID;
  return true;
}

// -------------------------------------------------------------------------------------------------

uint8_t LanguageSelector::current() const {
  return current_;
}

// -------------------------------------------------------------------------------------------------

const char *LanguageSelector::label(uint8_t language) const {
  if (language >= NUM_LANGUAGES) {
    language = DEFAULT_LANGUAGE;
  }
  return LANGUAGE_LABELS[language];
}

// -------------------------------------------------------------------------------------------------

uint8_t LanguageSelector::readRaw() const {
  int8_t found = -1;
  for (uint8_t i = 0; i < NUM_LANGUAGES; i++) {
    if (digitalRead(pins_[i]) == LOW) {
      // Exactly one switch position should be grounded. Multiple LOW pins means the selector is
      // between detents or wiring is invalid, so the debouncer should ignore it.
      if (found != -1) {
        return INVALID;
      }
      found = (int8_t)i;
    }
  }
  return found < 0 ? INVALID : (uint8_t)found;
}
