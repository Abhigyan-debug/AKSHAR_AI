import { useCallback, useEffect, useRef, useState } from 'react'

// Records one item at a time from a microphone stream that is opened once and
// reused, so the browser asks for permission only at the start of the test.
// Auto-stops after `silenceMs` of silence (5 s) or at `maxMs`.

export interface Recording {
  blob: Blob
  filename: string
  durationMs: number
}

const SILENCE_RMS = 0.015 // below this the input counts as silence (provisional, tune on real phones)

function pickMime(): { mimeType: string; ext: string } {
  const candidates: [string, string][] = [
    ['audio/webm;codecs=opus', 'webm'],
    ['audio/webm', 'webm'],
    ['audio/mp4', 'm4a'], // Safari
    ['audio/ogg;codecs=opus', 'ogg'],
  ]
  for (const [mimeType, ext] of candidates) {
    if (typeof MediaRecorder !== 'undefined' && MediaRecorder.isTypeSupported(mimeType)) return { mimeType, ext }
  }
  return { mimeType: '', ext: 'webm' }
}

export type MicState = 'idle' | 'requesting' | 'ready' | 'recording' | 'denied' | 'unsupported'

export function useRecorder() {
  const [state, setState] = useState<MicState>('idle')
  const [level, setLevel] = useState(0) // 0..1, for the listening animation
  const streamRef = useRef<MediaStream | null>(null)
  const ctxRef = useRef<AudioContext | null>(null)
  const analyserRef = useRef<AnalyserNode | null>(null)
  const recRef = useRef<MediaRecorder | null>(null)
  // setInterval, not requestAnimationFrame: rAF pauses when the page is hidden
  // (screen dims, app switch), which would stop the silence/max-length checks.
  const timerRef = useRef<number | null>(null)
  const maxTimerRef = useRef<number | null>(null)
  const resolveRef = useRef<((r: Recording | null) => void) | null>(null)

  const openMic = useCallback(async (): Promise<boolean> => {
    if (streamRef.current) return true
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
      setState('unsupported')
      return false
    }
    setState('requesting')
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, channelCount: 1 },
      })
      streamRef.current = stream
      const ctx = new AudioContext()
      const analyser = ctx.createAnalyser()
      analyser.fftSize = 1024
      ctx.createMediaStreamSource(stream).connect(analyser)
      ctxRef.current = ctx
      analyserRef.current = analyser
      setState('ready')
      return true
    } catch {
      setState('denied')
      return false
    }
  }, [])

  const clearTimers = useCallback(() => {
    if (timerRef.current !== null) window.clearInterval(timerRef.current)
    if (maxTimerRef.current !== null) window.clearTimeout(maxTimerRef.current)
    timerRef.current = maxTimerRef.current = null
  }, [])

  const stop = useCallback(() => {
    const rec = recRef.current
    if (rec && rec.state !== 'inactive') rec.stop()
  }, [])

  /** Starts recording; resolves with the clip when it stops (tap, silence or max length). */
  const record = useCallback(
    async ({ silenceMs = 5000, maxMs = 20000 }: { silenceMs?: number; maxMs?: number } = {}): Promise<Recording | null> => {
      if (!(await openMic())) return null
      const stream = streamRef.current!
      const analyser = analyserRef.current!
      await ctxRef.current?.resume()
      const { mimeType, ext } = pickMime()
      const rec = new MediaRecorder(stream, mimeType ? { mimeType } : undefined)
      const chunks: BlobPart[] = []
      const started = performance.now()
      let lastSound = started

      rec.ondataavailable = (e) => {
        if (e.data.size) chunks.push(e.data)
      }
      const done = new Promise<Recording | null>((resolve) => {
        resolveRef.current = resolve
      })
      rec.onstop = () => {
        clearTimers()
        setLevel(0)
        setState('ready')
        const blob = new Blob(chunks, { type: rec.mimeType || mimeType || 'audio/webm' })
        resolveRef.current?.({ blob, filename: `clip.${ext}`, durationMs: performance.now() - started })
        resolveRef.current = null
      }

      const buf = new Float32Array(analyser.fftSize)
      const tick = () => {
        analyser.getFloatTimeDomainData(buf)
        let sum = 0
        for (const v of buf) sum += v * v
        const rms = Math.sqrt(sum / buf.length)
        setLevel(Math.min(1, rms * 12))
        const now = performance.now()
        if (rms > SILENCE_RMS) lastSound = now
        if (now - lastSound >= silenceMs || now - started >= maxMs) stop()
      }

      recRef.current = rec
      rec.start()
      setState('recording')
      timerRef.current = window.setInterval(tick, 100)
      maxTimerRef.current = window.setTimeout(stop, maxMs + 500) // backstop if the interval is throttled
      return done
    },
    [openMic, stop, clearTimers],
  )

  useEffect(
    () => () => {
      clearTimers()
      const rec = recRef.current
      if (rec && rec.state !== 'inactive') {
        rec.onstop = null
        rec.stop()
      }
      streamRef.current?.getTracks().forEach((t) => t.stop())
      ctxRef.current?.close()
    },
    [clearTimers],
  )

  return { state, level, openMic, record, stop }
}
