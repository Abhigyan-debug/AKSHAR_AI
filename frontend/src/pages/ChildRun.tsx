import { AnimatePresence, motion } from 'motion/react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { api, type Lang, type Report, type Section, type Tap, type TestItem } from '../api'
import { LiveTapStrip, MicButton, Owl, SpeechBubble, Stars } from '../components/child'
import { Button, ErrorBox, Spinner } from '../components/ui'
import { graphemes } from '../lib/diff'
import { useRecorder, type Recording } from '../lib/recorder'
import { speak, stopSpeaking } from '../lib/speech'
import { UploadQueue } from '../lib/uploadQueue'
import { silentWav } from '../lib/wav'

type Step =
  | { kind: 'intro'; lang: Lang; section: Section }
  | { kind: 'item'; lang: Lang; section: Section; item: TestItem; index: number; count: number }
  | { kind: 'done' }

const SECTION_NAMES: Record<Lang, Record<Section, string>> = {
  hi: { A: 'अक्षर', B: 'शब्द', C: 'नए शब्द', D: 'कहानी', E: 'आवाज़ का खेल' },
  en: { A: 'Letters', B: 'Words', C: 'Made-up words', D: 'Story', E: 'Sound game' },
}
// Spoken with the browser's voice when each section starts (audio instructions).
const INSTRUCTIONS: Record<Lang, Record<Section, string>> = {
  hi: {
    A: 'हर अक्षर को ज़ोर से पढ़ो।',
    B: 'हर शब्द को ज़ोर से पढ़ो।',
    C: 'ये नए, बनाए हुए शब्द हैं। जैसे लिखे हैं, वैसे ही पढ़ो।',
    D: 'अब यह छोटी कहानी ज़ोर से पढ़ो।',
    E: 'ध्यान से सुनो, फिर जवाब बोलो।',
  },
  en: {
    A: 'Read each letter aloud.',
    B: 'Read each word aloud.',
    C: 'These are made-up words. Read them the way they are written.',
    D: 'Now read this short story aloud.',
    E: 'Listen carefully, then say the answer.',
  },
}
const START_LABEL: Record<Lang, string> = { hi: 'शुरू करो', en: "Let's start" }
const VOICE: Record<Lang, 'hi-IN' | 'en-IN'> = { hi: 'hi-IN', en: 'en-IN' }
const MAX_MS: Record<Section, number> = { A: 15000, B: 15000, C: 15000, D: 120000, E: 20000 }

function buildSteps(banks: Record<Lang, TestItem[]>, soundGame: boolean): Step[] {
  const steps: Step[] = []
  for (const lang of ['hi', 'en'] as Lang[]) {
    for (const section of ['A', 'B', 'C', 'D', 'E'] as Section[]) {
      if (section === 'E' && !soundGame) continue
      const items = banks[lang].filter((i) => i.section === section)
      if (!items.length) continue
      steps.push({ kind: 'intro', lang, section })
      items.forEach((item, index) => steps.push({ kind: 'item', lang, section, item, index, count: items.length }))
    }
  }
  steps.push({ kind: 'done' })
  return steps
}

export default function ChildRun() {
  const { sessionId: sid } = useParams()
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const sessionId = Number(sid)
  const childId = Number(params.get('child'))
  const soundGame = params.get('sound') !== '0'

  const rec = useRecorder()
  const queue = useMemo(() => new UploadQueue(), [])
  const [queueStatus, setQueueStatus] = useState(queue.status())
  const [steps, setSteps] = useState<Step[] | null>(null)
  const [index, setIndex] = useState(0)
  const [waitingTap, setWaitingTap] = useState<Recording | null>(null)
  const [loadError, setLoadError] = useState<unknown>(null)
  const indexRef = useRef(0)
  const tapRef = useRef<Tap | null>(null)

  useEffect(() => queue.subscribe(setQueueStatus), [queue])
  useEffect(() => {
    Promise.all([api.getTest('hi'), api.getTest('en')])
      .then(([hi, en]) => setSteps(buildSteps({ hi: hi.items, en: en.items }, soundGame)))
      .catch(setLoadError)
  }, [soundGame])

  // Don't lose clips that are still uploading.
  useEffect(() => {
    const warn = (e: BeforeUnloadEvent) => {
      if (queue.status().pending) e.preventDefault()
    }
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [queue])

  const step = steps?.[index]

  const goNext = useCallback((from: number) => {
    // Only advance from the step the action belongs to (guards double taps).
    if (indexRef.current !== from) return
    indexRef.current = from + 1
    setWaitingTap(null)
    tapRef.current = null
    setIndex(from + 1)
  }, [])

  // Speak section instructions and sound-game prompts when they appear.
  useEffect(() => {
    if (!step || step.kind === 'done') return
    if (step.kind === 'intro') void speak(INSTRUCTIONS[step.lang][step.section], VOICE[step.lang])
    else if (step.section === 'E' && step.item.prompt) void speak(step.item.prompt, VOICE[step.lang])
    return stopSpeaking
  }, [step])

  function enqueue(item: TestItem, clip: { blob: Blob; filename: string }, liveTap?: Tap) {
    queue.add({ sessionId, itemId: item.id, blob: clip.blob, filename: clip.filename, liveTap })
  }

  async function onMic() {
    if (!step || step.kind !== 'item') return
    if (rec.state === 'recording') {
      rec.stop()
      return
    }
    stopSpeaking()
    const at = index
    const current = step
    const clip = await rec.record({ silenceMs: 5000, maxMs: MAX_MS[current.section] })
    if (!clip) return
    if (current.item.scoring === 'manual') {
      const tap = tapRef.current
      if (tap) {
        enqueue(current.item, clip, tap)
        goNext(at)
      } else {
        setWaitingTap(clip) // stopped by silence: wait for the teacher's tap
      }
    } else {
      enqueue(current.item, clip)
      goNext(at)
    }
  }

  function onTap(tap: Tap) {
    if (!step || step.kind !== 'item') return
    if (rec.state === 'recording') {
      tapRef.current = tap // onMic finishes the item when the recorder stops
      rec.stop()
      return
    }
    const clip = waitingTap ?? { blob: silentWav(), filename: 'silence.wav' }
    enqueue(step.item, clip, tap)
    goNext(index)
  }

  async function startSection() {
    if (!(await rec.openMic())) return
    goNext(index)
  }

  function exit() {
    if (window.confirm('Stop the test? Items already recorded are kept.')) {
      stopSpeaking()
      navigate(`/teacher/child/${childId}`)
    }
  }

  if (loadError) return <main className="p-6"><ErrorBox error={loadError} /></main>
  if (!steps || !step) return <main className="p-6"><Spinner label="Loading…" /></main>
  if (step.kind === 'done') return <Done sessionId={sessionId} childId={childId} queue={queue} status={queueStatus} />

  const sections = soundGame ? 5 : 4
  const sectionIndex = ['A', 'B', 'C', 'D', 'E'].indexOf(step.section)
  const manual = step.kind === 'item' && step.item.scoring === 'manual'

  return (
    <main className="mx-auto flex h-dvh max-w-[480px] flex-col bg-surface">
      <header className="flex items-center justify-between border-b border-outline/30 px-4 pt-3 pb-2">
        <button type="button" onClick={exit} aria-label="Stop test" className="flex h-10 w-10 items-center justify-center rounded-full bg-surface-container text-lg">
          ✕
        </button>
        <span className="inline-flex items-center gap-2 rounded-full border border-outline/60 bg-white px-3 py-1 text-sm font-bold">
          <span className="h-2 w-2 rounded-full bg-accent" />
          {step.lang === 'hi' ? 'हिंदी' : 'English'}
        </span>
        <div className="flex items-center gap-2">
          {queueStatus.pending > 0 && <span className="text-[11px] text-ink-muted" title="clips uploading">↑{queueStatus.pending}</span>}
          <Stars total={sections} filled={sectionIndex} />
        </div>
      </header>

      <AnimatePresence mode="wait">
        <motion.section
          key={index}
          initial={{ opacity: 0, x: 40 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: -40 }}
          transition={{ duration: 0.25 }}
          className="flex flex-1 flex-col gap-4 overflow-y-auto px-4 py-4"
        >
          {step.kind === 'intro' ? (
            <Intro step={step} onStart={startSection} micState={rec.state} />
          ) : (
            <>
              <SpeechBubble>
                <span lang={step.lang}>{step.section === 'E' ? INSTRUCTIONS[step.lang].E : step.lang === 'hi' ? 'ज़ोर से पढ़ो! 📢' : 'Read it aloud! 📢'}</span>
              </SpeechBubble>
              <ItemCard step={step} />
              <div className="mt-auto flex flex-col items-center gap-2 pb-2">
                <MicButton
                  listening={rec.state === 'recording'}
                  level={rec.level}
                  onClick={onMic}
                  disabled={!!waitingTap}
                  label={rec.state === 'recording' ? 'Stop' : 'Start reading'}
                />
                <span lang={step.lang} className="rounded-full bg-primary-container px-4 py-1.5 text-sm font-bold text-on-primary-container">
                  {rec.state === 'recording'
                    ? step.lang === 'hi' ? 'सुन रहे हैं…' : 'Listening…'
                    : waitingTap
                      ? step.lang === 'hi' ? 'बहुत अच्छे!' : 'Well done!'
                      : step.lang === 'hi' ? 'माइक दबाओ और पढ़ो' : 'Tap the mic and read'}
                </span>
              </div>
            </>
          )}
        </motion.section>
      </AnimatePresence>

      {manual && <LiveTapStrip onTap={onTap} highlight={!!waitingTap} />}
    </main>
  )
}

function Intro({ step, onStart, micState }: { step: Extract<Step, { kind: 'intro' }>; onStart: () => void; micState: string }) {
  const { lang, section } = step
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-6 text-center">
      <motion.div initial={{ scale: 0.6, rotate: -8 }} animate={{ scale: 1, rotate: 0 }} transition={{ type: 'spring', stiffness: 200 }}>
        <Owl size={120} />
      </motion.div>
      <h1 lang={lang} className="font-display text-4xl font-semibold text-primary">
        {SECTION_NAMES[lang][section]}
      </h1>
      <p lang={lang} className="max-w-xs text-xl">
        {INSTRUCTIONS[lang][section]}
      </p>
      <Button onClick={onStart} className="px-10 py-4 text-xl" disabled={micState === 'requesting'}>
        <span lang={lang}>▶ {START_LABEL[lang]}</span>
      </Button>
      {micState === 'denied' && (
        <p className="max-w-xs rounded-[12px] bg-risk-specialist/10 p-3 text-sm text-risk-specialist">
          Microphone blocked. Allow the microphone for this site in the browser settings, then tap start again.
        </p>
      )}
      {micState === 'unsupported' && (
        <p className="max-w-xs rounded-[12px] bg-risk-specialist/10 p-3 text-sm text-risk-specialist">
          This browser can't record audio. Please use a recent Chrome, Edge or Safari.
        </p>
      )}
    </div>
  )
}

function ItemCard({ step }: { step: Extract<Step, { kind: 'item' }> }) {
  const { item, lang, section } = step
  let body
  if (section === 'E') {
    // The sound game is heard, not read: never show the answer.
    body = (
      <button
        type="button"
        onClick={() => item.prompt && void speak(item.prompt, VOICE[lang])}
        className="flex flex-col items-center gap-3 text-primary"
        aria-label="Hear the question again"
      >
        <span className="text-7xl" aria-hidden>👂</span>
        <span lang={lang} className="font-bold">{lang === 'hi' ? '🔊 फिर से सुनो' : '🔊 Hear it again'}</span>
      </button>
    )
  } else if (section === 'D') {
    body = (
      <p lang={lang} className="text-left text-[26px] leading-[1.9] select-none">
        {item.text}
      </p>
    )
  } else {
    const size = section === 'A' ? '120px' : graphemes(item.text).length <= 4 ? 'clamp(48px, 24vw, 104px)' : 'clamp(40px, 19vw, 88px)'
    body = (
      <span lang={lang} className="font-display font-semibold select-none" style={{ fontSize: size, lineHeight: 1.5 }}>
        {item.text}
      </span>
    )
  }
  return (
    <div className="flex min-h-[240px] flex-col items-center justify-center rounded-[28px] border border-surface-high bg-white p-6 shadow-sm">
      {body}
    </div>
  )
}

function Done({ sessionId, childId, queue, status }: { sessionId: number; childId: number; queue: UploadQueue; status: ReturnType<UploadQueue['status']> }) {
  const [report, setReport] = useState<Report | null>(null)
  const [error, setError] = useState<unknown>(null)

  useEffect(() => {
    let cancelled = false
    queue
      .whenIdle()
      .then(() => api.finishSession(sessionId))
      .then((r) => !cancelled && setReport(r.report))
      .catch((e) => !cancelled && setError(e))
    return () => {
      cancelled = true
    }
  }, [queue, sessionId])

  return (
    <main className="mx-auto flex min-h-dvh max-w-[480px] flex-col items-center justify-center gap-6 px-6 text-center">
      <div className="relative">
        {Array.from({ length: 8 }, (_, i) => (
          <motion.span
            key={i}
            className="absolute left-1/2 top-1/2 text-3xl text-accent"
            initial={{ x: 0, y: 0, opacity: 0 }}
            animate={{ x: Math.cos((i / 8) * 2 * Math.PI) * 110, y: Math.sin((i / 8) * 2 * Math.PI) * 110, opacity: [0, 1, 0.8] }}
            transition={{ duration: 0.9, delay: 0.1 + i * 0.04 }}
          >
            ★
          </motion.span>
        ))}
        <motion.div initial={{ scale: 0.5 }} animate={{ scale: 1 }} transition={{ type: 'spring', stiffness: 180 }}>
          <Owl size={140} />
        </motion.div>
      </div>
      <h1 className="font-display text-4xl font-semibold text-primary">
        <span lang="hi">शाबाश!</span> Well done!
      </h1>
      <p lang="hi" className="text-xl">
        तुमने बहुत अच्छे से पढ़ा।
      </p>

      <div className="mt-6 w-full rounded-[20px] border border-outline/60 bg-white p-4 text-left text-sm">
        <p className="mb-2 font-bold text-ink-muted">For the teacher</p>
        {status.pending > 0 && <Spinner label={`Uploading ${status.pending} clip(s)… keep this page open.`} />}
        {status.failed.length > 0 && (
          <p className="text-risk-specialist">
            {status.failed.length} clip(s) could not be uploaded ({status.failed.map((f) => f.itemId).join(', ')}). They will show as missing in the report.
          </p>
        )}
        {status.pending === 0 && !report && !error && <Spinner label="Scoring and writing the report…" />}
        {error ? <ErrorBox error={error} /> : null}
        {report && (
          <Link to={`/teacher/child/${childId}`} className="mt-2 block">
            <Button className="w-full">Open report →</Button>
          </Link>
        )}
      </div>
    </main>
  )
}
