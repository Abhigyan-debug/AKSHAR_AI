# Scoring

How Akshar turns a recording into a result. All numbers below come from `backend/config/thresholds.json`. They are provisional: they were calibrated on synthetic voices and are not clinically validated.

## Why the scoring looks like this

Before building anything, the team ran a spike to answer one question: does Whisper "auto-correct" a child's misreading into the expected word and hide the error? It does not. On 20 synthetic clips, `whisper-large-v3` never rewrote an error back to the target. It kept every deliberate Hindi error (पमीर read as पनीर, मीठा as मिठा, वजन as बजन, खाना as काना, स्कूल as सकूल, skipped words). The real problem was mishearing short English words ("ded" heard as "did", "saw" as "song") and isolated Hindi letters (ब heard as बाद). Those findings shape everything below: Hindi auto-scoring is trusted, English and letters lean on the teacher, and Whisper's own confidence decides when to ask.

## Item status

Every item gets one status when it is scored. It never changes.

| Status | When | Counts toward the result |
|---|---|---|
| `manual` | letters and sound-game answers in both languages, one-syllable English nonwords | once the teacher taps correct, incorrect or skipped |
| `teacher_verify` | Whisper's `avg_logprob` below -0.6, `no_speech_prob` above 0.6, an empty transcript, or the wrong script (a Hindi item heard in Latin letters) | once the teacher verifies it |
| `auto` | everything else | Hindi at once; English only after the teacher confirms it |

Manual items are scored by a live tap on the child's screen and never reach the verify queue. On the spike clips, every mishearing had `avg_logprob` around -0.9 and every correct transcript was at -0.45 or higher.

## Comparing the transcript with the target

Both sides are normalized first, so spelling variants that sound the same compare equal:

- Unicode NFC, lower case, punctuation (including the danda) removed, zero-width joiners dropped
- nukta removed (ज़ = ज), except on ड़ and ढ़, which are different sounds
- chandrabindu treated as anusvara (हँस = हंस), and a nasal consonant with virama before a consonant treated as anusvara (हिन्दी = हिंदी)
- doubled consonants collapsed (गुब्बारा = गुबारा)
- for single-word items, spaces ignored, because Whisper sometimes splits a made-up word ("mistop" heard as "mis top")

An item is correct when the transcript matches the target or one of its `accepted_variants`.

## Error types

When the item is wrong, `classify_rules.py` labels what happened. Hindi words are split into aksharas and flattened into consonant-plus-vowel units, then aligned.

| Type | Example | Notes |
|---|---|---|
| `lexicalization` | पमीर → पनीर, napkim → napkin | a made-up word read as a real one (its `near_real`, or a real word from the test) |
| `matra_confusion` | मीठा → मिठा | vowel sign swapped, dropped or added; anusvara dropped or added |
| `visual_akshara_swap` | वजन → बजन | look-alike pairs ब/व, भ/म, घ/ध, प/ष, ड/ङ, थ/य, and ख/रव |
| `aspiration_error` | खाना → काना | क/ख, ग/घ, च/छ, ज/झ, ट/ठ, ड/ढ, त/थ, द/ध, प/फ, ब/भ |
| `conjunct_error` | स्कूल → सकूल, प्यास → पास | low confidence and low weight |
| `transposition` | कमल → मकल, from → form | neighbours swapped |
| `letter_reversal` | bed → ded | b/d, p/q, u/n, m/w |
| `word_reversal` | was → saw | |
| `vowel_error` | cat → cot | English vowels |
| `omission`, `addition` | frog → fog | a letter, akshara or passage word missing or added |
| `first_letter_guess` | बकरी → बगीचा | first akshara right, the rest a different word |
| `self_correction` | पम पमीर | a restart of the same word; the last attempt is scored |
| `unclassified` | है → था | left for the LLM to label, from an allowed list only |

Several words heard for a one-word item count as a self-correction only when each earlier word starts like the last one and is not longer. Otherwise the words are joined and judged as one reading ("drumpet" heard as "Drum Pit" is a vowel error, not a retry).

When a teacher marks an item correct, its rule errors are removed, because they came from a mishearing.

## Timing

| Flag | Rule | Applies to |
|---|---|---|
| `hesitation` | a gap of 1.0 s or more between words, or any word lasting more than 0.8 s | the passage and other multi-word reading only |
| `slow_start` | the first word starts 3.0 s or more into the clip | every item |
| `slow_decoding` | first word to last word longer than 3 s (letters), 4 s (words), 5 s (nonwords), 6 s (sound game) | single items |

The long-word rule exists because `whisper-large-v3` folds a pause into the next word's timestamps instead of leaving a gap. It does not apply to single words: in the end-to-end test, correct readings of three- and four-akshara words took 0.82 to 0.88 s and were flagged falsely.

## Risk

Only items that count (see Item status) feed the accuracies. A section with less than 60% of its items counted is pending; if words or nonwords are pending in a language, that language is pending.

Per language, Akshar computes accuracy for letters, words, nonwords and the sound game, words correct per minute on the passage, and a weighted error score over letters, words and nonwords:

| Error | Weight |
|---|---|
| `lexicalization` | 3 |
| `hesitation`, `slow_start`, `slow_decoding` | 2 |
| Hindi `matra_confusion`, `aspiration_error`, `visual_akshara_swap`, `transposition` | 2 |
| English `letter_reversal`, `word_reversal`, `vowel_error`, `transposition` | 1 |
| `omission`, `addition`, `first_letter_guess` | 1 |
| `conjunct_error`, `unclassified` | 0.5 |
| `self_correction` | 0.25 |

The passage's word-level errors stay out of this score because the passage is measured by words correct per minute. The sound game's timing stays out too, because thinking time there is not a reading signal.

A language is weak when word accuracy is below 70%, nonword accuracy below 60%, or the passage rate below the grade guide (20, 35, 50, 65 and 80 words correct per minute for grades 1 to 5). A specific pattern needs a Hindi weighted error score of at least 0.5 and one of: nonwords are the weakest Hindi section, at least two lexicalizations across both languages, or hesitation on at least 30% of Hindi items.

| Hindi | English | Pattern | Result |
|---|---|---|---|
| on track | on track | | Low risk |
| on track | weak | | English exposure gap |
| weak | weak | yes | Needs specialist check |
| weak | weak | no | Needs reading support |
| weak | on track | | Needs Hindi reading support |
| any | pending | | Provisional: verify the English items |
| pending | any | | Pending teacher check |

Every report lists the reasons (accuracies, the error counts and examples such as "Read the made-up word पमीर as पनीर") and a scoring breakdown: the share of items auto-scored, sent to teacher check and live-tapped.

## The LLM

The LLM does two narrow jobs. It never decides the result.

1. It labels word errors the rules left as `unclassified`, on reliable items only, choosing from an allowed list. It may use `lexicalization` only on real made-up words. These labels show as "AI" in the report.
2. It writes the teacher summary (English), a next step (rephrasing a fixed recommendation for each result) and the parent summary with exactly three home tips (Hindi).

Replies must be valid JSON and pass validation: no "dyslexia" wording in either language, Hindi text at least 80% Devanagari, exactly three tips. A rejected reply gets one retry; after that a hand-written template is used. The parent text never quotes test items, because practising them at home would spoil a later re-screen. While a result is pending or provisional, the LLM is not called at all.

The model was chosen by running the real prompt on three Groq models. `openai/gpt-oss-120b` gave the most accurate teacher summaries; `gpt-oss-20b` once described a low-risk child as below the thresholds, and `qwen3.8-27b` made Hindi grammar mistakes and sometimes took 15 to 28 seconds.
