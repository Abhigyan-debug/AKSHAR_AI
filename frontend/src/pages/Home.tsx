import {
  ArrowRightIcon,
  ChalkboardTeacherIcon,
  FingerprintIcon,
  HardDrivesIcon,
  LockKeyIcon,
  MicrophoneIcon,
  ScalesIcon,
  SealCheckIcon,
  WaveformIcon,
} from '@phosphor-icons/react'
import { AnimatePresence, motion, useInView, useReducedMotion } from 'motion/react'
import { useEffect, useRef, useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import type { RiskLevel } from '../api'
import { Owl } from '../components/child'
import { RiskBadge } from '../components/ui'
import { diffHeard } from '../lib/diff'
import { RISK } from '../lib/labels'

const EASE = [0.16, 1, 0.3, 1] as const

// Real examples from Akshar's rule engine (see docs/scoring.md).
const SAMPLES = [
  { lang: 'hi', target: 'पमीर', heard: 'पनीर', label: 'Made-up word read as a real word' },
  { lang: 'hi', target: 'मीठा', heard: 'मिठा', label: 'Long ी read as short ि' },
  { lang: 'en', target: 'bed', heard: 'ded', label: 'b read as d' },
] as const

export default function Home() {
  return (
    <div className="overflow-x-clip">
      <Nav />
      <main>
        <Hero />
        <Listens />
        <TwoLanguages />
        <HowItWorks />
        <Privacy />
        <Closing />
      </main>
      <footer className="border-t border-outline/50">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-4 py-8 text-sm text-ink-muted md:px-8">
          <span className="flex items-center gap-2">
            <Owl size={24} /> Akshar, built for the AI with Education hackathon.
          </span>
          <span>Screener, not a diagnosis. Thresholds are illustrative.</span>
        </div>
      </footer>
    </div>
  )
}

function Nav() {
  const links = [
    { href: '#listens', label: 'What it hears' },
    { href: '#how', label: 'How it works' },
    { href: '#privacy', label: 'Privacy' },
    { href: '/practice', label: 'Practice games' },
  ]
  return (
    <header className="sticky top-0 z-20 border-b border-outline/40 bg-surface/85 backdrop-blur-sm">
      <div className="mx-auto flex h-16 max-w-7xl items-center gap-8 px-4 md:px-8">
        <Link to="/" className="flex items-center gap-2.5">
          <Owl size={34} />
          <span className="font-display text-xl font-semibold text-primary">Akshar</span>
        </Link>
        <nav aria-label="Page" className="hidden gap-6 text-sm font-bold text-ink-muted md:flex">
          {links.map((l) => (
            <a key={l.href} href={l.href} className="hover:text-ink">
              {l.label}
            </a>
          ))}
        </nav>
        <Link
          to="/login"
          className="ml-auto inline-flex items-center gap-2 rounded-[12px] border border-primary px-4 py-2 text-sm font-bold whitespace-nowrap text-primary hover:bg-primary-container"
        >
          <LockKeyIcon size={16} aria-hidden /> Teacher sign in
        </Link>
      </div>
    </header>
  )
}

function Hero() {
  const reduce = useReducedMotion()
  const rise = (delay: number) =>
    reduce ? {} : { initial: { opacity: 0, y: 16 }, animate: { opacity: 1, y: 0 }, transition: { duration: 0.6, delay, ease: EASE } }
  return (
    <section className="mx-auto grid max-w-7xl items-center gap-12 px-4 pt-12 pb-20 md:px-8 md:pt-20 lg:grid-cols-[1.05fr_0.95fr]">
      <div>
        <motion.h1 {...rise(0)} className="font-display text-5xl leading-[1.05] font-semibold tracking-[-0.02em] text-balance md:text-6xl">
          Hear the child, <span className="text-primary">not the label.</span>
        </motion.h1>
        <motion.p {...rise(0.08)} className="mt-6 max-w-[46ch] text-lg leading-relaxed text-ink-muted md:text-xl">
          A ten-minute read-aloud check in Hindi and English that shows teachers which children need reading support.
        </motion.p>
        <motion.div {...rise(0.16)} className="mt-8 flex flex-wrap gap-3">
          <Link
            to="/child"
            className="group inline-flex items-center gap-2 rounded-[12px] bg-primary px-6 py-3.5 text-lg font-bold text-on-primary shadow-[0_6px_20px_rgba(91,58,142,0.28)] hover:bg-primary/90 active:scale-[0.98]"
          >
            <MicrophoneIcon size={22} weight="fill" aria-hidden />
            Start screening
            <ArrowRightIcon size={18} className="transition-transform duration-150 group-hover:translate-x-0.5" aria-hidden />
          </Link>
          <a href="#how" className="inline-flex items-center rounded-[12px] px-5 py-3.5 text-lg font-bold text-ink hover:bg-surface-container">
            How it works
          </a>
        </motion.div>
      </div>
      <LiveDemo />
    </section>
  )
}

/** The focal moment: a real reading card listening, then showing what it heard. */
function LiveDemo() {
  const reduce = useReducedMotion()
  const ref = useRef<HTMLDivElement>(null)
  const inView = useInView(ref, { amount: 0.4 })
  const [i, setI] = useState(0)
  const [phase, setPhase] = useState<'listen' | 'heard'>(reduce ? 'heard' : 'listen')

  useEffect(() => {
    if (reduce || !inView) return
    const timers: number[] = []
    const run = () => {
      setPhase('listen')
      timers.push(window.setTimeout(() => setPhase('heard'), 1500))
      timers.push(window.setTimeout(() => setI((n) => (n + 1) % SAMPLES.length), 4200))
    }
    run()
    return () => timers.forEach(clearTimeout)
  }, [i, inView, reduce])

  const s = SAMPLES[i]
  return (
    <div ref={ref}>
      <div className="relative mx-auto w-full max-w-md rounded-[28px] border border-outline/60 bg-white p-6 shadow-[0_24px_60px_rgba(91,58,142,0.14)] md:p-8">
        <div className="mb-5 flex items-center justify-between">
          <span className="inline-flex items-center gap-2 rounded-full border border-outline/60 px-3 py-1 text-sm font-bold">
            <span lang={s.lang}>{s.lang === 'hi' ? 'हिंदी' : 'English'}</span>
          </span>
          <Owl size={40} />
        </div>
        <div className="flex min-h-[150px] items-center justify-center">
          <AnimatePresence mode="wait">
            <motion.span
              key={s.target}
              lang={s.lang}
              initial={reduce ? false : { opacity: 0, y: 12, filter: 'blur(6px)' }}
              animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
              exit={{ opacity: 0, y: -12, filter: 'blur(6px)', transition: { duration: 0.2 } }}
              transition={{ duration: 0.45, ease: EASE }}
              className="font-display text-[88px] leading-[1.4] font-semibold"
            >
              {s.target}
            </motion.span>
          </AnimatePresence>
        </div>
        <div className="mt-4 flex min-h-[92px] items-center justify-center">
          <AnimatePresence mode="wait">
            {phase === 'listen' ? (
              <motion.div key="listen" exit={{ opacity: 0, scale: 0.9, transition: { duration: 0.15 } }} className="relative flex h-16 w-16 items-center justify-center">
                <motion.span
                  className="absolute inset-0 rounded-full bg-primary-container"
                  animate={{ scale: [1, 1.35, 1], opacity: [0.9, 0.35, 0.9] }}
                  transition={{ duration: 1.2, repeat: Infinity, ease: 'easeInOut' }}
                />
                <span className="relative flex h-14 w-14 items-center justify-center rounded-full bg-primary text-on-primary">
                  <MicrophoneIcon size={26} weight="fill" aria-hidden />
                </span>
              </motion.div>
            ) : (
              <motion.div
                key={`heard-${s.target}`}
                initial={reduce ? false : { opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, transition: { duration: 0.15 } }}
                transition={{ duration: 0.35, ease: EASE }}
                className="w-full text-center"
              >
                <p className="text-sm text-ink-muted">
                  Heard{' '}
                  <span lang={s.lang} className="font-display text-2xl text-ink">
                    {diffHeard(s.target, s.heard).map((p, k) =>
                      p.same ? (
                        <span key={k}>{p.text}</span>
                      ) : (
                        <mark key={k} className="rounded bg-accent/40 px-0.5 text-ink">
                          {p.text}
                        </mark>
                      ),
                    )}
                  </span>
                </p>
                <motion.span
                  initial={reduce ? false : { opacity: 0, scale: 0.9 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ delay: 0.2, duration: 0.25, ease: EASE }}
                  className="mt-3 inline-block rounded-full border border-primary/30 bg-primary-container px-3 py-1 text-sm font-bold text-on-primary-container"
                >
                  {s.label}
                </motion.span>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
      <p className="mt-4 text-center text-sm text-ink-muted">What the teacher sees after a child reads one item.</p>
    </div>
  )
}

function Reveal({ children, delay = 0, className = '' }: { children: ReactNode; delay?: number; className?: string }) {
  const reduce = useReducedMotion()
  return (
    <motion.div
      className={className}
      initial={reduce ? false : { opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.3 }}
      transition={{ duration: 0.55, delay, ease: EASE }}
    >
      {children}
    </motion.div>
  )
}

function Example({ lang, target, heard, onDark, big }: { lang: string; target: string; heard: string; onDark?: boolean; big?: boolean }) {
  return (
    <p lang={lang} className={`font-display ${big ? 'text-5xl md:text-6xl' : 'text-3xl'} ${onDark ? 'text-on-primary' : 'text-ink'}`}>
      {target}
      <ArrowRightIcon size={22} className={`mx-3 inline align-middle ${onDark ? 'text-accent' : 'text-ink-muted'}`} aria-label="read as" />
      {diffHeard(target, heard).map((p, k) =>
        p.same ? (
          <span key={k}>{p.text}</span>
        ) : (
          <mark key={k} className={`rounded px-0.5 ${onDark ? 'bg-accent text-on-accent' : 'bg-accent/40 text-ink'}`}>
            {p.text}
          </mark>
        ),
      )}
    </p>
  )
}

function Listens() {
  return (
    <section id="listens" className="mx-auto max-w-7xl scroll-mt-20 px-4 py-20 md:px-8">
      <h2 className="max-w-[22ch] font-display text-4xl leading-tight font-semibold tracking-[-0.02em] md:text-5xl">
        It listens for how a child gets a word wrong.
      </h2>
      <p className="mt-4 max-w-[60ch] text-lg text-ink-muted">
        Fluency apps count mistakes. Akshar sorts them into the patterns reading research looks for, in Devanagari aksharas as well as English
        letters.
      </p>
      <div className="mt-12 grid gap-4 md:grid-cols-4 md:grid-rows-2">
        <Reveal className="flex flex-col justify-between gap-10 rounded-[20px] bg-primary p-8 text-on-primary md:col-span-2 md:row-span-2">
          <Example lang="hi" target="पमीर" heard="पनीर" onDark big />
          <div>
          <h3 className="font-display text-2xl font-semibold">Made-up words read as real ones</h3>
          <p className="mt-3 max-w-[40ch] text-on-primary/80">
            A made-up word can't be remembered, only decoded. When a child turns it into a familiar word, Akshar gives that the most weight.
          </p>
          </div>
        </Reveal>
        <Reveal delay={0.05} className="rounded-[20px] bg-accent-container p-6">
          <Example lang="hi" target="मीठा" heard="मिठा" />
          <h3 className="mt-5 font-display text-lg font-semibold">Vowel signs swapped</h3>
          <p className="mt-1 text-ink-muted">Long and short matras confused.</p>
        </Reveal>
        <Reveal delay={0.1} className="rounded-[20px] border border-outline/60 bg-white p-6">
          <Example lang="hi" target="खाना" heard="काना" />
          <h3 className="mt-5 font-display text-lg font-semibold">Breathy sounds dropped</h3>
          <p className="mt-1 text-ink-muted">Aspirated letters read plain.</p>
        </Reveal>
        <Reveal delay={0.15} className="rounded-[20px] bg-primary-container p-6">
          <Example lang="en" target="bed" heard="ded" />
          <h3 className="mt-5 font-display text-lg font-semibold">Mirror letters</h3>
          <p className="mt-1 text-on-primary-container/80">b and d, p and q, was and saw.</p>
        </Reveal>
        <Reveal delay={0.2} className="rounded-[20px] bg-surface-container p-6">
          <WaveformIcon size={34} className="text-primary" aria-hidden />
          <h3 className="mt-5 font-display text-lg font-semibold">Pauses and slow starts</h3>
          <p className="mt-1 text-ink-muted">Timed from the recording itself, so they count even when speech recognition is unsure.</p>
        </Reveal>
      </div>
    </section>
  )
}

function TwoLanguages() {
  const cell = (level: RiskLevel, note: string) => (
    <div className="flex flex-col justify-between gap-6 rounded-[16px] bg-white p-5">
      <RiskBadge level={level} label={RISK[level].short} />
      <p className="text-ink-muted">{note}</p>
    </div>
  )
  return (
    <section className="bg-surface-container">
      <div className="mx-auto grid max-w-7xl gap-12 px-4 py-20 md:px-8 lg:grid-cols-[0.8fr_1.2fr] lg:items-center">
        <div>
          <h2 className="font-display text-4xl leading-tight font-semibold tracking-[-0.02em]">Two languages give a fairer answer.</h2>
          <p className="mt-4 max-w-[48ch] text-lg text-ink-muted">
            Most children here learn to read in two scripts. A child who struggles only in English usually needs more English, not a
            specialist. Akshar checks both before it says anything.
          </p>
        </div>
        <div>
          <div className="mb-3 grid grid-cols-[auto_1fr_1fr] items-end gap-3 text-sm font-bold text-ink-muted">
            <span className="w-20" />
            <span>English on track</span>
            <span>English weak</span>
          </div>
          <div className="grid grid-cols-[auto_1fr_1fr] gap-3">
            <span className="flex w-20 items-center text-sm font-bold text-ink-muted">Hindi on track</span>
            {cell('low_risk', 'Reading well in both.')}
            {cell('english_exposure_gap', 'Needs English practice, not a reading label.')}
            <span className="flex w-20 items-center text-sm font-bold text-ink-muted">Hindi weak</span>
            {cell('hindi_support', 'Check the home language first.')}
            <div className="flex flex-col gap-3 rounded-[16px] bg-white p-5">
              <RiskBadge level="reading_support" label={RISK.reading_support.short} />
              <RiskBadge level="specialist_check" label={RISK.specialist_check.short} />
              <p className="text-ink-muted">Specialist only when the error pattern shows up in both languages.</p>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}

function HowItWorks() {
  const moments = [
    {
      icon: MicrophoneIcon,
      title: 'The child reads aloud',
      body: 'One item at a time on any phone: letters, words, made-up words and a short story, first in Hindi, then in English. No scores on screen.',
    },
    {
      icon: WaveformIcon,
      title: 'Akshar finds the pattern',
      body: 'Speech recognition writes down what was said. Rules compare it to the target akshara by akshara. Anything the AI is unsure about goes to the teacher, not into the result.',
    },
    {
      icon: ChalkboardTeacherIcon,
      title: 'The teacher confirms, the parent hears',
      body: 'Each flag links to the recording. The teacher gets the evidence, and the parent gets a warm summary in Hindi, read aloud on their phone.',
    },
  ]
  return (
    <section id="how" className="mx-auto grid max-w-7xl scroll-mt-20 gap-12 px-4 py-20 md:px-8 lg:grid-cols-[0.8fr_1.2fr]">
      <div className="lg:sticky lg:top-28 lg:self-start">
        <h2 className="font-display text-4xl leading-tight font-semibold tracking-[-0.02em]">About ten minutes per child.</h2>
        <p className="mt-4 max-w-[40ch] text-lg text-ink-muted">A teacher with a phone is all it needs. No trained assessor, no printed test.</p>
      </div>
      <ol className="space-y-4">
        {moments.map((m, i) => (
          <Reveal key={m.title} delay={i * 0.05}>
            <li className="flex gap-5 rounded-[20px] border border-outline/60 bg-white p-6">
              <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-[14px] bg-primary-container text-primary">
                <m.icon size={26} weight="duotone" aria-hidden />
              </span>
              <div>
                <h3 className="font-display text-xl font-semibold">{m.title}</h3>
                <p className="mt-2 max-w-[60ch] text-ink-muted">{m.body}</p>
              </div>
            </li>
          </Reveal>
        ))}
      </ol>
    </section>
  )
}

function Privacy() {
  const points = [
    { icon: ScalesIcon, title: 'A screener, not a diagnosis', body: 'Akshar never says “dyslexic”. It says who may need support or a specialist check.' },
    { icon: FingerprintIcon, title: 'Codes, not names', body: 'Children are known only by a code the teacher picks. Parent links show no code at all.' },
    { icon: HardDrivesIcon, title: 'Recordings stay with the school', body: 'Audio is stored on the school’s own server, and a teacher can delete it at any time.' },
    { icon: LockKeyIcon, title: 'Teachers sign in', body: 'Reports and recordings need the school PIN. Parents only see their own child’s page.' },
    { icon: SealCheckIcon, title: 'Honest about its limits', body: 'Cut-offs are illustrative and not clinically validated. They should be tuned on real classrooms.' },
  ]
  return (
    <section id="privacy" className="scroll-mt-20 border-y border-outline/50 bg-white">
      <div className="mx-auto max-w-7xl px-4 py-20 md:px-8">
        <ul className="grid gap-x-12 gap-y-10 md:grid-cols-2 lg:grid-cols-3">
          <li>
            <h2 className="max-w-[14ch] font-display text-4xl leading-tight font-semibold tracking-[-0.02em]">Built to protect the child first.</h2>
          </li>
          {points.map((p) => (
            <li key={p.title} className="flex gap-4">
              <p.icon size={28} weight="duotone" className="shrink-0 text-primary" aria-hidden />
              <div>
                <h3 className="font-display text-lg font-semibold">{p.title}</h3>
                <p className="mt-1 text-ink-muted">{p.body}</p>
              </div>
            </li>
          ))}
        </ul>
      </div>
    </section>
  )
}

function Closing() {
  return (
    <section className="mx-auto max-w-7xl px-4 py-24 md:px-8">
      <Reveal className="flex flex-col items-start justify-between gap-8 rounded-[28px] bg-accent-container p-10 md:flex-row md:items-center md:p-14">
        <div>
          <h2 className="font-display text-4xl leading-tight font-semibold tracking-[-0.02em]">Ready when your class is.</h2>
          <p className="mt-3 max-w-[48ch] text-lg text-ink-muted">Sign in with the school PIN, pick a child code and hand over the phone.</p>
        </div>
        <Link
          to="/child"
          className="group inline-flex shrink-0 items-center gap-2 rounded-[12px] bg-primary px-6 py-3.5 text-lg font-bold text-on-primary hover:bg-primary/90 active:scale-[0.98]"
        >
          <MicrophoneIcon size={22} weight="fill" aria-hidden />
          Start screening
          <ArrowRightIcon size={18} className="transition-transform duration-150 group-hover:translate-x-0.5" aria-hidden />
        </Link>
      </Reveal>
    </section>
  )
}
