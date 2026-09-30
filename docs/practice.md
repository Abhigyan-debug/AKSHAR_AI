# Practice games

Five-minute games that give a child daily practice on their own error pattern. They are played at home on the parent's phone and in class on the teacher's phone, always with an adult sitting alongside. No child login is needed.

- `/practice` shows every game.
- `/practice/<token>` uses the parent link's token to put the child's own games first. The parent page and the teacher report both link there.

Progress (games played, stars) is remembered only on that device.

## The games

| Game | For the error pattern | What the child does |
|---|---|---|
| मात्रा पहचानो (matra) | `matra_confusion` | Hears a word and picks it from a pair that differs only in one vowel sign, such as मिल / मील or बेल / बैल |
| हवा वाले अक्षर (breath) | `aspiration_error` | Same task with pairs that differ only in aspiration, such as पल / फल or बात / भात |
| जुड़वाँ अक्षर (twins) | `visual_akshara_swap` | Finds every copy of a letter in a grid full of its look-alike (ब/व, भ/म, घ/ध, प/ष, थ/य) |
| शब्द बनाओ (builder) | lexicalization, guessing, conjunct and omission errors | Hears a word or made-up word and builds it from akshara tiles; one or two trap tiles differ by a matra or aspiration |
| b, d, p, q (mirror) | `letter_reversal`, `word_reversal` | Hears an English word and picks its first letter from mirror pairs, then sees the word complete |
| साथ-साथ पढ़ो (read-along) | hesitation, slow starts, slow passage reading | Reads one short story three times: listening while each word lights up, reading aloud with a steady highlight, then alone |

`backend/app/services/practice.py` orders the games by how often the child made the error each one targets. A passage below the grade guide adds the read-along, and an English exposure gap adds the English games. Until the result is final, no games are recommended.

## Why they look like this

| Research finding | What it changed |
|---|---|
| Hindi readers with dyslexia made far more vowel substitutions and deletions than consonant errors ([Gupta, via summary](https://www.deepdyve.com/lp/springer_journal/reading-difficulties-of-hindi-speaking-children-with-developmental-raPNNQkSNe/1)). | The matra game is the first game for most children, and matra pairs are the largest content set. |
| In Kannada, another akshara script, children's spelling errors clustered on phonologically similar consonants and on small vowel marks ([Nag, Treiman and Snowling, "Learning to spell in an alphasyllabary"](https://profiles.wustl.edu/en/publications/learning-to-spell-in-an-alphasyllabary-the-case-of-kannada/)). | Separate games for vowel signs, aspirated pairs and look-alike letters. |
| A mobile game improved Hindi akshara recognition and reading and spelling of complex akshara; spaced and massed practice worked equally well ([Improving Hindi decoding skills via a mobile game, 2019](https://eric.ed.gov/?id=EJ1231476)). | Short daily sessions of about ten rounds, with items repeated across days. |
| GraphoGame-style sound-to-print matching beat a control group on in-game measures in a Delhi school, though not on paper tests ([GraphoLearn India, 2018](https://www.frontiersin.org/journals/psychology/articles/10.3389/fpsyg.2018.01045/full)). A review found no overall effect unless an adult was involved; with adult engagement the effect size was 0.48 ([McTigue et al., 2020](https://ila.onlinelibrary.wiley.com/doi/10.1002/rrq.256); [summary](https://haskinsglobal.org/?p=491)). | Listen-then-choose tasks, and every game opens with a Hindi tip for the adult and ends with one activity to do without the phone. |
| Children played more at school, but only parental involvement was linked to engagement and learning outcomes ([school vs home study](https://jyx.jyu.fi/handle/123456789/47910)). | Games work at home and in class, and the parent page links to them. |
| Same-language subtitling, where words light up as they are sung or spoken, raised reading scores in Indian primary schools ([PlanetRead research summary](https://betatest.planetread.org/pdf/Research_summary_Impact_of_SLS_on_reading_literacy.pdf)); a research synthesis found repeated reading the most effective fluency intervention for students with learning disabilities, helped further by a model of fluent reading ([Stevens, Walker and Vaughn, 2016](https://pmc.ncbi.nlm.nih.gov/articles/PMC5097019)). | The read-along highlights each word while it is spoken, then repeats the same story twice. |
| Letter reversals are common in typically developing young writers, and researchers still disagree about their cause ([Fischer and Luxembourger, 2021](https://www.frontiersin.org/articles/10.3389/fcomm.2021.719652/full)). | The b/d game gives many short sound-to-letter choices rather than drilling shapes. Its thumbs-up hand trick is a common classroom memory aid, offered without a claim that it has been tested. |
| Immediate feedback and rewards keep children with reading difficulties playing ([meta-analysis](https://pubmed.ncbi.nlm.nih.gov/36603312/)). | A soft chime and a check mark on success, stars at the end. |

These are published studies about other tools and children. They explain design choices; they are not evidence that Akshar's games work.

## Rules the games follow

- The child never sees a red cross or a score. A wrong choice fades, the word is replayed slowly, and after two misses the right card gently pulses.
- Difficulty adapts: two choices to start, one more after three first-try successes, one fewer after two misses in a row.
- Games do not use speech recognition. The child listens and taps, because children's speech is where recognition is least reliable.
- When the phone has no voice for the language, "an adult reads" mode turns on: the adult holds a button to see the word privately and says it aloud.
- Content never reuses the screening test's words, made-up words or passage, so practice cannot inflate a re-screen. Single letters are the exception, since they are the alphabet itself.

## Content

All content is in `backend/data/practice.json` and served by `GET /api/practice`. `backend/tests/test_practice.py` checks it with the rule engine itself: every matra pair must differ in exactly one vowel sign, every breath pair only in aspiration, every twin pair must be a known look-alike, builder tiles must spell their word, and nothing may overlap the test. Run `python -m pytest backend/tests/test_practice.py` after editing it.
