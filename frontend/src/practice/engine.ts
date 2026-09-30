import { useCallback, useRef, useState } from 'react'
import type { GameId } from './meta'

export function shuffle<T>(xs: readonly T[]): T[] {
  const a = [...xs]
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1))
    ;[a[i], a[j]] = [a[j], a[i]]
  }
  return a
}

export function pick<T>(xs: readonly T[]): T {
  return xs[Math.floor(Math.random() * xs.length)]
}

/**
 * Adaptive difficulty in the GraphoGame style: keep the child mostly succeeding.
 * Start with 2 choices; three first-try successes in a row add a choice (up to
 * `max`); two misses in a row take one away.
 */
export function useAdaptive(min = 2, max = 4) {
  const [choices, setChoices] = useState(min)
  const streak = useRef(0)
  const misses = useRef(0)
  const record = useCallback(
    (firstTry: boolean) => {
      if (firstTry) {
        misses.current = 0
        streak.current += 1
        if (streak.current >= 3) {
          streak.current = 0
          setChoices((c) => Math.min(max, c + 1))
        }
      } else {
        streak.current = 0
        misses.current += 1
        if (misses.current >= 2) {
          misses.current = 0
          setChoices((c) => Math.max(min, c - 1))
        }
      }
    },
    [min, max],
  )
  return { choices, record }
}

// Progress is a per-device convenience (which games were played, stars), so it
// lives in localStorage and every access tolerates storage being unavailable.
export interface GameProgress {
  plays: number
  stars: number
  last: string
}

function storageKey(scope: string) {
  return `akshar.practice.${scope}`
}

export function loadProgress(scope: string): Partial<Record<GameId, GameProgress>> {
  try {
    return JSON.parse(localStorage.getItem(storageKey(scope)) ?? '{}')
  } catch {
    return {}
  }
}

export function saveProgress(scope: string, game: GameId, stars: number) {
  try {
    const all = loadProgress(scope)
    const prev = all[game]
    all[game] = { plays: (prev?.plays ?? 0) + 1, stars: (prev?.stars ?? 0) + stars, last: new Date().toISOString().slice(0, 10) }
    localStorage.setItem(storageKey(scope), JSON.stringify(all))
  } catch {
    /* progress just isn't remembered on this device */
  }
}

/** A short, soft two-note chime for a correct answer. Silent if audio is unavailable. */
let ctx: AudioContext | null = null
export function chime() {
  try {
    ctx ??= new AudioContext()
    const now = ctx.currentTime
    ;[660, 880].forEach((freq, i) => {
      const osc = ctx!.createOscillator()
      const gain = ctx!.createGain()
      osc.type = 'sine'
      osc.frequency.value = freq
      gain.gain.setValueAtTime(0.0001, now + i * 0.09)
      gain.gain.exponentialRampToValueAtTime(0.12, now + i * 0.09 + 0.02)
      gain.gain.exponentialRampToValueAtTime(0.0001, now + i * 0.09 + 0.25)
      osc.connect(gain).connect(ctx!.destination)
      osc.start(now + i * 0.09)
      osc.stop(now + i * 0.09 + 0.3)
    })
  } catch {
    /* no audio */
  }
}
