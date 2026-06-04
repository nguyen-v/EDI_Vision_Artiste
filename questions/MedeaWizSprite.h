/**
 * @file    MedeaWizSprite.h
 * @brief   MedeaWiz Sprite: send one binary byte to play a file (9600 8N1 TTL).
 */

#pragma once

#include <Arduino.h>
#include <SoftwareSerial.h>

class MedeaWizSprite {
public:
  /**
   * @param serial SoftwareSerial port (RX pin unused if not wired; use INPUT_PULLUP on RX).
   * @param txPin Arduino pin wired to Sprite RX (for logging only).
   */
  MedeaWizSprite(SoftwareSerial &serial, uint8_t txPin);

  bool playFile(uint8_t fileIndex);

  uint8_t txPin() const;

private:
  SoftwareSerial &serial_;
  uint8_t txPin_;
};
