import { CheckIcon, EyeIcon, PlayIcon, SpeakerHighIcon } from '@phosphor-icons/react'
import { AnimatePresence, motion, useReducedMotion } from 'motion/react'
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { speak, speakWithWords, stopSpeaking, type SpeechLang } from '../lib/speech'
import { chime, pick, shuffle, useAdaptive } from './engine'
import type { PracticeContent } from './meta'

const VOICE: Record<'hi' | 'en', SpeechLang> = { hi: 'hi-IN', en: 'en-IN' }
const EASE = [0.16, 1, 0.3, 1] as const

export interface GameProps {
  adultVoice: boolean // no device voice: an adult reads the word instead
  onProgress: (done: number, total: number) => void
  onDone: (stars: number) => void
}

/* ------------------------------------------------------------------ shared */

/** Big button that plays the word; in adult-voice mode it becomes a hidden cue for the adult. */
function ListenButton({ text, lang, adultVoice }: { text: string; lang: 'hi' | 'en'; adultVoice: boolean }) {
  const reduce = useReducedMotion()
  const [peek, setPeek] = useState(false)
  useEffect(() => {
    if (!adultVoice) void speak(text, VOICE[lang], 0.8)
    return stopSpeaking
  }, [text, lang, adultVoice])

  if (adultVoice)
    return (
      <div className="flex flex-col items-center gap-2">
        <button
          type="button"
          onPointerDown={() => setPeek(true)}
          onPointerUp={() => setPeek(false)}
          onPointerLeave={() => setPeek(false)}
          onClick={() => {
            setPeek(true)
            window.setTimeout(() => setPeek(false), 2000)
          }}
          className="flex items-center gap-2 rounded-full border border-outline bg-surface-container px-4 py-2 text-sm font-bold text-ink-muted"
        >
          <EyeIcon size={18} aria-hidden /> बड़ों के लिए: दबाकर शब्द देखें
        </button>
        <AnimatePresence>
          {peek && (
            <motion.p
              initial={{ opacity: 0, y: -4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              lang={lang}
              className="rounded-[12px] bg-ink px-4 py-2 font-display text-2xl text-white"
            >
              यह बोलिए: {text}
            </motion.p>
          )}
        </AnimatePresence>
      </div>
    )

  return (
    <motion.button
      type="button"
      onClick={() => void speak(text, VOICE[lang], 0.7)}
      whileTap={reduce ? undefined : { scale: 0.94 }}
      aria-label="फिर से सुनो"
      className="flex h-24 w-24 items-center justify-center rounded-full bg-primary text-on-primary shadow-[0_8px_24px_rgba(91,58,142,0.3)]"
    >
      <SpeakerHighIcon size={44} weight="fill" aria-hidden />
    </motion.button>
  )
}

type CardState = 'idle' | 'wrong' | 'right' | 'hint'

function ChoiceCard({ children, state, onClick, lang }: { children: ReactNode; state: CardState; onClick: () => void; lang: 'hi' | 'en' }) {
  const reduce = useReducedMotion()
  const styles: Record<CardState, string> = {
    idle: 'border-outline/70 bg-white',
    wrong: 'border-outline/40 bg-surface-container opacity-40',
    right: 'border-primary bg-primary-container',
    hint: 'border-accent bg-accent-container',
  }
  return (
    <motion.button
      type="button"
      lang={lang}
      disabled={state === 'wrong' || state === 'right'}
      onClick={onClick}
      whileTap={reduce ? undefined : { scale: 0.95 }}
      animate={!reduce && state === 'right' ? { scale: [1, 1.08, 1] } : !reduce && state === 'hint' ? { scale: [1, 1.04, 1] } : { scale: 1 }}
      transition={{ duration: 0.35, repeat: state === 'hint' ? Infinity : 0, repeatDelay: 0.6 }}
      className={`relative flex min-h-[96px] items-center justify-center rounded-[20px] border-2 px-4 py-5 font-display text-5xl font-semibold transition-colors ${styles[state]}`}
      style={{ lineHeight: 1.4 }}
    >
      {children}
      {state === 'right' && (
        <span className="absolute top-2 right-2 flex h-7 w-7 items-center justify-center rounded-full bg-primary text-on-primary">
          <CheckIcon size={16} weight="bold" aria-label="सही" />
        </span>
      )}
    </motion.button>
  )
}

/**
 * Runs `total` rounds with adaptive difficulty. `solve(firstTry)` records the
 * round and moves on; at the end it awards up to 5 stars for first-try answers.
 */
function useRounds(total: number, onProgress: GameProps['onProgress'], onDone: GameProps['onDone']) {
  const { choices, record } = useAdaptive(2, 4)
  const [round, setRound] = useState(0)
  const firstTries = useRef(0)
  useEffect(() => onProgress(round, total), [round, total, onProgress])
  const solve = useCallback(
    (firstTry: boolean) => {
      record(firstTry)
      if (firstTry) firstTries.current += 1
      if (round + 1 >= total) onDone(Math.max(1, Math.round((firstTries.current / total) * 5)))
      else setRound((r) => r + 1)
    },
    [record, round, total, onDone],
  )
  return { round, choices, solve }
}

/* ----------------------------------------------------- listen and choose */

interface ChooseRound {
  answer: string
  options: string[]
  speakText: string
  frame?: string // mirror game: the word with its first letter missing
}

interface ChooseProps extends GameProps {
  lang: 'hi' | 'en'
  total: number
  prompt: string
  makeRound: (choices: number) => ChooseRound
}

function ListenChoose({ lang, total, prompt, makeRound, adultVoice, onProgress, onDone }: ChooseProps) {
  const { round, choices, solve } = useRounds(total, onProgress, onDone)
  return (
    <ChooseRoundView key={round} lang={lang} prompt={prompt} adultVoice={adultVoice} start={() => makeRound(choices)} onSolved={solve} />
  )
}

/** One round; keyed by round number, so its question is drawn once when it mounts. */
function ChooseRoundView({
  lang,
  prompt,
  adultVoice,
  start,
  onSolved,
}: {
  lang: 'hi' | 'en'
  prompt: string
  adultVoice: boolean
  start: () => ChooseRound
  onSolved: (firstTry: boolean) => void
}) {
  const [r] = useState(start)
  const [wrong, setWrong] = useState<string[]>([])
  const [solved, setSolved] = useState(false)

  function choose(opt: string) {
    if (solved) return
    if (opt === r.answer) {
      chime()
      setSolved(true)
      window.setTimeout(() => onSolved(wrong.length === 0), 1000)
    } else {
      setWrong((w) => [...w, opt])
      if (!adultVoice) void speak(r.speakText, VOICE[lang], 0.6)
    }
  }

  const stateOf = (opt: string): CardState =>
    solved && opt === r.answer ? 'right' : wrong.includes(opt) ? 'wrong' : wrong.length >= 2 && opt === r.answer ? 'hint' : 'idle'

  return (
    <div className="flex flex-col items-center gap-8">
      <p lang={lang} className="text-center text-lg text-ink-muted">
        {prompt}
      </p>
      <ListenButton text={r.speakText} lang={lang} adultVoice={adultVoice} />
      {r.frame && (
        <p lang="en" className="font-display text-6xl font-semibold tracking-wide">
          <span className="inline-block min-w-[0.8em] border-b-4 border-accent text-center">{solved ? r.answer : ' '}</span>
          {r.frame.slice(1)}
        </p>
      )}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3, ease: EASE }}
        className="grid w-full max-w-md grid-cols-2 gap-4"
      >
        {r.options.map((opt) => (
          <ChoiceCard key={opt} lang={lang} onClick={() => choose(opt)} state={stateOf(opt)}>
            {opt}
          </ChoiceCard>
        ))}
      </motion.div>
    </div>
  )
}

function pairRound(pairs: [string, string][], choices: number): ChooseRound {
  const pair = pick(pairs)
  const answer = pick(pair)
  const partner = pair[0] === answer ? pair[1] : pair[0]
  // The minimal-pair partner is always there; extra choices come from other pairs.
  const others = shuffle(pairs.filter((p) => p !== pair).flat()).slice(0, Math.max(0, choices - 2))
  return { answer, options: shuffle([answer, partner, ...others]), speakText: answer }
}

const MIRROR_PARTNER: Record<string, string> = { b: 'd', d: 'b', p: 'q', q: 'p' }

export function MatraGame(props: GameProps & { content: PracticeContent }) {
  const pairs = props.content.games.matra.pairs
  return <ListenChoose {...props} lang="hi" total={10} prompt="सुनो, कौन-सा शब्द बोला?" makeRound={(c) => pairRound(pairs, c)} />
}

export function BreathGame(props: GameProps & { content: PracticeContent }) {
  const pairs = props.content.games.breath.pairs
  return <ListenChoose {...props} lang="hi" total={10} prompt="हवा वाली आवाज़ है या नहीं? सही शब्द चुनो" makeRound={(c) => pairRound(pairs, c)} />
}

export function MirrorGame(props: GameProps & { content: PracticeContent }) {
  const words = props.content.games.mirror.words
  return (
    <ListenChoose
      {...props}
      lang="en"
      total={10}
      prompt="Which letter does the word start with?"
      makeRound={(c) => {
        const word = pick(words)
        const answer = word[0]
        const rest = shuffle(['b', 'd', 'p', 'q'].filter((l) => l !== answer && l !== MIRROR_PARTNER[answer])).slice(0, Math.max(0, c - 2))
        return { answer, options: shuffle([answer, MIRROR_PARTNER[answer], ...rest]), speakText: word, frame: `_${word.slice(1)}` }
      }}
    />
  )
}

/* ----------------------------------------------------------------- twins */

interface Board {
  target: string
  tiles: string[]
  nTarget: number
}

function makeBoard(pairs: [string, string][], choices: number): Board {
  const pair = pick(pairs)
  const target = pick(pair)
  const twin = pair[0] === target ? pair[1] : pair[0]
  const size = 4 + choices * 2 // 8, 10, 12 tiles as the child gets better
  const nTarget = 3
  const nTwin = Math.ceil((size - nTarget) / 2)
  const others = shuffle(pairs.filter((p) => p !== pair).flat()).slice(0, size - nTarget - nTwin)
  return { target, tiles: shuffle([...Array(nTarget).fill(target), ...Array(nTwin).fill(twin), ...others]), nTarget }
}

export function TwinsGame({ content, onProgress, onDone }: GameProps & { content: PracticeContent }) {
  const pairs = content.games.twins.pairs
  const { round, choices, solve } = useRounds(6, onProgress, onDone)
  return <TwinsRound key={round} start={() => makeBoard(pairs, choices)} onSolved={solve} />
}

function TwinsRound({ start, onSolved }: { start: () => Board; onSolved: (firstTry: boolean) => void }) {
  const reduce = useReducedMotion()
  const [board] = useState(start)
  const [found, setFound] = useState<number[]>([])
  const [miss, setMiss] = useState<number | null>(null)
  const errors = useRef(0)

  useEffect(() => {
    void speak(board.target, 'hi-IN', 0.8)
    return stopSpeaking
  }, [board])

  function tap(i: number) {
    if (found.includes(i)) return
    if (board.tiles[i] === board.target) {
      const now = [...found, i]
      setFound(now)
      if (now.length === board.nTarget) {
        chime()
        window.setTimeout(() => onSolved(errors.current === 0), 900)
      }
    } else {
      errors.current += 1
      setMiss(i)
      window.setTimeout(() => setMiss(null), 500)
    }
  }

  return (
    <div className="flex flex-col items-center gap-6">
      <p lang="hi" className="text-lg text-ink-muted">
        यह अक्षर नीचे {board.nTarget} बार छिपा है। सब ढूँढो!
      </p>
      <motion.div
        initial={reduce ? false : { scale: 0.7, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        className="flex h-32 w-32 items-center justify-center rounded-[24px] bg-primary font-display text-7xl font-semibold text-on-primary"
        lang="hi"
      >
        {board.target}
      </motion.div>
      <div className="grid w-full max-w-md grid-cols-4 gap-3">
        {board.tiles.map((t, i) => (
          <motion.button
            key={i}
            type="button"
            lang="hi"
            onClick={() => tap(i)}
            animate={!reduce && miss === i ? { x: [0, -4, 4, 0] } : !reduce && found.includes(i) ? { scale: [1, 1.12, 1] } : {}}
            transition={{ duration: 0.3 }}
            className={`aspect-square rounded-[16px] border-2 font-display text-4xl font-semibold transition-colors ${
              found.includes(i) ? 'border-primary bg-primary-container text-on-primary-container' : 'border-outline/70 bg-white'
            }`}
            style={{ lineHeight: 1.4 }}
            aria-label={found.includes(i) ? `${t}, मिल गया` : t}
          >
            {t}
          </motion.button>
        ))}
      </div>
    </div>
  )
}

/* --------------------------------------------------------------- builder */

type BuilderWord = PracticeContent['games']['builder']['words'][number]

export function BuilderGame({ content, adultVoice, onProgress, onDone }: GameProps & { content: PracticeContent }) {
  const [words] = useState(() => shuffle(content.games.builder.words).slice(0, 6))
  const { round, choices, solve } = useRounds(words.length, onProgress, onDone)
  const w = words[round]
  return (
    <BuilderRound
      key={round}
      word={w}
      adultVoice={adultVoice}
      start={() => shuffle([...w.tiles, ...w.distractors.slice(0, choices >= 3 ? 2 : 1)])}
      onSolved={solve}
    />
  )
}

function BuilderRound({
  word: w,
  adultVoice,
  start,
  onSolved,
}: {
  word: BuilderWord
  adultVoice: boolean
  start: () => string[]
  onSolved: (firstTry: boolean) => void
}) {
  const reduce = useReducedMotion()
  const [pool] = useState(start)
  const [filled, setFilled] = useState<number[]>([])
  const [bounce, setBounce] = useState<number | null>(null)
  const errors = useRef(0)

  function tap(i: number) {
    if (filled.includes(i) || filled.length === w.tiles.length) return
    if (pool[i] === w.tiles[filled.length]) {
      const now = [...filled, i]
      setFilled(now)
      if (now.length === w.tiles.length) {
        chime()
        if (!adultVoice) void speak(w.word, 'hi-IN', 0.8)
        window.setTimeout(() => onSolved(errors.current === 0), 1400)
      }
    } else {
      errors.current += 1
      setBounce(i)
      window.setTimeout(() => setBounce(null), 450)
      if (!adultVoice) void speak(w.tiles.slice(filled.length).join(' '), 'hi-IN', 0.6)
    }
  }

  return (
    <div className="flex flex-col items-center gap-7">
      <p lang="hi" className="text-center text-lg text-ink-muted">
        {w.is_nonword ? 'यह बनाया हुआ शब्द है। सुनो और जोड़ो।' : 'सुनो और टुकड़े जोड़कर शब्द बनाओ'}
      </p>
      <ListenButton text={w.word} lang="hi" adultVoice={adultVoice} />
      <div className="flex gap-3" aria-label="शब्द">
        {w.tiles.map((_, k) => (
          <div
            key={k}
            lang="hi"
            className={`flex h-20 w-20 items-center justify-center rounded-[16px] border-2 border-dashed font-display text-4xl font-semibold ${
              filled[k] !== undefined ? 'border-primary bg-primary-container' : 'border-outline'
            }`}
            style={{ lineHeight: 1.4 }}
          >
            <AnimatePresence>
              {filled[k] !== undefined && (
                <motion.span initial={reduce ? false : { y: 30, opacity: 0 }} animate={{ y: 0, opacity: 1 }} transition={{ duration: 0.25, ease: EASE }}>
                  {pool[filled[k]]}
                </motion.span>
              )}
            </AnimatePresence>
          </div>
        ))}
      </div>
      <div className="flex flex-wrap justify-center gap-3">
        {pool.map((t, i) => (
          <motion.button
            key={i}
            type="button"
            lang="hi"
            disabled={filled.includes(i)}
            onClick={() => tap(i)}
            animate={!reduce && bounce === i ? { y: [0, -10, 0] } : {}}
            transition={{ duration: 0.35 }}
            className="h-20 w-20 rounded-[16px] border-2 border-outline/70 bg-white font-display text-4xl font-semibold shadow-[0_3px_0_rgba(207,196,183,0.9)] transition-opacity disabled:opacity-20"
            style={{ lineHeight: 1.4 }}
          >
            {t}
          </motion.button>
        ))}
      </div>
    </div>
  )
}

/* ------------------------------------------------------------- read-along */

type Story = PracticeContent['games']['readalong']['stories'][number]
type Phase = 'listen' | 'together' | 'alone'
const PHASES: { id: Phase; label: string; hint: string }[] = [
  { id: 'listen', label: 'सुनो', hint: 'चमकते शब्द के साथ आँखें चलाओ' },
  { id: 'together', label: 'साथ पढ़ो', hint: 'चमकते शब्द के साथ ज़ोर से पढ़ो' },
  { id: 'alone', label: 'खुद पढ़ो', hint: 'अब अकेले पढ़ो, धीरे-धीरे' },
]

export function ReadAlongGame({
  content,
  adultVoice,
  preferLang,
  onProgress,
  onDone,
}: GameProps & { content: PracticeContent; preferLang: 'hi' | 'en' }) {
  const stories = useMemo(() => {
    const all = content.games.readalong.stories
    return [...all.filter((s) => s.lang === preferLang), ...all.filter((s) => s.lang !== preferLang)]
  }, [content, preferLang])
  const [story, setStory] = useState<Story | null>(null)

  if (!story)
    return (
      <div className="flex flex-col items-center gap-5">
        <p lang="hi" className="text-lg text-ink-muted">
          कौन-सी कहानी पढ़ें?
        </p>
        <div className="grid w-full max-w-md gap-3">
          {stories.map((s) => (
            <button
              key={s.id}
              type="button"
              lang={s.lang}
              onClick={() => setStory(s)}
              className="rounded-[20px] border-2 border-outline/70 bg-white p-5 text-left hover:border-primary"
            >
              <span className="font-display text-2xl font-semibold">{s.title}</span>
              <span className="mt-1 block text-ink-muted">{s.lines[0]}</span>
            </button>
          ))}
        </div>
      </div>
    )
  return <ReadAlongStory story={story} adultVoice={adultVoice} onProgress={onProgress} onDone={onDone} />
}

function ReadAlongStory({ story, adultVoice, onProgress, onDone }: GameProps & { story: Story }) {
  const reduce = useReducedMotion()
  const [phase, setPhase] = useState(0)
  const [active, setActive] = useState<{ line: number; word: number } | null>(null)
  const [running, setRunning] = useState(false)
  const [slow, setSlow] = useState(true)
  const cancelled = useRef(false)
  const lines = useMemo(() => story.lines.map((l) => l.split(/\s+/)), [story])
  const current = PHASES[phase]

  useEffect(() => onProgress(phase, PHASES.length), [phase, onProgress])
  useEffect(
    () => () => {
      cancelled.current = true
      stopSpeaking()
    },
    [],
  )

  async function run() {
    cancelled.current = false
    setRunning(true)
    for (let li = 0; li < lines.length && !cancelled.current; li++) {
      if (current.id === 'listen' && !adultVoice) {
        await speakWithWords(story.lines[li], VOICE[story.lang], 0.8, (wi) => setActive({ line: li, word: wi }))
        await new Promise((r) => setTimeout(r, 300))
      } else {
        // A pacer: the highlight moves at a steady, child-friendly speed while the child (or adult) reads.
        for (let wi = 0; wi < lines[li].length && !cancelled.current; wi++) {
          setActive({ line: li, word: wi })
          await new Promise((r) => setTimeout(r, (slow ? 950 : 650) + [...lines[li][wi]].length * 40))
        }
      }
    }
    setActive(null)
    setRunning(false)
  }

  function finishPhase() {
    chime()
    if (phase + 1 >= PHASES.length) onDone(3)
    else setPhase((p) => p + 1)
  }

  return (
    <div className="flex flex-col items-center gap-6">
      <ol className="flex gap-2" aria-label="चरण">
        {PHASES.map((p, i) => (
          <li
            key={p.id}
            lang="hi"
            className={`rounded-full px-3 py-1 text-sm font-bold ${
              i === phase ? 'bg-primary text-on-primary' : i < phase ? 'bg-primary-container text-on-primary-container' : 'bg-surface-container text-ink-muted'
            }`}
          >
            {p.label}
          </li>
        ))}
      </ol>
      <p lang="hi" className="text-lg text-ink-muted">
        {current.hint}
        {current.id === 'listen' && adultVoice ? ' (बड़े पढ़कर सुनाएँ)' : ''}
      </p>
      <div lang={story.lang} className="w-full max-w-lg rounded-[24px] border border-outline/60 bg-white p-6">
        <h3 className="mb-3 font-display text-2xl font-semibold">{story.title}</h3>
        {lines.map((words, li) => (
          <p key={li} className="text-[28px] leading-[1.9]">
            {words.map((w, wi) => {
              const on = current.id !== 'alone' && active?.line === li && active.word === wi
              return (
                <span key={wi} className="relative mr-2 inline-block">
                  {on && (
                    <motion.span
                      layoutId={reduce ? undefined : 'readalong-word'}
                      className="absolute -inset-x-1 inset-y-1 rounded-[8px] bg-accent/45"
                      transition={{ type: 'spring', stiffness: 600, damping: 40 }}
                    />
                  )}
                  <span className="relative">{w}</span>
                </span>
              )
            })}
          </p>
        ))}
      </div>
      {current.id === 'together' && (
        <label lang="hi" className="flex items-center gap-2 text-ink-muted">
          <input type="checkbox" checked={slow} onChange={(e) => setSlow(e.target.checked)} className="h-5 w-5 accent-primary" />
          धीमी रफ़्तार
        </label>
      )}
      <div className="flex gap-3">
        {current.id !== 'alone' && (
          <button
            type="button"
            disabled={running}
            onClick={() => void run()}
            className="flex items-center gap-2 rounded-[14px] border-2 border-primary px-5 py-3 font-bold text-primary disabled:opacity-40"
            lang="hi"
          >
            <PlayIcon size={18} weight="fill" aria-hidden />
            {running ? 'चल रहा है' : 'शुरू करो'}
          </button>
        )}
        <button
          type="button"
          disabled={running}
          onClick={finishPhase}
          className="rounded-[14px] bg-primary px-5 py-3 font-bold text-on-primary disabled:opacity-40"
          lang="hi"
        >
          {phase + 1 >= PHASES.length ? 'पढ़ ली!' : 'आगे चलो'}
        </button>
      </div>
    </div>
  )
}
