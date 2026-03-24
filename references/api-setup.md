# API Setup

## Recommended provider split

- Text planning: Xiaolongxia or Coze built-in model
- Singing with accompaniment: 302.AI Suno Custom Mode `chirp-auk`
- Cartoon images: 302.AI `gpt-image-1-mini`
- Video render: local ffmpeg

This avoids paying for a separate text API and keeps music and images on one mainland-friendly billing provider.

## 1. 302.AI key

### Apply

1. Sign in to 302.AI.
2. Open the API key page in the 302 dashboard.
3. Create an API key.
4. Put the key into `THREEZERO2_API_KEY`.

### Environment variable

```powershell
$env:THREEZERO2_API_KEY="your_302_key"
$env:THREEZERO2_MUSIC_MODEL="chirp-auk"
$env:THREEZERO2_SUNO_TAGS="儿歌, 快乐"
$env:THREEZERO2_IMAGE_MODEL="gpt-image-1-mini"
```

### Notes

- `chirp-auk` is the default true-singing model in this skill.
- Suno Custom Mode only needs `prompt`, `tags`, and `mv`; if you do not send `title`, 302 will return `unTitled`.
- If lyrics exceed the configured limit, the script splits them into two parts and concatenates the resulting mp3 files automatically.
- The local pipeline trims leading and trailing silent music after generation.
- `gpt-image-1-mini` is the default image model because it is fast and already validated in this workflow.
- Both music and images use the same 302 key.
- If you move the image step to OpenRouter Gemini Flash, recommend a consistent style preset such as `Pixar / Disney inspired 3D cartoon style`.
- Public repo users should always fill in their own keys through `.env.example`; do not ship real credentials.

## 2. ffmpeg

Install `ffmpeg` in the runtime that executes the render step.

### Windows

1. Install a Windows build of ffmpeg.
2. Add the `bin` directory to `PATH`.
3. Verify with:

```powershell
ffmpeg -version
ffprobe -version
```

## 3. What you do not need

You do not need OpenRouter or fal in this skill unless you explicitly want to swap providers later.

## 4. Deployment advice

- Self-hosted Xiaolongxia: full workflow can run locally.
- Coze workflow: planning plus API calls map cleanly to nodes. The ffmpeg render step may need your own service if the hosted runtime cannot execute local binaries.
