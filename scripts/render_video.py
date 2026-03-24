#!/usr/bin/env python3
"""Render a slideshow-style MP4 from images and an audio track."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from glob import glob
from pathlib import Path
from typing import Sequence


def resolve_binary(name: str) -> str:
    env_name = f"{name.upper()}_BIN"
    env_value = os.getenv(env_name, "").strip()
    if env_value and Path(env_value).exists():
        return env_value

    binary = shutil.which(name)
    if binary:
        return binary

    if os.name == "nt":
        package_root = Path(os.getenv("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages"
        pattern = str(package_root / "Gyan.FFmpeg*" / "ffmpeg-*" / "bin" / f"{name}.exe")
        matches = glob(pattern)
        if matches:
            return matches[0]

    raise RuntimeError(f"{name} is required but not available in PATH")


def probe_audio_duration(audio_path: Path) -> float:
    ffprobe_bin = resolve_binary("ffprobe")
    result = subprocess.run(
        [
            ffprobe_bin,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(audio_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return float(result.stdout.strip())


def write_concat_file(image_paths: Sequence[Path], duration_per_image: float, concat_path: Path) -> None:
    lines: list[str] = []
    for image_path in image_paths:
        lines.append(f"file '{image_path.resolve().as_posix()}'")
        lines.append(f"duration {duration_per_image:.6f}")
    lines.append(f"file '{image_paths[-1].resolve().as_posix()}'")
    concat_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def format_timestamp(seconds: float) -> str:
    milliseconds = int(round(seconds * 1000))
    hours = milliseconds // 3_600_000
    milliseconds %= 3_600_000
    minutes = milliseconds // 60_000
    milliseconds %= 60_000
    secs = milliseconds // 1000
    milliseconds %= 1000
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"


def write_srt(captions: Sequence[str], total_duration: float, srt_path: Path) -> None:
    if not captions:
        return
    chunk = total_duration / len(captions)
    blocks: list[str] = []
    start = 0.0
    for index, caption in enumerate(captions, start=1):
        end = total_duration if index == len(captions) else start + chunk
        blocks.append(
            "\n".join(
                [
                    str(index),
                    f"{format_timestamp(start)} --> {format_timestamp(end)}",
                    caption.strip() or " ",
                ]
            )
        )
        start = end
    srt_path.write_text("\n\n".join(blocks) + "\n", encoding="utf-8")


def escape_subtitles_path(path: Path) -> str:
    value = path.resolve().as_posix()
    return value.replace("\\", "/").replace(":", "\\:").replace("'", "\\'")


def render_package(
    image_paths: Sequence[Path],
    audio_path: Path,
    video_path: Path,
    srt_path: Path | None = None,
    captions: Sequence[str] | None = None,
    burn_subtitles: bool = False,
    fps: int = 24,
    width: int = 1280,
    height: int = 720,
) -> dict:
    ffmpeg_bin = resolve_binary("ffmpeg")
    resolve_binary("ffprobe")

    if not image_paths:
        raise ValueError("At least one image is required to render a video")
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    video_path.parent.mkdir(parents=True, exist_ok=True)
    if srt_path is not None:
        srt_path.parent.mkdir(parents=True, exist_ok=True)

    total_duration = probe_audio_duration(audio_path)
    duration_per_image = total_duration / len(image_paths)

    if srt_path is not None and captions:
        write_srt(captions, total_duration, srt_path)

    concat_path = video_path.parent / "_images.concat.txt"
    write_concat_file(image_paths, duration_per_image, concat_path)
    video_filter = (
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2"
    )
    if burn_subtitles and srt_path is not None and srt_path.exists():
        subtitle_filter = (
            f"subtitles='{escape_subtitles_path(srt_path)}':"
            "force_style='FontName=Microsoft YaHei,FontSize=22,"
            "PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
            "BorderStyle=1,Outline=2,Shadow=0,MarginV=28,Alignment=2'"
        )
        video_filter = f"{video_filter},{subtitle_filter}"

    try:
        subprocess.run(
            [
                ffmpeg_bin,
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_path),
                "-i",
                str(audio_path),
                "-vf",
                video_filter,
                "-r",
                str(fps),
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-shortest",
                str(video_path),
            ],
            check=True,
        )
    finally:
        if concat_path.exists():
            concat_path.unlink()

    return {
        "video_path": str(video_path.resolve()),
        "audio_duration_seconds": round(total_duration, 3),
        "image_count": len(image_paths),
        "subtitle_path": str(srt_path.resolve()) if srt_path and srt_path.exists() else None,
    }


def load_captions(path: Path | None) -> list[str]:
    if path is None:
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [str(item).strip() for item in payload if str(item).strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Render slideshow video from images and audio.")
    parser.add_argument("--images-dir", required=True, help="Directory that contains scene_*.png files.")
    parser.add_argument("--audio", required=True, help="Path to the audio file.")
    parser.add_argument("--output", required=True, help="Path to the MP4 output.")
    parser.add_argument("--captions-json", help="Optional JSON array file for scene captions.")
    parser.add_argument("--srt-output", help="Optional SRT output path.")
    parser.add_argument("--no-burn-subtitles", action="store_true", help="Keep SRT sidecar only and do not burn subtitles into the MP4.")
    parser.add_argument("--fps", type=int, default=24)
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    args = parser.parse_args()

    image_dir = Path(args.images_dir)
    image_paths = sorted(image_dir.glob("scene_*.png"))
    if not image_paths:
        image_paths = sorted(image_dir.glob("scene_*.jpg"))

    result = render_package(
        image_paths=image_paths,
        audio_path=Path(args.audio),
        video_path=Path(args.output),
        srt_path=Path(args.srt_output) if args.srt_output else None,
        captions=load_captions(Path(args.captions_json)) if args.captions_json else None,
        burn_subtitles=not args.no_burn_subtitles,
        fps=args.fps,
        width=args.width,
        height=args.height,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
