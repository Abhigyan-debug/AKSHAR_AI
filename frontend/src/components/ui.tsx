import { CircleIcon, HourglassMediumIcon, InfoIcon, WarningCircleIcon } from '@phosphor-icons/react'
import type { ButtonHTMLAttributes, ReactNode } from 'react'
import type { RiskLevel } from '../api'
import { RISK } from '../lib/labels'

/** The 🟢🔵🟡🔴⏳ result marks, drawn as icons in the risk colour. */
export function RiskMark({ level, size = 12 }: { level: RiskLevel; size?: number }) {
  const r = RISK[level]
  if (level === 'pending' || level === 'provisional') return <HourglassMediumIcon size={size + 2} weight="bold" className={r.color} aria-hidden />
  return <CircleIcon size={size} weight="fill" className={r.color} aria-hidden />
}

export function RiskBadge({ level, label, size = 'md' }: { level: RiskLevel | null; label?: string; size?: 'md' | 'lg' }) {
  if (!level) return <span className="text-sm text-ink-muted">Not screened</span>
  const r = RISK[level]
  const pad = size === 'lg' ? 'px-4 py-2 text-base' : 'px-3 py-1 text-sm'
  return (
    <span className={`inline-flex items-center gap-2 rounded-full border font-bold ${pad} ${r.bg} ${r.color}`}>
      <RiskMark level={level} size={size === 'lg' ? 14 : 11} />
      {label ?? r.short}
    </span>
  )
}

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger'
const VARIANTS: Record<Variant, string> = {
  primary: 'bg-primary text-on-primary hover:bg-primary/90 disabled:bg-primary/40',
  secondary: 'border border-primary text-primary hover:bg-primary-container disabled:opacity-40',
  ghost: 'text-ink-muted hover:bg-surface-container disabled:opacity-40',
  danger: 'border border-risk-specialist/40 text-risk-specialist hover:bg-risk-specialist/10 disabled:opacity-40',
}

export function Button({
  variant = 'primary',
  className = '',
  children,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; children: ReactNode }) {
  return (
    <button
      {...rest}
      className={`inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-[12px] px-4 py-2 font-bold transition-[background-color,transform] duration-150 active:scale-[0.98] ${VARIANTS[variant]} ${className}`}
    >
      {children}
    </button>
  )
}

export function Card({ title, children, className = '', right }: { title?: ReactNode; children: ReactNode; className?: string; right?: ReactNode }) {
  return (
    <section className={`rounded-[16px] border border-outline/60 bg-white p-5 ${className}`}>
      {(title || right) && (
        <div className="mb-3 flex items-center justify-between gap-3">
          {title && <h2 className="font-display text-lg font-semibold">{title}</h2>}
          {right}
        </div>
      )}
      {children}
    </section>
  )
}

export function Disclaimer({ text }: { text?: string }) {
  return (
    <p className="flex items-start gap-2 rounded-[12px] bg-surface-container px-4 py-3 text-sm text-ink-muted">
      <InfoIcon size={18} className="mt-0.5 shrink-0" aria-hidden />
      {text ?? 'Screener, not a diagnosis. Thresholds are illustrative and not clinically validated, for demo use.'}
    </p>
  )
}

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex items-center gap-3 text-ink-muted" role="status">
      <span className="h-5 w-5 animate-spin rounded-full border-2 border-primary border-t-transparent motion-reduce:animate-none" />
      {label}
    </div>
  )
}

export function ErrorBox({ error }: { error: unknown }) {
  const message = error instanceof Error ? error.message : String(error)
  return (
    <p role="alert" className="flex items-start gap-2 rounded-[12px] border border-risk-specialist/40 bg-risk-specialist/5 px-4 py-3 text-risk-specialist">
      <WarningCircleIcon size={20} className="mt-0.5 shrink-0" aria-hidden />
      {message}
    </p>
  )
}
