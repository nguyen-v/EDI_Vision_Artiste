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
 * Scoring: each answer adds choiceWeights[button][category] (0–10) to categoryScores[].
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

static const uint8_t SCORE_WEIGHT_MIN = 0;
static const uint8_t SCORE_WEIGHT_MAX = 10;

// En cas d'égalité de score total : premier profil listé ici l'emporte.
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
  QuestionScreen questionScreen;
  uint8_t choiceWeights[NUM_CHOICES][NUM_CATEGORIES];
};

/**
 * choiceWeights : points 0–10 per category when B1..B4 is pressed (workbook score grid).
 * questionFileOffset : SD text file index (= step 1..N), set automatically by the workbook.
 * Image file index = questionFileOffset (same slot on the artwork SD card).
 * Regenerer QUESTIONS[] depuis le classeur (CodeGen) ou --emit-cpp.
 */
// --- BEGIN_QUESTIONNAIRE_CONFIG ---
static const uint8_t NUM_QUESTIONS = 13;
static const QuestionEntry QUESTIONS[NUM_QUESTIONS] = {
  // Step 1 - Caravaggio - Supper at Emmaus
  { 1, Landscape, { { 10, 0, 0, 0 }, { 0, 10, 0, 0 }, { 0, 0, 10, 0 }, { 0, 0, 0, 10 } } },
  // Step 2 - Monet - Rouen Cathedrals
  { 2, Portrait, { { 0, 0, 0, 10 }, { 0, 10, 0, 0 }, { 0, 0, 10, 0 }, { 10, 0, 0, 0 } } },
  // Step 3 - Magritte - Empire of Light
  { 3, Portrait, { { 10, 0, 0, 0 }, { 0, 10, 0, 0 }, { 0, 0, 10, 0 }, { 0, 0, 0, 10 } } },
  // Step 4 - Delaunay / Kirchner - night landscape
  { 4, Landscape, { { 10, 0, 0, 0 }, { 0, 10, 0, 0 }, { 0, 0, 10, 0 }, { 0, 0, 0, 10 } } },
  // Step 5 - Van Gogh - Starry Night
  { 5, Landscape, { { 10, 0, 0, 0 }, { 0, 10, 0, 0 }, { 0, 0, 10, 0 }, { 0, 0, 0, 10 } } },
  // Step 6 - Hopper - Nighthawks (Q6A)
  { 6, Landscape, { { 10, 0, 0, 0 }, { 0, 0, 0, 10 }, { 0, 0, 10, 0 }, { 0, 10, 0, 0 } } },
  // Step 7 - Hopper - Night Windows (Q6B)
  { 7, Landscape, { { 0, 10, 0, 0 }, { 0, 0, 10, 0 }, { 0, 0, 0, 10 }, { 10, 0, 0, 0 } } },
  // Step 8 - Photo - Sudek / Brassai (Q7)
  { 8, Portrait, { { 0, 0, 10, 0 }, { 0, 0, 0, 10 }, { 0, 10, 0, 0 }, { 10, 0, 0, 0 } } },
  // Step 9 - Fuseli - The Nightmare
  { 9, Landscape, { { 10, 0, 0, 0 }, { 0, 0, 0, 10 }, { 0, 10, 0, 0 }, { 0, 0, 10, 0 } } },
  // Step 10 - Soulages - Outrenoir
  { 10, Landscape, { { 0, 0, 10, 0 }, { 0, 0, 0, 10 }, { 0, 10, 0, 0 }, { 10, 0, 0, 0 } } },
  // Step 11 - Vallotton - The Bibliophile
  { 11, Portrait, { { 10, 0, 0, 0 }, { 0, 0, 0, 10 }, { 0, 10, 0, 0 }, { 0, 0, 10, 0 } } },
  // Step 12 - Grandville - Cast Shadows
  { 12, Landscape, { { 0, 10, 0, 0 }, { 10, 0, 0, 0 }, { 0, 0, 10, 0 }, { 0, 0, 0, 10 } } },
  // Step 13 - Your work - final 4 motifs Q12
  { 13, Portrait, { { 10, 0, 0, 0 }, { 0, 0, 0, 10 }, { 0, 10, 0, 0 }, { 0, 0, 10, 0 } } },
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

inline void applyChoiceScore(
  uint8_t questionIndex,
  uint8_t choice,
  uint16_t scores[NUM_CATEGORIES]
) {
  if (questionIndex >= NUM_QUESTIONS || choice >= NUM_CHOICES) {
    return;
  }
  const QuestionEntry &entry = QUESTIONS[questionIndex];
  for (uint8_t c = 0; c < NUM_CATEGORIES; c++) {
    scores[c] += entry.choiceWeights[choice][c];
  }
}

inline uint8_t dominantCategoryForChoice(uint8_t questionIndex, uint8_t choice) {
  if (questionIndex >= NUM_QUESTIONS || choice >= NUM_CHOICES) {
    return CAT_EMOTIONS;
  }
  const QuestionEntry &entry = QUESTIONS[questionIndex];
  uint8_t best = 0;
  uint8_t bestWeight = 0;
  for (uint8_t c = 0; c < NUM_CATEGORIES; c++) {
    const uint8_t w = entry.choiceWeights[choice][c];
    if (w > bestWeight) {
      bestWeight = w;
      best = c;
    }
  }
  return best;
}

inline const char *personalityName(uint8_t category) {
  if (category >= NUM_CATEGORIES) {
    category = 0;
  }
  return PERSONALITY_NAMES[category];
}

inline uint8_t resultCategory(const uint16_t scores[NUM_CATEGORIES]) {
  uint16_t maxScore = 0;
  for (uint8_t c = 0; c < NUM_CATEGORIES; c++) {
    if (scores[c] > maxScore) {
      maxScore = scores[c];
    }
  }
  if (maxScore == 0) {
    return TIEBREAK_ORDER[0];
  }
  for (uint8_t i = 0; i < NUM_CATEGORIES; i++) {
    const uint8_t c = TIEBREAK_ORDER[i];
    if (scores[c] == maxScore) {
      return c;
    }
  }
  return TIEBREAK_ORDER[0];
}

}  // namespace QuestionnaireConfig
