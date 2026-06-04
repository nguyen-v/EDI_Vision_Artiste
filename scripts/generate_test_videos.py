#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate placeholder test videos for the Vision Artiste quiz MedeaWiz setup.

Two SD cards (copy subfolders onto each card):
  sd_wiz1/      WIZ1, 1920x1080 (portrait layout rotated 90 deg CW), 4 language blocks
  sd_wiz2/      WIZ2, 1920x1080 landscape artwork

Naming matches MediaMap_workbook.xlsx / QuestionnaireConfig.h:
  Portrait file index = lang * FILES_PER_LANGUAGE + offset  (000.mp4 ?)
  WIZ2 file index     = same slot as text offset (000 idle, 001 step 1, ?)

Clips are H.264 yuv420p, 1920x1080 (WIZ1 rotated), AAC.
Defaults: 70s quiz, 600s idle, 60s profile. See questions/README_MediaMap.md.
Requires ffmpeg on PATH.

Example:
  python3 scripts/generate_test_videos.py
  python3 scripts/generate_test_videos.py --card portrait --languages FR
  python3 scripts/generate_test_videos.py --only 0,32,10 --media-duration 5
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# ---------------------------------------------------------------------------
# Media map metadata (shared with generate_media_workbook.py)
# ---------------------------------------------------------------------------

_SCRIPT_DIR = Path(__file__).resolve().parent


def _load_media_workbook():
    path = _SCRIPT_DIR / "generate_media_workbook.py"
    spec = importlib.util.spec_from_file_location("media_workbook", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


_MW = _load_media_workbook()
WIZ1_SD_ROWS = _MW.WIZ1_SD_ROWS
WIZ2_SD_ROWS = _MW.WIZ2_SD_ROWS
DEFAULT_QUESTIONS = _MW.DEFAULT_QUESTIONS
FILES_PER_LANGUAGE = _MW.FILES_PER_LANGUAGE
LANG_CODES: Tuple[str, ...] = _MW.LANG_CODES
CAT_NAMES: Tuple[str, ...] = _MW.CAT_NAMES

# ---------------------------------------------------------------------------
# Rendering defaults
# ---------------------------------------------------------------------------

PORTRAIT_WIDTH = 1080
PORTRAIT_HEIGHT = 1920
LANDSCAPE_WIDTH = 1920
LANDSCAPE_HEIGHT = 1080
FPS = 30
# Placeholder encode rate (1 fps => 600 frames per 10 min, not 18 000).
PLACEHOLDER_OUTPUT_FPS = 1
MEDIA_DURATION = 70  # 1m10s (quiz clips; question timeout is 60 s)
INTRO_DURATION = 10 * 60  # idle text + idle artwork
PROFILE_DURATION = 60  # personality finale (matches firmware)

LANGUAGE_COLOURS = ["#8957e5", "#db61a2", "#cf222e", "#0969da"]
WIZ1_ACCENT = "#2ea043"
WIZ2_ACCENT = "#8957e5"
INTRO_COLOUR = "#161b22"
PROFILE_COLOURS = ["#6e40c9", "#1f6feb", "#bc4c00", "#2ea043"]
QUESTION_COLOURS = [
    "#1f6feb", "#2ea043", "#d29922", "#bc4c00", "#8957e5",
    "#0969da", "#cf222e", "#3a3a3a", "#6e40c9", "#1b7f79",
    "#9a6700", "#8250df", "#21262d",
]

IDLE_TITLE = {
    "EN": "Out of the shadows\nartist?!",
    "FR": "Sors de l'ombre\nl'artiste?!",
    "DE": "Aus dem Schatten\nK\u00fcnstler?!",
    "IT": "Fuori dall'ombra\nartista?!",
}

PROFILE_TITLE = {
    "Emotions": {
        "EN": "Profile \u2013 Poetic / Emotions",
        "FR": "Profil \u2013 Po\u00e9tique / \u00c9motions",
        "DE": "Profil \u2013 Poetisch / Emotionen",
        "IT": "Profilo \u2013 Poetico / Emozioni",
    },
    "Realiste": {
        "EN": "Profile \u2013 Realist / Precision",
        "FR": "Profil \u2013 R\u00e9aliste / Pr\u00e9cision",
        "DE": "Profil \u2013 Realist / Pr\u00e4zision",
        "IT": "Profilo \u2013 Realista / Precisione",
    },
    "Matiere": {
        "EN": "Profile \u2013 Matter / Texture",
        "FR": "Profil \u2013 Mati\u00e8re",
        "DE": "Profil \u2013 Materie",
        "IT": "Profilo \u2013 Materia",
    },
    "Conteur": {
        "EN": "Profile \u2013 Storyteller",
        "FR": "Profil \u2013 Conteur",
        "DE": "Profil \u2013 Erz\u00e4hler",
        "IT": "Profilo \u2013 Narratore",
    },
}


@dataclass(frozen=True)
class Clip:
    filename: str
    file_index: int
    player: str
    orientation: str
    width: int
    height: int
    role: str
    label: str
    meta: str
    language: Optional[str]
    bg: str
    accent: str
    duration: int

    @property
    def stem(self) -> str:
        return Path(self.filename).stem

    @property
    def layout_is_portrait(self) -> bool:
        return self.height > self.width

    @property
    def rotate_cw90(self) -> bool:
        """WIZ1 portrait panels: compose tall, encode 1920x1080 rotated."""
        return self.player == "WIZ1" and self.layout_is_portrait

    @property
    def output_width(self) -> int:
        return self.height if self.rotate_cw90 else self.width

    @property
    def output_height(self) -> int:
        return self.width if self.rotate_cw90 else self.height


def _offset_question_map() -> dict[int, tuple]:
    """Map portrait text offset ? (step, screen, artwork, categories)."""
    out: dict[int, tuple] = {}
    for i, (cats, screen, artwork) in enumerate(DEFAULT_QUESTIONS):
        out[i + 1] = (i + 1, screen, artwork, cats)
    return out


def _parse_aspect(aspect: str) -> Tuple[int, int]:
    w, h = aspect.lower().split("x")
    return int(w), int(h)


def _question_colour(step: int) -> str:
    return QUESTION_COLOURS[(step - 1) % len(QUESTION_COLOURS)]


def _format_categories(cats: Sequence[int]) -> str:
    return " | ".join(f"B{i + 1}={CAT_NAMES[c]}" for i, c in enumerate(cats))


def _role_has_language_variants(role: str) -> bool:
    """Rows with EN/FR/DE/IT filenames (question text, idle intro, profile text)."""
    if role.startswith("Question text") or role.startswith("Idle intro"):
        return True
    return role.startswith("Profile") and not role.startswith("Profile art")


def build_wiz_clips(
    player: str,
    sd_rows: Sequence[Tuple],
    languages: Sequence[str],
    *,
    media_duration: int,
    intro_duration: int,
    profile_duration: int,
) -> List[Clip]:
    clips: List[Clip] = []
    qmap = _offset_question_map()
    accent = WIZ1_ACCENT if player == "WIZ1" else WIZ2_ACCENT

    for role, qref, file_idx, desc, aspect in sd_rows:
        width, height = _parse_aspect(aspect)
        orientation = "portrait" if height > width else "landscape"
        is_text = _role_has_language_variants(role)

        if is_text:
            lang_list = [lg for lg in LANG_CODES if lg in languages]
            for lang_idx, lang in enumerate(LANG_CODES):
                if lang not in languages:
                    continue
                file_index = lang_idx * FILES_PER_LANGUAGE + int(file_idx)
                filename = f"{file_index:03d}.mp4"
                meta_extra = ""
                if int(file_idx) == 0:
                    label = IDLE_TITLE.get(lang, IDLE_TITLE["EN"])
                    duration = intro_duration
                    bg = INTRO_COLOUR
                elif 17 <= int(file_idx) <= 20:
                    cat_key = CAT_NAMES[int(file_idx) - 17]
                    label = PROFILE_TITLE[cat_key].get(lang, cat_key)
                    meta_extra = "Profile result"
                    bg = PROFILE_COLOURS[int(file_idx) - 17]
                    duration = profile_duration
                elif int(file_idx) in qmap:
                    step, screen, art_title, cats = qmap[int(file_idx)]
                    label = f"Q{step}\n{art_title}"
                    meta_extra = f"Question on: {screen}\n{_format_categories(cats)}"
                    bg = _question_colour(step)
                    duration = media_duration
                else:
                    label = f"{role}\n{desc}"
                    bg = "#3a3a3a"
                    duration = media_duration
                meta = (
                    f"file {filename}\nindex {file_index}\nlang {lang}\n"
                    f"{player} | {aspect}\n{role}\n{meta_extra}\n{desc}"
                ).strip()
                clips.append(
                    Clip(
                        filename=filename,
                        file_index=file_index,
                        player=player,
                        orientation=orientation,
                        width=width,
                        height=height,
                        role=role,
                        label=label,
                        meta=meta,
                        language=lang,
                        bg=bg,
                        accent=LANGUAGE_COLOURS[lang_idx % len(LANGUAGE_COLOURS)],
                        duration=duration,
                    )
                )
        else:
            file_index = int(file_idx)
            filename = f"{file_index:03d}.mp4"
            text_offset = file_index
            extra = ""
            duration = media_duration
            if text_offset in qmap:
                step, screen, art_title, cats = qmap[text_offset]
                extra = f"Q{step} | Question on: {screen}\n{_format_categories(cats)}\n"
                bg = _question_colour(step)
                label = f"{role}\n{art_title}"
            elif 17 <= file_index <= 20:
                cat_key = CAT_NAMES[file_index - 17]
                extra = f"Profile art - {cat_key}\n"
                bg = PROFILE_COLOURS[file_index - 17]
                label = f"{role}\n{desc}"
                duration = profile_duration
            elif file_index == 0:
                bg = INTRO_COLOUR
                label = f"{role}\n{desc}"
                duration = intro_duration
            else:
                bg = "#3a3a3a"
                label = f"{role}\n{desc}"
                duration = media_duration
            meta = (
                f"file {filename}\nindex {file_index}\n{player} | {aspect}\n"
                f"{extra}{desc}"
            ).strip()
            clips.append(
                Clip(
                    filename=filename,
                    file_index=file_index,
                    player=player,
                    orientation=orientation,
                    width=width,
                    height=height,
                    role=role,
                    label=label,
                    meta=meta,
                    language=None,
                    bg=bg,
                    accent=accent,
                    duration=duration,
                )
            )
    return clips


def find_font() -> str:
    candidates = [
        Path(r"C:\Windows\Fonts\arial.ttf"),
        Path(r"C:\Windows\Fonts\segoeui.ttf"),
        Path("/Library/Fonts/Arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        Path("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
    ]
    for c in candidates:
        if c.exists():
            return str(c).replace("\\", "/").replace(":", r"\:")
    raise FileNotFoundError(
        "Could not find a TTF font; pass --font path/to/font.ttf"
    )


def escape_drawtext(s: str) -> str:
    return (
        s.replace("\\", r"\\")
        .replace(":", r"\:")
        .replace("'", r"\'")
        .replace("%", r"\%")
    )


class DrawtextFiles:
    """UTF-8 text files for ffmpeg drawtext=textfile= (reliable non-ASCII)."""

    def __init__(self, directory: Path) -> None:
        self._dir = directory
        self._n = 0

    def arg(self, text: str) -> str:
        self._n += 1
        path = self._dir / f"{self._n:02d}.txt"
        path.write_text(text, encoding="utf-8")
        escaped = str(path.resolve()).replace("\\", "/").replace(":", r"\:")
        return f"textfile='{escaped}'"


def parse_indices(s: str) -> List[int]:
    out: List[int] = []
    for part in (p.strip() for p in s.split(",")):
        if not part:
            continue
        if "-" in part:
            start_s, end_s = part.split("-", 1)
            start, end = int(start_s), int(end_s)
            if end < start:
                raise ValueError(f"bad descending range {part!r}")
            out.extend(range(start, end + 1))
        else:
            out.append(int(part))
    return out


def scaled_size(base: int, width: int, height: int, ref_w: int, ref_h: int) -> int:
    return max(12, round(base * min(width / ref_w, height / ref_h)))


def build_filter(clip: Clip, font: str, show_frame: bool, text_files: DrawtextFiles) -> str:
    header_text = (
        f"{clip.player} \u00b7 {clip.orientation.upper()} \u00b7 "
        f"{clip.width}x{clip.height}"
    )
    lang_text = clip.language if clip.language else "-"

    ref_w = LANDSCAPE_WIDTH if clip.orientation == "landscape" else PORTRAIT_WIDTH
    ref_h = LANDSCAPE_HEIGHT if clip.orientation == "landscape" else PORTRAIT_HEIGHT
    w, h = clip.width, clip.height

    title_size = scaled_size(36, w, h, ref_w, ref_h)
    title_border = scaled_size(8, w, h, ref_w, ref_h)
    main_size = scaled_size(52 if clip.orientation == "portrait" else 64, w, h, ref_w, ref_h)
    main_spacing = scaled_size(18, w, h, ref_w, ref_h)
    main_border = scaled_size(16, w, h, ref_w, ref_h)
    meta_size = scaled_size(28 if clip.orientation == "portrait" else 32, w, h, ref_w, ref_h)
    meta_spacing = scaled_size(8, w, h, ref_w, ref_h)
    meta_border = scaled_size(10, w, h, ref_w, ref_h)
    chip_size = scaled_size(30, w, h, ref_w, ref_h)
    chip_border = scaled_size(8, w, h, ref_w, ref_h)

    accent = WIZ1_ACCENT if clip.player == "WIZ1" else WIZ2_ACCENT
    top_y = scaled_size(48, w, h, ref_w, ref_h)
    main_offset = scaled_size(40, w, h, ref_w, ref_h)
    meta_offset = scaled_size(200 if clip.orientation == "portrait" else 160, w, h, ref_w, ref_h)

    parts = []

    if show_frame:
        fw = scaled_size(4, w, h, ref_w, ref_h)
        parts.append(
            f"drawbox=x=0:y=0:w=iw:h=ih:color=white@0.25:t={fw}"
        )

    parts.append(
        f"drawtext=fontfile='{font}':{text_files.arg(header_text)}:"
        f"fontcolor=white:fontsize={title_size}:"
        f"x=(w-text_w)/2:y={top_y}:"
        f"box=1:boxcolor={accent}@0.9:boxborderw={title_border}"
    )
    parts.append(
        f"drawtext=fontfile='{font}':{text_files.arg(clip.role)}:"
        f"fontcolor=white@0.9:fontsize={chip_size}:"
        f"x=(w-text_w)/2:y={top_y + scaled_size(52, w, h, ref_w, ref_h)}:"
        f"box=1:boxcolor=black@0.45:boxborderw={chip_border}"
    )
    if clip.language:
        parts.append(
            f"drawtext=fontfile='{font}':{text_files.arg(lang_text)}:"
            f"fontcolor=white:fontsize={chip_size + 4}:"
            f"x=(w-text_w)/2:y={top_y + scaled_size(96, w, h, ref_w, ref_h)}:"
            f"box=1:boxcolor={clip.accent}@0.85:boxborderw={chip_border}"
        )

    parts.append(
        f"drawtext=fontfile='{font}':{text_files.arg(clip.label)}:"
        f"fontcolor=white:fontsize={main_size}:line_spacing={main_spacing}:"
        f"x=(w-text_w)/2:y=(h-text_h)/2-{main_offset}:"
        f"box=1:boxcolor=black@0.35:boxborderw={main_border}"
    )
    parts.append(
        f"drawtext=fontfile='{font}':{text_files.arg(clip.meta)}:"
        f"fontcolor=white@0.88:fontsize={meta_size}:line_spacing={meta_spacing}:"
        f"x=(w-text_w)/2:y=(h-text_h)/2+{meta_offset}:"
        f"box=1:boxcolor=black@0.5:boxborderw={meta_border}"
    )
    return ",".join(parts)


def probe_duration_seconds(path: Path) -> Optional[float]:
    """Return container duration, or None if missing/unreadable."""
    if not path.is_file():
        return None
    try:
        out = subprocess.check_output(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "csv=p=0",
                str(path),
            ],
            stderr=subprocess.DEVNULL,
            text=True,
        )
        return float(out.strip())
    except (subprocess.CalledProcessError, ValueError, FileNotFoundError):
        return None


def duration_matches(path: Path, expected: int, tolerance: float = 2.0) -> bool:
    actual = probe_duration_seconds(path)
    if actual is None:
        return False
    return abs(actual - expected) <= tolerance


@dataclass(frozen=True)
class RenderOptions:
    font: str
    overwrite: bool
    show_frame: bool
    per_frame_encode: bool
    output_fps: int
    silent_audio: Optional[Path]
    with_audio: bool


def ensure_silent_audio(cache_dir: Path, duration: int) -> Path:
    """Encode one silent AAC per duration; reused via stream copy (much faster)."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"silent_{duration}s.m4a"
    if path.exists() and path.stat().st_size > 0:
        return path
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"anullsrc=r=48000:cl=mono:d={duration}",
            "-c:a",
            "aac",
            "-b:a",
            "32k",
            str(path),
        ],
        check=True,
    )
    return path


def render_clip(
    clip: Clip,
    out_dir: Path,
    options: RenderOptions,
) -> Path:
    out_path = out_dir / clip.filename
    if out_path.exists() and not options.overwrite:
        if duration_matches(out_path, clip.duration):
            return out_path
        print(
            f"  stale {clip.filename}: expected {clip.duration}s, "
            f"re-encoding",
            flush=True,
        )

    with tempfile.TemporaryDirectory(prefix="va_drawtext_") as tmp:
        text_files = DrawtextFiles(Path(tmp))
        vfilter = build_filter(clip, options.font, options.show_frame, text_files)
        if clip.rotate_cw90:
            vfilter = f"{vfilter},transpose=1"

        if options.per_frame_encode:
            _render_clip_per_frame(clip, out_path, vfilter, options)
        else:
            _render_clip_static_loop(
                clip, out_path, vfilter, Path(tmp), options
            )
    return out_path


def _render_clip_static_loop(
    clip: Clip,
    out_path: Path,
    vfilter: str,
    tmp: Path,
    options: RenderOptions,
) -> None:
    """One composed frame, low-fps loop, optional cached audio copy."""
    frame_png = tmp / "frame.png"
    out_fps = options.output_fps
    frame_dur = 1.0 / out_fps
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c={clip.bg}:s={clip.width}x{clip.height}:d={frame_dur}:r={out_fps}",
            "-vf",
            vfilter,
            "-frames:v",
            "1",
            str(frame_png),
        ],
        check=True,
    )

    cmd: List[str] = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y" if options.overwrite else "-n",
        "-loop",
        "1",
        "-framerate",
        str(out_fps),
        "-i",
        str(frame_png),
    ]
    if options.with_audio and options.silent_audio is not None:
        cmd.extend(["-i", str(options.silent_audio)])
    cmd.extend(
        [
            "-t",
            str(clip.duration),
            "-map",
            "0:v:0",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-preset",
            "ultrafast",
            "-tune",
            "stillimage",
            "-crf",
            "23",
            "-r",
            str(out_fps),
            "-frames:v",
            str(max(1, clip.duration * out_fps)),
        ]
    )
    if options.with_audio and options.silent_audio is not None:
        cmd.extend(["-map", "1:a:0", "-c:a", "copy"])
    else:
        cmd.append("-an")
    part_path = out_path.with_name(f"{out_path.stem}.part{out_path.suffix}")
    cmd.extend(["-movflags", "+faststart", str(part_path)])
    subprocess.run(cmd, check=True)
    part_path.replace(out_path)


def clip_output_valid(path: Path, expected_duration: int) -> bool:
    if not duration_matches(path, expected_duration):
        return False
    try:
        subprocess.run(
            ["ffmpeg", "-v", "error", "-i", str(path), "-f", "null", "-"],
            capture_output=True,
            check=True,
            timeout=120,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return False
    return True


def clips_failing_verify(
    clips: Sequence[Clip],
    portrait_dir: Path,
    paysage_dir: Path,
) -> List[Clip]:
    """Clips whose output is missing, wrong duration, or fails decode."""
    bad: List[Clip] = []
    for clip in clips:
        out_dir = portrait_dir if clip.player == "WIZ1" else paysage_dir
        path = out_dir / clip.filename
        if not clip_output_valid(path, clip.duration):
            bad.append(clip)
    return bad


def _render_worker(task: Tuple[Clip, Path, RenderOptions]) -> str:
    clip, out_dir, options = task
    render_clip(clip, out_dir, options)
    return clip.filename


def _render_clip_per_frame(
    clip: Clip,
    out_path: Path,
    vfilter: str,
    options: RenderOptions,
) -> None:
    """Encode every frame at 30 fps (slow; use only with --per-frame)."""
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y" if options.overwrite else "-n",
            "-f",
            "lavfi",
            "-i",
            f"color=c={clip.bg}:s={clip.width}x{clip.height}:d={clip.duration}:r={FPS}",
            "-f",
            "lavfi",
            "-i",
            f"anullsrc=r=48000:cl=stereo:d={clip.duration}",
            "-vf",
            vfilter,
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-preset",
            "veryfast",
            "-tune",
            "stillimage",
            "-r",
            str(FPS),
            "-c:a",
            "aac",
            "-b:a",
            "96k",
            "-movflags",
            "+faststart",
            str(out_path),
        ],
        check=True,
    )


def write_manifest(clips: Sequence[Clip], path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "filename", "file_index", "player", "orientation",
            "language", "role", "label", "width", "height", "duration_s",
        ])
        for c in clips:
            w.writerow([
                c.filename,
                c.file_index,
                c.player,
                c.orientation,
                c.language or "",
                c.role,
                c.label.replace("\n", " / "),
                c.output_width,
                c.output_height,
                c.duration,
            ])


def main(argv: Iterable[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--out",
        type=Path,
        default=Path("videos/test"),
        help="Output root (creates sd_wiz1/ and sd_wiz2/ subdirs).",
    )
    p.add_argument(
        "--card",
        choices=("both", "wiz1", "wiz2", "portrait", "paysage"),
        default="both",
        help="Which SD card (wiz1/wiz2 or legacy portrait/paysage aliases).",
    )
    p.add_argument("--font", type=str, default=None, help="TTF font path.")
    p.add_argument(
        "--no-overwrite",
        action="store_true",
        help="Skip files that already exist.",
    )
    p.add_argument(
        "--languages",
        type=str,
        default=",".join(LANG_CODES),
        help=f"Languages for portrait clips (subset of {','.join(LANG_CODES)}).",
    )
    p.add_argument(
        "--media-duration",
        type=int,
        default=MEDIA_DURATION,
        help=f"Duration for question / artwork clips (default: {MEDIA_DURATION}s).",
    )
    p.add_argument(
        "--intro-duration",
        type=int,
        default=INTRO_DURATION,
        help=f"Duration for idle text + idle artwork (default: {INTRO_DURATION}s).",
    )
    p.add_argument(
        "--profile-duration",
        type=int,
        default=PROFILE_DURATION,
        help=f"Duration for personality clips (default: {PROFILE_DURATION}s).",
    )
    p.add_argument(
        "--only",
        type=str,
        default=None,
        help="Comma-separated file indices/ranges, e.g. 0,32,10-22.",
    )
    p.add_argument(
        "--safe-frame",
        action="store_true",
        help="Draw a thin border to visualize the full frame.",
    )
    p.add_argument(
        "--per-frame",
        action="store_true",
        help="Encode every frame at 30 fps (slow). Default: 1 still + low-fps loop.",
    )
    p.add_argument(
        "--output-fps",
        type=int,
        default=PLACEHOLDER_OUTPUT_FPS,
        help=(
            f"Output fps for placeholder loop (default {PLACEHOLDER_OUTPUT_FPS}). "
            "Use 30 only if the player rejects low-fps files."
        ),
    )
    p.add_argument(
        "--no-audio",
        action="store_true",
        help="No audio track (fastest). MedeaWiz usually wants AAC; default keeps audio.",
    )
    p.add_argument(
        "-j",
        "--jobs",
        type=int,
        default=max(1, (os.cpu_count() or 4) - 1),
        help="Parallel ffmpeg jobs (default: CPU count - 1).",
    )
    args = p.parse_args(list(argv) if argv is not None else None)

    if shutil.which("ffmpeg") is None:
        print("error: ffmpeg not found on PATH", file=sys.stderr)
        return 2

    font = args.font
    if font is None:
        font = find_font()
    else:
        font = font.replace("\\", "/").replace(":", r"\:")

    wanted = {c.strip().upper() for c in args.languages.split(",") if c.strip()}
    unknown = wanted - set(LANG_CODES)
    if unknown:
        print(f"error: unknown language(s): {sorted(unknown)}", file=sys.stderr)
        return 2

    clips: List[Clip] = []
    if args.card in ("both", "portrait", "wiz1"):
        clips.extend(
            build_wiz_clips(
                "WIZ1",
                WIZ1_SD_ROWS,
                wanted,
                media_duration=args.media_duration,
                intro_duration=args.intro_duration,
                profile_duration=args.profile_duration,
            )
        )
    if args.card in ("both", "paysage", "wiz2"):
        clips.extend(
            build_wiz_clips(
                "WIZ2",
                WIZ2_SD_ROWS,
                wanted,
                media_duration=args.media_duration,
                intro_duration=args.intro_duration,
                profile_duration=args.profile_duration,
            )
        )

    if args.only:
        try:
            wanted_indices = set(parse_indices(args.only))
        except ValueError as e:
            print(f"error: bad --only value: {e}", file=sys.stderr)
            return 2
        clips = [c for c in clips if c.file_index in wanted_indices]

    portrait_dir = args.out / "sd_wiz1"
    paysage_dir = args.out / "sd_wiz2"
    portrait_dir.mkdir(parents=True, exist_ok=True)
    paysage_dir.mkdir(parents=True, exist_ok=True)

    portrait_clips = [c for c in clips if c.player == "WIZ1"]
    paysage_clips = [c for c in clips if c.player == "WIZ2"]

    if args.output_fps < 1:
        print("error: --output-fps must be >= 1", file=sys.stderr)
        return 2

    audio_cache = args.out / ".cache"
    silent_by_duration: dict[int, Path] = {}
    if not args.no_audio:
        for duration in {c.duration for c in clips}:
            silent_by_duration[duration] = ensure_silent_audio(audio_cache, duration)

    mode = "30 fps full encode" if args.per_frame else (
        f"{args.output_fps} fps still loop"
    )
    audio_mode = "none" if args.no_audio else "cached AAC copy"
    print(
        f"Rendering {len(clips)} clips into {args.out.resolve()} "
        f"({len(portrait_clips)} wiz1, {len(paysage_clips)} wiz2) ? {mode}, {audio_mode}, "
        f"-j {args.jobs}"
    )

    overwrite = not args.no_overwrite
    options_for = lambda clip: RenderOptions(
        font=font,
        overwrite=overwrite,
        show_frame=args.safe_frame,
        per_frame_encode=args.per_frame,
        output_fps=args.output_fps if not args.per_frame else FPS,
        silent_audio=silent_by_duration.get(clip.duration),
        with_audio=not args.no_audio,
    )
    tasks = [
        (
            clip,
            portrait_dir if clip.player == "WIZ1" else paysage_dir,
            options_for(clip),
        )
        for clip in clips
    ]

    if args.jobs <= 1:
        for i, (clip, out_dir, opts) in enumerate(tasks, 1):
            lang_part = f"  {clip.language}" if clip.language else ""
            print(
                f"  [{i:3d}/{len(clips)}] {clip.filename}  "
                f"{clip.player} {clip.output_width}x{clip.output_height}{lang_part}  "
                f"{clip.role} - {clip.label.replace(chr(10), ' / ')}"
            )
            render_clip(clip, out_dir, opts)
    else:
        done = 0
        with ProcessPoolExecutor(max_workers=args.jobs) as pool:
            futures = {
                pool.submit(_render_worker, task): task[0] for task in tasks
            }
            for fut in as_completed(futures):
                clip = futures[fut]
                done += 1
                print(f"  [{done:3d}/{len(clips)}] {clip.filename}  {clip.role}")
                fut.result()

    failed = clips_failing_verify(clips, portrait_dir, paysage_dir)
    if failed:
        print(
            f"Verifying output: {len(failed)} clip(s) wrong duration — re-rendering serially",
            flush=True,
        )
        for clip in failed:
            out_dir = portrait_dir if clip.player == "WIZ1" else paysage_dir
            opts = RenderOptions(
                font=font,
                overwrite=True,
                show_frame=args.safe_frame,
                per_frame_encode=args.per_frame,
                output_fps=args.output_fps if not args.per_frame else FPS,
                silent_audio=silent_by_duration.get(clip.duration)
                if not args.no_audio
                else None,
                with_audio=not args.no_audio,
            )
            print(f"  repair {clip.filename} (want {clip.duration}s)", flush=True)
            render_clip(clip, out_dir, opts)
        still_bad = clips_failing_verify(clips, portrait_dir, paysage_dir)
        if still_bad:
            names = ", ".join(c.filename for c in still_bad)
            print(f"error: still invalid after repair: {names}", file=sys.stderr)
            return 1

    if portrait_clips:
        write_manifest(portrait_clips, portrait_dir / "manifest.csv")
    if paysage_clips:
        write_manifest(paysage_clips, paysage_dir / "manifest.csv")

    print("Done.")
    print(f"  Portrait SD -> {portrait_dir.resolve()}/")
    print(f"  Paysage SD  -> {paysage_dir.resolve()}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
