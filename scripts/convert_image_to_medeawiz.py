#!/usr/bin/env python3
"""Convert a still image to a MedeaWiz-ready MP4 (cross-platform; Windows, Linux, macOS)."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent
_DEFAULT_WORKBOOK = _REPO_ROOT / "questions" / "MediaMap_workbook.xlsx"
_DEFAULT_OUT_DIR = _REPO_ROOT / "videos" / "out"

# Local import (same directory)
from medeawiz_workbook import ClipTarget, resolve_clip  # noqa: E402

USAGE_EPILOG = """
Examples:
  python scripts/convert_image_to_medeawiz.py photo.png --q 3 --part text --lang FR
  python scripts/convert_image_to_medeawiz.py art.png --q 3 --part image
  python scripts/convert_image_to_medeawiz.py intro.png --idle --part text --lang EN
  python scripts/convert_image_to_medeawiz.py portrait intro_en.png 000.mp4 --type idle
"""


def _duration_for_type(clip_type: str, override: int | None) -> int:
    if override is not None:
        return override
    return {"idle": 600, "question": 70, "profile": 60}[clip_type]


def _video_filter(mode: str, fit: str) -> str:
    fit_expr = (
        "force_original_aspect_ratio=decrease"
        if fit == "contain"
        else "force_original_aspect_ratio=increase"
    )
    if mode == "portrait":
        if fit == "contain":
            return f"scale=1080:1920:{fit_expr},pad=1080:1920:(ow-iw)/2:(oh-ih)/2,transpose=1"
        return f"scale=1080:1920:{fit_expr},crop=1080:1920,transpose=1"
    if fit == "contain":
        return f"scale=1920:1080:{fit_expr},pad=1920:1080:(ow-iw)/2:(oh-ih)/2"
    return f"scale=1920:1080:{fit_expr},crop=1920:1080"


def _require_tool(name: str) -> str:
    path = shutil.which(name)
    if not path:
        print(f"error: {name} not found on PATH", file=sys.stderr)
        sys.exit(1)
    return path


def _print_workbook_slot(
    target: ClipTarget,
    *,
    part: str,
    profile: str | None,
    idle: bool,
) -> None:
    print("Workbook slot:")
    if target.step is not None:
        print(f"  step      Q{target.step}")
    elif idle:
        print("  step      idle")
    else:
        print(f"  step      profile {profile}")
    lang_suffix = f" / {target.language}" if target.language else ""
    print(f"  part      {part}{lang_suffix}")
    print(f"  player    {target.player} -> {target.sd_folder}/{target.filename}")
    if target.artwork:
        print(f"  artwork   {target.artwork}")


def _encode(
    *,
    input_path: Path,
    output_path: Path,
    mode: str,
    clip_type: str,
    duration: int,
    fit: str,
    fps: int,
    with_audio: bool,
) -> None:
    ffmpeg = _require_tool("ffmpeg")
    ffprobe = _require_tool("ffprobe")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_out = Path(f"{output_path}.part.mp4")
    if tmp_out.exists():
        tmp_out.unlink()

    mode_desc = (
        "1080x1920, rotate 90 CW -> 1920x1080"
        if mode == "portrait"
        else "1920x1080"
    )
    print(f"Converting: {input_path}")
    print(f"  mode      {mode} ({mode_desc})")
    print(f"  type      {clip_type} ({duration}s)")
    print(f"  fit       {fit} @ {fps} fps")
    print(f"  output    {output_path}")

    vf = _video_filter(mode, fit)
    cmd: list[str] = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-loop",
        "1",
        "-framerate",
        str(fps),
        "-i",
        str(input_path),
    ]
    if with_audio:
        cmd.extend(["-f", "lavfi", "-i", f"anullsrc=r=48000:cl=mono:d={duration}"])
    cmd.extend(
        [
            "-vf",
            vf,
            "-t",
            str(duration),
            "-map",
            "0:v:0",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-preset",
            "medium",
            "-tune",
            "stillimage",
            "-crf",
            "23",
            "-r",
            str(fps),
            "-frames:v",
            str(duration * fps),
        ]
    )
    if with_audio:
        cmd.extend(["-map", "1:a:0", "-c:a", "aac", "-b:a", "32k"])
    else:
        cmd.append("-an")
    cmd.extend(["-movflags", "+faststart", str(tmp_out)])

    subprocess.run(cmd, check=True)
    tmp_out.replace(output_path)

    actual = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "csv=p=0",
            str(output_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    vinfo = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=codec_name,width,height,pix_fmt",
            "-of",
            "csv=p=0",
            str(output_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    ainfo = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-select_streams",
            "a:0",
            "-show_entries",
            "stream=codec_name",
            "-of",
            "csv=p=0",
            str(output_path),
        ],
        capture_output=True,
        text=True,
    ).stdout.strip()

    subprocess.run(
        [ffmpeg, "-v", "error", "-i", str(output_path), "-f", "null", "-"],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    print(f"Done: {output_path}")
    print(f"  duration  {actual}s (wanted {duration}s)")
    print(f"  video     {vinfo}")
    if with_audio and ainfo:
        print(f"  audio     {ainfo}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=USAGE_EPILOG,
    )
    parser.add_argument(
        "mode_or_input",
        help="Workbook mode: INPUT image. Manual mode: portrait|landscape",
    )
    parser.add_argument(
        "input_or_output",
        nargs="?",
        help="Manual mode: INPUT image",
    )
    parser.add_argument(
        "manual_output",
        nargs="?",
        type=Path,
        help="Manual mode: target .mp4",
    )

    slot = parser.add_mutually_exclusive_group()
    slot.add_argument("--q", "--question", type=int, dest="question", metavar="STEP")
    slot.add_argument("--idle", action="store_true")
    slot.add_argument(
        "--profile", metavar="NAME", help="emotions, realiste, matiere, conteur"
    )

    parser.add_argument("--part", choices=("text", "image"), help="Text vs artwork")
    parser.add_argument("--lang", "--language", dest="language")
    parser.add_argument("--workbook", type=Path, default=_DEFAULT_WORKBOOK)
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=_DEFAULT_OUT_DIR,
        help=f"Workbook output root (default: {_DEFAULT_OUT_DIR.relative_to(_REPO_ROOT)})",
    )
    parser.add_argument("--type", choices=("idle", "question", "profile"))
    parser.add_argument("--duration", type=int)
    parser.add_argument("--fit", choices=("contain", "cover"), default="contain")
    parser.add_argument("--fps", type=int, default=1)
    parser.add_argument("--no-audio", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def _resolve_paths(
    args: argparse.Namespace,
) -> tuple[Path | None, Path | None, str | None, str | None]:
    """Return input_path, output_path, mode, error_message."""
    workbook_mode = (
        args.question is not None or args.idle or args.profile is not None
    )
    if workbook_mode:
        if args.input_or_output is not None:
            return (
                None,
                None,
                None,
                "unexpected positional argument in workbook mode (output comes from --out-dir)",
            )
        return Path(args.mode_or_input), None, None, None

    if args.mode_or_input in ("portrait", "landscape"):
        mode = args.mode_or_input
        if not args.input_or_output or args.manual_output is None:
            return None, None, None, "manual mode requires MODE INPUT OUTPUT"
        return Path(args.input_or_output), args.manual_output, mode, None

    return (
        None,
        None,
        None,
        f"MODE must be portrait or landscape (got: {args.mode_or_input})",
    )


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    input_path, output_path, mode, path_err = _resolve_paths(args)
    if path_err:
        parser.print_help()
        print(f"\nerror: {path_err}", file=sys.stderr)
        return 1

    assert input_path is not None
    if not input_path.is_file():
        print(f"error: input not found: {input_path}", file=sys.stderr)
        return 1

    workbook_mode = args.question is not None or args.idle or args.profile is not None
    clip_type = args.type or "question"
    profile_name = args.profile

    if workbook_mode:
        if not args.part:
            print("error: workbook mode requires --part text or --part image", file=sys.stderr)
            return 1
        if not args.workbook.is_file():
            print(f"error: workbook not found: {args.workbook}", file=sys.stderr)
            return 1

        try:
            target = resolve_clip(
                workbook=args.workbook,
                question=args.question,
                idle=args.idle,
                profile=args.profile,
                part=args.part,
                language=args.language,
            )
        except (ValueError, OSError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

        mode = target.encode_mode
        clip_type = target.clip_type
        output_path = args.out_dir / target.sd_folder / target.filename
        _print_workbook_slot(
            target,
            part=args.part,
            profile=profile_name,
            idle=args.idle,
        )

        if args.dry_run:
            print(f"Dry run: would encode {mode} -> {output_path} (type {clip_type})")
            return 0
    else:
        assert mode is not None and output_path is not None

    if args.dry_run and not workbook_mode:
        print(f"Dry run: would encode {mode} -> {output_path} (type {clip_type})")
        return 0

    try:
        duration = _duration_for_type(clip_type, args.duration)
    except KeyError:
        print(f"error: unknown clip type {clip_type!r}", file=sys.stderr)
        return 1

    try:
        _encode(
            input_path=input_path,
            output_path=output_path,
            mode=mode,
            clip_type=clip_type,
            duration=duration,
            fit=args.fit,
            fps=args.fps,
            with_audio=not args.no_audio,
        )
    except subprocess.CalledProcessError:
        print("error: ffmpeg encode failed", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
