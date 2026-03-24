# Coze Workflow Mapping

This skill is easiest to run in a self-hosted runtime with shell access. The same logic can be mapped into Coze workflow as follows.

## Node layout

1. `Start`
2. `Large Model`
3. `HTTP Request` for 302 music
4. `Loop` over scenes
5. `HTTP Request` for OpenRouter image generation
6. `Code` or custom service to collect files
7. `Code` or custom render service for ffmpeg
8. `End`

## Recommended inputs

- `source_text`
- `target_age`
- `topic`
- optional `preferred_voice_style`
- optional `scene_count`

## Large-model node output

The large-model node should output the JSON object defined in [plan-schema.md](plan-schema.md).

Use the platform's built-in model here. This is the cheapest place to do the text transformation.

## 302 music node

POST `https://api.302.ai/minimaxi/v1/music_generation`

Headers:

- `Authorization: Bearer {{THREEZERO2_API_KEY}}`
- `Content-Type: application/json`

Body fields:

- `model`: `music-2.5`
- `prompt`
- `lyrics`
- `audio_setting`

## OpenRouter image node

POST `https://openrouter.ai/api/v1/chat/completions`

Headers:

- `Authorization: Bearer {{OPENROUTER_API_KEY}}`
- `Content-Type: application/json`

Body fields:

- `model`: `google/gemini-3.1-flash-image-preview`
- `messages`
- `modalities`: `["image","text"]`
- `image_config.image_size`
- `image_config.aspect_ratio`

## Render step

Inference:
If your hosted Coze runtime does not allow installing or invoking `ffmpeg`, expose the render step as your own HTTP service and call it from a workflow node. The Python code in `scripts/render_video.py` is structured so it can be reused in that service.

## Output contract

Return these URLs or file handles from the final step:

- `song_mp3`
- `images[]`
- `song_mp4`
- `song_srt`
- `manifest_json`
