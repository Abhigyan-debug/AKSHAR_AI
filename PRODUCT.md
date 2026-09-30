# Product

## Platform

web

## Users

- Class teachers in government Hindi-medium primary schools (Classes 1 to 5), confirmed as the first place Akshar will be used. The teacher screens one child at a time on a phone, taps the result of letter and sound-game items live, then reviews reports and a verify queue on a laptop or phone.
- Children aged about 6 to 10 who read aloud in Hindi and English. In these schools many are first-generation readers. They see one item at a time and never see a score.
- Parents, reached through a shareable link or QR code. They read Hindi and may have limited literacy, so the parent page is written in simple Hindi and read aloud by the phone.
- Hackathon judges evaluate the product in Round 1 of the AI with Education hackathon.

## Product Purpose

Find children who may need reading support or a specialist check early, in schools where no trained assessor is available. A child reads for about ten minutes; Akshar finds the error patterns linked to reading difficulty, separates a weak-only-in-English child (exposure gap) from a child struggling in both languages, and tells the teacher who needs what and the parent, in Hindi, what to do next. Practice games then give the child five-minute daily practice on their own error pattern at home and in class.

Success means the right children reach support or a specialist, and no child is labelled by a machine: every flag is backed by the child's own recording and confirmed or overridable by the teacher.

## Positioning

Akshar screens error patterns, not just speed or accuracy, and does it in Devanagari aksharas as well as English letters. It compares the two languages before saying anything, so limited English exposure is not mistaken for a reading difficulty. Scoring is deterministic and explainable; the LLM only writes summaries from computed facts. Items the speech model is unsure about go to the teacher instead of into the result.

## Operating Context

- Screening happens in school on a phone handed to the child after the teacher signs in with the school PIN and picks a child code.
- Assumed, not confirmed: classrooms are noisy, one phone is shared, and connectivity can be patchy. The child screen uploads clips in the background with retries for this reason.
- Practice games are played at home on the parent's phone (from the parent link) and in class on the teacher's phone, with an adult nearby. No child login.
- Reports are read by teachers; parent pages are shared by link or QR code.

## Capabilities and Constraints

- Hindi + English test: letters, real words, made-up words, a short passage, an optional sound game. All test content is original; nothing is copied from DALI or any published test.
- Speech-to-text is Groq `whisper-large-v3`; summaries use Groq `openai/gpt-oss-120b`. Clips are sent to Groq; everything else stays on the school's server.
- Results: Low risk, English exposure gap, Needs Hindi reading support, Needs reading support, Needs specialist check, plus pending/provisional while checks remain.
- Every threshold is provisional and illustrative, calibrated on synthetic voices only.
- Teacher access is a single shared school PIN. Per-teacher accounts, an audit log, encryption at rest and a retention period are undecided.
- Practice content must never reuse test items, so practice cannot spoil a re-screen.
- Undecided: deployment host, pilot school, consent process for sending clips to Groq.

## Brand Commitments

- Name: Akshar (अक्षर). Tagline: "Hear the child, not the label."
- Owl mascot in child mode, the landing page and the parent page.
- Always "screener, not a diagnosis". Never call a child dyslexic, in English or Hindi.
- Children are identified by codes, never names.
- Parents are addressed in warm, non-blaming Hindi ("आपका बच्चा आलसी नहीं है" only when a difficulty is shown).

## Evidence on Hand

None yet. There are no partner schools, no recordings of real children, no testimonials, no case studies and no expert review. All testing so far used text-to-speech voices and a simulated microphone. Future work must not invent users, schools, quotes, outcome numbers or endorsements. Research cited for design decisions (for example GraphoGame and same-language subtitling studies) is published third-party evidence, not evidence about Akshar.

## Product Principles

1. The teacher decides. Akshar shows evidence and suggestions; anything uncertain waits for a teacher.
2. Two languages before one verdict. Weak-only-in-English is an exposure gap, not a reading difficulty.
3. Explainable over clever. Rules score, the LLM only phrases, and every flag links to the recording.
4. Protect the child first: codes not names, data stays with the school, nothing on screen that feels like failing.
5. Practice with an adult. Games are built for a parent or teacher to sit alongside, because published evidence shows reading games work far better with adult involvement.

## Accessibility & Inclusion

- Children 6 to 10 who are early or struggling readers: very large Devanagari type with room for matras, one item per screen, spoken instructions, large touch targets, no timers on screen and no scores.
- Parents with limited literacy: simple Hindi, read aloud by the phone, with a fallback note when the phone has no Hindi voice.
- Reduced-motion settings are respected everywhere.
