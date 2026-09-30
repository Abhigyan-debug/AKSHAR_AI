// Browser text-to-speech (speechSynthesis) for child-mode instructions, the
// parent page's read-aloud and the practice games. Voices load
// asynchronously in some browsers.

export type SpeechLang = 'hi-IN' | 'en-IN'

function voicesReady(): Promise<SpeechSynthesisVoice[]> {
  const synth = window.speechSynthesis
  const now = synth.getVoices()
  if (now.length) return Promise.resolve(now)
  return new Promise((resolve) => {
    const done = () => resolve(synth.getVoices())
    synth.addEventListener('voiceschanged', done, { once: true })
    setTimeout(done, 1500)
  })
}

export function speechSupported(): boolean {
  return typeof window !== 'undefined' && 'speechSynthesis' in window
}

/** The best voice for a language, or null if the device has none. */
export async function findVoice(lang: SpeechLang): Promise<SpeechSynthesisVoice | null> {
  if (!speechSupported()) return null
  const voices = await voicesReady()
  const base = lang.split('-')[0]
  return (
    voices.find((v) => v.lang === lang) ??
    voices.find((v) => v.lang.replace('_', '-').toLowerCase() === lang.toLowerCase()) ??
    voices.find((v) => v.lang.toLowerCase().startsWith(base)) ??
    null
  )
}

/** Speaks `text`; resolves when finished or cancelled. Returns false if no voice. */
export async function speak(text: string, lang: SpeechLang, rate = 0.9): Promise<boolean> {
  return speakWithWords(text, lang, rate)
}

/**
 * Speaks `text` and reports which word is being spoken, for read-along
 * highlighting. Uses the voice's word-boundary events when it sends them, and
 * otherwise estimates timing from word length.
 */
export async function speakWithWords(text: string, lang: SpeechLang, rate = 0.9, onWord?: (index: number) => void): Promise<boolean> {
  if (!speechSupported()) return false
  const voice = await findVoice(lang)
  const synth = window.speechSynthesis
  synth.cancel()
  const u = new SpeechSynthesisUtterance(text)
  u.lang = lang
  u.rate = rate
  if (voice) u.voice = voice

  // Character offset where each word starts, to map boundary events to words.
  const starts: number[] = []
  text.replace(/\S+/g, (m, offset: number) => {
    starts.push(offset)
    return m
  })
  const words = text.split(/\s+/).filter(Boolean)
  let gotBoundary = false
  const timers: number[] = []

  if (onWord) {
    u.onboundary = (e) => {
      if (e.name && e.name !== 'word') return
      gotBoundary = true
      timers.forEach(clearTimeout)
      let idx = 0
      while (idx + 1 < starts.length && starts[idx + 1] <= e.charIndex) idx++
      onWord(idx)
    }
    u.onstart = () => {
      onWord(0)
      // Fallback schedule, cancelled as soon as a real boundary event arrives.
      let t = 0
      for (let i = 1; i < words.length; i++) {
        t += (180 + [...words[i - 1]].length * 70) / rate
        timers.push(window.setTimeout(() => !gotBoundary && onWord(i), t))
      }
    }
  }

  return new Promise((resolve) => {
    const finish = (ok: boolean) => {
      timers.forEach(clearTimeout)
      resolve(ok)
    }
    u.onend = () => finish(true)
    u.onerror = () => finish(false)
    synth.speak(u)
  })
}

export function stopSpeaking(): void {
  if (speechSupported()) window.speechSynthesis.cancel()
}
