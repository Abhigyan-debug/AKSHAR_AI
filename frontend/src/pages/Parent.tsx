import { motion, useReducedMotion } from 'motion/react'
import { GameControllerIcon } from '@phosphor-icons/react'
import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, type ParentView } from '../api'
import { Owl } from '../components/child'
import { Spinner } from '../components/ui'
import { findVoice, speak, speechSupported, stopSpeaking } from '../lib/speech'

const TIP_ICONS = ['📖', '👂', '⭐']
const HELP_ICONS = ['🏫', '🏥', '🧑‍🏫']

// Parent page: simple Hindi, read aloud with the browser's hi-IN voice.
export default function Parent() {
  const { token } = useParams()
  const reduce = useReducedMotion()
  const [data, setData] = useState<ParentView | null>(null)
  const [notFound, setNotFound] = useState(false)
  const [speaking, setSpeaking] = useState(false)
  const [hasVoice, setHasVoice] = useState(true)

  useEffect(() => {
    api.parent(token ?? '').then(setData).catch(() => setNotFound(true))
    findVoice('hi-IN').then((v) => setHasVoice(!!v))
    return stopSpeaking
  }, [token])

  async function listen() {
    if (!data) return
    if (speaking) {
      stopSpeaking()
      setSpeaking(false)
      return
    }
    setSpeaking(true)
    const text = [data.label_hi, data.summary_hi, 'घर पर आप यह कर सकते हैं।', ...data.tips_hi].join(' ')
    await speak(text, 'hi-IN', 0.85)
    setSpeaking(false)
  }

  if (notFound)
    return (
      <main lang="hi" className="mx-auto max-w-md p-6 text-center">
        <Owl size={80} />
        <p className="mt-4 text-lg">यह लिंक सही नहीं है या पुराना हो गया है। कृपया शिक्षक से नया लिंक माँगें।</p>
      </main>
    )
  if (!data) return <main className="p-6"><Spinner label="लोड हो रहा है…" /></main>

  return (
    <main lang="hi" className="mx-auto max-w-md px-4 pt-6 pb-10">
      <header className="mb-5 flex items-center gap-3">
        <Owl size={44} />
        <div>
          <p className="font-display text-2xl font-semibold text-primary">अक्षर</p>
          <p className="text-sm text-ink-muted">आपके बच्चे की पढ़ाई की जाँच</p>
        </div>
      </header>

      <motion.section
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        className="rounded-[20px] border border-outline/60 bg-white p-5 shadow-sm"
      >
        <p className="mb-3 font-display text-[22px] leading-snug font-semibold">{data.label_hi}</p>
        <p className="text-[18px] leading-[1.8]">{data.summary_hi}</p>
      </motion.section>

      {data.ready && speechSupported() && (
        <>
          <button
            type="button"
            onClick={listen}
            className="mt-4 flex w-full items-center justify-center gap-3 rounded-[16px] bg-primary px-5 py-4 text-xl font-bold text-on-primary active:scale-[0.98]"
          >
            {speaking ? (
              <>
                <span className="flex h-6 items-end gap-1" aria-hidden>
                  {[0, 1, 2, 3].map((i) => (
                    <motion.span
                      key={i}
                      className="w-1.5 rounded-full bg-accent"
                      animate={reduce ? { height: 14 } : { height: [6, 22, 10, 18, 6] }}
                      transition={{ duration: 1, repeat: Infinity, delay: i * 0.12 }}
                    />
                  ))}
                </span>
                ⏸ रोकें
              </>
            ) : (
              <>🔊 सुनिए</>
            )}
          </button>
          {!hasVoice && (
            <p className="mt-2 text-center text-sm text-ink-muted">
              आपके फ़ोन में हिंदी आवाज़ नहीं मिली, इसलिए यह किसी और आवाज़ में पढ़ा जा सकता है।
            </p>
          )}
        </>
      )}

      {data.ready && (
        <Link
          to={`/practice/${token}`}
          className="mt-4 flex items-center gap-4 rounded-[16px] border-2 border-primary/30 bg-primary-container/60 p-4"
        >
          <GameControllerIcon size={36} weight="duotone" className="shrink-0 text-primary" aria-hidden />
          <span>
            <span className="block font-display text-lg font-semibold">अभ्यास के खेल</span>
            <span className="text-ink-muted">रोज़ 5 मिनट, बच्चे के साथ बैठकर खेलें</span>
          </span>
        </Link>
      )}

      {data.ready && data.tips_hi.length > 0 && (
        <section className="mt-8">
          <h2 className="mb-3 font-display text-xl font-semibold">घर पर आप क्या कर सकते हैं</h2>
          <ol className="space-y-3">
            {data.tips_hi.map((tip, i) => (
              <motion.li
                key={i}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.1 + i * 0.08 }}
                className="flex gap-3 rounded-[12px] border border-outline/50 bg-white p-4"
              >
                <span className="text-2xl" aria-hidden>
                  {TIP_ICONS[i] ?? '•'}
                </span>
                <span className="text-[17px] leading-[1.7]">{tip}</span>
              </motion.li>
            ))}
          </ol>
        </section>
      )}

      {data.ready && data.show_help && (
        <section className="mt-8">
          <h2 className="mb-3 font-display text-xl font-semibold">मदद कहाँ मिलेगी</h2>
          <ul className="space-y-2">
            {data.help_hi.map((h, i) => (
              <li key={i} className="flex gap-3 rounded-[12px] bg-surface-container p-3 text-[17px] leading-[1.7]">
                <span aria-hidden>{HELP_ICONS[i] ?? '•'}</span>
                {h}
              </li>
            ))}
          </ul>
        </section>
      )}

      <p className="mt-8 text-center text-sm text-ink-muted">{data.disclaimer_hi}</p>
    </main>
  )
}
