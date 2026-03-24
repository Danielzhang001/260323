---
name: english-cartoon-song-maker
description: 将英语课本、教材段落、课堂对话或单元词汇改写成适合儿童学习的英文儿歌方案，并生成真唱音频、卡通配图和 MP4 成片。用户需要把英文教学内容做成可下载的 MP3、图片、字幕和视频素材时使用。优先用于中国大陆可访问、按量付费的方案：文本改写走小龙虾或扣子内置大模型，音乐和配图统一走 302.AI，视频走本地 ffmpeg。
---

# English Cartoon Song Maker

## Overview

Use this skill to turn English teaching material into a reusable media package:

1. Convert the lesson text into a structured kids-song plan.
2. Generate a sung song with accompaniment.
3. Generate cartoon images for each scene.
4. Render a slideshow-style MP4 plus sidecar subtitles.

This skill is designed for two runtime shapes:

- `Preferred`: self-hosted Xiaolongxia or any runtime where you can install `ffmpeg`.
- `Portable`: Coze workflow for planning and API calls, with the final ffmpeg render moved into your own service if the hosted runtime cannot execute local binaries.

## Before Use

Anyone reusing this project must fill in their own API keys.

- Do not commit real API keys.
- Use the placeholders in `.env.example`.
- Keep generated `output/` files out of version control.

## Workflow

### 1. Use the built-in model for text planning

Do not add another text API by default.

When running inside Xiaolongxia or Coze workflow, use the platform's native large-model capability to convert the source lesson into a JSON plan that matches [references/plan-schema.md](references/plan-schema.md).

The model step must produce:

- `song_title`
- `music_prompt`
- `lyrics`
- `scenes[]` with `image_prompt`
- short scene captions or lyric excerpts

Keep the output constrained:

- 4 to 6 scenes
- simple AABB or ABAB rhyme
- clear beginner-friendly pronunciation
- 16:9 visual prompts
- one consistent cartoon character profile across all scenes

### 2. Run the pipeline script

Use [scripts/run_pipeline.py](scripts/run_pipeline.py) after the JSON plan is ready.

Example:

```powershell
$env:THREEZERO2_API_KEY="your_302_key"
python .\scripts\run_pipeline.py `
  --plan .\references\sample-plan.json `
  --output-dir .\output\demo
```

The script writes:

- `lyrics.txt`
- `plan.json`
- `audio/song.mp3`
- `images/scene_01.png` ...
- `video/song_video.mp4`
- `video/song_video.srt`
- `manifest.json`

### 3. Return downloadable files

Return absolute paths for:

- final `mp3`
- generated images
- `mp4`
- `srt` when present

If the provider key is missing, fail fast with a clear message instead of silently downgrading quality.

## Runtime Rules

### Preferred provider mix

- `Text`: Xiaolongxia or Coze built-in model
- `Singing`: 302.AI Suno Custom Mode `chirp-auk`
- `Images`: 302.AI `gpt-image-1-mini`
- `Video render`: local `ffmpeg`

### China-mainland rule

Treat China-mainland availability as a hard requirement.

- Prefer 302.AI for both music and image generation so billing and networking stay on one provider.
- Use Suno Custom Mode `chirp-auk` when you want true sung vocals with custom lyrics.
- Keep lyric rewriting minimal: only line breaks, rhythm shaping, and a small repeated chorus when needed.
- If the lyric text exceeds the model limit, split it into two parts automatically and concatenate the generated audio.
- Do not burn subtitles into the mp4 by default. Keep the `.srt` sidecar unless the user explicitly asks for burned-in subtitles.
- Trim leading and trailing empty music locally after the song is generated.
- Use `gpt-image-1-mini` for lower-cost cartoon image generation through the same 302 key.
- If you swap image generation to OpenRouter Gemini Flash, a recommended house style is `Pixar / Disney inspired 3D cartoon style`, with bright classroom lighting, soft materials, large expressive eyes, rounded shapes, and family-friendly color design.
- If a hosted runtime cannot execute `ffmpeg`, keep the render step in your own service.

See [references/api-setup.md](references/api-setup.md) and [references/coze-workflow-mapping.md](references/coze-workflow-mapping.md).

## Quality Bar

- Keep the original lesson meaning intact.
- Favor short, singable lines over literal translation.
- Make image prompts child-safe, bright, and visually consistent.
- Keep each song short enough for classroom replay.
- Do not claim lip-sync or character animation. This skill outputs a slideshow-style MP4 unless the user explicitly asks for a separate video-generation step.

## Resources

### scripts/

- `run_pipeline.py`: end-to-end package builder
- `render_video.py`: standalone slideshow renderer

### references/

- `plan-schema.md`: exact JSON shape for the built-in model
- `api-setup.md`: API key setup and deployment notes
- `coze-workflow-mapping.md`: mapping to Coze workflow nodes
- `sample-plan.json`: runnable example
