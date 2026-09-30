import { useEffect, useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, type Child } from '../api'
import { Owl } from '../components/child'
import { TeacherHeader } from '../components/TeacherHeader'
import { Button, Card, ErrorBox } from '../components/ui'

const HOME_LANGS = ['Hindi', 'Bhojpuri', 'Awadhi', 'Urdu', 'Marathi', 'Bengali', 'English', 'Other']

// Teacher-facing: pick or create a child code, then hand the phone to the child.
export default function ChildSetup() {
  const navigate = useNavigate()
  const [children, setChildren] = useState<Child[]>([])
  const [selected, setSelected] = useState<number | ''>('')
  const [code, setCode] = useState('')
  const [grade, setGrade] = useState(3)
  const [homeLang, setHomeLang] = useState('Hindi')
  const [soundGame, setSoundGame] = useState(true)
  const [error, setError] = useState<unknown>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    api.listChildren().then(setChildren).catch(setError)
  }, [])

  async function start(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      const child = selected === '' ? await api.createChild(code.trim(), grade, homeLang) : children.find((c) => c.id === selected)!
      const session = await api.createSession(child.id, soundGame)
      navigate(`/child/run/${session.id}?child=${child.id}&sound=${soundGame ? 1 : 0}`)
    } catch (err) {
      setError(err)
      setBusy(false)
    }
  }

  const input = 'w-full rounded-[12px] border border-outline bg-white px-3 py-2.5 text-base focus:border-primary'
  return (
    <>
    <TeacherHeader />
    <main className="mx-auto max-w-lg px-4 py-8">
      <div className="mb-6 flex items-center gap-3">
        <Owl size={56} />
        <div>
          <h1 className="font-display text-2xl font-semibold">Screen a child</h1>
          <p className="text-ink-muted">About 10 minutes · Hindi, then English</p>
        </div>
      </div>

      <form onSubmit={start} className="space-y-4">
        <Card title="Child">
          {children.length > 0 && (
            <label className="mb-4 block">
              <span className="mb-1 block text-sm font-bold">Choose a child</span>
              <select className={input} value={selected} onChange={(e) => setSelected(e.target.value === '' ? '' : Number(e.target.value))}>
                <option value="">+ New child code</option>
                {children.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.code} · Grade {c.grade}
                  </option>
                ))}
              </select>
            </label>
          )}
          {selected === '' && (
            <div className="space-y-3">
              <label className="block">
                <span className="mb-1 block text-sm font-bold">Child code</span>
                <input
                  className={input}
                  required
                  maxLength={20}
                  pattern="[A-Za-z0-9_\-]+"
                  placeholder="e.g. R01"
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                />
                <span className="mt-1 block text-xs text-ink-muted">Codes only, no names (privacy). Letters, numbers, - and _.</span>
              </label>
              <div className="grid grid-cols-2 gap-3">
                <label className="block">
                  <span className="mb-1 block text-sm font-bold">Grade</span>
                  <select className={input} value={grade} onChange={(e) => setGrade(Number(e.target.value))}>
                    {[1, 2, 3, 4, 5, 6, 7, 8].map((g) => (
                      <option key={g} value={g}>
                        {g}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="block">
                  <span className="mb-1 block text-sm font-bold">Home language</span>
                  <select className={input} value={homeLang} onChange={(e) => setHomeLang(e.target.value)}>
                    {HOME_LANGS.map((l) => (
                      <option key={l}>{l}</option>
                    ))}
                  </select>
                </label>
              </div>
            </div>
          )}
        </Card>

        <Card title="Test">
          <label className="flex items-start gap-3">
            <input type="checkbox" className="mt-1 h-5 w-5 accent-primary" checked={soundGame} onChange={(e) => setSoundGame(e.target.checked)} />
            <span>
              <span className="block font-bold">Include the sound game</span>
              <span className="text-sm text-ink-muted">Optional section E: 5 listening questions per language.</span>
            </span>
          </label>
          <p className="mt-4 text-sm text-ink-muted">
            Letters are scored by you with the small teacher buttons at the bottom of the screen while the child reads. Everything else is
            scored from the recording.
          </p>
        </Card>

        {error ? <ErrorBox error={error} /> : null}
        <Button type="submit" className="w-full py-3 text-lg" disabled={busy}>
          {busy ? 'Starting' : 'Start reading'}
        </Button>
      </form>
    </main>
    </>
  )
}
