/**
 * =================================================================================================
 * @file    LanguageSelector.h
 * @ingroup position_reader
 * @brief   Debounced four-position language selector.
 * @date    2026-05-27
 *
 * This class reads a rotary switch wired as four `INPUT_PULLUP` pins, where exactly one selected
 * language pin is grounded at a time. Invalid transient readings are ignored, and a new language is
 * accepted only after it remains stable for the configured debounce period.
 * =================================================================================================
 */

#pragma once

#include <Arduino.h>

// =================================================================================================
// Language selector
// =================================================================================================

/**
 * @brief Debounced reader for the four-way language selector.
 */
class LanguageSelector {
public:
  /// Number of supported language positions.
  static const uint8_t NUM_LANGUAGES = 4;

  /// Invalid raw selection (no pin grounded or several pins grounded).
  static const uint8_t INVALID = 0xFF;

  /// Default language used when no valid selection is available at boot.
  static const uint8_t DEFAULT_LANGUAGE = 0;

  /**
   * @brief Construct a language selector reader.
   * @param pins Four Arduino pins wired to the rotary selector.
   * @param debounceMs Required stability time before accepting a new language.
   */
  LanguageSelector(const uint8_t (&pins)[NUM_LANGUAGES], unsigned long debounceMs);

  // -----------------------------------------------------------------------------------------------
  /**
   * @brief Configure the selector pins and capture the boot language.
   */
  void begin();

  // -----------------------------------------------------------------------------------------------
  /**
   * @brief Update debounce state.
   * @param now Current `millis()` timestamp.
   * @return `true` when the current language changed.
   */
  bool update(unsigned long now);

  // -----------------------------------------------------------------------------------------------
  /**
   * @brief Return the currently accepted language index.
   */
  uint8_t current() const;

  // -----------------------------------------------------------------------------------------------
  /**
   * @brief Return a short printable language label.
   * @param language Language index.
   */
  const char *label(uint8_t language) const;

  // -----------------------------------------------------------------------------------------------
  /**
   * @brief Read the raw selector state without debounce.
   */
  uint8_t readRaw() const;

private:
  const uint8_t *pins_;
  unsigned long debounceMs_;
  uint8_t current_ = DEFAULT_LANGUAGE;
  uint8_t pending_ = INVALID;
  unsigned long pendingSinceMs_ = 0;
};
