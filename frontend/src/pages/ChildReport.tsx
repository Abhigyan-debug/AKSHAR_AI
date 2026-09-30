import { ArrowLeftIcon, ArrowRightIcon, ArrowsClockwiseIcon, GameControllerIcon, ArrowSquareOutIcon, CopyIcon, DotsThreeIcon, QrCodeIcon, TrashIcon } from '@phosphor-icons/react'
import { AnimatePresence, motion } from 'motion/react'
import { QRCodeSVG } from 'qrcode.react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { Bar, BarChart, CartesianGrid, LabelList, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api, type ChildReport as ChildReportData, type ItemResult, type Lang, type Report, type Tap } from '../api'
import { DecisionButtons, ErrorPills, Heard, PlayButton, ResultMark, StatusChip } from '../components/report'
import { ERROR_LABELS, SECTION_LABELS } from '../lib/labels'
import { TeacherHeader } from '../components/TeacherHeader'
import { Button, Card, Disclaimer, ErrorBox, RiskBadge, Spinner } from '../components/ui'

const HINDI_COLOR = '#5b3a8e'
const ENGLISH_COLOR = '#e8a317'

export default function ChildReport() {
  const { childId } = useParams()
  const navigate = useNavigate()
  const [data, setData] = useState<ChildReportData | null>(null)
  const [error, setError] = useState<unknown>(null)
  const [finishing, setFinishing] = useState(false)
  const [showParent, setShowParent] = useState(false)
  const [tab, setTab] = useState<Lang>('hi')

  const load = useCallback(() => {
    api.childReport(Number(childId)).then(setData).catch(setError)
  }, [childId])
  useEffect(load, [load])

  async function finish() {
    if (!data?.session) return
    setFinishing(true)
    setError(null)
    try {
      await api.finishSession(data.session.id)
      load()
    } catch (e) {
      setError(e)
    } finally {
      setFinishing(false)
    }
  }

  async function decide(item: ItemResult, tap: Tap, wordsCorrect?: number) {
    try {
      const res = await api.decide(item.id, tap, wordsCorrect)
      setData((d) =>
        d && {
          ...d,
          items: d.items.map((i) => (i.id === item.id ? res.result : i)),
          report: res.report ?? d.report,
        },
      )
    } catch (e) {
      setError(e)
    }
  }

  async function deleteClip(item: ItemResult) {
    if (!window.confirm('Delete this audio clip? The score stays.')) return
    try {
      await api.deleteAudio(item.id)
      setData((d) => d && { ...d, items: d.items.map((i) => (i.id === item.id ? { ...i, audio_url: null } : i)) })
    } catch (e) {
      setError(e)
    }
  }

  async function deleteChild() {
    if (!data) return
    const typed = window.prompt(`This deletes ${data.child.code}, every recording and the report. Type the child code to confirm.`)
    if (typed?.trim().toUpperCase() !== data.child.code) return
    try {
      await api.deleteChild(data.child.id)
      navigate('/teacher', { replace: true })
    } catch (e) {
      setError(e)
    }
  }

  async function deleteAllAudio() {
    if (!data || !window.confirm(`Delete all audio for ${data.child.code}? Scores and the report stay.`)) return
    try {
      await api.deleteChildAudio(data.child.id)
      load()
    } catch (e) {
      setError(e)
    }
  }

  if (!data)
    return (
      <>
        <TeacherHeader />
        <main className="p-8">{error ? <ErrorBox error={error} /> : <Spinner label="Loading report" />}</main>
      </>
    )

  const { child, session, report, items } = data
  const queue = items.filter((i) => i.awaiting_verification)

  return (
    <>
    <TeacherHeader />
    <main className="mx-auto max-w-[1200px] px-4 py-6 md:px-8">
      <Link to="/teacher" className="inline-flex items-center gap-1.5 text-sm font-bold text-primary">
        <ArrowLeftIcon size={16} aria-hidden /> Class
      </Link>
      <header className="mt-2 mb-6 flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl font-semibold">Child {child.code}</h1>
          <p className="text-ink-muted">
            Grade {child.grade} · Home language: {child.home_lang}
            {session && ` · Tested ${new Date(session.created_at).toLocaleDateString()}`}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          {report && <RiskBadge level={report.risk_level} label={report.label} size="lg" />}
          {report && (
            <Button variant="secondary" onClick={() => setShowParent(true)}>
              <QrCodeIcon size={18} aria-hidden /> Parent page
            </Button>
          )}
          {report && report.risk_level !== 'pending' && report.risk_level !== 'provisional' && (
            <a href={`/practice/${report.parent_token}`} target="_blank" rel="noreferrer">
              <Button variant="secondary">
                <GameControllerIcon size={18} aria-hidden /> Practice games
              </Button>
            </a>
          )}
          <PrivacyMenu hasAudio={items.some((i) => i.audio_url)} onDeleteAudio={deleteAllAudio} onDeleteChild={deleteChild} />
        </div>
      </header>

      {error ? <div className="mb-4"><ErrorBox error={error} /></div> : null}

      {!session && (
        <Card>
          <p className="mb-3">This child hasn't been screened yet.</p>
          <Link to="/child">
            <Button>Screen now</Button>
          </Link>
        </Card>
      )}

      {session && !report && (
        <Card className="mb-6">
          <p className="mb-3">
            The reading session isn't finished ({items.length} items recorded). Finish it to score the recorded items and write the report.
          </p>
          <Button onClick={finish} disabled={finishing}>
            {finishing ? 'Scoring' : 'Finish and score'}
          </Button>
        </Card>
      )}

      {report && (
        <div className="space-y-6">
          <WhyPanel report={report} />
          <div className="grid gap-6 lg:grid-cols-2">
            <LanguageBars report={report} />
            <ErrorTypes report={report} />
          </div>
          <SummaryCard report={report} onRefresh={finish} refreshing={finishing} />
        </div>
      )}

      {queue.length > 0 && (
        <Card className="mt-6 border-accent" title={`Needs your check (${queue.length})`}>
          <p className="mb-3 text-sm text-ink-muted">
            The AI was unsure about these, or they are English items (English counts only after you confirm it). Listen and choose.
          </p>
          <ul className="divide-y divide-outline/40">
            <AnimatePresence initial={false}>
              {queue.map((item) => (
                <motion.li
                  key={item.id}
                  layout
                  exit={{ opacity: 0, height: 0 }}
                  className="flex flex-wrap items-center gap-3 py-3"
                >
                  <PlayButton url={item.audio_url} />
                  <div className="min-w-[180px] flex-1">
                    <p lang={item.lang} className="font-display text-lg font-semibold">
                      {item.section === 'E' ? item.prompt : item.section === 'D' ? 'Passage' : item.text}
                    </p>
                    <div className="text-sm text-ink-muted">
                      {SECTION_LABELS[item.section]} · Heard: <Heard item={item} />
                    </div>
                    {item.confidence.reasons.length > 0 && (
                      <p className="text-xs text-ink-muted">Why unsure: {item.confidence.reasons.join(', ')}</p>
                    )}
                  </div>
                  <DecisionButtons item={item} onDecide={(tap, words) => decide(item, tap, words)} />
                </motion.li>
              ))}
            </AnimatePresence>
          </ul>
        </Card>
      )}

      {items.length > 0 && (
        <Card
          className="mt-6"
          title="All items"
          right={
            <div className="flex rounded-full border border-outline p-0.5">
              {(['hi', 'en'] as Lang[]).map((l) => (
                <button
                  key={l}
                  type="button"
                  onClick={() => setTab(l)}
                  className={`rounded-full px-4 py-1 text-sm font-bold ${tab === l ? 'bg-primary text-on-primary' : 'text-ink-muted'}`}
                >
                  {l === 'hi' ? 'हिंदी' : 'English'}
                </button>
              ))}
            </div>
          }
        >
          <ItemTable items={items.filter((i) => i.lang === tab)} onDecide={decide} onDelete={deleteClip} />
        </Card>
      )}

      <div className="mt-6">
        <Disclaimer text={data.disclaimer} />
      </div>

      <AnimatePresence>
        {showParent && report && session && (
          <ParentModal
            token={report.parent_token}
            onRotate={async () => {
              const { parent_token } = await api.newParentLink(session.id)
              setData((d) => d && d.report && { ...d, report: { ...d.report, parent_token } })
            }}
            onClose={() => setShowParent(false)}
          />
        )}
      </AnimatePresence>
    </main>
    </>
  )
}

/** Privacy actions: kept behind a menu so they are never hit by accident. */
function PrivacyMenu({ hasAudio, onDeleteAudio, onDeleteChild }: { hasAudio: boolean; onDeleteAudio: () => void; onDeleteChild: () => void }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="relative">
      <Button variant="ghost" aria-expanded={open} aria-haspopup="menu" onClick={() => setOpen((o) => !o)}>
        <DotsThreeIcon size={20} weight="bold" aria-hidden />
        <span className="sr-only">Privacy actions</span>
      </Button>
      <AnimatePresence>
        {open && (
          <motion.div
            role="menu"
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4, transition: { duration: 0.1 } }}
            transition={{ duration: 0.15 }}
            className="absolute right-0 z-30 mt-2 w-60 rounded-[12px] border border-outline/60 bg-white p-1.5 shadow-[0_8px_24px_rgba(42,36,32,0.12)]"
          >
            {hasAudio && (
              <button
                role="menuitem"
                type="button"
                onClick={() => {
                  setOpen(false)
                  onDeleteAudio()
                }}
                className="flex w-full items-center gap-2 rounded-[8px] px-3 py-2 text-left text-sm hover:bg-surface-container"
              >
                <TrashIcon size={18} aria-hidden /> Delete all recordings
              </button>
            )}
            <button
              role="menuitem"
              type="button"
              onClick={() => {
                setOpen(false)
                onDeleteChild()
              }}
              className="flex w-full items-center gap-2 rounded-[8px] px-3 py-2 text-left text-sm font-bold text-error hover:bg-risk-specialist/10"
            >
              <TrashIcon size={18} aria-hidden /> Delete this child
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

function WhyPanel({ report }: { report: Report }) {
  const b = report.scoring_breakdown.overall
  return (
    <Card title="Why this result">
      <ul className="list-disc space-y-1 pl-5">
        {report.reasons.map((r, i) => (
          <li key={i}>{r}</li>
        ))}
      </ul>
      {b && (
        <p className="mt-3 text-sm text-ink-muted">
          Scored: {Math.round(b.auto_pct)}% automatically · {Math.round(b.teacher_verify_pct)}% sent to teacher check ·{' '}
          {Math.round(b.live_tap_pct)}% live tap
          {b.pending_verify > 0 && ` · ${b.pending_verify} still waiting for you`}
        </p>
      )}
    </Card>
  )
}

function pct(x: number | null | undefined) {
  return x === null || x === undefined ? null : Math.round(x * 100)
}

function LanguageBars({ report }: { report: Report }) {
  const { hi, en } = report.metrics
  const data = (['A', 'B', 'C', 'E'] as const).map((s) => ({
    section: SECTION_LABELS[s],
    Hindi: pct(hi.accuracy[s]),
    English: pct(en.accuracy[s]),
  }))
  return (
    <Card title="Hindi vs English">
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} layout="vertical" margin={{ left: 8, right: 36 }}>
            <CartesianGrid horizontal={false} stroke="#efe6da" />
            <XAxis type="number" domain={[0, 100]} unit="%" tick={{ fontSize: 12 }} />
            <YAxis type="category" dataKey="section" width={90} tick={{ fontSize: 13 }} />
            <Tooltip formatter={(v) => (v === null || v === undefined ? 'not scored yet' : `${v}%`)} />
            <Legend />
            <Bar dataKey="Hindi" fill={HINDI_COLOR} radius={[0, 6, 6, 0]}>
              <LabelList dataKey="Hindi" position="right" formatter={(v: unknown) => (v === null || v === undefined ? '' : `${v}%`)} fontSize={12} />
            </Bar>
            <Bar dataKey="English" fill={ENGLISH_COLOR} radius={[0, 6, 6, 0]}>
              <LabelList dataKey="English" position="right" formatter={(v: unknown) => (v === null || v === undefined ? '' : `${v}%`)} fontSize={12} />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <p className="mt-2 text-sm text-ink-muted">
        Passage (words correct per minute): Hindi {hi.wcpm ?? 'n/a'} · English {en.wcpm ?? 'n/a'} · grade guide {hi.wcpm_min}
      </p>
    </Card>
  )
}

function ErrorTypes({ report }: { report: Report }) {
  const { hi, en } = report.metrics
  const types = [...new Set([...Object.keys(hi.error_counts), ...Object.keys(en.error_counts)])]
  const data = types
    .map((t) => ({ type: ERROR_LABELS[t] ?? t, Hindi: hi.error_counts[t] ?? 0, English: en.error_counts[t] ?? 0 }))
    .sort((a, b) => b.Hindi + b.English - (a.Hindi + a.English))
  return (
    <Card title="Error types">
      {data.length === 0 ? (
        <p className="text-ink-muted">No reading errors in scored letters, words or nonwords.</p>
      ) : (
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} margin={{ bottom: 40 }}>
              <CartesianGrid vertical={false} stroke="#efe6da" />
              <XAxis dataKey="type" angle={-25} textAnchor="end" interval={0} tick={{ fontSize: 11 }} />
              <YAxis allowDecimals={false} tick={{ fontSize: 12 }} />
              <Tooltip />
              <Legend verticalAlign="top" />
              <Bar dataKey="Hindi" fill={HINDI_COLOR} radius={[6, 6, 0, 0]} />
              <Bar dataKey="English" fill={ENGLISH_COLOR} radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
      <p className="mt-2 text-xs text-ink-muted">Letters, words and nonwords only; the passage is measured by words correct per minute.</p>
    </Card>
  )
}

function SummaryCard({ report, onRefresh, refreshing }: { report: Report; onRefresh: () => void; refreshing: boolean }) {
  const ai = report.summary_source === 'llm'
  return (
    <Card
      title="Summary"
      right={
        <span className="rounded-full bg-surface-container px-3 py-1 text-xs text-ink-muted">
          {ai ? 'Written by AI from the rule engine’s facts' : 'Template summary'}
        </span>
      }
    >
      {report.summary_stale && (
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2 rounded-[12px] bg-accent-container px-3 py-2 text-sm">
          The result changed after this summary was written.
          <Button className="px-3 py-1 text-sm" onClick={onRefresh} disabled={refreshing}>
            {refreshing ? 'Updating' : 'Update summary'}
          </Button>
        </div>
      )}
      <p className="leading-relaxed">{report.teacher_summary}</p>
      <div className="mt-4 flex gap-3 rounded-[12px] bg-primary-container/70 px-4 py-3">
        <ArrowRightIcon size={20} weight="bold" className="mt-0.5 shrink-0 text-primary" aria-hidden />
        <div>
          <p className="text-sm font-bold text-primary">Next step</p>
          <p>{report.next_step}</p>
        </div>
      </div>
      {!ai && report.risk_level !== 'pending' && report.risk_level !== 'provisional' && (
        <Button variant="ghost" className="mt-3 text-sm" onClick={onRefresh} disabled={refreshing}>
          {refreshing ? 'Writing' : 'Write AI summary'}
        </Button>
      )}
    </Card>
  )
}

function ItemTable({
  items,
  onDecide,
  onDelete,
}: {
  items: ItemResult[]
  onDecide: (item: ItemResult, tap: Tap, words?: number) => Promise<void>
  onDelete: (item: ItemResult) => void
}) {
  const [open, setOpen] = useState<number | null>(null)
  const groups = useMemo(() => {
    const g: Record<string, ItemResult[]> = {}
    for (const i of items) (g[i.section] ??= []).push(i)
    return Object.entries(g).sort(([a], [b]) => a.localeCompare(b))
  }, [items])
  if (!items.length) return <p className="text-ink-muted">No items recorded in this language.</p>
  return (
    <div className="space-y-5">
      {groups.map(([section, rows]) => (
        <div key={section}>
          <h3 className="mb-1 text-sm font-bold tracking-wide text-ink-muted uppercase">{SECTION_LABELS[section]}</h3>
          <ul className="divide-y divide-outline/30 rounded-[12px] border border-outline/40">
            {rows.map((item) => (
              <li key={item.id} className="px-3 py-2">
                <div className="flex flex-wrap items-center gap-3">
                  <PlayButton url={item.audio_url} />
                  <span className="w-6 text-center">
                    <ResultMark item={item} />
                  </span>
                  <span lang={item.lang} className={`font-display font-semibold ${item.section === 'D' ? 'text-base' : 'min-w-[80px] text-xl'}`}>
                    {item.section === 'D' ? 'Passage' : item.section === 'E' ? item.text : item.text}
                  </span>
                  <span className="min-w-[120px] flex-1 text-sm">
                    <span className="text-ink-muted">Heard: </span>
                    {item.section === 'D' ? `${item.words_correct}/${item.words_total} words` : <Heard item={item} />}
                  </span>
                  <ErrorPills errors={item.errors} />
                  <StatusChip item={item} />
                  <button
                    type="button"
                    onClick={() => setOpen(open === item.id ? null : item.id)}
                    className="rounded-full px-2 text-ink-muted hover:bg-surface-container"
                    aria-label="More"
                  >
                    ⋯
                  </button>
                </div>
                {item.section === 'D' && item.pairs.length > 0 && (
                  <div className="mt-2 rounded-[8px] bg-surface-container p-3 text-sm">
                    <Heard item={item} />
                  </div>
                )}
                <AnimatePresence>
                  {open === item.id && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: 'auto', opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      className="overflow-hidden"
                    >
                      <div className="mt-2 flex flex-wrap items-center gap-3 rounded-[8px] bg-surface-container p-3">
                        <span className="text-sm font-bold">{item.status === 'manual' ? 'Change live tap:' : 'Override:'}</span>
                        <DecisionButtons compact item={item} onDecide={(tap, words) => onDecide(item, tap, words).then(() => setOpen(null))} />
                        {item.audio_url && (
                          <button type="button" onClick={() => onDelete(item)} className="ml-auto text-sm font-bold text-error">
                            Delete audio
                          </button>
                        )}
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  )
}

function ParentModal({ token, onRotate, onClose }: { token: string; onRotate: () => Promise<void>; onClose: () => void }) {
  const link = `${window.location.origin}/p/${token}`
  const [copied, setCopied] = useState(false)
  const [rotating, setRotating] = useState(false)
  return (
    <motion.div
      className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 p-4"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      onClick={onClose}
    >
      <motion.div
        role="dialog"
        aria-label="Parent page"
        className="w-full max-w-sm rounded-[20px] bg-white p-6 text-center"
        initial={{ scale: 0.95, y: 10 }}
        animate={{ scale: 1, y: 0 }}
        exit={{ scale: 0.95, y: 10 }}
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="font-display text-xl font-semibold">Parent page</h2>
        <p className="mb-4 text-sm text-ink-muted">Hindi summary with read-aloud. The link shows no child code or name.</p>
        <div className="mx-auto mb-4 w-fit rounded-[12px] border border-outline p-3">
          <QRCodeSVG value={link} size={180} fgColor="#2a2420" />
        </div>
        <p className="mb-3 break-all rounded-[8px] bg-surface-container px-3 py-2 text-xs">{link}</p>
        <div className="flex justify-center gap-2">
          <Button
            variant="secondary"
            onClick={() => {
              void navigator.clipboard?.writeText(link).then(() => setCopied(true))
            }}
          >
            <CopyIcon size={18} aria-hidden /> {copied ? 'Copied' : 'Copy link'}
          </Button>
          <a href={link} target="_blank" rel="noreferrer">
            <Button>
              <ArrowSquareOutIcon size={18} aria-hidden /> Open
            </Button>
          </a>
        </div>
        <button
          type="button"
          disabled={rotating}
          onClick={async () => {
            if (!window.confirm('Make a new link? The old link and QR code stop working.')) return
            setRotating(true)
            try {
              await onRotate()
              setCopied(false)
            } finally {
              setRotating(false)
            }
          }}
          className="mt-4 inline-flex items-center gap-1.5 text-sm font-bold text-ink-muted hover:text-ink"
        >
          <ArrowsClockwiseIcon size={16} aria-hidden /> {rotating ? 'Making a new link' : 'Make a new link'}
        </button>
        <button type="button" onClick={onClose} className="mt-2 block w-full text-sm text-ink-muted">
          Close
        </button>
      </motion.div>
    </motion.div>
  )
}
