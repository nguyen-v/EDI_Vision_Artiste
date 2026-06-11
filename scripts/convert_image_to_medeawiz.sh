#!/usr/bin/env bash
# Convert a still image to a MedeaWiz-ready MP4 for Vision Artiste SD cards.
#
# Manual (you pick mode + output filename):
#   ./scripts/convert_image_to_medeawiz.sh portrait intro_en.png 000.mp4 --type idle
#   ./scripts/convert_image_to_medeawiz.sh landscape artwork_01.png 001.mp4
#
# From workbook (filename, WIZ, portrait/landscape from Questions sheet):
#   ./scripts/convert_image_to_medeawiz.sh photo.png --q 3 --part text --lang FR
#   ./scripts/convert_image_to_medeawiz.sh art.png --q 3 --part image
#   ./scripts/convert_image_to_medeawiz.sh intro.png --idle --part text --lang EN
#   ./scripts/convert_image_to_medeawiz.sh idle.png --idle --part image
#   ./scripts/convert_image_to_medeawiz.sh prof.png --profile emotions --part text --lang DE
#
# Copy sd_wiz1/*.mp4 onto the WIZ1 SD card, sd_wiz2/*.mp4 onto WIZ2.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
DEFAULT_WORKBOOK="${REPO_ROOT}/questions/MediaMap_workbook.xlsx"

MODE=""
INPUT=""
OUTPUT=""
TYPE=""
DURATION=""
FIT="contain"
FPS="1"
WITH_AUDIO=1
WORKBOOK=""
OUT_DIR=""
WB_QUESTION=""
WB_IDLE=0
WB_PROFILE=""
WB_PART=""
WB_LANG=""
DRY_RUN=0

usage() {
  cat <<'EOF'
Usage:
  convert_image_to_medeawiz.sh MODE INPUT OUTPUT [options]
  convert_image_to_medeawiz.sh INPUT --q STEP --part text|image [--lang LANG] [options]

Workbook-linked (reads questions/MediaMap_workbook.xlsx):
  --q, --question STEP   Quiz step 1-13 (Questions sheet)
  --idle                 Idle intro text (WIZ1) or artwork (WIZ2)
  --profile NAME         emotions | realiste | matiere | conteur
  --part text|image      Question/idle/profile text vs artwork
  --lang, --language XX  EN | FR | DE | IT (required for text clips)
  --workbook PATH        Override workbook path
  --out-dir DIR          Write under DIR/sd_wiz1|sd_wiz2/ (default: videos/out)

Manual encode:
  MODE                   portrait | landscape
  OUTPUT                 Target .mp4 (e.g. 001.mp4)

Options:
  --type TYPE     idle (600 s) | question (70 s) | profile (60 s)
  --duration SEC  Override clip length
  --fit MODE      contain (letterbox) | cover (crop)  [default: contain]
  --fps N         Still loop frame rate  [default: 1]
  --no-audio      Omit AAC track
  --dry-run       Resolve workbook slot only; do not encode
  -h, --help      Show this help
EOF
}

die() {
  echo "error: $*" >&2
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    portrait|landscape)
      MODE="$1"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    --q|--question)
      WB_QUESTION="${2:-}"
      shift 2
      ;;
    --idle)
      WB_IDLE=1
      shift
      ;;
    --profile)
      WB_PROFILE="${2:-}"
      shift 2
      ;;
    --part)
      WB_PART="${2:-}"
      shift 2
      ;;
    --lang|--language)
      WB_LANG="${2:-}"
      shift 2
      ;;
    --workbook)
      WORKBOOK="${2:-}"
      shift 2
      ;;
    --out-dir)
      OUT_DIR="${2:-}"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --type)
      TYPE="${2:-}"
      shift 2
      ;;
    --duration)
      DURATION="${2:-}"
      shift 2
      ;;
    --fit)
      FIT="${2:-}"
      shift 2
      ;;
    --fps)
      FPS="${2:-}"
      shift 2
      ;;
    --no-audio)
      WITH_AUDIO=0
      shift
      ;;
    -*)
      die "unknown option: $1"
      ;;
    *)
      if [[ -z "$INPUT" ]]; then
        INPUT="$1"
      elif [[ -z "$OUTPUT" && -z "$WB_PART" ]]; then
        OUTPUT="$1"
      elif [[ -n "$WB_PART" && -z "$OUTPUT" ]]; then
        die "unexpected argument: $1 (workbook mode sets OUTPUT via --out-dir)"
      else
        die "unexpected argument: $1"
      fi
      shift
      ;;
  esac
done

[[ -n "$INPUT" ]] || { usage; die "INPUT image path is required"; }
[[ -f "$INPUT" ]] || die "input not found: $INPUT"

if [[ -n "$WB_QUESTION" || "$WB_IDLE" -eq 1 || -n "$WB_PROFILE" ]]; then
  [[ -n "$WB_PART" ]] || die "workbook mode requires --part text or --part image"
  [[ -f "${WORKBOOK:-$DEFAULT_WORKBOOK}" ]] || die "workbook not found: ${WORKBOOK:-$DEFAULT_WORKBOOK}"

  RESOLVE_ARGS=(python3 "${SCRIPT_DIR}/medeawiz_workbook.py" --shell --part "$WB_PART")
  RESOLVE_ARGS+=(--workbook "${WORKBOOK:-$DEFAULT_WORKBOOK}")
  if [[ -n "$WB_QUESTION" ]]; then
    RESOLVE_ARGS+=(--q "$WB_QUESTION")
  elif [[ "$WB_IDLE" -eq 1 ]]; then
    RESOLVE_ARGS+=(--idle)
  else
    RESOLVE_ARGS+=(--profile "$WB_PROFILE")
  fi
  if [[ -n "$WB_LANG" ]]; then
    RESOLVE_ARGS+=(--lang "$WB_LANG")
  fi
  if [[ -n "$OUT_DIR" ]]; then
    RESOLVE_ARGS+=(--out-dir "$OUT_DIR")
  elif [[ -z "$OUTPUT" ]]; then
    OUT_DIR="${REPO_ROOT}/videos/out"
    RESOLVE_ARGS+=(--out-dir "$OUT_DIR")
  fi

  RESOLVED="$( "${RESOLVE_ARGS[@]}" )" || die "workbook resolve failed"
  eval "$RESOLVED"

  echo "Workbook slot:"
  if [[ -n "${STEP:-}" ]]; then
    echo "  step      Q${STEP}"
  elif [[ "$WB_IDLE" -eq 1 ]]; then
    echo "  step      idle"
  else
    echo "  step      profile ${WB_PROFILE}"
  fi
  echo "  part      ${WB_PART}${LANGUAGE:+ / ${LANGUAGE}}"
  echo "  player    ${PLAYER} -> ${SD_FOLDER}/${FILENAME}"
  [[ -n "${ARTWORK:-}" ]] && echo "  artwork   ${ARTWORK}"

  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "Dry run: would encode ${MODE} -> ${OUTPUT} (type ${TYPE})"
    exit 0
  fi
fi

[[ -n "$MODE" ]] || { usage; die "MODE (portrait|landscape) is required, or use --q / --idle / --profile"; }
[[ -n "$OUTPUT" ]] || die "OUTPUT .mp4 path is required (or use workbook mode with --out-dir)"

case "$MODE" in
  portrait|landscape) ;;
  *) die "MODE must be portrait or landscape (got: $MODE)" ;;
esac

if [[ -z "$TYPE" ]]; then
  TYPE="question"
fi

case "$TYPE" in
  idle)     [[ -n "$DURATION" ]] || DURATION=600 ;;
  question) [[ -n "$DURATION" ]] || DURATION=70 ;;
  profile)  [[ -n "$DURATION" ]] || DURATION=60 ;;
  *) die "--type must be idle, question, or profile (got: $TYPE)" ;;
esac

case "$FIT" in
  contain|cover) ;;
  *) die "--fit must be contain or cover (got: $FIT)" ;;
esac

command -v ffmpeg >/dev/null 2>&1 || die "ffmpeg not found on PATH"
command -v ffprobe >/dev/null 2>&1 || die "ffprobe not found on PATH"

if [[ "$FIT" == "contain" ]]; then
  FIT_EXPR="force_original_aspect_ratio=decrease"
else
  FIT_EXPR="force_original_aspect_ratio=increase"
fi

if [[ "$MODE" == "portrait" ]]; then
  if [[ "$FIT" == "contain" ]]; then
    VF="scale=1080:1920:${FIT_EXPR},pad=1080:1920:(ow-iw)/2:(oh-ih)/2,transpose=1"
  else
    VF="scale=1080:1920:${FIT_EXPR},crop=1080:1920,transpose=1"
  fi
else
  if [[ "$FIT" == "contain" ]]; then
    VF="scale=1920:1080:${FIT_EXPR},pad=1920:1080:(ow-iw)/2:(oh-ih)/2"
  else
    VF="scale=1920:1080:${FIT_EXPR},crop=1920:1080"
  fi
fi

mkdir -p "$(dirname "$OUTPUT")"

TMP_OUT="${OUTPUT}.part.mp4"
rm -f "$TMP_OUT"

echo "Converting: $INPUT"
echo "  mode      $MODE ($([[ "$MODE" == portrait ]] && echo '1080x1920, rotate 90 CW -> 1920x1080' || echo '1920x1080'))"
echo "  type      $TYPE (${DURATION}s)"
echo "  fit       $FIT @ ${FPS} fps"
echo "  output    $OUTPUT"

FFMPEG_ARGS=(
  ffmpeg -hide_banner -loglevel error -y
  -loop 1 -framerate "$FPS" -i "$INPUT"
)

if [[ "$WITH_AUDIO" -eq 1 ]]; then
  FFMPEG_ARGS+=(
    -f lavfi -i "anullsrc=r=48000:cl=mono:d=${DURATION}"
  )
fi

FFMPEG_ARGS+=(
  -vf "$VF"
  -t "$DURATION"
  -map 0:v:0
  -c:v libx264 -pix_fmt yuv420p
  -preset medium -tune stillimage -crf 23
  -r "$FPS"
  -frames:v "$(( DURATION * FPS ))"
)

if [[ "$WITH_AUDIO" -eq 1 ]]; then
  FFMPEG_ARGS+=(
    -map 1:a:0
    -c:a aac -b:a 32k
  )
else
  FFMPEG_ARGS+=(-an)
fi

FFMPEG_ARGS+=(-movflags +faststart "$TMP_OUT")

"${FFMPEG_ARGS[@]}"
mv -f "$TMP_OUT" "$OUTPUT"

ACTUAL="$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$OUTPUT")"
VINFO="$(ffprobe -v error -select_streams v:0 -show_entries stream=codec_name,width,height,pix_fmt -of csv=p=0 "$OUTPUT")"
AINFO="$(ffprobe -v error -select_streams a:0 -show_entries stream=codec_name -of csv=p=0 "$OUTPUT" 2>/dev/null || true)"
ffmpeg -v error -i "$OUTPUT" -f null - >/dev/null

echo "Done: $OUTPUT"
echo "  duration  ${ACTUAL}s (wanted ${DURATION}s)"
echo "  video     ${VINFO}"
if [[ "$WITH_AUDIO" -eq 1 ]]; then
  echo "  audio     ${AINFO}"
fi
