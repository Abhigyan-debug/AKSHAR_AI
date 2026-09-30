import { CheckIcon, MinusIcon, PauseIcon, PlayIcon, SpeakerSlashIcon, XIcon } from '@phosphor-icons/react'
import { useEffect, useRef, useState } from 'react'
import { fetchAudio, type ErrorLabel, type ItemResult, type Tap, type WordPair } from '../api'
import { diffHeard } from '../lib/diff'
import { ERROR_LABELS } from '../lib/labels'
import { Button } from './ui'

// One shared player so only one clip plays at a time.
let current: HTMLAudioElement | null = null

export function PlayButton({ url }: { url: string | null }) {
  const [playing, setPlaying] = useState(false)
  const ref = useRef<HTMLAudioElement | null>(null)
  useEffect(() => () => ref.current?.pause(), [])
  if (!url)
    return (
      <span className="inline-flex h-9 w-9 shrink-0 items-center justify-center text-ink-muted" title="Audio deleted">
        <SpeakerSlashIcon size={18} aria-label="Audio deleted" />
      </span>
    )
  async function toggle() {
    if (playing && ref.current) {
      ref.current.pause()
      return
    }
    current?.pause()
    setPlaying(true)
    try {
      // Clips need the teacher token, so fetch them and play from a blob URL.
      const src = URL.createObjectURL(await fetchAudio(url!))
      const audio = new Audio(src)
      ref.current = audio
      current = audio
      const done = () => {
        setPlaying(false)
        URL.revokeObjectURL(src)
      }
      audio.onended = audio.onpause = audio.onerror = done
      await audio.play()
    } catch {
      setPlaying(false)
    }
  }
  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={playing ? 'Pause clip' : 'Play clip'}
      className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary-container text-primary hover:bg-primary hover:text-on-primary"
    >
      {playing ? <PauseIcon size={16} weight="fill" /> : <PlayIcon size={16} weight="fill" />}
    </button>
  )
}

export function ErrorPills({ errors }: { errors: ErrorLabel[] }) {
  if (!errors.length) return null
  return (
    <div className="flex flex-wrap gap-1">
      {errors.map((e, i) => (
        <span
          key={i}
          title={e.source === 'llm' ? 'Labelled by AI (rules could not classify it)' : undefined}
          className={`rounded-full border px-2 py-0.5 text-xs ${
            e.type === 'lexicalization'
              ? 'border-primary/40 bg-primary-container font-bold text-on-primary-container'
              : e.low_confidence
                ? 'border-dashed border-outline text-ink-muted'
                : 'border-outline bg-surface-container text-ink'
          }`}
        >
          {ERROR_LABELS[e.type] ?? e.type}
          {e.detail && !e.detail.startsWith('whole word') ? ` ${e.detail}` : ''}
          {e.source === 'llm' ? ' · AI' : ''}
        </span>
      ))}
    </div>
  )
}

/** What was heard, with the parts that differ from the target highlighted. */
export function Heard({ item }: { item: ItemResult }) {
  const lang = item.lang
  if (!item.transcript.trim()) return <span className="text-ink-muted italic">nothing heard</span>
  if (item.section === 'D' && item.pairs.length) return <PassagePairs pairs={item.pairs} lang={lang} />
  if (item.section === 'A' || item.status === 'manual')
    return (
      <span lang={lang} className="text-ink-muted">
        {item.transcript}
      </span>
    )
  const parts = diffHeard(item.text ?? '', item.transcript.replace(/[.,!?।]+$/u, ''))
  return (
    <span lang={lang}>
      {parts.map((p, i) =>
        p.same ? (
          <span key={i}>{p.text}</span>
        ) : (
          <mark key={i} className="rounded bg-accent/35 px-0.5 text-ink">
            {p.text}
          </mark>
        ),
      )}
    </span>
  )
}

function PassagePairs({ pairs, lang }: { pairs: WordPair[]; lang: string }) {
  return (
    <span lang={lang} className="block leading-[2]">
      {pairs.map((p, i) => {
        if (p.kind === 'match') return <span key={i}>{p.target} </span>
        if (p.kind === 'del')
          return (
            <span key={i} title="skipped" className="text-error line-through decoration-2">
              {p.target}{' '}
            </span>
          )
        if (p.kind === 'ins')
          return (
            <span key={i} title="added" className="underline decoration-accent decoration-2">
              {p.heard}{' '}
            </span>
          )
        return (
          <mark key={i} title={`target: ${p.target}`} className="rounded bg-accent/35 px-0.5">
            {p.heard}{' '}
          </mark>
        )
      })}
    </span>
  )
}

export function StatusChip({ item }: { item: ItemResult }) {
  let text: string
  let cls = 'border-outline text-ink-muted'
  if (item.status === 'manual') text = item.live_tap ? 'Live tap' : 'Live tap missing'
  else if (item.awaiting_verification) {
    text = 'Needs your check'
    cls = 'border-accent bg-accent-container text-on-accent font-bold'
  } else if (item.verified) text = 'Teacher-verified'
  else text = 'Auto'
  return <span className={`whitespace-nowrap rounded-full border px-2 py-0.5 text-xs ${cls}`}>{text}</span>
}

export function ResultMark({ item }: { item: ItemResult }) {
  if (item.correct === null) return <span className="font-bold text-ink-muted" title="Waiting for your check">?</span>
  if (item.skipped) return <MinusIcon size={18} className="text-ink-muted" aria-label="Skipped" />
  if (item.section === 'D')
    return (
      <span className="text-sm font-bold whitespace-nowrap">
        {item.words_correct}/{item.words_total}
      </span>
    )
  return item.correct ? (
    <CheckIcon size={18} weight="bold" className="text-primary" aria-label="Correct" />
  ) : (
    <XIcon size={18} weight="bold" className="text-error" aria-label="Incorrect" />
  )
}

/** correct / incorrect / skipped buttons; for the passage, "incorrect" asks for the teacher's word count. */
export function DecisionButtons({
  item,
  onDecide,
  compact,
}: {
  item: ItemResult
  onDecide: (tap: Tap, wordsCorrect?: number) => Promise<void>
  compact?: boolean
}) {
  const [busy, setBusy] = useState(false)
  const [counting, setCounting] = useState(false)
  const [count, setCount] = useState(item.words_correct)
  const size = compact ? 'px-2.5 py-1 text-xs' : 'px-3 py-1.5 text-sm'

  async function decide(tap: Tap, words?: number) {
    setBusy(true)
    try {
      await onDecide(tap, words)
      setCounting(false)
    } finally {
      setBusy(false)
    }
  }

  if (item.section === 'D' && item.status !== 'manual') {
    if (counting)
      return (
        <div className="flex flex-wrap items-center gap-2">
          <label className="text-sm">
            Words read correctly
            <input
              type="number"
              min={0}
              max={item.words_total}
              value={count}
              onChange={(e) => setCount(Math.max(0, Math.min(item.words_total, Number(e.target.value))))}
              className="ml-2 w-20 rounded-[8px] border border-outline px-2 py-1"
            />{' '}
            / {item.words_total}
          </label>
          <Button className={size} disabled={busy} onClick={() => decide('incorrect', count)}>
            Save
          </Button>
          <Button variant="ghost" className={size} onClick={() => setCounting(false)}>
            Cancel
          </Button>
        </div>
      )
    return (
      <div className="flex flex-wrap gap-2">
        <Button variant="secondary" className={size} disabled={busy} onClick={() => decide('correct')}>
          <CheckIcon size={16} weight="bold" aria-hidden /> AI heard it right
        </Button>
        <Button variant="secondary" className={size} disabled={busy} onClick={() => setCounting(true)}>
          <XIcon size={16} weight="bold" aria-hidden /> AI heard it wrong
        </Button>
        <Button variant="ghost" className={size} disabled={busy} onClick={() => decide('skipped')}>
          <MinusIcon size={16} weight="bold" aria-hidden /> Skipped
        </Button>
      </div>
    )
  }
  return (
    <div className="flex flex-wrap gap-2">
      <Button variant="secondary" className={size} disabled={busy} onClick={() => decide('correct')}>
        <CheckIcon size={16} weight="bold" aria-hidden /> Correct
      </Button>
      <Button variant="secondary" className={size} disabled={busy} onClick={() => decide('incorrect')}>
        <XIcon size={16} weight="bold" aria-hidden /> Incorrect
      </Button>
      <Button variant="ghost" className={size} disabled={busy} onClick={() => decide('skipped')}>
        <MinusIcon size={16} weight="bold" aria-hidden /> Skipped
      </Button>
    </div>
  )
}
