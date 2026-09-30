import { getToken, signOut } from './lib/auth'
import type { PracticeContent } from './practice/meta'

// Typed client for the FastAPI backend (backend/app/routes). Shapes mirror
// store.result_view / store.report_view / routes.*.

export type Lang = 'hi' | 'en'
export type Section = 'A' | 'B' | 'C' | 'D' | 'E'
export type Tap = 'correct' | 'incorrect' | 'skipped'
export type RiskLevel =
  | 'low_risk'
  | 'english_exposure_gap'
  | 'reading_support'
  | 'hindi_support'
  | 'specialist_check'
  | 'provisional'
  | 'pending'

export interface Child {
  id: number
  code: string
  grade: number
  home_lang: string
  created_at: string
}

export interface TestItem {
  id: string
  section: Section
  text: string
  prompt?: string
  is_nonword: boolean
  near_real: string | null
  accepted_variants: string[]
  scoring: 'auto' | 'manual'
  grade: number
  tags: string[]
  word_count?: number
}

export interface TestBank {
  lang: Lang
  version: number
  note: string
  items: TestItem[]
}

export interface Session {
  id: number
  child_id: number
  status: 'in_progress' | 'finished'
  include_sound_game: boolean
  created_at: string
}

export interface ErrorLabel {
  type: string
  target: string | null
  heard: string | null
  detail: string
  low_confidence: boolean
  source: 'rules' | 'llm'
}

export interface WordPair {
  kind: 'match' | 'sub' | 'del' | 'ins'
  target: string | null
  heard: string | null
}

export interface ItemResult {
  id: number
  item_id: string
  lang: Lang
  section: Section
  text: string | null
  prompt: string | null
  is_nonword: boolean
  status: 'auto' | 'teacher_verify' | 'manual'
  verified: boolean
  live_tap: Tap | null
  awaiting_verification: boolean
  transcript: string
  correct: boolean | null
  suggested_correct: boolean
  skipped: boolean
  errors: ErrorLabel[]
  pairs: WordPair[]
  words_correct: number
  words_total: number
  confidence: { avg_logprob: number | null; no_speech_prob: number | null; reasons: string[] }
  timing: {
    start_latency_s: number | null
    duration_s: number | null
    hesitation: boolean
    slow_start: boolean
    slow_decoding: boolean
  }
  audio_url: string | null
}

export interface LanguageMetrics {
  lang: Lang
  accuracy: Record<'A' | 'B' | 'C' | 'E', number | null>
  coverage: Record<'A' | 'B' | 'C' | 'E', number>
  wcpm: number | null
  wcpm_min: number
  lexicalizations: number
  lexicalization_examples: string[]
  timing_rate: number
  weighted_error_score: number
  error_counts: Record<string, number>
  pending_sections: string[]
  pending: boolean
  weak: boolean
  weak_reasons: string[]
}

export interface Breakdown {
  items: number
  auto_pct: number
  teacher_verify_pct: number
  live_tap_pct: number
  pending_verify: number
}

export interface Report {
  risk_level: RiskLevel
  emoji: string
  label: string
  reasons: string[]
  metrics: Record<Lang, LanguageMetrics>
  scoring_breakdown: Record<string, Breakdown>
  teacher_summary: string
  next_step: string
  summary_source: 'llm' | 'template' | ''
  summary_stale: boolean
  parent_token: string
  updated_at: string
}

export interface ChildReport {
  child: Child
  session: Session | null
  report: Report | null
  items: ItemResult[]
  disclaimer: string
}

export interface ClassRow extends Child {
  session_id: number | null
  session_status: Session['status'] | null
  tested_at: string | null
  items_recorded: number
  pending_verify: number
  risk_level: RiskLevel | null
  emoji: string | null
  label: string | null
  summary_stale: boolean
}

export interface ParentView {
  ready: boolean
  grade: number
  risk_level: RiskLevel
  label_hi: string
  summary_hi: string
  tips_hi: string[]
  help_hi: string[]
  show_help: boolean
  disclaimer_hi: string
  practice: string[] // game ids, the child's own error pattern first
}

const BASE = (import.meta.env.VITE_API_BASE as string | undefined)?.replace(/\/$/, '') ?? ''

/** Absolute URL for a backend path such as "/api/audio/3". */
export function apiUrl(path: string): string {
  return `${BASE}${path}`
}

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

/** Called when the API says the teacher token is missing or expired. */
let onUnauthorized: () => void = () => {}
export function setUnauthorizedHandler(fn: () => void) {
  onUnauthorized = fn
}

function withAuth(init?: RequestInit): RequestInit {
  const token = getToken()
  if (!token) return init ?? {}
  const headers = new Headers(init?.headers)
  headers.set('Authorization', `Bearer ${token}`)
  return { ...init, headers }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(apiUrl(path), withAuth(init))
  if (res.status === 401 && !path.startsWith('/api/auth/')) {
    signOut()
    onUnauthorized()
  }
  if (!res.ok) {
    let message = `${res.status} ${res.statusText}`
    try {
      const body = await res.json()
      if (typeof body.detail === 'string') message = body.detail
      else if (Array.isArray(body.detail)) message = body.detail.map((d: { msg: string }) => d.msg).join('; ')
    } catch {
      /* not JSON */
    }
    throw new ApiError(res.status, message)
  }
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

function json(method: string, body: unknown): RequestInit {
  return { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }
}

/** Audio clips need the teacher token, so they are fetched rather than linked. */
export async function fetchAudio(path: string): Promise<Blob> {
  const res = await fetch(apiUrl(path), withAuth())
  if (!res.ok) throw new ApiError(res.status, 'Could not load the clip')
  return res.blob()
}

export const api = {
  login: (pin: string) => request<{ token: string; expires_at: number }>('/api/auth/login', json('POST', { pin })),
  listChildren: () => request<Child[]>('/api/children'),
  createChild: (code: string, grade: number, home_lang: string) =>
    request<Child>('/api/children', json('POST', { code, grade, home_lang })),
  getTest: (lang: Lang) => request<TestBank>(`/api/tests/${lang}`),
  createSession: (child_id: number, include_sound_game: boolean) =>
    request<Session>('/api/sessions', json('POST', { child_id, include_sound_game })),
  uploadAudio: (sessionId: number, itemId: string, audio: Blob, filename: string, liveTap?: Tap) => {
    const form = new FormData()
    form.append('file', audio, filename)
    if (liveTap) form.append('live_tap', liveTap)
    return request<ItemResult>(`/api/sessions/${sessionId}/items/${itemId}/audio`, { method: 'POST', body: form })
  },
  finishSession: (sessionId: number) =>
    request<{ session: Session; report: Report }>(`/api/sessions/${sessionId}/finish`, { method: 'POST' }),
  childReport: (childId: number) => request<ChildReport>(`/api/children/${childId}/report`),
  decide: (resultId: number, decision: Tap, words_correct?: number) =>
    request<{ result: ItemResult; report: Report | null }>(
      `/api/results/${resultId}`,
      json('PATCH', words_correct === undefined ? { decision } : { decision, words_correct }),
    ),
  classSummary: () => request<ClassRow[]>('/api/class/summary'),
  deleteAudio: (clipId: number) => request<void>(`/api/audio/${clipId}`, { method: 'DELETE' }),
  deleteChildAudio: (childId: number) => request<void>(`/api/children/${childId}/audio`, { method: 'DELETE' }),
  parent: (token: string) => request<ParentView>(`/api/parent/${token}`),
  practice: () => request<PracticeContent>('/api/practice'),
  deleteChild: (childId: number) => request<void>(`/api/children/${childId}`, { method: 'DELETE' }),
  newParentLink: (sessionId: number) =>
    request<{ parent_token: string }>(`/api/sessions/${sessionId}/parent-link`, { method: 'POST' }),
}
