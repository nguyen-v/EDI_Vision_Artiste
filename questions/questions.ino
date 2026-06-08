/**
 * =================================================================================================
 * @file    questions.ino
 * @brief   Quiz "Sors de l'ombre l'artiste?!" — dual MedeaWiz, 12 questions, 4 profils.
 *
 * Boutons B1..B4 : réponse immédiate (passe à la question suivante).
 * Bouton B5 (A2) : reset / démarrage — idle ↔ quiz.
 * D4–D7 : sélecteur de langue.
 * WIZ1 TX=D10, WIZ2 TX=D12 (SoftwareSerial 9600).
 * =================================================================================================
 */

#include <Arduino.h>
#include <SoftwareSerial.h>

#include "LanguageSelector.h"
#include "MedeaWizSprite.h"
#include "QuestionnaireConfig.h"

using namespace QuestionnaireConfig;

// =================================================================================================
// Hardware
// =================================================================================================

static const uint8_t CHOICE_PINS[NUM_CHOICES] = { 8, A0, A1, 9 };
static const uint8_t RESET_PIN = A2;
// Language selector — LANGUAGE_PINS[lang] = D pin that reads LOW for that language.
//   [0] EN   [1] FR   [2] DE   [3] IT   (indices fixed; match SD file blocks on WIZ1)
//
// Software remap (no soldering): if detents always fire the same pins CW (e.g. D4→D5→D6→D7),
// permute this array so each language points at the pin for the detent where you want that language.
// Each of the four pin numbers must appear exactly once.
//
//   Detents CW fire:  D4       D5       D6       D7
//   Default array:    EN       FR       DE       IT     →  { 4, 5, 6, 7 }
//   Want CW read:     FR       IT       DE       EN     →  { 7, 4, 6, 5 }
//                     (FR←4    IT←5    DE←6    EN←7)
//
//   Detents CW fire:  D4       D5       D6       D7
//   Want CW read:     IT       FR       EN       DE     →  { 6, 5, 7, 4 }
//
// If detents CW fire pins in a non-monotonic order (e.g. D5→D7→D6→D4), the same idea applies:
// list which pin is LOW at each CW stop, then set LANGUAGE_PINS[lang] for that language.
//
// Active build: EN→D4  FR→D5  DE→D6  IT→D7  →  { 4, 5, 6, 7 }.
static const uint8_t LANGUAGE_PINS[LanguageSelector::NUM_LANGUAGES] = { 4, 5, 6, 7 };

static const uint8_t WIZ1_RX_PIN = 11;
static const uint8_t WIZ1_TX_PIN = 10;
static const uint8_t WIZ2_RX_PIN = 13;
static const uint8_t WIZ2_TX_PIN = 12;

static const unsigned long SPRITE_BAUD = 9600;
static const unsigned long SPRITE_BOOT_DELAY_MS = 500;
static const unsigned long SPRITE_INTER_CMD_GAP_MS = 3;
static const bool SPRITE_BOOT_SELF_TEST = false;
static const unsigned long LANGUAGE_DEBOUNCE_MS = 40;
static const unsigned long BUTTON_DEBOUNCE_MS = 30;
static const unsigned long LOOP_DELAY_MS = 20;

// =================================================================================================
// State
// =================================================================================================

enum class AppState : uint8_t {
  Idle,
  Question,
  Personality,
};

SoftwareSerial wiz1Serial(WIZ1_RX_PIN, WIZ1_TX_PIN);
SoftwareSerial wiz2Serial(WIZ2_RX_PIN, WIZ2_TX_PIN);

MedeaWizSprite wiz1(wiz1Serial, WIZ1_TX_PIN);
MedeaWizSprite wiz2(wiz2Serial, WIZ2_TX_PIN);
LanguageSelector languageSelector(LANGUAGE_PINS, LANGUAGE_DEBOUNCE_MS);

AppState appState = AppState::Idle;
uint8_t currentQuestion = 0;
uint8_t currentLanguage = LanguageSelector::DEFAULT_LANGUAGE;
uint16_t categoryScores[NUM_CATEGORIES] = {};
unsigned long stateSinceMs = 0;

uint8_t activeWiz1File = 255;
uint8_t activeWiz2File = 255;
unsigned long lastMediaCommandMs = 0;

uint8_t lastRawReading[5] = { HIGH, HIGH, HIGH, HIGH, HIGH };
unsigned long lastRawChangeMs[5] = {};
bool debouncedDown[5] = {};

// =================================================================================================
// Buttons
// =================================================================================================

static uint8_t buttonPin(uint8_t index) {
  return index < NUM_CHOICES ? CHOICE_PINS[index] : RESET_PIN;
}

static bool buttonPressedEdge(uint8_t index, unsigned long now) {
  const uint8_t raw = digitalRead(buttonPin(index));

  if (raw != lastRawReading[index]) {
    lastRawChangeMs[index] = now;
    lastRawReading[index] = raw;
  }

  const bool down =
    raw == LOW
    && (unsigned long)(now - lastRawChangeMs[index]) >= BUTTON_DEBOUNCE_MS;
  const bool edge = down && !debouncedDown[index];
  debouncedDown[index] = down;
  return edge;
}

static void initButtons() {
  for (uint8_t i = 0; i < NUM_CHOICES; i++) {
    pinMode(CHOICE_PINS[i], INPUT_PULLUP);
  }
  pinMode(RESET_PIN, INPUT_PULLUP);
}

// =================================================================================================
// MedeaWiz
// =================================================================================================

static void printMedeaWizFile(uint8_t fileIndex) {
  if (fileIndex < 100) {
    Serial.print('0');
  }
  if (fileIndex < 10) {
    Serial.print('0');
  }
  Serial.print(fileIndex);
  Serial.print(F(".xxx"));
}

static void initSpritePorts() {
  pinMode(WIZ1_RX_PIN, INPUT_PULLUP);
  pinMode(WIZ2_RX_PIN, INPUT_PULLUP);
  wiz1Serial.begin(SPRITE_BAUD);
  wiz2Serial.begin(SPRITE_BAUD);
}

static void markMediaCommand(unsigned long now) {
  lastMediaCommandMs = now;
}

static void playQuiet(MedeaWizSprite &wiz, uint8_t fileIndex) {
  if (fileIndex <= 200) {
    wiz.playFile(fileIndex);
  }
}

static void logAndPlay(
  MedeaWizSprite &wiz,
  const __FlashStringHelper *wizLabel,
  const __FlashStringHelper *role,
  uint8_t fileIndex
) {
  Serial.print(F("play "));
  Serial.print(wizLabel);
  Serial.print(F(" pin D"));
  Serial.print(wiz.txPin());
  Serial.print(F(" "));
  Serial.print(role);
  Serial.print(F(" "));
  printMedeaWizFile(fileIndex);
  Serial.print(F(" (index "));
  Serial.print(fileIndex);
  Serial.print(F(" cmd 0x"));
  if (fileIndex < 16) {
    Serial.print('0');
  }
  Serial.print(fileIndex, HEX);
  Serial.print(F(")"));

  if (!wiz.playFile(fileIndex)) {
    Serial.println(F(" FAIL"));
    return;
  }
  Serial.println(F(" TX ok"));
}

static void commandDualMedia(
  uint8_t wiz1File,
  uint8_t wiz2File,
  const __FlashStringHelper *role1,
  const __FlashStringHelper *role2,
  unsigned long now
) {
  activeWiz1File = wiz1File;
  activeWiz2File = wiz2File;
  logAndPlay(wiz1, F("WIZ1"), role1, wiz1File);
  delay(SPRITE_INTER_CMD_GAP_MS);
  logAndPlay(wiz2, F("WIZ2"), role2, wiz2File);
  markMediaCommand(now);
}

static void playIdleMedia(unsigned long now) {
  const uint8_t qFile = idleQuestionFile(currentLanguage);
  const uint8_t artFile = IDLE_IMAGE_FILE;

  Serial.print(F("media IDLE lang "));
  Serial.println(languageSelector.label(currentLanguage));

  // WIZ1 intro text per language (000, 032, …); WIZ2 idle art once at 000 for all langs.
  commandDualMedia(qFile, artFile, F("intro"), F("idle-art"), now);
}

static void playQuestionMedia(uint8_t questionIndex, uint8_t language, unsigned long now) {
  const uint8_t qFile = questionFile(questionIndex, language);
  const uint8_t iFile = imageFile(questionIndex);
  const QuestionScreen screen = questionScreenFor(questionIndex);

  Serial.print(F("media Q"));
  Serial.print((int)(questionIndex + 1));
  Serial.print(F(" lang "));
  Serial.println(languageSelector.label(language));

  if (questionOnWiz1(screen)) {
    commandDualMedia(qFile, iFile, F("question"), F("image"), now);
  } else {
    commandDualMedia(iFile, qFile, F("image"), F("question"), now);
  }
}

static void playPersonalityMedia(uint8_t category, uint8_t language, unsigned long now) {
  const uint8_t textFile = personalityFile(category, language);
  const uint8_t artFile = personalityArtworkFile(category);

  Serial.print(F("media personality "));
  Serial.print(personalityName(category));
  Serial.print(F(" lang "));
  Serial.println(languageSelector.label(language));

  // WIZ1 = profile text (per language); WIZ2 = profile artwork at same slot index.
  commandDualMedia(textFile, artFile, F("personality"), F("personality-art"), now);
}

static void handleMediaWatchdog(unsigned long now) {
  if (activeWiz1File == 255 && activeWiz2File == 255) {
    return;
  }
  const unsigned long watchdogMs =
    (appState == AppState::Idle) ? MEDIA_WATCHDOG_IDLE_MS : MEDIA_WATCHDOG_MS;
  if ((unsigned long)(now - lastMediaCommandMs) < watchdogMs) {
    return;
  }

  if (activeWiz1File != 255) {
    playQuiet(wiz1, activeWiz1File);
    delay(SPRITE_INTER_CMD_GAP_MS);
  }
  if (activeWiz2File != 255) {
    playQuiet(wiz2, activeWiz2File);
  }
  markMediaCommand(now);
}

static void replayCurrentMedia(unsigned long now) {
  switch (appState) {
    case AppState::Idle:
      playIdleMedia(now);
      break;
    case AppState::Question:
      playQuestionMedia(currentQuestion, currentLanguage, now);
      break;
    case AppState::Personality:
      playPersonalityMedia(resultCategory(categoryScores), currentLanguage, now);
      break;
  }
}

// =================================================================================================
// Flow
// =================================================================================================

static void resetCategoryScores() {
  for (uint8_t i = 0; i < NUM_CATEGORIES; i++) {
    categoryScores[i] = 0;
  }
}

static void enterIdle(unsigned long now) {
  appState = AppState::Idle;
  stateSinceMs = now;
  resetCategoryScores();
  playIdleMedia(now);
  Serial.println(F("state: IDLE (press reset to start)"));
}

static void startQuestion(uint8_t questionIndex, unsigned long now) {
  appState = AppState::Question;
  currentQuestion = questionIndex;
  stateSinceMs = now;
  playQuestionMedia(currentQuestion, currentLanguage, now);
  Serial.print(F("state: Q"));
  Serial.println((int)(questionIndex + 1));
}

static void startQuiz(unsigned long now) {
  resetCategoryScores();
  startQuestion(0, now);
  Serial.println(F("state: quiz started"));
}

static void enterPersonality(unsigned long now) {
  const uint8_t category = resultCategory(categoryScores);

  appState = AppState::Personality;
  stateSinceMs = now;
  playPersonalityMedia(category, currentLanguage, now);

  Serial.print(F("your personality is "));
  Serial.println(personalityName(category));
  Serial.print(F("scores Emo/Rea/Mat/Con: "));
  for (uint8_t i = 0; i < NUM_CATEGORIES; i++) {
    if (i > 0) {
      Serial.print(F("/"));
    }
    Serial.print(categoryScores[i]);
  }
  Serial.println();
  Serial.print(F("personality files WIZ1="));
  printMedeaWizFile(personalityFile(category, currentLanguage));
  Serial.print(F(" WIZ2="));
  printMedeaWizFile(personalityArtworkFile(category));
  Serial.println(F(" (60s then idle, or press reset)"));
}

static void selectChoice(uint8_t choice, unsigned long now) {
  applyChoiceScore(currentQuestion, choice, categoryScores);
  const uint8_t dominant = dominantCategoryForChoice(currentQuestion, choice);

  Serial.print(F("answer B"));
  Serial.print((int)(choice + 1));
  Serial.print(F(" -> +weights, dominant "));
  Serial.println(personalityName(dominant));

  if (isLastQuestion(currentQuestion)) {
    Serial.println(F("state: last question answered -> PERSONALITY"));
    enterPersonality(now);
    return;
  }

  const uint8_t nextQuestion = (uint8_t)(currentQuestion + 1);
  if (nextQuestion >= NUM_QUESTIONS) {
    Serial.println(F("state: quiz complete -> PERSONALITY"));
    enterPersonality(now);
    return;
  }

  startQuestion(nextQuestion, now);
}

static void handleQuestionTimeout(unsigned long now) {
  if (appState != AppState::Question) {
    return;
  }
  if ((unsigned long)(now - stateSinceMs) < QUESTION_TIMEOUT_MS) {
    return;
  }
  Serial.println(F("state: question timeout -> IDLE"));
  enterIdle(now);
}

static void handlePersonalityTimeout(unsigned long now) {
  if (appState != AppState::Personality) {
    return;
  }
  if (PERSONALITY_DISPLAY_MS == 0UL) {
    return;
  }
  if ((unsigned long)(now - stateSinceMs) < PERSONALITY_DISPLAY_MS) {
    return;
  }
  Serial.println(F("state: personality done -> IDLE"));
  enterIdle(now);
}

static void handleResetButton(unsigned long now) {
  if (!buttonPressedEdge(4, now)) {
    return;
  }

  Serial.println(F("reset button"));

  switch (appState) {
    case AppState::Idle:
      startQuiz(now);
      break;
    case AppState::Question:
    case AppState::Personality:
      enterIdle(now);
      break;
  }
}

static bool questionInputUnlocked(unsigned long now) {
  return (unsigned long)(now - stateSinceMs) >= QUESTION_INPUT_LOCK_MS;
}

static void handleChoiceButtons(unsigned long now) {
  if (appState != AppState::Question) {
    return;
  }
  if (!questionInputUnlocked(now)) {
    return;
  }

  for (uint8_t c = 0; c < NUM_CHOICES; c++) {
    if (buttonPressedEdge(c, now)) {
      selectChoice(c, now);
      return;
    }
  }
}

static void handleButtons(unsigned long now) {
  handleResetButton(now);
  handleChoiceButtons(now);
}

// =================================================================================================
// Arduino
// =================================================================================================

void setup() {
  Serial.begin(115200);

  initSpritePorts();
  delay(SPRITE_BOOT_DELAY_MS);

  if (SPRITE_BOOT_SELF_TEST) {
    wiz1Serial.write((uint8_t)0);
    delay(SPRITE_INTER_CMD_GAP_MS);
    wiz2Serial.write((uint8_t)0);
  }

  initButtons();
  languageSelector.begin();
  currentLanguage = languageSelector.current();

  const unsigned long now = millis();
  enterIdle(now);
}

void loop() {
  const unsigned long now = millis();

  if (languageSelector.update(now)) {
    currentLanguage = languageSelector.current();
    Serial.print(F("language "));
    Serial.println(languageSelector.label(currentLanguage));
    stateSinceMs = now;
    replayCurrentMedia(now);
  }

  handleButtons(now);
  handleQuestionTimeout(now);
  handlePersonalityTimeout(now);
  handleMediaWatchdog(now);

  delay(LOOP_DELAY_MS);
}
