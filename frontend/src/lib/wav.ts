/** A short silent WAV clip. Used when the teacher taps a manual item before the
 * child said anything: the API needs a clip, and silence is the honest evidence. */
export function silentWav(seconds = 0.5, sampleRate = 16000): Blob {
  const samples = Math.round(seconds * sampleRate)
  const buffer = new ArrayBuffer(44 + samples * 2)
  const v = new DataView(buffer)
  const str = (offset: number, s: string) => [...s].forEach((c, i) => v.setUint8(offset + i, c.charCodeAt(0)))
  str(0, 'RIFF')
  v.setUint32(4, 36 + samples * 2, true)
  str(8, 'WAVE')
  str(12, 'fmt ')
  v.setUint32(16, 16, true) // PCM chunk size
  v.setUint16(20, 1, true) // PCM
  v.setUint16(22, 1, true) // mono
  v.setUint32(24, sampleRate, true)
  v.setUint32(28, sampleRate * 2, true) // byte rate
  v.setUint16(32, 2, true) // block align
  v.setUint16(34, 16, true) // bits per sample
  str(36, 'data')
  v.setUint32(40, samples * 2, true)
  return new Blob([buffer], { type: 'audio/wav' })
}
