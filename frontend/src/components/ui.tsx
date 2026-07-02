import { useEffect, useRef, useState } from 'react'
import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode, TextareaHTMLAttributes } from 'react'

const buttonStyles = {
  primary:
    'rounded-lg bg-accent px-4 py-2 font-heading text-sm font-bold text-white transition-colors hover:bg-accent-dark disabled:opacity-60',
  ghost:
    'rounded-lg border border-line bg-cream px-4 py-2 font-heading text-sm font-bold text-ink transition-colors hover:border-accent disabled:opacity-60',
  danger:
    'rounded-lg border border-accent px-4 py-2 font-heading text-sm font-bold text-accent transition-colors hover:bg-accent hover:text-white disabled:opacity-60',
}

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: keyof typeof buttonStyles
}

export function Button({ variant = 'primary', className = '', ...props }: ButtonProps) {
  return <button type="button" className={`${buttonStyles[variant]} ${className}`} {...props} />
}

/** Destructive action with an inline two-click confirm (no browser dialog). */
export function ConfirmButton({
  label,
  onConfirm,
  className = '',
}: {
  label: string
  onConfirm: () => void
  className?: string
}) {
  const [armed, setArmed] = useState(false)
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined)

  useEffect(() => () => clearTimeout(timer.current), [])

  const handleClick = () => {
    if (armed) {
      clearTimeout(timer.current)
      setArmed(false)
      onConfirm()
    } else {
      setArmed(true)
      timer.current = setTimeout(() => setArmed(false), 3000)
    }
  }

  return (
    <Button variant="danger" className={className} onClick={handleClick}>
      {armed ? 'Confirm?' : label}
    </Button>
  )
}

const fieldStyles =
  'w-full rounded-lg border border-line bg-cream px-3 py-2 text-sm text-ink outline-none transition-colors focus:border-accent'

export function Input(props: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={fieldStyles} {...props} />
}

export function TextArea(props: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea rows={3} className={fieldStyles} {...props} />
}

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 block font-heading text-xs font-bold uppercase tracking-wide text-ink/60">
        {label}
      </span>
      {children}
    </label>
  )
}

export function Card({ className = '', children }: { className?: string; children: ReactNode }) {
  return (
    <section className={`rounded-[15px] border border-accent bg-cream p-6 shadow-md ${className}`}>
      {children}
    </section>
  )
}

export function ErrorNote({ message }: { message: string | null }) {
  if (!message) return null
  return <p className="mt-3 text-sm text-accent">{message}</p>
}

const chipStyles: Record<string, { label: string; className: string }> = {
  new: { label: 'New', className: 'bg-parchment text-ink/60' },
  recording: { label: '● Recording', className: 'bg-accent text-white animate-pulse' },
  transcribing: { label: 'Transcribing…', className: 'bg-accent/15 text-accent animate-pulse' },
  transcribed: { label: 'Transcribed', className: 'bg-heading/15 text-heading' },
  error: { label: 'Error', className: 'bg-accent text-white' },
}

export function StatusChip({ status }: { status: string }) {
  const chip = chipStyles[status] ?? { label: status, className: 'bg-parchment text-ink/60' }
  return (
    <span
      className={`rounded-full px-3 py-1 font-heading text-xs font-bold uppercase tracking-wide ${chip.className}`}
    >
      {chip.label}
    </span>
  )
}
