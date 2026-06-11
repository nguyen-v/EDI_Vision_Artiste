# MediaMap workbook ? Vision Artiste

File: **`MediaMap_workbook.xlsx`** (English)

## Add or remove a question

1. Open **Questions**.
2. Fill the first empty **Artwork** row (rows 4–27).
3. Set **Question plays on** (dropdown) and the **score grid** (columns M–AB).
4. **Step** updates automatically. **Image index** and SD file names are computed (no manual file numbers).
5. **Remove a step:** clear **Artwork** on that row (do not delete the row — formulas use fixed row numbers).
6. **CodeGen** sheet: column A follows Questions live (scores, screen, step). Recalculate the workbook after edits (Excel: **F9**; LibreOffice: recalculate all). Or run `python3 scripts/generate_media_workbook.py --emit-cpp` and paste into `QuestionnaireConfig.h`.
   Each `QUESTIONS[]` line must be `{ offset, Portrait|Landscape, { weights… } }`. The pre-8130f96 format `{ offset, { CAT_… }, screen }` swaps text/artwork WIZ routing and breaks language switching.
7. **SD WIZ1** / **SD WIZ2** follow the Questions sheet automatically (recalculate after edits).

SD file numbering: same slot index on both cards per step (questions 1-13 use indices 1-13). **Idle text** = 4 language files on WIZ1 (`000`, `032`, ...). **Idle artwork** = single `000.mp4` on WIZ2. **Profiles** = indices **17-20** (text per language on WIZ1, one artwork per profile on WIZ2) so they do not overlap the last question at index 13.

## Scoring (weighted profiles)

Each answer adds **0–10 points per profile** (see the **B1–B4 score grid** on the Questions sheet: columns M–AB). Default template when a row is created: one profile gets **10**, the others **0** per button. Totals are summed across all steps; highest wins. Edit the grid on **Questions**; **CodeGen** picks up changes after recalc, or use `--emit-cpp`.

## Video files (SD content)

Each row on **SD WIZ1** / **SD WIZ2** is one MP4 on that card. Use the exact filename from the sheet (`000.mp4`, `001.mp4`, ...).

### Format

| Property | Value |
|----------|--------|
| Container | MP4 (`+faststart` / `moov` at front recommended) |
| Video | **H.264**, pixel format **yuv420p** |
| Frame rate | Not critical for static slides; any common rate is fine (placeholders often use 1 fps) |
| Audio | **AAC** (MedeaWiz expects a track; silent AAC is OK for test files) |
| Filename | Three digits + `.mp4` (e.g. `012.mp4`) |

### Resolution

| Player | Encoded size | Content layout |
|--------|----------------|----------------|
| **WIZ1** (portrait display) | **1920x1080** | Author in **1080x1920**, then rotate **90 deg clockwise** for the file (or deliver equivalent 1920x1080) |
| **WIZ2** (landscape display) | **1920x1080** | Native landscape |

Match the **Aspect** column on each SD sheet row.

### Duration

| Clip type | Placeholder / recommended length |
|-----------|----------------------------------|
| **Idle** text (WIZ1, per language) + idle artwork (WIZ2 `000`) | **10 minutes** (600 s) |
| **Questions** + question artwork | **1 min 10 s** (70 s; firmware question timeout is 60 s) |
| **Personality text** (WIZ1, indices 17–20 × language blocks) | **60 s** |
| **Personality artwork** (WIZ2, indices 17–20, all languages) | **60 s** |

### Convert images to MP4

From the project root, use **`scripts/convert_image_to_medeawiz.sh`** to turn a still image (PNG, JPEG, …) into a MedeaWiz-ready clip. The script loops the image at 1 fps, applies portrait rotation or landscape scaling, and adds a silent AAC track.

**Workbook-linked mode** (recommended): pass the step and part; filename, WIZ player, portrait/landscape, and clip length come from **`MediaMap_workbook.xlsx`**.

```bash
# Question text (per language) — e.g. Q3 French intro on WIZ1
./scripts/convert_image_to_medeawiz.sh artwork.png --q 3 --part text --lang FR

# Question artwork (language-independent) — e.g. Q3 image on WIZ2
./scripts/convert_image_to_medeawiz.sh magritte.png --q 3 --part image

# Idle intro text (WIZ1, per language) and idle artwork (WIZ2)
./scripts/convert_image_to_medeawiz.sh intro_en.png --idle --part text --lang EN
./scripts/convert_image_to_medeawiz.sh idle_art.png --idle --part image

# Personality profile text (WIZ1) — emotions, realiste, matiere, conteur
./scripts/convert_image_to_medeawiz.sh profile_de.png --profile emotions --part text --lang DE
./scripts/convert_image_to_medeawiz.sh profile_art.png --profile emotions --part image
```

By default, encoded files land under **`videos/out/sd_wiz1/`** and **`videos/out/sd_wiz2/`**. Copy each folder onto the matching SD card (WIZ1 card ← `sd_wiz1`, WIZ2 card ← `sd_wiz2`).

Use **`--dry-run`** to print the resolved slot without encoding. Use **`--out-dir DIR`** to write elsewhere (e.g. a staging folder before copying to the cards).

**Manual mode** (when you already know mode and filename):

```bash
./scripts/convert_image_to_medeawiz.sh portrait intro_en.png 000.mp4 --type idle
./scripts/convert_image_to_medeawiz.sh landscape artwork_01.png 001.mp4 --type question
```

| Option | Purpose |
|--------|---------|
| `--type idle\|question\|profile` | Clip length: 600 s / 70 s / 60 s (manual mode; set automatically in workbook mode) |
| `--duration SEC` | Override length |
| `--fit contain\|cover` | Letterbox (default) or crop to fill |
| `--no-audio` | Omit AAC track |
| `--workbook PATH` | Alternate workbook path |

Requires **ffmpeg** and **ffprobe** on `PATH`, and **`pip install openpyxl`** for workbook resolution (`medeawiz_workbook.py`).

### Firmware timers

| State | Behaviour |
|-------|-----------|
| **Idle** | No auto-idle; media watchdog every **9 min 50 s** (per-language intro is not restarted too soon) |
| **Question** | **60 s** without an answer → idle; watchdog every **55 s** during the step |
| **Personality** | **60 s** → idle; watchdog every **55 s** |
| **Reset (B5)** | Idle immediately |

### Placeholder test videos

From the project root:

```bash
python3 scripts/generate_test_videos.py
```

Output: `videos/test/sd_wiz1/` and `videos/test/sd_wiz2/` (copy onto each SD card).

- Defaults: **70 s** quiz, **600 s** idle, **60 s** profile; **1920×1080** (WIZ1 rotated), H.264 + AAC.
- Placeholders are a single still image looped for the duration (fast encode).
- Options: `--media-duration`, `--intro-duration`, `--profile-duration`, `--no-audio`, `-j N`.

Requires **ffmpeg** on `PATH` and `pip install openpyxl` (workbook import).

## Tie-break

If two profiles reach the **exact same total** after weighted scoring: Emotions, then Conteur, then Matiere, then Realiste.
