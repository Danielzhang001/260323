# Song Plan Schema

Use the built-in Xiaolongxia or Coze large-model step to output a single JSON object only.

Do not wrap the JSON in Markdown fences.
Do not add prose before or after the JSON.

## Required fields

```json
{
  "topic": "Self introduction",
  "source_text": "Hello. My name is Tom. I am ten years old. I like reading books.",
  "song_title": "Hello Tom",
  "target_age": "6-9",
  "music_prompt": "Bright children's pop, cheerful classroom sing-along, female lead vocal, clear pronunciation, light drums, ukulele, easy chorus, 100 BPM",
  "lyrics": "[Intro]\nHello, hello!\nCome and sing with me!\n\n[Verse]\nHello, hello, my name is Tom,\nTen years old and feeling strong.\nI love books from page to page,\nReading stories every day.\n\n[Chorus]\nHello, Tom, hello, Tom,\nSing it loud and sing along.\nRead a book and smile all day,\nLearn in English, laugh and play.",
  "scenes": [
    {
      "caption": "Tom waves hello in class.",
      "lyric_excerpt": "Hello, hello, my name is Tom",
      "image_prompt": "Children's book illustration, bright pastel classroom, one cheerful boy named Tom with short brown hair and blue school uniform waving hello, big friendly eyes, clean outlines, 16:9, child-safe, consistent character design."
    },
    {
      "caption": "Tom shows he is ten years old.",
      "lyric_excerpt": "Ten years old and feeling strong",
      "image_prompt": "Same cartoon boy Tom in the same children's book illustration style, holding up ten fingers with playful energy, colorful classroom wall numbers, bright pastel colors, 16:9, consistent character design."
    },
    {
      "caption": "Tom reads books happily.",
      "lyric_excerpt": "I love books from page to page",
      "image_prompt": "Same cartoon boy Tom sitting in a cozy reading corner with open storybooks, warm sunlight, bookshelves, bright pastel children's illustration, 16:9, consistent character design."
    },
    {
      "caption": "The class sings together.",
      "lyric_excerpt": "Learn in English, laugh and play",
      "image_prompt": "Same cartoon boy Tom and classmates singing together in a happy classroom, teacher smiling, musical notes floating, bright pastel children's book illustration, 16:9, consistent character design."
    }
  ]
}
```

## Planning prompt template

Use this with the built-in model when the user provides lesson content:

```text
You are writing a classroom-ready English children's song package plan.

Task:
1. Rewrite the lesson into a short, catchy English children's song.
2. Preserve the lesson meaning and target vocabulary.
3. Produce 4 to 6 visual scenes.
4. Keep the visuals child-safe, bright, and stylistically consistent.
5. Output JSON only using the required schema.

Rules:
- Use simple words and short lines.
- Make the chorus easy to repeat.
- Keep pronunciation clear for learners in China.
- Make the music prompt suitable for a real sung track with accompaniment.
- Each image prompt must say the same character design details again for consistency.
- Prefer 16:9 classroom-friendly illustrations.
```

## Validation checklist

- `lyrics` is not empty.
- `music_prompt` mentions style, mood, vocals, and accompaniment.
- `scenes` length is between 4 and 6.
- Every scene has `image_prompt`.
- Every scene has `caption` or `lyric_excerpt`.
