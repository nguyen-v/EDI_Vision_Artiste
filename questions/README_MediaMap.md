# MediaMap workbook ? Vision Artiste

File: **`MediaMap_workbook.xlsx`** (English)

## Add a question

1. Open **Questions**.
2. Fill the first empty **Artwork** row (rows 4?27).
3. Set **Question plays on** (dropdown) and the **score grid** (columns M–AB).
4. **Step** updates automatically. **Image index** and SD file names are computed (no manual file numbers).
5. Copy **CodeGen** column A into `QuestionnaireConfig.h` (or use `--emit-cpp`).
6. **SD WIZ1** / **SD WIZ2** follow the Questions sheet automatically (open/recalculate in Excel or LibreOffice).

SD file numbering: same slot index on both cards per step (questions 1-13 use indices 1-13). **Idle text** = 4 language files on WIZ1 (`000`, `032`, ...). **Idle artwork** = single `000.mp4` on WIZ2. **Profiles** = indices **17-20** (text per language on WIZ1, one artwork per profile on WIZ2) so they do not overlap the last question at index 13.

## Scoring (weighted profiles)

Each answer adds **0–10 points per profile** (see the **B1–B4 score grid** on the Questions sheet: columns M–AB). Default template when a row is created: one profile gets **10**, the others **0** per button. Totals are summed across all steps; highest wins. Edit the grid in the workbook, then run `python3 scripts/generate_media_workbook.py --emit-cpp` and update `QuestionnaireConfig.h`.

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
