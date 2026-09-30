# Writing test content

The test items live in `backend/data/tests/hi.json` and `backend/data/tests/en.json`. All of them are original. Do not copy items from DALI or any published test.

## Sections

Each language has the same five sections, shown to the child one item per screen:

| Section | Items | Hindi | English | Scored by |
|---|---|---|---|---|
| A. Letters | 10 | confusable aksharas: ब व, भ म, घ ध, प ष, क ख | b d p q m w n u s h | teacher live tap |
| B. Real words | 10 | grade-level words with matras and two conjuncts | cat, ship, was, from… | auto (English confirmed by the teacher) |
| C. Nonwords | 10 | made-up words, four of them close to real ones | two-syllable made-up words | auto (English confirmed by the teacher) |
| D. Passage | 1 | an original story of about 40 words | the same | auto |
| E. Sound game | 5 | spoken questions such as "कमल में से 'क' हटाओ" | "Say 'cat' without the /k/" | teacher live tap |

The sound game is optional per session. Its answer is never shown to the child: the question is spoken by the browser and can be replayed.

## Item format

```json
{
  "id": "hi_C_01",
  "section": "C",
  "text": "पमीर",
  "is_nonword": true,
  "near_real": "पनीर",
  "accepted_variants": [],
  "scoring": "auto",
  "grade": 3,
  "tags": ["matra_ii", "near_real"]
}
```

| Field | Meaning |
|---|---|
| `id` | `{lang}_{section}_{nn}`. The tests check the prefix matches the file and section. |
| `text` | What the child reads. For section E it is the expected answer, and `prompt` holds the spoken question. |
| `is_nonword` | `true` for made-up words. Only these can be scored as lexicalization. |
| `near_real` | The real word a child is likely to say instead (पमीर → पनीर). Reading it counts as lexicalization. |
| `accepted_variants` | Other spellings of a correct reading only, for example ष also written श, or स्कूल said as इस्कूल. Never list a variant that is itself an error you want to catch. |
| `scoring` | `manual` for live tap, `auto` otherwise. |
| `word_count` | Passage only; the tests check it matches the text. |

## Rules for new items

- Keep every item original.
- Made-up words must not be real Hindi or English words, or sound like one. If a made-up word sounds exactly like a real word, Whisper writes the real word even when the child reads correctly.
- English made-up words need two syllables. One-syllable ones ("mib") were misheard too often in the spike and would have to be scored by hand.
- Keep letters and sound-game answers on `manual`. Isolated letters and very short answers were unreliable in testing (ब heard as बाद, सड़ as सर्द).
- Write Devanagari in Unicode NFC. The tests reject anything else.
- Run `python -m pytest backend/tests/test_items.py` after any change. It checks section counts, unique ids, scoring rules, two-syllable English nonwords, passage length, that every item read correctly is scored correct, and that every `near_real` reading is scored as lexicalization.
