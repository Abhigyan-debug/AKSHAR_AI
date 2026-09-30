import { CheckIcon, LockKeyIcon, MinusIcon, StarIcon, XIcon } from '@phosphor-icons/react'
import { motion, useReducedMotion } from 'motion/react'
import type { ReactNode } from 'react'
import type { Tap } from '../api'

/** Friendly owl mascot (inline SVG, no external image). */
export function Owl({ size = 52 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" aria-hidden>
      <circle cx="32" cy="32" r="31" fill="#EDE4F7" />
      <path d="M14 22 L20 12 L26 20 Z M50 22 L44 12 L38 20 Z" fill="#5B3A8E" />
      <ellipse cx="32" cy="36" rx="18" ry="20" fill="#5B3A8E" />
      <ellipse cx="32" cy="42" rx="10" ry="11" fill="#E8A317" />
      <circle cx="24" cy="30" r="7" fill="#fff" />
      <circle cx="40" cy="30" r="7" fill="#fff" />
      <circle cx="25" cy="31" r="3.2" fill="#2A2420" />
      <circle cx="39" cy="31" r="3.2" fill="#2A2420" />
      <circle cx="26" cy="29.8" r="1" fill="#fff" />
      <circle cx="40" cy="29.8" r="1" fill="#fff" />
      <path d="M29 36 L32 40 L35 36 Z" fill="#E8A317" />
    </svg>
  )
}

export function Stars({ total, filled }: { total: number; filled: number }) {
  return (
    <div className="flex items-center gap-0.5 rounded-full border border-outline/60 bg-white px-2.5 py-1" aria-label={`progress ${filled} of ${total}`}>
      {Array.from({ length: total }, (_, i) => (
        <motion.span
          key={i}
          initial={false}
          animate={{ scale: i < filled ? [1.35, 1] : 1 }}
          transition={{ duration: 0.35 }}
          className={`flex ${i < filled ? 'text-accent' : 'text-outline'}`}
        >
          <StarIcon size={15} weight={i < filled ? 'fill' : 'regular'} aria-hidden />
        </motion.span>
      ))}
    </div>
  )
}

export function SpeechBubble({ children }: { children: ReactNode }) {
  return (
    <div className="flex items-center gap-3">
      <Owl />
      <motion.div
        key={String(children)}
        initial={{ opacity: 0, x: -6 }}
        animate={{ opacity: 1, x: 0 }}
        className="relative max-w-[280px] rounded-2xl border border-[#E8C882] bg-accent-container px-4 py-2 font-display text-[17px] font-bold text-on-accent"
      >
        {children}
      </motion.div>
    </div>
  )
}

const MicIcon = () => (
  <svg width="44" height="44" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
    <path d="M12 14a3 3 0 0 0 3-3V5a3 3 0 1 0-6 0v6a3 3 0 0 0 3 3Zm5-3a5 5 0 0 1-10 0H5a7 7 0 0 0 6 6.92V21h2v-3.08A7 7 0 0 0 19 11h-2Z" />
  </svg>
)

/** 120px mic button; the ring follows the voice level while listening. */
export function MicButton({
  listening,
  level,
  disabled,
  onClick,
  label,
}: {
  listening: boolean
  level: number
  disabled?: boolean
  onClick: () => void
  label: string
}) {
  const reduce = useReducedMotion()
  return (
    <div className="relative flex h-40 w-40 items-center justify-center">
      {listening && (
        <motion.span
          className="absolute inset-0 rounded-full bg-primary-container"
          animate={reduce ? { opacity: 0.8 } : { scale: 0.8 + level * 0.35, opacity: 0.9 }}
          transition={{ type: 'spring', stiffness: 300, damping: 20 }}
        />
      )}
      {listening && !reduce && (
        <motion.span
          className="absolute inset-3 rounded-full border-4 border-primary/25"
          animate={{ scale: [1, 1.25], opacity: [0.6, 0] }}
          transition={{ duration: 1.6, repeat: Infinity, ease: 'easeOut' }}
        />
      )}
      <motion.button
        type="button"
        onClick={onClick}
        disabled={disabled}
        whileTap={{ scale: 0.93 }}
        aria-label={label}
        className="relative z-10 flex h-[120px] w-[120px] items-center justify-center rounded-full bg-primary text-on-primary shadow-md disabled:opacity-50"
      >
        {listening ? (
          <span className="h-9 w-9 rounded-md bg-white" aria-hidden />
        ) : (
          <MicIcon />
        )}
      </motion.button>
    </div>
  )
}

/** Teacher live tap: small and neutral so the child doesn't read it as feedback. */
export function LiveTapStrip({ onTap, disabled, highlight }: { onTap: (t: Tap) => void; disabled?: boolean; highlight?: boolean }) {
  const btn =
    'inline-flex items-center gap-1 whitespace-nowrap rounded-full border border-outline/60 px-2.5 py-1.5 text-xs font-bold text-ink-muted transition-colors active:scale-95 disabled:opacity-40'
  return (
    <div
      className={`flex items-center justify-between gap-2 border-t border-outline/40 px-3 py-2 transition-colors ${
        highlight ? 'bg-accent-container' : 'bg-surface-container/95'
      }`}
    >
      <span className="flex items-center gap-1 text-[11px] font-bold whitespace-nowrap text-ink-muted" title="Teacher">
        <LockKeyIcon size={13} aria-hidden /> शिक्षक
      </span>
      <div className="flex gap-1.5">
        <button type="button" disabled={disabled} className={`${btn} hover:border-risk-low hover:text-risk-low`} onClick={() => onTap('correct')}>
          <CheckIcon size={13} weight="bold" aria-hidden /> Correct
        </button>
        <button type="button" disabled={disabled} className={`${btn} hover:border-risk-specialist hover:text-risk-specialist`} onClick={() => onTap('incorrect')}>
          <XIcon size={13} weight="bold" aria-hidden /> Incorrect
        </button>
        <button type="button" disabled={disabled} className={`${btn} hover:border-risk-pending`} onClick={() => onTap('skipped')}>
          <MinusIcon size={13} weight="bold" aria-hidden /> Skipped
        </button>
      </div>
    </div>
  )
}
