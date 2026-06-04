/**
 * =================================================================================================
 * @file    QuestionnaireConfig.h
 * @brief   "Sors de l'ombre l'artiste?!" — questions, écrans, profils, fichiers MedeaWiz.
 *
 * Catégories (index):
 *   CAT_EMOTIONS  — L'artiste poétique / des émotions
 *   CAT_REALISTE  — L'artiste réaliste / de la précision
 *   CAT_MATIERE   — L'artiste de la matière
 *   CAT_CONTEUR   — L'artiste conteur
 *
 * Fichiers (écran question, par langue) — bloc de FILES_PER_LANGUAGE :
 *   offset 0 = écran d'attente (intro / idle)
 *   offset 1..N = texte question (questionFileOffset par étape du quiz)
 *   offsets 17..20 = résultats profil (4 catégories ; après les 13 questions)
 *
 * Fichiers (écran image, carte WIZ2 ou WIZ1 selon la question) — même indice que le
 * texte de l'étape (questionFileOffset), sans décalage ; indépendant de la langue sur
 * la carte artwork. Idle : texte = bloc langue (WIZ1) ; visuel idle = 000 seul (toutes langues).
 *
 * questionScreen — where question TEXT plays (artwork is always on the other WIZ):
 *   Portrait  = question on WIZ1 (1080x1920), artwork on WIZ2 (1920x1080).
 *   Landscape = question on WIZ2 (1920x1080), artwork on WIZ1 (1080x1920).
 * =================================================================================================
 */

#pragma once

#include <Arduino.h>

namespace QuestionnaireConfig {

// -------------------------------------------------------------------------------------------------
// Profils
// -------------------------------------------------------------------------------------------------

static const uint8_t CAT_EMOTIONS = 0;
static const uint8_t CAT_REALISTE = 1;
static const uint8_t CAT_MATIERE = 2;
static const uint8_t CAT_CONTEUR = 3;

static const uint8_t NUM_CHOICES = 4;
static const uint8_t NUM_CATEGORIES = 4;
static const uint8_t NUM_LANGUAGES = 4;

static const uint8_t FILES_PER_LANGUAGE = 32;

static const uint8_t IDLE_QUESTION_OFFSET = 0;
static const uint8_t QUESTION_FILE_FIRST_OFFSET = 1;
static const uint8_t PERSONALITY_FILE_BASE_OFFSET = 17;

static const uint8_t IDLE_IMAGE_FILE = 0;

// En cas d'égalité : premier profil listé ici qui atteint le score max l'emporte.
static const uint8_t TIEBREAK_ORDER[NUM_CATEGORIES] = {
  CAT_EMOTIONS,
  CAT_CONTEUR,
  CAT_MATIERE,
  CAT_REALISTE,
};

/// Ignore B1–B4 at the start of each question (prevents skipping through by spamming).
static const unsigned long QUESTION_INPUT_LOCK_MS = 2000UL;

static const unsigned long QUESTION_TIMEOUT_MS = 60UL * 1000UL;
static const unsigned long PERSONALITY_DISPLAY_MS = 60UL * 1000UL;
/// Idle: long replay interval so per-language intro clips are not restarted too soon.
static const unsigned long MEDIA_WATCHDOG_IDLE_MS = (9UL * 60UL + 50UL) * 1000UL;
/// Questions / personality: shorter than question timeout (60 s).
static const unsigned long MEDIA_WATCHDOG_MS = 55UL * 1000UL;

// -------------------------------------------------------------------------------------------------
// Écrans portrait / paysage
// -------------------------------------------------------------------------------------------------

enum QuestionScreen : uint8_t {
  Portrait,   ///< Question text on WIZ1; artwork on WIZ2.
  Landscape,  ///< Question text on WIZ2; artwork on WIZ1.
};

// -------------------------------------------------------------------------------------------------
// Par question
// -------------------------------------------------------------------------------------------------

struct QuestionEntry {
  uint8_t questionFileOffset;
  uint8_t choiceCategories[NUM_CHOICES];
  QuestionScreen questionScreen;
};

/**
 * choiceCategories : boutons B1..B4 (ordre du texte fourni pour chaque question).
 * questionFileOffset : SD text file index (= step 1..N), set automatically by the workbook.
 * Image file index = questionFileOffset (same slot on the artwork SD card).
 * Regenerer QUESTIONS[] depuis le classeur (CodeGen) ou --emit-cpp.
 */
// --- BEGIN_QUESTIONNAIRE_CONFIG ---
static const uint8_t NUM_QUESTIONS = 13;
static const QuestionEntry QUESTIONS[NUM_QUESTIONS] = {
  { 1, { CAT_EMOTIONS, CAT_REALISTE, CAT_MATIERE, CAT_CONTEUR }, Landscape },
  { 2, { CAT_CONTEUR, CAT_REALISTE, CAT_MATIERE, CAT_EMOTIONS }, Portrait },
  { 3, { CAT_EMOTIONS, CAT_REALISTE, CAT_MATIERE, CAT_CONTEUR }, Portrait },
  { 4, { CAT_EMOTIONS, CAT_REALISTE, CAT_MATIERE, CAT_CONTEUR }, Landscape },
  { 5, { CAT_EMOTIONS, CAT_REALISTE, CAT_MATIERE, CAT_CONTEUR }, Landscape },
  { 6, { CAT_EMOTIONS, CAT_CONTEUR, CAT_MATIERE, CAT_REALISTE }, Landscape },
  { 7, { CAT_REALISTE, CAT_MATIERE, CAT_CONTEUR, CAT_EMOTIONS }, Landscape },
  { 8, { CAT_MATIERE, CAT_CONTEUR, CAT_REALISTE, CAT_EMOTIONS }, Portrait },
  { 9, { CAT_EMOTIONS, CAT_CONTEUR, CAT_REALISTE, CAT_MATIERE }, Landscape },
  { 10, { CAT_MATIERE, CAT_CONTEUR, CAT_REALISTE, CAT_EMOTIONS }, Landscape },
  { 11, { CAT_EMOTIONS, CAT_CONTEUR, CAT_REALISTE, CAT_MATIERE }, Portrait },
  { 12, { CAT_REALISTE, CAT_EMOTIONS, CAT_MATIERE, CAT_CONTEUR }, Landscape },
  { 13, { CAT_EMOTIONS, CAT_CONTEUR, CAT_REALISTE, CAT_MATIERE }, Portrait },











};
// --- END_QUESTIONNAIRE_CONFIG ---

static const uint8_t PERSONALITY_FILE_OFFSET[NUM_CATEGORIES] = {
  17, 18, 19, 20
};

static const char *const PERSONALITY_NAMES[NUM_CATEGORIES] = {
  "Emotions",
  "Realiste",
  "Matiere",
  "Conteur",
};

// -------------------------------------------------------------------------------------------------
// Helpers
// -------------------------------------------------------------------------------------------------

inline bool questionOnWiz1(QuestionScreen screen) {
  return screen == Portrait;
}

inline uint8_t languageBase(uint8_t language) {
  if (language >= NUM_LANGUAGES) {
    language = 0;
  }
  return (uint8_t)(language * FILES_PER_LANGUAGE);
}

inline uint8_t idleQuestionFile(uint8_t language) {
  return (uint8_t)(languageBase(language) + IDLE_QUESTION_OFFSET);
}

inline bool isLastQuestion(uint8_t questionIndex) {
  return questionIndex >= NUM_QUESTIONS - 1;
}

inline uint8_t questionFileOffset(uint8_t questionIndex) {
  if (questionIndex >= NUM_QUESTIONS) {
    questionIndex = 0;
  }
  return QUESTIONS[questionIndex].questionFileOffset;
}

inline uint8_t questionFile(uint8_t questionIndex, uint8_t language) {
  return (uint8_t)(languageBase(language) + questionFileOffset(questionIndex));
}

inline uint8_t personalityFile(uint8_t category, uint8_t language) {
  if (category >= NUM_CATEGORIES) {
    category = 0;
  }
  return (uint8_t)(languageBase(language) + PERSONALITY_FILE_OFFSET[category]);
}

inline uint8_t personalityArtworkFile(uint8_t category) {
  if (category >= NUM_CATEGORIES) {
    category = 0;
  }
  return PERSONALITY_FILE_OFFSET[category];
}

inline QuestionScreen questionScreenFor(uint8_t questionIndex) {
  if (questionIndex >= NUM_QUESTIONS) {
    return Portrait;
  }
  return QUESTIONS[questionIndex].questionScreen;
}

inline uint8_t imageFile(uint8_t questionIndex) {
  if (questionIndex >= NUM_QUESTIONS) {
    return IDLE_IMAGE_FILE;
  }
  return questionFileOffset(questionIndex);
}

inline uint8_t categoryForChoice(uint8_t questionIndex, uint8_t choice) {
  if (questionIndex >= NUM_QUESTIONS || choice >= NUM_CHOICES) {
    return CAT_EMOTIONS;
  }
  return QUESTIONS[questionIndex].choiceCategories[choice];
}

inline const char *personalityName(uint8_t category) {
  if (category >= NUM_CATEGORIES) {
    category = 0;
  }
  return PERSONALITY_NAMES[category];
}

inline uint8_t resultCategory(const uint8_t counts[NUM_CATEGORIES]) {
  uint8_t maxCount = 0;
  for (uint8_t c = 0; c < NUM_CATEGORIES; c++) {
    if (counts[c] > maxCount) {
      maxCount = counts[c];
    }
  }
  if (maxCount == 0) {
    return TIEBREAK_ORDER[0];
  }
  for (uint8_t i = 0; i < NUM_CATEGORIES; i++) {
    const uint8_t c = TIEBREAK_ORDER[i];
    if (counts[c] == maxCount) {
      return c;
    }
  }
  return TIEBREAK_ORDER[0];
}

}  // namespace QuestionnaireConfig
