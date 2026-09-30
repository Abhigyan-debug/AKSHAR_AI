import type { RiskLevel } from '../api'

export const RISK: Record<RiskLevel, { emoji: string; short: string; color: string; bg: string }> = {
  low_risk: { emoji: '🟢', short: 'Low risk', color: 'text-risk-low', bg: 'bg-risk-low/10 border-risk-low/30' },
  english_exposure_gap: {
    emoji: '🔵',
    short: 'English exposure gap',
    color: 'text-risk-english-gap',
    bg: 'bg-risk-english-gap/10 border-risk-english-gap/30',
  },
  reading_support: {
    emoji: '🟡',
    short: 'Needs reading support',
    color: 'text-risk-support',
    bg: 'bg-risk-support/10 border-risk-support/30',
  },
  hindi_support: {
    emoji: '🟡',
    short: 'Needs Hindi reading support',
    color: 'text-risk-support',
    bg: 'bg-risk-support/10 border-risk-support/30',
  },
  specialist_check: {
    emoji: '🔴',
    short: 'Needs specialist check',
    color: 'text-risk-specialist',
    bg: 'bg-risk-specialist/10 border-risk-specialist/30',
  },
  provisional: {
    emoji: '⏳',
    short: 'Provisional',
    color: 'text-risk-pending',
    bg: 'bg-risk-pending/10 border-risk-pending/30',
  },
  pending: { emoji: '⏳', short: 'Pending check', color: 'text-risk-pending', bg: 'bg-risk-pending/10 border-risk-pending/30' },
}

export const SECTION_LABELS: Record<string, string> = { A: 'Letters', B: 'Words', C: 'Nonwords', D: 'Passage', E: 'Sound game' }

export const ERROR_LABELS: Record<string, string> = {
  matra_confusion: 'matra',
  visual_akshara_swap: 'look-alike letter',
  aspiration_error: 'aspiration',
  conjunct_error: 'conjunct (low confidence)',
  transposition: 'order swapped',
  omission: 'omission',
  addition: 'addition',
  lexicalization: 'read as a real word',
  first_letter_guess: 'first-letter guess',
  letter_reversal: 'letter reversal',
  word_reversal: 'word reversal',
  vowel_error: 'vowel',
  hesitation: 'hesitation',
  slow_start: 'slow start',
  slow_decoding: 'slow decoding',
  self_correction: 'self-correction',
  unclassified: 'other',
}
