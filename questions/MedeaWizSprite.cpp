#include "MedeaWizSprite.h"

MedeaWizSprite::MedeaWizSprite(SoftwareSerial &serial, uint8_t txPin)
  : serial_(serial),
    txPin_(txPin) {}

uint8_t MedeaWizSprite::txPin() const {
  return txPin_;
}

bool MedeaWizSprite::playFile(uint8_t fileIndex) {
  // MedeaWiz: one raw byte (NOT ASCII). 0=000.xxx, 1=001.xxx, 51=051.xxx, etc.
  if (fileIndex > 200) {
    return false;
  }

  const size_t sent = serial_.write(fileIndex);
  // Let the 8N1 frame finish (~1 ms at 9600) before commanding the other Sprite.
  delayMicroseconds(1200);
  return sent == 1;
}
