import { ArrowRightIcon, CaretRightIcon, CheckCircleIcon, MagnifyingGlassIcon, MicrophoneIcon } from '@phosphor-icons/react'
import { AnimatePresence, LayoutGroup, motion, useReducedMotion } from 'motion/react'
import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, type ClassRow, type RiskLevel } from '../api'
import { TeacherHeader } from '../components/TeacherHeader'
import { Disclaimer, ErrorBox, RiskBadge, RiskMark } from '../components/ui'
import { RISK } from '../lib/labels'

type Group = 'specialist_check' | 'support' | 'english_exposure_gap' | 'low_risk' | 'pending'
type Filter = 'all' | Group

// Ordered by how urgently a teacher should look: this is also the table's sort order.
const GROUPS: { key: Group; label: string; level: RiskLevel; bar: string }[] = [
  { key: 'specialist_check', label: 'Specialist check', level: 'specialist_check', bar: 'bg-risk-specialist' },
  { key: 'support', label: 'Needs support', level: 'reading_support', bar: 'bg-risk-support' },
  { key: 'english_exposure_gap', label: 'English gap', level: 'english_exposure_gap', bar: 'bg-risk-english-gap' },
  { key: 'low_risk', label: 'Low risk', level: 'low_risk', bar: 'bg-risk-low' },
  { key: 'pending', label: 'Not final yet', level: 'pending', bar: 'bg-risk-pending' },
]
const ORDER = Object.fromEntries(GROUPS.map((g, i) => [g.key, i])) as Record<Group, number>
const EASE = [0.16, 1, 0.3, 1] as const

function groupOf(row: ClassRow): Group {
  switch (row.risk_level) {
    case 'specialist_check':
    case 'english_exposure_gap':
    case 'low_risk':
      return row.risk_level
    case 'reading_support':
    case 'hindi_support':
      return 'support'
    default:
      return 'pending'
  }
}

export default function TeacherDashboard() {
  const navigate = useNavigate()
  const reduce = useReducedMotion()
  const [rows, setRows] = useState<ClassRow[] | null>(null)
  const [error, setError] = useState<unknown>(null)
  const [filter, setFilter] = useState<Filter>('all')
  const [query, setQuery] = useState('')

  useEffect(() => {
    api.classSummary().then(setRows).catch(setError)
  }, [])

  const counts = useMemo(() => {
    const c = Object.fromEntries(GROUPS.map((g) => [g.key, 0])) as Record<Group, number>
    for (const r of rows ?? []) c[groupOf(r)] += 1
    return c
  }, [rows])

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase()
    return (rows ?? [])
      .filter((r) => (filter === 'all' || groupOf(r) === filter) && r.code.toLowerCase().includes(q))
      .sort((a, b) => ORDER[groupOf(a)] - ORDER[groupOf(b)] || b.pending_verify - a.pending_verify || a.code.localeCompare(b.code))
  }, [rows, filter, query])

  const toCheck = useMemo(
    () => (rows ?? []).filter((r) => r.pending_verify > 0).sort((a, b) => b.pending_verify - a.pending_verify),
    [rows],
  )
  const total = rows?.length ?? 0

  return (
    <>
      <TeacherHeader />
      <main className="mx-auto max-w-[1200px] px-4 py-8 md:px-8">
        <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
          <div>
            <h1 className="font-display text-3xl font-semibold">Your class</h1>
            <p className="text-ink-muted">
              {rows ? (total === 1 ? '1 child screened' : `${total} children screened`) : 'Loading results'}
            </p>
          </div>
        </div>

        {error ? <ErrorBox error={error} /> : null}

        {rows && total > 0 && (
          <section aria-label="Class results" className="mb-8 grid gap-4 lg:grid-cols-[1fr_320px]">
            <Distribution counts={counts} total={total} filter={filter} onPick={setFilter} reduce={!!reduce} />
            <NeedsYou rows={toCheck} />
          </section>
        )}

        {rows && total === 0 && <EmptyClass />}

        {(!rows || total > 0) && !error && (
          <>
            <div className="mb-4 flex flex-wrap items-center gap-3">
              <LayoutGroup id="filters">
                <div role="radiogroup" aria-label="Filter by result" className="flex flex-wrap gap-1 rounded-[14px] bg-surface-container p-1">
                  {[{ key: 'all' as const, label: 'All', n: total }, ...GROUPS.map((g) => ({ key: g.key, label: g.label, n: counts[g.key] }))].map(
                    (f) => {
                      const on = filter === f.key
                      return (
                        <button
                          key={f.key}
                          type="button"
                          role="radio"
                          aria-checked={on}
                          onClick={() => setFilter(f.key)}
                          className="relative rounded-[10px] px-3 py-1.5 text-sm font-bold"
                        >
                          {on && (
                            <motion.span
                              layoutId="filter-pill"
                              className="absolute inset-0 rounded-[10px] bg-white shadow-[0_1px_3px_rgba(91,58,142,0.18)]"
                              transition={{ type: 'spring', stiffness: 500, damping: 40 }}
                            />
                          )}
                          <span className={`relative flex items-center gap-1.5 ${on ? 'text-ink' : 'text-ink-muted hover:text-ink'}`}>
                            {f.key !== 'all' && <RiskMark level={GROUPS.find((g) => g.key === f.key)!.level} size={9} />}
                            {f.label}
                            <span className="tabular text-xs font-normal text-ink-muted">{f.n}</span>
                          </span>
                        </button>
                      )
                    },
                  )}
                </div>
              </LayoutGroup>
              <label className="relative ml-auto w-full md:w-64">
                <span className="sr-only">Search child code</span>
                <MagnifyingGlassIcon size={18} className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-ink-muted" aria-hidden />
                <input
                  type="search"
                  placeholder="Search child code"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  className="w-full rounded-[12px] border border-outline bg-white py-2 pr-3 pl-9 placeholder:text-ink-muted focus:border-primary"
                />
              </label>
            </div>

            <div className="overflow-x-auto rounded-[16px] border border-outline/60 bg-white">
              <table className="w-full min-w-[760px] text-left">
                <thead className="border-b border-outline/60 text-sm text-ink-muted">
                  <tr>
                    <th className="px-4 py-3 font-bold">Child</th>
                    <th className="px-4 py-3 font-bold">Grade</th>
                    <th className="px-4 py-3 font-bold">Home language</th>
                    <th className="px-4 py-3 font-bold">Tested</th>
                    <th className="px-4 py-3 font-bold">Result</th>
                    <th className="px-4 py-3 font-bold">To check</th>
                    <th className="w-10 px-4 py-3">
                      <span className="sr-only">Open</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {!rows && <SkeletonRows />}
                  <AnimatePresence initial={false}>
                    {visible.map((r) => (
                      <motion.tr
                        key={r.id}
                        layout={!reduce}
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0, transition: { duration: 0.12 } }}
                        transition={{ duration: 0.2, ease: EASE }}
                        onClick={() => navigate(`/teacher/child/${r.id}`)}
                        className="group cursor-pointer border-b border-outline/30 last:border-0 hover:bg-primary-container/40"
                      >
                        <td className="px-4 py-3">
                          <Link to={`/teacher/child/${r.id}`} className="font-display font-semibold hover:text-primary" onClick={(e) => e.stopPropagation()}>
                            {r.code}
                          </Link>
                        </td>
                        <td className="tabular px-4 py-3">{r.grade}</td>
                        <td className="px-4 py-3">{r.home_lang}</td>
                        <td className="tabular px-4 py-3 text-ink-muted">{r.tested_at ? new Date(r.tested_at).toLocaleDateString() : 'Not yet'}</td>
                        <td className="px-4 py-3">
                          {r.risk_level ? (
                            <RiskBadge level={r.risk_level} />
                          ) : r.session_status === 'in_progress' ? (
                            <span className="text-sm text-ink-muted">
                              In progress, {r.items_recorded} {r.items_recorded === 1 ? 'item' : 'items'}
                            </span>
                          ) : (
                            <span className="text-sm text-ink-muted">Not screened</span>
                          )}
                          {r.summary_stale && <span className="ml-2 text-xs text-ink-muted">summary out of date</span>}
                        </td>
                        <td className="px-4 py-3">
                          {r.pending_verify > 0 ? (
                            <span className="tabular rounded-full bg-accent-container px-2.5 py-1 text-sm font-bold text-on-accent">
                              {r.pending_verify} {r.pending_verify === 1 ? 'item' : 'items'}
                            </span>
                          ) : (
                            <span className="text-sm text-ink-muted">None</span>
                          )}
                        </td>
                        <td className="px-4 py-3 text-ink-muted">
                          <CaretRightIcon size={18} className="transition-transform duration-150 group-hover:translate-x-0.5 group-hover:text-primary" aria-hidden />
                        </td>
                      </motion.tr>
                    ))}
                  </AnimatePresence>
                  {rows && visible.length === 0 && (
                    <tr>
                      <td colSpan={7} className="px-4 py-10 text-center text-ink-muted">
                        No children match.{' '}
                        <button type="button" className="font-bold text-primary" onClick={() => (setFilter('all'), setQuery(''))}>
                          Show everyone
                        </button>
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </>
        )}

        <div className="mt-8">
          <Disclaimer />
        </div>
      </main>
    </>
  )
}

/** The class at a glance: one strip, each segment a result, click to filter the table. */
function Distribution({
  counts,
  total,
  filter,
  onPick,
  reduce,
}: {
  counts: Record<Group, number>
  total: number
  filter: Filter
  onPick: (f: Filter) => void
  reduce: boolean
}) {
  const present = GROUPS.filter((g) => counts[g.key] > 0)
  return (
    <div className="rounded-[16px] border border-outline/60 bg-white p-5">
      <h2 className="mb-4 font-display text-lg font-semibold">How the class is reading</h2>
      <div className="flex h-11 w-full gap-1 overflow-hidden rounded-[10px]" role="group" aria-label="Results across the class">
        {present.map((g, i) => {
          const dim = filter !== 'all' && filter !== g.key
          return (
            <motion.button
              key={g.key}
              type="button"
              onClick={() => onPick(filter === g.key ? 'all' : g.key)}
              aria-pressed={filter === g.key}
              aria-label={`${g.label}: ${counts[g.key]} of ${total}`}
              style={{ flexGrow: counts[g.key], flexBasis: 0, transformOrigin: 'left' }}
              initial={reduce ? false : { scaleX: 0 }}
              animate={{ scaleX: 1, opacity: dim ? 0.3 : 1 }}
              transition={{ scaleX: { duration: 0.45, delay: i * 0.05, ease: EASE }, opacity: { duration: 0.15 } }}
              className={`min-w-6 ${g.bar} focus-visible:outline-offset-[-3px]`}
            />
          )
        })}
      </div>
      <ul className="mt-4 flex flex-wrap gap-x-6 gap-y-2">
        {GROUPS.map((g) => (
          <li key={g.key}>
            <button
              type="button"
              onClick={() => onPick(filter === g.key ? 'all' : g.key)}
              className={`flex items-center gap-2 text-sm ${counts[g.key] === 0 ? 'text-ink-muted/60' : 'text-ink hover:text-primary'}`}
            >
              <RiskMark level={g.level} size={10} />
              <span className="font-bold">{g.label}</span>
              <span className="tabular text-ink-muted">{counts[g.key]}</span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}

/** What needs the teacher next: children with items in the verify queue. */
function NeedsYou({ rows }: { rows: ClassRow[] }) {
  return (
    <div className="rounded-[16px] border border-outline/60 bg-white p-5">
      <h2 className="mb-3 font-display text-lg font-semibold">Needs your check</h2>
      {rows.length === 0 ? (
        <p className="flex items-center gap-2 text-ink-muted">
          <CheckCircleIcon size={20} weight="fill" className="text-primary" aria-hidden />
          Nothing waiting. Every result is final.
        </p>
      ) : (
        <ul className="-mx-2">
          {rows.slice(0, 5).map((r) => (
            <li key={r.id}>
              <Link
                to={`/teacher/child/${r.id}`}
                className="group flex items-center justify-between gap-3 rounded-[10px] px-2 py-2 hover:bg-accent-container"
              >
                <span className="font-display font-semibold">{r.code}</span>
                <span className="tabular flex items-center gap-2 text-sm text-ink-muted">
                  {r.pending_verify} to check
                  <ArrowRightIcon size={16} className="transition-transform duration-150 group-hover:translate-x-0.5 group-hover:text-primary" aria-hidden />
                </span>
              </Link>
            </li>
          ))}
          {rows.length > 5 && <li className="px-2 pt-1 text-sm text-ink-muted">and {rows.length - 5} more in the table</li>}
        </ul>
      )}
    </div>
  )
}

function SkeletonRows() {
  return (
    <>
      {Array.from({ length: 4 }, (_, i) => (
        <tr key={i} className="border-b border-outline/30 last:border-0" aria-hidden>
          {[40, 20, 56, 64, 120, 48, 16].map((w, j) => (
            <td key={j} className="px-4 py-4">
              <span className="block h-3.5 animate-pulse rounded-full bg-surface-high motion-reduce:animate-none" style={{ width: w }} />
            </td>
          ))}
        </tr>
      ))}
    </>
  )
}

function EmptyClass() {
  return (
    <section className="mb-8 grid items-center gap-8 rounded-[16px] border border-outline/60 bg-white p-8 md:grid-cols-[1fr_auto]">
      <div>
        <h2 className="font-display text-2xl font-semibold">No one screened yet</h2>
        <p className="mt-2 max-w-[55ch] text-ink-muted">
          Give a phone to a child, pick a child code (no names), and Akshar walks them through letters, words, made-up words and a short story in
          Hindi and English. Results appear here as soon as the reading ends.
        </p>
        <Link
          to="/child"
          className="mt-5 inline-flex items-center gap-2 rounded-[12px] bg-primary px-4 py-2.5 font-bold text-on-primary hover:bg-primary/90 active:scale-[0.98]"
        >
          <MicrophoneIcon size={18} aria-hidden /> Screen the first child
        </Link>
      </div>
      <div className="hidden gap-2 md:grid">
        {GROUPS.slice(0, 4).map((g) => (
          <RiskBadge key={g.key} level={g.level} label={RISK[g.level].short} />
        ))}
      </div>
    </section>
  )
}
