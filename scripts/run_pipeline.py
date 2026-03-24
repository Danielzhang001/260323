#!/usr/bin/env python3
"""Build a kids-song media package from a structured plan JSON."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

import requests

from render_video import render_package, resolve_binary


def require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def load_plan(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError("Plan JSON must be an object")
    return payload


def nonempty_string(data: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    raise ValueError(f"Missing required string field. Tried keys: {', '.join(keys)}")


def lyric_lines(lyrics: str) -> list[str]:
    lines: list[str] = []
    for raw_line in lyrics.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            continue
        lines.append(line)
    return lines


def chunk_text(items: list[str], chunk_count: int) -> list[str]:
    if chunk_count <= 0:
        return []
    if not items:
        return [""] * chunk_count

    chunks: list[list[str]] = [[] for _ in range(chunk_count)]
    for index, item in enumerate(items):
        chunks[min(index * chunk_count // len(items), chunk_count - 1)].append(item)
    return [" ".join(chunk).strip() for chunk in chunks]


def normalize_plan(plan: dict[str, Any]) -> dict[str, Any]:
    title = nonempty_string(plan, "song_title", "title")
    lyrics = nonempty_string(plan, "lyrics")
    music_prompt = nonempty_string(plan, "music_prompt", "style_prompt")
    topic = nonempty_string(plan, "topic", "theme", "song_title", "title")
    scenes = plan.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        raise ValueError("Plan must contain a non-empty scenes array")

    clean_scenes: list[dict[str, Any]] = []
    lyric_chunks = chunk_text(lyric_lines(lyrics), len(scenes))
    for index, scene in enumerate(scenes, start=1):
        if not isinstance(scene, dict):
            raise ValueError("Each scene must be an object")
        image_prompt = nonempty_string(scene, "image_prompt", "prompt")
        caption = str(scene.get("caption", "")).strip()
        excerpt = str(scene.get("lyric_excerpt", "")).strip() or lyric_chunks[index - 1]
        if not caption:
            caption = excerpt or f"Scene {index}"
        clean_scene = {
            "index": index,
            "caption": caption,
            "lyric_excerpt": excerpt,
            "image_prompt": image_prompt,
        }
        clean_scenes.append(clean_scene)

    return {
        "topic": topic,
        "source_text": str(plan.get("source_text", "")).strip(),
        "song_title": title,
        "target_age": str(plan.get("target_age", "")).strip(),
        "music_prompt": music_prompt,
        "lyrics": lyrics,
        "scenes": clean_scenes,
    }


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def post_json(url: str, headers: dict[str, str], payload: dict[str, Any], timeout: int, attempts: int = 3) -> dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=timeout)
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            last_error = exc
            if attempt == attempts:
                break
            time.sleep(min(5 * attempt, 12))
    raise RuntimeError(f"Request failed after {attempts} attempts: {url}") from last_error


def download_file(url: str, output_path: Path) -> None:
    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            with requests.get(url, timeout=300, stream=True) as response:
                response.raise_for_status()
                output_path.parent.mkdir(parents=True, exist_ok=True)
                with output_path.open("wb") as handle:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            handle.write(chunk)
            return
        except Exception as exc:
            last_error = exc
            if attempt == 3:
                break
            time.sleep(min(5 * attempt, 12))
    raise RuntimeError(f"Failed to download file: {url}") from last_error


def compact_lyrics(lyrics: str) -> str:
    lines: list[str] = []
    for raw_line in lyrics.splitlines():
        line = raw_line.strip()
        if line:
            lines.append(line)
    return "\n".join(lines)


def split_lyrics_for_suno(lyrics: str, max_chars: int) -> list[str]:
    clean_lyrics = compact_lyrics(lyrics)
    if len(clean_lyrics) <= max_chars:
        return [clean_lyrics]

    lines = [line.strip() for line in clean_lyrics.splitlines() if line.strip()]
    if len(lines) < 2:
        raise RuntimeError("Lyrics are too long for Suno and cannot be split safely")

    total = 0
    split_index = 0
    target = len(clean_lyrics) // 2
    for index, line in enumerate(lines, start=1):
        total += len(line) + 1
        split_index = index
        if total >= target:
            break

    first = "\n".join(lines[:split_index]).strip()
    second = "\n".join(lines[split_index:]).strip()
    if not first or not second:
        raise RuntimeError("Lyrics exceed the Suno limit and could not be split into two parts")
    if len(first) > max_chars or len(second) > max_chars:
        raise RuntimeError("Lyrics still exceed the Suno limit after splitting into two parts")
    return [first, second]


def poll_302_suno_result(task_id: str, api_key: str, timeout_seconds: int) -> dict[str, Any]:
    url = f"https://api.302.ai/suno/fetch/{task_id}"
    headers = {"Authorization": f"Bearer {api_key}"}
    deadline = time.time() + timeout_seconds
    last_payload: dict[str, Any] | None = None

    while time.time() < deadline:
        response = requests.get(url, headers=headers, timeout=60)
        response.raise_for_status()
        payload = response.json()
        last_payload = payload
        data = payload.get("data") or {}
        entries = data.get("data") or []
        ready_entries = [item for item in entries if isinstance(item, dict) and item.get("audio_url")]
        if ready_entries:
            return ready_entries[0]
        status = str(payload.get("status") or data.get("status") or "").upper()
        if status in {"FAILED", "ERROR"}:
            raise RuntimeError(f"Suno task failed: {payload}")
        time.sleep(8)

    raise RuntimeError(f"Suno task timed out: {task_id}; last payload: {last_payload}")


def concat_audio_files(audio_parts: list[Path], output_path: Path) -> None:
    if len(audio_parts) == 1:
        shutil.copyfile(audio_parts[0], output_path)
        return

    ffmpeg_bin = resolve_binary("ffmpeg")
    concat_file = output_path.parent / "_audio.concat.txt"
    concat_lines = [f"file '{part.resolve().as_posix()}'" for part in audio_parts]
    concat_file.write_text("\n".join(concat_lines) + "\n", encoding="utf-8")
    try:
        import subprocess

        subprocess.run(
            [
                ffmpeg_bin,
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_file),
                "-c:a",
                "libmp3lame",
                "-b:a",
                "128k",
                str(output_path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    finally:
        if concat_file.exists():
            concat_file.unlink()


def trim_audio_silence(input_path: Path, output_path: Path) -> Path:
    ffmpeg_bin = resolve_binary("ffmpeg")
    try:
        subprocess.run(
            [
                ffmpeg_bin,
                "-y",
                "-i",
                str(input_path),
                "-af",
                (
                    "silenceremove=start_periods=1:start_silence=0.25:start_threshold=-35dB:"
                    "stop_periods=-1:stop_silence=0.8:stop_threshold=-35dB"
                ),
                "-c:a",
                "libmp3lame",
                "-b:a",
                "192k",
                str(output_path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        return output_path
    except Exception:
        return input_path


def call_302_music(plan: dict[str, Any], output_path: Path) -> dict[str, Any]:
    api_key = require_env("THREEZERO2_API_KEY")
    model = os.getenv("THREEZERO2_MUSIC_MODEL", "music-2.5").strip() or "music-2.5"
    timeout = int(os.getenv("THREEZERO2_MUSIC_TIMEOUT_SECONDS", "900"))

    if model.startswith("chirp-"):
        lyric_parts = split_lyrics_for_suno(plan["lyrics"], int(os.getenv("THREEZERO2_SUNO_MAX_CHARS", "2600")))
        part_paths: list[Path] = []
        task_ids: list[str] = []
        for index, lyric_part in enumerate(lyric_parts, start=1):
            payload: dict[str, Any] = {
                "prompt": lyric_part,
                "tags": os.getenv(
                    "THREEZERO2_SUNO_TAGS",
                    "female vocal, nursery rhyme, happy, no intro, no long outro, start singing immediately",
                ).strip()
                or "female vocal, nursery rhyme, happy, no intro, no long outro, start singing immediately",
                "mv": model,
            }
            submit_response = post_json(
                "https://api.302.ai/suno/submit/music",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                timeout=180,
                payload=payload,
            )
            task_id = submit_response.get("data")
            if not isinstance(task_id, str) or not task_id:
                raise RuntimeError(f"302 Suno submit response did not contain task id: {submit_response}")
            task_ids.append(task_id)
            result = poll_302_suno_result(task_id, api_key=api_key, timeout_seconds=timeout)
            part_path = output_path.parent / f"song_part_{index:02d}.mp3"
            audio_url = result.get("audio_url")
            if not isinstance(audio_url, str) or not audio_url:
                raise RuntimeError(f"302 Suno result did not contain audio URL: {result}")
            download_file(audio_url, part_path)
            part_paths.append(part_path)

        merged_path = output_path.parent / "song_raw.mp3"
        concat_audio_files(part_paths, merged_path)
        final_path = trim_audio_silence(merged_path, output_path)
        return {
            "provider": "302.ai",
            "model": model,
            "path": str(final_path.resolve()),
            "task_ids": task_ids,
            "segment_count": len(part_paths),
            "size_bytes": final_path.stat().st_size,
        }

    payload: dict[str, Any] = {
        "model": model,
        "prompt": plan["music_prompt"],
        "lyrics": plan["lyrics"],
        "audio_setting": {
            "sample_rate": 44100,
            "bitrate": 128000,
            "format": "mp3",
        },
        "output_format": "url",
    }

    data = post_json(
        "https://api.302.ai/minimaxi/v1/music_generation",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        timeout=timeout,
        payload=payload,
    )
    music_data = data.get("data") or {}
    audio_url = music_data.get("audio_url") or music_data.get("audio")
    if not isinstance(audio_url, str) or not audio_url:
        raise RuntimeError(f"302 music response did not contain audio URL: {data}")

    download_file(audio_url, output_path)
    return {
        "provider": "302.ai",
        "model": model,
        "path": str(output_path.resolve()),
        "audio_url": audio_url,
        "status": music_data.get("status"),
        "size_bytes": output_path.stat().st_size,
    }


def call_302_image(scene: dict[str, Any], output_path: Path) -> dict[str, Any]:
    api_key = require_env("THREEZERO2_API_KEY")
    model = os.getenv("THREEZERO2_IMAGE_MODEL", "gpt-image-1-mini").strip() or "gpt-image-1-mini"
    image_size = os.getenv("THREEZERO2_IMAGE_SIZE", "1024x1024").strip() or "1024x1024"
    aspect_ratio = os.getenv("THREEZERO2_IMAGE_ASPECT_RATIO", "16:9").strip() or "16:9"
    payload: dict[str, Any] = {
        "model": model,
        "prompt": scene["image_prompt"],
        "n": 1,
        "response_format": "url",
        "size": image_size,
        "aspect_ratio": aspect_ratio,
    }

    data = post_json(
        "https://api.302.ai/302/images/generations",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        timeout=300,
        payload=payload,
    )
    images = data.get("data") or []
    if not images or not isinstance(images[0], dict) or not images[0].get("url"):
        raise RuntimeError(f"302 image response did not contain image URL: {data}")

    download_file(images[0]["url"], output_path)
    return {
        "provider": "302.ai",
        "model": model,
        "path": str(output_path.resolve()),
        "source_url": images[0].get("url"),
    }


def build_output_layout(output_dir: Path) -> dict[str, Path]:
    return {
        "root": output_dir,
        "audio_dir": output_dir / "audio",
        "images_dir": output_dir / "images",
        "video_dir": output_dir / "video",
        "plan_json": output_dir / "plan.json",
        "lyrics_txt": output_dir / "lyrics.txt",
        "manifest_json": output_dir / "manifest.json",
        "audio_mp3": output_dir / "audio" / "song.mp3",
        "video_mp4": output_dir / "video" / "song_video.mp4",
        "video_srt": output_dir / "video" / "song_video.srt",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate song audio, images, and MP4 from a plan JSON.")
    parser.add_argument("--plan", required=True, help="Path to the structured plan JSON.")
    parser.add_argument("--output-dir", required=True, help="Target folder for outputs.")
    parser.add_argument("--skip-music", action="store_true", help="Skip 302 music generation.")
    parser.add_argument("--skip-images", action="store_true", help="Skip 302 image generation.")
    parser.add_argument("--skip-video", action="store_true", help="Skip ffmpeg video rendering.")
    parser.add_argument("--dry-run", action="store_true", help="Only validate and write plan artifacts.")
    args = parser.parse_args()

    raw_plan = load_plan(Path(args.plan))
    plan = normalize_plan(raw_plan)
    output_dir = Path(args.output_dir)
    layout = build_output_layout(output_dir)
    for path in (layout["audio_dir"], layout["images_dir"], layout["video_dir"]):
        path.mkdir(parents=True, exist_ok=True)

    write_json(layout["plan_json"], plan)
    write_text(layout["lyrics_txt"], plan["lyrics"] + "\n")

    manifest: dict[str, Any] = {
        "song_title": plan["song_title"],
        "topic": plan["topic"],
        "output_dir": str(output_dir.resolve()),
        "artifacts": {
            "plan_json": str(layout["plan_json"].resolve()),
            "lyrics_txt": str(layout["lyrics_txt"].resolve()),
            "audio_mp3": None,
            "images": [],
            "video_mp4": None,
            "video_srt": None,
        },
        "providers": {
            "text": "built-in-model",
            "music": None,
            "image": None,
        },
        "scenes": plan["scenes"],
    }

    if args.dry_run:
        write_json(layout["manifest_json"], manifest)
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
        return

    if not args.skip_music:
        music_result = call_302_music(plan, layout["audio_mp3"])
        manifest["providers"]["music"] = {
            "provider": music_result["provider"],
            "model": music_result["model"],
        }
        manifest["artifacts"]["audio_mp3"] = music_result["path"]

    if not args.skip_images:
        image_results: list[dict[str, Any]] = []
        for scene in plan["scenes"]:
            filename = f"scene_{scene['index']:02d}.png"
            image_result = call_302_image(scene, layout["images_dir"] / filename)
            image_results.append(image_result)
        manifest["providers"]["image"] = {
            "provider": "302.ai",
            "model": os.getenv("THREEZERO2_IMAGE_MODEL", "gpt-image-1-mini").strip() or "gpt-image-1-mini",
        }
        manifest["artifacts"]["images"] = [item["path"] for item in image_results]

    if not args.skip_video:
        if not layout["audio_mp3"].exists():
            raise RuntimeError("Cannot render video without audio/song.mp3")
        image_paths = [layout["images_dir"] / f"scene_{scene['index']:02d}.png" for scene in plan["scenes"]]
        missing_images = [str(path) for path in image_paths if not path.exists()]
        if missing_images:
            raise RuntimeError(f"Cannot render video because some scene images are missing: {missing_images}")
        render_result = render_package(
            image_paths=image_paths,
            audio_path=layout["audio_mp3"],
            video_path=layout["video_mp4"],
            srt_path=layout["video_srt"],
            captions=[scene["caption"] or scene["lyric_excerpt"] for scene in plan["scenes"]],
        )
        manifest["artifacts"]["video_mp4"] = render_result["video_path"]
        manifest["artifacts"]["video_srt"] = render_result["subtitle_path"]

    write_json(layout["manifest_json"], manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
