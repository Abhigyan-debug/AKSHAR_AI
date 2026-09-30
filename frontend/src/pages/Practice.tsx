import {
  ArrowLeftIcon,
  BookOpenTextIcon,
  EarIcon,
  PuzzlePieceIcon,
  SparkleIcon,
  StarIcon,
  TextAaIcon,
  UsersIcon,
  WindIcon,
  XIcon,
} from '@phosphor-icons/react'
import { AnimatePresence, motion, useReducedMotion } from 'motion/react'
import { useCallback, useEffect, useMemo, useState, type ComponentType } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api'
import { Owl } from '../components/child'
import { ErrorBox, Spinner } from '../components/ui'
import { findVoice, stopSpeaking } from '../lib/speech'
import { loadProgress, saveProgress } from '../practice/engine'
import { BreathGame, BuilderGame, MatraGame, MirrorGame, ReadAlongGame, TwinsGame, type GameProps } from '../practice/Games'
import { GAME_ORDER, GAMES, type GameId, type PracticeContent } from '../practice/meta'

const ICONS: Record<GameId, ComponentType<{ size?: number; weight?: 'duotone' | 'fill' | 'regular' }>> = {
  matra: EarIcon,
  breath: WindIcon,
  twins: TextAaIcon,
  builder: PuzzlePieceIcon,
  mirror: SparkleIcon,
  readalong: BookOpenTextIcon,
}
const EASE = [0.16, 1, 0.3, 1] as const

// Practice games (see docs/practice.md). /practice shows every game; /practice/:token (the
// parent link's token) puts the child's own error pattern first. No login.
export default function Practice() {
  const { token } = useParams()
  const [content, setContent] = useState<PracticeContent | null>(null)
  const [recommended, setRecommended] = useState<GameId[]>([])
  const [error, setError] = useState<unknown>(null)
  const [voices, setVoices] = useState<{ hi: boolean; en: boolean }>({ hi: true, en: true })
  const [playing, setPlaying] = useState<GameId | null>(null)
  const scope = token ?? 'demo'
  const [progress, setProgress] = useState(() => loadProgress(scope))

  useEffect(() => {
    api.practice().then(setContent).catch(setError)
    Promise.all([findVoice('hi-IN'), findVoice('en-IN')]).then(([hi, en]) => setVoices({ hi: !!hi, en: !!en }))
  }, [])
  useEffect(() => {
    if (!token) return
    api
      .parent(token)
      .then((p) => setRecommended((p.practice ?? []).filter((g): g is GameId => g in GAMES)))
      .catch(() => setRecommended([]))
  }, [token])

  const ordered = useMemo(() => [...recommended, ...GAME_ORDER.filter((g) => !recommended.includes(g))], [recommended])

  if (error) return <main className="p-6"><ErrorBox error={error} /></main>
  if (!content) return <main className="p-6"><Spinner label="खेल आ रहे हैं" /></main>

  if (playing)
    return (
      <Session
        game={playing}
        content={content}
        preferLang={recommended.includes('mirror') && !recommended.includes('matra') ? 'en' : 'hi'}
        hasVoice={voices[GAMES[playing].lang]}
        onExit={(stars) => {
          if (stars !== null) {
            saveProgress(scope, playing, stars)
            setProgress(loadProgress(scope))
          }
          stopSpeaking()
          setPlaying(null)
        }}
      />
    )

  return (
    <main lang="hi" className="mx-auto max-w-3xl px-4 pt-6 pb-12">
      <header className="mb-6 flex items-center gap-3">
        <Owl size={52} />
        <div>
          <h1 className="font-display text-3xl font-semibold text-primary">अभ्यास के खेल</h1>
          <p className="text-ink-muted">रोज़ 5 मिनट, किसी बड़े के साथ बैठकर</p>
        </div>
      </header>

      <div className="mb-6 flex items-start gap-3 rounded-[16px] bg-accent-container p-4">
        <UsersIcon size={24} className="mt-0.5 shrink-0 text-on-accent" weight="duotone" aria-hidden />
        <p className="text-[17px] leading-[1.7] text-on-accent">
          बच्चे के साथ बैठकर खेलें। बड़े साथ हों तो ऐसे खेलों से ज़्यादा फ़ायदा होता है। हर खेल से पहले आपके लिए एक छोटी सलाह है।
        </p>
      </div>

      {recommended.length > 0 && (
        <h2 className="mb-3 font-display text-xl font-semibold">आपके बच्चे के लिए सबसे पहले</h2>
      )}
      <ul className="grid gap-3 sm:grid-cols-2">
        {ordered.map((id, i) => {
          const g = GAMES[id]
          const Icon = ICONS[id]
          const mine = recommended.includes(id)
          const p = progress[id]
          return (
            <motion.li key={id} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.04, duration: 0.3, ease: EASE }}>
              <button
                type="button"
                onClick={() => setPlaying(id)}
                className={`flex h-full w-full items-start gap-4 rounded-[20px] border-2 p-5 text-left transition-colors hover:border-primary active:scale-[0.99] ${
                  mine ? 'border-primary/40 bg-primary-container/60' : 'border-outline/60 bg-white'
                }`}
              >
                <span className={`flex h-14 w-14 shrink-0 items-center justify-center rounded-[16px] ${mine ? 'bg-primary text-on-primary' : 'bg-surface-container text-primary'}`}>
                  <Icon size={30} weight="duotone" />
                </span>
                <span className="min-w-0">
                  <span lang={g.lang} className="block font-display text-xl font-semibold">
                    {g.title}
                  </span>
                  <span className="mt-1 block text-ink-muted">{g.practises}</span>
                  <span className="mt-2 flex items-center gap-3 text-sm">
                    {mine && <span className="rounded-full bg-primary px-2.5 py-0.5 font-bold text-on-primary">आपके लिए</span>}
                    {p && (
                      <span className="tabular flex items-center gap-1 text-ink-muted">
                        <StarIcon size={14} weight="fill" className="text-accent" aria-hidden /> {p.stars}
                        <span className="sr-only">तारे</span>, {p.plays} बार खेला
                      </span>
                    )}
                  </span>
                </span>
              </button>
            </motion.li>
          )
        })}
      </ul>

      {!voices.hi && (
        <p className="mt-6 text-sm text-ink-muted">
          इस फ़ोन में हिंदी आवाज़ नहीं मिली। खेलों में शब्द बड़े पढ़कर सुनाएँगे, इसके लिए हर खेल में "दबाकर शब्द देखें" बटन है।
        </p>
      )}
      <p className="mt-8 text-center text-sm text-ink-muted">
        ये खेल अभ्यास के लिए हैं, जाँच के लिए नहीं। इनमें जाँच वाले शब्द कभी नहीं आते।
      </p>
      {token && (
        <p className="mt-4 text-center">
          <Link to={`/p/${token}`} className="font-bold text-primary">
            वापस रिपोर्ट पर
          </Link>
        </p>
      )}
    </main>
  )
}

function Session({
  game,
  content,
  preferLang,
  hasVoice,
  onExit,
}: {
  game: GameId
  content: PracticeContent
  preferLang: 'hi' | 'en'
  hasVoice: boolean
  onExit: (stars: number | null) => void
}) {
  const reduce = useReducedMotion()
  const meta = GAMES[game]
  const [stage, setStage] = useState<'intro' | 'play' | 'done'>('intro')
  const [adultVoice, setAdultVoice] = useState(!hasVoice)
  const [progress, setProgress] = useState({ done: 0, total: 1 })
  const [stars, setStars] = useState(0)

  const onProgress = useCallback((done: number, total: number) => setProgress({ done, total }), [])
  const onDone = useCallback((s: number) => {
    setStars(s)
    setStage('done')
  }, [])
  const props: GameProps & { content: PracticeContent } = { content, adultVoice, onProgress, onDone }

  return (
    <main lang="hi" className="mx-auto flex min-h-dvh max-w-[560px] flex-col px-4 pb-8">
      <header className="flex items-center gap-3 py-3">
        <button type="button" onClick={() => onExit(null)} aria-label="खेल बंद करें" className="flex h-11 w-11 items-center justify-center rounded-full bg-surface-container">
          <XIcon size={20} aria-hidden />
        </button>
        <span lang={meta.lang} className="font-display text-lg font-semibold">
          {meta.title}
        </span>
        {stage === 'play' && (
          <div className="ml-auto h-2.5 w-28 overflow-hidden rounded-full bg-surface-high" role="progressbar" aria-valuemin={0} aria-valuemax={progress.total} aria-valuenow={progress.done}>
            <motion.div className="h-full rounded-full bg-accent" animate={{ width: `${(progress.done / progress.total) * 100}%` }} transition={{ duration: 0.3, ease: EASE }} />
          </div>
        )}
      </header>

      <AnimatePresence mode="wait">
        {stage === 'intro' && (
          <motion.section key="intro" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="flex flex-1 flex-col justify-center gap-6">
            <div className="flex items-center gap-3">
              <Owl size={64} />
              <p lang={meta.lang} className="font-display text-2xl font-semibold">
                {meta.childLine}
              </p>
            </div>
            <div className="rounded-[20px] border border-outline/60 bg-white p-5">
              <p className="mb-1 text-sm font-bold text-ink-muted">बड़ों के लिए</p>
              <p className="text-[17px] leading-[1.7]">{meta.adultTip}</p>
            </div>
            {game !== 'twins' && (
              <label className="flex items-start gap-3 rounded-[16px] bg-surface-container p-4">
                <input type="checkbox" className="mt-1 h-5 w-5 accent-primary" checked={adultVoice} onChange={(e) => setAdultVoice(e.target.checked)} />
                <span>
                  <span className="block font-bold">शब्द बड़े पढ़कर सुनाएँगे</span>
                  <span className="text-sm text-ink-muted">
                    {hasVoice ? 'फ़ोन की आवाज़ की जगह आप खुद बोलें।' : 'इस फ़ोन में यह भाषा की आवाज़ नहीं है, इसलिए यह चालू है।'}
                  </span>
                </span>
              </label>
            )}
            <button
              type="button"
              onClick={() => setStage('play')}
              className="rounded-[16px] bg-primary px-6 py-4 font-display text-xl font-semibold text-on-primary active:scale-[0.98]"
            >
              खेल शुरू करो
            </button>
          </motion.section>
        )}

        {stage === 'play' && (
          <motion.section key="play" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="flex flex-1 flex-col justify-center py-4">
            {game === 'matra' && <MatraGame {...props} />}
            {game === 'breath' && <BreathGame {...props} />}
            {game === 'twins' && <TwinsGame {...props} />}
            {game === 'builder' && <BuilderGame {...props} />}
            {game === 'mirror' && <MirrorGame {...props} />}
            {game === 'readalong' && <ReadAlongGame {...props} preferLang={preferLang} />}
          </motion.section>
        )}

        {stage === 'done' && (
          <motion.section key="done" initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex flex-1 flex-col items-center justify-center gap-6 text-center">
            <div className="flex gap-1" aria-label={`${stars} तारे`}>
              {Array.from({ length: game === 'readalong' ? 3 : 5 }, (_, i) => (
                <motion.span
                  key={i}
                  initial={reduce ? false : { scale: 0, rotate: -30 }}
                  animate={{ scale: 1, rotate: 0 }}
                  transition={{ delay: 0.15 + i * 0.1, type: 'spring', stiffness: 300, damping: 15 }}
                  className={i < stars ? 'text-accent' : 'text-outline'}
                >
                  <StarIcon size={44} weight={i < stars ? 'fill' : 'regular'} aria-hidden />
                </motion.span>
              ))}
            </div>
            <h2 className="font-display text-4xl font-semibold text-primary">शाबाश!</h2>
            <div className="w-full rounded-[20px] border border-outline/60 bg-white p-5 text-left">
              <p className="mb-1 text-sm font-bold text-ink-muted">बड़ों के लिए: आज फ़ोन के बिना</p>
              <p className="text-[17px] leading-[1.7]">{meta.followUp}</p>
            </div>
            <div className="flex w-full gap-3">
              <button type="button" onClick={() => setStage('intro')} className="flex-1 rounded-[16px] border-2 border-primary px-4 py-3 font-bold text-primary">
                फिर खेलें
              </button>
              <button type="button" onClick={() => onExit(stars)} className="flex flex-1 items-center justify-center gap-2 rounded-[16px] bg-primary px-4 py-3 font-bold text-on-primary">
                <ArrowLeftIcon size={18} aria-hidden /> सारे खेल
              </button>
            </div>
          </motion.section>
        )}
      </AnimatePresence>
    </main>
  )
}
